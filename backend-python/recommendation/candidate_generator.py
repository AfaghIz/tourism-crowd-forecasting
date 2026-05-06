"""
Spatial filtering: attach great-circle distances from an origin and select POIs inside a radius.

Distances use the Haversine formula on the WGS84 sphere; computation is fully vectorized.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_LAT, COL_LON

COL_DISTANCE_KM: Final[str] = "distance_km"

_EARTH_RADIUS_KM: Final[float] = 6371.0


def haversine_km(
    origin_lat: float,
    origin_lon: float,
    lat: np.ndarray | pd.Series,
    lon: np.ndarray | pd.Series,
) -> np.ndarray:
    """
    Great-circle distance from one origin to many points (vectorized).

    Parameters
    ----------
    origin_lat, origin_lon
        Origin in decimal degrees (WGS84).
    lat, lon
        Target latitude/longitude arrays or Series (same length).

    Returns
    -------
    numpy.ndarray
        Distances in kilometers, shape ``(n,)``.
    """
    lat_arr = np.asarray(lat, dtype=np.float64)
    lon_arr = np.asarray(lon, dtype=np.float64)
    if lat_arr.shape != lon_arr.shape:
        raise ValueError("lat and lon must have the same shape")

    φ1 = np.radians(np.float64(origin_lat))
    λ1 = np.radians(np.float64(origin_lon))
    φ2 = np.radians(lat_arr)
    λ2 = np.radians(lon_arr)

    dφ = φ2 - φ1
    dλ = λ2 - λ1

    sin_dφ = np.sin(dφ / 2.0)
    sin_dλ = np.sin(dλ / 2.0)
    h = sin_dφ * sin_dφ + np.cos(φ1) * np.cos(φ2) * sin_dλ * sin_dλ
    h = np.clip(h, 0.0, 1.0)
    return _EARTH_RADIUS_KM * (2.0 * np.arcsin(np.sqrt(h)))


def get_candidates(
    df: pd.DataFrame,
    origin_lat: float,
    origin_lon: float,
    radius_km: float = 5.0,
    *,
    lat_column: str = COL_LAT,
    lon_column: str = COL_LON,
    distance_column: str = COL_DISTANCE_KM,
) -> pd.DataFrame:
    """
    Return POIs within ``radius_km`` of the origin, sorted by ascending distance.

    Appends a ``distance_km`` column (by default) with Haversine distance from
    ``(origin_lat, origin_lon)``. Does not mutate the input frame.

    Parameters
    ----------
    df
        Must contain latitude/longitude columns (defaults: ``lat``, ``lon``). Rows with
    non-numeric or missing coordinates are skipped.
    origin_lat, origin_lon
        Query point in decimal degrees (WGS84).
    radius_km
        Inclusion radius in kilometers; must be positive.
    lat_column, lon_column
        Column names for coordinates (override if your frame uses different names).
    distance_column
        Name of the added distance column.

    Returns
    -------
    pandas.DataFrame
        Filtered and sorted copy including ``distance_km``.

    Raises
    ------
    ValueError
        If ``radius_km`` is not positive, required columns are missing, or coordinates
        are invalid.
    """
    if radius_km <= 0:
        raise ValueError(f"radius_km must be positive, got {radius_km}")
    if not (-90.0 <= origin_lat <= 90.0) or not (-180.0 <= origin_lon <= 180.0):
        raise ValueError(
            "origin_lat must be in [-90, 90] and origin_lon in [-180, 180] (degrees)."
        )
    if lat_column not in df.columns or lon_column not in df.columns:
        raise ValueError(
            f"DataFrame must include '{lat_column}' and '{lon_column}' columns."
        )

    if df.empty:
        out = df.copy()
        out[distance_column] = pd.Series(dtype=np.float64)
        return out

    lat_s = pd.to_numeric(df[lat_column], errors="coerce")
    lon_s = pd.to_numeric(df[lon_column], errors="coerce")
    valid = lat_s.notna() & lon_s.notna()
    base = df.loc[valid].copy()
    lat_s = lat_s.loc[valid]
    lon_s = lon_s.loc[valid]

    if base.empty:
        base[distance_column] = pd.Series(dtype=np.float64)
        return base

    dist = haversine_km(origin_lat, origin_lon, lat_s.to_numpy(), lon_s.to_numpy())

    out = base
    out[distance_column] = dist

    within = out[out[distance_column] <= radius_km].sort_values(
        distance_column,
        ascending=True,
        kind="mergesort",
    )
    return within.reset_index(drop=True)
