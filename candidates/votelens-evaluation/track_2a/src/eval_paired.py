"""Historical development-plan and coverage helpers. Run experiment_runner.py.

Gold references are used only after inference for evidence coverage scoring.
No change to the historical split; its complement is not an independent holdout.
"""
from collections import Counter
import random
import re
import unicodedata

from eval_nli import DEV_SEED, DEV_SIZE, split_indices


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
