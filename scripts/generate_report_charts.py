#!/usr/bin/env python3
"""Generate report-ready SVG charts from saved evaluation outputs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUT_DIR = DOCS_DIR / "report-figures"
POSTER_OUTPUT_DIR = DOCS_DIR / "poster-figures"

PART_A_PATH = EVAL_DIR / "part_a_model_comparison.csv"
PART_B_PATH = EVAL_DIR / "part_b_model_comparison.csv"

@dataclass(frozen=True)
class ChartStyle:
    bg_color: str
    text_primary: str
    text_secondary: str
    axis_color: str
    grid_color: str
    bar_palette: tuple[str, ...]
    title_font: str
    label_font: str


REPORT_STYLE = ChartStyle(
    bg_color="#ffffff",
    text_primary="#111827",
    text_secondary="#4b5563",
    axis_color="#1f2937",
    grid_color="#d1d5db",
    bar_palette=(
        "#4c78a8",
        "#6b7280",
        "#8c8c8c",
        "#9ca3af",
        "#374151",
        "#94a3b8",
        "#52525b",
    ),
    title_font="Times New Roman, Times, serif",
    label_font="Arial, Helvetica, sans-serif",
)

POSTER_STYLE = ChartStyle(
    bg_color="#ffffff",
    text_primary="#111827",
    text_secondary="#4b5563",
    axis_color="#1f2937",
    grid_color="#d1d5db",
    bar_palette=(
        "#2563eb",
        "#f97316",
        "#10b981",
        "#ef4444",
        "#8b5cf6",
        "#06b6d4",
        "#eab308",
    ),
    title_font="Times New Roman, Times, serif",
    label_font="Arial, Helvetica, sans-serif",
)


def read_metric_rows(path: Path, metric_column: str) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            model = (row.get("model") or "").strip()
            value = (row.get(metric_column) or "").strip()
            if not model or not value:
                continue
            rows.append((model, float(value)))
    return rows


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_bar_chart(
    *,
    title: str,
    subtitle: str,
    y_label: str,
    rows: Iterable[tuple[str, float]],
    output_path: Path,
    style: ChartStyle,
) -> None:
    data = list(rows)
    if not data:
        raise ValueError(f"No data available for {title}")

    width = 1100
    height = 700
    margin_top = 90
    margin_right = 40
    margin_bottom = 170
    margin_left = 110

    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    x_axis_y = margin_top + plot_height
    max_value = max(value for _, value in data)
    y_max = max_value * 1.12 if max_value > 0 else 1.0
    ticks = 5
    bar_gap = 22
    bar_width = (plot_width - bar_gap * (len(data) - 1)) / len(data)

    def y_pos(value: float) -> float:
        return x_axis_y - (value / y_max) * plot_height

    precision = 3 if max_value < 0.1 else 2

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts.append(f'<rect width="100%" height="100%" fill="{style.bg_color}"/>')
    parts.append(
        f'<text x="{width / 2}" y="44" text-anchor="middle" '
        f'font-family="{style.title_font}" font-size="28" font-weight="700" '
        f'fill="{style.text_primary}">{_svg_escape(title)}</text>'
    )
    parts.append(
        f'<text x="{width / 2}" y="72" text-anchor="middle" '
        f'font-family="{style.label_font}" font-size="14" fill="{style.text_secondary}">'
        f"{_svg_escape(subtitle)}</text>"
    )

    x0 = margin_left
    x1 = margin_left + plot_width
    parts.append(
        f'<line x1="{x0}" y1="{margin_top}" x2="{x0}" y2="{x_axis_y}" stroke="{style.axis_color}" stroke-width="2"/>'
    )
    parts.append(
        f'<line x1="{x0}" y1="{x_axis_y}" x2="{x1}" y2="{x_axis_y}" stroke="{style.axis_color}" stroke-width="2"/>'
    )

    for i in range(ticks + 1):
        tick_value = y_max * (i / ticks)
        y = y_pos(tick_value)
        parts.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{style.grid_color}" stroke-width="1.2"/>')
        parts.append(
            f'<text x="{x0 - 12}" y="{y + 5}" text-anchor="end" '
            f'font-family="{style.label_font}" font-size="12" fill="{style.text_secondary}">'
            f"{tick_value:.{precision}f}</text>"
        )

    label_y = margin_top + plot_height / 2
    parts.append(
        f'<text x="28" y="{label_y}" transform="rotate(-90 28 {label_y})" text-anchor="middle" '
        f'font-family="{style.label_font}" font-size="17" fill="{style.axis_color}">{_svg_escape(y_label)}</text>'
    )

    for index, (label, value) in enumerate(data):
        x = margin_left + index * (bar_width + bar_gap)
        y = y_pos(value)
        height_value = x_axis_y - y
        bar_color = style.bar_palette[index % len(style.bar_palette)]
        parts.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{height_value}" rx="8" fill="{bar_color}"/>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2}" y="{y - 10}" text-anchor="middle" '
            f'font-family="{style.label_font}" font-size="12" font-weight="700" fill="{style.text_primary}">'
            f"{value:.{precision}f}</text>"
        )
        label_x = x + bar_width / 2
        label_y2 = x_axis_y + 18
        parts.append(
            f'<g transform="translate({label_x},{label_y2}) rotate(32)">'
            f'<text text-anchor="start" font-family="{style.label_font}" font-size="13" fill="{style.axis_color}">'
            f"{_svg_escape(label)}</text></g>"
        )

    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def generate_chart_set(output_dir: Path, style: ChartStyle) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    specs = [
        ("Part A Model Comparison by RMSE", "Lower values indicate better predictive performance", "RMSE", PART_A_PATH, "rmse_test", "part_a_rmse.svg"),
        ("Part A Model Comparison by MAE", "Lower values indicate better predictive performance", "MAE", PART_A_PATH, "mae_test", "part_a_mae.svg"),
        ("Part A Model Comparison by R²", "Higher values indicate better predictive performance", "R²", PART_A_PATH, "r2_test", "part_a_r2.svg"),
        ("Part B Model Comparison by RMSE", "Lower values indicate better predictive performance", "RMSE", PART_B_PATH, "rmse_test", "part_b_rmse.svg"),
        ("Part B Model Comparison by MAE", "Lower values indicate better predictive performance", "MAE", PART_B_PATH, "mae_test", "part_b_mae.svg"),
        ("Part B Model Comparison by R²", "Higher values indicate better predictive performance", "R²", PART_B_PATH, "r2_test", "part_b_r2.svg"),
    ]

    for title, subtitle, y_label, path, metric_column, filename in specs:
        write_bar_chart(
            title=title,
            subtitle=subtitle,
            y_label=y_label,
            rows=read_metric_rows(path, metric_column),
            output_path=output_dir / filename,
            style=style,
        )


def main() -> None:
    generate_chart_set(OUTPUT_DIR, REPORT_STYLE)
    generate_chart_set(POSTER_OUTPUT_DIR, POSTER_STYLE)
    print(f"Wrote report charts to {OUTPUT_DIR}")
    print(f"Wrote poster charts to {POSTER_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
