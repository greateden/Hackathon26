"""
NLI Judge: Classify claim-vs-evidence relationship (entailment/contradiction/neutral).

Backends (selected via LLM_BACKEND in config.py; default is "lexical"):
  - "lexical": no-LLM keyword heuristic, plumbing smoke tests only.
  - "mlx":     mlx_lm.generate against a local MLX model (Apple Silicon).
  - "ollama":  Ollama HTTP API (requires Ollama installed and running).
  - "openai":  OpenAI-compatible HTTP API (/v1/chat/completions), used to
               reach mlx_lm.server on the host from anywhere, incl. Docker.
"""
import json
import re
from typing import Dict, List

from config import (
    LLM_BACKEND, OLLAMA_MODEL, OLLAMA_BASE_URL,
    MLX_MODEL, OPENAI_BASE_URL, JUDGE_MODEL, JUDGE_TIMEOUT_S,
    PROMPT_CONFIG,
)
from labels import normalise_label


SYSTEM_PROMPT = (
    "You are a document-grounded NLI system. Determine the relationship between a CLAIM "
    "and EVIDENCE drawn from Swiss voting booklets.\n\n"
    "Labels:\n"
    "- entailment: EVIDENCE clearly supports the CLAIM.\n"
    "- contradiction: EVIDENCE contradicts the CLAIM.\n"
    "- neutral: EVIDENCE does not give enough information either way.\n\n"
    "Judge ONLY using the given evidence, not outside knowledge. "
    "If the evidence is in another language, translate and compare meaning.\n"
    "Reply with EXACTLY this JSON and nothing else:\n"
    '{"label": "entailment"|"contradiction"|"neutral", '
    '"reasoning": "one short sentence", '
    '"evidence_snippet": "verbatim key sentence(s) from the evidence"}'
)

USER_TEMPLATE = (
    "## Claim\n{claim}\n\n"
    "## Evidence from the official voting booklet\n{evidence}\n\n"
    "## Task\nBased ONLY on the evidence above, classify the claim as "
    "entailment, contradiction, or neutral. Reply with JSON only."
)

# Stricter label definitions (ablation config "strict", 2026-10-10).
# Motivation (offline analysis of the two dev runs): the judge over-predicts
# entailment (precision 0.39 retrieve / 0.35 oracle) and collapses
# contradiction into entailment even when the denial is inside the sent
# evidence - i.e. topic overlap is being read as support. This prompt keeps
# the response format identical (label-first JSON) so the ablation isolates
# the wording, not the output schema.
STRICT_SYSTEM_PROMPT = (
    "You are a document-grounded NLI system. Decide whether EVIDENCE from a "
    "Swiss federal voting booklet supports, contradicts, or is silent about "
    "a CLAIM.\n\n"
    "Labels (apply exactly):\n"
    "- entailment: the EVIDENCE, read as a whole, states or entails what "
    "the CLAIM asserts. Sharing the same topic is NOT entailment.\n"
    "- contradiction: the EVIDENCE explicitly denies, rejects or states the "
    "opposite of what the CLAIM asserts.\n"
    "- neutral: everything else. If the EVIDENCE does not say enough either "
    "way, answer neutral - never entailment, never contradiction.\n\n"
    "Notes:\n"
    "- A booklet passage may describe the proposal or quote arguments from "
    "several sides. Describing a position is not endorsing it: judge only "
    "whether the passage as a whole confirms or denies the CLAIM.\n"
    "- Many claims are indirect (\"the Federal Council recommends "
    "that...\", \"according to the message...\"): check that the attributed "
    "statement actually occurs in the EVIDENCE.\n"
    "- Judge ONLY using the given evidence, not outside knowledge. If the "
    "evidence is in another language, translate and compare meaning.\n"
    "Reply with EXACTLY this JSON and nothing else:\n"
    '{"label": "entailment"|"contradiction"|"neutral", '
    '"reasoning": "one short sentence", '
    '"evidence_snippet": "verbatim key sentence(s) from the evidence"}'
)

