.PHONY: install install-hooks init-db db-up db-down db-logs format lint test pr-check run-api run-worker

install:
	python3 -m pip install -e ".[dev]"

install-hooks:
	python3 -m pre_commit install --hook-type pre-commit --hook-type pre-push

init-db:
	python3 -m scripts.init_db

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

format:
	python3 -m ruff format .

lint:
	python3 -m ruff check .

test:
	python3 -m pytest

pr-check:
	python3 -m scripts.check_pr_metadata

run-api:
	python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

run-worker:
	python3 -m app.worker
