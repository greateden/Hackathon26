# VoteLens: The Courage to Be Wrong

**OST evaluation integration, 15 October:** the authoritative entrypoint is now
`docker run IMAGE --input /data/cases.jsonl --output /output/predictions.jsonl`
with runtime `BASE_URL`/`API_KEY`, read-only `/data`, and writable `/output`.
Build for `linux/amd64`; SentenceSwissBERT is bundled at build time and runtime
model downloads are disabled. The default remains Apertus v1.5 70B.
See [exact commands and failure limitations](docs/RUNNING.md#authoritative-ost-evaluation-entrypoint-15-october-integration).
`make run` remains the development demo. Publication, official failure-row policy
and qualifying Macro-F1 remain release gates; this integration is not a readiness certificate.


**HackApertus Track 2A — OST: Multilingual Document-Grounded NLI over
Swiss Official Voting Booklets.**

Give the application either a reference passage and claim (Beginner), or a
voting booklet PDF, vote and claim (Advanced). It returns entailment, neutral
or contradiction with grounded evidence; Advanced evidence includes physical
PDF pages. Apertus judges the claim, while SentenceSwissBERT selects evidence
within the supplied booklet.

The P0 submission candidate is now `vote-aware-v1`: dense Top-5 retrieval uses
the specified vote and the unchanged claim. Apertus must identify the proposal
in the selected evidence and choose source passage IDs for citations. Unknown
or ambiguous votes fail explicitly. The original `dense-v1` experiment path
remains available to historical Python runners. Existing accuracy figures and
historical deployment smokes measure that original path. A later 54-case paired
development evaluation and one Advanced CSCS Docker smoke exercise the complete
candidate; neither is independent generalisation evidence. See the
[P0 implementation record](docs/P0_CORRECTNESS.md) for verification and limits.

A genuine local Apertus v1.5 8B MLX smoke run is recorded: label `0`
(entailment), a verified page-15 snippet, 1,007 input tokens and 71 output
tokens. This single development example is not an accuracy benchmark.
A separate Docker application smoke against CSCS Apertus v1.5 70B exited 0
with entailment, a verified page-19 citation and no lexical fallback. This
single example is also not an accuracy benchmark. Optional managed 8B startup
and cross-platform execution remain unverified.

## Run

This directory is the project root required by the
[official template](https://github.com/HackApertus/project-template/tree/main/track_2a).
You need GNU Make, Docker with Compose and a provisioned official Apertus v1.5
endpoint. Set `LLM_NAME`, `LLM_BASE_URL` and, when required, `LLM_API_KEY`;
default `make run` starts only the CPU application and requires no local NVIDIA
GPU. Endpoints without `/tokenize` are supported while response identity, token
usage and completion checks remain strict. Runtime portability remains
unverified. The committed Beginner request needs neither a PDF nor an encoder
download. Advanced requests need the specified local PDF; the rebuilt Docker
image bundles SentenceSwissBERT. Native Python needs a cached or downloadable encoder.

For the selected CSCS Apertus v1.5 70B default, set
`CSCS_INFERENCE_API_KEY` outside the repository, edit `data/request.json`, and
run `make run-cscs`. This uses the external Docker application and the existing
optional token-preflight contract because CSCS does not document `/tokenize`.
See [RUNNING.md](docs/RUNNING.md) for the exact checks and limitations.

1. Export the three `LLM_*` variables above or copy `.env.example` to `.env` and
   configure them. Keep credentials out of Git.
2. Edit `data/request.json` to identify the booklet and claim.
3. Run `make run` from this directory. The repository-root Makefile also forwards here.

For an optional self-managed server, `LLM_NAME=swiss-ai/Apertus-v1.5-8B make run SUBMISSION_MODE=managed` builds
the CPU application and starts the official v1.5 vLLM GPU service,
waits for readiness, then runs `src/booklet_app.py`. The model service downloads
uncached weights into a persistent Docker volume. Both services stop when the
application exits, and its exit status is propagated. No separately started
server or lexical fallback is used. **This managed deployment is configured but
has not passed a real Docker smoke test.** Apple Silicon Docker cannot run its
NVIDIA service; the prior native MLX smoke does not establish submission readiness.

[Running instructions](docs/RUNNING.md) cover environment variables, local
PDFs, result files, Windows limitations and the separate native Mac path.

## Input and output

The CLI accepts the two official request shapes. Beginner input classifies the
supplied reference directly:

```json
{
  "id": "case-0043",
  "reference": {"text": "Example reference passage"},
  "claim": {"text": "Example claim"}
}
```

Advanced input searches only the named booklet (paths are relative to
`data/request.json`):

```json
{
  "id": "case-0042",
  "booklet": {"path": "booklets/example_de.pdf"},
  "vote": "Example vote",
  "claim": {"text": "Example claim"}
}
```

Booklet language is detected as German, French or Italian; the claim may be in
any of those languages. No evaluation file or gold reference is read.

The CLI prints only the official response. Labels are `0` entailment, `1`
neutral and `2` contradiction. Non-neutral evidence must match the supplied
source; advanced evidence carries the physical PDF page. Beginner evidence has
`page: null` because the supplied reference has no PDF page. Metrics come from
endpoint usage and the measured completion latency. Invalid, ungrounded or
incomplete results exit non-zero instead of inventing fields.

```json
{
  "id": "case-0042",
  "label": 0,
  "label_name": "entailment",
  "evidence": [{"page": 7, "text": "Verbatim supporting passage"}],
  "metrics": {"input_tokens": 8431, "output_tokens": 112,
              "inference_time_ms": 1820}
}
```

## Model configurations

| Path | Model and configuration | Verification |
|---|---|---|
| Submission Docker | `swiss-ai/Apertus-v1.5-70B`; CSCS external endpoint by default; optional managed official vLLM server | External endpoints use strict response checks without requiring `/tokenize`; managed inference pending |
| CSCS external (default) | `swiss-ai/Apertus-v1.5-70B`; `https://api.inference.cscs.ch/v1`; optional token preflight | One booklet/retrieval Docker smoke passed on Apple Silicon; n=1 |
| Native Apple Silicon development | `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`; MLX; new paired runner requires exact token preflight | Historical n=1 smoke used optional preflight; new wrapper runtime pending |
| Historical research | Apertus v1.1 4B MLX INT4, global retrieval, oracle diagnostics and lexical controls | Archived measurements; not current submission results |

The managed and native arms use temperature 0, seed 20261011 and a 512-token
output budget. The CSCS optional path uses the standard OpenAI-compatible
fields, so it does not send the vLLM-specific thinking control or seed. The
successful MLX run explicitly disabled thinking at server startup. Its
quantisation and serving behaviour differ from the submission target.

## Paired experiment runner

From this directory, use the existing environment:

```bash
../.venv/bin/python src/experiment_runner.py preflight
```

Then manually start the cached MLX server in one terminal and run the prepared
experiment in another. [EXPERIMENTS.md](docs/EXPERIMENTS.md) gives the exact
commands, resumption rules and optional Docker smoke. The frozen nine-example
matrix compares full-booklet and retrieved evidence with 18 planned model
calls. Results are saved immediately under `data/experiments/v15-paired/`.
The later 81-example local run and 27-example CSCS prompt comparison are
documented in the technical report; both use exposed development data.

## Evaluation and repository map

- [Project status](docs/PROJECT_STATUS.md): requirements, verified work and remaining gaps.
- [Technical report](technical_report.md): concise submission report (6 pages) with retrieval, evidence-sensitivity and paired results.
- [Technical report PDF](docs/report/technical_report.pdf): 6-page A4 render; rebuild via `make pdf` from this directory.
- [Long-form technical reference](docs/TECHNICAL_REPORT_LONG.md): full methodology, per-case analysis and counterfactual design.
- [Interactive diagnostic](docs/experience/courage-to-be-wrong/README.md): failure-first presentation layer with data-verification guard (no model, no server, no network).
- [Evidence index](docs/evidence/README.md): saved runs and verification provenance.
- [Historical archive](docs/archive/README.md): original research measurements and integrity caveats.
- `src/`: application, paired evaluation and preserved research scripts.
- `tests/`: offline regression checks. Run from the repository root:
  - `make test` — portable unit tests (no model, no data, no network); data-dependent tests skip transparently.
  - `make test-integrity` — additionally runs experiment-integrity checks that require git-ignored raw records (`data/experiments/`, `data/eval/`). Skips cleanly in a clean checkout.
- [Data policy](data/README.md): small committed examples, ignored corpora and local results.

Report PDF is at `docs/report/technical_report.pdf` (6 pages, A4). Team metadata, demo and
external-material licensing still need human review. Report licence: CC-BY-4.0, following the
[technical-report template](https://github.com/HackApertus/project-template/blob/main/track_2a/technical_report.md).

Release validation and remaining approval conditions: [14 October release record](docs/RELEASE_CANDIDATE_20261014.md). Team-authored source: Apache-2.0; documentation: CC-BY-4.0; external materials retain their own terms ([notices](../THIRD_PARTY_NOTICES.md)).
