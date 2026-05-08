from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = DATA_DIR / "evaluation"

MODEL_TABLE_PATH = DATA_DIR / "otm_part_b_modeling_table.csv"
MANUAL_WEIGHTS_PATH = DATA_DIR / "otm_poi_weights_manual_final.csv"
RF_METRICS_PATH = DATA_DIR / "otm_part_b_rf_metrics.json"
XGB_METRICS_PATH = DATA_DIR / "otm_part_b_xgb_metrics.json"
GROUP_STATS_PATH = DATA_DIR / "otm_poi_weight_group_stats_manual_final.csv"

CSV_OUTPUT_PATH = OUTPUT_DIR / "part_b_model_comparison.csv"
MD_OUTPUT_PATH = OUTPUT_DIR / "part_b_model_comparison.md"
MANUAL_METRICS_OUTPUT_PATH = OUTPUT_DIR / "part_b_manual_metrics.json"
MANUAL_PREDICTIONS_OUTPUT_PATH = OUTPUT_DIR / "part_b_manual_test_predictions.csv"

RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_model_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    df["category_clean"] = df["category_clean"].fillna(df.get("category_clean.1"))
    df["query_area"] = df["query_area"].fillna(df.get("query_area.1"))
    return df


def load_manual_constants(path: Path) -> tuple[int, int]:
    stats = pd.read_csv(path)
    return int(stats["k_default"].iloc[0]), int(stats["k_religious"].iloc[0])


