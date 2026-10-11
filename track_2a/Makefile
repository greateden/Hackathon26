# Makefile - HackApertus Track 2A (Swiss voting-booklet NLI)
# Judges: `make run` runs the pipeline in Docker (portable; needs Docker
# and a configured v1.5 endpoint, no Python setup). Historical native paths + the
# .venv give the Apertus MLX backend (see README.md and AGENTS.md
# "Docker runtime" for the model-endpoint setup and corpus downloads).

VENV_DIR = $(if $(wildcard .venv/bin/python),$(CURDIR)/.venv,$(abspath ../.venv))
VENV_PY = $(if $(wildcard $(VENV_DIR)/bin/python),$(VENV_DIR)/bin/python,python3)

MLX_MODEL ?= swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4
MLX_SERVER_HOST ?= 127.0.0.1
MLX_SERVER_PORT ?= 8080

.PHONY: help run smoke serve-apertus run-native test test-full test-docker test-docker-pipeline eval-data eval-lex-quick eval-lex-full eval-lex-docker eval-apertus-quick eval-apertus-full eval-apertus-docker eval-apertus-oracle-docker ablation-dev ablation-smoke fetch-booklets eval-e2e-quick eval-e2e-full

help:
	@echo "run                    - Specified-booklet Docker application (configure LLM_BASE_URL; see docs/RUNNING.md)"
	@echo "smoke                  - Docker pipeline, lexical baseline only (no model server)"
	@echo "serve-apertus          - serve the Apertus MLX checkpoint natively (host GPU; separate terminal)"
	@echo "run-native             - same, natively with python3 (needed for the MLX backend)"
	@echo "test                   - offline unit checks, native (no model/corpus needed)"
	@echo "test-full              - also run the retrieval smoke test, native (needs corpus)"
	@echo "test-docker            - offline unit checks inside the container (no model server needed)"
	@echo "test-docker-pipeline   - full-pipeline smoke test in Docker (needs corpus + embedding model)"
	@echo "eval-lex-docker        - 60-item dev eval, lexical heuristic, in Docker (needs eval data)"
	@echo "eval-data              - download the official evaluation dataset"
	@echo "eval-lex-quick         - 60-item dev eval, lexical heuristic (plumbing only)"
	@echo "eval-lex-full          - full eval split, lexical heuristic"
	@echo "eval-apertus-quick     - 10-item dev eval with the Apertus MLX judge (native .venv only)"
	@echo "eval-apertus-full      - full eval split with the Apertus MLX judge (native .venv only)"
	@echo "fetch-booklets         - download 60 booklet PDFs + extract passage corpus"
	@echo "eval-e2e-quick         - 60-item class-balanced end-to-end retrieval eval"
	@echo "eval-e2e-full          - full 1,488-item end-to-end retrieval eval"
	@echo "ablation-smoke         - offline wiring check of the ablation harness (dry-run; plumbing only)"
	@echo "ablation-dev           - FULL prompt-config ablation, fixed dev split (needs serve-apertus; ran 2026-10-10, report §4.3)"

# --- Docker (portable, Linux containers) ----------------------------------
# `make run` uses the specified-booklet v1.5 endpoint application below.
# `make smoke` and the MLX server are historical research entry points.
# The v1.1 MLX server is not a prerequisite for the submission application.
serve-apertus:
	@test -x "$(VENV_DIR)/bin/mlx_lm.server" || { echo "ERROR: .venv/bin/mlx_lm.server missing."; echo "Rebuild: python3.12 -m venv .venv && .venv/bin/pip install 'mlx-lm==0.32.0' requests"; exit 1; }
	@echo "Serving $(MLX_MODEL) on $(MLX_SERVER_HOST):$(MLX_SERVER_PORT) (host GPU, MLX). Leave running; Ctrl-C stops. Historical client: make eval-apertus-docker."
	"$(VENV_DIR)/bin/mlx_lm.server" --model $(MLX_MODEL) --host $(MLX_SERVER_HOST) --port $(MLX_SERVER_PORT)

run:
	docker compose -f compose.submission.yaml run --build --rm app

