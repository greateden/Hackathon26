"""
Shared sampling helpers for the eval harnesses.

Two properties matter for trustworthy eval numbers:
  1. reproducibility  - fixed seed, order-independent selection
  2. class balance    - quick runs must not silently overfit to the majority
                        class (the full set is 48/30/22 entailment/neutral/
                        contradiction, so index-order slicing is class-biased)
"""
import random
from collections import defaultdict
from typing import Dict, List


def balanced_sample(records: List[Dict], n: int,
                    key=lambda r: r["entailment_label"],
                    seed: int = 42) -> List[Dict]:
    """Seeded class-stratified sample of up to n records.

    Round-robin over classes so small classes are exhausted before the
    majority class is padded, preserving the requested total. Records are
    first sorted by a stable id (index in the file) so the result never
    depends on dict iteration or input order quirks.
    """
    if n <= 0 or n >= len(records):
        return list(records)

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for i, rec in enumerate(records):
        groups[str(key(rec))].append((i, rec))

    rng = random.Random(seed)
    for items in groups.values():
        rng.shuffle(items)

    # Round-robin pick, largest class first, until n collected.
    buckets = sorted(groups.values(), key=len, reverse=True)
    picked: List = []
    idx = 0
    while len(picked) < n:
        added = False
        for bucket in buckets:
            if idx < len(bucket):
                picked.append(bucket[idx])
                added = True
                if len(picked) >= n:
                    break
        if not added:
            break
        idx += 1

    picked.sort(key=lambda t: t[0])
    return [rec for _, rec in picked]


def label_counts(records: List[Dict],
                 key=lambda r: r["entailment_label"]) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for rec in records:
        out[str(key(rec))] += 1
    return dict(sorted(out.items()))