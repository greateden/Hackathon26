"""Configuration for the NLI pipeline."""
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
REPOS_DIR = PROJECT_ROOT / "repos"
DATA_DIR = PROJECT_ROOT / "data"

# OCR text source - use the pre-existing cleaned text
OCR_TEXT_DIR = REPOS_DIR / "VotingBooklets-mono" / "cleaned_ocr_txt" / "gemini-ocr"

# Language directories in OCR text
LANG_DIRS = {
    "de": "Deutsch",
    "fr": "Franz\u00f6sisch",
    "it": "Italienisch",
    "rm": "R\u00e4toromanisch",
}

# Available voting dates (years)
YEARS = ["1977", "1985", "2007"]

# Embedding model for retrieval
EMBEDDING_MODEL = "jgrosjean-mathesis/sentence-swissbert"
BATCH_SIZE = 32

# LLM for NLI judgment.
# Backend options: "lexical" (no LLM, smoke-test only), "mlx" (Apple Silicon
# local via mlx_lm), "ollama" (requires Ollama installed and running).
# Override with:  LLM_BACKEND=mlx python main.py
LLM_BACKEND = os.environ.get("LLM_BACKEND", "lexical")

# MLX backend: default model. Override with:
#   MLX_MODEL=<hf-id> python main.py           (or:  ./run.sh <hf-id>)
#
# IMPORTANT: the model's `model_type` must be implemented in your installed
# mlx-lm. The default below has `model_type: "apertus"`, which needs
# mlx-lm >= 0.22. The verified setup is the .venv at the repo root
# (mlx-lm 0.32.0, first successful Apertus load 2026-10-09):
#   python3.12 -m venv .venv && .venv/bin/pip install "mlx-lm==0.32.0"
# `make eval-apertus-*` uses that .venv automatically. With the system
# python3 (older mlx-lm) set MLX_MODEL to a qwen2/llama model instead:
#   mlx-community/Qwen2.5-3B-Instruct-4bit     ~1.7 GB
#   mlx-community/Qwen2.5-7B-Instruct-4bit     ~4.3 GB
#   mlx-community/Meta-Llama-3.1-8B-Instruct-4bit  ~4.5 GB
MLX_MODEL = os.environ.get("MLX_MODEL", "swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4")

# Ollama backend (kept for later use).
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "apertus-8b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Retrieval settings
TOP_K = 5  # number of passages to retrieve
MIN_SIMILARITY = 0.3  # minimum cosine similarity threshold

# NLI labels
NLI_LABELS = ["entailment", "contradiction", "neutral"]