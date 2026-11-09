"""The NBA in-play loop (nba_live/) and its model (models/nba_live_ingame.py),
against a fake ESPN and a fake odds feed.

What each test pins (docs/nba_models_2026.md 7.3, IG-2, as the loop runs it):
  - the phase of a stamp: Q1-Q2, the halftime break (not a phase), Q3, and an
    open period of a game still in progress is live, not postgame;
  - the tick: once an hour at hh:55:36 UTC, inside a 4-minute window, never
    between ticks, and a pass outside it makes no odds call;
  - freshness: a quote is refused when a point came after its stamp, and the
    model is decided at the next tick on a fresh quote;
  - Pinnacle must have quoted within 60 s of the deciding quote;
  - one decision per (game, model): a later tick never writes a second;
  - the lock across restarts: a new process reads the ledger and the picks;
  - the price floor (-200), with the side chosen before the floor, as the lab;
  - the label quotes the side's own number and is read back against its fields;
  - the credit floor: no odds call under the account floor or past a cap;
  - the ESPN summary parses into the lab's play rows.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import models.nba_live_ingame as M
from nba_live import espn as E
from nba_live import gameday as G
from nba_live import odds as O
from nba_live import state as S
from scripts import nba_ingame_data as D

FIX = Path(__file__).resolve().parent / "fixtures" / "espn_nba_summary_401836747_trimmed.json"
ART = M.load_artifact()

HOME, AWAY = "BOS", "NYK"
HOME_NAME, AWAY_NAME = "Boston Celtics", "New York Knicks"
HID, AID = 2, 18
EID = 401900001
TIP = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)
GID = "NBA_2026-11-19_NYK_BOS"
SEASON = 2027


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def at(h, m, s=0) -> datetime:
    """A wall time on the night of the game (hours past 00:00Z on 11-20)."""
    return TIP + timedelta(hours=h, minutes=m, seconds=s)


# ── a fake game ──────────────────────────────────────────────────────────────

def play(seq, wc, period, clock, kind="miss", team=HID, athlete=1001):
    """One ESPN summary play. kind: 'make2' / 'make3' / 'miss' / 'jump' / 'end' /
    'foul'."""
    m, s = divmod(clock, 60)
    disp = f"{int(m)}:{int(s):02d}" if clock >= 60 else f"{clock:.1f}"
    base = {"id": str(seq), "sequenceNumber": str(seq), "period": {"number": period},
            "clock": {"displayValue": disp}, "wallclock": iso(wc), "team": {"id": str(team)},
            "participants": [{"athlete": {"id": str(athlete)}}], "coordinate": {"x": 25, "y": 10},
            "homeScore": 0, "awayScore": 0, "scoringPlay": False, "scoreValue": 0,
            "shootingPlay": False, "pointsAttempted": 0}
    if kind == "jump":
        return {**base, "type": {"id": "615", "text": "Jumpball"}, "text": "jump ball"}
    if kind == "end":
        return {**base, "type": {"id": "412", "text": "End Period"}, "text": "End of period",
                "team": {}, "participants": []}
    if kind == "foul":
        return {**base, "type": {"id": "45", "text": "Personal Foul"}, "text": "personal foul"}
    if kind == "make3":
        return {**base, "type": {"id": "92", "text": "Jump Shot"}, "scoringPlay": True, "scoreValue": 3,
                "shootingPlay": True, "pointsAttempted": 3, "coordinate": {"x": 25, "y": 25},
                "text": "makes 25-foot three point jumper"}
    if kind == "make2":
        return {**base, "type": {"id": "5", "text": "Layup Shot"}, "scoringPlay": True, "scoreValue": 2,
                "shootingPlay": True, "pointsAttempted": 2, "coordinate": {"x": 25, "y": 2},
                "text": "makes 2-foot layup"}
    return {**base, "type": {"id": "92", "text": "Jump Shot"}, "shootingPlay": True, "pointsAttempted": 2,
            "text": "misses 15-foot jumper"}


def game_plays(through: str = "q3", home_lead_plays: int = 6) -> list[dict]:
    """Q1 and Q2 played and ended; Q3 under way, home well ahead. Each play is
    tagged with the moment ESPN posted it (`_posted`, its wallclock unless set)."""
    ps = [play(1, at(0, 10), 1, 720, "jump")]
    seq = 2
    for k in range(home_lead_plays):          # home threes in Q1
        ps.append(play(seq, at(0, 12 + 2 * k), 1, 690 - 60 * k, "make3")); seq += 1
    ps.append(play(seq, at(0, 36), 1, 0, "end")); seq += 1
    ps.append(play(seq, at(0, 39), 2, 700, "make2", team=AID, athlete=2001)); seq += 1
    if through in ("q2", "half", "q3"):
        ps.append(play(seq, at(0, 50), 2, 400, "miss")); seq += 1
    if through in ("half", "q3"):
        ps.append(play(seq, at(1, 5), 2, 0, "end")); seq += 1
    if through == "q3":
        ps.append(play(seq, at(1, 25), 3, 700, "make2")); seq += 1
        ps.append(play(seq, at(1, 50), 3, 300, "miss", team=AID, athlete=2001)); seq += 1
    return ps


def summary(plays: list[dict], state: str = "in") -> dict:
    comp = {"id": str(EID), "date": iso(TIP),
            "status": {"type": {"state": state, "completed": state == "post"}, "period": 3},
            "competitors": [
                {"homeAway": "home", "team": {"id": str(HID), "abbreviation": HOME, "location": "Boston"}},
                {"homeAway": "away", "team": {"id": str(AID), "abbreviation": "NY", "location": "New York"}}]}
    box = [{"team": {"abbreviation": HOME}, "statistics": [{"athletes": [
               {"athlete": {"id": str(1001 + i), "displayName": f"H{i}"}, "starter": i < 5} for i in range(8)]}]},
           {"team": {"abbreviation": "NY"}, "statistics": [{"athletes": [
               {"athlete": {"id": str(2001 + i), "displayName": f"A{i}"}, "starter": i < 5} for i in range(8)]}]}]
    return {"header": {"id": str(EID), "season": {"year": SEASON, "type": 2}, "competitions": [comp]},
            "plays": [{k: v for k, v in p.items() if k != "_posted"} for p in plays],
            "boxscore": {"players": box}}


class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def now(self) -> datetime:
        return self.t

    def sleep(self, s: float) -> None:
        self.t = self.t + timedelta(seconds=s)


class FakeEspn:
    """Serves the plays ESPN had POSTED by the clock's time."""

    def __init__(self, clock: Clock, plays: list[dict], state: str = "in"):
        self.clock, self.plays, self.state = clock, plays, state
        self.calls = 0

    def posted(self) -> list[dict]:
        t = iso(self.clock.now())
        return [p for p in self.plays if p.get("_posted", p["wallclock"]) <= t]

    def scoreboard(self, d):
        self.calls += 1
        return [E.EspnEvent(EID, iso(TIP), 2, self.state, self.state == "post", 3, HOME, "NY",
                            "Boston", "New York")]

    def summary(self, eid):
        self.calls += 1
        return summary(self.posted(), self.state)


