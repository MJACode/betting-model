"""The NBA in-play loop (models/nba_live_loop.py), driven slot by slot with a
fake ESPN, a fake Odds API and the database calls replaced.

Pinned here:
  * THE CADENCE IS THE GRADE'S PURCHASE GRID: a fetch only at an hourly
    instant or a listed tip time, the first tick at or after it, at most
    10 minutes late, once; no fetch on any other tick;
  * a fetch with no eligible quote decides nothing and the next instant tries
    again; an eligible fetch decides the rule, bet or not, and the rule is
    never decided again -- in this process or after a restart (the ledger);
  * the loop reads the play-by-play only after waiting past the fetch, so a
    basket logged before the served time counts;
  * one game never carries two bets that cannot both win;
  * the pick row: label, the HOME number, the deciding book and price,
    P(win | no push), is_live, the quarter and home-minus-away score;
  * --dry-run writes nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from tests import _nba_live_synth as S
import models.nba_live_ig2 as M
import models.nba_live_loop as LP
from data.ingestors.nba_live_feed import Fetch, parse_scoreboard


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now = self.now + timedelta(seconds=float(s))


class FakeEspn:
    def __init__(self, plays, clock, period=2, state="in"):
        self.plays, self.clock, self.period, self.state = plays, clock, period, state
        self.calls = 0

    def scoreboard(self, d):
        self.calls += 1
        return parse_scoreboard(S.scoreboard_event(self.period, self.state)) if d == S.GAME_DATE else []

    def summary(self, eid):
        self.calls += 1
        return S.summary(self.plays, known_until=self.clock.now)


class FakeFeed:
    def __init__(self, clock, books_at):
        self.clock, self.books_at = clock, books_at
        self.calls = 0
        self.credits_used = 0

    def fetch(self):
        self.calls += 1
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
    """The loop's database calls, in memory."""

    def __init__(self, extra_tip=None, standing=None):
        self.ledger: dict = {}
        self.picks: list = []
        self.credits: list = []
        self.prices: list = []
        self.extra_tip = extra_tip
        self.standing = standing or []

    def install(self, monkeypatch):
        db = self

        def slate_games(conn, dates):
            out = {(S.GAME_DATE, "NYK", "BOS"): LP.GameCtx(S.GAME_ID, S.GAME_DATE, 2027, "BOS", "NYK",
                                                          pd.Timestamp(S.TIP))}
            if db.extra_tip is not None:      # another game of the slate, not in play: its tip is a slot
                out[(S.GAME_DATE, "ORL", "MIA")] = LP.GameCtx("NBA_2026-11-04_ORL_MIA", S.GAME_DATE, 2027,
                                                             "MIA", "ORL", pd.Timestamp(db.extra_tip))
            return out

        def load_prior(conn, ctx, art):
            ctx.mu_pre = 2.0

        def load_top(conn, ctx, starters):
            ctx.top = M.top_players(ctx.game_id, ctx.espn_event_id, starters,
                                    pd.DataFrame(columns=["espn_id", "minutes", "game_date", "season"]),
                                    ctx.game_date, ctx.season)

        def insert_ledger(conn, row):
            k = (row["game_id"], row["model_id"])
            if k in db.ledger:
                return False
            db.ledger[k] = row
            return True

        def write_bet(conn, pick):
            if any(p["game_id"] == pick["game_id"] and p["model_id"] == pick["model_id"] for p in db.picks):
                return False
            db.picks.append(pick)
            return True

        monkeypatch.setattr(LP, "slate_games", slate_games)
        monkeypatch.setattr(LP, "load_prior", load_prior)
        monkeypatch.setattr(LP, "load_top", load_top)
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
        return self


def books(stamp, fd_spread=(-2.5, -120, 100), dk_spread=(-3.5, -105, -115), ml=(-140, 120)):
    return [S.book("pinnacle", stamp - timedelta(seconds=3), h2h=(-150, 130), spread=(-3.5, -110, -110)),
            S.book("draftkings", stamp, h2h=ml, spread=dk_spread),
            S.book("fanduel", stamp, h2h=(ml[0] - 5, ml[1] + 5), spread=fd_spread)]


def make_loop(art, plays, clock, books_at, db, dry_run=False, period=2):
    return LP.Loop(art, FakeEspn(plays, clock, period=period), FakeFeed(clock, books_at), lambda: FakeConn(),
                   dry_run=dry_run, wait=45.0, sleep=clock.sleep, clock=clock,
                   slate_dates=lambda: [S.GAME_DATE])


# ─── the cadence ──────────────────────────────────────────────────────────────

