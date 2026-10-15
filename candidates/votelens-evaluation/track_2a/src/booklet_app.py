"""Submission application: one specified PDF and claim, with page citations.

Historical main.py / eval_e2e.py remain separate global-search experiments.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

from config import DATA_DIR, BOOKLET_PDF_DIR
from labels import LABEL_PARSE_VERSION, label_to_code
from nli_judge import SYSTEM_PROMPT, USER_TEMPLATE, parse_nli_response

MODEL = "swiss-ai/Apertus-v1.5-8B"
CSCS_MODEL = "swiss-ai/Apertus-v1.5-70B"
MLX_MODEL = "m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit"
OFFICIAL_MODELS = (MODEL, CSCS_MODEL)
LANGUAGES = ("de", "fr", "it")
FROZEN_PIPELINE = "dense-v1"
CANDIDATE_PIPELINE = "vote-aware-v1"

VOTE_INSTRUCTIONS = (
    "Resolve the specified vote against the supplied evidence, including translated "
    "proposal names. Set vote_status to recognised only if it identifies one proposal "
    "unambiguously; otherwise use ambiguous or unrecognised. Do not guess from the claim. "
    "Judge only that proposal. Keep the Federal Council, Parliament, proponents and "
    "opponents separate: disagreement between speakers does not contradict a claim "
    "about what one of them says. If the requested position is absent, use neutral."
)
CANDIDATE_OUTPUT_CONTRACT = (
    'Reply with exactly one JSON object and nothing else. It must contain every one of '
    'these six fields: label, reasoning, vote_status, vote_reference, evidence_status, '
    'and evidence_refs. Use exactly this structure: '
    '{"label":"entailment","reasoning":"one short sentence",'
    '"vote_status":"recognised","vote_reference":{"passage_id":"e1"},'
    '"evidence_status":"sufficient",'
    '"evidence_refs":[{"passage_id":"e2"}]}. '
    'Never omit any field. For a specified vote, vote_status must be recognised only if '
    'the evidence identifies one proposal unambiguously; otherwise use ambiguous or '
    'unrecognised. When recognised, vote_reference must select a supplied passage that '
    'establishes the proposal identity; otherwise it must be null. For a request without '
    'a specified vote, both vote_status and vote_reference must be null. vote_reference '
    'is separate from evidence_refs and is required even when the claim is neutral. '
    'evidence_status must be "sufficient" for entailment or '
    'contradiction, or "insufficient" for neutral. evidence_refs is a list such as '
    '[{"passage_id":"e2"}]. Select only passages that jointly justify the label '
    'for the claimed proposal and speaker, including necessary qualifications. '
    'Do not select a passage merely because it mentions the topic. For neutral, '
    'return an empty list. The application copies the selected source text directly; '
    'do not generate quotations. An optional start/end pair selects zero-based, '
    'end-exclusive character offsets within that passage; omit both to select '
    'the complete passage. If evidence is insufficient, never invent a label '
    'other than neutral or a source reference.'
)


def is_apertus_v15(model_id):
    """Accept only the explicitly supported official models or MLX conversion."""
    return model_id in OFFICIAL_MODELS + (MLX_MODEL,)


def token_preflight_mode():
    """'required' (default): /tokenize first, reported usage must match.

    'optional' = endpoint without /tokenize (including CSCS and mlx_lm.server). Input
    length is then not pre-rejected; a reply only counts when the server reports
    finish_reason='stop' plus valid token usage. This cannot independently detect
    a server silently dropping input; that requires exact token preflight.
    """
    return os.environ.get("LLM_TOKEN_PREFLIGHT", "required")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)


def candidate_json(text):
    """Parse candidate output, tolerating only one surplus final ``}``."""
    try:
        value = strict_json(text)
        recovered = False
    except json.JSONDecodeError:
        stripped = text.rstrip()
        if not stripped.endswith("}"):
            raise
        value = strict_json(stripped[:-1] + text[len(stripped):])
        recovered = True
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value, recovered


def detect_language(text):
    """Identify the booklet language from common function words."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    markers = {
        "de": {"aber", "auch", "das", "der", "die", "eine", "für", "mit", "nicht", "und"},
        "fr": {"avec", "dans", "des", "est", "les", "mais", "pas", "pour", "une", "que"},
        "it": {"che", "con", "del", "della", "gli", "non", "per", "sono", "una", "nel"},
    }
    counts = {lang: sum(word in vocabulary for word in words)
              for lang, vocabulary in markers.items()}
    language, score = max(counts.items(), key=lambda item: item[1])
    if score < 2 or list(counts.values()).count(score) > 1:
        raise ValueError("Could not identify booklet language as de, fr or it")
    return language


