# Submission readiness verification — 13 October 2026

Bounded readiness audit for the 16 October deadline: it records (1) what the
`make run` submission path verifiably does today, (2) an evidence-based
assessment of frozen `dense-v1` versus the CLI-forced `vote-aware-v1`
candidate, (3) a class-separated statement of the v1.5 inference evidence, and
(4) a smallest acceptance plan with its live-call budget. Methods: offline
inspection on the development machine plus one full offline test run. No
inference, no container execution and no source-code change was made by this
audit. Evidence classes: **VERIFIED** (re-executed here), **OBSERVED** (recorded
artefact inspected), **INFERRED** (interpretation), **NOT TESTED**.

## 1. Executive summary

- **The submission CLI currently forces `vote-aware-v1`.**
  `src/booklet_app.py::main()` sets `request["pipeline_version"] =
  CANDIDATE_PIPELINE` for every run, and `normalise_request()` maps official
  nested requests to the candidate; the flat Python experiment API still
  defaults to `dense-v1` (`validate_request`). This is the state committed in
  the P0 candidate update, not a regression.
- **The only real paired evidence favours `dense-v1` as the submission
  baseline.** On the 54-case paired development evaluation (CSCS Apertus
  v1.5-70B, both arms through `booklet_app.classify` and
  `submission_output`), `dense-v1` produced 43/54 valid official outputs
  (strict accuracy 0.5926, macro-F1 0.652) against 25/54 (0.4259, macro-F1
  0.491) for `vote-aware-v1`; errors remain in the denominator. Raw label
  accuracy was slightly higher for the candidate (0.7593 vs 0.7407): the loss
  is contract rejection, not comprehension. Exact paired McNemar p = 0.122078,
  so single-run variance cannot fully separate the arms — but the failure mode
  is structural and consistent (all 18 gold-neutral cases rejected; 14
  `vote_unrecognised` + 15 `invalid_vote_status`). Neutral is the largest label
  class in the official set (498/1,488 in `data/eval/mnli_swiss_v1.1.jsonl`,
  recounted locally today), so a neutral-hostile contract is a scoring risk,
  not a cosmetic one.
- **Recommendation:** resolve the mismatch between "dense-v1 remains the
  baseline" (`technical_report.md` §7) and "the submission CLI now uses
  vote-aware-v1" (`docs/PROJECT_STATUS.md`) **before** submission. If the team
  accepts the paired-dev evidence, the smallest route is an env-knob
  reverting the CLI default to `dense-v1` (§4 item J), with the §5 acceptance
  plan run afterwards. Do not silently flip defaults while leaving
  `test_p0_contracts.py` and the docs asserting forced-candidate behaviour.
- Submission-blocking unknowns unchanged from `docs/PROJECT_STATUS.md`: no
  managed 8B runtime evidence, no Linux/Windows execution evidence, no cold
  image build, no independent-holdout quality number.

## 2. Verified submission execution path

Chain (all files under `track_2a/` unless stated):

1. Repository-root `Makefile` forwards to `track_2a/Makefile`
   (`$(MAKE) -C track_2a $@`) — VERIFIED by inspection.
2. `make run` → `docker compose -f compose.submission.yaml up --build
   --abort-on-container-exit --exit-code-from app app`;
   `SUBMISSION_MODE=managed` adds `compose.managed.yaml` (vLLM service,
   healthcheck-gated `depends_on`, internal `http://apertus:8000`, required
   `/tokenize` preflight, no published model port); `make run-cscs` exports
   `LLM_NAME=swiss-ai/Apertus-v1.5-70B`,
   `LLM_BASE_URL=https://api.inference.cscs.ch/v1` and
   `LLM_TOKEN_PREFLIGHT=optional` — VERIFIED by inspection of the Makefile and
   both Compose files. The Compose configuration renders on this host today
   (`docker compose -f compose.submission.yaml config --quiet`, exit 0) —
   VERIFIED; no container was started (Docker daemon down today).
3. Image: `python:3.11-slim` + `poppler-utils` + pinned CPU requirements;
   non-root `app` user; no model weights at build; `data/` bind-mounted
   read-write; `hf-cache` named volume for the encoder. `compose.submission.yaml`
   overrides the image default command with `python3 booklet_app.py` —
   VERIFIED by inspection.
