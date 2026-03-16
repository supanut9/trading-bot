from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

REQUIRED_ASSIGNEE = "supanut9"
REQUIRED_PROJECT = "Trading Bot Delivery"


@dataclass(frozen=True, slots=True)
class PrMetadata:
    number: int
    url: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    milestone: str | None
    projects: tuple[str, ...]


def main() -> int:
    args = parse_args()
    try:
        metadata = load_pr_metadata(args.pr)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"PR metadata check failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_pr_metadata(metadata)
    if errors:
        print(f"PR metadata invalid for PR #{metadata.number} ({metadata.url}):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"PR metadata valid for PR #{metadata.number} ({metadata.url})")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate PR labels, assignee, milestone, and project policy."
    )
    parser.add_argument(
        "pr",
        nargs="?",
        help="Pull request number or URL. Defaults to the PR for the current branch.",
    )
    return parser.parse_args()


def load_pr_metadata(pr: str | None) -> PrMetadata:
    command = [
        "gh",
        "pr",
        "view",
        *([pr] if pr else []),
        "--json",
        "number,url,labels,assignees,milestone,projectItems",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown gh error"
        raise RuntimeError(message)

    payload = json.loads(result.stdout)
    return PrMetadata(
        number=payload["number"],
        url=payload["url"],
        labels=tuple(label["name"] for label in payload["labels"]),
        assignees=tuple(assignee["login"] for assignee in payload["assignees"]),
        milestone=payload["milestone"]["title"] if payload["milestone"] else None,
        projects=tuple(project["title"] for project in payload["projectItems"]),
    )


def validate_pr_metadata(metadata: PrMetadata) -> list[str]:
    errors: list[str] = []
    type_labels = select_labels(metadata.labels, "type:")
    area_labels = select_labels(metadata.labels, "area:")
    risk_labels = select_labels(metadata.labels, "risk:")

    if len(type_labels) != 1:
        errors.append(f"expected exactly one type:* label, found {format_labels(type_labels)}")
    if not 1 <= len(area_labels) <= 2:
        errors.append(f"expected one or two area:* labels, found {format_labels(area_labels)}")
    if len(risk_labels) != 1:
        errors.append(f"expected exactly one risk:* label, found {format_labels(risk_labels)}")
    if REQUIRED_ASSIGNEE not in metadata.assignees:
        errors.append(f"expected assignee @{REQUIRED_ASSIGNEE}")
    if metadata.milestone is None:
        errors.append("expected a milestone")
    if REQUIRED_PROJECT not in metadata.projects:
        errors.append(f"expected project '{REQUIRED_PROJECT}'")

    return errors


def select_labels(labels: Sequence[str], prefix: str) -> tuple[str, ...]:
    return tuple(label for label in labels if label.startswith(prefix))


def format_labels(labels: Sequence[str]) -> str:
    return ", ".join(labels) if labels else "none"


if __name__ == "__main__":
    raise SystemExit(main())
