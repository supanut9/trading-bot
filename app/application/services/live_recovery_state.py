from datetime import UTC, datetime


def classify_recovery_state(
    *,
    status: str,
    updated_at: datetime,
    stale_threshold_minutes: int,
    now: datetime | None = None,
) -> str:
    effective_now = now or datetime.now(tz=UTC)
    effective_updated_at = (
        updated_at.replace(tzinfo=UTC) if updated_at.tzinfo is None else updated_at.astimezone(UTC)
    )
    age_minutes = int((effective_now - effective_updated_at).total_seconds() // 60)
    is_stale = age_minutes >= stale_threshold_minutes

    if status == "review_required":
        return "manual_review_required"
    if status == "partially_filled":
        return "stale_partial_fill" if is_stale else "partial_fill_in_flight"
    if status in {"submitting", "submitted", "open"}:
        return "stale_open_order" if is_stale else "awaiting_exchange"
    return "resolved"


def next_action_for_recovery_state(recovery_state: str) -> str:
    if recovery_state == "manual_review_required":
        return "inspect_exchange_state"
    if recovery_state in {"stale_open_order", "stale_partial_fill"}:
        return "reconcile_or_cancel"
    if recovery_state in {"awaiting_exchange", "partial_fill_in_flight"}:
        return "reconcile_or_wait"
    return "none"