def test_slots_are_the_top_of_each_hour_and_every_listed_tip():
    t = datetime(2026, 11, 5, 0, 37, 10, tzinfo=timezone.utc)
    tips = [pd.Timestamp("2026-11-05T00:30:00Z"), pd.Timestamp("2026-11-05T01:30:00Z")]
    inst = LP.Slots.instants(t, tips)
    assert datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc) in inst
    assert datetime(2026, 11, 5, 0, 30, tzinfo=timezone.utc) in inst
    s = LP.Slots(late=600)
    assert s.due(t, tips) == datetime(2026, 11, 5, 0, 30, tzinfo=timezone.utc)
    s.mark(s.due(t, tips), t, tips)
    assert s.due(t + timedelta(seconds=20), tips) is None                 # once
    late = LP.Slots(late=600)
    assert late.due(datetime(2026, 11, 5, 0, 41, tzinfo=timezone.utc), tips) is None   # 11 min late: skipped
    assert late.due(datetime(2026, 11, 5, 1, 0, 30, tzinfo=timezone.utc), tips) is not None


def test_no_fetch_on_a_tick_that_is_not_a_slot(art, monkeypatch):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    clock = Clock(w + timedelta(seconds=20))                  # 00:32:xx, no instant within 10 min
    db = Db().install(monkeypatch)
    loop = make_loop(art, plays, clock, lambda now: books(w + timedelta(seconds=5)), db)
    res = loop.tick()
    assert res["live"] == 1 and res["slot"] is None
    assert loop.feed.calls == 0 and db.ledger == {}


def test_a_slot_fetches_once_decides_and_writes_the_bet(art, monkeypatch):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    slot = w + timedelta(seconds=20)
    db = Db(extra_tip=slot).install(monkeypatch)
    clock = Clock(slot)
    loop = make_loop(art, plays, clock, lambda now: books(w + timedelta(seconds=5)), db)
    res = loop.tick()
    assert loop.feed.calls == 1 and db.credits == [2]
    assert (S.GAME_ID, M.SPREAD_Q12) in db.ledger
    assert db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet"
    assert len(db.picks) == 1 and res["decisions"] == 1
    p = db.picks[0]
    assert p["model_id"] == M.SPREAD_Q12 and p["is_live"] is True and p["signal_type"] == "BET"
    assert p["pick_side"] == "away" and p["pick_label"] == "NYK +2.5 (live)"
    assert p["scored_line"] == -2.5                           # the HOME number
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == 100.0
    assert p["line_book"] == "fanduel"                       # DraftKings hung -3.5, not -2.5
    assert p["dk_odds"] is None and p["edge"] == 0.0
    assert p["inning_at_pick"] == 2 and p["score_diff_at_pick"] == db.ledger[
        (S.GAME_ID, M.SPREAD_Q12)]["h_pts"] - db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["a_pts"]
    assert db.prices and all(r["snapshot_type"] == "in_play" for r in db.prices)
    from tracking.pick_integrity import pick_problems
    assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"], p["model_id"], "BOS", "NYK") == []
    # the same tick again: the slot is spent, nothing is fetched
    clock.now = slot + timedelta(seconds=90)
    loop.tick()
    assert loop.feed.calls == 1


