"""Model training service — supports XGBoost, LightGBM, and Random Forest."""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.strategies.base import Candle
from app.domain.strategies.features import (
    ALL_FEATURE_NAMES,
    DEFAULT_FEATURE_NAMES,
    build_feature_matrix,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrainModelRequest:
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    exchange: str = "binance"
    model_type: str = "xgboost"  # "xgboost" | "lightgbm" | "random_forest"
    label_type: str = "forward_return"  # "next_candle" | "forward_return"
    label_horizon: int = 5  # how many candles forward
    label_threshold: float = 0.003  # min % move to count as signal (0.3%)
    feature_names: list[str] | None = None  # None = DEFAULT_FEATURE_NAMES
    candle_limit: int = 10000  # max candles to fetch for training
    n_estimators: int = 200
    max_depth: int = 4
    learning_rate: float = 0.1
    split_ratio: float = 0.7
    buy_threshold: float = 0.60
    sell_threshold: float = 0.40


@dataclass(frozen=True, slots=True)
class FeatureImportance:
    feature: str
    importance: float


@dataclass(frozen=True, slots=True)
class TrainModelResult:
    status: str  # "completed" | "error" | "insufficient_data"
    symbol: str
    timeframe: str
    model_type: str
    model_path: str
    label_type: str
    label_horizon: int
    label_threshold: float
    feature_names: list[str]
    sample_count: int
    train_count: int
    test_count: int
    oos_start_index: int
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
        """Train a model on stored candles and save it to disk with sidecar metadata."""
        feature_names = (
            list(request.feature_names) if request.feature_names else list(DEFAULT_FEATURE_NAMES)
        )

        # Validate feature names
        invalid = [f for f in feature_names if f not in ALL_FEATURE_NAMES]
        if invalid:
            return TrainModelResult(
                status="error",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_type=request.model_type,
                model_path="",
                label_type=request.label_type,
                label_horizon=request.label_horizon,
                label_threshold=request.label_threshold,
                feature_names=feature_names,
                sample_count=0,
                train_count=0,
                test_count=0,
                oos_start_index=0,
                detail=f"invalid features: {invalid}",
            )

        safe_symbol = request.symbol.replace("/", "").lower()
        ext = "pkl" if request.model_type == "random_forest" else "json"
        model_path = f"models/{request.model_type}_{safe_symbol}_{request.timeframe}.{ext}"
        meta_path = model_path.replace(f".{ext}", ".meta.json")

        records = self._market_data.list_candles(
            exchange=request.exchange,
            symbol=request.symbol,
            timeframe=request.timeframe,
            limit=request.candle_limit,
        )

        if not records:
            return TrainModelResult(
                status="insufficient_data",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_type=request.model_type,
                model_path=model_path,
                label_type=request.label_type,
                label_horizon=request.label_horizon,
                label_threshold=request.label_threshold,
                feature_names=feature_names,
                sample_count=0,
                train_count=0,
                test_count=0,
                oos_start_index=0,
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

        X, y = build_feature_matrix(
            candles,
            feature_names=feature_names,
            label_type=request.label_type,
            label_horizon=request.label_horizon,
            label_threshold=request.label_threshold,
        )

        if len(X) < 100:
            return TrainModelResult(
                status="insufficient_data",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_type=request.model_type,
                model_path=model_path,
                label_type=request.label_type,
                label_horizon=request.label_horizon,
                label_threshold=request.label_threshold,
                feature_names=feature_names,
                sample_count=len(X),
                train_count=0,
                test_count=0,
                oos_start_index=0,
                detail=f"only {len(X)} labeled samples — need ≥100",
            )

        split_idx = int(len(X) * request.split_ratio)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        try:
            model, importances = self._fit_model(request, feature_names, X_train, y_train)
            sklearn_metrics = importlib.import_module("sklearn.metrics")
            y_pred = model.predict(X_test)
            y_proba_raw = model.predict_proba(X_test)
            y_proba = [p[1] for p in y_proba_raw]

            accuracy = float(sklearn_metrics.accuracy_score(y_test, y_pred))
            precision = float(sklearn_metrics.precision_score(y_test, y_pred, zero_division=0))
            recall = float(sklearn_metrics.recall_score(y_test, y_pred, zero_division=0))
            roc_auc = float(sklearn_metrics.roc_auc_score(y_test, y_proba))

            importance_objs = tuple(
                FeatureImportance(feature=n, importance=float(v))
                for n, v in sorted(
                    zip(feature_names, importances, strict=False),
                    key=lambda x: -x[1],
                )
            )

            # Save model
            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            self._save_model(model, request.model_type, model_path)

            # Save sidecar metadata
            meta: dict[str, Any] = {
                "model_type": request.model_type,
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "feature_names": feature_names,
                "label_type": request.label_type,
                "label_horizon": request.label_horizon,
                "label_threshold": request.label_threshold,
                "buy_threshold": request.buy_threshold,
                "sell_threshold": request.sell_threshold,
                "sample_count": len(X),
                "train_count": len(X_train),
                "test_count": len(X_test),
                "accuracy": accuracy,
                "roc_auc": roc_auc,
                "oos_start_index": split_idx,
            }
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            from app.application.services.model_registry import clear_cache

            clear_cache()

            logger.info(
                "trained %s model: symbol=%s timeframe=%s samples=%d auc=%.4f path=%s",
                request.model_type,
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
                model_type=request.model_type,
                model_path=model_path,
                label_type=request.label_type,
                label_horizon=request.label_horizon,
                label_threshold=request.label_threshold,
                feature_names=feature_names,
                sample_count=len(X),
                train_count=len(X_train),
                test_count=len(X_test),
                oos_start_index=split_idx,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                roc_auc=roc_auc,
                feature_importances=importance_objs,
            )

        except Exception as exc:
            logger.exception("model training failed: %s", exc)
            return TrainModelResult(
                status="error",
                symbol=request.symbol,
                timeframe=request.timeframe,
                model_type=request.model_type,
                model_path=model_path,
                label_type=request.label_type,
                label_horizon=request.label_horizon,
                label_threshold=request.label_threshold,
                feature_names=feature_names,
                sample_count=len(X),
                train_count=0,
                test_count=0,
                oos_start_index=0,
                detail=str(exc),
            )

    def _fit_model(
        self,
        request: TrainModelRequest,
        feature_names: list[str],
        X_train: list[list[float]],
        y_train: list[int],
    ) -> tuple[Any, list[float]]:
        mt = request.model_type

        if mt == "lightgbm":
            lgb = importlib.import_module("lightgbm")
            # Use sklearn API for consistent predict_proba
            model = lgb.LGBMClassifier(
                n_estimators=request.n_estimators,
                max_depth=request.max_depth,
                learning_rate=request.learning_rate,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            model.fit(X_train, y_train)
            importances = list(model.feature_importances_)
            return model, importances

        if mt == "random_forest":
            sklearn_ensemble = importlib.import_module("sklearn.ensemble")
            model = sklearn_ensemble.RandomForestClassifier(
                n_estimators=request.n_estimators,
                max_depth=request.max_depth if request.max_depth > 0 else None,
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X_train, y_train)
            importances = list(model.feature_importances_)
            return model, importances

        # xgboost (default)
        xgb = importlib.import_module("xgboost")
        model = xgb.XGBClassifier(
            n_estimators=request.n_estimators,
            max_depth=request.max_depth,
            learning_rate=request.learning_rate,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        importances = list(model.feature_importances_)
        return model, importances

    @staticmethod
    def _save_model(model: Any, model_type: str, model_path: str) -> None:
        if model_type == "random_forest":
            joblib = importlib.import_module("joblib")
            joblib.dump(model, model_path)
        elif model_type == "lightgbm":
            model.booster_.save_model(model_path)
        else:  # xgboost
            model._estimator_type = "classifier"
            model.save_model(model_path)
