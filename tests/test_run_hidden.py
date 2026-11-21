"""scripts/run_hidden.pyw: the windowless launcher the PC's scheduled tasks run
through (docs/local_ops.md, "Every scheduled task starts windowless").

The point of it over `conhost.exe --headless` is that the command's exit code
reaches Task Scheduler: the backup runner exits non-zero when a step fails, and
`scripts/local_mirror_report.read_task` stores the task's last result.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "run_hidden.pyw"

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="CREATE_NO_WINDOW is Windows-only")


def _load():
    loader = importlib.machinery.SourceFileLoader("run_hidden", str(LAUNCHER))
    spec = importlib.util.spec_from_loader("run_hidden", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_no_command_is_an_error_not_a_success():
    assert _load().main([]) == 2


@windows_only
@pytest.mark.parametrize("code", [0, 1, 7])
def test_the_commands_exit_code_comes_back(code):
    assert _load().main([sys.executable, "-c", f"raise SystemExit({code})"]) == code


@windows_only
def test_the_process_exit_code_is_the_commands(tmp_path):
    # The launcher as Task Scheduler runs it: its own process exit code is what
    # Task Scheduler records as the task's last result.
    out = subprocess.run([sys.executable, str(LAUNCHER), sys.executable, "-c", "raise SystemExit(7)"])
    assert out.returncode == 7
