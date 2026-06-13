"""Tests for config loading, including the knowledge-bridge settings."""

from __future__ import annotations

from pathlib import Path

from hevy_brain.config import load_config


def test_knowledge_root_defaults_to_vault_path(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        "[vault]\npath = 'my_vault'\nsubfolder = 'Hevy'\n", encoding="utf-8"
    )
    config = load_config(base_dir=tmp_path)

    assert config.knowledge_path is None
    assert config.knowledge_root == config.vault_path
    assert config.knowledge_topics == ["training"]


def test_knowledge_path_and_topics_override(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        "[vault]\npath = 'my_vault'\n\n"
        "[knowledge]\npath = 'brain'\ntopics = ['training', 'sleep']\n",
        encoding="utf-8",
    )
    config = load_config(base_dir=tmp_path)

    assert config.knowledge_path == (tmp_path / "brain").resolve()
    assert config.knowledge_root == (tmp_path / "brain").resolve()
    assert config.knowledge_topics == ["training", "sleep"]


def test_charts_config_defaults_and_overrides(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        "[vault]\npath = 'v'\n", encoding="utf-8"
    )
    default = load_config(base_dir=tmp_path)
    assert default.charts_enabled is True
    assert default.charts_volume_weeks == 12
    assert default.charts_e1rm_points == 10

    (tmp_path / "config.toml").write_text(
        "[vault]\npath = 'v'\n\n"
        "[charts]\nenabled = false\nvolume_weeks = 8\ne1rm_points = 20\n",
        encoding="utf-8",
    )
    overridden = load_config(base_dir=tmp_path)
    assert overridden.charts_enabled is False
    assert overridden.charts_volume_weeks == 8
    assert overridden.charts_e1rm_points == 20


def test_absolute_knowledge_path_is_respected(tmp_path: Path) -> None:
    abs_path = (tmp_path / "elsewhere").resolve()
    (tmp_path / "config.toml").write_text(
        f"[vault]\npath = 'v'\n\n[knowledge]\npath = '{abs_path.as_posix()}'\n",
        encoding="utf-8",
    )
    config = load_config(base_dir=tmp_path)

    assert config.knowledge_path == abs_path
