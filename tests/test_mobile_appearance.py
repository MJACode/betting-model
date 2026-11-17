"""Appearance: System / Light / Dark (Matt, 2026-11-16).

The behavioural pins live in mobile/scripts/verify_appearance.ts (the pure
rules, the boot order, theme.ts picking its palette at import) and the Dark
palette's contrast in mobile/scripts/verify_contrast_tokens.ts. These run both.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_a_theme_change_never_reloads_the_runtime():
    """lib/otaUpdate.ts: no in-process reload (2026-10-19 crash). A theme
    change applies at the next open instead."""
    lib = _read(MOBILE / "src/lib/appearance.ts")
    assert "next open" in lib.lower()
    for path in (MOBILE / "index.tsx", MOBILE / "src/hooks/useAppearance.ts"):
        assert "reloadAsync" not in _read(path), path


def test_default_is_light_opt_in():
    assert "export const APPEARANCE_DEFAULT: AppearancePref = 'light';" in _read(
        MOBILE / "src/lib/appearance.ts"
    )


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
@pytest.mark.parametrize("script", ["verify_appearance.ts", "verify_contrast_tokens.ts"])
def test_the_behavioural_checks_pass(script: str):
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), f"scripts/{script}"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
