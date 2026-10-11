# Evidence index

No model experiment was run during submission cleanup.

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
