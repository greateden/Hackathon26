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
    `data/results_*.json`.
  - `eval_retrieval.py`, `diag_embeddings.py`, `diag_claim_retrieval.py` —
    measurement/diagnostic scripts whose output backs the report. Keep them
    runnable; they are the reproduction path for documented findings.
  - `run.sh` — convenience wrapper for the MLX backend.
- `data/example_claims.json` — 10 smoke-test claims (flawed; see below).
- `data/logs/`, `data/results_*.json` — generated outputs, git-ignored.
- `repos/` — external upstream corpus checkouts (VotingBooklets,
  VotingBooklets-mono). External source material, not project code.

## Commands (from `src/`, no LLM download needed)

```bash
python3 test_pipeline.py                     # corpus + index + 3 retrieval probes
python3 main.py                              # full CLI, lexical judge
python3 eval_retrieval.py                    # retrieval eval (~12 s, model cached)
python3 eval_retrieval.py --mode same-lang   # encoder degeneracy control
python3 diag_embeddings.py
python3 diag_claim_retrieval.py
```

MLX judge runs (`LLM_BACKEND=mlx`, `./run.sh`) download LLM weights and are
expensive; they are not required for routine checks.

## Invariants and conventions

- NLI labels are the strings `entailment` / `contradiction` / `neutral`
  (`config.NLI_LABELS`). The challenge asks for numeric codes 0 =
  entailment, 1 = neutral, 2 = contradiction; the mapping has deliberately
  not been added yet — decide it explicitly, do not slip it in.
- No macro-F1 aggregation exists yet: per-item `expected` labels are logged
  but not scored. Adding it is future work, not an existing feature.
- Retrieval adapter configuration is *measured, not arbitrary*: queries are
  encoded with the `de_CH` adapter, passages with their own language
  adapter (see the comment in `Retriever.retrieve` and report §5.2 — the
  uniform-adapter alternative measured worse).
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

- Claim→evidence retrieval from English queries is the bottleneck: a
  decisive passage sits at rank 13/526 for the English query vs rank 1 for
  German (report §5.3). Next step per report §7A: normalise/translate the
  query language before embedding.
- `example_claims.json` is not a benchmark: n=10; claims #7 and #9
  reference topics absent from the indexed subset; the "army weapons"
  claim's gold label is wrong (defensibly `neutral`); all claims are
  English. Plan is ~50 claims with gold evidence spans (report §6).
- Only 3 booklets / 526 passages of 529 upstream files are indexed; full
  corpus behaviour is unmeasured.
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