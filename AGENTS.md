# AGENTS.md

## Project Objective

Operate a paper-trading-first trading platform with deterministic backtesting, operator-facing controls, reporting, deployment hardening, and guarded live-readiness groundwork.

## Current Phase

- monorepo with Python backend plus Next.js operator UI
- production target remains paper trading
- live capabilities exist only as controlled groundwork and must stay disabled by default until the runbook checklist is satisfied operationally
- current feature queue and bounded delivery plan live in `docs/features.md`

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- Pydantic settings
- PostgreSQL via Docker for local development
- SQLite only as a lightweight local fallback where explicitly appropriate
- Next.js in `web/`
- TanStack Query, Tailwind, shadcn/ui for the operator UI
- pytest

## Architecture Rules

- Keep strategy logic pure and deterministic.
- Do not call exchange APIs from strategy modules.
- Separate domain, application, infrastructure, and interface concerns.
- Keep paper trading as the default mode.
- Keep the Next.js UI thin: it may call FastAPI APIs, but it must not own trading logic.
- Route all runtime actions through application services, not directly from API routes or UI code.
- Keep execution mode derived from configuration and persisted operator controls, not ad hoc request flags.
- Treat shadow and live flows as safety-sensitive infrastructure paths, not strategy-layer concerns.
- Do not introduce microservices for v1.

## Coding Rules

- Add type hints to new Python code.
- Keep new frontend code typed as well.
- Prefer small single-purpose modules.
- Keep side effects in infrastructure and application layers.
- Never hardcode secrets.
- Use environment variables for configuration.
- Add concise docstrings only where behavior is not obvious from the code.
- Preserve structured logging and correlation identifiers for runtime, control, and notification flows.
- Keep API handlers thin; validation and orchestration belong in schemas and services.

## Validation Rules

- Add or update tests for strategy and risk changes.
- Add or update frontend tests when operator workflows or report rendering changes materially.
- Run `make format` before finishing implementation work.
- Run `make lint` before finishing implementation work.
- Run `make test` before finishing implementation work.
- Run `make pr-check` before finishing PR preparation when metadata or delivery state changed.
- Keep Git hooks installed locally with `make install-hooks`.
- For execution-related changes, include failure handling and structured logging.
- For live, shadow, worker, startup, reconciliation, and notification changes, validate the affected control/reporting path as well as the service itself.

## Documentation Rules

- Update `docs/product-spec.md` when system behavior changes.
- Update `docs/decisions.md` when architecture or workflow decisions change.
- Update `docs/runbook.md` when startup or operational procedures change.
- Update `docs/features.md` when adding, splitting, or completing a bounded feature.
- Update `docs/roadmap.md` when roadmap sequencing changes.
- Follow `docs/testing.md` when adding or changing tests.
- Add a dedicated strategy document under `docs/strategies/` before implementing a new strategy.

## Delivery Workflow

- Before making implementation changes, break the work down by feature first.
- Define the current feature boundary in `docs/features.md` before coding when the work is not already mapped there.
- Prefer one feature branch per bounded unit of work using the pattern `feature/<name>`.
- Keep commits small and logically grouped inside the current feature.
- After implementation, follow the cycle: branch, implement, validate, push, PR, review, resolve, merge.
- Do not continue stacking unrelated work into the current feature once its boundary is exceeded.
- Small harmless docs or workflow-note updates may stay with the current feature branch.
- Do not let runtime behavior, architecture, schema, or other material code changes hitchhike on an unrelated feature branch.
- Treat backend runtime work and operator UI work as one feature only when they deliver the same bounded operator outcome.

## Main Branch Policy

- `main` receives changes through pull requests only.
- Do not merge a PR into `main` while required checks are failing or missing.
- Do not merge a PR into `main` while unresolved review threads remain.
- Do not squash merge feature branches.
- Prefer merge commits for feature branches unless another merge method is explicitly requested.

## PR Metadata Policy

- Every PR should have exactly one `type:*` label.
- Every PR should have at least one `area:*` label and at most two.
- Every PR should have one `risk:*` label.
- Use `status:*` labels only for active workflow state such as ready or blocked.
- Assign PRs to `@supanut9` by default unless told otherwise.
- Use milestones for roadmap phases or feature groups, not for tiny tasks.
- Use the `Trading Bot Delivery` GitHub Project for active PR tracking.

## Review Workflow

- When a PR has review comments or review threads, inspect them before making more feature changes.
- AI review is auto-triggered for PR open, reopen, synchronize, and ready-for-review events.
- Manually retrigger AI review after meaningful updates when needed, for example by commenting `@codex review`.
- Address review feedback in this order: understand the comment, decide whether to apply a fix, implement the change if valid, validate the affected area, then reply on the PR thread.
- It is acceptable to decline a suggestion when it is incorrect or out of scope, but respond with a clear technical reason.
- Resolve review threads only after the code or rationale has been posted back to the PR.
- Do not merge while unresolved review threads remain unless the unresolved thread is explicitly acknowledged and intentionally deferred.

## Safety Rules

- Live trading must remain disabled unless explicitly enabled by configuration.
- Paper trading is the required default posture.
- Shadow trading and live trading must never both be enabled at the same time.
- Duplicate-order protection is required before any real execution work.
- Max-loss and position-size controls must exist before live execution is considered.
- Exchange symbol rules and quantity snapping must be enforced before any real order submission.
- Qualification and live-readiness gates must not be bypassed in promotion or operator workflows.
- Failing safely is preferred over attempting recovery with uncertain exchange state.

## Execution Policy

Proceed without asking for additional permission when the action stays within the repository, local development workflow, or normal GitHub delivery lifecycle and does not modify account or system security settings.

Default-allowed actions:

- read, create, edit, move, and delete files inside this repository
- run local development commands such as format, lint, test, API, web, worker, backtest, smoke-check, and local Docker commands
- install project dependencies required for development or verification
- install and run repository Git hooks
- create branches, stage files, commit changes, inspect git history, and prepare releases
- push branches to the configured remote
- inspect, create, update, review, comment on, and resolve pull request discussions
- inspect and manage normal GitHub workflow items related to the repository lifecycle, including PR status, checks, issue context, review follow-up, and merge-readiness work

Ask first for actions that change security posture, machine-wide state, or operate outside normal repo delivery:

- changing GitHub authentication state, switching accounts, or modifying GitHub settings
- changing repository visibility, branch protection, secrets, webhooks, environments, or admin settings
- enabling live trading or changing trading safety defaults
- destructive git operations such as `git reset --hard`, force-push, or deleting remote branches unless explicitly requested
- commands outside the repository that are not required for the current task
- opening GUI applications or changing OS-level configuration

Practical rule:

- GitHub lifecycle work is allowed by default.
- Dependency installation is allowed by default.
- Permission prompts should be reserved for security-sensitive, destructive, or out-of-scope actions.

## Commands

- Install: `make install`
- Install web: `make install-web`
- Install hooks: `make install-hooks`
- Init DB: `make init-db`
- DB up: `make db-up`
- DB down: `make db-down`
- DB logs: `make db-logs`
- Format: `make format`
- Lint: `make lint`
- Test: `make test`
- PR check: `make pr-check`
- Run API: `make run-api`
- Run web: `make run-web`
- Run worker: `make run-worker`
- Run backtest: `make run-backtest`
- Docker build: `make docker-build`
- Docker run API: `make docker-run-api`
- Docker run worker: `make docker-run-worker`
- Smoke check API: `make smoke-check-api`
- Smoke check worker: `make smoke-check-worker`