def load_booklet(spec, language=None):
    """Resolve a PDF path, cached PDF stem, or HTTPS URL; never read gold data."""
    if language is not None and language not in LANGUAGES:
        raise ValueError("booklet_language must be de, fr or it")
    source = str(spec)
    if source.startswith("https://"):
        import requests
        # A historical basename cache does not establish URL identity.
        pdf = DATA_DIR / "booklets" / "submission" / (digest(source.encode()) + ".pdf")
        if not pdf.exists():
            response = requests.get(source, timeout=90)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError("Specified URL did not return a PDF")
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(response.content)
    else:
        if urlparse(source).scheme and not Path(source).is_file():
            raise ValueError("Only HTTPS URLs, local PDF paths and cached PDF stems are supported")
        pdf = Path(source)
        if not pdf.is_file():
            if Path(source).name != source:
                raise ValueError("PDF path does not exist")
            pdf = BOOKLET_PDF_DIR / (source.removesuffix(".pdf") + ".pdf")
    body = pdf.read_bytes()
    if not body.startswith(b"%PDF"):
        raise ValueError("Specified file is not a PDF")
    # Always extract from the identified bytes. No stale global corpus/text cache.
    try:
        proc = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"],
                              capture_output=True, timeout=120)
    except FileNotFoundError as exc:
        raise RuntimeError("pdftotext required; use the Docker application") from exc
    if proc.returncode:
        raise ValueError("PDF extraction failed: " + proc.stderr.decode("utf-8", "replace")[:200])
    text = proc.stdout.decode("utf-8")
    pages = [{"page": i, "text": page.strip()} for i, page in enumerate(text.split("\f"), 1)
             if page.strip()]
    if not pages:
        raise ValueError("PDF has no extractable text; scanned PDFs need OCR (not implemented)")
    language = language or detect_language("\n".join(page["text"] for page in pages))
    return {"source": source, "sha256": digest(body), "language": language, "pages": pages}


def passages(booklet):
    # Preserve short text and sentence tails; every character belongs to a chunk.
    return [{"id": f"p{page['page']}-c{offset // 900 + 1}", "page": page["page"],
             "text": page["text"][offset:offset + 900], "lang": booklet["language"],
             "source": booklet["source"], "pdf_sha256": booklet["sha256"]}
            for page in booklet["pages"] for offset in range(0, len(page["text"]), 900)]


class BookletRetriever:
    def __init__(self):
        self.encoder = None
        self.indices = {}

    def retrieve(self, booklet, claim, top_k=5):
        import numpy as np
        from retriever import Retriever, LANG_TO_ADAPTER, cosine_sim_matrix
        if self.encoder is None:
            self.encoder = Retriever()
        key = (booklet["sha256"], booklet["language"])
        adapter = LANG_TO_ADAPTER[booklet["language"]]
        if key not in self.indices:
            records = passages(booklet)
            embeddings = self.encoder.encode([r["text"] for r in records], lang_code=adapter)
            self.indices[key] = records, embeddings
        records, embeddings = self.indices[key]
        query = self.encoder.encode([claim], lang_code=adapter)
        scores = cosine_sim_matrix(query, embeddings)
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [dict(records[i], source=booklet["source"], score=float(scores[i])) for i in order]


def evidence_payload(booklet, evidence):
    return "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in evidence)


def build_messages(claim, evidence, system_prompt=SYSTEM_PROMPT, *, vote=None,
                   pipeline_version=FROZEN_PIPELINE):
    if pipeline_version == CANDIDATE_PIPELINE:
        system_prompt = system_prompt.split("Reply with EXACTLY", 1)[0].rstrip()
        if vote is not None:
            system_prompt += "\n\n" + VOTE_INSTRUCTIONS
            evidence = "Specified vote (request metadata): " + json.dumps(vote, ensure_ascii=False) + "\n\n" + evidence
        system_prompt += "\n\n" + CANDIDATE_OUTPUT_CONTRACT
    return [{"role": "system", "content": system_prompt},
            {"role": "user", "content": USER_TEMPLATE.format(claim=claim, evidence=evidence)}]


