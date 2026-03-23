---
name: risk-check
description: Review or implement code that touches order execution, position sizing, live trading flags, loss limits, promotion gates, reconciliation safety, or any trading safety control. Use when a change could weaken paper-first posture, risk controls, fail-closed behavior, or live-readiness safeguards.
---

# Risk Check

1. Read `AGENTS.md`, `docs/product-spec.md`, and the relevant strategy or runtime workflow docs.
2. Confirm paper trading remains the default posture unless the task explicitly changes guarded live groundwork.
3. Check duplicate-order protection, position sizing bounds, max-loss controls, and exchange-rule enforcement where relevant.
4. Check failure handling, structured logging, and operator visibility for uncertain or blocked execution paths.
5. Add or update tests that prove the safety behavior.
6. Summarize the safety-sensitive assumptions and the controls validated by the change.
