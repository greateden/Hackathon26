# HackApertus — Track 2A (OST) Technical Report

**Project:** Swiss voting-booklet fact-checking prototype
**Pipeline:** claim → evidence retrieval → NLI/LLM judgement → cited evidence
**Date:** 2026-10-06
**Status:** retrieval layer measured and working; judgement layer measured and **not yet working**

> **How to read this document.** Every number below was produced by a command that was
> actually run in this workspace and is reproducible. Anything that was *attempted but not
> verified* is explicitly marked. Section 7 lists what is still unproven, so that nothing
> here is mistaken for a finished result.

---

## 1. What the task needs, and where the real difficulty is

The track asks for a system that, given a claim about a Swiss voting booklet, finds the
passage(s) in the booklet that settle the claim and returns a verdict *with* a citation.

Architecturally that is two stages, and they have very different failure modes:

| Stage | Question it answers | If it fails… |
|---|---|---|
| Retrieval | *where* in the corpus is the relevant text? | the judge never sees the evidence, so it cannot answer correctly no matter how good it is |
| Judgement (NLI) | given that text, does it entail / contradict / not address the claim? | evidence is present but misread |

Most of the work so far assumed retrieval was the easy part. **The measurements in
section 5 show the opposite is true in one specific way:** retrieval transfers between
languages well, but it retrieves poorly when the *query* is English while the corpus is
German. That is the current bottleneck, and it is a cheap fix — no bigger model required.

---

## 2. Existing upstream assets (what we did not have to build)

Two upstream repos were cloned into `repos/`. Neither contains a fact-checking pipeline.

- `repos/VotingBooklets/` — the OCR project. Ships `full_corpus-gemini-ocr-2.5-flash-lite/`
  (**529 `.txt` files, 34 MB**), `aligned_corpus/`, `gold_files/gold_alignment/`, and
  `alignment_experiments/`.
- `repos/VotingBooklets-mono/` — a single-operator variant with `cleaned_ocr_txt/gemini-ocr/`
  (**11 `.txt` files, 252 KB**) and `parallel_corpus/`.

Two facts about the upstream material matter for interpreting everything below:

1. **There is no upstream NLI or claim-verification code to reproduce.** A recursive search
   for `entail|contradict|fact.check|NLI` across both repos' Python and Markdown returns a
   single hit, in a README. The upstream work is OCR and *paragraph alignment* (matching
   "this German paragraph is the same paragraph as this French one"). Alignment is a
   similar-looking task that is **not** the task here: it compares a text to its own
   translation, not a claim to its supporting or refuting evidence. So the useful thing
   taken from upstream is the *encoder recipe* (mean-pooled SentenceSwissBERT + cosine)
   and the *data*, not a baseline to beat.

2. **The upstream repos are not a git checkout** (`git status` → "not a git repository"),
   so upstream versions can't be pinned or diffed.

### The corpus we actually index

The pipeline currently indexes **526 passages from 3 voting dates** (1977, 1985, 2007) out
of the 529-file upstream corpus. That is ~0.6% of the available booklets. Every retrieval
number in this report is therefore a *subset* result and says nothing about behaviour at
full scale, where distractors multiply and vocabulary drifts across decades.


---

## 3. What is implemented

```
repos/…/cleaned_ocr_txt/gemini-ocr → ingest.py → retriever.py → nli_judge.py → main.py → logs + results JSON
                              ↑
                        eval_retrieval.py   (added in this audit)
```

- **`ingest.py`** — loads OCR text, splits it into ≤500-char passages, tags each with
  `lang`/`year`/`id`. 526 passages currently.
- **`retriever.py`** — SentenceSwissBERT (`jgrosjean-mathesis/sentence-swissbert`) on MPS,
  mean pooling, cosine ranking, optional `filter_year` / `filter_lang`.
- **`nli_judge.py`** — three interchangeable backends behind one `judge()` interface:
  `lexical` (keyword overlap, no model), `mlx` (local MLX), `ollama` (HTTP).
