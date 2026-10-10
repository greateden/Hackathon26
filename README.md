# Swiss voting-booklet claim verification (Track 2A prototype)

Given a claim about a Swiss voting booklet (Abstimmungsbuechlein), the
pipeline retrieves the passages that settle it from the OCR'd trilingual
corpus (DE/FR/IT, plus RM) and asks a language model whether the booklet
**entails**, **contradicts** or is **neutral** towards the claim — quoting
the evidence it used.

```
claim → retrieval (SentenceSwissBERT) → evidence → NLI judge → verdict + cited passages
```

All code lives in `src/` and is run from that directory.

## Status (October 2026)

Exploratory prototype — the plumbing works; the science is still open.

- End-to-end CLI over 526 passages from three voting booklets (1977/1985/2007).
- Cross-lingual retrieval measures R@1 0.83–1.00 on gold-aligned translation
  pairs. This is a *proxy* task, not claim→evidence retrieval.
- Retrieval is now measurable properly: `make fetch-booklets` downloads the
  60 booklet PDFs referenced by the official eval set and extracts 16,618
  passages into `data/booklets/corpus.json` (resumable; 1,470 of 1,488 gold
  evidence strings — 98.8% — locate inside that text). `make eval-e2e-quick`
  / `eval-e2e-full` (`src/eval_e2e.py`) then measure claim→evidence
  retrieval end-to-end, searching the whole corpus with no booklet filter.
  Corrected full benchmark (2026-10-10, 1,470 items, single runs,
  `data/eval_results_full_deploy.json`) under the deploy protocol —
  symmetric BM25 tokenisation plus the adapter chosen from the claim
  language (what a deployable pipeline can actually do): BM25 R@5 0.094,
  hybrid RRF 0.094, dense (untranslated) 0.084. Nothing is clearly ahead at
  this sample size. The earlier 2026-10-09 ranking (dense 0.212 ahead of
  BM25 0.056) is WITHDRAWN: it crippled the lexical channel (documents were
  tokenised case- and umlaut-sensitively while queries were normalised) and
  gave the dense channel the gold evidence language at query time
  (`--adapter-policy oracle` — a diagnostic ceiling, not a deployable
  setting). Both the withdrawn and the corrected measurements, and what each
  can and cannot establish, are documented in report §5.4.
  Numbers are lower bounds (substring-matched gold). The legacy
  526-passage CLI corpus is unchanged; `RETRIEVAL_CONFIG=v2|hybrid`
  lets `main.py` opt into the booklet-corpus stacks (plumbing verified,
  no quality benchmark on the pipeline path yet).
- Judgement is now measured, not guessed: `eval_nli.py` scores any judge
  backend against the official 1,488-item MNLI-over-Swiss-Voting-Booklets
  set (v1.1, MIT; `make eval-data` to download). Accuracy + macro-F1 +
  confusion matrix, pure Python. `--evidence oracle` isolates the
  judgement step from retrieval; `--evidence retrieve` runs the full
  pipeline over the legacy 526-passage CLI corpus — a plumbing check, since
  those booklets are not in it; `--evidence retrieve-v2` runs the production
  booklet-corpus stack end to end. Claim→evidence retrieval over the full
  booklet corpus is measured by `eval_e2e.py` instead.
  The old 10-claim smoke set (3/10, flawed) is superseded, not extended.
- The Apertus backend runs and has been measured (2026-10-10, seeded
  60-item dev split; `swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4` served
  locally via `mlx_lm.server`). Full paired prompt-config ablation in
  report §4.3: best retrieved-evidence result **acc 0.483 / macro-F1
  0.467** (experimental `select` arm) vs 0.450 / 0.436 for its paired
  `t0` control and 0.483 / 0.466 for the earlier T=0.1 default run.
  Production default unchanged. These are development measurements, not
  held-out submission scores (report §4.3 lists the caveats).
- The `select` bundle is now de-confounded: single-factor arms `fill_only`
  and `window_only` exist, and offline prompt-equivalence analysis
  (`src/diag_evidence_ablation.py`, report §4.4) shows every 2×2 cell is
  byte-identical to an already-recorded run — the factors are attributed
  without spending new inference (fill budget = the +2 retrieve flips;
  window selection = the −6 oracle flips).

Evidence, measurements and explicit caveats: `REPORT_HACKAPERTUS_OST.md`
(§8 lists everything that is unverified). Official requirements:
`challenge_spec.md`. Working notes for coding agents: `AGENTS.md`.

## Setup

Two ways to run: **Docker** (portable — macOS and Linux; needs only
Docker, no Python setup) or **native Python 3.12+** (required for the
Apple Silicon MLX judge).

```bash
# 1. External corpus checkouts (~3.1 GB, excluded from Git). Skip any that already exist.
mkdir -p repos
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets.git repos/VotingBooklets
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets-mono.git repos/VotingBooklets-mono

# 2. Native Python dependencies (skip if you only use Docker)
python3 -m pip install -r requirements.txt
# On Apple Silicon, for the MLX judge backend also:
python3 -m pip install -r requirements-macos-mlx.txt
```

