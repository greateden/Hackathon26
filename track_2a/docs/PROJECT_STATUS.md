> **14 October release update:** the submission default is external CSCS official Apertus v1.5 70B. Four bounded Docker calls and remaining neutral/approval blockers are recorded in [the release record](RELEASE_CANDIDATE_20261014.md). Earlier 8B-target and runtime status entries below are historical.

# Project status — 13 October 2026

**P0 candidate update:** the submission CLI now uses `vote-aware-v1`, with
vote-conditioned dense Top-5 retrieval and source-selected citations. The
original `dense-v1` Python experiment path remains unchanged in its ranking
and prompt inputs. P0 offline checks are recorded in
[P0_CORRECTNESS.md](P0_CORRECTNESS.md). Subsequent evidence comprises one
successful candidate Advanced Docker smoke and a 54-case paired exploratory
CSCS 70B development evaluation; neither is independent generalisation evidence.
No historical result or frozen plan was rewritten.

The specified-booklet application has genuine local Apertus v1.5 8B MLX
evidence and one successful Docker run against CSCS Apertus v1.5 70B. The Docker
application exited 0, returned entailment with a verified page-19 citation and
passed all eight application acceptance criteria plus the no-fallback check.
This is a one-example deployment smoke, not an accuracy result. Repository
packaging follows `track_2a/`.

**Submission readiness is still incomplete.** The optional managed 8B service
has not run: it needs compatible NVIDIA hardware and authorised model access.
Windows/Linux execution and a clean cold build also remain unverified. The
27-example CSCS prompt comparison did not improve accuracy, so `current_v1`
remains the production prompt.

## Requirements and evidence

