# Failure-first attribution & verification record (the "Verification Ledger")

**Scope.** This record does two things that a normal report blurs together:

1. **Recomputes** every failure number the "Courage to Be Wrong" experience
   displays, straight from the frozen run records, and refuses to show a number
   the records do not support.
2. **Refuses fabricated labels.** Where the project brief handed me a number or
   an example ID that does not survive verification, that is recorded here as a
   correction, *not* quietly fixed so the story reads cleaner.

This is **analysis of recorded outputs, not a second model evaluation and not a
quality benchmark.** No inference was run, no frozen artefact changed, no prompt
or validation policy edited (project skill: `experiment-integrity`).

Evidence classes used throughout — **VERIFIED** (recomputed from records),
**OBSERVED** (stated in the record, not causal), **AI-ANNOTATED** (a model read
the record; not independent truth), **HYPOTHESISED** (plausible mechanism,
untested), **NOT TESTED** (designed but not run).

---

## 0. Source provenance (verify before trusting)

| Artefact | SHA-256 | What it is | Read by |
|---|---|---|---|
| `data/experiments/vote-aware-paired-v2/predictions.jsonl` | `1d7553e0…c34d1fe` (full: `1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe`) | 108 paired CSCS calls (`dense-v1` vs `vote-aware-v1`) on Apertus v1.5 **70B**, 54 cases | `courage_data.py`, this record |
| `data/experiments/evidence-sensitivity-v2/predictions.jsonl` | `805550d0…33dc85` | 60 calls, 15 cases × 4 evidence conditions, native 6-bit 8B | `courage_data.py`, `counterfactual_experiment.py` |
| `docs/evidence/offline_attribution_v2/tracked_facts_v2.json` | (tracked) | the prior aggregate-claim verification | cross-checked |

The two `.jsonl` files are **Git-ignored**: they were present and hash-checked
against the recorded values on 13 October 2026, on the machine that built the
dataset. A clean Git checkout does **not** reproduce them, and the committed
`facts.json`/`facts.js` must therefore be read as a **historical build-time
result** — the static page does *not* re-run the hash check, and it must never be
described as "a clean checkout has just verified the raw files". The re-runnable
guard is `courage_data.py`: when the raw tree *is* present it verifies both
hashes and re-counts before it will rewrite `facts.json`, and it **skips** (and
does not overwrite) when the tree is absent. On a clean checkout, restore the
tree and compare the hashes first; the committed facts carry these hashes so a
mismatch is visible.

### 0.1 The `grouped81-p0-004 / 028 / 059` problem — NOT ESTABLISHED

The brief listed `grouped81-p0-004`, `-p0-028`, `-p0-059` as "P0 examples to
inspect". **These identifiers do not exist** in `predictions.jsonl`, in
`docs/evidence/paired_grouped81_plan_20261011.json`, or in the evaluation set.
The real documented representative cases are `official-row-1115`, `-728` and
`-964` (candidate rejections) plus the evidence-sensitivity rows
`1026 / 1344 / 189 / 195`. The experience uses **those**, and does not invent a
neutral case to fit the template. (The brief itself says some of its example
facts are stale and must be verified — this is that verification doing its job.)

---

## 1. The corrected P0 ledger (the 29 candidate rejections)

**Population.** 54 paired cases. `dense-v1` produced 43 valid / 11 invalid
outputs; `vote-aware-v1` produced 25 valid / 29 invalid. Every one of the 29
rejections still contained a *parseable* raw NLI label.

Gate taxonomy (recomputed, VERIFIED): **14** rejections declared
`vote_status=unrecognised`; **15** returned `null`/invalid `vote_status` (12 of
these returned JSON `null` for `vote_status` and `vote_reference`). Both are
*identity-gate* stops. **No rejection produced a quotation**, so mechanical
citation verification never ran on them; it ran on the 25 accepted outputs,
which passed 25/25.

Recomputed facts (all VERIFIED by `courage_data.py`, self-check passes):

```
rejections_total                                29
gate_unrecognised                               14
gate_null_or_invalid_status                     15
raw_correct_among_rejections                    18     (not "20")
raw_incorrect_among_rejections                  11
gold_distribution          E/N/C               3 / 18 / 8
raw_predicted_labels       E/N/C               0 / 15 / 14   (not "12 N + 17 C")
gold_neutral_rejections                         18     (all gold-neutral cases rejected)
gold_neutral_rejections with raw label neutral  12     (6 returned contradiction)
incorrect_label_by_gate      unrecognised        8
incorrect_label_by_gate      null/invalid        3     (so 8 + 3, NOT "5 + 5")
```

### 1.1 Ledger entries the brief asserts, checked

