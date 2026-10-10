"""Evaluate the NLI judge against the official Track 2A eval set.

Data: data/eval/mnli_swiss_v1.1.jsonl (regenerate: python3 fetch_eval_data.py).
Official label codes: 0=entailment, 1=neutral, 2=contradiction (src/labels.py).

Modes:
  --evidence oracle       (default) judge receives each item's gold
                          reference_string: measures the judgement step.
  --evidence retrieve     full pipeline over the legacy 526-passage CLI
                          corpus (plumbing check only - see AGENTS.md).
  --evidence retrieve-v2  full pipeline over the 60-booklet PDF corpus via
                          main.Pipeline with retrieval forced to the booklet
                          stack - the same stack production `make run` uses.
Retrieval failures and unparseable/failed judge replies are recorded as
errors (pred=None), never defaulted to a label.

Leakage policy: dev split = seeded 60-item plumbing subset; eval split is
held out and must only be run after prompts/settings are frozen.

Usage (from src/):
    python3 eval_nli.py --split dev --limit 30
    python3 eval_nli.py --split eval --backend mlx
    python3 eval_nli.py --split dev --backend openai --evidence retrieve-v2
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (DATA_DIR, LLM_BACKEND, MLX_MODEL, OLLAMA_MODEL, TOP_K,
                    OPENAI_BASE_URL, JUDGE_MODEL)
from labels import CODE_TO_LABEL, label_to_code
from nli_judge import build_judge

DEFAULT_DATA = DATA_DIR / "eval" / "mnli_swiss_v1.1.jsonl"
DEV_SEED = 20261009
DEV_SIZE = 60
EVIDENCE_MAX_CHARS = 1900   # < format_evidence 2000 cap so gold evidence is
                            # not silently dropped by its per-chunk check
CLASSES = ["entailment", "neutral", "contradiction"]


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    bad = [r for r in rows if CODE_TO_LABEL.get(r.get("entailment_label")) is None
           or not r.get("reference_string")]
    if bad:
        sys.exit(f"ERROR: {len(bad)} rows have a missing/non-official label "
                 "or empty reference_string - refusing to score")
    return rows


def split_indices(n, split, seed, dev_size):
    """Deterministic seeded split; dev exists for plumbing checks only."""
    if split == "all":
        return list(range(n))
    rng = random.Random(seed)
    dev = set(rng.sample(range(n), min(dev_size, n)))
    if split == "dev":
        return sorted(dev)
    return [i for i in range(n) if i not in dev]


def oracle_evidence(item):
    # Keys mirror retriever output so every judge (incl. LexicalJudge which
    # reads p["score"]) works unchanged on oracle evidence.
    return [{"id": "gold",
             "lang": (item.get("reference_language") or "?").lower(),
             "year": "?",
             "source_file": item.get("vote", "official-eval-set"),
             "score": 1.0,
             "text": item["reference_string"][:EVIDENCE_MAX_CHARS]}]


def evaluate(items, judge, evidence_for=None, retrieve_for=None):
    """retrieve_for: claim -> passages, timed and accounted separately:
    retrieval failures must not blur into NLI errors. Items whose evidence
    step failed or found nothing are recorded as errors (pred=None) - the
    chain broke before the judge, so no verdict is trustworthy (the
    never-default-to-neutral invariant)."""
    results = []
    for n, item in enumerate(items, 1):
        gold = CODE_TO_LABEL[item["entailment_label"]]
        retrieval_error = None
        t_ret = time.perf_counter()
        if retrieve_for is not None:
            try:
                passages = retrieve_for(item)
            except Exception as e:
                passages, retrieval_error = [], f"retrieval raised: {e!r}"
        else:
            passages = evidence_for(item)
        retrieval_s = time.perf_counter() - t_ret
        no_evidence = not passages
        t0 = time.perf_counter()
        if retrieval_error or no_evidence:
            verdict, error = {}, (retrieval_error
                                  or "no evidence passages retrieved")
        else:
            try:
                verdict = judge.judge(item["claim"], passages)
                error = verdict.get("error")
            except Exception as e:
                verdict, error = {}, f"judge raised: {e!r}"
        elapsed = time.perf_counter() - t0
        pred = None if (retrieval_error or no_evidence) \
            else verdict.get("label")
        rec = {
            "index": n,
            "claim": item["claim"][:300],
            "pair": (f'{item.get("claim_language")}->'
                     f'{item.get("reference_language")}'),
            "gold": gold, "gold_code": item["entailment_label"],
            "pred": pred, "pred_code": label_to_code(pred),
            "correct": pred == gold, "error": error,
            "elapsed_s": round(elapsed, 2),
            "retrieval_s": round(retrieval_s, 2),
        }
        if no_evidence:
            rec["no_evidence"] = True
        if not retrieval_error and no_evidence:
            rec["error"] = "no evidence passages retrieved"
        if verdict.get("usage"):
            rec["usage"] = verdict["usage"]
        results.append(rec)
        if n % 25 == 0 or n == len(items):
            ok = sum(1 for r in results if r["correct"])
            print(f"  {n}/{len(items)}: correct={ok}", flush=True)
    return results


def summarise(results):
    # Pure-Python metrics (AGENTS.md: no sklearn/SciPy). Error items count
    # as false negatives for their gold class, never as a predicted class.
    per_class = {}
    for c in CLASSES:
        tp = sum(1 for r in results if r["gold"] == c and r["pred"] == c)
        fn = sum(1 for r in results if r["gold"] == c and r["pred"] != c)
        fp = sum(1 for r in results if r["gold"] != c and r["pred"] == c)
        p_ = tp / (tp + fp) if tp + fp else 0.0
        r_ = tp / (tp + fn) if tp + fn else 0.0
        f_ = 2 * p_ * r_ / (p_ + r_) if p_ + r_ else 0.0
        per_class[c] = {"precision": round(p_, 3), "recall": round(r_, 3),
                        "f1": round(f_, 3), "support": tp + fn}
    present = [c for c in CLASSES if per_class[c]["support"] > 0]
    macro = (round(sum(per_class[c]["f1"] for c in present) / len(present), 3)
             if present else 0.0)
    confusion = {g: {p: 0 for p in CLASSES + ["ERROR"]} for g in CLASSES}
    for r in results:
        confusion[r["gold"]][r["pred"] if r["pred"] in CLASSES else "ERROR"] += 1
    lat = sorted(r["elapsed_s"] for r in results if r["pred"])
    ret = [r.get("retrieval_s") for r in results
           if r.get("retrieval_s") is not None]
    kinds = {}
    for r in results:
        if not r["pred"]:
            e = str(r.get("error") or "")
            if e == "unparseable_response":
                k = "unparseable_response"
            elif (e.startswith("retrieval raised")
                  or e == "no evidence passages retrieved"):
                k = "retrieval_error"
            elif ("Endpoint error" in e or "timed out" in e
                  or "Connection" in e or "Max retries" in e):
                k = "endpoint_error"
            else:
                k = "judge_error"
            kinds[k] = kinds.get(k, 0) + 1
    return {
        "n": len(results),
        "errors": sum(1 for r in results if not r["pred"]),
        "error_kinds": kinds,
        "accuracy": round(sum(1 for r in results if r["correct"])
                          / max(1, len(results)), 3),
        "macro_f1": macro,
        "per_class": per_class,
        "confusion": confusion,
        "mean_latency_s": round(sum(lat) / len(lat), 2) if lat else None,
        "median_latency_s": (round((lat[(len(lat) - 1) // 2]
                                    + lat[len(lat) // 2]) / 2, 2)
                             if lat else None),
        "mean_retrieval_s": round(sum(ret) / len(ret), 3) if ret else None,
        "prompt_tokens_total": sum(
            r.get("usage", {}).get("prompt_tokens", 0) for r in results),
        "completion_tokens_total": sum(
            r.get("usage", {}).get("completion_tokens", 0) for r in results),
    }


def main():
    ap = argparse.ArgumentParser(description="Track 2A eval harness")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--split", choices=["dev", "eval", "all"], default="dev")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=DEV_SEED)
    ap.add_argument("--backend", default=None,
                    choices=["lexical", "mlx", "ollama", "openai"])
    ap.add_argument("--evidence",
                    choices=["oracle", "retrieve", "retrieve-v2"],
                    default="oracle")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        sys.exit(f"eval data not found: {data_path}\n"
                 "Run: python3 fetch_eval_data.py")
    rows = load_rows(data_path)
    idx = split_indices(len(rows), args.split, args.seed, DEV_SIZE)
    if args.limit:
        idx = idx[:args.limit]
    items = [rows[i] for i in idx]
    if not items:
        sys.exit("no items selected")

    backend = args.backend or LLM_BACKEND
    retrieve_for = None
    judge = None
    retrieval_desc = "oracle: gold reference_string (judgement step only)"
    if args.evidence == "retrieve":
        from ingest import build_corpus
        from retriever import build_retriever
        retriever = build_retriever(build_corpus())

        def retrieve_for(item):
            return retriever.retrieve(item["claim"], top_k=args.top_k)
        retrieval_desc = "legacy 526-passage CLI corpus (plumbing only)"
    elif args.evidence == "retrieve-v2":
        # Reuse main.Pipeline verbatim: booklet PDF corpus + claim-language
        # adapter heuristic, i.e. the stack production runs. The flag beats
        # the RETRIEVAL_CONFIG env default on purpose. booklet_url and
        # reference_string are never consulted at prediction time.
        import logging
        import main as main_mod
        main_mod.RETRIEVAL_CONFIG = "v2"
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        pipe = main_mod.Pipeline(logging.getLogger("eval-retrieve-v2"),
                                 backend=backend)
        judge = pipe.judge

        def retrieve_for(item):
            return pipe._retrieve_booklet(item["claim"], args.top_k)
        retrieval_desc = ("60-booklet PDF corpus, global dense, "
                          "claim-lang adapter (production stack)")

    print(f"Eval: {len(items)} items | backend={backend} | "
          f"evidence={args.evidence} ({retrieval_desc}) | "
          f"split={args.split} | seed={args.seed}")

    if judge is None:
        judge = build_judge(backend)
    t0 = time.perf_counter()
    if args.evidence == "oracle":
        results = evaluate(items, judge, evidence_for=oracle_evidence)
    else:
        results = evaluate(items, judge, retrieve_for=retrieve_for)
    summary = summarise(results)

    payload = {
        "meta": {
            "created_utc": datetime.now(timezone.utc)
                               .isoformat(timespec="seconds"),
            "backend": backend,
            "model": (MLX_MODEL if backend == "mlx" else
                      JUDGE_MODEL if backend == "openai" else
                      OLLAMA_MODEL if backend == "ollama" else None),
            "endpoint": OPENAI_BASE_URL if backend == "openai" else None,
            "retrieval": retrieval_desc,
            "data_file": str(data_path), "n_items": len(items),
            "split": args.split, "seed": args.seed,
            "evidence_mode": args.evidence,
            "note": ("oracle mode measures the judgement step with gold "
                     "evidence, not retrieval quality"
                     if args.evidence == "oracle" else
                     "end-to-end via main.Pipeline stack: evidence from "
                     "retrieval; retrieval misses and unparseable replies "
                     "are recorded as errors (pred=None), never labelled"),
            "elapsed_total_s": round(time.perf_counter() - t0, 1),
        },
        "summary": summary,
        "items": results,
    }
    out = DATA_DIR / (f"eval_results_{datetime.now():%Y%m%d_%H%M%S}"
                      f"_{args.split}_{backend}_{args.evidence}.json")
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    print(f"\naccuracy  {summary['accuracy']}  "
          f"(errors: {summary['errors']}/{summary['n']})")
    print(f"macro_f1  {summary['macro_f1']}")
    for c, m in summary["per_class"].items():
        print(f"  {c:<14} P={m['precision']:<6} R={m['recall']:<6} "
              f"F1={m['f1']:<6} n={m['support']}")
    print(f"results JSON: {out}")


if __name__ == "__main__":
    main()