def book(key, stamp: datetime, ml=None, spread=None):
    """One bookmaker's h2h and/or spreads: ml (home, away); spread (home number,
    home price, away price)."""
    mk = []
    if ml:
        mk.append({"key": "h2h", "last_update": iso(stamp), "outcomes": [
            {"name": HOME_NAME, "price": ml[0], "link": f"https://{key}/h"},
            {"name": AWAY_NAME, "price": ml[1], "link": f"https://{key}/a"}]})
    if spread:
        mk.append({"key": "spreads", "last_update": iso(stamp), "outcomes": [
            {"name": HOME_NAME, "price": spread[1], "point": spread[0], "link": f"https://{key}/h"},
            {"name": AWAY_NAME, "price": spread[2], "point": -spread[0], "link": f"https://{key}/a"}]})
    return {"key": key, "last_update": iso(stamp), "markets": mk}


class Resp:
    def __init__(self, payload, credits=2, remaining=2_000_000, status=200):
        self._p, self.status_code = payload, status
        self.headers = {"x-requests-last": str(credits), "x-requests-remaining": str(remaining),
                        "x-requests-used": "1"}

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(self.status_code)


class FakeOddsSession:
    def __init__(self, books_fn, remaining=2_000_000):
        self.books_fn, self.calls, self.remaining = books_fn, 0, remaining

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return Resp([{"id": "e1", "home_team": HOME_NAME, "away_team": AWAY_NAME,
                      "commence_time": iso(TIP), "bookmakers": self.books_fn()}],
                    remaining=self.remaining)


