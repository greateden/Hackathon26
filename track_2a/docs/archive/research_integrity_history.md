> Historical evidence ledger, migrated 11 October 2026. Findings below describe the
> dated audit, not current closure status. See PROJECT_STATUS.md for this iteration.
> Original baseline and reproduction evidence are retained; no measurements were rerun here.

# Independent full-repository audit — HackApertus Track 2A OST

Date: 10 October 2026. Baseline commit: `7456228e37591efff3af20b35e32eb70d319631f`.

**Post-audit cleanup (10 Oct 2026, after this report was written):** the
artefacts named throughout this document — `src/test_audit.py`,
`src/audit_offline.py`, `the retired one-off audit JSON` and their successor
`tests/test_retrieval_audit.py` — were one-off audit tooling and have been
removed from the tree. The permanent regression checks that replaced them
live in `tests/test_project_contract.py` (run `make test` from the repo
root, or `PYTHONPATH=src python3 -m unittest discover -s tests -p
'test_*.py'`). The "Reproduction commands" section below is therefore a
record of how the evidence was produced at audit time, not a runnable
procedure. The findings themselves are unchanged.

## Executive summary

- **High: the lexical channel is incorrectly tokenised.** Documents retain case and punctuation; queries do not. The published BM25/hybrid comparison cannot establish that a correctly implemented lexical channel is inferior.
- **High: the reserved split is not independent.** It contains 39 exact claim/reference/label duplicates of development examples. Full-set retrieval results have also already informed configuration choices.
- **High: invalid model outputs can become valid labels**, including JSON `true`, `1.9`, `"neutral-ish"` and `"2.5"`. Historical raw replies are absent, so their effect on recorded scores cannot be determined.
- **High, fixed:** endpoint identity accepted substrings and empty IDs; CLI failures could disappear, and empty retrieval could produce successful neutral predictions.
- **High: native installation is not reproducible from the declared requirements.** macOS has no active PyTorch requirement; MLX-LM 0.32.0 requires Transformers ≥5.7.0, conflicting with the portable 4.48.3 pin.
- **Medium, fixed:** ablations selected the newest JSON in a shared directory and could report a partial run as a successful comparison. They now own their output paths and fail on incomplete execution.
- All 16 saved NLI runs reproduce their stored summaries under the existing scorer. Independent arithmetic found a 0.001 rounding discrepancy in two lexical runs; the ten full 60-item Apertus runs have consistent headline arithmetic.
- The documented factorial render equivalences hold under the current dev data and code. Equal token counts alone do **not** establish equal historical prompts; the diagnostic can incorrectly pass missing/disjoint run sets.
- Original 44 checks and 20 new offline tests pass. New tests against the original source fail (10 failures, 5 errors including subtests/API changes). No model weights, inference servers or Docker workloads were started.
- Production defaults, retrieval rankings, parser policy, labels, split membership and scoring rules remain unchanged. Scientific corrections below are proposed for review, not applied.

## Scope and baseline

The working tree was clean before work. Every first-party tracked Python file, root document, shell script, build/configuration file and the smoke claims was inspected, including diagnostics outside the prompt's core list. Discovery covered all root entries, ignored data artefacts and both external repository structures. External repositories, their PDFs and installed packages were treated as inputs, not as first-party code to rewrite. This is not a line-by-line audit of external dependencies or all upstream OCR software.

Reviewed areas: `config`, `labels`, `ingest`, `retriever`, `hybrid_retrieval`, `main`, all three evaluation harnesses, both fetchers, `sampling`, `nli_judge`, `ablation_dev`, all five diagnostic scripts, both original tests, `run.sh`, README, AGENTS, technical report, challenge specification, Makefile, Dockerfile, Compose and both requirements files. The tracked 49 MB embedding array was inspected for dimensions and finiteness, not regenerated.

Runtime: macOS 27.2 arm64; both interpreters are Python 3.12.4. System packages: NumPy 2.5.3, PyTorch 2.14.0, Transformers 5.15.1, MLX 0.22.0, MLX-LM 0.21.2, Requests 2.32.3. Project `.venv`: NumPy 2.5.3, PyTorch 2.14.1, Transformers 5.19.0, MLX 0.32.3, MLX-LM 0.32.0, Requests 2.34.2. `.venv/bin/python -m pip check` reports no broken installed requirements; this does not validate the repository's contradictory pins.

The current dataset has 1,488 rows: E=495, N=498, C=495. Dev is E=15, N=26, C=19; eval has 1,428 rows and disjoint row indices. Corpus: 16,618 unique passage IDs, 60 documents, DE=5,184 / FR=5,792 / IT=5,642. Cache: `(16618, 768)`, float32, all finite, key `92f67a425caeafc5`. Coverage recomputation matches the saved benchmark: 1,469 probe matches, one shingle match and 18 exclusions.

