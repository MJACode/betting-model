"""The NBA in-play loop (models/nba_live_loop.py), driven window by window with
a fake ESPN, a fake Odds API and the database calls replaced.

Pinned here:
  * THE FETCH TIMES ARE THE GRADE'S HOURLY PURCHASE: each hour minus 264 s,
    a window of 240 s, never a time built from a tip, nothing on any other tick;
  * a fetch with no eligible quote decides nothing and the next window tries
    again; an eligible fetch decides the rule, bet or not, and the rule is
    never decided again -- in this process or after a restart (the ledger);
  * the loop reads ESPN after a wait and AGAIN after a recheck, and skips a
    game whose second read carries a play logged before the served time that
    the first did not (ESPN publishing late: fail closed);
  * an attempt that cannot decide (the feed, ESPN, starters, an error) writes
    a 'skipped' row and is retried inside the same window;
  * the earlier-fetch dedupe survives a restart (seeded from the loop's own
    odds rows), and does not swallow a skipped game's quotes;
  * one game never carries two bets that cannot both win;
  * the pick row: label, the HOME number, the deciding book and price,
    P(win | no push), is_live, the quarter and home-minus-away score;
  * --dry-run writes nothing.

The synthetic game (tests/_nba_live_synth.py) has its plays at minutes that
are not an hour minus 264 s, so each test moves the fetch time to where it
needs it with slots_at(): the same rule, with the offset chosen so the window
opens at that instant.
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


def slots_at(instant: datetime, window: float = 240.0) -> LP.Slots:
    """LP.Slots whose window opens at `instant` (offset = the seconds from it
    to the next hour)."""
    nxt = instant.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return LP.Slots(offset=(nxt - instant).total_seconds(), window=window)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now = self.now + timedelta(seconds=float(s))


class FakeEspn:
    """`lag`: seconds between a play's wallclock (when ESPN logged it) and the
    moment the summary serves it. `down`: summary reads that fail first.
    `header_ahead`: summary reads (from the second on) whose header score is 2
    points ahead of the play list. `frozen_at`: the play list stops at this
    instant; `clock_runs`: the header clock still moves read to read."""

    def __init__(self, plays, clock, period=2, state="in", lag=0.0, down=0, header_ahead=0,
                 frozen_at=None, clock_runs=False):
        self.plays, self.clock, self.period, self.state = plays, clock, period, state
        self.lag, self.down = float(lag), int(down)
        self.header_ahead, self.frozen_at, self.clock_runs = int(header_ahead), frozen_at, clock_runs
        self.reads = 0
        self.calls = 0

    def scoreboard(self, d):
        self.calls += 1
        return parse_scoreboard(S.scoreboard_event(self.period, self.state)) if d == S.GAME_DATE else []

    def summary(self, eid):
        self.calls += 1
        if self.down > 0:
            self.down -= 1
            return None
        self.reads += 1
        until = self.clock.now - timedelta(seconds=self.lag)
        if self.frozen_at is not None:
            until = min(until, self.frozen_at)
        s = S.summary(self.plays, known_until=until)
        comp = s["header"]["competitions"][0]
        if self.header_ahead and self.reads >= 2:
            self.header_ahead -= 1
            for c in comp["competitors"]:
                if c["homeAway"] == "home":
                    c["score"] = str(int(c["score"]) + 2)
        if self.clock_runs:
            comp["status"]["clock"] = float(comp["status"]["clock"]) - 10.0 * self.reads
        return s


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
    """The loop's database calls, in memory."""

    def __init__(self, standing=None, seen=None):
        self.ledger: dict = {}
        self.notes: list = []                  # 'skipped' and 'carried' rows
        self.ledger_attempts: list = []
        self.picks: list = []
        self.credits: list = []
        self.prices: list = []
        self.standing = standing or []
        self.seen = seen or set()

    @property
    def skips(self) -> list:
        return [r for r in self.notes if r["outcome"] == "skipped"]

    @property
    def carried(self) -> list:
        return [r for r in self.notes if r["outcome"] == "carried"]

    def install(self, monkeypatch):
        db = self

        def slate_games(conn, dates):
            return {(S.GAME_DATE, "NYK", "BOS"): LP.GameCtx(S.GAME_ID, S.GAME_DATE, 2027, "BOS", "NYK",
                                                           pd.Timestamp(S.TIP))}

        def load_prior(conn, ctx, art):
            ctx.mu_pre = 2.0

        def load_top(conn, ctx, starters):
            ctx.top = M.top_players(ctx.game_id, ctx.espn_event_id, starters,
                                    pd.DataFrame(columns=["espn_id", "minutes", "game_date", "season"]),
                                    ctx.game_date, ctx.season)

        def insert_ledger(conn, row):
            k = (row["game_id"], row["model_id"])
            if row["outcome"] in ("skipped", "carried"):
                db.notes.append(row)
                return True
            db.ledger_attempts.append(k)
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
        monkeypatch.setattr(LP, "seen_from_odds", lambda conn, ids: set(db.seen))
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
        # NBA live picks have a destination unless a test removes it
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {"NBA": "https://example.invalid/nba-live"})
        return self


def books(stamp, fd_spread=(-2.5, -120, 100), dk_spread=(-3.5, -105, -115), ml=(-140, 120)):
    return [S.book("pinnacle", stamp - timedelta(seconds=3), h2h=(-150, 130), spread=(-3.5, -110, -110)),
            S.book("draftkings", stamp, h2h=ml, spread=dk_spread),
            S.book("fanduel", stamp, h2h=(ml[0] - 5, ml[1] + 5), spread=fd_spread)]


def make_loop(art, plays, clock, books_at, db, slot, dry_run=False, period=2, lag=0.0, down=0, fail=0,
              wait=45.0, recheck=30.0, **espn_kw):
    return LP.Loop(art, FakeEspn(plays, clock, period=period, lag=lag, down=down, **espn_kw),
                   FakeFeed(clock, books_at, fail=fail), lambda: FakeConn(),
                   dry_run=dry_run, wait=wait, recheck=recheck, sleep=clock.sleep, clock=clock,
                   slate_dates=lambda: [S.GAME_DATE], slots=slots_at(slot))


def standard(art, monkeypatch, **kw):
    """The quarter-2 game, a window opening 20 s after the 7:00 made shot,
    quotes stamped 5 s after it."""
    plays = kw.pop("plays", None) or S.build_plays()
    w = S.wall_of(S.build_plays(), 2, 420.0)
    slot = w + timedelta(seconds=20)
    db = Db(standing=kw.pop("standing", None), seen=kw.pop("seen", None)).install(monkeypatch)
    clock = Clock(slot)
    bk = kw.pop("books_at", None) or (lambda now: books(w + timedelta(seconds=5)))
    loop = make_loop(art, plays, clock, bk, db, slot, **kw)
    return loop, db, clock, w, slot


# ─── the fetch times ──────────────────────────────────────────────────────────

def test_the_fetch_time_is_each_hour_minus_264_seconds_never_a_tip():
    """The archive's hourly purchase served the market 264 s before the hour.
    The window opens at hh:55:36 and lasts 240 s; the top of the hour, a :30,
    and a listed tip are not fetch times."""
    s = LP.Slots()
    assert s.offset == 264.0 and s.window == 240.0
    inst = datetime(2026, 11, 5, 0, 55, 36, tzinfo=timezone.utc)
    assert s.instant(inst) == inst
    assert s.instant(inst + timedelta(seconds=239)) == inst
    assert s.instant(inst + timedelta(seconds=241)) is None              # the window has closed
    assert s.instant(datetime(2026, 11, 5, 1, 0, 30, tzinfo=timezone.utc)) is None    # top of the hour
    assert s.instant(datetime(2026, 11, 5, 0, 30, 0, tzinfo=timezone.utc)) is None    # a :30 tip
    assert s.instant(datetime(2026, 11, 5, 0, 10, 0, tzinfo=timezone.utc)) is None    # an actual start
    import inspect
    assert "tip" not in inspect.signature(LP.Slots.instant).parameters


