"""
Multi-stop itinerary construction from a ranked POI list.

Uses greedy nearest-neighbor routing with optional geographic clustering, detour penalties,
trip-style presets (fast vs explore), and optional rest/break stops (café-like POIs).

Routing internals can be swapped for OR-Tools later without changing :func:`generate_itinerary`.
"""

from __future__ import annotations

from typing import Any, Final, Literal

import numpy as np
import pandas as pd

from recommendation.data_loader import COL_CATEGORY, COL_LAT, COL_LON
from recommendation.geo import haversine_km

COL_DISPLAY_NAME: Final[str] = "display_name_en"
COL_NAME: Final[str] = "name"
COL_POI_ID: Final[str] = "poi_id"

_DEFAULT_TRAVEL_SPEED_KMH: Final[float] = 4.5

# Default substring hints for rest stops (category_clean or name).
_DEFAULT_BREAK_KEYWORDS: Final[tuple[str, ...]] = (
    "cafe",
    "coffee",
    "restaurant",
    "food",
    "bakery",
    "bar",
    "bistro",
    "tea",
    "brunch",
    "dining",
)

TripStyle = Literal["fast", "explore"]


def travel_time_hours(distance_km: float, speed_kmh: float) -> float:
    """Convert ground distance to travel time in hours."""
    if speed_kmh <= 0 or not np.isfinite(speed_kmh):
        raise ValueError("travel_speed_kmh must be positive and finite.")
    return float(max(distance_km, 0.0)) / float(speed_kmh)


def _pick_row_name(row: pd.Series) -> str:
    for key in (COL_DISPLAY_NAME, COL_NAME):
        if key in row.index:
            v = row[key]
            if v is not None and str(v).strip():
                return str(v).strip()
    pid = row.get(COL_POI_ID)
    if pid is not None and str(pid).strip():
        return str(pid).strip()
    return "POI"


