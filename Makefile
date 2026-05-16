.PHONY: install test lint run clean

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=botox_session_ledger --cov=api --cov-report=term-missing

lint:
	ruff check .

run:
	uvicorn api:app --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete
