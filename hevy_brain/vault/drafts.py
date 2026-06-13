"""Routine drafts (`Routines/Drafts/`), ready for `push routine`.

Two kinds of draft, both copies of an existing Hevy routine that keep the
original ``hevy_routine_id`` so the slice-1 round-trip applies unchanged
(review the frontmatter, then ``hevy-brain push routine <draft> --dry-run``):

- **Return-week drafts** (`guide return`): loads scaled down for the first
  week back after a lapse.
- **Redesign drafts** (`guide redesign`): unchanged copies — an editing
  canvas for a programme change. Pushing one unedited is a no-op by
  construction ("no changes — nothing to push").

Safety properties:

- **Write-once.** A draft is user-owned the moment it exists — regenerating
  never overwrites an existing draft file.
- **No data loss.** Pushing a draft PUT-replaces the routine in Hevy, so the
  draft body carries the original loads; restoring is pushing the original
  spec back (the managed note keeps it until the next sync).
- The return-week load fraction is a configurable default, NOT a cited
  recommendation — programming claims are not in the knowledge corpus yet
  (general-knowledge).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .routines import ROUTINE_NOTE_TYPE, routine_exercises_spec
from .writer import VaultWriter, render_note, sanitize_filename

DRAFTS_DIR = "Routines/Drafts"
RETURN_PREFIX = "Return Week 1"
REDESIGN_PREFIX = "Redesign"


def scale_weight(weight_kg: float, fraction: float, step: float = 2.5) -> float:
    """Scale a load and round to the nearest plate step.

    Never returns more than the original load (a return week must not load
    heavier than pre-lapse), so weights at or below one step pass through.
    """
    if weight_kg <= step:
        return weight_kg
    rounded = int(weight_kg * fraction / step + 0.5) * step
    return min(max(rounded, step), weight_kg)


def scale_exercises(
    spec: list[dict[str, Any]], fraction: float
) -> list[dict[str, Any]]:
    """Return the spec with every weighted set scaled; bodyweight untouched."""
    scaled: list[dict[str, Any]] = []
    for exercise in spec:
        entry = {k: v for k, v in exercise.items() if k != "sets"}
        entry["sets"] = [
            {
                **s,
                **(
                    {"weight_kg": scale_weight(s["weight_kg"], fraction)}
                    if s.get("weight_kg")
                    else {}
                ),
            }
            for s in exercise["sets"]
        ]
        scaled.append(entry)
    return scaled


def select_return_routines(
    routines: dict[str, dict[str, Any]],
    recent_titles: list[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Pick the routines a comeback week should be drafted from.

    Routines whose title matches a pre-lapse workout title come first (Hevy
    stamps a workout with its routine's title), then the most recently
    updated fill the remainder.
    """
    recent = {t.lower() for t in recent_titles}
    by_recency = sorted(
        (r for r in routines.values() if _pushable(r)),
        key=lambda r: r.get("updated_at") or "",
        reverse=True,
    )
    matched = [r for r in by_recency if (r.get("title") or "").lower() in recent]
    rest = [r for r in by_recency if r not in matched]
    return (matched + rest)[:limit]


def _pushable(routine: dict[str, Any]) -> bool:
    """Report whether a draft of this routine would pass the push parser."""
    exercises = routine.get("exercises") or []
    return bool(exercises) and all(
        e.get("exercise_template_id") and e.get("sets") for e in exercises
    )


def _format_set(s: dict[str, Any]) -> str:
    weight = s.get("weight_kg")
    reps = s.get("reps")
    rep_range = s.get("rep_range") or {}
    if reps is not None:
        reps_text = str(reps)
    elif rep_range.get("start") is not None:
        reps_text = f"{rep_range['start']}–{rep_range.get('end', '?')}"
    else:
        reps_text = "—"
    weight_text = f"{weight:g} kg" if weight is not None else "BW"
    return f"{weight_text} × {reps_text}"


def _load_row(original: dict[str, Any], scaled: dict[str, Any], index: int) -> str:
    return f"| {index} | {_format_set(original)} | {_format_set(scaled)} |"


