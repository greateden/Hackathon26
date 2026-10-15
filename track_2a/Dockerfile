# syntax=docker/dockerfile:1
# HackApertus Track 2A - portable (Linux) runtime image.
#
# Deliberate design choices (see docs/RUNNING.md):
#   - MLX is not installed. Submission Compose runs booklet_app.py against
#     the managed or external official v1.5 endpoint. The image's default
#     entrypoint is the authoritative mixed-task evaluation CLI.
#   - Encoder weights are pinned and included at build time. Runtime model
#     downloads are disabled; Apertus inference uses the injected endpoint.
#   - Corpus/data are bind-mounted at run time (compose.yaml), never
#     COPYied into the image.

FROM python:3.11-slim AS runtime-base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/app/.cache/huggingface \
    LLM_BACKEND=lexical \
    RETRIEVAL_CONFIG=legacy

# poppler-utils provides pdftotext, used by fetch_booklets.py.
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
# The PyTorch cpu extra index keeps x86-64 images small; aarch64 falls
# back to the CPU wheels on PyPI (see the platform markers in
# requirements.txt).
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r requirements.txt

# Freeze the encoder at build time; runtime inference never contacts Hugging Face.
ARG ENCODER_REVISION=7a91fa8a01af56c1f06060f7af3698ef5619e41c
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('jgrosjean-mathesis/sentence-swissbert', revision='${ENCODER_REVISION}', local_dir='/opt/models/sentence-swissbert', allow_patterns=['*.json','*.model','*.safetensors','README.md'])"
ENV EMBEDDING_MODEL=/opt/models/sentence-swissbert \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HOME=/tmp/huggingface \
    XDG_CACHE_HOME=/tmp/cache \
    LLM_NAME=swiss-ai/Apertus-v1.5-70B \
    LLM_TOKEN_PREFLIGHT=optional \
    SUBMISSION_MODEL_REQUIRED=1
# Verify both model and tokenizer can load without network before shipping.
RUN python -c "from transformers import AutoTokenizer, AutoModel; p='/opt/models/sentence-swissbert'; AutoTokenizer.from_pretrained(p, local_files_only=True); AutoModel.from_pretrained(p, local_files_only=True)"

RUN useradd -m -d /home/app app && \
    mkdir -p /home/app/.cache/huggingface && \
    chown -R app:app /app /home/app

# Offline regression image. Gold-labelled fixtures and test-only evidence live
# here, never in the default production stage.
FROM runtime-base AS test
COPY --chown=app:app src ./src
COPY --chown=app:app tests ./tests
COPY --chown=app:app docs/evidence/paired_grouped81_plan_20261011.json \
     docs/evidence/prompt_pilot27_plan_v1.json \
     ./docs/evidence/
USER app
WORKDIR /app
ENTRYPOINT []
CMD ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

# Default release image: runtime source only. Keep this stage last so an
# unqualified `docker build` cannot accidentally publish the test image.
FROM runtime-base AS production
COPY --chown=app:app src ./src
COPY docs/SENTENCE_SWISSBERT_NOTICE.md /usr/share/doc/sentence-swissbert/NOTICE.md
USER app
WORKDIR /app/src
ENTRYPOINT ["python3", "/app/src/submission_cli.py"]
CMD []