`requirements.txt` is the portable, pinned set (CPU PyTorch) used by the
Docker image; MLX (Apple Metal only) lives in `requirements-macos-mlx.txt`
and is never installed inside a container.

## Running with Docker

From the repo root (requires Docker; the first dense run downloads the
embedding model once into a cached volume):

```bash
make serve-apertus   # (host, separate terminal; needs .venv) serves Apertus
                     # natively on :8080 — start it for the next two lines
make run             # full pipeline with REAL Apertus via that endpoint
                     # (fails fast if the endpoint is down — no lexical fallback)
make smoke           # same pipeline with the LEXICAL baseline — plumbing
                     # smoke test only, NOT an Apertus model result
make test-docker     # offline unit checks inside the container
make eval-apertus-docker        # 60-item dev eval, real Apertus judge,
                     # retrieved evidence (end-to-end; needs eval data +
                     # booklet corpus); use eval-apertus-oracle-docker for
                     # the gold-evidence (judgement-only) variant
```

`repos/` and `data/` are mounted, never copied into the image. MLX never
runs inside a container: Apple Silicon MLX only runs natively (`make
serve-apertus`, `make run-native`). Any OpenAI-compatible endpoint works —
set `OPENAI_BASE_URL`; `LLM_BACKEND=ollama OLLAMA_MODEL=<model> make smoke`
is the alternative. The model server keeps several GB of RAM resident —
stop it when you are done.

An empty corpus, an unreachable model endpoint, or an unparseable model
reply is reported as an error — never silently replaced by a lexical
prediction. Architecture and troubleshooting: `AGENTS.md`, section
"Docker runtime".

## Running natively (from `src/`)

All commands run from `src/`. First run downloads the sentence-swissbert
embedding model (~0.5 GB, cached afterwards); no LLM download is needed
unless you opt in.

```bash
cd src
python3 test_pipeline.py        # retrieval smoke test (no LLM)
python3 main.py                 # full CLI over data/example_claims.json, lexical judge
python3 main.py --year 2007 "A claim to check"   # one-off claim
RETRIEVAL_CONFIG=v2 python3 main.py "..."        # opt-in booklet-corpus stack
python3 eval_retrieval.py       # retrieval-quality evaluation on gold-aligned pairs
python3 fetch_booklets.py       # build the 60-booklet PDF corpus (internet, resumable)
python3 eval_e2e.py --configs lexical            # full-set e2e retrieval eval, no model
python3 eval_e2e.py --limit 60  # class-balanced 60-item e2e eval, all six configs
python3 ablation_dev.py --dry-run  # plan the prompt-config ablation (offline)
python3 diag_evidence_ablation.py  # offline check: factorial prompt-equivalence + oracle-flip analysis
python3 ablation_dev.py --backend openai  # FULL ablation (t0/strict/select vs a
                     # paired t0 baseline on the fixed dev split) — needs a
                     # live endpoint (start `make serve-apertus` first, in a
                     # separate terminal, with other memory-heavy apps
                     # unloaded) and writes one JSON per run; refuses to run
                     # without the endpoint — no lexical fallback
LLM_BACKEND=mlx python3 main.py # real LLM judge (MLX); or: ./run.sh [mlx-model-id]
```

Each run writes a log to `data/logs/` and a results JSON to `data/`
(git-ignored, regenerable).

## Reproducible entry points (from the repo root)

The `Makefile` wraps the common runs and uses `.venv/bin/python` for the
Apertus targets when that venv exists.

```bash
make test                 # offline unit checks (labels, parser, evidence)
make eval-data            # download the official eval set (needs internet)
make eval-lex-quick       # 60-item dev split, lexical heuristic (plumbing)
make eval-apertus-quick   # 10-item dev split, Apertus MLX judge (needs .venv)
make eval-apertus-full    # 1,428-item held-out eval split (long run)
make serve-apertus        # host endpoint on :8080 (for the Docker Apertus runs)
make eval-apertus-docker  # 60-item dev eval, real Apertus via Docker (needs serve-apertus)
make fetch-booklets       # download 60 booklet PDFs -> data/booklets/corpus.json
make eval-e2e-quick       # 60-item class-balanced retrieval eval (all six configs)
make eval-e2e-full        # full 1,488-item retrieval eval (~1 min with cached indexes)
make ablation-smoke       # offline wiring check of the prompt-ablation runner
make ablation-dev         # full prompt-config ablation on the fixed dev split
                          # (needs `make serve-apertus` running in a separate
                          # terminal; ran once with a real endpoint on
                          # 2026-10-10 — results in report §4.3; the runner
                          # refuses to start without a live endpoint)
```

Set up the Apertus venv once with:

```bash
python3 -m venv .venv && .venv/bin/pip install "mlx-lm==0.32.0" requests
```

The dev/eval split is a fixed seeded partition of the 1,488-item set
(`--seed` to change; `--limit` to subsample). Treat `eval` as held out:
freeze prompts and settings before running it, and record the printed
command line with any numbers you report.