- **`main.py`** — runs claims end to end, writes `data/logs/run_<ts>_<backend>.log` and
  `data/results_<ts>_<backend>.json`.

Default backend is `lexical`, deliberately, so the pipeline runs without downloading a
model. This matters for how to read section 4: **the default configuration has never
consulted a language model**, so any earlier "it works" impression was about plumbing,
not accuracy.

---

## 4. Judgement-layer result (the honest headline)

First real model-backed run, completed during this audit:

```bash
cd src        # all commands in this report run from src/
env LLM_BACKEND=mlx MLX_MODEL=mlx-community/Qwen2.5-3B-Instruct-4bit python3 main.py
# → DONE: 10 claims in 139.0s
# → data/results_20261006_200808_mlx.json   (purged in the Oct 2026 cleanup; regenerable)
```

Scored against the `expected` fields in `data/example_claims.json`:

| Run | Backend | Accuracy |
|---|---|---|
| 163756 | lexical (no LLM) | **4/10 = 40%** |
| 165250 | lexical (no LLM) | **4/10 = 40%** |
| 172737 | lexical (no LLM) | **4/10 = 40%** |
| 200808 | **Qwen2.5-3B-4bit (MLX)** | **3/10 = 30%** |

**The LLM is currently worse than keyword matching.** Label distributions explain why —
the model defaults to `neutral`:

```
gold distribution: entailment 4, contradiction 4, neutral 2
model prediction : neutral 8,  contradiction 2,  entailment 0
```

Zero entailment predictions on a set with four entailment gold labels is the signature of
"the evidence I was given doesn't actually discuss this", not of a weak judge. Which
raises the question of what the judge was shown at all — see next section.

### 4.1 The earlier MLX failure, and its real cause

An earlier MLX attempt (log `run_20261006_170024_mlx.log`) died with:

```
File ".../mlx_lm/utils.py", line 139, in _get_classes
    raise ValueError(msg)
ValueError: Model type apertus not supported.
```

This was an **architecture-support gap in the installed `mlx-lm` (0.21.2)**, which cannot
instantiate the Apertus model class — not a bug in the pipeline, and not a memory problem
(this machine has 128 GB RAM). `run.sh` documents upgrading `mlx-lm` as the route back to
Apertus. **Swiss-native model evaluation is still unverified**; the Qwen run above only
proves the plumbing works.

Two related corrections made during this audit:
- `run.sh` aborts below 20% free memory. On a 128 GB machine 17% free ≈ 21 GB free, which
  is ample for a 1.7 GB model — the threshold is miscalibrated and the Qwen run had to
  skip it. Worth changing to an absolute figure.
- Ollama is **not installed and not running** (no `ollama` binary; `localhost:11434` gives
  no response), so the `ollama` backend has never been exercised.

### 4.2 First Apertus measurements (2026-10-10) — Docker container → host endpoint

Setup, now supported end to end: the 60-item dev split (seed 20261009) was judged
inside the Docker container (CPU, linux/aarch64 via colima) against a **real**
OpenAI-compatible endpoint on the host — `mlx_lm.server` serving
`swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4` (mlx-lm 0.32, Apple GPU). MLX never
runs inside the container; the container reaches the host-only server via
`host.docker.internal`. All 120 calls returned and parsed (0 endpoint errors,
0 parse errors).

| Run | Evidence | Accuracy | Macro-F1 | Mean judge latency |
|---|---|---|---|---|
| retrieve-v2 (end-to-end, booklet corpus) | retrieved top-5 | **0.483** | 0.466 | 1.91 s |
| oracle | gold `reference_string` | **0.433** | 0.393 | ≈1.5 s |

Artifacts: `data/eval_results_20261010_082336_dev_openai_retrieve-v2.json`,
`data/eval_results_20261010_082936_dev_openai_oracle.json`.

How to read these honestly:

1. **Development-set plumbing measurements, not submission scores.** n=60 seeded
   plumbing split, single runs, no variance control. The 1,428-item held-out eval
   split has still not been run with any model.
