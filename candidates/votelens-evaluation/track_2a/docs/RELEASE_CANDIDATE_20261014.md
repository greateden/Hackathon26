# Release candidate validation — 14 October 2026

Starting branch: `feature/votelens-research-positioning`, clean at
`3d1f5c774eb6fc279377f772c72f6c194a5d0a4f`. No main merge, deployment,
visibility change or submission is authorised by this record.

## Selected runtime and contract

**VERIFIED:** external `swiss-ai/Apertus-v1.5-70B` at
`https://api.inference.cscs.ch/v1`; exact model-list and completion-model checks,
positive integer usage, consistent total, completed response and source-reference
checks remain enforced. `~/.config/hackapertus/cscs.env` existed with mode 0600;
`CSCS_INFERENCE_API_KEY` loaded into a controlled subprocess and worked. No value
was printed, copied or committed. The private file is not loaded automatically.
`LLM_API_KEY` takes precedence over the CSCS variable in Compose.

70B was chosen for the existing successful deployment history and new real Docker
success, not a claim of superior accuracy. The live model listing also offered
v1.5 8B, but no new 8B inference was run. The existing Apple Silicon Colima VM is
not a suitable managed NVIDIA host. No weights/server were provisioned. Managed
8B stays explicit and untested; its overlay now sets matching app/server model IDs.

The chain exercised was root Make → Track Make → Compose build/up → application
→ CSCS → official JSON. It needs Make, Docker/Compose, an authorised endpoint/key
and network; Advanced additionally needs PDF access and SentenceSwissBERT. It is
not self-contained. No host Python package or MLX server is used for this path.

## Four real calls, no retries

Compact telemetry and hashes: [release_smoke_20261014.json](evidence/release_smoke_20261014.json).
Raw diagnostics, outputs and logs remain in ignored `data/experiments/release-20261014/`.
All calls used 70B, `vote-aware-v1`, temperature 0, 512 output cap, optional token
preflight. Input usage is provider-reported, not independently reconstructed.

| Case | Expected / raw / accepted | Input / output tokens | Inference seconds | App / root make exit |
|---|---|---:|---:|---:|
| Beginner identical reference | entailment / entailment / 0 | 519 / 71 | 2.559 | 0 / 0 |
| Advanced row 106 | entailment / entailment / 0 | 1677 / 84 | 1.395 | 0 / 0 |
| Advanced row 728 | neutral / neutral / rejected | 1744 / 125 | 1.916 | 1 / 2 |
| Tracked-only export Beginner | entailment / entailment / 0 | 519 / 71 | see JSON | 0 / 0 |

Advanced gold comes from the unchanged MIT-labelled OSTswiss v1.1 dataset,
zero-based rows 106/728; not independent human adjudication. Gold never entered
requests. Accepted non-neutral evidence passed source checks. Neutral failed
`invalid_vote_status` with null identity and no evidence, and is **not a successful
smoke**. Three of four calls produced valid official JSON; this selected smoke is
not an accuracy benchmark. No prediction policy changed and no historical record
was rewritten.

The tracked-only export excluded venv, `.env`, historical corpus and model caches,
used a new Compose project/cache, and succeeded on Beginner. Docker build layers
were reused: this does not establish a fully cold image build, a cold Advanced
encoder download, Windows or Linux x86-64 execution. The Advanced run used the
existing encoder cache on Linux aarch64.

## Existing 54-case failures: bounded offline analysis

The unchanged raw file SHA-256 is
`1d7553e0f85498b8c83316e35b34836f1db3fdba508623745509c00d4c34d1fe`.
Recomputed raw/strict/valid counts: dense 40/32/43; vote-aware 41/23/25, each /54.
Three-way Macro-F1 (invalid outputs retained as errors): 0.652 / 0.491.

| Category | Evidence and interpretation |
|---|---|
| A Political refusal | No explicit political-safety refusal identified. The keyword “refuse” in row 1075 describes a landlord refusing subletting, not model refusal. Rejections alone are not evidence of safety refusal. |
| B Incorrect NLI | 14 dense and 13 candidate raw labels disagree with dataset gold. Of 29 candidate rejections, 11 have incorrect raw labels; this overlaps identity failure. Semantic cause is not independently adjudicated. |
| C Schema/format | Five candidate responses used the existing single trailing-brace recovery; no final parse failures. Null vote status (15) is classified under D, not a JSON parsing failure. |
| D Vote identity | All 29 candidate rejections: 15 invalid/null status, 14 unrecognised. 18 rejected raw labels match gold. |
| E Citation/evidence | All 11 dense invalid outputs fail the non-neutral grounding requirement on offline rendering. Candidate citation checks are not reached after identity failure; 25 accepted candidate citations pass mechanical provenance, not semantic adjudication. |
| F Endpoint/execution | No endpoint failure in these 108 recorded calls; four new smoke calls reached completed model responses. Application rejection is distinct from endpoint failure. |

