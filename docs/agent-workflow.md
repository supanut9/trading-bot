# Agent Workflow

## Purpose

Keep agent guidance aligned with the current OpenAI Codex structure so durable rules, repeatable workflows, and custom execution profiles stay separated.

## Repository Layout

- `AGENTS.md`: durable repository constraints that should apply broadly
- `.agents/skills/`: reusable repo skills for repeatable workflows
- `.codex/agents/`: optional Codex-specific custom subagent profiles

## Usage Rules

Use `AGENTS.md` for:

- architecture boundaries
- trading safety constraints
- required validation and documentation updates
- stable delivery constraints that rarely change

Use `.agents/skills/` for:

- repeatable implementation workflows
- repo-specific review checklists
- domain procedures that are too specific or too long for `AGENTS.md`

Use `.codex/agents/` only when you need a custom Codex subagent profile with different:

- model or reasoning settings
- sandbox or approval posture
- MCP configuration
- specialized developer instructions for delegated work

## Practical Guidance

- Keep `AGENTS.md` short and durable.
- Keep skills procedural and narrowly scoped.
- Prefer normal documentation in `docs/` for human-readable process details.
- Use subagents only for explicit delegation or parallel bounded work, not as the default workflow for ordinary repository tasks.

## Current Repo Skills

- `api-implementation`
- `risk-check`
- `strategy-design`

Add new skills only when the workflow is repeated often enough that re-explaining it in prompts or `AGENTS.md` creates drift.

## Current Custom Agents

- `repo_explorer`: read-only codebase mapper for locating execution paths and owning modules before implementation or review
- `trading_reviewer`: read-only reviewer for safety-sensitive runtime, execution, and risk changes
- `operator_ui_reviewer`: read-only reviewer for Next.js operator flows and FastAPI contract usage

Use these only when you explicitly want delegated or parallel subagent work. They are not the default path for ordinary repository tasks.
