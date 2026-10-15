# Running the submission application

## Authoritative OST evaluation entrypoint (15 October integration)

Direct Docker execution reads mixed Task A/B UTF-8 JSONL. `make run` remains the
single-request development demo; it is not the batch evaluation interface.
Build on a networked machine; the pinned SentenceSwissBERT encoder is included
in the image. No Apertus weights are downloaded. Runtime model downloads are
disabled. Local PDF paths are resolved relative to `/data`; absolute paths,
`..` traversal, symlink escapes and URL inputs are rejected. Production output
must resolve beneath `/output`.

```sh
cd track_2a
docker build --platform linux/amd64 -t votelens:evaluation-20261015 .
mkdir -p output
# Make this dedicated output directory writable by the image's non-root app user.
chmod 777 output
docker run --rm --platform linux/amd64 \
  -e BASE_URL -e API_KEY \
  -v "$PWD/data:/data:ro" -v "$PWD/output:/output" \
  votelens:evaluation-20261015 --input /data/cases.jsonl --output /output/predictions.jsonl
```

For opt-in performance diagnostics, add `-e VOTELENS_PROFILE=1`. Diagnostics
go to stderr and include PDF extraction, passage/embedding, retrieval, API
request and per-case durations; the JSONL output is unchanged. CPU threading is
controlled by the standard `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and
`OPENBLAS_NUM_THREADS` variables, which may be passed to `docker run`.

The official smoke helper defaults to `linux/amd64`. For a native Apple
Silicon experiment, build and run a separate image:

```sh
docker build --platform linux/arm64 --target production -t votelens:arm64-test .
CSCS_SMOKE_IMAGE=votelens:arm64-test CSCS_SMOKE_PLATFORM=linux/arm64 \
  OMP_NUM_THREADS=8 VOTELENS_PROFILE=1 \
  ./run_cscs_mixed_smoke.sh data/booklets/example.pdf "EXACT VOTE TITLE" "CLAIM"
```

The independent embedding benchmark makes no CSCS requests and is not run
automatically:

```sh
cd track_2a
python3 src/benchmark_embedding.py --threads default,4,8
```

Export the organiser's endpoint and key privately before running; never put keys
in command arguments, source files or build arguments. `BASE_URL` and `API_KEY`
override `LLM_BASE_URL` and `LLM_API_KEY` in the actual client. Injected proxies
need only `/v1/chat/completions`, not `/v1/models` or `/tokenize`. The default
remains `swiss-ai/Apertus-v1.5-70B`; configured and returned model identities must
match an allowlisted Apertus v1.5 model. Provider token usage and completion
status remain mandatory; latency measures the completion HTTP request only.

Each input has `id`, `vote`, `claim: {text, language}` and exactly one of
`booklet: {path, language}` (A) or `reference: {text, language}` (B). Language is
optional; when supplied it is de/fr/it. No gold fields are used. For example:

```json
{"id":"B-editable","vote":"Proposal name","reference":{"text":"Der Bundesrat lehnt die Vorlage ab.","language":"de"},"claim":{"text":"Der Bundesrat unterstützt die Vorlage.","language":"de"}}
```

Use DE/FR/IT language codes in actual input. Edit the reference and claim independently. For a booklet
example, place the actual PDF at `data/booklets/example.pdf`, replace `reference`
with `"booklet":{"path":"booklets/example.pdf","language":"de"}`, and specify
its actual proposal name. These are editable input templates, not saved successes.

Task B receives the vote as context and accepts valid labels without citations;
any emitted citation must still resolve to supplied text. Task A retains proposal
identity and source-grounding gates. Pages start at 1. All nine source/claim
language combinations are structurally supported. The existing booklet-language
adapter is used for both source and query; this integration does not establish
cross-language quality. Up to eight extracted PDFs are cached in memory per batch,
keyed by path, language, size and modification time; nothing is persisted.

**Failure limitation:** valid cases produce official prediction rows. A failed
case produces `{"id":"...","label":null,"error":"classification_failed:..."}`,
then processing continues and the batch exits 1. This is explicit failure accounting,
not an official prediction or an invented Neutral. Malformed/duplicate input IDs
and startup failures abort before inference. A fully populated valid prediction
file cannot be guaranteed under model/gate failures. Organisers must confirm
failure handling; do not claim unconditional evaluation readiness.

Offline Docker contract check (mock completions; no CSCS calls):

```sh
fixture=$(mktemp -d "$HOME/votelens-contract.XXXXXX")
python3 tests/docker_evaluation_contract.py --prepare "$fixture/data"
mkdir "$fixture/output"
chmod 777 "$fixture/output"
docker run --rm --platform linux/amd64 --network none \
  -v "$fixture/data:/data:ro" -v "$fixture/output:/output" \
  -v "$PWD/tests/docker_evaluation_contract.py:/test/docker_evaluation_contract.py:ro" \
  --entrypoint python3 votelens:evaluation-20261015 /test/docker_evaluation_contract.py
