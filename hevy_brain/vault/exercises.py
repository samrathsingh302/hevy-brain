"""One evergreen markdown note per exercise."""

from __future__ import annotations

from typing import Any

import yaml

from ..analytics import progression
from ..config import Config
from ..models import pair_label
from . import charts
from .writer import MANAGED_MARKER, VaultWriter, render_note, sanitize_filename

_MAX_PR_ROWS = 15
_MAX_SESSION_ROWS = 12


def exercise_note_path(title: str) -> str:
    """Relative note path for an exercise."""
    return f"Exercises/{sanitize_filename(title)}.md"


def _progression_section(
    history: dict[str, Any], progression_cfg: Config | None
) -> list[str]:
    """Render a 'next session target' callout, or [] if nothing to suggest.

    Returns no orphan heading when progression is disabled or the lift has no
    usable load to progress (bodyweight-only / thin history).
    """
    if progression_cfg is None:
        return []
    target = progression.next_target(history, progression_cfg)
    if target is None:
        return []
    return ["\n> [!tip] Next session target", f"> {target['note']}"]


def render_exercise_note(
    history: dict[str, Any],
    workout_paths: dict[str, str],
    e1rm_max_points: int = 0,
    progression_cfg: Config | None = None,
) -> str:
    """Render an exercise note from its history (managed content)."""
    frontmatter = {
        "exercise": history["title"],
        "template_id": history["template_id"] or None,
        "times_performed": history["times_performed"],
        "last_performed": history["last_performed"].isoformat(),
        "best_weight_kg": round(history["best_weight_kg"], 1),
        "best_e1rm_kg": round(history["best_e1rm_kg"], 1),
        "total_volume_kg": round(history["total_volume_kg"], 1),
        "tags": ["hevy/exercise"],
    }

    pair = pair_label(history["title"])
    lines = [f"# {history['title']}"]
    lines.append(
        f"\nPerformed **{history['times_performed']}×** · last on "
        f"**{history['last_performed'].isoformat()}** · best weight "
        f"**{history['best_weight_kg']:g} kg{pair}** · best est. 1RM "
        f"**{history['best_e1rm_kg']:.1f} kg{pair}**"
    )
    if pair:
        lines.append(
            f"\n> [!info] Hevy stores dumbbell loads as PAIR TOTALS — the "
            f"{history['best_weight_kg']:g} kg above is "
            f"{history['best_weight_kg'] / 2:g} kg per hand."
        )

    lines.extend(_progression_section(history, progression_cfg))

    if e1rm_max_points:
        lines.extend(
            charts.chart_section(
                "est. 1RM trend",
                charts.e1rm_chart(history, e1rm_max_points),
                caption="Loaded sessions only (bodyweight/cardio excluded).",
            )
        )

    if history["prs"]:
        lines.append("\n## PR history")
        lines.append("\n| Date | Type | Value (kg) | Previous (kg) |")
        lines.append("| ---- | ---- | ---------- | ------------- |")
        for pr in reversed(history["prs"][-_MAX_PR_ROWS:]):
            previous = f"{pr['previous']:.1f}" if pr["previous"] else "—"
            lines.append(
                f"| {pr['date'].isoformat()} | {pr['type']} "
                f"| {pr['value']:.1f} | {previous} |"
            )

    lines.append("\n## Recent sessions")
    lines.append(
        "\n| Date | Workout | Top weight (kg) | est. 1RM | Sets | Reps | Volume (kg) |"
    )
    lines.append(
        "| ---- | ------- | --------------- | -------- | ---- | ---- | ----------- |"
    )
    for session in reversed(history["sessions"][-_MAX_SESSION_ROWS:]):
        note_path = workout_paths.get(session["workout_id"], "")
        note_name = note_path.rsplit("/", 1)[-1].removesuffix(".md")
        link = f"[[{note_name}]]" if note_name else session["workout_title"]
        lines.append(
            f"| {session['date'].isoformat()} | {link} "
            f"| {session['top_weight_kg']:g} | {session['best_e1rm_kg']:.1f} "
            f"| {session['sets']} | {session['reps']} "
            f"| {session['volume_kg']:g} |"
        )

    return render_note(frontmatter, "\n".join(lines))


def generate_exercise_notes(
    writer: VaultWriter,
    histories: dict[str, dict[str, Any]],
    workout_paths: dict[str, str],
    e1rm_max_points: int = 0,
    progression_cfg: Config | None = None,
) -> int:
    """Write all exercise notes. Returns number of files changed."""
    changed = 0
    for history in histories.values():
        note = render_exercise_note(
            history, workout_paths, e1rm_max_points, progression_cfg
        )
        if writer.write(exercise_note_path(history["title"]), note):
            changed += 1
    return changed


def _managed_exercise_title(text: str) -> str | None:
    """Return the ``exercise`` frontmatter of a note hevy-brain wrote, else None."""
    if MANAGED_MARKER not in text or not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    title = data.get("exercise") if isinstance(data, dict) else None
    return title if isinstance(title, str) and title else None


def archive_stale_exercise_notes(
    writer: VaultWriter, histories: dict[str, dict[str, Any]]
) -> int:
    """Archive managed exercise notes no current history owns.

    An exercise renamed or deleted in Hevy leaves its old-title note behind.
    Only notes hevy-brain wrote (managed marker + ``exercise`` frontmatter)
    are touched; user files under ``Exercises/`` are not. Returns the number
    of notes archived.
    """
    exercises_dir = writer.root / "Exercises"
    if not exercises_dir.is_dir():
        return 0
    active_paths = {exercise_note_path(h["title"]) for h in histories.values()}
    active_titles = {h["title"] for h in histories.values()}
    archived = 0
    for path in sorted(exercises_dir.glob("*.md")):
        rel_path = f"Exercises/{path.name}"
        if rel_path in active_paths:
            continue
        try:
            title = _managed_exercise_title(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue  # not a note hevy-brain wrote (it writes UTF-8)
        if title is None or title in active_titles:
            continue
        if writer.archive(rel_path):
            archived += 1
    return archived
