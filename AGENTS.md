# AGENTS.md — working notes for coding agents

> **Current release guidance — 15 October 2026, based on GitHub `main`.**
> The submission project root is `track_2a/`; the repository-root `make`
> forwards to it. Treat this section, the current source code, and
> `track_2a/docs/RUNNING.md` as authoritative over dated research notes below.
> Do not use obsolete branch names, historical 8B-only assumptions, or
> past `make run` successes to infer evaluation readiness.
>
> **Authoritative OST evaluation path:** `track_2a/src/submission_cli.py`,
> launched by the Dockerfile `ENTRYPOINT` and passed `--input /data/cases.jsonl`
> `--output /output/predictions.jsonl`. The container accepts mixed Task A/B
> JSONL, evaluation-injected `BASE_URL` and `API_KEY`, a read-only `/data`,
> and a writable `/output`. Build for `linux/amd64`. The SentenceSwissBERT
> encoder is downloaded at **build** time and included in the image;
> no runtime Hugging Face download is intended.
>
> **Model selection:** the current default is official
> `swiss-ai/Apertus-v1.5-70B` via a separately authorised CSCS-compatible
> endpoint. Official v1.5 8B is also allowlisted, but selecting 8B requires
> separately validated endpoint/model configuration. The team did not agree
> an 8B-only rule. Historical v1.1 or third-party MLX checkpoints are not
> substitutes for the submitted official v1.5 model.
>
> **Separate developer path:** `make run` uses `compose.submission.yaml` and
> `booklet_app.py` for one-request demonstration; it is **not** the OST
> mixed-JSONL evaluation entrypoint. `src/main.py`, `compose.yaml`, `run-native`
> and older OCR/global-retrieval evaluators are preserved research paths.
>
> **Verification as of 15 October:** source-recorded offline regression suite:
> 216 tests passed. An AMD64 image was exercised under ARM64 emulation with
> a loopback **mock** proxy, offline encoder, read-only `/data` and mixed A/B;
> native AMD64 and a **real integrated A/B CSCS batch have not been verified**.
> Earlier genuine 70B Docker Beginner/Advanced entailment smokes succeeded;
> an Advanced Neutral smoke was rejected. Task A `vote-aware-v1` has recorded
> 54-case development Macro-F1 0.491 and 0/18 accepted gold-Neutral examples;
> these are exposed development results, not official held-out quality.
> Task A / B qualification thresholds reported in OST Q&A are 0.60 / 0.75
> Macro-F1; qualification is **not established**. Error rows with null labels
> and nonzero batch exits are not valid official predictions. A publicly
> pullable image from the final code and its digest still require verification.
>
> **Safety and licensing:** do not expose credentials or copy local `.env`
> files into Git/images. Do not include gold-labelled development fixtures in
> the final production image. SentenceSwissBERT carries third-party
> CC-BY-NC-4.0 terms; check attribution, redistribution and permitted uses
> **before publishing an image containing its weights**. Source-code
> Apache-2.0 does not relicense those weights. See `THIRD_PARTY_NOTICES.md`.
>
> **Agent remit:** make minimal, tested release fixes; preserve study data,
> original code, and evidence. No dead-code purge, model fallback, fabricated
> labels, unapproved inference, repository visibility changes, registry push,
> or contest submission. The team approves behavioural changes, public access,
> release image, and final reports. The demo notebook is a separate artefact;
> do not suggest that the static research site performs live inference.

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
  guards, recorded-benchmark provenance). The official mixed-JSONL boundary
  is `src/submission_cli.py`, with contracts in `tests/test_submission_cli.py`
  and `tests/docker_evaluation_contract.py`. Run from `track_2a/`:
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

## Docker runtime and evaluation contract (updated 2026-10-15)

- **Production evaluation:** `src/submission_cli.py` is the only authorised
  mixed Task A/B JSONL entrypoint, passed through `Dockerfile` `ENTRYPOINT`.
  It requires `--input` and `--output`, accepts evaluation-injected `BASE_URL`
  / `API_KEY`, processes local PDF paths beneath `/data`, and writes to the
  separate writable `/output`. Empty or failed predictions are not silently
  converted into classes. Check `docs/RUNNING.md` for the exact invocation.
- **Docker image:** `python:3.11-slim` with CPU PyTorch, `poppler-utils`,
  application source and a **build-time-bundled SentenceSwissBERT encoder**
  pinned to revision `7a91fa8a01af56c1f06060f7af3698ef5619e41c`.
  The Apertus language-model weights themselves are **not** in the image:
  remote API inference is required. MLX is never used in the production image.
- **Network/cache:** the production image uses `HF_HUB_OFFLINE=1` and
  `TRANSFORMERS_OFFLINE=1`; no encoder weights should be downloaded at
  inference time. Advanced requests need a supplied, readable local PDF.
- **Evaluation validation recorded:** ARM64-hosted `linux/amd64` emulation,
  non-root runtime, read-only `/data`, writable `/output`, a genuine CPU
  encoder and mock OpenAI-compatible HTTP responses with valid source-page
  citations and token metrics. This verifies the *interface*, not genuine
  model predictions, Linux/AMD64 native performance or Macro-F1.
- **Model-provider integration:** `BASE_URL` and `API_KEY` override developer
  `LLM_BASE_URL` / `LLM_API_KEY`. The evaluation proxy need not expose
  `/v1/models`; response model identity and token usage remain checked.
  In developer mode, `/v1/models` may still be used. Credentials must never
  enter the Dockerfile, image, logs or Git.
- **Separate single-request demo:** `make run` / `make run-cscs` use
  `compose.submission.yaml` and `booklet_app.py` with `REQUEST_FILE` and
  `RESULT_FILE`; unlike official JSONL evaluation, this path may use writable
  local dev volumes. Do not claim that a `make run` smoke certifies batch CLI.
- **Historical research-only paths:** `compose.yaml`, `main.py`, native MLX,
  old global OCR retrieval and lexical baselines remain preserved to reproduce
  dated studies. Do not treat those configurations as submitted predictions.
- **Remaining P0 risks:** current Task A identity gate rejects some correct
  raw labels; an invalid-case batch emits `label:null` and exits nonzero;
  an official held-out-quality score has not been measured. The production
  stage excludes tests/gold fixtures; `make test-docker` builds the separate
  test target and explicitly overrides its entrypoint.
  Fix from targeted tests, never guess missing labels or drop vote grounding.
- **Published image:** local build success is not publication. Before release
  confirm licensing, build from approved final `main`, publish an immutable
  tag/digest, and independently pull/run it under the documented CLI.

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
- **Superseded historical v1.5 assumption (2026-10-09):** earlier notes
  speculated that only v1.1 MLX existed. This is no longer the submission
  policy. Official `swiss-ai/Apertus-v1.5-70B` ran successfully via CSCS,
  and a v1.5 8B MLX development smoke was recorded. Production uses
  official v1.5 API inference, not the older v1.1 MLX configuration.
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
- Genuine real-model traffic includes native MLX development runs and
  CSCS 70B single-request Docker smokes. The **new mixed JSONL batch** has
  only mock completion evidence. The historical Ollama backend was mock-tested.
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