def normalise_request(request, base_dir=None):
    """Map the official Beginner/Advanced shapes to the internal request."""
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    # Retain compatibility for the recorded experiment runners. The public CLI
    # uses the nested official shapes below.
    if isinstance(request.get("claim"), str):
        return dict(request, task=request.get("task", "advanced"))
    case_id = request.get("id")
    claim = request.get("claim")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("id must be a non-empty string")
    if not isinstance(claim, dict) or not isinstance(claim.get("text"), str):
        raise ValueError("claim.text must be a non-empty string")
    normalised = {"id": case_id, "claim": claim["text"], "task": None,
                  "pipeline_version": CANDIDATE_PIPELINE}
    if "language" in claim:
        normalised["claim_language"] = claim["language"]
    if "booklet" in request and "reference" in request:
        raise ValueError("request must contain booklet or reference, not both")
    if "booklet" in request:
        booklet = request["booklet"]
        if not isinstance(booklet, dict) or not isinstance(booklet.get("path"), str):
            raise ValueError("booklet.path must identify one PDF")
        source = booklet["path"]
        if not urlparse(source).scheme:
            path = Path(source)
            if base_dir is not None and not path.is_absolute():
                path = Path(base_dir) / path
            source = str(path)
        normalised.update(task="advanced", booklet=source, vote=request.get("vote"))
        if "language" in booklet:
            normalised["booklet_language"] = booklet["language"]
    elif "reference" in request:
        reference = request["reference"]
        if not isinstance(reference, dict) or not isinstance(reference.get("text"), str):
            raise ValueError("reference.text must be a non-empty string")
        normalised.update(task="beginner", reference=reference["text"])
        if "language" in reference:
            normalised["reference_language"] = reference["language"]
    else:
        raise ValueError("request must contain booklet or reference")
    return normalised


def validate_request(request, base_dir=None):
    request = normalise_request(request, base_dir)
    pipeline = request.get("pipeline_version", FROZEN_PIPELINE)
    if pipeline not in (FROZEN_PIPELINE, CANDIDATE_PIPELINE):
        raise ValueError("Unknown pipeline_version")
    if request["task"] not in ("beginner", "advanced"):
        raise ValueError("task must be beginner or advanced")
    if "booklet" in request and "reference" in request:
        raise ValueError("request must contain booklet or reference, not both")
    if "id" in request and (not isinstance(request["id"], str) or not request["id"].strip()):
        raise ValueError("id must be a non-empty string")
    if not isinstance(request.get("claim"), str) or not request["claim"].strip():
        raise ValueError("claim must be a non-empty string")
    for field in ("claim_language", "booklet_language", "reference_language"):
        if field in request and request[field] not in LANGUAGES:
            raise ValueError(field + " must be de, fr or it")
    if request["task"] == "advanced":
        if not isinstance(request.get("booklet"), str) or not request["booklet"].strip():
            raise ValueError("booklet must identify one PDF")
        if (request.get("id") is not None or pipeline == CANDIDATE_PIPELINE) and (
                not isinstance(request.get("vote"), str) or not request["vote"].strip()):
            raise ValueError("vote must be a non-empty string")
        if request.get("evidence", "retrieved") not in ("full", "retrieved"):
            raise ValueError("evidence must be full or retrieved")
        top_k = request.get("top_k", 5)
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer from 1 to 20")
    elif not isinstance(request.get("reference"), str) or not request["reference"].strip():
        raise ValueError("reference.text must be a non-empty string")
    return request


