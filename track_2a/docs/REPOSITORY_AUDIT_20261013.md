# HackApertus Track 2A — repository audit, 13 October 2026

## Executive summary

**The recorded headline results survive this audit; submission readiness does not follow from them.** The application implements specified-booklet multilingual NLI, explicit endpoint identity checks and source-grounded output. Its CLI still forces `vote-aware-v1`. On the preserved 54-case CSCS 70B comparison, this candidate produced 23/54 valid, correct outputs against 32/54 for `dense-v1`, and rejected all 18 gold-neutral cases. This is a submission risk, not proof that every rejection should be accepted.

The audit reproduced and repaired corpus publication, cached-PDF validation, manifest/event consistency, incomplete paired reporting and missing-record diagnostic defects. These changes do not alter retrieval, prompts, parsing, labels, citation acceptance or historical predictions. Eleven regression tests were added. The original full check passed 163 tests; the final full check passed 174. A continuation check passed all 17 tests in the three affected test modules.

The main unresolved engineering issues are non-hermetic offline tests, incomplete pre-inference provenance enforcement in the paired runner, and event-only interruption recovery in the evidence-sensitivity runner. The latter can issue another call for an unknown previous outcome; it was reproduced with a mock, not real inference. Research changes to vote grounding, neutral acceptance and citation boundaries remain deferred. No live inference, model download, container build or deployment was performed.

Evidence terminology in this report:

- **VERIFIED:** reproduced by an executed check, arithmetic reconstruction or a direct comparison of saved artefacts.
- **OBSERVED:** present in source, configuration, documentation or recorded output.
- **INFERRED:** consequence supported by those observations, without a new deployment or quality experiment.
- **NOT TESTED:** explicitly outside the executed checks.

Paths below are relative to `track_2a/` unless stated otherwise. Line references describe the audited source after the local fixes. Severity reflects impact and exposure; an unfavourable research outcome is not automatically a software bug.

## Repository state and scope

Branch: `experiment-multilingual-retrieval-ablation`. Initial local and remote HEAD were both `34222658fd17a0d3a76dade8144d52cd0e0a1859`. Relevant preceding commits were `cc755d4` (candidate), `d750b10` (pre-candidate implementation), `4d63cb2` (evidence sensitivity) and `701472e` (retrieval ablation analysis). No branch switch, merge, history rewrite, PR, tag or release is part of this audit.

At entry, `technical_report.md` already had an academic revision: 144 added and 52 removed lines. It was read but not edited, reverted, staged or committed by the audit. Its continuation SHA-256 is `e921899f3ada6de773dc202d3082c6818c60107e08f674ebeacd17856105c0b6`. That revision is available locally but remains pending integration. An untracked repository-root `.opencode/` directory appeared by continuation and was likewise left untouched and unpublished.

Inspection covered the submission path, current runners, evaluation/diagnostic helpers, legacy routing, tests, tracked documentation, Docker/Make/dependencies/ignore rules, local experiment inventories and the preserved evidence. The original tracked inventory contained 126 files and no tracked CI configuration. All tracked Python files parsed and all 27 tracked JSON files decoded. This is a bounded repository audit, not a proof of every possible execution path or a dependency vulnerability assessment. Upstream `repos/` and installed packages were not modified.

The interruption removed `/tmp/hackapertus-audit-20261013/`. Earlier tool outputs remain in the audit conversation, but the original temporary scripts/logs are not distributed evidence. The continuation reused those recorded results, reviewed the actual diff, and refreshed focused tests, frozen paired hashes and completed-summary consistency. It did not repeat the full audit or full suite. The reproductions and permanent regression names below make the implemented fixes reviewable without those temporary files.

## Architecture and execution paths

| Entry/interface | Actual route and defaults | Boundary/evidence |
|---|---|---|
| Repository-root `make run` | Forward to project Makefile; external `compose.submission.yaml`; `python3 booklet_app.py` | Configured endpoint required. No managed GPU by default. |
| `make run SUBMISSION_MODE=managed` | Add `compose.managed.yaml`; NVIDIA vLLM service; health-gated CPU app | Default official v1.5 8B; required `/tokenize`; runtime not verified here. |
| `make run-cscs` | External CSCS v1.5 70B, credential supplied by environment, optional token preflight | Historical real Docker smokes only; no new request. |
| `booklet_app.main`, line 655 | Strict input JSON, request validation, force candidate, endpoint preflight, classify, render official JSON | Flat CLI input also becomes `vote-aware-v1`; caller cannot select dense via CLI. |
| `classify`, line 537, flat Python request | Defaults to `dense-v1` unless explicitly versioned | Historical runners preserve claim-only query and original prompt. |
| Official nested Python request | `normalise_request`, line 223, assigns candidate | Beginner uses reference directly; Advanced uses booklet/vote. |
| `experiment_runner.py` | Cached-input preflight, native pinned MLX comparison; separate submission-smoke path | Full/retrieved methods; append-only attempts; contract fingerprint. |
| `vote_aware_paired_eval.py` | Frozen 54-case plan, pinned encoder preparation, frozen Top-5, alternating AB/BA CSCS calls | Explicit dense/candidate arms; strict and raw scores separated. |
| `main.py`, `run-native`, historical `compose.yaml` | Legacy global-search application, lexical/legacy defaults | Distinct task; not the current official submission. |

