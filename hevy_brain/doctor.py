"""hevy-brain doctor - read-only health checks (D2).

Verifies the things that quietly break the unattended pipeline: the API key,
the configured vault path, a non-empty cache, sync freshness, and whether the
vault has been built. Pure and offline - every check reads env / config / cache
/ filesystem only, so it is fully testable and never touches Hevy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .store.cache import CacheStore

OK = "ok"
WARN = "warn"
FAIL = "fail"

# The sync task runs hourly, so anything older than this is stale.
_SYNC_STALE_HOURS = 25


@dataclass
class Check:
    """One health-check result."""

    name: str
    status: str
    detail: str


def _parse_iso(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _sync_freshness(meta: dict, now: datetime) -> Check:
    last = _parse_iso(meta.get("last_sync"))
    if last is None:
        return Check("Sync freshness", WARN, "never synced - run 'hevy-brain sync'")
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    age_hours = (now - last).total_seconds() / 3600
    if age_hours < 0:
        return Check("Sync freshness", WARN, "last_sync is in the future - clock skew?")
    if age_hours <= _SYNC_STALE_HOURS:
        return Check("Sync freshness", OK, f"last synced {age_hours:.1f}h ago")
    return Check(
        "Sync freshness",
        WARN,
        f"last synced {age_hours / 24:.1f} days ago - the hourly task may be down",
    )


def run_checks(config: Config, store: CacheStore, now: datetime) -> list[Check]:
    """Run all health checks and return their results (read-only)."""
    checks: list[Check] = []

    if config.hevy_api_key:
        checks.append(Check("Hevy API key", OK, "HEVY_API_KEY is set"))
    else:
        checks.append(
            Check("Hevy API key", FAIL, "HEVY_API_KEY not set - sync/push won't work")
        )

    if config.anthropic_api_key:
        checks.append(Check("Anthropic API key", OK, "set - 'coach --api' available"))
    else:
        checks.append(
            Check(
                "Anthropic API key",
                WARN,
                "not set - free coach path only (fine unless you use --api)",
            )
        )

    if config.vault_path.is_dir():
        checks.append(Check("Vault path", OK, str(config.vault_path)))
    else:
        checks.append(Check("Vault path", FAIL, f"{config.vault_path} does not exist"))

    count = len(store.workouts)
    if count > 0:
        checks.append(Check("Cache", OK, f"{count} workouts cached"))
    else:
        checks.append(
            Check("Cache", FAIL, "no workouts cached - run 'hevy-brain sync'")
        )

    checks.append(_sync_freshness(store.meta, now))

    if (config.vault_root / "Dashboard.md").is_file():
        checks.append(Check("Vault built", OK, "Dashboard.md present"))
    else:
        checks.append(
            Check("Vault built", WARN, "no Dashboard.md - run 'hevy-brain vault'")
        )

    return checks


def worst_status(checks: list[Check]) -> str:
    """Return the most severe status across checks (fail > warn > ok)."""
    if any(c.status == FAIL for c in checks):
        return FAIL
    if any(c.status == WARN for c in checks):
        return WARN
    return OK
