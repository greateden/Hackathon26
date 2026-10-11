# Project status — 11 October 2026

**TL;DR:** The specified-booklet application and paired evaluation code are
implemented. Real PDF/SwissBERT retrieval works across all nine language pairs.
**The project is not submission-ready:** v1.5 inference, a clean Docker run,
Windows execution and final packaging remain unverified. No model server was
started; no large weights were downloaded. Deadline from the task brief:
16 October 2026, 12:00 CEST.

## Requirements and current configuration

| Requirement | Status | Evidence / remaining condition |
|---|---|---|
| Specified booklet + claim; numeric NLI + sources | PASS (implementation) | `booklet_app.py`; contract tests cover labels and physical page citations; no real v1.5 verdict yet |
| Nine DE/FR/IT combinations | PASS (interface/retrieval) | Actual extraction and cached encoder smoke, one dev item per pair; NLI quality UNVERIFIED |
| Apertus v1.5 8B inference | UNVERIFIED | Exact model preflight implemented; endpoint/credentials absent, weights not cached |
| `make run` using Docker, clean checkout | UNVERIFIED | Build-and-run recipe and Compose validation pass statically; local Docker daemon stopped |
| Official LLM environment variables | PASS (implementation) | `.env.example`, Compose and authenticated endpoint tests |
| No preparatory Make targets | PASS for provisioned-endpoint path | Application performs extraction/retrieval/inference; local model server lifecycle is outstanding |
| Full-document / retrieved paired baselines | PASS (implementation), results UNVERIFIED | Shared prompts/parser/seed; explicit context failures; saved nine-item plan |
| Windows CMD | UNVERIFIED | New run recipe avoids POSIX assignments and Make shell discovery; no Windows execution |
| Template structure, report PDF, submission | FAIL / incomplete | Report draft exists; `track_2a/` packaging, ≤6-page PDF, demo and team metadata outstanding |
| Data ≤100 MB | PASS for tracked inventory | 51,052,919 bytes before this iteration plus a small request JSON; ignored corpora excluded |

Sources: [template](https://github.com/HackApertus/project-template),
[OST page](https://hackapertus.notion.site/track-2a-ost),
[portal](https://hackapertus.ch/online-hack/submissions). Template verified;
OST and portal returned access errors on both retrieval attempts. The explicit
v1.5 requirement and PDF limit follow the user brief; the accessible README
only specifies the Apertus family. Earlier local claims of v1.1 compliance
must not be reused as current acceptance evidence.

**Run configuration:** `make run` → `compose.submission.yaml` →
`src/booklet_app.py`; model `swiss-ai/Apertus-v1.5-8B`, provided vLLM-compatible
endpoint, T=0, seed 20261011, 512 output tokens. Set `LLM_BASE_URL` and any
required `LLM_API_KEY`; edit `data/request.json`. See [RUNNING.md](RUNNING.md).
This is a configured target, not a verified v1.5 deployment.

## What the configurations mean

| Dimension / configuration | Role |
|---|---|
| Baseline A: `full` | All extracted text from the supplied PDF; no silent truncation |
| Approach B: `retrieved` | Top-five SwissBERT passages from that same PDF; known booklet-language adapter |
| Historical `legacy` | Global legacy OCR corpus; remains `main.py` default only |
| Historical `retrieve-v2` | Global booklet-corpus pipeline, a different search task |
| `lexical` | Heuristic judge or BM25 retrieval, depending on script; never Apertus inference |
| `oracle` | Gold reference diagnostic; never the full-document baseline |
| `baseline` / `t0` | Historical prompt registry; T=0.1 / T=0 respectively |
| `strict` | Historical changed instructions; unsuccessful neutral collapse |
| `select` / factorial arms | Historical selection/formatting variants; experimental, not new application defaults |

## Measurements and completed work

- **New retrieval-only smoke:** cached `jgrosjean-mathesis/sentence-swissbert`,
  no NLI model; deterministic historical-dev sample n=9, all language pairs,
  three labels equally represented. Mean gold-reference shingle coverage:
  full PDF 0.921, within-PDF top-five 0.204. Mean extraction/retrieval time
  1.722 s, including first encoder load; Apple MPS. This is lexical coverage,
  not accuracy. Encoder revision was unavailable from the loader.
  Provenance: [retrieval artefact](evidence/booklet_retrieval_smoke_20261011.json).
- **Historical model evidence only:** Apertus v1.1 4B MLX INT4, dev n=60:
  global retrieve-v2 accuracy/F1 0.483/0.466; oracle 0.433/0.393.
  Provenance: `data/eval_results_20261010_082336_dev_openai_retrieve-v2.json`
  and `data/eval_results_20261010_082936_dev_openai_oracle.json` (local,
  git-ignored). These are neither v1.5 nor full-document comparisons.
- **Fresh split audit, no model:** 24/60 dev rows duplicate normalised
  claim/reference/label triples in the 1,428-row complement; 25 share claims,
  46 share references. Selected dev sample n=9 contains three such duplicates.
  Dataset hash and row IDs: [paired plan](evidence/paired_dev_plan_20261011.json).
  Do not describe the complement as independently held out.
- Preserved historical raw results; migrated the dated audit in full to
  [research integrity history](research_integrity_history.md). Prior global
  retrieval rankings and prompt ablations cannot establish improvements on
  this new supplied-booklet task. No new NLI prediction flips are measured.

## Remaining priorities

**P0:** provision and verify a real v1.5 8B endpoint; complete one clean Docker
smoke with actual labels and citations. If self-hosted startup is required,
add and test GPU server orchestration. Host has 128 GiB RAM and roughly 273 GiB
free disk, but Apple Silicon Docker supplies no CUDA device.

**P1:** execute the saved nine-item paired run (18 calls); inspect per-item
errors, evidence, token counts and latency before expanding. Define a content-
grouped independent split. Validate Windows on Windows. Complete template
packaging and final PDF; independently confirm current OST requirements.

**P2:** OCR/layout support, immutable encoder/model/image revisions, and
remaining historical diagnostic/cache/dependency issues in the evidence ledger.
Do not spend this iteration rerunning unrelated historical experiments.

**Verification:** seven focused contract tests passed; `make test` ran once and passed
all judge/label checks, Python compilation and 69 discovered tests. Output:
`evidence/verification_20261011.txt`. Compose config
and Make dry-run passed. Actual `make run` failed clearly for missing endpoint
configuration, then for the stopped Docker daemon when an endpoint placeholder
was supplied. Real v1.5 token usage and inference latency remain unmeasured.