The production Advanced request flows through `validate_request` (line 268), `load_booklet` (132), `passages` (176), `BookletRetriever.retrieve` (189), `build_messages` (211), `SubmissionJudge.judge` (338), candidate parsing and reference resolution, then `submission_output` (609). Beginner bypasses PDFs and retrieval and assigns the supplied reference source ID `e1` with a null page.

PDF identity uses the selected source and a SHA-256 of PDF bytes. HTTPS submission caches use a URL digest rather than a basename. Poppler extracts UTF-8 physical pages; blank pages are omitted only after page enumeration, preserving page numbers. Page text is stripped, then partitioned into consecutive 900-character chunks. Candidate offsets refer to this extracted, stripped text, not PDF byte positions or printed page labels. Scanned PDFs with no text fail; OCR is not implemented.

Dense retrieval uses SentenceSwissBERT mean pooling, the known booklet-language adapter for both query and passages, stable descending cosine ranking and Top-5. The candidate query prepends vote metadata; the dense query is the original claim. There is no within-booklet proposal-section filter. Duplicate content on different pages can occupy multiple slots. Neither path is the historical global retrieval task using unknown evidence language.

The submission judge allowlists official v1.5 8B/70B and, outside Docker submission, the specified MLX conversion. It checks the exact model listing and response model, one completion, positive integer token usage, optional total consistency, context budget and `finish_reason=stop`. Required preflight independently tokenises and checks the reported prompt count. Optional preflight relies on server reports and cannot prove absence of silent server-side truncation. Optional mode does not send the recorded default seed or thinking-control extension. HTTP failures remain errors; there is no lexical fallback.

Candidate JSON permits only one surplus final closing brace and retains the original response. Duplicate JSON keys, ambiguous multiple objects and other tested malformed forms fail. Advanced candidate acceptance requires recognised vote identity and a selected vote passage, separately from evidence references. Non-neutral results need sufficient evidence and references; neutral results need insufficient evidence and empty references. Source selection copies exact spans, rejects unknown IDs, duplicates and invalid offsets, and is recomputed before official output. These checks establish provenance, not whether the selected text identifies the correct proposal or logically supports the label.

Official output comprises ID, numeric/string label, page/text evidence and actual token/latency metrics. Existing output files are refused. Diagnostics retain additional source, response and offset details. `labels.py` centrally maps entailment/neutral/contradiction to 0/1/2.

Other components: `retrieval_ablation.py` implements dense, symmetric BM25/RRF and proposition reranking; `prompt_ab_experiment.py` freezes shared evidence across prompts; `diagnose_evidence.py` separates retrospective diagnosis and Oracle runs; `evidence_sensitivity*.py` materialise reviewed evidence conditions; `eval_nli.py` scores failures as errors using pure Python; `eval_e2e.py` performs the separate global retrieval task; `hybrid_retrieval.py` supplies BM25, RRF and historical caches; `serve_experiments.py` instruments the pinned native loader. Older smoke scripts and scratch probes are historical utilities, not production acceptance tests.

## Verified capabilities and limits

**VERIFIED offline:** request/label/error contracts through regression tests; candidate bounded syntax recovery; exact source offsets for checked citations; preserved dense prompt/ranking behaviour with deterministic encoders; saved result arithmetic; static external/managed Compose configuration. All nine language-pair deterministic comparisons with `d750b10` matched dense passage records, scores and prompt bytes. This establishes compatibility of the tested routes, not real-model reproducibility across machines.

**VERIFIED from historical records:** native 6-bit MLX v1.5 experiments, CSCS 70B experiments and recorded Docker smokes. The paired audit independently checked 36 cached PDF identities, 108 prepared prompt/evidence hashes and 89 citation records. No source or prompt mismatch was found. Re-rendering all 108 saved outcomes reproduced their recorded validity and predictions.

**NOT TESTED in this audit:** official v1.5 8B deployment, managed NVIDIA startup, fresh image/weight downloads, cold dependency installation, Windows/Linux runtime, OCR, performance under hostile PDFs, or independent model quality. A 70B Docker success is not an 8B deployment result. Endpoint model strings are not cryptographic weight attestation.

## Experimental history and reconstructed results

