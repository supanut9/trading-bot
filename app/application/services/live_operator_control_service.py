from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database.repositories.runtime_control_repository import (
    RuntimeControlRepository,
)

LIVE_TRADING_HALTED_CONTROL = "live_trading_halted"


@dataclass(frozen=True, slots=True)
class LiveTradingHaltState:
    halted: bool
    source: str
    reason: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


@dataclass(frozen=True, slots=True)
class LiveTradingHaltUpdate:
    previous_halted: bool
    current_halted: bool
    changed: bool
    source: str
    reason: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class LiveOperatorControlService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._controls = RuntimeControlRepository(session)
        self._settings = settings

    def get_live_trading_halt_state(self) -> LiveTradingHaltState:
        record = self._controls.get_by_name(LIVE_TRADING_HALTED_CONTROL)
        if record is None:
            return LiveTradingHaltState(
                halted=self._settings.live_trading_halted,
                source="settings",
            )
        return LiveTradingHaltState(
            halted=record.bool_value,
            source="runtime_control",
            reason=record.string_value,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def set_live_trading_halted(
        self,
        *,
        halted: bool,
        updated_by: str,
        reason: str | None = None,
    ) -> LiveTradingHaltUpdate:
        previous = self.get_live_trading_halt_state()
        record = self._controls.upsert_bool(
            control_name=LIVE_TRADING_HALTED_CONTROL,
            bool_value=halted,
            string_value=reason,
            updated_by=updated_by,
        )
        return LiveTradingHaltUpdate(
            previous_halted=previous.halted,
            current_halted=record.bool_value,
            changed=previous.halted != record.bool_value,
            source="runtime_control",
            reason=record.string_value,
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )
