"""EuroLeague's live API as the halftime loop reads it
(data/ingestors/euroleague_live_feed.py), on one real game's answers.

Pinned here:
  * the half's last shot, the game's first shot and the half-time score are
    read off the shot chart (UTC stamps; A is the home club), as the grade
    read them;
  * the half is over at the second quarter's 'EP'; the third has begun at its
    'BP' or its first shot. The third quarter's substitutions are logged
    DURING the break (numbered before its 'BP' in the real game), so a third
    quarter holding only substitutions is still the break;
  * a half-time score the play-by-play or the header disagrees with is a
    problem, never a decision; clubs that are not our game's are unreadable;
  * the client asks one endpoint at a time, PAUSE_S apart, and backs off on
    Cloudflare's HTTP 429;
  * in-play rows are stored only for games under way, under the loop's source.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from data.ingestors import euroleague_live_feed as F  # noqa: E402
from tests import _euroleague_live_synth as S  # noqa: E402


def test_the_finished_game_reads_its_half_off_the_shot_chart():
    h = F.read_half(S.answers(), S.HOME, S.AWAY)
    assert h.status == "second_half"
    assert h.last_q2_shot == S.LAST_Q2 and h.first_shot == S.FIRST_SHOT and h.q3_at == S.FIRST_Q3
    assert (h.ht_home, h.ht_away) == S.HALF


def test_the_break_is_read_with_the_third_quarters_substitutions_already_logged():
    a = S.at_break()
    q3 = a["pbp"]["ThirdQuarter"]
    assert q3 and {str(p["PLAYTYPE"]).strip() for p in q3} <= {"IN", "OUT"}     # not empty during the break
    full = S.answers()["pbp"]["ThirdQuarter"]
    bp = next(p["NUMBEROFPLAY"] for p in full if str(p["PLAYTYPE"]).strip() == "BP")
    assert all(p["NUMBEROFPLAY"] < bp for p in q3)    # numbered before the restart: logged in the break
    h = F.read_half(a, S.HOME, S.AWAY)
    assert h.status == "break" and h.problem is None
    assert h.last_q2_shot == S.LAST_Q2 and (h.ht_home, h.ht_away) == S.HALF and h.q3_at is None
    assert h.pbp_score == S.HALF and h.header_score == S.HALF


def test_the_third_quarter_begins_at_its_begin_period_or_its_first_shot():
    h = F.read_half(S.third_begun(with_shot=False), S.HOME, S.AWAY)
    assert h.status == "second_half" and h.q3_at is None
    h = F.read_half(S.third_begun(with_shot=True), S.HOME, S.AWAY)
    assert h.status == "second_half" and h.q3_at == S.FIRST_Q3


def test_before_the_end_period_it_is_the_first_half():
    h = F.read_half(S.first_half(), S.HOME, S.AWAY)
    assert h.status == "first_half" and h.problem is None


def test_a_header_score_that_is_not_the_shot_charts_is_a_problem():
    a = S.at_break()
    a["header"]["ScoreQuarter2A"] = 35
    h = F.read_half(a, S.HOME, S.AWAY)
    assert h.status == "break" and "header says 35-32" in h.problem


def test_a_play_by_play_score_that_is_not_the_shot_charts_is_a_problem():
    a = S.at_break()
    last = [p for p in a["pbp"]["SecondQuarter"] if p.get("POINTS_A") is not None][-1]
    last["POINTS_B"] = 31
    h = F.read_half(a, S.HOME, S.AWAY)
    assert h.status == "break" and h.problem and "play-by-play says 33-31" in h.problem


def test_clubs_that_are_not_our_games_are_unreadable():
    h = F.read_half(S.at_break(), S.AWAY, S.HOME)          # our home is EuroLeague's B: never flipped here
    assert h.status == "unreadable" and "PAN v BAR" in h.problem


def test_no_shot_with_a_time_after_the_half_is_unreadable():
    a = S.at_break()
    for r in a["points"]["Rows"]:
        r["UTC"] = ""
    assert F.read_half(a, S.HOME, S.AWAY).status == "unreadable"


# ─── the client ───────────────────────────────────────────────────────────────

class Resp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body if body is not None else {}
        self.text = "{}" if body is not None else ""

    def json(self):
        return self._body


class Session:
    def __init__(self, codes):
        self.codes = list(codes)
        self.urls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.urls.append((url.rsplit("/", 1)[-1], params["seasoncode"], params["gamecode"]))
        return Resp(self.codes.pop(0), {"ok": True})


class Time:
    def __init__(self):
        self.t = 1000.0
        self.slept = []

    def mono(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


def test_the_client_asks_one_endpoint_at_a_time_with_a_pause():
    tm, ses = Time(), Session([200, 200, 200])
    api = F.EuroleagueApi(ses, sleep=tm.sleep, monotonic=tm.mono)
    got = api.game("E2026", 110)
    assert set(got) == {"pbp", "points", "header"}
    assert [u[0] for u in ses.urls] == ["PlayByPlay", "Points", "Header"] and ses.urls[0][1:] == ("E2026", 110)
    assert tm.slept == [F.PAUSE_S, F.PAUSE_S] and api.calls == 3


def test_a_rate_limit_backs_the_client_off_and_the_game_is_not_read():
    tm, ses = Time(), Session([429, 200, 200, 200])
    api = F.EuroleagueApi(ses, sleep=tm.sleep, monotonic=tm.mono)
    assert api.game("E2026", 110) is None and api.refused == 1
    api.game("E2026", 110)
    assert tm.slept[0] == F.BACKOFF_S


# ─── the odds rows ────────────────────────────────────────────────────────────

def test_in_play_rows_are_kept_only_for_games_under_way():
    ev = S.events([S.book("draftkings", S.LAST_Q2 + pd.Timedelta(minutes=2), spread=(-5.5, -110, -110))])
    ev += [{**ev[0], "id": "later", "commence_time": "2026-11-13T21:00:00Z", "home_team": "Real Madrid",
            "away_team": "Olympiacos"}]

    def resolver(home, away, commence):
        return (S.GAME_ID, False) if home == S.HOME_FEED else ("EUROLEAGUE_E2026_999", False)
    rows = F.rows_from_events(ev, S.utc("2026-11-13T20:12:37Z"), resolver, started={S.GAME_ID})
    assert {r["game_id"] for r in rows} == {S.GAME_ID}
    r = rows[0]
    assert r["market"] == "spreads" and r["spread_home"] == -5.5 and r["bookmaker"] == "draftkings"
    assert r["snapshot_type"] == "in_play" and r["source"] == F.LIVE_SOURCE
    assert F.rows_from_events(ev, S.utc("2026-11-13T20:12:37Z"), None, {S.GAME_ID}) == []


def test_the_flipped_feed_puts_our_home_clubs_number_in_spread_home():
    ev = S.events([S.book("draftkings", S.LAST_Q2, spread=(-5.5, -105, -115))])
    rows = F.rows_from_events(ev, S.utc("2026-11-13T20:12:37Z"), lambda h, a, c: (S.GAME_ID, True), {S.GAME_ID})
    r = rows[0]
    assert r["spread_home"] == 5.5 and r["home_price"] == -115 and r["away_price"] == -105


def test_the_live_call_is_three_markets_at_the_ten_history_books():
    import config
    feed = F.odds_feed(10, 30)
    assert feed.url.endswith("/v4/sports/basketball_euroleague/odds") and feed.markets == ("h2h", "spreads", "totals")
    assert feed.books() == list(config.EUROLEAGUE_HISTORY_BOOKMAKERS) and len(feed.books()) == 10


def test_every_one_of_the_ten_books_survives_the_parser():
    """The rule counts the reference books toward a read's median and its two
    other books; a book the parser dropped would starve it."""
    import config
    stamp = S.LAST_Q2 + pd.Timedelta(minutes=2)
    ev = S.events([S.book(b, stamp, spread=(-5.5, -110, -110)) for b in config.EUROLEAGUE_HISTORY_BOOKMAKERS])
    rows = F.rows_from_events(ev, S.utc("2026-11-13T20:12:37Z"), lambda h, a, c: (S.GAME_ID, False), {S.GAME_ID})
    assert sorted(r["bookmaker"] for r in rows) == sorted(config.EUROLEAGUE_HISTORY_BOOKMAKERS)