def test_no_fetch_outside_a_window(art, monkeypatch):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)
    db = Db().install(monkeypatch)
    clock = Clock(w + timedelta(seconds=20))
    loop = LP.Loop(art, FakeEspn(plays, clock), FakeFeed(clock, lambda now: books(w + timedelta(seconds=5))),
                   lambda: FakeConn(), sleep=clock.sleep, clock=clock, slate_dates=lambda: [S.GAME_DATE])
    res = loop.tick()                                   # the real Slots: 00:33 is no fetch time
    assert res["live"] == 1 and res["slot"] is None
    assert loop.feed.calls == 0 and db.ledger == {}


def test_a_window_fetches_once_decides_and_writes_the_bet(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch)
    res = loop.tick()
    assert loop.feed.calls == 1 and db.credits == [2]
    assert db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet"
    assert len(db.picks) == 1 and res["decisions"] == 1 and db.skips == []
    p = db.picks[0]
    assert p["model_id"] == M.SPREAD_Q12 and p["is_live"] is True and p["signal_type"] == "BET"
    assert p["pick_side"] == "away" and p["pick_label"] == "NYK +2.5 (live)"
    assert p["scored_line"] == -2.5                           # the HOME number
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == 100.0
    assert p["line_book"] == "fanduel"                       # DraftKings hung -3.5, not -2.5
    assert p["dk_odds"] is None and p["edge"] == 0.0
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert p["inning_at_pick"] == 2 and p["score_diff_at_pick"] == row["h_pts"] - row["a_pts"]
    assert db.prices and all(r["snapshot_type"] == "in_play" and r["source"] == "nba_live_loop"
                             for r in db.prices)
    from tracking.pick_integrity import pick_problems
    assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"], p["model_id"], "BOS", "NYK") == []
    clock.now = slot + timedelta(seconds=150)            # still in the window: it is closed
    loop.tick()
    assert loop.feed.calls == 1


# Production's NOT NULL columns on picks with no default, read from
# information_schema on 2026-11-06. data/supabase_schema.sql still lists
# dk_odds as NOT NULL; production dropped that, and a line-book pick stores
# NULL there. The test fixture enforces none of these, which is how a NULL
# dk_implied_prob passed every test and failed the first real insert.
PICKS_NOT_NULL = ("model_id", "sport", "game_date", "pick_side", "pick_label", "model_probability",
                  "dk_implied_prob", "edge", "kelly_fraction", "recommended_bet", "bankroll_at_pick")


def test_a_bet_draftkings_does_not_price_fills_every_column_production_requires(art, monkeypatch):
    """The 2026-11-06 slate: UTA +5.5 at Hard Rock -105, DraftKings at another number.
    build_pick left dk_implied_prob NULL, the insert failed, and the bet was
    neither stored nor posted. A line-book pick stores 0.0 there, as the
    scorer does."""
    loop, db, _clock, _w, _slot = standard(art, monkeypatch)
    loop.tick()
    p = db.picks[0]
    assert p["line_book"] == "fanduel" and p["dk_odds"] is None    # DraftKings hung another number
    missing = [c for c in PICKS_NOT_NULL if p.get(c) is None]
    assert missing == [], f"production rejects a pick with {missing} NULL"
    assert p["dk_implied_prob"] == 0.0 and p["edge"] == 0.0


# ─── ESPN: the wait, and the second read ──────────────────────────────────────

