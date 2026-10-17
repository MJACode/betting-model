"""The NBA totals overs model (`nba_total_luck`): every rule it ships on.

models/nba_total_luck.py holds the rule; scripts/nba_total_luck_card.py writes
it. Each test below names the rule it pins. The replay of the lab on the
research cache is tests/test_nba_total_luck_replay.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


# ── helpers ──────────────────────────────────────────────────────────────────

def _et(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


def _season(n_games: int, opp_fg3m: int = 10, hot_fg3m: int = 18, start="2026-10-21"):
    """A synthetic season: HOM and AWY each play OT1/OT2 once a day.

    Against HOM and AWY the others make `opp_fg3m` of 40 threes; HOM and AWY
    make `hot_fg3m`. With 10 against 18 the league rate sits near 35% and
    HOM's and AWY's opponents shot 25%: their luck-adjusted defence is worse
    than the raw one, so the adjusted total is HIGHER (an over gap)."""
    games, box = [], []
    d0 = pd.Timestamp(start)
    for i in range(n_games):
        day = (d0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        for home, away in (("HOM", "OT1"), ("OT2", "AWY")):
            gid = f"NBA_{day}_{away}_{home}"
            games.append({"game_id": gid, "season": 2027, "game_date": day,
                          "home_team": home, "away_team": away})
            for team in (home, away):
                ours = team in ("HOM", "AWY")
                box.append({"game_id": gid, "team": team, "points": 110 if ours else 100,
                            "fg_att": 88, "fg3_made": hot_fg3m if ours else opp_fg3m,
                            "fg3_att": 40, "ft_made": 16, "ft_att": 20,
                            "offensive_reb": 10, "turnovers": 13})
    return pd.DataFrame(games), pd.DataFrame(box)


def _target(day="2026-11-05"):
    return pd.DataFrame([{"game_id": f"NBA_{day}_AWY_HOM", "season": 2027, "game_date": day,
                          "home_team": "HOM", "away_team": "AWY"}])


def _rows(gid, fetch, quotes):
    """odds-table rows: (book, line, over, under) at one fetch."""
    out = []
    for book, line, over, under in quotes:
        out.append({"game_id": gid, "bookmaker": book, "market": "totals",
                    "snapshot_type": "open",
                    "snapshot_at": (fetch - timedelta(seconds=30)).isoformat(),
                    "created_at": fetch.isoformat(), "total_line": line,
                    "over_price": over, "under_price": under,
                    "over_link": f"https://{book}/over", "under_link": f"https://{book}/under"})
    return pd.DataFrame(out)


@pytest.fixture(scope="module")
def art():
    return tl.load_artifact()


def _decide(art, quotes, gap, tip=None, monkeypatch=None, **kw):
    """decide() on one target whose luck gap is forced to `gap` (the offer
    mechanics, independent of the ratings)."""
    t = _target()
    tip = tip or _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    games = t.assign(tip=pd.Timestamp(tip))
    q = tl.quote_frame(_rows(t.game_id[0], fetch, quotes), games)
    proj = t.assign(gap_total=gap, gap_margin=0.0)
    monkeypatch.setattr(tl, "f4_projections", lambda targets, tb: proj)
    monkeypatch.setattr(tl, "missing_boxes", lambda *a: {})
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    empty = pd.DataFrame(columns=["game_id", "team", *tl.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team"])
    return tl.decide(t, q, empty, final, times, art, **kw)


# ── the gap: one copy, shared with the lab ───────────────────────────────────

def test_the_lab_grades_the_very_functions_the_live_model_bets():
    """RULE: the live gap equals the lab's for the same inputs. Never two copies:
    the lab imports the live model's F4 functions."""
    from scripts import nba_game2_luck as L
    for name in ("team_box", "as_of_ratings", "f4_projections", "f4_signal", "side_strength",
                 "_before"):
        assert getattr(L, name) is getattr(tl, name), f"the lab has its own {name}"
    assert (L.MIN_GAMES, L.FTA_POSS, L.BOX_COLS) == (tl.MIN_GAMES, tl.FTA_POSS, tl.BOX_COLS)