Machine-readable evidence, hashes, exact dev indices and historical flips: `the retired one-off audit JSON`. Reproduce with `src/audit_offline.py`; this reads the reserved rows only for integrity/coverage checks, never for tuning or new retrieval rankings. The upstream checkouts are now real Git repositories, contrary to the historical report: VotingBooklets `945fb346016fd08d73b6b658b8cebcd301e0bef8`; VotingBooklets-mono `d619ad386fdf2afd30a92f1b8f77a6cff35641a1`.

## Confirmed defects

References below use the final working-tree line numbers; descriptions of old behaviour refer to the baseline commit above.

### D01 — High — asymmetric BM25 tokenisation invalidates the intended lexical comparison

**Location:** `src/hybrid_retrieval.py:66–103`; callers `src/eval_e2e.py:463–470`, `src/hybrid_retrieval.py:150–155`.

**Root cause:** `BM25.__init__` uses `t.split()` on raw PDF text; `top_k` applies `norm_text(query)`. Capitalised words, punctuation and accented tokens often cannot match themselves. The claimed “BM25 on normalised tokens” was not run.

**Reproducer:** `BM25(['Bundesrat.', 'bundesrat']).top_k('Bundesrat', 2)` returns only document 1, score 0.693147. With both texts normalised it returns both, tied at 0.182322. Expected: symmetric preprocessing and equal token statistics. This is a scoring-input defect, independent of whether BM25 is ultimately competitive.

**Impact:** all lexical, hyb_rrf, two_stage_lex and two_stage rankings using this implementation are affected. §5.4's 0.0558/0.1320/0.0463/0.0762 R@5 values remain records of the broken implementation, not fair estimates of the intended baselines. Dense-only ranks and the `retrieve-v2` NLI runs do not use BM25. The ranking after correction is unknown; no corrected full-set run was performed.

**Status:** not fixed: it changes retrieval semantics and requires a separately named rerun. Proposed local patch:

```diff
-        self.doc_tok = [t.split() for t in texts]
+        self.doc_tok = [norm_text(t).split() for t in texts]
```

**Evidence:** `audit_offline.py`, `reproductions.bm25_raw` and `bm25_normalised_proposal`. This is a characterisation of an unresolved bug, not a passing regression guard for corrected BM25.

### D02 — High — row-disjoint dev/eval splits contain duplicate examples

**Location:** `src/eval_nli.py:64–72`, `src/eval_nli.py:295–298`; current `data/eval/mnli_swiss_v1.1.jsonl`.

**Root cause:** seeded sampling separates row indices, not example identities or document groups. It is deterministic for an unchanged ordered file, but this is weaker than independent held-out data.

**Reproducer/actual:** reconstruct the fixed dev indices, then count held-out rows sharing dev keys. There are 45 matching claims, 128 matching reference strings, 852 matching booklet URLs, and **39 exact claim + reference + label triples**. Document/reference overlap alone is not necessarily invalid for a within-document task; identical example overlap is the strongest finding. Expected: held-out generalisation claims disclose or exclude such overlap under an agreed protocol.

**Impact:** dev arithmetic is unaffected. A future 1,428-row score would not be an independent unseen-example estimate. In addition, all 1,488 rows have already been used to compare six retrieval systems and choose a preferred approach (§5.4), so “untouched held out” is inaccurate for the complete system even though no held-out model run is present.

**Status:** split membership intentionally unchanged. Proposed preflight patch, which blocks an independence claim without silently reassigning rows:

```python
key = lambda r: (r['claim'], r['reference_string'], r['entailment_label'])
dev_keys = {key(rows[i]) for i in dev_indices}
overlap = [i for i in eval_indices if key(rows[i]) in dev_keys]
if overlap:
    raise ValueError(f'{len(overlap)} held-out rows duplicate development examples')
```

A versioned group-disjoint or new external evaluation set is a separate methodological decision; do not replace the existing split in place. Evidence: `heldout_overlap_counts` and `split` in the audit JSON.

### D03 — High — parser accepts invalid codes and partial label values

**Location:** `src/labels.py:31–46`, `src/nli_judge.py:174–220`.

**Root cause:** `int(code)` coerces booleans and non-integral numbers; the broken-JSON fallback matches a label prefix at a word boundary even after a complete JSON object has an invalid label. It therefore converts `"neutral-ish"` to neutral and `"2.5"` to contradiction. A prose response beginning “neutral is not justified…” is also interpreted as neutral, although the leading-label policy is explicitly intentional.

**Reproducer/actual:** `{"label": true}` → neutral; `{"label": 1.9}` → neutral; `{"label": "neutral-ish"}` → neutral; `{"label": "2.5"}` → contradiction; `{"label": "entailment or contradiction"}` → entailment. Expected: these invalid values produce `label=None`, not a guessed valid class.

**Impact:** any model backend's recorded accuracy/errors may be affected. No saved raw replies exist for the principal NLI runs, so the number of affected predictions is **unknown**, not assumed positive. Summaries being internally consistent does not clear this defect.

