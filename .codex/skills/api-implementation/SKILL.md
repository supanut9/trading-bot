---
name: api-implementation
description: Use when implementing or changing FastAPI endpoints, request and response schemas, or API-facing orchestration.
---

# Purpose

Implement API changes consistently with the repository architecture.

# Workflow

1. Read `AGENTS.md` and `docs/architecture.md`.
2. Keep business logic out of route handlers.
3. Add or update schemas near the API layer.
4. Add or update tests for endpoint behavior.
5. Update docs when endpoint behavior changes.
