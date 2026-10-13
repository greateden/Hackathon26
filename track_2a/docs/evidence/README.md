# Evidence index

Raw inference records remain in ignored experiment directories; compact tracked
summaries link to them without duplicating the data.

- [Vote-aware paired result audit](vote_aware_paired_results_20261013.json):
  54 paired development cases and 108 accounted CSCS 70B calls comparing frozen
  `dense-v1` with the complete `vote-aware-v1` candidate. It records metric
  definitions, failure counts, source hashes and three representative cases.
  Raw plan, manifest, events, predictions and summaries remain ignored under
  `data/experiments/vote-aware-paired-v2/`.
- [Vote-aware CSCS Advanced smoke](vote_aware_cscs_smoke_20261013.json): one
  successful Docker inference with recognised vote, page-19 source provenance
  and bounded syntax recovery. The citation begins mid-word, so this is
  functional evidence with a recorded boundary limitation, not a quality result.

- [Evidence sensitivity v2 results](evidence_sensitivity_results_v2_20261012.json):
  60 completed calls on 15 post-hoc selected cases; all predictions, response
  text, token usage, independently recomputed metrics and raw-file hashes.
  The [frozen plan](evidence_sensitivity_plan_v2_20261012.json) contains exact
  passages, offsets and PDF provenance;
  [annotations](evidence_sensitivity_annotations_v2_20261012.json) record the
  independent AI-assisted approval and two exclusions. Original records remain
  under `data/experiments/evidence-sensitivity-v2/` (ignored). The summary's flat
  token-total fields are incorrectly zero; nested totals agree with raw usage.
  Preparation-era validation records describe their original review state.
  The final analysis does not alter production retrieval or historical records.

- [Prompt-only pilot results](prompt_pilot27_results_v1.json): completed paired
  CSCS Apertus v1.5 70B comparison, 27 rows and 54 calls. Accuracy was tied;
  `current_v1` remains the production default. The frozen selection is in the
  [pilot plan](prompt_pilot27_plan_v1.json).

- [Local v1.5 smoke](v15_local_smoke/verification.json): saved successful
  development run, n=1, 11 October 2026. See [result](v15_local_smoke/result.json)
  and [request](v15_local_smoke/request.json).
- [Loaded model](v15_local_smoke/loaded_model.json): Apertus MLX 6-bit revision
  `9a3c32df1b84c6abc8ea597c7f57a482e40e3d0e`; loader/config and shard sizes.
- [Server prompt](v15_local_smoke/server_prompt.json) and
  [observational wrapper](v15_local_smoke/server_probe.py): recorded token IDs
  and loader observation. The wrapper is evidence, not the production server.
- [First attempt](v15_local_smoke/attempt1_result.json): retained failure,
  `finish_reason=length`, 512 output tokens. The successful attempt disabled
  thinking at server startup; this is not a paired A/B comparison.
- [Retrieval smoke](booklet_retrieval_smoke_20261011.json): n=9 across language
  pairs, no NLI inference; shingle coverage is not semantic evidence accuracy.
- [Paired plan](paired_dev_plan_20261011.json): sample IDs, dataset hash and
  contamination audit; planned execution is not a result.
- [Earlier verification](verification_20261011.txt): pre-cleanup offline checks.

The v1.5 JSON copies replace original local path prefixes with
`<original-checkout>/` and `<home>/`; values and token IDs are otherwise retained.
[SHA-256 manifest](v15_local_smoke/source_sha256.json) hashes the **original**
bytes, preserved under `../../data/logs/v15_first_real_20261011_1839/` (ignored).
Old recorded paths describe the run location at the time. For a rerun, use the
cached PDF stem or its new `track_2a/data/` path; do not edit the raw evidence.
The model-list response alone cannot prove which weights were loaded.
