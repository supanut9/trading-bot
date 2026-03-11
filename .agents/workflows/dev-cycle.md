---
description: Development workflow — branch, code, commit, PR, CI, review, merge cycle
---

# Development Workflow

// turbo-all

This workflow defines how each task goes from code to merge. Follow this for every feature, bugfix, or phase.

## Git Flow

```
main (protected)
  └── feat/phase-1a-strategy-base   ← task branch
        ├── commit: "feat: add AbstractStrategy base class"
        ├── commit: "feat: add SMA indicator"
        └── PR → CI runs → review → merge → delete branch
```

## Steps

### 1. Create a task branch from main

```bash
git checkout main
git pull origin main
git checkout -b feat/<task-name>
```

Branch naming convention:
- `feat/<name>` — new feature
- `fix/<name>` — bugfix  
- `refactor/<name>` — refactoring
- `test/<name>` — adding tests

### 2. Code & commit (small, atomic commits)

```bash
git add -A
git commit -m "<type>: <short description>"
```

Commit types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

### 3. Push & create PR

```bash
git push origin feat/<task-name>
gh pr create --title "<type>: <description>" --body "## Changes\n- ...\n\n## Testing\n- ..." --base main
```

### 4. CI runs automatically

GitHub Actions will:
- **Lint** (ruff for Python / golangci-lint for Go)
- **Type check** (mypy for Python)
- **Test** (pytest for Python / go test for Go)
- **Build** verification

### 5. Review & fix

If CI fails or changes needed:
```bash
# fix issues locally
git add -A
git commit -m "fix: address review feedback"
git push origin feat/<task-name>
```

### 6. Merge & cleanup

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull origin main
```
