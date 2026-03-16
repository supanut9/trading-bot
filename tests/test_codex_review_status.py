from datetime import UTC, datetime

from scripts.codex_review_status import (
    CodexReviewState,
    evaluate_codex_review_status,
    parse_timestamp,
)


def make_comment(author: str, body: str, created_at: str) -> dict[str, object]:
    return {
        "author": {"login": author},
        "body": body,
        "createdAt": created_at,
    }


def make_review(author: str, created_at: str) -> dict[str, object]:
    return {
        "author": {"login": author},
        "createdAt": created_at,
    }


def test_codex_review_pending_without_request_comment() -> None:
    state = evaluate_codex_review_status({"comments": [], "reviews": []})

    assert state == CodexReviewState(False, "latest @codex review request not found")


def test_codex_review_pending_without_connector_response() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [],
        }
    )

    assert state == CodexReviewState(False, "connector has not responded yet")


def test_codex_review_pending_when_response_is_older_than_latest_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:10:00Z"),
                make_comment(
                    "chatgpt-codex-connector",
                    "old response",
                    "2026-03-17T01:05:00Z",
                ),
            ],
            "reviews": [],
        }
    )

    assert state == CodexReviewState(
        False,
        "connector response is older than the latest review request",
    )


def test_codex_review_completed_from_connector_comment_after_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
                make_comment(
                    "chatgpt-codex-connector",
                    "review finished",
                    "2026-03-17T01:01:00Z",
                ),
            ],
            "reviews": [],
        }
    )

    assert state == CodexReviewState(True, "connector response recorded after request")


def test_codex_review_completed_from_connector_review_after_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [
                make_review("chatgpt-codex-connector", "2026-03-17T01:02:00Z"),
            ],
        }
    )

    assert state == CodexReviewState(True, "connector response recorded after request")


def test_parse_timestamp_normalizes_zulu_to_utc() -> None:
    parsed = parse_timestamp("2026-03-17T01:02:03Z")

    assert parsed == datetime(2026, 3, 17, 1, 2, 3, tzinfo=UTC)