| Preserved directory under `data/experiments/` | Rechecked outcome | Scope |
|---|---|---|
| `v15-grouped81-80k/` | 162 recorded attempts; 161 completed, one failed. Full 42/81, accuracy/F1 .519/.479; retrieved 65/81, .802/.807 | Pinned local MLX; exposed development corpus. |
| `v15-grouped81-oracle-20261012/` | 19/19 complete; .842/.846 | Post-hoc selected errors/controls, not a production gain. |
| `retrieval-ablation-v1/` | 243/243 complete; A .827/.824, B .802/.797, C .790/.784 | 81 cases per arm; no candidate promotion supported. |
| `prompt-pilot27-v1/` | 54/54 complete; both prompts 23/27; macro-F1 .850 and .853 | Same accuracy does not imply identical class-specific F1. |
| `evidence-sensitivity-v2/` | 60/60 complete; A 8/15 (.533/.593), B 15/15 (1/1), C 14/15 (.933/.933), D 11/15 (.733/.786) | Case-informed evidence; only two gold classes; selected diagnostic. |
| `vote-aware-paired-v2/` | 108/108 calls; 54 pairs, 49 votes, 36 PDFs | Complete-system comparison on CSCS 70B. |
| `vote-aware-paired-v1/` | Zero prediction records | Preparation is not an additional completed experiment. |

The paired v2 reconstruction is:

| Metric | Dense | Vote-aware |
|---|---:|---:|
| Raw correct | 40/54 (.7407) | 41/54 (.7593) |
| Strict correct | 32/54 (.5926) | 23/54 (.4259) |
| Valid output | 43/54 (.7963) | 25/54 (.4630) |
| Strict macro-F1 | .652 | .491 |
| Errors | 11 | 29 |
| Gold-neutral failures | 1/18 | 18/18 |
| Raw-correct rejected | 8 | 18 |
| Input tokens | 69,023 | 89,243 |

Candidate failures: 14 `vote_unrecognised`, 15 `invalid_vote_status`. Five surplus-brace recoveries all produced accepted outputs. All 25 accepted candidate raw objects contained the six instructed fields. Strict paired outcomes were 18 dense-only correct, nine candidate-only correct, 14 both correct and 13 both incorrect. Independently evaluating the exact binomial tail gives McNemar p = 0.12207812070846558; the rounded saved .122078 is correct. The difference is -9/54 = -.1667. Wilson interval implementation follows the usual score formula. Such intervals/tests do not remove case selection, shared-PDF clustering or dependence between related votes.

Strict candidate gains: rows 106, 21, 242, 289, 405 (gold entailment); 1383, 1450, 1407, 1224 (gold contradiction). Losses: rows 964, 584, 912, 558, 785, 977, 562, 904, 789, 507, 534, 807, 936 (gold neutral); 435, 137 (gold entailment); 1115, 1198, 1148 (gold contradiction). These are historical between-arm outcomes. **This audit changed no prediction.**

Raw labels, strictly accepted outputs, accepted-output conditional accuracy and citation source occurrence answer different questions. In particular, 23/25 candidate conditional accuracy excludes every neutral case and cannot establish general superiority. Macro-F1 averages gold-supported classes in `eval_nli.summarise`; the 15-case evidence diagnostic therefore averages two classes, while the balanced paired evaluation averages three. Errors remain false negatives and remain in attempted-row denominators. Missing calls are separately reported rather than silently assumed successful.

Plans and compact evidence are tracked; most raw records, PDFs and caches are ignored. Hashes identify local content but do not make it available to a remote reviewer. Historical v1.1 global retrieval, oracle and lexical measurements remain distinct from specified-booklet v1.5 work. The archived withdrawal of asymmetric BM25/oracle-language comparisons must not be replaced by the older ranking claims still present in historical guidance.

## Findings ranked by severity

### A01 — HIGH · DESIGN LIMITATION · candidate submission default has lower accepted accuracy

**Location:** `src/booklet_app.py:513`, `:537`, `:655`; paired evidence JSON; `docs/PROJECT_STATUS.md:5`.

**Observed/verified:** the CLI forces the candidate; strict accuracy .4259 versus .5926 and valid-output rate .4630 versus .7963. All gold-neutral candidate cases fail identity acceptance. Identity requires a passage from the same Top-5 supplied for judgement; there is no independent document-identity stage. The code can represent a valid neutral response with recognised identity, but the recorded model did not satisfy that contract on these neutral cases.

**Reproduction:** inspect CLI assignment and replay recorded results through `record_outcome`; the compact evidence contains counts and failure audit. **Expected:** deployment selection should account for valid end-to-end output, not raw accuracy alone. **Impact:** lost submission answers; raw-correct rejections are not automatically safe answers. **Resolution:** unresolved, no default/prompt/validation change. Agree a versioned identity/neutral contract and adjudicate failed evidence before another treatment. No historical measurement was invalidated by the audit.

### A02 — HIGH · CONFIRMED BUG · incomplete ingestion overwrote canonical corpus

**Location:** `src/fetch_booklets.py:192`, publication at `:254`.

**Original reproduction:** in a temporary root, preserve a non-empty `corpus.json`, patch the dataset to zero rows, and call `main(['--skip-fetch'])`. It exited 0 and replaced the corpus with `[]`. Missing documents and a limited smoke run could likewise replace the global output. The unconditional write preceded the missing-document check.

**Fix:** reject empty/incomplete builds before publication; require a separate `--out` for limited runs; publish completed JSON through a temporary file in the output directory and replacement. Preserve an existing output permission mode; new outputs use 0644. Final review reproduced and corrected the temporary file's initial 0600 permission regression before publication. Valid full ingestion/chunking is unchanged. **Regression:** all five tests in `test_ingestion_safety.py`, including corpus byte preservation and successful separate subset output. **Historical impact:** no stored corpus was rebuilt or altered. **Status:** fixed for empty/missing/limited publication and torn writes; stale extraction provenance remains A14.

### A03 — HIGH · CONFIRMED BUG · paired records were not bound to their own event

**Location:** `src/vote_aware_paired_eval.py:242`.

**Original reproduction:** an event for `0:dense-v1` with attempt ID `a` and a prediction for `1:vote-aware-v1` with the same ID passed validation when both keys were scheduled. Membership in an attempt-ID set did not bind record metadata to the event.

**Fix:** map attempts to events and compare key, row, case, arm, gold, attempt number and configured model. Seven independent mutations are rejected by `test_prediction_must_match_its_event_identity`. **Expected/impact:** a resume must not score one attempt as another case. **Historical impact:** all 108 existing records pass the stronger check; no corrupt recorded binding was found. **Status:** fixed for event/prediction binding; broader manifest trust is A08.

### A04 — HIGH · CONFIRMED BUG · advertised offline suite depends on ignored assets

**Location:** `tests/test_vote_aware_paired_eval.py:31`; `tests/test_evidence_sensitivity_v2.py:16`; `tests/test_retrieval_ablation.py:24`; `Dockerfile:34`; Makefile `test`/`test-docker`.

**Reproduction:** copy tracked project files to a temporary tree and run only `test_vote_aware_paired_eval.py` with the existing interpreter. Five tests passed and the selection test failed with `FileNotFoundError` for ignored `data/eval/mnli_swiss_v1.1.jsonl` (six tests before additions). Other tests reconstruct ignored predictions/PDFs and import an MLX tokenizer requiring cached assets. Docker copies only two evidence plans and excludes MLX.

**Expected:** the advertised no-model/no-corpus offline target should run from tracked fixtures. **Impact:** native 174-pass result is environment-specific; current Docker/clean-checkout suite success is not established by an older 110-test pass. **Status:** unresolved. Replace these dependencies with small deterministic fixtures and retain separately named explicit integration checks. This needs coordinated fixture/test separation; skipping assertions would hide the defect. No missing-Metal failure occurred in this audit's native runs.

### A05 — HIGH · CONFIRMED BUG / RECOVERY DESIGN WEAKNESS · event-only interruption can repeat inference

**Location:** `src/evidence_sensitivity_v2.py:469`, especially `:493–501` and event append at `:525`.

**Reproduction:** a one-item copy of the plan, matching manifest, empty predictions and an existing `A_original` event with no prediction was resumed with a mocked connection/judge. The runner made four judge-double calls, including `A_original` again, exited 0, and left five events but four predictions. Network was disabled. The original probe was a temporary script; its output was retained in the audit conversation before the temporary directory disappeared.

**Root cause:** pending calls are derived solely from predictions; prior events are never reconciled. The existing resume regression covers a completed saved prediction, not termination after event append and before outcome persistence. A client cannot know whether a remote inference completed in this interval without endpoint idempotency/query support. Nevertheless, silently issuing another call and omitting the unknown attempt is avoidable: stop explicitly, or record an unknown outcome and require an explicit retry policy.

**Impact:** potential duplicate paid calls and misleading attempt accounting after hard termination. **Historical impact:** the saved sensitivity run has exactly 60 events and 60 predictions with matching attempt-ID sets; no such duplicate was found. **Status:** documented, implementation unchanged. Fixing the representation requires decisions about unknown outcomes, retry authority and missing latency; inventing zero measured latency is not an acceptable shortcut. This is not a false alarm and does not invalidate the checked completed run.

### A06 — MEDIUM · CONFIRMED BUG · manifest configuration could disagree with frozen plan

**Location:** `src/vote_aware_paired_eval.py:213`.

**Original reproduction:** copy the real manifest, change only `configuration.model`, and call `validate_manifest`; it passed. **Fix:** require exact configuration equality with the frozen plan. `test_manifest_configuration_must_match_frozen_plan` verifies both unchanged acceptance and altered-model rejection using a synthetic complete manifest. **Impact:** misleading provenance previously passed validation. **Historical impact:** real plan/manifest configuration matched before the fix. **Status:** fixed for this discrepancy, not complete runtime attestation.

