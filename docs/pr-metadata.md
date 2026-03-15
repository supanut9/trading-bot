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

## Assignees

- default assignee: `@supanut9`

## Milestones

Milestones should represent roadmap phases or grouped feature outcomes, not single commits.

Recommended initial milestones:

- `Phase 1 - Foundation`
- `Phase 2 - Core Trading Flow`
- `Phase 3 - Operations API`

## Projects

Use the `Trading Bot Delivery` project to track active PRs and feature delivery state.

## Review Resolution

When PR feedback arrives:

1. inspect all open review threads
2. decide whether each comment should be fixed, answered, or declined
3. implement the fix when appropriate
4. rerun validation for the affected scope
5. reply on the PR thread
6. resolve the thread after the response or fix is in place

## Merge Gate

- `main` should only be updated through pull requests
- PRs should resolve review threads before merge
- PRs should have passing CI checks before merge
- PRs should have at least one approval before merge
- prefer squash merge for feature branches
