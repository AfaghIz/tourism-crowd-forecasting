"""
Run the full recommendation pipeline with an Istanbul sample point and print top results.

Usage (from ``backend-python``):

    .venv\\Scripts\\activate
    python pipeline_demo.py
"""

from __future__ import annotations

import textwrap
from typing import Any


def _fmt_item(idx: int, item: dict[str, Any], width: int = 88) -> str:
    name = item.get("name", "?")
    score = item.get("score")
    score_s = f"{float(score):.4f}" if score is not None else "n/a"
    km = item.get("distance_km")
    km_s = str(km) if km is not None else "n/a"
    cat = item.get("category", "?")
    crowd = item.get("crowd_level_label", "?")
    expl = item.get("explanation") or item.get("explanation_text", "")
    pid = item.get("poi_id", "")
    lat = item.get("lat")
    lng = item.get("lng")
    ll = (
        f"{lat}, {lng}"
        if lat is not None and lng is not None
        else "n/a"
    )

    lines = [
        f"  #{idx}  {name}",
        f"       poi_id: {pid or 'n/a'}",
        f"       score: {score_s}   distance_km: {km_s}   category: {cat}   crowd: {crowd}",
        f"       lat/lng: {ll}",
        "",
        "       Explanation:",
    ]
    wrapped = textwrap.fill(expl, width=width, subsequent_indent="       ")
    lines.append(wrapped)
    return "\n".join(lines)


def main() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    from recommendation.pipeline import recommend

    # Sultanahmet — representative tourist origin (walking distance to major sights)
    origin_lat = 41.0086
    origin_lon = 28.9802

    print()
    print("=" * 72)
    print("  Recommendation pipeline demo — Istanbul")
    print("=" * 72)
    print(f"  Origin: lat={origin_lat}, lon={origin_lon}")
    print("  Radius: 5 km   Top: 5")
    print("=" * 72)
    print()

    results = recommend(
        origin_lat,
        origin_lon,
        radius_km=5.0,
        top_k=5,
    )

    items = results.get("recommendations", [])
    if not items:
        print("  No recommendations (empty candidate set). Check CSV path and radius.")
        print()
        return

    print(f"  Returned {len(items)} recommendation(s).\n")

    for i, item in enumerate(items, start=1):
        print(_fmt_item(i, item))
        print()
        print("-" * 72)
        print()

    print("Done.")
    print()


if __name__ == "__main__":
    main()