```

The default production stage contains `src/` and the SentenceSwissBERT notice,
not `tests/` or gold-labelled fixtures. `make test-docker` builds the separate
`test` target and overrides its entrypoint for offline regression checks.

The integration does not publish an image. Publish an approved linux/amd64 image,
record its immutable registry digest and verify an unauthenticated pull before submission.

## Publishing to GitHub Container Registry (manual release)

**Recommended on Apple Silicon:** use the manual GitHub Actions workflow
[Publish VoteLens AMD64 to GHCR](https://github.com/greateden/Hackathon26/actions/workflows/publish-votelens-ghcr.yml) after reviewing the encoder licence.
It builds natively on a GitHub-hosted AMD64 runner, uses the repository's
`GITHUB_TOKEN` (no personal token to paste), and prints the immutable digest.
Open **Actions → Publish VoteLens AMD64 to GHCR → Run workflow**; the trigger is
manual only. Then switch the GHCR package to Public and test an anonymous pull.

Before publishing, complete the required human review of the bundled
SentenceSwissBERT CC BY-NC 4.0 model licence. Authenticate to GHCR using a
GitHub personal access token (classic) with `write:packages`, supplied privately
via standard input; never store the token in Git or a Dockerfile. From the
repository root, after checking the desired commit:

```sh
cd track_2a
# After securely setting GHCR_PAT, run:
printf '%s' "$GHCR_PAT" | docker login ghcr.io -u greateden --password-stdin
# Only run after approved token and licensing review:
docker buildx build --platform linux/amd64 --target production \
  -t ghcr.io/greateden/hackathon26:latest --push .
docker buildx imagetools inspect ghcr.io/greateden/hackathon26:latest
```

The GHCR package is **private by default**; in GitHub Packages, open the
published container package's settings and change visibility to **Public**.
A public repository alone does not make the package public. Verify a fresh
anonymous `docker pull` (e.g. from an empty temporary Docker config), and
record the immutable `ghcr.io/greateden/hackathon26@sha256:...` digest from the
registry. Supply the verified image reference in the organiser's submission
portal. Building on Apple Silicon may be slow due to AMD64 emulation.

Minimum qualifying Macro-F1 is A >= 0.60 and B >= 0.75; neither is demonstrated
for this integrated path. See the [team checklist](SUBMISSION_TEAM_REVIEW_20261015.md).
Earlier sections below describe development and historical validation.


Run from `track_2a/`. The repository-root Makefile forwards here.
The submission uses `src/booklet_app.py`; historical experiments use
`main.py` and `compose.yaml`.

## Existing external endpoint (default)

The selected default is CSCS official Apertus v1.5 70B. An operator must provision an Apertus v1.5 OpenAI-compatible endpoint; the
official template does not promise an endpoint, API key or GPU from the judges.
The application container does not need NVIDIA access. Export the standard variables
or put them in `.env`:

```text
LLM_NAME=swiss-ai/Apertus-v1.5-70B
LLM_BASE_URL=https://api.inference.cscs.ch/v1
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

Optional preflight cannot independently detect a server silently dropping
input. Its usage and completion checks are necessary but are not equivalent to
an independently reconstructed prompt-token count. Configure the context limit
to match the endpoint; use required preflight when available.

The committed Beginner request needs no PDF or encoder. The rebuilt image bundles
SentenceSwissBERT for Advanced retrieval; place a local PDF under `data/`. Native
Python development still needs a cached encoder or a first-use download. No
historical corpus or embedding cache is required.

## Managed server (optional)

Install GNU Make, Docker Compose and NVIDIA Container Toolkit on a compatible
NVIDIA host. The default official server image targets Linux amd64 and CUDA 13.
Minimum VRAM has not been measured. Apple Silicon Docker cannot run this GPU
service. Windows/WSL2, Linux and fresh-checkout inference remain unverified.

