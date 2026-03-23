# Roadmap

## Delivery Model

Work should be planned and delivered feature by feature.

Preferred cycle:

1. define feature scope
2. create `feature/<name>` branch from `main`
3. implement only that feature
4. run format, lint, and tests
5. commit in small logical commits
6. push branch
7. open PR
8. review and resolve comments
9. merge to `main`
10. start the next feature

Feature boundaries may evolve as the project becomes clearer, but implementation should still start from a named feature scope rather than an open-ended task list.

Practical scoping rule:

- small harmless docs or workflow-note updates can stay with the active feature branch
- behavior-changing or materially unrelated code changes should not ride along with another feature

The current feature map lives in `docs/features.md`.

## Main Branch Rule

`main` is protected delivery history.

Expected merge gate:

1. pull request opened from a feature branch
2. CI checks pass
3. review feedback is addressed
4. review threads are resolved
5. PR is merged with a normal merge commit unless preserving history differently is explicitly requested

## PR Metadata

Default PR metadata should stay lightweight:

- labels answer type, area, and risk
- assignee defaults to the repo owner
- milestones map to roadmap phases or grouped feature outcomes
- GitHub Project tracking is used for active PR delivery

## Review And Merge Rule

Before merge:

1. review comments are inspected
2. valid comments are fixed
3. validation is rerun for affected areas
4. replies are posted on the PR
5. review threads are resolved

`main` should receive changes through PRs only, and PRs should clear review feedback before merge.

## Current Delivery Status

Completed on `main`:

- Phase 1 through Phase 15

Current repo baseline:

- paper-trading-first runtime with deterministic backtesting, bounded operator controls, in-repo Next.js operator UI, performance analytics, deployment packaging, live-readiness groundwork, correlated runtime logging, correlation-aware notifications, notification-delivery reporting, notification-delivery filters, audit-report filters, audit-report columns, preset-first rule-builder backtests, backtest run history, market-data coverage readiness, realistic backtest cost modeling, walk-forward validation, signal quality improvements, exchange rule enforcement, shadow strategy runtime, strategy qualification gates, live risk hard gates, smart order execution, validate-only live orders, live ledger reconciliation hardening, production secrets and ops hardening, canary live rollout, live incident auto-halt, backtest daily-loss reset, DEFAULT_TIMEFRAME 1h, and multi-timeframe HTF trend confirmation

Recommended next feature queue:

Strategy quality first — these three features must come before any live deployment work:

- 1. `feature/realistic-backtest-cost-modeling` (implemented on `main`)
- 2. `feature/walk-forward-validation` (implemented on `main`)
- 3. `feature/signal-quality-improvements` (implemented on `main`)

Live readiness — exchange correctness, shadow validation, and qualification gates:

- 4. `feature/exchange-rule-enforcement` (implemented on `main`)
- 5. `feature/shadow-strategy-runtime` (implemented on `main`)
- 6. `feature/strategy-qualification-gates` (implemented on `main`)

Live execution infrastructure — risk gates, smart order routing, submission proof, and ledger:

- 7. `feature/live-risk-hard-gates` (implemented on `main`)
- 8. `feature/smart-order-execution` (implemented on `main`)
- 9. `feature/validate-only-live-orders` (implemented on `main`)
- 10. `feature/live-ledger-reconciliation-hardening` (implemented on `main`)

Live deployment — ops hardening, canary rollout, and fail-closed halting:

- 11. `feature/production-secrets-and-ops-hardening` (implemented on `main`)
- 12. `feature/canary-live-rollout` (implemented on `main`)
- 13. `feature/live-incident-auto-halt` (implemented on `main`)

Backtest hardening and dashboard visibility:

- 14. `feature/futures-leverage-backtest` (implemented on `main`)
- 15. `feature/dashboard-unrealized-pnl` (implemented on `main`)

Iteration — performance review and strategy improvement loop:

- 16. `feature/live-performance-review-loop` (partially implemented on `main`; completion pass needed)
- 17. `feature/strategy-iteration-workflow` (planned)

Recommended next bounded implementation sequence from the current codebase:

- 1. `feature/live-readiness-gate` (completed) — make live enablement depend on one explicit readiness report spanning qualification, reconciliation health, stale-order state, runtime halt posture, and configured live limits
- 2. `feature/portfolio-risk-governor` (completed) — add portfolio-level exposure, concentration, and concurrent-position controls on top of the existing live hard gates
- 3. `feature/execution-reconciliation-recovery` (completed) — turn the current restart, reconcile, and stale-order tools into one trusted recovery workflow
- 4. `feature/runtime-promotion-workflow` (in progress) — make paper → shadow → qualified → canary → live progression explicit, durable, and operator-auditable
- 5. `feature/backtest-market-friction-hardening` (in progress) — close more of the gap between replay assumptions and live-market behavior

