from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend-python"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from forecast_service import ForecastService  # noqa: E402
from recommendation.explanation_engine import crowd_level_label  # noqa: E402
from recommendation.pipeline import recommend  # noqa: E402
from weekly_model import IstanbulWeeklyModelRepository  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
CSV_OUTPUT_PATH = OUTPUT_DIR / "recommendation_system_evaluation.csv"
MD_OUTPUT_PATH = OUTPUT_DIR / "recommendation_system_evaluation.md"
JSON_OUTPUT_PATH = OUTPUT_DIR / "recommendation_system_summary.json"
POI_TABLE_PATH = PROJECT_ROOT / "data" / "processed" / "otm_pois_model_ready_with_nlp_features_exclusions.csv"

ANCHOR_SPECS: list[dict[str, str]] = [
    {"poi_id": "otm_R1555271", "name": "Hagia Sophia"},
    {"poi_id": "otm_N7294561685", "name": "Chora Mosque / Kariye Museum"},
    {"poi_id": "otm_W23236783", "name": "Galata Tower"},
    {"poi_id": "otm_N7215645385", "name": "The Blue Mosque"},
    {"poi_id": "otm_R1564032", "name": "Süleymaniye Mosque"},
    {"poi_id": "otm_R7318154", "name": "Rumeli Fortress"},
]


def load_anchor_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    df["anchor_name"] = df["display_name_en"].fillna(df["name"])
    return df


