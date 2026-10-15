# Supplementary paired analysis: retrieval ablation

This supplement records the manual comparison of the 11 cases whose correctness
changed between A (dense SwissBERT) and C (hybrid retrieval followed by
proposition-aware reranking). It is based on the immutable records in
`data/experiments/retrieval-ablation-v1/`. The experiment contains 81 paired
examples; four A→C changes are improvements and seven are regressions.

Reference coverage is the recorded 40-character shingle proxy, reported here to
three decimals. A verified citation means that the generated quotation occurs
in the supplied passages after the documented conservative normalisation. It
does not mean that the quotation supports the prediction. Passage identifiers
are listed in model-input order. Observations below are separated from causal
hypotheses; the categories are overlapping rather than mutually exclusive.

## Case matrix

| Row | Pair; gold | Claim (English gloss) | A / B / C | A→C coverage; citation | Ordered evidence, A → C | Observed comparison and cautious interpretation |
|---:|---|---|---|---|---|---|
| 29 | DE→FR; entailment | The Federal Council favours accepting the occupational-pension reform. | E / E / N | .352→.461; yes→yes | `p29-c2,p7-c1,p28-c1,p21-c3,p20-c2` → `p30-c1,p29-c1,p22-c1,p20-c1,p28-c1` | **Observed:** C removes the direct recommendation (`p29-c2`) and summary (`p7-c1`), but its fifth passage still says that the Council and Parliament approve the proposal. C nevertheless says their position is absent. **Hypothesis:** displacement reduced salience, while a remaining interpretation failure was also necessary for the regression. |
| 119 | DE→FR; entailment | The summary says that Switzerland imports about 75% of its energy. | N / E / E | .487→.485; yes→yes | `p30-c2,p6-c1,p31-c1,p30-c1,p32-c1` → `p6-c1,p35-c2,p4-c2,p12-c2,p16-c2` | **Observed:** all arms contain the explicit 75% statement. A repeats the fact in its reasoning but returns neutral; B and C return entailment. **Hypothesis:** ordering or surrounding material may have helped, but missing evidence cannot explain the gain. |
| 297 | FR→FR; entailment | The committee says SMEs lack the resources for two weeks of paternity leave because short replacements are costly and complex. | E / E / C | .337→.380; yes→no | `p59-c1,p64-c3,p62-c2,p11-c1,p64-c1` → `p65-c1,p62-c2,p10-c1,p60-c1,p11-c1` | **Observed:** C places a government counterargument about broad financing and SMEs first; the committee passage remains second. C treats the counterargument as contradicting the attributed committee view. **Hypothesis:** stakeholder mixing induced by a higher-ranked distractor plausibly contributed. |
| 432 | IT→IT; entailment | The committee argues that sperm donation for lesbian couples violates Article 119 and the child's rights. | C / E / E | .553→.531; no→yes | `p27-c1,p26-c3,p28-c2,p26-c2,p29-c1` → `p26-c3,p29-c1,p27-c1,p26-c1,p32-c1` | **Observed:** A already contains the decisive committee passages but misreads them; B and C return entailment, with C moving the Article 119 and child-right material upwards. **Hypothesis:** order may have helped, but this is primarily an interpretation change rather than evidence recovery. |
| 442 | IT→DE; entailment | The summary states that use of the E-ID is voluntary and free. | E / E / C | .379→.030; no→no | `p26-c1,p30-c1,p23-c1,p6-c2,p23-c2` → `p7-c1,p28-c1,p28-c2,p26-c1,p28-c3` | **Observed:** C adds referendum/opposition passages questioning future voluntariness, while retaining the explicit voluntary/free statement only at rank four. It then states that the E-ID is not voluntary and may cost money. **Hypothesis:** source-attribution and opposition distractors plausibly dominated the retained summary evidence. |
| 455 | IT→FR; entailment | Companies must conduct and report human-rights and environmental due diligence, prevent violations and end existing ones. | E / E / N | .287→.239; no→no | `p9-c2,p17-c2,p19-c1,p4-c2,p14-c2` → `p17-c2,p18-c1,p14-c2,p5-c1,p12-c1` | **Observed:** C removes the most explicit duty passages (`p9-c2`, `p19-c1`/`p19-c2`) and retains broader initiative and counterproposal discussion. It says the detailed duty is unconfirmed. **Hypothesis:** loss of the decisive legal proposition is the strongest selection-based explanation among the regressions. |
| 1026 | DE→IT; contradiction | Financial aid was limited to people who had already received sufficient support. | N / N / C | .000→.000; yes→no | `p45-c2,p43-c1,p31-c2,p31-c1,p37-c1` → `p37-c1,p45-c2,p44-c1,p45-c3,p32-c2` | **Observed:** no arm retrieves the annotated reference probe. C ranks broad aid provisions first and correctly rejects the asserted limitation, but its citation is unverified. **Hypothesis:** C found semantically useful alternative evidence that the lexical reference proxy cannot credit; the reasoning remains less directly grounded than a reference hit. |
| 1178 | FR→FR; contradiction | The Federal Council recommends accepting the clean-water initiative. | E / E / C | .241→.241; yes→yes | `p14-c1,p26-c1,p18-c1,p25-c2,p5-c1` → `p26-c1,p25-c2,p5-c1,p18-c1,p16-c1` | **Observed:** every arm contains the rejection recommendation. A and B explicitly say “rejecting” supports a claim of “accepting”; C reads the polarity correctly after reordering. **Hypothesis:** this is a model polarity error corrected without new decisive evidence. |
| 1344 | IT→FR; contradiction | Film providers must invest at least 10% of gross revenue in Swiss independent films or pay an equivalent levy. | C / E / N | .265→.006; yes→yes | `p22-c1,p23-c1,p22-c2,p4-c1,p12-c1` → `p18-c1,p12-c2,p11-c1,p5-c1,p4-c1` | **Observed:** A ranks the legal 4% provision first and compares 10% with 4%. C demotes the shorter 4% summary to rank five and calls 10% merely unsupported. **Hypothesis:** reduced numerical precision in selection and a failure to use the remaining 4% evidence both contributed. |
| 1401 | IT→IT; contradiction | The Federal Assembly recommends approving the Justice Initiative. | C / C / N | .253→.388; yes→yes | `p30-c2,p19-c2,p48-c1,p20-c1,p28-c1` → `p28-c1,p18-c1,p19-c2,p29-c2,p3-c1` | **Observed:** C adds material from another proposal in the same booklet and says the Justice Initiative recommendation is absent, although `p29-c2` contains the rejection recommendation. **Hypothesis:** cross-proposal contamination plus failure to interpret a lower-ranked relevant passage explains the pattern more plausibly than recall alone. |
| 1475 | IT→FR; contradiction | The Federal Assembly recommends approving the initiative against arms financing. | C / N / N | .362→.535; no→yes | `p31-c2,p32-c1,p20-c1,p30-c1,p3-c1` → `p30-c1,p7-c1,p18-c1,p31-c1,p29-c2` | **Observed:** C raises the coverage proxy while dropping A's exact “reject” sentence (`p31-c2`). It retains related “Non” and recommendation material but says the institutional recommendation is absent. **Hypothesis:** loss of the decisive clause and sensitivity to institutional attribution plausibly caused the regression; the higher coverage score is therefore misleading. |