**Status:** not fixed because changing accepted predictions changes the evaluation protocol. Proposed patch: accept numeric codes only when `type(value) is int` and value is 0/1/2, or when an explicitly allowed digit string is exactly `0`, `1` or `2`; reject `bool`, float and all other types. After successful JSON decoding, return an error for an invalid label rather than falling through to a regex. For genuinely truncated JSON, require a complete quoted label value, e.g. `r'"label"\s*:\s*"(entailment|neutral|contradiction|[012])"'`. Decide separately whether only an exact standalone bare label should be accepted. Preserve the existing all-three-label and truncated-reasoning fixtures. Capture raw outputs and parser version before comparing corrected results.

**Evidence:** five minimal cases in `reproductions.invalid_labels`. No historical result files were rewritten.

### D04 — High — wrong or empty endpoint model IDs accepted (fixed)

**Location:** `src/nli_judge.py:360–414`.

**Root cause:** startup checked bidirectional substring membership and basename containment. `Apertus`, an empty string, or the requested ID with `-other` appended could pass as the requested checkpoint.

**Reproducer:** mock `requests.get` to return each advertised ID. Previously these were accepted; malformed numeric/None IDs could also cause an unhelpful TypeError. Expected: exact, non-empty model ID membership, or a deliberately configured exact server alias.

**Fix:** non-string/blank IDs are ignored, and the requested model must be an exact member. If a server advertises a local path/alias, set `JUDGE_MODEL` to that exact ID deliberately. The check establishes the server's advertised identity, not cryptographic proof of its weights; per-response identity/revision attestation remains absent.

**Impact:** no evidence that the historical endpoint was wrong; recorded model metadata is insufficient to independently prove actual loaded bytes. Valid exact-ID requests retain the same prompts and generation settings.

**Regression:** `test_identity_exact`, `test_identity_substrings_rejected`, `test_identity_endpoint_failure`; all pass without an HTTP server.

### D05 — High — CLI conceals missing/failed predictions (fixed)

**Location:** `src/main.py:161–236`, `src/main.py:269–272`, `src/main.py:286–334`.

**Root cause:** `verify` called the judge for empty retrieval; LexicalJudge returned neutral. `run` caught exceptions and continued without a result row. `main` exited successfully after per-item failures or absent claims. A label plus an error, or an unknown truthy label, could also receive status `ok`.

**Reproducer/actual:** a fake empty retriever produced `{label: neutral, status: ok}`. A fake retriever raising for the only claim produced `[]`; an error result still yielded CLI exit 0. Expected: one error row per failed input, no fabricated class, non-zero CLI status after saving the report.

**Fix:** empty retrieval bypasses the judge and returns an error; explicit judge errors and invalid labels cannot be success; raised exceptions remain in the batch; missing claims and any per-item error cause exit 1. Successful valid labels and retrieval strategy are unchanged. The separate `eval_nli.evaluate` already retained raised/empty-retrieval errors and was not changed.

**Impact:** historical CLI result counts can omit failures. The 60-item eval artefacts do not use `main.run`; their denominators are unaffected by this fix. Error rows can increase the CLI result count relative to previous behaviour, intentionally restoring accounting rather than changing evaluation denominators.

**Regression:** seven pipeline/CLI tests plus the all-label preservation fixture in `test_audit.py`. No real judge is invoked.

### D06 — High — declared native dependency installation is incomplete and contradictory

**Location:** `requirements.txt:12–14`, `requirements-macos-mlx.txt:6–7`, README setup and venv instructions.

**Root cause:** both PyTorch markers select Linux only. On macOS, installing the portable requirements cannot provide the `torch` imported by `retriever.py`. The installed MLX-LM 0.32.0 distribution declares `transformers>=5.7.0`; the portable file pins `transformers==4.48.3`. Sequential installation may upgrade away from the portable pin; installing both files together is incompatible. A minimal `mlx-lm requests` venv also does not itself declare PyTorch.

**Verification:** evaluated every marker for Darwin/arm64 and inspected `.venv` package metadata; 4.48.3 does not satisfy the declared MLX-LM constraint. Neither interpreter matches the portable pins. This conclusion does not require a fresh installation or network resolver run.

**Expected:** separate, tested native versus container installation instructions with a compatible complete dependency set. **Status:** not fixed; changing pins requires rebuild/container validation under AGENTS.md, and heavy rebuilds were not authorised. No package was installed. Portable Linux wheel availability and a fresh macOS resolution still require verification.

### D07 — Medium — ablation result ownership and incomplete execution are unsafe (fixed)

**Location:** `src/ablation_dev.py:68–96`, `src/ablation_dev.py:186–200`; `src/eval_nli.py:271–288`, `src/eval_nli.py:384–388`.

**Root cause:** the runner loaded the globally newest `eval_results_*.json` after each subprocess. Concurrent runs, future mtimes or another writer could substitute an unrelated artefact. Same-second filenames could overwrite repeated lexical results. After a later subprocess failure, already collected runs could still be printed/saved as a comparison with exit 0.

