"""The women's halftime loop (models/ncaabw_live_loop.py), driven read by read
with a fake ESPN, a fake Odds API and the database calls replaced.

Pinned here:
  * THE READ TIMES ARE THE GRADE'S SNAPSHOTS: each five-minute mark plus 37 s;
  * a read inside the break with an eligible quote decides the game once, bet
    or not; the ledger stops a restart deciding it again;
  * before the half ends nothing is written; a break that passes undecided is
    recorded once as missed;
  * ESPN is fetched after a wait and again after a recheck: a play logged
    before the read that only the second fetch carries, or a header score
    that is not the play list's, skips the game at that read;
  * no #ncaabw-live destination: nothing is decided;
  * a halftime bet that cannot win beside the game's pre-game total bet is
    declined; the price floor and the edge cap decline too;
  * the pick row: label, the total, the deciding book, P(win | no push),
    is_live; --dry-run makes no paid call.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.ncaabw_live_ht as M  # noqa: E402
import models.ncaabw_live_loop as LP  # noqa: E402
from data.ingestors.nba_live_feed import Fetch  # noqa: E402
from data.ingestors.ncaabw_live_feed import parse_scoreboard  # noqa: E402
from tests import _ncaabw_live_synth as S  # noqa: E402


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def slots_at(instant: datetime, window: float = LP.FETCH_WINDOW_SEC) -> LP.Slots:
    """Read slots whose five-minute grid has a read at `instant`."""
    floor = instant.replace(minute=instant.minute - instant.minute % 5, second=0, microsecond=0)
    return LP.Slots(offset=(floor + timedelta(minutes=5) - instant).total_seconds(), window=window,
                    cadence_min=M.CADENCE_MIN)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now = self.now + timedelta(seconds=float(s))


class FakeEspn:
    def __init__(self, plays, clock, lag=0.0, down=0, period=2, status="STATUS_HALFTIME", header_score=None):
        self.plays, self.clock, self.lag, self.down = plays, clock, float(lag), int(down)
        self.period, self.status, self.header_score = period, status, header_score
        self.calls = 0

    def scoreboard(self, d):
        self.calls += 1
        return parse_scoreboard(S.scoreboard(self.period, status=self.status)) if d == S.GAME_DATE else []

    def summary(self, eid):
        self.calls += 1
        if self.down > 0:
            self.down -= 1
            return None
        return S.summary(self.plays, self.clock.now - timedelta(seconds=self.lag), period=self.period,
                         status=self.status, header_score=self.header_score)


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
        self.credits_used += 6
        return Fetch(S.events(self.books_at(self.clock.now)), self.clock.now, 6, 10_000)


class FakeConn:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Db:
    def __init__(self, standing=None):
        self.final: dict = {}
        self.notes: list = []
        self.picks: list = []
        self.credits: list = []
        self.prices: list = []
        self.standing = standing or []
        self.spread_bet = None                 # a standing spread bet's label, when the game holds one

    def paired(self, side):
        """What models.cbb_pairs.clash says: an under beside a big favourite's spread bet."""
        if self.spread_bet and side == "under":
            return f"paired_with:{self.spread_bet} (a big favourite's spread on the same game)"
        return None

    def outcomes(self, kind):
        return [r for r in self.notes if r["outcome"] == kind]

    def install(self, monkeypatch):
        db = self

        def slate_games(conn, dates):
            return {S.EVENT_ID: LP.GameCtx(S.GAME_ID, S.GAME_DATE, S.SEASON, S.HOME, S.AWAY, pd.Timestamp(S.TIP),
                                           S.EVENT_ID, S.HOME_ID, S.AWAY_ID)}

        def load_prior(conn, ctx):
            ctx.prior = (8.0, 130.0)

        def insert_ledger(conn, row):
            if row["outcome"] not in LP.FINAL:
                db.notes.append(row)
                return True
            if row["game_id"] in db.final:
                return False
            db.final[row["game_id"]] = row
            return True

        def write_bet(conn, pick):
            db.picks.append(pick)
            return True

        monkeypatch.setattr(LP, "slate_games", slate_games)
        monkeypatch.setattr(LP, "load_prior", load_prior)
        monkeypatch.setattr(LP, "decided_games", lambda conn, ids: set(db.final))
        monkeypatch.setattr(LP, "insert_ledger", insert_ledger)
        monkeypatch.setattr(LP, "write_bet", write_bet)
        monkeypatch.setattr(LP, "standing_totals", lambda conn, gid: list(db.standing))
        monkeypatch.setattr(LP, "paired_bet", lambda conn, gid, mid, side, line: db.paired(side))
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
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {"NCAABW": "https://example.invalid/ncaabw-live"})
        return self


