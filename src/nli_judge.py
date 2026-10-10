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


def format_evidence(passages: List[Dict], max_chars: int = 2000) -> str:
    """Concatenate retrieved passages into an evidence block, capped to max_chars."""
    if not passages:
        return "(No relevant passages found.)"
    parts, total = [], 0
    for p in passages:
        tag = f"[{p['lang'].upper()}] [{p['id']}]"
        chunk = f"{tag}\n{p['text']}"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts) if parts else "(No relevant passages found.)"


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_LABEL_KEY_RE = re.compile(
    r'"label"\s*:\s*\(?\s*"?(entailment|neutral|contradiction|0|1|2)\b',
    re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(
    r"\s*(entailment|neutral|contradiction)\b", re.IGNORECASE)


def parse_nli_response(raw: str) -> Dict:
    """Parse an LLM reply into {label, reasoning, evidence_snippet}.

    Strict by design (2026-10-09): a reply yields a label only if
      (a) it contains a JSON object with a valid "label", or
      (b) a "label": <value> pair can still be recovered from broken JSON, or
      (c) the reply starts with a bare label word.
    The old substring keyword fallback was removed: it let prose that merely
    *mentions* a label word masquerade as a prediction (see test_judge.py).
    Anything else returns label=None + error="unparseable_response" and the
    harness must report it as a failure, never score it as Neutral.
    Numeric codes ("0"/"1"/"2") are accepted via labels.normalise_label.
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

    m2 = _LABEL_KEY_RE.search(text) or _LEADING_LABEL_RE.match(text)
    if m2:
        label = normalise_label(m2.group(1))
        if label:
            return {"label": label, "reasoning": text[:200],
                    "evidence_snippet": ""}
    return {"label": None,
            "reasoning": f"Unparseable response: {text[:120]}",
            "evidence_snippet": "",
            "error": "unparseable_response"}


class MlxJudge:
    """Local NLI judge backed by mlx_lm (Apple Silicon)."""

    def __init__(self, model_id: str = MLX_MODEL, max_tokens: int = 400,
                 temperature: float = 0.1):
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
        self.max_tokens = max_tokens
        self.temperature = temperature
        print("MLX model loaded.")

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        evidence = format_evidence(passages)
        user_msg = USER_TEMPLATE.format(claim=claim, evidence=evidence)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        import requests
        self.model = model
        self.base_url = base_url
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
        evidence = format_evidence(passages)
        user_msg = USER_TEMPLATE.format(claim=claim, evidence=evidence)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "options": {"temperature": 0.1},
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
                 timeout: float = JUDGE_TIMEOUT_S):
        try:
            import requests
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "LLM_BACKEND=openai needs the 'requests' package "
                "(pinned in requirements.txt)") from e
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
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
        if not any(self.model in s or s in self.model or
                   self.model.rsplit("/", 1)[-1] in s for s in served):
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
                if isinstance(item, str):
                    ids.append(item)
                elif isinstance(item, dict) and "id" in item:
                    ids.append(item["id"])
        return ids

    def judge(self, claim: str, passages: List[Dict]) -> Dict:
        evidence = format_evidence(passages)
        user_msg = USER_TEMPLATE.format(claim=claim, evidence=evidence)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
            "max_tokens": 400,
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


def build_judge(backend: str = None):
    backend = backend or LLM_BACKEND
    if backend == "mlx":
        return MlxJudge()
    if backend == "ollama":
        return OllamaJudge()
    if backend == "openai":
        return OpenAICompatJudge()
    if backend == "lexical":
        print("Using LEXICAL fallback judge (no LLM) — plumbing smoke test only")
        return LexicalJudge()
    raise ValueError(f"unknown LLM_BACKEND: {backend}")