### A07 — MEDIUM · CONFIRMED BUG · incomplete paired effect used the full denominator

**Location:** `src/vote_aware_paired_eval.py:372`, paired result at `:402`.

**Original reproduction:** one accounted discordant pair produced a reported difference -.0185 (= -1/54), although the observed pair difference was -1.0; missing pairs were implicitly ties in that displayed effect. A p-value was also printed for partial data. Complete-with-errors output incorrectly said that all outcomes still needed accounting.

**Fix:** expose paired `n`; report the planned comparison and p-value only when all 54 pairs/108 primary outcomes are accounted for, otherwise null; gate the incomplete-analysis warning on completeness rather than error-free status. `test_partial_summary_does_not_report_a_full_plan_paired_estimate` verifies the partial case. **Historical impact:** recomputation in a temporary directory matched every original completed paired field and every arm metric; only the new `n=54` field is added. No original summary was rewritten. **Status:** fixed.

### A08 — MEDIUM · CONFIRMED VALIDATION GAP · offline paired validation overstates provenance

**Location:** `src/vote_aware_paired_eval.py:136`, `:213`, `:426`, `:496`.

**Observed:** stored source hashes are not compared with current code before live execution. Plan validation checks hash, count and balance, but does not reconstruct every case from dataset rows. Manifest validation checks identities and passage count but does not reconstruct prompt/evidence hashes. Runtime hash checking occurs after classification. `validate` prints that PDFs/routes passed without loading current PDFs. The configuration-equality repair does not close these gaps.

**Expected:** reconstruct source/PDF/request/prompt identity before an authorised model call, and bind event fields to the manifest as well as each other. **Impact:** drift may be discovered only after spending a call, and parser/source changes may escape prompt checks. **Historical impact:** independent reconstruction found all 108 prompts/evidence sets and 36 PDF hashes consistent; initial five stored source hashes matched the starting source. **Status:** deferred comprehensive preflight enforcement. The audit itself changes the runner hash; historical reproduction must use the recorded revision, not claim byte-identical whole-run source at audit HEAD.

### A09 — MEDIUM · CONFIRMED BUG · diagnostic false success on absent/disjoint records

**Location:** `src/diag_evidence_ablation.py:100`, `:152`.

**Original reproduction:** `part_b_recorded({})` returned true; comparing row 1 only with row 2 only returned one item and zero differences. Duplicate IDs were collapsed by dictionaries. Equal token counts were described as identical prompts.

**Fix:** reject empty, duplicate or unequal ID sets; missing required t0/select retrieval runs return false; remove the unsupported prompt-identity/decoding-cause assertion. Three tests in `test_diagnostic_integrity.py` cover rejection and valid comparison. **Historical impact:** no saved results or inputs changed. **Remaining limit:** this remains a token-count/label diagnostic; matching tokens and labels do not establish byte-identical prompts, and optional unrecorded cells cannot be certified. **Status:** fixed within that scope.

### A10 — MEDIUM · CONFIRMED BUG · corrupt PDF cache treated as valid

**Location:** `src/fetch_booklets.py:86`, `:240`.

**Original reproduction:** a 2 KB HTML file at the cache destination returned `cached` without network access. **Fix:** check `%PDF` on cache reuse and before extraction, including `--skip-fetch`; retain the suspect file for inspection and refuse incomplete corpus publication. **Tests:** corrupt cache unchanged and rejected; valid cache retained. **Historical impact:** no PDF downloads, deletions or cache rewrites. **Status:** fixed for magic-byte validation; it is not a full PDF validator.

### A11 — MEDIUM · DOCUMENTATION DISCREPANCY / SCHEMA GAP · not every instructed field is enforced

**Location:** `src/booklet_app.py:32`, `:513`.

**Reproduction:** a Beginner candidate result with label neutral, insufficient status and empty references passes `candidate_result` without `reasoning`, `vote_status` or `vote_reference`. Advanced validates identity but does not require reasoning. The prompt says every field is required, including null vote fields without a vote.

**Expected:** choose and document a single schema policy. **Impact:** claims of full six-field validation are too strong. **Historical impact:** all 25 accepted candidate saved responses contained the six fields, so no accepted-output count change was demonstrated. **Status:** deferred; strictness changes affect the evaluated contract and must not silently retain the same treatment identity. Likewise, relaxing neutral identity validation is not an audit fix.

### A12 — MEDIUM · REPORTING LIMITATION · saved diagnostic metric names need qualifications

**Location:** `src/vote_aware_paired_eval.py:298`, `:330`; `src/evidence_sensitivity_v2.py:383`; working-tree `technical_report.md:402`.

