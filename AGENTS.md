> **Submission cleanup, 11 October 2026:** the project root is now `track_2a/`.
> All project-relative paths and commands below refer to that directory.
> Root `make` forwards there. The existing repository-root `.venv` is preserved
> and is a fallback for native Make targets. Historical reports and requirements
> are in `track_2a/docs/archive/`; their dated claims do not override current
> `track_2a/docs/PROJECT_STATUS.md`. Genuine local v1.5 MLX inference is now
> evidenced in `track_2a/docs/evidence/v15_local_smoke/`; submission Docker,
> self-contained model startup and cross-platform execution remain unverified.

# AGENTS.md — working notes for coding agents

> **11 October 2026 submission override:** `make run` now uses
> `compose.submission.yaml` and `src/booklet_app.py`, requiring a configured
> `swiss-ai/Apertus-v1.5-8B` endpoint. It accepts a specified booklet and claim.
> `src/main.py`, its `legacy` default, and global-search experiments remain
> historical research paths. Their no-booklet-filter rule applies to those
> experiments only. The supplied booklet and its language are valid application
> inputs. Do not describe v1.1 as satisfying the current v1.5 acceptance target.
> See `docs/PROJECT_STATUS.md`, `docs/RUNNING.md`, and `technical_report.md`.
> No real v1.5 run, Windows execution or new Docker execution is verified yet.
>
> **Mac-only development path (added 2026-10-11, unverified):** `booklet_app.py`
> can also address a local `mlx_lm.server` serving
> `m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`. That endpoint has no `/tokenize`
> and advertises models by Hugging Face repo id, hence the two new knobs
> `LLM_TOKEN_PREFLIGHT` (default `required` = old behaviour) and a `LLM_NAME`
> that may name another Apertus v1.5 build. Both must stay off the Docker
> submission path, and the served id must still pass the `/v1/models` check.
> See `docs/RUNNING.md` ("Local Apple Silicon development endpoint").


Code is the source of truth for implementation detail. This file records
what is *not* obvious from the code. Before touching retrieval or judgement
logic, read `docs/archive/REPORT_HACKAPERTUS_OST.md` §5 (retrieval measurements) and §8
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
  - `nli_judge.py` — judge backends (`lexical` / `mlx` / `ollama` / `openai`)
    behind one `judge()` interface, plus `format_evidence` and
    `parse_nli_response`. `openai` talks to an OpenAI-compatible HTTP
    endpoint (`OPENAI_BASE_URL`), checks `/v1/models` at startup and fails
    hard if the endpoint or model id is missing — no lexical fallback.
    Also holds the `PROMPT_CONFIGS` registry (`baseline`/`t0`/`strict`/
    `select` plus the single-factor factorial arms `fill_only`/`window_only`,
    resolved by `get_prompt_config`, rendered via `build_chat`): system/user
    prompt text, temperature, max tokens and evidence style (`drop`/`fill`)
    all come from the selected config. `baseline` is deliberately
    byte-identical to the pre-ablation default; `test_judge.py` guards that,
    plus the factorial render equivalences (identical rendered (system, user)
    messages ⇒ identical model inputs; checked per dev item by
    `diag_evidence_ablation.py`, see report §4.4).
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
    `--evidence retrieve-v2` runs the production booklet-corpus stack end
    to end (`main.Pipeline`); empty evidence, retrieval failures and
    unparseable replies are recorded as errors (`pred=None`), never
    guessed.
  - `labels.py` — the official numeric code mapping (0 = entailment,
    1 = neutral, 2 = contradiction) in both directions. `test_judge.py`
    guards it and the judge parser.
  - `eval_retrieval.py`, `diag_embeddings.py`, `diag_claim_retrieval.py` —
    measurement/diagnostic scripts whose output backs the report. Keep them
    runnable; they are the reproduction path for documented findings.
  - `diag_eval_errors.py` — offline error analysis over recorded
    `eval_results_*.json` (per-class confusion, oracle/retrieve flips,
    truncation correlates). No model needed.
  - `diag_evidence_ablation.py` — offline analysis of the evidence-processing
    factorial: verifies per dev item that the twin cells render byte-identical
    prompts (retrieve mode never exercises the window; oracle evidence is one
    sub-cap chunk, so style is inert), then classifies recorded oracle flips
    by what the window did to the evidence. Needs the eval set and a
    `data/ablation_*.json` + its per-run files. No model needed; exits
    non-zero if an equivalence premise breaks.
  - `ablation_dev.py` — prompt-config ablation runner: spawns `eval_nli.py`
    per (config × evidence) combo on the fixed dev split, one result JSON
    per run, prints the comparison table + T=0 determinism check. Refuses
    to start without a live endpoint (`--dry-run` plans offline); never
    quote its lexical `ablation-smoke` numbers as model quality. First full
    dev run completed 2026-10-10 (8 paired runs, real Apertus endpoint via
    `mlx_lm.server`, report §4.3).
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
- `tests/` — permanent offline regression checks over the evaluation path
  (`test_project_contract.py`: judge/pipeline contract, the lexical-protocol
  guards, recorded-benchmark provenance). Run from the repo root:
  `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'`
  (used by `make test` and `make test-docker`). One-off review or scoring
  experiments do not belong in `src/` or `tests/` — give them a `tmp/` path
  outside the tracked tree.
