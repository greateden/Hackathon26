# Repository repair and runner handoff — 11 October 2026

Implemented and verified offline. No model inference, embedding computation,
large download, container build/start, commit or push was performed. The six
pre-existing modified deployment/documentation files were preserved and updated.
Historical raw results and dated reports were retained.

## Findings and resolution

| Priority | Confirmed problem | Resolution |
|---|---|---|
| P0 | External endpoint configuration still depended on the NVIDIA model service | Split the CPU app and managed server into base/overlay Compose files; `make run SUBMISSION_MODE=external` starts the app alone |
| P0 | Model name matching accepted any string containing Apertus and v1.5; completion identity was not checked | Explicit official/known-MLX allowlist, official-only Docker guard and exact completion model check |
| P0 | Model-generated JSON could replace recorded model, usage and other provenance fields | Copy only parsed label, reasoning, snippet and error fields |
| P0 | Optional MLX token preflight could not reject an overlong full booklet before inference | New cached-only manual server exposes the actual tokenizer and loaded checkpoint metadata; paired runs require exact token preflight |
| P1 | Paired results were written only at the end, with no safe resume and a hardcoded official model name even for MLX | One three-mode runner, immediate durable attempt records, frozen resume contract, explicit errors and genuine backend metadata |
| P1 | Incomplete input validation could reach endpoint setup before rejecting malformed requests | Validate one booklet/claim and language/top-k fields first; check supplied booklet/evidence identity |
| P1 | Token usage validation accepted incomplete or wrongly typed measurements | Require integer prompt/completion counts, matching preflight and complete generation |
| P1 | Local pinned encoder paths could trigger the global-cache tokenizer fallback | Use the tokenizer in the selected local snapshot before any global-cache fallback |
| P2 | Encoder progress polluted stdout; deployment documentation and old paired CLI were inconsistent | Send progress to stderr, add RESULT_FILE handling, replace obsolete CLI with documented runner and retain plan/coverage helpers |

A missing or unlocatable citation remains explicit. Native label metrics and
citation verification are separate; the Docker smoke requires both a label
and a verified citation. No prediction improvement follows from these repairs.

## Requirement verification

The current [project template](https://github.com/HackApertus/project-template)
and [Track 2A README](https://github.com/HackApertus/project-template/blob/main/track_2a/README.md)
require the fixed track directory, Docker `make run`, standard LLM environment
variables and at most 100 MB of submitted data. Track 2 requires Apertus; v1.5
is the stricter acceptance target in this task. The template directs submissions
to the event website, not Devpost. The [Devpost rules](https://hackapertus.devpost.com/rules)
confirm 16 October 2026, 12:00 CEST. The online-hack page returned no readable
content, and the challenge/portal pages remained inaccessible to the tool.
The local original specification was read; it is a historical transcription,
not independent confirmation of current challenge-specific requirements.
The final six-page PDF, team/demo metadata and licensing review remain open.

## Files

Changed:

- `.env.example`, `Makefile`, `Dockerfile`, `compose.submission.yaml`
- `README.md`, `technical_report.md`
- `docs/PROJECT_STATUS.md`, `docs/RUNNING.md`
- `src/booklet_app.py`, `src/eval_paired.py`, `src/retriever.py`
- `tests/test_booklet_app.py`

Created:

- `compose.managed.yaml`
- `src/experiment_runner.py`, `src/serve_experiments.py`
- `tests/test_experiment_runner.py`, `tests/fixtures/paired_examples.json`
- `docs/EXPERIMENTS.md`, this handoff
- `docs/evidence/runner_regression_20261011.txt`

No whole files were deleted. The obsolete non-resumable execution/CLI portion
of `eval_paired.py` was removed; its deterministic planning and coverage helpers
remain. Generated preflight output is under ignored `data/experiments/v15-paired/`.

## Verification

- Runner-specific suite: 24 mocked/offline tests passed. Application-specific
  suite: six tests passed before the final regression.
- `make test` ran once after implementation: all 53 judge/label checks passed,
  all source files compiled, and 92 discovered unittest tests passed (0.094 s).
  [Full sanitised output](evidence/runner_regression_20261011.txt). PASS messages
  inside smoke unit tests refer to command doubles, never real inference.
- Actual offline preflight: PASS; nine original rows, all nine language pairs,
  three examples per label, 18 planned calls, at most 36 with the default retry.
  Cached PDF extraction, dependency imports and pinned checkpoint availability
  passed. Both Compose variants and both Make dry-runs passed.
- Both new scripts' `--help` commands passed. `pip check` reported no broken
  requirements in the existing environment. No lint/type configuration or
  installed Ruff/mypy executable was present; no toolchain was installed.
- `git diff --check` passed after removing one extra trailing blank line.
- Docker daemon unavailable; no listener on 8000 or 8080. Host RAM verified as
  128 GiB. These read-only checks started no services.

Failure tests cover unavailable endpoints, timeouts/retries, malformed output,
wrong models, missing usage, incomplete completions, context overflow, invalid
inputs, missing files, unrelated evidence, interrupted requests, partial log
writes, changed resume contracts, missing Docker/GPU/credentials, smoke timeout
and absent deployment results. Existing regression checks remain intact apart
from moving the old paired-loop test into the new runner contracts.

## Commands and results

See [EXPERIMENTS.md](EXPERIMENTS.md) for directly copyable commands. From this
project directory:

```bash
../.venv/bin/python src/experiment_runner.py preflight
# Terminal 1; manual cached model load:
../.venv/bin/python src/serve_experiments.py --context 32768
# Terminal 2:
../.venv/bin/python src/experiment_runner.py run
# Optional, on provisioned NVIDIA Docker hardware:
../.venv/bin/python src/experiment_runner.py submission-smoke --out data/experiments/submission-managed
```

The real native run will create `manifest.json`, `predictions.jsonl`,
`summary.json` and `summary.md` in `data/experiments/v15-paired/`, alongside
`preflight.json` and `events.jsonl`. Optional smoke artefacts use the selected
smoke directory. Send the four main files to ChatGPT; include events for an
interrupted run and separate smoke summaries when available.

Plan for 18 calls, or at most 36 with default retries. A warm native run might
need 5–30 minutes; this is an estimate, not a measurement. Repeated 180-second
completion timeouts alone can consume 108 minutes. Allow roughly 20 MB of
result storage; cached MLX weights are about 6.54 GB, with additional encoder,
PDF and KV-cache memory. Minimum RAM/VRAM and Docker image storage remain
unmeasured. Full-booklet context rejections may reduce actual model-call count.

## ChatGPT Handoff

- Current state: specified-booklet v1.5 application; managed Docker default,
  explicit external endpoint mode, native paired runner implemented. Real runs pending.
- Changes: deployment split, model/provenance/input hardening, resumable runner,
  cached MLX instrumentation and concise documentation; files listed above.
- Evidence: 24 focused tests; 92 regression tests plus 53 judge checks;
  actual preflight PASS for the frozen nine-row matrix. No new model measurements.
- Prediction changes: none measured; no inference ran.
- Uncertainties: first real wrapper launch, full-booklet context fit, real Docker
  startup, clean checkout, cross-platform operation and final deliverables.
- Next experiment: run the frozen 18-call native comparison to measure paired
  accuracy/F1, citation validity, token cost and latency without changing settings.
- Execution status: no model server running on 8000/8080; Docker daemon stopped.
  User manually starts the documented server, runs the matrix and stops it with Ctrl-C.
