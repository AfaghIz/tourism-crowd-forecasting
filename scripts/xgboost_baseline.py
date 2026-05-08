from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


RANDOM_STATE = 42
TEST_SIZE = 0.2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "xgboost_baseline"
METRICS_PATH = OUTPUT_DIR / "metrics.csv"
FEATURE_IMPORTANCE_PATH = OUTPUT_DIR / "feature_importance.csv"
PREDICTIONS_PATH = OUTPUT_DIR / "predictions.csv"


def load_and_prepare_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["date"])
    data = data.sort_values("date").reset_index(drop=True)
    return data


def build_features_target(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = data.drop(columns=["date", "crowd_index", "crowd_level"], errors="ignore").copy()
    y = data["crowd_index"].copy()
    return X, y


def chronological_split(
    X: pd.DataFrame, y: pd.Series, test_size: float
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    split_idx = int(len(X) * (1 - test_size))
    X_train = X.iloc[:split_idx].copy()
    X_test = X.iloc[split_idx:].copy()
    y_train = y.iloc[:split_idx].copy()
    y_test = y.iloc[split_idx:].copy()
    return X_train, X_test, y_train, y_test


def evaluate_predictions(y_true: pd.Series, y_pred: np.ndarray) -> tuple[float, float, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return rmse, mae, r2


def build_feature_importance_table(model: XGBRegressor, feature_names: list[str]) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "model": "XGBoost",
                "feature": feature_names,
                "importance": model.feature_importances_,
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_and_prepare_data(INPUT_PATH)
    X, y = build_features_target(data)
    X_train, X_test, y_train, y_test = chronological_split(X, y, TEST_SIZE)

    model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    full_pred = model.predict(X)

    rmse_train, mae_train, r2_train = evaluate_predictions(y_train, train_pred)
    rmse_test, mae_test, r2_test = evaluate_predictions(y_test, test_pred)

    metrics_df = pd.DataFrame(
        [
            {
                "model": "XGBoost",
                "rmse_train": rmse_train,
                "rmse_test": rmse_test,
                "mae_train": mae_train,
                "mae_test": mae_test,
                "r2_train": r2_train,
                "r2_test": r2_test,
                "split": "chronological",
                "test_size": TEST_SIZE,
                "random_state": RANDOM_STATE,
                "n_estimators": 300,
                "learning_rate": 0.05,
                "max_depth": 6,
            }
        ]
    )

    feature_importance_df = build_feature_importance_table(model, X.columns.tolist())
    predictions_df = pd.DataFrame(
        {
            "date": pd.to_datetime(data["date"]),
            "actual_crowd_index": y,
            "predicted_crowd_index_xgb": full_pred,
            "split": ["train"] * len(X_train) + ["test"] * len(X_test),
        }
    )

    metrics_df.to_csv(METRICS_PATH, index=False)
    feature_importance_df.to_csv(FEATURE_IMPORTANCE_PATH, index=False)
    predictions_df.to_csv(PREDICTIONS_PATH, index=False)

    print(f"Loaded dataset: {INPUT_PATH}")
    print(f"Rows: {len(data)}, Features used: {X.shape[1]}")
    print(f"Train size: {X_train.shape}, Test size: {X_test.shape}")
    print("\n=== Performance Metrics ===")
    print(metrics_df.to_string(index=False))
    print("\n=== Top 15 Feature Importance ===")
    print(feature_importance_df.head(15).to_string(index=False))
    print(f"\nSaved metrics to: {METRICS_PATH}")
    print(f"Saved feature importance to: {FEATURE_IMPORTANCE_PATH}")
    print(f"Saved predictions to: {PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