The dense paired summary has 11 invalid official outputs but `failure_types={'none':54}`: `record_outcome` catches output-rendering errors without recording their reason in the result inspected by `arm_metrics`. Raw `native_json_rate` also requires a recognised label, not merely syntactically valid JSON. Retrieval latency in the paired run measures return of prepared passages through `FrozenRetriever`, not encoder/extraction/preparation time. The sensitivity summary's flat token totals are zero while nested usage totals contain actual measurements; the academic revision already discloses that discrepancy.

**Verification:** direct saved summary/record comparison; the headline accuracy/F1 matches reconstructed outcomes. **Impact:** misleading error, syntax or cost interpretation, not demonstrated corruption of reported classification scores. **Status:** documented; no frozen summary regeneration. Future reporting should retain rendering failure reasons, explicit metric denominators and measured/missing telemetry. Historical derived corrections must be separately identified.

### A13 — MEDIUM · SECURITY/RESOURCE DESIGN LIMITATION · trusted CLI is not a hardened PDF service

**Location:** `src/booklet_app.py:132`, `:300`; `compose.submission.yaml`; `Dockerfile`.

HTTPS sources are unrestricted, redirects are followed, response bodies are buffered before magic checks, and no PDF byte/page/extracted-text cap is enforced. Local PDF paths are intentionally accepted. These are observable behaviours; internal-network targeting and excessive-memory use are potential consequences if untrusted users can submit requests. No destructive URL/PDF test was performed, and no remotely exposed request service is configured by this repository.

**Resolution:** document the trusted-operator boundary; before service exposure, choose source/redirect policy and byte/page/time limits. The app runs non-root, has no published port or privileged flag, and needs only the data/cache mounts. Advanced PDFs are not shell-interpolated. HTTP and extraction timeouts exist; those are not memory limits. No policy change was imposed on legitimate local/HTTPS inputs during this audit.

### A14 — MEDIUM · REPRODUCIBILITY/DESIGN LIMITATION · caches, adapters and dependencies

**Locations:** `src/retriever.py:24`, `:94`, `:102`; `src/hybrid_retrieval.py:271`; `src/fetch_booklets.py:105`; dependency files.

Production encoder loads do not pin an immutable revision; native runners do. Adapter-setting exceptions are swallowed. Historical global cache identity omits encoder revision/software/tokenizer identity and accepts an absent manifest; shape/finiteness checks do not prove semantic identity. Historical extracted-text reuse is size-based rather than tied to PDF bytes. The PyMuPDF fallback joins pages with newlines, so downstream physical-page recovery is weaker than the Poppler path. These are outside the independently re-extracted paired submission evidence.

The existing native environment passes `pip check`, but portable Transformers 4.48.3 and the MLX environment's newer requirement are not a single reproducible installation recipe; portable macOS markers also do not install torch. No package pin or encoder behaviour was changed. Resolving these issues may change retrieval identity and requires a versioned provenance policy plus fresh environment checks. No current cache corruption, wrong adapter execution or historical fallback-dependent score change was demonstrated.

### A15 — HIGH deployment requirement / DOCUMENTATION DISCREPANCY · 8B remains unverified

**Locations:** `compose.submission.yaml`, `compose.managed.yaml`, `docs/PROJECT_STATUS.md:24`, `docs/RUNNING.md:39`.

Static default model agreement is verified for official v1.5 8B, and managed readiness/GPU configuration exists. Real external records use CSCS 70B; native 8B is a third-party 6-bit MLX conversion. No record inspected establishes the current candidate with the intended official 8B deployment. The managed image tag and base image are mutable. GPU capacity, cold startup, access and cross-platform behaviour remain unmeasured.

**Resolution:** an authorised small official-8B Beginner/Advanced deployment acceptance check on the intended host, with model/usage/source/failure/lifecycle records. No automatic inference is authorised by this audit. This is an outstanding acceptance requirement, not evidence that static Compose is broken.

## Security and deployment assessment

Bounded tracked-text scans found no private-key headers or common HF/OpenAI/GitHub credential-token matches and no tracked file above 10 MB. The 126-file inventory contained 3,641 bytes of Git-eligible data. `.env`, credentials and model weights are excluded by ignore rules; Docker uses an allowlisted build context. Actual `.env` contents and API keys were not read or printed. This is not a guarantee that arbitrary secrets cannot exist, and no package-CVE audit was claimed.

External and managed Compose were rendered with `/dev/null` as env file and dummy credentials in an isolated environment. Both passed; external contains only the app, managed contains app plus `apertus`; default model agrees, preflight is optional versus required respectively, and the app publishes no port. The managed service has no host port, requests NVIDIA hardware and gates the app on health. The base app requires an operator-provisioned endpoint; neither a judge credential nor a GPU should be assumed. Managed model service runs with its image's default privileges; the CPU application explicitly runs as non-root.

Public CLI errors are generic and result telemetry omits credentials. Diagnostics do contain supplied document/claim text and raw model output, so sharing them requires content review. Native development serving is loopback-only in `serve_experiments.py`. No model server was started or stopped by this audit; the initial port check found no listener on 8000 or 8080. That point-in-time observation is not a claim about all processes or later sessions.