class SubmissionJudge:
    """OpenAI-compatible API with explicit model and token-usage checks."""
    def __init__(self, timeout=180):
        import requests
        self.model = os.environ.get("LLM_NAME", MODEL)
        if os.environ.get("SUBMISSION_MODEL_REQUIRED") == "1" and self.model not in OFFICIAL_MODELS:
            raise ValueError("Docker submission requires an allowlisted official Apertus v1.5 model")
        if not is_apertus_v15(self.model):
            raise ValueError("Submission requires an allowlisted Apertus v1.5 checkpoint id; "
                             "historical models use main.py")
        if token_preflight_mode() not in ("required", "optional"):
            raise ValueError("LLM_TOKEN_PREFLIGHT must be 'required' or 'optional'")
        base = os.environ.get("BASE_URL", os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        if not base:
            raise ValueError("Set LLM_BASE_URL to an Apertus v1.5 OpenAI-compatible endpoint; no lexical fallback")
        parsed_base = urlparse(base)
        if (parsed_base.scheme not in ("http", "https") or not parsed_base.hostname
                or parsed_base.username or parsed_base.password or parsed_base.query or parsed_base.fragment):
            raise ValueError("LLM_BASE_URL must be an HTTP(S) URL without credentials, query or fragment")
        self.base = base[:-3] if base.endswith("/v1") else base
        self.context = int(os.environ.get("LLM_CONTEXT_TOKENS", "32768"))
        self.max_tokens = 512
        self.timeout = timeout
        if self.context <= self.max_tokens:
            raise ValueError("LLM_CONTEXT_TOKENS must exceed 512 and match the server limit")
        self.session = requests.Session()
        key = os.environ.get("API_KEY", os.environ.get("LLM_API_KEY"))
        if key:
            self.session.headers["Authorization"] = "Bearer " + key
        try:
            response = self.session.get(self.base + "/v1/models", timeout=10)
            response.raise_for_status()
            listing = response.json()
            rows = listing.get("data") if isinstance(listing, dict) else None
            if not isinstance(rows, list) or any(
                    not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in rows):
                raise ValueError("Invalid endpoint model listing")
            if self.model not in [r["id"] for r in rows]:
                raise ValueError("endpoint does not list the configured Apertus v1.5 model")
        except requests.RequestException as exc:
            raise RuntimeError("Apertus v1.5 endpoint preflight failed; check LLM_BASE_URL and credentials") from exc

    def judge(self, claim, evidence, seed=20261011, *, vote=None,
              pipeline_version=FROZEN_PIPELINE):
        # Experimental runners may set a versioned system prompt. The default
        # remains the original production prompt byte-for-byte.
        messages = build_messages(claim, evidence, getattr(self, "system_prompt", SYSTEM_PROMPT),
                                  vote=vote, pipeline_version=pipeline_version)
        preflight = token_preflight_mode()
        out = {"label": None, "label_code": None, "model": self.model,
               "parser_version": LABEL_PARSE_VERSION, "temperature": 0, "seed": seed,
               "max_tokens": self.max_tokens, "context_tokens": self.context,
               "token_preflight": preflight,
               "prompt_sha256": digest(json.dumps(messages, ensure_ascii=False).encode())}
        start = time.perf_counter()
        try:
            count = None
            if preflight == "required":
                tok = self.session.post(self.base + "/tokenize", json={
                    "model": self.model, "messages": messages, "add_generation_prompt": True,
                    "chat_template_kwargs": {"enable_thinking": False}}, timeout=30)
                tok.raise_for_status()
                count = tok.json()["count"]
                if type(count) is not int or count < 1:
                    raise ValueError("invalid token count")
                out["input_tokens"] = count
                if count + self.max_tokens > self.context:
                    out["error"] = "context_limit"
                    return out
            inference_start = time.perf_counter()
            payload = {
                "model": self.model, "messages": messages, "temperature": 0,
                "max_tokens": self.max_tokens, "stream": False}
            if preflight == "required":
                payload.update(seed=seed, chat_template_kwargs={"enable_thinking": False})
            else:
                # Keep hosted APIs on the standard OpenAI-compatible request surface.
                out["seed"] = None
            response = self.session.post(self.base + "/v1/chat/completions", json=payload,
                                         timeout=getattr(self, "timeout", 180))
            out["inference_s"] = time.perf_counter() - inference_start
            response.raise_for_status()
            data = response.json()
            out["response_model"] = data.get("model")
            if data.get("model") != self.model:
                out["error"] = "response_model_mismatch_or_missing"
                return out
            if not isinstance(data.get("choices"), list) or len(data["choices"]) != 1:
                raise ValueError("Expected exactly one completion")
            choice = data["choices"][0]
            raw = choice["message"]["content"]
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("Missing completion text")
            out.update(raw_response=raw, usage=data.get("usage") or {}, finish_reason=choice.get("finish_reason"))
            # Required preflight detects input-count changes; both modes reject
            # output exhaustion. Optional mode relies on the server's usage.
            reported = (data.get("usage") or {}).get("prompt_tokens")
            if preflight == "optional":
                out["input_tokens"] = reported
                if type(reported) is not int or reported < 1:
                    out["error"] = "missing_usage"
                elif reported + self.max_tokens > self.context:
                    out["error"] = "context_limit"
            elif type(reported) is not int or reported != count:
                out["error"] = "prompt_token_count_mismatch_or_missing_usage"
            completion_tokens = out["usage"].get("completion_tokens")
            if not out.get("error") and (type(completion_tokens) is not int or not 1 <= completion_tokens <= self.max_tokens):
                out["error"] = "missing_completion_usage"
            total = out["usage"].get("total_tokens")
            if not out.get("error") and total is not None and (
                    type(total) is not int or total != reported + completion_tokens):
                out["error"] = "inconsistent_total_usage"
            if not out.get("error") and choice.get("finish_reason") != "stop":
                out["error"] = "incomplete_completion"
            if not out.get("error"):
                if pipeline_version == CANDIDATE_PIPELINE:
                    try:
                        structured, recovered = candidate_json(raw)
                    except (json.JSONDecodeError, ValueError, TypeError) as exc:
                        out["error"] = f"model_response_parse_error:{type(exc).__name__}"
                        return out
                    if recovered:
                        out["syntax_recovery"] = "removed_single_trailing_closing_brace"
                    parse_input = json.dumps(structured, ensure_ascii=False)
                else:
                    parse_input = raw
                parsed = parse_nli_response(parse_input)
                out.update({key: parsed[key] for key in ("label", "reasoning", "evidence_snippet", "error", "vote_status", "vote_reference",
                                                       "evidence_status", "evidence_refs")
                            if key in parsed})
                if out.get("error"):
                    out["label"] = None
                out["label_code"] = label_to_code(out["label"])
        except Exception as exc:
            out["error"] = f"endpoint_or_tokenisation_error:{type(exc).__name__}"
        finally:
            out["elapsed_s"] = time.perf_counter() - start
        return out


def normalise_citation(text):
    # A PDF discretionary soft hyphen may split a word across a physical line.
    # Preserve ordinary hyphens, punctuation, case and all substantive text.
    text = re.sub(r"(?<=\w)\u00ad(?:[ \t]*\r?\n[ \t]*)?(?=\w)", "", text)
    return " ".join(text.split())


def source_passages(booklet, selected):
    """Attach exact offsets in extracted physical pages, without fuzzy matching."""
    pages = {p["page"]: p["text"] for p in booklet["pages"]}
    chunks = {p["id"]: p for p in passages(booklet)}
    located = []
    for index, passage in enumerate(selected, 1):
        text = passage["text"]
        page = pages[passage["page"]]
        start, end = passage.get("page_start"), passage.get("page_end")
        if "page_start" not in passage and "page_end" not in passage:
            chunk = chunks.get(passage.get("id"))
            if chunk and chunk["page"] == passage["page"] and chunk["text"] == text:
                start = (int(chunk["id"].rsplit("c", 1)[1]) - 1) * 900
            else:
                start = page.find(text)
                if start < 0 or page.find(text, start + 1) >= 0:
                    raise ValueError("Ambiguous or missing source passage")
            end = start + len(text)
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(page) or page[start:end] != text):
            raise ValueError("Invalid source passage offsets")
        located.append(dict(passage, id="e" + str(index), page_start=start, page_end=end))
    return located


