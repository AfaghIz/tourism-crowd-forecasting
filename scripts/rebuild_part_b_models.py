#!/usr/bin/env python3
"""Rebuild Part B Random Forest and XGBoost outputs.

This script trains the proxy-imputation models from the current modeling table,
writes refreshed score outputs, and saves evaluation artifacts so notebooks can
inspect the latest run without hard-coded metrics.
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"

BASE_INPUT_PATH = DATA_DIR / "otm_pois_model_ready_with_nlp_features_exclusions.csv"
MODEL_TABLE_PATH = DATA_DIR / "otm_part_b_modeling_table.csv"

RF_OUTPUT_PATH = DATA_DIR / "otm_part_b_rf_scores.csv"
XGB_OUTPUT_PATH = DATA_DIR / "otm_part_b_xgb_scores.csv"

RF_METRICS_PATH = DATA_DIR / "otm_part_b_rf_metrics.json"
XGB_METRICS_PATH = DATA_DIR / "otm_part_b_xgb_metrics.json"

RF_IMPORTANCES_PATH = DATA_DIR / "otm_part_b_rf_feature_importances.csv"
XGB_IMPORTANCES_PATH = DATA_DIR / "otm_part_b_xgb_feature_importances.csv"

RANDOM_STATE = 42


CATEGORICAL_FEATURES = [
    "category_clean",
    "query_area",
]

NUMERIC_FEATURES = [
    "lat",
    "lon",
    "rate",
    "dist_from_query_center_m",
    "candidate_count_same_key",
    "has_valid_wiki_identity_but_missing_pageviews",
    "is_mosque",
    "is_church",
    "is_synagogue",
    "is_cathedral",
    "is_palace",
    "is_museum",
    "is_monument",
    "is_cemetery",
    "is_fortress",
    "is_tower",
    "is_hamam",
    "is_bridge",
    "is_tekke_or_dergah",
    "is_tomb",
    "is_fountain",
    "is_gate",
    "subtype_flag_count",
    "has_possible_duplicate",
    "possible_duplicate_count",
    "family_iconic_landmark",
    "family_religious_monumental",
    "family_museum_cultural",
    "family_viewpoint_scenic",
    "family_palatial_imperial",
    "family_neighborhood_heritage",
]


def prepare_model_table() -> pd.DataFrame:
    df = pd.read_csv(MODEL_TABLE_PATH).copy()

    # The modeling table currently carries duplicate columns from earlier merges.
    df["category_clean"] = df["category_clean"].fillna(df.get("category_clean.1"))
    df["query_area"] = df["query_area"].fillna(df.get("query_area.1"))
    if "has_valid_wiki_identity_but_missing_pageviews.1" in df.columns:
        df["has_valid_wiki_identity_but_missing_pageviews"] = df[
            "has_valid_wiki_identity_but_missing_pageviews"
        ].fillna(df["has_valid_wiki_identity_but_missing_pageviews.1"])

    required = CATEGORICAL_FEATURES + NUMERIC_FEATURES + ["target_proxy", "has_direct_wiki_signal"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Model table missing required columns: {missing}")

    return df


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("num", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value=0.0))]), NUMERIC_FEATURES),
        ]
    )


def build_rf_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=400,
                    min_samples_leaf=2,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def build_xgb_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            (
                "model",
                XGBRegressor(
                    n_estimators=300,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    reg_lambda=1.0,
                    objective="reg:squarederror",
                    random_state=RANDOM_STATE,
                    n_jobs=4,
                ),
            ),
        ]
    )


def fit_and_score(
    model_df: pd.DataFrame,
    pipeline: Pipeline,
    *,
    pred_col: str,
    final_col: str,
    a_col: str,
    score_source_col: str,
    model_name: str,
    base_df: pd.DataFrame,
    output_path: Path,
    metrics_path: Path,
    importances_path: Path,
) -> dict[str, float]:
    labeled = model_df.loc[model_df["has_direct_wiki_signal"] == 1].copy()
    unlabeled = model_df.loc[model_df["has_direct_wiki_signal"] == 0].copy()

    X = labeled[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = labeled["target_proxy"].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    X_all = model_df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    all_preds = pipeline.predict(X_all)
    model_df[pred_col] = all_preds
    model_df["observed_proxy_score"] = model_df["target_proxy"].astype(float)
    model_df[final_col] = np.where(
        model_df["has_direct_wiki_signal"] == 1,
        model_df["observed_proxy_score"],
        model_df[pred_col],
    )
    model_df[a_col] = model_df[final_col] / model_df[final_col].sum()
    model_df[score_source_col] = np.where(
        model_df["has_direct_wiki_signal"] == 1,
        "observed_wiki",
        f"{model_name}_predicted",
    )

    merged = base_df.merge(
        model_df[
            [
                "poi_id",
                "has_direct_wiki_signal",
                "has_valid_wiki_identity_but_missing_pageviews",
                "target_proxy",
                "observed_proxy_score",
                pred_col,
                final_col,
                a_col,
                score_source_col,
            ]
        ],
        on="poi_id",
        how="left",
    )
    merged.to_csv(output_path, index=False)

    metrics = {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "labeled_rows": int(len(labeled)),
        "predict_rows": int(len(unlabeled)),
        "feature_count": int(len(CATEGORICAL_FEATURES) + len(NUMERIC_FEATURES)),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))

    preprocessor = pipeline.named_steps["preprocessor"]
    feature_names = preprocessor.get_feature_names_out()
    importances = pipeline.named_steps["model"].feature_importances_
    importance_df = (
        pd.DataFrame({"feature": feature_names, "importance": importances})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    importance_df.to_csv(importances_path, index=False)

    return metrics


def main() -> None:
    model_df = prepare_model_table()
    base_df = pd.read_csv(BASE_INPUT_PATH)

    rf_metrics = fit_and_score(
        model_df.copy(),
        build_rf_pipeline(),
        pred_col="rf_predicted_proxy_score",
        final_col="final_score_rf",
        a_col="A_rf",
        score_source_col="score_source_rf",
        model_name="rf",
        base_df=base_df,
        output_path=RF_OUTPUT_PATH,
        metrics_path=RF_METRICS_PATH,
        importances_path=RF_IMPORTANCES_PATH,
    )

    xgb_metrics = fit_and_score(
        model_df.copy(),
        build_xgb_pipeline(),
        pred_col="xgb_predicted_proxy_score",
        final_col="final_score_xgb",
        a_col="A_xgb",
        score_source_col="score_source_xgb",
        model_name="xgb",
        base_df=base_df,
        output_path=XGB_OUTPUT_PATH,
        metrics_path=XGB_METRICS_PATH,
        importances_path=XGB_IMPORTANCES_PATH,
    )

    print("RF metrics:", rf_metrics)
    print("XGB metrics:", xgb_metrics)


if __name__ == "__main__":
    main()