Accept the official checkpoint's access conditions and set `HF_TOKEN`. Edit
`data/request.json`, then run:

```text
LLM_NAME=swiss-ai/Apertus-v1.5-8B make run SUBMISSION_MODE=managed
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

For a fresh two-case check through the authoritative mixed-JSONL production
entrypoint, first build the image, then run the operator-only script with a
trusted local Federal Chancellery PDF, its exact proposal title and a claim:

```bash
docker build --platform linux/amd64 -t votelens:evaluation-20261015 .
./run_cscs_mixed_smoke.sh \
  /absolute/path/to/trusted-booklet.pdf \
  'Exact proposal title as printed in the booklet' \
  'Claim about that proposal'
```

The script reads `~/.config/hackapertus/cscs.env` without printing it, sends
exactly one Task A and one Task B request, prints a redacted Docker command,
exit codes, IDs/labels, citation pages and token/latency fields, and validates
the output schema. It records only predictions plus exit metadata under the
ignored `data/experiments/` tree. It makes paid remote calls and must be run by
an authorised user; it is a smoke check, not a benchmark.

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

The CLI uses the P0 `vote-aware-v1` candidate. Advanced retrieval encodes
`Vote: <vote>\nClaim: <original claim>` with the existing booklet-language
SwissBERT adapter and keeps dense Top-5 ranking. No hybrid or proposition
reranker is enabled. The judge receives the original claim separately and must
recognise the vote in a selected source passage; ambiguous, unrecognised or
unsupported identities fail. For a schema-consistent Neutral response with no
evidence citations, if Apertus returns null/unrecognised identity but the
complete requested vote title occurs in a selected source passage, the
application may recover only that exact source-grounded reference. Partial,
ambiguous, non-neutral and wrong-proposal matches still fail. Recognition and stakeholder
reasoning otherwise depend on Apertus. They have been measured only in the exposed 54-case paired development
evaluation documented in `technical_report.md`, not on an independent test set.

The model selects passage IDs instead of generating final quotations. The
application copies the selected source text, optionally using valid character
offsets, and records PDF hash, physical page and page-relative offsets in
diagnostics. Whitespace, punctuation and extraction artefacts are preserved.
Offsets refer to Poppler's stripped page text, not PDF byte positions. An
unrecognised ID, ambiguous source occurrence, invalid range or insufficient
non-neutral evidence fails without replacement. Source verification does not
establish semantic support. See [P0_CORRECTNESS.md](P0_CORRECTNESS.md) for the
frozen baseline and manual verification commands.

Result JSON goes to stdout; encoder progress goes to stderr. To save a JSON
file through `make run`, set `RESULT_FILE=/app/data/result.json` in `.env`.
Existing files are refused. `REQUEST_FILE` and `RESULT_FILE` are container
paths; the output directory must already exist and be writable by Docker's
non-root `app` user. Endpoint, token, parsing and input errors return non-zero.
The smoke runner additionally sets `DIAGNOSTICS_FILE` to a separate new file
for model, usage and citation checks; stdout and `RESULT_FILE` retain the exact
official JSON contract. Diagnostics include the supplied text and model reply.

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

## Release examples and credentials

The default endpoint/model are explicitly CSCS 70B; there is no automatic switching.
Compose accepts `LLM_API_KEY`, or falls back to `CSCS_INFERENCE_API_KEY`. The repository
does not automatically read private credential files. On the development machine:

```sh
set +x
set -a
. "$HOME/.config/hackapertus/cscs.env"
set +a
make run
# From either repository root or track_2a:
REQUEST_FILE=/app/data/examples/advanced-entailment.json make run
REQUEST_FILE=/app/data/examples/advanced-neutral.json make run
```

Judges need their own authorised CSCS key and network access, or an explicitly
configured allowlisted official 8B/70B endpoint. This is not self-contained.
Never display `env`, the credential file, or interpolated `docker compose config`
while recording. Advanced requests accept a supplied PDF URL or a path under mounted
`/app/data`; no code changes or historical evaluation corpus are required. First use
may download the PDF in this development workflow; the rebuilt Docker image bundles
SentenceSwissBERT. No Apertus weights are downloaded.
See `data/examples/README.md` for gold provenance and actual smoke outcomes.
