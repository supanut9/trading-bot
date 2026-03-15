# Decisions

## How To Use This File

Record decisions here when they materially affect architecture, trading behavior, safety controls, developer workflow, or operational handling.

Add a new entry when:

- a core technical choice is made
- a trading rule changes in a non-trivial way
- a safety control is introduced, removed, or redefined
- a workflow or repo policy changes

Do not use this file as a diary. Use it for durable decisions and their consequences.

## 2026-03-15

### Decision

Start with a single-repo monolith and paper trading only.

### Reason

This keeps the architecture small enough to be operated reliably by one developer and an AI agent while the domain model and workflow are still stabilizing.

### Consequence

Execution, API, and worker responsibilities stay in one codebase, but boundaries are enforced through modules instead of separate services.

## 2026-03-16

### Decision

Use PostgreSQL via Docker Compose as the default local development database, while keeping SQLite as a fallback.

### Reason

PostgreSQL provides a closer match to production-style persistence behavior and makes local development and repository integration testing more realistic. SQLite remains useful for simple bootstrap tasks when Docker is not needed.

### Consequence

The repository should prefer PostgreSQL-oriented persistence design, while still allowing local overrides of `DATABASE_URL` for lightweight workflows.
