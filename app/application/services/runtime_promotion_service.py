from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.application.services.canary_rollout_service import CanaryRolloutService
from app.application.services.live_readiness_service import LiveReadinessService
from app.application.services.operator_runtime_config_service import OperatorRuntimeConfigService
from app.application.services.performance_review_decision_service import (
    PerformanceReviewDecisionService,
)
from app.application.services.qualification_service import QualificationService
from app.config import Settings
from app.infrastructure.database.repositories.runtime_control_repository import (
    RuntimeControlRepository,
)

RUNTIME_PROMOTION_STAGE_CONTROL = "runtime_promotion_stage"
PromotionStage = Literal["paper", "shadow", "qualified", "canary", "live"]
_PROMOTION_STAGE_ORDER: dict[PromotionStage, int] = {
    "paper": 0,
    "shadow": 1,
    "qualified": 2,
    "canary": 3,
    "live": 4,
}


@dataclass(frozen=True, slots=True)
class RuntimePromotionState:
    stage: PromotionStage
    source: str
    blockers: tuple[str, ...]
    updated_at: datetime | None = None
    updated_by: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePromotionUpdate:
    previous_stage: PromotionStage
    current_stage: PromotionStage
    changed: bool
    source: str
    blockers: tuple[str, ...]
    updated_at: datetime | None = None
    updated_by: str | None = None


class RuntimePromotionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._controls = RuntimeControlRepository(session)

    def get_state(self) -> RuntimePromotionState:
        record = self._controls.get_by_name(RUNTIME_PROMOTION_STAGE_CONTROL)
        if record is None or record.string_value is None:
            stage = self._default_stage()
            return RuntimePromotionState(
                stage=stage,
                source="settings",
                blockers=self._evaluate_stage_blockers(stage),
            )
        stage = self._normalize_stage(record.string_value)
        return RuntimePromotionState(
            stage=stage,
            source="runtime_control",
            blockers=self._evaluate_stage_blockers(stage),
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def set_stage(
        self,
        *,
        stage: PromotionStage,
        updated_by: str,
    ) -> RuntimePromotionUpdate:
        previous = self.get_state()
        if _PROMOTION_STAGE_ORDER[stage] > _PROMOTION_STAGE_ORDER[previous.stage]:
            blockers = self._evaluate_stage_blockers(stage)
            if blockers:
                raise ValueError("; ".join(blockers))
        else:
            blockers = self._evaluate_stage_blockers(stage)

        record = self._controls.upsert_string(
            control_name=RUNTIME_PROMOTION_STAGE_CONTROL,
            string_value=stage,
            updated_by=updated_by,
        )
        return RuntimePromotionUpdate(
            previous_stage=previous.stage,
            current_stage=stage,
            changed=previous.stage != stage,
            source="runtime_control",
            blockers=blockers,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def _evaluate_stage_blockers(self, stage: PromotionStage) -> tuple[str, ...]:
        blockers: list[str] = []
        exchange, symbol = self._active_market()
        if stage in {"qualified", "canary", "live"}:
            report = QualificationService(self._session).evaluate(
                exchange=exchange,
                symbol=symbol,
            )
            if not report.all_passed:
                blockers.append("qualification gates are not all passing")

        if stage in {"canary", "live"}:
            readiness = LiveReadinessService(self._session, self._settings).build_report()
            if not readiness.ready:
                blockers.append("live readiness is blocked")

        if stage == "live":
            multiplier = CanaryRolloutService(
                self._session,
                self._settings,
            ).get_exposure_multiplier()
            if multiplier < Decimal("1.0"):
                blockers.append("canary rollout has not reached full exposure")
            blockers.extend(
                self._evaluate_live_review_decision_blockers(
                    exchange=exchange,
                    symbol=symbol,
                )
            )

        return tuple(blockers)

    def _active_market(self) -> tuple[str, str]:
        config = OperatorRuntimeConfigService(
            self._session,
            self._settings,
        ).get_effective_config()
        return self._settings.exchange_name, config.symbol

    def _evaluate_live_review_decision_blockers(
        self,
        *,
        exchange: str,
        symbol: str,
    ) -> list[str]:
        decision = PerformanceReviewDecisionService(self._session).get_latest_decision(
            exchange=exchange,
            symbol=symbol,
        )
        if decision is None:
            return ["no persisted performance review decision is available"]
        if decision.stale:
            return ["latest performance review decision is stale"]
        if decision.operator_decision != "keep_running":
            return ["latest performance review decision does not approve full live promotion"]
        return []

    def _default_stage(self) -> PromotionStage:
        if self._settings.shadow_trading_enabled:
            return "shadow"
        if self._settings.live_trading_enabled:
            return "canary"
        return "paper"

    @staticmethod
    def _normalize_stage(value: str) -> PromotionStage:
        normalized = value.strip().lower()
        if normalized not in _PROMOTION_STAGE_ORDER:
            return "paper"
        return normalized  # type: ignore[return-value]
