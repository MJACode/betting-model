"""The Picks board must ask for NHL games the scorer has already priced.

config.GAME_SCORE_AHEAD_DAYS (7) admits NHL with MLB, NBA and WNBA. Measured
2026-09-22: the only NHL rows in `picks` are game_date 2026-09-29, including
one BET whose pick_label is "CAR ML", written 2026-09-22 00:23 ET. Discord
and push already ledgered that lock_key. useTodayPicks fetched today plus
UFC, NFL and NCAAF look-aheads and never a future NHL date, so the NHL chip
stayed muted and both Today and Signals were empty.

8 days is that 7-day scorer horizon plus one day of ET/UTC-boundary margin,
the same shape as NFL_AHEAD_DAYS. A shorter window drops the opener.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_today_board_fetches_nhl_through_the_scorer_horizon():
    hook = _read(MOBILE / "src" / "hooks" / "useTodayPicks.ts")
    assert "fetchUpcomingNhlPicks" in hook
    match = re.search(r"const NHL_AHEAD_DAYS = (\d+);", hook)
    assert match, "NHL_AHEAD_DAYS must be a named constant beside the other horizons"
    # config.GAME_SCORE_AHEAD_DAYS default is 7. One extra day is the
    # ET/UTC-boundary margin NFL_AHEAD_DAYS already uses. Do not lower this
    # below the scorer horizon: the 2026-09-29 opener is exactly 7 days out
    # from the day it was written.
    assert int(match.group(1)) >= 8
    assert "fetchUpcomingNhlPicks(target, addDays(target, NHL_AHEAD_DAYS))" in hook


def test_nhl_lookahead_query_is_sport_scoped_and_keeps_signals():
    src = _read(MOBILE / "src" / "lib" / "queries.ts")
    start = src.index("export async function fetchUpcomingNhlPicks")
    # Stop at the next exported function so a later read cannot satisfy this.
    rest = src[start + 1 :]
    end = rest.index("\nexport async function ")
    block = src[start : start + 1 + end]
    assert ".eq('sport', 'NHL')" in block
    assert ".gt('game_date', afterDate)" in block
    assert ".lte('game_date', throughDate)" in block
    assert ".like('game_id', 'NHL_%')" in block
    assert ".order('signal_type', { ascending: true })" in block
    assert ".not('is_live', 'is', true)" in block
