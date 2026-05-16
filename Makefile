.PHONY: install test lint typecheck run migrate clean

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=botox_session_ledger --cov=app --cov-report=term-missing

lint:
	ruff check .

typecheck:
	mypy botox_session_ledger.py app/

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -name "*.pyc" -delete
