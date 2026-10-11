"""Offline error analysis for recorded NLI eval runs (no model, no network).

Joins recorded result JSONs (eval_nli.py output) back to the eval set rows
by reproducing the seeded dev split, then reports:
  1. per-class confusion + prediction distribution (bias check),
  2. per claim->evidence-language-pair accuracy,
  3. same-language vs cross-language accuracy,
  4. item-level oracle <-> retrieve agreement and flip patterns,
  5. evidence-shape proxies: oracle reference length/truncation, retrieve
     prompt-token counts (proxy for how much text the judge actually saw).

Usage (from src/):
    python3 diag_eval_errors.py DATA/eval_results_A.json DATA/eval_results_B.json
With one file, skips the cross-run comparison.
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR
from labels import CODE_TO_LABEL

DEFAULT_DATA = DATA_DIR / "eval" / "mnli_swiss_v1.1.jsonl"
DEV_SEED = 20261009
DEV_SIZE = 60
EVIDENCE_MAX_CHARS = 1900
CLASSES = ["entailment", "neutral", "contradiction"]


def load_rows(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def dev_indices(n, seed=DEV_SEED, size=DEV_SIZE):
    rng = random.Random(seed)
    return sorted(set(rng.sample(range(n), min(size, n))))


def confusion_and_bias(results, title):
    print(f"\n=== {title} ===")
    conf = {g: Counter() for g in CLASSES}
    for r in results:
        conf[r["gold"]][r["pred"] or "ERROR"] += 1
    header = "gold \\ pred " + "".join(f"{c[:12]:>14}" for c in CLASSES) + f"{'ERROR':>8}"
    print(header)
    for g in CLASSES:
        row = "".join(f"{conf[g][c]:>14}" for c in CLASSES)
        print(f"{g:<13}{row}{conf[g]['ERROR']:>8}")
    pred = Counter(r["pred"] or "ERROR" for r in results)
    gold = Counter(r["gold"] for r in results)
    print(f"pred dist: {dict(pred)}   gold dist: {dict(gold)}")
    acc = sum(1 for r in results if r["correct"]) / len(results)
    print(f"accuracy: {acc:.3f}")


def by_pair(results, title):
    print(f"\n=== {title}: accuracy by claim->evidence language pair ===")
    stats = defaultdict(lambda: [0, 0])
    for r in results:
        pair = r.get("pair", "?")
        stats[pair][0] += r["correct"]
        stats[pair][1] += 1
    for pair in sorted(stats, key=lambda p: -stats[p][1]):
        ok, n = stats[pair]
        same = "->" in pair and pair.split("->")[0] == pair.split("->")[1]
        tag = "same" if same else "cross"
        print(f"  {pair:<10} [{tag}] {ok:>2}/{n:<2} = {ok/n:.3f}")
    same_ok = same_n = cross_ok = cross_n = 0
    for r in results:
        a, _, b = r.get("pair", "?").partition("->")
        if a == b:
            same_ok += r["correct"]; same_n += 1
        else:
            cross_ok += r["correct"]; cross_n += 1
    if same_n:
        print(f"  SAME-LANG  total: {same_ok}/{same_n} = {same_ok/same_n:.3f}")
    if cross_n:
        print(f"  CROSS-LANG total: {cross_ok}/{cross_n} = {cross_ok/cross_n:.3f}")



def main():
    files = sys.argv[1:]
    if not files:
        sys.exit("usage: diag_eval_errors.py results1.json [results2.json]")
    rows = load_rows(DEFAULT_DATA)
    idx = dev_indices(len(rows))
    dev_rows = [rows[i] for i in idx]

    runs = []
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        runs.append((Path(f).name, data))

    # alignment check against the reproduced dev subset
    for name, data in runs:
        items = data["items"]
        mism = sum(1 for a, b in zip(items, dev_rows)
                   if a["claim"].strip() != b["claim"][:300].strip())
        state = "ALIGNED with seeded dev subset" if mism == 0 \
            else f"{mism} alignment mismatches (order/content differs!)"
        print(f"{name}: {len(items)} items, {state}")

    for name, data in runs:
        mode = data["meta"].get("evidence_mode", "?")
        confusion_and_bias(data["items"], f"{name} ({mode}) confusion")
        by_pair(data["items"], f"{name} ({mode})")

    # evidence-shape proxies
    for name, data in runs:
        mode = data["meta"].get("evidence_mode", "?")
        print(f"\n=== {name}: evidence-shape proxies ===")
        if mode == "oracle":
            lens = [len(r["reference_string"]) for r in dev_rows]
            trunc = sum(1 for l in lens if l > EVIDENCE_MAX_CHARS)
            med = sorted(lens)[len(lens) // 2]
            print(f"oracle reference_string chars: min={min(lens)} "
                  f"median={med} max={max(lens)}; truncated at "
                  f"{EVIDENCE_MAX_CHARS}: {trunc}/{len(lens)}")
            xlang = sum(1 for r in dev_rows
                        if r.get("claim_language") != r.get("reference_language"))
            print(f"oracle evidence in a DIFFERENT language than the claim: "
                  f"{xlang}/{len(dev_rows)}")
        else:
            pt = [r["usage"]["prompt_tokens"] for r in data["items"]
                  if r.get("usage", {}).get("prompt_tokens")]
            ct = [r["usage"]["completion_tokens"] for r in data["items"]
                  if r.get("usage", {}).get("completion_tokens")]
            no_ev = sum(1 for r in data["items"] if r.get("no_evidence"))
            print(f"retrieve prompt_tokens: n={len(pt)} min={min(pt)} "
                  f"median={sorted(pt)[len(pt)//2]} max={max(pt)}")
            med_c = sorted(ct)[len(ct) // 2]
            print(f"retrieve completion_tokens: min={min(ct)} median={med_c} "
                  f"max={max(ct)} (max_tokens cap=400; rambly output)")
            print(f"items flagged no_evidence: {no_ev}")
            big = [r for r in data["items"]
                   if r.get("usage", {}).get("prompt_tokens", 0) > 900]
            small = [r for r in data["items"]
                     if "usage" in r and 0 < r["usage"].get("prompt_tokens", 0) <= 900]
            if big and small:
                print(f"prompt_tokens > 900: "
                      f"{sum(1 for r in big if r['correct'])}/{len(big)} correct; "
                      f"<= 900: {sum(1 for r in small if r['correct'])}/{len(small)} correct")

    # cross-run comparison (same 60 items, same order)
    if len(runs) == 2:
        (na, da), (nb, db) = runs
        ia, ib = da["items"], db["items"]
        if len(ia) != len(ib):
            print("\n(runs have different item counts; skipping comparison)")
            return
        print("\n=== oracle vs retrieve item-level comparison ===")
        both_ok = both_bad = mixed = 0
        flips = Counter()
        for a, b in zip(ia, ib):
            if a["claim"].strip() != b["claim"].strip():
                print("  WARNING: item misalignment at claim:", a["claim"][:60])
                continue
            ca, cb = a["correct"], b["correct"]
            if ca and cb:
                both_ok += 1
            elif not ca and not cb:
                both_bad += 1
            else:
                mixed += 1
                flips[(f"A={a['pred']}", f"B={b['pred']}", f"gold={a['gold']}")] += 1
        print(f"both correct: {both_ok}  both wrong: {both_bad}  one-way: {mixed}")
        print(f"flip patterns (A={na[:28]} | B={nb[:28]}):")
        for k, v in flips.most_common(20):
            print("  ", " ".join(k), "x", v)
        agr = Counter()
        for a, b in zip(ia, ib):
            if a["pred"] and b["pred"]:
                agr[(a["gold"], "agree" if a["pred"] == b["pred"] else "disagree")] += 1
        print("pred agreement between modes:", dict(agr))


if __name__ == "__main__":
    main()

