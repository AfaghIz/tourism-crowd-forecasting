#!/usr/bin/env python3
"""Merge a recent Google Trends refresh into the combined raw Trends table.

The existing project stores Google Trends in one long-format CSV:

    data/raw/google_trends_istanbul.csv

with columns:
    - date
    - trend_score
    - category

This script keeps the historical rows before a chosen cutoff date, then
replaces overlapping rows from that date onward with newly exported weekly
Google Trends CSVs.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_TRENDS_PATH = PROJECT_ROOT / "data" / "raw" / "google_trends_istanbul.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "google_trends_istanbul_refreshed.csv"
DEFAULT_CUTOFF_DATE = "2025-12-28"
DEFAULT_REFRESH_DIR = Path.home() / "Downloads"


@dataclass(frozen=True)
class RefreshSource:
    category: str
    filename: str


REFRESH_SOURCES = [
    RefreshSource("travel_intent", "Visit_Istanbul.csv"),
    RefreshSource("attractions", "Istanbul_tourist_attractions.csv"),
    RefreshSource("museum", "Istanbul_museums.csv"),
    RefreshSource("historic", "Istanbul_historical_sites.csv"),
    RefreshSource("park", "Istanbul_parks.csv"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=RAW_TRENDS_PATH,
        help="Existing long-format Google Trends CSV.",
    )
    parser.add_argument(
        "--refresh-dir",
        type=Path,
        default=DEFAULT_REFRESH_DIR,
        help="Directory containing the recent weekly Google Trends exports.",
    )
    parser.add_argument(
        "--cutoff-date",
        default=DEFAULT_CUTOFF_DATE,
        help="Replace rows from this date onward for all tracked categories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the merged long-format output CSV.",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_refresh_rows(refresh_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for source in REFRESH_SOURCES:
        path = refresh_dir / source.filename
        if not path.exists():
            raise FileNotFoundError(f"Missing refresh file for {source.category}: {path}")

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader, None)  # header
            for raw_row in reader:
                if len(raw_row) < 2:
                    continue
                date_value = raw_row[0].strip()
                trend_value = raw_row[1].strip()
                if not date_value or trend_value == "":
                    continue
                rows.append(
                    {
                        "date": date_value,
                        "trend_score": trend_value,
                        "category": source.category,
                    }
                )

    return rows


def merge_rows(
    base_rows: list[dict[str, str]],
    refresh_rows: list[dict[str, str]],
    cutoff_date: str,
) -> list[dict[str, str]]:
    refresh_categories = {row["category"] for row in refresh_rows}

    kept_base = [
        row
        for row in base_rows
        if not (row["category"] in refresh_categories and row["date"] >= cutoff_date)
    ]

    merged = kept_base + refresh_rows
    merged.sort(key=lambda row: (row["category"], row["date"]))
    return merged


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "trend_score", "category"])
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, str]]) -> dict[str, tuple[str, str, int]]:
    counts = Counter(row["category"] for row in rows)
    mins: dict[str, str] = {}
    maxs: dict[str, str] = {}

    for row in rows:
        category = row["category"]
        date_value = row["date"]
        mins[category] = min(date_value, mins.get(category, date_value))
        maxs[category] = max(date_value, maxs.get(category, date_value))

    return {
        category: (mins[category], maxs[category], counts[category])
        for category in sorted(counts)
    }


def main() -> None:
    args = parse_args()
    base_rows = load_rows(args.base)
    refresh_rows = load_refresh_rows(args.refresh_dir)
    merged_rows = merge_rows(base_rows, refresh_rows, args.cutoff_date)
    write_rows(args.output, merged_rows)

    refresh_summary = summarize(refresh_rows)
    merged_summary = summarize(merged_rows)

    print(f"Wrote merged Google Trends file to: {args.output}")
    print(f"Cutoff date used for replacement: {args.cutoff_date}")
    print()
    print("Refresh rows loaded:")
    for category, (min_date, max_date, count) in refresh_summary.items():
        print(f"  - {category}: {count} rows ({min_date} -> {max_date})")
    print()
    print("Merged output coverage:")
    for category, (min_date, max_date, count) in merged_summary.items():
        print(f"  - {category}: {count} rows ({min_date} -> {max_date})")


if __name__ == "__main__":
    main()
