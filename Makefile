.PHONY: install test lint readme
install:
	pip install -e ".[dev]"
test:
	python -m pytest -q
lint:
	ruff check documind tests scripts
readme:
	python scripts/render_readme.py