**Reproducer:** create a future-dated unrelated result, then mock a successful child run. The old runner selects the unrelated file. Mock one successful child followed by failure: old control flow proceeds to comparison.

**Fix:** UUID-qualified per-run output passed through a new `--out`; exact returned metadata is checked; writes use exclusive creation and default filenames include microseconds. Incomplete ablations exit non-zero before comparison. Existing per-run files remain available for diagnosis.

**Impact:** all eight existing ablation summary entries match their actual per-run metadata and summaries; no substitution is observed there. No model inputs or scoring changed. **Regression:** ownership with an unrelated newer file, incomplete-run exit, explicit-output integration, and existing-file preservation tests pass.

### D08 — Medium — equivalence diagnostic can certify missing evidence

**Location:** `src/diag_evidence_ablation.py:84–113`, `src/diag_evidence_ablation.py:149–185`, `src/diag_evidence_ablation.py:231–266`; also `src/diag_eval_errors.py:99–135`.

**Root cause:** missing files/runs are skipped; comparisons use only intersecting numeric indices without validating identities or complete membership. Skipped checks return true. Equal prompt-token counts are described as identical prompts, although different text can have the same length/token count. `diag_eval_errors` checks alignment through `zip` and continues after a warning; it also crashes on retrieve runs with no usage tokens.

**Reproducer:** `compare_runs` on disjoint one-item index sets returns `(1, [], [])`. Running the diagnostic with a temporary `{"runs": []}` produces exit 0 and “all expected equivalences hold”. Expected: incomplete evidence yields an explicit incomplete/non-success result; byte identity requires bytes or hashes.

**Impact:** the current complete eight-run set and current oracle reconstruction pass independently. The failure is in the diagnostic's general guarantee, not proof that those particular twins differ. It cannot certify exact historical retrieved prompts, which were not saved.

**Status:** documented, not fixed. Proposed correction: require expected run keys and exact item identities/counts; separate PASS, FAIL and INCOMPLETE; compare prompt hashes and distinguish “same token count” from “same prompt”. Existing diagnostic was run successfully on the specified complete artefact; missing/disjoint adversarial cases were run separately.

### D09 — Medium — quick subsampling and macro-F1 conceal missing classes

**Location:** `src/eval_nli.py:64–72`, `src/eval_nli.py:210–226`, `src/eval_nli.py:295–298`; `Makefile:117–121`; `src/sampling.py:1–37`.

**Root cause:** the seeded dev indices are sorted back into file order before `--limit` takes a prefix. The first ten are all entailment. Macro-F1 averages only classes with gold support and averages their already rounded F1s. `sampling.py`'s claim that the full dataset is 48/30/22 is false for this snapshot; its order-independent claim is also not implemented (shuffling depends on input/group insertion order).

**Actual:** the saved ten-item MLX run has 0.700 accuracy / 0.824 macro-F1, but tests no neutral/contradiction gold examples. A fixed-three-class macro on that same prediction list would be about 0.275. The saved three-item MLX run's 1.000 is likewise an entailment-only smoke result. On the two 60-item lexical runs named in the JSON, unrounded F1 arithmetic gives 0.243434 → **0.243**, while the stored rounded-class mean is **0.244**.

**Expected:** disclose support in small-run headlines; agree and version the averaging convention; average full-precision values before display rounding. **Status:** scoring/sampling unchanged. Proposed metric patch: retain unrounded F1s separately, average the agreed class list, round only the final value. A future stratified quick sample must not silently change the fixed dev membership or be compared to historical prefixes as paired data.

**Evidence:** independent Fraction-based recomputation in `audit_offline.py`; manually calculated error-inclusive metric fixture passes. No headline F1 rounding discrepancy was found in the ten 60-item Apertus runs.

### D10 — Medium — cache does not identify the encoder revision or validate its contents

**Location:** `src/hybrid_retrieval.py:248–272`; `src/retriever.py:24–48`, `src/retriever.py:89–104`; consumers `src/main.py:131–141`, `src/eval_e2e.py:442–451`.

**Root cause:** the key contains model name, batch size, ordered text and languages, but not immutable model/tokenizer revisions, adapter mapping, pooling/truncation implementation or dtype. The model is loaded from a mutable default revision; tokenizer fallback chooses the lexicographically first cached snapshot. `load_index` accepts arbitrary shapes/NaNs and writes are non-atomic.

**Reproducer:** a `(1,2)` array under a valid cache filename is returned without validation. Reordering corpus text changes the key correctly; changing encoder implementation while retaining model name/text does not. Expected: manifest-backed compatibility and shape/finiteness validation, then atomic publication.

**Impact:** silent query/index encoder mismatch is possible; actual historical revision mismatch/corruption is **unproven**. The current array has the expected shape and finite values, but this cannot establish how its vectors were generated. It is a tracked 49 MB artefact under `data/cache`, despite AGENTS descriptions of caches under `data/booklets`.

