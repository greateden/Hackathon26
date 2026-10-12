# Retrieval quality and multilingual NLI over Swiss voting booklets

**Track:** 2A, OST · **Event:** Online · **Status:** submission draft, 12
October 2026. Team names and demo link remain to be supplied. This Markdown is
not yet the final, at-most-six-page PDF.

## Abstract

We study document-grounded natural-language inference (NLI) over official Swiss
voting booklets. The application accepts a specified booklet and a claim, then
returns entailment, neutral or contradiction with page-grounded evidence. A
previous 81-case development comparison found that within-booklet retrieval
outperformed full-booklet prompting (accuracy 0.802 versus 0.519) while using
96.3% fewer input tokens. We therefore ask whether stronger retrieval further
improves downstream NLI. On a separate frozen 81-case development sample, dense
SwissBERT retrieval achieved accuracy 0.827 and macro-F1 0.824. Hybrid reciprocal
rank fusion achieved 0.802/0.797, while proposition-aware reranking achieved
0.790/0.784 despite raising lexical reference Recall@5 from 0.580 to 0.716.
Paired changes were small and non-significant: proposition reranking produced
four gains, seven losses and 70 ties against the dense baseline. Manual analysis
attributes no single cause: decisive propositions were sometimes displaced,
stakeholders or proposals were conflated, the judge sometimes misread adequate
evidence, and the lexical reference proxy missed useful alternatives. The new
experiment provides no evidence that either experimental retrieval method
improves NLI accuracy. Dense within-booklet SwissBERT retrieval remains the
production default.

## 1. Research question and application

Swiss voting booklets are multilingual, structurally repetitive and often place
supporting and opposing arguments in the same document. Retrieval must therefore
find not only the topic but the correct proposition, number, condition and
speaker. Our research question is whether hybrid lexical–dense retrieval or
proposition-aware reranking improves classification over the existing dense
SwissBERT retriever.

`make run` builds the CPU application and addresses a configured Apertus v1.5
endpoint through `LLM_NAME`, `LLM_BASE_URL` and `LLM_API_KEY`. The request names
the official PDF and declares claim and booklet languages independently. Poppler
extracts physical pages; the current production path chunks only the supplied
booklet and retrieves five passages using SentenceSwissBERT mean-pooled cosine
similarity. Both query and passage adapters use the known booklet language. Gold
references and labels never enter extraction, ranking or judgement.

All experimental arms use the same NLI prompt, strict JSON label parser and
label codes: 0 entailment, 1 neutral and 2 contradiction. A citation is verified
only when its quoted snippet occurs in supplied evidence after conservative
whitespace and discretionary soft-hyphen normalisation. Verification establishes
textual provenance, not semantic support.

## 2. Model and experimental setting

The submission target is `swiss-ai/Apertus-v1.5-8B`, inference only. The local
experiments use the third-party conversion
`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit`, revision
`9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`, with 6-bit affine quantisation,
group size 64 and an 81,920-token context. The manifest records
`mlx_lm.models.apertus.Model`, temperature 0, seed 20261011, a 512-token output
allowance and disabled thinking. The retrieval ablation uses parser
`label-parse-v3.1-strict`; the earlier grouped and oracle studies use their
recorded parser versions. An endpoint model-name check does not attest the
server's underlying weights.

The evaluation source is the official MNLI-over-Swiss-Voting-Booklets v1.1
snapshot under `data/eval/`, with original Federal Chancellery PDFs. The current
60-row historical development split overlaps heavily with its complement, and
earlier work inspected the full corpus. All results are therefore exploratory
development evidence, not independent held-out estimates.

### 2.1 Cohorts and purposes

Three studies must not be conflated:

1. **Full booklet versus retrieval (n=81).** The content-grouped development
   sample compares complete-PDF prompting with top-five within-booklet dense
   retrieval. Its plan avoids exact claim/reference overlap with the historical
   60 rows, but the underlying corpus had already been exposed.
2. **Oracle diagnostic (n=19).** After observing the preceding results, 16
   errors and three controls were selected and supplied with annotated reference
   evidence. This diagnoses judgement under better evidence; selection makes it
   unsuitable for estimating general accuracy or an oracle gain.
