"""NHL joins the Today look-ahead UFC, NFL and NCAAF already have.

`nhl_moneyline` wrote a BET plus AVOID/NONE for game_date 2026-09-29. The
scorer's outer bound for NHL is ``config.GAME_SCORE_AHEAD_DAYS`` (7): a
game dated exactly that far out is scored. ``useTodayPicks`` fetched that
kind of window for UFC, NFL and NCAAF and not for NHL, so the sport chip
— the set of ``pick.sport`` values in the hook's rows — stayed muted and
the picks never reached Today.

The chip has no sport allowlist of its own. This file pins the fetch, the
window, and that the chip reads the hook. It does not call Supabase.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
HOOK = MOBILE / "src" / "hooks" / "useTodayPicks.ts"
QUERIES = MOBILE / "src" / "lib" / "queries.ts"
PICKS = MOBILE / "src" / "screens" / "PicksHomeScreen.tsx"

# The slate the bug names. Seven days before it is inside a 7-day window
# and outside a same-day read.
_OPENER = date(2026, 9, 29)
_BEFORE = date(2026, 9, 22)


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with
    # no encoding uses cp1252 and dies on box-drawing characters at collection
    # time (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    start = src.index(f"export async function {name}")
    nxt = src.find("\nexport async function ", start + 1)
    if nxt == -1:
        nxt = src.find("\n// Live ", start + 1)
    assert nxt != -1, f"could not bound {name}"
    return src[start:nxt]


def test_the_reported_slate_sits_on_the_scorer_horizon():
    span = (_OPENER - _BEFORE).days
    assert span == 7
    assert config.GAME_SCORE_AHEAD_DAYS == span
    assert "NHL" in config.GAME_SCORE_AHEAD_SPORTS
    # Same bound the scorer uses: game_date > today AND game_date <= today+N.
    horizon = _BEFORE + timedelta(days=config.GAME_SCORE_AHEAD_DAYS)
    assert _BEFORE < _OPENER <= horizon


def test_use_today_picks_fetches_nhl_across_that_window():
    src = _read(HOOK)
    days = re.search(r"const NHL_AHEAD_DAYS = (\d+);", src)
    assert days, "NHL_AHEAD_DAYS missing from useTodayPicks"
    assert int(days.group(1)) == config.GAME_SCORE_AHEAD_DAYS
    assert (
        "fetchUpcomingNhlPicks(target, addDays(target, NHL_AHEAD_DAYS))"
        in src
    )
    # A failed look-ahead is partial, the same as the other three cards.
    assert "swallow('the upcoming NHL card')" in src
    # The hook stamps Discord publish on `merged`, then `const all = merged.map`.
    # The five cards have to be in that array, or NHL never reaches Today.
    start = src.index("const merged = [")
    merged = src[start:src.index(".filter(", start)]
    assert "const all = merged" in merged
    for name in ("rows", "ufcRows", "nflRows", "ncaafRows", "nhlRows"):
        assert f"...{name}" in merged, f"{name} dropped from the Today merge"


def test_the_nhl_read_matches_the_other_look_aheads():
    body = _fn(_read(QUERIES), "fetchUpcomingNhlPicks")
    assert ".eq('sport', 'NHL')" in body
    # After today (the same-day read owns today) through the horizon inclusive,
    # so a game dated exactly NHL_AHEAD_DAYS out is returned.
    assert body.count(".gt('game_date', afterDate)") >= 3
    assert body.count(".lte('game_date', throughDate)") >= 3
    assert ".gte('game_date', afterDate)" not in body
    assert ".lt('game_date', throughDate)" not in body
    # Neither odds view has a sport column. An unscoped date window pulls
    # every other sport's future slate and silently truncates at 1,000 rows.
    assert body.count(".like('game_id', 'NHL_%')") == 2
    assert ".order('signal_type', { ascending: true })" in body
    assert "fetchAllPages" in body


def test_the_sport_chip_is_the_hook_not_an_allowlist():
    """PicksHomeScreen mutes a sport that is absent from useTodayPicks.
    There is no second list that could keep NHL off once the rows arrive."""
    src = _read(PICKS)
    assert "const { data: allData," in src and "useTodayPicks()" in src
    # Paused models' rows join the All board (Matt, 2026-09-26), so the chip
    # counts them too -- still straight from the hook, never an allowlist.
    assert "new Set([...allData, ...pausedData].map((d) => d.pick.sport))" in src
    # The toggle renders NHL. A fetch the chip cannot show is not a fix.
    sports = _read(MOBILE / "src" / "hooks" / "useSportFilter.ts")
    line = next(l for l in sports.splitlines() if l.startswith("export const SPORTS"))
    assert "'NHL'" in line
