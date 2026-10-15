# Submission team review — 15 October 2026

Review 11:00–13:00 CEST; intended submission Thursday evening. Deadline:
16 October 2026, 12:00 CEST. **This is not an unconditional release certificate.**
VERIFIED = exercised this release; SOURCE-RECORDED = earlier evidence;
NOT TESTED / BLOCKED / HUMAN DECISION REQUIRED are explicit limitations.

## Current candidate

- Feature branch only: `feature/votelens-research-positioning`; preparation began
  at `3d1f5c774eb6fc279377f772c72f6c194a5d0a4f`. Confirm final SHA with `git log -1`.
- **VERIFIED** default: official `swiss-ai/Apertus-v1.5-70B`, external CSCS
  `https://api.inference.cscs.ch/v1`. Existing authorised key worked (file 0600);
  never distribute it. 70B selected for proven deployment, not inferred accuracy.
- CSCS lists official 8B too; **NOT TESTED** here. Managed NVIDIA 8B remains
  explicit, unsuitable for this Apple Silicon host and unverified.
- CLI remains `vote-aware-v1`. No retrieval, prompt, identity or citation policy
  was weakened; no automatic model fallback exists.

## Commands and external requirements

Load the developer's existing credentials privately (not in a recording):

```sh
set +x
set -a
. "$HOME/.config/hackapertus/cscs.env"
set +a
make run
REQUEST_FILE=/app/data/examples/advanced-entailment.json make run
REQUEST_FILE=/app/data/examples/advanced-neutral.json make run
```

Judges need Make, Docker/Compose, network and their own authorised endpoint/key.
Compose uses `LLM_API_KEY` or `CSCS_INFERENCE_API_KEY`. No host Python/MLX is needed.
Advanced first use downloads the PDF and SentenceSwissBERT unless cached. A local
PDF under mounted `/app/data` and judge-supplied request path also work by contract;
no application edit is required. This credential-dependent route is not self-contained.

Exact `/v1/models` and completion identity, positive integer token usage,
`finish_reason=stop` and supplied-source evidence are checked. Optional preflight
uses provider usage; it cannot independently detect silent prompt truncation.

## Verification

See [release record](RELEASE_CANDIDATE_20261014.md) and
[compact real-call evidence](evidence/release_smoke_20261014.json).

| Check | Result |
|---|---|
| Beginner, real 70B Docker | VERIFIED, official label 0, app/make 0/0 |
| Advanced row 106, real PDF retrieval | VERIFIED, official label 0, app/make 0/0 |
| Advanced gold-neutral row 728 | Raw neutral; `invalid_vote_status`, app/make 1/2; failed smoke |
| Tracked-only export Beginner | VERIFIED, app/make 0/0; no venv/private corpus, reused image layers |
| `make test` | Exit 0, 207 tests, source/judge checks |
| Final `make test-docker` | Exit 0, 201 tests, 28 explicit data-dependent skips; network disabled |
| Earlier Docker tests | Missing fixtures, then MLX-only dependencies; non-zero attempts retained and corrected by isolation |
| `make pdf` | Final exit 0, six A4 pages; rendered pages inspected, figures readable, no clipping/overfull boxes |
| Demo data + JS syntax | Exit 0; snapshot checked against original records |
| Cold build / cold Advanced / Windows / x86-64 | NOT TESTED |

Four new inference calls total, no large experiment/retries. Unit tests are not
model acceptance evidence. Smoke outcomes are not benchmark scores.

## P0 scoring and remaining release conditions

**BLOCKED for unconditional scoring readiness:** historical 54-case Macro-F1 is
0.652 dense vs 0.491 candidate with invalid outputs retained. Candidate accepted
0/18 gold-neutral cases; a new neutral smoke reproduced rejection. Its 29 historical
rejections are identity failures (15 null/invalid, 14 unrecognised), not established
political-safety refusals. Dense's better score does not prove correct vote scope.
Removing the gate could admit wrong-proposal evidence. Evidence is insufficient
for a safe policy change; the risk remains visible for team review.

- [ ] All three members explicitly accept the current scoring risk or agree a
  separately validated repair. No silent promotion based on accepted-only accuracy.
- [ ] Confirm judge credential/endpoint arrangements and actual reviewer access.
- [ ] Approve final team/project names, member list and contributions. Current
  VoteLens title is provisional; no contributions/participation are invented.
- [ ] Approve the research headline; evidence preserved, strategic choice not made.
- [ ] Confirm code contributor authority and remaining external excerpt permissions.
  Root Apache-2.0 added; docs CC-BY-4.0; upstream datasets/models retain their terms.
  New team datasets would use CDLA-Permissive-2.0, not override upstream licences.
- [ ] Aline: follow [Pages preparation](DEMO_DELIVERY.md) Thursday morning after
  approval. Local Safari/static assets verified; no deployment URL exists yet.
- [ ] Mikal: record a real Advanced `make run` Thursday lunch/afternoon using the
  recording checklist. No video exists or was uploaded; audio optional.
- [ ] Replace the report Demo link only with a tested accessible site/video URL.
  Current link is the real repository demo README, for authorised reviewers;
  GitHub source preview does not run the interactive page.
- [ ] Confirm GitHub visibility/access with organisers before changing it.
- [ ] Confirm submission website procedure and each person's participation;
  the current official template says submissions are **not handled on Devpost**.
- [ ] Confirm Michelle's ECTS guidance: separate UZH report, format/length,
  deadline and individual AI declarations remain unverified. Do not invent guidance.
- [ ] Review preserved substantial AI Assistance Declaration; cross-model AI audits
  are not independent human verification. Each member confirms their own declaration.

## Sign-off and merge recommendation

| Member | Review / approval |
|---|---|
| Aline | Pending |
| Mikal | Pending |
| Third member | Pending; confirm public name |

Feature branch is prepared for review, not merged. Recommend merging only after
all-three review of the conditions above, including explicit scoring-risk and
credential acceptance. No main/default-branch/visibility changes or submission
were performed. Thursday-evening submission remains the target.

**One Thursday-morning action:** all three review the recorded Neutral failure
and decide whether to accept the documented gate policy for submission before
spending time on presentation polish.
