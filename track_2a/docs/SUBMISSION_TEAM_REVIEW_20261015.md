# Submission team review — 15 October 2026 (checklist)

Prepared for the Thursday 15 October review (approx. 11:00–13:00 CEST), ahead of the
intended Thursday-evening submission and the official deadline of **16 October 2026,
12:00 CEST**. This page is a *review aid*, not a submission-readiness certificate.
Status tags: **VERIFIED** (checked in this working tree) · **SOURCE-RECORDED** (documented
in `docs/` or `data/` records, not re-run now) · **NOT TESTED** · **HUMAN DECISION REQUIRED**.

## A. Project summary (one paragraph)

VoteLens is a document-grounded NLI diagnostic over official Swiss voting booklets. Given
a booklet (or a supplied reference) and a claim, it extracts pages (Poppler), retrieves
Top-5 within-booklet passages with SentenceSwissBERT, asks an Apertus v1.5 model (OpenAI-compatible
endpoint) to judge entailment/neutral/contradiction with cited source spans, and validates
the model answer against an output contract (vote-identity gate, citation-occurrence check,
schema checks) before emitting the official JSON response; invalid outputs exit non-zero
with no lexical fallback. The research contribution is a failure anatomy at the
retrieval–judgement–validation interface, with one headline result about coverage (§B).
The submission path is `make run` → `compose.submission.yaml` → `src/booklet_app.py`.

## B. Headline result (with denominators)

**Stricter output validation can create a substantial coverage cost.** 54-case paired
development comparison on CSCS **Apertus v1.5 70B** (`swiss-ai/Apertus-v1.5-70B`), not the
8B submission target:

| | `dense-v1` | `vote-aware-v1` |
|---|---:|---:|
| Raw label accuracy | 40/54 | 41/54 |
| Strict correctness | 32/54 (59.3%) | 23/54 (42.6%) |
| Valid-output coverage | 43/54 | 25/54 |

Of the candidate's 29 rejected outputs, **18 had a correct raw NLI label**; of 18
gold-neutral cases, **none** became a valid accepted output. Conditional accuracy among
the 25 accepted outputs: 23/25 = 92%. Paired exact McNemar p = 0.122078.
Exploratory exposed-development evidence; multiple pipeline components changed together
(no single-factor causal attribution; do not attribute every error to the identity gate).
Source: `docs/evidence/vote_aware_paired_results_20261013.json` (**SOURCE-RECORDED**;
raw per-call records are git-ignored under `data/experiments/`). **NOT TESTED** on the
official 8B target — never present these numbers as 8B acceptance evidence.

## C. Current branch and commit

- Branch: `feature/votelens-research-positioning` (work stays here; no merge into `main`).
- Preparation base commit: `f424b3656200932be21377e9219615e7dc9c0224`; this checklist and
  the report changes are committed on top — confirm the exact SHA with `git log -1` on
  Thursday before quoting it.

## D. Submission artefact paths

- Markdown report: `track_2a/technical_report.md` (aligned to the official
  `HackApertus/project-template` `track_2a/technical_report.md` structure).
- Six-page PDF: `track_2a/docs/report/technical_report.pdf` (LaTeX source
  `track_2a/docs/report/technical_report.tex`; rebuild: `make pdf` from `track_2a/`).
- Research demo: `track_2a/docs/experience/courage-to-be-wrong/` (`index.html` + README;
  recorded-results static layer, no model/server/network; **not** a live inference
  service; no public hosting URL).
- Makefile submission entrypoint: `track_2a/Makefile` (`make run`; the repository-root
  Makefile forwards here). Request fixture: `track_2a/data/request.json`.

## E. Verified tests and remaining risks

- **VERIFIED** on 14 October 2026 (this tree, Apple Silicon macOS): `make test` exit 0 —
  judge/label checks, source compilation and **207 unittest regressions** (includes
  `tests/test_output_gate_contract.py`; the renamed
  `test_05_wrong_topic_evidence_not_rejected_by_mechanical_gate` documents that the
  citation gate is mechanical only and does *not* demonstrate semantic rejection of
  wrong-topic evidence). `make pdf` exit 0 — 6 A4 pages, no overfull boxes.
- **SOURCE-RECORDED** (earlier records, do not re-quote as current): 69/92/110-test runs
  of 11–12 October in `docs/PROJECT_STATUS.md`, `docs/SUBMISSION_READINESS_20261013.md`.
- Remaining risks: see §F–§M; the P0 list is §F (official 8B) and §J (metadata/licence).
- Note: `make test` is offline/portable; it does not test Docker, endpoints or corpora.

## F. Official 8B validation — unresolved

