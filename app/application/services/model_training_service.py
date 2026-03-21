"""Model training service — trains XGBoost models from stored candle data."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.strategies.base import Candle
from app.domain.strategies.features import FEATURE_NAMES, build_feature_matrix

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrainModelRequest:
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    exchange: str = "binance"
    n_estimators: int = 200
    max_depth: int = 4
    learning_rate: float = 0.1
    split_ratio: float = 0.7


@dataclass(frozen=True, slots=True)
class FeatureImportance:
    feature: str
    importance: float


@dataclass(frozen=True, slots=True)
class TrainModelResult:
    status: str  # "completed" | "error" | "insufficient_data"
    symbol: str
    timeframe: str
    model_path: str
    sample_count: int
    train_count: int
    test_count: int
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    roc_auc: float | None = None
    feature_importances: tuple[FeatureImportance, ...] = ()
    detail: str = ""


class ModelTrainingService:
    def __init__(self, market_data_repo: Any) -> None:
        self._market_data = market_data_repo

    def train(self, request: TrainModelRequest) -> TrainModelResult:
        """Train an XGBoost model on stored candles and save it to disk."""
        try:
            xgb = importlib.import_module("xgboost")
            sklearn_metrics = importlib.import_module("sklearn.metrics")
        except ImportError:
            return TrainModelResult(
                status="error",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_path="",
                sample_count=0,
                train_count=0,
                test_count=0,
                detail="xgboost or scikit-learn not installed",
            )

        records = self._market_data.list_candles(
            exchange=request.exchange,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=10000,
        )

        if not records:
            return TrainModelResult(
                status="insufficient_data",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_path="",
                sample_count=0,
                train_count=0,
                test_count=0,
                detail="no candles found — run a backtest first to sync candle data",
            )

        candles = [
            Candle(
                open_time=r.open_time,
                close_time=r.close_time,
                open_price=Decimal(str(r.open_price)),
                high_price=Decimal(str(r.high_price)),
                low_price=Decimal(str(r.low_price)),
                close_price=Decimal(str(r.close_price)),
                volume=Decimal(str(r.volume)),
            )
            for r in records
        ]

        X, y = build_feature_matrix(candles)

        safe_symbol = request.symbol.replace("/", "").lower()
        model_path = f"models/xgboost_{safe_symbol}_{request.timeframe}.json"

        if len(X) < 100:
            return TrainModelResult(
                status="insufficient_data",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_path=model_path,
                sample_count=len(X),
                train_count=0,
                test_count=0,
                detail=(
                    f"only {len(X)} labeled samples — need at least 100; sync more candle history"
                ),
            )

        split_idx = int(len(X) * request.split_ratio)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        try:
            model = xgb.XGBClassifier(
                n_estimators=request.n_estimators,
                max_depth=request.max_depth,
                learning_rate=request.learning_rate,
                eval_metric="logloss",
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1]

            accuracy = float(sklearn_metrics.accuracy_score(y_test, y_pred))
            precision = float(sklearn_metrics.precision_score(y_test, y_pred, zero_division=0))
            recall = float(sklearn_metrics.recall_score(y_test, y_pred, zero_division=0))
            roc_auc = float(sklearn_metrics.roc_auc_score(y_test, y_proba))

            importances = tuple(
                FeatureImportance(feature=name, importance=float(imp))
                for name, imp in sorted(
                    zip(FEATURE_NAMES, model.feature_importances_, strict=False),
                    key=lambda x: -x[1],
                )
            )

            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            model._estimator_type = "classifier"  # required by xgboost>=2 sklearn wrapper
            model.save_model(model_path)

            # Invalidate registry cache so next inference uses the new model.
            from app.application.services.model_registry import clear_cache

            clear_cache()

            logger.info(
                "trained xgboost model: symbol=%s timeframe=%s samples=%d auc=%.4f path=%s",
                request.symbol,
                request.timeframe,
                len(X),
                roc_auc,
                model_path,
            )

            return TrainModelResult(
                status="completed",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_path=model_path,
                sample_count=len(X),
                train_count=len(X_train),
                test_count=len(X_test),
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                roc_auc=roc_auc,
                feature_importances=importances,
            )

        except Exception as exc:
            logger.exception("model training failed: %s", exc)
            return TrainModelResult(
                status="error",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_path=model_path,
                sample_count=len(X),
                train_count=0,
                test_count=0,
                detail=str(exc),
            )