3. **Three-arm retrieval ablation (n=81; 243 calls).** A separately frozen,
   class- and language-pair-balanced development sample compares A: dense
   SwissBERT, B: dense plus BM25 reciprocal rank fusion, and C: B followed by
   proposition-aware reranking. It excludes components exposed by the earlier
   grouped study, but is still drawn from the historically inspected dataset.

Every ablation row was located in its booklet by the exact 60-character
reference probe. This confirms corpus coverage for this sample, not semantic
sufficiency of the probe or retrieved passage.

## 3. Full-booklet and oracle baselines

The grouped experiment completed 161/162 calls; one retrieval reply reached the
output limit and remains an error. Full-booklet inference was correct on 42/81
cases, compared with 65/81 for retrieval. Retrieval reduced reported prompt
tokens from 2,774,950 to 102,976 (96.3%) and increased verified citations from
27/81 to 49/81. It also reduced mean successful-call latency from 31.34 s to
3.61 s on the development machine, although prefix caching and order prevent a
causal latency claim.

| Study and evidence | Sample | Accuracy | Macro-F1 | Verified citations | Status and provenance |
|---|---:|---:|---:|---:|---|
| Full booklet, v1.5 MLX | 81 | 0.519 | 0.479 | 27/81 | 81 complete; `data/experiments/v15-grouped81-80k/` |
| Dense top-five retrieval, same rows | 81 | 0.802 | 0.807 | 49/81 | 80 complete, one output-limit error; same directory |
| Oracle diagnostic, selected errors and controls | 19 | 0.842 | 0.846 | — | 19 complete; `data/experiments/v15-grouped81-oracle-20261012/` |

In the oracle diagnostic, 14/16 selected errors improved and two were unchanged;
among three controls, two were unchanged and one worsened. This shows that
reference evidence can resolve many already observed failures, but the
post-hoc, error-enriched sample cannot quantify an expected production benefit.
The lone worsened control also shows that better evidence does not guarantee a
correct judgement.

Earlier nine-row 32K and 80K comparisons remain historical evidence. At 80K,
retrieval scored 8/9 versus 3/9 for full-booklet prompting and used about 29
times fewer input tokens. At 32K, five full-booklet inputs failed preflight;
none was silently truncated. A 27-row prompt-only pilot on CSCS Apertus v1.5
70B produced 23/27 correct under both prompts, with three prediction changes and
18.8% more input tokens for the refined prompt. A one-example CSCS-backed
Docker smoke passed the application acceptance checks; it is deployment
evidence, not an accuracy estimate. Historical v1.1 results are retained in the
[archive](docs/archive/README.md) and do not satisfy the present v1.5 target.

The historical audit reconstructed every saved prompt and matched PDF and text
hashes. All nine 80K full-booklet replies were neutral, while all 13 replies
that completed at both context limits were byte-identical. No parser fallback,
application truncation or missing claim was found; reduced use of long evidence
remains a plausible mechanism rather than an isolated cause. A citation audit
found one conservative soft-hyphen false negative and otherwise rejected
non-contiguous, translated or rewritten snippets. It also corrected a reporting
adapter that had read nested usage fields as zero; saved predictions and
classification scores were unchanged. The original result directories remain
unaltered, with the audit and hashes under `docs/evidence/`.

## 4. Three-arm retrieval ablation

The frozen runner completed all 243 planned calls: 81 cases per arm, no errors,
failures, missing rows or retries. The sample contains 27 examples per NLI label
and nine per claim/booklet language pair across DE, FR and IT. Method A retrieves
dense SwissBERT candidates. B fuses dense and BM25 rankings with reciprocal rank
fusion. C proposition-reranks B's candidate set. Classification is scored over
all 81 rows per arm. Reference Recall@k uses annotated-string matching and must
not be interpreted as evidence correctness.

