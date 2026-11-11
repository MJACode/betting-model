"""The NCAAF moneyline model in the app (UX review, 2026-11-10).

`ncaaf_moneyline_market` decides each game once, at 14:00 UTC on game day
(scripts/ncaaf_moneyline_card.py), and bets a moneyline, which has no line.
The app's default copy said picks lock "at the first scoring run of the day
... at the line and price shown" and sent a member back "after the next
pipeline refresh". These pin the page and the pick note to what the card does.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_META = ROOT / "mobile" / "src" / "lib" / "modelMeta.ts"
MARKETS = ROOT / "mobile" / "src" / "lib" / "markets.ts"
MODEL_ID = "ncaaf_moneyline_market"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _list(src: str, name: str) -> str:
    m = re.search(rf"const {name}: readonly string\[\] = \[(.*?)\];", src, re.S)
    assert m, f"{name} not found"
    return m.group(1)


def test_its_page_says_when_it_decides_and_its_cap():
    src = _read(MODEL_META)
    assert f"'{MODEL_ID}'" in _list(src, "GAME_MORNING_MODELS")
    body = re.search(r"const GAME_MORNING_BODY: Readonly<Record<string, string>> = \{(.*?)\n\};", src, re.S)
    assert body, "GAME_MORNING_BODY not found"
    mine = re.search(rf"{MODEL_ID}:\s*((?:\s*'[^']*'\s*\+?)+)", body.group(1))
    assert mine, "the model has no page body of its own"
    text = "".join(re.findall(r"'([^']*)'", mine.group(1)))
    # 14:00 UTC: 10am ET on daylight time, 9am ET once the clocks go back.
    assert "at 10am ET on game day (9am ET from early November)" in text
    assert "never lays more than -200" in text
    assert "never re-priced" in text
    # a moneyline has no line: the page must not promise one
    assert "line and price" not in text


def test_its_probability_note_is_its_own():
    src = _read(MODEL_META)
    notes = re.search(r"const PROBABILITY_NOTE[^=]*=\s*\{(.*?)\n\};", src, re.S)
    assert notes, "PROBABILITY_NOTE not found"
    assert re.search(rf"\b{MODEL_ID}:", notes.group(1)), "the model falls back to the default note"


def test_its_pick_note_is_posted_once_at_a_price_with_no_line():
    src = _read(MARKETS)
    assert f"'{MODEL_ID}'" in _list(src, "POSTED_MONEYLINE_MODELS")
    assert f"pick.model_id === '{MODEL_ID}'" in src, "the pick is not in the posted-once branch"
