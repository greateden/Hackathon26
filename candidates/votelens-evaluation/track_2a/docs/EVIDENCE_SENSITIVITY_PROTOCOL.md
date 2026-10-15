# Evidence sufficiency and order-sensitivity protocol

## Purpose and scope

This standalone diagnostic asks whether selected multilingual NLI errors are
associated with missing evidence, distracting evidence, evidence order or
failure to interpret evidence already present. It does not change production
retrieval, `make run`, Docker, model configuration, prompts, parsing or saved
results. The 17 cases are selected from a previously inspected 81-case
development experiment and are not an independent benchmark.

The frozen plan is
`docs/evidence/evidence_sensitivity_plan_20261012.json`. Its inputs include the
dataset and the immutable A/C records from
`data/experiments/retrieval-ablation-v1/`, identified by SHA-256. The structured
review template is
`docs/evidence/evidence_sensitivity_annotations_20261012.json`.

## Case selection

The sample contains all 11 A/C discordant rows: improvements 119, 432, 1026
and 1178; regressions 29, 297, 442, 455, 1344, 1401 and 1475.

Six deterministic controls are added:

- both correct: the lowest row index for each gold label (1, 550, 1035);
- both failed: the lowest row for each gold label represented among failures
  (189 entailment, 1058 contradiction), plus the next-lowest remaining failure
  (195 entailment).

No both-failed neutral case exists in the frozen 81 rows. Row 550 is a neutral
topic-mismatch control whose minimal sufficiency is explicitly uncertain.

## Conditions

- **A — original:** the recorded, unchanged dense SwissBERT Top-5 passages.
- **B — minimal:** exact PDF-page substrings proposed by offline inspection.
  Every set remains `pending_review` and cannot be used live yet.
- **C — minimal plus distractors:** B followed by two exact passages drawn
  from the recorded A/C evidence pool.
- **D — reordered:** the exact reverse order of C.

For every row, C and D have the same passage multiset, source identifiers,
page numbers, text, passage count and sum of passage characters. Only block
order changes. The future live output must also report actual prompt-token
usage; any order-dependent tokenizer-boundary difference is a measured
confound, not silently treated as equal length. B versus C is deliberately
length-confounded because distractors are added.

No sentence is rewritten. Minimal quotations are stored with physical PDF
page number and zero-based `[page_char_start, page_char_end)` offsets into the
current `pdftotext` extraction. The annotation file records attribution,
proposal identity, negation, quantities, conditions, exceptions and
sufficiency uncertainty. Annotated dataset references were used only as an
inspection aid; the frozen evidence consists of independently located PDF
substrings.

## Fixed inference contract

The runner reuses the existing `SubmissionJudge`, prompt builder and strict
parser. The frozen contract is Apertus v1.5
`m1rkocasu/Apertus-v1.5-8B-text-MLX-6bit` at revision
`9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`, temperature 0, seed 20261011,
512 maximum completion tokens, 81,920 context tokens, thinking disabled and
the recorded strict label parser. Gold labels and review metadata are never
sent to the model.

`run` requires a loopback endpoint, the explicit `--live` flag and complete
human approval. Records are append-only, attempts have unique IDs, resume
requires the unchanged plan and approval, and retries are bounded to 0–2.
Each result records actual prompt/completion usage, latency, prediction,
parser status and strict supplied-passage citation verification.

## Human approval gate

1. Review every row in `docs/EVIDENCE_SENSITIVITY_REVIEW_20261012.md` and the
   full exact spans in the plan.
2. In the annotation JSON, change each `review_decision` from
   `pending_review` to `approved` or `excluded`. Add `reviewer_note` where a
   decision needs explanation. An `excluded` case blocks the current frozen
   plan; request a separately versioned plan rather than editing evidence.
3. Only when every case is approved, set `overall_status` to `approved`, add a
   non-empty `reviewer`, and set `reviewed_utc` to an ISO-8601 timestamp.
4. Run the offline gate:

   ```bash
   ../.venv/bin/python src/evidence_sensitivity.py validate
   ```

The validator permits review-field changes but rejects any alteration of case
selection, quotations, distractors, attribution notes or sufficiency notes.

## Manual execution after approval

Start the pinned local server in one terminal:

```bash
../.venv/bin/python src/serve_experiments.py --context 81920
```

Then run the 68-call diagnostic in another terminal:

```bash
../.venv/bin/python src/evidence_sensitivity.py run --live \
  --context 81920 --retries 0 \
  --out data/experiments/evidence-sensitivity-v1
```

Resume without replacing prior attempts:

```bash
../.venv/bin/python src/evidence_sensitivity.py run --live --resume \
  --context 81920 --retries 0 \
  --out data/experiments/evidence-sensitivity-v1
```

Stop the server manually afterwards. Return `manifest.json`, `events.jsonl`,
`predictions.jsonl`, `summary.json` and `summary.md` from the output directory.

## Interpretation limits

Accuracy and macro-F1 are descriptive for this selected sample. Paired B/C
changes probe distractor sensitivity; C/D changes probe order sensitivity.
Neither identifies a unique causal mechanism. A correct minimal-evidence
prediction does not prove robust understanding, strict citation verification
proves textual provenance rather than semantic support, and neutral claims may
not be establishable from a short positive excerpt.
