---
description: Agent workflow for executing a task using the full dev cycle (branch → code → PR → merge)
---

# Execute Task with Dev Cycle

// turbo-all

This workflow should be used when executing any build phase or task. It wraps the actual work in the proper git branch → PR → merge cycle.

## Inputs
- `TASK_NAME`: e.g., "phase-1a-strategy-base"
- `TASK_TYPE`: e.g., "feat", "fix", "refactor", "test"
- `REPO_DIR`: e.g., "/Users/supanut.tan/projects/supanut9/trading-backtest-engine"
- `DESCRIPTION`: e.g., "Add AbstractStrategy base class and SMA indicator"

## Steps

### 1. Create task branch

```bash
cd $REPO_DIR
git checkout main
git pull origin main
git checkout -b $TASK_TYPE/$TASK_NAME
```

### 2. Execute the actual task

Do the implementation work here — create files, write code, run tests locally.

### 3. AI Self-Review & Audit 🤖

Before pushing, perform a systematic review:
1. **Logic**: Check for edge cases (empty data, network timeouts).
2. **Performance**: Verify Big O complexity (especially in data loops).
3. **Type Safety**: Ensure all new functions have strict type hints.
4. **Consistency**: Follow the project's architectural patterns.

If issues are found, fix them before moving to step 4.

### 4. Commit changes

Make small, atomic commits:
```bash
git add -A
git commit -m "$TASK_TYPE: $DESCRIPTION"
```

### 5. Push and create Standardized PR

Use the professional template for the PR body:

```bash
PR_TEMPLATE="## Summary
$DESCRIPTION

## Type of Change
- [x] $([[ $TASK_TYPE == "feat" ]] && echo "✨ Feature" || echo "$TASK_TYPE")
- [ ] 🐛 Bug Fix
- [ ] ⚡ Performance
- [ ] 🧪 Test

## AI Review Notes
- [Check 1]: Logic verified for $TASK_NAME
- [Check 2]: Type safety confirmed with Mypy
- [Check 3]: Performance audit complete

## Testing Results
- [x] Local Tests Passed
"

git push -u origin $TASK_TYPE/$TASK_NAME
gh pr create \
  --title "$TASK_TYPE: $DESCRIPTION" \
  --body "$PR_TEMPLATE" \
  --base main
```

### 5. Check CI status

```bash
sleep 10  # wait for CI to start
gh pr checks --watch
```

### 6. If CI fails, fix and push

```bash
# read CI output
gh pr checks

# fix issues
# ... make fixes ...

git add -A
git commit -m "fix: address CI failures"
git push
```

Repeat until CI passes.

### 7. Merge PR

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull origin main
```

### 8. Verify

```bash
git log --oneline -5
```
