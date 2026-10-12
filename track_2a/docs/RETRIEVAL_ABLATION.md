# Opt-in multilingual retrieval ablation

This experiment is separate from the submission application. It does not alter
`make run`, `booklet_app.py`, Docker defaults, prompts, parsing or production
retrieval. Its three arms differ only in retrieval/evidence selection:

- **A — dense baseline:** the existing specified-booklet SwissBERT ranking,
  unchanged, with five 900-character passages.
- **B — hybrid RRF:** Arm A plus symmetric, dependency-free BM25, fused with
  Reciprocal Rank Fusion (`k=60`), still within the supplied booklet.
- **C — hybrid plus proposition reranking:** Arm B candidates reranked with
  explicit multilingual cues for the supplied proposal title, government or
  committee attribution, entities, quantities, negation, conditions and
  exceptions. A small greedy coverage term favours complementary passages.

The reranker is label-agnostic. Diagnostic flags never discard evidence,
change a prediction to neutral or override Apertus.

## Frozen comparison

The plan is `docs/evidence/retrieval_ablation_plan_20261012.json`: 81 new rows,
three per language-pair × label cell, covering all nine DE/FR/IT pairs and 60
booklets. It excludes the exposed grouped 81, all 19 Oracle cases, the
historical 60-row development split and identifiable pilot rows, including all
exact normalised claim/reference content components that touch those cases.

There are 81 distinct exact booklet-plus-vote-title groups and at most two rows
per booklet. This reduces leakage but does not create an independent benchmark:
the source dataset has informed prior retrieval work, and no reliable
multilingual proposal identifier proves that translated vote titles are
different topics.

Gold references are used only after retrieval for offline measurement. They are
not indexed, queried, reranking features or prompt content.

## Offline verification

From `track_2a/`:

```bash
../.venv/bin/python src/retrieval_ablation.py preflight \
  --out data/experiments/retrieval-ablation-preflight

../.venv/bin/python src/retrieval_ablation.py dry-run \
  --out data/experiments/retrieval-ablation-dry-run
```

`preflight` checks cached inputs and hashes without encoder inference. `dry-run`
executes cached SwissBERT/BM25 retrieval and writes all output schemas with an
empty `predictions.jsonl`; it makes zero Apertus/API calls. The retrieval audit
separates full-reference, exact-probe and approximate-shingle matching, then
distinguishes references absent from the extracted booklet, initial candidate
failures and Top-5 ranking failures.

## Live paired run (manual only)

Start the already documented pinned local server in one terminal:

```bash
../.venv/bin/python src/serve_experiments.py --context 81920
```

In another terminal, run the frozen 243-call comparison:

```bash
../.venv/bin/python src/retrieval_ablation.py run \
  --context 81920 --retries 0 \
  --out data/experiments/retrieval-ablation-v1
```

Resume safely after interruption:

```bash
../.venv/bin/python src/retrieval_ablation.py run \
  --context 81920 --retries 0 --resume \
  --out data/experiments/retrieval-ablation-v1
```

Retry recorded failures explicitly (maximum two retries is enforced):

```bash
../.venv/bin/python src/retrieval_ablation.py run \
  --context 81920 --retries 1 --resume --retry-failed \
  --out data/experiments/retrieval-ablation-v1
```

Stop the server manually after the experiment. Do not tune reranker weights or
plan membership after inspecting these results.

## Outputs to return for review

Send these files from `data/experiments/retrieval-ablation-v1/`:

- `manifest.json`
- `predictions.jsonl`
- `summary.json`
- `paired_comparison.csv`
- `error_analysis.md`
- `retrieval_audit.json`
- `events.jsonl` if the run was interrupted or retried

`summary.json` reports accuracy, macro-F1, language-pair slices, nested token
usage, latency, citation verification, paired wins/losses, an exact sign test
and a 95% Wilson interval over discordant pairs. These outputs do not establish
an accuracy improvement until the live run is complete.

## Deliberately unsupported

The PDF extraction exposes page text but no reliable section or speaker field.
Arm C therefore detects explicit actor phrases in source text; it does not
invent section labels. It uses the supplied vote title as an optional soft
feature, never an inferred official ID or hard filter. Named-entity matching is
conservative and mainly helps same-script exact names; no additional LLM or
translation call is made.
