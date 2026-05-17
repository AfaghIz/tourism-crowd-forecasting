#!/usr/bin/env python3
"""Extend weekly weather by copying seasonally aligned rows from the prior year."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "weather_istanbul_weekly.csv"
WEEKLY_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "weather_istanbul_weekly_extended.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=WEEKLY_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=WEEKLY_OUTPUT_PATH)
    parser.add_argument("--start-date", default="2026-01-11")
    parser.add_argument("--end-date", default="2026-05-03")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    weekly = pd.read_csv(args.input, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    lookup = weekly.set_index("date")

    future_dates = pd.date_range(args.start_date, args.end_date, freq="W-SUN")
    rows: list[dict[str, object]] = []
    for future_date in future_dates:
        source_date = future_date - pd.Timedelta(days=364)
        if source_date not in lookup.index:
            raise KeyError(f"Missing source weather row for {source_date.date()} while building {future_date.date()}")
        source_row = lookup.loc[source_date]
        rows.append(
            {
                "date": future_date,
                "temp_max": float(source_row["temp_max"]),
                "temp_min": float(source_row["temp_min"]),
                "temp_avg": float(source_row["temp_avg"]),
                "precipitation": float(source_row["precipitation"]),
            }
        )

    extension = pd.DataFrame(rows)
    combined = (
        pd.concat([weekly, extension], ignore_index=True)
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.output, index=False)

    print(f"Wrote extended weekly weather to: {args.output}")
    print(f"Original coverage: {weekly['date'].dt.date.iloc[0]} -> {weekly['date'].dt.date.iloc[-1]} ({len(weekly)} rows)")
    print(
        "Extended coverage: "
        f"{combined['date'].dt.date.iloc[0]} -> {combined['date'].dt.date.iloc[-1]} ({len(combined)} rows)"
    )


if __name__ == "__main__":
    main()