def test_cold_opponent_threes_give_an_over_gap_and_hot_ones_an_under_gap():
    """RULE: the gap is luck-adjusted minus raw projected total; opponents who
    shot cold make the adjusted total higher."""
    games, box = _season(12)
    cold = tl.f4_projections(_target(), tl.team_box(box, games))["gap_total"].iloc[0]
    games, box = _season(12, opp_fg3m=18, hot_fg3m=10)
    hot = tl.f4_projections(_target(), tl.team_box(box, games))["gap_total"].iloc[0]
    assert cold >= tl.GAP_CUT and hot <= -tl.GAP_CUT, (cold, hot)


def test_the_gap_uses_only_games_before_the_game_date():
    """RULE: ratings from games final before the game's Eastern date only (an
    afternoon game that day is left out, as in the lab)."""
    games, box = _season(12)
    t = _target("2026-11-01")                    # the 12th day of the season
    base = tl.f4_projections(t, tl.team_box(box, games))["gap_total"].iloc[0]
    g2, b2 = _season(13)                         # adds games ON 2026-11-02
    same_day = g2[g2["game_date"] == "2026-11-02"].copy()
    same_day["game_date"] = "2026-11-01"
    b_same = b2[b2["game_id"].isin(same_day["game_id"])].copy()
    # a wild night that day: HOM's and AWY's opponents go 0 for 40 from three
    b_same.loc[b_same["team"].isin(["OT1", "OT2"]), "fg3_made"] = 0
    games2 = pd.concat([games, same_day], ignore_index=True)
    box2 = pd.concat([box, b_same], ignore_index=True)
    after = tl.f4_projections(t, tl.team_box(box2, games2))["gap_total"].iloc[0]
    assert after == pytest.approx(base)
    # and the same night one day EARLIER does move it (the check can see a change)
    earlier = same_day.assign(game_date="2026-10-31")
    moved = tl.f4_projections(t, tl.team_box(box2, pd.concat([games, earlier], ignore_index=True)))
    assert moved["gap_total"].iloc[0] != pytest.approx(base)