# Prompt/judging configurations (ablation study 2026-10-10, see AGENTS.md).
#   evidence: "drop"  = original format_evidence behaviour (whole chunks are
#                       dropped once the cap is hit) - unchanged default.
#             "fill"  = chunks are truncated to fit instead of dropped.
#   window:   eval_nli oracle mode replaces head truncation of the gold
#             reference_string with a claim-lexical sliding window.
# temperature/max_tokens are passed to the endpoint per request.
PROMPT_CONFIGS = {
    "baseline": {
        "system": SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.1, "max_tokens": 400,
        "evidence": "drop", "window": False,
    },
    "t0": {
        "system": SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.0, "max_tokens": 400,
        "evidence": "drop", "window": False,
    },
    "strict": {
        "system": STRICT_SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.0, "max_tokens": 400,
        "evidence": "drop", "window": False,
    },
    "select": {
        "system": SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.0, "max_tokens": 400,
        "evidence": "fill", "window": True,
    },
    # 2x2 de-confounding arms (factorial step, 2026-10-10): each isolates ONE
    # factor of `select`. Equivalence facts verified offline by
    # diag_evidence_ablation.py, not assumed: `window` is applied only in
    # eval_nli.oracle_evidence, so in retrieve mode fill_only renders
    # byte-identically to `select` and window_only to `t0`; in oracle mode a
    # single gold chunk (<=1900 chars) always fits format_evidence's 2000-char
    # cap, so the style factor is inert - fill_only renders identically to
    # `t0`, window_only to `select`. Re-running a cell whose twin is already
    # recorded is redundant inference, not new evidence; these arms exist to
    # express the factorial cleanly and to let test_judge.py guard the
    # equivalences above.
    "fill_only": {
        "system": SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.0, "max_tokens": 400,
        "evidence": "fill", "window": False,
    },
    "window_only": {
        "system": SYSTEM_PROMPT, "user": USER_TEMPLATE,
        "temperature": 0.0, "max_tokens": 400,
        "evidence": "drop", "window": True,
    },
}


def get_prompt_config(name: str = None) -> Dict:
    name = name or PROMPT_CONFIG
    if name not in PROMPT_CONFIGS:
        raise ValueError(f"unknown PROMPT_CONFIG {name!r}; "
                         f"valid: {sorted(PROMPT_CONFIGS)}")
    return PROMPT_CONFIGS[name]


def format_evidence(passages: List[Dict], max_chars: int = 2000,
                    style: str = "drop") -> str:
    """Concatenate retrieved passages into an evidence block, capped to max_chars.

    style="drop" is the original behaviour (kept byte-identical for the
    baseline config): a chunk that does not fit is dropped, together with
    everything after it. style="fill" truncates chunks to fit the remaining
    budget instead, so long passages still contribute their leading part.
    """
    if not passages:
        return "(No relevant passages found.)"
    parts, total = [], 0
    for p in passages:
        tag = f"[{p['lang'].upper()}] [{p['id']}]"
        sep = 2 if parts else 0  # the "\n\n" join costs 2 chars
        chunk = f"{tag}\n{p['text']}"
        if total + sep + len(chunk) > max_chars:
            if style != "fill":
                break
            room = max_chars - total - sep - len(tag) - 2  # \n + ellipsis
            if room < 40:  # too little room to add anything meaningful
                break
            chunk = f"{tag}\n{p['text'][:room - 1]}\u2026"
        parts.append(chunk)
        total += sep + len(chunk)
    return "\n\n".join(parts) if parts else "(No relevant passages found.)"


def build_chat(pconf: Dict, claim: str, passages: List[Dict]):
    """Render (system, user) messages from a prompt config (testable seam)."""
    evidence = format_evidence(passages, style=pconf.get("evidence", "drop"))
    user_msg = pconf["user"].format(claim=claim, evidence=evidence)
    return pconf["system"], user_msg



_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
# Broken-JSON recovery (2026-10-10 audit fix): capture the COMPLETE value
# token, never a prefix. The old pattern matched the "1" inside "1.5" (and
# "neutral" inside "neutral-ish"), so a float/garbage label decoded as a
# fabricated prediction. Group 1 = exact quoted string value, group 2 = bare
# numeric/bool literal; both go through strict normalise_label.
_LABEL_KEY_RE = re.compile(
    r'"label"\s*:\s*"([^"]*)"'
    r'|"label"\s*:\s*(true|false|null|[0-9]+(?:\.[0-9]+)?)(?![0-9.\w])',
    re.IGNORECASE)
