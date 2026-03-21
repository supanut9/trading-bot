from dataclasses import asdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.operational_control_service import (
    BacktestRunOptions,
    MarketSyncRunOptions,
    OperationalControlService,
)
from app.application.services.qualification_service import QualificationService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session_factory_dependency
from app.interfaces.api.backtest_rule_mapping import (
    to_rule_builder_config,
    to_rule_builder_request,
)
from app.interfaces.api.schemas import (
    BacktestControlRequest,
    BacktestControlResponse,
    FeatureImportanceSchema,
    LiveCancelControlRequest,
    LiveCancelControlResponse,
    LiveHaltControlRequest,
    LiveHaltControlResponse,
    LiveReconcileControlResponse,
    MarketSyncControlRequest,
    MarketSyncControlResponse,
    ModelStatusItem,
    ModelStatusResponse,
    OperatorConfigRequest,
    OperatorConfigResponse,
    QualificationGateResponse,
    QualificationReportResponse,
    SymbolRulesControlResponse,
    TrainModelResponse,
    WorkerControlResponse,
)
from app.interfaces.api.schemas import (
    TrainModelRequest as TrainModelRequestSchema,
)

router = APIRouter(prefix="/controls", tags=["controls"])
settings_dependency = Depends(get_settings)
session_factory_dependency = Depends(get_session_factory_dependency)


