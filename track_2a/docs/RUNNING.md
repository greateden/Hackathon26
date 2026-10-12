# Running the submission application

Run from `track_2a/`. The repository-root Makefile forwards here.
The submission uses `src/booklet_app.py`; historical experiments use
`main.py` and `compose.yaml`.

## Existing external endpoint (default)

The judges can provision an Apertus v1.5 OpenAI-compatible endpoint; the
application container does not need NVIDIA access. Export the standard variables
or put them in `.env`:

```text
LLM_NAME=swiss-ai/Apertus-v1.5-8B
LLM_BASE_URL=http://host.docker.internal:8000
LLM_API_KEY=
LLM_CONTEXT_TOKENS=32768
```

Then run `make run` from the repository root. Only
`compose.submission.yaml` is used. The default
`LLM_TOKEN_PREFLIGHT=optional` supports endpoints without `/tokenize`; a verdict
is accepted only when `/v1/models` lists the exact configured model, the response
model matches, token usage contains positive integer prompt and completion
counts, and `finish_reason=stop`. Set `LLM_TOKEN_PREFLIGHT=required` for servers
that expose `/tokenize` and require an exact prompt-token match. There is no
lexical fallback. Both base URLs ending in `/v1` and those without it are
normalised correctly.

The committed request downloads a public voting booklet, and retrieved mode
downloads SentenceSwissBERT on the first run into the `hf-cache` volume. For an
offline judge environment, place a PDF under `data/` and pre-populate the named
`hf-cache` volume; no historical corpus or embedding cache is required.

## Managed server (optional)

Install GNU Make, Docker Compose and NVIDIA Container Toolkit on a compatible
NVIDIA host. The default official server image targets Linux amd64 and CUDA 13.
Minimum VRAM has not been measured. Apple Silicon Docker cannot run this GPU
service. Windows/WSL2, Linux and fresh-checkout inference remain unverified.

Accept the official checkpoint's access conditions and set `HF_TOKEN`. Edit
`data/request.json`, then run:

```text
make run SUBMISSION_MODE=managed
```

This merges `compose.submission.yaml` (CPU application) and
`compose.managed.yaml` (official v1.5 vLLM server). Docker builds the application,
starts the model service and waits for readiness. Uncached weights are downloaded
into the `apertus-cache` volume; SentenceSwissBERT uses `hf-cache`. The app requires
`swiss-ai/Apertus-v1.5-8B`, checks `/v1/models`, counts the prompt with `/tokenize`
and makes one NLI request. There is no lexical or other-model fallback.

`LLM_CONTEXT_TOKENS` configures both services, including 512 output tokens.
`LLM_API_KEY` optionally authenticates the internal API; `HF_TOKEN` grants
model-download access. Neither belongs in Git. The model card requires a
modified vLLM build; the application's Transformers dependency serves the
encoder only. The image tag is mutable; `APERTUS_IMAGE` accepts a tested digest.
NVIDIA arm64 deployments can select the published arm64 image/platform but
remain untested.

Compose stops services when the app exits and propagates its exit code.
After interrupted startup, stop the managed services without deleting caches:

```text
docker compose -f compose.submission.yaml -f compose.managed.yaml down
```

The managed overlay replaces the endpoint with its internal `apertus` service
and enforces required `/tokenize` preflight. Container-to-endpoint networking
outside the previously recorded CSCS smoke remains to be tested on the target
host. The third-party MLX conversion is refused by the Docker submission path.

### CSCS Apertus v1.5 70B

The CSCS OpenAI-compatible endpoint is an opt-in external backend. It advertises
`swiss-ai/Apertus-v1.5-70B` but does not document `/tokenize`, so use the
existing optional preflight path. Keep the API key outside the repository:

```bash
export CSCS_INFERENCE_API_KEY='...'
make run-cscs
```

`run-cscs` sets `LLM_NAME=swiss-ai/Apertus-v1.5-70B`,
`LLM_BASE_URL=https://api.inference.cscs.ch/v1`, maps the key to
`LLM_API_KEY`, selects `LLM_TOKEN_PREFLIGHT=optional`, and runs external mode.
Both a base URL ending in `/v1` and one without it resolve to exactly
`/v1/models` and `/v1/chat/completions`; `/v1/v1/...` is not produced.
Edit `data/request.json` before running. This can send a paid remote inference
request. One full booklet/retrieval Docker smoke passed on Apple Silicon with
exit code 0, a verified page citation and no lexical fallback. It used one
example and therefore establishes application-path execution, not accuracy or
cross-platform portability. The default managed 8B service remains unverified.

## Input and output

`data/request.json` contains one official Beginner or Advanced object. Beginner:

```json
{
  "id": "case-0043",
  "reference": {"text": "Example reference passage"},
  "claim": {"text": "Example claim"}
}
```

Advanced:

```json
{
  "id": "case-0042",
  "booklet": {"path": "booklets/example_de.pdf"},
  "vote": "Example vote",
  "claim": {"text": "Example claim"}
}
```

Relative booklet paths resolve from the request file's directory, so the
example above names `data/booklets/example_de.pdf`. Image-only PDFs require
OCR, which is not implemented.

The booklet language is detected as `de`, `fr` or `it`; claims may independently
use any of those languages. Advanced mode retrieves up to five passages from
the specified PDF only. Beginner mode sends the supplied reference directly.
The output contains exactly `id`, integer `label`, `label_name`, grounded
`evidence`, and recorded token/latency `metrics`. Labels are 0 entailment, 1
neutral and 2 contradiction. Non-neutral output without grounded evidence
fails; neutral evidence is empty. Beginner evidence uses `page: null` because
no PDF page was supplied.

Result JSON goes to stdout; encoder progress goes to stderr. To save a JSON
file through `make run`, set `RESULT_FILE=/app/data/result.json` in `.env`.
Existing files are refused. `REQUEST_FILE` and `RESULT_FILE` are container
paths; the output directory must already exist and be writable by Docker's
non-root `app` user. Endpoint, token, parsing and input errors return non-zero.

## Native development and experiments

Use [EXPERIMENTS.md](EXPERIMENTS.md) for the cached-only preflight, manually
started MLX server, paired runner and separate Docker smoke. Native Python
does not read `.env`. The runner sets its own v1.5 model and required token
preflight; no native experiment verifies the official Docker deployment.

The historical n=1 local MLX smoke used optional token preflight with an
observational wrapper. Its saved prompt independently confirms 1,007 input
tokens for that example only. The new experiment server exposes exact token
preflight and loader metadata; its first real run is pending. Historical
`make serve-apertus` still defaults to v1.1 and must not be used for v1.5 work.

`make test` runs offline checks with the project-local `.venv`, falling back
to the preserved repository-root `.venv` and then `python3`. No model inference
is required. The existing native environment passes `pip check`; combining
the portable Transformers pin with current MLX requirements in a fresh native
environment remains unsupported. Docker's application dependencies are separate.
