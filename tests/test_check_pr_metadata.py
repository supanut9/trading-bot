from scripts.check_pr_metadata import PrMetadata, validate_pr_metadata


def test_validate_pr_metadata_accepts_policy_compliant_pr() -> None:
    metadata = PrMetadata(
        number=5,
        url="https://github.com/supanut9/trading-bot/pull/5",
        labels=("type:feature", "area:execution", "area:database", "risk:medium"),
        assignees=("supanut9",),
        milestone="Phase 2 - Core Trading Flow",
        projects=("Trading Bot Delivery",),
    )

    assert validate_pr_metadata(metadata) == []


def test_validate_pr_metadata_reports_missing_required_metadata() -> None:
    metadata = PrMetadata(
        number=6,
        url="https://github.com/supanut9/trading-bot/pull/6",
        labels=("status:ready",),
        assignees=(),
        milestone=None,
        projects=(),
    )

    errors = validate_pr_metadata(metadata)

    assert "expected exactly one type:* label, found none" in errors
    assert "expected one or two area:* labels, found none" in errors
    assert "expected exactly one risk:* label, found none" in errors
    assert "expected assignee @supanut9" in errors
    assert "expected a milestone" in errors
    assert "expected project 'Trading Bot Delivery'" in errors
