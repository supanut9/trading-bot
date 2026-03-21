#!/usr/bin/env python3
"""Train an XGBoost signal model on stored candle data.

Usage:
    python scripts/train_xgboost.py
    python scripts/train_xgboost.py --symbol ETH/USDT --timeframe 4h
    python scripts/train_xgboost.py --symbol BTC/USDT --timeframe 1h --n-estimators 200

The trained model is saved to models/xgboost_<symbol>_<timeframe>.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path when run directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib
from decimal import Decimal

from app.config import get_settings
from app.domain.strategies.base import Candle
from app.domain.strategies.features import FEATURE_NAMES, build_feature_matrix
from app.infrastructure.database.repositories.market_data import MarketDataRepository
from app.infrastructure.database.session import create_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost signal model")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument(
        "--split-ratio", type=float, default=0.7, help="Train/test split (default 0.7)"
    )
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument(
        "--output",
        default=None,
        help="Output model path (default: models/xgboost_<symbol>_<timeframe>.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        xgb = importlib.import_module("xgboost")
        sklearn_metrics = importlib.import_module("sklearn.metrics")
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Run: pip install xgboost scikit-learn")
        sys.exit(1)

    settings = get_settings()
    factory = create_session_factory(settings)

    print(f"Loading candles: {args.symbol} {args.timeframe} ({args.exchange})")

    with factory() as session:
        repo = MarketDataRepository(session)
        records = repo.list_candles(
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            limit=10000,
        )

    if not records:
        print("No candles found. Run a backtest first to auto-sync candles.")
        sys.exit(1)

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

    print(f"Loaded {len(candles)} candles")

    print("Engineering features...")
    X, y = build_feature_matrix(candles)

    if len(X) < 100:
        print(f"Only {len(X)} labeled samples — need at least 100. Sync more candles.")
        sys.exit(1)

    print(f"Feature matrix: {len(X)} samples x {len(X[0])} features")
    print(
        f"Label distribution: {sum(y)} up / {len(y) - sum(y)} down"
        f" ({100 * sum(y) / len(y):.1f}% up)"
    )

    # Walk-forward split
    split_idx = int(len(X) * args.split_ratio)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    print(f"Train: {len(X_train)} | Test (OOS): {len(X_test)}")

    # Train
    print(
        f"\nTraining XGBoost"
        f" (n_estimators={args.n_estimators},"
        f" max_depth={args.max_depth},"
        f" lr={args.learning_rate})..."
    )
    model = xgb.XGBClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    # Evaluate OOS
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    accuracy = sklearn_metrics.accuracy_score(y_test, y_pred)
    precision = sklearn_metrics.precision_score(y_test, y_pred, zero_division=0)
    recall = sklearn_metrics.recall_score(y_test, y_pred, zero_division=0)
    auc = sklearn_metrics.roc_auc_score(y_test, y_proba)

    print("\n-- OOS Evaluation --")
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  ROC-AUC:   {auc:.4f}")

    # Feature importances
    importances = model.feature_importances_
    print("\n-- Feature Importances --")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1]):
        print(f"  {name:<20} {imp:.4f}")

    # Save model
    safe_symbol = args.symbol.replace("/", "").lower()
    output_path = args.output or f"models/xgboost_{safe_symbol}_{args.timeframe}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    model.save_model(output_path)
    print(f"\nModel saved -> {output_path}")
    print(
        "Run a backtest with strategy_name='xgboost_signal'"
        " to evaluate trading performance."
    )


if __name__ == "__main__":
    main()
