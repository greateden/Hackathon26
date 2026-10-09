# AGENTS.md — working notes for coding agents

Code is the source of truth for implementation detail. This file records
what is *not* obvious from the code. Before touching retrieval or judgement
logic, read `REPORT_HACKAPERTUS_OST.md` §5 (retrieval measurements) and §8
(explicitly unverified claims), and §6 (problems with the smoke-test claim
set) before changing `data/example_claims.json`.

## Repository map

- `src/` — all pipeline code. Scripts are run *from* this directory (they
  add it to `sys.path`; scripts import `config` directly, not `src.config`).
  - `config.py` — single place for paths, model ids, retrieval parameters
    (`TOP_K`, `MIN_SIMILARITY`, `BATCH_SIZE`) and the label set.
  - `ingest.py` — OCR text → passage records `{id, year, lang, text,
    source_file}`. `python3 ingest.py` prints corpus stats.
  - `retriever.py` — SentenceSwissBERT mean-pooling + cosine retrieval;
    entry points `Retriever`, `build_retriever`.
  - `nli_judge.py` — judge backends (`lexical` / `mlx` / `ollama`) behind
    one `judge()` interface, plus `format_evidence` and
    `parse_nli_response`.
  - `main.py` — CLI entry point; writes `data/logs/run_*.log` and
    `data/results_*.json`. Retrieval stack is `RETRIEVAL_CONFIG` (env,
    default `legacy` = 526-passage ingest corpus; `v2`/`hybrid` load
    `data/booklets/corpus.json` instead — plumbing-verified only, no
    quality benchmark on the pipeline path).
  - `eval_nli.py` — official eval harness over
    `data/eval/mnli_swiss_v1.1.jsonl` (1,488 items, fetched by
    `fetch_eval_data.py`); accuracy + macro-F1 + confusion, pure Python.
    `--evidence oracle` feeds the gold reference passage (isolates the
    judgement step); `--evidence retrieve` runs the full pipeline over the
    indexed 1977/1985/2007 corpus, which does NOT contain the eval
    booklets — its numbers are plumbing checks, never accuracy.
  - `labels.py` — the official numeric code mapping (0 = entailment,
    1 = neutral, 2 = contradiction) in both directions. `test_judge.py`
    guards it and the judge parser.
  - `eval_retrieval.py`, `diag_embeddings.py`, `diag_claim_retrieval.py` —
    measurement/diagnostic scripts whose output backs the report. Keep them
    runnable; they are the reproduction path for documented findings.
  - `fetch_booklets.py` — booklet PDF corpus builder: discovers the unique
    PDFs via the eval set's `booklet_url` field, downloads them (verifies
    `%PDF` magic bytes), extracts text (`pdftotext`, PyMuPDF fallback) and
    chunks into `data/booklets/corpus.json` (`{id, doc_id, year, lang,
    text}`). Resumable. `make fetch-booklets`.
  - `sampling.py` — seeded class-stratified round-robin sampler
    (`balanced_sample`, `label_counts`) used by `eval_e2e.py`.
  - `eval_e2e.py` — evidence-based retrieval eval over the booklet PDF
    corpus. Gold passage = where the `reference_string` appears verbatim
    (probe) or with ≥50% 40-char shingle coverage; unlocatable items are
    excluded from denominators, never guessed. Configs: `lexical` (BM25),
    `emb_v1` (de_CH query adapter), `emb_v2` (evidence-language adapter +
    optional Ollama query translation), and research stacks `hyb_rrf`,
    `two_stage_lex`, `two_stage` (implemented in `hybrid_retrieval.py`;
    routing knobs `--doc-top-n`/`--cand`/`--per-doc-cap`). Full-corpus
    search for the global configs; two-stage routes booklets first.
  - `hybrid_retrieval.py` — hybrid/two-stage stacks + per-config index
    caches under `data/booklets/`. Measured WORSE than `emb_v2` on the
    full benchmark (report §5.4); research-only, not a promotion path.
  - `diag_two_stage.py` — splits two-stage misses into empty-result /
    wrong-booklet / right-booklet-missed-passage (output behind §5.4/3).
  - `run.sh` — convenience wrapper for the MLX backend.
- `data/example_claims.json` — 10 smoke-test claims (flawed; see below).
- `data/logs/`, `data/results_*.json` — generated outputs, git-ignored.
- `repos/` — external upstream corpus checkouts (VotingBooklets,
  VotingBooklets-mono). External source material, not project code.

