# syntax=docker/dockerfile:1
# HackApertus Track 2A - portable (Linux) runtime image.
#
# Deliberate design choices (see docs/RUNNING.md):
#   - MLX is not installed. Submission Compose runs booklet_app.py against
#     the managed or external official v1.5 endpoint. The image's default
#     command remains the historical lexical smoke path.
#   - Encoder weights are pinned and included at build time. Runtime model
#     downloads are disabled; Apertus inference uses the injected endpoint.
#   - Corpus/data are bind-mounted at run time (compose.yaml), never
#     COPYied into the image.

FROM python:3.11-slim

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
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('jgrosjean-mathesis/sentence-swissbert', revision='${ENCODER_REVISION}', local_dir='/opt/models/sentence-swissbert', allow_patterns=['*.json','*.model','*.safetensors'])"
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

COPY src ./src
COPY tests ./tests
COPY docs/evidence/paired_grouped81_plan_20261011.json \
     docs/evidence/prompt_pilot27_plan_v1.json \
     ./docs/evidence/

RUN useradd -m -d /home/app app && \
    mkdir -p /home/app/.cache/huggingface && \
    chown -R app:app /app /home/app
USER app
WORKDIR /app/src
ENTRYPOINT ["python3", "/app/src/submission_cli.py"]
CMD []