def test_the_wait_puts_a_basket_logged_before_the_served_time_into_the_rule(art, monkeypatch):
    """A basket logged 5 s before the fetch, served 30 s after it was logged:
    read after the 45 s wait, it is in, the quotes are stale, nothing decided."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    loop, db, clock, w, slot = standard(art, monkeypatch, plays=plays, lag=30.0)
    loop.tick()
    assert loop.feed.calls == 1 and db.ledger == {} and db.skips == []
    loop2, db2, *_ = standard(art, monkeypatch, lag=30.0)       # no basket: decided
    loop2.tick()
    assert (S.GAME_ID, M.SPREAD_Q12) in db2.ledger


def test_espn_publishing_later_than_the_wait_fails_closed(art, monkeypatch):
    """The same basket served 60 s after it was logged: the read after the
    45 s wait misses it, the quotes would read fresh. The second read, 30 s
    later, carries it, so the game is skipped at that attempt (a 'skipped'
    row), and the retry inside the window sees the basket and decides
    nothing."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    loop, db, clock, w, slot = standard(art, monkeypatch, plays=plays, lag=60.0)
    loop.tick()
    assert db.picks == [] and (S.GAME_ID, M.SPREAD_Q12) not in db.ledger
    assert db.skips and "publishing late" in db.skips[0]["reason"]
    clock.now = clock.now + timedelta(seconds=5)          # next tick, inside the window
    loop.tick()
    assert loop.feed.calls == 2 and db.picks == [] and (S.GAME_ID, M.SPREAD_Q12) not in db.ledger


# ─── skipped attempts are retried inside the window ───────────────────────────

def test_a_failed_odds_call_is_skipped_and_retried_in_the_same_window(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch, fail=1)
    loop.tick()
    assert loop.feed.calls == 1 and db.ledger == {}
    assert db.skips and all(r["outcome"] == "skipped" and "feed" in r["reason"] for r in db.skips)
    clock.now = slot + timedelta(seconds=30)            # under the retry gap: not yet
    loop.tick()
    assert loop.feed.calls == 1
    clock.now = slot + timedelta(seconds=70)
    loop.tick()
    assert loop.feed.calls == 2 and db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet"


def test_an_unreadable_espn_summary_is_skipped_and_retried(art, monkeypatch):
    # three failed reads use up the first read's retries: the attempt is skipped
    loop, db, clock, w, slot = standard(art, monkeypatch, down=3)
    loop.tick()
    assert db.ledger == {} and db.skips and "unreadable" in db.skips[0]["reason"]
    clock.now = clock.now + timedelta(seconds=5)
    loop.tick()
    # the retry's quotes are the first attempt's (same stamps): not swallowed by the dedupe
    assert db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet"


def test_a_window_that_closes_without_a_decision_is_not_retried_outside_it(art, monkeypatch):
    loop, db, clock, w, slot = standard(art, monkeypatch, fail=10)
    loop.tick()
    clock.now = slot + timedelta(seconds=300)            # past the 240 s window
    loop.tick()
    assert loop.feed.calls == 1 and db.ledger == {}


# ─── decided once ─────────────────────────────────────────────────────────────

