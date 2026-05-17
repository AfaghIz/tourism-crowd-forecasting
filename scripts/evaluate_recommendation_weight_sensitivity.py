from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend-python"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from forecast_service import ForecastService  # noqa: E402
from recommendation import alternatives as alt_module  # noqa: E402
from recommendation.explanation_engine import crowd_level_label  # noqa: E402
from recommendation.pipeline import recommend  # noqa: E402
from weekly_model import IstanbulWeeklyModelRepository  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
CSV_OUTPUT_PATH = OUTPUT_DIR / "recommendation_weight_sensitivity.csv"
MD_OUTPUT_PATH = OUTPUT_DIR / "recommendation_weight_sensitivity.md"
JSON_OUTPUT_PATH = OUTPUT_DIR / "recommendation_weight_sensitivity_summary.json"
POI_TABLE_PATH = PROJECT_ROOT / "data" / "processed" / "otm_pois_model_ready_with_nlp_features_exclusions.csv"

ANCHOR_SPECS: list[dict[str, str]] = [
    {"poi_id": "otm_R1555271", "name": "Hagia Sophia"},
    {"poi_id": "otm_N7294561685", "name": "Chora Mosque / Kariye Museum"},
    {"poi_id": "otm_W23236783", "name": "Galata Tower"},
    {"poi_id": "otm_N7215645385", "name": "The Blue Mosque"},
    {"poi_id": "otm_R1564032", "name": "Süleymaniye Mosque"},
    {"poi_id": "otm_R7318154", "name": "Rumeli Fortress"},
]