**Status:** not fixed; invalidating this cache would require an authorised rebuild. Proposed correction: pin model and tokenizer to one revision, include an encoder version/manifest, validate row count/dimension/finiteness and use atomic replace. An unchanged ordered corpus fixture verifies alignment when the fake encoder groups languages.

### D11 — Medium — resumable ingestion trusts stale files and can replace a complete corpus with a partial one

**Location:** `src/fetch_booklets.py:85–107`, `src/fetch_booklets.py:190–253`; `src/fetch_eval_data.py:31–69`.

**Root cause:** cached PDFs larger than 1 KB skip magic validation; cached text is accepted by size with no source fingerprint. `--limit` and extraction failures still write the canonical `corpus.json`, and missing documents still return success. `--skip-fetch` does not force re-extraction. The dataset downloader replaces the old destination before validation; verification warns on row-count changes and does not actually reject unofficial label values.

**Reproducer:** write 2,006 bytes of HTML to a temporary `.pdf`; `fetch_pdf` returns `cached` without network access. For corpus replacement, mock `list_booklets` with two entries and `build_corpus` with one record, run `main(['--limit','1','--skip-fetch'])` with a temporary output path: it replaces an existing full-corpus sentinel and returns 0. Expected: validate cached file identity and make partial output explicit, preserving the canonical corpus on failure.

**Impact:** future fetch/smoke commands can invalidate coverage and indexes; the current 60-document corpus/coverage is intact. **Status:** not fixed. Proposed correction: validate cache headers and fingerprints; write temporary outputs; require complete coverage before replacing the canonical corpus, or require a separate output for partial builds. No real corpus or PDF was altered during this audit.

### D12 — Medium — Ollama paths do not honour the stated experiment configuration

**Location:** `src/nli_judge.py:302–338`, `src/ablation_dev.py:176–182`, `src/eval_e2e.py:290–386`, `src/eval_e2e.py:498–510`.

**Root cause/verification:** mocked Ollama traffic receives `options={'temperature':0.0}` with no `num_predict`, even though eval metadata records `max_tokens=400`. The ablation preflight checks `OPENAI_BASE_URL` and `/v1/models` even for `--backend ollama`. Translation availability probes a hard-coded localhost URL, ignoring the configured URL; empty translations silently become the original claim but are reported as translated. Hybrid lexical retrieval still receives the original claim while dense retrieval receives the translated query. Translation-cache keys omit model/prompt identity.

**Expected:** backend-correct readiness and generation limits; truthful translation status and explicit mixed-query policy. **Impact:** comparisons across backends or translated runs are not controlled as documented. No real Ollama/translated quality run was found, so the recorded OpenAI/untranslated results are not invalidated by this finding.

**Status:** not fixed. Request construction and wrong preflight target were confirmed with mocks; translation control flow was inspected, not run against a live service.

### D13 — Medium — Docker targets override advertised endpoint/environment choices

**Location:** `Makefile:50–77`, `compose.yaml:20–27`; README Docker setup.

**Root cause:** `run` and both Apertus Docker eval recipes hardcode `OPENAI_BASE_URL`, overriding even `make ... OPENAI_BASE_URL=http://custom:9999`. Compose does not forward `PROMPT_CONFIG` or `JUDGE_TIMEOUT_S`. Conversely, `make smoke` inherits `LLM_BACKEND`, so it is only lexical in a clean/default environment; `LLM_BACKEND=openai make smoke` is not a no-model smoke run.

**Verification:** `make -n run eval-apertus-docker OPENAI_BASE_URL=http://custom:9999` prints `host.docker.internal:8080`. No Docker workload was launched. Expected: explicit documented overrides take effect and smoke intent is unambiguous.

**Impact/status:** not fixed; historical default endpoint runs are unaffected. Proposed correction: use an overridable Make variable for the container endpoint and forward the intended settings, with a deliberate decision whether smoke enforces lexical or is explicitly overrideable. Linux host-gateway routing to a loopback-only host server is additionally unverified; name resolution alone is not connectivity evidence.

## Potential defects requiring verification

