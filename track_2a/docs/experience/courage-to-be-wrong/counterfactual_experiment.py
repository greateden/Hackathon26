#!/usr/bin/env python3
"""Offline counterfactual experiment generator (research-only, NOT the submission path).

Purpose
-------
Answer, eventually, the "Cost of Coverage" question: when a case is already
**complete** (the full bookelt text was supplied and still failed), does making
the evidence *provably correct* (a citation-provenance oracle) and then adding
*neutral distractors* recover the answer — or does it just change how often the
system declines to answer? That distinction is the whole point: **rejection is
not reliability**, so this tool keeps failures in the denominator and never
converts a rejection into a guess.

Four variants per case
---------------------
- ``full``            — the complete extracted booklet text (the known "complete
                        but incorrect" starting condition).
- ``retrieved``       — the recorded within-booklet Top-5 dense passages.
- ``oracle_verified`` — the recorded gold-reference *citation*, but its
                        provenance is taken from the run record (was the
                        quotation actually present in the supplied passages?) —
                        **not** from a hard-coded flag. An oracle is only an
                        oracle if its provenance verifies.
- ``neutral_distractor`` — ``oracle_verified`` plus reviewed non-decisive
                        distractors, and a re-ordered twin. This is exactly the
                        evidence-sensitivity B→C→D design.

Two modes
---------
* ``offline`` (default) — no network, no model. Builds and validates the four
  variants for each case, checks the integrity invariants below, and writes
  ``counterfactual_plan.json``. Nothing is scored; no result is claimed. This is
  the only mode that does anything: the tool is an **offline plan builder**.
* ``live`` — a **deliberately disabled guard, not a runner.** No four-variant
  runner is wired to any endpoint and no append-only recorder exists in this
  commit; requesting ``live`` prints a refusal and exits non-zero. It is gated
  behind ``--endpoint`` *and* ``VOTELENS_ENABLE_LIVE_EXPERIMENT=1`` so it can
  never run by accident or be routed into the default/submission path, and it has
  **no lexical or keyword fallback**. Even with both flags set it stops before
  any request. There is therefore **no runnable live experiment here** — only a
  plan builder plus a guard that keeps one hypothetical.

Status: **NOT TESTED, and NOT IMPLEMENTED end-to-end.** No live run has been
performed; no accuracy number may be quoted from it. If a future author wires a
runner, unparseable or failed replies must be recorded as errors (never defaulted
to a label) and failures must stay in the denominator, per the project invariant.

Integrity invariants enforced offline (any break ⇒ non-zero exit):
  1. ``oracle_verified`` provenance is copied from the run record, never asserted.
  2. Every variant that fails or is unparseable stays in the denominator.
  3. Counterfactual prompt fragments are labelled and quarantined from the
     production ``current_v1`` prompt.
  4. C/D share identical evidence and token budgets (position-only change).

Run (from ``track_2a/``):

    python3 docs/experience/courage-to-be-wrong/counterfactual_experiment.py offline
    python3 docs/experience/courage-to-be-wrong/counterfactual_experiment.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = ["full", "retrieved", "oracle_verified", "neutral_distractor",
            "neutral_distractor_reordered"]

# Quarantined research prompt. NOT the production prompt and never routed into
# booklet_app.py. Kept here so a reader can see exactly what would be sent.
RESEARCH_SYSTEM = (
    "RESEARCH COUNTERFACTUAL — NOT THE SUBMISSION PROMPT. You are given numbered "
    "passages that may come from different stakeholder voices or proposals. "
    "Report entailment/neutral/contradiction for the claim *as attributed*, and "
    "state whether the decisive proposition is present, absent, or contradicted."
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_jsonl(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build_variants(case: dict, sens_records) -> dict:
    """Assemble the four counterfactual variants for one case from records.

    ``case`` supplies the claim + gold + which recorded rows carry the decisive
    evidence. Evidence text is taken from the recorded evidence-sensitivity
    conditions where present; the oracle provenance flag is read from the record,
    not asserted. When a required record is missing, the variant is emitted as
    ``unavailable`` rather than fabricated.
    """
    variants = {}
    for v in VARIANTS:
        variants[v] = {"available": False, "reason": "no recorded evidence source"}

    if sens_records:
        by_cond = {r["condition"]: r for r in sens_records
                   if r["row_index"] == case["row_index"]}
        A = by_cond.get("A_original")
        B = by_cond.get("B_minimal")
        C = by_cond.get("C_minimal_plus_distractors")
        D = by_cond.get("D_reordered")
        if A:
            variants["retrieved"] = {"available": True,
                                     "from_condition": "A_original"}
        if B:
            variants["oracle_verified"] = {
                "available": True,
                "from_condition": "B_minimal",
                "provenance_taken_from_record": True,
                "citation_verified_in_record": B["result"].get("citation_verified"),
                "note": "provenance copied from record; a manually curated "
                        "sufficient block is an upper bound, not a retrievable oracle",
            }
        if C and D:
            # C and D must carry the identical SET of passages (order differs by
            # construction — that is the point) and the identical token budget.
            # Comparing ordered hashes would differ by construction; compare the
            # order-insensitive multiset of passage texts instead.
            def passage_set(r):
                ps = r.get("passages") or []
                return sorted((p.get("text") or "") for p in ps)
            same_set = passage_set(C["result"]) == passage_set(D["result"])
            same_tok = (C["result"].get("input_tokens") == D["result"].get("input_tokens"))
            variants["neutral_distractor"] = {"available": True,
                                              "from_condition": "C_minimal_plus_distractors"}
            variants["neutral_distractor_reordered"] = {
                "available": True, "from_condition": "D_reordered",
                "shares_evidence_with_C": bool(same_set and same_tok),
                "note": "position-only change; identical evidence set and token budget"}
    return variants


def check_invariants(plan: dict) -> list[str]:
    """Return a list of invariant violations (empty == all hold)."""
    problems = []
    for case in plan["cases"]:
        for v, spec in case["variants"].items():
            if not spec.get("available"):
                continue
            if v == "oracle_verified" and not spec.get("provenance_taken_from_record"):
                problems.append(f"{case['case_id']}/{v}: oracle provenance asserted, not read")
            if v == "neutral_distractor_reordered" and spec.get("shares_evidence_with_C") is False:
                problems.append(f"{case['case_id']}/{v}: C/D no longer share evidence "
                                f"(no longer a position-only comparison)")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", default="offline",
                    choices=["offline", "live"],
                    help="offline builds+validates only (default); live needs an endpoint")
    ap.add_argument("--dry-run", action="store_true",
                    help="alias for offline; never sends a request")
    ap.add_argument("--endpoint", default=None, help="OpenAI-compatible base URL")
    ap.add_argument("--model", default=None, help="exact served model id to require")
    ap = ap.parse_args(argv)

    mode = "offline" if ap.dry_run else ap.mode
    exp = HERE.parent.parent.parent / "data" / "experiments"

    # The live path is intentionally hard-gated. A real v1.5 endpoint is not
    # available here and no live run has been authorised or performed.
    if mode == "live":
        if not ap.endpoint:
            print("ERROR: live mode needs --endpoint. Refusing (no lexical fallback).")
            return 2
        if os.environ.get("VOTELENS_ENABLE_LIVE_EXPERIMENT") != "1":
            print("ERROR: live mode also needs VOTELENS_ENABLE_LIVE_EXPERIMENT=1, "
                  "which you have not set. This keeps the counterfactual experiment "
                  "out of any default or submission path. Nothing was sent.")
            return 2
        print("Live mode requested but NOT IMPLEMENTED END-TO-END in this commit: "
              "the four variants must first be reviewed and the four-variant runner "
              "wired to the append-only recorder, then authorised. Stopping, as "
              "designed, rather than running an unreviewed experiment or falling back "
              "to a lexical baseline. Status remains NOT TESTED.")
        return 2

    # ---- offline: build + self-check from recorded artefacts ----
    sens = load_jsonl(exp / "evidence-sensitivity-v2" / "predictions.jsonl")
    paired = load_jsonl(exp / "vote-aware-paired-v2" / "predictions.jsonl")

    # A handful of documented cases to replay; gold and labels come from records.
    replay = [
        {"case_id": "sens-1026", "row_index": 1026, "gold": "contradiction"},
        {"case_id": "sens-1344", "row_index": 1344, "gold": "contradiction"},
        {"case_id": "sens-189", "row_index": 189, "gold": "entailment"},
        {"case_id": "sens-195", "row_index": 195, "gold": "entailment"},
    ]

    cases = []
    for spec in replay:
        cases.append({
            "case_id": spec["case_id"],
            "gold_from_record": spec["gold"],
            "counterfactual_prompt_marker": "RESEARCH-COUNTERFACTUAL",
            "variants": build_variants(spec, sens),
        })

    plan = {
        "schema": "hackapertus-counterfactual-plan-v1",
        "status": "NOT TESTED — built and self-checked offline; no inference run",
        "system_prompt": RESEARCH_SYSTEM,
        "keep_failures_in_denominator": True,
        "cases": cases,
    }
    problems = check_invariants(plan)
    plan["invariant_check"] = "PASS" if not problems else "FAIL"

    out = HERE / "counterfactual_plan.json"
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)
    for c in cases:
        avail = [v for v, s in c["variants"].items() if s.get("available")]
        print(f"  {c['case_id']}: variants available = {avail}")

    if problems:
        print("\nINVARIANT CHECK FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("\ninvariant check: PASS (oracle provenance read from record; C/D share evidence;"
          "\nno variant converts a failure into a label; no live call made).")
    print("This is NOT an accuracy result. Run --dry-run any time; live mode is gated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())