def books(stamp, total=(131.5, -110, -110), fd=None):
    """Three bettable books and one that is not, all quoting the total."""
    return [S.book("draftkings", stamp, total=total, spread=(-7.5, -110, -110)),
            S.book("fanduel", stamp, total=fd or total),
            S.book("betmgm", stamp, total=total),
            S.book("lowvig", stamp, total=total)]


def make_loop(art, plays, clock, books_at, slot, dry_run=False, **espn):
    fail = espn.pop("fail", 0)
    return LP.Loop(art, FakeEspn(plays, clock, **espn), FakeFeed(clock, books_at, fail=fail),
                   lambda: FakeConn(), dry_run=dry_run, wait=90.0, recheck=60.0, sleep=clock.sleep,
                   clock=clock, slate_dates=lambda: [S.GAME_DATE], read_slots=slots_at(slot),
                   resolver_factory=lambda: (lambda home, away, commence: (S.GAME_ID, False)))


def standard(art, monkeypatch, plays=None, after_half=180.0, stamp_after_half=120.0, standing=None,
             books_at=None, **kw):
    """A read three minutes into the break; every book re-posted two minutes
    into it. The half ended Iowa 40, Drake 30 against a pre-game total of 130."""
    plays = plays or S.build_plays()
    half = S.half_end(S.build_plays())
    slot = half + timedelta(seconds=after_half)
    db = Db(standing=standing).install(monkeypatch)
    clock = Clock(slot)
    bk = books_at or (lambda now: books(half + timedelta(seconds=stamp_after_half)))
    return make_loop(art, plays, clock, bk, slot, **kw), db, clock, half, slot


# ─── the read times ───────────────────────────────────────────────────────────

def test_the_reads_are_each_five_minute_mark_plus_37_seconds():
    s = LP.slots()
    assert s.offset == -37.0 and s.cadence == 5 and s.window == LP.FETCH_WINDOW_SEC
    for inst in (datetime(2026, 11, 12, 0, 50, 37, tzinfo=timezone.utc),
                 datetime(2026, 11, 12, 0, 55, 37, tzinfo=timezone.utc)):
        assert s.instant(inst) == inst and s.instant(inst + timedelta(seconds=LP.FETCH_WINDOW_SEC - 1)) == inst
        assert s.instant(inst + timedelta(seconds=LP.FETCH_WINDOW_SEC + 1)) is None
        assert s.instant(inst - timedelta(seconds=1)) is None
    assert M.CADENCE_MIN == 5 and M.FETCH_AFTER_SEC == 37.0


# ─── the decision ─────────────────────────────────────────────────────────────

def test_a_read_in_the_break_decides_and_writes_the_bet(art, monkeypatch):
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(S.half_end(S.build_plays()) + timedelta(seconds=120),
                                                     fd=(131.5, -105, -115)))
    res = loop.tick()
    assert loop.feed.calls == 1 and db.credits == [6] and db.notes == []
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "bet" and row["model_id"] == M.MODEL_ID and row["fetch_at"] == slot
    assert (row["h_pts"], row["a_pts"]) == S.HALF_SCORE and (row["mu_pre"], row["t_pre"]) == (8.0, 130.0)
    assert row["quote_at"] == half + timedelta(seconds=120) and row["ev"] >= art.cut
    assert res["decisions"] == 1 and len(db.picks) == 1
    p = db.picks[0]
    assert p["model_id"] == M.MODEL_ID and p["sport"] == "NCAABW" and p["is_live"] is True
    assert p["signal_type"] == "BET" and p["pick_side"] == "over" and p["scored_line"] == 131.5
    assert p["pick_label"] == "Drake @ Iowa Over 131.5 (live)"
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == -105.0      # the better over price
    assert p["dk_odds"] == -110.0 and p["line_book"] is None                     # DraftKings' own, same total
    assert p["inning_at_pick"] == 2 and p["score_diff_at_pick"] == 10
    assert p["model_probability"] == pytest.approx(row["p_win"], abs=1e-4) and 0.6 < p["model_probability"] < 0.8
    assert p["decision_edge"] == pytest.approx(p["model_probability"] - p["decision_implied_prob"], abs=1e-4)
    from tracking.pick_integrity import pick_problems
    assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"], p["model_id"], S.HOME, S.AWAY) == []
    # every market of the read is stored as an in-play price under the loop's source
    assert {r["market"] for r in db.prices} == {"spreads", "totals"}
    assert all(r["snapshot_type"] == "in_play" and r["source"] == "ncaabw_live_loop" for r in db.prices)
    clock.now = slot + timedelta(minutes=5)             # the next read: the game is decided, no call
    loop.tick()
    assert loop.feed.calls == 1


