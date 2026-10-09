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
one sport, and at least 2 games), and a leftover id of a game the feed now
prices under another id is not a stale game. Below 2 priced games the check
asks whether the feed stored any DraftKings pre-game row inside the bound.
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
    """The games read answers `rows`. The feed read (any DraftKings pre-game
    row stored inside the bound) answers `feed_fresh`; `feed_boom` makes only
    that read fail."""

    def __init__(self, rows=None, boom: Exception | None = None,
                 feed_fresh: bool = True, feed_boom: Exception | None = None):
        self.rows = rows or []
        self.boom = boom
        self.feed_fresh = feed_fresh
        self.feed_boom = feed_boom
        self.rolled_back = False
        self.params = None
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        if self.boom:
            raise self.boom
        flat = " ".join(sql.split())
        if self.feed_boom and flat.startswith("SELECT 1 FROM odds"):
            raise self.feed_boom
        self.sql.append(flat)
        self.params = params
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        assert self.sql[-1].startswith("SELECT 1 FROM odds"), self.sql[-1]
        return (1,) if self.feed_fresh else None

    def rollback(self):
        self.rolled_back = True


def _row(gid, sport, kick, h2h, spreads, totals, home=None, away=None):
    """(game_id, sport, commence_time, home_team, away_team, newest h2h,
    spreads, totals). Names default to the id's last two parts, which is how
    every id since 08-01 is built (sport, date, away, home)."""
    parts = gid.split("_")
    if home is None:
        home = parts[3] if len(parts) == 4 else gid
    if away is None:
        away = parts[2] if len(parts) == 4 else gid
    return (gid, sport, kick, home, away, h2h, spreads, totals)


def _game(gid, sport, newest, kick=KICK, home=None, away=None):
    return _row(gid, sport, kick, newest, newest, newest, home=home, away=away)


def _run(rows, now=NOW, **kw):
    r = sh.HealthReport("2026-10-09")
    conn = _Conn(rows, **kw)
    sh.check_pregame_prices_current(conn, r, now=now)
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
    rows = [_row("NCAAF_2026-10-10_big_fav", "NCAAF", KICK, OLD, FRESH, FRESH),
            _row("NCAAF_2026-10-10_other_one", "NCAAF", KICK, FRESH, FRESH, None)]
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
    res, _ = _run([_game("NCAAF_2026-10-10_fcs_a", "NCAAF", None)], feed_fresh=True)
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


# ── too few games to judge one by one: ask whether the feed is alive ─────────
#
# The share needs at least 2 stale games, so with 0 or 1 priced game in the
# next 36 hours a dead odds fetch read SKIPPED (which never alerts) or OK (and
# STALE -> OK posted an all-clear). Below that size the check now asks whether
# ANY DraftKings pre-game row was stored inside the bound. The first two tests
# failed before that question existed.

def test_a_dead_feed_with_one_stale_game_is_a_crit():
    res, conn = _run([_game("NHL_2026-10-10_A_B", "NHL", OLD)], feed_fresh=False)
    assert (res["status"], res["severity"]) == ("STALE", "CRIT"), res["detail"]
    assert "odds fetch has stopped" in res["detail"]


def test_a_dead_feed_with_no_priced_game_is_a_crit():
    res, _ = _run([_game("NCAAF_2026-10-10_fcs_a", "NCAAF", None)], feed_fresh=False)
    assert (res["status"], res["severity"]) == ("STALE", "CRIT"), res["detail"]


def test_a_live_feed_with_no_priced_game_is_skipped():
    res, _ = _run([_game("NCAAF_2026-10-10_fcs_a", "NCAAF", None)], feed_fresh=True)
    assert res["status"] == "SKIPPED"


def test_one_cancelled_fight_on_a_live_feed_is_ok():
    res, _ = _run([_game("UFC_2026-10-10_mickey-gall_sedriques-dumas", "UFC", OLD)],
                  feed_fresh=True)
    assert res["status"] == "OK", res["detail"]
    assert "1 do not" in res["detail"]


def test_the_feed_read_is_draftkings_pre_game_rows_outside_nfl_and_golf():
    """NFL and golf have pollers of their own that could keep the answer
    green while the main fetch is dead."""
    _, conn = _run([_game("NHL_2026-10-10_A_B", "NHL", OLD)], feed_fresh=False)
    feed = conn.sql[-1]
    assert "snapshot_at >= ?" in feed and "bookmaker = ?" in feed
    assert "snapshot_type <> 'in_play'" in feed
    assert "sport NOT IN ('GOLF', 'NFL')" in feed and "LIMIT 1" in feed
    floor = (NOW - timedelta(minutes=config.PREGAME_PRICE_MAX_AGE_MIN)).strftime(
        "%Y-%m-%dT%H:%M:%S")
    assert conn.params == (floor, config.ODDS_API_BOOKMAKER)


