"""The player page's added sections (2026-09-20).

Matt: "do the same for player props, there should be more helpful information
there." screens/PlayerStatsScreen.tsx gained, around its existing hit-rate
chart: tonight's posted line for the selected stat with the member's best
over / under price, DraftKings' movement since open and Pinnacle's no-vig
read; the same threshold split home / away / vs tonight's opponent (and
starter / bench in basketball); season Statcast for MLB; and our settled
record on the player, per market, in units. Data in hooks/usePlayerDetail.ts,
reductions in lib/playerDetail.ts. No node on the machines that run this
suite, so the TypeScript-level facts are pinned structurally here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SCREEN = MOBILE / "src" / "screens" / "PlayerStatsScreen.tsx"
HOOK = MOBILE / "src" / "hooks" / "usePlayerDetail.ts"
LIB = MOBILE / "src" / "lib" / "playerDetail.ts"
QUERIES = MOBILE / "src" / "lib" / "queries.ts"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_chart_follows_the_posted_line_until_the_reader_moves_it():
    """A hit rate at the median when the book hangs a different number answers
    a question nobody asked. The ruler snaps to the posted line, once, and a
    stepped ruler is never overridden."""
    screen = _read(SCREEN)
    assert "thresholdFromBookLine(detail.tonight.line)" in screen
    assert "lineTouched" in screen
    m = re.search(r"const stepLine = \(deltaSteps: number\) => \{\n\s*setLineTouched\(true\);", screen)
    assert m, "stepping the ruler must mark it as the reader's"


def test_the_book_line_to_threshold_conversion_is_the_boards():
    """5.5 → 6+, and a whole-number line stays itself (a push at exactly 7)."""
    lib = _read(LIB)
    m = re.search(r"export function thresholdFromBookLine\(line: number\): number \{\n(.*?)\n\}", lib, re.S)
    assert m
    assert "Number.isInteger(line) ? line : Math.ceil(line)" in m.group(1)


def test_the_player_record_read_is_the_record_filter_on_the_server():
    q = _read(QUERIES)
    m = re.search(r"export async function fetchSettledPropPicksForPlayer\(.*?\n\}\n", q, re.S)
    assert m, "fetchSettledPropPicksForPlayer is missing"
    body = m.group(0)
    assert ".from('picks')" in body
    assert ".eq('signal_type', 'BET')" in body
    assert ".in('result', ['WIN', 'LOSS', 'PUSH'])" in body
    assert "model_action_thresholds" not in body, "a record query never joins the threshold table (§1c)"
    # nfl_prop_market writes player_key and no player_id (39 of 39 settled
    # BETs, measured 2026-09-20) -- the label match is what finds those.
    assert "pick_label.ilike" in body


def test_every_player_page_read_names_its_relation_literally():
    hook = _read(HOOK)
    for fn in (
        "fetchPropLineRows",
        "fetchPropOddsHistory",
        "fetchGamesByIds",
        "fetchSettledPropPicksForPlayer",
        "fetchSavantStats",
        "fetchLineupSlot",
        "fetchSlateGames",
    ):
        assert fn in hook, f"usePlayerDetail no longer reads through {fn}"
    q = _read(QUERIES)
    for fn, rel in (
        ("fetchPropLineRows", "v_latest_prop_odds_all_books"),
        ("fetchPropOddsHistory", "player_prop_odds"),
        ("fetchGamesByIds", "games"),
        ("fetchSavantStats", "player_savant_stats"),
        ("fetchLineupSlot", "lineup_slots"),
    ):
        m = re.search(rf"export async function {fn}\(.*?\n\}}\n", q, re.S)
        assert m, f"{fn} is missing from queries.ts"
        assert f".from('{rel}')" in m.group(0), f"{fn} must read '{rel}' by literal name"


def test_units_never_price_an_unpriced_pick():
    lib = _read(LIB)
    m = re.search(r"export function playerPickRecord\(.*?\n\}\n", lib, re.S)
    assert m
    assert "hasPricedLine(p)" in m.group(0)
    assert "unpriced" in m.group(0)


def test_results_are_units_never_dollars_and_never_paper():
    for p in (SCREEN, LIB, HOOK):
        src = _read(p)
        assert "formatCurrency" not in src, f"{p.name} formats a result as money"
        assert not re.search(r"\$\d", src), f"{p.name} prints a dollar figure"
        assert "paper" not in src.lower(), f"{p.name} mentions paper trading"


def test_the_hook_is_plain_effects_only():
    assert "useFocusEffect(" not in _read(HOOK)


def test_the_starter_split_reads_the_integer_column():
    """nba/wnba_player_game_log.is_starter is `integer` (measured); a boolean
    comparison would be a TypeScript error against the log's index signature
    and would never match a row."""
    lib = _read(LIB)
    m = re.search(r"export function statSplits\(.*?\n\}\n", lib, re.S)
    assert m
    assert "s === 1 || s === '1'" in m.group(0)
    assert "s === true" not in m.group(0)