def test_before_the_half_ends_nothing_is_written(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch, after_half=-120.0, stamp_after_half=-150.0,
                                           status="STATUS_IN_PROGRESS")
    res = loop.tick()
    assert loop.feed.calls == 1 and res["decisions"] == 0
    assert db.final == {} and db.notes == [] and db.picks == []
    assert db.prices                                    # the read's prices are kept all the same


def test_a_decision_under_the_cut_spends_the_game(art, monkeypatch):
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(half + timedelta(seconds=120), total=(137.5, -110, -110)))
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "no_bet" and row["ev"] < art.cut and "under the cut" in row["reason"]
    assert db.picks == []
    loop.feed.books_at = lambda now: books(half + timedelta(seconds=400))        # a bet now, were it not spent
    clock.now = slot + timedelta(minutes=5)
    loop.tick()
    assert loop.feed.calls == 1 and db.picks == []


def test_quotes_from_before_the_half_carry_and_the_next_read_decides(art, monkeypatch):
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(art, monkeypatch, stamp_after_half=-40.0)
    loop.tick()
    assert db.final == {} and len(db.outcomes("carried")) == 1
    assert "0 stamped after the half ended" in db.outcomes("carried")[0]["reason"]
    loop.feed.books_at = lambda now: books(half + timedelta(seconds=400))
    clock.now = slot + timedelta(minutes=5)
    loop.tick()
    assert loop.feed.calls == 2 and db.final[S.GAME_ID]["outcome"] == "bet" and len(db.picks) == 1


def test_a_break_that_passes_undecided_is_recorded_once_as_missed(art, monkeypatch):
    plays = S.build_plays()
    third = S.third_start(plays)
    loop, db, clock, half, slot = standard(art, monkeypatch, plays=plays,
                                           after_half=(third - S.half_end(plays)).total_seconds() + 30.0,
                                           period=3, status="STATUS_IN_PROGRESS")
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "missed" and db.picks == []
    clock.now = slot + timedelta(minutes=5)
    loop.tick()
    assert loop.feed.calls == 1


# ─── failing closed ───────────────────────────────────────────────────────────

def test_espn_publishing_later_than_the_wait_fails_closed(art, monkeypatch):
    """A substitution logged 5 s before the read reaches ESPN's list only for
    the second fetch (ESPN running 100 s behind): the first picture of the
    read was incomplete, so the game is not decided on it."""
    base = S.build_plays()
    half = S.half_end(base)
    slot = half + timedelta(seconds=180)
    late = [{"period": 3, "clock_s": 600.0, "wallclock": slot - timedelta(seconds=5), "score": S.HALF_SCORE}]
    loop, db, clock, half, slot = standard(art, monkeypatch, plays=S.build_plays(extra=late), lag=100.0)
    loop.tick()
    assert db.final == {} and db.picks == []
    assert len(db.outcomes("skipped")) == 1 and "publishing late" in db.outcomes("skipped")[0]["reason"]


def test_a_header_score_that_is_not_the_play_lists_skips_the_read(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch, header_score=(42, 30))
    loop.tick()
    assert db.final == {} and db.picks == []
    assert "ESPN's header says 42-30" in db.outcomes("skipped")[0]["reason"]


def test_an_unreadable_summary_is_skipped(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch, down=99)
    loop.tick()
    assert db.final == {} and "unreadable" in db.outcomes("skipped")[0]["reason"]


def test_a_failed_odds_call_is_skipped_and_tried_again_inside_the_window(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch, fail=1)
    loop.tick()
    assert loop.feed.calls == 1 and db.final == {} and len(db.outcomes("skipped")) == 1
    clock.now = slot + timedelta(seconds=LP.RETRY_GAP_SEC - 5)       # too soon
    loop.tick()
    assert loop.feed.calls == 1
    clock.now = slot + timedelta(seconds=LP.RETRY_GAP_SEC + 1)
    loop.tick()
    assert loop.feed.calls == 2 and db.final[S.GAME_ID]["outcome"] == "bet"


