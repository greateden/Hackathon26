# Running the paired experiment

Run commands from `track_2a/`. Use the preserved repository environment;
no packages or weights are installed by this runner.

## Completed prompt-only pilot

`data/experiments/prompt-pilot27-v1/` contains the ignored raw records for the
completed 27-row, 54-call CSCS Apertus v1.5 70B comparison. The frozen plan and
compact result are tracked as
[`prompt_pilot27_plan_v1.json`](evidence/prompt_pilot27_plan_v1.json) and
[`prompt_pilot27_results_v1.json`](evidence/prompt_pilot27_results_v1.json).
Both prompts used identical retrieved evidence. Accuracy was 23/27 for each;
the refined prompt used 18.8% more input tokens, so `current_v1` remains the
production default. This exposed development sample is not a held-out test.

To regenerate only the derived summaries, without inference:

```bash
../.venv/bin/python src/prompt_ab_experiment.py summarise --out data/experiments/prompt-pilot27-v1
```

## Preflight

```bash
../.venv/bin/python src/experiment_runner.py preflight
```

This reads the frozen dataset and nine verified examples, extracts the cached
PDFs, checks package imports, cached checkpoints, Python syntax, output access,
Compose configuration and both Make recipes. It does not call an endpoint,
load model weights, compute embeddings or download anything. Docker checks are
static; missing Docker prerequisites are reported separately from native ones.
A clean checkout needs the official dataset and PDF cache prepared manually
with `make eval-data` and `make fetch-booklets`; it also needs the documented
model caches. Preflight reports their absence without fetching them.

The selected original rows are 1095, 192, 979, 1328, 171, 533, 187, 555 and 1365.
They cover all nine DE/FR/IT claim–booklet combinations, with three examples
per label. The runner checks the dataset SHA-256 against the saved plan and
compares the rows with `tests/fixtures/paired_examples.json`. These are existing
official examples, not generated labels. The historical development split has
content overlap with its complement; this small experiment is not a held-out
quality benchmark.

## Native MLX run

In terminal 1:

```bash
../.venv/bin/python src/serve_experiments.py --context 32768
```

This manual command loads only the cached 6-bit text conversion
`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`, revision
`9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`, using mlx-lm 0.32.0. It binds to
loopback port 8080 and disables thinking. Missing weights cause an error;
o download is attempted. Do not use the historical `make serve-apertus`,
whose default is v1.1. If another service occupies port 8080, choose `--port`
and use the matching `--endpoint` below.

In terminal 2:

```bash
../.venv/bin/python src/experiment_runner.py run
```

The runner obtains loader metadata from `/experiment-metadata` and checks the
model class, revision, configuration, shard identities and sizes against the
cached snapshot. This is local instrumentation, not cryptographic attestation
of an arbitrary remote server. `/v1/models` alone would be insufficient: the
standard MLX server lists cached models, including ones it has not loaded.
The wrapper's `/tokenize` uses the server's own `_tokenize` method. Both arms
require exact agreement between that count and the completion's prompt usage.
The adapter is specific to mlx-lm 0.32.0 and has only been tested with doubles
in this repair session; its first real launch remains to be verified.

Full means every extracted non-empty physical PDF page, including its final
text. Retrieved means five contiguous 900-character chunks ranked only within
that same PDF. Both use the booklet-language SwissBERT adapter. The encoder is
loaded from cached revision `7a91fa8a01af56c1f06060f7af3698ef5619e41c`.
The claim, prompt templates, model, temperature 0, seed 20261011, 512-token
output allowance and parser are identical. Arm order alternates by item.
No gold reference enters inference. Complete messages and evidence are saved,
so the payload difference can be inspected directly.

Input plus output allowance must fit 32,768 tokens. Overlong full booklets
produce `context_limit` without a completion request; they are never shortened
and called a full baseline. This is a configured budget below the checkpoint's
architectural maximum, not a measured hardware capacity. Token limits are
checked during `run`, not guessed from page counts in offline preflight.

Stop terminal 1 with Ctrl-C after the experiment. The runner never starts or
kills the model server.

## Failure and resumption

```bash
../.venv/bin/python src/experiment_runner.py run --resume
```

Completed arms are skipped. Previously failed or interrupted arms remain
failed unless explicitly retried:

```bash
../.venv/bin/python src/experiment_runner.py run --resume --retry-failed
```

Code, environment, dataset, extracted text, PDF bytes and configuration must
match the original manifest. A changed contract requires a fresh directory,
for example `--out data/experiments/v15-second`. Keep the same CLI options on
resume. A file lock prevents concurrent writers. A damaged final JSONL write
is backed up before its incomplete tail is removed; earlier corruption stops
the runner. A request started before a hard interruption has an unknown
outcome and is recorded as such. Retrying may therefore repeat server work.

