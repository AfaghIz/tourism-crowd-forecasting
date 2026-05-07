from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


RANDOM_STATE = 42
TEST_SIZE = 0.2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "linear_baseline"
METRICS_PATH = OUTPUT_DIR / "metrics.csv"
COEFFICIENTS_PATH = OUTPUT_DIR / "coefficients.csv"


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

    data["month"] = data["date"].dt.month
    data["day_of_week"] = data["date"].dt.dayofweek
    data["season"] = data["month"].map(month_to_season)

    return data


def build_features_targets(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    target_col = "crowd_index"
    drop_columns = ["date", "crowd_index", "crowd_level"]
    X = data.drop(columns=drop_columns, errors="ignore")
    y = data[target_col]
    return X, y


def chronological_split(X: pd.DataFrame, y: pd.Series, test_size: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    split_idx = int(len(X) * (1 - test_size))
    X_train = X.iloc[:split_idx].copy()
    X_test = X.iloc[split_idx:].copy()
    y_train = y.iloc[:split_idx].copy()
    y_test = y.iloc[split_idx:].copy()
    return X_train, X_test, y_train, y_test


def create_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    categorical_cols = X.select_dtypes(include=["object", "category", "bool", "string"]).columns.tolist()
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
            ("cat", categorical_pipeline, categorical_cols),
        ]
    )


def evaluate_model(name: str, model: Pipeline, X_train: pd.DataFrame, X_test: pd.DataFrame, y_train: pd.Series, y_test: pd.Series) -> tuple[dict, pd.DataFrame]:
    model.fit(X_train, y_train)

    pred_train = model.predict(X_train)
    pred_test = model.predict(X_test)

    rmse_train = float(np.sqrt(mean_squared_error(y_train, pred_train)))
    rmse_test = float(np.sqrt(mean_squared_error(y_test, pred_test)))
    mae_train = float(mean_absolute_error(y_train, pred_train))
    mae_test = float(mean_absolute_error(y_test, pred_test))

    preprocessor = model.named_steps["preprocessor"]
    regressor = model.named_steps["regressor"]
    feature_names = preprocessor.get_feature_names_out()
    coefficients = regressor.coef_

    coefficient_df = pd.DataFrame(
        {
            "model": name,
            "feature": feature_names,
            "coefficient": coefficients,
            "abs_coefficient": np.abs(coefficients),
        }
    ).sort_values("abs_coefficient", ascending=False)

    intercept_row = pd.DataFrame(
        {
            "model": [name],
            "feature": ["(intercept)"],
            "coefficient": [float(regressor.intercept_)],
            "abs_coefficient": [abs(float(regressor.intercept_))],
        }
    )

    coefficient_df = pd.concat([intercept_row, coefficient_df], ignore_index=True)

    metrics = {
        "model": name,
        "rmse_train": rmse_train,
        "rmse_test": rmse_test,
        "mae_train": mae_train,
        "mae_test": mae_test,
        "split": "chronological",
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
    }

    return metrics, coefficient_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_and_prepare_data(INPUT_PATH)
    X, y = build_features_targets(data)
    X_train, X_test, y_train, y_test = chronological_split(X, y, TEST_SIZE)

    print(f"Loaded dataset: {INPUT_PATH}")
    print(f"Rows: {len(data)}, Features: {X.shape[1]}")
    print(f"Train size: {X_train.shape}, Test size: {X_test.shape}")

    preprocessor = create_preprocessor(X_train)

    models = {
        "Ordinary Least Squares": LinearRegression(),
        "Ridge (alpha=1.0)": Ridge(alpha=1.0),
        "Lasso (alpha=0.0001)": Lasso(alpha=0.0001, random_state=RANDOM_STATE, max_iter=10000),
    }

    all_metrics: list[dict] = []
    all_coefficients: list[pd.DataFrame] = []

    for model_name, regressor in models.items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("regressor", regressor),
            ]
        )
        metrics, coefficients = evaluate_model(model_name, pipeline, X_train, X_test, y_train, y_test)
        all_metrics.append(metrics)
        all_coefficients.append(coefficients)

    metrics_df = pd.DataFrame(all_metrics)
    coefficients_df = pd.concat(all_coefficients, ignore_index=True)

    metrics_df.to_csv(METRICS_PATH, index=False)
    coefficients_df.to_csv(COEFFICIENTS_PATH, index=False)

    print("\n=== Performance Metrics ===")
    print(metrics_df.to_string(index=False))

    print("\n=== Top 10 Most Important Features by |Coefficient| (per model) ===")
    for model_name in metrics_df["model"]:
        top_features = (
            coefficients_df[
                (coefficients_df["model"] == model_name)
                & (coefficients_df["feature"] != "(intercept)")
            ]
            .sort_values("abs_coefficient", ascending=False)
            .head(10)
        )
        print(f"\n[{model_name}]")
        print(top_features[["feature", "coefficient", "abs_coefficient"]].to_string(index=False))

    print(f"\nSaved metrics to: {METRICS_PATH}")
    print(f"Saved coefficients to: {COEFFICIENTS_PATH}")


if __name__ == "__main__":
    main()
