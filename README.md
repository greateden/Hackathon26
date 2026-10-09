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
- The judgement layer does **not** yet work: the one LLM run scored 3/10 on
  ten smoke-test claims, largely because English queries retrieve the wrong
  evidence. The default `lexical` judge is a keyword heuristic for
  smoke-testing only; its labels are not real NLI.
- The Apertus backend has never run: the installed `mlx-lm` 0.21.2 cannot
  load the `apertus` architecture (upgrading to ≥ 0.22 is the documented
  way back).

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
LLM_BACKEND=mlx python3 main.py # real LLM judge (MLX); or: ./run.sh [mlx-model-id]
```

Each run writes a log to `data/logs/` and a results JSON to `data/`
(git-ignored, regenerable).