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


def make_review_comment(author: str, body: str, created_at: str) -> dict[str, object]:
    return {
        "user": {"login": author},
        "body": body,
        "created_at": created_at,
    }


def test_codex_review_pending_without_request_comment() -> None:
    state = evaluate_codex_review_status({"comments": [], "reviews": [], "review_comments": []})

    assert state == CodexReviewState(False, "latest @codex review request not found")


def test_codex_review_pending_without_review_evidence() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
                make_comment(
                    "chatgpt-codex-connector",
                    "connector ping only",
                    "2026-03-17T01:01:00Z",
                ),
            ],
            "reviews": [],
            "review_comments": [],
        }
    )

    assert state == CodexReviewState(
        False,
        "connector has not produced review evidence after the latest request",
    )


def test_codex_review_completed_from_connector_review_after_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [
                make_review("chatgpt-codex-connector", "2026-03-17T01:02:00Z"),
            ],
            "review_comments": [],
        }
    )

    assert state == CodexReviewState(True, "connector review recorded after request")


def test_codex_review_completed_from_connector_review_comment_after_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [],
            "review_comments": [
                make_review_comment(
                    "chatgpt-codex-connector[bot]",
                    "Review finding",
                    "2026-03-17T01:03:00Z",
                ),
            ],
        }
    )

    assert state == CodexReviewState(
        True,
        "connector review comment recorded after request",
    )


def test_codex_review_completed_from_explicit_no_issues_comment_after_request() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
                make_comment(
                    "chatgpt-codex-connector",
                    "No issues found in this pull request.",
                    "2026-03-17T01:04:00Z",
                ),
            ],
            "reviews": [],
            "review_comments": [],
        }
    )

    assert state == CodexReviewState(
        True,
        "connector no-issues comment recorded after request",
    )


def test_parse_timestamp_normalizes_zulu_to_utc() -> None:
    parsed = parse_timestamp("2026-03-17T01:02:03Z")

    assert parsed == datetime(2026, 3, 17, 1, 2, 3, tzinfo=UTC)