| Method | Correct | Accuracy | Macro-F1 | R@5 | R@10 | R@20 | Citation verified | Mean prompt tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · dense SwissBERT | 67/81 | 0.827 | 0.824 | 47/81 (0.580) | 0.778 | 0.852 | 42/81 (51.9%) | 1,215 |
| B · hybrid RRF | 65/81 | 0.802 | 0.797 | 50/81 (0.617) | 0.741 | 0.877 | 40/81 (49.4%) | 1,326 |
| C · proposition reranking | 64/81 | 0.790 | 0.784 | 58/81 (0.716) | 0.840 | 0.877 | 36/81 (44.4%) | 1,314 |

![Grouped bars comparing reference Recall@5 and NLI accuracy across methods A, B and C.](docs/figures/figure1_recall_accuracy.svg)

**Figure 1. Reference Recall@5 versus downstream NLI accuracy.** Percentages use
the same 81 paired cases per method. Source: recorded `summary.json` and
`retrieval_audit.json` in `data/experiments/retrieval-ablation-v1/`.

C increased R@5 by 11/81 cases relative to A, yet produced three fewer correct
labels. B likewise produced two fewer correct labels. Thus neither experimental
method improved NLI accuracy, macro-F1 or citation verification. Both also used
about 8–9% more prompt tokens per case than A.

### 4.1 Paired comparisons

| Transition | Later method wins | Later method loses | Ties | Exact two-sided sign test | 95% Wilson interval for win share among discordances |
|---|---:|---:|---:|---:|---:|
| A→B | 3 | 5 | 73 | p=0.727 | [0.137, 0.694] |
| A→C | 4 | 7 | 70 | p=0.549 | [0.152, 0.646] |
| B→C | 5 | 6 | 70 | p=1.000 | [0.213, 0.720] |

The tests condition on discordant pairs and are underpowered because only
8–11 pairs change. None supports a statistically significant difference, and
the intervals include equal win/loss probability.

![Stacked paired outcomes showing gains, losses and ties for A to B, A to C and B to C.](docs/figures/figure2_paired_outcomes.svg)

**Figure 2. Paired changes in classification correctness.** Each bar contains
81 paired cases; a win or loss refers to the later method. Source:
`paired_comparison.csv` and `summary.json` in the ablation directory.

![Two-panel chart comparing verified citation rate and mean prompt tokens per case.](docs/figures/figure3_grounding_cost.svg)

**Figure 3. Grounding and input-cost trade-offs.** Citation rates and mean
reported prompt tokens use 81 calls per method. Source: ablation `summary.json`;
totals were 98,387, 107,408 and 106,465 prompt tokens for A, B and C.

## 5. Paired failure analysis

A and C differ in correctness on 11 cases: C improves four and regresses seven.
The complete passage-by-passage analysis, including ordered passage IDs,
coverage, citation status and multilingual claims, appears in the
[supplement](docs/RETRIEVAL_ABLATION_PAIRED_ANALYSIS.md). The categories below
overlap and describe observed patterns rather than proven causes.

| Outcome | Rows | Main observation |
|---|---|---|
| Four improvements | 119, 432, 1026, 1178 | Rows 119 and 432 already contain decisive evidence under A, but A misinterprets it. Row 1178 is an explicit accept/reject polarity error corrected after reordering. Row 1026 is correctly contradicted by broad aid evidence even though no arm matches the annotated reference probe. |
| Seven regressions | 29, 297, 442, 455, 1344, 1401, 1475 | Four lose or demote a concise decisive proposition; three elevate counterarguments, another stakeholder or another proposal. Several still contain adequate evidence, so evidence selection alone is insufficient as an explanation. |

The observed error taxonomy is: (i) decisive proposition displacement or
demotion; (ii) stakeholder or cross-proposal contamination; (iii) model
interpretation, numerical or polarity errors despite adequate evidence; and
(iv) semantically useful evidence that the lexical reference proxy does not
credit. Numbers matter in row 1344 (10% versus 4%); recommendation polarity and
institutional attribution matter in rows 29, 1178, 1401 and 1475; stakeholder
attribution matters in rows 297 and 442; and detailed legal conditions matter
in row 455.

Recall and correctness changed largely independently. Relative to A, C improved
R@5 on 15 cases: 14 predictions were unchanged and one worsened. Of 62 cases
with unchanged recall, three improved, 55 were unchanged and four worsened. Of
four cases with worse recall, one improved, one was unchanged and two worsened.
Reference matching therefore neither captures all useful evidence nor measures
whether the decisive proposition is prominent, correctly attributed and
interpreted by the judge.

