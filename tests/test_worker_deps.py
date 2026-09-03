"""The worker's requirements.txt must not carry weight the worker never uses.

WHY THIS FILE EXISTS
The Railway worker's start command is `python scheduler.py`. Its image was
1.17 GB, and a deploy on 2026-09-02 stalled pushing it -- 618 MB in, the push
dropped to ~65 KB/s and the new container did not go live for over half an
hour. A big image is not just slow; it is a failure mode.

Measured from the installed tree, 2026-09-03:

    nvidia-nccl-cu12   475.7 MB   transitive dep of `xgboost` on Linux
    xgboost            239.0 MB   19.3 MB as xgboost-cpu
    plotly              58.9 MB   imported only by dashboard/app.py
    pydeck              47.5 MB   nothing imports it directly
    matplotlib          37.0 MB   nothing imports it directly
    streamlit           33.0 MB   imported only by dashboard/app.py

None of it is reachable from the worker. The repo asks for a GPU exactly
nowhere, and the Streamlit dashboard runs on Matt's machine.

These tests are the tripwire for the next `pip install` that quietly puts it
all back. They read the requirements files as text on purpose -- the point is
what gets INSTALLED on the container, which is not observable from the
importable environment a test happens to run in.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
WORKER_REQS = ROOT / "requirements.txt"
DASHBOARD_REQS = ROOT / "requirements-dashboard.txt"

# encoding="utf-8": read_text() with no encoding uses the PLATFORM default and
# raises UnicodeDecodeError on the box this suite actually runs on (section 7).
def _requirements(path: Path) -> list[str]:
    """Package names actually requested, comments and pins stripped."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        out.append(re.split(r"[<>=!~\[; ]", line, 1)[0].strip().lower())
    return out


# ── the GPU stack ─────────────────────────────────────────────────────────────

def test_the_worker_asks_for_the_cpu_build_of_xgboost():
    """`xgboost` drags in nvidia-nccl-cu12: 475.7 MB on a container with no GPU.
    xgboost-cpu is the same project, version and import name without it."""
    reqs = _requirements(WORKER_REQS)
    assert "xgboost-cpu" in reqs, "the CPU build is not requested"
    assert "xgboost" not in reqs, (
        "requirements.txt asks for plain `xgboost`, which pulls nvidia-nccl-cu12 "
        "(475.7 MB) onto a container that never uses a GPU")


def test_nothing_in_the_repo_actually_wants_a_gpu():
    """The claim that justifies the CPU build. If someone adds GPU training this
    fails, and the requirement should go back to plain xgboost with it."""
    gpu = re.compile(r"gpu_hist|gpu_predictor|device\s*=\s*['\"]cuda|tree_method\s*=\s*['\"]gpu")
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", "node_modules/", "mobile/")):
            continue
        if gpu.search(path.read_text(encoding="utf-8", errors="replace")):
            offenders.append(rel)
    assert offenders == [], (
        "these modules ask for GPU training, so xgboost-cpu is now the wrong "
        "dependency: " + ", ".join(offenders))


# ── the dashboard stack ───────────────────────────────────────────────────────

DASHBOARD_ONLY = ("streamlit", "plotly")


@pytest.mark.parametrize("pkg", DASHBOARD_ONLY)
def test_dashboard_packages_are_not_on_the_worker(pkg):
    assert pkg not in _requirements(WORKER_REQS), (
        f"{pkg} is back in requirements.txt; it belongs in "
        f"requirements-dashboard.txt unless something outside dashboard/ imports it")
    assert pkg in _requirements(DASHBOARD_REQS), f"{pkg} is in neither file"


@pytest.mark.parametrize("pkg", DASHBOARD_ONLY)
def test_only_the_dashboard_imports_them(pkg):
    """The predicate that makes the split safe. The moment a module outside
    dashboard/ imports one of these, the worker needs it back -- and this fails
    rather than letting the container ImportError at boot."""
    pattern = re.compile(rf"^\s*(?:import {pkg}|from {pkg}[. ])", re.M)
    importers = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", "node_modules/", "mobile/", "dashboard/")):
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
            importers.append(rel)
    assert importers == [], (
        f"{pkg} is imported outside dashboard/ ({', '.join(importers)}), so it "
        f"must move back into requirements.txt or the worker will ImportError")


def test_the_dashboard_file_is_additive_not_a_replacement():
    """Someone installing only the dashboard file would get a machine that
    cannot run anything else. The header has to say so."""
    text = DASHBOARD_REQS.read_text(encoding="utf-8")
    assert "requirements.txt" in text, (
        "requirements-dashboard.txt does not tell the reader it is installed "
        "ALONGSIDE requirements.txt")
