"""
End-to-end runner: claim -> retrieval -> evidence -> NLI judgement + source.

Usage:
    python main.py                            # run all example_claims.json
    python main.py "a claim"                  # run one claim
    LLM_BACKEND=mlx python main.py            # use MLX judge (needs to
                                              # download a model first)
    LLM_BACKEND=ollama python main.py         # use Ollama judge
"""
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import TOP_K, LLM_BACKEND, MLX_MODEL, OLLAMA_MODEL, DATA_DIR
from ingest import build_corpus
from retriever import build_retriever
from nli_judge import build_judge, format_evidence


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
    def __init__(self, log: logging.Logger, backend: str = None):
        log.info("=" * 60)
        log.info("Stage 1: build corpus")
        t0 = time.time()
        self.corpus = build_corpus()
        log.info("  %d passages in %.1fs", len(self.corpus), time.time() - t0)

        log.info("Stage 2: build retrieval index")
        t0 = time.time()
        self.retriever = build_retriever(self.corpus)
        log.info("  index built in %.1fs", time.time() - t0)

        log.info("Stage 3: init NLI judge (backend=%s)", backend or LLM_BACKEND)
        t0 = time.time()
        self.judge = build_judge(backend)
        log.info("  judge ready in %.1fs", time.time() - t0)

    def verify(self, claim: str, year: str = None, lang: str = None,
               top_k: int = TOP_K) -> dict:
        passages = self.retriever.retrieve(
            claim, top_k=top_k, filter_year=year, filter_lang=lang,
        )
        verdict = self.judge.judge(claim, passages)
        return {
            "claim": claim,
            "year_filter": year,
            "label": verdict.get("label", "neutral"),
            "reasoning": verdict.get("reasoning", ""),
            "evidence_snippet": verdict.get("evidence_snippet", ""),
            "retrieved": [
                {
                    "id": p["id"],
                    "lang": p["lang"],
                    "year": p["year"],
                    "source_file": p["source_file"],
                    "score": round(p["score"], 3),
                    "text_head": p["text"][:200],
                }
                for p in passages
            ],
        }


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

        mark = ""
        if expected:
            mark = "  OK" if expected == res["label"] else f"  (expected {expected})"
        log.info("   -> %-13s (%.1fs)%s", res["label"].upper(), elapsed, mark)
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

    # Structured results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = DATA_DIR / f"results_{ts}_{backend}.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    log.info("results JSON: %s", out_json)


if __name__ == "__main__":
    main()
