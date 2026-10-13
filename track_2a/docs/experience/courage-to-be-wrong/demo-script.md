# Demo script — "The Courage to Be Wrong" (≈5 minutes)

Open `index.html` (double-click, or `python3 -m http.server` in this folder).
Nothing needs a model, a server, or the internet; if a reviewer's environment has
no `data/experiments/` tree, the page still renders — the Verification Ledger says
the raw records could not be re-verified there.

**Ground rule for the demo.** We do not show the system winning. We show it
*caught* — including by its own tooling. Every number is recomputed from records;
every mechanism is labelled OBSERVED or HYPOTHESIS. If a judge asks "is this
real?", the answer is always "here is the file, here is the hash, run it."

---

## Act I — The Promise (≈40 s)

- Start on **0 · Overview**. Point at the integrity banner: *different
  denominators per panel; no held-out benchmark; do not reward abstention.*
- Say the thesis once: **trust comes from making failures visible, not from
  looking infallible.** The four "swords" on this page are Mirror (Failure
  Gallery), Sword (the Ledger and the cross-examination), Shield (provenance),
  Pandora (the Cost of Coverage).

## Act II — The Temptation (≈70 s)

- Go to **1 · Failure Gallery** (press `1`).
- **Row 1115** (first card): "Both arms got the label *right*. The strict,
  citation-forcing candidate then **threw the correct answer away** because it
  couldn't name the vote. Strictness did not make it more correct — it made it
  *silent on a case it had solved.*"
- **Row 728** (second card): "The retrieval brought the **wrong proposal** —
  the Climate Act for a COVID-19 claim. The baseline *confidently* read that
  wrong-topic evidence as support. Plausible, cited, and wrong."
- Keyboard tour: `→` walks the cards; the top tabs are `1`–`5`.

## Act III — The Contradiction & The Mirror (≈90 s)

- Go to **2 · Evidence Sufficiency Lab** (press `2`). Default shows **all four
  evidence conditions at once**.
- Pick **row 1344** (`→`): "The decisive fact — *4%, not 10%* — is in the
  evidence every time. Read the D panel: the model *says* '4%, not 10%' and then
  outputs **neutral**. Same facts, moved behind distractors, different label. We
  do **not** claim that is proven positional — single runs; that is a hypothesis."
- Pick **row 189 / 195**: "Both recommendations are present; the model turns a
  stakeholder *disagreement* into a *contradiction* of an attributed claim.
  Attribution failure, not missing evidence."

## Act IV — The Cost of Certainty (≈70 s)

- Go to **3 · Coverage vs Accuracy** (press `3`). Default is the **Paired 54-case**
  view (one denominator, one metric): "Here is the trap. The candidate looks
  *more accurate* if you only look at what it chose to answer. But it answered
  **25 of 54**, and 18 of its refusals were cases it had actually got right —
  including **every** neutral case. Higher conditional accuracy among accepted
  answers does not mean higher overall correctness."
- Toggle to **"All cohorts"**: "These are four *different* studies on different
  denominators *and* different x-axis metrics — completion coverage, a
  citation-verification rate, valid-output coverage. The honest default is 'not
  comparable'; we deliberately do not join them into one frontier. In the grouped
  cohort dense retrieval had higher accuracy *and* slightly lower completion
  coverage — so even here there is no clean accuracy↔coverage tradeoff to draw,
  and we refuse to draw one."

## Act V — The Reconciliation (≈50 s)

- Go to **4 · Verification Ledger** (press `4`).
- "These are numbers a reviewer might *assume*. Two-thirds are wrong against the
  records, and the three example cases in the brief (`p0-004/028/059`) **do not
  exist**. Our own data tool refuses to display a figure that disagrees with the
  raw run — it caught one of *our own* bugs while we were building this."
- Close: *"We did not build a system that cannot be wrong. We made its errors
  harder to hide — including from ourselves."*

---

## Anticipated Q&A

**Q: Why default the Lab to "oracle" / curated evidence?**
A: We do **not** present curated evidence as a retrievable oracle. B is a
case-informed *upper bound*; the panel says so, and the README lists it as
NOT a deployable method. The default view shows *all four* conditions so the
comparison, not the "win", is the point.

**Q: Is "18/29 neutral" or "coverage lost"?**
A: 18 is a **gold**-neutral count; 15 is a **predicted**-neutral count; they are
different sets. Calling it "the model correctly abstained" is exactly the mistake
the Ledger exists to block.

**Q: Is the 70B result the submission result?**
A: No. The submission target is **Apertus v1.5 8B**. The 70B paired run and the
Docker smoke are *different* models and *exposed development data* — not a
benchmark, not independent, not a held-out generalisation estimate.

**Q: Did you prove the identity gate causes the coverage loss?**
A: No. We separate *where* outputs were rejected (the contract) from *why* the
answer went wrong (scope / sufficiency / attribution), and we say the causal
split is **untested**. The counterfactual that would settle it is an *offline plan
builder with a deliberately disabled live interface* — designed and guarded, never
run; no live experiment exists to run.

**Q: Is the evidence lab just generic LLM observability with Swiss branding?**
A: The *method* (a coverage–accuracy diagnostic, an evidence-ablation protocol) is
good practice, not novelty by itself. The **finding** is Swiss-specific: because
voting booklets are per-language editions of one vote day with *parallel*
passages, the failure modes cluster around **proposal scope** and
**stakeholder attribution** — e.g. the Climate-Act-for-COVID-19 case and the
"Council-Yes-committee-No" reversal — rather than generic hallucination.