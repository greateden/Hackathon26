# Offline failure-attribution verification — 13 October 2026 (offline_attribution_v2)

Analysis-only verification record for the 29 rejected `vote-aware-v1` outputs of
the 54-case paired development evaluation (`vote-aware-paired-v2`, tracked compact
audit [`vote_aware_paired_results_20261013.json`](../vote_aware_paired_results_20261013.json)).
Requested work: verify the aggregate counts of an earlier "29-case offline
attribution analysis" (a quoted summary) against the original per-case records,
then complete that analysis. No inference, model call, prompt change,
validation-policy change or frozen-artefact change was made or authorised here.
Companion machine-readable facts: [`tracked_facts_v2.json`](tracked_facts_v2.json);
re-runnable aggregate + per-case check:
[`verify_offline_attribution_v2.py`](verify_offline_attribution_v2.py).

## 1. Evidence status — the original per-case records are present locally, but are Git-ignored

Distinguish two things that were previously conflated:

- **LOCAL (this working tree):** the raw paired-run records and the earlier
  `offline_attribution_v1` annotations **exist** and were read and reproduced on
  13 October 2026. `data/experiments/vote-aware-paired-v2/predictions.jsonl` is
  present; its SHA-256
  (`1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe`) matches
  the value recorded in the compact audit, and the 29-case contingency table was
  recomputed from it (see §3 and the companion script). The earlier analysis
  directory `data/experiments/vote-aware-paired-v2/offline_attribution_v1/` is
  also present (`attribution.json`, `blind_annotations.jsonl`,
  `blind_cases.jsonl`, `handoff.md`).
- **REMOTE (a clean Git checkout):** the whole `data/experiments/vote-aware-paired-v2/`
  tree, including the `offline_attribution_v1` subdirectory, is Git-ignored and
  was never published. A clean checkout therefore does **not** automatically
  reproduce these per-case records; they have to be restored from the environment
  that holds the snapshot. This is a reproducibility caveat, not a claim that the
  records are missing.

1. The quoted "original 29-case attribution analysis" whose figures are checked in
   §2 is **not** the `offline_attribution_v1` analysis that actually exists here.
   The real v1 file records 18 gold-matching raw labels, 14 `vote_unrecognised`
   and 15 no-`vote_status` (schema) rejections, and 28/29 cases with the target
   vote title present. The quoted summary instead recites "20 correctly
   relabelled", "13 identity and 16 citation failures", "5 of 13 fail citation
   verification" and case rows 2504/1200/567/1311 — figures that appear in no
   file, tracked or ignored. Those quoted numbers are treated below as
   **NOT ESTABLISHED** (no source), not as a real prior measurement being
   corrected.
2. Because the raw records exist locally, a per-case recount **was** executed here
   against `predictions.jsonl`; its result reproduces the tracked published
   aggregates — `technical_report.md` §6, the compact audit JSON,
   [`REPOSITORY_AUDIT_20261013.md`](../../REPOSITORY_AUDIT_20261013.md) and
   [`P0_CORRECTNESS.md`](../../P0_CORRECTNESS.md) — on every shared count (29
   rejections; 14 `vote_unrecognised` + 15 `invalid_vote_status`; 18 gold-matching
   and 11 non-matching raw labels; all 18 gold-neutral cases rejected). The
   original temporary audit scripts under `/tmp/hackapertus-audit-20261013/` were
   removed by an interruption; the permanent companion script replaces them and is
   re-runnable against a restored `predictions.jsonl`.
3. Warning sign about the quoted "original analysis": its case rows
   (29, 297, 442, 455, 1344, 1401, 1475) are the 81-case retrieval-ablation row
   indices of report §5–§6. Those rows belong to a different experiment (local MLX
   8B ablation, not the CSCS 70B paired run) and cannot be members of the 29 paired
   candidate rejections. The quoted analysis conflated experiments.

## 2. Claim-by-claim verification

Evidence classes: **VERIFIED-INCONSISTENT** (records contradict the quoted claim),
**VERIFIED-CONSISTENT** (records support it), **NOT ESTABLISHED** (no source; the
quoted figure has no origin in either the tracked aggregates or the actual v1 file).