Default request limits are 10 seconds for model/metadata checks, 30 seconds
for tokenisation and 180 seconds for a completion. There is one retry for a
network timeout or connection failure, and every failed attempt is retained.
Malformed replies, wrong models, missing usage and context overflow are not
retried automatically. `--retries 0` disables automatic retries; the maximum
is two. HTTP error responses are retained without automatic retry. A requests
read timeout bounds inactivity, not the duration of a server that continuously
sends data. Exit codes: 0 complete/preflight passed, 1 recorded failures,
2 blocked prerequisites or incompatible resume, 130 interrupted.

## Output schema

Default directory: `track_2a/data/experiments/v15-paired/`, ignored by Git.

| File | Contents |
|---|---|
| `preflight.json` | Offline checks, input plan and missing prerequisites |
| `manifest.json` | `hackapertus-experiments-v1`, Git revision, source hashes, package versions, frozen contract and server sessions |
| `events.jsonl` | Durable start record for every attempted item and arm |
| `predictions.jsonl` | Append-only attempt records: input, messages, gold, prediction, passages, citations, usage, timing, errors and status |
| `summary.json` | Latest attempt per arm, earlier failed-attempt count, metrics, token coverage, payload hashes and prediction changes |
| `summary.md` | Short human-readable status and metric table |

Errors count as failed predictions in attempted-row accuracy/F1. Missing rows
are reported separately and excluded from those partial metrics. A second
paired-success table uses only rows completed by both arms. Missing usage
stays missing; a token sum always includes its measured-row count. Runtime
includes failed attempts. A verified citation proves that a snippet occurs in
the supplied text, not that its NLI interpretation is correct. Null or missing
results never become neutral predictions. Earlier attempts remain in JSONL
even when a later retry succeeds.

API keys, environment dumps, local cache paths and raw deployment logs are
not written to these artefacts. The endpoint and public booklet URLs are
recorded. Keep secrets out of URLs and claims.

## Optional real Docker smoke

After provisioning the official model's access and compatible Docker hardware:

```bash
../.venv/bin/python src/experiment_runner.py submission-smoke --out data/experiments/submission-managed
```

To use an already running official v1.5 endpoint, configure `LLM_BASE_URL`,
`LLM_NAME` and credentials in `.env` as described in [RUNNING.md](RUNNING.md):

```bash
../.venv/bin/python src/experiment_runner.py submission-smoke --deployment external --out data/experiments/submission-external
```

This external smoke also accepts the allowlisted CSCS 70B model and optional
token preflight. Configure the CSCS values documented in RUNNING.md first; the
smoke records the selected model and preflight mode, and still requires exact
response-model identity, usage, a parsed label and a verified citation.

This invokes `make run` itself, with an isolated request/result file under the
output directory. Managed mode checks Docker's NVIDIA runtime and requires
`HF_TOKEN`; external mode probes model identity/access without a local GPU.
An unavailable endpoint or missing deployment prerequisites is `BLOCKED`.
The opt-in smoke can build/pull images and download uncached official weights,
encoder files and the sample PDF. Its default deadline is 2,400 seconds.
A configuration check can never produce PASS. A successful real result must
match the requested booklet/claim, official response model, label and citation.
It is one application smoke, not clean-checkout or cross-platform proof.
The smoke records manifest, predictions and both summaries in its selected
directory; a new attempt needs a new directory. No real smoke was run during
this repair session.

## Cost and handoff

The native matrix has 18 planned completion calls, at most 36 with the default
single retry; context failures reduce that count. Allow roughly 5–30 minutes
for a warm local run, as a planning estimate only. Eighteen doubled 180-second
completion timeouts could consume about 108 minutes, plus tokenisation and
setup. Booklets contain 31–144 non-empty pages, so some full arms may exceed
the chosen context budget. No paired runtime has been measured.

The cached MLX weights occupy about 6.54 GB; long-context KV memory and the
encoder need additional RAM. This checkout uses an Apple Silicon machine
with 128 GiB; minimum RAM has not been established. Allow about 20 MB for
result artefacts, excluding existing model/PDF caches. Native runs download
nothing. Managed Docker needs an NVIDIA GPU/runtime and substantial extra
image/weight disk space; minimum VRAM and exact storage remain unmeasured.

Send `summary.md`, `summary.json`, `manifest.json` and `predictions.jsonl` to
ChatGPT, plus `events.jsonl` if interrupted and the separate Docker-smoke
summaries if attempted. These files preserve both results and their limits.