def test_an_ineligible_fetch_decides_nothing_and_is_not_retried(art, monkeypatch):
    """A basket after the stamp and before the fetch, read in time: no eligible
    quote is not a skip. No row, no retry in the window."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    loop, db, clock, w, slot = standard(art, monkeypatch, plays=plays)
    loop.tick()
    clock.now = slot + timedelta(seconds=120)
    loop.tick()
    assert loop.feed.calls == 1 and db.ledger == {} and db.skips == []


def test_an_eligible_fetch_that_misses_the_cut_spends_the_rule(art, monkeypatch):
    """The first eligible fetch decides the rule even when nothing clears the
    cut; a later window whose offer WOULD clear it is never used."""
    import config
    base = S.build_plays()
    w = S.wall_of(base, 2, 420.0)
    w2 = S.wall_of(base, 2, 240.0)
    first, second = w + timedelta(seconds=20), w2 + timedelta(seconds=20)
    db = Db().install(monkeypatch)
    clock = Clock(first)
    stamps = {first: w + timedelta(seconds=5), second: w2 + timedelta(seconds=5)}
    loop = make_loop(art, base, clock, lambda now: books(max(s_ for k, s_ in stamps.items() if k <= now)), db, first)
    floors = dict(config.MODEL_OWN_EV_FLOOR)
    monkeypatch.setattr(config, "MODEL_OWN_EV_FLOOR", {**floors, M.SPREAD_Q12: 5.0})   # nothing clears
    loop.tick()
    row = db.ledger.get((S.GAME_ID, M.SPREAD_Q12))
    assert row is not None and row["outcome"] == "no_bet" and db.picks == []
    monkeypatch.setattr(config, "MODEL_OWN_EV_FLOOR", floors)                          # it would clear now
    loop.slots = slots_at(second)
    clock.now = second
    loop.tick()
    assert db.picks == [] and len([k for k in db.ledger if k[1] == M.SPREAD_Q12]) == 1


def test_a_restart_never_decides_a_rule_the_ledger_holds(art, monkeypatch):
    """A new process reads the ledger: a rule decided by an earlier process is
    not evaluated again, and a game whose three rules are all decided costs
    no fetch at all."""
    loop, db, clock, w, slot = standard(art, monkeypatch)
    db.ledger[(S.GAME_ID, M.SPREAD_Q12)] = {"outcome": "no_bet"}
    loop.tick()
    assert db.picks == [] and (S.GAME_ID, M.SPREAD_Q12) not in db.ledger_attempts
    loop2, db2, *_ = standard(art, monkeypatch)
    for mid in M.MODEL_IDS:
        db2.ledger[(S.GAME_ID, mid)] = {"outcome": "no_bet"}
    loop2.tick()
    assert loop2.feed.calls == 0


def test_a_restart_remembers_the_stamps_it_already_fetched(art, monkeypatch):
    """The earlier-fetch dedupe is seeded from the loop's own in-play rows: a
    quote whose stamp an earlier process already fetched is not new."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    stamp = pd.Timestamp(w + timedelta(seconds=5))
    seen = {(S.GAME_ID, mk, book, stamp) for mk in ("h2h", "spreads")
            for book in ("draftkings", "fanduel")}
    seen |= {(S.GAME_ID, mk, "pinnacle", stamp - pd.Timedelta(seconds=3)) for mk in ("h2h", "spreads")}
    loop, db, *_ = standard(art, monkeypatch, seen=seen)
    loop.tick()
    assert db.ledger == {} and db.picks == []


def test_a_bet_that_cannot_win_beside_a_standing_one_is_declined(art, monkeypatch):
    """These prices bet NYK +2.5 (the HOME number -2.5: NYK covers on a home
    margin of 2 or less). A standing BOS -30.5 needs 31 or more: never both."""
    standing = [{"model_id": M.SPREAD_Q3, "market": "spreads", "side": "home", "line": -30.5,
                 "label": "BOS -30.5 (live)"}]
    loop, db, *_ = standard(art, monkeypatch, standing=standing)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert row["side"] == "away" and row["line"] == -2.5
    assert row["outcome"] == "declined" and "cannot both win" in row["reason"] and db.picks == []
    loop2, db2, *_ = standard(art, monkeypatch, standing=[{**standing[0], "line": -1.5, "label": "BOS -1.5 (live)"}])
    loop2.tick()
    assert db2.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet" and len(db2.picks) == 1


def test_a_paused_model_is_declined_not_bet(art, monkeypatch):
    import config
    monkeypatch.setattr(config, "PAUSED_MODELS", set(config.PAUSED_MODELS) | {M.SPREAD_Q12})
    loop, db, *_ = standard(art, monkeypatch)
    loop.tick()
    assert db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "declined" and db.picks == []


def test_dry_run_writes_nothing(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch, dry_run=True)
    res = loop.tick()
    assert res["decisions"] == 0                         # no paid call, so nothing to decide on
    assert db.ledger == {} and db.picks == [] and db.credits == [] and db.prices == [] and db.notes == []


def test_a_game_espn_lists_the_other_way_round_still_matches(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch)
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


class SqlConn:
    """Records statements; returns canned rows."""

    def __init__(self, rows=None):
        self.sql, self.params, self.rows = [], [], rows or []
        self._dirty = True                     # release_read leaves it alone

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self.params.append(params)
        rows = self.rows

        class Cur:
            def fetchall(self_):
                return rows

            def fetchone(self_):
                return rows[0] if rows else None
        return Cur()

    def rollback(self):
        pass


