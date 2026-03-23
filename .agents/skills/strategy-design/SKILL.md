---
name: strategy-design
description: Create, revise, or review trading strategy definitions, entry and exit rules, indicators, regime filters, stop logic, or risk assumptions in this repository. Use when a strategy idea must be turned into a deterministic spec before implementation or when a strategy change needs doc-first clarification.
---

# Strategy Design

1. Read `AGENTS.md`, `docs/product-spec.md`, and `docs/architecture.md`.
2. Create or update `docs/strategies/<strategy-name>.md` before implementation when the strategy behavior changes materially.
3. Define market, timeframe, indicators, entry rules, exit rules, stop assumptions, sizing assumptions, and invalidation conditions explicitly.
4. Keep strategy logic deterministic and free of exchange or persistence side effects.
5. List the required code and test changes before implementation when the request starts as design or review work.
6. Update `docs/decisions.md` when the strategy change also changes workflow or architecture expectations.