def test_the_wait_puts_a_basket_logged_before_the_served_time_into_the_rule(art, monkeypatch):
    """A basket logged 10 s after the quotes' stamp and before the fetch:
    the loop reads ESPN only after its wait, so the quote is stale and the
    fetch decides nothing."""
    base = S.build_plays()
    w = S.wall_of(base, 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    slot = w + timedelta(seconds=20)
    db = Db(extra_tip=slot).install(monkeypatch)
    clock = Clock(slot)
    loop = make_loop(art, plays, clock, lambda now: books(w + timedelta(seconds=5)), db)
    loop.tick()
    assert loop.feed.calls == 1 and db.ledger == {}


def test_an_ineligible_slot_carries_and_the_next_one_decides(art, monkeypatch):
    base = S.build_plays()
    w = S.wall_of(base, 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    first = w + timedelta(seconds=20)
    w2 = S.wall_of(base, 2, 240.0)                 # a later made shot in quarter 2
    second = w2 + timedelta(seconds=20)
    db = Db(extra_tip=first).install(monkeypatch)
    clock = Clock(first)
    stamps = {first: w + timedelta(seconds=5), second: w2 + timedelta(seconds=5)}
    loop = make_loop(art, plays, clock, lambda now: books(max(s for k, s in stamps.items() if k <= now)), db)
    loop.tick()
    assert db.ledger == {}
    db.extra_tip = None
    loop.ctxs[(S.GAME_DATE, "ORL", "MIA")].tip = pd.Timestamp(second)
    clock.now = second
    loop.tick()
    assert loop.feed.calls == 2 and (S.GAME_ID, M.SPREAD_Q12) in db.ledger


def test_an_eligible_fetch_that_misses_the_cut_spends_the_rule(art, monkeypatch):
    """The first eligible fetch decides the rule even when nothing clears the
    cut; a later fetch whose offer WOULD clear it is never used."""
    import config
    base = S.build_plays()
    w = S.wall_of(base, 2, 420.0)
    w2 = S.wall_of(base, 2, 240.0)
    first, second = w + timedelta(seconds=20), w2 + timedelta(seconds=20)
    db = Db(extra_tip=first).install(monkeypatch)
    clock = Clock(first)
    stamps = {first: w + timedelta(seconds=5), second: w2 + timedelta(seconds=5)}
    loop = make_loop(art, base, clock, lambda now: books(max(s_ for k, s_ in stamps.items() if k <= now)), db)
    floors = dict(config.MODEL_OWN_EV_FLOOR)
    monkeypatch.setattr(config, "MODEL_OWN_EV_FLOOR", {**floors, M.SPREAD_Q12: 5.0})   # nothing clears
    loop.tick()
    row = db.ledger.get((S.GAME_ID, M.SPREAD_Q12))
    assert row is not None and row["outcome"] == "no_bet" and db.picks == []
    monkeypatch.setattr(config, "MODEL_OWN_EV_FLOOR", floors)                          # it would clear now
    loop.ctxs[(S.GAME_DATE, "ORL", "MIA")].tip = pd.Timestamp(second)
    clock.now = second
    loop.tick()
    assert db.picks == [] and len([k for k in db.ledger if k[1] == M.SPREAD_Q12]) == 1


def test_a_restart_never_decides_a_rule_the_ledger_holds(art, monkeypatch):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    slot = w + timedelta(seconds=20)
    db = Db(extra_tip=slot).install(monkeypatch)
    db.ledger[(S.GAME_ID, M.SPREAD_Q12)] = {"outcome": "no_bet"}
    clock = Clock(slot)
    loop = make_loop(art, plays, clock, lambda now: books(w + timedelta(seconds=5)), db)
    loop.tick()
    assert db.picks == [] and len(db.ledger) == 1


def test_a_bet_that_cannot_win_beside_a_standing_one_is_declined(art, monkeypatch):
    """These prices bet NYK +2.5 (the HOME number -2.5: NYK covers on a home
    margin of 2 or less). A standing BOS -30.5 needs 31 or more: never both."""
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    slot = w + timedelta(seconds=20)
    standing = [{"model_id": M.SPREAD_Q3, "market": "spreads", "side": "home", "line": -30.5,
                 "label": "BOS -30.5 (live)"}]
    db = Db(extra_tip=slot, standing=standing).install(monkeypatch)
    loop = make_loop(art, plays, Clock(slot), lambda now: books(w + timedelta(seconds=5)), db)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert row["side"] == "away" and row["line"] == -2.5
    assert row["outcome"] == "declined" and "cannot both win" in row["reason"] and db.picks == []
    # and a standing bet that CAN win beside it leaves the bet alone
    db2 = Db(extra_tip=slot, standing=[{**standing[0], "line": -1.5, "label": "BOS -1.5 (live)"}]).install(monkeypatch)
    loop2 = make_loop(art, plays, Clock(slot), lambda now: books(w + timedelta(seconds=5)), db2)
    loop2.tick()
    assert db2.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet" and len(db2.picks) == 1


def test_a_paused_model_is_declined_not_bet(art, monkeypatch):
    import config
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    slot = w + timedelta(seconds=20)
    db = Db(extra_tip=slot).install(monkeypatch)
    monkeypatch.setattr(config, "PAUSED_MODELS", set(config.PAUSED_MODELS) | {M.SPREAD_Q12})
    loop = make_loop(art, plays, Clock(slot), lambda now: books(w + timedelta(seconds=5)), db)
    loop.tick()
    assert db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "declined" and db.picks == []


def test_dry_run_writes_nothing(art, monkeypatch):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    slot = w + timedelta(seconds=20)
    db = Db(extra_tip=slot).install(monkeypatch)
    loop = make_loop(art, plays, Clock(slot), lambda now: books(w + timedelta(seconds=5)), db, dry_run=True)
    res = loop.tick()
    assert res["decisions"] == 1
    assert db.ledger == {} and db.picks == [] and db.credits == [] and db.prices == []


def test_a_game_espn_lists_the_other_way_round_still_matches(art, monkeypatch):
    plays = S.build_plays()
    db = Db().install(monkeypatch)
    loop = make_loop(art, plays, Clock(S.TIP + timedelta(minutes=30)), lambda now: [], db)
    ev = parse_scoreboard(S.scoreboard_event())[0]
    flipped = type(ev)(**{**ev.__dict__, "home": ev.away, "away": ev.home})
    assert len(loop.match([flipped])) == 1


# ─── the gates ────────────────────────────────────────────────────────────────

def test_a_bet_at_the_rules_cut_clears_the_platform_gates():
    import config
    for mid in M.MODEL_IDS:
        # EV exactly at the cut on P(win | no push): 0.525 x 2.0 - 1 = 0.05
        assert LP.platform_gates(mid, 0.525, 100.0) is None
        assert LP.platform_gates(mid, 0.80, -210.0) is not None          # under the -200 floor
        assert config.min_ev_for(mid) == 0.05 and config.min_odds_for(mid) == -200