Labels in the prediction column are E = entailment, N = neutral and C =
contradiction; bold “Observed” statements describe record contents, whereas
“Hypothesis” statements are interpretations.

## Error taxonomy

1. **Decisive proposition displaced or demoted** (rows 29, 455, 1344 and
   1475; partly 442). Reranking may increase reference overlap while removing
   the shortest, most explicit proposition needed by the judge.
2. **Stakeholder or proposal contamination** (rows 297, 442 and 1401).
   Passages from an opponent, government response or another proposal are
   topically relevant but answer a different attribution.
3. **Interpretation or polarity failure despite sufficient evidence** (rows
   119, 432 and 1178; also visible in 29, 1344 and 1401). The model sometimes
   states the decisive fact correctly and still emits the wrong label.
4. **Useful evidence not credited by the reference proxy** (row 1026). A
   correct answer can arise from a semantically adequate passage that does not
   match the annotated reference string.

## Why Recall@5 did not transfer to NLI accuracy

Relative to A, C increased Recall@5 on 15 cases, left it unchanged on 62 and
reduced it on four. The joint correctness table is:

| Recall@5 change, A→C | Accuracy improved | Accuracy unchanged | Accuracy worsened | Total |
|---|---:|---:|---:|---:|
| Improved | 0 | 14 | 1 | 15 |
| Unchanged | 3 | 55 | 4 | 62 |
| Worsened | 1 | 1 | 2 | 4 |
| **Total** | **4** | **70** | **7** | **81** |

The extra reference hits mostly changed no label. Reference matching measures
lexical overlap with one annotation, not the presence, prominence or
attribution of every proposition required for NLI. Conversely, useful
non-reference evidence can be scored as a miss. C also changed passage order
and composition, sometimes elevating counterarguments or parallel proposals.
Finally, several flips show direct model interpretation errors under evidence
that was already sufficient. The records therefore support a multi-stage
explanation—proxy limitations, selection trade-offs and judgement errors—not a
causal claim that reranking itself produced every changed prediction.

## Provenance

Primary records: `summary.json`, `predictions.jsonl`,
`paired_comparison.csv`, `retrieval_audit.json`, `error_analysis.md`,
`manifest.json` and `preflight.json` in
`data/experiments/retrieval-ablation-v1/`. No inference was rerun and no saved
record was modified for this analysis.