def build_manual_group_stats(train_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    category_stats = (
        train_df.groupby("category_clean", dropna=False)["target_proxy"]
        .agg(group_median="median", group_count="size")
        .reset_index()
    )
    category_area_stats = (
        train_df.groupby(["category_clean", "query_area"], dropna=False)["target_proxy"]
        .agg(group_median="median", group_count="size")
        .reset_index()
    )
    global_median = float(train_df["target_proxy"].median())
    return category_stats, category_area_stats, global_median


def build_manual_predictions(
    eval_df: pd.DataFrame,
    category_stats: pd.DataFrame,
    category_area_stats: pd.DataFrame,
    *,
    global_median: float,
    k_default: int,
    k_religious: int,
    min_religious_area_group: int = 5,
) -> pd.DataFrame:
    df = eval_df.copy()
    df = df.merge(
        category_stats.rename(
            columns={"group_median": "category_median", "group_count": "category_count"}
        ),
        on="category_clean",
        how="left",
    )
    df = df.merge(
        category_area_stats.rename(
            columns={"group_median": "category_area_median", "group_count": "category_area_count"}
        ),
        on=["category_clean", "query_area"],
        how="left",
    )

    def predict_row(row: pd.Series) -> pd.Series:
        area_median = row["category_area_median"]
        area_count = row["category_area_count"]
        category_median = row["category_median"]
        category_count = row["category_count"]

        use_area = pd.notna(area_median) and pd.notna(area_count)
        if row["category_clean"] == "religious":
            use_area = use_area and float(area_count) >= min_religious_area_group

        if use_area:
            chosen_median = float(area_median)
            chosen_count = float(area_count)
            chosen_source = "category_area"
        elif pd.notna(category_median) and pd.notna(category_count):
            chosen_median = float(category_median)
            chosen_count = float(category_count)
            chosen_source = "category"
        else:
            chosen_median = float(global_median)
            chosen_count = 0.0
            chosen_source = "global"

        k_value = k_religious if row["category_clean"] == "religious" else k_default
        lambda_value = chosen_count / (chosen_count + k_value) if chosen_count > 0 else 0.0
        predicted = lambda_value * chosen_median

        return pd.Series(
            {
                "manual_predicted_proxy_score": predicted,
                "manual_group_source": chosen_source,
                "manual_group_count": chosen_count,
                "manual_group_median": chosen_median,
                "manual_lambda": lambda_value,
            }
        )

    pred_cols = df.apply(predict_row, axis=1)
    return pd.concat([df, pred_cols], axis=1)


def score_predictions(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"mae": mae, "rmse": rmse, "r2": r2}


def evaluate_manual_baseline(model_df: pd.DataFrame, k_default: int, k_religious: int) -> tuple[dict[str, object], pd.DataFrame]:
    labeled = model_df.loc[model_df["has_direct_wiki_signal"] == 1].copy()
    train_df, test_df = train_test_split(labeled, test_size=TEST_SIZE, random_state=RANDOM_STATE)

    category_stats, category_area_stats, global_median = build_manual_group_stats(train_df)
    train_pred_df = build_manual_predictions(
        train_df,
        category_stats,
        category_area_stats,
        global_median=global_median,
        k_default=k_default,
        k_religious=k_religious,
    )
    test_pred_df = build_manual_predictions(
        test_df,
        category_stats,
        category_area_stats,
        global_median=global_median,
        k_default=k_default,
        k_religious=k_religious,
    )

    train_metrics = score_predictions(train_pred_df["target_proxy"], train_pred_df["manual_predicted_proxy_score"])
    test_metrics = score_predictions(test_pred_df["target_proxy"], test_pred_df["manual_predicted_proxy_score"])

    metrics = {
        "model": "Manual baseline",
        "mae_train": train_metrics["mae"],
        "rmse_train": train_metrics["rmse"],
        "r2_train": train_metrics["r2"],
        "mae_test": test_metrics["mae"],
        "rmse_test": test_metrics["rmse"],
        "r2_test": test_metrics["r2"],
        "split": "random_labeled_train_test_split",
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "labeled_rows": int(len(labeled)),
        "feature_count": 0,
        "manual_eval_basis": "fallback_simulation_without_direct_wiki_signal",
    }

    return metrics, test_pred_df


def load_json_metrics(path: Path, model: str, family: str, notes: str) -> dict[str, object]:
    payload = json.loads(path.read_text())
    return {
        "model": model,
        "family": family,
        "source_type": "metrics_json",
        "source_file": str(path),
        "split_type": "random_labeled_train_test_split",
        "rmse_train": None,
        "rmse_test": float(payload["rmse"]),
        "mae_train": None,
        "mae_test": float(payload["mae"]),
        "r2_train": None,
        "r2_test": float(payload["r2"]),
        "train_rows": int(payload["train_rows"]),
        "test_rows": int(payload["test_rows"]),
        "labeled_rows": int(payload["labeled_rows"]),
        "predict_rows": int(payload["predict_rows"]),
        "feature_count": int(payload["feature_count"]),
        "notes": notes,
    }


def build_summary_table(manual_metrics: dict[str, object]) -> pd.DataFrame:
    rows = [
        {
            "model": "Manual baseline",
            "family": "Rule-based fallback",
            "source_type": "evaluation_script",
            "source_file": str(MANUAL_METRICS_OUTPUT_PATH),
            "split_type": str(manual_metrics["split"]),
            "rmse_train": float(manual_metrics["rmse_train"]),
            "rmse_test": float(manual_metrics["rmse_test"]),
            "mae_train": float(manual_metrics["mae_train"]),
            "mae_test": float(manual_metrics["mae_test"]),
            "r2_train": float(manual_metrics["r2_train"]),
            "r2_test": float(manual_metrics["r2_test"]),
            "train_rows": int(manual_metrics["train_rows"]),
            "test_rows": int(manual_metrics["test_rows"]),
            "labeled_rows": int(manual_metrics["labeled_rows"]),
            "predict_rows": 0,
            "feature_count": int(manual_metrics["feature_count"]),
            "notes": "Manual fallback is evaluated by hiding the direct wiki score and reconstructing the category/category-area shrinkage estimate from train only.",
        },
        load_json_metrics(
            RF_METRICS_PATH,
            model="Random Forest",
            family="Bagged decision trees",
            notes="Trained on the labeled subset and evaluated on a random held-out test split.",
        ),
        load_json_metrics(
            XGB_METRICS_PATH,
            model="XGBoost",
            family="Gradient-boosted trees",
            notes="Trained on the labeled subset and evaluated on a random held-out test split.",
        ),
    ]

    summary = pd.DataFrame(rows)
    summary["part"] = "Part B"
    summary["target_name"] = "target_proxy"
    summary["rank_by_rmse_test"] = summary["rmse_test"].rank(method="min", ascending=True).astype("Int64")
    summary["rank_by_mae_test"] = summary["mae_test"].rank(method="min", ascending=True).astype("Int64")
    summary["rank_by_r2_test"] = summary["r2_test"].rank(method="min", ascending=False).astype("Int64")

    ordered_columns = [
        "part",
        "model",
        "family",
        "source_type",
        "source_file",
        "split_type",
        "rmse_train",
        "rmse_test",
        "mae_train",
        "mae_test",
        "r2_train",
        "r2_test",
        "train_rows",
        "test_rows",
        "labeled_rows",
        "predict_rows",
        "feature_count",
        "rank_by_rmse_test",
        "rank_by_mae_test",
        "rank_by_r2_test",
        "target_name",
        "notes",
    ]
    return summary[ordered_columns].sort_values(["rank_by_rmse_test", "model"]).reset_index(drop=True)


def write_markdown_summary(path: Path, summary: pd.DataFrame) -> None:
    display = summary[
        [
            "model",
            "family",
            "rmse_test",
            "mae_test",
            "r2_test",
            "train_rows",
            "test_rows",
            "source_type",
        ]
    ].copy()

    display["rmse_test"] = display["rmse_test"].map(lambda v: f"{v:.6f}")
    display["mae_test"] = display["mae_test"].map(lambda v: f"{v:.6f}")
    display["r2_test"] = display["r2_test"].map(lambda v: f"{v:.6f}")

    header = "| " + " | ".join(display.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    data_lines = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in display.itertuples(index=False, name=None)
    ]

    lines = [
        "# Part B Model Comparison",
        "",
        "This summary compares the manual fallback baseline against the Part B Random Forest and XGBoost models.",
        "",
        "Important interpretation note:",
        "- The manual baseline is not scored using copied observed wiki labels. Instead, direct wiki signal is hidden and the fallback shrinkage estimate is rebuilt from the training split only.",
        "",
        header,
        separator,
        *data_lines,
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_df = load_model_table(MODEL_TABLE_PATH)
    k_default, k_religious = load_manual_constants(GROUP_STATS_PATH)
    manual_metrics, manual_test_predictions = evaluate_manual_baseline(
        model_df,
        k_default=k_default,
        k_religious=k_religious,
    )

    MANUAL_METRICS_OUTPUT_PATH.write_text(json.dumps(manual_metrics, indent=2))
    manual_test_predictions.to_csv(MANUAL_PREDICTIONS_OUTPUT_PATH, index=False)

    summary = build_summary_table(manual_metrics)
    summary.to_csv(CSV_OUTPUT_PATH, index=False)
    write_markdown_summary(MD_OUTPUT_PATH, summary)

    print("Saved Part B comparison CSV to:", CSV_OUTPUT_PATH)
    print("Saved Part B comparison Markdown to:", MD_OUTPUT_PATH)
    print("Saved manual baseline metrics to:", MANUAL_METRICS_OUTPUT_PATH)
    print("Saved manual test predictions to:", MANUAL_PREDICTIONS_OUTPUT_PATH)
    print()
    print(summary[["model", "rmse_test", "mae_test", "r2_test", "rank_by_rmse_test"]].to_string(index=False))


if __name__ == "__main__":
    main()