class FakeStore(G.Store):
    def __init__(self, ledger=None, picks=None, minutes=None, used=0):
        super().__init__(conn_factory=lambda: None)
        self.ledger = ledger if ledger is not None else {}
        self.picks = picks if picks is not None else []
        self.minutes = minutes or {}
        self.used = used
        self.prices, self.fetches = [], []

    def resolve_game(self, home, away, et_date):
        return {"game_id": GID, "home": HOME, "away": AWAY, "game_date": "2026-11-19", "season": SEASON,
                "g_ct": iso(TIP), "s_ct": iso(TIP), "game_type": "regular",
                "days": [(SEASON, "2026-10-20", "regular"), (SEASON, "2027-04-11", "regular")]}

    def pinnacle_spread_rows(self, game_id, tip):
        t = tip - timedelta(minutes=30)
        return [(GID, "pinnacle", "spreads", "open", iso(t), iso(t + timedelta(seconds=20)), -4.5, -110, -110)]

    def decided_models(self, game_id):
        return {m for (g, m) in self.ledger if g == game_id} | {
            p["model_id"] for p in self.picks if p["game_id"] == game_id}

    def prior_minutes(self, box, season, before):
        return {int(r["athlete_id"]): self.minutes.get(int(r["athlete_id"]), 30.0 - (int(r["athlete_id"]) % 10))
                for r in box}

    def bankroll(self):
        return 1000.0

    def used_today(self):
        return self.used

    def latest_remaining(self):
        return None

    def unsettled_bet_dates(self):
        return set()

    def ensure_ledger(self):
        pass

    def write_decision(self, row, pick):
        key = (row["game_id"], row["model_id"])
        if key in self.ledger or any(p["game_id"] == row["game_id"] and p["model_id"] == row["model_id"]
                                     for p in self.picks):
            return False, False
        self.ledger[key] = row
        if pick is not None:
            self.picks.append(pick)
        return True, pick is not None

    def record_prices(self, rows, known):
        self.prices += rows
        return len(rows)

    def record_fetch(self, credits, fired_at):
        self.fetches.append((credits, fired_at))

    def notify(self, d):
        pass

    def recycle(self):
        pass

    def close(self):
        pass


def make_loop(clock, plays, books_fn, store=None, remaining=2_000_000, feed_remaining=None, state="in"):
    espn = FakeEspn(clock, plays, state)
    sess = FakeOddsSession(books_fn, remaining)
    feed = O.LiveOddsFeed(session=sess, remaining=feed_remaining, now=clock.now)
    loop = G.Loop(store or FakeStore(), espn, feed, ART, now=clock.now, sleep=clock.sleep, settle=30)
    return loop, espn, sess


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "test-key")


# A Q3 board, every quote stamped 20 s before the tick and fresh: home well
# ahead, so the model likes home on the spread and the moneyline.
def q3_books(stamp=None, pin_stamp=None, home_ml=-150, home_sp=(-6.5, -110, -110)):
    s = stamp or at(1, 55, 16)
    p = pin_stamp or s
    return lambda: [book("draftkings", s, ml=(home_ml, +125), spread=home_sp),
                    book("fanduel", s, ml=(home_ml - 10, +120), spread=(home_sp[0], -115, -105)),
                    book("pinnacle", p, ml=(-180, +160), spread=(-8.5, -105, -105))]


TICK = at(1, 55, 36)


# ── the tick ─────────────────────────────────────────────────────────────────

def test_the_tick_is_hh_55_36_utc_inside_a_four_minute_window():
    c = G.TickClock()
    assert c.due(at(1, 55, 36)) == pd.Timestamp(at(1, 55, 36))
    assert c.due(at(1, 59, 30)) == pd.Timestamp(at(1, 55, 36))
    assert c.due(at(1, 59, 37)) is None                      # past the window
    assert c.due(at(1, 55, 30)) is None                      # before it
    assert c.due(at(2, 0, 0)) is None                        # the top of the hour is not a tick
    c.mark(at(1, 55, 36))
    assert c.due(at(1, 57, 0)) is None                       # consumed once
    assert c.due(at(2, 55, 40)) == pd.Timestamp(at(2, 55, 36))


def test_a_pass_between_ticks_makes_no_odds_call():
    clock = Clock(at(1, 40))
    loop, _, sess = make_loop(clock, game_plays(), q3_books())
    out = loop.pass_once()
    assert out["ours"] == 1 and out["tick"] is None
    assert sess.calls == 0


