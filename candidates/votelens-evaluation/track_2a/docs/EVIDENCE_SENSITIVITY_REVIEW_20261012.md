# Human review: proposed evidence sets

**Gate status: `pending_review`. No live execution is permitted.**

The full source text, physical page, exact extraction offsets, PDF SHA-256,
attribution notes and distractor passages are in
`docs/evidence/evidence_sensitivity_plan_20261012.json`. Review decisions are
recorded only in
`docs/evidence/evidence_sensitivity_annotations_20261012.json`.

| Row | Role | Pair; gold | Proposed decisive source | Main review question |
|---:|---|---|---|---|
| 29 | A correct, C wrong | DE→FR; entailment | p.29, Federal Council and Parliament recommend accepting the pension reform | Is the institutional attribution and proposal identity exact? |
| 119 | A wrong, C correct | DE→FR; entailment | p.6, Switzerland imports about 75% of its energy | Direct summary statement; check translation only. |
| 297 | A correct, C wrong | FR→FR; entailment | p.62, referendum committee says SMEs lack financial and organisational means and short replacements are costly/complex | Does the excerpt preserve every causal component? |
| 432 | A wrong, C correct | IT→IT; entailment | pp.26–27, referendum committees on Article 119 and the child's biological-parent interests | Two excerpts are required; does the claim overstate the source? |
| 442 | A correct, C wrong | IT→DE; entailment | p.26, E-ID is optional and its use is free | The page also permits a cantonal fee for in-person identification; retain this exception. |
| 455 | A correct, C wrong | IT→FR; entailment | p.9, initiative due-diligence duties | Confirm this is the initiative, not the counterproposal, and that all duties remain. |
| 1026 | A wrong, C correct | DE→IT; contradiction | p.31, financial aid was expanded to further affected businesses | The wording does not exactly reproduce “too little or no prior support”; sufficiency is uncertain. |
| 1178 | A wrong, C correct | FR→FR; contradiction | p.25, Federal Council and Parliament recommend rejection | Direct polarity check. |
| 1344 | A correct, C wrong | IT→FR; contradiction | p.22, 4% investment or replacement tax, averaged over four years | Check the 4%/10% contradiction and tax condition. |
| 1401 | A correct, C wrong | IT→IT; contradiction | p.19, Federal Assembly recommends rejection of the nursing initiative | Confirm proposal identity; distractors include another initiative. |
| 1475 | A correct, C wrong | IT→FR; contradiction | p.31, Federal Assembly recommends rejection of the arms-financing initiative | Direct polarity and attribution check. |
| 1 | both correct control | DE→FR; entailment | p.22, automatic post-2033 increase at 80% of added life expectancy | Check timing and numerical scope. |
| 550 | both correct control | DE→FR; neutral | p.9, booklet concerns stamp duty, not a CHF 40/hour minimum wage | A short excerpt cannot prove booklet-wide absence. Approve only if this operational neutral control is acceptable. |
| 1035 | both correct control | DE→FR; contradiction | p.5, roads are congested and six targeted projects are proposed | The `Oui` recommendation is adjacent; ensure the excerpt makes rejection false without relying on omitted layout. |
| 189 | both failed control | FR→IT; entailment | p.5, Federal Council and Parliament reject the limitation initiative | The proponent's `Sì` passage is an intentional stakeholder distractor. |
| 195 | both failed control | FR→FR; entailment | p.22, referendum committee says existing criminal-law bases suffice | Check whether “public humiliation” is a faithful compression of the committee text. |
| 1058 | both failed control | DE→FR; contradiction | p.4, reform applies to both primary and secondary residences | Direct scope contradiction. |

For each row, verify the exact quotation against its stored page and offsets,
then inspect the two proposed distractors. Approve only if B is minimally
sufficient while preserving attribution and necessary context, and if the C
additions are genuinely irrelevant or plausibly misleading rather than omitted
decisive evidence.