# ── the ten-game rule ────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,priced", [(9, False), (10, True)])
def test_both_teams_need_ten_games(monkeypatch, art, n, priced):
    """RULE: CLAUDE.md section 3 -- no bet until both teams have played 10 games."""
    games, box = _season(n)
    day = (pd.Timestamp("2026-10-21") + pd.Timedelta(days=n)).strftime("%Y-%m-%d")
    t = _target(day)
    tip = _et(*map(int, day.split("-")), 19, 30)
    fetch = tip - timedelta(minutes=65)
    q = tl.quote_frame(_rows(t.game_id[0], fetch, [("pinnacle", 224.5, -105, -115),
                                                   ("draftkings", 224.5, -110, -110)]),
                       t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    bets, decisions, diag = tl.decide(t, q, box, games, times, art)
    assert diag["early_season"] == (0 if priced else 1)
    assert (len(bets) == 1) is priced, (decisions, diag)


def test_a_missing_box_score_declines_the_game(art):
    """RULE: a final game with no box score would drop out of BOTH teams'
    ratings and move the gap silently; such a game is not priced."""
    games, box = _season(12)
    gone = games["game_id"].iloc[3]
    box = box[box["game_id"] != gone]
    t = _target()
    tip = _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    q = tl.quote_frame(_rows(t.game_id[0], fetch, [("draftkings", 224.5, -110, -110)]),
                       t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    bets, decisions, diag = tl.decide(t, q, box, games, times, art)
    assert not bets and diag["box_missing"] == 1
    assert decisions[0].detail.startswith("box_missing")


# ── the offer: exactly the harness's choice ──────────────────────────────────

def test_the_offer_is_the_best_ev_under_the_market_fair_line(monkeypatch, art):
    """RULE: the over at the deciding book with the highest EV under the
    market's fair line (Pinnacle's no-vig through the empirical distribution).
    Same number, the best price wins; a better number can beat a better price."""
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -110, -110),
         ("fanduel", 224.5, -105, -115), ("betmgm", 225.5, +100, -120),
         ("williamhill_us", 223.5, -118, -102)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert len(bets) == 1
    b = bets[0]
    # the harness's own ranking of the same offers
    sig = {(2027, "totals"): tl.pricing_dist(art, 2027)}
    t = _target()
    tip = _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    frame = tl.quote_frame(_rows(t.game_id[0], fetch, q), t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    vis = H.visible(frame, times)
    neutral = H.fair_offers(H.offers(vis), H.market_fair(vis, sig))
    overs = neutral[(neutral["side"] == "over") & neutral["book"].isin(config.BEST_LINE_BOOKMAKERS)]
    best = overs.sort_values("ev", ascending=False).iloc[0]
    assert (b.book, b.line, b.price) == (best["book"], best["line"], best["price"])
    assert b.fair_ref == "pinnacle"
    assert b.ev_fair == pytest.approx(float(best["ev"]))
    assert b.ev_fair >= overs["ev"].max() - 1e-12


def test_a_tie_goes_to_the_earlier_book(monkeypatch, art):
    """RULE: equal EV -> the earlier book in config.BEST_LINE_BOOKMAKERS."""
    q = [("pinnacle", 224.5, -105, -115), ("betrivers", 224.5, -105, -115),
         ("fanduel", 224.5, -105, -115)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    order = config.BEST_LINE_BOOKMAKERS
    assert order.index("fanduel") < order.index("betrivers")
    assert bets[0].book == "fanduel"


def test_without_pinnacle_the_fair_line_is_the_deciding_books_median(monkeypatch, art):
    q = [("draftkings", 224.5, -110, -110), ("fanduel", 225.5, -105, -115),
         ("betmgm", 224.5, -105, -115)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets and bets[0].fair_ref == "consensus"


def test_pinnacle_and_bovada_are_never_the_book_taken(monkeypatch, art):
    q = [("pinnacle", 224.5, +120, -140), ("bovada", 220.5, +150, -180),
         ("draftkings", 224.5, -110, -110)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets[0].book == "draftkings"


# ── the price floor ──────────────────────────────────────────────────────────

def test_an_over_under_minus_200_is_never_taken_even_when_the_platform_floor_moves(
        monkeypatch, art):
    """RULE: -200 or better (config.min_odds_for, pinned in MODEL_MIN_ODDS),
    even when a Railway DEFAULT_MIN_ODDS override moves the harness's own
    import-time floor."""
    assert config.min_odds_for(tl.MODEL_ID) == -200
    monkeypatch.setattr(H, "PRICE_FLOOR", -1000.0)
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 219.5, -210, +170),
         ("fanduel", 224.5, -110, -110)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets and bets[0].book == "fanduel" and bets[0].price >= -200
    only = [("pinnacle", 224.5, -105, -115), ("draftkings", 219.5, -210, +170)]
    bets, decisions, _ = _decide(art, only, gap=4.0, monkeypatch=monkeypatch)
    assert not bets and decisions[0].detail == "no_offer"


# ── overs only, and the cut ──────────────────────────────────────────────────

@pytest.mark.parametrize("gap", [-6.0, -3.0, 2.99])
def test_no_bet_below_the_cut_and_never_an_under(monkeypatch, art, gap):
    """RULE: bet the over when gap >= 3; an under gap is never bet (the
    unders were mixed), and no side is taken under the cut."""
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, +110, -130),
         ("fanduel", 224.5, -130, +110)]
    bets, decisions, _ = _decide(art, q, gap=gap, monkeypatch=monkeypatch)
    assert bets == [] and decisions[0].detail.startswith("gap_below_cut")


def test_an_under_gap_never_bets_the_under_even_at_a_great_price(monkeypatch, art):
    """RULE: overs only. A gap of -6 favours the under by 6; the rule still
    bets nothing, however good the under's price."""
    q = [("pinnacle", 224.5, -105, -115), ("fanduel", 224.5, -150, +130)]
    for gap in (-6.0, 6.0):
        bets, _, _ = _decide(art, q, gap=gap, monkeypatch=monkeypatch)
        assert all(b.line == 224.5 and b.price == -150 for b in bets), bets
        assert (len(bets) == 1) is (gap > 0)


def test_at_the_cut_the_bet_is_the_over(monkeypatch, art):
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -130, +110)]
    bets, _, _ = _decide(art, q, gap=3.0, monkeypatch=monkeypatch)
    assert len(bets) == 1 and bets[0].book == "draftkings" and bets[0].price == -130


# ── the probability ──────────────────────────────────────────────────────────

