# PR Metadata

## Purpose

This document defines the default metadata and review workflow for pull requests in this repository.

## Labels

Every PR should use:

- exactly one `type:*` label
- one or two `area:*` labels
- exactly one `risk:*` label

Optional labels:

- one `status:*` label when workflow state needs to be visible

### Type Labels

- `type:feature`
- `type:fix`
- `type:chore`
- `type:docs`
- `type:test`
- `type:refactor`

### Area Labels

- `area:strategy`
- `area:risk`
- `area:execution`
- `area:market-data`
- `area:api`
- `area:database`
- `area:infra`
- `area:docs`

### Status Labels

- `status:ready`
- `status:blocked`

### Risk Labels

- `risk:low`
- `risk:medium`
- `risk:high`

## Assignees

- default assignee: `@supanut9`

## Milestones

Milestones should represent roadmap phases or grouped feature outcomes, not single commits.

Recommended initial milestones:

- `Phase 1 - Foundation`
- `Phase 2 - Core Trading Flow`
- `Phase 3 - Operations API`

Suggested mapping:

- foundation and persistence scaffolding work -> `Phase 1 - Foundation`
- market-data ingestion, strategy, risk, paper execution, and worker orchestration -> `Phase 2 - Core Trading Flow`
- API operations and operational visibility work -> `Phase 3 - Operations API`

## Projects

Use the `Trading Bot Delivery` project to track active PRs and feature delivery state.

### Project Status Meaning

- `Todo`: planned work that has not started
- `In Progress`: implementation is active on a feature branch
- `Done`: the PR is merged or the work is complete

Default mapping:

- planned but not started -> `Todo`
- create or start a feature branch -> `In Progress`
- open PRs also remain in `In Progress` on the current project because the board does not yet have a dedicated `In Review` status
- merge the PR -> `Done`

## Review Resolution

When PR feedback arrives:

1. inspect all open review threads
2. rely on the automated AI-review trigger for normal PR lifecycle events
3. wait for the `Codex Review Status` workflow to confirm the latest `@codex review` request received real review evidence
4. manually retrigger AI review after meaningful updates when needed
5. decide whether each comment should be fixed, answered, or declined
6. implement the fix when appropriate
7. rerun validation for the affected scope
8. reply on the PR thread
9. resolve the thread after the response or fix is in place

## Merge Gate

- `main` should only be updated through pull requests
- PRs should resolve review threads before merge
- PRs should have passing CI checks before merge
- PRs should have a passing `Codex Review Status` check before merge
- prefer squash merge for feature branches

## Validation Command

Use the repo check before calling a PR ready:

```bash
make pr-check
```

Behavior:

- inspects the PR for the current branch by default
- fails if required labels, assignee, milestone, or project are missing
- can also target a specific PR with `python3 -m scripts.check_pr_metadata <number-or-url>`