@router.post(
    "/worker-cycle",
    response_model=WorkerControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_worker_cycle(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> WorkerControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_worker_cycle(source="api.control")
    return WorkerControlResponse.model_validate(result)


@router.get(
    "/operator-config",
    response_model=OperatorConfigResponse,
    status_code=status.HTTP_200_OK,
)
def get_operator_config(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> OperatorConfigResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).get_operator_config()
    return OperatorConfigResponse.model_validate(result)


@router.post(
    "/operator-config",
    response_model=OperatorConfigResponse,
    status_code=status.HTTP_200_OK,
)
def update_operator_config(
    request: OperatorConfigRequest,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> OperatorConfigResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_update_operator_config(
        strategy_name=request.strategy_name,
        symbol=request.symbol,
        timeframe=request.timeframe,
        fast_period=request.fast_period,
        slow_period=request.slow_period,
        trading_mode=request.trading_mode,
        source="api.control",
    )
    return OperatorConfigResponse.model_validate(result)


@router.post(
    "/backtest",
    response_model=BacktestControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_backtest(
    request: Annotated[BacktestControlRequest | None, Body()] = None,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> BacktestControlResponse:
    payload = request or BacktestControlRequest()
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_backtest(
        options=BacktestRunOptions(
            strategy_name=payload.strategy_name,
            exchange=payload.exchange,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            fast_period=payload.fast_period,
            slow_period=payload.slow_period,
            starting_equity=payload.starting_equity,
            slippage_pct=payload.slippage_pct,
            fee_pct=payload.fee_pct,
            walk_forward_split_ratio=payload.walk_forward_split_ratio,
            rules=to_rule_builder_config(payload.rules),
            rsi_period=payload.rsi_period,
            rsi_overbought=payload.rsi_overbought,
            rsi_oversold=payload.rsi_oversold,
            volume_ma_period=payload.volume_ma_period,
            macd_signal_period=payload.macd_signal_period,
            bb_period=payload.bb_period,
            bb_std_dev=payload.bb_std_dev,
            breakout_period=payload.breakout_period,
            atr_period=payload.atr_period,
            atr_breakout_multiplier=payload.atr_breakout_multiplier,
            atr_stop_multiplier=payload.atr_stop_multiplier,
            adx_period=payload.adx_period,
            adx_threshold=payload.adx_threshold,
            multi_tf_timeframe=payload.multi_tf_timeframe,
            multi_tf_period=payload.multi_tf_period,
            trading_mode=payload.trading_mode,
            leverage=payload.leverage,
            margin_mode=payload.margin_mode,
            xgb_model_path=payload.xgb_model_path,
            xgb_buy_threshold=(
                Decimal(str(payload.xgb_buy_threshold))
                if payload.xgb_buy_threshold is not None
                else None
            ),
            xgb_sell_threshold=(
                Decimal(str(payload.xgb_sell_threshold))
                if payload.xgb_sell_threshold is not None
                else None
            ),
            oos_only=payload.oos_only,
            model_type=payload.model_type,
        ),
        source="api.control",
    )
    result_payload = asdict(result)
    result_payload["rules"] = (
        to_rule_builder_request(result.rules).model_dump(mode="python")
        if result.rules is not None
        else None
    )
    return BacktestControlResponse.model_validate(result_payload)


@router.post(
    "/market-sync",
    response_model=MarketSyncControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_market_sync(
    request: Annotated[MarketSyncControlRequest | None, Body()] = None,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> MarketSyncControlResponse:
    payload = request or MarketSyncControlRequest()
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_market_sync(
        options=MarketSyncRunOptions(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            limit=payload.limit,
            backfill=payload.backfill,
        ),
        source="api.control",
    )
    return MarketSyncControlResponse.model_validate(result)


@router.post(
    "/live-reconcile",
    response_model=LiveReconcileControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_reconcile(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveReconcileControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_reconcile(source="api.control")
    return LiveReconcileControlResponse.model_validate(result)


@router.post(
    "/live-halt",
    response_model=LiveHaltControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_halt(
    request: LiveHaltControlRequest,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveHaltControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_halt(
        halted=request.halted,
        source="api.control",
    )
    return LiveHaltControlResponse.model_validate(result)


@router.post(
    "/live-cancel",
    response_model=LiveCancelControlResponse,
    status_code=status.HTTP_200_OK,
)
def run_live_cancel(
    request: LiveCancelControlRequest,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> LiveCancelControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).run_live_cancel(
        order_id=request.order_id,
        client_order_id=request.client_order_id,
        exchange_order_id=request.exchange_order_id,
        source="api.control",
    )
    return LiveCancelControlResponse.model_validate(result)


@router.get(
    "/symbol-rules",
    response_model=SymbolRulesControlResponse,
    status_code=status.HTTP_200_OK,
)
def get_symbol_rules(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> SymbolRulesControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).get_symbol_rules()
    return SymbolRulesControlResponse.model_validate(result)


@router.post(
    "/symbol-rules/refresh",
    response_model=SymbolRulesControlResponse,
    status_code=status.HTTP_200_OK,
)
def refresh_symbol_rules(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> SymbolRulesControlResponse:
    result = OperationalControlService(
        settings,
        session_factory=session_factory,
    ).refresh_symbol_rules(source="api.control")
    return SymbolRulesControlResponse.model_validate(result)


@router.get(
    "/qualification",
    response_model=QualificationReportResponse,
    status_code=status.HTTP_200_OK,
)
def get_qualification(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> QualificationReportResponse:
    with session_factory() as session:
        report = QualificationService(session).evaluate(
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
        )
    return QualificationReportResponse(
        exchange=report.exchange,
        symbol=report.symbol,
        all_passed=report.all_passed,
        gates=[
            QualificationGateResponse(
                name=g.name,
                passed=g.passed,
                reason=g.reason,
                evidence=g.evidence,
            )
            for g in report.gates
        ],
    )


@router.post(
    "/train-model",
    response_model=TrainModelResponse,
    status_code=status.HTTP_200_OK,
)
def train_model(
    payload: TrainModelRequestSchema,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> TrainModelResponse:
    from app.application.services.model_training_service import (  # noqa: PLC0415
        ModelTrainingService,
    )
    from app.application.services.model_training_service import (
        TrainModelRequest as SvcRequest,
    )
    from app.infrastructure.database.repositories.market_data import (  # noqa: PLC0415
        MarketDataRepository,
    )

    with session_factory() as session:
        repo = MarketDataRepository(session)
        service = ModelTrainingService(market_data_repo=repo)
        result = service.train(
            SvcRequest(
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                exchange=payload.exchange,
                model_type=payload.model_type,
                label_type=payload.label_type,
                label_horizon=payload.label_horizon,
                label_threshold=payload.label_threshold,
                feature_names=payload.feature_names,
                candle_limit=payload.candle_limit,
                n_estimators=payload.n_estimators,
                max_depth=payload.max_depth,
                learning_rate=payload.learning_rate,
                split_ratio=payload.split_ratio,
                buy_threshold=payload.buy_threshold,
                sell_threshold=payload.sell_threshold,
            )
        )
    return TrainModelResponse(
        status=result.status,
        symbol=result.symbol,
        timeframe=result.timeframe,
        model_type=result.model_type,
        model_path=result.model_path,
        label_type=result.label_type,
        label_horizon=result.label_horizon,
        label_threshold=result.label_threshold,
        feature_names=result.feature_names,
        sample_count=result.sample_count,
        train_count=result.train_count,
        test_count=result.test_count,
        oos_start_index=result.oos_start_index,
        accuracy=result.accuracy,
        precision=result.precision,
        recall=result.recall,
        roc_auc=result.roc_auc,
        feature_importances=[
            FeatureImportanceSchema(feature=f.feature, importance=f.importance)
            for f in result.feature_importances
        ],
        detail=result.detail,
    )


@router.get(
    "/model-status",
    response_model=ModelStatusResponse,
    status_code=status.HTTP_200_OK,
)
def model_status() -> ModelStatusResponse:
    from pathlib import Path

    models_dir = Path("models")
    items: list[ModelStatusItem] = []
    if models_dir.exists():
        for path in sorted(models_dir.glob("xgboost_*.json")):
            # Filename pattern: xgboost_btcusdt_1h.json
            parts = path.stem.split("_")  # ["xgboost", "btcusdt", "1h"]
            timeframe = parts[-1] if len(parts) >= 3 else "unknown"
            raw_symbol = (
                "_".join(parts[1:-1])
                if len(parts) >= 3
                else (parts[1] if len(parts) >= 2 else "unknown")
            )
            size_kb = round(path.stat().st_size / 1024, 1)
            items.append(
                ModelStatusItem(
                    symbol=raw_symbol.upper(),
                    timeframe=timeframe,
                    model_path=str(path),
                    exists=True,
                    file_size_kb=size_kb,
                )
            )
    return ModelStatusResponse(models=items)
