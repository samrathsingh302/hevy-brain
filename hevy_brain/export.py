"""Export the local cache to CSV for external analysis (Excel/Sheets/pandas).

Stdlib only, offline, read-only over the cache. Writes OUTSIDE the vault — under
``<base_dir>/exports/`` by default — so personal training data never lands in the
path-jailed ``Hevy/`` subfolder. ``None`` values (bodyweight sets carry
``weight_kg=None``; RPE is often unset) serialise as an empty cell, never the
string ``"None"``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

WORKOUT_FIELDS = [
    "date",
    "title",
    "duration_min",
    "volume_kg",
    "total_reps",
    "exercise_count",
    "hevy_id",
]

SET_FIELDS = [
    "date",
    "workout_title",
    "exercise",
    "set_index",
    "set_type",
    "weight_kg",
    "reps",
    "rpe",
]

# Leading characters a spreadsheet may interpret as a formula. A cell starting
# with one is prefixed with an apostrophe so Excel/Sheets render it as text.
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection in one CSV cell.

    A user can name a Hevy workout/exercise ``=HYPERLINK(...)`` / ``+cmd`` etc.;
    written raw it becomes a live formula in the opener. Prefix such a string
    with an apostrophe so it renders as literal text. Non-strings pass through.
    """
    if isinstance(value, str) and value[:1] in _FORMULA_LEAD:
        return "'" + value
    return value


def workout_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per workout, chronological (records are already sorted)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        start = record["start_time"]
        rows.append(
            {
                "date": start.date().isoformat(),
                "title": record["title"],
                "duration_min": round(record["duration_seconds"] / 60),
                "volume_kg": record["volume_kg"],
                "total_reps": record["total_reps"],
                "exercise_count": record["exercise_count"],
                "hevy_id": record["id"],
            }
        )
    return rows


def set_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per set (warm-ups included), in workout/exercise/set order.

    ``set_index`` is 1-based within its exercise. ``weight_kg`` and ``rpe`` keep
    a real ``None`` when unset (bodyweight / unlogged RPE) so the CSV writer
    emits an empty cell rather than the string "None".
    """
    rows: list[dict[str, Any]] = []
    for record in records:
        date = record["start_time"].date().isoformat()
        title = record["title"]
        for exercise in record["exercises"]:
            for index, workout_set in enumerate(exercise["sets"], start=1):
                rows.append(
                    {
                        "date": date,
                        "workout_title": title,
                        "exercise": exercise["title"],
                        "set_index": index,
                        "set_type": workout_set.get("type"),
                        "weight_kg": workout_set.get("weight_kg"),
                        "reps": workout_set.get("reps"),
                        "rpe": workout_set.get("rpe"),
                    }
                )
    return rows


def default_out_path(base_dir: Path, kind: str) -> Path:
    """Default target, OUTSIDE the vault: ``<base_dir>/exports/hevy-<kind>.csv``."""
    return base_dir / "exports" / f"hevy-{kind}.csv"


def write_csv(
    rows: list[dict[str, Any]], fieldnames: list[str], out_path: Path
) -> None:
    """Write rows to ``out_path`` as UTF-8 CSV (header always written).

    ``None`` serialises as an empty cell via the writer's ``restval`` default.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: ("" if v is None else _csv_safe(v)) for k, v in row.items()}
            )


def export_csv(
    records: list[dict[str, Any]], kind: str, out_path: Path
) -> tuple[Path, int]:
    """Export ``records`` to CSV by ``kind`` (``workouts`` or ``sets``).

    Returns the resolved absolute path written and the data row count (header
    excluded). An empty cache writes a header-only file and returns count 0 —
    exporting nothing is not an error.
    """
    if kind == "sets":
        rows = set_rows(records)
        fieldnames = SET_FIELDS
    else:
        rows = workout_rows(records)
        fieldnames = WORKOUT_FIELDS
    write_csv(rows, fieldnames, out_path)
    return out_path.resolve(), len(rows)
