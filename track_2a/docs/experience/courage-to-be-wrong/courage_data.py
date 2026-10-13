#!/usr/bin/env python3
"""Build the "Courage to Be Wrong" dataset from recorded experiment artefacts.

This is the *verification layer* of the experience, not a frontend convenience.
Two invariants:

1. The app shows numbers, not vibes. Every aggregate shown in the experience
   is recomputed here from the raw per-case records (``predictions.jsonl``).
   If a curated gloss disagrees with the records, the script prints the
   mismatch and exits non-zero — so a hand-typed figure cannot silently drift
   from what was actually run. This is the guard that refuses fabricated labels.

2. Nothing here mutates a frozen artefact. The raw records are read-only
   inputs. When the Git-ignored ``data/experiments/`` tree is absent (a clean
   Git checkout) the script does NOT overwrite the committed dataset; it keeps
   the published facts and records that the raw tree could *not* be re-verified.
   The committed ``facts.json``/``facts.js`` therefore always present
   verification as a **historical, build-time result** — never as "a clean
   checkout has just re-verified the ignored raw files". A reader who needs a
   fresh verification must supply the raw tree and re-run this script.

Provenance discipline (see ``attribution-verification.md``): every displayed
string is classed as one of SOURCE-RECORDED, PROGRAMMATIC (recomputed here),
AI-ANNOTATED (a model's own reasoning text), HYPOTHESIS, or NOT TESTED. Model
``reasoning`` strings are the *model's own output* copied verbatim from a
record; they are AI-ANNOTATED, not independent ground truth, and they are not
warranted to reproduce any booklet faithfully.

Run (from ``track_2a/``):

    ../.venv/bin/python docs/experience/courage-to-be-wrong/courage_data.py

or, with only the standard library available:

    python3 docs/experience/courage-to-be-wrong/courage_data.py

It writes ``facts.json`` and ``facts.js`` next to this file and prints a
self-check table. No model, no endpoint, no network, no inference.
"""
from __future__ import annotations

import json
import hashlib
import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent  # track_2a/
EXP = ROOT / "data" / "experiments"

PAIRED_JSONL = EXP / "vote-aware-paired-v2" / "predictions.jsonl"
SENS_JSONL = EXP / "evidence-sensitivity-v2" / "predictions.jsonl"

# SHA-256 of the *recorded* raw files, so a clean checkout can prove the
# dataset was built from the same bytes that produced the published numbers.
# BOTH are verified at build time; a mismatch on either fails the build closed.
PAIRED_SHA256 = "1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe"
SENS_SHA256 = "805550d07f9a7c69fea05269d6c2f2b055d43db635a8383d32a1b6497533dc85"

# Experiment each published identifier is sourced from. A gallery/lab case that
# is not found in its *declared* experiment, or whose gold disagrees with the
# record, is a hard failure — not a silent fall-through to hand-typed labels.
PAIRED_EXPERIMENT = "vote-aware-paired-v2"
SENS_EXPERIMENT = "evidence-sensitivity-v2"

# ---------------------------------------------------------------------------
# 1. Curated ledger facts, each with the value the records must reproduce.
#    A "claim under test" that disagrees with the records is shown in the
#    experience as VERIFIED-INCONSISTENT, i.e. the app deliberately reports
#    the wrong number it was handed, not the number someone assumed.
# ---------------------------------------------------------------------------
EXPECTED_LEDGER = {
    "rejections_total": 29,
    "gate_unrecognised": 14,
    "gate_null_or_invalid_status": 15,
    "raw_correct_among_rejections": 18,
    "raw_incorrect_among_rejections": 11,
    "gold_distribution": {"entailment": 3, "neutral": 18, "contradiction": 8},
    "raw_label_distribution": {"entailment": 0, "neutral": 15, "contradiction": 14},
    "gold_neutral_rejections": 18,
    "gold_neutral_rejections_raw_label_is_neutral": 12,
    "incorrect_by_gate": {"unrecognised": 8, "null_or_invalid_status": 3},
    "accepted_outputs": 25,
    "accepted_citation_verified": 25,
    "rejections_with_quotation": 0,
    "dense_valid": 43,
    "dense_invalid": 11,
    "dense_invalid_but_raw_correct": 8,
    "dense_invalid_citation_verified": 0,
}