2. **The judge layer remains a real bottleneck.** Oracle (perfect evidence) scores
   *below* end-to-end — within noise at n=60, but it shows the 4B judge does not
   reliably exploit even correct evidence. The entailment bias is measurable: 33
   entailment predictions against 15 entailment golds; 20 of the 45 non-entailment
   items were answered `entailment`, many on passages that do not discuss the claim.
   Compared with §4 (Qwen defaulting to `neutral`), the failure mode changed, the
   problem did not.
3. **Failure behaviour verified on the same path:** with the endpoint stopped, the
   container run exits non-zero and names the endpoint — no silent lexical fallback.

Commands: §9. Stop `serve-apertus` when idle — the server keeps several GB resident.
---

## 5. Retrieval-layer result — and a methodology correction

### 5.1 First measurement was wrong; here is how it was caught

An initial attempt to quantify cross-lingual retrieval returned R@1 ≈ 2–5%, i.e. chance
level, which would have meant "retrieval is broken". Before reporting that, a control was
run: query each passage against itself. Self-similarity came back at exactly **1.0000**,
which is impossible if the encoder were degenerate — so the *harness* was suspect, not the
model.

The bug: `retriever.cosine_sim_matrix()` is written for a **single** query and ends with
`return (q_norm @ c_norm.T)[0]`. The evaluation fed it 32-query batches; the `[0]` collapsed
each batch to the first query's scores, and NumPy broadcast that row across all 32 rows
without raising. Every query was silently scored against the wrong vector.

**Production `retrieve()` is unaffected** — it passes one claim at a time, shape `(1, D)`,
which is what that function expects. `eval_retrieval.py` now uses its own correct batched
matmul, and the module docstring records the trap so it is not re-introduced.

Lesson kept: an evaluation harness needs a control case with a known answer before its
output can be trusted.

October 2026 cleanup note: the `--mode same-lang` control in `eval_retrieval.py`
suffered from a sibling of that harness bug — it masked the gold passage before
ranking (score -> -inf), so its output was maximal by construction and carried no
signal. The mask is now removed; a rerun of the fixed control gives DE
snippet→passage R@1 of 0.45–0.64 against chance levels of 0.01–0.03 (mean gold
rank 3–4), independently confirming the encoder was never degenerate. The
cross-lingual measurements in §5.2 never ran through the control and are
unaffected by this fix.

### 5.2 Cross-lingual retrieval is genuinely good

Using the upstream **gold parallel corpus** as ground truth (a German passage and its
official FR/IT/RM translation), each German segment is used as a query and must retrieve
its own translation out of the whole foreign-language corpus.

`python3 eval_retrieval.py --mode mismatched` (adapters as shipped):

| Booklet | DE→FR | DE→IT | DE→RM |
|---|---|---|---|
| 1977 (n=94) | R@1 **0.926** / R@5 0.968 | R@1 **0.851** / R@5 0.989 | *skipped — no Romansh in this booklet* |
| 1985 (n=32) | R@1 **1.000** | R@1 **0.969** | R@1 **0.969** |
| 2007 (n=36) | R@1 **0.972** | R@1 **1.000** | R@1 **0.833** |

Chance R@1 is 0.011–0.031 and mean gold rank is ~1.0–1.3, so this is a large real effect.
Cross-lingual evidence retrieval **works**.

Two side findings:
- The 1977 gold file contains **no Romansh at all** (0 of 169 segments). The first run
  scored it anyway by embedding empty strings and reported R@1 = 0.011 as if Romansh had
  failed. The eval now skips languages a booklet doesn't contain.
- Encoding *everything* with the `de_CH` adapter is **worse** than the shipped per-language
  adapters (DE→IT on 1977 drops 0.851 → 0.617; DE→RM on 2007 drops 0.833 → 0.556). The
  comment in `retriever.py` claims uniform adapters "give the most stable cross-lingual
  similarity" — that claim is unsupported and contradicted by this measurement. The shipped
  behaviour is the better one; the comment should be fixed, not the code.