def referenced_citations(result, selected):
    """Verify source selection independently of the model's semantic judgement."""
    refs = result.get("evidence_refs")
    if not isinstance(refs, list):
        raise ValueError("missing_evidence_refs")
    if result.get("label") == "neutral":
        if refs or result.get("evidence_status") != "insufficient":
            raise ValueError("invalid_neutral_evidence")
        return []
    if result.get("evidence_status") != "sufficient" or not refs:
        raise ValueError("insufficient_evidence")
    return resolve_references(refs, selected)


def resolve_references(refs, selected):
    """Copy exactly the source spans selected by the model."""
    by_id = {p["id"]: p for p in selected}
    citations = []
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("passage_id"), str):
            raise ValueError("invalid_evidence_reference")
        passage = by_id.get(ref["passage_id"])
        if passage is None:
            raise ValueError("unknown_evidence_reference")
        text = passage["text"]
        start, end = ref.get("start", 0), ref.get("end", len(text))
        if (("start" in ref) != ("end" in ref) or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(text) or not text[start:end].strip()):
            raise ValueError("invalid_citation_offsets")
        identity = (ref["passage_id"], start, end)
        if identity in seen:
            raise ValueError("duplicate_evidence_reference")
        seen.add(identity)
        citations.append(dict(passage, text=text[start:end],
                              passage_start=start, passage_end=end,
                              page_start=passage["page_start"] + start,
                              page_end=passage["page_start"] + end))
    return citations