# Claims handed to the ledger that the records contradict. Kept verbatim so
# the experience can show what was asserted vs what the records say. The point
# of the ledger is to be embarrassed on the project's behalf, not to flatter it.
LEDGER_CORRECTIONS = [
    {
        "asserted": "20 of 29 rejected outputs are correctly relabelled",
        "recorded": "18 of 29 carry a gold-matching raw label (11 do not)",
        "status": "VERIFIED-INCONSISTENT",
        "note": "The '20' appears in no record; it also conflated a different "
                "experiment whose rows were not members of this 54-case run.",
    },
    {
        "asserted": "18 of 29 rejections are neutral",
        "recorded": "18 have GOLD label neutral; 15 have PREDICTED label neutral. "
                    "Those are different sets of cases.",
        "status": "VERIFIED-AMBIGUOUS",
        "note": "Reading 'neutral' as the model output gives 15, not 18. The "
                "ledger separates gold from prediction to avoid exactly this.",
    },
    {
        "asserted": "only 4 (later: 9) of 18 neutral labels preserve the gold "
                    "neutral label",
        "recorded": "12 of the 18 gold-neutral rejections returned a raw label "
                    "of neutral; the other 6 returned contradiction.",
        "status": "VERIFIED-INCONSISTENT",
        "note": "At the raw-prediction level neutral is preserved 12/18. At the "
                "strict (accepted) level it is 0/18: every one of the 18 was "
                "rejected at the identity gate before its evidence could be "
                "verified. Neither 4 nor 9 matches.",
    },
    {
        "asserted": "5 of the 14 identity failures and 5 of the 15 schema "
                    "failures carry an incorrect label",
        "recorded": "the incorrect-label split by gate is 8 (unrecognised) + 3 "
                    "(null/invalid status) = 11",
        "status": "VERIFIED-INCONSISTENT",
        "note": "The 14/15 gate counts are right; the per-gate error counts are "
                "not. Citation verification never ran on any rejection (no "
                "quotation was produced), so no citation pass/fail exists to count.",
    },
    {
        "asserted": "example cases grouped81-p0-004, p0-028, p0-059",
        "recorded": "no such identifiers exist in any tracked or ignored record",
        "status": "NOT ESTABLISHED",
        "note": "The real documented representatives are official-row-1115, "
                "-728 and -964 (candidate rejections) and evidence-sensitivity "
                "rows 1026/1344/189/195. The experience uses those instead and "
                "does not invent neutral cases to fit a template.",
    },
    {
        "asserted": "in the grouped-81 cohort dense Top-5 had higher accuracy AND "
                    "higher coverage than full-booklet",
        "recorded": "dense had higher accuracy (65/81 vs 42/81) but LOWER "
                    "completion coverage: 80/81 vs 81/81 (one dense reply hit the "
                    "512-token output limit and stays an error)",
        "status": "VERIFIED-INCONSISTENT",
        "note": "Corrected 2026-10-13. 'Answered' and 'reliable' are different "
                "axes. This entry exists because the earlier draft repeated the "
                "wrong direction of the coverage axis; the numeric chart values "
                "were already right (80/81 < 81/81), only the prose was wrong.",
    },
]

