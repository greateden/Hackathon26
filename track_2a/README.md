# Swiss voting-booklet claim verification

**HackApertus Track 2A — OST: Multilingual Natural Language Inference over
Swiss Official Voting Booklets.**

Give the application a voting booklet PDF, a claim and their languages
(German, French or Italian). It returns entailment, neutral or contradiction,
with passages and physical PDF page citations. Apertus judges the claim;
SentenceSwissBERT selects evidence within the supplied booklet.

A genuine local Apertus v1.5 8B MLX smoke run is recorded: label `0`
(entailment), a verified page-15 snippet, 1,007 input tokens and 71 output
tokens. This single development example is not an accuracy benchmark.
The submission Docker path and self-contained model startup remain unverified.

## Run

This directory is the project root required by the
[official template](https://github.com/HackApertus/project-template/tree/main/track_2a).
You need GNU Make, Docker with Compose, NVIDIA Container Toolkit, a compatible
NVIDIA GPU with enough VRAM, network/disk capacity for initial downloads, and
Hugging Face access to the gated official v1.5 checkpoint. Alternatively, use a
provisioned official endpoint with `make run SUBMISSION_MODE=external`; that mode
starts only the CPU application and requires no local NVIDIA GPU. GPU memory
needs and runtime portability remain unverified.

1. Copy `.env.example` to `.env` and set `HF_TOKEN` after accepting the model's
   access conditions. Keep credentials out of Git; the internal endpoint is preconfigured.
2. Edit `data/request.json` to identify the booklet and claim.
3. Run `make run` from this directory. The repository-root Makefile also forwards here.

In default managed mode, Docker builds the CPU application, starts the official
v1.5 vLLM GPU service,
waits for readiness, then runs `src/booklet_app.py`. The model service downloads
uncached weights into a persistent Docker volume. Both services stop when the
application exits, and its exit status is propagated. No separately started
server or lexical fallback is used. **This managed deployment is configured but
has not passed a real Docker smoke test.** Apple Silicon Docker cannot run its
NVIDIA service; the prior native MLX smoke does not establish submission readiness.

[Running instructions](docs/RUNNING.md) cover environment variables, local
PDFs, result files, Windows limitations and the separate native Mac path.

## Input and output

Example request (place `my-booklet.pdf` in this directory's `data/`):

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

A public HTTPS PDF URL also works. The committed request uses one, so it needs
no private corpus. `full` selects Baseline A (all extracted pages); `retrieved`
selects Approach B (top-five passages from that booklet). No evaluation gold
reference is used to select evidence.

The output JSON includes `label_code` (`0` entailment, `1` neutral,
`2` contradiction), reasoning, passages, PDF hash, token usage and timings.
`citation_verified` means the generated snippet matches a supplied passage;
it does not prove the judgement is correct. Errors have a null label.
For example, this subset comes from the saved local development smoke:

```json
{
  "label": "entailment",
  "label_code": 0,
  "citation_verified": true,
  "usage": {"prompt_tokens": 1007, "completion_tokens": 71, "total_tokens": 1078}
}
```

## Model configurations

| Path | Model and configuration | Verification |
|---|---|---|
| Submission Docker | `swiss-ai/Apertus-v1.5-8B`; Managed official vLLM server or explicit external endpoint; required token preflight | Application contract tested offline; real Docker inference pending |
| Native Apple Silicon development | `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`; MLX; new paired runner requires exact token preflight | Historical n=1 smoke used optional preflight; new wrapper runtime pending |
| Historical research | Apertus v1.1 4B MLX INT4, global retrieval, oracle diagnostics and lexical controls | Archived measurements; not current submission results |

Both current arms use temperature 0, seed 20261011 and a 512-token output
budget. The successful MLX run explicitly disabled thinking at server startup.
Its quantisation and serving behaviour differ from the submission target.

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
Preflight and offline tests do not establish real model or Docker success.

## Evaluation and repository map

- [Project status](docs/PROJECT_STATUS.md): requirements, verified work and remaining gaps.
- [Technical report](technical_report.md): template-aligned draft; paired NLI results pending.
- [Evidence index](docs/evidence/README.md): saved runs and verification provenance.
- [Historical archive](docs/archive/README.md): original research measurements and integrity caveats.
- `src/`: application, paired evaluation and preserved research scripts.
- `tests/`: offline regression checks; `make test` runs them without inference.
- [Data policy](data/README.md): small committed examples, ignored corpora and local results.

No final report PDF or submission has been produced. Team metadata, demo and
code licensing still need review. Report licence: CC-BY-4.0, following the
[technical-report template](https://github.com/HackApertus/project-template/blob/main/track_2a/technical_report.md).