| Asserted | Record says | Class |
|---|---|---|
| "20 of 29 correctly relabelled" | 18 gold-matching (11 do not) | VERIFIED-INCONSISTENT |
| "18/29 are neutral" | 18 are **gold**-neutral; 15 are **predicted**-neutral — different sets | VERIFIED-AMBIGUOUS |
| "only 4 (then 9) of 18 preserve neutral" | 12 of 18 gold-neutral rejections returned neutral at the raw level | VERIFIED-INCONSISTENT |
| "5/14 identity + 5/15 schema failures wrong" | gate counts 14/15 are right; per-gate wrong-label counts are 8 and 3 | VERIFIED-INCONSISTENT |

The "18 neutral cases" *do* deserve their own layer, because that is the
genuinely interesting pattern — but it must be stated as *coverage lost*, not
"the model correctly abstained". See §4.

---

## 2. Complete per-case analysis (12 cases)

Each block: **source → gold → both methods/conditions → recorded outputs →
error class → evidence class → what to measure next.** Labels are E=entailment,
N=neutral, C=contradiction. *Paired* cases show `dense-v1` and `vote-aware-v1`;
*lab* cases show the four evidence conditions A/B/C/D. Raw-label correctness is
"did the recovered NLI label match gold"; acceptance/validity is separate.

### 2.1 Paired 70B cases (CSCS `swiss-ai/Apertus-v1.5-70B`, exposed dev split)

**P-1 · `official-row-1115` — Right answer thrown away at the gate.**
- Source: `predictions.jsonl` (both arms). Gold **C**. Domain: health-insurance
  premium-relief initiative; claim: "the booklet says the premium reduction is
  financed *entirely* by the Confederation".
- Evidence (both arms): the booklet says the reduction would cost billions of
  francs a year and the Confederation covers at least two thirds, not all. That
  contradicts "entirely financed by the Confederation".
- `dense-v1`: raw C (correct) → **accepted**, citation verified, strict correct.
- `vote-aware-v1`: raw C (correct), reasoning *names the contradiction* →
  **rejected** (`vote_status=unrecognised`); citation never verified.
- Error class: **over-abstention / contract rejection despite adequate
  evidence.** Not an NLI error and not a retrieval error: evidence supports the
  label; it is the identity gate that lost a correct answer.
- Evidence class: **OBSERVED**. The causal claim "the gate alone caused it" is
  **INFERRED** from the recorded fields, not proven.
- Next: replay with vote identity judged independently of the label, then confirm
  whether the page-8 citation would have verified.

