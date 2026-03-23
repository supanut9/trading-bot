---
name: api-implementation
description: Implement or revise FastAPI endpoints, request and response schemas, and API-facing orchestration in this repository. Use when changing HTTP routes, interface schemas, control endpoints, or API-layer validation and when the work must preserve the repository architecture of thin handlers and application-owned orchestration.
---

# API Implementation

1. Read `AGENTS.md`, `docs/architecture.md`, and any behavior docs that define the affected endpoint.
2. Keep route handlers thin. Put orchestration in application services and validation in schemas.
3. Keep exchange, persistence, and trading logic out of interface modules.
4. Add or update tests for endpoint behavior and failure paths.
5. Update `docs/product-spec.md`, `docs/runbook.md`, or `docs/decisions.md` when the API behavior or workflow changes materially.
