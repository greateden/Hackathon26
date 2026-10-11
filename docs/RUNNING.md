# Running the submission application

The submission path is `make run` → Docker → `booklet_app.py`. Historical
experiments remain in `main.py` and `compose.yaml`. No preparatory Make target,
local Python installation, global corpus checkout or manually started MLX
server is part of the submission path.

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

## Model provisioning boundary

The supported application path consumes an already provisioned endpoint;
local GPU server lifecycle is **not** orchestrated in this iteration. This is
an outstanding reproducibility limitation if judges require self-hosted model
startup. There is no verified v1.5 inference installation on this Mac.

The [official v1.5 model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)
currently specifies modified vLLM/Transformers builds. Its published container
is `ghcr.io/swiss-ai/vllm_apertus_1.5_release:latest-amd64` (also arm64).
Do not use the application's old Transformers pin to load v1.5. Provision the
server separately on appropriate NVIDIA GPU hardware, using the official
image and `vllm serve swiss-ai/Apertus-v1.5-8B`, with
`--chat-template-content-format string` and a context limit that fits the GPU.
The published image tag is mutable: freeze a tested digest before submission.
Apple Silicon Docker does not provide an NVIDIA CUDA device; an arm64 image
alone does not solve that. No image or large weights were downloaded here.
