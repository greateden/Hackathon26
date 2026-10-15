# Submission team review — 15 October 2026

Review 11:00–13:00 CEST; intended submission Thursday evening. Deadline:
16 October 2026, 12:00 CEST. **This is not an unconditional release certificate.**
VERIFIED = exercised this release; SOURCE-RECORDED = earlier evidence;
NOT TESTED / BLOCKED / HUMAN DECISION REQUIRED are explicit limitations.

## Evaluation integration verification (15 October)

This section supersedes the earlier single-request entrypoint instructions below.
Only relevant files were extracted from Mikal's candidate copy at
`10d431535cc4cadf622da98718dbe40e35cb126d`; the branch/project was not merged.
The actual `track_2a/` now contains the evaluation CLI, offline encoder packaging,
Compose entrypoint compatibility and adapted/new contract tests.

| Contract | Status / evidence |
|---|---|
| Mixed A/B `--input` / `--output`, UTF-8 and ID preservation | VERIFIED with mock completions; failed IDs receive explicit error rows |
| linux/amd64 CPU image | VERIFIED on Colima ARM64 through amd64 emulation; native x86 host NOT TESTED |
| Bundled encoder, no runtime downloads | VERIFIED: pinned revision `7a91fa8a01af56c1f06060f7af3698ef5619e41c`; build-time local load; runtime `--network none` |
| `/data:ro`, non-root `/output` | VERIFIED in container; initial host `/tmp` fixture mount failed, shared-home fixture passed |
| Task A grounded evidence, page numbering, metrics | VERIFIED against synthetic PDF and mock HTTP usage; page 1, exact source text, 100 input / 20 output tokens per case |
| Task B vote and optional evidence | VERIFIED for all three labels and nine language pairs; no identity gate; prompt changed, quality NOT TESTED |
| Proxy injection | VERIFIED mock: BASE_URL/API_KEY override aliases, no models/tokenise request required, exact response-model check retained |
| Nine language combinations / adapters | VERIFIED structurally; existing booklet-language adapter for both source/query unchanged; quality NOT TESTED |
| Extraction cache | VERIFIED one extraction for two same-PDF requests; bounded eight-entry batch-local cache |
| Gold/credential isolation | VERIFIED normalisation excludes gold fields; allowlisted Docker context; dummy-only mock credentials; no real key read or baked into image |
| Native regression | VERIFIED `make test`, repository `.venv/bin/python`, 216 tests, exit 0, plus judge/source checks; local ignored data/cache available |
| Final focused checks | VERIFIED submission 9, P0 17, output gates 18; exit 0; `git diff --check` passed |
| Local image | `votelens:evaluation-20261015`, image ID `sha256:0cbcee56ba91d84dfce3f73adfa6c9328b7b5a220329995adc769cd4b7978c1a`; not a registry publication digest |
| Live integrated CSCS / benchmark | NOT TESTED; zero new real requests; 54-case benchmark not repeated |
| Notebook | PRESENT at `docs/HackApertus-demo.ipynb`; `LIVE_RUN=False`; configuration/display execution is offline; saved outputs remain historical. Static research demo remains separate. |

Reproduction: [evaluation commands and offline Docker contract test](RUNNING.md#authoritative-ost-evaluation-entrypoint-15-october-integration).
The committed `tests/docker_evaluation_contract.py` runs the actual CLI as a subprocess
inside the non-root, network-disabled container with a loopback mock endpoint and real
bundled encoder. It tests one A and one B input, not model quality. Build-time warning
about `LLM_TOKEN_PREFLIGHT` is a name heuristic: the value is `optional`, not a secret.
The unused XMOD pooler is initialised by Transformers; retrieval uses hidden-state mean
pooling, unchanged from the existing encoder implementation.

**BLOCKED for merge/submission readiness:** no guaranteed valid prediction for every
input ID on inference/gate failure. Error rows retain `label: null`, never fabricated
labels; batch exit 1 deliberately signals incompleteness. Organisers must confirm how
such failures are scored/handled. A published pullable image is still required and was
explicitly not published in this task. Qualifying Macro-F1 (A >= 0.60, B >= 0.75) is not
established for the integrated path; below either threshold the submission scores zero.

Task A's 29/54 recorded rejections (15 invalid/null identity, 14 unrecognised) reproduce
the historical gate. The current implementation permits deterministic recovery only
for schema-consistent Neutral responses without evidence citations, and only when the
complete requested vote title occurs in a selected source passage. It does not accept
partial, ambiguous, non-neutral or wrong-proposal matches and has no new live score.
An offline trace of the hash-matched saved raw records found that 13 of the 15
historical null-status Neutral responses satisfy this exact-title condition; the
other two and all 14 non-neutral/unrecognised responses remain rejected. This is a
post-hoc contract replay on exposed development records, not a new Macro-F1 result.
All 18 gold-Neutral cases were rejected in that historical run (12 raw Neutral, six raw
Contradiction); candidate Macro-F1 was 0.491. These remain historical development facts,
not new results or Task B quality estimates. No item-level prediction improvements are
claimed. Next experiment: blind human review of those rejected cases to distinguish
correct vote scope from wrong-proposal evidence before any gate change.

Remaining team decisions: official error-row policy; gate/scoring risk; approved image
registry/tag and publication owner; final team/contribution details and demo access.
No model server was started and no live commands are needed to reproduce the mock check.

## Current candidate

- Release work is on `main`; confirm the final local and remote SHA with `git log -1`
  after the verified release commit.
- **VERIFIED** default: official `swiss-ai/Apertus-v1.5-70B`, external CSCS
  `https://api.inference.cscs.ch/v1`. Existing authorised key worked (file 0600);
  never distribute it. 70B selected for proven deployment, not inferred accuracy.
- CSCS lists official 8B too; **NOT TESTED** here. Managed NVIDIA 8B remains
  explicit, unsuitable for this Apple Silicon host and unverified.
- Task A remains `vote-aware-v1` with unchanged dense retrieval and source/citation
  requirements; the narrow exact-title identity recovery is described above. Task B
  carries vote context and accepts optional citations.
  No automatic model fallback exists.

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
The development demo may download the PDF; the rebuilt image bundles SentenceSwissBERT. A local
PDF under mounted `/app/data` and judge-supplied request path also work by contract;
no application edit is required. This credential-dependent route is not self-contained.

Exact `/v1/models` and completion identity, positive integer token usage,
`finish_reason=stop` and supplied-source evidence are checked. Optional preflight
uses provider usage; it cannot independently detect silent prompt truncation.

## Earlier single-request release verification

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
