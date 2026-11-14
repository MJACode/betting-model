"""The NCAAF moneyline model's decision-timing replay
(scripts/ncaaf_moneyline_timing.py).

mike, 2026-11-14: when a model decides is a per-model parameter, chosen by
out-of-sample expected units (CLAUDE.md §1c: the lock is on a BET, not a
game). The replay must run the card's own decision at each instant, move with
the hour it is asked for, lock a check-until-it-bets timing at its first BET,
and divide its significance over every timing it searched. The check against
the research's 311 bets runs on the real extracts (the script's --check-bets).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.ncaaf_moneyline_market as mm  # noqa: E402
import scripts.ncaaf_moneyline_timing as tm  # noqa: E402
from tests.test_ncaaf_moneyline_market import (  # noqa: E402
    BOOKS4, _decide, _moneylines, _rows, _spreads)

DAY = "2026-11-14"
KICK = pd.Timestamp(f"{DAY} 20:30", tz="UTC")


@pytest.fixture(scope="module")
def art():
    return mm.load_artifact()


def _pull(quotes, stamped_at):
    """Rows as tm.pull_rows hands them to the panel: no instant, sorted by ts."""
    r = _rows(quotes, instant=pd.Timestamp(stamped_at, tz="UTC"), tip=KICK)
    return r.drop(columns=["instant", "link1", "link2"]).sort_values("ts").reset_index(drop=True)


def _games():
    return pd.DataFrame({"game_id": ["g"], "season": [2026], "et_date": [DAY], "kick": [KICK]})


def _tables(art):
    return {2026: (art["table"], art["offset"], 0)}


def test_the_panel_at_14z_makes_the_cards_own_decision(art):
    ml, sp = _moneylines(art), _spreads()
    card = _decide(art, ml, sp)[0]
    assert card.status == "bets"
    p = tm.panel((_pull(ml, f"{DAY} 14:00"), _pull(sp, f"{DAY} 14:00"), _games()),
                 _tables(art), hours=[14], log_every=0)
    assert len(p) == 1
    r = p.iloc[0]
    assert (r.status, r.bookmaker, r.side, r.price) == (
        card.status, card.best["bookmaker"], card.best["side"], card.best["price"])
    assert r.edge == pytest.approx(card.best["edge"], abs=0)
    assert r.ml_books == len(BOOKS4)


def test_the_hour_moves_the_read(art):
    """Quotes stamped before 14:00 UTC are outside an 18:00 check's 60-minute
    window: that check has no quote, so the game is not in its scope."""
    ml, sp = _moneylines(art), _spreads()
    rows = (_pull(ml, f"{DAY} 14:00"), _pull(sp, f"{DAY} 14:00"), _games())
    assert len(tm.panel(rows, _tables(art), hours=[14], log_every=0)) == 1
    assert len(tm.panel(rows, _tables(art), hours=[18], log_every=0)) == 0


def test_a_check_within_five_minutes_of_kickoff_is_never_made(art):
    ml, sp = _moneylines(art), _spreads()
    late = (_pull(ml, f"{DAY} 20:00"), _pull(sp, f"{DAY} 20:00"), _games())
    assert len(tm.panel(late, _tables(art), hours=[20], log_every=0)) == 1
    games = _games().assign(kick=pd.Timestamp(f"{DAY} 20:04", tz="UTC"))
    assert len(tm.panel((late[0], late[1], games), _tables(art), hours=[20], log_every=0)) == 0


def _panel(rows):
    return pd.DataFrame([{"game_id": g, "season": 2026, "instant": pd.Timestamp(t, tz="UTC"),
                          "status": s, "price": pr} for g, t, s, pr in rows])


def test_first_bet_locks_at_the_first_bet_and_a_game_that_never_bets_is_not_bet():
    p = _panel([("g1", f"{DAY} 10:00", "below_cut", 140.0),
                ("g1", f"{DAY} 12:00", "bets", 150.0),
                ("g1", f"{DAY} 15:00", "bets", 130.0),
                ("g2", f"{DAY} 11:00", "below_cut", 120.0),
                ("g2", f"{DAY} 16:00", "below_cut", 125.0)])
    games = pd.DataFrame({"game_id": ["g1", "g2"], "et_date": [DAY, DAY]})
    d = tm.timing_rows(p, games, "first_bet").set_index("game_id")
    assert d.loc["g1", "instant"] == pd.Timestamp(f"{DAY} 12:00", tz="UTC")
    assert d.loc["g1", "price"] == 150.0
    assert d.loc["g2", "status"] == "below_cut"


def test_a_fixed_hour_is_that_hour_on_the_games_eastern_date():
    p = _panel([("g", "2026-11-13 14:00", "bets", 150.0),
                ("g", f"{DAY} 14:00", "below_cut", 140.0),
                ("g", f"{DAY} 19:00", "bets", 160.0)])
    games = pd.DataFrame({"game_id": ["g"], "et_date": [DAY]})
    h14 = tm.timing_rows(p, games, "h14")
    assert list(h14["status"]) == ["below_cut"]
    assert list(tm.timing_rows(p, games, "last_read")["price"]) == [160.0]
    assert tm.timing_rows(p, games, "h09").empty


def test_bh_fdr_divides_by_every_timing_searched():
    p = {"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}
    assert tm.bh(p, 0.10) == {"a", "b", "c"}
    # The same p-values among 26 searched timings: only the smallest survives.
    p26 = {**p, **{f"x{i}": 0.9 for i in range(22)}}
    assert tm.bh(p26, 0.10) == {"a"}
    assert len(tm.CANDIDATES) == 26


def test_clv_is_the_bet_price_against_pinnacles_no_vig_close():
    b = pd.DataFrame({"game_id": ["g", "h"], "side": ["home", "home"], "price": [150.0, 110.0]})
    pin = pd.DataFrame({"pin_home": [130.0, 130.0], "pin_away": [-150.0, -150.0],
                        "pin_ts": [KICK, KICK]}, index=pd.Index(["g", "h"], name="game_id"))
    c = tm.with_clv(b, pin).set_index("game_id")["clv_pct"]
    assert c["g"] > 0 > c["h"]


def test_the_panel_is_the_same_split_over_processes(art):
    """Each instant reads only its own window, so splitting the hours across
    worker processes cannot change a decision."""
    ml, sp = _moneylines(art), _spreads()
    mls = pd.concat([_pull(ml, f"{DAY} {h}:00") for h in ("14", "16", "18")], ignore_index=True)
    sps = pd.concat([_pull(sp, f"{DAY} {h}:00") for h in ("14", "16", "18")], ignore_index=True)
    mls = mls.sort_values("ts", kind="mergesort").reset_index(drop=True)
    sps = sps.sort_values("ts", kind="mergesort").reset_index(drop=True)
    rows = (mls, sps, _games())
    one = tm.panel(rows, _tables(art), log_every=0, workers=1)
    two = tm.panel(rows, _tables(art), log_every=0, workers=2)
    assert len(one) >= 3
    pd.testing.assert_frame_equal(one, two)


def test_the_replay_refuses_what_the_card_refuses_after_deciding():
    """The card writes a decided bet as a BET only above its price floor and
    its EV floor (scripts/ncaaf_moneyline_card.py); so does the replay."""
    import config
    floor = config.min_ev_for(mm.MODEL_ID)
    b = pd.DataFrame({"price": [150.0, 150.0, -250.0],
                      "prob": [(1 + floor + 0.01) / 2.5, (1 + floor - 0.01) / 2.5, 0.9]})
    assert list(tm.card_gates(b)) == [True, False, False]
