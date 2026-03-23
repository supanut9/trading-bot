from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.live_order_recovery_report_service import (
    LiveOrderRecoveryReportService,
)
from app.application.services.operator_runtime_config_service import OperatorRuntimeConfigService
from app.application.services.qualification_service import QualificationService
from app.application.services.symbol_rules_service import SymbolRulesService
from app.config import Settings


@dataclass(frozen=True, slots=True)
class LiveReadinessCheck:
    name: str
    passed: bool
    severity: str
    detail: str


@dataclass(frozen=True, slots=True)
class LiveReadinessReport:
    status: str
    ready: bool
    checks: list[LiveReadinessCheck]
    blocking_reasons: list[str]


class LiveReadinessService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def build_report(self) -> LiveReadinessReport:
        config = OperatorRuntimeConfigService(
            self._session,
            self._settings,
        ).get_effective_config()
        symbol = config.symbol
        exchange = self._settings.exchange_name
        checks = [
            self._check_live_enabled(),
            self._check_runtime_halt(),
            self._check_exchange_credentials(),
            self._check_symbol_rules(exchange=exchange, symbol=symbol),
            self._check_qualification(exchange=exchange, symbol=symbol),
            self._check_startup_sync_enabled(),
            self._check_reconcile_schedule_enabled(),
            self._check_recovery_posture(),
            self._check_live_max_order_notional(),
            self._check_live_max_position_quantity(),
        ]
        blocking_reasons = [check.detail for check in checks if not check.passed]
        return LiveReadinessReport(
            status="ready" if not blocking_reasons else "blocked",
            ready=not blocking_reasons,
            checks=checks,
            blocking_reasons=blocking_reasons,
        )

    def blocking_reasons(self) -> list[str]:
        return self.build_report().blocking_reasons

    def is_ready(self) -> bool:
        return self.build_report().ready

    def _check_live_enabled(self) -> LiveReadinessCheck:
        return LiveReadinessCheck(
            name="live_trading_enabled",
            passed=self._settings.live_trading_enabled,
            severity="blocking",
            detail=(
                "live trading is enabled in configuration"
                if self._settings.live_trading_enabled
                else "live trading is disabled in configuration"
            ),
        )

    def _check_runtime_halt(self) -> LiveReadinessCheck:
        halted = (
            LiveOperatorControlService(
                self._session,
                self._settings,
            )
            .get_live_trading_halt_state()
            .halted
        )
        return LiveReadinessCheck(
            name="runtime_live_halt",
            passed=not halted,
            severity="blocking",
            detail=(
                "runtime live halt is cleared"
                if not halted
                else "live trading is currently halted by operator control"
            ),
        )

    def _check_exchange_credentials(self) -> LiveReadinessCheck:
        credentials_present = bool(
            self._settings.exchange_api_key and self._settings.exchange_api_secret
        )
        return LiveReadinessCheck(
            name="exchange_credentials",
            passed=credentials_present,
            severity="blocking",
            detail=(
                "exchange credentials are configured"
                if credentials_present
                else "exchange credentials are missing"
            ),
        )

    def _check_symbol_rules(self, *, exchange: str, symbol: str) -> LiveReadinessCheck:
        rules = SymbolRulesService(self._session).get_rules_result(exchange=exchange, symbol=symbol)
        return LiveReadinessCheck(
            name="symbol_rules",
            passed=rules is not None,
            severity="blocking",
            detail=(
                "exchange symbol rules are available"
                if rules is not None
                else "exchange symbol rules are not available for the configured symbol"
            ),
        )

    def _check_qualification(self, *, exchange: str, symbol: str) -> LiveReadinessCheck:
        report = QualificationService(self._session).evaluate(exchange=exchange, symbol=symbol)
        return LiveReadinessCheck(
            name="qualification",
            passed=report.all_passed,
            severity="blocking",
            detail=(
                "strategy qualification gates are passing"
                if report.all_passed
                else "strategy qualification gates are not all passing"
            ),
        )

    def _check_startup_sync_enabled(self) -> LiveReadinessCheck:
        return LiveReadinessCheck(
            name="startup_state_sync",
            passed=self._settings.startup_state_sync_enabled,
            severity="blocking",
            detail=(
                "startup state sync is enabled"
                if self._settings.startup_state_sync_enabled
                else "startup state sync is disabled"
            ),
        )

    def _check_reconcile_schedule_enabled(self) -> LiveReadinessCheck:
        return LiveReadinessCheck(
            name="live_reconcile_schedule",
            passed=self._settings.live_reconcile_schedule_enabled,
            severity="blocking",
            detail=(
                "live reconcile schedule is enabled"
                if self._settings.live_reconcile_schedule_enabled
                else "live reconcile schedule is disabled"
            ),
        )

    def _check_recovery_posture(self) -> LiveReadinessCheck:
        summary = (
            LiveOrderRecoveryReportService(
                self._session,
                self._settings,
            )
            .build_report(order_limit=50, audit_limit=1)
            .summary
        )
        passed = summary.posture in {"clear", "awaiting_exchange"}
        detail = f"live recovery posture is {summary.posture}"
        if passed and summary.unresolved_order_count == 0:
            detail = "live recovery posture is clear"
        elif passed:
            detail = f"live recovery posture is {summary.posture}: {summary.summary}"
        else:
            detail = (
                f"live recovery posture is blocked: {summary.summary} "
                f"(next action: {summary.next_action})"
            )
        return LiveReadinessCheck(
            name="live_recovery_posture",
            passed=passed,
            severity="blocking",
            detail=detail,
        )

    def _check_live_max_order_notional(self) -> LiveReadinessCheck:
        value = self._settings.live_max_order_notional
        return LiveReadinessCheck(
            name="live_max_order_notional",
            passed=value is not None and value > Decimal("0"),
            severity="blocking",
            detail=(
                "live max order notional is configured"
                if value is not None and value > Decimal("0")
                else "live max order notional is not configured"
            ),
        )

    def _check_live_max_position_quantity(self) -> LiveReadinessCheck:
        value = self._settings.live_max_position_quantity
        return LiveReadinessCheck(
            name="live_max_position_quantity",
            passed=value is not None and value > Decimal("0"),
            severity="blocking",
            detail=(
                "live max position quantity is configured"
                if value is not None and value > Decimal("0")
                else "live max position quantity is not configured"
            ),
        )