def _validate_origin(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise ValueError("origin_lat / origin_lon must be valid WGS84 degrees.")


def _cluster_lat_lon_kmeans(
    lat: np.ndarray,
    lon: np.ndarray,
    k: int,
    *,
    rng: np.random.Generator | None = None,
    max_iter: int = 40,
) -> np.ndarray:
    """
    Simple k-means on (lat, lon) — adequate for city-scale grouping without sklearn.
    Returns integer labels ``0 .. k-1``.
    """
    n = lat.shape[0]
    k = max(1, min(int(k), n))
    rng = rng or np.random.default_rng(42)
    xy = np.column_stack([lat, lon])
    idx = rng.choice(n, size=k, replace=False)
    centroids = xy[idx].copy()

    labels = np.zeros(n, dtype=np.int32)
    for _ in range(max_iter):
        for i in range(n):
            d2 = np.sum((centroids - xy[i]) ** 2, axis=1)
            labels[i] = int(np.argmin(d2))
        new_c = np.empty_like(centroids)
        for j in range(k):
            mask = labels == j
            if np.any(mask):
                new_c[j] = xy[mask].mean(axis=0)
            else:
                new_c[j] = centroids[j]
        if np.allclose(new_c, centroids):
            break
        centroids = new_c
    return labels


def _order_clusters_from_origin(
    labels: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    origin_lat: float,
    origin_lon: float,
) -> list[int]:
    """Visit cluster whose centroid is closest to origin first, then next closest, …"""
    k = int(labels.max()) + 1 if labels.size else 0
    centroids = []
    for j in range(k):
        mask = labels == j
        if np.any(mask):
            centroids.append(
                (float(lat[mask].mean()), float(lon[mask].mean()))
            )
        else:
            centroids.append((origin_lat, origin_lon))
    dists = [
        haversine_km(origin_lat, origin_lon, c[0], c[1]) for c in centroids
    ]
    return sorted(range(len(dists)), key=lambda i: dists[i])


def _row_is_break_stop(
    row: pd.Series,
    keywords: tuple[str, ...],
    category_column: str,
) -> bool:
    blob = ""
    if category_column in row.index and pd.notna(row[category_column]):
        blob += str(row[category_column]).lower()
    blob += " " + _pick_row_name(row).lower()
    return any(kw in blob for kw in keywords)


def _effective_hop_cost(
    hop_km: float,
    median_neighbor_km: float,
    detour_penalty: float,
) -> float:
    """Penalize hops much longer than the typical neighbor distance (detour discouragement)."""
    if detour_penalty <= 0:
        return hop_km
    med = max(median_neighbor_km, 0.05)
    ratio = hop_km / med
    excess = max(0.0, ratio - 1.0)
    return hop_km * (1.0 + float(detour_penalty) * excess * excess)


def greedy_nearest_neighbor_route(
    origin_lat: float,
    origin_lon: float,
    candidates: list[tuple[int, float, float, pd.Series]],
    *,
    time_budget_hours: float,
    avg_time_per_poi: float,
    travel_speed_kmh: float,
    detour_penalty: float = 0.0,
    cluster_sequence: list[list[tuple[int, float, float, pd.Series]]] | None = None,
    break_visit_hours: float | None = None,
    break_keywords: tuple[str, ...] | None = None,
    category_column: str = COL_CATEGORY,
    prefer_break_after_visits: int = 0,
) -> tuple[list[tuple[float, float, float, pd.Series, str, int | None]], float, float]:
    """
    Greedy NN under time budget.

    If ``cluster_sequence`` is set, each inner list is exhausted (in order) before the next
    cluster — geographic batching before routing.

    Each segment tuple adds ``stop_kind`` (``\"visit\"`` | ``\"break\"``) and ``cluster_id``.
    """
    remaining = float(time_budget_hours)
    if remaining <= 0 or not np.isfinite(remaining):
        return [], 0.0, 0.0

    break_kw = break_keywords if break_keywords is not None else _DEFAULT_BREAK_KEYWORDS
    break_visit = float(break_visit_hours) if break_visit_hours is not None else None

    pools: list[list[tuple[int, float, float, pd.Series]]]
    cluster_ids: list[int | None]
    if cluster_sequence:
        pools = [list(p) for p in cluster_sequence]
        cluster_ids = list(range(len(pools)))
    else:
        pools = [list(candidates)]
        cluster_ids = [None]

    current_lat, current_lon = float(origin_lat), float(origin_lon)
    segments: list[tuple[float, float, float, pd.Series, str, int | None]] = []
    total_km = 0.0
    visits_since_break = 0

    for ci, pool in enumerate(pools):
        cid = cluster_ids[ci] if ci < len(cluster_ids) else None
        while pool and remaining > 1e-12:
            # Median hop distance from current to remaining pool — scales detour penalty.
            hop_lens: list[float] = []
            for _, plat, plon, _ in pool:
                hop_lens.append(
                    haversine_km(current_lat, current_lon, plat, plon)
                )
            median_hop = (
                float(np.median(hop_lens))
                if hop_lens
                else 0.5
            )

            want_break = (
                prefer_break_after_visits > 0
                and break_visit is not None
                and visits_since_break >= prefer_break_after_visits
            )

            search_modes = [True, False] if want_break else [False]
            best_j = None
            best_tt = 0.0
            best_dist = 0.0
            best_orig = np.inf
            best_cost = np.inf
            best_break = False

            for break_only_pass in search_modes:
                for j, (orig_idx, plat, plon, row) in enumerate(pool):
                    d_km = haversine_km(current_lat, current_lon, plat, plon)
                    is_br = _row_is_break_stop(row, break_kw, category_column)
                    if break_only_pass and not is_br:
                        continue
                    if break_only_pass:
                        visit_h = float(break_visit) if break_visit is not None else float(avg_time_per_poi)
                    else:
                        visit_h = float(avg_time_per_poi)
                    cost = _effective_hop_cost(d_km, median_hop, detour_penalty)
                    tt = travel_time_hours(d_km, travel_speed_kmh)
                    need = tt + visit_h
                    if need > remaining + 1e-9:
                        continue
                    adj_cost = cost * (0.9 if is_br else 1.0)
                    if adj_cost < best_cost - 1e-15 or (
                        abs(adj_cost - best_cost) <= 1e-15 and orig_idx < best_orig
                    ):
                        best_cost = adj_cost
                        best_tt = tt
                        best_dist = d_km
                        best_orig = orig_idx
                        best_j = j
                        best_break = bool(break_only_pass and is_br)
                if best_j is not None:
                    break

            if best_j is None:
                break

            orig_idx, plat, plon, row = pool.pop(best_j)
            visit_use = (
                float(break_visit)
                if best_break and break_visit is not None
                else float(avg_time_per_poi)
            )
            kind = "break" if best_break else "visit"
            segments.append((best_tt, visit_use, best_dist, row, kind, cid))
            total_km += best_dist
            remaining -= best_tt + visit_use
            current_lat, current_lon = plat, plon
            if kind == "break":
                visits_since_break = 0
            else:
                visits_since_break += 1

    total_time = float(time_budget_hours) - remaining
    return segments, total_km, total_time


def generate_itinerary(
    pois_df: pd.DataFrame,
    origin_lat: float,
    origin_lon: float,
    time_budget_hours: float,
    *,
    avg_time_per_poi: float = 1.0,
    travel_speed_kmh: float = _DEFAULT_TRAVEL_SPEED_KMH,
    lat_column: str = COL_LAT,
    lon_column: str = COL_LON,
    # --- upgrades (defaults preserve legacy behaviour) ---
    detour_penalty: float = 0.0,
    cluster_before_route: bool = False,
    n_clusters: int | None = None,
    trip_style: TripStyle | None = None,
    include_break_stops: bool = False,
    break_visit_hours: float = 20.0 / 60.0,
    break_after_visits: int = 3,
    break_keywords: tuple[str, ...] | None = None,
    category_column: str = COL_CATEGORY,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """
    Build an ordered multi-stop plan from a ranked POI frame.

    Parameters
    ----------
    detour_penalty
        If ``> 0``, discourages unusually long hops vs the median candidate distance
        (quadratic excess term). Default ``0`` matches classic NN.
    cluster_before_route
        If ``True``, cluster POIs on the map (k-means on lat/lon), order clusters by
        proximity of their centroids to the origin, then run NN within each cluster.
    n_clusters
        Number of geographic clusters; ``None`` uses ``ceil(sqrt(n))`` clipped to ``[2, n]``.
    trip_style
        ``\"fast\"`` — higher effective speed, shorter visits, stronger detour penalty when
        ``detour_penalty`` / defaults apply. ``\"explore\"`` — slower pace, longer visits,
        milder detours. When ``cluster_before_route`` is ``True``, ``fast`` uses fewer clusters
        and ``explore`` uses more than the automatic default.
    include_break_stops
        When ``True`` and ``break_after_visits > 0``, periodically prefers POIs whose
        ``category_clean`` / name matches ``break_keywords`` (cafés, restaurants, …) with
        ``break_visit_hours`` dwell time.
    break_visit_hours
        Time at a rest stop (hours); default 20 minutes.
    break_after_visits
        Insert a break-oriented stop after this many **non-break** visits (``0`` disables).
    break_keywords
        Substrings matched against category + name (case-insensitive).

    Returns
    -------
    stops
        Each dict includes legacy fields plus optional ``stop_kind`` (``\"visit\"`` | ``\"break\"``)
        and ``cluster_id`` (``int`` when clustering is enabled).
    summary
        Adds ``n_clusters``, ``trip_style`` when applicable.
    """
    _validate_origin(origin_lat, origin_lon)
    if time_budget_hours <= 0 or not np.isfinite(time_budget_hours):
        raise ValueError("time_budget_hours must be positive and finite.")
    if avg_time_per_poi <= 0 or not np.isfinite(avg_time_per_poi):
        raise ValueError("avg_time_per_poi must be positive and finite.")

    eff_speed = float(travel_speed_kmh)
    eff_visit = float(avg_time_per_poi)
    eff_penalty = float(detour_penalty)
    eff_clusters_flag = bool(cluster_before_route)
    eff_k = n_clusters

    if trip_style == "fast":
        eff_speed *= 1.25
        eff_visit *= 0.8
        eff_penalty = max(eff_penalty * 1.5, 0.15)
    elif trip_style == "explore":
        eff_speed *= 0.88
        eff_visit *= 1.15
        eff_penalty = eff_penalty * 0.55 if eff_penalty > 0 else 0.06

    if pois_df.empty:
        return [], _empty_summary(trip_style)

    if lat_column not in pois_df.columns or lon_column not in pois_df.columns:
        raise ValueError(
            f"pois_df must include '{lat_column}' and '{lon_column}' for routing."
        )

    candidates: list[tuple[int, float, float, pd.Series]] = []
    for i, (_, row) in enumerate(pois_df.iterrows()):
        la = pd.to_numeric(row[lat_column], errors="coerce")
        lo = pd.to_numeric(row[lon_column], errors="coerce")
        if pd.isna(la) or pd.isna(lo):
            continue
        candidates.append((i, float(la), float(lo), row))

    if not candidates:
        return [], _empty_summary(trip_style)

    n = len(candidates)
    lat_a = np.array([c[1] for c in candidates], dtype=np.float64)
    lon_a = np.array([c[2] for c in candidates], dtype=np.float64)

    cluster_sequence: list[list[tuple[int, float, float, pd.Series]]] | None = None
    n_cl_out = 1

    if eff_clusters_flag and n >= 2:
        if eff_k is not None:
            k_use = max(2, min(int(eff_k), n))
        else:
            base = max(2, int(np.ceil(np.sqrt(n))))
            if trip_style == "fast":
                k_use = max(2, min(n, base // 2))
            elif trip_style == "explore":
                k_use = max(2, min(n, int(np.ceil(base * 1.45))))
            else:
                k_use = max(2, min(n, base))

        labels = _cluster_lat_lon_kmeans(lat_a, lon_a, k_use)
        order_ci = _order_clusters_from_origin(labels, lat_a, lon_a, origin_lat, origin_lon)
        k_labels = int(labels.max()) + 1 if labels.size else 0
        buckets: dict[int, list[tuple[int, float, float, pd.Series]]] = {
            j: [] for j in range(k_labels)
        }
        for idx, c in enumerate(candidates):
            buckets[int(labels[idx])].append(c)
        cluster_sequence = [
            buckets[j] for j in order_ci if buckets.get(j) and len(buckets[j]) > 0
        ]
        n_cl_out = len(cluster_sequence or [])
    else:
        eff_clusters_flag = False

    br_vis = float(break_visit_hours) if include_break_stops else None
    br_every = int(break_after_visits) if include_break_stops else 0

    segments, total_travel_km, total_time_hours = greedy_nearest_neighbor_route(
        origin_lat,
        origin_lon,
        candidates,
        time_budget_hours=time_budget_hours,
        avg_time_per_poi=eff_visit,
        travel_speed_kmh=eff_speed,
        detour_penalty=eff_penalty,
        cluster_sequence=cluster_sequence,
        break_visit_hours=br_vis,
        break_keywords=break_keywords,
        category_column=category_column,
        prefer_break_after_visits=br_every,
    )

    stops: list[dict[str, Any]] = []
    total_travel_hours = 0.0
    total_visit_hours = 0.0

    for order, (tt_prev, visit_h, _d_km, row, kind, cid) in enumerate(segments, start=1):
        total_travel_hours += tt_prev
        total_visit_hours += visit_h
        plat = float(pd.to_numeric(row[lat_column], errors="coerce"))
        plon = float(pd.to_numeric(row[lon_column], errors="coerce"))
        item: dict[str, Any] = {
            "order": order,
            "name": _pick_row_name(row),
            "lat": plat,
            "lon": plon,
            "visit_time_estimate": float(visit_h),
            "travel_time_from_prev": float(tt_prev),
            "stop_kind": kind,
        }
        pid = row.get(COL_POI_ID)
        if pid is not None and str(pid).strip():
            item[COL_POI_ID] = str(pid).strip()
        if cid is not None:
            item["cluster_id"] = int(cid)
        stops.append(item)

    summary = {
        "total_travel_km": float(total_travel_km),
        "total_travel_hours": float(total_travel_hours),
        "total_visit_hours": float(total_visit_hours),
        "total_time_hours": float(total_time_hours),
        "n_clusters": int(n_cl_out),
    }
    if trip_style is not None:
        summary["trip_style"] = trip_style
    return stops, summary


def _empty_summary(trip_style: TripStyle | None) -> dict[str, Any]:
    s: dict[str, Any] = {
        "total_travel_km": 0.0,
        "total_travel_hours": 0.0,
        "total_visit_hours": 0.0,
        "total_time_hours": 0.0,
        "n_clusters": 0,
    }
    if trip_style is not None:
        s["trip_style"] = trip_style
    return s
