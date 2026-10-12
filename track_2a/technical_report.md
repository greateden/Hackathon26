# Technical report — Swiss voting-booklet NLI

**Track:** 2A, OST. **Event:** Online. **Status:** submission draft, 12 October
2026. Team names and demo link remain to be supplied. This Markdown is not yet
the final, at-most-six-page PDF.

## 1. Summary

The application accepts a specified official voting booklet and a claim. It
returns entailment, neutral or contradiction with source passages and page
references. The current submission implementation targets Apertus v1.5 8B via
an HTTP endpoint. It compares a full-document baseline with within-booklet
retrieval. In an 81-example, nine-language-pair development comparison using
local v1.5 6-bit MLX at 81,920 tokens, retrieval achieved accuracy 0.802 and
macro-F1 0.807, versus 0.519 and 0.479 for full-document inference. Retrieval
used 96.3% fewer input tokens. Of 162 planned calls, 161 completed; one
retrieval reply hit the output limit and counts as an error. These are
exploratory, historically exposed data, not an independent holdout. The earlier
nine-example comparison and v1.1 experiments are retained as historical evidence.
A separate one-example Docker smoke used CSCS Apertus v1.5 70B and passed the
application acceptance checks; it is deployment evidence, not an accuracy result.

## 2. Architecture

`make run` builds the CPU application and starts the official model service in
Docker. `SUBMISSION_MODE=external` instead uses a provisioned official endpoint
without starting a local GPU service. The external application path has completed
one CSCS-backed Docker smoke on Apple Silicon. The default managed 8B service,
self-contained model startup and cross-platform execution remain unverified.
The JSON request
identifies a PDF and declares booklet and claim languages independently.
Poppler extracts text with physical page boundaries. Baseline A sends all
extracted pages. Approach B divides those pages into contiguous chunks and
uses SentenceSwissBERT mean-pooled cosine similarity to select five passages
from that document only. Both query and passage adapters use the known
booklet language. This is legitimate supplied-input metadata; no gold evidence
text enters extraction, ranking or judgement. All nine DE/FR/IT combinations
are accepted, but acceptance is not proof of classification quality.

Both arms share the same NLI system/user templates and strict label parser.
The evidence payload is the experimental difference. The returned label codes
are 0 entailment, 1 neutral and 2 contradiction. Physical page and PDF hash
references identify supplied evidence. A generated snippet is marked verified
only if it occurs in a supplied passage after whitespace and discretionary
soft-hyphen normalisation. Ordinary hyphens, punctuation and substantive text
remain significant; verification never searches unsupplied passages.
Unverified citations remain explicit rather than being fabricated.

## 3. Use of Apertus

Submission target: `swiss-ai/Apertus-v1.5-8B`, inference only, no fine-tuning.
The endpoint must advertise the configured `LLM_NAME`; that check alone
cannot attest the server's underlying weights. Temperature is zero, seed is
20261011, output allowance is 512 tokens, and the current client explicitly
disables thinking in both tokenisation and generation requests.
The same settings apply to both arms. The paired native runs record the loaded
model class and revision; in the earlier nine-row comparison, all 13 replies
completed at both context limits are byte-identical. This is limited
repeatability evidence, not a cross-platform
determinism guarantee or verification of the official Docker endpoint.

The submission configuration uses `/tokenize` before generation. Full-document inputs that
exceed the configured context budget are recorded as errors, never silently
truncated. Reported prompt usage must match the preflight count. Authentication
and endpoint configuration follow `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`.
The [official model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)
describes the vLLM serving path, which remains unverified here.

The verified Mac development path uses the third-party text conversion
`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`, revision
`9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`, 6-bit affine quantisation,
group size 64, served by mlx-lm 0.32.0. The loader records the Apertus model
class and the checkpoint configuration. The MLX HTTP server lacks `/tokenize`,
so the earlier direct HTTP smoke used optional preflight; the paired native
experiment uses the model's cached tokenizer for required preflight. For the
saved successful example, an observational
server wrapper captured the complete prompt token IDs and verified the 1,007-token
count independently. Thinking was disabled at server startup; the earlier
attempt reached the 512-token output limit and remains a recorded failure.
See [evidence and original-byte hashes](docs/evidence/README.md). No model
weights or inference settings were changed during repository cleanup.

## 4. Data