# ---------------------------------------------------------------------------
# 2. Curated glosses (English). Labels/reasoning are pulled from the records;
#    these carry only the human-facing framing, each tagged with an evidence
#    class so a reader knows which part is measured and which is interpretation.
#    Every ``*_class``/``status``/``provenance`` string is the author's own
#    annotation (AI-ANNOTATED framing over SOURCE-RECORDED values), never a
#    second model evaluation. The per-case Evidence Passport below is generated
#    from the records; these glosses are the interpretation layer on top.
# ---------------------------------------------------------------------------
GALLERY_CASES = [
    {
        "case_id": "official-row-1115",
        "source_experiment": PAIRED_EXPERIMENT,   # validated against the paired run
        "task_language": "it",                    # booklet language (claim is DE)
        "title": "Right answer, thrown away at the gate",
        "vote_en": "Popular initiative 'At most 10 percent of income for "
                   "health-insurance premiums' (cheaper-premiums initiative)",
        "claim_en": "The booklet text claims the premium reduction is financed "
                    "entirely by the Confederation.",
        "gold": "contradiction",
        "story": "Both arms' evidence says the reduction would cost billions of "
                 "francs a year and the Confederation would cover at least two "
                 "thirds, not all. That contradicts 'entirely financed by the "
                 "Confederation'.",
        "observed": "The candidate's reasoning names the contradiction correctly "
                    "and its raw label (contradiction) matches gold, but it sets "
                    "vote_status to 'unrecognised', so the pipeline rejects the "
                    "whole answer before the citation can be verified. The dense "
                    "arm returns the same correct label, keeps its citation, and "
                    "is accepted.",
        "error_class": "Over-abstention / contract rejection despite adequate "
                       "evidence",
        "evidence_class": "OBSERVED (record content) — the causal claim that the "
                          "identity gate is what lost a correct answer is INFERRED "
                          "from the recorded fields, not proven.",
        "status": "PARTIALLY VERIFIED",
        "next_step": "Replay with vote identity checked independently of the NLI "
                     "label, and confirm whether the citation would have verified.",
    },
    {
        "case_id": "official-row-728",
        "source_experiment": PAIRED_EXPERIMENT,
        "task_language": "fr",
        "title": "It retrieved the wrong proposal",
        "vote_en": "Amendment of 16 December 2022 to the COVID-19 Act",
        "claim_en": "The Federal Council says the energy transition must be "
                    "accelerated to hit the 2030 climate targets.",
        "gold": "neutral",
        "story": "The claim is about the COVID-19 Act amendment, but every "
                 "retrieved passage concerns the Climate and Innovation Act — a "
                 "different vote in the same language.",
        "observed": "The candidate reads the (wrong-vote) evidence as neutral and "
                    "is rejected at the identity gate with no verified citation. "
                    "The dense arm reads the same climate material as entailment "
                    "— i.e. it supports the claim — which is wrong against a "
                    "neutral gold label, yet it is accepted. So the failure here "
                    "starts in retrieval scope, not in the gate.",
        "error_class": "Retrieval scope failure, plus dense over-generalising from "
                       "topically-related-but-wrong evidence",
        "evidence_class": "OBSERVED. The two models disagree on whether the "
                          "climate evidence speaks to a COVID-19 claim at all.",
        "status": "PARTIALLY VERIFIED",
        "next_step": "Check whether the same claim's evidence, scoped to the named "
                     "vote, supports entailment, and keep failures in the "
                     "denominator either way.",
    },
    {
        "case_id": "official-row-964",
        "source_experiment": PAIRED_EXPERIMENT,
        "task_language": "it",
        "title": "It named the initiative and still got the label wrong",
        "vote_en": "Popular initiative 'Yes to an independent, free Swiss "
                   "currency with coins or banknotes (Cash is freedom)' and its "
                   "direct counter-proposal",
        "claim_en": "If approved, Switzerland will introduce a new corporate "
                    "income-tax regime from 2027.",
        "gold": "neutral",
        "story": "The passages identify the Cash initiative and say it will not "
                 "create new tax regimes. A corporate-tax claim is simply absent "
                 "from a currency-and-cash vote, which is neutral, not "
                 "contradiction.",
        "observed": "The candidate correctly notes the claim is not addressed, yet "
                    "emits contradiction and flags the vote as unrecognised, so it "
                    "is rejected. Its reasoning says one thing (not supported) and "
                    "its label says another (contradicted) — an explanation/label "
                    "inconsistency, plus an identity failure with a wrong label.",
        "error_class": "Attribution conflation + explanation/label inconsistency",
        "evidence_class": "OBSERVED. Generated reasoning cannot be assumed to "
                          "reflect the internal decision (cf. Turpin et al., 2023).",
        "status": "PARTIALLY VERIFIED",
        "next_step": "Separate 'not about this claim' (neutral) from 'denied by "
                     "this claim' (contradiction) in a controlled prompt test.",
    },
    {
        # This case lives in the *evidence-sensitivity* experiment, NOT the paired
        # run (verified: `official-row-1344` has 0 rows in the paired file). It is
        # shown once, sourced from its real experiment, and its evidence is the
        # 15-case A/B/C/D single-run design — not a paired 70B arm comparison.
        "case_id": "official-row-1344",
        "source_experiment": SENS_EXPERIMENT,
        "task_language": "NOT VERIFIED",  # sensitivity record carries no claim/booklet lang
        "title": "It read the number, then changed the label",
        "vote_en": "Popular initiative for more Swiss films (media/film quota)",
        "claim_en": "Streaming providers must invest at least 10% of gross "
                    "revenue in Swiss independent films, or pay an equivalent levy.",
        "gold": "contradiction",
        "story": "The relevant article specifies a 4% requirement, not 10%. "
                 "'10% required' is denied by evidence stating 4%, so the gold "
                 "label is contradiction.",
        "observed": "On the recorded top-five and on the re-ordered late-evidence "
                    "run, the model's explanation correctly says '4%, not 10%' — "
                    "and then emits neutral, not contradiction. The raw JSON "
                    "already contained neutral, so the parser did not change it.",
        "error_class": "Numeric/relation error despite sufficient evidence",
        "evidence_class": "OBSERVED. Whether position caused the flip is a "
                          "hypothesis: C and D share the same evidence, only the "
                          "block order differs, on single runs.",
        "status": "PARTIALLY VERIFIED",
        "next_step": "Counterbalance block order with repeated unchanged controls "
                     "before attributing the flip to position.",
    },
]

GALLERY_GLOSSES = {c["case_id"]: c for c in GALLERY_CASES}

# Lab rows are evidence-sensitivity cases (15-case A/B/C/D, native 6-bit 8B).
LAB_ROWS = [1026, 1344, 189, 195]
LAB_COND = ["A_original", "B_minimal", "C_minimal_plus_distractors", "D_reordered"]