The structural authority is the [Track 2A README](https://github.com/HackApertus/project-template/blob/main/track_2a/README.md)
and [repository README](https://github.com/HackApertus/project-template/blob/main/README.md),
rechecked on 12 October 2026. They require keeping `track_2a/`, Docker through
`make run`, standard LLM environment variables and at most 100 MB of submitted
data. They mandate the Apertus family but do not state a Track 2A model version;
v1.5 8B remains this project's conservative target. The six-page report limit
and 16 October 12:00 CEST deadline are retained from the project brief. The
current template and Devpost rules were rechecked: submission goes through
the event website, and Devpost confirms the deadline. The online-hack page had
no readable text; challenge-specific rules and portal details remain unconfirmed.

| Requirement | Status | Evidence / limitation |
|---|---|---|
| `track_2a/` with Makefile, src, data, docs, README and technical report | Passed | Required layout present; repository-root Makefile forwards into it |
| Apertus family used | Passed for local development | Real loader records v1.5 8B text branch, 6-bit MLX; no inference fallback |
| Exact submission v1.5 8B model identity | Passed statically; runtime unverified | Compose and the application require `swiss-ai/Apertus-v1.5-8B`; official weights were not loaded here |
| Official model availability | Blocked locally | Colima is Linux arm64 with no NVIDIA runtime; access and weights were not tested or downloaded |
| Specified booklet + claim, label and citations | Passed in local MLX and external Docker smokes | Both returned entailment with verified physical-page citations; n=1 each, not quality benchmarks |
| All nine DE/FR/IT combinations | Development evidence only | Candidate comparison has two rows per language-pair/label cell; exposed n=54, not independent quality evidence |
| `make run` launches Docker from project root | Passed for external CSCS mode | Root forwarding, build and one real application inference passed on Apple Silicon; managed 8B inference remains blocked locally |
| Clean checkout without preinstalled application dependencies | Partly verified | Docker build context is self-contained; fresh managed inference still needs an NVIDIA host and authorised model access |
| Self-contained model startup | Implemented; runtime unverified | Optional managed vLLM overlay, GPU reservation, readiness dependency and stop-on-exit lifecycle |
| `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY` | Passed for CSCS external mode | Compose forwarded the configured 70B model, endpoint and external credential; the credential was not recorded |
| Input/output and failure contract | Passed offline and in candidate live calls | Request identity, strict parsing, usage, finish reason and citation provenance passed when accepted; candidate valid-output rate was 25/54 in exploratory development data |
| CSCS v1.5 70B external backend | Candidate Docker smoke passed | Vote-aware specified-booklet retrieval, inference, bounded syntax recovery and page citation completed in Docker; n=1, not accuracy evidence |
| Windows, macOS and Linux submission execution | Unverified | Submission recipe avoids POSIX assignments; Windows needs GNU Make; no OS runtime matrix |
| Submitted data at most 100 MB | Passed for Git-eligible files | Only README and two request/smoke JSON files; cache/corpora ignored; local data directory is larger |
| No model weights or credentials in candidate tree | Passed bounded inspection | No model files, credential-pattern matches or files over 10 MB found; this is not a credential audit guarantee |
| Technical report template | Passed for draft structure | Sections 1–8, licence, references and current development results are present |
| Final report, team metadata, demo and licence review | Failed / incomplete | No final PDF produced; the public template does not name or locate one, and challenge-specific details need confirmation |

## Submission configuration

`make run` → base `compose.submission.yaml` → `src/booklet_app.py`, using the
externally provisioned endpoint from the standard `LLM_*` variables with no
local GPU dependency. `make run SUBMISSION_MODE=managed` adds
`compose.managed.yaml` and its NVIDIA vLLM service.
Target model: `swiss-ai/Apertus-v1.5-8B`; temperature 0; seed 20261011;
512 output tokens; context default 32,768, which must match the server.
Edit `data/request.json`; configure `LLM_NAME`, `LLM_BASE_URL` and
`LLM_API_KEY` outside Git. Managed mode uses `http://apertus:8000` and requires
a compatible NVIDIA GPU/runtime, `HF_TOKEN`, sufficient VRAM and large initial
image/weight downloads; no quantised substitution is configured.
The managed Docker path retains required `/tokenize` preflight. The new native
MLX experiment wrapper also supplies exact token preflight. Optional preflight is
now used by the opt-in CSCS backend: it relies on completion usage and finish
reason and never silently falls back. See [RUNNING.md](RUNNING.md).

| Configuration | Meaning | Evaluation state |
|---|---|---|
| Baseline A: `full` | All extracted pages from the supplied PDF, no silent truncation | Grouped development n=81 complete; accuracy 0.519, macro-F1 0.479 |
| Approach B: `retrieved` | Top-five SwissBERT passages within the same PDF; known booklet-language adapter | Grouped development n=81; accuracy 0.802, macro-F1 0.807; 80/81 completed |
| Historical `legacy` / `retrieve-v2` | Global OCR / booklet-corpus retrieval in `main.py` | Different task; preserved research measurements |
| Historical `oracle` | Gold reference supplied to the judge | Diagnostic only; not Baseline A |
| Historical `lexical` | Heuristic judge or BM25, depending on script | Never Apertus model quality |
| Historical `baseline`, `t0`, `strict`, `select`, factorial arms | Prompt/evidence ablations | Not current application settings; strict was unsuccessful |
| Frozen `dense-v1` versus candidate `vote-aware-v1` | Complete-system paired development comparison | n=54; raw accuracy 0.7407 versus 0.7593, strict accuracy 0.5926 versus 0.4259; not an isolated vote-awareness effect |

The completed prompt-only comparison used identical retrieved evidence for both
arms and CSCS `swiss-ai/Apertus-v1.5-70B`. Both scored 23/27. The refined arm
used 40,795 input tokens against 34,342 for `current_v1` (18.8% more), with one
improved flip, one worsened flip and one both-wrong flip. Keep `current_v1` as
production default. See the [tracked result](evidence/prompt_pilot27_results_v1.json).

## Verified results and preserved provenance

- **Vote-aware paired evaluation, n=54:** 108/108 primary CSCS 70B calls are
  accounted for. `dense-v1` versus `vote-aware-v1` raw label accuracy was
  0.7407 versus 0.7593; strict accuracy was 0.5926 versus 0.4259, and valid
  output rate was 0.7963 versus 0.4630. Candidate identity failures were 14
  unrecognised and 15 invalid/missing statuses. Exact paired McNemar p=0.122078.
  This is exploratory exposed development evidence. See the
  [compact audit](evidence/vote_aware_paired_results_20261013.json).
- **Vote-aware CSCS Docker smoke, n=1:** Advanced FR→FR inference returned
  entailment with a recognised vote and verified page-19 source span; 1,330
  input / 91 output tokens and 1.340 s inference. Bounded one-brace recovery
  succeeded. The span starts mid-word and includes extraneous text, so citation
  boundaries remain imperfect. See the
  [compact smoke record](evidence/vote_aware_cscs_smoke_20261013.json).

- **CSCS Docker smoke, n=1, FR→FR:** `swiss-ai/Apertus-v1.5-70B` through
  `make run-cscs`. Docker exit 0; entailment (0); verified page-19 citation;
  785 input / 80 output tokens; inference 1.23 s and total execution 24.06 s.
  All eight application criteria and the separate no-lexical-fallback check
  passed. This verifies one external-endpoint application path, not accuracy,
  portability or the default managed 8B deployment. Original record:
  `data/experiments/docker-verification-cscs-20261012T093746Z-49ed3309/`.
- **Grouped v1.5 experiment, n=81:** local 6-bit MLX at 81,920 tokens. Full
  accuracy/macro-F1 was 0.519/0.479; retrieved was 0.802/0.807, with one
  retrieved output-limit error. These historically exposed development data
  are not an independent holdout.
- **CSCS prompt comparison, n=27:** both prompts scored 23/27 on identical
  retrieved evidence. `current_v1` used fewer input tokens and remains the
  default. The sample is exposed development data, not a generalisation result.
- **Final offline verification:** the image built successfully on Apple Silicon.
  Host and Docker runs each passed 110 unit tests with zero failures, errors or
  skips. Judge/label checks and Python compilation also passed. Root `make run`
  emitted the official Beginner JSON contract against a deterministic mock.
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

**P0 — judge entry point:** default `make run` now uses an externally
provisioned v1.5 endpoint and does not require a container GPU. The managed
server remains an explicit option and is unverified. A tracked-files-only copy
built successfully, and the repository-root command passed against a
deterministic endpoint without `/tokenize`; the earlier CSCS smoke is the only
real external inference. These checks do not establish cold-build or
cross-platform portability.

**P1 — submission evidence and deliverables:** validate Windows and Linux;
review code/data licensing, supply team and demo metadata, then complete the
report and requested PDF within the confirmed limit. A genuinely independent
held-out prompt evaluation remains future work; do not promote the exposed pilot.

**P2 — reproducibility and research limitations:** the new native runner pins encoder/model revisions; production image and encoder
pinning remain open. Resolve the recorded MLX tokenizer warning and fresh-native
dependency conflict; assess OCR/layout gaps and historical diagnostic/cache issues.
Retain uncertain scratch files until their evidence value is settled.

## Cleanup verification

See [cleanup record](CLEANUP_20261011.md) for exact moves, unchanged-code hashes,
Compose checks, regression output, Git inventory and final status. Static checks
do not establish runtime portability or scientific validity. Historical evidence
files retain original paths and dates; the migration does not rewrite measurements.

## P0 deployment repair verification — 11 October 2026

- Before repair, `docker compose -f track_2a/compose.submission.yaml config --quiet`
  failed because `LLM_BASE_URL` was required and no model service existed.
- After repair, the same configuration check passed. Rendered Compose checks
  passed for defaults and an overridden context/API key/arm64 configuration:
  model and context agree between services, credentials are forwarded,
  readiness gates the application, GPU reservation is present, token preflight
  is required and no model port is published. These are static checks only.
- `make -n run` resolved the repository-root wrapper to the managed Compose
  `up --build --abort-on-container-exit --exit-code-from app app` command.
- One real `make run` attempt failed before any container or download: Docker
  could not connect to `/Users/liyitian/.colima/default/docker.sock` (absent).
  Colima status confirmed it was stopped; the host is Apple Silicon arm64,
  without the NVIDIA device required by this deployment. No end-to-end result.
- `make test` ran once: all judge/label checks and Python compilation passed;
  **69 unittest regressions passed** (0.037 s). `git diff --check` passed.
- No model/application source, prompts, retrieval or evaluation logic changed.
  No large weights or images downloaded, no benchmarks, no server started,
  no commit or push. The published image tag remains mutable and untested here.

**Outcome: PARTIAL.** The smallest next action is one clean-checkout `make run`
on an existing compatible NVIDIA Docker host, with approved Hugging Face access
and the official weights available or an authorised initial download. Verify
the label, citation, token counts and service shutdown before declaring PASS.

## Submission P0 recheck — 12 October 2026

- The live official template still requires the unchanged `track_2a/` layout,
  repository-root `make run`, Docker, the three standard `LLM_*` variables and
  no more than 100 MB under `data/`.
- A temporary tree containing only Git-eligible candidate files resolved root
  `make run`, passed both Compose configurations and built the application image.
  The build reused cached base/dependency layers; it did not test a cold network install.
- Dummy sentinel checks confirmed model name, base URL, API key, context and
  token-preflight forwarding. The managed model and application both resolve to
  `swiss-ai/Apertus-v1.5-8B` by default.
- The clean-built application exited 1 against an unreachable endpoint before
  PDF download or embedding work. No lexical fallback or inference occurred.
- No repository configuration or packaging defect was confirmed. The local
  `docker compose build` frontend is broken because its buildx plugin path is
  missing; the legacy builder succeeded. This host has no NVIDIA runtime, so
  managed service startup, official weight availability and real output remain blocked.

The exact next verification is `make run` from the repository root on a clean
amd64 checkout with NVIDIA Container Toolkit, authorised `HF_TOKEN` in
`track_2a/.env`, and permission for the official initial download. Record the
result JSON and non-zero/zero exit status; do not declare submission runtime
ready until that command returns a verified citation and the configured model.

## Runner repair verification — 11 October 2026

The new three-mode runner passed 24 focused offline tests. The single final
`make test` passed 53 judge/label checks, source compilation and 92 unittest
regressions. Actual preflight passed for the frozen nine-row matrix (18 planned
calls; up to 36 with one retry), including cached inputs and both static
Compose configurations. No inference, image build or deployment smoke ran.
Docker is stopped; ports 8000/8080 have no listener. The new MLX wrapper's real
startup, paired measurements and official Docker execution remain unverified.
See [repair handoff](RUNNER_REPAIR_20261011.md) and [commands](EXPERIMENTS.md).
