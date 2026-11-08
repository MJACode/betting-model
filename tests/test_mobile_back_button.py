"""The stack's Back button is iOS's own arrow, with no custom label.

Matt, 2026-11-08. On iOS 27.2 the native Back stopped responding after a
pop-up had been opened on the screen (Settings twice, Player Stats after
Compare odds). Apple's reported iOS 27 bug is a Back button carrying a custom
title; the workaround is the minimal display mode with no custom title. A
`headerBackTitle` anywhere brings the custom title back.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _code(text: str) -> str:
    """Source with // and /* */ comments removed, so a comment naming the
    option does not count as setting it."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)//.*$", "", text)


def _sources():
    yield MOBILE / "App.tsx"
    yield from (MOBILE / "src").rglob("*.ts*")


def test_no_screen_sets_a_custom_back_title():
    offenders = [
        str(p.relative_to(ROOT))
        for p in _sources()
        if "headerBackTitle" in _code(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"custom Back title set in: {offenders}"


def test_stack_uses_the_minimal_back_button():
    app = _code((MOBILE / "App.tsx").read_text(encoding="utf-8"))
    nav = re.search(r"<Stack\.Navigator\b(.*?)>", app, flags=re.S)
    assert nav, "Stack.Navigator not found in App.tsx"
    assert re.search(r"headerBackButtonDisplayMode:\s*'minimal'", nav.group(1)), (
        "Stack.Navigator must set screenOptions headerBackButtonDisplayMode: 'minimal'"
    )
