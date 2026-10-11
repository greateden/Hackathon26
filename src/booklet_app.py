"""Submission application: one specified PDF and claim, with page citations.

Historical main.py / eval_e2e.py remain separate global-search experiments.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

from config import DATA_DIR, BOOKLET_PDF_DIR
from labels import LABEL_PARSE_VERSION, label_to_code
from nli_judge import SYSTEM_PROMPT, USER_TEMPLATE, parse_nli_response

MODEL = "swiss-ai/Apertus-v1.5-8B"
LANGUAGES = ("de", "fr", "it")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_booklet(spec, language):
    """Resolve a PDF path, cached PDF stem, or HTTPS URL; never read gold data."""
    if language not in LANGUAGES:
        raise ValueError("booklet_language must be de, fr or it")
    source = str(spec)
    if source.startswith("https://"):
        import requests
        from fetch_booklets import pdf_path
        # Reuse historical downloads only after validating the actual PDF bytes.
        candidate = pdf_path(source)
        pdf = DATA_DIR / "booklets" / "submission" / (digest(source.encode()) + ".pdf")
        if candidate.is_file():
            pdf = candidate
        elif not pdf.exists():
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
        return [dict(records[i], score=float(scores[i])) for i in order]


def evidence_payload(booklet, evidence):
    return "\n\n".join(f"[page {p['page']}]\n{p['text']}" for p in evidence)


class SubmissionJudge:
    """vLLM-compatible API with exact token preflight, no implicit truncation."""
    def __init__(self):
        import requests
        self.model = os.environ.get("LLM_NAME", MODEL)
        if self.model != MODEL:
            raise ValueError(f"Submission requires LLM_NAME={MODEL}; historical models use main.py")
        base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        if not base:
            raise ValueError("Set LLM_BASE_URL to an Apertus v1.5 8B vLLM endpoint; no lexical fallback")
        self.base = base[:-3] if base.endswith("/v1") else base
        self.context = int(os.environ.get("LLM_CONTEXT_TOKENS", "32768"))
        self.max_tokens = 512
        if self.context <= self.max_tokens:
            raise ValueError("LLM_CONTEXT_TOKENS must exceed 512 and match the server limit")
        self.session = requests.Session()
        key = os.environ.get("LLM_API_KEY")
        if key:
            self.session.headers["Authorization"] = "Bearer " + key
        try:
            response = self.session.get(self.base + "/v1/models", timeout=10)
            response.raise_for_status()
            if self.model not in [r["id"] for r in response.json()["data"]]:
                raise ValueError("endpoint does not list the required Apertus v1.5 8B model")
        except requests.RequestException as exc:
            raise RuntimeError("Apertus v1.5 endpoint preflight failed; check LLM_BASE_URL and credentials") from exc

    def judge(self, claim, evidence, seed=20261011):
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(claim=claim, evidence=evidence)}]
        out = {"label": None, "label_code": None, "model": self.model,
               "parser_version": LABEL_PARSE_VERSION, "temperature": 0, "seed": seed,
               "max_tokens": self.max_tokens, "context_tokens": self.context,
               "prompt_sha256": digest(json.dumps(messages, ensure_ascii=False).encode())}
        start = time.perf_counter()
        try:
            tok = self.session.post(self.base + "/tokenize", json={
                "model": self.model, "messages": messages, "add_generation_prompt": True}, timeout=30)
            tok.raise_for_status()
            count = tok.json()["count"]
            if type(count) is not int or count < 1:
                raise ValueError("invalid token count")
            out["input_tokens"] = count
            if count + self.max_tokens > self.context:
                out["error"] = "context_limit"
                return out
            inference_start = time.perf_counter()
            response = self.session.post(self.base + "/v1/chat/completions", json={
                "model": self.model, "messages": messages, "temperature": 0,
                "seed": seed, "max_tokens": self.max_tokens, "stream": False}, timeout=180)
            out["inference_s"] = time.perf_counter() - inference_start
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            raw = choice["message"]["content"]
            out.update(raw_response=raw, usage=data.get("usage") or {}, finish_reason=choice.get("finish_reason"))
            # Detect an endpoint silently reducing input or exhausting output.
            if data.get("usage", {}).get("prompt_tokens") != count:
                out["error"] = "prompt_token_count_mismatch_or_missing_usage"
            elif choice.get("finish_reason") != "stop":
                out["error"] = "incomplete_completion"
            else:
                out.update(parse_nli_response(raw))
                if out.get("error"):
                    out["label"] = None
                out["label_code"] = label_to_code(out["label"])
        except Exception as exc:
            out["error"] = f"endpoint_or_tokenisation_error:{type(exc).__name__}"
        finally:
            out["elapsed_s"] = time.perf_counter() - start
        return out


def classify(request, judge, retriever=None, booklet=None, seed=20261011):
    claim = request.get("claim", "")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be a non-empty string")
    if request.get("claim_language") not in LANGUAGES:
        raise ValueError("claim_language must be de, fr or it")
    mode = request.get("evidence", "retrieved")
    if mode not in ("full", "retrieved"):
        raise ValueError("evidence must be full or retrieved")
    booklet = booklet or load_booklet(request["booklet"], request["booklet_language"])
    started = time.perf_counter()
    if mode == "full":
        selected = [dict(p, source=booklet["source"], pdf_sha256=booklet["sha256"])
                    for p in booklet["pages"]]
    else:
        top_k = request.get("top_k", 5)
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer from 1 to 20")
        selected = (retriever or BookletRetriever()).retrieve(booklet, claim, top_k)
    retrieval_s = time.perf_counter() - started
    if not selected:
        raise ValueError("No evidence extracted/retrieved")
    result = judge.judge(claim, evidence_payload(booklet, selected), seed=seed)
    snippet = result.get("evidence_snippet", "")
    normal = lambda s: " ".join(s.split())
    citations = [p for p in selected if snippet.strip() and normal(snippet) in normal(p["text"])]
    result.update(evidence_mode=mode, booklet=booklet["source"], pdf_sha256=booklet["sha256"],
                  claim_language=request["claim_language"], booklet_language=booklet["language"],
                  passages=selected, citations=citations, citation_verified=bool(citations),
                  retrieval_s=retrieval_s)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=os.environ.get("REQUEST_FILE", str(DATA_DIR / "request.json")))
    ap.add_argument("--out")
    args = ap.parse_args()
    try:
        request = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.out and Path(args.out).exists():
            raise ValueError("Output exists; choose a new path")
        judge = SubmissionJudge()  # fail before PDF/embedding downloads
        result = classify(request, judge)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.out:
            with open(args.out, "x", encoding="utf-8") as stream:
                stream.write(rendered + "\n")
        print(rendered)
        return 1 if result.get("error") else 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
