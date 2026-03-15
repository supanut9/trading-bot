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

The current feature map lives in `docs/features.md`.

## Main Branch Rule

`main` is protected delivery history.

Expected merge gate:

1. pull request opened from a feature branch
2. CI checks pass
3. review feedback is addressed
4. review threads are resolved
5. at least one approval exists
6. PR is merged, preferably with squash merge

## Phase 1

- bootstrap AI-operable repository
- define project rules and docs
- scaffold Python application structure
- add API and worker entrypoints

## Phase 2

- implement configuration loading
- add database models and session management
- define exchange abstraction
- implement market data service

## Phase 3

- define strategy interface
- document EMA crossover strategy
- add backtest runner
- implement risk service

## Phase 4

- implement paper execution flow
- add status and position endpoints
- add notifications
- improve test coverage
