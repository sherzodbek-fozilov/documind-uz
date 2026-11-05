.PHONY: install test lint readme pairs finetune-eval
install:
	pip install -e ".[dev]"
test:
	python -m pytest -q
lint:
	ruff check documind tests scripts kaggle
readme:
	python scripts/render_readme.py
pairs:
	python scripts/make_training_pairs.py
finetune-eval:
	python scripts/eval_finetune.py --ft-model-dir models/multilingual-e5-small-ft