- `Dockerfile`, `compose.yaml`, `.dockerignore` (root) — portable
  container runtime; see "Docker runtime" below.
- `requirements.txt` (root, pinned, portable/CPU) and
  `requirements-macos-mlx.txt` (Apple Silicon MLX extras, never installed
  in the container) replace the old unpinned `src/requirements.txt`.
- `data/example_claims.json` — 10 smoke-test claims (flawed; see below).
- `data/logs/`, `data/results_*.json` — generated outputs, git-ignored.
- `repos/` — external upstream corpus checkouts (VotingBooklets,
  VotingBooklets-mono). External source material, not project code.

## Commands (from repo root)

`make help` lists the canonical entry points. `make test` must stay
runnable offline; `make eval-apertus-*` uses `.venv/bin/python` when
present (that venv carries mlx-lm 0.32, the only setup that can load the
Apertus architecture; it is git-ignored and rebuildable:
`python3.12 -m venv .venv && .venv/bin/pip install "mlx-lm==0.32.0" requests`
— `requests` is needed by the `openai`/`ollama` backends). The Docker
entry points are `make smoke`, `make test-docker`,
`make test-docker-pipeline`, `make eval-lex-docker` (lexical baseline) and
`make run`, `make eval-apertus-docker`,
`make eval-apertus-oracle-docker` (real model: they call a host inference
endpoint — start `make serve-apertus` first and stop it afterwards; it
keeps several GB resident). Endpoint-backed Docker targets fail if the
endpoint is down — no silent lexical fallback. See "Docker runtime".

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
python3 ablation_dev.py --dry-run                # ablation planner, offline
python3 diag_evidence_ablation.py                # factorial equivalence + oracle-flip analysis (offline; needs the eval set + data/ablation_*.json)
python3 test_judge.py                            # includes prompt-config registry, select_window + factorial render-equivalence checks
```

MLX judge runs (`LLM_BACKEND=mlx`, `./run.sh`, `make serve-apertus` or
`make eval-apertus-*`) download LLM weights and keep several GB resident;
they are not required for routine checks, and the server should be stopped
when idle. Never quote their output without recording the exact model id.

## Docker runtime (added 2026-10-09)

Portable, reproducible path for non-macOS users and judges. Entry points
`make smoke`, `make run`, `make test-docker`,
`make test-docker-pipeline`, `make eval-lex-docker` and the
`make eval-apertus-*-docker` targets (from the repo root, via
`compose.yaml`); native paths (`make run-native`, `make test`,
`make eval-*`) are unchanged and remain the only place Apple Silicon MLX
runs.

- `Dockerfile` (root) — python:3.11-slim + CPU PyTorch from
  `requirements.txt` (pinned; platform markers keep x86-64 and aarch64
  CPU wheels small). No MLX, no model weights, no corpus in the image.
  Runs as non-root user `app`; `/app` and `/home/app` are owned by it
  (needed: `py_compile` writes `__pycache__` into `/app/src`).
- Dependency split: `requirements.txt` (portable) vs
  `requirements-macos-mlx.txt` (Apple Silicon only). The old
  `src/requirements.txt` (unpinned, mixed MLX) was removed; do not
  reintroduce a third dependency file. Changing a pin = rebuild + rerun
  the container checks.
- Mounts (compose): `./repos` read-only (legacy OCR corpus), `./data`
  read-write (booklet corpus, eval set, embedding caches, logs, results
  — host-visible), and named volume `hackapertus_hf-cache` at
  `/home/app/.cache/huggingface` (= `HF_HOME`). Keep model downloads on
  the volume, out of the image and out of the repo tree. Note:
  `retriever.load_tokenizer_compat` globs `~/.cache/huggingface/hub`,
  so the home-cache layout and `HF_HOME` must stay the same path — they
  are intentionally identical for the tokenizer.json fallback to work.
- Model endpoints (hard rule): inside a container `LLM_BACKEND` is
  `lexical` (default; smoke-test baseline only), `ollama` or `openai`,
  each pointing at an external server (`OLLAMA_BASE_URL` /
  `OPENAI_BASE_URL`, default `http://host.docker.internal:8080` via
  `extra_hosts: host-gateway` — container→host networking is verified,
  not assumed). The `openai` backend is the supported real-model path: it
  checks `/v1/models` and fails hard when the endpoint is unreachable or
  the served model id does not match `LLM_MODEL`.
  `LLM_BACKEND=mlx` inside the container fails loudly (mlx_lm is not
  installed) — never let anything fall back to lexical, and never quote
  lexical container numbers as model quality. Failed or unparseable
  endpoint replies are recorded as errors (`label: None`), per the
  existing invariant.
