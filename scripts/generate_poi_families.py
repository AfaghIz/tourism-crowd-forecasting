#!/usr/bin/env python3
"""Generate tourism-experience family features for POIs.

This script adds a lightweight semantic middle layer between coarse
category labels and fine-grained subtype flags. The resulting family
features are reused in both Part B modeling and recommendation
compatibility.
"""

from __future__ import annotations

from pathlib import Path
import time

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data" / "processed" / "otm_pois_model_ready_with_nlp_features.csv"
EXCLUSIONS_PATH = ROOT / "data" / "processed" / "otm_pois_model_ready_with_nlp_features_exclusions.csv"
MODELING_PATH = ROOT / "data" / "processed" / "otm_part_b_modeling_table.csv"

FAMILY_COLUMNS = [
    "family_iconic_landmark",
    "family_religious_monumental",
    "family_museum_cultural",
    "family_viewpoint_scenic",
    "family_palatial_imperial",
    "family_neighborhood_heritage",
]

RELIGIOUS_COLUMNS = ["is_mosque", "is_church", "is_synagogue", "is_cathedral"]
VIEWPOINT_COLUMNS = ["is_tower", "is_bridge", "is_fortress"]
NEIGHBORHOOD_HERITAGE_COLUMNS = [
    "is_gate",
    "is_fountain",
    "is_monument",
    "is_hamam",
    "is_tomb",
    "is_cemetery",
]
SUBTYPE_COLUMNS = [
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
]


def _ensure_binary(series: pd.Series) -> pd.Series:
    return series.fillna(0).astype(int).clip(lower=0, upper=1)


def build_family_features(df: pd.DataFrame) -> pd.DataFrame:
    """Assign reusable tourism-experience families from existing POI features."""
    out = df.copy()

    category = out.get("category_clean", pd.Series("", index=out.index)).fillna("").astype(str).str.lower()
    wiki_pageviews_total = pd.to_numeric(out.get("wiki_pageviews_total", 0), errors="coerce").fillna(0)
    rate = pd.to_numeric(out.get("rate", 0), errors="coerce").fillna(0)

    subtype_total = pd.DataFrame(
        {col: _ensure_binary(out.get(col, 0)) for col in SUBTYPE_COLUMNS},
        index=out.index,
    ).sum(axis=1)

    has_structural_tourism_signal = category.isin({"museum", "historic", "religious", "attraction"}) | subtype_total.gt(0)
    prominence_signal = wiki_pageviews_total.ge(20_000) | rate.ge(7)

    out["family_iconic_landmark"] = (has_structural_tourism_signal & prominence_signal).astype(int)
    out["family_religious_monumental"] = pd.DataFrame(
        {col: _ensure_binary(out.get(col, 0)) for col in RELIGIOUS_COLUMNS},
        index=out.index,
    ).max(axis=1)
    out["family_museum_cultural"] = (category.eq("museum") | _ensure_binary(out.get("is_museum", 0)).eq(1)).astype(int)
    out["family_viewpoint_scenic"] = pd.DataFrame(
        {col: _ensure_binary(out.get(col, 0)) for col in VIEWPOINT_COLUMNS},
        index=out.index,
    ).max(axis=1)
    out["family_palatial_imperial"] = _ensure_binary(out.get("is_palace", 0))
    out["family_neighborhood_heritage"] = (
        category.eq("historic")
        | pd.DataFrame(
            {col: _ensure_binary(out.get(col, 0)) for col in NEIGHBORHOOD_HERITAGE_COLUMNS},
            index=out.index,
        ).max(axis=1).eq(1)
    ).astype(int)

    for col in FAMILY_COLUMNS:
        out[col] = _ensure_binary(out[col])

    return out


def propagate_family_columns(master_df: pd.DataFrame, target_path: Path) -> None:
    target_df = pd.read_csv(target_path)
    family_lookup = master_df[["poi_id", *FAMILY_COLUMNS]].copy()
    merged = target_df.drop(columns=FAMILY_COLUMNS, errors="ignore").merge(family_lookup, on="poi_id", how="left")
    for col in FAMILY_COLUMNS:
        merged[col] = _ensure_binary(merged[col])
    merged.to_csv(target_path, index=False)


def main() -> None:
    start = time.perf_counter()

    master_df = pd.read_csv(MASTER_PATH)
    master_df = build_family_features(master_df)
    master_df.to_csv(MASTER_PATH, index=False)

    propagate_family_columns(master_df, EXCLUSIONS_PATH)
    propagate_family_columns(master_df, MODELING_PATH)

    elapsed = time.perf_counter() - start
    print(f"Updated family features in {elapsed:.3f}s")
    print("Row count:", len(master_df))
    print("Family counts:")
    print(master_df[FAMILY_COLUMNS].sum().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
