# Official Apertus v1.5-8B submission smoke — blocked pre-flight record (2026-10-14)

**Scope.** Bounded acceptance gate: determine whether the actual submission
entrypoint (`make run` → `compose.submission.yaml` → `src/booklet_app.py`)
can run against a genuine, provisioned OpenAI-compatible endpoint serving
exactly `swiss-ai/Apertus-v1.5-8B`. **No inference request was executed in
this session.** This file records the pre-flight blockers only; it is not a
test record and must not be cited as evidence that any smoke ran.

**Status: BLOCKED / NOT TESTED.** Acceptance criteria A–F of the acceptance
plan were not evaluated because no qualifying endpoint existed on this host.

## Environment facts (VERIFIED by direct probe, 2026-10-14, host macOS)

- Branch `feature/votelens-research-positioning`, HEAD `0a87676`, working
  tree clean (VERIFIED via `git status --porcelain`).
- `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY` unset in the environment; no
  `.env` file present. Therefore the default `make run` path exits non-zero
  at `SubmissionJudge` construction (empty `LLM_BASE_URL`); this is the
  designed fail-hard behaviour, not a new defect (VERIFIED by code read of
  `src/booklet_app.py`).
- Docker CLI and colima installed; **colima daemon not running** (VERIFIED:
  `docker version` cannot reach `~/.colima/default/docker.sock`;
  `colima status` → "colima is not running"). No Docker daemon was started,
  no image pulled, no dependency installed, per the session's authorisation
  boundary. Whether `hackapertus:local` is cached is unknown (daemon down);
  a cold build on this host would additionally require base-image and
  dependency downloads.

## Endpoint identity survey (VERIFIED 2026-10-14)

Only four candidate backends were found; **none serves the official
`swiss-ai/Apertus-v1.5-8B`**:

| Endpoint / artefact | Identity check | Qualifies? |
|---|---|---|
| `http://127.0.0.1:8000` (running) | `/v1/models` lists `mtplx-flash-next-optimized-speed` (MTPLX server, Qwen3-class custom build) | NO — third-party non-Apertus; would be rejected by the `/v1/models` identity gate |
| `https://api.inference.cscs.ch/v1` (reachable) | serves CSCS Apertus v1.5 **70B**; no API key configured locally | NO — wrong model size; 70B is not the official 8B acceptance target |
| HF cache `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit` | present on disk; no server running | NO — third-party quantised MLX; explicitly refused on the Docker submission path |
| HF cache `swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4` | present on disk; no server running | NO — historical v1.1 research path only |

No other OpenAI-compatible listeners were found (`lsof` sweep of common
ports plus full listening-socket listing). Endpoint addresses were not
guessed or invented.

## Neutral-rejection mechanism note (SOURCE-RECORDED + code-VERIFIED; no 8B measurement)

The historical 54-case paired development study on **CSCS 70B** recorded
vote-aware strict accuracy 23/54 with only 25/54 valid outputs; of 29
rejections, 18 had gold-correct raw labels, including 12 neutral outputs
rejected with `vote_status = null` (see
`vote_aware_paired_results_20261013.json` and the offline attribution v2
record in this directory). That is **70B development evidence, not official
8B evidence**, and supports no population-level rejection-rate inference.

The rejection chain was confirmed by reading current code
(`src/booklet_app.py`, `candidate_result` / `submission_output` /
`referenced_citations`): in `vote-aware-v1` advanced mode a neutral label
additionally requires `vote_status = recognised` with a resolvable
`vote_reference` passage, plus `evidence_status = insufficient` and empty
`evidence_refs`; a missing/null `vote_status` fails as
`vote_invalid_vote_status` before any NLI-quality assessment. Whether the
official 8B model can satisfy this chain end to end remains NOT TESTED.

## Required configuration for a real 8B smoke (next operator's checklist)

1. Provision a v1.5-8B OpenAI-compatible endpoint that advertises exactly
   `swiss-ai/Apertus-v1.5-8B` (e.g. `make run SUBMISSION_MODE=managed` on a
   compatible NVIDIA host — itself unverified — or any already-provisioned
   service; do not substitute CSCS 70B, the third-party MLX conversion or
   the local MTPLX server).
2. Start the colima/Docker daemon.
3. Set in `.env`: `LLM_NAME=swiss-ai/Apertus-v1.5-8B`,
   `LLM_BASE_URL=<endpoint>`, `LLM_API_KEY` if required,
   `LLM_TOKEN_PREFLIGHT=optional` unless the endpoint exposes `/tokenize`.
4. Before any run, verify identity with `curl <base>/v1/models` and confirm
   the exact id; a run against a wrong-model endpoint must not be reported
   as smoke success even on exit 0.
5. Only then run the bounded smoke (max 4 requests), with temp fixtures in a
   git-ignored `data/smoke/` subdirectory via container paths
   (`/app/data/smoke/...`).

## Claims boundary

- VERIFIED: everything above produced by direct probing or reading tracked
  code in this session.
- SOURCE-RECORDED: the 70B paired-development figures (from the tracked
  evidence files cited, not re-derived here).
- NOT TESTED: Beginner runtime, Advanced runtime, Neutral end-to-end
  acceptance, token-usage path on a real endpoint, Docker image build or
  cross-platform portability, and any accuracy statement. None of these may
  be recorded as PASS until executed against the official 8B model.