# Makefile - HackApertus Track 2A (Swiss voting-booklet NLI)
# Judges: run `make run` from the repository root (see README.md for
# corpus setup and for using the .venv with the Apertus MLX backend).

VENV_PY := $(shell test -x .venv/bin/python && echo $(CURDIR)/.venv/bin/python || echo python3)

.PHONY: help run test test-full eval-data eval-lex-quick eval-lex-full eval-apertus-quick eval-apertus-full fetch-booklets eval-e2e-quick eval-e2e-full

help:
	@echo "run                 - full pipeline over data/example_claims.json (lexical judge default)"
	@echo "test                - offline unit checks (no model/corpus needed)"
	@echo "test-full           - also run the retrieval smoke test (needs corpus)"
	@echo "eval-data           - download the official evaluation dataset"
	@echo "eval-lex-quick      - 60-item dev eval, lexical heuristic (plumbing only)"
	@echo "eval-lex-full       - full eval split, lexical heuristic"
	@echo "eval-apertus-quick  - 10-item dev eval with the Apertus MLX judge"
	@echo "eval-apertus-full   - full eval split with the Apertus MLX judge"
	@echo "fetch-booklets      - download 60 booklet PDFs + extract passage corpus"
	@echo "eval-e2e-quick      - 60-item class-balanced end-to-end retrieval eval"
	@echo "eval-e2e-full       - full 1,488-item end-to-end retrieval eval"

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

fetch-booklets:
	cd src && python3 fetch_booklets.py

eval-e2e-quick:
	cd src && python3 eval_e2e.py --limit 60 --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage

eval-e2e-full:
	cd src && python3 eval_e2e.py --configs lexical,emb_v1,emb_v2,hyb_rrf,two_stage_lex,two_stage --dump-failures 10