The evaluation input is the official MNLI-over-Swiss-Voting-Booklets v1.1
snapshot under `data/eval/`, regenerated by `src/fetch_eval_data.py`. Original
booklet PDFs come from the dataset's Federal Chancellery URLs. References and
labels are used only for scoring; the provided booklet is an inference input.
The existing dataset attribution records MIT; source booklet attribution must
be retained. No personal-data collection was added.

The fresh plan records the dataset SHA-256 and all selected row IDs in
`docs/evidence/paired_dev_plan_20261011.json`. Of the current 60 historical dev
rows, 24 have normalised claim/reference/label duplicates in the 1,428-row
complement; 25 share claims and 46 share references. These are content checks,
not model results. The complement is not an independent held-out set. The
nine-row paired sample covers every language pair, with three rows per label;
three of its rows have duplicate triples in the complement. The subsequent
81-row plan selects three examples for each of the nine language-pair/label
cells, without exact claim/reference component overlap with the historical
60-row dev set. Both samples are development work: historical experiments
already exposed the full corpus. An independent final evaluation requires new
data.

## 5. Evaluation and observed results

The new `experiment_runner.py` provides offline preflight, resumable native
runs and a separately requested real Docker smoke. It records accuracy,
macro-F1, per-class results, errors, token coverage, runtime, citation validity
and reference shingle coverage. The latter is a
40-character lexical coverage proxy; it cannot establish semantic evidence
correctness. Arms use identical examples and alternate order. Context failures
count as failed predictions and remain visible in the attempted-row denominators.
Missing rows remain explicit; a second comparison uses only successful pairs.
Append-only attempt logs retain earlier failures and raw replies. Exact messages,
PDF/text hashes, source hashes and server sessions make resumption auditable.
The cached-only MLX wrapper records the actual loaded class/revision and uses
its own tokenizer for preflight. The earlier nine-row and grouped 81-row native
runs used mlx-lm 0.32.0 and the 6-bit revision in §3, with encoder revision
`7a91fa8a01af56c1f06060f7af3698ef5619e41c`.
The old non-resumable paired CLI was removed; its plan and coverage helpers remain.

| Configuration | Model / evidence / split / sample | Observed result | Provenance |
|---|---|---|---|
| Baseline A, grouped 81 | v1.5 MLX 6-bit; complete PDF; content-grouped dev n=81; 80K | Accuracy 0.519, macro-F1 0.479; 81/81 completed | `data/experiments/v15-grouped81-80k/` |
| Approach B, grouped 81 | Same model and rows; top-five within-PDF; 80K | Accuracy 0.802, macro-F1 0.807; 80/81 completed, 1 output-limit error | same directory |
| Baseline A, 32K | v1.5 MLX 6-bit; complete PDF; dev n=9 | Accuracy 0.111, macro-F1 0.095; 4 completed, 5 context failures | `data/experiments/v15-paired/` |
| Approach B, 32K | Same model and rows; top-five within-PDF | Accuracy 0.889, macro-F1 0.886; 9 completed | same directory |
| Baseline A, 80K | v1.5 MLX 6-bit; complete PDF; same dev n=9 | Accuracy 0.333, macro-F1 0.167; 9 completed, all neutral | `data/experiments/v15-paired-80k/` |
| Approach B, 80K | Same model and rows; top-five within-PDF | Accuracy 0.889, macro-F1 0.886; 9 completed | same directory |
| Prompt `current_v1` | CSCS Apertus v1.5 70B; frozen retrieved evidence; exposed dev n=27 | 23/27 correct, macro-F1 0.850; 17/27 verified citations; 34,342 input tokens | `docs/evidence/prompt_pilot27_results_v1.json` |
| Prompt `teammate_rules_v1` | Same model, rows and evidence | 23/27 correct, macro-F1 0.853; 18/27 verified citations; 40,795 input tokens | same file |
| Docker submission smoke | CSCS Apertus v1.5 70B; retrieved; FR→FR; n=1 | Exit 0; entailment (0); verified page 19; 785 input / 80 output tokens; inference 1.23 s, total execution 24.06 s; no lexical fallback | `data/experiments/docker-verification-cscs-20261012T093746Z-49ed3309/` |
| Local v1.5 smoke | MLX 6-bit; retrieved; DE→DE; n=1 | Entailment (0); verified page 15; 1,007 input / 71 output tokens; inference 1.384 s, retrieval 2.374 s | `docs/evidence/v15_local_smoke/` |
| Extraction/retrieval smoke | SentenceSwissBERT; full vs top-five within-PDF; paired dev n=9; no NLI model | Mean reference shingle coverage 0.921 full, 0.204 retrieved | `docs/evidence/booklet_retrieval_smoke_20261011.json` |
| Historical NLI | Apertus v1.1 4B MLX INT4; global `retrieve-v2`; dev n=60 | Accuracy 0.483, macro-F1 0.466 | `data/eval_results_20261010_082336_dev_openai_retrieve-v2.json` |
| Historical diagnostic | Same v1.1 model; oracle reference; dev n=60 | Accuracy 0.433, macro-F1 0.393 | `data/eval_results_20261010_082936_dev_openai_oracle.json` |

