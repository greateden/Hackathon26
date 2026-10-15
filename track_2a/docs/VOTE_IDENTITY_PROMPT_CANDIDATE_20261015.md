# Experimental vote-identity prompt — 15 October 2026

Status (15 October): TWO CONTROLLED CSCS A/B RUNS COMPLETED; candidate not promoted. The original plan below is retained for provenance.

## Diagnosis

Observed: retest rows 194, 528 and 555 all failed `vote_unrecognised`.
Raw labels were contradiction, contradiction and neutral respectively. Row 528
explicitly treats a different topic as contradiction; rows 528/555 describe the
proposal topic but report unrecognised identity. These do not establish that the
retrieved passages unambiguously identify the requested proposal, nor explain all
14 original failures. The original 60-case run was native, not a completed Docker batch.

Current `VOTE_INSTRUCTIONS` already separates identity from claim support, and
`CANDIDATE_OUTPUT_CONTRACT` already permits recognised identity with Neutral.
The narrower ambiguity is procedural: no explicit identity → relevance → NLI order,
and “EVIDENCE contradicts the CLAIM” does not expressly exclude unrelatedness.
A booklet containing the proposal (A) is not sufficient: the supplied passages
must establish its identity (B). Claim relevance (C) does not decide identity;
support/refutation (D) decides the NLI label. Topic recognition alone does not
prove B. This is a prompt-salience hypothesis, not a demonstrated causal diagnosis.

The earlier 27-case prompt pilot (`docs/evidence/prompt_pilot27_results_v1.json`)
recorded 23/27 correct in both arms; it does not validate this new candidate.

## One opt-in candidate; exact prompt diff

`src/experimental_vote_identity.py` inserts only the following block before the
legacy `Reply with EXACTLY` marker. `build_messages()` retains it and replaces
the legacy schema with the unchanged six-field Task A contract. No existing
source file, production selector, parser, validator or retrieval setting changes.

```text
Decision order: (1) Identify the specified proposal from explicit evidence in the supplied passages and select its vote_reference. Its presence elsewhere in the booklet, request metadata, or topic similarity alone does not establish identity. If identity is unresolved, keep ambiguous or unrecognised; do not invent an identity or reference. (2) Determine whether the claim concerns that proposal, without changing an evidence-grounded identity because the claim is unrelated. (3) Use entailment when the evidence supports the claim, contradiction only when the evidence establishes that the claim is false, and neutral when the evidence neither establishes nor refutes it. An unrelated claim is not automatically a contradiction: without support or refutation, use neutral. A recognised proposal can have a neutral claim; retain its grounded vote_reference while using insufficient evidence_status and empty evidence_refs. Do not invent evidence, citations, or missing information.
```

Select explicitly in an authorised experimental harness using the existing hook:

```python
from experimental_vote_identity import VOTE_IDENTITY_V1
# Existing Task A SubmissionJudge instance, before its requests:
judge.system_prompt = VOTE_IDENTITY_V1
# Baseline arm: judge.system_prompt = booklet_app.SYSTEM_PROMPT
```

This is not a new CLI/environment switch. Production does not import the module;
its default prompt remains unchanged. Use only for Task A `vote-aware-v1`.

## Offline evidence

`PYTHONPATH=src python3` with unittest discovery over
`test_experimental_vote_identity.py`, `test_p0_contracts.py`,
`test_submission_cli.py` and `test_prompt_ab_experiment.py`: **43 tests passed,
exit 0**. Seven new tests cover the sole prompt addition, one unchanged output
contract, mocked recognised Neutral for an unrelated claim, ungrounded identity
rejection despite Neutral, valid entailment/contradiction citations, insufficient
contradiction evidence, invalid Neutral citations and unknown source IDs.
Existing tests retain strict JSON, identity-recovery and citation checks.

The unrelated-claim and contradiction examples are stipulated semantic fixtures:
mock outputs test integration, not whether a model reasons correctly. In particular,
source-occurrence checks cannot establish semantic contradiction. The candidate
instructs affirmative refutation; live evidence is still necessary.

Historical native/production-preparation/retest files were SHA-256 checked unchanged.
Original native predictions SHA-256:
`a3334fee0e80c8c8330f48271ec0e6c238974db3ea55f14d1533a14f41eab85f`.
Prior report and diagnostic-logging edits in the worktree are outside this change.

## Original nine-case A/B plan (subsequently executed)

- Freeze nine Task A rows: **194, 528, 555, 68, 171, 533, 694, 1076, 1095**.
  First three are diagnostic failures; remaining six are the first two accepted,
  correct original predictions per gold class in recorded input order. Gold counts:
  entailment 3, neutral 4, contradiction 2. This is exposed, selected development data.
- Freeze the same inputs, PDF hashes and retrieved passage bytes for both arms;
  keep gold separate and scoring-only. Use saved retest passages for the three
  diagnostic cases and unchanged local retrieval for the six controls. Verify
  extraction/source offsets before either arm; do not curate evidence using gold.
- Baseline: current production prompt. Candidate: `VOTE_IDENTITY_V1`.
  Same official CSCS 70B model, runtime, temperature 0, 512-token limit, parser and
  validation. Alternate baseline/candidate order by case; record prompt hashes.
- **9 requests per arm, 18 total maximum, no retries**, including failures. Do not
  reuse historical baseline predictions as the concurrent control. Stop at budget.
- Save append-only attempts, raw responses, validation reasons and official outputs
  separately from all historical runs. Record missing/endpoint failures explicitly.
- Per arm report valid-output rate /9, strict accuracy /9, three-class Macro-F1
  counting rejected/missing predictions as false negatives for gold, and vote-identity
  rejection rate /9 (`vote_unrecognised`, `vote_ambiguous`, `invalid_vote_status`).
  Also show raw-label outcomes separately and paired case-level changes.
- Inspect all six previously correct controls for accepted-to-rejected and
  correct-to-incorrect regressions (including gold labels). Require no control
  regressions and reduced diagnostic rejections without new incorrect acceptances
  before considering a larger separately authorised test. Nine selected cases
  cannot establish general quality, qualification or submission readiness.

No API calls, model downloads, Docker work, full evaluations, commit or push.

## Subsequent results (15 October 2026)

The original targeted nine-case A/B yielded baseline valid 6/9, strict correct 5/9, three-class Macro-F1 0.656; the identity-aware candidate yielded 8/9 valid, 7/9 correct, Macro-F1 0.850. A separate deterministically selected 20-case development A/B yielded 12/20 valid, 11/20 correct and Macro-F1 0.633 in **both** arms, with zero paired label flips or validity changes. These exposed development samples are not official or held-out evaluation. The production prompt was retained. Raw experiment records remain locally Git-ignored under `data/experiments/vote-identity-ab9-20261015T170130Z/` and `data/experiments/vote-identity-ab20-20261015T193500Z/`; a fresh checkout does not contain them.

The request-budget and non-execution statements above describe the **original preparation stage**, not the final experiment status.
