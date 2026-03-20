# Gemini Context: Trading Bot

## Project Overview
This project is a paper-trading-first trading bot platform designed to be operable by AI agents and humans. It features a Python backend using FastAPI and a Next.js frontend. The system supports backtesting, paper trading, and is built with a clean service architecture and strong safety defaults.

## Tech Stack
*   **Backend:** Python 3.12+, FastAPI, SQLAlchemy, Pydantic, PostgreSQL.
*   **Frontend:** Next.js (TypeScript), React, Tailwind CSS, TanStack Query, Vitest.
*   **Infrastructure:** Docker, Docker Compose.
*   **Testing:** Pytest (backend), Vitest (frontend).
*   **Linting/Formatting:** Ruff (backend), ESLint/Prettier (frontend).

## Directory Structure
*   `app/`: Backend application source code (API, worker, services, domain logic).
*   `web/`: Frontend Next.js application source code.
*   `scripts/`: Utility scripts for database initialization, checks, and deployment.
*   `tests/`: Backend test suite.
*   `docs/`: Project documentation (architecture, features, runbook).
*   `deployment/`: Deployment configurations.

## Setup & Development

### Prerequisites
*   Python 3.12+
*   Node.js & Yarn
*   Docker & Docker Compose

### Key Commands (Makefile)
The project uses a `Makefile` for common tasks.

**Setup:**
*   `make install`: Install backend dependencies.
*   `make install-web`: Install frontend dependencies.
*   `make install-hooks`: Setup git hooks (pre-commit).
*   `make init-db`: Initialize the local database schema.
*   `make db-up`: Start the local PostgreSQL database via Docker.

**Running:**
*   `make run-api`: Start the FastAPI backend (localhost:8000).
*   `make run-web`: Start the Next.js frontend (localhost:3005).
*   `make run-worker`: Start the background worker process.
*   `make run-backtest`: Run the backtesting engine.

**Testing & Quality:**
*   `make test`: Run backend and frontend tests.
*   `make lint`: Run linters (Ruff, ESLint).
*   `make format`: Auto-format code (Ruff).
*   `make pr-check`: Run metadata checks for PRs.

**Docker:**
*   `make docker-build`: Build the production Docker image.
*   `make docker-run-api`: Run the API in a container.
*   `make docker-run-worker`: Run the worker in a container.

## Development Conventions
*   **Code Style:** Strict adherence to `ruff` for Python and standard ESLint/Prettier rules for TypeScript/React.
*   **Testing:** All new features and bug fixes must include tests. Backend uses `pytest`, frontend uses `vitest`.
*   **Database:** Local development uses PostgreSQL via Docker. Do not use SQLite for non-local runtimes.
*   **Architecture:** Follows a service-layer architecture. Domain logic should reside in `app/domain` or `app/application`, not directly in API handlers.
*   **Documentation:** Update `docs/` when changing architecture or adding features.

## Important Files
*   `README.md`: Entry point and general guide.
*   `Makefile`: Task automation.
*   `pyproject.toml`: Python project configuration.
*   `web/package.json`: Frontend project configuration.
*   `docker-compose.yml`: Local infrastructure definition.