# ── the decision ─────────────────────────────────────────────────────────────

def test_a_q3_tick_decides_each_q3_model_once_and_bets_the_side_the_model_favours():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, sess = make_loop(clock, game_plays(), q3_books())
    out = loop.pass_once()
    assert sess.calls == 1
    led = loop.store.ledger
    assert set(m for (_, m) in led) == {"nba_live_spread_q3", "nba_live_moneyline"}
    # the first-half model is not decided in Q3 (its phase is over, nothing eligible)
    assert ("nba_live_spread_h1" not in {m for (_, m) in led})
    bets = {p["model_id"]: p for p in loop.store.picks}
    assert bets["nba_live_moneyline"]["pick_side"] == "home"
    assert bets["nba_live_moneyline"]["pick_label"] == "BOS ML (live)"
    assert bets["nba_live_spread_q3"]["pick_label"].startswith("BOS -6.5")
    assert all(p["is_live"] and p["signal_type"] == "BET" for p in loop.store.picks)
    assert out["tick"]["decisions"] == 2


def test_one_decision_per_model_a_later_tick_never_writes_a_second():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, sess = make_loop(clock, game_plays(), q3_books())
    loop.pass_once()
    n = len(loop.store.ledger)
    clock.t = at(2, 55, 40)
    loop.espn.plays = game_plays() + [play(99, at(2, 50), 3, 30, "miss")]
    loop.feed._session.books_fn = q3_books(stamp=at(2, 55, 20), home_ml=+300)
    loop.pass_once()
    assert len(loop.store.ledger) == n
    assert len(loop.store.picks) == 2


def test_the_lock_survives_a_restart():
    clock = Clock(TICK + timedelta(seconds=5))
    store = FakeStore(ledger={(GID, "nba_live_moneyline"): {"reason": "earlier process"}})
    loop, _, _ = make_loop(clock, game_plays(), q3_books(), store=store)
    loop.pass_once()
    assert [p["model_id"] for p in store.picks] == ["nba_live_spread_q3"]
    # and a BET already in picks locks its model the same way
    store2 = FakeStore(picks=[{"game_id": GID, "model_id": "nba_live_spread_q3"}])
    loop2, _, _ = make_loop(Clock(TICK + timedelta(seconds=5)), game_plays(), q3_books(), store=store2)
    loop2.pass_once()
    assert {p["model_id"] for p in store2.picks} == {"nba_live_spread_q3", "nba_live_moneyline"}
    assert len([p for p in store2.picks if p["model_id"] == "nba_live_spread_q3"]) == 1


# ── freshness ────────────────────────────────────────────────────────────────

def test_a_point_after_the_quotes_stamp_refuses_it_and_the_next_tick_decides():
    clock = Clock(TICK + timedelta(seconds=5))
    plays = game_plays() + [play(50, at(1, 55, 25), 3, 200, "make2", team=AID, athlete=2002)]
    loop, _, _ = make_loop(clock, plays, q3_books(stamp=at(1, 55, 16)))
    loop.pass_once()
    assert loop.store.ledger == {}                            # nothing eligible: nothing decided
    # an hour later, quotes stamped after the last score
    clock.t = at(2, 55, 40)
    loop.feed._session.books_fn = q3_books(stamp=at(2, 55, 10))
    loop.espn.plays = plays + [play(51, at(2, 40), 3, 60, "miss")]
    loop.pass_once()
    assert {m for (_, m) in loop.store.ledger} == {"nba_live_spread_q3", "nba_live_moneyline"}


def test_a_point_after_pinnacles_stamp_refuses_the_pair():
    clock = Clock(TICK + timedelta(seconds=5))
    plays = game_plays() + [play(50, at(1, 55, 10), 3, 210, "make2", team=AID, athlete=2002)]
    loop, _, _ = make_loop(clock, plays, q3_books(stamp=at(1, 55, 20), pin_stamp=at(1, 55, 5)))
    loop.pass_once()
    assert loop.store.ledger == {}


def test_a_play_espn_posts_late_is_still_counted_because_the_summary_is_read_after_settling():
    clock = Clock(TICK + timedelta(seconds=5))
    late = play(50, at(1, 55, 25), 3, 200, "make2", team=AID, athlete=2002)
    late["_posted"] = iso(TICK + timedelta(seconds=25))       # posted 20 s after the fetch
    loop, _, _ = make_loop(clock, game_plays() + [late], q3_books(stamp=at(1, 55, 16)))
    loop.pass_once()
    assert loop.store.ledger == {}