4. Endpoint preflight (`SubmissionJudge`): `LLM_BASE_URL` is mandatory (no
   lexical fallback); `/v1/models` must list the configured model; in Docker
   (`SUBMISSION_MODEL_REQUIRED=1`) only `swiss-ai/Apertus-v1.5-8B` and
   `swiss-ai/Apertus-v1.5-70B` are allowlisted, and the third-party MLX
   conversion is refused; a response whose `model` field differs is an error;
   missing/inconsistent token usage or `finish_reason != stop` is an error —
   VERIFIED by inspection plus offline tests.
5. Request contract (`data/request.json`, `REQUEST_FILE`): strict JSON
   (duplicate keys rejected); official Beginner shape (`reference.text`) and
   Advanced shape (`booklet.path` + `vote` + `claim.text`); booklet relative
   paths resolve from the request file's directory; HTTPS booklet URLs are
   fetched with `%PDF` magic-byte verification; language detection restricted to
   de/fr/it; Advanced retrieval returns Top-`top_k` (default 5, 1–20) passages
   from the specified PDF only, encoded with the booklet-language adapter —
   VERIFIED by inspection plus `tests/test_booklet_app.py`.
6. Judgement and output: temperature 0; explicit seed only in
   required-preflight mode; 512 output-token budget; output contains exactly
   `id`, integer `label`, `label_name`, grounded `evidence` and measured
   `metrics` (input/output tokens, inference ms) — missing actual metrics
   reject the run. Neutral emits empty evidence; entailment/contradiction
   require source-grounded citations; every citation is re-verified against
   the supplied source before rendering. Unparseable or failed replies record
   no label and exit non-zero — VERIFIED by inspection plus offline tests.
7. Today's runtime state: Docker daemon not running (colima stopped); port
   8000 occupied by the MTPLX assistant model server serving
   `mtplx-flash-next-optimized-speed` — that endpoint is **not** an Apertus
   endpoint and must not be wired into `LLM_BASE_URL`.

## 3. dense-v1 versus vote-aware-v1 (assessed per entry-point criterion)

| # | Criterion | Status | Detail |
|---|---|---|---|
| A | Official nested Beginner input | Both | `normalise_request` handles `reference` shapes; `data/request.json` (Beginner) would route through the candidate today |
| B | Official nested Advanced input (booklet + vote + claim) | Both | Candidate adds the vote to the retrieval query and the identity gate; dense sends the claim-only query |
| C | Advanced booklet PDF path | Both | Identical extraction/Top-5 stack; candidate adds `source_passages` offsets |
| D | Citation validity | Candidate stricter, not safer | Dense checks snippet occurrence (paraphrases fail, recorded in earlier audits); candidate copies source spans but the one live smoke produced a mid-word span — boundary defect recorded, not fixed |
| E | Output contract compliance | Both | Same five-field official JSON; candidate adds identity/sufficiency gates that rejected 29/54 paired cases |
| F | Failure handling | Both | Errors record `label: None` and exit 1; no lexical fallback in either arm |
| G | Measured validity (n=54 exposed dev, single runs) | dense ahead | 43/54 vs 25/54 valid; strict 0.5926 vs 0.4259; macro-F1 0.652 vs 0.491; McNemar p = 0.122078 (single-run variance not excluded); all 18 gold-neutral rejected in candidate |
| H | Provenance impact of reverting the CLI default | None, if done openly | `dense-v1` is not new code: the paired run executed it through the same `classify`/`submission_output` path. A versioned, documented switch plus a post-switch rerun *improves* integrity; silently shipping the candidate while quoting dense numbers would not |
| I | What a switch minimally requires | NOT IMPLEMENTED | An env knob (e.g. `SUBMISSION_PIPELINE`) or CLI default change in `booklet_app.main`; `normalise_request` default; updates to `tests/test_p0_contracts.py` (two tests assert CLI-forced candidate), `README.md`, `docs/RUNNING.md`, `docs/P0_CORRECTNESS.md` wording. Then §5 acceptance on the chosen default |
| J | Decision status | OPEN | `docs/PROJECT_STATUS.md` declares the candidate as the current CLI path; `technical_report.md` §7 says the results do not justify promoting it. The contradiction must be resolved by the team before submission |

Sources for the numbers: `docs/evidence/vote_aware_paired_results_20261013.json`
(VERIFIED recount today), `docs/P0_CORRECTNESS.md` (13 October validation
section), `docs/evidence/offline_attribution_v2/verification_report.md`.

## 4. v1.5 inference evidence — three classes that must not be conflated

1. **Official `swiss-ai/Apertus-v1.5-8B`: NOT TESTED.** No run has loaded the
   official weights. Current evidence is static only: the allowlist, Compose
   defaults and configuration renders (VERIFIED statically). The managed vLLM
   path needs a Linux/NVIDIA host, authorised access and a large initial
   download — none available on this machine.