# Leading-label rule, tightened 2026-10-11. `\b` matched at a hyphen or a
# slash too, so a reply that REFUSED TO CHOOSE decoded as its leading word:
# "neutral-ish"/"contradiction-like" -> neutral/contradiction and
# "entailment/neutral"/"neutral/contradiction" -> entailment/neutral. Those
# are not verdicts, and scoring them against a gold label invents accuracy.
# The lookahead therefore ends the token at a joiner (hyphen, slash, tilde,
# pipe, backslash, or any word char). Delimiters that genuinely end a token
# -- ".", ":", ";", ",", newline, space -- still pass, so a delimited
# explanation ("Neutral: insufficient evidence") stays a prediction. A reply
# that spells the alternative out with spaces ("neutral or contradiction")
# still decodes as its leading word: at that boundary no rule separates a
# refusal from a legitimate explanation, and over-rejecting would silently
# move the measurement the other way.
_LEADING_LABEL_RE = re.compile(
    r"\s*(entailment|neutral|contradiction)(?![\w/~\\|-])", re.IGNORECASE)


def parse_nli_response(raw: str) -> Dict:
    """Parse an LLM reply into {label, reasoning, evidence_snippet}.

    Strict by design (2026-10-09): a reply yields a label only if
      (a) it contains a JSON object with a valid "label", or
      (b) a "label": <value> pair can still be recovered from broken JSON, or
      (c) the reply starts with a bare label word whose token ENDS there.
    The old substring keyword fallback was removed: it let prose that merely
    *mentions* a label word masquerade as a prediction (see test_judge.py).
    Anything else returns label=None + error="unparseable_response" and the
    harness must report it as a failure, never score it as Neutral.
    Numeric codes are accepted ONLY in strict form (labels.LABEL_PARSE_VERSION
    = "label-parse-v3-strict"): exact "0"/"1"/"2" strings or exact int codes;
    floats, booleans and castable junk decode to None. The broken-JSON
    recovery regex captures the COMPLETE value token, so "1.5" never
    prefix-matches back into a fabricated label, and since v3 the leading
    label word is held to the same rule: a token JOINED to something else
    ("neutral-ish", "entailment/neutral", "contradiction-like",
    "neutral/contradiction") is a refusal to choose, not a prediction, and
    decodes to None.
    Earlier dev runs (report §4.2/§4.3) used the v1 parser that accepted
    int()-castable values - attributable via this version tag.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    m = _JSON_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(0))
            label = normalise_label(obj.get("label"))
            if label:
                obj["label"] = label
                return obj
        except json.JSONDecodeError:
            pass

    m2 = _LABEL_KEY_RE.search(text)
    raw_label = None
    if m2:
        raw_label = (m2.group(1) if m2.group(1) is not None
                     else m2.group(2))
    if raw_label is None:
        m3 = _LEADING_LABEL_RE.match(text)
        if m3:
            raw_label = m3.group(1)
    if raw_label is not None:
        label = normalise_label(raw_label)
        if label:
            return {"label": label, "reasoning": text[:200],
                    "evidence_snippet": ""}
    return {"label": None,
            "reasoning": f"Unparseable response: {text[:120]}",
            "evidence_snippet": "",
            "error": "unparseable_response"}


class MlxJudge:
    """Local NLI judge backed by mlx_lm (Apple Silicon)."""

    def __init__(self, model_id: str = MLX_MODEL, max_tokens: int = None,
                 temperature: float = None, prompt_config: str = None):
        import mlx_lm
        from mlx_lm import load
        self.model_id = model_id
        print(f"Loading MLX model: {model_id}   (mlx-lm {mlx_lm.__version__})")
        print("           first load downloads weights from Hugging Face; "
              "subsequent runs are cached.")
        try:
            self.model, self.tokenizer = load(model_id)
        except (ValueError, ModuleNotFoundError) as e:
            msg = str(e)
            hint_lines = []
            if "not supported" in msg or "mlx_lm.models." in msg:
                m = re.search(r"Model type (\S+) not supported", msg)
                arch = m.group(1) if m else "unknown"
                hint_lines = [
                    "",
                    f"  Root cause: mlx-lm {mlx_lm.__version__} does not implement",
                    f"  the '{arch}' model architecture, so the downloaded weights",
                    "  cannot be loaded.",
                    "",
                    "  Fix (pick ONE):",
                    "    (a) upgrade mlx-lm to latest, which includes Apertus:",
                    "          pip3 install --upgrade mlx-lm",
                    "        then re-run ./run.sh",
                    "    (b) keep mlx-lm as-is and use a qwen2/llama model:",
                    "          ./run.sh mlx-community/Qwen2.5-3B-Instruct-4bit",
                    "          ./run.sh mlx-community/Qwen2.5-7B-Instruct-4bit",
                    "          ./run.sh mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
                    "",
                ]
            raise RuntimeError(
                f"Failed to load MLX model {model_id!r}: {msg}\n" + "\n".join(hint_lines)
            ) from e
        self.pconf = get_prompt_config(prompt_config)
        self.max_tokens = max_tokens or self.pconf["max_tokens"]
        self.temperature = (temperature if temperature is not None
                            else self.pconf["temperature"])
        print("MLX model loaded.")

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        sys_msg, user_msg = build_chat(self.pconf, claim, passages)
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False
        )
        sampler = make_sampler(temp=self.temperature)
        try:
            raw = generate(
                self.model, self.tokenizer, prompt=prompt,
                max_tokens=self.max_tokens, sampler=sampler, verbose=False,
            )
        except Exception as e:
            # Generation failures must be reported, never defaulted to a label.
            return {"label": None,
                    "reasoning": f"MLX generation failed: {e}",
                    "evidence_snippet": "", "error": str(e)}
        if isinstance(raw, tuple) and raw:
            raw = raw[0]  # older mlx-lm returned (text, response)
        elif not isinstance(raw, str):
            raw = getattr(raw, "text", None) or str(raw)
        return parse_nli_response(raw)


class OllamaJudge:
    """NLI judge via Ollama HTTP API."""

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL,
                 prompt_config: str = None):
        import requests
        self.model = model
        self.base_url = base_url
        self.pconf = get_prompt_config(prompt_config)
        self._requests = requests
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                names = [m["name"] for m in resp.json().get("models", [])]
                print(f"Ollama OK. Models: {names}")
            else:
                print(f"Ollama returned HTTP {resp.status_code}")
        except Exception as e:
            print(f"WARNING: cannot reach Ollama at {base_url}: {e}")

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        sys_msg, user_msg = build_chat(self.pconf, claim, passages)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            "options": {"temperature": self.pconf["temperature"]},
            "stream": False,
        }
        try:
            resp = self._requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=120
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"]
            return parse_nli_response(raw)
        except Exception as e:
            return {"label": None,
                    "reasoning": f"Ollama error: {e}",
                    "evidence_snippet": "", "error": str(e)}


class OpenAICompatJudge:
    """NLI judge via an OpenAI-compatible HTTP endpoint
    (/v1/chat/completions + /v1/models).

    Designed for mlx_lm.server serving the Apertus MLX checkpoint on the
    host (works unchanged from Docker via host.docker.internal), but speaks
    the generic OpenAI chat API, so any compatible server can be pointed at
    it via OPENAI_BASE_URL.

    Deliberate policy (2026-10-10): an unreachable endpoint or a model-identity
    mismatch at init RAISES. This backend exists to run genuine model
    inference; continuing without a verified endpoint would fabricate verdicts
    (see AGENTS.md: never quote non-model output as model quality). Per-call
    failures (timeout, HTTP error, unparseable reply) are recorded as
    error results (label=None), never defaulted to a label.
    """

    def __init__(self, model: str = JUDGE_MODEL,
                 base_url: str = OPENAI_BASE_URL,
                 timeout: float = JUDGE_TIMEOUT_S,
                 prompt_config: str = None):
        try:
            import requests
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "LLM_BACKEND=openai needs the 'requests' package "
                "(pinned in requirements.txt)") from e
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.pconf = get_prompt_config(prompt_config)
        self._requests = requests
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
            resp.raise_for_status()
            served = self._served_model_ids(resp.json())
        except Exception as e:
            raise RuntimeError(
                f"Apertus endpoint not reachable at {self.base_url}: {e!r}. "
                "Start the model server first - from the repo root:\n"
                "    make serve-apertus\n"
                "(or point OPENAI_BASE_URL at a running OpenAI-compatible "
                "endpoint). Refusing to fall back to the lexical baseline.") \
                from e
        if not served:
            raise RuntimeError(
                f"Endpoint {self.base_url} is up but /v1/models lists no "
                f"models; cannot verify the judge model identity "
                f"(expected {self.model!r}).")
        if self.model not in served:
            raise RuntimeError(
                f"Endpoint {self.base_url} serves {served}, which does not "
                f"match JUDGE_MODEL={self.model!r}. Verify the server "
                "identity and pass JUDGE_MODEL=<served id> if intentional.")
        self.served = served
        print(f"OpenAI-compatible endpoint OK: {self.base_url}; "
              f"served={served}")

    @staticmethod
    def _served_model_ids(payload) -> list:
        """Accept OpenAI-style {"data": [{"id": ...}]} or bare listings."""
        data = payload.get("data") if isinstance(payload, dict) else payload
        ids = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str) and item.strip():
                    ids.append(item)
                elif (isinstance(item, dict)
                      and isinstance(item.get("id"), str)
                      and item["id"].strip()):
                    ids.append(item["id"])
        return ids

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        sys_msg, user_msg = build_chat(self.pconf, claim, passages)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": self.pconf["temperature"],
            "max_tokens": self.pconf["max_tokens"],
            "stream": False,
        }
        try:
            resp = self._requests.post(
                f"{self.base_url}/v1/chat/completions", json=payload,
                timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            out = parse_nli_response(raw)
            usage = data.get("usage")
            if usage:
                out["usage"] = usage
            return out
        except Exception as e:
            return {"label": None,
                    "reasoning": f"Endpoint error ({type(e).__name__}): {e}",
                    "evidence_snippet": "", "error": str(e)}


class LexicalJudge:
    """
    No-LLM fallback: crude keyword polarity heuristic. Only useful for smoke-testing
    that the retrieval -> judge -> report plumbing works. NOT a real NLI classifier.
    Do not report these labels as evidence of model quality.
    """

    _NEG = (" lehnen ", " ablehnen ", "nicht ", " reject ", " refuse ",
            " widerspr", "ne pas ", "no ", " nicht zulässig")
    _POS = (" empfehlen", " accept", " unterstützt", "garanti", " unterst")

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        if not passages:
            return {"label": "neutral",
                    "reasoning": "no evidence retrieved",
                    "evidence_snippet": ""}
        claim_l = " " + claim.lower() + " "
        ev = " ".join(p["text"] for p in passages).lower()
        neg = sum(1 for t in self._NEG if t in ev)
        pos = sum(1 for t in self._POS if t in ev)
        label = "neutral"
        if neg > pos:
            # Contradiction heuristic: claim asserts what evidence negates.
            assertive = any(k in claim_l for k in
                            ("accept", "recommends accepting",
                             "supports", "increases", "is approved",
                             "reduces by 5 billion"))
            label = "contradiction" if assertive else "entailment"
        elif pos > 0:
            label = "entailment"
        top = passages[0]
        return {
            "label": label,
            "reasoning": f"LEXICAL heuristic only (no LLM). "
                         f"top hit sim={top['score']:.3f} from {top['id']}",
            "evidence_snippet": top["text"][:200],
        }


def build_judge(backend: str = None, prompt_config: str = None):
    backend = backend or LLM_BACKEND
    if backend == "mlx":
        return MlxJudge(prompt_config=prompt_config)
    if backend == "ollama":
        return OllamaJudge(prompt_config=prompt_config)
    if backend == "openai":
        return OpenAICompatJudge(prompt_config=prompt_config)
    if backend == "lexical":
        print("Using LEXICAL fallback judge (no LLM) — plumbing smoke test only")
        return LexicalJudge()
    raise ValueError(f"unknown LLM_BACKEND: {backend}")

