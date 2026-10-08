# Running the pipeline (collaborative mode)

## External corpus setup

The external corpus checkouts in `repos/` are excluded from Git (about 3.1 GB
locally, including their Git history). The pipeline still needs these files.
On a fresh checkout, run these commands from the project root:

```bash
mkdir -p repos
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets.git repos/VotingBooklets
git clone --depth 1 https://github.com/Eljuanina/VotingBooklets-mono.git repos/VotingBooklets-mono
```

Skip cloning any repository already present locally. Generated logs and
`data/results_*.json` are also excluded; `data/example_claims.json` is retained.

I write the code, you run the heavy stuff, I read the log back. Anything that loads
a language model into RAM (~1 GB or more) goes on your side.

## What's already verified

- Corpus ingestion works: **526 passages** across 1977 / 1985 / 2007 × 4 languages.
- **SwissBERT embedding + NumPy cosine retrieval works end-to-end** on your machine.
  Cross-lingual retrieval verified (German query hits the matching French passage).
- `main.py` runs the full claim → evidence → verdict loop and writes both a `.log`
  and a `.json` per run.
- The `lexical` backend (default `LLM_BACKEND`) uses a keyword heuristic — only for
  smoke-testing the plumbing. Its labels are **not real NLI**.

## What just happened

You ran the MLX pipeline with `swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4`. It
downloaded successfully but failed to load:

```
ValueError: Model type apertus not supported.
ModuleNotFoundError: No module named 'mlx_lm.models.apertus'
```

**Why**: `Apertus` is a custom architecture (uses `xielu` activation + `qk_norm` +
custom chat template). Your installed `mlx-lm 0.21.2` predates Apertus support.
`apertus.py` was added to mlx-lm main after 0.21.2; the current PyPI release is
`0.32.0`. Nothing wrong with the code — just the wrong model for the runtime.

## What to run next

Two viable paths. Do them in this order.

### Path A (fast, safe, ~30 s to first verdict) — Qwen2.5 3B 4bit

This is now the default model in `run.sh` — it uses `qwen2` arch which mlx-lm 0.21.2
ships. ~1.7 GB download once, cached afterwards.

```bash
cd '/Users/liyitian/Documents/Hackathon 26/2/src'
MEMORY_CHECK=1 ./run.sh 2>&1 | tee /tmp/nli_run_qwen3b.log
```

If that works, immediately escalate quality:

```bash
./run.sh mlx-community/Qwen2.5-7B-Instruct-4bit 2>&1 | tee /tmp/nli_run_qwen7b.log
```

### Path B (better quality on Swiss German / FR / IT / RM, but requires mlx-lm upgrade)

Upgrade mlx-lm first:

```bash
pip3 install --user --upgrade mlx-lm
# verify:
python3 -c "import mlx_lm, os; print(mlx_lm.__version__); \
            print(os.path.exists(os.path.join(os.path.dirname(mlx_lm.__file__),'models','apertus.py')))"
# should now print 0.32.0 (or ≥0.22) and True
```

Then:

```bash
cd '/Users/liyitian/Documents/Hackathon 26/2/src'
./run.sh mlx-community/Apertus-8B-Instruct-2509-4bit 2>&1 | tee /tmp/nli_run_apertus8b.log
```

Apertus weights are already on disk from your earlier run — no re-download needed.

If Path B fails after upgrade (e.g. mlx version clash with torch), fall back to Path A.

## What to tell me when it's done

Just say "done" (or "it crashed") and I'll:

1. Read the tee'd log at `/tmp/nli_run_*.log`.
2. Read `data/logs/run_*_mlx.log` for correctness + timing.
3. Read `data/results_*_mlx.json` and compare each label against `expected` in
   `data/example_claims.json`.
4. Decide the next improvement: better chunking / year filter / language filter /
   stricter evidence formatting / more diverse claims.

## Known issues in the current smoke-test claims

- Claims #7 ("nuclear energy") and #9 ("firearms") reference topics **not present**
  in the 1977 / 1985 / 2007 OCR corpus. Their correct label should end up as
  `neutral`. If your MLX run says `entailment` for these, that's a real retrieval
  failure, not a model failure — I'll add a "no relevant evidence" fallback.
- The claim set is very skewed toward the 2007 healthcare initiative. That's for
  smoke-testing. After we get a working LLM judge I'll expand it to ~30 claims
  across all three years and all four source languages, so accuracy is meaningful.

## Reproducing the earlier crashes (for reference)

- `ImportError: .../_spropack.cpython-312-darwin.so` — broken SciPy binary; I already
  removed all SciPy / scikit-learn imports from `retriever.py`, so it doesn't fire.
- `AttributeError` on `XLMRobertaTokenizer` — transformers 5.15 regression; handled
  by `retriever.load_tokenizer_compat` which loads `tokenizer.json` directly.

## Manual smoke-test without an LLM (safe anytime)

```bash
cd '/Users/liyitian/Documents/Hackathon 26/2/src'
python3 test_pipeline.py     # retrieval only, ~5 s
python3 main.py              # full loop with lexical judge, ~5 s
```
