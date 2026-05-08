from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
CSV_OUTPUT_PATH = OUTPUT_DIR / "part_a_model_comparison.csv"
MD_OUTPUT_PATH = OUTPUT_DIR / "part_a_model_comparison.md"

LINEAR_METRICS_PATH = PROJECT_ROOT / "data" / "processed" / "linear_baseline" / "metrics.csv"
LIGHTGBM_METRICS_PATH = PROJECT_ROOT / "data" / "processed" / "lightgbm_baseline" / "metrics.csv"
LSTM_METRICS_PATH = PROJECT_ROOT / "data" / "processed" / "lstm_baseline" / "metrics.csv"
RF_METRICS_PATH = PROJECT_ROOT / "data" / "processed" / "random_forest_baseline" / "metrics.csv"
XGB_METRICS_PATH = PROJECT_ROOT / "data" / "processed" / "xgboost_baseline" / "metrics.csv"


def load_target_context(path: Path) -> dict[str, float]:
    df = pd.read_csv(path)
    target = df["crowd_index"]
    return {
        "target_min": float(target.min()),
        "target_max": float(target.max()),
        "target_mean": float(target.mean()),
        "target_std": float(target.std()),
        "target_range": float(target.max() - target.min()),
    }


def load_linear_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    family_map = {
        "Ordinary Least Squares": "Linear regression",
        "Ridge (alpha=1.0)": "Regularized linear regression",
        "Lasso (alpha=0.0001)": "Regularized linear regression",
    }
    display_map = {
        "Ordinary Least Squares": "OLS",
        "Ridge (alpha=1.0)": "Ridge",
        "Lasso (alpha=0.0001)": "Lasso",
    }

    rows: list[dict[str, object]] = []
    for row in df.to_dict(orient="records"):
        model_name = str(row["model"])
        rows.append(
            {
                "model": display_map.get(model_name, model_name),
                "model_variant": model_name,
                "family": family_map.get(model_name, "Linear regression"),
                "source_type": "metrics_csv",
                "source_file": str(path),
                "split_type": row.get("split", "chronological"),
                "rmse_train": float(row["rmse_train"]),
                "rmse_test": float(row["rmse_test"]),
                "mae_train": float(row["mae_train"]),
                "mae_test": float(row["mae_test"]),
                "r2_train": float(row["r2_train"]) if "r2_train" in row and pd.notna(row["r2_train"]) else None,
                "r2_test": float(row["r2_test"]) if "r2_test" in row and pd.notna(row["r2_test"]) else None,
                "notes": "Target is largely reconstructable from source features used to create crowd_index.",
            }
        )
    return pd.DataFrame(rows)


def load_single_row_metrics(
    path: Path,
    *,
    model: str,
    family: str,
    notes: str,
) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"No rows found in metrics file: {path}")
    row = df.iloc[0]
    return pd.DataFrame(
        [
            {
                "model": model,
                "model_variant": row.get("model", model),
                "family": family,
                "source_type": "metrics_csv",
                "source_file": str(path),
                "split_type": row.get("split", "chronological"),
                "rmse_train": float(row["rmse_train"]),
                "rmse_test": float(row["rmse_test"]),
                "mae_train": float(row["mae_train"]),
                "mae_test": float(row["mae_test"]),
                "r2_train": float(row["r2_train"]) if "r2_train" in row and pd.notna(row["r2_train"]) else None,
                "r2_test": float(row["r2_test"]) if "r2_test" in row and pd.notna(row["r2_test"]) else None,
                "notes": notes,
            }
        ]
    )