LAB_GLOSSES = {
    1026: {
        "title": "Decisive evidence kept, then ignored when moved",
        "domain": "financial aid limited vs extended",
        "gold": "contradiction",
        "key_fact": "A page-8 summary says aid was *extended* to people who had "
                    "had too little or no prior support, which contradicts a claim "
                    "that aid was limited to the already-adequately-supported.",
        "story": "The decisive sentence is present in every configuration. What "
                 "changes is where it sits relative to two neutral distractors.",
    },
    1344: {
        "title": "4% versus 10%, read correctly, mislabelled",
        "domain": "film-investment quota",
        "gold": "contradiction",
        "key_fact": "Article 24b specifies 4%, not the claimed 10%, with the "
                   "replacement-tax condition and four-year average retained.",
        "story": "The 4% fact is present and correctly quoted even when the label "
                 "goes wrong — so this is a use-of-evidence failure, not a "
                 "missing-evidence failure.",
    },
    189: {
        "title": "Both recommendations present; stakeholder scope lost",
        "domain": "limitation initiative — Federal Council vs committee stance",
        "gold": "entailment",
        "key_fact": "The Council and Parliament recommend *rejecting*; the "
                   "initiative committee recommends *yes*. The claim is about the "
                   "Council's rejection.",
        "story": "When both stances sit together, the answer sometimes contrasts "
                 "the two stakeholders and calls that contradiction of a claim "
                 "that merely reports the Council's own rejection.",
    },
    195: {
        "title": "Attributed to the committee; a distractor flips it",
        "domain": "sufficiency of existing anti-racism criminal law",
        "gold": "entailment",
        "key_fact": "The committee says existing penal-code provisions already "
                   "cover insults/humiliation. That attribution is what makes the "
                   "claim true.",
        "story": "Adding the Council/Parliament's opposing view as a distractor "
                 "moves entailment to contradiction, even though the claim only "
                 "reports the committee's position.",
    },
}

# ---------------------------------------------------------------------------
# Coverage-frontier points. Each records its own cohort, denominator AND
# coverage definition, because these are *not* one comparable frontier. Three
# different coverage metrics are deliberately kept distinct:
#   * completion coverage      — fraction of attempted cases that produced a
#                                rendered (non-error) answer (the two grouped-81
#                                points). "Answered", not "correct".
#   * citation-verification    — fraction with a mechanically-verified quotation
#     rate                       (the ablation point). Not a coverage rate at all.
#   * official valid-output    — fraction passing the identity + evidence +
#     coverage                     citation contract (the two paired points).
# Only the two paired-70B points share a denominator (n=54) and a metric, so
# they are the only genuinely comparable pair, and are the default view.
# ---------------------------------------------------------------------------
FRONTIER_POINTS = [
    {
        "id": "p0-dense",
        "label": "Paired · dense-v1",
        "group": "paired",
        "cohort": "Paired development, n=54",
        "model": "Apertus v1.5 70B (CSCS external)",
        "coverage": 43 / 54,
        "accuracy": 32 / 54,
        "coverage_metric": "official valid-output coverage",
        "coverage_basis": "valid output rate 43/54 = 0.796 (renderable official "
                          "JSON after identity/evidence/citation checks)",
        "accuracy_basis": "strict accuracy 32/54 = 0.593 (valid AND gold-correct); "
                          "raw-label accuracy is 40/54 = 0.741",
        "note": "8 of its 11 invalid outputs were actually gold-correct — "
                "correct-but-unrenderable, not wrong. Shares denominator + metric "
                "with vote-aware-v1, so the two are the comparable pair.",
    },
    {
        "id": "p0-vote-aware",
        "label": "Paired · vote-aware-v1 (candidate)",
        "group": "paired",
        "cohort": "Paired development, n=54",
        "model": "Apertus v1.5 70B (CSCS external)",
        "coverage": 25 / 54,
        "accuracy": 23 / 54,
        "coverage_metric": "official valid-output coverage",
        "coverage_basis": "valid output rate 25/54 = 0.463",
        "accuracy_basis": "strict accuracy 23/54 = 0.426; raw-label accuracy is "
                          "41/54 = 0.759 — higher than dense's 40/54",
        "note": "Higher raw-label accuracy than dense, but far fewer answers. "
                "18 of its 29 rejections were gold-correct, and it rejected every "
                "gold-neutral case. Rejection is not the same as reliability.",
    },
    {
        "id": "grouped-full",
        "label": "Grouped · Full-booklet prompt",
        "group": "other",
        "cohort": "Grouped development, n=81",
        "model": "Apertus v1.5 8B (MLX 6-bit, native)",
        "coverage": 81 / 81,
        "accuracy": 42 / 81,
        "coverage_metric": "completion coverage (answered, not correct)",
        "coverage_basis": "every case answered (0 errors); neutral recall 1.0 but "
                          "entailment recall 0.333 and contradiction recall 0.222 "
                          "— it over-answers toward neutral",
        "accuracy_basis": "full-document prompt, no retrieval",
        "note": "High coverage is not the same as high quality: it answers "
                "everything but defaults to neutral. Do not read 'answered' as "
                "'reliable'.",
    },
    {
        "id": "grouped-dense",
        "label": "Grouped · Dense within-booklet Top-5",
        "group": "other",
        "cohort": "Grouped development, n=81",
        "model": "Apertus v1.5 8B (MLX 6-bit, native)",
        "coverage": 80 / 81,
        "accuracy": 65 / 81,
        "coverage_metric": "completion coverage (answered, not correct)",
        "coverage_basis": "80/81 completed; one reply hit the 512-token output "
                          "limit and stays an error",
        "accuracy_basis": "top-5 SentenceSwissBERT within the supplied PDF",
        "note": "Higher accuracy (65/81 vs 42/81) but LOWER completion coverage "
                "(80/81 vs 81/81) than full-booklet, at 96.3% fewer input tokens. "
                "Higher conditional accuracy among completed answers does not "
                "raise overall correctness; and this is a different cohort from "
                "the paired points, so not one frontier line.",
    },
    {
        "id": "ablation-C",
        "label": "Ablation · Proposition reranking (arm C)",
        "group": "other",
        "cohort": "Retrieval ablation, n=81",
        "model": "Apertus v1.5 8B (MLX 6-bit, native)",
        "coverage": 36 / 81,
        "accuracy": 0.790,
        "coverage_metric": "citation-verification rate (NOT a coverage rate)",
        "coverage_basis": "verified citations 36/81 (arm A dense: 42/81); citation "
                          "rate, not valid-output rate — not comparable on the "
                          "coverage axis",
        "accuracy_basis": "dense+BM25 RRF then proposition reranking",
        "note": "Raised lexical reference Recall@5 (0.580→0.716) while lowering "
                "accuracy (0.827→0.790). Proxy recall up, downstream NLI down.",
    },
]

