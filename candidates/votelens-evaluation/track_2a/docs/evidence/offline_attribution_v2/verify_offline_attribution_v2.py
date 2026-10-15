#!/usr/bin/env python3
"""Re-runnable aggregate and per-case checks for the vote-aware-paired-v2 offline
verification (offline_attribution_v2, 13 October 2026).

STATUS: re-run 13 October 2026 against the local
`data/experiments/vote-aware-paired-v2/predictions.jsonl`. Those raw records and
the earlier `offline_attribution_v1` annotations are present in this working tree
(Git-ignored) and were reproduced here; the 29-case contingency table was
recomputed from the raw records, not transcribed. A clean Git checkout does not
contain the ignored tree, so these per-case checks skip there and only the tracked
aggregate checks run. Run with `python3 verify_offline_attribution_v2.py`.

Checks (all on tracked or restored files, no inference, no model call):
  1. Arithmetic of the tracked compact audit
     (docs/evidence/vote_aware_paired_results_20261013.json).
  2. Exact two-sided McNemar p from the paired strict counts.
  3. Frozen-plan membership: template case rows 2504/1200/567/1311 must NOT be
     in the 81-row plan from which the 54 paired cases were drawn.
  4. Raw-record probe (skipped if the ignored tree is absent): SHA-256 of
     data/experiments/vote-aware-paired-v2/predictions.jsonl against the hash
     recorded in the compact audit, then a per-case recount of the 29 rejected
     vote-aware outputs. The recount must reproduce the recorded aggregate exactly:
       * rejection taxonomy 14 vote_unrecognised + 15 invalid_vote_status = 29;
       * gold split entailment 3 / neutral 18 / contradiction 8;
       * raw-predicted-label split entailment 0 / neutral 15 / contradiction 14;
       * raw-correct 18 and raw-incorrect 11;
       * every rejection carries citations=[] and citation_verified=false, i.e.
         the citation fields are present-but-empty, not missing JSON keys.

A failing check means a tracked summary no longer reproduces; preserve the files
and investigate rather than editing any frozen artefact. Citation provenance and
semantic support are distinct here: none of the 29 rejections had a quotation, so
semantic-sufficiency verification was neither run nor skipped-by-accident, and
nothing in this script asserts that a rejected citation passed or failed it.
"""
import hashlib
import json
import os
import sys
from collections import Counter
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE is <root>/docs/evidence/offline_attribution_v2; three levels up is the
# project root (track_2a), NOT track_2a/docs.
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
AUDIT = os.path.join(ROOT, "docs", "evidence",
                     "vote_aware_paired_results_20261013.json")
PLAN = os.path.join(ROOT, "docs", "evidence",
                    "paired_grouped81_plan_20261011.json")
PREDICTIONS = os.path.join(ROOT, "data", "experiments",
                           "vote-aware-paired-v2", "predictions.jsonl")
TEMPLATE_IDS = (2504, 1200, 567, 1311)
RECORDED_PREDICTIONS_SHA256 = (
    "1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe")

failures = []


def check(name, ok, detail=""):
    detail = str(detail)
    print(("PASS " if ok else "FAIL ") + name + (": " + detail if detail else ""))
    if not ok:
        failures.append(name)


def mcnemar_two_sided(b, c, n):
    """Exact two-sided binomial tail; equals the recorded McNemar p."""
    m = max(b, c)
    tail = sum(comb(n, k) for k in range(m, n + 1)) / 2 ** n
    return min(1.0, 2.0 * tail)


