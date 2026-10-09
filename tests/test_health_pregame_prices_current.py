"""The health check raises an alarm when the scorer is refusing stale prices.

Since 2026-10-09 the scorer makes no pre-game pick on a game whose newest
DraftKings price is older than config.PREGAME_PRICE_MAX_AGE_MIN (180 minutes).
So an odds outage now empties the board after 3 hours. The older check,
odds_dk_lines, only fires when the newest odds row of ANY kind is 12 hours old,
and from 09-27 to 10-01 in-play rows and a trickle of DraftKings rows kept it
green while the odds fetch failed on every pass ("Invalid ODDS_API_KEY").

The new row (odds_dk_pregame_current) asks, game by game, whether each game
DraftKings prices that kicks off in the next 36 hours has a DraftKings price
from inside the bound. Measured on production, sampled every 6 hours:
  * 2026-10-03 to 10-09 (28 samples): the only stale games were UFC fights
    the feed had moved to their swapped id (up to 10 on 09-26 18:00Z), plus
    the odd cancelled fight (1 of 15 UFC on 10-03).
  * The odds-key outage (09-27 to 09-30, 18:00Z): 11 of 11, 6 of 6, 9 of 9 and
    11 of 11 DraftKings-priced games stale.
So the alarm is a SHARE (at least half of the priced games, overall or within
one sport, and at least 2 games), and a UFC id whose swapped twin is current is
not a stale game.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import tracking.system_health as sh

NOW = datetime(2026, 10, 9, 18, 0, 0, tzinfo=timezone.utc)
KICK = "2026-10-10T19:30:00Z"                   # 25.5 hours after NOW
FRESH = "2026-10-09T17:16:31Z"                   # 43 minutes old
OLD = "2026-10-09T13:00:00Z"                     # 5 hours old


def _at(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Conn:
    def __init__(self, rows=None, boom: Exception | None = None):
        self.rows = rows or []
        self.boom = boom
        self.rolled_back = False
        self.params = None

    def execute(self, sql, params=None):
        if self.boom:
            raise self.boom
        self.params = params
        return self

    def fetchall(self):
        return self.rows

    def rollback(self):
        self.rolled_back = True


def _game(gid, sport, newest, kick=KICK):
    """(game_id, sport, commence_time, newest h2h, spreads, totals)."""
    return (gid, sport, kick, newest, newest, newest)


def _run(rows, **kw):
    r = sh.HealthReport("2026-10-09")
    conn = _Conn(rows, **kw)
    sh.check_pregame_prices_current(conn, r, now=NOW)
    assert len(r.results) == 1, r.results
    return r.results[0], conn


def test_an_odds_outage_is_a_crit():
    """The 09-27 shape: every priced game's DraftKings price is hours old."""
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", OLD) for i in range(6)]
    rows += [_game(f"MLB_2026-10-10_C{i}_D{i}", "MLB", OLD) for i in range(2)]
    res, _ = _run(rows)
    assert (res["check_name"], res["status"], res["severity"]) == (
        "odds_dk_pregame_current", "STALE", "CRIT")
    assert "8 of 8" in res["detail"]
    assert sh._parse_ts(res["latest_seen"]) == sh._parse_ts(OLD)


def test_a_normal_board_is_ok():
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", FRESH) for i in range(10)]
    res, _ = _run(rows)
    assert res["status"] == "OK"
    assert "10 of 10" in res["detail"]


def test_a_ufc_fight_the_feed_moved_to_its_swapped_id_is_not_stale():
    """2026-10-09: UFC_2026-10-10_rj-harris_allen-frye-jr stopped at 10-08
    18:17Z, its swapped id is current. Two such fights are not an outage."""
    rows = [
        _game("UFC_2026-10-10_rj-harris_allen-frye-jr", "UFC", "2026-10-08T18:17:06Z"),
        _game("UFC_2026-10-10_allen-frye-jr_rj-harris", "UFC", FRESH),
        _game("UFC_2026-10-10_darya-zheleznyakova_alice-pereira", "UFC",
              "2026-10-08T18:17:06Z"),
        _game("UFC_2026-10-10_alice-pereira_darya-zheleznyakova", "UFC", FRESH),
    ]
    res, _ = _run(rows)
    assert res["status"] == "OK", res["detail"]
    assert "2 of 2" in res["detail"]


