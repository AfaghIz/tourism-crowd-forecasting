from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


RANDOM_STATE = 42
TEST_SIZE = 0.2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "lightgbm_baseline"
METRICS_PATH = OUTPUT_DIR / "metrics.csv"
IMPORTANCE_PATH = OUTPUT_DIR / "feature_importance.csv"

NUMERIC_FEATURES = [
    "trend_demand",
    "temp_max",
    "temp_min",
    "temp_avg",
    "precipitation",
    "month",
    "day_of_week",
]
CATEGORICAL_FEATURES = [
    "season",
    "is_holiday",
]


def month_to_season(month: int) -> str:
    if month in {12, 1, 2}:
        return "winter"
    if month in {3, 4, 5}:
        return "spring"
    if month in {6, 7, 8}:
        return "summer"
    return "autumn"


def load_and_prepare_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["date"])
    data = data.sort_values("date").reset_index(drop=True)

    data["month"] = data["date"].dt.month
    data["day_of_week"] = data["date"].dt.dayofweek
    data["season"] = data["month"].map(month_to_season)

    return data


def build_features_target(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = data.drop(columns=["date", "crowd_index", "crowd_level"], errors="ignore").copy()
    y = data["crowd_index"].copy()

    X = X[NUMERIC_FEATURES + CATEGORICAL_FEATURES]

    for col in NUMERIC_FEATURES:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        X[col] = X[col].fillna(X[col].median())

    X["season"] = X["season"].fillna("missing").astype("category")
    X["is_holiday"] = X["is_holiday"].fillna(-1).astype("int64").astype("category")

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


def evaluate_predictions(y_true: pd.Series, y_pred: np.ndarray) -> tuple[float, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    return rmse, mae


def build_importance_table(model: LGBMRegressor, feature_names: list[str]) -> pd.DataFrame:
    split_importance = model.booster_.feature_importance(importance_type="split")
    gain_importance = model.booster_.feature_importance(importance_type="gain")

    importance_df = pd.DataFrame(
        {
            "model": "LightGBM Regressor",
            "feature": feature_names,
            "split_importance": split_importance,
            "gain_importance": gain_importance,
        }
    )
    importance_df["gain_importance_normalized"] = (
        importance_df["gain_importance"] / importance_df["gain_importance"].sum()
    )
    return importance_df.sort_values("gain_importance", ascending=False).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_and_prepare_data(INPUT_PATH)
    X, y = build_features_target(data)
    X_train, X_test, y_train, y_test = chronological_split(X, y, TEST_SIZE)

    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=-1,
        random_state=RANDOM_STATE,
    )

    model.fit(X_train, y_train, categorical_feature=CATEGORICAL_FEATURES)

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    rmse_train, mae_train = evaluate_predictions(y_train, train_pred)
    rmse_test, mae_test = evaluate_predictions(y_test, test_pred)

    metrics_df = pd.DataFrame(
        [
            {
                "model": "LightGBM Regressor",
                "rmse_train": rmse_train,
                "rmse_test": rmse_test,
                "mae_train": mae_train,
                "mae_test": mae_test,
                "split": "chronological",
                "test_size": TEST_SIZE,
                "random_state": RANDOM_STATE,
            }
        ]
    )

    importance_df = build_importance_table(model, X.columns.tolist())

    metrics_df.to_csv(METRICS_PATH, index=False)
    importance_df.to_csv(IMPORTANCE_PATH, index=False)

    print(f"Loaded dataset: {INPUT_PATH}")
    print(f"Rows: {len(data)}, Features used: {X.shape[1]}")
    print(f"Train size: {X_train.shape}, Test size: {X_test.shape}")

    print("\n=== Performance Metrics ===")
    print(metrics_df.to_string(index=False))

    print("\n=== Top 15 Feature Importance (gain) ===")
    print(
        importance_df[["feature", "gain_importance", "split_importance", "gain_importance_normalized"]]
        .head(15)
        .to_string(index=False)
    )

    print("\n=== Interpretation Notes ===")
    print("- Compare these metrics to your Linear/Ridge/Lasso baseline CSVs for direct benchmarking.")
    print("- With near-linear target structure, LightGBM may match or only slightly improve linear baselines.")
    print("- Tree ensembles are usually more robust to redundant predictors than plain OLS.")

    print(f"\nSaved metrics to: {METRICS_PATH}")
    print(f"Saved feature importance to: {IMPORTANCE_PATH}")


if __name__ == "__main__":
    main()