def test_no_womens_live_destination_means_nothing_is_decided(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch)
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {})
    res = loop.tick()
    assert "DISCORD_CHANNEL_LIVE_NCAABW" in res["blocked"] and loop.feed.calls == 0 and db.final == {}


def test_a_restart_never_decides_a_game_the_ledger_holds(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch)
    db.final[S.GAME_ID] = {"outcome": "no_bet"}
    loop.tick()
    assert loop.feed.calls == 0 and db.picks == []


# ─── the gates on a bet ───────────────────────────────────────────────────────

def test_a_bet_that_cannot_win_beside_the_pregame_total_bet_is_declined(art, monkeypatch):
    pre = [{"model_id": "ncaabw_total_blend", "market": "totals", "side": "under", "line": 128.5,
            "label": "Drake @ Iowa Under 128.5"}]
    loop, db, clock, half, slot = standard(art, monkeypatch, standing=pre)
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "cannot both win with Drake @ Iowa Under 128.5" in row["reason"]
    assert db.picks == []


def test_a_bet_that_can_win_beside_the_pregame_total_bet_is_made(art, monkeypatch):
    pre = [{"model_id": "ncaabw_total_blend", "market": "totals", "side": "under", "line": 135.5,
            "label": "Drake @ Iowa Under 135.5"}]
    loop, db, clock, half, slot = standard(art, monkeypatch, standing=pre)       # 132 to 135 wins both
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "bet" and len(db.picks) == 1


def test_a_price_shorter_than_the_floor_is_declined(art, monkeypatch):
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(half + timedelta(seconds=120), total=(121.5, -230, +180)))
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "under the floor -200" in row["reason"] and db.picks == []


def test_an_edge_above_the_cap_is_declined_as_a_data_error(art, monkeypatch):
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(half + timedelta(seconds=120), total=(100.5, -110, -110)))
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "data-error cap 0.4" in row["reason"] and db.picks == []


def test_dry_run_makes_no_paid_call_and_writes_nothing(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch, dry_run=True)
    res = loop.tick()
    assert loop.feed.calls == 0 and db.final == {} and db.notes == [] and db.picks == [] and res["decisions"] == 0


# ─── the fast way: DraftKings' board confirms the break (mike, 2026-11-13) ────

class FakeDkBoard:
    """DraftKings' board for the game: its newest row's period and total."""

    def __init__(self, clock, label, total=(131.5, -110.0, -110.0), at=None):
        self.clock, self.label, self.total, self.at = clock, label, total, at

    def last_read(self):
        import pandas as pd
        return pd.Timestamp(self.clock.now) - pd.Timedelta(seconds=1), True

    def reads(self, ids):
        import pandas as pd
        at = self.at or (self.clock.now - timedelta(seconds=30))
        return pd.DataFrame([{"game_id": S.GAME_ID, "read_at": pd.Timestamp(at), "period_label": self.label,
                              "period": 2, "clock_s": 0.0, "home_score": 40, "away_score": 30, "spread_home": None,
                              "spread_home_price": None, "spread_away_price": None, "total_line": self.total[0],
                              "over_price": self.total[1], "under_price": self.total[2]}])


def test_draftkings_showing_the_break_decides_at_once_with_no_espn_wait(art, monkeypatch):
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(half + timedelta(seconds=120), fd=(131.5, -105, -115)))
    loop.dk = FakeDkBoard(clock, "Halftime", at=half + timedelta(seconds=120))
    loop.tick()
    assert clock.now == slot                                     # no 90 s + 60 s waits
    assert db.final[S.GAME_ID]["outcome"] == "bet"


def test_draftkings_showing_the_third_quarter_takes_the_graded_waits(art, monkeypatch):
    """ESPN still shows the break, DraftKings has the third quarter under way:
    the read is not settled, and the loop waits as graded."""
    half = S.half_end(S.build_plays())
    loop, db, clock, half, slot = standard(
        art, monkeypatch, books_at=lambda now: books(half + timedelta(seconds=120), fd=(131.5, -105, -115)))
    loop.dk = FakeDkBoard(clock, "3rd Quarter", at=half + timedelta(seconds=150))
    loop.tick()
    assert (clock.now - slot).total_seconds() >= 90.0 + 60.0


def test_no_draftkings_board_for_the_game_takes_the_graded_waits(art, monkeypatch):
    loop, db, clock, half, slot = standard(art, monkeypatch)
    loop.tick()
    assert (clock.now - slot).total_seconds() >= 90.0 + 60.0
