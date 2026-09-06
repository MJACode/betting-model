"""The live loops must not lose a game to the midnight ET boundary.

#296 fixed the 8pm ET half of this: the worker runs UTC, `date.today()` rolled
over at 00:00 UTC, and the loop asked for TOMORROW's games all evening. The
other half survived it. A game carries the game_date of its FIRST PITCH, so a
10:08pm ET start in Anaheim is in the fourth inning at 00:30 ET the next day --
and at midnight the loops stopped asking for it, because it is no longer
today's game.

Measured 2026-08-30 against DraftKings' own feed: the last in-play row on
2026-08-29 landed at 23:50:35 ET while DK went on quoting PHI@LAA, ARI@SF and
BAL@ATH until 01:07 ET. Seventy-seven minutes, three games, no prices.

These are behaviour- AND source-level tripwires because the failure is SILENT:
"no active games" is also exactly what an empty slate looks like, which is why
#296 ran for ten nights before anyone saw it.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).parent.parent


def _at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


# -- the helper ---------------------------------------------------------------

def test_just_after_midnight_still_asks_about_yesterday():
    """00:30 ET on 08-30 is the exact moment the loop went dark."""
    assert config.live_slate_dates(_at(2026, 8, 30, 0, 30)) == [
        "2026-08-30", "2026-08-29"]


def test_just_before_midnight_asks_about_today_only():
    assert config.live_slate_dates(_at(2026, 8, 29, 23, 50)) == ["2026-08-29"]


def test_by_daytime_yesterday_is_dropped():
    """Yesterday's games cannot still be running at noon, and carrying the date
    forever would put a whole extra slate in scope on every pass."""
    assert config.live_slate_dates(_at(2026, 8, 30, 12, 0)) == ["2026-08-30"]


def test_today_is_always_first():
    """Callers that collapse to one date must still get TODAY, not yesterday."""
    for hour in range(24):
        assert config.live_slate_dates(_at(2026, 8, 30, hour))[0] == "2026-08-30"


def test_the_lookback_closes_before_the_next_slate_opens():
    assert 0 < config.LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET <= 10


# -- discovery actually uses every date ---------------------------------------

def test_discovery_asks_statsapi_about_every_date_it_is_given(monkeypatch):
    from data.ingestors import live_game_state_poller as p

    asked: list[str] = []

    def fake_schedule(date, sportId):  # noqa: N803 - statsapi's own signature
        asked.append(date)
        return [{"game_id": 700 + len(asked),
                 "away_id": 143, "home_id": 108,
                 "status": "In Progress", "abstract_game_state": "Live"}]

    monkeypatch.setattr(p.statsapi, "schedule", fake_schedule)
    out = p._discover_active_games(["2026-08-30", "2026-08-29"])
    assert asked == ["2026-08-30", "2026-08-29"], (
        "yesterday's schedule is where the in-progress late game lives")
    assert len(out) == 2


def test_discovery_still_accepts_a_bare_string(monkeypatch):
    """The CLI passes --date as one string; it must not iterate characters."""
    from data.ingestors import live_game_state_poller as p

    asked: list[str] = []

    def fake_schedule(date, sportId):  # noqa: N803
        asked.append(date)
        return []

    monkeypatch.setattr(p.statsapi, "schedule", fake_schedule)
    p._discover_active_games("2026-08-30")
    assert asked == ["2026-08-30"]


def test_one_broken_date_does_not_lose_the_other(monkeypatch):
    """The extra date exists for the window where it carries the ONLY live
    games, so a failure on today must not take yesterday down with it."""
    from data.ingestors import live_game_state_poller as p

    def flaky(date, sportId):  # noqa: N803
        if date == "2026-08-30":
            raise RuntimeError("statsapi 503")
        return [{"game_id": 777, "away_id": 109, "home_id": 137,
                 "status": "In Progress", "abstract_game_state": "Live"}]

    monkeypatch.setattr(p.statsapi, "schedule", flaky)
    assert len(p._discover_active_games(["2026-08-30", "2026-08-29"])) == 1


def test_a_game_seen_twice_is_polled_once(monkeypatch):
    from data.ingestors import live_game_state_poller as p

    monkeypatch.setattr(p.statsapi, "schedule", lambda date, sportId: [  # noqa: N803
        {"game_id": 42, "away_id": 109, "home_id": 137,
         "status": "In Progress", "abstract_game_state": "Live"}])
    out = p._discover_active_games(["2026-08-30", "2026-08-30"])
    assert len(out) == 1


# -- source tripwires: the failure is silent, so the guard must be static -----

def test_the_live_scorer_does_not_pin_games_to_a_single_date():
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert "AND game_date = ANY(%s)" in src, (
        "a single game_date drops the late game that is still in progress")
    assert "live_slate_dates" in src


def test_the_ncaaf_live_loop_got_the_same_fix():
    """CLAUDE.md 1b: a change to how one loop operates is assessed against all
    of them. NCAAF plays MORE games across midnight ET than MLB does."""
    src = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    assert "AND g.game_date = ANY(%(d)s)" in src
    assert "live_slate_dates" in src


def test_both_live_loops_share_one_definition_of_the_slate():
    """Per-sport copies are how the first-signal lock and the live price log
    each came to exist in one sport and not the others."""
    for rel in ("models/live_scorer.py", "ncaaf_live/gameday.py",
                "data/ingestors/live_game_state_poller.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "live_slate_dates" in src, f"{rel} rolls its own slate window"


def test_the_scorer_announces_every_date_it_scored():
    """Both notifiers filter picks on game_date. Scoring yesterday's late game
    while notifying only today would write a BET and never announce it."""
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    body = src[src.index('if not dry_run and summary["bets"]:'):]
    assert "for _d in dates:" in body
    assert "notify_live_signals(target_date=_d" in body
    assert "notify_discord_live(target_date=_d" in body


# -- the APP is a live surface too, and it was the one that went dark ---------
#
# 2026-09-06: UCLA @ California kicked off 10:37pm ET on 09-05, and its live
# moneyline crossed at 1:07am ET on 09-06 under game_date 2026-09-05. The live
# loop scored it (live_slate_dates), the Discord producer posted it, push
# delivered it -- and the app's live board asked for a single todayET(),
# '2026-09-06', and showed nothing for the rest of the game. CLAUDE.md 1b: the
# app, Discord and push show the SAME picks, and a surface with its own window
# is a surface that will disagree silently.
#
# Source-level, like the loops above, and for the same reason: there is no CI
# for the app and an empty live board is indistinguishable from a missed one.
# The behaviour is pinned off-device by mobile/scripts/verify_live_slate.ts.

MOBILE = ROOT / "mobile"


def test_the_app_has_its_own_copy_of_the_slate_window():
    src = (MOBILE / "src/lib/format.ts").read_text(encoding="utf-8")
    assert "export function liveSlateDatesET" in src, (
        "the app needs config.live_slate_dates() in TypeScript -- without it "
        "every live read is pinned to one date")
    assert "LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET = 6" in src, (
        "the app's lookback must mirror config.LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET")
    assert config.LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET == 6, (
        "config moved; move mobile/src/lib/format.ts with it")


def test_the_apps_live_reads_take_a_LIST_of_dates():
    """`.eq('game_date', date)` is the bug. Both live reads must be `.in(...)`."""
    src = (MOBILE / "src/lib/queries.ts").read_text(encoding="utf-8")
    for fn in ("fetchLivePicks", "fetchLiveGameStates"):
        body = src[src.index(f"export async function {fn}("):]
        body = body[:body.index("\n}\n")]
        assert ".eq('game_date'" not in body, (
            f"{fn} pins live rows to ONE date, so a game that kicked off late "
            f"disappears from the app at midnight ET while every other surface "
            f"keeps publishing it")
        assert ".in('game_date'" in body, f"{fn} must read the whole slate window"


def test_the_apps_live_hook_resolves_the_window_per_fetch():
    """Not captured at mount: an app left warm across midnight would keep asking
    about yesterday for as long as it stayed in memory (#512 fixed that half for
    a single date; this keeps it fixed for the window)."""
    src = (MOBILE / "src/hooks/useLivePicks.ts").read_text(encoding="utf-8")
    assert "liveSlateDatesET" in src and "todayET()" not in src, (
        "useLivePicks must resolve the slate window, not a single ET date")
    body = src[src.index("const refresh = useCallback"):]
    assert "liveSlateDatesET()" in body[:body.index("}, [])")], (
        "the window must be recomputed inside refresh, not frozen in useState")
