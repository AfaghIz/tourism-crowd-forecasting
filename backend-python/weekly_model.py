from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

RESOURCE_NAME = "istanbul_weekly_model.csv"


@dataclass(frozen=True)
class WeeklyRow:
    week_start: date
    crowd_index: float
    crowd_level: str


class IstanbulWeeklyModelRepository:
    """Loads notebook-derived weekly Istanbul CSV under ``data/``."""

    def __init__(self) -> None:
        self._rows: list[WeeklyRow] = []
        self._load()

    def _csv_path(self) -> Path:
        return Path(__file__).resolve().parent / "data" / RESOURCE_NAME

    def _load(self) -> None:
        path = self._csv_path()
        if not path.is_file():
            log.warning(
                "Missing %s; city-wide forecast will fall back to demo scoring.",
                path,
            )
            return
        parsed: list[WeeklyRow] = []
        try:
            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header is None:
                    return
                for row in reader:
                    if not row or not row[0].strip():
                        continue
                    parsed_row = _parse_line(row)
                    if parsed_row is not None:
                        parsed.append(parsed_row)
        except OSError:
            log.exception("Failed to load %s", path)
            parsed.clear()

        self._rows = parsed
        log.info("Loaded %s weekly Istanbul rows from %s", len(self._rows), path)

    def is_loaded(self) -> bool:
        return len(self._rows) > 0

    def all_rows(self) -> list[WeeklyRow]:
        return self._rows


def _parse_line(parts: list[str]) -> WeeklyRow | None:
    # Notebook CSV: date,...,crowd_index,crowd_level,... — fixed column indices.
    if len(parts) < 8:
        return None
    try:
        d = date.fromisoformat(parts[0].strip())
        idx = float(parts[6].strip())
        lvl = parts[7].strip()
        if lvl.lower() not in ("low", "medium", "high"):
            return None
        level = lvl[0].upper() + lvl[1:].lower()
        return WeeklyRow(d, idx, level)
    except (ValueError, IndexError):
        return None