- **Gold relevance is a heuristic, not verified evidence sufficiency.** `eval_e2e.py:74–125` marks a passage gold if any of three short probes matches, even if the decisive sentence is elsewhere. A synthetic common-introduction-only passage is accepted (audit JSON). Shingle fallback permits secondary passages with 30% coverage once one reaches 50%. This confirms that the report's strict “lower bound” interpretation is unjustified: false positives can raise scores as well as false negatives lowering them. How many real labels are wrong remains unmeasured; do not silently tighten the matcher or change the denominator.
- **Actual cache/model revision mismatch:** not established. Model loading would be needed to compare current encoder output; a stable old revision may make the cache entirely correct. No such inference was authorised.
- **Actual empty formatted evidence:** one corpus passage exceeds 2,000 characters (maximum 2,081); baseline formatting can drop an oversized first passage and everything after it. The eval checks non-empty passage lists, not the rendered evidence block. Whether any saved dev item ranked this passage first cannot be determined from saved NLI records. Chunking also exceeds its advertised 500-character bound on 351 passages. Fixing chunking/formatting changes experimental inputs and requires a new version.
- **Adapter failures are swallowed** in `Retriever.set_default_language`. A failing model adapter can leave previous mutable model state active; no actual failure on this checkpoint was observed. Concurrent calls are not protected, though the current CLI is serial. Unknown `RETRIEVAL_CONFIG` strings silently select legacy while recording the misspelled name.
- **Prompt injection and citations:** retrieved text/claims are untrusted model input; there is no evidence-snippet substring validation. A valid class does not establish that its quotation is present or supports it. No exploit or measured hallucination rate is claimed.
- **Numerical and input edges:** empty corpus construction fails before an actionable corpus error, `top_k<=0` is not validated, and ties via `argpartition`/`argsort` have no explicit stable document-ID rule. `cosine_sim_matrix` still silently drops all but the first query if misused; current callers inspected here are single-query, and eval uses separate batched matmul. These are hardening opportunities, not demonstrated changes to current results.
- **Dependency/platform execution:** neither a fresh native environment nor an image build, Linux x86-64, Docker Desktop, file ownership under bind mounts, nor container-to-host connectivity was tested in this audit. Static inspection finds no lexical fallback in the OpenAI path and no MLX dependency in the image.

## Evaluation integrity assessment

### What the artefacts support

All 16 saved NLI result files align with the expected dev prefix and have consistent `correct` flags, confusion counts and existing scorer summaries. The eight ablation summary entries match their referenced files. The ten full 60-item Apertus runs reproduce the reported accuracy/F1 values under the existing parser/scorer assumptions:

| Configuration | Evidence | Correct / n | Errors | Stored accuracy / macro-F1 |
|---|---|---:|---:|---:|
| baseline | retrieve-v2 | 29/60 | 0 | .483 / .466 |
| baseline | oracle | 26/60 | 0 | .433 / .393 |
| t0, each of two runs | retrieve-v2 | 27/60 | 0 | .450 / .436 |
| strict | retrieve-v2 | 27/60 | 2 | .450 / .302 |
| select | retrieve-v2 | 29/60 | 0 | .483 / .467 |
| t0, each of two runs | oracle | 31/60 | 0 | .517 / .452 |
| strict | oracle | 27/60 | 1 | .450 / .243 |
| select | oracle | 25/60 | 0 | .417 / .365 |

Errors remain in these denominators as false negatives for the gold class; they are not automatically neutral. The numeric mapping is consistent across project label helpers and stored gold/prediction codes. This audit checked the local snapshot and project specification, not a newly fetched external dataset release.

The same two t0 repeat pairs agree on all 60 labels and recorded usage per mode. Oracle equivalence recomputation yields zero mismatches for t0/fill_only and select/window_only, and window selection changes 29/60 oracle inputs. Retrieve-mode twin equivalence follows from code: window is never applied in that path, and all fields consumed by the renderer and generation settings are equal. Boundary fixtures confirm it even for oversize evidence. Oracle equivalence assumes short normal language tags and the 1,900-character cap; arbitrary long metadata or changed caps can invalidate it.

`select` retrieve improves items **26 and 40**, both gold neutral, entailment→neutral. Oracle improves **5 and 8** (gold entailment); worsens **19,25,28,30** (gold neutral, neutral→entailment), **36,39,40** (gold neutral, neutral→contradiction), and **53** (gold contradiction, contradiction→neutral). These are historical within-dev observations, not new predictions from this audit.

### What the artefacts do not support

- Correct BM25 versus dense/hybrid rankings, or the general conclusion that booklet routing is structurally harmful: D01 confounds the lexical systems. The reported `doc_routing_top1` measures the final top passage's document, not the internal stage-one route; the separate diagnostic is lexical-only on a different 60-item sample.
- A deployment-level R@5 of .2122: `emb_v2` and dense hybrid queries use **gold reference language** to select adapters (`eval_e2e.py:477`, `500`). This is documented as an oracle adapter in `main.py`, but the aggregate report's “claim only/no gold information” language is too strong. Production uses a claim-language heuristic. No gold reference text or booklet filter enters production retrieval; choosing the corpus from benchmark booklet URLs is a benchmark scope choice, not hidden passage leakage.
- A strictly untouched held-out system score: full-set retrieval comparisons already informed development, and exact dev/eval duplicates exist. No reserved-set model scoring or configuration selection was performed by this audit.
- Exact historical prompt/encoder identity or strict-parser accuracy. NLI files omit raw replies, full prompts/evidence IDs/hashes, original dataset row IDs, dataset/corpus hashes, immutable model revisions and code/runtime versions. Claim text is truncated to 300 characters. `top_k` is not saved in eval metadata. The new audit hashes identify today's snapshot, not necessarily each historical input.
- Perfect oracle evidence: oracle mode truncates references to 1,900 characters and may select another window. It isolates retrieval removal, not an unlimited-evidence upper bound. Repeated t0 agreement within one session does not prove determinism across machines/sessions or unrecorded arms.
- General multilingual coverage: the new corpus contains DE/FR/IT, no RM; the production detector has no explicit RM branch. The legacy corpus contains RM, but modern-corpus RM quality is unmeasured.