def candidate_result(result, selected, vote=None):
    citations = []
    if not result.get("error"):
        try:
            if vote is not None and result.get("vote_status") != "recognised":
                status = result.get("vote_status")
                raise ValueError("vote_" + status if status in ("ambiguous", "unrecognised")
                                 else "invalid_vote_status")
            if vote is not None:
                result["vote_citation"] = resolve_references([result.get("vote_reference")], selected)[0]
            citations = referenced_citations(result, selected)
        except ValueError as exc:
            result.update(label=None, label_code=None, error=str(exc))
    result.update(passages=selected, citations=citations, citation_verified=bool(citations),
                  pipeline_version=CANDIDATE_PIPELINE,
                  citation_method="source-selection-v1", semantic_support="model_judgement_only")
    return result


def candidate_evidence(selected):
    return "\n\n".join("[" + p["id"] + "; page " + str(p["page"]) + "]\n" + p["text"]
                       for p in selected)


def classify(request, judge, retriever=None, booklet=None, seed=20261011):
    request = validate_request(request)
    pipeline = request.get("pipeline_version", FROZEN_PIPELINE)
    candidate = pipeline == CANDIDATE_PIPELINE
    claim = request["claim"]
    if request["task"] == "beginner":
        reference = request["reference"]
        if candidate:
            selected = [{"id": "e1", "page": None, "text": reference,
                         "source": "supplied_reference", "source_sha256": digest(reference.encode()),
                         "page_start": 0, "page_end": len(reference)}]
            result = judge.judge(claim, candidate_evidence(selected), seed=seed,
                                 pipeline_version=pipeline)
            result.update(case_id=request.get("id"), claim=claim, task="beginner", retrieval_s=0.0)
            return candidate_result(result, selected)
        result = judge.judge(claim, reference, seed=seed)
        snippet = result.get("evidence_snippet", "")
        if not isinstance(snippet, str):
            result.update(label=None, label_code=None, error="invalid_evidence_snippet")
            snippet = ""
        passage = {"page": None, "text": reference, "source": "supplied_reference"}
        citations = [passage] if snippet.strip() and normalise_citation(snippet) in normalise_citation(reference) else []
        result.update(case_id=request.get("id"), claim=claim, task="beginner",
                      passages=[passage], citations=citations,
                      citation_verified=bool(citations), retrieval_s=0.0)
        return result
    mode = request.get("evidence", "retrieved")
    booklet = booklet or load_booklet(request["booklet"], request.get("booklet_language"))
    if booklet["source"] != request["booklet"] or (
            request.get("booklet_language") and booklet["language"] != request["booklet_language"]):
        raise ValueError("Loaded booklet does not match the request")
    started = time.perf_counter()
    if mode == "full":
        selected = [dict(p, source=booklet["source"], pdf_sha256=booklet["sha256"])
                    for p in booklet["pages"]]
    else:
        top_k = request.get("top_k", 5)
        query = ("Vote: " + request["vote"] + "\nClaim: " + claim) if candidate else claim
        selected = (retriever or BookletRetriever()).retrieve(booklet, query, top_k)
    retrieval_s = time.perf_counter() - started
    if not selected:
        raise ValueError("No evidence extracted/retrieved")
    pages = {p["page"]: p["text"] for p in booklet["pages"]}
    if any(p.get("source") != booklet["source"] or p.get("pdf_sha256") != booklet["sha256"]
           or p.get("page") not in pages or p["text"] not in pages[p["page"]] for p in selected):
        raise ValueError("Evidence is not from the selected booklet")
    if candidate:
        selected = source_passages(booklet, selected)
        result = judge.judge(claim, candidate_evidence(selected), seed=seed,
                             vote=request["vote"], pipeline_version=pipeline)
        result.update(claim=claim, evidence_mode=mode, booklet=booklet["source"],
                      pdf_sha256=booklet["sha256"], case_id=request.get("id"), task="advanced",
                      vote=request["vote"], retrieval_query=query if mode == "retrieved" else None,
                      claim_language=request.get("claim_language"), booklet_language=booklet["language"],
                      retrieval_s=retrieval_s)
        return candidate_result(result, selected, request["vote"])
    result = judge.judge(claim, evidence_payload(booklet, selected), seed=seed)
    snippet = result.get("evidence_snippet", "")
    if not isinstance(snippet, str):
        result.update(label=None, label_code=None, error="invalid_evidence_snippet")
        snippet = ""
    citations = [p for p in selected if snippet.strip()
                 and normalise_citation(snippet) in normalise_citation(p["text"])]
    result.update(claim=claim, evidence_mode=mode, booklet=booklet["source"], pdf_sha256=booklet["sha256"],
                  case_id=request.get("id"), task="advanced", pipeline_version=pipeline,
                  vote=request.get("vote"), retrieval_query=query if mode == "retrieved" else None,
                  claim_language=request.get("claim_language"), booklet_language=booklet["language"],
                  passages=selected, citations=citations, citation_verified=bool(citations),
                  retrieval_s=retrieval_s)
    return result