# The single default view is the paired 54-case comparison (shared denominator +
# metric). Everything else is an explanatory, non-comparable cohort view.
FRONTIER_DEFAULT_VIEW = "paired"

FRONTIER_CONTROL = {
    "id": "no-citation-control",
    "label": "No-citation control (not run)",
    "status": "NOT TESTED",
    "planned": "Identical retrieval and inputs with citation verification "
               "disabled, to ask whether validation *improves correctness* or "
               "merely *prevents answering*.",
    "why_not_run": "Needs a real v1.5 endpoint and fresh inference, which are "
                   "not available and not authorised here. `counterfactual_"
                   "experiment.py` is an OFFLINE PLAN BUILDER whose live "
                   "interface is deliberately disabled and not implemented "
                   "end-to-end; no number is claimed from it.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def gate_of(result: dict) -> str:
    return ("unrecognised" if result.get("vote_status") == "unrecognised"
            else "null_or_invalid_status")


def recompute_paired(lines):
    """Return the ledger aggregates straight from predictions.jsonl."""
    va = [x for x in lines if x["arm"] == "vote-aware-v1"]
    de = [x for x in lines if x["arm"] == "dense-v1"]
    rej = [x for x in va if not x.get("valid_output", True)]
    acc = [x for x in va if x.get("valid_output", True)]
    dinv = [x for x in de if not x.get("valid_output", True)]
    gold_neutral = [x for x in rej if x.get("gold") == "neutral"]
    return {
        "rejections_total": len(rej),
        "gate_unrecognised": sum(1 for x in rej if gate_of(x["result"]) == "unrecognised"),
        "gate_null_or_invalid_status": sum(1 for x in rej if gate_of(x["result"]) == "null_or_invalid_status"),
        "raw_correct_among_rejections": sum(1 for x in rej if x.get("raw_correct")),
        "raw_incorrect_among_rejections": sum(1 for x in rej if not x.get("raw_correct")),
        "gold_distribution": {k: sum(1 for x in rej if x.get("gold") == k)
                              for k in ("entailment", "neutral", "contradiction")},
        "raw_label_distribution": {k: sum(1 for x in rej if x.get("raw_label") == k)
                                   for k in ("entailment", "neutral", "contradiction")},
        "gold_neutral_rejections": len(gold_neutral),
        "gold_neutral_rejections_raw_label_is_neutral": sum(
            1 for x in gold_neutral if x.get("raw_label") == "neutral"),
        "incorrect_by_gate": {
            "unrecognised": sum(1 for x in rej
                                if gate_of(x["result"]) == "unrecognised" and not x.get("raw_correct")),
            "null_or_invalid_status": sum(1 for x in rej
                                          if gate_of(x["result"]) == "null_or_invalid_status" and not x.get("raw_correct")),
        },
        "accepted_outputs": len(acc),
        "accepted_citation_verified": sum(1 for x in acc if x["result"].get("citation_verified")),
        "rejections_with_quotation": sum(
            1 for x in rej if bool(x["result"].get("citations"))),
        "dense_valid": sum(1 for x in de if x.get("valid_output")),
        "dense_invalid": len(dinv),
        "dense_invalid_but_raw_correct": sum(1 for x in dinv if x.get("raw_correct")),
        "dense_invalid_citation_verified": sum(
            1 for x in dinv if x["result"].get("citation_verified")),
    }


# ---------------------------------------------------------------------------
# 3. Case-level verification + Evidence Passport (built from records only).
#    Nothing here is hand-authored: every field is read from the correct
#    experiment, or explicitly marked NOT VERIFIED. A case that is not found
#    where it is declared to live, or whose gold disagrees, is a build failure.
# ---------------------------------------------------------------------------
def _passage_refs(rec):
    """Return [{id, page}] for a record's supplied passages, or None if absent."""
    ps = (rec.get("result") or {}).get("passages")
    if not ps:
        return None
    return [{"id": p.get("id"), "page": p.get("page")} for p in ps]


def _source_identity(rec):
    """Booklet identity for a record. NOT VERIFIED where the record omits it.

    A booklet URL/hash only says *where* a passage came from; it never proves
    the passage semantically supports the label (that is the `semantic_status`
    field, left NOT ANNOTATED).
    """
    res = rec.get("result") or {}
    booklet = res.get("booklet")
    pdf = res.get("pdf_sha256")
    if not booklet and not pdf:
        return {"booklet": "NOT VERIFIED", "pdf_sha256": "NOT VERIFIED",
                "note": "record carries no booklet/pdf provenance"}
    return {"booklet": booklet or "NOT VERIFIED",
            "pdf_sha256": pdf or "NOT VERIFIED",
            "note": "occurrence metadata only; not semantic support"}


def _langs(rec):
    res = rec.get("result") or {}
    cl = res.get("claim_language")
    bl = res.get("booklet_language")
    return (cl or "NOT VERIFIED", bl or "NOT VERIFIED")


def passport_from_paired(lines):
    """Evidence Passport for the three paired P0 gallery cases (both arms)."""
    by_case = {}
    for x in lines:
        by_case.setdefault(x["case_id"], {})[x["arm"]] = x
    passports = []
    for gloss in GALLERY_CASES:
        cid = gloss["case_id"]
        if gloss["source_experiment"] != PAIRED_EXPERIMENT:
            continue
        arms_rec = by_case.get(cid)
        if arms_rec is None:
            raise AssertionError(f"{cid}: declared in paired run but no record found")
        # gold must agree between gloss and record (records are source of truth)
        rec_gold = next(iter(arms_rec.values())).get("gold")
        if gloss["gold"] != rec_gold:
            raise AssertionError(f"{cid}: gloss gold {gloss['gold']!r} != record "
                                 f"{rec_gold!r} — refusing to show a hand-typed label")
        rec0 = next(iter(arms_rec.values()))
        claim_lang, booklet_lang = _langs(rec0)
        arm_passports = {}
        for arm, rec in arms_rec.items():
            res = rec["result"]
            arm_passports[arm] = {
                "raw_prediction": rec.get("raw_label"),
                "contract_validity": ("valid" if rec.get("valid_output")
                                       else "rejected / invalid"),
                "validator_error": res.get("error") or "none",
                "citation_mechanical": ("verified" if res.get("citation_verified")
                                        else "not run / no quotation"),
                "passages": _passage_refs(rec) or "NOT VERIFIED",
                "source_identity": _source_identity(rec),
            }
        # Neutral: top-5 insufficiency vs document-wide absence is a different
        # claim; only retrieved-top-5 was examined, so booklet-wide is NOT VERIFIED.
        if gloss["gold"] == "neutral":
            scope = ("Retrieved top-5 does not establish the claim; whether it is "
                     "absent from the whole named booklet is NOT VERIFIED (only the "
                     "retrieved five were inspected). Top-5 absence never proves "
                     "booklet-wide absence.")
        else:
            scope = ("Evidence addresses the claim; no document-wide search was run, "
                     "so full-booklet extent is NOT VERIFIED.")
        passports.append({
            "case_id": cid,
            "experiment": PAIRED_EXPERIMENT,
            "model": rec0.get("configured_model") or "NOT VERIFIED",
            "requested_vote": gloss["vote_en"],
            "claim_language": claim_lang,
            "booklet_language": booklet_lang,
            "gold_label": rec_gold,
            "arms": arm_passports,
            "citation_verification": "Mechanical occurrence check only; semantic "
                                     "support NOT ANNOTATED (a passage appearing in "
                                     "the source does not prove it supports the claim).",
            "semantic_sufficiency_status": "NOT ANNOTATED (no independent adjudication)",
            "insufficiency_scope": scope,
            "annotation_provenance": "Human-authored interpretation over source-"
                                     "recorded fields; reasoning strings are the "
                                     "model's own output (AI-ANNOTATED).",
            "remaining_uncertainties": gloss["next_step"],
        })
    return passports


def passport_from_sensitivity(lines):
    """Evidence Passport for the four evidence-sensitivity rows (A/B/C/D)."""
    by_row = {}
    for x in lines:
        by_row.setdefault(x["row_index"], {})[x["condition"]] = x
    passports = []
    for row in LAB_ROWS:
        conds = by_row.get(row)
        if conds is None:
            raise AssertionError(f"evidence-sensitivity row {row}: declared but "
                                 f"no record found")
        missing = [c for c in LAB_COND if c not in conds]
        if missing:
            raise AssertionError(f"evidence-sensitivity row {row}: missing "
                                 f"conditions {missing} — condition membership "
                                 f"must match the 2x2 (A/B/C/D) design")
        rec0 = conds["A_original"]
        gloss = LAB_GLOSSES[row]
        if gloss["gold"] != rec0.get("gold"):
            raise AssertionError(f"sensitivity row {row}: gloss gold "
                                 f"{gloss['gold']!r} != record {rec0.get('gold')!r}")
        cond_passports = {}
        for c, rec in conds.items():
            res = rec["result"]
            cond_passports[c] = {
                "prediction": rec.get("pred"),
                "matches_gold": bool(rec.get("correct")),
                "citation_mechanical": ("verified" if res.get("citation_verified")
                                        else "not run / no quotation"),
                "passages": _passage_refs(rec) or "NOT VERIFIED",
                "source_identity": _source_identity(rec),
            }
        passports.append({
            "case_id": f"sensitivity-row-{row}",
            "experiment": SENS_EXPERIMENT,
            "model": (rec0.get("result") or {}).get("model") or "NOT VERIFIED",
            "requested_vote": gloss["domain"],
            "claim_language": "NOT VERIFIED",
            "booklet_language": "NOT VERIFIED",
            "gold_label": rec0.get("gold"),
            "conditions": cond_passports,
            "cd_evidence_order_invariant": (
                "C and D carry the identical passage multiset and token budget "
                "(position-only change) — see counterfactual_experiment.py."),
            "citation_verification": "Mechanical occurrence check only; semantic "
                                     "support NOT ANNOTATED.",
            "semantic_sufficiency_status": "NOT ANNOTATED (B is a curated upper "
                                           "bound, not a verified retrievable oracle)",
            "insufficiency_scope": "Single-run A/B/C/D diagnostic; no document-wide "
                                   "search, so booklet-wide extent is NOT VERIFIED.",
            "annotation_provenance": "Human-authored interpretation; reasoning "
                                     "strings are model output (AI-ANNOTATED). "
                                     "Single runs, not variance-controlled.",
            "remaining_uncertainties": "Whether a placement effect caused any flip "
                                       "is a HYPOTHESIS (see attribution-verification "
                                       "record §2.2/§4.1); needs counterbalanced runs.",
        })
    return passports


def gallery_from_records(paired):
    """Pull the four failure-gallery cases' real per-arm data from the records.

    The three paired cases contribute both arms (dense-v1 + vote-aware-v1).
    official-row-1344 is an evidence-sensitivity case and contributes NO paired
    arms — the caller supplies its condition data separately.
    """
    by_case = {}
    for x in paired:
        cid = x["case_id"]
        if cid in GALLERY_GLOSSES:
            by_case.setdefault(cid, {})[x["arm"]] = {
                "raw_label": x.get("raw_label"),
                "valid_output": bool(x.get("valid_output")),
                "strict_correct": bool(x.get("strict_correct")),
                "citation_verified": bool(x["result"].get("citation_verified")),
                "vote_status": x["result"].get("vote_status"),
                "reasoning": (x["result"].get("reasoning") or "").strip(),
            }
    cards = []
    for gloss in GALLERY_CASES:
        cid = gloss["case_id"]
        arms = by_case.get(cid, {})
        cards.append({
            "case_id": cid,
            "source_experiment": gloss["source_experiment"],
            "is_paired": gloss["source_experiment"] == PAIRED_EXPERIMENT,
            "task_language": gloss["task_language"],
            "votelabel": gloss["vote_en"],
            "claim_en": gloss["claim_en"],
            "gold": gloss["gold"],
            "title": gloss["title"],
            "story": gloss["story"],
            "observed": gloss["observed"],
            "error_class": gloss["error_class"],
            "evidence_class": gloss["evidence_class"],
            "status": gloss["status"],
            "next_step": gloss["next_step"],
            "annotation_provenance": "Human-authored interpretation (AI-assisted); "
                                     "source-recorded fields, not a model evaluation.",
            "arms": arms,
        })
    return cards


def lab_from_records(sens):
    """Build the Evidence Sufficiency Lab from the recorded A/B/C/D conditions."""
    out = {}
    for row, gloss in LAB_GLOSSES.items():
        conds = {}
        for x in sens:
            if x["row_index"] == row:
                r = x["result"]
                conds[x["condition"]] = {
                    "pred": x.get("pred"),
                    "correct": bool(x.get("correct")),
                    "reasoning": (r.get("reasoning") or "").strip(),
                }
        out[str(row)] = {**gloss, "conditions": conds}
    return out


def main() -> int:
    paired_present = PAIRED_JSONL.exists()
    sens_present = SENS_JSONL.exists()
    problems: list[str] = []

    # -- hash guard: verify BOTH raw files, fail closed on any mismatch --------
    if paired_present:
        if sha256(PAIRED_JSONL) != PAIRED_SHA256:
            problems.append("paired predictions.jsonl hash changed: got "
                            f"{sha256(PAIRED_JSONL)} expected {PAIRED_SHA256}")
    if sens_present:
        if sha256(SENS_JSONL) != SENS_SHA256:
            problems.append("sensitivity predictions.jsonl hash changed: got "
                            f"{sha256(SENS_JSONL)} expected {SENS_SHA256}")

    # -- ledger recount from the paired records --------------------------------
    if paired_present and not problems:
        got = recompute_paired(load_jsonl(PAIRED_JSONL))
        for k, want in EXPECTED_LEDGER.items():
            have = got.get(k)
            if have != want:
                problems.append(f"ledger fact {k}: records say {have}, curated {want}")
        print("== ledger self-check (paired records) ==")
        for k, want in EXPECTED_LEDGER.items():
            flag = "ok" if got.get(k) == want else "MISMATCH"
            print(f"  {flag:8} {k}: records={got.get(k)}")
    else:
        print("== ledger self-check ==")
        print("  raw data/experiments/ tree absent or hash mismatch: per-case "
              "checks skipped; published facts retained, NOT re-verified here.")

    # -- assemble the dataset. Only when BOTH raw trees are present AND the
    #    hashes verified do we rebuild the per-case layer. Otherwise the
    #    committed snapshot is kept untouched (a clean checkout never re-"verifies").
    if paired_present and sens_present and not problems:
        gallery = gallery_from_records(load_jsonl(PAIRED_JSONL))
        lab = lab_from_records(load_jsonl(SENS_JSONL))
        passports = (passport_from_paired(load_jsonl(PAIRED_JSONL))
                     + passport_from_sensitivity(load_jsonl(SENS_JSONL)))
        verification = {
            "state": "BUILD-TIME VERIFIED",
            "note": "Recomputed at build time from the two Git-ignored raw files "
                    "on the machine that ran this script. These committed facts are "
                    "a HISTORICAL result: opening them in a clean Git checkout does "
                    "NOT re-verify the raw files (they are absent there). To "
                    "re-verify, restore the raw tree, check the hashes, and re-run "
                    "courage_data.py. Until then treat the checks as historical.",
        }
    else:
        gallery, lab, passports = None, None, None
        verification = {
            "state": "NOT RE-VERIFIED IN THIS BUILD",
            "note": "One or both raw trees were absent, or a hash did not match; "
                    "the committed facts were kept as the last build-time snapshot "
                    "and were NOT recomputed here. Do not read them as freshly "
                    "verified.",
        }

    facts = {
        "schema": "hackapertus-courage-to-be-wrong-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                         .isoformat(timespec="seconds"),
        "provenance": {
            "paired_predictions_sha256": PAIRED_SHA256,
            "sensitivity_predictions_sha256": SENS_SHA256,
            "raw_tree_present": bool(paired_present and sens_present),
            "note": "Source hashes of the raw files the numbers were built from, "
                    "NOT a claim that this checkout has them or has re-checked them. "
                    "See `verification.state`.",
        },
        "verification": verification,
        "coverage_frontier": {
            "default_view": FRONTIER_DEFAULT_VIEW,
            "title": "Coverage vs accuracy — NOT one frontier (mixed denominators)",
            "points": FRONTIER_POINTS,
            "control": FRONTIER_CONTROL,
            "caveat": "Only the two paired-70B points share a denominator (n=54) "
                      "and a coverage metric, so they are the only comparable pair "
                      "(the default view). The two grouped-81 points use completion "
                      "coverage (answered, not correct) and the ablation point uses a "
                      "citation-verification rate — none of which measure the same "
                      "thing as the paired points' valid-output coverage. The points "
                      "are deliberately not joined; this is not a benchmark, not a "
                      "Pareto frontier, and not a holdout result.",
        },
        "verification_ledger": {
            "corrections": LEDGER_CORRECTIONS,
            "recomputed_facts": (recompute_paired(load_jsonl(PAIRED_JSONL))
                                 if (paired_present and not problems)
                                 else "not re-verified in this build"),
        },
        "failure_gallery": gallery,
        "evidence_lab": lab,
        "evidence_passport": passports,
    }

    if problems:
        print("\nSELF-CHECK FAILED (build closed):")
        for p in problems:
            print("  -", p)
        return 1

    if gallery is not None and lab is not None:
        (HERE / "facts.json").write_text(
            json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        (HERE / "facts.js").write_text(
            "// Generated by courage_data.py. Regenerate, do not hand-edit.\n"
            "// Verification state is build-time; a clean checkout does NOT re-run "
            "these checks.\n"
            "window.COURAGE = " + json.dumps(facts, ensure_ascii=False) + ";\n",
            encoding="utf-8")
        print("\nwrote facts.json and facts.js")
    else:
        print("\nfacts not regenerated (raw tree absent or hash mismatch); "
              "committed files kept as a historical snapshot.")
    print("\nSelf-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())