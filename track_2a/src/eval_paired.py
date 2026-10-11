"""Small paired development evaluation of specified-booklet full vs retrieval.

Gold references are used only after inference for evidence coverage scoring.
No change to the historical split; its complement is not an independent holdout.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import unicodedata
import time

from booklet_app import (MODEL, BookletRetriever, SubmissionJudge, classify, digest,
                         load_booklet)
from eval_nli import (DEFAULT_DATA, DEV_SEED, DEV_SIZE, load_rows, split_indices,
                      summarise)
from labels import CODE_TO_LABEL, LABEL_PARSE_VERSION


def normal(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def content_key(row):
    return normal(row["claim"]), normal(row["reference_string"]), row["entailment_label"]


def plan(rows, limit, seed):
    dev = split_indices(len(rows), "dev", DEV_SEED, DEV_SIZE)
    rest = set(range(len(rows))) - set(dev)
    rest_keys = {content_key(rows[i]) for i in rest}
    rest_claims = {normal(rows[i]["claim"]) for i in rest}
    rest_refs = {normal(rows[i]["reference_string"]) for i in rest}
    # Deduplicate the development pool, retaining original row identities.
    seen, buckets = set(), {}
    order = dev[:]
    random.Random(seed).shuffle(order)
    for i in order:
        row = rows[i]
        key = content_key(row)
        if key in seen:
            continue
        seen.add(key)
        cell = (row["claim_language"], row["reference_language"], row["entailment_label"])
        buckets.setdefault(cell, []).append(i)
    selected = []
    cells = sorted(buckets)
    random.Random(seed).shuffle(cells)
    # Prefer a new language pair, then a least represented label, at each draw.
    while buckets and len(selected) < limit:
        pairs = Counter((rows[i]["claim_language"], rows[i]["reference_language"]) for i in selected)
        labels = Counter(rows[i]["entailment_label"] for i in selected)
        cell = min((c for c in cells if c in buckets), key=lambda c: (pairs[c[:2]], labels[c[2]]))
        selected.append(buckets[cell].pop())
        if not buckets[cell]:
            del buckets[cell]
    return {"row_indices": selected, "split": "historical-dev-deduplicated",
            "split_seed": DEV_SEED, "sample_seed": seed, "n": len(selected),
            "label_counts": dict(Counter(rows[i]["entailment_label"] for i in selected)),
            "language_pairs": dict(Counter(rows[i]["claim_language"] + "->" + rows[i]["reference_language"] for i in selected)),
            "historical_dev_rows": len(dev), "historical_eval_rows": len(rest),
            "dev_exact_normalised_triples_in_eval": sum(content_key(rows[i]) in rest_keys for i in dev),
            "dev_claims_in_eval": sum(normal(rows[i]["claim"]) in rest_claims for i in dev),
            "dev_references_in_eval": sum(normal(rows[i]["reference_string"]) in rest_refs for i in dev),
            "selected_triples_in_eval": sum(content_key(rows[i]) in rest_keys for i in selected),
            "holdout_warning": "Row complement is contaminated; no independent held-out claim."}


def coverage(reference, records):
    """40-character shingle recall proxy, not semantic evidence correctness."""
    gold = normal(reference)
    width = min(40, len(gold))
    if not width:
        return None
    shingles = {gold[i:i + width] for i in range(len(gold) - width + 1)}
    texts = [normal(p["text"]) for p in records]
    return sum(any(s in text for text in texts) for s in shingles) / len(shingles)


def run_pairs(rows, selection, judge, retriever, seed):
    results = {"full": [], "retrieved": []}
    booklets = {}
    for n, i in enumerate(selection):
        row = rows[i]
        # Allowlist inference inputs: never forward the dataset row or reference.
        request = {"booklet": row["booklet_url"], "booklet_language": row["reference_language"],
                   "claim": row["claim"], "claim_language": row["claim_language"]}
        key = (request["booklet"], request["booklet_language"])
        modes = ("full", "retrieved") if n % 2 == 0 else ("retrieved", "full")
        for mode in modes:
            started = time.perf_counter()
            try:
                if key not in booklets:
                    booklets[key] = load_booklet(*key)
                result = classify(dict(request, evidence=mode), judge, retriever, booklets[key], seed)
            except Exception as exc:
                result = {"label": None, "error": f"pipeline_error:{type(exc).__name__}:{exc}",
                          "elapsed_s": time.perf_counter() - started, "passages": []}
            result.update(row_index=i, gold=CODE_TO_LABEL[row["entailment_label"]],
                          pred=result.get("label"), pair=request["claim_language"] + "->" + request["booklet_language"])
            result["correct"] = result["pred"] == result["gold"]
            result["reference_shingle_coverage"] = coverage(row["reference_string"], result["passages"])
            results[mode].append(result)
        print(f"Paired item {n + 1}/{len(selection)} complete", flush=True)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--limit", type=int, default=9)
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.out.exists():
        ap.error("Output exists; choose a new path")
    if not 1 <= args.limit <= DEV_SIZE:
        ap.error("limit must be between 1 and 60; this runner is development-only")
    rows = load_rows(args.data)
    selection = plan(rows, args.limit, args.seed)
    payload = {"created_utc": datetime.now(timezone.utc).isoformat(), "model": MODEL,
               "dataset_sha256": digest(args.data.read_bytes()), "parser_version": LABEL_PARSE_VERSION,
               "plan": selection, "status": "planned-no-inference"}
    if not args.dry_run:
        judge = SubmissionJudge()
        results = run_pairs(rows, selection["row_indices"], judge, BookletRetriever(), args.seed)
        summaries = {}
        for mode, records in results.items():
            summary = summarise(records)
            summary["prompt_tokens_total"] = (sum(r["input_tokens"] for r in records)
                                               if all("input_tokens" in r for r in records) else None)
            measured = [r["reference_shingle_coverage"] for r in records if not r.get("error")]
            summary["mean_reference_shingle_coverage_successful"] = sum(measured) / len(measured) if measured else None
            summary["citation_verified_count"] = sum(bool(r.get("citation_verified")) for r in records)
            summary["tokens_note"] = "input_tokens includes context-rejected payloads; missing measurements stay null"
            summaries[mode] = summary
        payload.update(status="executed", results=results, summaries=summaries)
        payload["prediction_changes"] = [
            {"row_index": a["row_index"], "gold": a["gold"], "full": a["pred"],
             "retrieved": b["pred"], "full_correct": a["correct"], "retrieved_correct": b["correct"]}
            for a, b in zip(results["full"], results["retrieved"]) if a["pred"] != b["pred"]]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(json.dumps(selection, indent=2))
    print(args.out)
    if payload.get("summaries") and any(s["errors"] for s in payload["summaries"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
