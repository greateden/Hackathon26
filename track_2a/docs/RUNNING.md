# Running the submission application

Run the following commands from `track_2a/`, the project root.

The submission path is `make run` → Docker → `booklet_app.py`. Historical
experiments remain in `main.py` and `compose.yaml`. Docker supplies application dependencies; a separately provisioned model
endpoint is required. No model server lifecycle is orchestrated by `make run`.

## Prerequisites

- GNU Make and a running Docker engine with Compose v2. Docker builds the CPU
  application image, including Poppler and SentenceSwissBERT dependencies.
- A provisioned **vLLM-compatible Apertus v1.5 8B endpoint** reachable from the
  container, exposing `/v1/models`, `/tokenize`, and `/v1/chat/completions`.
  An API key is needed only if the endpoint requires one. The endpoint must
  return token usage and reject overlong requests rather than truncate them.
- Internet for the image/dependencies, sample PDF and initial SwissBERT cache,
  or those resources pre-populated. The application does not download LLM
  weights. Scanned PDFs without an embedded text layer require separate OCR.

Copy `.env.example` to `.env`, set the endpoint and optional key, then run:

```text
make run
```

This recipe uses no POSIX environment-assignment prefix or shell discovery.
Windows CMD portability has been checked statically only; Windows execution
has **not** been tested. GNU Make must be available on Windows. The legacy
Make targets still contain POSIX commands and are not Windows-supported.

`LLM_BASE_URL` can include `/v1` or omit it. For a host service, use
`http://host.docker.internal:8000` and bind that service to an interface Docker
can reach. `localhost` inside the container refers to the container itself.
`LLM_CONTEXT_TOKENS` must match the server's actual configured context limit.
A missing endpoint variable fails at Compose interpolation, before image build;
unreachable or wrong-model endpoints fail before PDF or encoder loading.
No lexical fallback exists in this path.

## Input and output

Edit `data/request.json`. It contains:

```json
{
  "booklet": "/app/data/my-booklet.pdf",
  "booklet_language": "de",
  "claim": "Der Bundesrat empfiehlt die Annahme der Vorlage.",
  "claim_language": "de",
  "evidence": "retrieved",
  "top_k": 5
}
```

`booklet` accepts an HTTPS PDF URL, a PDF path inside the container, or the stem
of a cached PDF under `data/booklets/pdf/`. Put a local PDF under host `data/`
and use its `/app/data/...` path. The supplied language codes are `de`, `fr`,
`it` in any combination. `evidence` selects `full` or `retrieved`. The full
arm sends all extracted pages; the retrieved arm ranks only that PDF's chunks.
The supplied booklet language selects the SwissBERT adapter for both sides.

Output contains `label_code` (0 entailment, 1 neutral, 2 contradiction), label,
reasoning, supplied passages, PDF hash and physical page references. `citations`
contains passages with a verified verbatim model snippet; `citation_verified`
is false when that snippet cannot be located. Supplied passages are not proof
that the model's conclusion is correct. Errors retain a null label and return
a non-zero exit code. Save machine-readable output with:

```text
docker compose -f compose.submission.yaml run --build --rm app python3 booklet_app.py --out /app/data/results_submission.json
```

Existing output files are never overwritten. The JSON file excludes encoder
progress messages printed to the terminal.

## Paired development experiment

Fetch the official dataset with the existing `fetch_eval_data.py` if absent.
It is an evaluation prerequisite, not an application prerequisite.

```text
docker compose -f compose.submission.yaml run --build --rm app python3 eval_paired.py --limit 9 --out /app/data/eval_results_paired_v15.json
```

The deterministic sample is restricted to the historical development pool,
normalised-content deduplicated, and alternates arm order. Both arms use the
same judge, temperature 0, seed 20261011, output budget 512 and parser. Full
input is tokenised before generation and rejected if it cannot fit. No input
truncation parameter is sent; usage must agree with preflight tokenisation.
Gold references enter only the post-inference 40-character shingle coverage
proxy. This is lexical annotation coverage, not human-rated evidence quality.
Per-item raw replies, prompt hashes, input tokens, latency, errors, citations
and paired prediction changes are saved. A provider without `/tokenize` is
unsupported; do not disable this check to get a baseline score.

## Local Apple Silicon development endpoint (MLX) — not the submission path

One genuine local retrieved-evidence run is saved in
[evidence](evidence/README.md): entailment, page 15, 1,007 input / 71 output
tokens. This is a smoke test, not a paired quality evaluation.

For development on an Apple Silicon Mac the application can instead talk to a
local `mlx_lm.server` serving `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit` (the text
branch of Apertus v1.5, 6.54 GB, `model_type: apertus`, loaded by the repo `.venv`
with mlx-lm 0.32). Two endpoint differences keep this a development path only:

