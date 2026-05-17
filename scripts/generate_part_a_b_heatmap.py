from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "otm_crowdindex_xgb__rf_weekly.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "evaluation"
OUTPUT_PNG = OUTPUT_DIR / "part_a_part_b_crowd_heatmap_top20.png"
OUTPUT_CSV = OUTPUT_DIR / "part_a_part_b_crowd_heatmap_top20.csv"
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
        (255, 255, 204),
        (255, 237, 160),
        (254, 178, 76),
        (240, 59, 32),
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
        "display_name_en",
        "date",
        "crowdindex_poi",
        "city_demand_score",
        "poi_weight_value",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    top_pois = (
        df.groupby("display_name_en")["crowdindex_poi"]
        .mean()
        .sort_values(ascending=False)
        .head(20)
        .index
    )
    top_df = df.loc[df["display_name_en"].isin(top_pois)].copy()
    pivot = top_df.pivot_table(
        index="display_name_en",
        columns="date",
        values="crowdindex_poi",
        aggfunc="mean",
    )
    pivot = pivot.loc[top_pois]
    heatmap_values = (pivot / pivot.max().max() * 100.0).round(2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    heatmap_values.to_csv(OUTPUT_CSV)

    dates = pd.to_datetime(heatmap_values.columns)
    cell_w = 5
    cell_h = 32
    left = 500
    top = 165
    right = 140
    bottom = 145
    heat_w = len(dates) * cell_w
    heat_h = len(heatmap_values.index) * cell_h
    width = left + heat_w + right
    height = top + heat_h + bottom

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    regular = _font(FONT_REGULAR, 20)
    small = _font(FONT_REGULAR, 16)
    tiny = _font(FONT_REGULAR, 14)
    title_font = _font(FONT_BOLD, 30)
    subtitle_font = _font(FONT_REGULAR, 21)

    draw.text((24, 24), "Part A x Part B Crowd Pressure Heatmap", fill="#161616", font=title_font)
    draw.text(
        (24, 66),
        "XGBoost temporal demand combined with Random Forest POI attractiveness",
        fill="#444444",
        font=subtitle_font,
    )
    draw.text(
        (24, 104),
        "Rows show the 20 POIs with the highest average combined crowd index; color is normalized 0-100.",
        fill="#555555",
        font=small,
    )

    values = heatmap_values.to_numpy()
    for row_idx, name in enumerate(heatmap_values.index):
        y0 = top + row_idx * cell_h
        draw.text((24, y0 + 7), str(name), fill="#222222", font=small)
        for col_idx, value in enumerate(values[row_idx]):
            x0 = left + col_idx * cell_w
            draw.rectangle(
                [x0, y0, x0 + cell_w - 1, y0 + cell_h - 1],
                fill=_color(float(value)),
            )

    draw.rectangle([left, top, left + heat_w, top + heat_h], outline="#333333", width=1)

    tick_dates = pd.date_range(dates.min(), dates.max(), freq="4MS")
    total_days = max((dates.max() - dates.min()).days, 1)
    for tick in tick_dates:
        if tick < dates.min() or tick > dates.max():
            continue
        x = left + int(((tick - dates.min()).days / total_days) * heat_w)
        draw.line([(x, top + heat_h), (x, top + heat_h + 7)], fill="#333333", width=1)
        draw.text((x - 28, top + heat_h + 12), tick.strftime("%Y-%m"), fill="#333333", font=tiny)

    draw.text((left + heat_w // 2 - 60, height - 55), "Modeled week", fill="#222222", font=regular)
    draw.text((24, top - 28), "Top POIs by average combined crowd index", fill="#222222", font=regular)

    bar_x = left + heat_w + 42
    bar_y = top
    bar_w = 26
    bar_h = heat_h
    for i in range(bar_h):
        score = 100.0 - (i / max(bar_h - 1, 1)) * 100.0
        draw.rectangle([bar_x, bar_y + i, bar_x + bar_w, bar_y + i], fill=_color(score))
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline="#333333", width=1)
    for score in (0, 25, 50, 75, 100):
        y = bar_y + bar_h - int(score / 100 * bar_h)
        draw.line([(bar_x + bar_w + 2, y), (bar_x + bar_w + 8, y)], fill="#333333", width=1)
        draw.text((bar_x + bar_w + 12, y - 8), str(score), fill="#333333", font=tiny)
    draw.text((bar_x - 14, bar_y + bar_h + 12), "Normalized", fill="#333333", font=tiny)

    caption = (
        "Source: data/processed/otm_crowdindex_xgb__rf_weekly.csv. "
        "Each cell is the combined weekly POI crowd index, normalized to the maximum "
        "value in the displayed top-20 POI matrix."
    )
    draw.text((24, height - 30), caption, fill="#555555", font=tiny)
    image.save(OUTPUT_PNG)
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