def test_a_skipped_row_is_never_read_as_a_decision():
    conn = SqlConn(rows=[("g1", M.SPREAD_Q12)])
    LP.decided_keys(conn, {"g1"})
    assert "outcome IN ('bet', 'no_bet', 'declined')" in conn.sql[0]
    ctx = LP.GameCtx("g1", S.GAME_DATE, 2027, "BOS", "NYK", pd.Timestamp(S.TIP))
    rule = M.RULE_BY_ID[M.SPREAD_Q12]
    c2 = SqlConn(rows=[("g1",)])
    LP.insert_ledger(c2, LP.ledger_row(ctx, rule, None, "skipped", "feed", None, {}, None, "v"))
    assert "ON CONFLICT" not in c2.sql[0]
    c3 = SqlConn(rows=[])
    assert LP.insert_ledger(c3, LP.ledger_row(ctx, rule, None, "no_bet", "x", None, {}, None, "v")) is False
    assert "ON CONFLICT (game_id, model_id) WHERE outcome IN ('bet', 'no_bet', 'declined')" in c3.sql[0]


def test_the_dedupe_memory_is_read_from_the_loops_own_rows():
    conn = SqlConn(rows=[("g1", "spreads", "fanduel", "2026-11-05T00:32:45Z")])
    got = LP.seen_from_odds(conn, {"g1"})
    assert got == {("g1", "spreads", "fanduel", pd.Timestamp("2026-11-05T00:32:45Z"))}
    assert conn.params[0][0] == "nba_live_loop" and "snapshot_type = 'in_play'" in conn.sql[0]


# ─── the operations review ────────────────────────────────────────────────────

def test_no_nba_live_destination_means_nothing_is_decided(art, monkeypatch):
    """With neither DISCORD_WEBHOOK_LIVE_NBA nor DISCORD_CHANNEL_LIVE_NBA a bet
    would never post (NBA does not fall back), so the loop decides nothing and
    says why; main() then exits 3 so the job reads failed."""
    import config
    loop, db, *_ = standard(art, monkeypatch)
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {})
    res = loop.tick()
    assert "DISCORD_WEBHOOK_LIVE_NBA" in res["blocked"] and loop.feed.calls == 0 and db.ledger == {}
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {"NBA": "123456789012345678"})
    assert loop.tick().get("blocked") is None and loop.feed.calls == 1


def test_a_play_list_behind_its_header_is_reread_then_refused(art, monkeypatch):
    """ESPN's header two points ahead of the newest play on every read after
    the first: re-read once, still behind, refused for that game."""
    loop, db, *_ = standard(art, monkeypatch, header_ahead=5)
    loop.tick()
    assert db.ledger == {} and db.skips and "header score" in db.skips[0]["reason"]
    # behind on one read only: the re-read agrees and the game is decided
    loop2, db2, *_ = standard(art, monkeypatch, header_ahead=1)
    loop2.tick()
    assert db2.ledger[(S.GAME_ID, M.SPREAD_Q12)]["outcome"] == "bet"


def test_a_stopped_play_list_under_a_running_clock_is_refused(art, monkeypatch):
    """The play list stops at the quotes' moment while ESPN's clock keeps
    moving: by the decision the newest play is older than the bound."""
    w = S.wall_of(S.build_plays(), 2, 420.0)
    loop, db, *_ = standard(art, monkeypatch, frozen_at=w + timedelta(seconds=10), clock_runs=True,
                            wait=200.0, recheck=60.0)
    loop.tick()
    assert db.ledger == {} and db.skips and "clock is running" in db.skips[0]["reason"]
    # the same stopped list with the clock stopped (a timeout): decided
    loop2, db2, *_ = standard(art, monkeypatch, frozen_at=w + timedelta(seconds=10), clock_runs=False,
                              wait=200.0, recheck=60.0)
    loop2.tick()
    assert (S.GAME_ID, M.SPREAD_Q12) in db2.ledger