### 5.3 …but claim→evidence retrieval is the actual bottleneck

Cross-lingual matching above compares a text to its own translation. The real task compares
an English claim to a German argument. Those are different problems, and `src/diag_claim_retrieval.py`
isolates it on a case where the answer is unambiguous.

The 2007 booklet states, verbatim, `Bundesrat und Parlament lehnen die Initiative ab.`
("The Federal Council and Parliament reject the initiative") — which settles claim #1 as
entailment. That sentence lives in passage `de_2007_002`. Rank achieved, out of 526
passages, `top_k = 5`:

| Query | Rank of the decisive passage |
|---|---|
| English claim, as written in `example_claims.json` | **13** ❌ |
| Same claim in **German** | **1** ✅ (cos 0.885) |
| Verbatim German decisive sentence | 9 |
| English paraphrase with no shared keywords | 23 ❌ |

With the English query, top hits were French procedural boilerplate (treaty preambles,
`vu l'art. 139…`) and a French passage about reserve funds. The judge in run 200808 was
therefore shown text that genuinely does not discuss the claim — **its 8/10 `neutral`
answers were largely correct given the input.** The failure is upstream of the judge.

Note also that passages are language *copies*: `de_2007_017`, `fr_2007_019` and
`fr_2007_021` cover the same content in two languages, so `top_k = 5` spends slots on
duplicates instead of widening coverage.

### 5.4 Full-set benchmark of retrieval stacks (2026-10-09)

With the 60-booklet PDF corpus (16,618 passages) and `eval_e2e.py` in place, claim→evidence
retrieval became measurable as a *task*, not a proxy. Setup: all 1,488 eval items, of which
1,470 have gold evidence locatable in the extracted text (denominator; the 18 others are
excluded, never guessed); gold passages are the chunks containing the annotated
`reference_string` (probe or ≥50% shingle match). Every config searches the **whole**
corpus with no booklet or language filter; `reference_string` and `booklet_url` are used
only to label gold, never at query time. Embedding configs: query = claim, encoded with
the evidence-language adapter, **untranslated** (Ollama was not running; see §8). One run
per config, ~40 s total on the cached index.

| config | R@1 | R@3 | R@5 | MRR@5 | doc-route@1 | R@5 cross-lang (n=959) | R@5 same-lang (n=511) |
|---|---|---|---|---|---|---|---|
| lexical (BM25) | .0245 | .0442 | .0558 | .0355 | .1415 | .0021 | .1566 |
| emb_v1 (dense, de_CH adapter) | .0333 | .0639 | .0891 | .0520 | .1619 | .0740 | .1174 |
| **emb_v2 (dense, evidence-lang adapter)** | **.0966** | **.1673** | **.2122** | **.1375** | **.4483** | **.2002** | **.2348** |
| hyb_rrf (global BM25+dense, RRF) | .0361 | .0966 | .1320 | .0695 | .1755 | .0865 | .2172 |
| two_stage_lex (booklet routing, lexical) | .0224 | .0367 | .0463 | .0305 | .1286 | .0010 | .1311 |
| two_stage (routing, lexical+dense) | .0306 | .0633 | .0762 | .0483 | .1667 | .0083 | .2035 |

Four findings:

1. **The query-side adapter is the biggest lever.** Matching the adapter to the evidence
   language roughly quadruples R@5 over BM25 (0.212 vs 0.056) and lifts cross-language
   retrieval from 0.002 to 0.200. The §5.3/§7-A bottleneck was largely a *configuration*
   problem — queries encoded with the wrong adapter — not an unsolvable cross-lingual
   limit of the encoder. (Even emb_v1's uniform de_CH adapter beats BM25 cross-language,
   0.074 vs 0.002.) Translation on top remains untested.