Profitability improvements — what separates this bot from better real-world bots:

- 18. `feature/trade-exit-stop-loss` — ATR hard stop + trailing stop (highest impact) (implemented on `main`)
- 19. `feature/regime-detection` — ADX filter to avoid trading in choppy markets (implemented on `main`)
- 20. `feature/volatility-adjusted-sizing` — size positions relative to ATR, not flat % (implemented on `main`)
- 21. `feature/multi-symbol-trading` — trade multiple pairs for more edge opportunities (implemented on `main`)
- 22. `feature/multi-timeframe-confirmation` — higher timeframe trend alignment filter (implemented on `main`)
- 23. `feature/xgboost-signal-strategy` — ML-based signal generation using XGBoost on indicator features

Project completion boundary:

- one approved strategy can trade real money and has demonstrated positive expectancy after costs in walk-forward and shadow validation
- live execution is bounded by hard risk gates, exchange-rule enforcement, trustworthy reconciliation, and fail-closed incident handling
- completion means operationally safe and evidence-backed live execution, not guaranteed profitability in all market conditions

## Phase 1

Status:

- completed on `main`

- bootstrap AI-operable repository
- define project rules and docs
- scaffold Python application structure
- add API and worker entrypoints

## Phase 2

Status:

- completed on `main`

- implement configuration loading
- add database models and session management
- define exchange abstraction
- implement market data service

## Phase 3

Status:

- completed on `main`

- define strategy interface
- document EMA crossover strategy
- add backtest runner
- implement risk service

## Phase 4

Status:

- completed on `main`

- implement paper execution flow
- add status and position endpoints
- add notifications
- improve test coverage

## Phase 5

Status:

- completed on `main`

- harden live operations around exchange state visibility
- add scheduled reconciliation and startup resync paths
- add bounded cancellation and stale-order controls
- add exchange account visibility for operators

## Phase 6

Status:

- completed on `main`

- detect and surface stale live orders that remain open too long
- expose operator recovery tools for unresolved live order state
- strengthen live-state reporting and audit visibility
- reduce manual ambiguity during live incident handling

## Phase 7

Status:

- completed on `main`

- add deployment-oriented runbook hardening
- define alerting and operator response expectations
- improve backup, restore, and restart readiness
- document production operating constraints and safety checks

## Phase 8

Status:

- completed on `main`

- package the API and worker for reproducible deployment
- define deployment-time environment expectations and examples
- add bounded smoke-check tooling for post-deploy verification
- reduce manual setup drift between local and deployment environments

## Phase 9

Status:

- completed on `main`

- strengthen runtime reliability and operator diagnostics
- improve structured logging and failure correlation across API and worker paths
- tighten startup validation for deployment misconfiguration
- add bounded health or readiness checks for unattended operation

## Phase 10

Status:

- completed on `main`

- add an operator-facing UX inside the current FastAPI app
- surface live price and current market context without requiring raw API calls
- make paper-trading and demo validation easier through bounded operator controls
- keep the UX operational and lightweight instead of introducing a separate frontend stack

## Phase 11

Status:

- completed on `main`

- finish the research-first operator workflow
- add editable rule-builder backtests, recent replay history, and replay-readiness visibility
- keep all strategy flexibility bounded to backtesting rather than runtime execution

## Phase 12

Status:

- completed on `main`

- add realistic slippage and fee modeling to backtests so PnL expectations are trustworthy
- add walk-forward validation to detect overfitting before any live decisions are made
- add RSI and volume signal filters to reduce false entries and improve edge quality

## Phase 13

Status:

- completed on `main`

- enforce exchange symbol rules and precision for pre-submit correctness
- run the strategy in shadow mode against live data and measure signal drift versus walk-forward baseline
- define qualification gates that require positive cost-adjusted out-of-sample evidence before any capital is risked

## Phase 14

Status:

- completed on `main`

- harden live risk controls into hard blocking gates
- add limit-order execution with slippage tracking and fee-aware pre-submit validation
- prove signed submission via validate-only controls and harden the live ledger for partial fills

## Phase 15

Status:

- completed on `main`

- close operational gaps in secrets, backups, alerts, and incident drills
- enable one tightly bounded canary live rollout gated by the full promotion checklist
- add automatic incident halts when live state becomes unreliable

## Phase 16

Status:

- planned

- compare live results against walk-forward and shadow expectations on a fixed review loop
- identify whether underperformance is strategy decay, execution cost overshoot, or regime change
- define and execute the strategy re-validation and re-promotion workflow when results fall short
