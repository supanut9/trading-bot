from dataclasses import dataclass

from app.infrastructure.database.models.order import OrderRecord

ACTIVE_LIVE_ORDER_STATUSES = ("submitting", "submitted", "open", "partially_filled")
UNRESOLVED_LIVE_ORDER_STATUSES = ACTIVE_LIVE_ORDER_STATUSES + ("review_required",)
RECONCILABLE_LIVE_ORDER_STATUSES = UNRESOLVED_LIVE_ORDER_STATUSES
CANCELABLE_LIVE_ORDER_STATUSES = ACTIVE_LIVE_ORDER_STATUSES

_TERMINAL_STATUSES = ("filled", "canceled", "rejected")
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "submitting": {
        "submitting",
        "submitted",
        "open",
        "partially_filled",
        "canceled",
        "rejected",
        "review_required",
    },
    "submitted": {
        "submitted",
        "open",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "review_required",
    },
    "open": {
        "open",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "review_required",
    },
    "partially_filled": {
        "partially_filled",
        "filled",
        "canceled",
        "review_required",
    },
    "review_required": {
        "review_required",
        "open",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
    },
    "filled": {"filled"},
    "canceled": {"canceled"},
    "rejected": {"rejected"},
}
_STATUS_ALIASES = {
    "new": "open",
    "open": "open",
    "submitted": "submitted",
    "submitting": "submitting",
    "partiallyfilled": "partially_filled",
    "partially_filled": "partially_filled",
    "filled": "filled",
    "canceled": "canceled",
    "cancelled": "canceled",
    "rejected": "rejected",
    "expired": "rejected",
}


@dataclass(frozen=True, slots=True)
class LiveOrderStateResolution:
    status: str
    detail: str
    requires_operator_review: bool = False


def resolve_submission_state(raw_status: str | None) -> LiveOrderStateResolution:
    normalized = normalize_live_order_status(raw_status)
    if normalized is None:
        return LiveOrderStateResolution(
            status="review_required",
            detail="live submission returned an unknown exchange status",
            requires_operator_review=True,
        )
    if normalized == "filled":
        return LiveOrderStateResolution(
            status="review_required",
            detail="live submission returned filled status before reconciliation",
            requires_operator_review=True,
        )
    if normalized == "submitting":
        return LiveOrderStateResolution(status="submitted", detail="live order submitted")
    if normalized in _TERMINAL_STATUSES:
        return LiveOrderStateResolution(
            status=normalized,
            detail=f"live submission completed with terminal status {normalized}",
        )
    return LiveOrderStateResolution(status=normalized, detail="live order submitted")


def resolve_reconcile_state(
    raw_status: str | None,
    *,
    has_fill_details: bool,
) -> LiveOrderStateResolution:
    normalized = normalize_live_order_status(raw_status)
    if normalized is None:
        return LiveOrderStateResolution(
            status="review_required",
            detail="exchange returned an unknown live order status",
            requires_operator_review=True,
        )
    if normalized == "filled" and not has_fill_details:
        return LiveOrderStateResolution(
            status="review_required",
            detail="exchange reported filled but fill details were unavailable",
            requires_operator_review=True,
        )
    if normalized == "filled":
        return LiveOrderStateResolution(
            status="filled",
            detail="live order reconciled from filled exchange status",
        )
    if normalized == "canceled":
        return LiveOrderStateResolution(
            status="canceled",
            detail="exchange reported live order canceled",
        )
    if normalized == "rejected":
        return LiveOrderStateResolution(
            status="rejected",
            detail="exchange reported live order rejected",
        )
    if normalized == "partially_filled":
        return LiveOrderStateResolution(
            status="partially_filled",
            detail="live order partially filled on exchange",
        )
    return LiveOrderStateResolution(status=normalized, detail="live order still open on exchange")


def resolve_cancellation_state(raw_status: str | None) -> LiveOrderStateResolution:
    normalized = normalize_live_order_status(raw_status)
    if normalized in {"canceled", "rejected"}:
        return LiveOrderStateResolution(
            status=normalized,
            detail="live order canceled" if normalized == "canceled" else "live order rejected",
        )
    if normalized is None:
        return LiveOrderStateResolution(
            status="review_required",
            detail="live cancel returned an unknown exchange status",
            requires_operator_review=True,
        )
    return LiveOrderStateResolution(
        status="review_required",
        detail=f"live cancel returned non-terminal status {normalized}",
        requires_operator_review=True,
    )


def normalize_live_order_status(raw_status: str | None) -> str | None:
    if raw_status is None:
        return None
    key = raw_status.strip().lower()
    return _STATUS_ALIASES.get(key)


def transition_live_order(order: OrderRecord, *, next_status: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(order.status, {order.status, "review_required"})
    if next_status not in allowed:
        raise ValueError(f"invalid live order state transition: {order.status} -> {next_status}")
    order.status = next_status


def requires_operator_review(status: str) -> bool:
    return status == "review_required"