def test_a_broken_feed_read_is_an_error_and_rolls_back():
    res, conn = _run([_game("NHL_2026-10-10_A_B", "NHL", OLD)],
                     feed_boom=RuntimeError("statement timeout"))
    assert (res["status"], res["severity"]) == ("ERROR", "CRIT")
    assert conn.rolled_back


def test_enough_games_are_judged_one_by_one_without_the_feed_read():
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", FRESH) for i in range(3)]
    _, conn = _run(rows, feed_fresh=False)
    assert not any(s.startswith("SELECT 1 FROM odds") for s in conn.sql)


# ── leftover ids of one game ─────────────────────────────────────────────────
#
# The feed re-keys a game when it flips home and away (UFC), shifts its date,
# or renames a team, and the old id keeps its last price forever. Counted as
# stale games, two leftovers meet the 2-game minimum by themselves. A stale id
# is now not counted when a CURRENT id in the same sport shares a team or
# fighter name and starts within 6 hours of it (that id may sit outside the 36
# hours), and stale ids linked the same way count once. No timestamp is used
# as a reference, so a trickle of fresh rows elsewhere cannot hide an outage.
# Production shapes, replayed 2026-10-09; the first two alarmed before this.

def _ufc(gid, home, away, kick, newest):
    return _game(gid, "UFC", newest, kick=kick, home=home, away=away)


def test_the_09_12_swapped_and_date_shifted_ufc_copies_are_not_an_alarm():
    """2026-09-12 22:30Z: 3 of 6 stale, and all 3 were copies of the Jean
    Silva fight, which DraftKings priced under UFC_2026-09-12_jose-delgado_
    jean-silva (22:19Z). Before: CRIT, 'the board is emptying'."""
    now = datetime(2026, 9, 12, 22, 30, tzinfo=timezone.utc)
    rows = [
        _ufc("UFC_2026-09-12_marwan-rahiki_tommy-mcmillen", "Tommy McMillen",
             "Marwan Rahiki", "2026-09-12T22:53:00+00:00", "2026-09-12T22:29:26Z"),
        _ufc("UFC_2026-09-12_joseph-morales_brandon-moreno", "Brandon Moreno",
             "Joseph Morales", "2026-09-12T23:29:00+00:00", "2026-09-12T22:29:26Z"),
        _ufc("UFC_2026-09-12_jean-silva_yair-rodriguez", "Yair Rodriguez",
             "Jean Silva", "2026-09-12T23:45:00+00:00", "2026-08-19T20:11:44Z"),
        _ufc("UFC_2026-09-12_yair-rodriguez_jean-silva", "Jean Silva",
             "Yair Rodriguez", "2026-09-13T00:00:00+00:00", "2026-08-11T19:17:16Z"),
        _ufc("UFC_2026-09-12_jose-delgado_jean-silva", "Jean Silva",
             "Jose Delgado", "2026-09-13T00:11:00+00:00", "2026-09-12T22:19:36Z"),
        _ufc("UFC_2026-09-13_jose-delgado_jean-silva", "Jean Silva",
             "Jose Delgado", "2026-09-13T04:00:00+00:00", "2026-09-03T08:16:28Z"),
    ]
    res, _ = _run(rows, now=now)
    assert res["status"] == "OK", res["detail"]
    assert "3 of 3" in res["detail"]