**Prompt-only pilot.** The two prompts used byte-identical top-five evidence,
temperature zero, the same strict parser and alternating call order. All 54
calls completed. Three predictions changed: row 661 improved, row 169 worsened,
and row 1060 remained wrong under both prompts. The refined prompt did not
improve accuracy and used 18.8% more input tokens; the small Macro-F1 and
citation differences do not establish an improvement. `current_v1` therefore
remains the production default. This was a small, already exposed development
sample, not independent held-out evaluation. The compact evidence summary links
to the ignored raw directory and records hashes without copying its records.

**Grouped 81-row result.** The frozen plan has nine claims for every claim/booklet
language pair and 27 examples per NLI label. Preflight passed; the run ended
`COMPLETE_WITH_ERRORS` (161/162 completed, one failed, none missing), with no
retries. Errors count against accuracy. Full-booklet inference was correct on
42/81 examples; retrieval was correct on 65/81, a 28.3-point gain. The
successful-pair-only comparison (80 pairs) gives accuracy/macro-F1
0.512/0.476 for full and 0.812/0.812 for retrieval. Retrieval exceeded full
accuracy in each of the nine language pairs, although each pair has only nine
examples. The earlier nine-row full-booklet *all-neutral* result did not
generalise literally: on 81 rows, full inference correctly identified 9/27
entailments, 27/27 neutral examples and 6/27 contradictions. Its strong neutral
bias remains visible.

| Grouped 81-row metric | Baseline A: full | Approach B: retrieved |
|---|---:|---:|
| Correct predictions | 42/81 | 65/81 |
| Accuracy / macro-F1 | 0.519 / 0.479 | 0.802 / 0.807 |
| Verified contiguous source citations | 27/81 | 49/81 |
| Reported prompt tokens (81 calls) | 2,774,950 | 102,976 |
| Mean call latency, successful calls | 31.34 s | 3.61 s |
| Sum of call wall time, including errors | 2,538.52 s | 298.80 s |

Retrieval reduced reported prompt tokens by 96.3% (about 27 times fewer) and
had about 8.7 times lower mean successful-call latency on this machine. The
timings include retrieval work where applicable but exclude server setup and
initial model loading. Prefix caching and run order limit causal latency claims.
The strict citation test accepted 33.3% of full replies and 60.5% of retrieved
replies; this checks text provenance, not whether the citation supports the
label. On row 507 (DE claim, FR booklet), retrieval generated an excessively
long snippet and reached `max_tokens=512`, producing `incomplete_completion`;
the recorded result has no usable label and was not rescued from a partial
reply. All other 161 calls completed. The saved `manifest.json`,
`events.jsonl`, `predictions.jsonl`, `preflight.json` and `summary.json`
preserve the exact sample, configuration, errors, model revision and measurements.

The original result directories remain byte-for-byte unchanged (14 files).
An [offline audit](docs/evidence/v15_paired_analysis_20261011.json) records their
SHA-256 hashes, checks and corrected telemetry separately. No inference was
rerun for this analysis. Historical results cannot substitute for a submission
reproduction.

| Context / arm | Completed / attempted | Input tokens reported | Output tokens reported | Original verified citations | Sum of call wall time |
|---|---:|---:|---:|---:|---:|
| 32,768 / full | 4/9 | 81,368 (4 rows) | 494 (4 rows) | 0/9 | 56.04 s |
| 32,768 / retrieved | 9/9 | 9,899 | 1,189 | 3/9 | 32.77 s |
| 81,920 / full | 9/9 | 287,025 | 1,216 | 3/9 | 232.94 s |
| 81,920 / retrieved | 9/9 | 9,899 | 1,189 | 3/9 | 33.62 s |

