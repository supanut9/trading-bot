from datetime import UTC, datetime

from scripts.codex_review_status import (
    CodexReviewState,
    evaluate_codex_review_status,
    load_pr_activity,
    parse_pr_repository,
    parse_timestamp,
    run_gh_paginated_json,
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


def test_codex_review_completed_from_connector_review_with_submitted_at() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("github-actions", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [
                {
                    "author": {"login": "chatgpt-codex-connector"},
                    "submittedAt": "2026-03-17T01:02:00Z",
                },
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


def test_codex_review_accepts_manual_request_comment() -> None:
    state = evaluate_codex_review_status(
        {
            "comments": [
                make_comment("supanut9", "@codex review", "2026-03-17T01:00:00Z"),
            ],
            "reviews": [
                make_review("chatgpt-codex-connector", "2026-03-17T01:02:00Z"),
            ],
            "review_comments": [],
        }
    )

    assert state == CodexReviewState(True, "connector review recorded after request")


def test_parse_timestamp_normalizes_zulu_to_utc() -> None:
    parsed = parse_timestamp("2026-03-17T01:02:03Z")

    assert parsed == datetime(2026, 3, 17, 1, 2, 3, tzinfo=UTC)


def test_parse_pr_repository_uses_requested_pr_url() -> None:
    owner, repo = parse_pr_repository(
        {"url": "https://github.com/example-org/example-repo/pull/42"}
    )

    assert (owner, repo) == ("example-org", "example-repo")


def test_run_gh_paginated_json_flattens_pages(monkeypatch) -> None:
    def fake_run_gh_json(command: list[str]) -> list[list[dict[str, object]]]:
        assert command == ["gh", "api", "--paginate", "--slurp", "repos/o/r/pulls/42/comments"]
        return [
            [make_review_comment("first", "page-one", "2026-03-17T01:00:00Z")],
            [make_review_comment("second", "page-two", "2026-03-17T01:01:00Z")],
        ]

    monkeypatch.setattr("scripts.codex_review_status.run_gh_json", fake_run_gh_json)

    payload = run_gh_paginated_json(
        ["gh", "api", "--paginate", "--slurp", "repos/o/r/pulls/42/comments"]
    )

    assert payload == [
        make_review_comment("first", "page-one", "2026-03-17T01:00:00Z"),
        make_review_comment("second", "page-two", "2026-03-17T01:01:00Z"),
    ]


def test_load_pr_activity_uses_requested_pr_repository_for_comments(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_gh_json(command: list[str]) -> object:
        calls.append(command)
        if command[:4] == [
            "gh",
            "pr",
            "view",
            "https://github.com/example-org/example-repo/pull/42",
        ]:
            return {
                "number": 42,
                "url": "https://github.com/example-org/example-repo/pull/42",
                "comments": [],
                "reviews": [],
            }
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/example-org/example-repo/pulls/42/comments",
        ]:
            return [
                [
                    make_review_comment(
                        "chatgpt-codex-connector",
                        "evidence",
                        "2026-03-17T01:00:00Z",
                    )
                ]
            ]
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("scripts.codex_review_status.run_gh_json", fake_run_gh_json)

    payload = load_pr_activity("https://github.com/example-org/example-repo/pull/42")

    assert payload["review_comments"] == [
        make_review_comment(
            "chatgpt-codex-connector",
            "evidence",
            "2026-03-17T01:00:00Z",
        )
    ]
    assert calls == [
        [
            "gh",
            "pr",
            "view",
            "https://github.com/example-org/example-repo/pull/42",
            "--json",
            "number,comments,reviews,url",
        ],
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/example-org/example-repo/pulls/42/comments",
        ],
    ]