2. **Hybridisation with the lexical channel lost.** Fusing global BM25 candidates with
   dense candidates via RRF (0.132 R@5) is worse than dense alone (0.212), and its
   same-language slice (0.217) barely differs from dense (0.235) — the BM25 candidate
   pool mostly injected noise. §7-C did not reproduce as designed on the full corpus.
3. **Explicit booklet routing is strictly harmful, for a structural reason.** The
   two-stage configs route to the correct booklet for top-1 far less often (13–17%) than
   plain global dense retrieval does as a side-effect (45%). Diagnostic
   (`src/diag_two_stage.py`): booklets exist as **per-language editions** of the same
   vote day, so a German claim's gold evidence frequently sits in the FR or IT edition —
   and lexical routing from a short claim never crosses that boundary (it routes to the
   same-language, wrong-day edition instead). Confining passage search to the three
   routed booklets therefore loses most of the recall that global search still finds.
   The §7-B duplicate problem is real, but per-document routing is the wrong fix.
4. **These R@5 numbers are lower bounds.** A spot-check of `wrong_passage` failures found
   top-ranked passages that *do* settle the claim (palm-oil item: the retrieved DE passage
   states the claim's content nearly verbatim, while the annotated reference string sits in
   a different chunk). Two spot-checked items among the 18 unlocatable references turned
   out not to be verbatim booklet text at all (heading + "SÌ" stance marker + summary), so
   they are labelling artefacts, not extraction gaps. Substring gold and semantic gold
   diverge; a system answering correctly via a non-annotated passage scores as a miss.

Decision: the only configuration that improved on all metrics is emb_v2-style *global
dense retrieval with language-aligned embeddings*; it is the shape being promoted into the
main pipeline (`RETRIEVAL_CONFIG=v2`, opt-in, default stays `legacy`). Hybrid and
two-stage remain research configs, measured worse here — do not tune their knobs
(`--doc-top-n`, `--cand`, `--per-doc-cap`) without a rerun.

Provenance: `python3 eval_e2e.py --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage --dump-failures 10 --out ../data/eval_results_full_benchmark.json`
from `src/` on 2026-10-09 (MPS, float32, single run, cached index); full output incl.
failure examples in `data/eval_results_full_benchmark.json`. An earlier 60-item smoke
(emb_v2 R@5 0.25, hyb_rrf 0.15, two_stage 0.10) pointed the same direction; these
full-set numbers supersede it.
---

## 6. The evaluation set is the second weak link

`data/example_claims.json` holds 10 claims. Before trusting any accuracy number produced
with it, its problems need to be on the record — otherwise 30% gets read as "the model is
weak" when part of it is "the test is wrong".

1. **Three of the ten claims are not answerable from the indexed corpus.** Grepping
   `de_2007.txt` for nuclear/atomic terms returns **0** hits, and for
   `waffe|Armee|Militär|feuerwerk` also **0**. The 2007 subset contains only two
   initiatives — *Einheitskrankenkasse* (single health-insurer fund) and *gentechnikfreie
   Landwirtschaft* (GMO-free farming). So the claims about nuclear policy, the "army weapons
   article" and "military spending cut by 5 billion" have no evidence either way.
   The judge answered `neutral` on all three, which is **correct**, and scores as 2/3
   because one of them is labelled otherwise.

2. **At least one gold label is wrong.** "The new army weapons article prohibits all
   firearms" is labelled `contradiction` with the note "the weapons article expands
   regulation". But no weapons article exists in this booklet, so the defensible label is
   `neutral`. That single mislabel is worth 10 points of measured accuracy.

3. **n = 10 is too small to rank anything.** One mistake moves accuracy by 10 percentage
   points, and the 40% (lexical) vs 30% (LLM) gap is one item wide. It is a plumbing test,
   not a benchmark.

4. **All 10 claims are English against a German/French/It/Romantsch corpus**, which mixes
   a translation problem into every retrieval result (see 5.3).

5. **There are no gold evidence spans.** Without "which passage settles this claim", a
   wrong answer cannot be attributed to retrieval or judgement without manual digging —
   exactly the digging that section 5.3 had to do by hand.

