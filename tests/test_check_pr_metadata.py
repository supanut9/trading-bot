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


def test_main_returns_failure_when_gh_cli_is_missing(monkeypatch, capsys) -> None:
    from scripts import check_pr_metadata

    monkeypatch.setattr(check_pr_metadata, "parse_args", lambda: type("Args", (), {"pr": None})())
    monkeypatch.setattr(
        check_pr_metadata,
        "load_pr_metadata",
        lambda _pr: (_ for _ in ()).throw(FileNotFoundError("gh not found")),
    )

    exit_code = check_pr_metadata.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "PR metadata check failed: gh not found" in captured.err
