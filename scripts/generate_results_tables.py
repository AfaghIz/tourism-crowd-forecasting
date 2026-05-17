from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"

PART_A_INPUT = EVALUATION_DIR / "part_a_model_comparison.csv"
PART_B_INPUT = EVALUATION_DIR / "part_b_model_comparison.csv"

PART_A_TABLE_CSV = EVALUATION_DIR / "part_a_results_table.csv"
PART_B_TABLE_CSV = EVALUATION_DIR / "part_b_results_table.csv"
COMBINED_TABLE_CSV = EVALUATION_DIR / "part_a_part_b_results_tables.csv"
COMBINED_TABLE_MD = EVALUATION_DIR / "part_a_part_b_results_tables.md"
PART_A_TABLE_PNG = EVALUATION_DIR / "part_a_results_table.png"
PART_B_TABLE_PNG = EVALUATION_DIR / "part_b_results_table.png"
PART_A_ERROR_GRAPH_PNG = EVALUATION_DIR / "part_a_error_metrics.png"
PART_A_R2_GRAPH_PNG = EVALUATION_DIR / "part_a_r2_scores.png"
PART_B_ERROR_GRAPH_PNG = EVALUATION_DIR / "part_b_error_metrics.png"
PART_B_R2_GRAPH_PNG = EVALUATION_DIR / "part_b_r2_scores.png"


def _fmt_number(value: object, decimals: int = 4) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{decimals}f}"


def _fmt_r2(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.3f}"


def _fmt_pct(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.1f}%"


def build_part_a_table(path: Path = PART_A_INPUT) -> pd.DataFrame:
    """Create a compact table for the Part A temporal model results."""
    df = pd.read_csv(path).sort_values(["rank_by_rmse_test", "model"]).reset_index(drop=True)
    table = pd.DataFrame(
        {
            "Rank": df["rank_by_rmse_test"].astype("Int64"),
            "Model": df["model"],
            "Model family": df["family"],
            "RMSE test": df["rmse_test"].map(_fmt_number),
            "MAE test": df["mae_test"].map(_fmt_number),
            "R2 test": df["r2_test"].map(_fmt_r2),
            "RMSE (% target range)": df["rmse_test_pct_of_range"].map(_fmt_pct),
            "Split": df["split_type"],
        }
    )
    return table


def build_part_b_table(path: Path = PART_B_INPUT) -> pd.DataFrame:
    """Create a compact table for the Part B POI attractiveness model results."""
    df = pd.read_csv(path).sort_values(["rank_by_rmse_test", "model"]).reset_index(drop=True)
    table = pd.DataFrame(
        {
            "Rank": df["rank_by_rmse_test"].astype("Int64"),
            "Model": df["model"],
            "Model family": df["family"],
            "RMSE test": df["rmse_test"].map(_fmt_number),
            "MAE test": df["mae_test"].map(_fmt_number),
            "R2 test": df["r2_test"].map(_fmt_r2),
            "Train rows": df["train_rows"].astype("Int64"),
            "Test rows": df["test_rows"].astype("Int64"),
            "Split": df["split_type"],
        }
    )
    return table


def load_chart_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).sort_values(["rank_by_rmse_test", "model"]).reset_index(drop=True)
    return df[
        [
            "model",
            "rmse_test",
            "mae_test",
            "r2_test",
            "rank_by_rmse_test",
        ]
    ].copy()