WEIGHT_POLICIES: list[dict[str, Any]] = [
    {
        "policy_id": "implemented_dynamic",
        "label": "Implemented dynamic policy",
        "description": "Current demand-aware policy used in the app.",
        "mode": "dynamic",
    },
    {
        "policy_id": "crowd_heavy_fixed",
        "label": "Crowd-heavy fixed policy",
        "description": "Strongly prioritizes crowd relief in every period.",
        "mode": "fixed",
        "weights": {"crowd_relief": 0.60, "similarity": 0.25, "practicality": 0.15},
    },
    {
        "policy_id": "balanced_fixed",
        "label": "Balanced fixed policy",
        "description": "Keeps crowd relief highest but gives more room to similarity and practicality.",
        "mode": "fixed",
        "weights": {"crowd_relief": 0.45, "similarity": 0.35, "practicality": 0.20},
    },
    {
        "policy_id": "similarity_practicality_fixed",
        "label": "Similarity-practicality fixed policy",
        "description": "Places more emphasis on preserving the experience and geographic feasibility.",
        "mode": "fixed",
        "weights": {"crowd_relief": 0.30, "similarity": 0.40, "practicality": 0.30},
    },
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


def _with_weight_policy(policy: dict[str, Any], fn: Callable[[], Any]) -> Any:
    original = alt_module.choose_alternative_weights
    try:
        if policy["mode"] == "fixed":
            fixed_weights = dict(policy["weights"])

            def fixed_policy(_: float) -> dict[str, float]:
                return fixed_weights

            alt_module.choose_alternative_weights = fixed_policy
        return fn()
    finally:
        alt_module.choose_alternative_weights = original


def evaluate_policies(anchor_df: pd.DataFrame, periods: list[dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in ANCHOR_SPECS:
        match = anchor_df.loc[anchor_df["poi_id"] == spec["poi_id"]]
        if match.empty:
            raise ValueError(f"Anchor POI not found: {spec['poi_id']} ({spec['name']})")
        anchor_row = match.iloc[0]
        origin_lat = float(anchor_row["lat"])
        origin_lon = float(anchor_row["lon"])

        for period in periods:
            basis_week_start = period["basis_week_start"]
            timestamp = pd.Timestamp(f"{basis_week_start}T12:00:00").to_pydatetime()

            for policy in WEIGHT_POLICIES:
                def run_case() -> dict[str, Any]:
                    return recommend(
                        origin_lat,
                        origin_lon,
                        timestamp=timestamp,
                        radius_km=6.0,
                        top_k=5,
                        anchor_poi_id=spec["poi_id"],
                        anchor_radius_km=3.0,
                    )

                result = _with_weight_policy(policy, run_case)
                anchor_payload = result.get("anchor") or {}
                recommendations = list(result.get("recommendations") or [])
                top = recommendations[0] if recommendations else {}
                top3_ids = [
                    str(item.get("poi_id")).strip()
                    for item in recommendations[:3]
                    if item.get("poi_id") is not None and str(item.get("poi_id")).strip()
                ]
                anchor_crowd_signal = _to_float(anchor_payload.get("crowd_signal"))

                rows.append(
                    {
                        "policy_id": policy["policy_id"],
                        "policy_label": policy["label"],
                        "policy_description": policy["description"],
                        "anchor_poi_id": spec["poi_id"],
                        "anchor_name": str(anchor_row["anchor_name"]),
                        "basis_week_start": basis_week_start,
                        "basis_label": period["basis_label"],
                        "basis_level": period["basis_level"],
                        "anchor_crowd_signal": anchor_crowd_signal,
                        "anchor_crowd_level": crowd_level_label(anchor_crowd_signal).title() if anchor_crowd_signal is not None else period["basis_level"],
                        "recommendation_count": int(len(recommendations)),
                        "top_alternative_poi_id": top.get("poi_id"),
                        "top_alternative_name": top.get("name"),
                        "top3_alternative_poi_ids": json.dumps(top3_ids, ensure_ascii=False),
                        "top_alternative_score": _to_float(top.get("score")),
                        "top_crowd_relief": _to_float(top.get("crowd_relief")),
                        "top_similarity": _to_float(top.get("similarity")),
                        "top_practicality": _to_float(top.get("practicality")),
                        "top_distance_to_anchor_km": _to_float(top.get("distance_to_anchor_km")),
                    }
                )
    return pd.DataFrame(rows)


def _parse_id_list(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        loaded = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(x).strip() for x in loaded if str(x).strip()]


def _overlap_rate(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    aset = set(a)
    bset = set(b)
    return len(aset & bset) / float(max(len(aset), len(bset)))


def _top1_rank_in_list(top1_id: str | None, ranked_ids: list[str]) -> int | None:
    if top1_id is None:
        return None
    target = str(top1_id).strip()
    if not target:
        return None
    try:
        return ranked_ids.index(target) + 1
    except ValueError:
        return None


def build_summary(df: pd.DataFrame) -> dict[str, Any]:
    baseline = df.loc[df["policy_id"] == "implemented_dynamic"].copy()
    summary_rows: list[dict[str, Any]] = []
    for policy in WEIGHT_POLICIES:
        policy_id = policy["policy_id"]
        subset = df.loc[df["policy_id"] == policy_id].copy()
        if subset.empty:
            continue

        merged = subset.merge(
            baseline[
                [
                    "anchor_poi_id",
                    "basis_week_start",
                    "top_alternative_poi_id",
                    "top3_alternative_poi_ids",
                    "recommendation_count",
                ]
            ].rename(
                columns={
                    "top_alternative_poi_id": "baseline_top_alternative_poi_id",
                    "top3_alternative_poi_ids": "baseline_top3_alternative_poi_ids",
                    "recommendation_count": "baseline_recommendation_count",
                }
            ),
            on=["anchor_poi_id", "basis_week_start"],
            how="left",
        )
        same_top = merged["top_alternative_poi_id"].eq(merged["baseline_top_alternative_poi_id"])
        top3_overlap = [
            _overlap_rate(
                _parse_id_list(row["top3_alternative_poi_ids"]),
                _parse_id_list(row["baseline_top3_alternative_poi_ids"]),
            )
            for _, row in merged.iterrows()
        ]
        baseline_top1_rank_under_policy = [
            _top1_rank_in_list(
                row["baseline_top_alternative_poi_id"],
                _parse_id_list(row["top3_alternative_poi_ids"]),
            )
            for _, row in merged.iterrows()
        ]
        rank_changed = [
            rank is None or rank != 1
            for rank in baseline_top1_rank_under_policy
        ]
        summary_rows.append(
            {
                "policy_id": policy_id,
                "policy_label": policy["label"],
                "coverage_rate": float((subset["recommendation_count"] > 0).mean()),
                "average_recommendation_count": float(subset["recommendation_count"].mean()),
                "average_top_crowd_relief": float(subset["top_crowd_relief"].mean()),
                "average_top_similarity": float(subset["top_similarity"].mean()),
                "average_top_practicality": float(subset["top_practicality"].mean()),
                "average_top_distance_to_anchor_km": float(subset["top_distance_to_anchor_km"].mean()),
                "top1_match_rate_vs_implemented": float(same_top.mean()) if len(merged) else 0.0,
                "changed_top1_cases_vs_implemented": int((~same_top).sum()) if len(merged) else 0,
                "average_top3_overlap_vs_implemented": float(sum(top3_overlap) / len(top3_overlap)) if top3_overlap else 0.0,
                "baseline_top1_rank_changed_cases": int(sum(rank_changed)) if rank_changed else 0,
            }
        )

    return {
        "total_cases_per_policy": int(len(ANCHOR_SPECS) * len(df["basis_week_start"].dropna().unique())),
        "policies": summary_rows,
    }


def _fmt_float(value: Any, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return f"{float(value):.{digits}f}"


def write_markdown(path: Path, df: pd.DataFrame, summary: dict[str, Any]) -> None:
    summary_df = pd.DataFrame(summary["policies"]).copy()
    if not summary_df.empty:
        summary_df["coverage_rate"] = summary_df["coverage_rate"].map(lambda v: f"{float(v):.2%}")
        summary_df["top1_match_rate_vs_implemented"] = summary_df["top1_match_rate_vs_implemented"].map(lambda v: f"{float(v):.2%}")
        summary_df["average_top3_overlap_vs_implemented"] = summary_df["average_top3_overlap_vs_implemented"].map(lambda v: f"{float(v):.2%}")
        for col in [
            "average_recommendation_count",
            "average_top_crowd_relief",
            "average_top_similarity",
            "average_top_practicality",
            "average_top_distance_to_anchor_km",
        ]:
            summary_df[col] = summary_df[col].map(_fmt_float)

    lines = [
        "# Recommendation Weight Sensitivity",
        "",
        "This analysis checks whether small policy changes to the anchor-based alternative ranking weights substantially alter recommendation behavior.",
        "",
        "Interpreting the results:",
        "- A high top-1 match rate means the chosen policy is not highly fragile relative to nearby alternatives.",
        "- A high top-3 overlap means the broader short list remains stable even when the exact policy changes.",
        "- Few baseline top-1 rank changes mean the implemented winner is not easily displaced under nearby policies.",
        "- Similar average crowd relief, similarity, and practicality values suggest that the overall recommendation behavior remains coherent across policy variants.",
        "",
    ]

    if not summary_df.empty:
        header = "| " + " | ".join(summary_df.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(summary_df.columns)) + " |"
        rows = [
            "| " + " | ".join(str(v) for v in row) + " |"
            for row in summary_df.itertuples(index=False, name=None)
        ]
        lines.extend(["## Policy Summary", "", header, separator, *rows, ""])

    baseline = df.loc[
        df["policy_id"] == "implemented_dynamic",
        ["anchor_name", "basis_week_start", "top_alternative_name", "top3_alternative_poi_ids"],
    ].rename(
        columns={
            "top_alternative_name": "implemented_top_alternative",
            "top3_alternative_poi_ids": "implemented_top3_ids",
        }
    )
    comparison = df.loc[df["policy_id"] != "implemented_dynamic", [
        "policy_label",
        "anchor_name",
        "basis_week_start",
        "top_alternative_name",
        "top3_alternative_poi_ids",
    ]].merge(baseline, on=["anchor_name", "basis_week_start"], how="left")
    comparison = comparison.rename(
        columns={
            "top_alternative_name": "policy_top_alternative",
            "top3_alternative_poi_ids": "policy_top3_ids",
        }
    )
    comparison["top3_overlap_rate"] = [
        _overlap_rate(_parse_id_list(a), _parse_id_list(b))
        for a, b in zip(comparison["policy_top3_ids"], comparison["implemented_top3_ids"])
    ]
    comparison["implemented_top1_rank_under_policy"] = [
        _top1_rank_in_list(
            top1_id,
            _parse_id_list(policy_top3),
        )
        for top1_id, policy_top3 in zip(comparison["implemented_top_alternative"], comparison["policy_top3_ids"])
    ]
    comparison["top3_overlap_rate"] = comparison["top3_overlap_rate"].map(lambda v: f"{float(v):.2%}")

    if not comparison.empty:
        lines.extend(["## Top-1 Comparison", ""])
        header = "| " + " | ".join(comparison.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(comparison.columns)) + " |"
        rows = [
            "| " + " | ".join("" if (isinstance(v, float) and pd.isna(v)) else str(v) for v in row) + " |"
            for row in comparison.itertuples(index=False, name=None)
        ]
        lines.extend([header, separator, *rows, ""])

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    anchor_df = load_anchor_table(POI_TABLE_PATH)
    periods = build_periods()
    df = evaluate_policies(anchor_df, periods)
    summary = build_summary(df)

    df.to_csv(CSV_OUTPUT_PATH, index=False)
    JSON_OUTPUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_markdown(MD_OUTPUT_PATH, df, summary)

    print("Saved weight sensitivity CSV to:", CSV_OUTPUT_PATH)
    print("Saved weight sensitivity Markdown to:", MD_OUTPUT_PATH)
    print("Saved weight sensitivity JSON to:", JSON_OUTPUT_PATH)
    print()
    print(pd.DataFrame(summary["policies"]).to_string(index=False))


if __name__ == "__main__":
    main()
