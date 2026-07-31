.PHONY: help venv install test lint verify run-api run-worker clean

VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
UVICORN = $(VENV)/bin/uvicorn

help:
	@echo "Finance Intelligence Management Commands:"
	@echo "  make venv         - Initialize Python virtual environment"
	@echo "  make install      - Install locked dependencies"
	@echo "  make test         - Run all backend, integration, and contract tests"
	@echo "  make lint         - Run python syntax & boundary scanner checks"
	@echo "  make verify       - Run workspace boundary scanner"
	@echo "  make run-api      - Run FastAPI API control plane on port 8000"
	@echo "  make run-worker   - Run async worker skeleton"

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.lock

test:
	$(PYTEST) tests/

lint:
	$(PYTHON) -m py_compile services/api/app/main.py
	$(PYTHON) scripts/verify_boundary.py

verify:
	$(PYTHON) scripts/verify_boundary.py

run-api:
	PYTHONPATH=. $(UVICORN) services.api.app.main:app --reload --port 8000

run-worker:
	PYTHONPATH=. $(PYTHON) services/worker/app/main.py

clean:
	rm -rf .pytest_cache __pycache__ .venv