## Test coverage assessment

The original 44 checks cover mappings, selected parser cases, prompt registry and render equivalences, plus an unreachable endpoint. They omit all demonstrated BM25/split/metric/cache/accounting bugs. `test_pipeline.py` prints model-backed smoke outputs but has no assertions; it is not an independent retrieval accuracy test and was not run here because it loads weights.

Some guards repeat implementation constants: the “original prompt verbatim” check compares `build_chat` to the same current `SYSTEM_PROMPT`, checks a suffix and keyword, and never stores an independent historical prompt snapshot. It cannot prove byte identity against a previous commit. The existing unreachable-port check is also not fully hermetic; new endpoint tests mock HTTP.

New 20-test suite covers exact identity and malformed IDs, inference failure accounting, all valid labels, CLI status/report persistence, ablation output ownership and partial failure, safe output writing, hand-calculated classification/retrieval metrics, RRF arithmetic, language-group index alignment, order-sensitive cache keys and render boundaries. The fake encoder verifies alignment without creating a `Retriever` model instance. These tests deliberately do not bless the unresolved parser or BM25 semantics.

Executed after corrections:

- `make test`: original **44 checks**, new **20 tests**, and all Python files compiled successfully.
- `.venv/bin/python -m unittest discover -s src -p test_audit.py -v`: **20 passed**.
- `python3 src/audit_offline.py`: **16 historical NLI files** checked; corpus coverage and hashes emitted; five parser counterexamples and other unresolved defects reproduced.
- `diag_evidence_ablation.py` on the exact eight-run artefact: passed, 60/60 oracle twins, 29 windows moved, two retrieve flips and ten oracle flips.
- Same 20 tests against a temporary copy of baseline source: non-zero, **10 failures / 5 errors** (including invalid-ID subtests and the previously absent output API). This is a reproduction check, not an unexplained final test failure.
- Shell syntax, Make dry runs, installed metadata/marker checks, final whitespace diff checks passed. No dependency resolver install/build, endpoint inference, or expensive retrieval test was run.

## Changes made

| File | Behavioural consequence |
|---|---|
| `src/nli_judge.py` | D04: exact non-empty advertised model identity at startup. |
| `src/main.py` | D05: retain failed claims, reject empty-evidence/error verdicts, non-zero CLI exit on failure. |
| `src/eval_nli.py` | D07: explicit exclusive output path and microsecond default filenames; scoring unchanged. |
| `src/ablation_dev.py` | D07: own output paths, metadata checks, abort partial comparisons. |
| `src/test_audit.py` | 20 independent offline/regression tests. |
| `src/audit_offline.py` | Read-only integrity and defect reproduction script. |
| `Makefile` | Run the new tests in native/container offline test targets. No container target was executed. |
| `the retired one-off audit JSON` | New audit evidence; no historical artefact replacement. |
| `REPORT_HACKAPERTUS_OST.md` | Audit caveat/link above historical claims; numbers retained. |
| `docs/research_integrity_history.md` | This report and proposed semantic corrections. |

No commits, package changes, external repository edits, model downloads, historical result edits or cleanup/deletions were made. No change was made to `example_claims.json`, default prompts, embeddings, adapters, scoring formulas or split membership. The corrected endpoint check may reject previously tolerated model aliases until an exact advertised ID is explicitly configured.

## Reproduction commands

From the repository root, safe with installed dependencies and the current cached artefacts:

```bash
make test
.venv/bin/python -m unittest discover -s src -p test_audit.py -v
python3 src/audit_offline.py
(cd src && python3 diag_evidence_ablation.py --ablation ../data/ablation_20261010_122340_openai.json)
.venv/bin/python -m pip check
bash -n src/run.sh
make -n run eval-apertus-docker OPENAI_BASE_URL=http://custom:9999
git diff --check
git status --short
```

`audit_offline.py` prints JSON; redirect only to a new filename if retaining another snapshot. Its optional-data requirements are the existing eval set, corpus, cache, NLI files and named ablation. It performs no downloads, model construction or ranking optimisation. Missing inputs should be restored from a separately preserved snapshot, not silently fetched as an equivalent dataset version.

Safe missing-evidence diagnostic reproducer:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, 'src')
from diag_evidence_ablation import compare_runs, part_b_recorded
print(compare_runs({'items':[{'index':1,'pred':'neutral'}]},
                   {'items':[{'index':2,'pred':'contradiction'}]}))