- Offline use: pre-populate the cache volume, or bind-mount a host
  `~/.cache/huggingface` over it. `RETRIEVAL_CONFIG=legacy` remains the
  default in the image; `v2`/`hybrid` in containers are plumbing-checked
  only, same caveat as native.
- Verified 2026-10-09 on Apple Silicon via colima (linux/aarch64, Docker
  29.5): image build; `make test-docker` (all offline checks); a full
  `make run` with the lexical judge; and ollama-backend plumbing against a
  MOCK Ollama-compatible server on the host. **2026-10-10: re-verified
  against a REAL endpoint** — `mlx_lm.server` serving
  `swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4` on host loopback, reached
  from the container as `host.docker.internal:8080`: two 60-item dev runs
  (retrieve-v2 + oracle, 120 calls, 0 endpoint/parse errors; report §4.2),
  an endpoint-down run (exits non-zero, no lexical fallback), and
  `requests` present in the image. UNVERIFIED: Linux x86-64 hosts, Docker
  Desktop, and `v2`/`hybrid` quality on the `main.py` pipeline path (the
  §4.2 retrieve-v2 run is the eval harness, not the CLI default). Do not
  mark those as working without a rerun.
- Host quirks found the hard way (not repo bugs): stale
  `~/.docker/cli-plugins/docker-compose` symlinks pointing at a deleted
  Docker.app, and `credsStore: "desktop"` in `~/.docker/config.json`
  with the credential helper missing, break `docker compose build`
  ("error listing credentials" / "unknown command: compose"). Fix:
  `brew install docker-compose` + relink the plugin, and clear
  `credsStore` in that file.

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
- Prompt/judgement ablations (2026-10-10): `PROMPT_CONFIG` (env, `config.py`)
  or `--prompt-config` (`eval_nli.py`/`main.py`) selects a `PROMPT_CONFIGS`
  entry. `baseline` must stay behaviourally identical to the pre-ablation
  default (guards in `test_judge.py`); the ablation arms (`t0`, `strict`,
  `select`, and the later factorial arms `fill_only`/`window_only`) each
  change ONE factor and are compared against a same-session paired `t0` run,
  never against the older T=0.1 dev runs. Run procedure: unload other
  memory-heavy apps (MTPLX) BEFORE starting `make serve-apertus`, stop the
  server right after, and never auto-kill server processes from scripts.
  First real-model run exists (2026-10-10, report §4.3): `strict` is REJECTED
  — predictions collapsed to `neutral` (54–56/60) and all three unparseable
  responses came from that arm. `select` is kept as an EXPERIMENTAL
  candidate, not promoted. Its two factors were SINCE decoupled offline
  (2026-10-10, report §4.4): `fill_only`/`window_only` each isolate one, and
  per-item render comparison shows every 2×2 cell is byte-identical to an
  already-recorded run — retrieve mode never exercises the window
  (`fill_only` ≡ `select`, `window_only` ≡ `t0`), and oracle evidence is one
  sub-cap chunk so style is inert (`fill_only` ≡ `t0`, `window_only` ≡
  `select`). Do not rerun an equivalent cell and call it new evidence:
  identical inputs at T=0 re-sample decoding identity, not configuration —
  `diag_evidence_ablation.py` checks the equivalences offline and
  `test_judge.py` guards them. Production default remains `baseline`, and the
  reserved 1,428-item eval split is not a tuning set.
