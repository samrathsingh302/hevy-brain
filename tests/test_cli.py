"""Tests for CLI output configuration."""

from __future__ import annotations

import io
import sys

import pytest

from hevy_brain.cli import _configure_output


def test_configure_output_survives_cp1252_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dry-run diff prints '→'; a cp1252 Windows console must not crash
    (live finding 13/06/2026: the first dry-run died mid-print)."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    _configure_output()
    sys.stdout.write("80kg ×6–8 → 47.5kg ×6–8\n")
    stream.flush()

    assert b"47.5kg" in buffer.getvalue()


def test_configure_output_tolerates_streams_without_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    _configure_output()  # must not raise