## Documentation consistency

The working academic revision accurately distinguishes the main cohorts, raw/strict/conditional scores, exposed development data, 70B versus 8B, selected evidence diagnostics and unchanged historical predictions. Its principal numeric tables reproduce the raw records. It is not yet committed by this audit.

Specific remaining corrections should be integrated separately with that revision:

1. `docs/PROJECT_STATUS.md:22`, `:88` and `:119` call `current_v1` the production prompt. It remains the dense/prompt-pilot base, but the submission candidate transforms it and appends vote/schema instructions. Use interface-specific wording.
2. `docs/RUNNING.md:178` says the native wrapper's first real run is pending, despite the recorded completed grouped runs. Dated historical statements should stay dated; current instructions need an updated qualification.
3. `PROJECT_STATUS.md:122` records 110 native/Docker tests. That older run is not the current suite, which now includes local-asset dependencies. Its remaining-work wording also calls an earlier CSCS smoke the only real external inference despite subsequent records.
4. The academic definition of native JSON should include the recognised-label condition implemented by the summary. Prepared retrieval time must not be presented as full retrieval latency.
5. Root `AGENTS.md` deliberately mixes historical and current claims, including withdrawn retrieval rankings and earlier deployment status. Current code, dated evidence and `PROJECT_STATUS.md` take precedence; archived observations were not rewritten.

No broken relative Markdown links were found in the original non-archived tracked documentation. External scholarly references, current contest rules, licensing and submission portal requirements were not independently revalidated in this audit. No final report PDF, team/demo metadata or completed licence review was produced.

## Fixes, tests and preservation evidence

| Changed file | Exact purpose | Verification |
|---|---|---|
| `src/fetch_booklets.py` | Reject corrupt PDF cache; prevent incomplete/limited canonical publication; separate output; atomic replacement | Five deterministic ingestion tests; no real corpus build. |
| `src/vote_aware_paired_eval.py` | Bind configuration and event identity; suppress incomplete paired estimates; expose paired n | Nine module tests; existing 108 outcomes validate; complete summary fields unchanged. |
| `src/diag_evidence_ablation.py` | Reject absent/empty/duplicate/disjoint comparisons; remove unsupported identity wording | Three integrity tests; no historical experiment rewrite. |
| `tests/test_ingestion_safety.py` | New five-case permanent ingestion regressions | Failed against original defects, pass after fixes. |
| `tests/test_vote_aware_paired_eval.py` | Three additional tests with identity-mutation subtests | Original six retained; nine pass. |
| `tests/test_diagnostic_integrity.py` | New three-case permanent diagnostic regressions | Original missing/disjoint cases failed expected assertions; corrected version passes. |
| `docs/REPOSITORY_AUDIT_20261013.md` | Findings, scope, evidence and continuation handoff | Source/diff/result review; publication excludes unrelated files. |

Executed environment: macOS 27.2 arm64, Python 3.12.4; requests 2.34.2, NumPy 2.5.3, torch 2.14.1, Transformers 5.19.0, huggingface-hub 2.2.0, MLX .32.3, mlx-lm .32.0, tokenizers .23.3. The cached tokenizer emitted its previously documented regex warning. It was not interpreted as proof of a classification defect or changed.

- Initial root `make test`: **163 unittest tests, zero failures/errors/skips**, 20.139 s unittest time, 22.31 s wall time; all 53 judge/label checks and source compilation passed.
- Final root `make test`, once after source fixes: **174 tests, zero failures/errors/skips**, 19.705 s unittest time, 21.64 s wall time; judge/label and compilation passed. The temporary log subsequently disappeared; these results are retained tool output from the uninterrupted phase.
- Continuation: **17 focused tests passed in .030 s**, covering all three affected modules. The final focused run includes the subsequent permission-preservation assertion and correction. The 174-test full pass preceded that small filesystem-metadata adjustment; the full suite was not rerun during continuation.
- `pip check`: no broken installed requirements. AST, tracked JSON and `git diff --check` checks passed. Static Compose checks passed; no container execution occurred.
- The pre-interruption snapshot covered **154 files** across evidence/archive/experiment/fixture trees plus the pre-existing report. All 154 hashes matched after source fixes. Aggregate snapshot SHA-256: `607ff67daa698321bd67dd5c012774daad385f29bc8e7893f09f4fe1d8411279`. The snapshot map itself was temporary and is no longer available; this aggregate alone is not a reconstructable manifest.
- Continuation refreshed the five published hashes for paired plan, manifest, predictions, summary and analysis against `docs/evidence/vote_aware_paired_results_20261013.json`: **all match**. Tracked evidence/archive/fixture diffs are empty. Completed arm metrics and all original paired fields still match after temporary-copy summarisation. No original `summarise` command was invoked against a frozen run directory.

