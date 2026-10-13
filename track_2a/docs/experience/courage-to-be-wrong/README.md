# The Courage to Be Wrong — research experience (docs/experience)

A **failure-first, presentation-only** layer over *recorded* experiment results.
It is not the submission pipeline and does not change it. It exists to make the
pipeline's failure mechanisms legible and to keep the numbers honest while doing
so.

## Open it

```bash
# from track_2a/docs/experience/courage-to-be-wrong/
python3 -m http.server 8080      # then open http://127.0.0.1:8080/
# or simply double-click index.html (works over file:// — no fetch, no build)
```

No model, no server, no network, no paid services. `index.html` loads `facts.js`
(a generated data snapshot) and `app.js` (a ~450-line vanilla-JS renderer) via
`<script>` tags, so it works from a plain file open and from a static host.
Keyboard: `1`–`5` switch layers, `←`/`→` move between cases/conditions, `Esc`
collapses. Respects `prefers-reduced-motion` and `prefers-contrast`.

## What the layers are

| Layer | Question it lets you answer |
|---|---|
| 0 · Overview | How to read the thing; evidence classes; the three research questions |
| 1 · Failure Gallery | Predicted vs gold; raw vs strict vs output-validity; recorded outputs for both arms |
| 2 · Evidence Sufficiency Lab | Same claim under four evidence configurations; evidence *present* vs evidence *sufficient* |
| 3 · Coverage vs Accuracy | Accuracy vs a *coverage-style rate* (three different metrics); default is the one comparable pair (paired 54, shared denominator); other cohorts shown only as a non-comparable map; no reward for abstention |
| 4 · Verification Ledger | A reviewer might assume X — the records say Y; wrong numbers stay visible |

## How to regenerate / re-verify (no inference)

```bash
python3 docs/experience/courage-to-be-wrong/courage_data.py
python3 docs/experience/courage-to-be-wrong/counterfactual_experiment.py --dry-run
```

- `courage_data.py` recomputes the ledger figures from
  `data/experiments/*/predictions.jsonl` and **exits non-zero if any shown figure
  disagrees with the records**. It first checks **both** raw-file SHA-256 values
  against the recorded ones (`1d7553e0…` paired, `805550d0…` sensitivity) and
  fails closed on a mismatch. It then validates each Gallery/Lab case ID, gold
  label, per-arm raw label, condition membership (the 2×2 A/B/C/D) and available
  source metadata **against the correct experiment**, and refuses to display a
  hand-typed label that the records do not back. This is the guard that refuses
  fabricated labels.
- When the Git-ignored `data/experiments/` tree is **absent** (a clean checkout),
  it does **not** overwrite the committed `facts.json`; it keeps the published
  snapshot and reports `verification.state = NOT RE-VERIFIED IN THIS BUILD`. A
  clean checkout therefore still opens and still shows the provenance, but it must
  **not** be read as "the raw files were just verified here" — the committed
  `facts.json`/`facts.js` are a *historical build-time* result. To re-verify,
  restore the raw tree, check the hashes, and re-run the script.

## Files

| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js` | the experience (presentation only) |
| `facts.js`, `facts.json` | generated data snapshot (regenerate, don't hand-edit); includes the build-time **Evidence Passport** + `verification.state` (outside the submission JSON contract) |
| `courage_data.py` | builds + self-verifies the data; the verification layer (checks both hashes, validates case IDs/labels/conditions against the correct experiment, fails closed) |
| `counterfactual_experiment.py` | **offline plan builder** for the four counterfactual variants + invariant guard; its `live` interface is **deliberately disabled and not implemented end-to-end** — no runnable live experiment exists, and it never falls back to a lexical baseline |
| `counterfactual_plan.json` | generated offline variant plan (NOT an accuracy result; no inference run) |
| `attribution-verification.md` | the full Verification Ledger write-up + per-case analysis + annotation protocol |
| `demo-script.md` | 5-minute three-act demo + Q&A |

## Relationship to the official path (read before reviewing)

- This lives under `docs/`, **not** `src/` or `tests/`. `.dockerignore`
  excludes `docs/experience/`, and the `Dockerfile` copies only two pinned
  evidence JSONs, so **none of this is in the Docker image or the submission
  runtime**.
- The counterfactual experiment must never enter the default Docker path; its
  counterfactual prompt must never be routed into the production system prompt.
  It is a research instrument, kept offline and gated.

## Integrity limits (what is NOT true here — do not oversell)

- **No benchmark.** All figures are single-run, exposed-development observations.
  The paired run is **Apertus v1.5 70B**, not the 8B submission target.
- **Different denominators, different metrics.** Coverage and accuracy are
  computed on different bases per panel; the three coverage metrics (completion,
  citation-verification rate, valid-output coverage) are deliberately kept
  distinct and the panel does **not** join its points into one frontier. Only the
  paired 54-case pair shares a denominator and is the default view.
- **Rejection ≠ reliability.** A large rejection count is not proof of trust.
- **Explanation ≠ decision.** Model reasoning shown here is not assumed to
  describe the model's internal process (Turpin et al., 2023).
- **`grouped81-p0-004/028/059` do not exist.** Real cases (`official-row-1115`,
  `-728`, `-964`, and rows `1026/1344/189/195`) are used instead.
- The 18 "over-narrow / lost-neutral" pattern is **genuine** — but it is a
  *coverage* observation, not evidence that those answers should have been
  emitted, and not evidence that removing the identity gate is safe.
- The interactive app was re-verified this pass to render with **no console errors,
  no warnings and no failed requests** (served over localhost, all five panels and
  the tab/keyboard navigation exercised), and the data layer's self-check passes;
  it has **not** been audited by a screen reader or checked against a pixel design.

Report/data licence: CC-BY-4.0, following the technical-report template. **No full
booklet text, PDF, or long verbatim source block is redistributed here.** What the
snapshot *does* carry is (a) our own analysis and (b) short per-case `reasoning`
strings that are the **predictor model's own output**, copied verbatim from the
run records and marked **AI-ANNOTATED** — these paraphrase the case and may quote a
short (<25-word) source phrase, but reproduce no substantial booklet passage. They
are shown as *not assumed faithful* to the model's decision, and their provenance
is stated in each Evidence Passport and in `attribution-verification.md`; unresolved
source-licence questions are flagged there, not silently bundled. The `docs/` layer
is also excluded from the Docker image (`.dockerignore` allow-list + the two pinned
evidence JSONs), so none of this is in the submission runtime.