def test_the_probability_is_market_fair_plus_the_walk_forward_uplift(monkeypatch, art):
    """RULE: model_probability = the market-fair P(over) at the line + the
    gap >= 3 bucket's uplift fitted on the seasons before the live one
    (2021-22..2025-26 for 2026-27: 290 wins in 508 bets against a mean fair
    0.5050)."""
    up = tl.uplift(art, 2027)
    assert up == pytest.approx((290 - sum(v["sum_p_win"] for v in art["bucket"].values())) / 508)
    assert up == pytest.approx(0.0659, abs=5e-4)
    assert tl.uplift(art, 2026) == pytest.approx(0.0679, abs=5e-4)    # fitted on 2022-2025
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -110, -110)]
    b = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)[0][0]
    assert b.p_model == pytest.approx(b.p_fair + up)
    assert b.uplift == pytest.approx(up)


def test_the_artifact_prices_each_season_from_the_seasons_before_it(art):
    """RULE: the empirical totals distribution for season S uses the
    residuals of seasons before S only (the lab's close_dist)."""
    assert tl.newest_season(art) == 2026
    r = tl.residual_frame(art)
    assert tl.pricing_dist(art, 2027).n == int((r["season"] < 2027).sum())
    assert tl.pricing_dist(art, 2026).n == int((r["season"] < 2026).sum())


def test_the_ev_floor_is_not_a_second_cut():
    """RULE (CLAUDE.md 1b): the model carries its own EV floor, and it is not a
    second cut. Written EV on the 508 graded bets: smallest -0.012 (one bet),
    next +0.030. A negative smallest is floored at 0.00 (the house rule), so
    the floor removes that one bet and none other; and every bet it lets
    through passes the publishers' edge cut (edge = EV / decimal >= 0)."""
    floor = config.min_ev_for(tl.MODEL_ID)
    assert floor == 0.0 and floor < 0.030
    assert tl.MODEL_ID in config.MODEL_OWN_EV_FLOOR
    assert config.ACTION_THRESHOLDS[tl.MODEL_ID]["min_edge"] <= floor
    assert config.ACTION_THRESHOLDS[tl.MODEL_ID]["min_prob"] == 0.0
    assert tl.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.scoring_method(tl.MODEL_ID) == "rule"


# ── timing: the last refresh pass at least 60 minutes out ────────────────────

def _refresh_jobs(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh
    monkeypatch.setattr(jh, "seed", lambda jid: None)
    monkeypatch.setattr(jh, "mark_disabled", lambda jid, *a, **k: None)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "all")
    jobs = {j.id: j for j in scheduler.build_scheduler().get_jobs()}
    return [jobs[name] for name, _, _ in tl.REFRESH_PASS_CRON]


def _fires(job, start, end):
    out, prev, t = [], None, start
    while True:
        nxt = job.trigger.get_next_fire_time(prev, t)
        if nxt is None or nxt > end:
            return out
        out.append(nxt.astimezone(UTC))
        prev, t = nxt, nxt + timedelta(seconds=1)


def test_the_model_knows_the_scheduler_s_refresh_cadence(monkeypatch):
    """RULE: 'the last pass' is computed from the cadence the scheduler really
    runs. A change to the refresh crons fails here until the model follows."""
    start, end = _et(2026, 11, 2, 0, 0), _et(2026, 11, 9, 0, 0)    # a week, across a DST change
    sched = sorted(f for job in _refresh_jobs(monkeypatch) for f in _fires(job, start, end))
    ours = tl.pass_starts(start - timedelta(seconds=1), end)
    assert ours == sched


@pytest.mark.parametrize("hh,mm", [(12, 0), (13, 0), (15, 30), (17, 0), (18, 0), (19, 0),
                                   (19, 30), (20, 0), (21, 30), (22, 0), (22, 30)])
def test_every_tip_is_decided_by_exactly_one_pass_at_60_to_120_minutes(hh, mm):
    """RULE: decide on the LAST scheduled refresh pass that starts 60+ minutes
    before tip, on the fetch it stored. The rows land seconds after the pass
    starts (measured 8-12 s), so the lead is read at the pass's start, the
    fetch's requested instant, as the lab read it at the purchase's."""
    tip = _et(2026, 11, 5, hh, mm)
    decided = []
    for start in tl.pass_starts(tip - timedelta(minutes=200), tip):
        fetch = start + timedelta(seconds=10)
        now = fetch + timedelta(seconds=90)               # the card runs after group 1
        if tl.timing(tip, fetch, now) == "decide":
            decided.append(tl.lead_minutes(tip, start))
    assert len(decided) == 1, decided
    assert 60 <= decided[0] < 120, decided