## Scientific-integrity assessment

No evidence found in these reconstructions invalidates the reported completed classification counts. No gold label/reference entered the submission's retrieval query or NLI prompt; experimental Oracle and manually curated evidence are explicitly separate diagnostics. Balanced sampling uses gold labels by design. Within-PDF language metadata is a legitimate input for this task and must not be confused with the historical global-search oracle-adapter setting.

The evidence supports compatibility of frozen dense inputs and recorded results, not an independent generalisation claim. Historical corpus exposure and overlapping content remain; manually selected evidence and post-hoc cases cannot estimate deployable retrieval improvement. Vote-aware versus dense changes query, prompt, schema, validation and citation policy together. A causal attribution to vote awareness alone would therefore be unsupported. The audit did not relax identity/citation validation, change thresholds, optimise prompts or implement a new treatment version.

Remaining reporting/provenance weaknesses were recorded without rewriting their historical artefacts. Unknown-outcome resume handling, strict schema changes and encoder/protocol changes require an explicit next-stage decision. Publication of the local safety fixes is safe independently of those unresolved research decisions.

## Recommended next-stage options

| Priority/option | Objective and expected benefit | Effort, scientific value, risks and required evidence | New inference? |
|---|---|---|---|
| 1. Offline identity/neutral adjudication | Determine whether each of the 29 candidate rejections had sufficient proposal identity and claim evidence | Small/medium; highest immediate information value. Blind review of Top-5, proposal/speaker and reference validity; distinguish absent identity from absent claim support. Avoid gold-driven acceptance relaxation. Freeze annotations and proposed contract before implementation. | No |
| 2. Runner/test reproducibility repair | Make offline tests runnable from tracked fixtures; enforce full preflight and an explicit unknown-outcome resume policy | Medium; prevents false confidence and duplicate calls. Use clean-tree checks and crash injection with mocks; retain historical logs and allow genuinely missing latency. No skips to manufacture a pass. | No |
| 3. Official 8B deployment acceptance | Establish the actual submission environment and output contract | Small code effort, potentially substantial infrastructure/download cost. Authorised host, model access and fixed request/control set; preserve exact model, usage, citations, exit status and lifecycle. A smoke remains insufficient for quality. | Yes, separately authorised |
| 4. New independent evaluation cohort | Estimate generalisation after the task/contract/default is agreed | Large annotation/design effort. New vote/topic-disjoint cases with adjudicated neutral labels; frozen method and adequate paired sampling. Existing exposed rows cannot become held out again. | Yes, later |

The first recommendation is offline adjudication of the 29 rejections, alongside independent runner/test work. Decide whether to retain the submission candidate or introduce a separately versioned identity policy only after that evidence. Do not automatically promote dense or accept the 18 raw-correct rejected labels. A deployment decision also needs genuine official-8B evidence.

## Publication and ChatGPT continuation brief

The delivery consists of two commits: `c314670e38dd7e620b81015322c9c6a6e555205f` (`fix(track2a): resolve audited correctness defects`), then this report in a separate documentation commit. Exact final local/remote SHAs and push verification are provided in the accompanying task handoff; this document cannot contain its own final commit hash. The initial revision above is the comparison base. Only the seven audit files listed above are authorised for these commits. `technical_report.md` and `.opencode/` remain outside them.

**Current state:** specified-booklet multilingual NLI with dense SentenceSwissBERT and Apertus v1.5 endpoints; CLI candidate `vote-aware-v1`, flat Python default `dense-v1`. **Changes:** ingestion and audit/runner safeguards only. **Evidence:** 163 baseline/174 final tests; 17 continuation focused tests; 108 saved calls, 36 PDFs, 108 prompts and 89 citation records checked. **Prediction changes:** none from the audit; historical candidate strict gains/losses are nine/18. **Uncertainties:** clean-test portability, full preflight identity, hard-interruption accounting, semantic citation sufficiency and official 8B deployment. **Next experiment:** first perform a no-inference adjudication of the 29 rejections to separate identity absence from claim-evidence absence. **Execution:** no new inference/download/server/deployment; no next-stage work automatically started.

Copyable continuation: Work on `experiment-multilingual-retrieval-ablation` from the final audit commits identified in the handoff. Preserve the uncommitted academic report and `.opencode/`. The 54-case CSCS 70B comparison remains dense raw/strict .7407/.5926 versus candidate .7593/.4259; candidate coverage is 25/54 and every gold-neutral case was rejected. Safety fixes have 174-test native evidence, but clean-checkout tests still require fixture work. Evidence-sensitivity hard-interruption resume can duplicate an unknown call; freeze a recovery policy before changing it. No prediction, prompt, retrieval treatment or frozen record was modified. The next human decision is the identity/neutral contract and submission default, informed by offline adjudication and later authorised official-8B acceptance evidence.
