"""Offline audit of the 2x2 evidence-processing factorial (no model, no server).

Context (report §4.3): `select` bundles TWO evidence factors - `fill`
evidence style and the claim-lexical window selector - so the first ablation
could not attribute its retrieve gain (+2 items) or its oracle loss (-6
items) to either factor. Two single-factor arms now exist in PROMPT_CONFIGS:

    fill_only    fill style, no window      window_only  drop style, window on

This script decides WITHOUT any inference which new runs would be redundant,
by comparing rendered model inputs and the token counts recorded in the
saved 2026-10-10 ablation runs:

  A) retrieve mode: the window flag never fires (select_window is wired
     into eval_nli.oracle_evidence only), so fill_only would render
     identically to `select` and window_only to `t0`. It also counts where
     the style factor ACTUALLY bit (per-item prompt_tokens differ) and
     checks that recorded label flips sit inside that set - a flip on an
     item with identical prompt_tokens would be decoding noise, not a
     configuration effect.
  B) oracle mode: evidence is a single chunk of <= EVIDENCE_MAX_CHARS,
     always inside format_evidence's 2000-char cap, so style is inert:
     fill_only renders identically to `t0`, window_only to `select`.
     Verified per dev item by rendering both prompts and comparing bytes.
  C) flip audit: the oracle items where `select` changed the label versus
     its paired `t0` control are classified by what the window did to the
     evidence (moved nowhere / dropped negation cues / gained cues /
     moved region with no cue delta).

Reads only saved artefacts (data/eval/mnli_swiss_v1.1.jsonl +
data/ablation_*.json + the per-run eval_results_*.json files it lists).
If a future ablation includes fill_only / window_only runs, section B also
verifies end-to-end that equivalent cells produced identical predictions.

Usage (from src/):
    python3 diag_evidence_ablation.py
    python3 diag_evidence_ablation.py --ablation ../data/ablation_20261010_122340_openai.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR
from eval_nli import (DEFAULT_DATA, DEV_SEED, DEV_SIZE, EVIDENCE_MAX_CHARS,
                      load_rows, oracle_evidence, select_window,
                      split_indices)
from nli_judge import build_chat, get_prompt_config

# crude negation/contradiction markers (same spirit as LexicalJudge._NEG)
NEG_MARKERS = ("nicht ", " ne pas ", "kein ", "widerspr", "lehnen",
               "ablehn", " reject ", "refuse", "refus", "contradic",
               "no ", "non ")

# Equivalent render pairs (config_a, evidence_a, config_b, evidence_b):
# byte-identical model inputs are expected; runs of the twin cells would be
# redundant inference, and differing predictions prove nondeterminism.
EQUIV_PAIRS = [
    ("fill_only", "retrieve-v2", "select", "retrieve-v2"),
    ("window_only", "retrieve-v2", "t0", "retrieve-v2"),
    ("fill_only", "oracle", "t0", "oracle"),
    ("window_only", "oracle", "select", "oracle"),
]
# --- helpers -----------------------------------------------------------------
def neg_count(text):
    low = " " + text.lower().replace("\n", " ") + " "
    return sum(low.count(m) for m in NEG_MARKERS)


def chat_of(cfg, claim, passages):
    return build_chat(get_prompt_config(cfg), claim, passages)


def dev_items():
    if not DEFAULT_DATA.exists():
        return None
    rows = load_rows(DEFAULT_DATA)
    return [rows[i] for i in split_indices(len(rows), "dev",
                                            DEV_SEED, DEV_SIZE)]


def load_runs(ablation_path):
    """Index ablation summary + per-run payloads by (cfg, evidence, rep)."""
    data = json.loads(Path(ablation_path).read_text(encoding="utf-8"))
    runs = {}
    for r in data["runs"]:
        f = Path(r["file"])
        if not f.exists():
            f = DATA_DIR / Path(r["file"]).name
        if not f.exists():
            print(f"[skip] run file missing: {r['file']}")
            continue
        payload = json.loads(f.read_text(encoding="utf-8"))
        runs[(r["config"], r["evidence"], r["rep"])] = payload
    return runs


def compare_runs(run_a, run_b):
    """Per-item (prompt_tokens, pred) comparison between two recorded runs."""
    a_items = {it["index"]: it for it in run_a["items"]}
    b_items = {it["index"]: it for it in run_b["items"]}
    if (not a_items or set(a_items) != set(b_items)
            or len(a_items) != len(run_a["items"]) or len(b_items) != len(run_b["items"])):
        raise ValueError("Comparison requires non-empty unique matching row IDs")
    tok_diff, pred_diff = [], []
    for idx in sorted(set(a_items) & set(b_items)):
        a, b = a_items[idx], b_items[idx]
        ta = a.get("usage", {}).get("prompt_tokens")
        tb = b.get("usage", {}).get("prompt_tokens")
        if ta is not None and tb is not None and ta != tb:
            tok_diff.append(idx)
        if a.get("pred") != b.get("pred"):
            pred_diff.append((idx, a.get("pred"), b.get("pred"),
                              ta, tb))
    return len(a_items), tok_diff, pred_diff

def part_a_oracle_equivalence(items):
    print("A) oracle-mode render equivalence (recomputed, no model):")
    bad_tf = bad_wt = moved = 0
    for it in items:
        if chat_of("t0", it["claim"],
                   oracle_evidence(it, get_prompt_config("t0"))) \
                != chat_of("fill_only", it["claim"],
                           oracle_evidence(it, get_prompt_config("fill_only"))):
            bad_tf += 1
        if chat_of("select", it["claim"],
                   oracle_evidence(it, get_prompt_config("select"))) \
                != chat_of("window_only", it["claim"],
                           oracle_evidence(it, get_prompt_config("window_only"))):
            bad_wt += 1
        if select_window(it["reference_string"], it["claim"],
                         EVIDENCE_MAX_CHARS) \
                != it["reference_string"][:EVIDENCE_MAX_CHARS]:
            moved += 1
    n = len(items)
    ok = bad_tf == 0 and bad_wt == 0
    print(f"   t0 == fill_only renders identical: {n - bad_tf}/{n}; "
          f"select == window_only: {n - bad_wt}/{n}")
    print(f"   items where the window actually selects a different region "
          f"than the head cut: {moved}/{n}")
    print("   -> " + ("PASS: in oracle mode fill_only duplicates `t0` and "
                      "window_only duplicates `select` (style inert on a "
                      "single sub-cap chunk)."
                      if ok else
                      "FAIL: a supposed equivalence broke - do NOT treat "
                      "the factorial as measured; investigate first."))
    return ok


def part_b_recorded(runs):
    print("\nB) recorded retrieve-mode evidence (token-count proxy):")
    t0r = runs.get(("t0", "retrieve-v2", 1))
    t0r2 = runs.get(("t0", "retrieve-v2", 2))
    selr = runs.get(("select", "retrieve-v2", 1))
    if not (t0r and selr):
        print("   [fail] required t0/select retrieve-v2 runs are missing")
        return False
    ok = True
    if t0r2:
        n, tok, pred = compare_runs(t0r, t0r2)
        print(f"   paired t0 controls: {n} items, token mismatches "
              f"{len(tok)}, prediction mismatches {len(pred)} "
              f"(expect 0/0 under T=0)")
        ok = ok and not tok and not pred
    n, tok, pred = compare_runs(t0r, selr)
    print(f"   t0 vs select (retrieve): style factor changed the prompt on "
          f"{len(tok)}/{n} items; label flips: {len(pred)}")
    for idx, pa, pb, ta, tb in pred:
        src = "prompt differed" if idx in tok else \
            "equal token counts; prompt identity and cause unverified"
        print(f"     item {idx}: {pa} -> {pb} ({src}; tokens {ta} vs {tb})")
        ok = ok and idx in tok
    # Redundancy/determinism check for twin cells (fires once the optional
    # spot-check runs of fill_only / window_only are recorded).
    for ca, ea, cb, eb in EQUIV_PAIRS:
        ra = runs.get((ca, ea, 1))
        rb = runs.get((cb, eb, 1)) or runs.get((cb, eb, 2))
        if ra and rb:
            n, tok, pred = compare_runs(ra, rb)
            flag = ("PASS (matching recorded labels; prompt identity needs separate verification)"
                    if not pred else
                    "MISMATCH - equivalence hypothesis or determinism broken")
            print(f"   twin cells {ca}/{ea} vs {cb}/{eb}: {n} items, "
                  f"token diffs {len(tok)}, label diffs {len(pred)} - {flag}")
            ok = ok and not pred
    return ok

def part_c_oracle_flips(runs, items):
    print("\nC) oracle flip audit (select vs paired t0 control):")
    t0o = runs.get(("t0", "oracle", 1))
    selo = runs.get(("select", "oracle", 1))
    if not (t0o and selo):
        print("   [skip] need recorded oracle t0 + select runs")
        return True
    if not items or len(t0o["items"]) != len(items):
        print(f"   [skip] audit needs the full {len(t0o['items'])}-item dev "
              f"set locally; found {len(items) if items else 0}")
        return True
    t0_items = {it["index"]: it for it in t0o["items"]}
    sel_items = {it["index"]: it for it in selo["items"]}
    cats = {}
    for idx in sorted(t0_items):
        a, b = t0_items[idx], sel_items.get(idx)
        if b is None or a.get("pred") == b.get("pred"):
            continue
        it = items[idx - 1]
        ref = it["reference_string"]
        head = ref[:EVIDENCE_MAX_CHARS]
        win = select_window(ref, it["claim"], EVIDENCE_MAX_CHARS)
        same_input = win == head
        nh, nw = neg_count(head), neg_count(win)
        if same_input:
            cat = "same-evidence (window did not move)"
        elif nw < nh:
            cat = f"dropped negation cues ({nh}->{nw})"
        elif nw > nh:
            cat = f"gained negation cues ({nh}->{nw})"
        else:
            cat = f"region moved, no cue delta ({nh}=={nw})"
        cats[cat] = cats.get(cat, 0) + 1
        delta = ("fixed" if b["correct"] else
                 "broke" if a["correct"] else "wrong->wrong")
        print(f"   item {idx:>2} [{it.get('claim_language')}->"
              f"{it.get('reference_language')}] gold={a['gold']}: "
              f"{a.get('pred')} -> {b.get('pred')} ({delta}); {cat}")
    print("   category counts: "
          + "; ".join(f"{k}: {v}" for k, v in sorted(cats.items()))
          if cats else "   no oracle flips recorded")
    return True


def main():
    ap = argparse.ArgumentParser(
        description="offline audit of the evidence-processing factorial")
    ap.add_argument("--ablation", default=None,
                    help="ablation summary JSON (default: newest in data/)")
    args = ap.parse_args()

    path = Path(args.ablation) if args.ablation else None
    if path is None:
        candidates = sorted(DATA_DIR.glob("ablation_*.json"))
        if not candidates:
            sys.exit("no data/ablation_*.json found; run the ablation first "
                     "or pass --ablation")
        path = candidates[-1]
    print(f"audit input: {path}\n")

    runs = load_runs(path)
    items = dev_items()
    if items is None:
        print("[skip] eval set absent - oracle recomputation unavailable; "
              "run: python3 fetch_eval_data.py")

    ok = True
    if items:
        ok = part_a_oracle_equivalence(items) and ok
    ok = part_b_recorded(runs) and ok
    ok = part_c_oracle_flips(runs, items) and ok

    print("\nVERDICT:", "all expected equivalences hold" if ok
          else "equivalence or determinism premise violated - see above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
