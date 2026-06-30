"""Configuration loading for hevy-brain.

Reads optional ``config.toml`` from the repo/working directory and merges it
with defaults. Secrets (API keys) only ever come from environment variables.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .analytics import landmarks

DEFAULT_CONFIG_FILE = "config.toml"


@dataclass
class Config:
    """Runtime configuration."""

    base_dir: Path
    vault_path: Path
    vault_subfolder: str = "Hevy"
    knowledge_path: Path | None = None
    knowledge_topics: list[str] = field(default_factory=lambda: ["training"])
    data_dir: Path = Path("data")
    page_size: int = 10
    coach_model: str = "claude-opus-4-8"
    coach_max_calls_per_day: int = 4
    plateau_weeks: int = 4
    push_pull_low: float = 0.8
    push_pull_high: float = 1.25
    review_weeks: int = 4
    review_months: int = 2
    lapse_nudge_days: int = 7
    deload_weeks: int = 6
    deload_rpe: float = 8.5
    muscle_overrides: dict[str, str] = field(default_factory=dict)
    guide_lapse_days: int = 14
    guide_load_fraction: float = 0.6
    guide_draft_limit: int = 3
    guide_baseline_weeks: int = 4
    guide_redesign_weeks: int = 8
    charts_enabled: bool = True
    charts_volume_weeks: int = 12
    charts_e1rm_points: int = 10
    charts_heatmap_enabled: bool = True
    charts_heatmap_weeks: int = 26
    progression_enabled: bool = True
    progression_rep_low: int = 8
    progression_rep_high: int = 12
    progression_increment_kg: float = 2.5
    progression_min_sessions: int = 3
    landmark_weeks: int = 4
    landmark_bands: dict[str, dict[str, float]] = field(
        default_factory=landmarks.default_bands
    )

    @property
    def vault_root(self) -> Path:
        """Folder inside the vault that hevy-brain owns."""
        return self.vault_path / self.vault_subfolder

    @property
    def knowledge_root(self) -> Path:
        r"""Folder holding the read-only knowledge layer (topics/notes/_meta).

        Since the 27/06/2026 three-zone reorg these folders live under the
        vault's ``brain/`` zone, so ``[knowledge] path`` must point there (the
        canonical config.toml uses ``C:\\Users\\samra\\vault\\brain``). The
        ``vault_path`` fallback is a legacy default that no longer resolves on
        its own.
        """
        return self.knowledge_path or self.vault_path

    @property
    def hevy_api_key(self) -> str | None:
        """Hevy API key from the environment (never from config files)."""
        return os.environ.get("HEVY_API_KEY")

    @property
    def anthropic_api_key(self) -> str | None:
        """Anthropic API key from the environment (never from config files)."""
        return os.environ.get("ANTHROPIC_API_KEY")


def load_config(
    base_dir: Path | None = None, config_file: Path | None = None
) -> Config:
    """Load config.toml (if present) merged over defaults."""
    base = (base_dir or Path.cwd()).resolve()
    path = config_file or base / DEFAULT_CONFIG_FILE
    raw: dict = {}
    if path.is_file():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))

    vault = raw.get("vault", {})
    sync = raw.get("sync", {})
    coach = raw.get("coach", {})
    analytics = raw.get("analytics", {})
    knowledge = raw.get("knowledge", {})
    guide = raw.get("guide", {})
    charts = raw.get("charts", {})
    progression = raw.get("progression", {})
    landmarks_cfg = raw.get("landmarks", {})

    # User per-group band overrides merge onto the published defaults, so a user
    # can move a single band without re-specifying every group.
    landmark_bands = landmarks.default_bands()
    for group, band in (landmarks_cfg.get("bands", {}) or {}).items():
        landmark_bands[group] = {
            "mev": float(band["mev"]),
            "mav": float(band["mav"]),
            "mrv": float(band["mrv"]),
        }

    vault_path = Path(vault.get("path", "vault_staging"))
    if not vault_path.is_absolute():
        vault_path = base / vault_path
    data_dir = Path(sync.get("data_dir", "data"))
    if not data_dir.is_absolute():
        data_dir = base / data_dir

    knowledge_path: Path | None = None
    if knowledge.get("path"):
        knowledge_path = Path(knowledge["path"])
        if not knowledge_path.is_absolute():
            knowledge_path = base / knowledge_path

    return Config(
        base_dir=base,
        vault_path=vault_path,
        vault_subfolder=vault.get("subfolder", "Hevy"),
        knowledge_path=knowledge_path,
        knowledge_topics=list(knowledge.get("topics", ["training"])),
        data_dir=data_dir,
        page_size=int(sync.get("page_size", 10)),
        coach_model=coach.get("model", "claude-opus-4-8"),
        coach_max_calls_per_day=int(coach.get("max_calls_per_day", 4)),
        plateau_weeks=int(analytics.get("plateau_weeks", 4)),
        push_pull_low=float(analytics.get("push_pull_low", 0.8)),
        push_pull_high=float(analytics.get("push_pull_high", 1.25)),
        review_weeks=int(analytics.get("review_weeks", 4)),
        review_months=int(analytics.get("review_months", 2)),
        lapse_nudge_days=int(analytics.get("lapse_nudge_days", 7)),
        deload_weeks=int(analytics.get("deload_weeks", 6)),
        deload_rpe=float(analytics.get("deload_rpe", 8.5)),
        muscle_overrides=dict(analytics.get("muscle_overrides", {})),
        guide_lapse_days=int(guide.get("lapse_days", 14)),
        guide_load_fraction=float(guide.get("load_fraction", 0.6)),
        guide_draft_limit=int(guide.get("draft_limit", 3)),
        guide_baseline_weeks=int(guide.get("baseline_weeks", 4)),
        guide_redesign_weeks=int(guide.get("redesign_weeks", 8)),
        charts_enabled=bool(charts.get("enabled", True)),
        charts_volume_weeks=int(charts.get("volume_weeks", 12)),
        charts_e1rm_points=int(charts.get("e1rm_points", 10)),
        charts_heatmap_enabled=bool(charts.get("heatmap_enabled", True)),
        charts_heatmap_weeks=int(charts.get("heatmap_weeks", 26)),
        progression_enabled=bool(progression.get("enabled", True)),
        progression_rep_low=int(progression.get("rep_low", 8)),
        progression_rep_high=int(progression.get("rep_high", 12)),
        progression_increment_kg=float(progression.get("increment_kg", 2.5)),
        progression_min_sessions=int(progression.get("min_sessions", 3)),
        landmark_weeks=int(landmarks_cfg.get("weeks", 4)),
        landmark_bands=landmark_bands,
    )
