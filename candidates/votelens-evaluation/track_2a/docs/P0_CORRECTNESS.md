# P0 correctness and reliability — 12 October 2026

Branch: `experiment-multilingual-retrieval-ablation`. Starting commit:
`d750b10cede6f3524be1f0427a3dbfe6766b2332`. The working tree was clean before
this task. No commit, push, model download or model-server startup was performed.

## Audit before implementation

| Item | Confirmed defect or existing behaviour | Minimal correction and acceptance |
|---|---|---|
| Vote | Validated but unused in retrieval and judgement | Include vote in the dense query and judge context; preserve the original claim; reject ambiguous/unrecognised identities; exercise nine language pairs and conflicting positions |
| Citations | Generated snippets had to match extraction; no character offsets | Model selects provided passage IDs; copy source spans, validate offsets and reject unknown/ambiguous references; keep semantic sufficiency separate |
| Runtime | Root Docker/Compose wiring, 8B/CSCS configuration and optional token preflight already existed; unknown tasks and non-finite latency could pass validation | Retain deployment wiring; tighten malformed input/output checks and verify measured output fields |
| Baseline | Dense Top-5 was the default; experimental rankers were separate | Keep original queries/prompts for historical runners; version the new CLI candidate and preserve all frozen artefacts |

The official [Track 2A template](https://github.com/HackApertus/project-template/blob/main/track_2a/README.md)
and [root template](https://github.com/HackApertus/project-template/blob/main/README.md)
were read live. They require the Track 2A layout, Docker through `make run`,
Apertus and the standard LLM variables. They do not promise judge-provided
credentials, an endpoint or GPU. The challenge-specific Notion page could not
be retrieved; its local historical transcription was not treated as newly
verified requirements.

## Subsequent validation — 13 October 2026

After the implementation audit above, one real Advanced Docker request completed
against CSCS `swiss-ai/Apertus-v1.5-70B`. It returned entailment, recognised the
specified vote, selected a page-19 source span and produced valid official JSON
after the candidate-only one-surplus-brace recovery. Reported usage was 1,330
input and 91 output tokens, with 1,340 ms inference latency. The copied span
begins mid-word and includes trailing material, so the smoke verifies a working
end-to-end path but also records an unresolved evidence-boundary defect.

A separate paired exploratory development evaluation accounted for 108/108
CSCS 70B calls over 54 cases. `vote-aware-v1` raw label accuracy was 0.7593
against 0.7407 for frozen `dense-v1`, but strict accuracy was 0.4259 against
0.5926 and valid-output rate was 0.4630 against 0.7963. Candidate errors were 14
`vote_unrecognised` and 15 `invalid_vote_status`; all 18 gold-neutral cases were
rejected. The exact paired strict-accuracy McNemar p-value was 0.122078. Because
the arms differ in retrieval query, prompt, response schema, identity validation
and citation handling, this is a complete-system comparison rather than an
isolated vote-awareness effect. See the tracked
[paired audit](evidence/vote_aware_paired_results_20261013.json) and
[smoke record](evidence/vote_aware_cscs_smoke_20261013.json); raw records remain
ignored. These later observations do not alter the historical audit statements
below about what had not yet run during the original P0 implementation task.

## Implementation and observable behaviour

`src/booklet_app.py` keeps the encoder, adapters, 900-character chunks, cosine
ranking and Top-5 default. The candidate query is `Vote: <vote>\nClaim: <claim>`.
The judge receives the unchanged claim and explicit vote metadata. It must
return `vote_status=recognised` and a `vote_reference` selecting a supplied
passage that identifies the proposal. Ambiguous/unrecognised/missing statuses
or invalid references produce errors with no final label. Recognition can fail
when the Top-5 lacks identity context; there is no fallback to another vote.
No translation model, new embedding model or additional inference call is used.
All nine language pairs follow the same path; real multilingual recognition
and attribution accuracy remain unmeasured.

The candidate replaces generated quotations with `evidence_refs`, each naming
a supplied passage ID and optionally a start/end pair. Without offsets it
copies the entire explicitly selected passage. It never chooses a replacement
passage for an invalid reference. Model paraphrases are not emitted as quotes.
Non-neutral labels require `evidence_status=sufficient` and non-empty valid
references; neutral requires `insufficient` and empty references. The latter is
the ordinary NLI absence-of-support outcome, distinct from missing trustworthy
source text, which is an error. These are model assertions of semantic support,
not an independently verified sufficiency score.

Diagnostics retain source URL/path, PDF SHA-256, physical page, passage and
page offsets, plus a separate vote citation. Offsets are zero-based and
end-exclusive in the stripped Poppler page text; they are not PDF byte offsets.
The final official JSON retains only page/text evidence and measured metrics.
Punctuation, whitespace, ordinary hyphens and discretionary soft hyphens are
copied exactly. Ambiguous unlocated repeated passages and invalid offsets fail.
Citation records are recomputed and compared before rendering official output.

The public path rejects partial/non-object JSON, duplicate keys, invalid model
listings, incomplete completions, inconsistent reported token totals, unknown
tasks and non-finite latency. Errors have no lexical fallback. The existing
`submission-smoke` adapter in `src/experiment_runner.py` now verifies selected
source spans and vote identity instead of requiring citations to equal whole
passage dictionaries. Historical experiment execution and scoring are unchanged.

## Frozen baseline versus candidate

| Property | Original `dense-v1` | Candidate `vote-aware-v1` |
|---|---|---|
| Entry point | Existing flat Python experiment requests; optional explicit `pipeline_version=dense-v1` | Official nested requests and every submission CLI request |
| Retrieval | Original claim, dense Top-5 | Specified vote plus original claim, dense Top-5 |
| Judgement | Original prompt, unchanged evidence rendering | Vote/attribution instructions, source IDs and sufficiency contract |
| Citation | Original snippet occurrence check | Explicit source selection and exact source offsets |
| Quality evidence | Historical exposed development runs only | At the implementation audit: none; subsequent paired development evidence is recorded above |

The CLI forces the candidate even for legacy-shaped input. A flat Python
request without `pipeline_version` retains the historical behaviour, including
its unused vote, so frozen experiment runners do not silently change tasks.
For exact historical reproduction, use the starting Git commit and recorded
model/encoder revisions and manifests; do not resume old runs with the candidate.
No model pin, decoding budget, retrieval threshold, experimental ranker or plan
was changed. The 81-case 0.827/0.824 dense, 0.802/0.797 hybrid and 0.790/0.784
reranked results remain development measurements of the original system only.

## Verification

- Focused tests passed: 13 P0 regressions, 14 application tests and 32 runner
  tests. Replies/encoders were doubles; test messages saying "real Docker" are
  simulated runner branches, not deployment evidence.
- `make test` ran exactly once. All 53 judge/label checks and source compilation
  passed. Unittest discovery then aborted in the pre-existing
  `test_evidence_sensitivity_v2` path: its cached tokenizer loader imports
  `mlx_lm`, which fails without a Metal device in this sandbox, followed by a
  nanobind duplicate-registration abort. The full suite did not complete and
  is not reported as passed. The diagnostic's GPU-dependent offline-test design
  is outside these production P0 edits and was not changed. Log:
  `/tmp/hackapertus-p0-make-test.log`. No full-suite rerun was made.
- Original/current comparison on all nine existing language-pair fixtures:
  identical dense passage records/scores and frozen prompt bytes. Encoder and
  judge were deterministic doubles, with zero inference calls; this verifies
  compatibility, not prediction quality.
- Compose external 8B, managed 8B and external CSCS 70B configurations passed
  using an empty env file and dummy credentials in an isolated environment.
  Root `make -n run` resolves to Docker in external and managed modes, propagates
  application exit status and invokes no host Python.
- Docker daemon/image queries were unavailable in this session. No image build,
  container execution, GPU server, model download or live inference was attempted.
  Earlier Docker smokes predate this candidate.
- No real API credentials or `.env` files were read, displayed or recorded.
  HTTP tests used dummy keys; endpoint exception details are not copied to results.
- SHA-256 checks matched all 137 pre-existing files under `docs/evidence/`,
  `docs/archive/`, `data/experiments/` and `tests/fixtures/`. Historical
  predictions, plans, reports and fixture data remain unchanged. Snapshot:
  `/tmp/hackapertus-p0-frozen-before.json`. `git diff --check` passed.

| P0 requirement | Status | Remaining limit |
|---|---|---|
| Vote identity | PARTIAL | Implemented and offline-tested; real multilingual identity/attribution acceptance pending |
| Citation verification | PASS | Deterministic source contract verified; semantic sufficiency remains a model judgement |
| Production pipeline | PARTIAL | Static/HTTP-double checks pass; current Docker/live execution and full regression completion unverified |
| Baseline preservation | PASS | Original prompt/ranking fixture comparison and all frozen hashes match |

Changed files: `src/booklet_app.py`, `src/experiment_runner.py` (submission-smoke
validation only), `tests/test_p0_contracts.py`, `tests/test_booklet_app.py`,
`tests/test_experiment_runner.py`, `README.md`, `technical_report.md`,
`docs/PROJECT_STATUS.md`, `docs/RUNNING.md` and this record. Makefiles, Compose,
Dockerfile, dependencies, historical judgement/retrieval modules and plans were
not modified.

## Pending manual verification

Prerequisite for external execution: GNU Make, running Docker/Compose and an
operator-provisioned allowlisted Apertus v1.5 endpoint. Set `LLM_NAME`,
`LLM_BASE_URL`, `LLM_API_KEY` when required, and the endpoint's actual context
limit outside Git. A clean build needs network access or cached dependencies.
Advanced mode additionally needs an accessible PDF and cached/downloadable
SentenceSwissBERT. Optional token preflight relies on reported usage; it cannot
independently prove that the endpoint did not truncate input.

From the repository root, the committed Beginner request can check the new
citation/output contract (use fresh result paths on each run):

```bash
RESULT_FILE=/app/data/p0-beginner-result.json \
DIAGNOSTICS_FILE=/app/data/p0-beginner-diagnostics.json make run
```

Prepare `track_2a/data/p0-advanced.json` with the documented official Advanced
shape, a real local booklet path relative to that JSON, its exact vote title
and an original DE/FR/IT claim. Then, with the 8B endpoint configured:

```bash
REQUEST_FILE=/app/data/p0-advanced.json \
RESULT_FILE=/app/data/p0-8b-result.json \
DIAGNOSTICS_FILE=/app/data/p0-8b-diagnostics.json make run
```

For opt-in CSCS, set `CSCS_INFERENCE_API_KEY` externally and run:

```bash
REQUEST_FILE=/app/data/p0-advanced.json \
RESULT_FILE=/app/data/p0-cscs-result.json \
DIAGNOSTICS_FILE=/app/data/p0-cscs-diagnostics.json make run-cscs
```

Managed 8B additionally requires a compatible NVIDIA host/runtime, sufficient
unmeasured VRAM, authorised model access and permission for image/weight downloads:

```bash
REQUEST_FILE=/app/data/p0-advanced.json \
RESULT_FILE=/app/data/p0-managed-result.json \
DIAGNOSTICS_FILE=/app/data/p0-managed-diagnostics.json make run SUBMISSION_MODE=managed
```

Verify model/usage/finish reason, recognised proposal, its identity citation,
label, source spans and final JSON against the PDF. One smoke cannot establish
quality. The next bounded experiment is a paired original/candidate probe on
one two-proposal booklet with opposing stakeholder positions, using all nine
claim/booklet language pairs. Include ambiguous and absent vote names as error
controls. Review identity and semantic support separately from exact provenance;
record gains, losses and refusals without changing historical predictions.
P1 work can continue independently, but candidate model acceptance and production
readiness remain pending these runtime and semantic checks.
