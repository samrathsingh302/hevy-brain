"""The Dataview/Bases starter pack (A6) — Hevy/Queries.md.

A single managed note of ready-made queries over the frontmatter every
hevy-brain note already carries (#hevy/workout, #hevy/exercise,
#hevy/review/*). The queries run **live** in Obsidian (Dataview plugin), so
they stay fresh without hevy-brain regenerating them, and the user can add
their own below the managed marker.

The note is intentionally static (no per-build timestamp) so it's written once
and never churns; only a change to the query set here re-renders it.
"""

from __future__ import annotations

from .writer import render_note

_BODY = """# Queries

Ready-made [Dataview](https://github.com/blacksmithgu/obsidian-dataview)
queries over your Hevy notes. They run **live** in Obsidian — install the
**Dataview** community plugin and they populate automatically; nothing here
needs hevy-brain to refresh. Add your own queries below the
`%% hevy-brain:end %%` marker and they'll survive every regeneration.

## Recent workouts

```dataview
TABLE date AS Date, volume_kg AS "Volume (kg)", duration_min AS Min, total_reps AS Reps
FROM #hevy/workout
SORT date DESC
LIMIT 20
```

## Biggest sessions by volume

```dataview
TABLE date AS Date, volume_kg AS "Volume (kg)", exercise_count AS Exercises
FROM #hevy/workout
SORT volume_kg DESC
LIMIT 10
```

## This month's training

```dataview
TABLE date AS Date, title AS Workout, volume_kg AS "Volume (kg)"
FROM #hevy/workout
WHERE date >= date(today) - dur("28 days")
SORT date DESC
```

## Strongest lifts (estimated 1RM)

```dataview
TABLE best_e1rm_kg AS "Est 1RM", best_weight_kg AS "Top", times_performed AS Sessions
FROM #hevy/exercise
SORT best_e1rm_kg DESC
LIMIT 20
```

## Most-trained exercises

```dataview
TABLE times_performed AS Sessions, last_performed AS Last, total_volume_kg AS Volume
FROM #hevy/exercise
SORT times_performed DESC
LIMIT 20
```

## Lifts going stale (train these)

```dataview
TABLE last_performed AS "Last trained", times_performed AS Sessions
FROM #hevy/exercise
SORT last_performed ASC
LIMIT 15
```

## Weekly review log

```dataview
TABLE sessions AS Sessions, volume_kg AS "Volume (kg)"
FROM #hevy/review/weekly
SORT start DESC
```

## Monthly review log

```dataview
TABLE sessions AS Sessions, volume_kg AS "Volume (kg)"
FROM #hevy/review/monthly
SORT month DESC
```

## Bases (Obsidian's built-in database)

Prefer Obsidian **Bases** (core, 1.9+) over the Dataview plugin? Create a base
and filter on `tags contains "hevy/workout"`, then add columns for `date`,
`volume_kg`, and `duration_min` — the same frontmatter powers both. Dataview
above is the zero-setup option."""


def render_queries() -> str:
    """Render the static Queries.md starter pack (managed content)."""
    return render_note({"tags": ["hevy/queries"]}, _BODY)