def test_a_cancelled_fight_and_a_pulled_game_do_not_raise_the_alarm():
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", FRESH) for i in range(8)]
    rows += [_game(f"UFC_2026-10-10_x{i}_y{i}", "UFC", FRESH) for i in range(10)]
    rows += [_game("UFC_2026-10-10_mickey-gall_sedriques-dumas", "UFC", OLD),
             _game("NHL_2026-10-10_PUL_LED", "NHL", OLD)]
    res, _ = _run(rows)
    assert res["status"] == "OK", res["detail"]
    assert "2 do not" in res["detail"]


def test_one_sports_fetch_failing_is_a_crit_even_when_the_rest_are_fine():
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", FRESH) for i in range(20)]
    rows += [_game(f"NCAAF_2026-10-10_c{i}_d{i}", "NCAAF", OLD) for i in range(4)]
    res, _ = _run(rows)
    assert res["status"] == "STALE"
    assert "NCAAF 4 of 4" in res["detail"]


def test_a_game_draftkings_never_priced_is_not_counted():
    rows = [_game("NCAAF_2026-10-10_fcs_a", "NCAAF", None),
            _game("NCAAF_2026-10-10_fcs_b", "NCAAF", None),
            _game("NHL_2026-10-10_A_B", "NHL", FRESH)]
    res, _ = _run(rows)
    assert res["status"] == "OK"
    assert "1 of 1" in res["detail"]


def test_the_newest_of_the_three_markets_counts():
    """DraftKings pulls a lopsided game's moneyline and keeps its spread and
    total; an h2h-only read called one 10-09 NCAAF game stale that was not."""
    rows = [("NCAAF_2026-10-10_big_fav", "NCAAF", KICK, OLD, FRESH, FRESH),
            ("NCAAF_2026-10-10_other_one", "NCAAF", KICK, FRESH, FRESH, None)]
    res, _ = _run(rows)
    assert res["status"] == "OK"
    assert "2 of 2" in res["detail"]


def test_only_unstarted_games_inside_36_hours_are_checked():
    rows = [_game("NHL_2026-10-09_GO_NOW", "NHL", OLD, kick=_at(30)),      # started
            _game("NHL_2026-10-11_FAR_OFF", "NHL", OLD,
                  kick=(NOW + timedelta(hours=37)).strftime("%Y-%m-%dT%H:%M:%SZ")),
            _game("NHL_2026-10-10_A_B", "NHL", FRESH),
            _game("NHL_2026-10-10_C_D", "NHL", FRESH, kick="2026-10-10T19:30:00+00:00")]
    res, _ = _run(rows)
    assert res["status"] == "OK"
    assert "2 of 2" in res["detail"]


def test_nothing_to_check_is_skipped_not_ok():
    res, _ = _run([_game("NCAAF_2026-10-10_fcs_a", "NCAAF", None)])
    assert res["status"] == "SKIPPED"


def test_a_broken_query_is_an_error_and_rolls_back():
    res, conn = _run([], boom=RuntimeError("statement timeout"))
    assert (res["status"], res["severity"]) == ("ERROR", "CRIT")
    assert conn.rolled_back


def test_the_limit_is_the_scorers_bound(monkeypatch):
    """Not a number typed into the check: move the bound, the verdict moves."""
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", _at(200)) for i in range(4)]
    assert _run(rows)[0]["status"] == "STALE"            # 200 min > 180
    monkeypatch.setattr(config, "PREGAME_PRICE_MAX_AGE_MIN", 240)
    assert _run(rows)[0]["status"] == "OK"               # 200 min < 240
    src = Path(sh.__file__).read_text(encoding="utf-8")
    body = src[src.index("def check_pregame_prices_current"):]
    body = body[:body.index("\ndef ")]
    assert "config.PREGAME_PRICE_MAX_AGE_MIN" in body
    assert "180" not in body


def test_it_asks_for_draftkings_by_the_configured_name():
    _, conn = _run([_game("NHL_2026-10-10_A_B", "NHL", FRESH)])
    assert config.ODDS_API_BOOKMAKER in conn.params


def test_the_daily_run_includes_it():
    src = Path(sh.__file__).read_text(encoding="utf-8")
    run = src[src.index("def run_system_health"):]
    assert "check_pregame_prices_current(conn, r)" in run
