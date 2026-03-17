.PHONY: install install-hooks init-db db-up db-down db-logs format lint test pr-check run-api run-worker run-backtest docker-build docker-run-api docker-run-worker smoke-check-api smoke-check-worker

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

run-backtest:
	python3 -m app.backtest

docker-build:
	docker build -t trading-bot:latest .

docker-run-api:
	docker run --rm -p 8000:8000 --env-file .env -e API_HOST=0.0.0.0 trading-bot:latest

docker-run-worker:
	docker run --rm --env-file .env -e APP_RUNTIME=worker trading-bot:latest

smoke-check-api:
	python3 -m scripts.post_deploy_smoke_check --role api --base-url $${SMOKE_CHECK_BASE_URL:-http://127.0.0.1:8000}

smoke-check-worker:
	python3 -m scripts.post_deploy_smoke_check --role worker