**P-2 · `official-row-728` — Retrieval scope failure (the brief's "P0-028").**
- Source: `predictions.jsonl`. Gold **N**. Requested vote: the **COVID-19 Act
  amendment**; claim about accelerating the 2030 energy transition.
- Evidence (candidate): all five retrieved passages concern the **Climate and
  Innovation Act** — a different proposal. Retrieval left the named vote's scope.
- `dense-v1`: raw **entailment** (WRONG vs neutral gold) but accepted — it
  treats topically-related climate material as *supporting* the claim.
- `vote-aware-v1`: raw neutral (correct) → rejected (no citation).
- Note the brief's draft of this case said "dense narrowly correct, candidate
  neutral". Record: **dense is wrong (entailment); candidate is right but
  rejected.** The two models *disagree about whether the climate evidence speaks
  to a COVID-19 claim at all*.
- Error class: **retrieval scope failure, plus dense over-generalising.** The
  neutral-vs-absence question (is the fact absent from the *whole* booklet?) is
  **UNCERTAIN** — the record only shows the retrieved five passages.
- Next: scope evidence to the named vote; keep failures in the denominator.

**P-3 · `official-row-964` — Named the initiative, still wrong label.**
- Source: `predictions.jsonl`. Gold **N**. Requested vote: the **Cash /
  "currency with coins or banknotes"** initiative + counter-proposal; claim
  about a *new corporate income-tax regime from 2027*.
- Evidence: identifies the Cash initiative; says neither proposal creates new
  tax regimes.
- `dense-v1`: raw neutral (correct) → accepted.
- `vote-aware-v1`: raw **contradiction** (WRONG) → rejected
  (`vote_status=unrecognised`); reasoning says "not mentioned or supported",
  i.e. one thing, while its label says another.
- Error class: **attribution conflation + explanation/label inconsistency**,
  *plus* an identity failure with a wrong label. This is a genuine **over-narrow
  "absent → contradiction"** case (absent-in-retrieved-five, not proven
  booklet-wide-absent).
- Next: separate "not about this claim" (neutral) from "denied by this claim"
  (contradiction) in a controlled prompt test; generated reasoning cannot be
  assumed faithful (Turpin et al., 2023).

### 2.2 Evidence-Sufficiency Lab cases (native 6-bit 8B, A/B/C/D conditions)

Legend for conditions: **A** = recorded retrieval top-5; **B** = manually
curated sufficient evidence (case-informed **upper bound**, not a retrievable
oracle); **C** = B + two reviewed non-decisive distractors (longer input);
**D** = the B block moved *behind* the distractors — **per row, C and D carry the
identical passage multiset and identical input-token count** (verified: 1026 a
4-passage set at 533 tokens each, 1344 a 3-passage set at 701, 189 3-passage at
543, 195 4-passage at 603). Only the block order changes; the facts do not. Read
the flips as *placement*, not *new facts*.

**L-1 · row 1026 — Decisive fact kept, then ignored when moved.**
- Gold **C** (a contradiction between "aid limited to the already-served" and
  the booklet's "aid *extended* to those with too little/no prior support").
- A: neutral (wrong) · **B: contradiction (correct)** · **C: contradiction
  (correct)** · **D: neutral (wrong)** — with D's reasoning discussing
  "advance-payment procedure and referendum deadlines".
- Decisive sentence present in B, C *and* D. **OBSERVED:** the same facts,
  reordered, change the label. **HYPOTHESIS (single runs):** a mid-list
  position effect (cf. Liu et al., 2024) — *not proven*, and the model's own
  reasoning about what it attended to is untrusted.

**L-2 · row 1344 — 4% vs 10%, read correctly, mislabelled.**
- Gold **C** (Article 24b specifies **4%**, claim says **10%**).
- A: contradiction (correct) · B: contradiction · C: contradiction · **D: neutral
  (wrong)**, yet its explanation says *correctly* "4%, not 10%".
- Error class: **numeric/relation + explanation/label inconsistency**. The model
  states the disqualifying fact and emits neutral. A candidate **over-narrow**
  failure *and* a faithfulness case.

**L-3 · row 189 — Both recommendations present; stakeholder scope lost.**
- Gold **E** (claim: the *Federal Council* recommends rejecting; evidence says
  the Council *and* Parliament recommend No, the committee recommends Yes).
- A: contradiction (wrong) · **B: entailment (correct)** · **C: entailment
  (correct)** · **D: contradiction (wrong)**, while correctly stating both
  recommendations.
- This is *not* proof the government recommendation became ambiguous; it is
  **attribution-sensitive labelling** — disagreement between stakeholders treated
  as contradiction of an attributed claim.

**L-4 · row 195 — Attributed to the committee; a distractor flips it.**
- Gold **E** (claim reports the *committee's* view that existing law suffices).
- A: neutral (wrong) · **B: entailment (correct)** · **C: contradiction (WRONG)**
  · **D: contradiction (WRONG)** — adding the Council/Parliament's opposing view.
- Error class: **stakeholder-attribution failure** under added distractors.
  Candidate for the controlled `StanceAttributionChallenge` (§4).

**Remaining eight (for the full ledger, abbreviated, all A/B/C/D = recorded):**
rows **29, 119, 297, 442, 455, 1026(↑), 1178, 1344(↑), 1401, 1475** carry the
eleven A→C correctness changes analysed in
`docs/RETRIEVAL_ABLATION_PAIRED_ANALYSIS.md`; rows **189, 195, 1026, 1344** are
the four lab cases above. Cross-reference that file rather than restating its
passage-by-passage matrix here.

---

## 3. Four-layer failure taxonomy (the deliverable this record was built for)

A failure is assigned to the **earliest stage that is independently measurable**;
"reasoning failure" is used only *after* evidence adequacy is independently
verified. This prevents the two traps the brief names — **blaming retrieval for a
reasoning failure**, and **mistaking evidence presence for evidence adequacy**.

- **L1 — Retrieval scope.** Evidence left the named vote/proposal, or the
  decisive proposition was displaced/demoted by the ranker. *Measured* by whether
  the retrieved five are within the named vote's scope (not by Recall@5, which
  rose while accuracy fell). Example: row 728.
- **L2 — Semantic sufficiency.** Evidence is topically relevant but does not
  *establish* the claim (a distractor, or a paraphrase that never asserts the
  proposition). Requires independent annotation of "sufficient for entailment /
  for contradiction / insufficient for either". *This layer does not yet have
  independent ground truth.*
- **L3 — Speaker-attribution.** The right proposition is present but credited to
  the wrong stakeholder (Council vs committee vs another proposal), so an
  attributed claim is marked contradiction because *someone* disagrees. Examples:
  rows 189, 195, and the two stakeholder-contamination lab cases.
- **L4 — Output-contract.** A **correct raw label rejected by the output
  contract**: identity (`vote_status`) or citation/`evidence_mode` errors. The
  29 rejections are all here *at the surface*, but their **upstream** cause is
  split across L1–L3; **18 of the 29 were gold-correct** at the raw level, so
  L4 is *where they died*, not *why they were wrong*.

The whole point: **P0 rejected both correct and incorrect outputs.** "Errors
caused by the identity-gate repair" is not a single mechanism, and the number of
strict losses is *not* a clean 18-vs-13 — it is 18 dense-only-correct vs
9 candidate-only-correct (McNemar p = 0.122078), and every "18 neutral"
statement mixes a gold count with a prediction count.

---

## 4. The coverage question, stated without a false tradeoff

- In the paired run, `vote-aware-v1` had **higher raw-label accuracy than dense**
  (41/54 vs 40/54) but **far lower coverage** (25/54 vs 43/54). Its rejections
  are *not* its errors: 18 rejections were gold-correct; dense also had
  correct-but-unrenderable outputs (8 of its 11 invalid were gold-correct).
- It rejected **all 18 gold-neutral cases** — including 12 whose raw label was
  correctly neutral. That is a **coverage loss on a class the task explicitly
  needs**, not a reliability win.
- **Do not read a high error rate as proof of reliability.** If a *complete*
  bookelt input failed, the problem is model use of evidence, not missing
  evidence; more strict source constraints are not automatically more reliable.
- **No clean accuracy↔coverage tradeoff should be drawn**, and the paired and
  grouped cohorts must not be conflated. In the *grouped* cohort dense within-PDF
  retrieval beat full-booklet on **accuracy (65/81 vs 42/81) while having slightly
  LOWER completion coverage (80/81 vs 81/81 — one dense reply hit the token limit
  and stayed an error)**; it is a different cohort, model (8B) and x-axis metric
  from the paired points. In the *paired* cohort dense-v1 has both higher strict
  accuracy and higher valid-output coverage than vote-aware-v1 (one denominator,
  n=54). The panel therefore defaults to that paired pair as the only comparable
  view and shows the rest **grouped by cohort and un-joined, on different
  coverage metrics**, saying so on-screen.
- The through-line that *is* safe to state: **higher conditional accuracy among
  accepted/completed answers does not imply higher overall strict correctness.**
  Both cohorts show the failure and the correct label being thrown away at the
  contract gate; the panel refuses to read a coverage drop as a reliability gain.

### 4.1 The counterfactual to run *offline* (NOT TESTED — designed here only)

`counterfactual_experiment.py` (offline mode) already builds and self-checks, for
rows 1026 / 1344 / 189 / 195, the four required variants — `full`, `retrieved`,
`oracle_verified`, `neutral_distractor`(+reordered) — and **enforces** that the
oracle provenance is *copied from the record, not asserted* (the earlier failed
self-check proved the guard bites: it caught this author comparing an
order-sensitive hash; C/D genuinely share their evidence set). Its `live` mode is
hard-gated behind an endpoint **and** `VOTELENS_ENABLE_LIVE_EXPERIMENT=1`, and
it refuses to fall back to lexical. **No number is claimed from it.**

Tier-C controlled experiments to authorise *only if* the offline replay leaves
RQ1–RQ3 open:
1. **Identity-gate ablation on fixed evidence** (isolates L4 from L1–L3).
2. **Fixed-evidence NLI-judgement comparison** (isolates reasoning from
   retrieval).
3. **Evidence-order ablation with repeated controls** (isolates placement;
   counterbalances C/D order).
4. **`StanceAttributionChallenge`** — Council vs committee vs another proposal,
   for L3.

Each must state which variables are held fixed and disclose that a deterministic
replay cannot reveal how the model would answer a prompt it never received.

---

## 5. Independent-annotation protocol (BlindAdjudicationProbe, v1)

AI annotation is **exploratory, not independent ground truth.** The prior
`offline_attribution_v1` was generated by a local Qwen-family assistant, a
*different family* from the Apertus predictors — cross-family sampling weakens a
shared-decoder concern but proves nothing about reliability. Until human review,
the experience shows the AI annotation as **AI-annotated**, never as truth, and
no gold/decision is exposed in a blind export.

Per-item fields the annotator judges **blindly** (no gold, no model output shown):

1. **Vote identity present / ambiguous / absent** (RQ1).
2. **Claim addressed / unrelated** by the supplied evidence.
3. **Correct stakeholder/speaker** for an attributed claim (RQ3, L3).
4. **Evidence sufficient for entailment / for contradiction / for neither**
   (RQ3, L2).
5. **Semantic support by the cited text** — *does the quotation support the
   label*, kept strictly separate from *does the quotation occur in the source*.
6. **Exact source occurrence** (mechanical), recorded separately from (5).
7. **Scope of the insufficiency judgement**: "absent from retrieved top-5" vs
   "absent from the whole named booklet". These are **not interchangeable**;
   top-5 absence never establishes booklet-wide absence (the row-550 lesson).

Adjudication: two independent annotators (human where possible), report exact +
nominal agreement, send disagreements to a third; keep all failures in the
denominator; freeze the protocol before collecting. Counterfactual prompts, if
used, must **not** reveal gold labels. A deterministic replay cannot establish a
model's answer to a prompt it never received.