smoke:
	docker compose run --rm app python3 main.py

test-docker:
	docker compose run --rm app bash -c "cd /app && python3 src/test_judge.py && PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' && python3 -m py_compile src/*.py"

test-docker-pipeline:
	docker compose run --rm app python3 test_pipeline.py

eval-lex-docker:
	docker compose run --rm app python3 eval_nli.py --split dev

# Real-Apertus evals through the container (need make serve-apertus).
# eval-apertus-docker = the genuine end-to-end task: retrieved evidence
# over the 60-booklet corpus (needs data/booklets/corpus.json first).
eval-apertus-docker:
	@echo ">> 60-item dev eval, REAL Apertus judge, retrieved evidence (booklet corpus)."
	@echo ">> Needs: make serve-apertus + data/booklets/corpus.json + data/eval/mnli_swiss_v1.1.jsonl"
	LLM_BACKEND=openai RETRIEVAL_CONFIG=v2 OPENAI_BASE_URL=http://host.docker.internal:$(MLX_SERVER_PORT) docker compose run --rm app python3 eval_nli.py --split dev --backend openai --evidence retrieve-v2

eval-apertus-oracle-docker:
	@echo ">> 60-item dev eval, REAL Apertus judge, GOLD evidence (judgement step only - not end-to-end)."
	LLM_BACKEND=openai OPENAI_BASE_URL=http://host.docker.internal:$(MLX_SERVER_PORT) docker compose run --rm app python3 eval_nli.py --split dev --backend openai --evidence oracle

# --- Prompt-config ablation (src/ablation_dev.py, added 2026-10-10) --------
# Memory procedure (hard rule): unload other memory-heavy apps (MTPLX etc.)
# first, start the server in a SEPARATE terminal (`make serve-apertus`), run
# the ablation, then Ctrl-C the server (verify: lsof -nP -iTCP:8080
# -sTCP:LISTEN). Do NOT auto-kill server processes from scripts.
# The runner checks the endpoint up front and refuses to start without it -
# no silent lexical fallback. Ran once with a real endpoint on 2026-10-10
# (report §4.3): strict rejected, select kept experimental, default unchanged.
ablation-dev:
	@echo ">> FULL prompt ablation on the fixed 60-item dev split:"
	@echo ">> t0/strict/select x retrieve-v2+oracle, t0 repeated for the"
	@echo ">> determinism check (8 runs). Needs make serve-apertus running."
	cd src && python3 ablation_dev.py --backend openai --repeats 2

ablation-smoke:
	@echo ">> Offline wiring check (no model). Uses the lexical heuristic"
	@echo ">> for plumbing only - its numbers are NOT model quality."
	cd src && python3 test_judge.py && python3 ablation_dev.py --dry-run

# --- Native paths (macOS: Apple Silicon MLX lives here, not in Docker) ----
run-native:
	cd src && python3 main.py

test:
	cd src && "$(VENV_PY)" test_judge.py && "$(VENV_PY)" -m py_compile *.py
	PYTHONPATH=src "$(VENV_PY)" -m unittest discover -s tests -p 'test_*.py'

test-full: test
	cd src && python3 test_pipeline.py

eval-data:
	cd src && python3 fetch_eval_data.py

eval-lex-quick:
	cd src && python3 eval_nli.py --split dev

eval-lex-full:
	cd src && python3 eval_nli.py --split eval

eval-apertus-quick:
	cd src && LLM_BACKEND=mlx MLX_MODEL=swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4 $(VENV_PY) eval_nli.py --split dev --backend mlx --limit 10

eval-apertus-full:
	cd src && LLM_BACKEND=mlx MLX_MODEL=swiss-ai/Apertus-v1.1-4B-Instruct-MLX-INT4 $(VENV_PY) eval_nli.py --split eval --backend mlx

fetch-booklets:
	cd src && python3 fetch_booklets.py

eval-e2e-quick:
	cd src && python3 eval_e2e.py --limit 60 --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage

eval-e2e-full:
	cd src && python3 eval_e2e.py --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage --dump-failures 10