- Retrieval-stack ranking is MEASURED (report §5.4, six configs, full
  1,470-item run, `data/eval_results_full_benchmark.json`): global dense
  with evidence-language adapters beats BM25, beats hybrid RRF, beats
  both two-stage routings. Booklet routing caps top-1 booklet accuracy
  at ~17% because booklets are per-language editions of one vote day —
  do not "fix" language-duplicate noise by adding booklet filters or
  routing without a rerun and a report entry. `RETRIEVAL_CONFIG=v2` in
  the CLI is plumbing-verified only; keep `legacy` as the default until
  the pipeline path itself is benchmarked.
- v1.5 compliance check (2026-10-09): `docs/archive/challenge_spec.md` requires local
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
  Apertus dev-split runs are recorded now (2026-10-10): two T=0.1 single
  runs (retrieve-v2 0.483 acc / 0.466 F1, oracle 0.433 / 0.393, report
  §4.2) and an 8-run paired T=0 prompt ablation (report §4.3; best arm
  select/retrieve-v2 0.483 / 0.467, paired control t0 0.450 / 0.436 —
  single runs per arm except the t0 controls, so differences smaller than
  ~2 items are not yet separable from run identity). The 2×2 evidence
  factorial (fill style vs window selection) has since been decoupled
  OFFLINE (report §4.4): all four cells are byte-identical twins of recorded
  runs, so no new inference is owed to identify the factors; only an
  optional paired probe would re-check end-to-end determinism, and no
  such probe has been run. The 1,428-item
  held-out eval split has not run with any model.
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
- Real-model traffic has only been measured through the `openai` backend
  (report §4.2); the `ollama` backend has run only against a mock server.
- `run.sh` MEMORY_CHECK uses a percentage threshold that is miscalibrated
  for large-RAM machines (report §4.1); it is opt-in (`MEMORY_CHECK=1`).
- All reported numbers come from one machine (MPS, float32, single runs);
  no variance or seed control.

## Final-summary convention (ChatGPT Handoff)

Every final task summary ends with a compact **ChatGPT Handoff** section for
an external reviewer who will analyse the results and prepare the next
implementation prompt. Sections: Current state (what works; the production
default) / Changes (implementation + affected files) / Evidence (exact
measurements, sample sizes, test outcomes, artefact paths) / Prediction
changes (which items flipped, their gold labels, improved or worsened) /
Uncertainties (untested, confounded, possibly wrong) / Next experiment (one
specific experiment + expected information gain) / Execution status (model
servers running or not, manual commands needed). Keep measured facts,
interpretations and hypotheses clearly separated. British English.

## Do not modify casually

- `repos/` — upstream data, licences and attribution. Regenerable only via
  the clone commands in `README.md`; treat as read-only.
- `data/example_claims.json` — its flaws are deliberately documented in
  report §6; change it only with a stated reason.
- `docs/archive/REPORT_HACKAPERTUS_OST.md` numbers — only change by rerunning the
  relevant script and updating both number and provenance. Never "improve"
  a figure by hand, and do not present planned functionality as
  implemented.