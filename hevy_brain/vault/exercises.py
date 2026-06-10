"""One evergreen markdown note per exercise."""

from __future__ import annotations

from typing import Any

from .writer import VaultWriter, render_note, sanitize_filename

_MAX_PR_ROWS = 15
_MAX_SESSION_ROWS = 12


def exercise_note_path(title: str) -> str:
    """Relative note path for an exercise."""
    return f"Exercises/{sanitize_filename(title)}.md"


def render_exercise_note(history: dict[str, Any], workout_paths: dict[str, str]) -> str:
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

    lines = [f"# {history['title']}"]
    lines.append(
        f"\nPerformed **{history['times_performed']}×** · last on "
        f"**{history['last_performed'].isoformat()}** · best weight "
        f"**{history['best_weight_kg']:g} kg** · best est. 1RM "
        f"**{history['best_e1rm_kg']:.1f} kg**"
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
) -> int:
    """Write all exercise notes. Returns number of files changed."""
    changed = 0
    for history in histories.values():
        note = render_exercise_note(history, workout_paths)
        if writer.write(exercise_note_path(history["title"]), note):
            changed += 1
    return changed
