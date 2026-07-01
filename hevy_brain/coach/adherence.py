"""Guide-draft adherence — the C1 coach-memory extension.

When a guide draft (a ``guide return`` or ``guide redesign`` routine draft) is
pushed to Hevy, hevy-brain records an objective **adherence target**: the
prescribed exercises and their top-set loads, plus the push date. A later coach
run grades — purely from logged workouts — whether those lifts were actually
trained since the push, and at what fraction of the prescribed load.

Like the rest of coach memory, this grades the objective *prescription* against
real Hevy data, never the free-text advice below the ``%% hevy-brain:end %%``
marker. Loads are loads; judgement stays with the reader.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..vault.drafts import REDESIGN_PREFIX, RETURN_PREFIX

META_KEY = "draft_adherence"
_KEEP = 6
# A trained top set at or above this fraction of target counts as "on target";
# at or above _OVER it's "above target". Below _ON_TARGET it's "under target".
_ON_TARGET = 0.95
_OVER = 1.05


def draft_kind(title: str) -> str | None:
    """Classify a routine title as a guide draft, or None if it isn't one."""
    if title.startswith(RETURN_PREFIX):
        return "return"
    if title.startswith(REDESIGN_PREFIX):
        return "redesign"
    return None


def build_target(body: dict[str, Any], today: date) -> dict[str, Any] | None:
    """Build an adherence target from a routine PUT body.

    Returns None when the routine isn't a guide draft (so non-guide pushes are
    never tracked). The prescription is the top-set weight per exercise (max
    weight across its sets); a bodyweight-only exercise records
    ``top_weight_kg = None`` and is later graded on trained/not-trained alone.
    """
    routine = body.get("routine") or {}
    title = routine.get("title") or ""
    kind = draft_kind(title)
    if kind is None:
        return None

    prescribed: list[dict[str, Any]] = []
    for exercise in routine.get("exercises") or []:
        template_id = exercise.get("exercise_template_id")
        if not template_id:
            continue
        sets = exercise.get("sets") or []
        weights = [s.get("weight_kg") for s in sets if s.get("weight_kg")]
        prescribed.append(
            {
                "template_id": str(template_id),
                "top_weight_kg": max(weights) if weights else None,
                "sets": len(sets),
            }
        )
    if not prescribed:
        return None
    return {
        "pushed_on": today.isoformat(),
        "routine_title": title,
        "kind": kind,
        "prescribed": prescribed,
    }


def record_target(meta: dict[str, Any], target: dict[str, Any]) -> None:
    """Append an adherence target to the bounded history in meta."""
    targets = meta.setdefault(META_KEY, [])
    targets.append(target)
    meta[META_KEY] = targets[-_KEEP:]


def latest_target(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Return the most recent adherence target, or None if there isn't one."""
    targets = meta.get(META_KEY)
    if isinstance(targets, list) and targets:
        last = targets[-1]
        return last if isinstance(last, dict) else None
    return None


def _exercise_label(
    template_id: str, templates: dict[str, dict[str, Any]] | None
) -> str:
    if templates and template_id in templates:
        title = templates[template_id].get("title")
        if title:
            return str(title)
    return template_id


def _trained_top_weight(
    records_after: list[dict[str, Any]], template_id: str
) -> tuple[float, int]:
    """Best trained top-set weight for a template_id and the #sessions it hit."""
    best = 0.0
    sessions = 0
    for record in records_after:
        hit = False
        for exercise in record["exercises"]:
            if exercise.get("template_id") == template_id:
                best = max(best, exercise.get("top_working_weight_kg") or 0.0)
                hit = True
        if hit:
            sessions += 1
    return best, sessions


def _grade_item(
    item: Any,
    records_after: list[dict[str, Any]],
    templates: dict[str, dict[str, Any]] | None,
) -> tuple[str | None, bool, float | None]:
    """Grade one prescribed exercise. Returns (line, was_trained, load_ratio).

    ``line`` is None for a malformed item (skipped, never counted);
    ``load_ratio`` is None for a not-trained or bodyweight exercise.
    """
    if not isinstance(item, dict) or not item.get("template_id"):
        return None, False, None
    template_id = str(item["template_id"])
    label = _exercise_label(template_id, templates)
    best, sessions = _trained_top_weight(records_after, template_id)
    if sessions == 0:
        return f"- **{label}**: prescribed but **not trained yet**", False, None
    sess = "session" if sessions == 1 else "sessions"
    target_w = item.get("top_weight_kg")
    if not target_w:
        return (
            f"- **{label}**: trained over {sessions} {sess} "
            "(bodyweight — load not graded)",
            True,
            None,
        )
    ratio = best / target_w
    if ratio >= _OVER:
        verdict = f"above target ({ratio:.0%})"
    elif ratio >= _ON_TARGET:
        verdict = f"on target ({ratio:.0%})"
    else:
        verdict = f"under target ({ratio:.0%})"
    line = (
        f"- **{label}**: {best:g} kg vs {target_w:g} kg prescribed over "
        f"{sessions} {sess} — **{verdict}**"
    )
    return line, True, ratio


def grade_target(
    target: dict[str, Any] | None,
    records: list[dict[str, Any]],
    *,
    templates: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    """Render a "Draft adherence" recap, or None if there's no target to grade.

    Grades only objective loads against workouts logged after the push — never
    the written advice. Tolerant of a hand-edited/old-schema target: a malformed
    target or item is skipped, never crashes the (unattended) coach run.
    """
    if not target or not target.get("pushed_on"):
        return None
    try:
        pushed = date.fromisoformat(target["pushed_on"])
    except (ValueError, TypeError):
        return None
    prescribed = target.get("prescribed")
    if not isinstance(prescribed, list) or not prescribed:
        return None

    title = target.get("routine_title") or "guide draft"
    header = [
        f"## Draft adherence — {title}",
        (
            f"_Pushed {pushed.isoformat()}; graded from workouts logged since — "
            "objective loads only, not a judgement of the written advice._"
        ),
    ]

    after = [r for r in records if r["start_time"].date() > pushed]
    if not after:
        return "\n".join(
            [
                *header,
                f"\n_No workouts logged since {pushed.isoformat()} — "
                "the draft hasn't been trained yet._",
            ]
        )

    lines: list[str] = []
    trained = 0
    valid = 0
    ratios: list[float] = []
    for item in prescribed:
        line, was_trained, ratio = _grade_item(item, after, templates)
        if line is None:
            continue
        valid += 1
        if was_trained:
            trained += 1
        if ratio is not None:
            ratios.append(ratio)
        lines.append(line)

    summary = f"\n- Trained **{trained}/{valid}** prescribed lifts since the push"
    if ratios:
        summary += f"; average load **{sum(ratios) / len(ratios):.0%}** of prescribed"
    return "\n".join([*header, summary, *lines])