| # | Quoted claim under verification | Actual tracked/recomputed value | Status |
|---|---|---|---|
| 1 | "20 of 29 rejected outputs are correctly relabelled; 11 have incorrect raw labels" | Recount of `predictions.jsonl`: 18 gold-matching + 11 non-matching = 29 | "20" VERIFIED-INCONSISTENT (18 is the actual count); "11 incorrect" VERIFIED-CONSISTENT |
| 2 | "9 of the 29 rejected cases have a gold label of neutral" | All 18 gold-neutral cases were rejected; 18 of the 29 rejections are gold-neutral (12 raw neutral + 6 raw contradiction) | VERIFIED-INCONSISTENT (18, not 9) |
| 3 | "13 identity failures and 16 citation failures; 9 rejected outputs pass all citation checks; 20 pass syntax and evidence checks" | The 29 rejections are 14 `vote_unrecognised` + 15 `invalid_vote_status`, all stopped at the identity gate; **no rejection produced a quotation**, so mechanical citation-provenance verification never ran on them (it ran on the 25 accepted outputs, 25/25 passed) | VERIFIED-INCONSISTENT / NOT ESTABLISHED (no source for 13, 16, 9 or 20; the 13/16 split does not match the recorded 14/15) |
| 4 | "5 of the 13 identity failure cases fail citation verification; 2 have unknown citation status" | The 29 rejections carry `citations = []` and `citation_verified = false` — the citation fields are **present but empty**, not absent, and no quotation was offered to verify | NOT ESTABLISHED; the quoted pass/fail counts have no source, and no rejection is claimed here to have *passed or failed* semantic citation verification |
| 5 | "12 neutral and 17 contradiction labels among the 29 rejections" | Recount of raw labels over the 29 rejections: 0 entailment, **15 neutral, 14 contradiction** (the 18 gold-neutral rejections are 12 neutral + 6 contradiction; the 11 non-neutral-gold rejections are 3 neutral + 8 contradiction) | VERIFIED-INCONSISTENT (15 neutral + 14 contradiction; neither "12 neutral" nor "17 contradiction" is the recorded split) |
| 6 | Case rows 2504, 1200, 567, 1311 as rejection cases | None appears in the frozen 81-row plan (`paired_grouped81_plan_20261011.json`) from whose cells the 54-case set was drawn; none is a `case_id` in `predictions.jsonl`. "2504" additionally appears nowhere in `data/eval/mnli_swiss_v1.1.jsonl`, and the dataset spans 60 dev + 1,428 complement = 1,488 rows (max plan row index 1,480), so a row 2504 cannot exist | VERIFIED-INCONSISTENT (all four) |
| 7 | Corrected dataset-scale claim "51/1900 valid outputs" | Valid outputs: 25/54 candidate, 43/54 dense (108/108 calls accounted). Dataset size 1,488 rows; "1900" has no tracked source, and 51 matches no recorded coverage count | VERIFIED-INCONSISTENT |

Note on the template's corrected case list (106, 1383, 1224, 1407): these four
*are* plan members and ran in the paired evaluation, but the repository audit
lists them among the nine candidate **strict gains** — accepted, citation-checked
outputs — so they are not identity-failure examples either. The tracked
identity-failure representative is `official-row-1115` (premium-relief initiative
explicitly named, gold-matching raw contradiction, rejected
`vote_unrecognised`); `official-row-728` is the retrieval-scope failure and
`official-row-964` combines identity failure with a wrong raw label.

Note on quotation exact-matching. A **separate, earlier** verification recorded
that archived evidence quotations failed the exact source-match check in its own
eighteen-case v1.5-8B paired run: `v15_paired_analysis_20261011.json` lists twelve
such quotation-match failures (across eight cases). That experiment is distinct
from the 29 paired-v2 rejections, whose records contain no quotation at all. The
figure is stated here only to separate *mechanical source occurrence* from
*semantic support* — a quotation can be present yet fail exact matching, and a
citation check can be skipped because no quotation was produced. Nothing in this
record claims that the 29 rejected outputs had a quotation that passed or failed
semantic verification; no such quotation existed and no such annotation was run.

