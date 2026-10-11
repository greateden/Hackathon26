# Data and generated files

Only this file, `request.json` and `example_claims.json` are intended for Git.
The template limits submitted `data/` to 100 MB. The local directory contains
larger downloaded corpora and is not suitable for direct ZIP submission.

- `request.json`: current supplied-booklet application input; public PDF URL.
- `example_claims.json`: historical ten-claim smoke set, not a benchmark. Its
  known flaws remain documented in the historical report (§6).
- `booklets/`, `eval/`, `cache/`, `logs/`, result and ablation JSON files: local,
  ignored and preserved. The old 51 MB embedding cache is no longer submitted.
- `../docs/evidence/`: small reviewable evidence selected for submission.

The dataset can be fetched with `make eval-data`; historical PDFs/corpus with
`make fetch-booklets`. Neither is required by the sample application request.
Both commands download data; neither was run during repository cleanup.
External OCR checkouts live in `../repos/` and remain ignored.
Do not force-add model weights, private PDFs, credentials or generated caches.