def build_summary_table(target_context: dict[str, float]) -> pd.DataFrame:
    frames = [
        load_linear_metrics(LINEAR_METRICS_PATH),
        load_single_row_metrics(
            LIGHTGBM_METRICS_PATH,
            model="LightGBM",
            family="Gradient-boosted trees",
            notes="Flexible tabular baseline; still evaluated against a formula-derived target.",
        ),
        load_single_row_metrics(
            LSTM_METRICS_PATH,
            model="LSTM",
            family="Sequence neural network",
            notes="Uses an 8-week lookback sequence; task still uses a constructed crowd_index target.",
        ),
        load_single_row_metrics(
            RF_METRICS_PATH,
            model="Random Forest",
            family="Bagged decision trees",
            notes="Saved from the aligned Random Forest baseline script using the same chronological split pattern.",
        ),
        load_single_row_metrics(
            XGB_METRICS_PATH,
            model="XGBoost",
            family="Gradient-boosted trees",
            notes="Saved from the aligned XGBoost baseline script using the same chronological split pattern.",
        ),
    ]

    summary = pd.concat(frames, ignore_index=True)
    summary["part"] = "Part A"
    summary["target_name"] = "crowd_index"
    summary["target_min"] = target_context["target_min"]
    summary["target_max"] = target_context["target_max"]
    summary["target_mean"] = target_context["target_mean"]
    summary["target_std"] = target_context["target_std"]
    summary["target_range"] = target_context["target_range"]
    summary["mae_test_pct_of_range"] = summary["mae_test"] / target_context["target_range"] * 100.0
    summary["rmse_test_pct_of_range"] = summary["rmse_test"] / target_context["target_range"] * 100.0
    summary["rank_by_rmse_test"] = summary["rmse_test"].rank(method="min", ascending=True).astype("Int64")
    summary["rank_by_mae_test"] = summary["mae_test"].rank(method="min", ascending=True).astype("Int64")
    summary["rank_by_r2_test"] = summary["r2_test"].rank(method="min", ascending=False).astype("Int64")

    ordered_columns = [
        "part",
        "model",
        "model_variant",
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
        "mae_test_pct_of_range",
        "rmse_test_pct_of_range",
        "rank_by_rmse_test",
        "rank_by_mae_test",
        "rank_by_r2_test",
        "target_name",
        "target_min",
        "target_max",
        "target_mean",
        "target_std",
        "target_range",
        "notes",
    ]
    return summary[ordered_columns].sort_values(["rank_by_rmse_test", "model"]).reset_index(drop=True)


def write_markdown_summary(path: Path, summary: pd.DataFrame, target_context: dict[str, float]) -> None:
    display = summary[
        [
            "model",
            "family",
            "rmse_test",
            "mae_test",
            "r2_test",
            "rmse_test_pct_of_range",
            "mae_test_pct_of_range",
            "source_type",
        ]
    ].copy()

    display["rmse_test"] = display["rmse_test"].map(lambda v: f"{v:.6f}")
    display["mae_test"] = display["mae_test"].map(lambda v: f"{v:.6f}")
    display["r2_test"] = display["r2_test"].map(lambda v: f"{v:.6f}" if pd.notna(v) else "")
    display["rmse_test_pct_of_range"] = display["rmse_test_pct_of_range"].map(lambda v: f"{v:.2f}%")
    display["mae_test_pct_of_range"] = display["mae_test_pct_of_range"].map(lambda v: f"{v:.2f}%")

    header = "| " + " | ".join(display.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    data_lines = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in display.itertuples(index=False, name=None)
    ]

    lines = [
        "# Part A Model Comparison",
        "",
        "This summary compares model performance on the `crowd_index` target used in Part A.",
        "",
        f"- Target minimum: `{target_context['target_min']:.6f}`",
        f"- Target maximum: `{target_context['target_max']:.6f}`",
        f"- Target mean: `{target_context['target_mean']:.6f}`",
        f"- Target standard deviation: `{target_context['target_std']:.6f}`",
        f"- Target range: `{target_context['target_range']:.6f}`",
        "",
        "Important interpretation note:",
        "- `crowd_index` is a constructed target based directly on trend demand, temperature, and precipitation, so very small linear-model errors partly reflect target reconstructability rather than purely out-of-sample forecasting difficulty.",
        "",
        header,
        separator,
        *data_lines,
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    target_context = load_target_context(DATASET_PATH)
    summary = build_summary_table(target_context)

    summary.to_csv(CSV_OUTPUT_PATH, index=False)
    write_markdown_summary(MD_OUTPUT_PATH, summary, target_context)

    print("Saved Part A comparison CSV to:", CSV_OUTPUT_PATH)
    print("Saved Part A comparison Markdown to:", MD_OUTPUT_PATH)
    print()
    print(summary[["model", "rmse_test", "mae_test", "r2_test", "rank_by_rmse_test"]].to_string(index=False))


if __name__ == "__main__":
    main()