## Commands (from repo root)

`make help` lists the canonical entry points. `make test` must stay
runnable offline; `make eval-apertus-*` uses `.venv/bin/python` when
present (that venv carries mlx-lm 0.32, the only setup that can load the
Apertus architecture; it is git-ignored and rebuildable:
`python3.12 -m venv .venv && .venv/bin/pip install "mlx-lm==0.32.0"`).

## Commands (from `src/`, no LLM download needed)

```bash
python3 test_judge.py                        # offline unit checks (labels/parse)
python3 test_pipeline.py                     # corpus + index + 3 retrieval probes
python3 main.py                              # full CLI, lexical judge
python3 fetch_eval_data.py                   # download official eval set (~1 MB)
python3 eval_nli.py --split dev              # 60-item dev eval, lexical judge
python3 eval_retrieval.py                    # retrieval eval (~12 s, model cached)
python3 eval_retrieval.py --mode same-lang   # encoder degeneracy control
python3 diag_embeddings.py
python3 diag_claim_retrieval.py
python3 fetch_booklets.py                        # 60-booklet PDF corpus (needs internet, resumable)
python3 eval_e2e.py --configs lexical            # full-set e2e eval without any model
python3 eval_e2e.py                              # default 3 configs (emb_v1,emb_v2,lexical)
python3 eval_e2e.py --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage  # all six (~40 s cached, ~4 min cold)
python3 diag_two_stage.py                        # booklet-routing failure breakdown
```

MLX judge runs (`LLM_BACKEND=mlx`, `./run.sh` or `make eval-apertus-*`)
download LLM weights and are expensive; they are not required for routine
checks.

## Invariants and conventions

- Label codes are DECIDED (2026-10-09): the official mapping 0 =
  entailment, 1 = neutral, 2 = contradiction lives in `src/labels.py`
  (`CODE_TO_LABEL` / `label_to_code`); internal labels remain the strings
  `entailment` / `contradiction` / `neutral` (`config.NLI_LABELS`).
  Convert at the boundary with official files only; never hardcode a code
  elsewhere. Do not change the mapping without a report entry.
- Macro-F1 / accuracy / confusion matrix live in `eval_nli.summarise`,
  pure Python — the no-SciPy/scikit-learn invariant applies to eval code
  too. Unparseable or failed judge output is recorded as an error
  (`label: None`), never defaulted to neutral: `parse_nli_response` has no
  keyword-search fallback over free text. Reintroducing one turns accuracy
  into fiction.
- `eval-apertus-*` Make targets pin `MLX_MODEL=swiss-ai/Apertus-...`
  explicitly. Never run an "Apertus eval" under a silently different model
  id, and never quote lexical-judge or oracle-mode numbers as model
  quality.
- Retrieval adapter configuration is *measured, not arbitrary*: queries are
  encoded with the `de_CH` adapter, passages with their own language
  adapter (see the comment in `Retriever.retrieve` and report §5.2 — the
  uniform-adapter alternative measured worse). `eval_e2e.py`'s `emb_v2`
  config instead encodes each *query* with its evidence-language adapter
  (optionally translating first) — the full-set benchmark confirms it
  (R@5 0.212 vs 0.089 de_CH-only, report §5.4). Do not unify the two
  adapter paths without a rerun.
- `eval_e2e.py` integrity rules: `reference_string` and `booklet_url` are
  gold-labelling material ONLY — never query text, never a retrieval
  filter. Retrieval searches the whole corpus and must route to the right
  booklet itself; "helping" it by pre-filtering booklets or languages
  changes the task being measured. If Ollama is down, `--translate`
  degrades to *untranslated* queries and the report says so — never fake
  a translated run, and never quote degraded numbers as translated ones.
- Retrieval-stack ranking is MEASURED (report §5.4, six configs, full
  1,470-item run, `data/eval_results_full_benchmark.json`): global dense
  with evidence-language adapters beats BM25, beats hybrid RRF, beats
  both two-stage routings. Booklet routing caps top-1 booklet accuracy
  at ~17% because booklets are per-language editions of one vote day —
  do not "fix" language-duplicate noise by adding booklet filters or
  routing without a rerun and a report entry. `RETRIEVAL_CONFIG=v2` in
  the CLI is plumbing-verified only; keep `legacy` as the default until
  the pipeline path itself is benchmarked.
