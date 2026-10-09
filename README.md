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
  First numbers (single runs, 2026-10-09): BM25 full-set R@5 0.056 overall,
  0.002 cross-language vs 0.157 same-language; 60-item embedding smoke
  favors the evidence-language adapter (R@5 0.25) over de_CH-only (0.08).
  Directional findings, not benchmark claims. The legacy 526-passage CLI
  corpus is unchanged.
- Judgement is now measured, not guessed: `eval_nli.py` scores any judge
  backend against the official 1,488-item MNLI-over-Swiss-Voting-Booklets
  set (v1.1, MIT; `make eval-data` to download). Accuracy + macro-F1 +
  confusion matrix, pure Python. `--evidence oracle` isolates the
  judgement step from retrieval; `--evidence retrieve` runs the full
  pipeline over the legacy 526-passage CLI corpus — a plumbing check, since
  those booklets are not in it. Claim→evidence retrieval over the full
  booklet corpus is measured by `eval_e2e.py` instead.
  The old 10-claim smoke set (3/10, flawed) is superseded, not extended.
- The Apertus backend runs: the git-ignored `.venv` carries mlx-lm 0.32,
  which loads `swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4`. The first run
  (2026-10-09) passed a 3-item dev smoke with 0 parse errors. That is
  plumbing evidence — no accuracy claim until a full split is recorded.

Evidence, measurements and explicit caveats: `REPORT_HACKAPERTUS_OST.md`
(§8 lists everything that is unverified). Official requirements:
`challenge_spec.md`. Working notes for coding agents: `AGENTS.md`.

## Setup

Requires Python 3.12+, PyTorch, and (on a fresh machine) an internet
connection to fetch the corpus and the embedding model. The MLX judge
backend additionally needs Apple Silicon.

```bash
# 1. External corpus checkouts (~3.1 GB, excluded from Git). Skip any that already exist.
mkdir -p repos
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets.git repos/VotingBooklets
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets-mono.git repos/VotingBooklets-mono

# 2. Python dependencies
python3 -m pip install -r src/requirements.txt
```

## Running

All commands run from `src/`. First run downloads the sentence-swissbert
embedding model (~0.5 GB, cached afterwards); no LLM download is needed
unless you opt in.

```bash
cd src
python3 test_pipeline.py        # retrieval smoke test (no LLM)
python3 main.py                 # full CLI over data/example_claims.json, lexical judge
python3 main.py --year 2007 "A claim to check"   # one-off claim
python3 eval_retrieval.py       # retrieval-quality evaluation on gold-aligned pairs
python3 fetch_booklets.py       # build the 60-booklet PDF corpus (internet, resumable)
python3 eval_e2e.py --configs lexical            # full-set e2e retrieval eval, no model
python3 eval_e2e.py --limit 60  # class-balanced 60-item e2e eval, all three configs
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
make fetch-booklets       # download 60 booklet PDFs -> data/booklets/corpus.json
make eval-e2e-quick       # 60-item class-balanced retrieval eval (lexical + embeddings)
make eval-e2e-full        # full 1,488-item retrieval eval (long run)
```

Set up the Apertus venv once with:

```bash
python3 -m venv .venv && .venv/bin/pip install "mlx-lm==0.32.0"
```

The dev/eval split is a fixed seeded partition of the 1,488-item set
(`--seed` to change; `--limit` to subsample). Treat `eval` as held out:
freeze prompts and settings before running it, and record the printed
command line with any numbers you report.