def render_return_draft(
    routine: dict[str, Any], *, fraction: float
) -> tuple[str, str]:
    """Render one return-week draft note. Returns (relative path, content)."""
    original_title = routine.get("title") or "Routine"
    draft_title = f"{RETURN_PREFIX} — {original_title}"
    original_spec = routine_exercises_spec(routine)
    scaled_spec = scale_exercises(original_spec, fraction)

    frontmatter: dict[str, Any] = {
        "type": ROUTINE_NOTE_TYPE,
        "hevy_routine_id": routine["id"],
        "title": draft_title,
        "exercises": scaled_spec,
        "tags": ["hevy/routine/draft"],
    }
    # PUT is a full replacement — without this, pushing wipes routine notes.
    if routine.get("notes"):
        frontmatter["notes"] = routine["notes"]

    lines = [
        f"# {draft_title}",
        (
            f"\nLoads scaled to **{fraction:.0%}** of the pre-lapse routine "
            "`[general-knowledge]` — the ramp fraction is a configurable "
            "default (`[guide] load_fraction` in config.toml), not a cited "
            "claim; programming content is not in the knowledge corpus yet."
        ),
        (
            "\n> [!warning] Pushing this draft **replaces** the routine "
            f"'{original_title}' in Hevy (PUT, full replacement). Preview "
            "first: `hevy-brain push routine <this file> --dry-run`. To "
            "restore afterwards, push the original loads below back."
        ),
    ]
    for original, scaled in zip(original_spec, scaled_spec, strict=True):
        lines.append(f"\n## {original['name']}")
        lines.append("\n| Set | Original | Week 1 |")
        lines.append("| --- | -------- | ------ |")
        for index, (orig_set, new_set) in enumerate(
            zip(original["sets"], scaled["sets"], strict=True), start=1
        ):
            lines.append(_load_row(orig_set, new_set, index))

    rel_path = f"{DRAFTS_DIR}/{sanitize_filename(draft_title)}.md"
    return rel_path, render_note(frontmatter, "\n".join(lines))


def render_redesign_draft(routine: dict[str, Any]) -> tuple[str, str]:
    """Render one redesign draft note. Returns (relative path, content).

    The frontmatter carries the routine's CURRENT spec unchanged (title
    included), so pushing the draft before editing it is a guaranteed no-op —
    the draft is a canvas for the redesign, not a load change.
    """
    title = routine.get("title") or "Routine"
    original_spec = routine_exercises_spec(routine)

    frontmatter: dict[str, Any] = {
        "type": ROUTINE_NOTE_TYPE,
        "hevy_routine_id": routine["id"],
        "title": title,
        "exercises": original_spec,
        "tags": ["hevy/routine/draft"],
    }
    # PUT is a full replacement — without this, pushing wipes routine notes.
    if routine.get("notes"):
        frontmatter["notes"] = routine["notes"]

    lines = [
        f"# {REDESIGN_PREFIX} — {title}",
        (
            "\nThis draft starts as an exact copy of the routine, so pushing "
            "it **unedited sends nothing** ('no changes'). Apply the redesign "
            "by editing the frontmatter spec (exercises, sets, reps, loads, "
            "rest, title), guided by the Redesign Briefing in `Coach/`."
        ),
        (
            f"\n> [!warning] Pushing this draft **replaces** the routine "
            f"'{title}' in Hevy (PUT, full replacement). Preview first: "
            "`hevy-brain push routine <this file> --dry-run`. The original "
            "spec stays in the table below and in the managed note until the "
            "next sync."
        ),
    ]
    for exercise in original_spec:
        lines.append(f"\n## {exercise['name']}")
        lines.append("\n| Set | Current |")
        lines.append("| --- | ------- |")
        for index, current_set in enumerate(exercise["sets"], start=1):
            lines.append(f"| {index} | {_format_set(current_set)} |")

    rel_path = f"{DRAFTS_DIR}/{sanitize_filename(f'{REDESIGN_PREFIX} — {title}')}.md"
    return rel_path, render_note(frontmatter, "\n".join(lines))


def _generate_drafts(
    writer: VaultWriter,
    routines: dict[str, dict[str, Any]],
    recent_titles: list[str],
    *,
    render: Callable[[dict[str, Any]], tuple[str, str]],
    limit: int,
) -> tuple[list[str], list[str]]:
    """Write drafts for the selected routines (write-once).

    Returns (written, skipped) relative paths.
    """
    written: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for routine in select_return_routines(routines, recent_titles, limit):
        rel_path, content = render(routine)
        if rel_path in seen:
            # Duplicate titles: same id-suffix scheme as the managed notes.
            rel_path = f"{rel_path[: -len('.md')]} ({routine['id'][:8]}).md"
        seen.add(rel_path)
        if (writer.root / rel_path).exists():
            skipped.append(rel_path)
            continue
        writer.write(rel_path, content)
        written.append(rel_path)
    return written, skipped


def generate_return_drafts(
    writer: VaultWriter,
    routines: dict[str, dict[str, Any]],
    recent_titles: list[str],
    *,
    fraction: float,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    """Write return-week drafts (write-once). Returns (written, skipped)."""
    return _generate_drafts(
        writer,
        routines,
        recent_titles,
        render=lambda routine: render_return_draft(routine, fraction=fraction),
        limit=limit,
    )


def generate_redesign_drafts(
    writer: VaultWriter,
    routines: dict[str, dict[str, Any]],
    recent_titles: list[str],
    *,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    """Write redesign canvas drafts (write-once). Returns (written, skipped)."""
    return _generate_drafts(
        writer, routines, recent_titles, render=render_redesign_draft, limit=limit
    )
