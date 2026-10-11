# syntax=docker/dockerfile:1
# HackApertus Track 2A - portable (Linux) runtime image.
#
# Deliberate design choices (see docs/RUNNING.md):
#   - MLX is not installed. Submission Compose runs booklet_app.py against
#     the managed or external official v1.5 endpoint. The image's default
#     command remains the historical lexical smoke path.
#   - No model weights are downloaded at build time. The embedding model
#     (sentence-swissbert) is fetched at first dense-retrieval run into a
#     persistent cache volume, or mounted beforehand.
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

COPY src ./src
COPY tests ./tests

RUN useradd -m -d /home/app app && \
    mkdir -p /home/app/.cache/huggingface && \
    chown -R app:app /app /home/app
USER app
WORKDIR /app/src
CMD ["python3", "main.py"]