def test_a_7pm_tip_is_decided_by_the_6pm_pass_and_a_6pm_tip_by_the_417_pass():
    """The pass exactly 60 minutes out decides, though its rows land 10 s later
    (the lab's C sat at exactly 60 on 609 of 611 bets). A 6:00 pm tip has no
    pass between 5:17 (43 minutes out) and 4:17, so 4:17 decides."""
    tip = _et(2026, 11, 5, 19, 0)
    assert tl.timing(tip, _et(2026, 11, 5, 17, 17, 10), _et(2026, 11, 5, 17, 19)) == "deferred"
    assert tl.timing(tip, _et(2026, 11, 5, 18, 0, 10), _et(2026, 11, 5, 18, 2)) == "decide"
    assert tl.timing(tip, _et(2026, 11, 5, 18, 10, 10), _et(2026, 11, 5, 18, 12)) == "too_late"
    tip = _et(2026, 11, 5, 19, 30)
    assert tl.timing(tip, _et(2026, 11, 5, 18, 20, 10), _et(2026, 11, 5, 18, 22)) == "deferred"
    assert tl.timing(tip, _et(2026, 11, 5, 18, 30, 10), _et(2026, 11, 5, 18, 32)) == "decide"
    tip = _et(2026, 11, 5, 18, 0)
    assert tl.timing(tip, _et(2026, 11, 5, 15, 17, 10), _et(2026, 11, 5, 15, 19)) == "deferred"
    assert tl.timing(tip, _et(2026, 11, 5, 16, 17, 10), _et(2026, 11, 5, 16, 19)) == "decide"
    assert tl.timing(tip, _et(2026, 11, 5, 17, 17, 10), _et(2026, 11, 5, 17, 19)) == "too_late"


def test_outside_the_window_and_on_a_stale_fetch_nothing_is_decided():
    tip = _et(2026, 11, 5, 19, 30)
    assert tl.timing(tip, _et(2026, 11, 5, 16, 17, 10), _et(2026, 11, 5, 16, 19)) == "too_early"
    # the newest fetch is an hour old: this pass's odds step failed
    assert tl.timing(tip, _et(2026, 11, 5, 17, 17, 10), _et(2026, 11, 5, 18, 32)) == "stale_fetch"
    # a pass off the schedule (a boot catch-up) is its own instant
    assert tl.requested_at(_et(2026, 11, 5, 18, 37)) == _et(2026, 11, 5, 18, 37)
    assert tl.requested_at(_et(2026, 11, 5, 18, 30, 10)) == _et(2026, 11, 5, 18, 30)


# ── the card: decided once, under the lock ───────────────────────────────────

class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Answers the card's reads; records its writes."""

    def __init__(self, decided=(), bet=(), ledger_table=True):
        self.decided, self.bet, self.ledger_table = set(decided), set(bet), ledger_table
        self.sql, self.ledger, self.picks, self.commits = [], [], [], 0

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "information_schema.tables" in sql:
            return _Cur([(1,)] if self.ledger_table else [])
        if "FROM nba_total_luck_decisions" in sql:
            return _Cur([(g,) for g in self.decided])
        if "FROM picks" in sql:
            return _Cur([(g,) for g in self.bet])
        if sql.startswith("INSERT INTO nba_total_luck_decisions"):
            if params["game_id"] in self.decided:
                return _Cur([])
            self.decided.add(params["game_id"])
            self.ledger.append(params)
            return _Cur([(params["game_id"],)])
        if sql.startswith("INSERT INTO picks"):
            self.picks.append(params)
            return _Cur([(len(self.picks),)])
        return _Cur([])

    def commit(self):
        self.commits += 1


def _bet(gid="NBA_2026-11-05_AWY_HOM", price=-110.0, p_fair=0.50, book="fanduel", dk=-110.0):
    return tl.TotalLuckBet(game_id=gid, season=2027, line=224.5, price=price, book=book, gap=4.2,
                           p_fair=p_fair, p_push=0.0, ev_fair=-0.04, uplift=0.0659,
                           p_model=p_fair + 0.0659, fair_ref="pinnacle", fair_mu=224.0,
                           fetch_at=_et(2026, 11, 5, 18, 20, 10), dk_price=dk,
                           link="https://fanduel/over", dk_link="https://draftkings/over")


