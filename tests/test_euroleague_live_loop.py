"""The EuroLeague halftime loop (models/euroleague_live_loop.py), driven read
by read with a fake EuroLeague API, a fake Odds API and the database calls
replaced. The game is a real one (tests/_euroleague_live_synth.py): Panathinaikos
33, Barcelona 32 at the half, the half's last shot at 20:09:38Z.

Pinned here:
  * THE READ TIMES ARE THE GRADE'S SNAPSHOTS: each five-minute mark plus 37 s;
  * a read inside the break with an eligible quote decides the game once, bet
    or not, the ledger row FIRST; the ledger stops a restart deciding it again;
  * before the half ends, and in its first minute, no paid call is made and
    nothing is written; a break that passes undecided is recorded once as missed;
  * EuroLeague's API is read again after the call: the half must be the same,
    and a header or play-by-play score that is not the shot chart's skips the read;
  * no EuroLeague live destination: nothing is decided;
  * no Pinnacle pre-game number: the game is refused and costs no call;
  * a bet that cannot win beside the game's standing spread bet is declined;
    the price floor and the edge cap decline too;
  * the pick row: label, the HOME number, the deciding book, P(win | no push),
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

import models.euroleague_live_ht as M  # noqa: E402
import models.euroleague_live_loop as LP  # noqa: E402
from data.ingestors.nba_live_feed import Fetch  # noqa: E402
from tests import _euroleague_live_synth as S  # noqa: E402

READ = S.LAST_Q2.to_pydatetime() + timedelta(minutes=3)        # 20:12:38Z
STAMP = S.LAST_Q2 + pd.Timedelta(minutes=2)                    # every book re-hung two minutes into the break


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


def slots_at(instant: datetime, window: float = LP.FETCH_WINDOW_SEC) -> LP.Slots:
    floor = instant.replace(minute=instant.minute - instant.minute % 5, second=0, microsecond=0)
    return LP.Slots(offset=(floor + timedelta(minutes=5) - instant).total_seconds(), window=window,
                    cadence_min=M.CADENCE_MIN)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class FakeApi:
    """Answers by state: a list is served one per game read, the last repeating."""

    def __init__(self, states):
        self.states = list(states) if isinstance(states, list) else [states]
        self.calls = 0

    def game(self, season_code, game_code):
        assert (season_code, game_code) == (S.SEASON_CODE, S.GAME_CODE)
        self.calls += 1
        st = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if st is None:
            return None
        if callable(st):
            return st()
        return {"break": S.at_break, "first": S.first_half, "third": S.third_begun}[st]()


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
        self.credits_used += 3
        return Fetch(S.events(self.books_at(self.clock.now)), self.clock.now, 3, 10_000)


class FakeConn:
    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Db:
    def __init__(self, standing=None, prior=(4.5, 160.5)):
        self.final: dict = {}
        self.notes: list = []
        self.picks: list = []
        self.credits: list = []
        self.prices: list = []
        self.standing = standing or []
        self.prior = prior

    def outcomes(self, kind):
        return [r for r in self.notes if r["outcome"] == kind]

    def install(self, monkeypatch):
        db = self

        def slate_games(conn, now):
            return {S.GAME_ID: LP.GameCtx(S.GAME_ID, S.GAME_DATE, S.SEASON, S.HOME, S.AWAY, S.TIP, S.SEASON_CODE,
                                          S.GAME_CODE)}

        def load_prior(conn, ctx, first_shot):
            assert pd.Timestamp(first_shot) == S.FIRST_SHOT
            if db.prior is None:
                ctx.refused = "no coherent Pinnacle pre-game spread and total stored: no pre-game number"
            else:
                ctx.prior = db.prior

        def insert_ledger(conn, row):
            if row["outcome"] not in LP.FINAL:
                db.notes.append(row)
                return True
            if row["game_id"] in db.final:
                return False
            db.final[row["game_id"]] = row
            return True

        def write_bet(conn, pick):
            assert pick["game_id"] in db.final            # the ledger row is written first
            db.picks.append(pick)
            return True

        monkeypatch.setattr(LP, "slate_games", slate_games)
        monkeypatch.setattr(LP, "load_prior", load_prior)
        monkeypatch.setattr(LP, "decided_games", lambda conn, ids: set(db.final))
        monkeypatch.setattr(LP, "insert_ledger", insert_ledger)
        monkeypatch.setattr(LP, "write_bet", write_bet)
        monkeypatch.setattr(LP, "standing_spreads", lambda conn, gid: list(db.standing))
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
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {"EUROLEAGUE": "https://example.invalid/euroleague-live"})
        return self


def board(stamp=STAMP, dk=(-5.5, -110, -110), fd=(-5.5, -105, -115)):
    """Three bookable books and two reference books, every one quoting the spread."""
    return [S.book("draftkings", stamp, spread=dk, total=(160.5, -110, -110)),
            S.book("fanduel", stamp, spread=fd),
            S.book("betmgm", stamp, spread=dk),
            S.book("pinnacle", stamp, spread=(-5.0, -108, -108)),
            S.book("unibet", stamp, spread=(-5.5, -110, -110))]


def make(art, monkeypatch, api="break", books_at=None, at=READ, standing=None, prior=(4.5, 160.5), fail=0,
         dry_run=False):
    db = Db(standing=standing, prior=prior).install(monkeypatch)
    clock = Clock(at)
    loop = LP.Loop(art, FakeApi(api), FakeFeed(clock, books_at or (lambda now: board()), fail=fail),
                   lambda: FakeConn(), dry_run=dry_run, clock=clock, read_slots=slots_at(at),
                   resolver_factory=lambda: (lambda home, away, commence: (S.GAME_ID, False)))
    return loop, db, clock


# ─── the read times ───────────────────────────────────────────────────────────

def test_the_reads_are_each_five_minute_mark_plus_37_seconds():
    s = LP.slots()
    assert s.offset == -37.0 and s.cadence == 5 and s.window == LP.FETCH_WINDOW_SEC
    for inst in (datetime(2026, 11, 13, 20, 10, 37, tzinfo=timezone.utc),
                 datetime(2026, 11, 13, 20, 15, 37, tzinfo=timezone.utc)):
        assert s.instant(inst) == inst and s.instant(inst + timedelta(seconds=LP.FETCH_WINDOW_SEC - 1)) == inst
        assert s.instant(inst + timedelta(seconds=LP.FETCH_WINDOW_SEC + 1)) is None
        assert s.instant(inst - timedelta(seconds=1)) is None
    assert M.CADENCE_MIN == 5 and M.FETCH_AFTER_SEC == 37.0


# ─── the decision ─────────────────────────────────────────────────────────────

def test_a_read_in_the_break_decides_and_writes_the_bet(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch)
    res = loop.tick()
    assert loop.feed.calls == 1 and db.credits == [3] and db.notes == []
    assert loop.api.calls == 2                            # before the call and after it
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "bet" and row["model_id"] == M.MODEL_ID and row["fetch_at"] == READ
    assert (row["h_pts"], row["a_pts"]) == S.HALF and (row["prior_m"], row["prior_t"]) == (4.5, 160.5)
    assert row["last_q2_shot"] == S.LAST_Q2.to_pydatetime() and row["first_shot"] == S.FIRST_SHOT.to_pydatetime()
    assert row["quote_at"] == STAMP.to_pydatetime() and row["ev"] >= art.cut
    assert res["decisions"] == 1 and len(db.picks) == 1
    p = db.picks[0]
    assert p["model_id"] == M.MODEL_ID and p["sport"] == "EUROLEAGUE" and p["is_live"] is True
    assert p["signal_type"] == "BET" and p["pick_side"] == "away"
    assert p["scored_line"] == -5.5                       # the HOME number taken (CLAUDE.md 4)
    assert p["pick_label"] == "BAR +5.5 (live)"
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -110.0   # FanDuel's away is -115
    assert p["dk_odds"] == -110.0 and p["line_book"] is None
    assert p["inning_at_pick"] == 2 and p["score_diff_at_pick"] == 1
    assert p["model_probability"] == pytest.approx(row["p_win"], abs=1e-4) and 0.55 < p["model_probability"] < 0.65
    assert p["decision_edge"] == pytest.approx(p["model_probability"] - p["decision_implied_prob"], abs=1e-4)
    from tracking.pick_integrity import pick_problems
    assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"], p["model_id"], S.HOME, S.AWAY) == []
    # every market of the read is stored as an in-play price under the loop's source
    assert {r["market"] for r in db.prices} == {"spreads", "totals"}
    assert all(r["snapshot_type"] == "in_play" and r["source"] == "euroleague_live_loop" for r in db.prices)
    clock.now = READ + timedelta(minutes=5)             # the next read: the game is decided, no call
    loop.slots = slots_at(clock.now)
    loop.tick()
    assert loop.feed.calls == 1


def test_before_the_half_ends_nothing_is_written(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch, api="first")
    loop.tick()
    assert loop.feed.calls == 0 and db.final == {} and db.notes == [] and db.picks == []


def test_in_the_halfs_first_minute_no_call_is_made(art, monkeypatch):
    at = S.LAST_Q2.to_pydatetime() + timedelta(seconds=50)
    loop, db, _ = make(art, monkeypatch, at=at)
    loop.tick()
    assert loop.feed.calls == 0 and db.final == {} and db.notes == []


def test_a_decision_under_the_cut_spends_the_game(art, monkeypatch):
    flat = lambda now: board(dk=(-3.5, -110, -110), fd=(-3.5, -110, -110))   # noqa: E731
    loop, db, clock = make(art, monkeypatch, books_at=flat)
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "no_bet" and row["ev"] < art.cut and db.picks == []
    clock.now = READ + timedelta(minutes=5)
    loop.slots = slots_at(clock.now)
    loop.tick()
    assert loop.feed.calls == 1                           # spent: never decided again


def test_quotes_not_re_hung_carry_and_the_next_read_decides(art, monkeypatch):
    stale = S.LAST_Q2 - pd.Timedelta(seconds=40)

    def books_at(now):
        return board(stamp=stale) if now < READ + timedelta(minutes=1) else board()
    loop, db, clock = make(art, monkeypatch, books_at=books_at)
    loop.tick()
    assert [r["outcome"] for r in db.notes] == ["carried"] and S.GAME_ID not in db.final
    assert "re-hung after the half's last shot" in db.notes[0]["reason"]
    clock.now = READ + timedelta(minutes=5)
    loop.slots = slots_at(clock.now)
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "bet" and loop.feed.calls == 2


def test_a_break_that_passes_undecided_is_recorded_once_as_missed(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch, api="third")
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "missed" and loop.feed.calls == 0
    clock.now = READ + timedelta(minutes=5)
    loop.slots = slots_at(clock.now)
    loop.tick()
    assert loop.api.calls == 1                            # decided: EuroLeague's API is not read again


def test_the_third_quarter_beginning_between_the_two_reads_is_missed_not_bet(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch, api=["break", lambda: S.third_begun(with_shot=False)])
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "missed" and db.picks == [] and loop.feed.calls == 1


def test_a_header_score_that_is_not_the_shot_charts_skips_the_read(art, monkeypatch):
    def bad():
        a = S.at_break()
        a["header"]["ScoreQuarter2B"] = 30
        return a
    loop, db, _ = make(art, monkeypatch, api=bad)
    loop.tick()
    assert [r["outcome"] for r in db.notes] == ["skipped"] and "header says 33-30" in db.notes[0]["reason"]
    assert loop.feed.calls == 0 and db.final == {}


def test_a_half_that_changes_between_the_two_reads_is_skipped(art, monkeypatch):
    def later_free_throw():
        a = S.at_break()
        r = dict(max(a["points"]["Rows"], key=lambda x: x["UTC"]))
        r["UTC"], r["NUM_ANOT"] = "20261113201100", 9999
        a["points"]["Rows"].append(r)
        return a
    loop, db, _ = make(art, monkeypatch, api=["break", later_free_throw])
    loop.tick()
    assert [r["outcome"] for r in db.notes] == ["skipped"] and "changed between the two reads" in db.notes[0]["reason"]
    assert db.final == {} and db.picks == []


def test_an_api_that_does_not_answer_is_skipped_and_tried_again_inside_the_window(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch, api=[None, "break"])
    loop.tick()
    assert [r["outcome"] for r in db.notes] == ["skipped"] and loop.feed.calls == 0
    clock.now = READ + timedelta(seconds=LP.RETRY_GAP_SEC + 1)
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "bet" and loop.feed.calls == 1


def test_a_failed_odds_call_is_skipped_and_tried_again_inside_the_window(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch, fail=1)
    loop.tick()
    assert [r["outcome"] for r in db.notes] == ["skipped"] and db.final == {}
    clock.now = READ + timedelta(seconds=LP.RETRY_GAP_SEC + 1)
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "bet" and loop.feed.calls == 2


def test_no_euroleague_live_destination_means_nothing_is_decided(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch)
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {}, raising=False)
    res = loop.tick()
    assert "DISCORD_CHANNEL_LIVE_EUROLEAGUE" in res["blocked"] and loop.feed.calls == 0 and loop.api.calls == 0
    assert db.final == {} and db.notes == []


def test_no_pinnacle_prior_refuses_the_game_and_costs_no_call(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch, prior=None)
    loop.tick()
    assert loop.feed.calls == 0 and db.final == {}
    assert [r["outcome"] for r in db.notes] == ["skipped"] and "Pinnacle" in db.notes[0]["reason"]
    clock.now = READ + timedelta(minutes=5)
    loop.slots = slots_at(clock.now)
    loop.tick()
    assert loop.api.calls == 1                            # refused: never read again


def test_a_restart_never_decides_a_game_the_ledger_holds(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch)
    db.final[S.GAME_ID] = {"outcome": "no_bet"}
    loop.tick()
    assert loop.feed.calls == 0 and loop.api.calls == 0 and db.picks == []


def test_a_bet_that_cannot_win_beside_the_standing_spread_bet_is_declined(art, monkeypatch):
    standing = [{"model_id": M.MODEL_ID, "market": "spreads", "side": "home", "line": -8.5, "label": "PAN -8.5 (live)"}]
    loop, db, _ = make(art, monkeypatch, standing=standing)
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "cannot both win" in row["reason"] and db.picks == []


def test_a_price_shorter_than_the_floor_is_declined(art, monkeypatch):
    import config
    monkeypatch.setitem(config.MODEL_MIN_ODDS, M.MODEL_ID, -105)
    loop, db, _ = make(art, monkeypatch)
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "under the floor" in row["reason"] and db.picks == []


def test_an_edge_above_the_cap_is_declined_as_a_data_error(art, monkeypatch):
    import models.euroleague_quote_bounds as qb
    monkeypatch.setitem(qb.EDGE_CAP, M.MODEL_ID, 0.01)
    loop, db, _ = make(art, monkeypatch)
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["outcome"] == "declined" and "data-error cap" in row["reason"] and db.picks == []


def test_dry_run_makes_no_paid_call_and_writes_nothing(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch, dry_run=True)
    loop.tick()
    assert loop.feed.calls == 0 and db.final == {} and db.notes == [] and db.picks == []


def test_no_game_in_progress_is_idle(art, monkeypatch):
    loop, db, clock = make(art, monkeypatch, at=S.TIP.to_pydatetime() - timedelta(minutes=10))
    assert loop.tick() == {"live": 0}
    clock.now = S.TIP.to_pydatetime() + timedelta(minutes=LP.IN_PROGRESS_MIN + 1)
    assert loop.tick() == {"live": 0}


def test_the_loop_reads_the_api_only_near_the_half(art, monkeypatch):
    loop, db, _ = make(art, monkeypatch, at=S.TIP.to_pydatetime() + timedelta(minutes=20, seconds=37))
    loop.tick()
    assert loop.api.calls == 0 and loop.feed.calls == 0


def test_the_scheduler_runs_it_on_pollers_in_euroleague_hours():
    import scheduler
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert "euroleague_live" in scheduler._POLLER_JOBS
    assert 'CronTrigger(hour="9-17", minute="8-59/10", timezone=TIMEZONE)' in src
    assert '[sys.executable, "-m", "models.euroleague_live_loop"]' in src
    assert 'os.environ.get("RUN_EUROLEAGUE_LIVE", "1")' in src
    from tracking.job_heartbeat import ACTIVE_HOURS_ET, MAX_SILENCE
    assert ACTIVE_HOURS_ET["euroleague_live"] == (9, 17, 30) and MAX_SILENCE["euroleague_live"] >= 910