def build_periods() -> list[dict[str, str]]:
    service = ForecastService(IstanbulWeeklyModelRepository())
    raw_options = service.period_options()
    periods: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_options:
        period_id = str(item["id"])
        if period_id in seen:
            continue
        periods.append(
            {
                "basis_week_start": period_id,
                "basis_label": str(item["label"]),
                "basis_level": str(item["level"]),
            }
        )
        seen.add(period_id)
    return periods


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def evaluate_anchor_periods(anchor_df: pd.DataFrame, periods: list[dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in ANCHOR_SPECS:
        match = anchor_df.loc[anchor_df["poi_id"] == spec["poi_id"]]
        if match.empty:
            raise ValueError(f"Anchor POI not found in evaluation table: {spec['poi_id']} ({spec['name']})")
        anchor_row = match.iloc[0]
        origin_lat = float(anchor_row["lat"])
        origin_lon = float(anchor_row["lon"])
        anchor_name = str(anchor_row["anchor_name"])
        anchor_category = str(anchor_row["category_clean"])

        for period in periods:
            basis_week_start = period["basis_week_start"]
            timestamp = f"{basis_week_start}T12:00:00"
            result = recommend(
                origin_lat,
                origin_lon,
                timestamp=pd.Timestamp(timestamp).to_pydatetime(),
                radius_km=6.0,
                top_k=5,
                anchor_poi_id=spec["poi_id"],
                anchor_radius_km=3.0,
            )
            anchor_payload = result.get("anchor") or {}
            recommendations = list(result.get("recommendations") or [])
            top = recommendations[0] if recommendations else {}

            anchor_crowd_signal = _to_float(anchor_payload.get("crowd_signal"))
            anchor_city_demand = _to_float(anchor_payload.get("city_demand_score"))
            anchor_crowd_level = (
                crowd_level_label(anchor_crowd_signal).title()
                if anchor_crowd_signal is not None
                else period["basis_level"]
            )

            row = {
                "anchor_poi_id": spec["poi_id"],
                "anchor_name": anchor_name,
                "anchor_category": anchor_category,
                "basis_week_start": basis_week_start,
                "basis_label": period["basis_label"],
                "basis_level": period["basis_level"],
                "anchor_crowd_signal": anchor_crowd_signal,
                "anchor_crowd_level": anchor_crowd_level,
                "anchor_city_demand_score": anchor_city_demand,
                "recommendation_count": int(len(recommendations)),
                "has_recommendation": bool(recommendations),
                "top_alternative_poi_id": top.get("poi_id"),
                "top_alternative_name": top.get("name"),
                "top_alternative_category": top.get("category"),
                "top_alternative_crowd_signal": _to_float(top.get("crowd_signal")),
                "top_crowd_relief": _to_float(top.get("crowd_relief")),
                "top_similarity": _to_float(top.get("similarity")),
                "top_practicality": _to_float(top.get("practicality")),
                "top_distance_to_anchor_km": _to_float(top.get("distance_to_anchor_km")),
                "top_distance_km": _to_float(top.get("distance_km")),
                "top_alternative_score": _to_float(top.get("score")),
                "top_family_overlap_count": _to_float(top.get("family_overlap_count")),
                "top_subtype_overlap_count": _to_float(top.get("subtype_overlap_count")),
                "top_explanation": top.get("explanation"),
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    df["reroute_recommended"] = df["has_recommendation"]
    df["anchor_is_high"] = df["anchor_crowd_level"].eq("High")
    df["anchor_is_low_or_medium"] = df["anchor_crowd_level"].isin(["Low", "Medium"])
    df["ui_would_show_alternatives"] = df["anchor_is_high"]
    df["raw_low_medium_suppressed"] = df["anchor_is_low_or_medium"] & (~df["has_recommendation"])
    return df


def build_summary(case_df: pd.DataFrame) -> dict[str, Any]:
    cases_with_recs = case_df.loc[case_df["has_recommendation"]]
    high_cases = case_df.loc[case_df["anchor_is_high"]]
    low_medium_cases = case_df.loc[case_df["anchor_is_low_or_medium"]]

    summary: dict[str, Any] = {
        "total_cases": int(len(case_df)),
        "cases_with_recommendations": int(case_df["has_recommendation"].sum()),
        "coverage_rate": float(case_df["has_recommendation"].mean()) if len(case_df) else 0.0,
        "average_recommendation_count": float(case_df["recommendation_count"].mean()) if len(case_df) else 0.0,
        "high_anchor_cases": int(len(high_cases)),
        "high_anchor_coverage_rate": float(high_cases["has_recommendation"].mean()) if len(high_cases) else 0.0,
        "low_medium_anchor_cases": int(len(low_medium_cases)),
        "raw_low_medium_suppression_rate": float((~low_medium_cases["has_recommendation"]).mean()) if len(low_medium_cases) else 0.0,
        "average_top_crowd_relief": float(cases_with_recs["top_crowd_relief"].mean()) if len(cases_with_recs) else 0.0,
        "median_top_crowd_relief": float(cases_with_recs["top_crowd_relief"].median()) if len(cases_with_recs) else 0.0,
        "average_top_similarity": float(cases_with_recs["top_similarity"].mean()) if len(cases_with_recs) else 0.0,
        "average_top_practicality": float(cases_with_recs["top_practicality"].mean()) if len(cases_with_recs) else 0.0,
        "average_top_distance_to_anchor_km": float(cases_with_recs["top_distance_to_anchor_km"].mean()) if len(cases_with_recs) else 0.0,
    }

    by_period = (
        case_df.groupby(["basis_week_start", "basis_label", "basis_level"], dropna=False)
        .agg(
            cases=("anchor_poi_id", "size"),
            recommendations=("has_recommendation", "sum"),
            average_anchor_crowd=("anchor_crowd_signal", "mean"),
            average_city_demand=("anchor_city_demand_score", "mean"),
            average_top_crowd_relief=("top_crowd_relief", "mean"),
        )
        .reset_index()
    )
    by_period["coverage_rate"] = by_period["recommendations"] / by_period["cases"]

    by_anchor = (
        case_df.groupby(["anchor_name", "anchor_category"], dropna=False)
        .agg(
            periods_evaluated=("basis_week_start", "size"),
            recommendations=("has_recommendation", "sum"),
            average_anchor_crowd=("anchor_crowd_signal", "mean"),
            average_top_crowd_relief=("top_crowd_relief", "mean"),
            average_top_similarity=("top_similarity", "mean"),
            average_top_distance_to_anchor_km=("top_distance_to_anchor_km", "mean"),
        )
        .reset_index()
    )
    by_anchor["coverage_rate"] = by_anchor["recommendations"] / by_anchor["periods_evaluated"]

    summary["by_period"] = by_period.to_dict(orient="records")
    summary["by_anchor"] = by_anchor.to_dict(orient="records")
    return summary


def _fmt_float(value: Any, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return f"{float(value):.{digits}f}"


def _markdown_table(df: pd.DataFrame) -> list[str]:
    header = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = [
        "| " + " | ".join("" if (isinstance(v, float) and pd.isna(v)) else str(v) for v in row) + " |"
        for row in df.itertuples(index=False, name=None)
    ]
    return [header, separator, *rows]


def write_markdown(path: Path, case_df: pd.DataFrame, summary: dict[str, Any]) -> None:
    overview = [
        "# Recommendation System Evaluation",
        "",
        "This evaluation treats the recommendation layer as an anchor-based decision system rather than a supervised predictor.",
        "The goal is to measure whether the system returns nearby, lower-crowd, semantically compatible alternatives across modeled periods.",
        "",
        "## Overall Summary",
        "",
        f"- Total anchor-period cases: `{summary['total_cases']}`",
        f"- Cases with at least one recommendation: `{summary['cases_with_recommendations']}`",
        f"- Overall coverage rate: `{summary['coverage_rate']:.2%}`",
        f"- High-anchor coverage rate: `{summary['high_anchor_coverage_rate']:.2%}`",
        f"- Raw low/medium-anchor suppression rate: `{summary['raw_low_medium_suppression_rate']:.2%}`",
        f"- Average recommendation count: `{summary['average_recommendation_count']:.2f}`",
        f"- Average top crowd relief: `{summary['average_top_crowd_relief']:.4f}`",
        f"- Median top crowd relief: `{summary['median_top_crowd_relief']:.4f}`",
        f"- Average top similarity: `{summary['average_top_similarity']:.4f}`",
        f"- Average top practicality: `{summary['average_top_practicality']:.4f}`",
        f"- Average top distance to anchor: `{summary['average_top_distance_to_anchor_km']:.3f}` km",
        "",
        "Important interpretation note:",
        "- These results evaluate recommendation behavior under modeled crowd conditions. They do not represent click-through accuracy or ground-truth user acceptance, because the project does not have labeled recommendation targets.",
        "- The app UI only surfaces anchor alternatives for high-crowd POIs, so the raw low/medium suppression rate here describes backend recommendation behavior rather than the final frontend gating rule.",
        "",
        "## By Modeled Period",
        "",
    ]

    by_period_df = pd.DataFrame(summary["by_period"]).copy()
    if not by_period_df.empty:
        by_period_df["coverage_rate"] = by_period_df["coverage_rate"].map(lambda v: f"{float(v):.2%}")
        by_period_df["average_anchor_crowd"] = by_period_df["average_anchor_crowd"].map(_fmt_float)
        by_period_df["average_city_demand"] = by_period_df["average_city_demand"].map(_fmt_float)
        by_period_df["average_top_crowd_relief"] = by_period_df["average_top_crowd_relief"].map(_fmt_float)
        overview.extend(_markdown_table(by_period_df))
    else:
        overview.append("_No modeled period rows were generated._")

    overview.extend(["", "## By Anchor", ""])
    by_anchor_df = pd.DataFrame(summary["by_anchor"]).copy()
    if not by_anchor_df.empty:
        by_anchor_df["coverage_rate"] = by_anchor_df["coverage_rate"].map(lambda v: f"{float(v):.2%}")
        for col in ["average_anchor_crowd", "average_top_crowd_relief", "average_top_similarity", "average_top_distance_to_anchor_km"]:
            by_anchor_df[col] = by_anchor_df[col].map(_fmt_float)
        overview.extend(_markdown_table(by_anchor_df))
    else:
        overview.append("_No anchor rows were generated._")

    overview.extend(["", "## Case Table", ""])
    display_df = case_df[
        [
            "anchor_name",
            "basis_week_start",
            "anchor_crowd_level",
            "anchor_crowd_signal",
            "anchor_city_demand_score",
            "recommendation_count",
            "top_alternative_name",
            "top_crowd_relief",
            "top_similarity",
            "top_practicality",
            "top_distance_to_anchor_km",
        ]
    ].copy()
    for col in ["anchor_crowd_signal", "anchor_city_demand_score", "top_crowd_relief", "top_similarity", "top_practicality", "top_distance_to_anchor_km"]:
        display_df[col] = display_df[col].map(_fmt_float)
    overview.extend(_markdown_table(display_df))
    overview.append("")

    path.write_text("\n".join(overview), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    anchor_df = load_anchor_table(POI_TABLE_PATH)
    periods = build_periods()
    case_df = evaluate_anchor_periods(anchor_df, periods)
    summary = build_summary(case_df)

    case_df.to_csv(CSV_OUTPUT_PATH, index=False)
    JSON_OUTPUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(MD_OUTPUT_PATH, case_df, summary)

    print("Saved recommendation evaluation CSV to:", CSV_OUTPUT_PATH)
    print("Saved recommendation evaluation Markdown to:", MD_OUTPUT_PATH)
    print("Saved recommendation evaluation JSON to:", JSON_OUTPUT_PATH)
    print()
    print(
        case_df[
            [
                "anchor_name",
                "basis_week_start",
                "anchor_crowd_level",
                "recommendation_count",
                "top_alternative_name",
                "top_crowd_relief",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
