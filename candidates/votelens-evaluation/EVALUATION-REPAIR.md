# VoteLens evaluation-interface repair

This corrected copy is based on Hackathon26-feature-votelens-research-positioning. The original Downloads folder was not modified. The vote-aware-v1 judgement and retrieval prompts are preserved.

## Implemented
- New submission_cli.py reads mixed A/B JSONL and writes compact JSONL using --input and --output (--out is an alias).
- BASE_URL and API_KEY take precedence over the development LLM_* aliases, including in the underlying HTTP client. The batch default is Apertus v1.5 70B; preflight is optional for the evaluation proxy.
- PDF paths resolve relative to /data (or the input directory during native testing). Evaluation batches reject URL sources; provide local PDFs. Only the output file is written by the batch wrapper. The retriever is reused across Task A cases.
- Docker ENTRYPOINT invokes the batch CLI. Compose explicitly clears it to preserve the existing make run single-request demo and research commands.
- Docker downloads SentenceSwissBERT at build time, pinned to revision 7a91fa8a01af56c1f06060f7af3698ef5619e41c; verifies tokenizer/model loading locally; sets offline model flags. Encoder path is immutable /opt/models/sentence-swissbert; HF/XDG caches point to /tmp. The build downloads approximately 638 MB of weights, increasing image size. Weights are not in this source archive.
- Failures do not fabricate neutral predictions: later cases are processed, valid earlier/later predictions are flushed, and failed cases cause a nonzero exit. Such cases still count as wrong officially. Malformed inputs and duplicate IDs are rejected before inference.

## Verified locally
212 unittest tests ran: 194 passed, 18 skipped, no failures/errors. Five new tests cover mixed batch/path resolution/retriever reuse, malformed inputs, preserving later cases after failure, environment precedence, and real classifier parsing with mocked HTTP transport. This is not live endpoint or Docker inference evidence. No API credit or GPU allocation was used.

## Required next verification
Docker socket access was denied to this assistant session, so the changed image has NOT been built, the pinned-weight download/build-time load has NOT been observed, and linux/amd64 runtime has NOT been verified. No container was published. Historical notebook successes apply to the earlier image, not this repair.

From this copy, use your Mac Terminal with Docker Desktop running and a key already exported as API_KEY or LLM_API_KEY:

```bash
cd track_2a
bash scripts/verify-evaluation.sh
```

The script downloads the demo PDF BEFORE container execution, builds the image for linux/amd64, and runs one A and one B case with /data mounted read-only and a fresh output directory. It makes two real completion calls. It validates IDs, response structure and metrics; predicted accuracy must be assessed separately. The output directory is newly created and made writable for the non-root container user. No key is printed or embedded in the image.

Equivalent judge invocation after building:

```bash
docker build --platform linux/amd64 -t votelens:verify .
mkdir -p output
docker run --rm --platform linux/amd64 \
  -e BASE_URL -e API_KEY \
  -v "$PWD/data:/data:ro" \
  -v "$PWD/output:/output" \
  votelens:verify --input /data/cases.jsonl --output /output/predictions.jsonl
```

Use UTF-8 JSONL with required id, vote, claim, and exactly one source per line. PDFs are relative to /data. Ensure /output is writable by image user app. Every remote model request uses the injected endpoint.

## Scope and remaining limitations
The classifier still uses its existing stricter evidence requirements for Task B, even though official Task B evidence is optional. Changing NLI semantics or failure recovery was outside this interface repair. No new quality benchmark was run. Exact platform validation, a full-language batch, runtime permissions and a pullable published image remain necessary before claiming evaluation readiness.
