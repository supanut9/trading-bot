---
name: strategy-design
description: Use when creating, revising, or reviewing a trading strategy definition, entry and exit rules, indicators, or risk assumptions.
---

# Purpose

Turn strategy ideas into deterministic specs before implementation.

# Workflow

1. Read `docs/product-spec.md` and `docs/architecture.md`.
2. Create or update `docs/strategies/<strategy-name>.md`.
3. Define market, timeframe, indicators, entry, exit, stop-loss assumptions, position sizing assumptions, and invalidation conditions.
4. List code changes required before implementation.
5. Implement only after the strategy document is explicit.

# Outputs

- strategy spec updated
- tests added or updated when code changes
- `docs/decisions.md` updated if architecture or workflow changes
