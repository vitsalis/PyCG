PYTHON ?= python3

.PHONY: test lint format

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check pycg tests tools micro-benchmark/validate.py
	$(PYTHON) -m ruff format --check pycg tests tools micro-benchmark/validate.py

format:
	$(PYTHON) -m ruff check --select I --fix pycg tests tools micro-benchmark/validate.py
	$(PYTHON) -m ruff format pycg tests tools micro-benchmark/validate.py