def test_the_09_02_renamed_ncaaf_ids_are_not_an_alarm():
    """2026-09-02 11:30Z: 6 of 9 stale. UCF and Kennesaw State were priced
    under renamed ids (Kennesaw's starts 09-04 00:18Z, outside the 36 hours),
    and Rutgers and Delaware each sat under two stale ids. Left: 2 of 5,
    under half. Before: CRIT."""
    now = datetime(2026, 9, 2, 11, 30, tzinfo=timezone.utc)

    def g(gid, home, away, kick, newest):
        return _game(gid, "NCAAF", newest, kick=kick, home=home, away=away)

    rows = [
        g("NCAAF_2026-09-03_massachusetts_rutgers", "Rutgers", "Massachusetts",
          "2026-09-03T22:00:00+00:00", "2026-09-01T16:17:00Z"),
        g("NCAAF_2026-09-03_umass-minutemen_rutgers", "Rutgers", "UMass Minutemen",
          "2026-09-03T22:00:00+00:00", "2026-08-27T17:17:38Z"),
        g("NCAAF_2026-09-03_merrimack_delaware", "Delaware", "Merrimack",
          "2026-09-03T23:00:00+00:00", "2026-08-31T11:55:07Z"),
        g("NCAAF_2026-09-03_merrimack-warriors_delaware", "Delaware",
          "Merrimack Warriors", "2026-09-03T23:07:00+00:00", "2026-09-01T16:17:00Z"),
        g("NCAAF_2026-09-03_bethune-cookman_ucf", "UCF", "Bethune-Cookman",
          "2026-09-03T23:00:00+00:00", "2026-08-31T11:55:07Z"),
        g("NCAAF_2026-09-03_bethune-cookman-wildcats_ucf", "UCF",
          "Bethune-Cookman Wildcats", "2026-09-03T23:02:22+00:00", "2026-09-02T11:16:33Z"),
        g("NCAAF_2026-09-03_west-georgia_kennesaw-state", "Kennesaw State",
          "West Georgia", "2026-09-03T23:00:00+00:00", "2026-08-31T11:55:07Z"),
        g("NCAAF_2026-09-03_west-georgia-wolves_kennesaw-state", "Kennesaw State",
          "West Georgia Wolves", "2026-09-04T00:18:47+00:00", "2026-09-02T11:16:33Z"),
        g("NCAAF_2026-09-03_akron_wake-forest", "Wake Forest", "Akron",
          "2026-09-03T23:00:00+00:00", "2026-09-02T11:16:33Z"),
        g("NCAAF_2026-09-03_albany_buffalo", "Buffalo", "Albany",
          "2026-09-03T23:00:00+00:00", "2026-09-02T11:16:33Z"),
        # never priced by DraftKings: not counted either way
        g("NCAAF_2026-09-03_ualbany_buffalo", "Buffalo", "UAlbany",
          "2026-09-03T23:00:00.000Z", None),
    ]
    res, _ = _run(rows, now=now)
    assert res["status"] == "OK", res["detail"]
    assert "NCAAF 2 of 5" in res["detail"]


def test_the_09_30_outage_still_alarms_with_a_fresh_row_elsewhere():
    """2026-09-30 18:00Z: every NHL game's newest main-market DraftKings price
    was 09-26 22:59Z while alternate-total rows kept arriving from another
    writer. A 'newest row in the feed' reference would have called all 11
    pulled. PHI plays twice, 23.5 hours apart: two games, not one."""
    now = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)
    old = "2026-09-26T22:59:42Z"
    games = [("NYI", "TOR", "2026-09-30T23:30:00Z"), ("PIT", "PHI", "2026-09-30T23:30:00Z"),
             ("LAK", "COL", "2026-10-01T02:00:00Z"), ("PHI", "NJD", "2026-10-01T23:00:00Z"),
             ("TBL", "NYR", "2026-10-01T23:00:00Z"), ("BUF", "CBJ", "2026-10-01T23:00:00Z"),
             ("MIN", "NSH", "2026-10-02T00:00:00Z"), ("SEA", "CGY", "2026-10-02T01:00:00Z"),
             ("CHI", "UTA", "2026-10-02T01:30:00Z"), ("FLA", "SJS", "2026-10-02T02:00:00Z"),
             ("EDM", "VAN", "2026-10-02T02:00:00Z")]
    rows = [_game(f"NHL_{k[:10]}_{a}_{h}", "NHL", old, kick=k) for a, h, k in games]
    res, _ = _run(rows, now=now, feed_fresh=True)
    assert (res["status"], res["severity"]) == ("STALE", "CRIT"), res["detail"]
    assert "11 of 11" in res["detail"]


def test_two_stale_ids_sharing_a_name_count_once():
    """Two leftovers of one game, nothing current: one stale game, not two,
    so on its own it does not reach the 2-game minimum."""
    rows = [_game(f"NHL_2026-10-10_A{i}_B{i}", "NHL", FRESH) for i in range(4)]
    rows += [_game("NCAAF_2026-10-10_umass_rutgers", "NCAAF", OLD),
             _game("NCAAF_2026-10-10_massachusetts_rutgers", "NCAAF", OLD)]
    res, _ = _run(rows)
    assert res["status"] == "OK", res["detail"]
    assert "NCAAF 1 of 1" in res["detail"]


def test_a_shared_name_more_than_6_hours_apart_is_another_game():
    """NYY's 17:00Z price is current and its 23:30Z game's is not: 6.5 hours
    apart, so the second game is not a leftover of the first."""
    rows = [_game("MLB_2026-10-10_NYY_BOS", "MLB", FRESH, kick="2026-10-10T17:00:00Z"),
            _game("MLB_2026-10-10_NYY_TOR", "MLB", OLD, kick="2026-10-10T23:30:00Z"),
            _game("MLB_2026-10-10_SEA_KC", "MLB", OLD, kick="2026-10-10T23:30:00Z")]
    res, _ = _run(rows)
    assert res["status"] == "STALE", res["detail"]
    assert "MLB 2 of 3" in res["detail"]
