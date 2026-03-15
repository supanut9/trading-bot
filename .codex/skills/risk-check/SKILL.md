---
name: risk-check
description: Use when code touches order execution, position sizing, live trading flags, loss limits, or any trading safety control.
---

# Purpose

Prevent unsafe execution changes from entering the codebase.

# Checklist

- paper trading remains the default
- duplicate-order protection is considered
- position sizing is bounded
- max-loss controls are considered
- failure paths are logged
- secrets are not hardcoded

# Output

Summarize the safety risks checked and the code or config changes made.
