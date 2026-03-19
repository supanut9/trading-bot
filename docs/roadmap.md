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

- Phase 1 through Phase 10

Current repo baseline:

- paper-trading-first runtime with deterministic backtesting, bounded operator controls, reporting UI, operator console, performance analytics, deployment packaging, live-readiness groundwork, correlated runtime logging, correlation-aware notifications, notification-delivery reporting, notification-delivery filters, audit-report filters, and audit-report columns

Recommended next feature queue:

1. `feature/recovery-reporting-ui`
2. `feature/notification-reporting-ui`

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