GAMES = {"NBA_2026-11-05_AWY_HOM": {"home": "HOM", "away": "AWY", "game_date": "2026-11-05",
                                    "season": 2027, "tip": _et(2026, 11, 5, 19, 30)}}


def test_a_decided_game_is_never_decided_again():
    """RULE (CLAUDE.md 1c): lock on first write. The second look writes nothing,
    whatever the price, and a game with a BET is never decided again."""
    from scripts import nba_total_luck_card as card
    b = _bet()
    rows, refused = card.pick_rows([b], GAMES, 1000.0)
    d = [tl.Decision(b.game_id, b.fetch_at, 4.2, 1, "bet")]
    conn = _Conn()
    assert card.publish(conn, rows, d, {b.game_id: 69.8}, refused) == (1, 1)
    better = card.pick_rows([_bet(price=+105.0)], GAMES, 1000.0)[0]
    assert card.publish(conn, better, d, {b.game_id: 59.8}, {}) == (0, 0)
    assert len(conn.picks) == 1 and conn.picks[0]["decision_odds"] == -110.0
    assert any("pg_advisory_xact_lock" in s for s in conn.sql), "published without the model lock"
    conn2 = _Conn(bet={b.game_id})
    assert card.publish(conn2, rows, d, {}, {}) == (0, 0)


def test_a_no_bet_decision_is_recorded_so_a_later_offer_cannot_bet_it():
    from scripts import nba_total_luck_card as card
    b = _bet()
    conn = _Conn()
    nobet = [tl.Decision(b.game_id, b.fetch_at, 4.2, 0, "no_offer")]
    assert card.publish(conn, [], nobet, {b.game_id: 69.8}, {}) == (0, 1)
    rows, _ = card.pick_rows([b], GAMES, 1000.0)
    assert card.publish(conn, rows, [tl.Decision(b.game_id, b.fetch_at, 4.2, 1, "bet")],
                        {}, {}) == (0, 0)
    assert conn.picks == [] and conn.ledger[0]["detail"] == "no_offer"


def test_run_card_decides_only_games_due_and_not_already_decided(monkeypatch):
    from scripts import nba_total_luck_card as card
    now = _et(2026, 11, 5, 18, 32)
    games = {
        "G_DUE": {"home": "HOM", "away": "AWY", "game_date": "2026-11-05", "season": 2027,
                  "tip": _et(2026, 11, 5, 19, 30)},
        "G_DONE": {"home": "OT1", "away": "OT2", "game_date": "2026-11-05", "season": 2027,
                   "tip": _et(2026, 11, 5, 19, 30)},
        "G_LATER": {"home": "AAA", "away": "BBB", "game_date": "2026-11-05", "season": 2027,
                    "tip": _et(2026, 11, 5, 20, 30)},
    }
    fetch = _et(2026, 11, 5, 18, 30, 10)
    conn = _Conn(decided={"G_DONE"})
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: games)
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {k: fetch for k in g})
    seen = {}

    def fake_decide(targets, quotes, box, final, times, art, **kw):
        seen["games"] = sorted(targets["game_id"])
        return [], [], dict.fromkeys(tl.DIAG_KEYS, 0)
    monkeypatch.setattr(tl, "decide", fake_decide)
    monkeypatch.setattr(card, "load_season", lambda c, s, b: (pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(card, "load_quote_rows", lambda c, g, s: pd.DataFrame(
        columns=list(tl.QUOTE_ROW_COLS)))
    out = card.run_card(do_publish=False, now=now)
    assert seen["games"] == ["G_DUE"]
    assert out["timing"]["already_decided"] == 1 and out["timing"]["deferred"] == 1


def test_a_dry_run_creates_no_ledger_and_writes_nothing(monkeypatch):
    """A dry run (run_pipeline --dry-run) writes nothing to production, not even
    the ledger's CREATE TABLE."""
    from scripts import nba_total_luck_card as card
    conn = _Conn(ledger_table=False)
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: dict(GAMES))
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {})
    card.run_card(do_publish=False, now=_et(2026, 11, 5, 18, 32))
    assert not any("CREATE" in s or s.startswith("INSERT") for s in conn.sql), conn.sql
    assert conn.commits == 0


