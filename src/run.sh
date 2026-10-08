#!/usr/bin/env bash
# Helper to run the pipeline against the MLX NLI backend.
#
# Usage:
#   ./run.sh                                -> default model (Qwen2.5-3B-4bit)
#   ./run.sh <hf-model-id>                  -> override model
#   MEMORY_CHECK=1 ./run.sh                 -> abort if <20% memory free
#
# Examples of models that work with the mlx-lm 0.21.2 on this Mac:
#   ./run.sh mlx-community/Qwen2.5-3B-Instruct-4bit        (default, ~1.7 GB)
#   ./run.sh mlx-community/Qwen2.5-7B-Instruct-4bit        (~4.3 GB)
#   ./run.sh mlx-community/Meta-Llama-3.1-8B-Instruct-4bit (~4.5 GB)
#
# Models that need `pip3 install --upgrade mlx-lm` first:
#   ./run.sh mlx-community/Apertus-8B-Instruct-2509-4bit
#   ./run.sh swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4
set -e
cd "$(dirname "$0")"

MODEL="${1:-mlx-community/Qwen2.5-3B-Instruct-4bit}"

if [[ "${MEMORY_CHECK:-0}" == "1" ]]; then
  FREE_PCT=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/{print $2}' | tr -d '% ')
  echo "free memory: ${FREE_PCT}%"
  if (( $(echo "$FREE_PCT < 20" | bc -l) )); then
    echo "less than 20% memory free - close other apps first (or use a smaller MLX_MODEL)"
    exit 1
  fi
fi

echo "== running NLI judge with MLX backend, model=$MODEL =="
LLM_BACKEND=mlx MLX_MODEL="$MODEL" python3 main.py
