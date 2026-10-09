# Makefile - HackApertus Track 2A (Swiss voting-booklet NLI)
# Judges: run `make run` from the repository root (see README.md for
# corpus setup and for using the .venv with the Apertus MLX backend).

VENV_PY := $(shell test -x .venv/bin/python && echo $(CURDIR)/.venv/bin/python || echo python3)

.PHONY: help run test test-full eval-data eval-lex-quick eval-lex-full eval-apertus-quick eval-apertus-full

help:
	@echo "run                 - full pipeline over data/example_claims.json (lexical judge default)"
	@echo "test                - offline unit checks (no model/corpus needed)"
	@echo "test-full           - also run the retrieval smoke test (needs corpus)"
	@echo "eval-data           - download the official evaluation dataset"
	@echo "eval-lex-quick      - 60-item dev eval, lexical heuristic (plumbing only)"
	@echo "eval-lex-full       - full eval split, lexical heuristic"
	@echo "eval-apertus-quick  - 10-item dev eval with the Apertus MLX judge"
	@echo "eval-apertus-full   - full eval split with the Apertus MLX judge"

run:
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
