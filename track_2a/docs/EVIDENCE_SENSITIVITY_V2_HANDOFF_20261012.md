# ChatGPT Handoff: evidence sensitivity v2

## Current state

**Prepared offline; pending independent ChatGPT confirmation.** All 17 rows adjudicated; 15 retained, rows 455 and 550 excluded, 60 initial calls planned with zero retries. No live inference executed by this preparation. Existing production defaults, retrieval, Docker, `make run`, labels, historical results, v1 files and `technical_report.md` are unchanged. No commit or push.

This is AI-assisted independent evidence adjudication, not completed human verification or a human signature. `accepted`/`revised` concern the scientific preparation, not permission to run. All external review decisions remain pending.

## Changes and case decisions

| Row | Status | Decision |
|---:|---|---|
| 29 | `accepted` | Direct attributed pension-reform acceptance. |
| 119 | `accepted` | Explicit approximate 75% energy-import share. |
| 297 | `revised` | Committee attribution; two weeks and full causal explanation. |
| 432 | `revised` | Committee identity plus both excerpts and age-18 qualification. |
| 442 | `accepted` | Free voluntary use; possible paid in-person identification retained. |
| 455 | `disputed` | Excluded: duty to exercise diligence differs from proof as a liability defence. |
| 1026 | `revised` | Replaced B with p.8: insufficient/no previous assistance. |
| 1178 | `revised` | Replaced corroborating p.16 distractor. |
| 1344 | `revised` | 4%, replacement-tax trigger, four-year average and SSR exception retained. |
| 1401 | `revised` | Nursing-initiative identity added to Assembly rejection. |
| 1475 | `revised` | Arms-financing identity added; corroborating rejection distractor replaced. |
| 1 | `revised` | Post-2033 80% rule; annual cap and notice retained. |
| 550 | `excluded` | Excluded: short evidence cannot establish booklet-wide absence. |
| 1035 | `revised` | Explicit Oui and six projects; corroborating p.14 distractor replaced. |
| 189 | `revised` | Limitation-initiative identity, Council No and separate committee Si. |
| 195 | `revised` | Stronger committee evidence at p.7 plus Penal Code argument at p.22. |
| 1058 | `revised` | Both residence types; special secondary-home tax kept distinct. |

The [source review annex](EVIDENCE_SENSITIVITY_V2_SOURCE_REVIEW_20261012.md) contains the exact B/replacement-X quotations, official URLs, printed/physical pages, offsets, PDF hashes, speaker/proposal provenance and all original distractor classifications. The JSON annotations/plan preserve the exact 34 historical candidates and 30 reviewed replacements. Corroborating/ambiguous candidates were replaced for every retained case; excluded cases retain their audit without planned calls.

C = B + [X1, X2]; D = [X1, X2] + B. The complete B block moves, preserving internal B and X order. Offline reconstruction verifies rendered prompts, source metadata, settings, budgets, all quotations/offsets, exclusions and token IDs. A remains byte-identical to the recorded SwissBERT Top-5 prompt.

## Evidence and verification

- Compilation: passed.
- Focused tests: 4 passed (10.355 s), including old reversal/metadata rejection, tampering/offset rejection, exclusions/review binding and a dry-run with network/inference entry points blocked.
- Offline source validation: PASS, 17 reviewed / 15 retained / 60 planned calls.
- Saved dry-run: zero inference calls; empty predictions JSONL.
- `make test`: executed exactly once; judge/label checks and compilation passed; 136 tests passed (14.178 s). Mock completion, Docker and expected-failure messages are test fixtures, not live evidence.
- C/D token counts: identical for all 15 cases. C adds 113–437 tokens over B. B/C is explicitly length-confounded and is not an isolated semantic-interference estimate.
- Historical source SHA-256 bindings preserved; no tracked Git diff; `git diff --check` passed.

Verification details: `docs/evidence/evidence_sensitivity_v2_checks_20261012.json`; frozen plan and annotations: `docs/evidence/evidence_sensitivity_{plan,annotations}_v2_20261012.json`; validation: `docs/evidence/evidence_sensitivity_offline_validation_v2_20261012.json`; dry-run: `data/experiments/evidence-sensitivity-v2-dry-run/`.

