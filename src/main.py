"""
End-to-end runner: claim -> retrieval -> evidence -> NLI judgement + source.

Usage:
    python main.py                            # run all example_claims.json
    python main.py "a claim"                  # run one claim
    LLM_BACKEND=mlx python main.py            # use MLX judge (needs to
                                              # download a model first)
    LLM_BACKEND=ollama python main.py         # use Ollama judge

    RETRIEVAL_CONFIG=<legacy|v2|hybrid> selects the retrieval stack
    (default legacy = the historical 526-passage OCR corpus):
      v2     - booklet PDF corpus (data/booklets/corpus.json), global dense
      hybrid - booklet corpus, two-stage: booklet routing -> in-booklet
               lexical+dense candidates -> RRF fusion (see hybrid_retrieval.py)
"""
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from config import (TOP_K, LLM_BACKEND, MLX_MODEL, OLLAMA_MODEL, DATA_DIR,
                    BOOKLET_CORPUS_JSON, RETRIEVAL_CONFIG)
from ingest import build_corpus
from retriever import build_retriever, LANG_TO_ADAPTER
from hybrid_retrieval import (TwoStageRetriever, detect_query_language,
                              index_cache_key, load_index, save_index)
from nli_judge import build_judge, format_evidence
from labels import label_to_code


LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def make_logger(tag: str = "") -> tuple[logging.Logger, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"run_{ts}" + (f"_{tag}" if tag else "")
    log_path = LOG_DIR / f"{name}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    log = logging.getLogger("nli")
    log.info("Log file: %s", log_path)
    return log, log_path


def load_claims(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


class Pipeline:
    """Retrieval stack chosen by RETRIEVAL_CONFIG (config.py, env override):

      legacy  - historical 526-passage OCR corpus + dense retrieval (default,
                kept unchanged so previous smoke results stay reproducible).
      v2      - booklet PDF corpus, global dense retrieval.
      hybrid  - booklet corpus, two-stage retrieval: rank booklets, then
                fuse in-booklet lexical + dense candidates via RRF.

    Booklet modes pick the query adapter from a claim-language heuristic -
    no gold evidence language or booklet info is available at prediction
    time (the eval's emb_v2 oracle-adapter setting is eval-only on purpose).
    """

    def __init__(self, log: logging.Logger, backend: str = None):
        log.info("=" * 60)
        self.retrieval_config = RETRIEVAL_CONFIG
        if RETRIEVAL_CONFIG in ("v2", "hybrid"):
            self._init_booklet(log)
        else:
            self._init_legacy(log)

        log.info("Stage 3: init NLI judge (backend=%s)", backend or LLM_BACKEND)
        t0 = time.time()
        self.judge = build_judge(backend)
        log.info("  judge ready in %.1fs", time.time() - t0)

    def _init_legacy(self, log):
        self.mode = "legacy"
        self.ts = None
        log.info("Stage 1: build corpus (RETRIEVAL_CONFIG=legacy)")
        t0 = time.time()
        self.corpus = build_corpus()
        log.info("  %d passages in %.1fs", len(self.corpus), time.time() - t0)

        log.info("Stage 2: build retrieval index")
        t0 = time.time()
        self.retriever = build_retriever(self.corpus)
        log.info("  index built in %.1fs", time.time() - t0)

    def _init_booklet(self, log):
        self.mode = "booklet"
        log.info("Stage 1: load booklet PDF corpus %s", BOOKLET_CORPUS_JSON)
        if not BOOKLET_CORPUS_JSON.exists():
            raise RuntimeError(
                f"{BOOKLET_CORPUS_JSON} missing - build it first "
                "(make fetch-booklets)")
        self.corpus = json.loads(
            BOOKLET_CORPUS_JSON.read_text(encoding="utf-8"))
        log.info("  %d passages", len(self.corpus))

        log.info("Stage 2: embedding index (disk-cached when available)")
        t0 = time.time()
        from retriever import Retriever
        self.retriever = Retriever()
        key = index_cache_key(self.corpus)
        mat = load_index(key)
        if mat is None:
            self.retriever.build_index(self.corpus)
            mat = self.retriever.corpus_embeddings
            save_index(key, mat)
        else:
            log.info("  embeddings loaded from cache (not re-encoded)")
        mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        hybrid = self.retrieval_config == "hybrid"
        self.ts = TwoStageRetriever(
            self.corpus, corpus_mat=mat,
            mode="two_stage" if hybrid else "global",
            use_lexical=hybrid)
        log.info("  retrieval stack ready in %.1fs", time.time() - t0)

    def _retrieve_booklet(self, claim: str, top_k: int):
        lang = detect_query_language(claim)
        adapter = LANG_TO_ADAPTER.get(lang, "de_CH")
        qemb = self.retriever.encode([claim], lang_code=adapter)[0]
        if self.retrieval_config == "hybrid":
            hits = self.ts.retrieve(claim, k=top_k, query_emb=qemb)
        else:  # v2: global dense only
            q = qemb / (np.linalg.norm(qemb) + 1e-9)
            sims = self.ts.mat @ q
            order = np.argsort(-sims)[:top_k]
            hits = [(int(j), float(sims[j])) for j in order]
        return [{**self.corpus[i], "score": s} for i, s in hits]

    def verify(self, claim: str, year: str = None, lang: str = None,
               top_k: int = TOP_K) -> dict:
        if self.mode == "legacy":
            passages = self.retriever.retrieve(
                claim, top_k=top_k, filter_year=year, filter_lang=lang,
            )
        else:
            # Booklet corpus spans all years/languages at once; year/lang
            # filters are a legacy-corpus feature and are ignored here.
            passages = self._retrieve_booklet(claim, top_k)
        verdict = self.judge.judge(claim, passages)
        label = verdict.get("label")
        result = {
            "claim": claim,
            "year_filter": year if self.mode == "legacy" else None,
            "retrieval_config": self.retrieval_config,
            "label": label,
            "label_code": label_to_code(label),
            "status": "ok" if label else "error",
            "reasoning": verdict.get("reasoning", ""),
            "evidence_snippet": verdict.get("evidence_snippet", ""),
            "retrieved": [
                {
                    "id": p.get("id"),
                    "lang": p.get("lang"),
                    "year": p.get("year") or p.get("booklet_date"),
                    "source_file": p.get("source_file"),
                    "score": round(p["score"], 3),
                    "text_head": p["text"][:200],
                }
                for p in passages
            ],
        }
        if verdict.get("error"):
            result["error"] = verdict["error"]
        if verdict.get("usage"):
            result["usage"] = verdict["usage"]
        return result


def run(pipeline, claims, log):
    results = []
    for i, item in enumerate(claims, 1):
        claim = item["claim"] if isinstance(item, dict) else item
        year = item.get("year") if isinstance(item, dict) else None
        expected = item.get("expected") if isinstance(item, dict) else None

        log.info("-" * 60)
        log.info("[%d/%d] %s", i, len(claims), claim[:100])
        t0 = time.time()
        try:
            res = pipeline.verify(claim, year=year)
        except Exception:
            log.exception("verify failed")
            continue
        elapsed = time.time() - t0

        label = res["label"]
        shown = (label or "ERROR").upper()
        mark = ""
        if expected:
            mark = "  OK" if expected == label else f"  (expected {expected})"
        log.info("   -> %-13s (%.1fs)%s", shown, elapsed, mark)
        for r in res["retrieved"][:3]:
            log.info("      . %s [%s] sim=%.3f  %s",
                     r["id"], r["lang"], r["score"], r["text_head"][:80])
        res["elapsed_s"] = round(elapsed, 2)
        res["expected"] = expected
        results.append(res)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("claim", nargs="*", help="optional one-off claim text")
    ap.add_argument("--backend", default=None,
                    choices=["lexical", "mlx", "ollama"],
                    help="override LLM_BACKEND")
    ap.add_argument("--year", default=None, help="restrict retrieval to a year")
    args = ap.parse_args()

    backend = args.backend or LLM_BACKEND
    log, log_path = make_logger(tag=backend)
    log.info("backend=%s  mlx_model=%s  ollama_model=%s",
             backend, MLX_MODEL if backend == "mlx" else "-",
             OLLAMA_MODEL if backend == "ollama" else "-")

    if args.claim:
        claims = [{"claim": " ".join(args.claim), "year": args.year}]
    else:
        claims = load_claims(DATA_DIR / "example_claims.json")
        if not claims:
            log.error("no example_claims.json found and no claim given")
            return

    log.info("%d claims to verify", len(claims))

    t_total = time.time()
    try:
        pipeline = Pipeline(log, backend=backend)
    except Exception as e:
        log.exception("pipeline build failed: %s", e)
        return

    results = run(pipeline, claims, log)
    log.info("=" * 60)
    log.info("DONE: %d claims in %.1fs", len(results), time.time() - t_total)

    # Structured results (machine-readable run report)
    n_err = sum(1 for r in results if r.get("status") == "error")
    if n_err:
        log.warning("%d/%d claims finished with status=error "
                    "(no trustworthy label)", n_err, len(results))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = DATA_DIR / f"results_{ts}_{backend}.json"
    report = {
        "config": {
            "backend": backend,
            "retrieval_config": RETRIEVAL_CONFIG,
            "model": (MLX_MODEL if backend == "mlx" else
                      OLLAMA_MODEL if backend == "ollama" else None),
            "top_k": TOP_K,
            "timestamp_utc": datetime.now(timezone.utc)
                                .isoformat(timespec="seconds"),
            "label_mapping": {"entailment": 0, "neutral": 1,
                              "contradiction": 2},
        },
        "results": results,
    }
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info("results JSON: %s", out_json)


if __name__ == "__main__":
    main()
