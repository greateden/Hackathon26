# Makefile - HackApertus Track 2A (Swiss voting-booklet NLI)
# Judges: `make run` runs the pipeline in Docker (portable; needs Docker
# only, no Python setup). On Apple Silicon, `make run-native` + the
# .venv give the Apertus MLX backend (see README.md and AGENTS.md
# "Docker runtime" for the model-endpoint setup and corpus downloads).

VENV_PY := $(shell test -x .venv/bin/python && echo $(CURDIR)/.venv/bin/python || echo python3)

.PHONY: help run run-native test test-full test-docker test-docker-pipeline eval-data eval-lex-quick eval-lex-full eval-lex-docker eval-apertus-quick eval-apertus-full fetch-booklets eval-e2e-quick eval-e2e-full

help:
	@echo "run                    - full pipeline over data/example_claims.json (lexical judge) via Docker"
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

# --- Docker (portable, Linux containers) ----------------------------------
# `make run` starts the pipeline through compose.yaml. Default judge is
# the LEXICAL baseline (smoke test only). For genuine Apertus inference
# run an Ollama-compatible server and pass its endpoint, e.g.:
#   LLM_BACKEND=ollama OLLAMA_MODEL=<model-on-your-server> make run
# (host.docker.internal:11434 is preconfigured; see AGENTS.md).
run:
	docker compose run --rm app python3 main.py

test-docker:
	docker compose run --rm app bash -c "python3 test_judge.py && python3 -m py_compile *.py"

test-docker-pipeline:
	docker compose run --rm app python3 test_pipeline.py

eval-lex-docker:
	docker compose run --rm app python3 eval_nli.py --split dev

# --- Native paths (macOS: Apple Silicon MLX lives here, not in Docker) ----
run-native:
	cd src && python3 main.py

test:
	cd src && python3 test_judge.py && python3 -m py_compile *.py

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

