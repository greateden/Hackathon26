# syntax=docker/dockerfile:1
# HackApertus Track 2A - portable (Linux) runtime image.
#
# Deliberate design choices (see AGENTS.md "Docker runtime"):
#   - MLX is NOT installed: Apple-Metal MLX cannot run in a Linux
#     container. Inside Docker the NLI judge is either the lexical
#     smoke-test baseline (LLM_BACKEND=lexical, default, no model) or a
#     genuine model reached through an external HTTP inference endpoint
#     (LLM_BACKEND=ollama + OLLAMA_BASE_URL, e.g. host Ollama).
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