2. **`swiss-ai/Apertus-v1.5-70B` (CSCS): OBSERVED.** One real Docker Advanced
   smoke (exit 0, entailment, recognised vote, page-19 citation, one-brace
   syntax recovery, 1,330/91 tokens) and the 108-call paired development
   evaluation (scripted entry point `src/vote_aware_paired_eval.py`). Both are
   real v1.5 inference records; neither is an accuracy result, and both used
   previously exposed development data.
3. **`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit` (third-party conversion):
   OBSERVED, development-only.** n=1 local smoke (independently confirmed
   1,007-token prompt, verified page-15 citation, `finish_reason=stop`) plus
   n=9 retrieval-only evidence. The Docker submission path deliberately refuses
   this conversion; never quote these numbers as the submission model.

Report/README wording must keep the classes separate: "real v1.5 evidence
exists" is true for classes 2 and 3 only, and only as path/smoke evidence.

## 5. Smallest acceptance plan (use after any baseline switch, or to certify the current default)

Stage 0 — offline, zero live calls:
- `make test` (174 offline checks) and
  `docker compose -f compose.submission.yaml config --quiet`.

Stage 1 — deterministic mock endpoint (zero live calls): one `make run`
against a mock OpenAI-compatible server without `/tokenize` (the 12 October
check), plus one run against a down endpoint (expect exit 1 before PDF or
encoder work, no lexical fallback).

Stage 2 — one real external endpoint inside Docker, **four live calls**:
- T1 Beginner entailment (1 call): five-field JSON, `page: null` evidence,
  positive integer token and latency metrics.
- T2 Advanced DE→DE retrieved (1 call): verified page/offset citation checked
  by hand against the PDF; if the candidate default ships, the vote must be
  recognised.
- T3 Advanced neutral claim (1 call): neutral with empty evidence must
  produce a valid output, not an error (this is exactly where the candidate
  failed 18/18 paired cases; the dense default must be shown to pass here).
- T4 Advanced FR claim → DE booklet (1 call): cross-language adapter path.
- Optional T5 (candidate only): ambiguous/absent vote name → expect the
  identity error path and exit 1.

Pass criteria per call: configured model id echoed, `finish_reason=stop`,
usage totals consistent, no silent fallback, exit code propagated, managed
mode leaves no running server after `make run` exits. Repeat Stage 2 once on
a Linux amd64 host (required for the managed path) and once on Windows/WSL2
(recipe-level); Stage 1+2 on the chosen default only, to halve the budget.
Optional evidence-integrity step after a baseline switch: rerun
`src/vote_aware_paired_eval.py` on the frozen 54-case set for the new default
(54 calls, single arm) before quoting any comparison figures post-switch.

## 6. Checks executed in this audit (13 October, this machine)

- `make test` from the repository root: **174 tests, OK**, before and after
  the documentation corrections made today. (A run with bare system `python3`
  instead of the project `.venv` reproduces the documented mlx_lm/torch
  environment failures; those are environment-dependent, not regressions.)
- `docker compose -f compose.submission.yaml config --quiet`: exit 0
  (client-side render only; daemon down, so no runtime claim).
- Git state at audit start: branch `experiment-multilingual-retrieval-ablation`
  at `0048286`, clean working tree.
- Documentation corrections applied (provenance only, no metric changed):
  `technical_report.md` §7/§9,
  `docs/evidence/offline_attribution_v2/verification_report.md` §4.2/§5, and
  the Git-ignored `data/experiments/vote-aware-paired-v2/offline_attribution_v1/handoff.md`.
  The attribution analyst was a local Qwen-family assistant, a different model
  family from the Apertus predictors; the annotations remain AI-generated and
  are not independent ground truth.

## 7. Still NOT TESTED / open risks

- Managed 8B Docker runtime (NVIDIA host, authorised weights), Linux x86-64
  and Windows execution, cold network image build.
- Any independent-holdout accuracy; all quoted figures use exposed development
  data, single runs, one remote endpoint, no variance control.
- Semantic citation sufficiency (mechanical provenance only); the recorded
  mid-word citation boundary defect from the 70B smoke.
- Final report PDF, team/demo metadata, licence review, and the challenge-portal
  specific rules that could not be read live (per `docs/PROJECT_STATUS.md`).
- `data/` submitted-size and no-credentials findings were taken from the
  12–13 October audits (OBSERVED, not re-audited here; tracked `data/` files
  were confirmed to be only README.md, `request.json` and
  `example_claims.json`).