def main():
    with open(AUDIT, encoding="utf-8") as handle:
        audit = json.load(handle)
    arms = audit["arms"]
    candidate = arms["vote-aware-v1"]
    dense = arms["dense-v1"]
    failure_audit = audit["candidate_failure_audit"]
    paired = audit["paired_strict_accuracy"]

    kinds = candidate["error_kinds"]
    check("error kinds sum to 29 rejections",
          kinds["vote_unrecognised"] == 14
          and kinds["invalid_vote_status"] == 15
          and sum(kinds.values()) == candidate["errors"] == 29,
          "14 + 15 = 29")
    check("raw-label split sums to rejections",
          failure_audit["raw_label_correct"] + failure_audit["raw_label_incorrect"]
          == failure_audit["rejected_outputs"] == 29
          and failure_audit["raw_label_present"] == 29,
          "18 + 11 = 29")
    neutral = failure_audit["gold_neutral"]
    check("gold-neutral rejection split", neutral["n"] == neutral["rejected"] == 18
          and neutral["accepted_correct"] == 0
          and neutral["raw_neutral"] + neutral["raw_contradiction"] == 18,
          "12 + 6 = 18, 0 accepted")
    check("accepted + rejected covers all 54 cases",
          25 + failure_audit["rejected_outputs"] == candidate["n"] == 54)
    strict = failure_audit["strict_correct_by_gold"]
    check("strict-by-gold sums to 23 accepted-correct",
          strict["entailment"] + strict["neutral"] + strict["contradiction"] == 23)
    check("arm totals", candidate["raw_label_accuracy"] == 0.7593
          and dense["raw_label_accuracy"] == 0.7407
          and dense["errors"] == 11)
    check("paired strict table sums to 54",
          paired["dense_only_correct"] + paired["vote_aware_only_correct"]
          + paired["both_correct"] + paired["both_incorrect"] == 54,
          "18 + 9 + 14 + 13 = 54")
    recomputed = mcnemar_two_sided(paired["dense_only_correct"],
                                   paired["vote_aware_only_correct"], 27)
    check("McNemar p reproduces recorded value",
          abs(recomputed - 0.122078) < 5e-7,
          "recomputed %.8f vs recorded 0.122078" % recomputed)

    with open(PLAN, encoding="utf-8") as handle:
        plan = json.load(handle)
    row_indices = plan["plan"]["row_indices"]
    for row in TEMPLATE_IDS:
        check("template case row %d absent from frozen 81-row plan" % row,
              row not in row_indices)
    check("max plan row index below dataset size 1488",
          max(row_indices) < 1488, "max = %d" % max(row_indices))

    if not os.path.exists(PREDICTIONS):
        print("INFO raw predictions ABSENT (ignored tree not present here): %s"
              % PREDICTIONS)
        print("INFO restore them, recheck the recorded SHA-256, then complete "
              "the per-case identity/sufficiency annotation before any "
              "validation-policy change.")
        return finish()

    raw = open(PREDICTIONS, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    check("local predictions.jsonl matches recorded SHA-256",
          digest == RECORDED_PREDICTIONS_SHA256, digest)

    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()
               if line.strip()]
    cand = [r for r in records if r.get("arm") == "vote-aware-v1"]
    check("candidate-arm case count is 54 (one per paired case)", len(cand) == 54,
          "n = %d" % len(cand))
    rejected = [r for r in cand if not r.get("valid_output")]
    check("rejected candidate outputs are 29", len(rejected) == 29,
          "n = %d" % len(rejected))

    gold = Counter(r.get("gold") for r in rejected)
    check("recount gold split matches recorded 3/18/8",
          gold.get("entailment") == 3 and gold.get("neutral") == 18
          and gold.get("contradiction") == 8, dict(gold))
    raw_lab = Counter(r.get("raw_label") for r in rejected)
    check("recount raw-predicted-label split (0 entailment / 15 neutral / "
          "14 contradiction)",
          raw_lab.get("entailment", 0) == 0 and raw_lab.get("neutral") == 15
          and raw_lab.get("contradiction") == 14, dict(raw_lab))
    correct = sum(1 for r in rejected if r.get("raw_correct"))
    check("recount raw-correct/incorrect = 18/11", correct == 18
          and len(rejected) - correct == 11,
          "correct %d / incorrect %d" % (correct, len(rejected) - correct))
    err = Counter(r.get("result", {}).get("error") for r in rejected)
    check("recount error kinds 14 vote_unrecognised / 15 invalid_vote_status",
          err.get("vote_unrecognised") == 14
          and err.get("invalid_vote_status") == 15, dict(err))
    # The raw recount must agree with the recorded aggregate, not just the task.
    check("recount agrees with recorded aggregate",
          correct == failure_audit["raw_label_correct"]
          and len(rejected) == failure_audit["rejected_outputs"]
          and gold.get("neutral") == failure_audit["gold_neutral"]["rejected"],
          "recomputed table == recorded audit")
    empty_cit = all(r.get("result", {}).get("citations") == []
                    and r.get("result", {}).get("citation_verified") is False
                    for r in rejected)
    check("rejections carry empty citations (present-but-empty, not missing)",
          empty_cit, "citations=[] and citation_verified=false on all rejections")

    required_case_ids = {r["case_id"] for r in rejected}
    check("all 29 rejected case IDs are present in the raw records",
          len(required_case_ids) == 29, "distinct case_ids = %d"
          % len(required_case_ids))
    for row in TEMPLATE_IDS:
        cid = "official-row-%d" % row
        check("template case %s is not one of the 29 rejections" % cid,
              cid not in required_case_ids)

    return finish()


def finish():
    if failures:
        print("RESULT: %d check(s) failed" % len(failures))
        return 1
    print("RESULT: all executed checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())