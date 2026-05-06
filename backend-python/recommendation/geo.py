from __future__ import annotations

import math

import numpy as np

_EARTH_R_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometers."""
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def pairwise_haversine_km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """
    Pairwise great-circle distances between ``n`` WGS84 points (symmetric ``(n, n)`` km).

    Parameters
    ----------
    lat, lon
        Length-``n`` arrays in decimal degrees.

    Returns
    -------
    numpy.ndarray
        Shape ``(n, n)``, ``[i, j]`` is distance from point ``i`` to ``j``.
    """
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    φ1 = np.radians(lat[:, np.newaxis])
    φ2 = np.radians(lat[np.newaxis, :])
    dφ = φ2 - φ1
    λ1 = np.radians(lon[:, np.newaxis])
    λ2 = np.radians(lon[np.newaxis, :])
    dλ = λ2 - λ1
    h = np.sin(dφ / 2.0) ** 2 + np.cos(φ1) * np.cos(φ2) * np.sin(dλ / 2.0) ** 2
    h = np.clip(h, 0.0, 1.0)
    return _EARTH_R_KM * (2.0 * np.arcsin(np.sqrt(h)))