## Prediction changes

None measured: v2 inference has not run. Historical A/C predictions are preserved solely as selection provenance. No inference-quality claim is made.

## Uncertainties

Post-hoc selection from previously observed cases prevents independent generalisation claims. Committee opinions are evaluated as attributed statements, not certified objective facts. Rows 1401/1475 have bare “the initiative” claims; their identity follows recorded source context. Row 455 has a disputed entailment label; row 550 cannot support a booklet-wide absence argument from short evidence. Dataset labels remain unchanged.

The installed tokenizer warns about its regex behaviour. The exact existing mlx-lm loader/template was retained, with cached tokenizer file hashes and frozen token counts; no silent correction or weight load occurred. Future live usage must match frozen prompt counts or the runner records an error. Runtime determinism and model quality remain unmeasured. Printed/physical pages 18–19 for row 455 and page 7 for row 195 were also visually inspected.

## Changed files

- `src/evidence_sensitivity_v2.py`
- `tests/test_evidence_sensitivity_v2.py`
- `docs/evidence/evidence_sensitivity_annotations_v2_20261012.json`
- `docs/evidence/evidence_sensitivity_plan_v2_20261012.json`
- `docs/evidence/evidence_sensitivity_offline_validation_v2_20261012.json`
- `docs/evidence/evidence_sensitivity_v2_checks_20261012.json`
- `docs/EVIDENCE_SENSITIVITY_V2_SOURCE_REVIEW_20261012.md`
- `docs/EVIDENCE_SENSITIVITY_V2_HANDOFF_20261012.md`

## Next experiment and execution status

After independent ChatGPT confirmation, execute the frozen 60-call A/B/C/D diagnostic once, with zero retries. It provides descriptive paired evidence sufficiency and order sensitivity for these retained cases. Preserve append-only records; interpret B/C with its measured length difference.

A Python process (PID 75262) was already listening on 127.0.0.1:8080. It was neither started nor stopped here; its model/revision was not probed in this session. The live runner requires matching pinned metadata. Reuse it only if it is the documented matching server; otherwise stop it manually and start the pinned server. Do not execute the following commands until the independent reviewer confirms all 15 retained cases, the two exclusions, and the distractors.

### Commands after confirmation

From the existing checkout, record the actual external confirmation. If the reviewer requests scientific changes, revise separately and do not run this approval command.

```bash
cd /Users/liyitian/Documents/Hackathon26/track_2a
../.venv/bin/python - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path('docs/evidence/evidence_sensitivity_annotations_v2_20261012.json')
a = json.loads(p.read_text())
a['overall_status'] = 'confirmed_by_independent_chatgpt'
a['reviewer'] = 'Independent ChatGPT confirmation recorded by user'
a['reviewed_utc'] = datetime.now(timezone.utc).isoformat()
for case in a['cases']:
    case['review_decision'] = 'approved' if case['primary_analysis'] else 'excluded'
p.write_text(json.dumps(a, ensure_ascii=False, indent=2) + '\n')
PY
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python src/evidence_sensitivity_v2.py validate
```

If needed, start the pinned server in a separate terminal after manually freeing port 8080:

```bash
cd /Users/liyitian/Documents/Hackathon26/track_2a
../.venv/bin/python src/serve_experiments.py --context 81920
```

Then execute in another terminal:

```bash
cd /Users/liyitian/Documents/Hackathon26/track_2a
../.venv/bin/python src/evidence_sensitivity_v2.py run --live \
  --context 81920 --retries 0 \
  --out data/experiments/evidence-sensitivity-v2
```

Resume an interrupted run with identical arguments plus `--resume`. Use `--resume --retry-failed` only if explicitly choosing to retry recorded failures; that can add calls beyond the initial 60. Stop any server you started manually afterwards. Return the live directory’s manifest, events, predictions and summaries for review.

**Stop point:** independent ChatGPT review of this v2 package. This preparation does not authorise the live run.
