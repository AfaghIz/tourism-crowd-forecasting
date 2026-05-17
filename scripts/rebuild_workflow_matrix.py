#!/usr/bin/env python3
"""Rebuild POI-time workflow matrices from refreshed Part A and Part B artifacts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

MODEL_DATASET_PATH = DATA / "model_dataset_with_holidays.csv"
MANUAL_PATH = DATA / "otm_poi_weights_manual_final.csv"
RF_PARTB_PATH = DATA / "otm_part_b_rf_scores.csv"
XGB_PARTB_PATH = DATA / "otm_part_b_xgb_scores.csv"

PRED_RF_PATH = DATA / "predictions_rf.csv"
PRED_XGB_PATH = DATA / "predictions_xgb.csv"
LEGACY_PRED_PATH = DATA / "predictions.csv"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    model_df = pd.read_csv(MODEL_DATASET_PATH, parse_dates=["date"])
    manual = pd.read_csv(MANUAL_PATH)
    rf_partb = pd.read_csv(RF_PARTB_PATH)
    xgb_partb = pd.read_csv(XGB_PARTB_PATH)
    return model_df, manual, rf_partb, xgb_partb


def build_temporal_predictions(model_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    X = model_df.drop(columns=["date", "crowd_index", "crowd_level"])
    y = model_df["crowd_index"]
    split_index = int(len(model_df) * 0.8)
    X_train = X.iloc[:split_index]
    y_train = y.iloc[:split_index]

    rf_model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
    rf_model.fit(X_train, y_train)
    pred_rf = model_df.copy()
    pred_rf["predicted_crowd"] = rf_model.predict(X)

    xgb_model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        objective="reg:squarederror",
        random_state=42,
    )
    xgb_model.fit(X_train, y_train)
    pred_xgb = model_df.copy()
    pred_xgb["predicted_crowd"] = xgb_model.predict(X)

    pred_rf.to_csv(PRED_RF_PATH, index=False)
    pred_xgb.to_csv(PRED_XGB_PATH, index=False)
    pred_xgb.to_csv(LEGACY_PRED_PATH, index=False)
    return pred_rf, pred_xgb


def prepare_part_b_tables(
    manual: pd.DataFrame, rf_partb: pd.DataFrame, xgb_partb: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    poi_cols = [
        "poi_id",
        "display_name_en",
        "category_clean",
        "query_area",
        "lat",
        "lon",
        "has_direct_wiki_signal",
        "exclude_from_part_b",
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
    ]

    manual_pois = manual[poi_cols + ["poi_weight", "poi_weight_source", "poi_weight_confidence"]].copy()
    manual_pois = manual_pois.rename(
        columns={
            "poi_weight": "poi_weight_value",
            "poi_weight_source": "score_source",
            "poi_weight_confidence": "score_confidence",
        }
    )
    manual_pois["part_b_model"] = "manual"

    rf_pois = rf_partb[
        poi_cols + ["A_rf", "score_source_rf", "observed_proxy_score", "rf_predicted_proxy_score", "final_score_rf"]
    ].copy()
    rf_pois = rf_pois.rename(
        columns={
            "A_rf": "poi_weight_value",
            "score_source_rf": "score_source",
            "rf_predicted_proxy_score": "predicted_proxy_score",
            "final_score_rf": "final_proxy_score",
        }
    )
    rf_pois["part_b_model"] = "rf"
    rf_pois["score_confidence"] = np.where(rf_pois["score_source"].eq("observed_wiki"), "high", "model_imputed")

    xgb_pois = xgb_partb[
        poi_cols
        + ["A_xgb", "score_source_xgb", "observed_proxy_score", "xgb_predicted_proxy_score", "final_score_xgb"]
    ].copy()
    xgb_pois = xgb_pois.rename(
        columns={
            "A_xgb": "poi_weight_value",
            "score_source_xgb": "score_source",
            "xgb_predicted_proxy_score": "predicted_proxy_score",
            "final_score_xgb": "final_proxy_score",
        }
    )
    xgb_pois["part_b_model"] = "xgb"
    xgb_pois["score_confidence"] = np.where(xgb_pois["score_source"].eq("observed_wiki"), "high", "model_imputed")

    return {"manual": manual_pois, "rf": rf_pois, "xgb": xgb_pois}


def prepare_temporal(df: pd.DataFrame, label: str) -> pd.DataFrame:
    temp = df[
        [
            "date",
            "predicted_crowd",
            "crowd_index",
            "crowd_level",
            "trend_demand",
            "temp_max",
            "temp_min",
            "temp_avg",
            "precipitation",
            "month",
            "week_of_year",
            "season_spring",
            "season_summer",
            "season_winter",
            "is_holiday",
        ]
    ].copy()
    temp = temp.rename(
        columns={
            "predicted_crowd": "city_demand_score",
            "crowd_index": "observed_city_crowd_index",
            "crowd_level": "city_crowd_level",
        }
    )
    temp["temporal_model"] = label
    return temp


def build_combo(temporal_df: pd.DataFrame, poi_df: pd.DataFrame, temporal_label: str, partb_label: str) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, t in temporal_df.iterrows():
        tmp = poi_df.copy()
        for c in temporal_df.columns:
            tmp[c] = t[c]
        tmp["crowdindex_poi"] = tmp["city_demand_score"] * tmp["poi_weight_value"]
        tmp["temporal_model"] = temporal_label
        tmp["part_b_model"] = partb_label
        rows.append(tmp)

    out = pd.concat(rows, ignore_index=True)
    out["workflow_model"] = out["temporal_model"] + "__" + out["part_b_model"]
    out["poi_crowd_rank_desc"] = out.groupby(["date", "workflow_model"])["crowdindex_poi"].rank(
        method="first", ascending=False
    )
    out["poi_crowd_percentile_desc"] = out.groupby(["date", "workflow_model"])["crowdindex_poi"].rank(
        pct=True, ascending=False
    )
    out["poi_busyness_band"] = pd.cut(
        out["poi_crowd_percentile_desc"],
        bins=[0, 0.2, 0.5, 0.8, 1.0],
        labels=["Very High", "High", "Medium", "Low"],
        include_lowest=True,
    )
    return out


def main() -> None:
    model_df, manual, rf_partb, xgb_partb = load_inputs()
    pred_rf, pred_xgb = build_temporal_predictions(model_df)
    part_b_tables = prepare_part_b_tables(manual, rf_partb, xgb_partb)

    rf_temporal = prepare_temporal(pred_rf, "rf")
    xgb_temporal = prepare_temporal(pred_xgb, "xgb")

    combo_frames: dict[str, pd.DataFrame] = {}
    for temporal_label, temporal_df in [("rf", rf_temporal), ("xgb", xgb_temporal)]:
        for partb_label, poi_df in part_b_tables.items():
            combo_name = f"{temporal_label}__{partb_label}"
            combo_frames[combo_name] = build_combo(temporal_df, poi_df, temporal_label, partb_label)
            combo_frames[combo_name].to_csv(DATA / f"otm_crowdindex_{combo_name}_weekly.csv", index=False)

    combined = pd.concat(combo_frames.values(), ignore_index=True)
    combined.to_csv(DATA / "otm_crowdindex_workflow_matrix_weekly.csv", index=False)

    # Keep the backend default provider file aligned with the currently preferred combo.
    combo_frames["xgb__rf"].to_csv(DATA / "otm_crowdindex_xgb__rf_weekly.csv", index=False)

    print("Rebuilt workflow matrices:")
    for name, df in combo_frames.items():
        print(f"  - {name}: {len(df)} rows, {df['date'].min().date()} -> {df['date'].max().date()}")
    print(f"Combined matrix: {len(combined)} rows")


if __name__ == "__main__":
    main()