All 18 candidate gold-neutral cases were rejected (12 raw neutral, six raw
contradiction). Row 728 retrieves the climate proposal instead of the requested
COVID amendment; accepting a coincidentally correct neutral label does not
establish correct scope. Dense emits an accepted wrong entailment on this row.
Dense can render the official JSON shape, but omits vote-scoped retrieval and
independent proposal identity; it is not a demonstrated semantic-contract repair.

**Decision:** preserve the existing gate and prompt. No narrow policy change is
sufficiently justified by these confounded observations. No guessed labels,
fabricated citations or political-refusal workaround was introduced. This leaves
a serious Macro-F1 risk requiring explicit team acknowledgement. Further gate
research is outside this release task.

## Reports, demonstration and licensing

Markdown retains the official sections and AI declaration; draft status and
internal brainstorming comments were removed. Active model claims now identify
70B, and historical 8B MLX results remain distinct. The existing research finding
is preserved; final headline choice remains a three-member decision. Long-report
relative links were repaired. Literature URLs were checked; blocked DOI landing
pages for BM25, RRF and Dietterich were checked through Crossref title metadata.
No reference discrepancy was found. Existing numerical evidence was checked
against compact/source records and the demo's recomputation; no inference study
was repeated.

PDF: six A4 pages after `make pdf`, rendered with Poppler and visually inspected.
Figures enlarged for readability; axes, captions and page edges show no clipping.
First rebuild failed on a newly introduced unescaped underscore and overflowed
onto seven pages; that was corrected, redundant prose shortened, and the final
build exited 0 with no overfull boxes. AI assistance remains explicit and is not
represented as independent human verification.

Static demo: five layers opened in Safari; keyboard navigation and the corrected
text were checked. Sibling assets resolve locally. Fixed literal HTML tags shown
as text and a row-1344 gloss that incorrectly attributed D's neutral output also
to A (raw A is contradiction). Regenerated snapshot from unchanged raw records;
no prediction changed. No recording exists among tracked video files. No website
was published. [Demo delivery instructions](DEMO_DELIVERY.md) assign the future
Pages/recording tasks; the report's existing repository README is a real artefact,
but a hosted interactive URL and authentic video remain unfinished.

Root Apache-2.0 LICENSE added for team-authored code; documentation remains
CC-BY-4.0. [Third-party notices](../../THIRD_PARTY_NOTICES.md) separate external
MIT-labelled examples, booklet excerpts, model and dependency terms. No PDFs or
weights added. Source review found no vendored code conflict; contributor authority
and existing excerpt permissions still require human confirmation before publishing.

## Verification and release decision

- `make test`: exit 0, 207 tests, judge checks and source compilation.
- Initial `make test-docker`: root exit 2, six missing-fixture errors (193 tests,
  10 skipped). Native historical data mounted into the test container activated
  checks whose tracked plans were absent from its image.
- A read-only fixture mount exposed two MLX-tokeniser errors and one related failure (root exit 2). A subsequent Compose `--tmpfs` attempt was rejected as an unsupported flag (root exit 2). Final fix: build the image, then run portable tests with `docker run --network none --tmpfs /app/data`, excluding host-only experiment records. Final exit 0: 201 tests, 28 explicit skips. Submission image/runtime unchanged.
- `courage_data.py`: exit 0, ledger/source hashes checked; generated facts updated.
- `node --check .../app.js`: exit 0.
- `make pdf`: final exit 0, six A4 pages; initial failure disclosed above.
- `git diff --check` and Markdown local-link checks: final checks before commit.

Merge recommendation: technically reviewable feature branch, **not unconditional
submission readiness**. Team must accept/resolve Neutral scoring risk, confirm
judge endpoint credentials, approve names/headline/licensing, finish an accessible
demo, and obtain all-three sign-off. Visibility and ECTS/Michelle guidance remain
human decisions. Target remains Thursday evening, before 16 October 12:00 CEST.