def test_pinnacle_must_have_quoted_within_60_seconds():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, _ = make_loop(clock, game_plays(), q3_books(stamp=at(1, 55, 20), pin_stamp=at(1, 54, 19)))
    loop.pass_once()
    assert loop.store.ledger == {}                            # 61 s apart: no pair, nothing eligible
    loop2, _, _ = make_loop(Clock(TICK + timedelta(seconds=5)), game_plays(),
                            q3_books(stamp=at(1, 55, 20), pin_stamp=at(1, 54, 21)))
    loop2.pass_once()
    assert len(loop2.store.ledger) == 2                       # 59 s apart: paired


# ── the price floor ──────────────────────────────────────────────────────────

def test_the_price_floor_refuses_a_price_shorter_than_minus_200():
    clock = Clock(TICK + timedelta(seconds=5))
    books = lambda: [book("draftkings", at(1, 55, 16), ml=(-260, +210)),        # noqa: E731
                     book("fanduel", at(1, 55, 16), ml=(-250, +205)),
                     book("pinnacle", at(1, 55, 16), ml=(-300, +250))]
    loop, _, _ = make_loop(clock, game_plays(), books)
    loop.pass_once()
    row = loop.store.ledger[(GID, "nba_live_moneyline")]
    assert row["bet"] is False and row["reason"].startswith("no_offer_at_floor")
    assert loop.store.picks == []


def test_the_side_is_chosen_before_the_floor_as_the_lab_chose_it():
    """Home's best offer has the higher EV but only at -250; a -190 home price
    elsewhere clears the floor and is the bet -- never the away side."""
    clock = Clock(TICK + timedelta(seconds=5))
    books = lambda: [book("draftkings", at(1, 55, 16), ml=(-250, +210)),        # noqa: E731
                     book("fanduel", at(1, 55, 16), ml=(-190, +150)),
                     book("pinnacle", at(1, 55, 16), ml=(-300, +250))]
    loop, _, _ = make_loop(clock, game_plays(), books)
    loop.pass_once()
    bets = [p for p in loop.store.picks if p["model_id"] == "nba_live_moneyline"]
    assert len(bets) == 1 and bets[0]["pick_side"] == "home" and bets[0]["decision_odds"] == -190
    assert bets[0]["decision_book"] == "fanduel"


# ── labels ───────────────────────────────────────────────────────────────────

def test_an_away_spread_quotes_the_away_teams_own_number():
    d = M.Decision("nba_live_spread_q3", GID, "spreads", "Q3", SEASON, None, None, True, "bet",
                   side="away", line=-3.5, price=-110)
    assert M.pick_label(d, HOME, AWAY) == "NYK +3.5 (live)"
    d.side = "home"
    assert M.pick_label(d, HOME, AWAY) == "BOS -3.5 (live)"


def test_a_label_that_disagrees_with_its_fields_is_refused():
    d = M.Decision("nba_live_spread_q3", GID, "spreads", "Q3", SEASON, None, None, True, "bet",
                   side="away", book="fanduel", line=-3.5, price=-110, p_win=0.6, h_pts=50, a_pts=40)
    g = G.Game(GID, EID, HOME, AWAY, SEASON, "2026-11-19", TIP)
    pick = G.build_pick(d, g, 1000.0, {})
    assert G.pick_refusal(pick, d, g) is None
    bad = dict(pick, pick_label="NYK -3.5 (live)")            # the HOME number on the away side
    assert "label mismatch" in G.pick_refusal(bad, d, g)


# ── credits ──────────────────────────────────────────────────────────────────

def test_no_odds_call_under_the_account_floor():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, sess = make_loop(clock, game_plays(), q3_books(), feed_remaining=O.MIN_REMAINING - 1)
    out = loop.pass_once()
    assert sess.calls == 0 and "floor" in out["tick"]["reason"]
    assert loop.store.ledger == {}


def test_no_odds_call_past_the_daily_cap():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, sess = make_loop(clock, game_plays(), q3_books(), store=FakeStore(used=O.DAILY_CREDIT_CAP))
    loop.pass_once()
    assert sess.calls == 0


