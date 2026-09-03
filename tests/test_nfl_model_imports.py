"""The nfl/ cards must import their own models under the SCHEDULER's invocation.

WHY THIS FILE EXISTS

`scripts/weekly_wind_card.py` failed on every scheduled run -- hourly in the
Railway deploy log -- with:

    from models.wind_totals import select_bets, UNIT_PCT, MAX_CALIBRATED_LEAD
    ModuleNotFoundError: No module named 'models.wind_totals'

and nothing caught it, because nothing exercised the way production actually
starts these scripts. The card is `nfl_wind_totals`, a LIVE insert-once model
(CLAUDE.md 1c), and it had been producing nothing.

THE MECHANISM, because it is not obvious and it will recur.

`nfl/models/` has no `__init__.py`, so it is a PEP 420 namespace portion. The
platform's top-level `models/` HAS one, so it is a regular package. When both
roots are on sys.path, Python records the namespace portion and KEEPS LOOKING,
and **a regular package found later wins over a namespace portion regardless of
path order**. So `sys.path.insert(0, <nfl root>)` does NOT save the bare import,
and the failure is a hard ModuleNotFoundError rather than a fallback.

Both roots are on sys.path on every scheduled run: scheduler.py sets
PYTHONPATH=<repo root> in BASE_ENV so these children can `import monitoring`,
and the scripts insert the nfl root themselves.

`scripts/nfl_preflight.py` asserted production was safe "because the scheduler
runs them with cwd=nfl/". **cwd is not sys.path** -- for `python scripts/foo.py`
sys.path[0] is the SCRIPT's directory, and cwd never enters into it. The card was
broken for as long as that reasoning stood.

These tests run the real thing in a SUBPROCESS with the real environment,
because that is the only thing the bug was visible from.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NFL = ROOT / "nfl"

# Exactly what scheduler.py's BASE_ENV does: repo root on PYTHONPATH, cwd=nfl/.
def _scheduler_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return env


def _import_under_scheduler_env(module_path: Path) -> subprocess.CompletedProcess:
    """Import one nfl script the way the scheduler starts it, in a subprocess."""
    code = (
        "import importlib.util, sys, os\n"
        # sys.path[0] is the script's own directory when run as `python scripts/x.py`
        f"sys.path.insert(0, {str(module_path.parent)!r})\n"
        f"spec = importlib.util.spec_from_file_location('under_test', {str(module_path)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['under_test'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "print('IMPORT_OK')\n"
    )
    return subprocess.run([sys.executable, "-c", code], cwd=str(NFL),
                          env=_scheduler_env(), capture_output=True, text=True,
                          timeout=120)


CARDS = ["weekly_wind_card.py", "replay_wind_card.py", "backtest_ev.py"]


@pytest.mark.parametrize("script", CARDS)
def test_the_card_imports_under_the_schedulers_invocation(script):
    """The regression. Before the fix this failed with ModuleNotFoundError on
    weekly_wind_card and replay_wind_card, which is what production saw."""
    r = _import_under_scheduler_env(NFL / "scripts" / script)
    assert "IMPORT_OK" in r.stdout, (
        f"{script} cannot be imported the way the scheduler runs it "
        f"(cwd=nfl/, PYTHONPATH=<repo root>):\n{r.stderr[-2000:]}")


def test_the_loader_reaches_nfls_models_not_the_platforms():
    """The whole point: nfl/models/wind_totals.py, never the platform package."""
    code = (
        "import sys, os\n"
        f"sys.path.insert(0, {str(NFL)!r})\n"
        "from _nfl_models import load_nfl_model\n"
        "w = load_nfl_model('wind_totals')\n"
        "print(w.__file__)\n"
        "import models; print(models.__file__)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(NFL),
                       env=_scheduler_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    loaded, platform_models = r.stdout.strip().splitlines()[:2]
    assert loaded == str(NFL / "models" / "wind_totals.py"), loaded
    # And it did NOT do so by shadowing the platform's package for everyone else.
    assert platform_models.startswith(str(ROOT / "models")), platform_models


def test_no_nfl_script_uses_the_bare_models_import():
    """The cheap tripwire. `from models.x import ...` under nfl/ resolves to the
    PLATFORM's models package whenever both roots are on sys.path, which is
    every scheduled run. Use nfl/_nfl_models.load_nfl_model instead."""
    bare = re.compile(r"^\s*(?:from\s+models\.|from\s+models\s+import|import\s+models\b)", re.M)
    # The loader itself QUOTES the bad import, in the docstring that explains why
    # it exists. Exempting it by name is honest; stripping docstrings so the
    # regex cannot see them would also blind this test to a real import hidden
    # under one.
    exempt = {"nfl/_nfl_models.py"}
    offenders = []
    for path in NFL.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.relative_to(ROOT).as_posix() in exempt:
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        # Strip the docstrings/comments that legitimately QUOTE the bad import.
        code_only = "\n".join(
            ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
        if bare.search(code_only):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], (
        "these nfl/ modules use a bare `models` import, which resolves to the "
        "platform's package on every scheduled run: " + ", ".join(offenders))


def test_the_exemption_is_the_loader_and_it_still_exists():
    """An exemption naming a file that no longer exists pre-approves whatever
    takes its place."""
    assert (NFL / "_nfl_models.py").exists()