def test_a_failure_building_the_pick_is_declined_and_recorded(art, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bad price row")
    monkeypatch.setattr(LP, "build_pick", boom)
    loop, db, *_ = standard(art, monkeypatch)
    loop.tick()
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert row["outcome"] == "declined" and "bad price row" in row["reason"] and db.picks == []


def test_a_failure_reading_the_fetch_is_skipped_not_raised(art, monkeypatch):
    def boom(*a, **k):
        raise ValueError("feed shape changed")
    import data.ingestors.nba_live_feed as F
    monkeypatch.setattr(F, "rows_from_events", boom)
    loop, db, *_ = standard(art, monkeypatch)
    loop.tick()
    assert db.ledger == {} and db.skips and "feed shape changed" in db.skips[0]["reason"]


def test_dry_run_makes_no_paid_call(art, monkeypatch):
    loop, db, *_ = standard(art, monkeypatch, dry_run=True)
    loop.tick()
    assert loop.feed.calls == 0


def test_a_fetch_with_no_eligible_quote_writes_a_carried_row(art, monkeypatch):
    w = S.wall_of(S.build_plays(), 2, 420.0)
    plays = S.build_plays(extra=[{"period": 2, "clock_s": 412.0, "wallclock": w + timedelta(seconds=15),
                                  "team": "A", "points": 2}])
    loop, db, *_ = standard(art, monkeypatch, plays=plays)
    loop.tick()
    assert db.ledger == {} and db.skips == [] and db.carried


def test_the_loop_beats_its_heartbeat_while_a_slate_runs(art, monkeypatch):
    import tracking.job_heartbeat as jh
    loop, db, clock, w, slot = standard(art, monkeypatch)
    beats = []
    monkeypatch.setattr(jh, "beat", lambda job, status="ok", detail="": beats.append((job, status)))
    loop.tick()
    loop.tick()                                            # inside 5 minutes: one beat
    assert beats == [("nba_live", "ok")]
    assert jh.ACTIVE_HOURS_ET["nba_live"] == (11, 23, 30)


def test_missing_offer_values_are_stored_as_null():
    import json
    ctx = LP.GameCtx("g1", S.GAME_DATE, 2027, "BOS", "NYK", pd.Timestamp(S.TIP))
    offers = pd.DataFrame([{"book": "fanduel", "side": "home", "line": float("nan"), "price": -110.0,
                            "ev": 0.06, "p_win": 0.55, "p_push": 0.0}])
    d = M.Decision("g1", M.ML_Q3, False, "x", offers=offers)
    row = LP.ledger_row(ctx, M.RULE_BY_ID[M.ML_Q3], d, "no_bet", "x", None, {}, None, "v")
    assert json.loads(row["offers"])[0]["line"] is None and "None" not in row["offers"]


def test_the_quota_floor_stops_fetching():
    from data.ingestors.nba_live_feed import LiveOddsFeed

    class R:
        def __init__(self):
            self.headers = {"x-requests-last": "2", "x-requests-remaining": "900", "x-requests-used": "4999100"}

        def raise_for_status(self):
            pass

        def json(self):
            return []

    class Sess:
        calls = 0

        def get(self, *a, **k):
            Sess.calls += 1
            return R()
    import os
    os.environ.setdefault("ODDS_API_KEY", "test-key-not-real")
    f = LiveOddsFeed(100, 200, session=Sess())
    assert f.fetch() is not None and Sess.calls == 1
    assert f.fetch() is None and Sess.calls == 1               # 900 left: under the floor


def test_a_low_share_of_the_plan_does_not_stop_fetching():
    """2026-11-07: 387,166 left of 5,000,000 (7.7%) stopped the loop after its
    first fetch under the old 15%-of-plan rule. Only the 1,000-credit line stops it."""
    from data.ingestors.nba_live_feed import LiveOddsFeed, below_floor

    class R:
        headers = {"x-requests-last": "2", "x-requests-remaining": "387166",
                   "x-requests-used": "4612834"}

        def raise_for_status(self):
            pass

        def json(self):
            return []

    class Sess:
        calls = 0

        def get(self, *a, **k):
            Sess.calls += 1
            return R()
    import os
    os.environ.setdefault("ODDS_API_KEY", "test-key-not-real")
    f = LiveOddsFeed(100, 200, session=Sess())
    assert f.fetch() is not None and f.fetch() is not None and Sess.calls == 2
    assert not below_floor(387166, 4612834) and below_floor(999, 4999001)