def test_the_card_refuses_a_season_the_artifact_does_not_end_just_before(monkeypatch, art):
    from scripts import nba_total_luck_card as card
    games = {"G": {"home": "HOM", "away": "AWY", "game_date": "2027-11-05", "season": 2028,
                   "tip": _et(2027, 11, 5, 19, 30)}}
    conn = _Conn()
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: games)
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {"G": _et(2027, 11, 5, 18, 30, 10)})
    called = []
    monkeypatch.setattr(tl, "decide", lambda *a, **k: called.append(1))
    out = card.run_card(do_publish=True, now=_et(2027, 11, 5, 18, 32))
    assert out["timing"]["deferred"] == 0, "the game must be due, or this proves nothing"
    assert called == [] and out["decided"] == 0 and conn.ledger == [] and conn.picks == []


# ── the row and its label ────────────────────────────────────────────────────

def test_the_label_reads_back_against_its_side_and_line():
    """RULE: 'HOM vs AWY Over 224.5' -- the side and the stored total agree with
    the label (tracking/pick_integrity), and the row carries the price taken."""
    from scripts import nba_total_luck_card as card
    from tracking.pick_integrity import pick_problems
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    r = rows[0]
    assert r["pick_label"] == "HOM vs AWY Over 224.5" and refused == {}
    assert r["pick_side"] == "over" and r["scored_line"] == 224.5
    assert pick_problems(r["pick_label"], r["pick_side"], r["scored_line"], tl.MODEL_ID,
                         "HOM", "AWY") == []
    assert (r["decision_book"], r["decision_odds"], r["best_book"]) == ("fanduel", -110.0, "fanduel")
    assert r["model_probability"] == r["model_probability_cal"] == round(0.50 + 0.0659, 4)
    assert r["signal_type"] == "BET" and r["sport"] == "NBA"


def test_a_label_that_disagrees_with_its_line_is_refused(monkeypatch):
    from scripts import nba_total_luck_card as card
    monkeypatch.setattr(card, "pick_label", lambda b, h, a: f"{h} vs {a} Over 230.5")
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    assert rows == [] and refused == {"NBA_2026-11-05_AWY_HOM": "label_mismatch"}


def test_a_bet_under_the_ev_floor_is_refused():
    from scripts import nba_total_luck_card as card
    rows, refused = card.pick_rows([_bet(p_fair=0.40)], GAMES, 1000.0)    # EV well under 0.00
    assert rows == [] and refused["NBA_2026-11-05_AWY_HOM"].startswith("ev_below_floor")


# ── wiring ───────────────────────────────────────────────────────────────────

def test_it_settles_as_a_total():
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick(tl.MODEL_ID) == "totals"


def test_the_refresh_pass_runs_it_after_the_odds_fetch_with_a_time_limit():
    import re
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    m = re.search(r"^step nba-total-luck$", sh, re.M)
    assert m, "the card is not in the refresh pass"
    first_wait = sh.index("\npar_wait\n")
    assert sh.index("\npar odds\n") < first_wait < m.start() < sh.index("\nstep scoring\n")
    assert re.search(r"^\s*\[nba-total-luck\]=\d+$", sh, re.M), "no time limit"


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("timeout") is None,
                    reason="needs bash and coreutils timeout")
def test_a_step_past_its_time_limit_is_killed_and_recorded():
    """The shipped step() under its table: a step over its limit is killed and
    counted failed; the pass goes on."""
    sh_path = (ROOT / "scripts" / "refresh_pass.sh").as_posix()
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "fake.sh"
        fake.write_text('#!/usr/bin/env bash\ncase "$1" in slow) sleep 5;; esac\nexit 0\n')
        harness = f'''
set -uo pipefail
FAILED_STEPS=()
STEPS_TOTAL=0
declare -A STEP_TIMEOUT_S=([slow]=1 [quick]=3)
eval "$(sed -n '/^step() {{/,/^}}/p' "{sh_path}" \
        | sed 's|python run_pipeline.py --step "$1"|bash "{fake.as_posix()}" "$1"|')"
step slow
step quick
echo "TOTAL=$STEPS_TOTAL"
echo "FAILED=${{FAILED_STEPS[*]:-none}}"
'''
        r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=60)
    assert "TOTAL=2" in r.stdout, (r.stdout, r.stderr)
    assert "FAILED=slow" in r.stdout, (r.stdout, r.stderr)
    assert "killed after its 1s limit" in r.stderr