**Recommendation:** before optimising either model, build ~50 claims that are (a) answerable
from text that is verifiably in the corpus, (b) labelled with the *specific passage id(s)*
that settle them, and (c) written in the source language plus an English variant, so query
language becomes a measured variable instead of a hidden confound. Swiss-language claims
sourced from real booklet statements are preferable to translated ones.

---

## 7. Proposed next steps, in order of expected payoff

Priority follows the evidence: the cheapest fix with the largest measured effect first.

**Status update (2026-10-09): A, B, C and E have since been implemented and measured on
the full 60-booklet corpus (§5.4).** A's adapter fix quadrupled R@5 (translation itself
still untested); C's BM25+dense RRF fusion measured *worse* than dense alone; B's
first fix — two-stage booklet routing — measured worse than global search (wrong tool,
see §5.4 finding 3); E is done, and §5.4 supersedes the §5.2 proxy numbers. Read §5.4
before pursuing any of these routes.

**A. Translate the claim before embedding (highest payoff, small change).**
Evidence: identical content retrieved at rank 13 (English) vs rank 1 (German). Route the
query through a de/fr/it normalisation step — either an MLX translation call or a
`source_language` field on claims — then retrieve in the corpus language. Re-run
`diag_claim_retrieval.py` and require rank-of-target to improve before anything else.

**B. Stop `top_k = 5` burning slots on parallel duplicates.** One fact exists as
`de_2007_002`, `fr_2007_002`, `it_2007_002`… Returning the *aligned group* once (or
diversifying by paragraph) would turn 5 near-duplicate passages into 5 distinct pieces of
evidence. The upstream alignment files already provide the grouping.

**C. Add a lexical/BM25 channel and hybridise.** The keyword baseline currently beats the
LLM end to end (40% vs 30%), which strongly suggests exact terminology in these documents
is highly informative. A dense + BM25 fusion is cheap and usually the fastest win on
short-document legal prose. Note `rank_bm25` is **not installed**; either add it to
`requirements.txt` or implement TF-IDF via scikit-learn (removed from
`requirements.txt` in the October 2026 cleanup as unused — re-add if you take this
route). Keep
retrieval importable without them (guarded import), since `scipy`/`sklearn` availability
should not be a hard dependency of the retrieval path.

**D. Only then tune the judge** — stricter JSON/label output, shorter and de-duplicated
evidence blocks, and an explicit "not discussed in this booklet" escape hatch so `neutral`
is a precise answer rather than a default.

**E. Scale the corpus last.** Going from 3 booklets to the full 529 will add distractors
and may invalidate 5.2's numbers; measure retrieval again after scaling rather than before.

**F. Swiss-native model evaluation, if still wanted.** Either upgrade `mlx-lm` to a release
that supports the `apertus` model type, or use a packaging the current version supports.
Until a run actually completes, Apertus is not a viable option — only a downloaded weight
file that crashes at load. *Update (2026-10-09): superseded — mlx-lm 0.32 loads the
Apertus INT4 MLX conversion and a 3-item dev smoke passed with 0 parse errors; still
plumbing evidence, not a quality result (§8).*

---

## 8. Explicitly unverified — do not present these as results

- **No held-out quality measurement yet.** The recorded model runs (§4, §4.2) are
  single runs on plumbing subsets (10 and 60 dev items). §4.2 numbers are indicative
  development measurements, not submission scores; the 1,428-item eval split has not
  been run with any model.
- **Retrieval has been benchmarked once against gold *claim→evidence* pairs** (§5.4:
  full 1,470-item set, 60-booklet corpus, six configs). Single runs, no variance control;
  gold is substring-matched and counts semantically correct but non-annotated passages as
  misses (spot-checked, §5.4 finding 4), so every §5.4 number is a lower bound. The
  translated-query path (`--translate`, Ollama) has never run.