At 80K, retrieval used about 29 times fewer input tokens. Reported inference
time summed to 231.49 s full and 24.03 s retrieved; call wall time also includes
retrieval and tokenisation, but excludes server startup and initial encoder
construction. Prefix caching was active. These are single-machine observations,
not controlled latency benchmarks. At 32K, rows 192, 171, 533, 187 and 555 failed
preflight: their input counts plus the 512-token allowance exceeded 32,768.
No completion was requested for them. On the four successful pairs alone,
full accuracy/F1 was 0.250/0.200 and retrieval 1.000/1.000; that subset contains
no entailment examples and is not comparable to the nine-row 80K result.

**Earlier nine-row full-booklet neutral collapse.** All nine raw 80K replies explicitly say
neutral, and the parser preserves them. All messages reconstruct exactly from
the saved claims and passages; full-page hashes match the manifest. Both arms
share templates, model, temperature, seed, output limit, parser and disabled
thinking. The evidence payload alone differs within each run; context is the
only recorded configuration difference between runs. All 18 prompts match
across runs, and all 13 replies that completed at 32K recur byte-for-byte at
80K. Reported input token counts match preflight, and all completed replies stop
normally. No application truncation, missing-claim or neutral-fallback bug was
found. Long-input evidence use is a plausible explanation, not an isolated
cause: row 1328 overlooks page-47 palm-oil restrictions, while rows 1095 and
1365 quote recommendations yet deny that recommendations are present.

**Citation failures.** Whitespace matching already tolerates line breaks and
carriage returns. One confirmed false negative is row 1095/full: page 15 splits
`abitazioni` with U+00AD and a newline. The verifier now removes only such
within-word discretionary soft hyphens before matching. The saved quotation
passes this offline check; the original citation scores above are retained.
The other failures justify rejection: rows 979/full, 1328/full and 555/retrieved
give English explanations instead of source quotations; 192/full and
192/retrieved merge or omit text; 979/retrieved reorders text and changes `les`
to `the`; 187/full paraphrases; 1365/full omits part of the law title.
Row 1328/retrieved omits a footnote, parenthesis and heading as well as repairing
an extracted word. Row 533/retrieved spans chunks and rewrites the final clause.
Row 1365/retrieved adds a sentence beginning absent from its selected chunk,
although present elsewhere on the page. These are not all hallucinations, but
none is a verified contiguous quotation from supplied evidence. No fuzzy
matching, punctuation deletion or search outside retrieved passages was added.

**Accounting defect.** The shared historical scorer reads top-level `usage`
and `retrieval_s`; paired logs nest them under `result`. This produced incorrect
zero scalar token totals and null retrieval timing, despite correct nested
token totals. A paired-record adapter now fills both ordinary and
successful-pair summaries consistently, with measured/missing row counts and
null totals when usage is absent. Preflight-only counts are not counted as
generation usage. Classification scoring is unchanged.

**Prediction review.** At 80K, retrieval improves rows 1095, 1328 and 1365
(gold contradiction) and 192 and 187 (gold entailment); rows 979, 533 and 555
remain correctly neutral. Row 171 changes from neutral to contradiction, both
wrong against gold entailment. Its verified page-33 quotation says rejection
ends the amendment and listed measures; the model incorrectly treats this as
contradicting their continuation on approval. The relevant conditional is
present in the retrieved evidence, so missing evidence cannot explain that
specific reasoning error. Gold labels remain unchanged. Row 192 also warns
against equating accuracy with sound reasoning: its gold-matching entailment
reply confuses a referendum committee's Covid-law rejection with the
government's approval, although the booklet's initiative-rejection evidence
is available in the selected page-144 passage.

## 6. Limitations

Genuine local v1.5 MLX inference and one CSCS-backed Docker application smoke
are recorded. The latter passed all eight application acceptance criteria plus
the separate no-lexical-fallback check, but its single prediction is not an
accuracy measurement. Default managed 8B startup, a clean cold build, and
Windows/Linux execution remain unverified. The MLX tokenizer emitted a regex
warning in the original logs; its impact is unresolved and no tokenizer change
was made during cleanup. The 81-row grouped comparison and 27-row prompt pilot
are development comparisons, not independent benchmarks. Quantisation,
long-input attention, prompt placement and the tokenizer warning have not been
isolated experimentally. A verified quotation establishes textual provenance,
not entailment or correct attribution; short neutral citations may be only headings.
Text extraction omits image-only content and may lose layout semantics. Retrieval
can omit decisive evidence. Long full documents can exceed context limits.
Current development/complement contamination invalidates independent holdout
claims. Historical global retrieval rankings do not establish within-booklet
rankings. Oracle evidence is a judgement diagnostic, not Baseline A.

