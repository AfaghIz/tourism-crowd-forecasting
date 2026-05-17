#!/usr/bin/env python3
"""Refresh Istanbul weather data from Open-Meteo and rebuild weekly weather."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "weather_istanbul_daily.csv"
WEEKLY_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "weather_istanbul_weekly.csv"

LAT = 41.0082
LON = 28.9784


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default="2026-05-03")
    parser.add_argument("--raw-output", type=Path, default=RAW_OUTPUT_PATH)
    parser.add_argument("--weekly-output", type=Path, default=WEEKLY_OUTPUT_PATH)
    return parser.parse_args()


def fetch_weather(start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "precipitation_sum",
            ]
        ),
        "timezone": "Europe/Istanbul",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urlencode(params)
    with urlopen(url) as response:
        payload = json.load(response)

    daily = payload["daily"]
    return pd.DataFrame(
        {
            "date": daily["time"],
            "temp_max": daily["temperature_2m_max"],
            "temp_min": daily["temperature_2m_min"],
            "temp_avg": daily["temperature_2m_mean"],
            "precipitation": daily["precipitation_sum"],
        }
    )


def build_weekly(weather_daily: pd.DataFrame) -> pd.DataFrame:
    weather = weather_daily.copy()
    weather["date"] = pd.to_datetime(weather["date"])
    weekly = (
        weather.set_index("date")
        .resample("W")
        .agg(
            {
                "temp_max": "mean",
                "temp_min": "mean",
                "temp_avg": "mean",
                "precipitation": "sum",
            }
        )
        .reset_index()
    )
    return weekly


def main() -> None:
    args = parse_args()
    daily = fetch_weather(args.start_date, args.end_date)
    weekly = build_weekly(daily)

    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.weekly_output.parent.mkdir(parents=True, exist_ok=True)

    daily.to_csv(args.raw_output, index=False)
    weekly.to_csv(args.weekly_output, index=False)

    print(f"Saved daily weather to: {args.raw_output}")
    print(f"Saved weekly weather to: {args.weekly_output}")
    print(f"Daily coverage: {daily['date'].iloc[0]} -> {daily['date'].iloc[-1]} ({len(daily)} rows)")
    print(
        "Weekly coverage: "
        f"{weekly['date'].dt.date.iloc[0]} -> {weekly['date'].dt.date.iloc[-1]} ({len(weekly)} rows)"
    )


if __name__ == "__main__":
    main()
