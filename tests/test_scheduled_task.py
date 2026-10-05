"""Tests for the scheduled-task action register_task.ps1 builds.

The task runs ``wscript run_hidden.vbs cmd.exe /c "<python> -m hevy_brain.cli
<command> >> <log> 2>&1"``. No powershell.exe in the chain: Windows PowerShell
5.1 under -Command exits 1 when a native command writes stderr under a
redirect, so the task read red while Python had exited 0. These run the real
script and the real wrapper; nothing is ever registered.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows Task Scheduler only"
)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _task_arguments() -> str:
    # Read-only snapshot of the registered actions (empty if none exist).
    # Fixed, test-owned command lines throughout this module (S603/S607).
    proc = subprocess.run(
        [  # noqa: S607
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-ScheduledTask -TaskName 'HevyBrain*' -ErrorAction SilentlyContinue"
                " | ForEach-Object { $_.TaskName + '|' + $_.Actions[0].Arguments }"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return proc.stdout


def test_dry_run_prints_cmd_actions_and_registers_nothing() -> None:
    before = _task_arguments()
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPTS / "register_task.ps1"),
            "-DryRun",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        for token in (
            "run_hidden.vbs",
            "cmd.exe /c",
            "-m hevy_brain.cli",
            ">>",
            "2>&1",
        ):
            assert token in line
        assert "powershell" not in line.lower()
    assert _task_arguments() == before


def _run_wrapped(tmp_path: Path, exit_code: int) -> tuple[int, str]:
    # The production shape through the real wrapper; the child writes one line
    # to stderr and exits with exit_code. The code has no spaces or double quotes
    # (wscript cannot carry nested quotes), like the real python/log paths.
    log = tmp_path / "task.log"
    code = (
        r"__import__('sys').stderr.write('hb-stderr-line\n');"
        f"__import__('sys').exit({exit_code})"
    )
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "wscript.exe",
            "//B",
            "//Nologo",
            str(SCRIPTS / "run_hidden.vbs"),
            "cmd.exe",
            "/c",
            f"{sys.executable} -c {code} >> {log} 2>&1",
        ],
        timeout=60,
        check=False,
    )
    return proc.returncode, log.read_text(encoding="utf-8", errors="replace")


def test_stderr_with_exit_zero_reads_green_and_lands_in_log(tmp_path: Path) -> None:
    if " " in sys.executable or " " in str(tmp_path):
        pytest.skip("the cmd.exe action needs space-free paths")
    rc, log = _run_wrapped(tmp_path, 0)
    assert rc == 0
    assert "hb-stderr-line" in log


def test_child_exit_code_is_the_task_result(tmp_path: Path) -> None:
    if " " in sys.executable or " " in str(tmp_path):
        pytest.skip("the cmd.exe action needs space-free paths")
    rc, log = _run_wrapped(tmp_path, 3)
    assert rc == 3
    assert "hb-stderr-line" in log