- **Full-corpus behaviour is measured; the CLI default is not.** §5.4 covers the
  60-booklet corpus via `eval_e2e.py` and the opt-in `RETRIEVAL_CONFIG=v2|hybrid`
  pipeline; the `legacy` default still indexes only 3 booklets / 526 passages and has
  never been benchmarked against anything.
- **Apertus has now run** (2026-10-10): mlx-lm 0.32 loads the INT4 checkpoint, and the
  first dev-set measurements are in §4.2. The container→host endpoint path is verified
  on Apple Silicon via colima only — no x86-64 run, no variance control.
- **The `ollama` backend has never executed** (Ollama not installed, service not answering).
- **Gated Hugging Face dataset access is unconfirmed.** It is not currently needed, because
  the corpus is already present locally under `repos/`.
- **The cross-lingual numbers rely on one machine, MPS, float32, single run.** No variance
  measured, no seed control, no CPU/other-hardware comparison.

## 9. Reproducing everything above

```bash
# retrieval quality (no LLM needed; ~12 s, model already cached)
cd src                              # all commands below run from src/
python3 eval_retrieval.py --mode mismatched     # as shipped
python3 eval_retrieval.py --mode uniform        # the worse adapter config
python3 diag_embeddings.py                      # adapter/degeneracy checks
python3 diag_claim_retrieval.py                 # the rank-13-vs-rank-1 case

# §5.4 full-set retrieval benchmark (needs `make fetch-booklets` and, for the dense
# configs, the cached SentenceSwissBERT index; ~40 s cached / ~4 min cold)
python3 eval_e2e.py --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage --dump-failures 10
python3 diag_two_stage.py                       # booklet-routing diagnosis behind §5.4/3

# end-to-end with a real LLM
LLM_BACKEND=mlx MLX_MODEL=mlx-community/Qwen2.5-3B-Instruct-4bit python3 main.py
```

```bash
# §4.2 (2026-10-10): first Apertus measurements, Docker container → host
# endpoint. From the repo root, two terminals:
#   make serve-apertus               # host endpoint on :8080 (several GB RAM — stop when done)
#   make eval-apertus-docker         # end-to-end: retrieved evidence, booklet corpus
#   make eval-apertus-oracle-docker  # judgement-only: gold evidence
# Requires the eval data and booklet corpus (eval-data / fetch-booklets).
```

Artifacts produced by the audit: the scripts (`src/eval_retrieval.py`,
`src/diag_embeddings.py`, `src/diag_claim_retrieval.py`) are kept in the
repo. The raw run outputs of the four October 2026 runs under `data/`
(logs and results JSON, including the failed Apertus-load log) were purged
in the October 2026 cleanup as regenerable; rerun the commands above to
reproduce them and compare against the numbers quoted in sections 4–5.

---

## 10. Summary

The retrieval layer is in better shape than the summary it inherited: cross-lingual
evidence retrieval measures **R@1 0.83–1.00** against gold-aligned pairs, which is real and
reproducible. The earlier "retrieval is at chance" reading was an artefact of a broken
evaluation harness, not a property of the model, and the code path used in production was
never affected.

The judgement layer has now had its first real run, and it does not work: **30%**, below the
40% of the no-LLM keyword baseline, with zero entailment predictions. The cause is
attributable and is mostly *not* the model — English queries miss the decisive passage
(rank 13 of 526) while German queries find it at rank 1, so the judge is being asked to
reason over boilerplate. Fixing query-language handling and evidence de-duplication (§7 A–B)
is the highest-value next work, and both are measurable before any model swap is worth
considering.

**Update 2026-10-10:** the swap happened — Apertus-4B is now the judge and has been
measured on the 60-item dev split (§4.2): 0.483 accuracy end-to-end, 0.433 with gold
evidence, via the Docker-container → host-endpoint path. The judge layer is no longer
untested; it is tested and mediocre, with the entailment bias (§4) replaced by an
entailment-default bias. Retrieval and judgement remain joint bottlenecks, and all
these numbers remain single-run development measurements, not held-out scores.


