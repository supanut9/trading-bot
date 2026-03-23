from pathlib import Path
from unittest.mock import MagicMock

from app.application.services.runtime_promotion_service import RuntimePromotionService
from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.runtime_control import RuntimeControlRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory


def build_session(tmp_path: Path, settings: Settings):
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    return create_session_factory(settings)()


def test_runtime_promotion_defaults_to_paper_stage(tmp_path: Path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion.db'}")
    session = build_session(tmp_path, settings)
    try:
        state = RuntimePromotionService(session, settings).get_state()

        assert state.stage == "paper"
        assert state.source == "settings"
        assert state.blockers == ()
        assert state.next_prerequisite is None
    finally:
        session.close()


def test_runtime_promotion_rejects_canary_when_readiness_blocked(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion_blocked.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session = build_session(tmp_path, settings)
    try:
        session.add(
            RuntimeControlRecord(
                control_name="runtime_promotion_stage",
                bool_value=False,
                string_value="paper",
                updated_by="test",
            )
        )
        session.commit()

        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.QualificationService",
            lambda _session: MagicMock(
                evaluate=lambda **kwargs: type("Report", (), {"all_passed": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.LiveReadinessService",
            lambda _session, _settings: MagicMock(
                build_report=lambda: type(
                    "Report",
                    (),
                    {
                        "ready": False,
                        "blocking_reasons": [
                            "live recovery posture is blocked: "
                            "1 unresolved live order(s) require manual exchange-state "
                            "review before trusting local recovery state "
                            "(next action: inspect_exchange_state)"
                        ],
                    },
                )()
            ),
        )

        service = RuntimePromotionService(session, settings)

        try:
            service.set_stage(stage="canary", updated_by="test")
        except ValueError as exc:
            assert "live readiness is blocked: live recovery posture is blocked" in str(exc)
        else:
            raise AssertionError("expected promotion to canary to be blocked")
    finally:
        session.close()


def test_runtime_promotion_promotes_to_live_when_prerequisites_pass(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion_live.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session = build_session(tmp_path, settings)
    try:
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.QualificationService",
            lambda _session: MagicMock(
                evaluate=lambda **kwargs: type("Report", (), {"all_passed": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.LiveReadinessService",
            lambda _session, _settings: MagicMock(
                build_report=lambda: type("Report", (), {"ready": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.CanaryRolloutService",
            lambda _session, _settings: MagicMock(get_exposure_multiplier=lambda: 1),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.PerformanceReviewDecisionService",
            lambda _session: MagicMock(
                get_latest_decision=lambda **kwargs: type(
                    "Decision",
                    (),
                    {
                        "operator_decision": "keep_running",
                        "stale": False,
                    },
                )()
            ),
        )

        update = RuntimePromotionService(session, settings).set_stage(
            stage="live",
            updated_by="test",
        )

        assert update.previous_stage == "canary"
        assert update.current_stage == "live"
        assert update.changed is True
        assert update.blockers == ()
        assert update.next_prerequisite is None
    finally:
        session.close()


def test_runtime_promotion_rejects_live_when_review_decision_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion_review_missing.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session = build_session(tmp_path, settings)
    try:
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.QualificationService",
            lambda _session: MagicMock(
                evaluate=lambda **kwargs: type("Report", (), {"all_passed": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.LiveReadinessService",
            lambda _session, _settings: MagicMock(
                build_report=lambda: type("Report", (), {"ready": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.CanaryRolloutService",
            lambda _session, _settings: MagicMock(get_exposure_multiplier=lambda: 1),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.PerformanceReviewDecisionService",
            lambda _session: MagicMock(get_latest_decision=lambda **kwargs: None),
        )

        try:
            RuntimePromotionService(session, settings).set_stage(
                stage="live",
                updated_by="test",
            )
        except ValueError as exc:
            assert "no persisted performance review decision is available" in str(exc)
        else:
            raise AssertionError("expected live promotion to be blocked without review decision")
    finally:
        session.close()


def test_runtime_promotion_rejects_live_when_review_decision_is_stale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion_review_stale.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session = build_session(tmp_path, settings)
    try:
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.QualificationService",
            lambda _session: MagicMock(
                evaluate=lambda **kwargs: type("Report", (), {"all_passed": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.LiveReadinessService",
            lambda _session, _settings: MagicMock(
                build_report=lambda: type("Report", (), {"ready": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.CanaryRolloutService",
            lambda _session, _settings: MagicMock(get_exposure_multiplier=lambda: 1),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.PerformanceReviewDecisionService",
            lambda _session: MagicMock(
                get_latest_decision=lambda **kwargs: type(
                    "Decision",
                    (),
                    {
                        "operator_decision": "keep_running",
                        "stale": True,
                    },
                )()
            ),
        )

        try:
            RuntimePromotionService(session, settings).set_stage(
                stage="live",
                updated_by="test",
            )
        except ValueError as exc:
            assert "latest performance review decision is stale" in str(exc)
        else:
            raise AssertionError("expected live promotion to be blocked by stale review")
    finally:
        session.close()


def test_runtime_promotion_rejects_live_when_operator_decision_is_not_keep_running(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'runtime_promotion_review_negative.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    session = build_session(tmp_path, settings)
    try:
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.QualificationService",
            lambda _session: MagicMock(
                evaluate=lambda **kwargs: type("Report", (), {"all_passed": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.LiveReadinessService",
            lambda _session, _settings: MagicMock(
                build_report=lambda: type("Report", (), {"ready": True})()
            ),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.CanaryRolloutService",
            lambda _session, _settings: MagicMock(get_exposure_multiplier=lambda: 1),
        )
        monkeypatch.setattr(
            "app.application.services.runtime_promotion_service.PerformanceReviewDecisionService",
            lambda _session: MagicMock(
                get_latest_decision=lambda **kwargs: type(
                    "Decision",
                    (),
                    {
                        "operator_decision": "reduce_risk",
                        "stale": False,
                    },
                )()
            ),
        )

        try:
            RuntimePromotionService(session, settings).set_stage(
                stage="live",
                updated_by="test",
            )
        except ValueError as exc:
            assert "does not approve full live promotion" in str(exc)
        else:
            raise AssertionError("expected live promotion to be blocked by operator decision")
    finally:
        session.close()