`make run` (default external mode) addresses whatever `LLM_BASE_URL` provides; default
`LLM_NAME=swiss-ai/Apertus-v1.5-8B` is checked against the endpoint's `/v1/models`
(`SUBMISSION_MODEL_REQUIRED=1`); no lexical fallback exists. **NOT TESTED** end to end
with official 8B weights. Docker Compose sets `LLM_TOKEN_PREFLIGHT=optional` (CSCS-style
endpoints without `/tokenize` are supported via strict usage/`finish_reason` checks; the
code default is `required`). Neutral output is supported (label 1, evidence list may be
empty); non-neutral evidence must match the supplied source verbatim. Beginner evidence
has `page: null`. Invalid/ungrounded/incomplete results exit non-zero. **Human
decision:** on Thursday, either run one clean `make run` against a provisioned 8B
endpoint (requires host Docker + an authorised endpoint — not started for this prep) or
submit with the runtime explicitly labelled NOT TESTED.

## G. Team / project name

`VoteLens: The Courage to Be Wrong` is the **provisional working title**, not an
irrevocable team decision (14 October meeting). The template header in
`technical_report.md` carries an explicit placeholder. **HUMAN DECISION REQUIRED:**
confirm project title, team name and how it is written.

## H. GitHub visibility

Private or public is an **organiser question** — no confirmation exists in the repo
(`docs/PROJECT_STATUS.md` rechecked the template on 12 October; challenge-specific rules
remain unconfirmed). **HUMAN DECISION REQUIRED:** ask organisers before 16 October 12:00
CEST; do not change visibility unilaterally.

## I. Devpost team registration

Submissions go through the event website; Devpost confirms the deadline
(**SOURCE-RECORDED**, `docs/PROJECT_STATUS.md`). Team registration and participation
requirements are **NOT TESTED/unverified**. **HUMAN DECISION REQUIRED:** one member
checks the challenge page and confirms what each member must do individually
(Devpost account, registration, team lead) — do this before Thursday evening.

## J. Team members, contributions, personal declarations

- Names, roles and per-member contribution statements: **HUMAN DECISION REQUIRED**;
  nothing in the repo may invent them. The report deliberately makes no claim about
  individual students' contributions and does not infer each teammate's AI usage.
- Reminder for all three members: each person must prepare/confirm their **personal
  declaration** (including their own generative-AI usage) — the team-level declaration
  (§K) does not replace it.

## K. AI assistance declaration

Location: `track_2a/technical_report.md` ("AI Assistance Declaration" section, after
§8) and the compact version in `docs/report/technical_report.pdf` (after the
conclusion). It states: substantial AI assistance (Qwen-based coding agents with
OpenCode; ChatGPT for research planning, interpretation and drafting; Codex for
cross-model repository auditing), the listed functions, team direction and
responsibility, automated-test/record checks, and that cross-model auditing is not
independent human verification and no independent human semantic adjudication was
performed. No changes needed unless a member objects.

## L. UZH ECTS (separate document)

The UZH ECTS declaration/report is **not** the HackApertus report. Expected to be a
separate two-page ACL-style report per course requirements — **NOT VERIFIED** what is
actually required this year. **HUMAN DECISION REQUIRED:** ask Michelle about ECTS
requirements (format, page limit, deadline, whether personal AI declarations are
individually required) before Thursday evening; do not assume the HackApertus
materials satisfy it.

## M. Licence and third-party data review

Report licence is set to CC-BY-4.0 per the official template. Code licence and
third-party data permissions are **not finally reviewed**: booklet PDFs and extracted
corpus are git-ignored and excluded from the Docker image; the demo redistributes only
short quotations and model-output strings (see `docs/experience/courage-to-be-wrong/README.md`);
SentenceSwissBERT/Apertus model-card terms and Swiss federal text reuse were not
verified as a licence audit. **HUMAN DECISION REQUIRED:** a final licence pass before
publication; add a repository `LICENSE` only after that decision.

## N. Final approval

Submission requires **explicit approval from all three members** after this review.
Do not submit on partial approval.

## O. Timeline

- Thu 15 October, ~11:00–13:00 CEST: team review (this document).
- Thu 15 October evening: target submission window after all-three approval.
- Fri 16 October, 12:00 CEST: hard deadline. No further code or experiment changes
  should be attempted inside this window; unresolved items above stay visibly open.

## Branch comparison for the review (no merge decided)

`main` is an ancestor of `feature/votelens-research-positioning`; the feature branch
adds (relative to `main`): the `vote-aware-v1` candidate work and paired evaluation,
the recorded demo under `docs/experience/`, the LaTeX/PDF report, new offline tests,
and the documentation above. Scientific/reporting quality is higher on the feature
branch. Official runtime scoring confidence is **not** automatically higher there: the
feature branch changes the default `make run` path away from `main.py`'s legacy stack,
and its default judge (the strict candidate with the identity gate) has the §B coverage
risk on exposed 70B development data, with official 8B NOT TESTED. `main` retains the
older default pipeline and lacks the new entry-point plumbing verification. The branch
choice for submission (and whether `vote-aware-v1` stays the default) is a Thursday
team decision, not an automatic consequence of this document.