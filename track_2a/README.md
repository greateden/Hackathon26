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
You need GNU Make, Docker with Compose, network access for initial downloads,
and a separately provisioned Apertus v1.5 8B endpoint.

1. Copy `.env.example` to `.env` and set `LLM_BASE_URL`, `LLM_NAME` and, if
   required, `LLM_API_KEY`. Keep the API key out of Git.
2. Edit `data/request.json` to identify the booklet and claim.
3. Run `make run` from this directory. The repository-root Makefile also forwards here.

Docker builds the CPU application and runs `src/booklet_app.py`. It does not
start or download the LLM. The endpoint must expose `/v1/models`, `/tokenize`
and `/v1/chat/completions`. This dependency does **not** satisfy self-contained
execution. Missing configuration, an unreachable endpoint or an invalid reply
fails explicitly; there is no heuristic fallback.

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
| Submission Docker | `swiss-ai/Apertus-v1.5-8B`; external vLLM-compatible server; required token preflight | Application contract tested offline; real Docker inference pending |
| Native Apple Silicon development | `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`; MLX; optional token preflight | One genuine retrieved-evidence run; see saved evidence |
| Historical research | Apertus v1.1 4B MLX INT4, global retrieval, oracle diagnostics and lexical controls | Archived measurements; not current submission results |

Both current arms use temperature 0, seed 20261011 and a 512-token output
budget. The successful MLX run explicitly disabled thinking at server startup.
Its quantisation and serving behaviour differ from the submission target.

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