def test_the_floor_is_read_from_each_response():
    clock = Clock(TICK + timedelta(seconds=5))
    loop, _, sess = make_loop(clock, game_plays(), q3_books(), remaining=O.MIN_REMAINING - 10)
    loop.pass_once()
    assert sess.calls == 1 and loop.feed.remaining == O.MIN_REMAINING - 10
    assert "floor" in loop.feed.refusal(0)
    assert loop.store.fetches and loop.store.fetches[0][0] == 2


# ── phases ───────────────────────────────────────────────────────────────────

def _rows_at(stamp: datetime, plays: list[dict], final=False) -> pd.DataFrame:
    recs = E.records_from_summary(summary(plays))
    pl = S.plays_from_records(recs, EID, GID, SEASON)
    q = pd.DataFrame([{"game_id": GID, "season": SEASON, "game_date": "2026-11-19", "tip": pd.Timestamp(TIP),
                       "market": "h2h", "book": "draftkings", "label": "in_play", "stamp": pd.Timestamp(stamp),
                       "fetch_at": pd.Timestamp(stamp), "served_at": pd.Timestamp(stamp) + pd.Timedelta(seconds=5),
                       "served_newest": pd.Timestamp(stamp), "line": np.nan, "price_a": -110, "price_b": -110,
                       "implied_sum": 1.04, "coherent": True, "fa": 0.5}])
    rows, _ = S.tick_rows(q, pl, pd.DataFrame(), final=final)
    return rows


def test_a_stamp_after_the_last_logged_play_of_a_game_in_progress_is_live():
    rows = _rows_at(at(1, 52), game_plays())                  # Q3 under way, last play 01:50
    assert list(rows["phase"]) == ["live"] and int(rows["period"].iloc[0]) == 3
    assert M.phase_label(rows).tolist() == ["Q3"]


def test_the_halftime_break_is_not_a_phase():
    rows = _rows_at(at(1, 10), game_plays(through="half"))    # Q2 ended at 01:05, Q3 not started
    assert list(rows["phase"]) == ["halftime"]
    assert M.phase_label(rows).tolist() == [""]


def test_the_second_quarter_is_the_first_half_phase():
    rows = _rows_at(at(0, 52), game_plays(through="q2"))
    assert M.phase_label(rows).tolist() == ["Q1-Q2"]


def test_a_finished_game_keeps_the_labs_postgame_label():
    rows = _rows_at(at(1, 52), game_plays(), final=True)
    assert rows.empty                                         # postgame is not in play


# ── ESPN parsing ─────────────────────────────────────────────────────────────

def test_the_espn_summary_parses_into_the_labs_play_rows():
    j = json.loads(FIX.read_text(encoding="utf-8"))
    recs = E.records_from_summary(j)
    assert len(recs) == 80 and recs[0]["home_team_abbrev"] == "MIL" and recs[0]["away_team_abbrev"] == "BOS"
    assert S.sides_swapped(recs, 401836747, "MIL", "BOS") is False
    assert S.sides_swapped(recs, 401836747, "BOS", "MIL") is True
    pl = S.plays_from_records(recs, 401836747, "NBA_2025-12-11_BOS_MIL", 2026)
    assert {"wc", "points", "pf", "tf", "fg3a", "team_side"} <= set(pl.columns)
    assert pl["wc"].notna().all() and pl["team_side"].isin([D.HOME, D.AWAY, None]).all()
    assert sum(1 for r in E.starters_from_summary(j) if r["starter"]) == 10
    assert E.summary_status(j)["state"] == "post"


def test_quotes_seen_at_an_earlier_tick_are_dropped_as_the_lab_dropped_them():
    rows = O.parse_events([{"home_team": HOME_NAME, "away_team": AWAY_NAME, "commence_time": iso(TIP),
                            "bookmakers": q3_books()()}], at(1, 55, 40), {GID})
    games = {GID: {"season": SEASON, "game_date": "2026-11-19", "tip": TIP}}
    q = S.quote_frame(rows, games, pd.Timestamp(TICK), pd.Timestamp(at(1, 55, 40)), O.BOOKS)
    seen = set(zip(q["game_id"], q["market"], q["book"], q["stamp"]))
    q2 = S.quote_frame(rows, games, pd.Timestamp(TICK), pd.Timestamp(at(1, 55, 40)), O.BOOKS, seen)
    assert len(q) == 6 and q2.empty
    assert set(q["book"]) == {"draftkings", "fanduel", "pinnacle"}