## 6. Discussion

The experiments support two conclusions. First, focused within-booklet evidence
is substantially more effective and cheaper than full-booklet prompting on the
earlier development cohort. Second, optimisation of a lexical reference-recall
proxy did not improve downstream NLI in the new cohort. The negative result is
operationally useful: hybrid and proposition-aware methods should remain
research arms rather than enter the production path.

The paired cases reveal an interface problem between retrieval and judgement.
A ranker can recover more text overlapping an annotation while displacing the
single sentence that resolves a number, negation or institutional position.
Conversely, the judge can fail despite receiving that sentence. Retrieval
evaluation should therefore add proposition-level sufficiency and attribution
checks, while judgement evaluation should control evidence order and isolate
polarity, numeric and stakeholder reasoning. These are hypotheses for future
tests, not causal findings from the present single runs.

## 7. Limitations and reproducibility

All model measurements are single runs on development data. The ablation has 81
cases, only 11 A–C discordances and no independent holdout. The oracle set was
selected after observing failures. Exact reference probes and shingle coverage
are lexical proxies; a verified citation proves source occurrence but not
support. Quantisation, prompt order, long-context behaviour and run-to-run
variance are not isolated. Extraction may lose layout or image-only content.
Managed Apertus 8B startup, a clean cold submission build, Linux/Windows
execution and cross-platform determinism remain unverified.

The local server log records two warnings. First,
`mlx_lm.server is not recommended for production` describes the development
server's limited security posture; the submission is intended to use a
configured official endpoint. Second, Transformers reports an `incorrect regex
pattern` for the cached tokenizer and suggests `fix_mistral_regex=True`. These
are observed warnings, not demonstrated classification defects, and no tokenizer,
cache, dependency or runtime setting was changed. The recorded model revision
is the 6-bit checkpoint above. The preserved environment is Python 3.12.4 on
Apple Silicon macOS with 128 GiB RAM, mlx-lm 0.32.0, mlx 0.32.3, Transformers
5.19.0, tokenizers 0.23.3, huggingface-hub 2.2.0, PyTorch 2.14.1 and NumPy 2.5.3.
The warning provenance is `data/logs/v15_first_real_20261011_1839/server.log`;
the model and experiment settings are recorded in the manifests.

Reproduction starts with [docs/RUNNING.md](docs/RUNNING.md). The ablation's
append-only records—manifest, preflight, events, predictions, summary, paired
comparison, retrieval audit and error analysis—are under
`data/experiments/retrieval-ablation-v1/`. No inference was rerun for this
report. Genuine local v1.5 MLX inference and one CSCS-backed Docker application
smoke are recorded; the latter is one functional check, not a benchmark.

## 8. Future research and conclusion

The next experiment should freeze a small manually adjudicated proposition set
that marks the decisive sentence, speaker, proposal, numerical relation and
acceptable alternative evidence. Evaluate passage selection separately from a
fixed judge, then run the judge on counterbalanced evidence orders. This would
distinguish selection failure from interpretation failure with greater
information gain than another end-to-end recall optimisation.

For final generalisation evidence, collect a new vote- or topic-disjoint test
set rather than reuse the exposed corpus. Until then, dense SwissBERT retrieval
is the defensible production default. The present 243-call ablation supplies no
evidence that hybrid RRF or proposition-aware reranking improves NLI accuracy,
and its negative result should be retained.

## License

Report: Creative Commons Attribution 4.0 (CC-BY-4.0), following the template.
Repository code and source-data licensing require final review.

## References

1. [Apertus v1.5 8B model card](https://huggingface.co/swiss-ai/Apertus-v1.5-8B).
2. [SentenceSwissBERT model card](https://huggingface.co/ZurichNLP/swissbert).
3. [Official HackApertus project template](https://github.com/HackApertus/project-template).
4. [OST Track 2A challenge page](https://hackapertus.notion.site/track-2a-ost).
5. Internal experimental provenance is linked in the relevant sections and
   indexed in [docs/evidence/README.md](docs/evidence/README.md).
