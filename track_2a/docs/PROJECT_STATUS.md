# Project status — 11 October 2026

The specified-booklet application has one genuine local Apertus v1.5 8B MLX
result with a verified citation and token counts. Repository packaging now
follows `track_2a/`. **Submission readiness is still incomplete:** the model
server is externally provisioned, and clean-checkout Docker execution and
cross-platform validation remain pending. No model experiments were run during
cleanup.

## Requirements and evidence

The structural authority is the [Track 2A README](https://github.com/HackApertus/project-template/blob/09f8e9e2b588db3325869b23c6d5132f5c3756f7/track_2a/README.md)
and [repository README](https://github.com/HackApertus/project-template/blob/09f8e9e2b588db3325869b23c6d5132f5c3756f7/README.md),
checked on 11 October 2026. They require keeping `track_2a/`, Docker through
`make run`, standard LLM environment variables and at most 100 MB of submitted
data. They mandate the Apertus family; the stricter v1.5 8B acceptance target,
six-page report limit and 16 October 12:00 CEST deadline are from the project
brief. Challenge-specific rules and the current portal still need confirmation.

| Requirement | Status | Evidence / limitation |
|---|---|---|
| `track_2a/` with Makefile, src, data, docs, README and technical report | Passed | Required layout present; repository-root Makefile forwards into it |
| Apertus family used | Passed for local development | Real loader records v1.5 8B text branch, 6-bit MLX; no inference fallback |
| Exact submission v1.5 8B serving configuration | Unverified | Native third-party MLX conversion is evidenced; official vLLM build not validated |
| Specified booklet + claim, label and citations | Passed for one local example | Entailment (0), physical page 15, verified snippet; not a quality benchmark |
| All nine DE/FR/IT combinations | Passed for interface/retrieval only | n=9 extraction/retrieval smoke; multilingual NLI quality unverified |
| `make run` launches Docker from project root | Passed statically; runtime unverified | Make dry-run and Compose configuration pass; no new container run |
| Clean checkout without preinstalled application dependencies | Unverified | Dockerfile installs application dependencies; fresh image not built in cleanup |
| Self-contained model startup | Failed / not implemented | Compose consumes an already provisioned endpoint; no model-serving service |
| `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY` | Passed statically / offline | Compose forwarding and endpoint contract checks; no real submission endpoint run |
| Windows, macOS and Linux submission execution | Unverified | Submission recipe avoids POSIX assignments; Windows needs GNU Make; no OS runtime matrix |
| Submitted data at most 100 MB | Passed for Git-eligible files | Only README and two request/smoke JSON files; cache/corpora ignored; local data directory is larger |
| No model weights or credentials in candidate tree | Passed bounded inspection | No model files, credential-pattern matches or files over 10 MB found; this is not a credential audit guarantee |
| Technical report template | Passed for draft structure | Sections 1–8, licence and references; evaluation results remain pending |
| Final report, team metadata, demo and licence review | Failed / incomplete | No final PDF produced; code licence and challenge-specific deliverables need review |

## Submission configuration

`make run` → `compose.submission.yaml` → `src/booklet_app.py`.
Target model: `swiss-ai/Apertus-v1.5-8B`; temperature 0; seed 20261011;
512 output tokens; context default 32,768, which must match the server.
Set endpoint credentials in `track_2a/.env`; edit `data/request.json`.
The Docker path retains required `/tokenize` preflight. Native MLX optional
preflight is a separate development path; see [RUNNING.md](RUNNING.md).

| Configuration | Meaning | Evaluation state |
|---|---|---|
| Baseline A: `full` | All extracted pages from the supplied PDF, no silent truncation | Paired NLI accuracy/F1, tokens and latency pending |
| Approach B: `retrieved` | Top-five SwissBERT passages within the same PDF; known booklet-language adapter | One local smoke; paired NLI results pending |
| Historical `legacy` / `retrieve-v2` | Global OCR / booklet-corpus retrieval in `main.py` | Different task; preserved research measurements |
| Historical `oracle` | Gold reference supplied to the judge | Diagnostic only; not Baseline A |
| Historical `lexical` | Heuristic judge or BM25, depending on script | Never Apertus model quality |
| Historical `baseline`, `t0`, `strict`, `select`, factorial arms | Prompt/evidence ablations | Not current application settings; strict was unsuccessful |

## Verified results and preserved provenance

- **Local v1.5 smoke, n=1, DE→DE:**
  `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`, revision
  `9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`, mlx-lm 0.32.0.
  Entailment (0), verified citation page 15, 1,007 input / 71 output tokens,
  `finish_reason=stop`; inference 1.384 s and retrieval 2.374 s.
  Thinking was disabled at server startup. The original first attempt reached
  the 512-token output limit and is retained. No accuracy or improvement claim
  follows from this one example. [Evidence index](evidence/README.md).
- **Retrieval-only smoke, n=9:** cached SentenceSwissBERT, all language pairs,
  three examples per label. Mean gold-reference shingle coverage: full PDF
  0.921; within-PDF top-five 0.204. Mean extraction/retrieval time 1.722 s,
  first encoder load included, Apple MPS. Lexical coverage is not NLI accuracy.
  [Original artefact](evidence/booklet_retrieval_smoke_20261011.json).
- **Historical v1.1 model runs, dev n=60:** global retrieve-v2 accuracy/F1
  0.483/0.466; oracle 0.433/0.393. Raw result files remain in ignored `data/`;
  [the report](../technical_report.md) names them. Neither is a v1.5 or
  full-document comparison. Withdrawn global retrieval rankings and integrity
  caveats remain in [the archive](archive/README.md).
- **Existing split audit:** 24/60 dev rows duplicate normalised
  claim/reference/label triples in the 1,428-row complement; 25 share claims,
  46 share references. The nine-item plan contains three duplicate triples.
  [Plan, IDs and dataset hash](evidence/paired_dev_plan_20261011.json).
  The complement must not be described as independently held out.

## Remaining work

**P0 — execution:** resolve judge-side model provisioning and self-contained
startup; verify one clean-checkout Docker run with the accepted v1.5 model,
label, citation and token counts. A provisioned endpoint is not evidence that
this requirement is met. Confirm hardware, access and challenge-specific rules.

**P1 — submission evidence and deliverables:** validate Windows and Linux;
review code/data licensing, supply team and demo metadata, then complete the
report and requested PDF within the confirmed limit. After cleanup review,
authorise the saved paired development experiment (18 calls) on one frozen
serving configuration. Design a content-grouped independent final split.
No paired experiment or PDF was produced in this task.

**P2 — reproducibility and research limitations:** pin encoder, model and image
revisions; resolve the recorded MLX tokenizer warning and fresh-native dependency
conflict; assess OCR/layout gaps and historical diagnostic/cache issues.
Retain uncertain scratch files until their evidence value is settled.

## Cleanup verification

See [cleanup record](CLEANUP_20261011.md) for exact moves, unchanged-code hashes,
Compose checks, regression output, Git inventory and final status. Static checks
do not establish runtime portability or scientific validity. Historical evidence
files retain original paths and dates; the migration does not rewrite measurements.
