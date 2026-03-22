"""Model registry — loads and caches trained ML model files with metadata.

This is an application-layer service. Strategy domain modules must not import
from here; they receive pre-loaded model objects through constructors.
"""

from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_model_cache: dict[str, Any] = {}


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    model_type: str
    symbol: str
    timeframe: str
    feature_names: list[str]
    label_type: str
    label_horizon: int
    label_threshold: float
    buy_threshold: float
    sell_threshold: float
    sample_count: int
    train_count: int
    test_count: int
    accuracy: float | None
    roc_auc: float | None
    oos_start_index: int  # candle index where OOS window begins


@dataclass(frozen=True, slots=True)
class LoadedModel:
    model: Any
    metadata: ModelMetadata


def load_model(model_path: str) -> LoadedModel:
    """Load a model and its sidecar metadata. Results are cached."""
    if model_path in _model_cache:
        return _model_cache[model_path]

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        raise FileNotFoundError(f"Model metadata not found: {meta_path}")

    with meta_path.open() as f:
        meta_dict = json.load(f)

    from app.domain.strategies.features import DEFAULT_FEATURE_NAMES

    metadata = ModelMetadata(
        model_type=meta_dict.get("model_type", "xgboost"),
        symbol=meta_dict.get("symbol", "BTC/USDT"),
        timeframe=meta_dict.get("timeframe", "1h"),
        feature_names=meta_dict.get("feature_names", list(DEFAULT_FEATURE_NAMES)),
        label_type=meta_dict.get("label_type", "next_candle"),
        label_horizon=meta_dict.get("label_horizon", 1),
        label_threshold=meta_dict.get("label_threshold", 0.0),
        buy_threshold=meta_dict.get("buy_threshold", 0.60),
        sell_threshold=meta_dict.get("sell_threshold", 0.40),
        sample_count=meta_dict.get("sample_count", 0),
        train_count=meta_dict.get("train_count", 0),
        test_count=meta_dict.get("test_count", 0),
        accuracy=meta_dict.get("accuracy"),
        roc_auc=meta_dict.get("roc_auc"),
        oos_start_index=meta_dict.get("oos_start_index", 0),
    )

    model_type = metadata.model_type
    model: Any

    if model_type == "random_forest":
        try:
            joblib = importlib.import_module("joblib")
        except ImportError as exc:
            raise ImportError("joblib not installed") from exc
        model = joblib.load(str(path))
    elif model_type == "lightgbm":
        try:
            lgb = importlib.import_module("lightgbm")
        except ImportError as exc:
            raise ImportError("lightgbm not installed — run: pip install lightgbm") from exc
        booster = lgb.Booster(model_file=str(path))
        model = _LightGBMAdapter(booster)
    else:  # xgboost
        try:
            xgb = importlib.import_module("xgboost")
        except ImportError as exc:
            raise ImportError("xgboost not installed") from exc
        m = xgb.XGBClassifier()
        m._estimator_type = "classifier"
        m.load_model(str(path))
        model = m

    loaded = LoadedModel(model=model, metadata=metadata)
    _model_cache[model_path] = loaded
    logger.info("loaded %s model from %s", model_type, model_path)
    return loaded


class _LightGBMAdapter:
    """Wraps a LightGBM Booster to expose sklearn-style predict_proba."""

    def __init__(self, booster: Any) -> None:
        self._booster = booster

    def predict_proba(self, X: list[list[float]]) -> list[list[float]]:
        import numpy as np

        preds = self._booster.predict(np.array(X))
        # Binary classification: preds is probability of class 1
        return [[1 - float(p), float(p)] for p in preds]


def load_xgboost_model(model_path: str) -> Any:
    """Backward-compat shim: load an XGBoost model (no sidecar required for legacy paths).

    If a sidecar .meta.json exists, delegates to load_model().
    Otherwise falls back to the original bare-file loading approach.
    """
    meta_path = Path(model_path).with_suffix(".meta.json")
    if meta_path.exists():
        return load_model(model_path).model

    # Legacy path: no sidecar, XGBoost only
    if model_path in _model_cache:
        return _model_cache[model_path]

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"XGBoost model not found: {model_path}")

    try:
        xgb = importlib.import_module("xgboost")
    except ImportError as exc:
        raise ImportError("xgboost is not installed — run: pip install xgboost") from exc

    model = xgb.XGBClassifier()
    model._estimator_type = "classifier"
    model.load_model(str(path))
    _model_cache[model_path] = model
    logger.info("loaded xgboost model (legacy) from %s", model_path)
    return model


def clear_cache() -> None:
    """Clear the in-memory model cache (useful in tests)."""
    _model_cache.clear()


def default_model_path(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    model_type: str = "xgboost",
) -> str:
    """Return the conventional model file path for a given symbol, timeframe, and model type."""
    safe_symbol = symbol.replace("/", "").lower()
    ext = "pkl" if model_type == "random_forest" else "json"
    return f"models/{model_type}_{safe_symbol}_{timeframe}.{ext}"
