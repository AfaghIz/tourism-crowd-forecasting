"""
Load and normalize OpenTripMap POI tables for downstream recommendation pipelines.

The source schema follows ``otm_pois_model_ready.csv`` column names; coordinate fields are
``lat`` and ``lon`` (WGS84). Callers that expect ``latitude``/``longitude`` should map
after loading or extend this module with explicit renames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pandas as pd

# --- Dataset column names (OTM export contract; change here if the CSV schema changes) ---

COL_LAT: Final[str] = "lat"
COL_LON: Final[str] = "lon"
COL_CATEGORY: Final[str] = "category_clean"
COL_RATE: Final[str] = "rate"
COL_POPULARITY: Final[str] = "wiki_popularity_score"

COL_MOCK_CROWD: Final[str] = "predicted_crowd_index_mock"
COL_RATE_NORM: Final[str] = "rate_normalized"
COL_POPULARITY_NORM: Final[str] = "wiki_popularity_normalized"
COL_EXCLUDE_FROM_PART_B: Final[str] = "exclude_from_part_b"

DEFAULT_CATEGORY_FILL: Final[str] = "unknown"


def load_poi_data(filepath: str) -> pd.DataFrame:
    """
    Load POI rows from a CSV file into a cleaned, analysis-ready DataFrame.

    Steps:

    1. Read CSV with UTF-8 encoding.
    2. Require valid numeric ``lat`` / ``lon``; rows with missing or non-numeric coordinates
       are dropped (coordinates cannot be imputed safely).
    3. Missing ``category_clean`` is filled with a neutral label (``unknown``).
    4. ``predicted_crowd_index_mock`` is added as a **deterministic** fallback (stable per
       ``poi_id``) used when no external model is registered; see :mod:`crowd_scores`.
    5. ``rate`` and ``wiki_popularity_score`` are coerced to numeric; missing rates are
       imputed with the column median before min–max scaling into ``rate_normalized`` and
       ``wiki_popularity_normalized`` (constant columns collapse to 0.5).

    Parameters
    ----------
    filepath
        Path to ``otm_pois_model_ready.csv`` or a compatible export.

    Returns
    -------
    pd.DataFrame
        A copy with cleaned coordinates, filled category, mock crowd column, and normalized
        numeric features. Original identifier and descriptive columns are preserved.

    Raises
    ------
    FileNotFoundError
        If ``filepath`` does not exist.
    ValueError
        If no rows remain after coordinate validation, or the file cannot be parsed as CSV.
    """
    path = Path(str(filepath)).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"POI CSV not found: {path}")

    df = pd.read_csv(path, encoding="utf-8")
    if df.empty:
        raise ValueError(f"No rows loaded from {path}")

    out = _clean_coordinates(df)
    if out.empty:
        raise ValueError(
            "No rows with valid latitude/longitude after cleaning; check coordinate columns."
        )

    out = _clean_category(out)
    out = _drop_excluded_rows(out)
    out = _add_mock_crowd_column(out)
    out = _add_normalized_features(out)

    return out.reset_index(drop=True)


def _clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce ``lat``/``lon`` to floats and drop rows with invalid or missing coordinates."""
    if COL_LAT not in df.columns or COL_LON not in df.columns:
        raise ValueError(
            f"Expected columns '{COL_LAT}' and '{COL_LON}' in POI table; got {list(df.columns)}"
        )

    work = df.copy()
    work[COL_LAT] = pd.to_numeric(work[COL_LAT], errors="coerce")
    work[COL_LON] = pd.to_numeric(work[COL_LON], errors="coerce")

    valid = work[COL_LAT].notna() & work[COL_LON].notna()
    # Drop obviously invalid WGS84 if present (optional guard; keeps bad rows out of maps)
    in_bounds = (
        (work[COL_LAT] >= -90.0)
        & (work[COL_LAT] <= 90.0)
        & (work[COL_LON] >= -180.0)
        & (work[COL_LON] <= 180.0)
    )
    work = work.loc[valid & in_bounds].copy()
    return work


def _clean_category(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing categories after stripping whitespace and lowercasing."""
    work = df.copy()
    if COL_CATEGORY not in work.columns:
        work[COL_CATEGORY] = DEFAULT_CATEGORY_FILL
    else:
        cat = work[COL_CATEGORY].astype("string").str.strip()
        cat = cat.replace("", pd.NA)
        work[COL_CATEGORY] = cat.fillna(DEFAULT_CATEGORY_FILL).str.lower()
    return work


def _drop_excluded_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove non-operational POIs when an explicit exclusion flag is available.

    The cleaned research dataset carries ``exclude_from_part_b`` for rows such as
    historical events and abstract entities that should not enter recommendation.
    """
    work = df.copy()
    if COL_EXCLUDE_FROM_PART_B not in work.columns:
        return work
    flag = pd.to_numeric(work[COL_EXCLUDE_FROM_PART_B], errors="coerce").fillna(0).astype(int)
    return work.loc[flag == 0].copy()


def _add_mock_crowd_column(df: pd.DataFrame) -> pd.DataFrame:
    """Append fallback crowd indices (deterministic per ``poi_id`` for reproducibility)."""
    from recommendation.crowd_scores import deterministic_fallback_score

    work = df.copy()
    if "poi_id" not in work.columns:
        work[COL_MOCK_CROWD] = 0.5
        return work
    work[COL_MOCK_CROWD] = work["poi_id"].astype("string").fillna("").map(
        lambda pid: deterministic_fallback_score(str(pid))
    )
    return work


def _add_normalized_features(df: pd.DataFrame) -> pd.DataFrame:
    """Min–max normalize ``rate`` and ``wiki_popularity_score`` into dedicated columns."""
    work = df.copy()

    work[COL_RATE_NORM] = _normalized_series(work, COL_RATE, impute="median")
    work[COL_POPULARITY_NORM] = _normalized_series(work, COL_POPULARITY, impute="zero")

    return work


def _normalized_series(
    df: pd.DataFrame,
    column: str,
    *,
    impute: str,
) -> pd.Series:
    """
    Return a 0–1 min–max scaled series for ``column``.

    Parameters
    ----------
    impute
        ``median`` — fill NaNs with median before scaling (for rates).
        ``zero`` — fill NaNs with 0 before scaling (sparse popularity signal).
    """
    if column not in df.columns:
        return pd.Series(0.5, index=df.index, dtype=float)

    raw = pd.to_numeric(df[column], errors="coerce")
    if impute == "median":
        fill = float(raw.median()) if raw.notna().any() else 0.0
        filled = raw.fillna(fill)
    elif impute == "zero":
        filled = raw.fillna(0.0)
    else:
        raise ValueError(f"Unknown impute strategy: {impute}")

    vmin = float(filled.min())
    vmax = float(filled.max())
    span = vmax - vmin
    if span <= 1e-12:
        return pd.Series(0.5, index=df.index, dtype=float)
    return (filled - vmin) / span
