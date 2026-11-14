"""The women's halftime loop, the fast way (models/ncaabw_live_loop.py; mike,
2026-11-13: "Move everything over to the fast way").

Pinned here:
  * a read at least HT_SETTLED_SEC after the half's last play is settled and
    judged on ESPN's summary read at once (no 90 s + 60 s waits); a read sooner
    than that, before the half, or after the third quarter has begun is not;
  * DraftKings' total in the read is DraftKings' own board's, stamped where
    the board first showed it; a game the board does not carry keeps the
    provider's row, and every other book's row is untouched;
  * the halftime model decides on that read exactly as on the provider's.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

import models.ncaabw_live_loop as LP
from models import ncaab_live_dk as DK
from models import ncaabw_live_ht as M
from models.ncaab_live_loop import quotes_frame
from tests import _ncaabw_live_synth as S

MODEL = M.TotalModel((1.03, 0.0, 0.32, 5.5), (33.0, 180.0, 58.0))


def ctx():
    return LP.GameCtx(S.GAME_ID, S.GAME_DATE, S.SEASON, S.HOME, S.AWAY, pd.Timestamp(S.TIP), S.EVENT_ID,
                      S.HOME_ID, S.AWAY_ID)


def test_a_read_two_minutes_into_the_break_is_settled_and_one_sooner_is_not():
    plays = S.build_plays()
    half = S.half_end(plays)
    summ = S.summary(plays, half + timedelta(minutes=5))
    assert LP.half_settled(summ, ctx(), half + timedelta(seconds=LP.HT_SETTLED_SEC + 1))
    assert not LP.half_settled(summ, ctx(), half + timedelta(seconds=LP.HT_SETTLED_SEC - 30))
    early = S.summary(plays, half - timedelta(minutes=2))
    assert not LP.half_settled(early, ctx(), half - timedelta(minutes=2) + timedelta(seconds=300))


def test_once_the_third_quarter_is_logged_the_break_is_not_settled():
    plays = S.build_plays()
    third = S.third_start(plays)
    summ = S.summary(plays, third + timedelta(minutes=3), period=3, status="STATUS_IN_PROGRESS")
    assert not LP.half_settled(summ, ctx(), third + timedelta(minutes=3))


def provider_rows(stamp):
    books = [S.book("draftkings", stamp, total=(131.5, -110, -110)), S.book("fanduel", stamp, total=(131.5, -112, -108)),
             S.book("betmgm", stamp, total=(132.5, -110, -110))]
    rows = []
    for b in books:
        for m in b["markets"]:
            o = {x["name"]: x for x in m["outcomes"]}
            rows.append({"game_id": S.GAME_ID, "market": "totals", "bookmaker": b["key"],
                         "snapshot_at": m["last_update"], "total_line": o["Over"]["point"],
                         "over_price": o["Over"]["price"], "under_price": o["Under"]["price"]})
    return rows


def test_draftkings_total_comes_from_its_board_and_the_other_books_stay_the_providers():
    plays = S.build_plays()
    half = S.half_end(plays)
    served = half + timedelta(minutes=4)
    q = quotes_frame(provider_rows(half + timedelta(minutes=1)), served)
    reads = pd.DataFrame([
        {"game_id": S.GAME_ID, "read_at": pd.Timestamp(half + timedelta(seconds=90)), "period_label": "Halftime",
         "period": 2, "clock_s": 0.0, "home_score": 40, "away_score": 30, "spread_home": None,
         "spread_home_price": None, "spread_away_price": None, "total_line": 133.5, "over_price": -105.0,
         "under_price": -115.0},
        {"game_id": S.GAME_ID, "read_at": pd.Timestamp(served - timedelta(seconds=1)), "period_label": "Halftime",
         "period": 2, "clock_s": 0.0, "home_score": 40, "away_score": 30, "spread_home": None,
         "spread_home_price": None, "spread_away_price": None, "total_line": 133.5, "over_price": -105.0,
         "under_price": -115.0}])
    dk = DK.current_quotes(reads, served, markets=("totals",))
    out = LP.overlay_dk(q, dk, served).set_index("book")
    assert out.loc["draftkings", "total_line"] == 133.5 and out.loc["draftkings", "over_price"] == -105.0
    assert out.loc["draftkings", "stamp"] == pd.Timestamp(half + timedelta(seconds=90))     # first shown
    assert out.loc["fanduel", "total_line"] == 131.5 and out.loc["betmgm", "total_line"] == 132.5
    other = DK.current_quotes(reads.assign(game_id="another"), served, markets=("totals",))
    assert LP.overlay_dk(q, other, served).set_index("book").loc["draftkings", "total_line"] == 131.5


def test_the_model_decides_on_the_overlaid_read_as_on_the_providers():
    plays = S.build_plays()
    half = S.half_end(plays)
    served = half + timedelta(minutes=4)
    st = M.states_from_rows(__import__("data.ingestors.ncaabw_pbp", fromlist=["x"]).summary_rows(
        S.summary(plays, served), espn_game_id=S.EVENT_ID, game_id=S.GAME_ID, season=S.SEASON,
        home_espn_id=S.HOME_ID, away_espn_id=S.AWAY_ID))
    q = quotes_frame(provider_rows(half + timedelta(minutes=1)), served)
    dk = pd.DataFrame([{"game_id": S.GAME_ID, "market": "totals", "book": "draftkings",
                        "stamp": pd.Timestamp(half + timedelta(seconds=90)), "spread_home": None,
                        "home_price": None, "away_price": None, "total_line": 131.5, "over_price": +100.0,
                        "under_price": -120.0}])
    r = M.read_break(LP.overlay_dk(q, dk, served), st, served, 130.0, MODEL, ("draftkings", "fanduel", "betmgm"))
    assert r.status == "decided" and r.best["book"] == "draftkings" and r.best["price"] == 100.0