def submission_output(result):
    """Render only the official output contract from recorded result fields."""
    if result.get("error") or result.get("label") is None:
        raise ValueError("classification did not produce a valid label")
    label_name = result["label"]
    label = label_to_code(label_name)
    if label is None or type(result.get("label_code")) is not int or result.get("label_code") != label:
        raise ValueError("label name/code mismatch")
    evidence = []
    candidate = result.get("pipeline_version") == CANDIDATE_PIPELINE
    if candidate:
        if result.get("task") == "advanced" and result.get("vote_status") != "recognised":
            raise ValueError("unresolved_vote")
        if result.get("task") == "advanced" and result.get("vote_citation") != resolve_references(
                [result.get("vote_reference")], result["passages"])[0]:
            raise ValueError("vote_source_mismatch")
        citations = referenced_citations(result, result["passages"])
        if citations != result.get("citations"):
            raise ValueError("citation_source_mismatch")
    if label_name != "neutral":
        if not result.get("citation_verified") or not result.get("citations"):
            raise ValueError("entailment and contradiction require grounded evidence")
        snippet = result.get("evidence_snippet", "")
        for citation in result["citations"]:
            text = citation["text"] if candidate else (
                snippet if snippet and snippet in citation["text"] else citation["text"])
            evidence.append({"page": citation.get("page"), "text": text})
    usage = result.get("usage") or {}
    input_tokens = result.get("input_tokens")
    output_tokens = usage.get("completion_tokens")
    inference_s = result.get("inference_s")
    if type(input_tokens) is not int or input_tokens < 1:
        raise ValueError("missing actual input token usage")
    if type(output_tokens) is not int or output_tokens < 1:
        raise ValueError("missing actual output token usage")
    if type(inference_s) not in (int, float) or not math.isfinite(inference_s) or inference_s < 0:
        raise ValueError("missing actual inference latency")
    case_id = result.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("missing case id")
    return {"id": case_id, "label": label, "label_name": label_name,
            "evidence": evidence,
            "metrics": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                        "inference_time_ms": round(inference_s * 1000)}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=os.environ.get("REQUEST_FILE", str(DATA_DIR / "request.json")))
    ap.add_argument("--out")
    args = ap.parse_args()
    try:
        request = strict_json(Path(args.input).read_text(encoding="utf-8"))
        request = validate_request(request, Path(args.input).parent)
        # The CLI always uses the candidate. Flat requests without a version are
        # retained only for the frozen Python experiment runners.
        request["pipeline_version"] = CANDIDATE_PIPELINE
        request = validate_request(request)
        if not request.get("id"):
            raise ValueError("id must be a non-empty string")
        args.out = args.out or os.environ.get("RESULT_FILE")
        diagnostics = os.environ.get("DIAGNOSTICS_FILE")
        if args.out and diagnostics and Path(args.out).resolve() == Path(diagnostics).resolve():
            raise ValueError("Result and diagnostics paths must differ")
        for target in (args.out, diagnostics):
            if target and Path(target).exists():
                raise ValueError("Output exists; choose a new path")
            if target and not Path(target).parent.is_dir():
                raise ValueError("Output directory does not exist")
        judge = SubmissionJudge()  # fail before PDF/embedding downloads
        with redirect_stdout(sys.stderr):
            result = classify(request, judge)
        if diagnostics:
            with open(diagnostics, "x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
        rendered = json.dumps(submission_output(result), ensure_ascii=False, indent=2)
        if args.out:
            with open(args.out, "x", encoding="utf-8") as stream:
                stream.write(rendered + "\n")
        print(rendered)
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: check request, endpoint and output configuration", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