def write_markdown_tables(part_a: pd.DataFrame, part_b: pd.DataFrame, path: Path) -> None:
    def to_markdown(df: pd.DataFrame) -> str:
        header = "| " + " | ".join(df.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
        data_lines = [
            "| " + " | ".join(str(value) for value in row) + " |"
            for row in df.itertuples(index=False, name=None)
        ]
        return "\n".join([header, separator, *data_lines])

    lines = [
        "# Part A and Part B Results Tables",
        "",
        "## Part A: Temporal Crowd-Index Models",
        "",
        to_markdown(part_a),
        "",
        "## Part B: POI Attractiveness Models",
        "",
        to_markdown(part_b),
        "",
        "Notes:",
        "- Lower RMSE and MAE are better.",
        "- Higher R2 is better.",
        "- Part A uses the constructed `crowd_index` target.",
        "- Part B predicts the POI attractiveness proxy used to distribute city-level demand across POIs.",
        "",
    ]
    path.write_text("\n".join(lines))


def write_png_table(table: pd.DataFrame, title: str, path: Path) -> bool:
    """Save a PNG table if matplotlib is installed; skip cleanly otherwise."""
    os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    try:
        import seaborn as sns

        sns.set_theme(style="whitegrid")
    except ImportError:
        pass

    row_count, col_count = table.shape
    fig_width = max(10, col_count * 1.45)
    fig_height = max(2.8, row_count * 0.45 + 1.2)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=14)

    rendered = ax.table(
        cellText=table.astype(str).values,
        colLabels=table.columns,
        cellLoc="center",
        loc="center",
    )
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(9)
    rendered.scale(1, 1.35)

    for (row, _col), cell in rendered.get_celld().items():
        if row == 0:
            cell.set_facecolor("#1f2937")
            cell.set_text_props(color="white", weight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#f3f4f6")
        else:
            cell.set_facecolor("white")
        cell.set_edgecolor("#d1d5db")

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return True


def _load_plotting():
    os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None, None

    try:
        import seaborn as sns

        sns.set_theme(style="whitegrid")
    except ImportError:
        sns = None

    return plt, sns


def write_error_metric_chart(df: pd.DataFrame, title: str, path: Path) -> bool:
    plt, sns = _load_plotting()
    if plt is None:
        return False

    plot_df = df.melt(
        id_vars="model",
        value_vars=["rmse_test", "mae_test"],
        var_name="metric",
        value_name="score",
    )
    plot_df["metric"] = plot_df["metric"].map(
        {
            "rmse_test": "RMSE",
            "mae_test": "MAE",
        }
    )

    fig_width = max(8, len(df) * 1.1)
    fig, ax = plt.subplots(figsize=(fig_width, 4.8))
    palette = ["#2563eb", "#f97316"]
    if sns is not None:
        sns.barplot(data=plot_df, x="model", y="score", hue="metric", palette=palette, ax=ax)
    else:
        plot_df.pivot(index="model", columns="metric", values="score").plot.bar(ax=ax, color=palette)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Test score (lower is better)")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(title="")
    ax.grid(axis="x", visible=False)

    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", fontsize=8, padding=2)

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return True


def write_r2_chart(df: pd.DataFrame, title: str, path: Path) -> bool:
    plt, sns = _load_plotting()
    if plt is None:
        return False

    fig_width = max(8, len(df) * 0.95)
    fig, ax = plt.subplots(figsize=(fig_width, 4.6))
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in df["r2_test"]]

    if sns is not None:
        sns.barplot(data=df, x="model", y="r2_test", palette=colors, hue="model", legend=False, ax=ax)
    else:
        ax.bar(df["model"], df["r2_test"], color=colors)

    ax.axhline(0, color="#111827", linewidth=1)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("R2 test (higher is better)")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="x", visible=False)

    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", fontsize=8, padding=2)

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return True


def write_graphs() -> list[Path]:
    part_a = load_chart_data(PART_A_INPUT)
    part_b = load_chart_data(PART_B_INPUT)

    outputs: list[Path] = []
    graph_specs = [
        (
            write_error_metric_chart,
            part_a,
            "Part A Test Error by Model",
            PART_A_ERROR_GRAPH_PNG,
        ),
        (
            write_r2_chart,
            part_a,
            "Part A Test R2 by Model",
            PART_A_R2_GRAPH_PNG,
        ),
        (
            write_error_metric_chart,
            part_b,
            "Part B Test Error by Model",
            PART_B_ERROR_GRAPH_PNG,
        ),
        (
            write_r2_chart,
            part_b,
            "Part B Test R2 by Model",
            PART_B_R2_GRAPH_PNG,
        ),
    ]

    for writer, df, title, path in graph_specs:
        if writer(df, title, path):
            outputs.append(path)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate clean Part A and Part B result tables from evaluation CSVs."
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="Also write PNG table images using matplotlib/seaborn if available.",
    )
    parser.add_argument(
        "--no-graphs",
        action="store_true",
        help="Skip graph PNG generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

    part_a = build_part_a_table()
    part_b = build_part_b_table()
    combined = pd.concat(
        [
            part_a.assign(Part="Part A"),
            part_b.assign(Part="Part B"),
        ],
        ignore_index=True,
        sort=False,
    )

    part_a.to_csv(PART_A_TABLE_CSV, index=False)
    part_b.to_csv(PART_B_TABLE_CSV, index=False)
    combined.to_csv(COMBINED_TABLE_CSV, index=False)
    write_markdown_tables(part_a, part_b, COMBINED_TABLE_MD)

    print("Saved Part A table CSV to:", PART_A_TABLE_CSV)
    print("Saved Part B table CSV to:", PART_B_TABLE_CSV)
    print("Saved combined table CSV to:", COMBINED_TABLE_CSV)
    print("Saved Markdown tables to:", COMBINED_TABLE_MD)

    if not args.no_graphs:
        graph_paths = write_graphs()
        if graph_paths:
            print("Saved graph PNGs to:")
            for graph_path in graph_paths:
                print(" -", graph_path)
        else:
            print("Skipped graph PNGs because matplotlib is not installed.")

    if args.png:
        wrote_part_a_png = write_png_table(
            part_a,
            "Part A: Temporal Crowd-Index Models",
            PART_A_TABLE_PNG,
        )
        wrote_part_b_png = write_png_table(
            part_b,
            "Part B: POI Attractiveness Models",
            PART_B_TABLE_PNG,
        )
        if wrote_part_a_png and wrote_part_b_png:
            print("Saved PNG tables to:", PART_A_TABLE_PNG, "and", PART_B_TABLE_PNG)
        else:
            print("Skipped PNG tables because matplotlib is not installed.")


if __name__ == "__main__":
    main()
