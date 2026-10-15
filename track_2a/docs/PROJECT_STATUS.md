> **Current release status — 15 October 2026, evening:** The public `linux/amd64` evaluation image `ghcr.io/greateden/hackathon26@sha256:87605f3f1c7afad8358e8322bd738593359c4569e959b8d38a0a0d6f47ac07d0` was built and pushed by [GitHub Actions](https://github.com/greateden/Hackathon26/actions/runs/38790904985), pulled anonymously with exit code 0 and inspected as `linux/amd64`. Its default entrypoint is `src/submission_cli.py` for mixed Task A/B JSONL; the runtime receives `BASE_URL` / `API_KEY` and uses Apertus v1.5 70B externally. `make run` remains a separate development demo. The report PDF was rebuilt on 15 October (commit `d08fc08`); short subsequent LaTeX text edits need a final render. The team reports completing its third-party licensing review. **Private scoring, organiser handling of `label: null` and non-zero exit, and final portal submission remain unverified.** Earlier 8B-oriented notes below are historical. No six-page limit was found in the supplied OST materials.

# Project status — historical 13 October record, refreshed 15 October 2026

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
the current external submission target is official `swiss-ai/Apertus-v1.5-70B`.
The OST Q&A additionally specifies an AMD64 container published to a registry,
readable by the organisers with runtime-injected `BASE_URL`/`API_KEY`, and the
Task A/B qualification thresholds of 0.60/0.75 Macro-F1. The two OST slide decks
and supplied challenge description do not specify a six-page PDF limit; do not
assert one without confirmation from the organisers. Submission is through the
HackApertus website, not Devpost; final portal details need verification.

| Requirement | Status | Evidence / limitation |
|---|---|---|
| `track_2a/` with Makefile, src, data, docs, README and technical report | Passed | Required layout present; repository-root Makefile forwards into it |
| Apertus family used | Passed for local development | Real loader records v1.5 8B text branch, 6-bit MLX; no inference fallback |
| Selected official v1.5 model | Configured; public image pull passed | External CSCS `swiss-ai/Apertus-v1.5-70B` is the selected model; published AMD64 image pulled anonymously. Private scoring remains unverified |
| Official model availability | Earlier real 70B endpoint smokes passed | Inference stays at the provided endpoint; the release container does not bundle 70B weights. Managed local 8B remains unverified |
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
| Final report, team metadata, demo and licence review | Present; PDF refresh and portal pending | Markdown, LaTeX and PDF files exist; team names and notebook link are populated. Team reports licensing review completed; registry image is public. Rebuild PDF after final LaTeX edits |

## Submission configuration

**Current OST evaluation path (15 October):** build `track_2a/Dockerfile` for
`linux/amd64` using its default `production` stage. The image starts
`src/submission_cli.py` with `--input /data/cases.jsonl --output
/output/predictions.jsonl`; input `/data` is read-only and output `/output`
is writable. `BASE_URL` and `API_KEY` are injected by the organiser at run
time; no Apertus model weights or API secrets are included in the image. The encoder is
bundled at build time, subject to its CC BY-NC 4.0 distribution terms. Selected
model: `swiss-ai/Apertus-v1.5-70B` via the externally provisioned endpoint,
temperature 0 and up to 512 output tokens. This external path does not send the
native/vLLM-specific seed or thinking control. See [RUNNING.md](RUNNING.md).

**Separate developer path:** `make run` uses `compose.submission.yaml` and
`src/booklet_app.py` for one-request demonstrations. The optional managed 8B
vLLM path requires NVIDIA hardware and has not passed a real inference smoke;
it is not the selected evaluation release path.

**Local qualification-oriented development checks (not official scoring):**
60-case exposed-development CSCS 70B runs recorded Task A three-class Macro-F1
**0.6635** with **46/60** valid outputs (14 errors), and Task B **0.8418**
with **60/60** valid outputs, versus OST thresholds **0.60** and **0.75**.
These scores do not establish qualification on the private held-out benchmark.
The historical 54-case paired experiment below used a distinct sample/protocol:
its `vote-aware-v1` Macro-F1 was **0.491**; it is not the same 60-case run.

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

**P0 — resolve organiser failure-row/exit handling:** The production `linux/amd64`
image is published at `ghcr.io/greateden/hackathon26@sha256:87605f3f1c7afad8358e8322bd738593359c4569e959b8d38a0a0d6f47ac07d0` and was
pulled anonymously with exit code 0. The verified default entrypoint is the mixed
Task A/B CLI (`src/submission_cli.py`); `make run` is the separate developer demo.
Rejected cases generate `label: null` error rows, and any failed case causes
batch exit 1; organiser scoring/acceptance of this behaviour is still unknown.
GHCR access alone does not establish a successful private scored batch.

**P1 — submission evidence and deliverables:** The public-image release, anonymous
pull and team licensing review are completed; keep the verified immutable digest.
Rebuild the tracked PDF after the latest LaTeX text edits, verify the organiser's
batch exit/error policy, and complete the actual submission portal process.
Team and notebook metadata are present. No six-page limit was verified in the
supplied OST materials. Independent held-out scoring remains unavailable; do not
promote the exposed prompt pilot.

**P2 — reproducibility and research limitations:** the production image has an immutable registry digest and the encoder revision is pinned in the Dockerfile; the external model endpoint is not bundled. Resolve the recorded MLX tokenizer warning and fresh-native
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
