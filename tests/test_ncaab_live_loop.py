"""The NCAAB in-play loop (models/ncaab_live_loop.py), driven window by window
with a fake ESPN, a fake Odds API and the database calls replaced.

Pinned here:
  * THE FETCH TIMES ARE THE GRADE'S HALF-HOUR PURCHASE: each :00 and :30 minus
    262 s, a 240 s window, never a time built from a tip;
  * an eligible fetch decides the rule, bet or not, once; the ledger stops a
    restart deciding it again; a quote older than a score is not eligible;
  * THE NIGHT: a decision bets only at or above tonight's cut, and only while
    the night holds fewer than five bets; otherwise it spends the rule;
  * ESPN is read after a wait and again after a recheck, and a play logged
    before the served time that only the second read carries skips the game;
  * no #ncaab-live destination: nothing is decided;
  * one game never carries two bets that cannot both win;
  * the pick row: label, the HOME number, the deciding book, P(win | no push),
    is_live, the half; --dry-run makes no paid call.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from tests import _ncaab_live_synth as S
import models.ncaab_live_ig as M
import models.ncaab_live_loop as LP
from data.ingestors.nba_live_feed import Fetch
from data.ingestors.ncaab_live_feed import parse_scoreboard


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def slots_at(instant: datetime, window: float = 240.0) -> LP.Slots:
    """LP.Slots whose window opens at `instant`."""
    nxt = instant.replace(minute=(instant.minute // 30) * 30, second=0, microsecond=0) + timedelta(minutes=30)
    return LP.Slots(offset=(nxt - instant).total_seconds(), window=window)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now = self.now + timedelta(seconds=float(s))


class FakeEspn:
    def __init__(self, plays, clock, lag=0.0, down=0):
        self.plays, self.clock, self.lag, self.down = plays, clock, float(lag), int(down)
        self.calls = 0

    def scoreboard(self, d):
        self.calls += 1
        return parse_scoreboard(S.scoreboard()) if d == S.GAME_DATE else []

    def summary(self, eid):
        self.calls += 1
        if self.down > 0:
            self.down -= 1
            return None
        return S.summary(self.plays, known_until=self.clock.now - timedelta(seconds=self.lag))


class FakeFeed:
    def __init__(self, clock, books_at, fail=0):
        self.clock, self.books_at, self.fail = clock, books_at, int(fail)
        self.calls = 0
        self.credits_used = 0

    def fetch(self):
        self.calls += 1
        if self.fail > 0:
            self.fail -= 1
            return None
        self.credits_used += 2
        return Fetch(S.events(self.books_at(self.clock.now)), self.clock.now, 2, 10_000)


class FakeConn:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Db:
    def __init__(self, standing=None, night=0, slate=1):
        self.ledger: dict = {}
        self.notes: list = []
        self.picks: list = []
        self.credits: list = []
        self.prices: list = []
        self.standing = standing or []
        self.night, self.slate = night, slate

    @property
    def skips(self):
        return [r for r in self.notes if r["outcome"] == "skipped"]

    @property
    def carried(self):
        return [r for r in self.notes if r["outcome"] == "carried"]

    def install(self, monkeypatch):
        db = self

        def slate_games(conn, dates):
            return {S.EVENT_ID: LP.GameCtx(S.GAME_ID, S.GAME_DATE, 2027, S.HOME, S.AWAY, pd.Timestamp(S.TIP),
                                           S.EVENT_ID, S.HOME_ID, S.AWAY_ID)}

        def load_prior(conn, ctx):
            ctx.prior = pd.DataFrame([{"game_id": ctx.game_id, "mu_pre": 12.0, "T_pre": 145.0,
                                       "prior_src": "pinnacle"}])

        def insert_ledger(conn, row):
            k = (row["game_id"], row["model_id"])
            if row["outcome"] in ("skipped", "carried"):
                db.notes.append(row)
                return True
            if k in db.ledger:
                return False
            db.ledger[k] = row
            return True

        def write_bet(conn, pick):
            db.picks.append(pick)
            return True

        monkeypatch.setattr(LP, "slate_games", slate_games)
        monkeypatch.setattr(LP, "load_prior", load_prior)
        monkeypatch.setattr(LP, "slate_size", lambda conn, d: db.slate)
        monkeypatch.setattr(LP, "night_bets", lambda conn, d: db.night)
        monkeypatch.setattr(LP, "decided_keys", lambda conn, ids: set(db.ledger))
        monkeypatch.setattr(LP, "insert_ledger", insert_ledger)
        monkeypatch.setattr(LP, "write_bet", write_bet)
        monkeypatch.setattr(LP, "standing_bets", lambda conn, gid: list(db.standing))
        monkeypatch.setattr(LP, "under_daily_cap", lambda conn, cost: True)
        monkeypatch.setattr(LP, "record_credits", lambda conn, c: db.credits.append(c))
        import data.ingestors.live_price_log as lpl
        monkeypatch.setattr(lpl, "record_live_prices",
                            lambda conn, rows, known_game_ids=None: db.prices.extend(rows) or len(rows))
        import models.scorer as sc
        monkeypatch.setattr(sc, "_get_current_bankroll", lambda conn: 1000.0)
        import config
        import tracking.job_heartbeat as jh
        monkeypatch.setattr(jh, "beat", lambda *a, **k: None)
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {"NCAAB": "https://example.invalid/ncaab-live"})
        return self


def books(stamp, dk=(-6.5, -110, -110), fd=(-6.5, -105, -115), total=(150.5, -110, -110)):
    return [S.book("pinnacle", stamp, spread=(-9.5, -110, -110), total=total),
            S.book("draftkings", stamp, spread=dk, total=total),
            S.book("fanduel", stamp, spread=fd, total=total)]


def resolver():
    return lambda home, away, commence: (S.GAME_ID, False)


def make_loop(art, plays, clock, books_at, db, slot, dry_run=False, lag=0.0, down=0, fail=0):
    return LP.Loop(art, FakeEspn(plays, clock, lag=lag, down=down), FakeFeed(clock, books_at, fail=fail),
                   lambda: FakeConn(), dry_run=dry_run, wait=90.0, recheck=60.0, sleep=clock.sleep,
                   clock=clock, slate_dates=lambda: [S.GAME_DATE], slots=slots_at(slot),
                   resolver_factory=resolver)


def standard(art, monkeypatch, plays=None, stamp_offset=5.0, **kw):
    """First half, 10:00 left, Duke 14-6 up (a Duke basket at W); quotes
    stamped 5 s after it; the window opens 20 s after it."""
    plays = plays or S.build_plays()
    w = S.wall_of(S.build_plays(), 1, 600.0)
    slot = w + timedelta(seconds=20)
    db = Db(standing=kw.pop("standing", None), night=kw.pop("night", 0), slate=kw.pop("slate", 1)).install(monkeypatch)
    clock = Clock(slot)
    bk = kw.pop("books_at", None) or (lambda now: books(w + timedelta(seconds=stamp_offset)))
    return make_loop(art, plays, clock, bk, db, slot, **kw), db, clock, w, slot


# ─── the fetch times ──────────────────────────────────────────────────────────

def test_the_fetch_times_are_each_half_hour_minus_262_seconds():
    s = LP.Slots()
    assert s.offset == 262.0 and s.window == 240.0 and s.cadence == 30
    for inst in (datetime(2026, 11, 8, 0, 25, 38, tzinfo=timezone.utc),
                 datetime(2026, 11, 8, 0, 55, 38, tzinfo=timezone.utc)):
        assert s.instant(inst) == inst and s.instant(inst + timedelta(seconds=239)) == inst
        assert s.instant(inst + timedelta(seconds=241)) is None
    assert s.instant(datetime(2026, 11, 8, 0, 10, 0, tzinfo=timezone.utc)) is None     # a tip time


def test_a_window_fetches_once_decides_and_writes_the_bet(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch)
    res = loop.tick()
    assert loop.feed.calls == 1 and db.credits == [2] and db.skips == []
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "bet" and row["night_cut"] == pytest.approx(0.02) and row["slate_games"] == 1
    assert res["decisions"] == 1 and len(db.picks) == 1
    p = db.picks[0]
    assert p["model_id"] == M.SPREAD_H1 and p["is_live"] is True and p["signal_type"] == "BET"
    assert p["pick_side"] == "home" and p["scored_line"] == -6.5                # the HOME number
    assert p["pick_label"] == "Duke -6.5 (live)"
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == -105.0     # the better home price
    assert p["inning_at_pick"] == 1 and p["score_diff_at_pick"] == 8
    assert 0.5 < p["model_probability"] < 1.0
    from tracking.pick_integrity import pick_problems
    assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"], p["model_id"], S.HOME, S.AWAY) == []
    assert db.prices and all(r["snapshot_type"] == "in_play" and r["source"] == "ncaab_live_loop"
                             for r in db.prices)
    clock.now = slot + timedelta(seconds=230)           # still the window: closed after the decision
    loop.tick()
    assert loop.feed.calls == 1


def test_a_quote_stamped_before_a_score_is_not_eligible(art, monkeypatch):
    """Stamped 10 s before Duke's basket: a point was scored between its stamp
    and the fetch, so it decides nothing (carried), as in the grade."""
    loop, db, *_ = standard(art, monkeypatch, stamp_offset=-10.0)
    loop.tick()
    assert db.ledger == {} and db.carried and db.picks == []


# ─── the night ────────────────────────────────────────────────────────────────

def test_a_decision_under_tonights_cut_spends_the_rule(art, monkeypatch):
    high = replace(art, ev_quantiles=np.full(len(art.ev_quantiles), 0.99))
    loop, db, clock, w, slot = standard(high, monkeypatch, slate=150)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "no_bet" and "under tonight's cut" in row["reason"] and db.picks == []
    assert row["night_cut"] == pytest.approx(0.99)
    nxt = slot + timedelta(minutes=30)                   # the next window: the rule stays spent
    clock.now = nxt
    loop.slots = slots_at(nxt)
    loop.tick()
    assert len(db.ledger) == 1 and db.picks == []


def test_a_full_night_spends_the_rule_without_a_bet(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch, night=M.NIGHT_CAP)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "no_bet" and "already holds 5 bets" in row["reason"] and db.picks == []
    assert row["night_bets_before"] == 5


def test_the_night_cut_is_never_under_the_rules_floor(art):
    for r in M.RULES:
        assert M.night_cut(art, 1, r) == pytest.approx(r.floor)
        assert M.night_cut(art, 0, r) == pytest.approx(r.floor)
    big = [M.night_cut(art, n, M.RULES[0]) for n in (10, 60, 150)]
    assert big == sorted(big) and big[-1] > 0.2          # a bigger slate, a higher cut


# ─── ESPN ─────────────────────────────────────────────────────────────────────

def test_espn_publishing_later_than_the_wait_fails_closed(art, monkeypatch):
    """A UNC basket logged 10 s before the fetch, served 120 s after it was
    logged: absent from the first read (90 s after the fetch), present on the
    second (60 s later): the game is skipped, not decided on an incomplete
    picture."""
    w = S.wall_of(S.build_plays(), 1, 600.0)
    plays = S.build_plays(extra=[{"period": 1, "clock_s": 595.0, "wallclock": w + timedelta(seconds=10),
                                  "team": "A", "points": 2}])
    loop, db, *_ = standard(art, monkeypatch, plays=plays, lag=120.0)
    loop.tick()
    assert db.ledger == {} and db.skips and "publishing late" in db.skips[0]["reason"]


def test_an_unreadable_summary_is_skipped_and_retried_in_the_window(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch, down=3)
    loop.tick()
    assert db.ledger == {} and db.skips
    clock.now = slot + timedelta(seconds=61)
    loop.tick()
    assert db.ledger[(S.GAME_ID, M.SPREAD_H1)]["outcome"] == "bet" and loop.feed.calls == 2


# ─── everything else ──────────────────────────────────────────────────────────

def test_no_ncaab_live_destination_means_nothing_is_decided(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch)
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {})
    res = loop.tick()
    assert res.get("blocked") and loop.feed.calls == 0 and db.ledger == {}


def test_a_restart_never_decides_a_rule_the_ledger_holds(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch)
    for r in M.RULES:
        db.ledger[(S.GAME_ID, r.model_id)] = {"outcome": "no_bet"}
    loop.tick()
    assert loop.feed.calls == 0 and db.picks == []


def test_a_bet_that_cannot_win_beside_a_standing_one_is_declined(art, monkeypatch):
    standing = [{"model_id": M.SPREAD_H2, "market": "spreads", "side": "away", "line": -3.5,
                 "label": "North Carolina +3.5 (live)"}]
    loop, db, *_ = standard(art, monkeypatch, standing=standing)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "declined" and "cannot both win" in row["reason"] and db.picks == []


def test_dry_run_makes_no_paid_call_and_writes_nothing(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch, dry_run=True)
    loop.tick()
    assert loop.feed.calls == 0 and db.ledger == {} and db.picks == [] and db.notes == []


def test_a_failed_odds_call_is_skipped_and_retried(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch, fail=1)
    loop.tick()
    assert db.skips and db.ledger == {}
    clock.now = slot + timedelta(seconds=61)
    loop.tick()
    assert db.ledger[(S.GAME_ID, M.SPREAD_H1)]["outcome"] == "bet"
