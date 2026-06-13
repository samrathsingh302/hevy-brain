"""One markdown note per Hevy routine.

The frontmatter carries the FULL editable routine spec (same shape the
push-routine parser reads), so a note can round-trip: duplicate it into
``Routines/Drafts/``, edit the frontmatter, then ``hevy-brain push routine
<file>``. Managed notes themselves are regenerated from the cache on every
vault build — edits belong in a draft copy, not in place.
"""

from __future__ import annotations

from typing import Any

import yaml

from .writer import MANAGED_MARKER, VaultWriter, render_note, sanitize_filename

ROUTINE_NOTE_TYPE = "hevy-routine"

_SET_SPEC_KEYS = (
    "type",
    "weight_kg",
    "reps",
    "rep_range",
    "distance_meters",
    "duration_seconds",
    "custom_metric",
)


def routine_exercises_spec(routine: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the editable exercise spec from a raw API routine payload.

    This is the exact shape the push-routine parser consumes; None/empty
    fields are dropped so the frontmatter stays readable.
    """
    spec: list[dict[str, Any]] = []
    for exercise in routine.get("exercises", []):
        entry: dict[str, Any] = {
            "name": exercise.get("title") or "Unknown Exercise",
            "exercise_template_id": exercise.get("exercise_template_id", ""),
        }
        if exercise.get("superset_id") is not None:
            entry["superset_id"] = exercise["superset_id"]
        if exercise.get("rest_seconds") is not None:
            entry["rest_seconds"] = exercise["rest_seconds"]
        if exercise.get("notes"):
            entry["notes"] = exercise["notes"]
        # The push parser defaults a missing type to "normal"; carrying the
        # default here keeps an unedited draft an exact no-op in routine_diff
        # even when the API omits the type.
        entry["sets"] = [
            {
                "type": "normal",
                **{k: s[k] for k in _SET_SPEC_KEYS if s.get(k) is not None},
            }
            for s in exercise.get("sets", [])
        ]
        spec.append(entry)
    return spec


def routine_note_paths(
    routines: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Stable mapping routine_id -> relative note path.

    Notes are named ``Routines/<title>.md``. Title clashes keep the oldest
    on the clean name; later ones get a short id suffix — deterministic
    across runs (same scheme as workout notes).
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for routine in routines.values():
        base = f"Routines/{sanitize_filename(routine.get('title') or 'Routine')}"
        groups.setdefault(base, []).append(routine)

    paths: dict[str, str] = {}
    for base, group in groups.items():
        group.sort(key=lambda r: (r.get("created_at") or "", r["id"]))
        for index, routine in enumerate(group):
            if index == 0:
                paths[routine["id"]] = f"{base}.md"
            else:
                paths[routine["id"]] = f"{base} ({routine['id'][:8]}).md"
    return paths


def _set_row(index: int, routine_set: dict[str, Any]) -> str:
    set_type = routine_set.get("type") or "normal"
    weight = routine_set.get("weight_kg")
    reps = routine_set.get("reps")
    rep_range = routine_set.get("rep_range") or {}
    if reps is not None:
        reps_text = str(reps)
    elif rep_range.get("start") is not None:
        reps_text = f"{rep_range['start']}–{rep_range.get('end', '?')}"
    else:
        reps_text = "—"
    weight_text = f"{weight:g}" if weight is not None else "—"
    extras = []
    if routine_set.get("duration_seconds"):
        extras.append(f"{routine_set['duration_seconds']}s")
    if routine_set.get("distance_meters"):
        extras.append(f"{routine_set['distance_meters']}m")
    extra_text = ", ".join(extras)
    return f"| {index} | {set_type} | {weight_text} | {reps_text} | {extra_text} |"


def render_routine_note(
    routine: dict[str, Any], folder_title: str | None = None
) -> str:
    """Render a full routine note (managed content, no marker)."""
    title = routine.get("title") or "Routine"
    frontmatter: dict[str, Any] = {
        "type": ROUTINE_NOTE_TYPE,
        "hevy_routine_id": routine["id"],
        "title": title,
        "updated_at": routine.get("updated_at"),
        "exercises": routine_exercises_spec(routine),
        "tags": ["hevy/routine"],
    }
    if folder_title:
        frontmatter["folder"] = folder_title
    if routine.get("notes"):
        frontmatter["notes"] = routine["notes"]

    lines: list[str] = [f"# {title}"]
    if folder_title:
        lines.append(f"\n**Folder:** {folder_title}")
    if routine.get("notes"):
        lines.append(f"\n> {routine['notes']}")

    for exercise in routine.get("exercises", []):
        name = exercise.get("title") or "Unknown Exercise"
        lines.append(f"\n## [[{sanitize_filename(name)}]]")
        if exercise.get("rest_seconds"):
            lines.append(f"*Rest: {exercise['rest_seconds']}s*")
        if exercise.get("notes"):
            lines.append(f"*{exercise['notes']}*")
        lines.append("\n| # | Type | Weight (kg) | Reps | Extra |")
        lines.append("| - | ---- | ----------- | ---- | ----- |")
        for index, routine_set in enumerate(exercise.get("sets", []), start=1):
            lines.append(_set_row(index, routine_set))

    lines.append(
        "\n> [!info] To edit this routine: duplicate the note into "
        "`Routines/Drafts/`, change the frontmatter, then run "
        "`hevy-brain push routine <file>`. This managed note is regenerated "
        "from Hevy on every sync."
    )
    return render_note(frontmatter, "\n".join(lines))


def _is_managed_routine_note(text: str) -> bool:
    if MANAGED_MARKER not in text or not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return False
    return isinstance(data, dict) and data.get("type") == ROUTINE_NOTE_TYPE


def archive_stale_routine_notes(
    writer: VaultWriter, active_paths: set[str]
) -> int:
    """Archive managed routine notes no active routine owns.

    A routine renamed in Hevy (e.g. by a draft push) gets a note at its new
    title, leaving the old-title note behind — the store only remembers
    deletions, not old titles. Only notes hevy-brain wrote (managed marker +
    ``type: hevy-routine``) are touched; user files and ``Drafts/`` are not.
    Returns the number of notes archived.
    """
    routines_dir = writer.root / "Routines"
    if not routines_dir.is_dir():
        return 0
    archived = 0
    for path in sorted(routines_dir.glob("*.md")):
        rel_path = f"Routines/{path.name}"
        if rel_path in active_paths:
            continue
        if not _is_managed_routine_note(path.read_text(encoding="utf-8")):
            continue
        if writer.archive(rel_path):
            archived += 1
    return archived


def generate_routine_notes(
    writer: VaultWriter,
    routines: dict[str, dict[str, Any]],
    folders: dict[str, dict[str, Any]],
) -> int:
    """Write all routine notes. Returns number of files changed."""
    paths = routine_note_paths(routines)
    changed = 0
    for routine_id, routine in routines.items():
        folder = folders.get(str(routine.get("folder_id")))
        note = render_routine_note(routine, (folder or {}).get("title"))
        if writer.write(paths[routine_id], note):
            changed += 1
    return changed
