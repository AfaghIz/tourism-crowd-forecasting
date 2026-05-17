from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "otm_crowdindex_xgb__rf_weekly.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
OUTPUT_PNG = OUTPUT_DIR / "part_a_part_b_poi_map_latest.png"
OUTPUT_CSV = OUTPUT_DIR / "part_a_part_b_poi_map_latest.csv"
FONT_REGULAR = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _color(value: float) -> tuple[int, int, int]:
    palette = [
        (255, 245, 204),
        (254, 204, 92),
        (253, 141, 60),
        (227, 26, 28),
        (128, 0, 38),
    ]
    x = max(0.0, min(100.0, float(value))) / 100.0
    scaled = x * (len(palette) - 1)
    idx = min(int(scaled), len(palette) - 2)
    t = scaled - idx
    c0, c1 = palette[idx], palette[idx + 1]
    return tuple(_lerp(c0[i], c1[i], t) for i in range(3))


def main() -> None:
    df = pd.read_csv(INPUT_CSV, parse_dates=["date"])
    required = {
        "poi_id",
        "display_name_en",
        "category_clean",
        "query_area",
        "lat",
        "lon",
        "date",
        "crowdindex_poi",
        "city_demand_score",
        "poi_weight_value",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    latest_date = df["date"].max()
    latest = df.loc[df["date"] == latest_date].copy()
    latest["lat"] = pd.to_numeric(latest["lat"], errors="coerce")
    latest["lon"] = pd.to_numeric(latest["lon"], errors="coerce")
    latest["crowdindex_poi"] = pd.to_numeric(latest["crowdindex_poi"], errors="coerce")
    latest = latest.dropna(subset=["lat", "lon", "crowdindex_poi"])
    latest = latest.sort_values("crowdindex_poi", ascending=False).reset_index(drop=True)
    latest["crowd_pressure_100"] = (
        latest["crowdindex_poi"] / max(float(latest["crowdindex_poi"].max()), 1e-12) * 100.0
    ).round(2)

    output_cols = [
        "date",
        "poi_id",
        "display_name_en",
        "category_clean",
        "query_area",
        "lat",
        "lon",
        "crowdindex_poi",
        "crowd_pressure_100",
        "city_demand_score",
        "poi_weight_value",
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest[output_cols].to_csv(OUTPUT_CSV, index=False)

    width = 1800
    height = 1260
    map_left = 80
    map_top = 170
    map_w = 1350
    map_h = 910
    pad_lon = 0.018
    pad_lat = 0.016
    lon_min = float(latest["lon"].min()) - pad_lon
    lon_max = float(latest["lon"].max()) + pad_lon
    lat_min = float(latest["lat"].min()) - pad_lat
    lat_max = float(latest["lat"].max()) + pad_lat

    def xy(lon: float, lat: float) -> tuple[int, int]:
        x = map_left + int((lon - lon_min) / (lon_max - lon_min) * map_w)
        y = map_top + int((lat_max - lat) / (lat_max - lat_min) * map_h)
        return x, y

    image = Image.new("RGB", (width, height), "#f7f1e6")
    draw = ImageDraw.Draw(image)
    title_font = _font(FONT_BOLD, 34)
    subtitle_font = _font(FONT_REGULAR, 22)
    regular = _font(FONT_REGULAR, 19)
    small = _font(FONT_REGULAR, 15)
    tiny = _font(FONT_REGULAR, 13)

    draw.text((70, 34), "Istanbul POI Crowd Pressure Map", fill="#151515", font=title_font)
    draw.text(
        (70, 82),
        "Part A XGBoost temporal demand x Part B Random Forest POI attractiveness",
        fill="#444444",
        font=subtitle_font,
    )
    draw.text(
        (70, 119),
        f"Modeled week: {latest_date.date()} | Points are POIs colored and sized by normalized combined crowd pressure.",
        fill="#555555",
        font=regular,
    )

    draw.rounded_rectangle(
        [map_left, map_top, map_left + map_w, map_top + map_h],
        radius=18,
        fill="#fbf7ef",
        outline="#d8cdbd",
        width=2,
    )

    water = "#cfe7f3"
    coast = "#a9c7d6"
    marmara_y = xy((lon_min + lon_max) / 2, 40.982)[1]
    draw.polygon(
        [
            (map_left, marmara_y),
            (map_left + map_w, marmara_y + 25),
            (map_left + map_w, map_top + map_h),
            (map_left, map_top + map_h),
        ],
        fill=water,
    )
    bosphorus = [
        xy(29.075, 41.155),
        xy(29.055, 41.110),
        xy(29.040, 41.070),
        xy(29.025, 41.035),
        xy(29.010, 41.005),
        xy(29.000, 40.980),
    ]
    draw.line(bosphorus, fill=water, width=46, joint="curve")
    draw.line(bosphorus, fill=coast, width=50)
    draw.line(bosphorus, fill=water, width=42, joint="curve")
    golden_horn = [xy(28.938, 41.045), xy(28.965, 41.032), xy(28.993, 41.021)]
    draw.line(golden_horn, fill=water, width=34, joint="curve")
    draw.line(golden_horn, fill=coast, width=38)
    draw.line(golden_horn, fill=water, width=30, joint="curve")
    draw.text(xy(29.017, 41.074), "Bosphorus", fill="#5a7f91", font=tiny)
    draw.text(xy(28.956, 41.013), "European side", fill="#b6a48e", font=small)
    draw.text(xy(29.055, 41.005), "Asian side", fill="#b6a48e", font=small)

    for i in range(5):
        lon = lon_min + (lon_max - lon_min) * i / 4
        x, _ = xy(lon, lat_min)
        draw.line([(x, map_top), (x, map_top + map_h)], fill="#eadfcc", width=1)
        draw.text((x - 24, map_top + map_h + 12), f"{lon:.2f}", fill="#6a6258", font=tiny)
    for i in range(5):
        lat = lat_min + (lat_max - lat_min) * i / 4
        _, y = xy(lon_min, lat)
        draw.line([(map_left, y), (map_left + map_w, y)], fill="#eadfcc", width=1)
        draw.text((map_left - 58, y - 8), f"{lat:.2f}", fill="#6a6258", font=tiny)

    for row in latest.sort_values("crowd_pressure_100").itertuples(index=False):
        x, y = xy(float(row.lon), float(row.lat))
        score = float(row.crowd_pressure_100)
        radius = int(5 + score / 100.0 * 20)
        color = _color(score)
        draw.ellipse([x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2], fill="#ffffff")
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color, outline="#58202a", width=1)

    legend_x = 1485
    legend_y = 215
    draw.rounded_rectangle([legend_x, legend_y, width - 70, 590], radius=14, fill="#ffffff", outline="#d8cdbd")
    draw.text((legend_x + 24, legend_y + 24), "Crowd pressure", fill="#151515", font=_font(FONT_BOLD, 22))
    draw.text((legend_x + 24, legend_y + 58), "Normalized 0-100", fill="#555555", font=small)
    for i, score in enumerate([20, 40, 60, 80, 100]):
        cy = legend_y + 105 + i * 47
        radius = int(5 + score / 100.0 * 20)
        draw.ellipse(
            [legend_x + 38 - radius, cy - radius, legend_x + 38 + radius, cy + radius],
            fill=_color(score),
            outline="#58202a",
            width=1,
        )
        draw.text((legend_x + 75, cy - 10), f"{score}", fill="#333333", font=regular)

    top_list_y = 640
    draw.rounded_rectangle([legend_x, top_list_y, width - 70, 1040], radius=14, fill="#ffffff", outline="#d8cdbd")
    draw.text((legend_x + 24, top_list_y + 24), "Top POIs", fill="#151515", font=_font(FONT_BOLD, 22))
    for idx, row in enumerate(latest.head(8).itertuples(index=False), start=1):
        y = top_list_y + 62 + (idx - 1) * 39
        name = str(row.display_name_en)
        if len(name) > 17:
            name = name[:14] + "..."
        draw.text((legend_x + 24, y), f"{idx}. {name}", fill="#333333", font=small)
        draw.text((width - 132, y), f"{float(row.crowd_pressure_100):.0f}", fill="#7f1734", font=small)

    caption = (
        "Source: data/processed/otm_crowdindex_xgb__rf_weekly.csv. "
        "The combined crowd pressure is Part A city-level demand multiplied by Part B POI attractiveness; "
        "scores are normalized within the selected week for map readability."
    )
    draw.text((70, height - 48), caption, fill="#555555", font=tiny)
    image.save(OUTPUT_PNG)
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
