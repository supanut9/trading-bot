"""Model registry — loads and caches trained ML model files.

This is an application-layer service.  Strategy domain modules must not import
from here; they receive pre-loaded model objects through constructors.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level cache: path → loaded model object
_model_cache: dict[str, Any] = {}


def load_xgboost_model(model_path: str) -> Any:
    """Load an XGBoost model from *model_path* and return the sklearn estimator.

    The model must have been saved with ``model.save_model(path)`` (XGBoost
    native JSON format).  Results are cached so repeated calls with the same
    path pay no IO cost.

    Raises FileNotFoundError if the model file does not exist.
    Raises ImportError if xgboost is not installed.
    """
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
    model.load_model(str(path))
    _model_cache[model_path] = model
    logger.info("loaded xgboost model from %s", model_path)
    return model


def clear_cache() -> None:
    """Clear the in-memory model cache (useful in tests)."""
    _model_cache.clear()


def default_model_path(symbol: str = "BTC/USDT", timeframe: str = "1h") -> str:
    """Return the conventional model file path for a given symbol and timeframe."""
    safe_symbol = symbol.replace("/", "").lower()
    return f"models/xgboost_{safe_symbol}_{timeframe}.json"