print(part_b_recorded({}))
PY
```

**Requires explicit user approval; not executed:** start `make serve-apertus` in a separate terminal, with MTPLX memory usage considered, then run the native venv client below to smoke-test strict endpoint identity. The server keeps several GB resident; historical dev latencies suggest seconds of inference for three items, plus model startup and retrieval initialisation. Budget roughly 1–3 minutes; actual runtime is unverified. Stop only that server with Ctrl-C afterwards.

```bash
# Terminal A, after approval:
make serve-apertus
# Terminal B, after approval, from repo root:
(cd src && ../.venv/bin/python eval_nli.py --split dev --limit 3 \
  --backend openai --evidence oracle --prompt-config baseline \
  --out ../data/eval_results_postaudit_identity_smoke.json)
```

This entailment-only prefix is a plumbing test, not quality evidence. It does not tune or score the reserved split. A Docker rebuild/native environment repair requires its own approved resource budget; no exact runtime is established here.

## Prioritised follow-up tasks

1. **Agree the evaluation contract before further quality claims.** Decide strict label parsing, full-precision macro-F1, duplicate handling and what “held out” can still mean. Preserve the original dataset/splits and name any new protocol/version. Save raw replies and immutable input/output provenance on all new runs.
2. **Repair BM25 under a new retrieval version.** First use the symmetric-token fixture and existing dev-only sample to verify the intended tokenisation. Audit gold-match precision on a small predeclared dev sample. Do not optimise knobs using the already exposed 1,428 rows or overwrite the historical six-system benchmark.
3. **Restore reproducible execution and trustworthy diagnostics.** Reconcile macOS/container requirements, add immutable encoder/cache manifests, make missing diagnostic evidence fail explicitly, then perform an approved tiny real-endpoint check of the conservative fixes. Address D11–D13 before relying on ingestion, Ollama or custom Docker settings.

Next specific experiment: a predeclared paired **dev-only BM25 preprocessing check**, raw versus symmetric-normalised tokens with every other setting fixed, using no model and a separately named artefact. It would determine the size and direction of D01 on development queries without changing production or treating a held-out rerun as fresh validation. It was not performed here.

## ChatGPT Handoff

1. **Current repository health:** executable exploratory prototype with passing offline tests; not ready for an independent quality/generalisation claim. Native defaults remain lexical/legacy/baseline; `make run` explicitly uses OpenAI/v2/baseline.
2. **Confirmed bugs:** High D01 tokenisation, D02 duplicate holdout, D03 invalid-label acceptance, D04 model-ID check, D05 CLI failure accounting, D06 native dependencies. Medium D07 ablation ownership, D08 diagnostic false assurance, D09 subsampling/F1, D10 cache compatibility, D11 ingestion, D12 Ollama, D13 environment overrides.
3. **Fixes applied:** D04/D05/D07 only, with regression tests; Make offline test targets include them. Scientific behaviour and old artefacts remain intact.
4. **Evidence:** 44 original checks + 20 new tests pass; 20 new tests also pass in `.venv`; 16 saved NLI files checked. Coverage remains 1,470/1,488, and `(16618,768)` cached vectors are finite. No new model predictions.
5. **Potentially invalidated measurements:** lexical-containing retrieval comparisons do not measure the intended BM25; future 1,428-row scores cannot be independent holdout estimates. Historical strict-parser validity is unknowable without raw outputs. Only two lexical F1 displays show the independently measured 0.001 rounding discrepancy; 60-item Apertus headline arithmetic matches.
6. **Prediction changes:** none from this audit. Historical select flips verified: retrieve improves 26/40 (gold neutral); oracle improves 5/8 (gold entailment), worsens 19/25/28/30/36/39/40 (gold neutral) and 53 (gold contradiction).
7. **Uncertainties/next three actions:** agree a versioned evaluation/parser contract; verify corrected BM25 on dev only; repair dependency/provenance/diagnostic guarantees before an approved endpoint smoke. Actual cache drift, false-positive gold rate and cross-platform execution remain unverified.
8. **Files/artefacts:** this report; `src/test_audit.py`; `src/audit_offline.py`; `the retired one-off audit JSON`; `data/eval/mnli_swiss_v1.1.jsonl`; `data/booklets/corpus.json`; `data/cache/emb_92f67a425caeafc5.npy`; `data/eval_results_full_benchmark.json`; `data/ablation_20261010_122340_openai.json` and its eight referenced per-run files; the two `082336`/`082936` baseline NLI files.
9. **Execution status:** no model, weight loader, model-serving process or Docker workload started. MTPLX was already running and was left untouched. Port 8080 had no listener at inspection. No commits made.
10. **Decisions requiring approval:** changes to parser/scoring/split/retrieval semantics and fresh validation protocol; model loading/inference, embedding rebuilds and heavy Docker work. No permission question blocks delivery of this completed audit; these are the boundary for the next iteration.
