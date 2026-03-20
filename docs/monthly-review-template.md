# Monthly Strategy Review — {MONTH} {YEAR}

## Instructions

Fill in each section from the `/reports/performance-review` API endpoint output.
Run `GET /reports/performance-review?review_period_days=30` before starting.

---

## 1. Performance Summary

**Review period:** {START_DATE} to {END_DATE} (30 days)

### Live Mode

| Metric | Value |
|---|---|
| Trade count | |
| Win rate % | |
| Expectancy | |
| Max drawdown % | |
| Total net PnL | |
| Total fees paid | |
| Avg slippage % | |
| Slippage sample count | |

### Shadow Mode

| Metric | Value |
|---|---|
| Trade count | |
| Win rate % | |
| Expectancy | |
| Max drawdown % | |
| Total net PnL | |

### OOS Baseline (latest walk-forward)

| Metric | Value |
|---|---|
| Backtest run ID | |
| Run date | |
| OOS return % | |
| OOS drawdown % | |
| OOS total trades | |
| In-sample return % | |
| Overfitting warning | |

---

## 2. Health Check

Fill in from `health_indicators` in the API response.

| Indicator | Value | Status |
|---|---|---|
| Slippage vs model % | | green / yellow / red |
| Shadow vs OOS expectancy drift % | | green / yellow / red |
| Live vs shadow win rate drift % | | green / yellow / red |
| Consecutive losses | | green / yellow / red |
| Signal frequency per week | | normal / low / high |

### Threshold Reference

| Indicator | Reduce risk | Pause and rework | Halt |
|---|---|---|---|
| Consecutive losses | — | — | >= 5 |
| Max drawdown % | — | — | > 30% |
| Live vs shadow win rate drift | < -10% | < -20% | — |
| Slippage vs model % | > 1.0% | > 2.0% | — |

---

## 3. System Recommendation

API recommendation (from `recommendation` field):

```
{recommendation}
```

Reasons (from `recommendation_reasons` field):

- {reason_1}
- {reason_2}

---

## 4. Operator Decision

Review each option and check exactly one:

- [ ] **keep_running** — performance within acceptable range, continue as configured
- [ ] **reduce_risk** — reduce position sizing or capital allocation; monitor closely
- [ ] **pause_and_rework** — suspend live entries, review strategy and parameters, re-qualify before resuming
- [ ] **halt** — immediately halt live entries, investigate root cause before any further execution

**Decision rationale:**

> (Write your reasoning here, including any factors not captured by the automated indicators)

---

## 5. Action Items

If decision is reduce_risk, pause_and_rework, or halt, list the specific steps:

- [ ]
- [ ]
- [ ]

**Target resolution date:** {DATE}

**Responsible operator:** {NAME}

---

## 6. Notes

Any additional context, market regime observations, or external factors:

>

---

*Generated from `/reports/performance-review` — review period: 30 days*