- v1.5 compliance check (2026-10-09): `challenge_spec.md` requires local
  open-source models (Apertus, SwissBERT) but mandates no version; HF has
  no MLX/GGUF conversion of Apertus v1.5 (v1.1 conversions only), and
  mlx-lm 0.32 is the only working loader here. Pinning
  v1.1-4B-Instruct-MLX-INT4 is compliant; a v1.5 switch needs a
  conversion path first — do not claim v1.5 support without one.
- `retriever.cosine_sim_matrix()` is single-query only and returns shape
  `(N,)`. Batch evaluation must use its own matmul (`eval_retrieval.batched_sims`);
  feeding it batches was a real bug (report §5.1).
- No SciPy/scikit-learn imports: a broken SciPy binary on the dev machine
  broke runs, so the retrieval path must stay importable without them.
- `LexicalJudge` is a documented baseline (4/10 on the smoke-test set), not
  dead code. Do not "fix" its heuristics or treat its output as NLI
  accuracy.
- Keep changes to retrieval semantics, label mapping, evaluation logic, and
  model settings out of unrelated refactors; record any intentional change
  in the report with a rerun to back it.

## Known limitations and unfinished work (do not present as done)

- The §5.3 cross-language bottleneck was largely a wrong-adapter
  artefact: with evidence-language adapters, cross-language R@5 reaches
  0.200 vs same-language 0.235 (report §5.4, full-set). English claims
  (a minority of the eval set) still have no adapter, and the §7A
  translate-before-embedding path remains untested.
- `example_claims.json` is not a benchmark: n=10; claims #7 and #9
  reference topics absent from the indexed subset; the "army weapons"
  claim's gold label is wrong (defensibly `neutral`); all claims are
  English. The measurement path is now `eval_nli.py` over the official
  1,488-item set; keep `example_claims.json` for smoke tests only.
- `eval_nli.py --evidence retrieve` still runs over the legacy
  526-passage CLI corpus, so its numbers remain plumbing checks
  (`data/eval/` is git-ignored; regenerate with `fetch_eval_data.py`).
  The first Apertus run (3 dev items, 2026-10-09, mlx-lm 0.32) loaded
  the model and parsed 3/3 verdicts — plumbing evidence, NOT a quality
  result; no full-split run has been recorded yet.
- The 60-booklet PDF corpus (`make fetch-booklets`, git-ignored
  `data/booklets/`) covers every booklet the eval set cites: 16,618
  passages; 1,470/1,488 (98.8%) gold evidence strings locate inside it.
  The 18 that do not are mostly FR/IT reference strings that match
  neither verbatim nor by shingle coverage; the 2 spot-checked are not
  verbatim booklet text at all (heading + stance-marker paraphrases),
  so probably labelling artefacts rather than extraction gaps —
  unresolved. `eval_e2e.py` over this corpus is the retrieval
  measurement path now; `main.py` defaults to the legacy 526-passage
  index unless `RETRIEVAL_CONFIG=v2|hybrid` (booklet modes verified for
  plumbing only).
- Full benchmark recorded 2026-10-09 (single runs, no variance control;
  `data/eval_results_full_benchmark.json`, 1,470 items): R@5 — emb_v2
  0.212 > hyb_rrf 0.132 > emb_v1 0.089 > two_stage 0.076 > BM25 0.056 >
  two_stage_lex 0.046. Numbers are lower bounds: substring gold scores
  semantically correct non-annotated passages as misses (§5.4 finding 4).
- `top_k = 5` burns slots on parallel language duplicates of the same
  passage (report §7B).
- The `ollama` backend has never executed (needs Ollama running; `requests`
  is in requirements.txt).
- `run.sh` MEMORY_CHECK uses a percentage threshold that is miscalibrated
  for large-RAM machines (report §4.1); it is opt-in (`MEMORY_CHECK=1`).
- All reported numbers come from one machine (MPS, float32, single runs);
  no variance or seed control.

## Do not modify casually

- `repos/` — upstream data, licences and attribution. Regenerable only via
  the clone commands in `README.md`; treat as read-only.
- `data/example_claims.json` — its flaws are deliberately documented in
  report §6; change it only with a stated reason.
- `REPORT_HACKAPERTUS_OST.md` numbers — only change by rerunning the
  relevant script and updating both number and provenance. Never "improve"
  a figure by hand, and do not present planned functionality as
  implemented.