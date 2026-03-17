from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

REQUEST_BODY = "@codex review"
CONNECTOR_LOGIN_PREFIX = "chatgpt-codex-connector"
NO_ISSUES_MARKERS = (
    "no issues found",
    "no actionable feedback",
    "no changes needed",
    "nothing to change",
)


@dataclass(frozen=True, slots=True)
class Activity:
    author: str
    created_at: datetime
    body: str = ""


@dataclass(frozen=True, slots=True)
class CodexReviewState:
    completed: bool
    reason: str


def main() -> int:
    args = parse_args()
    try:
        payload = load_pr_activity(args.pr)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Codex review status check failed: {exc}", file=sys.stderr)
        return 1

    state = evaluate_codex_review_status(payload)
    if state.completed:
        print(f"Codex review completed: {state.reason}")
        return 0

    print(f"Codex review pending: {state.reason}", file=sys.stderr)
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether Codex has produced real review evidence for the latest request."
    )
    parser.add_argument("pr", help="Pull request number or URL.")
    return parser.parse_args()


def load_pr_activity(pr: str) -> dict[str, Any]:
    pr_payload = run_gh_json(
        [
            "gh",
            "pr",
            "view",
            pr,
            "--json",
            "number,comments,reviews,url",
        ]
    )
    owner, repo = parse_pr_repository(pr_payload)
    review_comments = run_gh_paginated_json(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{owner}/{repo}/pulls/{pr_payload['number']}/comments",
        ]
    )

    return {
        "comments": pr_payload.get("comments", []),
        "reviews": pr_payload.get("reviews", []),
        "review_comments": review_comments,
    }


def run_gh_json(command: list[str]) -> Any:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown gh error"
        raise RuntimeError(message)
    return json.loads(result.stdout)


def run_gh_paginated_json(command: list[str]) -> list[dict[str, Any]]:
    payload = run_gh_json(command)
    if not isinstance(payload, list):
        raise ValueError("expected paginated gh payload to be a list")

    items: list[dict[str, Any]] = []
    for page in payload:
        if not isinstance(page, list):
            raise ValueError("expected paginated gh payload page to be a list")
        for item in page:
            if not isinstance(item, dict):
                raise ValueError("expected paginated gh payload item to be an object")
            items.append(item)
    return items


def evaluate_codex_review_status(payload: dict[str, Any]) -> CodexReviewState:
    latest_request = find_latest_request(payload.get("comments", []))
    if latest_request is None:
        return CodexReviewState(completed=False, reason="latest @codex review request not found")

    review = find_latest_connector_activity(payload.get("reviews", []))
    if is_after_request(review, latest_request):
        return CodexReviewState(completed=True, reason="connector review recorded after request")

    review_comment = find_latest_connector_activity(payload.get("review_comments", []))
    if is_after_request(review_comment, latest_request):
        return CodexReviewState(
            completed=True,
            reason="connector review comment recorded after request",
        )

    no_issues_comment = find_latest_no_issues_comment(payload.get("comments", []))
    if is_after_request(no_issues_comment, latest_request):
        return CodexReviewState(
            completed=True,
            reason="connector no-issues comment recorded after request",
        )

    return CodexReviewState(
        completed=False,
        reason="connector has not produced review evidence after the latest request",
    )


def find_latest_request(comments: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for comment in comments:
        body = read_body(comment)
        if body.strip() != REQUEST_BODY:
            continue
        latest = max_activity(latest, to_activity(comment))
    return latest


def find_latest_connector_activity(items: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for item in items:
        author = read_author_login(item)
        if not author.startswith(CONNECTOR_LOGIN_PREFIX):
            continue
        latest = max_activity(latest, to_activity(item))
    return latest


def find_latest_no_issues_comment(comments: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for comment in comments:
        author = read_author_login(comment)
        body = read_body(comment)
        if not author.startswith(CONNECTOR_LOGIN_PREFIX):
            continue
        normalized_body = body.lower()
        if not any(marker in normalized_body for marker in NO_ISSUES_MARKERS):
            continue
        latest = max_activity(latest, to_activity(comment))
    return latest


def is_after_request(activity: Activity | None, latest_request: Activity) -> bool:
    return activity is not None and activity.created_at > latest_request.created_at


def max_activity(left: Activity | None, right: Activity | None) -> Activity | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left.created_at >= right.created_at else right


def to_activity(item: dict[str, Any]) -> Activity:
    return Activity(
        author=read_author_login(item),
        created_at=parse_timestamp(read_timestamp(item)),
        body=read_body(item),
    )


def read_author_login(item: dict[str, Any]) -> str:
    author = item.get("author")
    if isinstance(author, dict):
        login = author.get("login")
        if isinstance(login, str):
            return login

    user = item.get("user")
    if isinstance(user, dict):
        login = user.get("login")
        if isinstance(login, str):
            return login

    raise ValueError("missing author login in PR activity payload")


def read_timestamp(item: dict[str, Any]) -> str:
    created_at = item.get("createdAt")
    if isinstance(created_at, str):
        return created_at
    created_at = item.get("created_at")
    if isinstance(created_at, str):
        return created_at
    submitted_at = item.get("submittedAt")
    if isinstance(submitted_at, str):
        return submitted_at
    raise ValueError("missing createdAt timestamp in PR activity payload")


def read_body(item: dict[str, Any]) -> str:
    body = item.get("body")
    return body if isinstance(body, str) else ""


def read_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        raise ValueError(f"missing {key} in PR activity payload")
    return value


def read_nested_login(item: dict[str, Any], key: str) -> str:
    nested = item.get(key)
    if not isinstance(nested, dict):
        raise ValueError(f"missing {key} in PR activity payload")
    login = nested.get("login")
    if not isinstance(login, str):
        raise ValueError(f"missing {key}.login in PR activity payload")
    return login


def parse_pr_repository(pr_payload: dict[str, Any]) -> tuple[str, str]:
    url = read_string(pr_payload, "url")
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4 or parts[2] != "pull":
        raise ValueError("unexpected pull request URL format in PR activity payload")
    return parts[0], parts[1]


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
