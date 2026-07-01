"""One markdown note per workout.

The frontmatter carries the FULL editable workout spec (same shape the
``push workout --update`` parser reads), so a logged workout can be fixed
from its note: duplicate it into ``Workouts/Drafts/``, correct the
frontmatter, then ``hevy-brain push workout <file> --update``. Managed notes
themselves are regenerated from the cache on every vault build — edits
belong in a draft copy, not in place.
"""

from __future__ import annotations

from typing import Any

from ..analytics.prs import epley_1rm, prs_for_workout
from .writer import VaultWriter, render_note, sanitize_filename

WORKOUT_NOTE_TYPE = "hevy-workout"

_SET_SPEC_KEYS = (
    "type",
    "weight_kg",
    "reps",
    "distance_meters",
    "duration_seconds",
    "rpe",
    "custom_metric",
)


def workout_exercises_spec(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the editable exercise spec from a processed workout record.

    This is the exact shape the push-workout parser consumes; None/empty
    fields are dropped so the frontmatter stays readable. Defaulting a
    missing set type to "normal" matches the parser, keeping an unedited
    draft an exact no-op in workout_diff.
    """
    spec: list[dict[str, Any]] = []
    for exercise in record["exercises"]:
        entry: dict[str, Any] = {
            "name": exercise.get("title") or "Unknown Exercise",
            "exercise_template_id": exercise.get("template_id", ""),
        }
        if exercise.get("superset_id") is not None:
            entry["superset_id"] = exercise["superset_id"]
        if exercise.get("notes"):
            entry["notes"] = exercise["notes"]
        entry["sets"] = [
            {
                "type": "normal",
                **{k: s[k] for k in _SET_SPEC_KEYS if s.get(k) is not None},
            }
            for s in exercise.get("sets", [])
        ]
        spec.append(entry)
    return spec


def workout_note_paths(records: list[dict[str, Any]]) -> dict[str, str]:
    """Stable mapping workout_id -> relative note path.

    Notes are named `Workouts/<date> <title>.md`. If several workouts share
    date+title, the earliest keeps the clean name and later ones get a short
    id suffix — deterministic across runs.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        date_str = record["start_time"].date().isoformat()
        base = f"Workouts/{date_str} {sanitize_filename(record['title'])}"
        groups.setdefault(base, []).append(record)

    paths: dict[str, str] = {}
    for base, group in groups.items():
        group.sort(key=lambda r: (r["start_time"], r["id"]))
        for index, record in enumerate(group):
            if index == 0:
                paths[record["id"]] = f"{base}.md"
            else:
                paths[record["id"]] = f"{base} ({record['id'][:8]}).md"
    return paths


def _set_row(index: int, workout_set: dict[str, Any]) -> str:
    set_type = workout_set.get("type") or "normal"
    weight = workout_set.get("weight_kg")
    reps = workout_set.get("reps")
    weight_text = f"{weight:g}" if weight is not None else "—"
    reps_text = str(reps) if reps is not None else "—"
    e1rm = epley_1rm(weight or 0, reps or 0)
    e1rm_text = f"{e1rm:.1f}" if e1rm else "—"
    extras = []
    if workout_set.get("duration_seconds"):
        extras.append(f"{workout_set['duration_seconds']}s")
    if workout_set.get("distance_meters"):
        extras.append(f"{workout_set['distance_meters']}m")
    if workout_set.get("rpe") is not None:
        extras.append(f"RPE {workout_set['rpe']:g}")
    extra_text = ", ".join(extras) if extras else ""
    return (
        f"| {index} | {set_type} | {weight_text} | {reps_text} "
        f"| {e1rm_text} | {extra_text} |"
    )


def render_workout_note(
    record: dict[str, Any], workout_prs: list[dict[str, Any]]
) -> str:
    """Render a full workout note (managed content, no marker)."""
    start = record["start_time"]
    frontmatter = {
        "type": WORKOUT_NOTE_TYPE,
        "hevy_id": record["id"],
        "date": start.date().isoformat(),
        "title": record["title"],
        "start_time": start.isoformat(),
        "end_time": record["end_time"].isoformat() if record["end_time"] else None,
        "is_private": record.get("is_private", False),
        "duration_min": round(record["duration_seconds"] / 60, 1),
        "volume_kg": round(record["volume_kg"], 1),
        "total_reps": record["total_reps"],
        "exercise_count": record["exercise_count"],
        "exercises": workout_exercises_spec(record),
        "tags": ["hevy/workout"],
    }
    if record.get("description"):
        frontmatter["description"] = record["description"]

    lines: list[str] = [f"# {record['title']}"]
    lines.append(
        f"\n**{start.strftime('%A, %d %B %Y %H:%M')}** · "
        f"{frontmatter['duration_min']:g} min · "
        f"{frontmatter['volume_kg']:g} kg total volume · "
        f"{record['total_reps']} reps across {record['exercise_count']} exercises"
    )
    if record.get("description"):
        lines.append(f"\n> {record['description']}")

    for pr in workout_prs:
        previous = f" (prev {pr['previous']:.1f})" if pr["previous"] else ""
        lines.append(
            f"\n> [!success] PR — {pr['exercise']}: "
            f"{pr['type']} {pr['value']:.1f} kg{previous}"
        )

    for exercise in record["exercises"]:
        lines.append(f"\n## [[{sanitize_filename(exercise['title'])}]]")
        if exercise.get("notes"):
            lines.append(f"*{exercise['notes']}*")
        lines.append("\n| # | Type | Weight (kg) | Reps | est. 1RM | Extra |")
        lines.append("| - | ---- | ----------- | ---- | -------- | ----- |")
        for index, workout_set in enumerate(exercise["sets"], start=1):
            lines.append(_set_row(index, workout_set))
        lines.append(
            f"\n**Volume:** {exercise['volume_kg']:g} kg · "
            f"**Top weight:** {exercise['top_working_weight_kg']:g} kg"
        )

    lines.append(
        "\n> [!info] To fix this workout (typo'd weight, forgotten set): "
        "duplicate the note into `Workouts/Drafts/`, correct the "
        "frontmatter, then run `hevy-brain push workout <file> --update`. "
        "This managed note is regenerated from Hevy on every sync."
    )
    return render_note(frontmatter, "\n".join(lines))


def generate_workout_notes(
    writer: VaultWriter,
    records: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
) -> int:
    """Write all workout notes. Returns number of files changed."""
    paths = workout_note_paths(records)
    changed = 0
    for record in records:
        note = render_workout_note(record, prs_for_workout(histories, record["id"]))
        if writer.write(paths[record["id"]], note):
            changed += 1
    return changed