`PROMPT_CONFIG` historical variants change prompting/decoding or evidence
formatting, not the task definition: `baseline` uses T=0.1, `t0` uses T=0;
`strict` changes instructions, while `select`, `fill_only`, `window_only` change
selection/formatting. They are preserved in historical scripts and are not
implicitly applied to the new paired experiment. See the dated report for
unsuccessful strict prompting and withdrawn/confounded retrieval comparisons.

## 7. Reproducibility

Start with [docs/RUNNING.md](docs/RUNNING.md), configure `.env`, edit
`data/request.json`, and run `make run`. A clean application checkout needs no
legacy corpus. Docker supplies Python, Poppler and encoder dependencies. API
availability and initial image/encoder/PDF network access are prerequisites.
The current host is Apple Silicon with 128 GiB RAM; it is not a validated CUDA
v1.5 server. The successful CSCS smoke used Docker for the application and the
remote 70B endpoint, not the managed local model service. Run all commands from
`track_2a/`; the repository-root Makefile forwards there.

`make test` is the offline regression entry point. The submission contract
checks use model doubles, explicitly separate from real encoder/PDF smoke
results. On 12 October, both host and Docker runs passed 104 unit tests with no
failures, errors or skips; judge/label checks and source compilation also
passed, and the Docker image built successfully on Apple Silicon. The template's
`track_2a/` layout is now implemented. Final report PDF, team metadata, demo,
managed 8B execution and cross-platform validation remain outstanding. The
tracked data inventory is below the template's 100 MB ceiling; ignored local
corpora and model caches must remain outside the submission bundle.

## 8. Next steps

The completed [81-row plan](docs/evidence/paired_grouped81_plan_20261011.json)
contains three examples per language-pair/label cell (27 per label), selected
with seed 20261012 without consulting predictions. Connected components join
rows sharing a normalised claim **or** reference, irrespective of label.
Exclude every component touching the historical 60 dev rows and take one row
per remaining component. The local smoke claim has no exact dataset match.
There are 594 eligible components (1,281 rows); the selected 81 have no repeated
normalised claims/references or component overlap with dev. The plan records
IDs, dataset hash, exclusions and the complete selection rule. Its native MLX
run is reported in §5.

This broader comparison retains a frozen configuration, but is not an
independent holdout: historical retrieval work used the entire dataset, all
20 vote dates occur in dev, and exact matching cannot detect every translated
near-duplicate. It supports a retrieval advantage in this sample, not a causal
explanation or a generalisation claim. A final generalisation test needs new
vote/topic-disjoint, manually reviewed data. Keep errors in the denominator
and inspect citation/rationale validity separately from label accuracy.

To reproduce the native run from `track_2a/`, start a matching local server:

```bash
../.venv/bin/python src/serve_experiments.py --context 81920
```

Then run the frozen plan into a fresh directory:

```bash
../.venv/bin/python src/experiment_runner.py run --context 81920 --retries 0 --plan docs/evidence/paired_grouped81_plan_20261011.json --out data/experiments/v15-grouped81-80k
```

This was the 162-call experiment recorded in §5; it ran with no retries.
Stop the manually started server afterwards. Do not overwrite these recorded
results when changing prompts or token limits. Before submission, validate the
default managed `make run` on an NVIDIA host, review citation failures and the
one output-limit error, add team/demo metadata, verify licences and produce the
final at-most-six-page PDF. The managed Apertus 8B deployment remains unverified.

## License

Report: Creative Commons Attribution 4.0 (CC-BY-4.0), following the template.
Repository code and source-data licensing require final review.

## References

[Official project template](https://github.com/HackApertus/project-template),
[OST challenge](https://hackapertus.notion.site/track-2a-ost),
[submission portal](https://hackapertus.ch/online-hack/submissions).
The template and [Devpost rules](https://hackapertus.devpost.com/rules) were
accessible on 11 October. Devpost confirms the 16 October, 12:00 CEST deadline;
the template directs submissions to the event website, not Devpost. The
online-hack page yielded no readable text, and the challenge/portal pages
remained inaccessible through the verification tool. The v1.5 requirement and six-page limit are retained from the task
brief, not claimed independently reverified. The layout was checked against
template revision `09f8e9e2b588db3325869b23c6d5132f5c3756f7`. Historical
measurements and caveats are retained in [the archive](docs/archive/README.md).
