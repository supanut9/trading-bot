from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

REQUEST_AUTHOR = "github-actions"
REQUEST_BODY = "@codex review"
CONNECTOR_LOGIN_PREFIX = "chatgpt-codex-connector"


@dataclass(frozen=True, slots=True)
class Activity:
    author: str
    created_at: datetime


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
        description="Check whether Codex has responded to the latest review request on a PR."
    )
    parser.add_argument("pr", help="Pull request number or URL.")
    return parser.parse_args()


def load_pr_activity(pr: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr,
            "--json",
            "comments,reviews",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown gh error"
        raise RuntimeError(message)

    return json.loads(result.stdout)


def evaluate_codex_review_status(payload: dict[str, Any]) -> CodexReviewState:
    latest_request = find_latest_request(payload.get("comments", []))
    if latest_request is None:
        return CodexReviewState(completed=False, reason="latest @codex review request not found")

    connector_comment = find_latest_connector_comment(payload.get("comments", []))
    connector_review = find_latest_connector_review(payload.get("reviews", []))
    latest_response = max_activity(connector_comment, connector_review)
    if latest_response is None:
        return CodexReviewState(completed=False, reason="connector has not responded yet")
    if latest_response.created_at <= latest_request.created_at:
        return CodexReviewState(
            completed=False,
            reason="connector response is older than the latest review request",
        )
    return CodexReviewState(completed=True, reason="connector response recorded after request")


def find_latest_request(comments: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for comment in comments:
        author = read_author_login(comment)
        body = str(comment.get("body") or "").strip()
        if author != REQUEST_AUTHOR or body != REQUEST_BODY:
            continue
        latest = max_activity(latest, to_activity(comment))
    return latest


def find_latest_connector_comment(comments: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for comment in comments:
        author = read_author_login(comment)
        if not author.startswith(CONNECTOR_LOGIN_PREFIX):
            continue
        latest = max_activity(latest, to_activity(comment))
    return latest


def find_latest_connector_review(reviews: list[dict[str, Any]]) -> Activity | None:
    latest: Activity | None = None
    for review in reviews:
        author = read_author_login(review)
        if not author.startswith(CONNECTOR_LOGIN_PREFIX):
            continue
        latest = max_activity(latest, to_activity(review))
    return latest


def max_activity(left: Activity | None, right: Activity | None) -> Activity | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left.created_at >= right.created_at else right


def to_activity(item: dict[str, Any]) -> Activity:
    created_at = item.get("createdAt")
    if not isinstance(created_at, str):
        raise ValueError("missing createdAt timestamp in PR activity payload")
    return Activity(
        author=read_author_login(item),
        created_at=parse_timestamp(created_at),
    )


def read_author_login(item: dict[str, Any]) -> str:
    author = item.get("author")
    if not isinstance(author, dict):
        raise ValueError("missing author in PR activity payload")
    login = author.get("login")
    if not isinstance(login, str):
        raise ValueError("missing author login in PR activity payload")
    return login


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
