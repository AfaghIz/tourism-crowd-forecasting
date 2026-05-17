#!/usr/bin/env python3
"""Rebuild the Part A temporal dataset and sync the app runtime CSV."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRENDS_PATH = PROJECT_ROOT / "data" / "raw" / "google_trends_istanbul_refreshed.csv"
DEFAULT_WEATHER_PATH = PROJECT_ROOT / "data" / "processed" / "weather_istanbul_weekly.csv"
WEEKLY_CROWD_PATH = PROJECT_ROOT / "data" / "processed" / "weekly_crowd_index.csv"
MODEL_DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset.csv"
MODEL_DATASET_HOLIDAYS_PATH = PROJECT_ROOT / "data" / "processed" / "model_dataset_with_holidays.csv"
BACKEND_WEEKLY_MODEL_PATH = PROJECT_ROOT / "backend-python" / "data" / "istanbul_weekly_model.csv"


FIXED_HOLIDAYS = [
    "2021-01-01",
    "2021-04-23",
    "2021-05-01",
    "2021-05-19",
    "2021-08-30",
    "2021-10-29",
    "2022-01-01",
    "2022-04-23",
    "2022-05-01",
    "2022-05-19",
    "2022-08-30",
    "2022-10-29",
    "2023-01-01",
    "2023-04-23",
    "2023-05-01",
    "2023-05-19",
    "2023-08-30",
    "2023-10-29",
    "2024-01-01",
    "2024-04-23",
    "2024-05-01",
    "2024-05-19",
    "2024-08-30",
    "2024-10-29",
    "2025-01-01",
    "2025-04-23",
    "2025-05-01",
    "2025-05-19",
    "2025-08-30",
    "2025-10-29",
    "2026-01-01",
    "2026-04-23",
    "2026-05-01",
]

RAMADAN_FEAST_FIRST_DAYS = [
    "2021-05-13",
    "2022-05-02",
    "2023-04-21",
    "2024-04-10",
    "2025-03-30",
    "2026-03-20",
]

SACRIFICE_FEAST_FIRST_DAYS = [
    "2021-07-20",
    "2022-07-09",
    "2023-06-28",
    "2024-06-16",
    "2025-06-06",
    "2026-05-27",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trends", type=Path, default=DEFAULT_TRENDS_PATH)
    parser.add_argument("--weather", type=Path, default=DEFAULT_WEATHER_PATH)
    return parser.parse_args()


def build_weekly_crowd_index(trends_path: Path, weather_path: Path) -> pd.DataFrame:
    trends = pd.read_csv(trends_path, parse_dates=["date"])
    weather = pd.read_csv(weather_path, parse_dates=["date"])

    trend_weekly = trends.groupby("date")["trend_score"].mean().reset_index()
    trend_weekly.rename(columns={"trend_score": "trend_demand"}, inplace=True)

    data = pd.merge(trend_weekly, weather, on="date", how="inner").sort_values("date").reset_index(drop=True)

    scaler = MinMaxScaler()
    data[["trend_demand", "temp_avg", "precipitation"]] = scaler.fit_transform(
        data[["trend_demand", "temp_avg", "precipitation"]]
    )

    data["crowd_index"] = (
        0.5 * data["trend_demand"] + 0.3 * data["temp_avg"] + 0.2 * (1 - data["precipitation"])
    )
    data["crowd_level"] = pd.qcut(data["crowd_index"], q=3, labels=["Low", "Medium", "High"])
    return data


def add_temporal_features(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    df["month"] = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)

    def get_season(month: int) -> str:
        if month in [12, 1, 2]:
            return "winter"
        if month in [3, 4, 5]:
            return "spring"
        if month in [6, 7, 8]:
            return "summer"
        return "autumn"

    df["season"] = df["month"].apply(get_season)
    df = pd.get_dummies(df, columns=["season"], drop_first=True)

    # Keep the historical notebook naming for downstream compatibility.
    if "week_of_year" in df.columns and "weekofyear" not in df.columns:
        df["weekofyear"] = df["week_of_year"]

    return df


def add_holiday_feature(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    holiday_dates = pd.to_datetime(FIXED_HOLIDAYS + RAMADAN_FEAST_FIRST_DAYS + SACRIFICE_FEAST_FIRST_DAYS)

    weekly_dates = df["date"].sort_values().drop_duplicates().reset_index(drop=True)
    mapped_week_dates: set[pd.Timestamp] = set()
    for holiday in holiday_dates:
        nearest_idx = (weekly_dates - holiday).abs().argmin()
        mapped_week_dates.add(weekly_dates.iloc[nearest_idx])

    df["is_holiday"] = df["date"].isin(mapped_week_dates).astype(int)
    return df


def sync_runtime_csv(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)


def main() -> None:
    args = parse_args()

    weekly_crowd = build_weekly_crowd_index(args.trends, args.weather)
    weekly_crowd.to_csv(WEEKLY_CROWD_PATH, index=False)

    model_dataset = add_temporal_features(weekly_crowd)
    model_dataset.to_csv(MODEL_DATASET_PATH, index=False)

    model_dataset_with_holidays = add_holiday_feature(model_dataset)
    model_dataset_with_holidays.to_csv(MODEL_DATASET_HOLIDAYS_PATH, index=False)

    sync_runtime_csv(MODEL_DATASET_HOLIDAYS_PATH, BACKEND_WEEKLY_MODEL_PATH)

    print(f"Wrote weekly crowd index: {WEEKLY_CROWD_PATH}")
    print(f"Wrote model dataset: {MODEL_DATASET_PATH}")
    print(f"Wrote holiday dataset: {MODEL_DATASET_HOLIDAYS_PATH}")
    print(f"Synced backend runtime file: {BACKEND_WEEKLY_MODEL_PATH}")
    print(
        "Coverage: "
        f"{model_dataset_with_holidays['date'].dt.date.iloc[0]} -> "
        f"{model_dataset_with_holidays['date'].dt.date.iloc[-1]} "
        f"({len(model_dataset_with_holidays)} rows)"
    )


if __name__ == "__main__":
    main()