## 3. Corrected aggregate picture (recomputed from `predictions.jsonl`; all sums internally consistent)

- 54 paired cases; 108/108 primary calls accounted. Candidate valid outputs
  25/54 (0.4630) versus dense 43/54 (0.7963); 29 candidate identity failures =
  14 `vote_unrecognised` + 15 `invalid_vote_status`.
- All 29 rejections contained a parseable raw NLI label; 18 matched gold and 11
  did not. Raw labels across the 29 rejections: 0 entailment, 15 neutral,
  14 contradiction. For the 18 gold-neutral rejections: 12 raw neutral, 6 raw
  contradiction. None of the 18 became an accepted output.
- Strict accuracy by gold: entailment 15/18, neutral 0/18, contradiction 8/18
  (sum 23 of 25 accepted; the 2 remaining accepted labels were wrong). Candidate
  raw accuracy 41/54, dense 40/54; dense correct-but-invalid 8/11 invalid.
- Citation provenance (mechanical source occurrence only) was executed on the 25
  accepted outputs (25/25 passed) and was **not** executed on the 29 rejections,
  which supplied no quotation; semantic-sufficiency verification of citations was
  not run on either arm and is not asserted here.
- Paired strict outcomes 18 dense-only / 9 candidate-only / 14 both / 13
  neither; exact two-sided McNemar p = 0.122078 (independently recomputed here
  from the binomial tail over 27 discordances: 0.12207812…).
- Paired case set ⊆ the 81-row frozen plan; rows 2504, 1200, 567 and 1311 are
  excluded by membership and, for 2504, by dataset range.

## 4. What a completed offline_attribution_v2 requires (status update)

1. The raw records are already present in this working tree and were hash-verified
   and recounted (see §1 and the companion script). They are, however, Git-ignored:
   a clean checkout must restore `data/experiments/vote-aware-paired-v2/` from the
   environment holding the snapshot and re-verify `predictions.jsonl` against the
   recorded SHA-256
   `1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe` before any
   analysis (the companion script performs this check automatically and skips the
   per-case checks when the ignored tree is absent).
2. The earlier `offline_attribution_v1` per-case annotations (`attribution.json`,
   `blind_annotations.jsonl`) are **AI-generated exploratory annotations produced
   by a local Qwen-family assistant (`Local-Qwen`, MTPLX
   flash-next-optimized-speed) — a different model family from the Apertus
   models that generated the predictions — and not independent
   human-adjudicated ground truth**. The v1 handoff recorded the analyst id but
   its "same model family" caveat misstated the provenance; cross-family
   sampling weakens a shared-decoder-bias concern yet does not establish
   annotation reliability, so a completed v2 must not treat these records as
   independent truth: the identity / sufficiency / citation judgments still need
   independent adjudication before any validation-policy change.
3. Freeze the annotation contract (identity check vs sufficiency check vs
   counterfactual swap) before implementation; keep both correct-and-accepted and
   wrong-and-accepted counterfactual cases; keep failures in the denominator.

## 5. Integrity statement

No CSCS 70B inference, no model-server call, no prompt or validation change, no
edit to any frozen plan, manifest, prediction file or the compact audit. The only
repository edits made by this verification are the three research questions and
one §9 cross-reference in `technical_report.md`, and one distinguishing index
entry in `docs/evidence/README.md`. The `predictions.jsonl` and v1 records are
read-only inputs here, not edited artefacts. Nothing in this record should be read
as causal attribution of the recorded failures; that requires independent
annotation of the evidence listed in §4.

Provenance addendum (13 October, after §4 was first written): the "same model
family" claims in this record, in `technical_report.md` §7 and §9, and in the
Git-ignored v1 `handoff.md` were replaced in place by the recorded analyst
identity — a local Qwen-family assistant — because the paired-v2 predictions
came from `swiss-ai/Apertus-v1.5-70B` (CSCS). The distinction preserved is
that generator and annotator were different model families while the
annotation remained AI-generated, procedurally blinded and unvalidated; the
independence requirement above is unchanged. No count, definition, script or
frozen artefact was altered by the correction.