- it does not implement `/tokenize` (that path answers 404), so
  `LLM_TOKEN_PREFLIGHT=optional` must be set. Input length is then not rejected
  before generation; only `finish_reason="stop"` plus a reported prompt token count
  are trusted, and a missing count or a `length` finish is recorded as an error.
  Keep `required` (the default) for any submission endpoint, which must reject
  overlong input instead of truncating it.
- it lists models as Hugging Face cache repo ids, so `LLM_NAME` has to be the
  served id (`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`) rather than
  `swiss-ai/Apertus-v1.5-8B`. The id must still appear in the endpoint's
  `/v1/models`, and v1.1 or non-Apertus ids remain refused.

Use the existing repository-root `.venv` (do not relocate it: installed
scripts contain absolute paths). A fresh native environment is not validated;
the portable Transformers pin and MLX requirements cannot simply be combined.
The following command uses the cached model; if absent, it would download about
6.54 GB. Download and server startup are manual, not cleanup actions.

Terminal 1, from `track_2a/` (thinking disabled, as in the successful smoke):

```text
../.venv/bin/mlx_lm.server --model m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit --host 127.0.0.1 --port 8080 --chat-template-args '{"enable_thinking":false}'
```

Terminal 2, from `track_2a/`, export the variables explicitly. Native Python
**does not load `.env`**; Compose does. The default `data/request.json` uses a
public PDF URL. For local inputs use a native path or cached PDF stem, not
`/app/data/...`.

```bash
export LLM_BASE_URL=http://127.0.0.1:8080
export LLM_NAME=m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit
export LLM_TOKEN_PREFLIGHT=optional
export LLM_CONTEXT_TOKENS=32768
../.venv/bin/python src/booklet_app.py --input data/request.json --out data/results_mlx_dev.json
```

Stop the server with Ctrl-C in terminal 1 when finished. The historical
`make serve-apertus` default remains v1.1; it is not the v1.5 smoke recipe.
The first recorded attempt exhausted 512 output tokens; only the later
thinking-disabled attempt produced the successful verdict. Token counts were
independently checked for that saved example, not for all optional-mode inputs.

`mlx_lm.server` applies the checkpoint's own `chat_template.jinja`; verify in the
saved output that the reply parses (no `unparseable_response` error) before
treating any label as a model judgement. Apple Silicon Docker supplies no CUDA
device, so the container never runs inference itself — it only calls an external
endpoint. Results from this MLX path are not comparable with a vLLM v1.5 run
(different quantisation, sampler and template handling).

## Model provisioning boundary

The supported application path consumes an already provisioned endpoint;
local GPU server lifecycle is **not** orchestrated in this iteration. This is
an outstanding reproducibility limitation if judges require self-hosted model
startup. Native v1.5 MLX inference is evidenced; the vLLM submission endpoint and
self-contained startup have not been verified.

The [official v1.5 model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)
currently specifies modified vLLM/Transformers builds. Its published container
is `ghcr.io/swiss-ai/vllm_apertus_1.5_release:latest-amd64` (also arm64).
Do not use the application's old Transformers pin to load v1.5. Provision the
server separately on appropriate NVIDIA GPU hardware, using the official
image and `vllm serve swiss-ai/Apertus-v1.5-8B`, with
`--chat-template-content-format string` and a context limit that fits the GPU.
The published image tag is mutable: freeze a tested digest before submission.
These provisioning notes are not evidence of a tested server installation.
Apple Silicon Docker does not provide an NVIDIA CUDA device; an arm64 image
alone does not solve that. No image or large weights were downloaded during repository cleanup. The
previous local MLX run used already cached weights.

## Portability and verification limits

The Docker build context is this directory. Compose mounts `./data` at
`/app/data`; `REQUEST_FILE` must be a container path. Set endpoint variables in
this directory's `.env`, including when invoking the root Makefile wrapper.
The submission Compose file deliberately does not forward
`LLM_TOKEN_PREFLIGHT=optional`; its default remains required.

macOS, Linux and Windows Docker execution of this submission path is pending.
Static Compose validation is not an image build or a container networking test.
Windows requires GNU Make (or the equivalent `docker compose` command), and
Docker Desktop must use Linux containers. Linux bind-mount permissions may
need adjustment for the image's non-root `app` user. No privileged workaround
is configured. Historical native targets use POSIX shell syntax.

`make test` uses a project-local `.venv` if available, then the preserved
repository-root `.venv`, otherwise `python3`. It loads no model. Historical
scripts and their limitations are indexed in [the archive](archive/README.md).
