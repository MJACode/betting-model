"""The NBA projection model STORES and SHOWS its probability shrunk; it BETS on its own (2026-11-05).

Graded on 2023-24..2025-26, nba_prop_projection's EV claims about three times what its bets
return, in every part of its range. A picks row for a game from config.MODEL_PROB_SHRINK's
"from" date stores p' = implied + k (p - implied) at the decision price, and every edge on the
row comes from p'. An earlier game's row stores p, as it always did. Nothing that decides a bet
may move:

  * find_bets decides on the model's own p and EV against the same floors;
  * the door (scripts/nba_props_card) ranks on the raw EV, so the same bets are written;
  * Discord's "good to" price (paid and free) solves the floor on the number the bet was
    decided on, for a row from before the boundary as much as after it;
  * the action filter's edge cut (0.0) passes every bet the card writes.

The last test replays every stored graded bet of both NBA prop models through this code, and
SKIPS where the research bet lists are absent (they live on the build machine, as for
tests/test_nba_prop_projection_replay.py).
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.honest_ev as hev  # noqa: E402
import models.nba_prop_projection as pj  # noqa: E402
import scripts.nba_prop_projection_card as card  # noqa: E402
import scripts.nba_props_card as door  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.discord_notifier import _honest, price_bound  # noqa: E402

MODEL = "nba_prop_projection"
K = config.MODEL_PROB_SHRINK[MODEL]["k"]
FROM = config.MODEL_PROB_SHRINK[MODEL]["from"]          # the first shrunk game_date
BEFORE = "2026-11-04"                                   # a game the live card has already bet
UTC = timezone.utc
TIP = datetime(2026, 11, 8, 0, 0, tzinfo=UTC)
FETCH = (TIP - timedelta(minutes=55)).isoformat()


def _bet(gid="NBA_2026-11-07_GSW_LAL", prob=0.55, price=110.0, book="fanduel", dk_price=None,
         market="player_steals", side="over", line=1.5, pid="2544", night=FROM, tip=TIP):
    ev = config.expected_value(prob, price)
    return pj.ProjectionBet(
        game_id=gid, game_date=night, tip=tip.isoformat(), player="LeBron James", player_id=pid,
        market=market, side=side, line=line, book=book, price=price, prob=round(prob, 4),
        ev=round(ev, 4), mu=1.4, link="x", fetch=FETCH, book_last_update=FETCH,
        dk_price=dk_price, dk_link=None)


def _without_shrink(monkeypatch):
    monkeypatch.setattr(config, "MODEL_PROB_SHRINK", {})


def _shrink_everything(monkeypatch):
    """The research seasons are before the boundary: replay them as if they were after it."""
    monkeypatch.setattr(config, "MODEL_PROB_SHRINK", {MODEL: {"k": K, "from": "2000-01-01"}})


# ── the number ───────────────────────────────────────────────────────────────

def test_k_is_the_all_season_fit_only_this_model_is_shrunk_and_only_from_its_date():
    assert config.MODEL_PROB_SHRINK == {MODEL: {"k": 0.325, "from": "2026-11-07"}}
    # still decided on its own number: no pooled map on top
    assert MODEL in config.MODELS_ON_OWN_PROBABILITY
    assert hev.shrink_factor(MODEL, FROM) == K == hev.shrink_factor(MODEL, "2026-12-25")
    assert hev.shrink_factor(MODEL, BEFORE) is None and hev.shrink_factor(MODEL, None) is None
    assert hev.shrink_factor("nba_prop_market", FROM) is None


@pytest.mark.parametrize("price", [-200, -150, -110, 100, 110, 150, 250, 380, 1000])
@pytest.mark.parametrize("prob", [0.10, 0.35, 0.48, 0.5123, 0.62, 0.71])
def test_the_shown_probability_is_implied_plus_k_times_the_gap_and_inverts_bit_for_bit(prob, price):
    i = implied(price)
    shown = hev.shown_probability(MODEL, prob, price, FROM)
    assert shown == pytest.approx(i + K * (prob - i), abs=1e-15)
    assert config.expected_value(shown, price) == pytest.approx(K * config.expected_value(prob, price), abs=1e-12)
    # stored in an unscaled numeric and read back: the decided number comes back exactly
    stored = float(Decimal(repr(shown)))
    assert hev.decision_probability(MODEL, stored, price, FROM) == prob
    # a game before the boundary stores, and reads back, the decided number itself
    assert hev.shown_probability(MODEL, prob, price, BEFORE) == prob
    assert hev.decision_probability(MODEL, prob, price, BEFORE) == prob


def test_any_other_model_or_a_missing_price_or_date_is_never_guessed():
    assert hev.shown_probability("nba_prop_market", 0.6, 110, FROM) == 0.6
    assert hev.decision_probability("nba_prop_market", 0.6, 110, FROM) == 0.6
    assert hev.decision_probability("nba_prop_market", 0.6, None, None) == 0.6
    assert hev.shown_probability(MODEL, 0.6, None, FROM) == 0.6
    assert hev.shown_probability(MODEL, 0.6, 110, None) == 0.6
    # a shrunk model's stored number with no price or no date cannot say what was decided
    assert hev.decision_probability(MODEL, 0.5, None, FROM) is None
    assert hev.decision_probability(MODEL, 0.5, 110, None) is None


# ── the decision does not move ───────────────────────────────────────────────

def test_find_bets_decides_on_the_models_own_number_whatever_k_is(monkeypatch):
    from tests.test_nba_prop_projection import _q, _run
    quotes = [_q("draftkings", 1.5, +105, -135), _q("fanduel", 1.5, +115, -145),
              _q("draftkings", 2.5, +140, -180, market="player_threes"),
              _q("fanduel", 2.5, +150, -190, market="player_threes")]
    with_k = _run(quotes)
    monkeypatch.setattr(config, "MODEL_PROB_SHRINK", {MODEL: {"k": 0.05, "from": "2000-01-01"}})
    other_k = _run(quotes)
    _without_shrink(monkeypatch)
    without = _run(quotes)
    assert with_k == other_k == without
    assert with_k[0] and all(b.prob == 0.6 for b in with_k[0])


def test_a_row_stores_the_shrunk_number_and_the_door_key_is_the_raw_ev():
    b = _bet(prob=0.6, price=115.0, book="fanduel", dk_price=105.0)
    r = card.pick_rows([b], 1000.0)[0]
    i, i_dk = implied(115.0), implied(105.0)
    want = i + K * (0.6 - i)
    assert r["model_probability"] == r["model_probability_cal"] == pytest.approx(want, abs=1e-15)
    assert r["decision_edge"] == round(K * (0.6 - i), 4) == r["best_edge"]
    assert r["edge"] == round(want - i_dk, 4)
    assert r["_ev"] == b.ev == round(0.6 * (1 + 115 / 100) - 1, 4)
    # what the bet itself was: unchanged
    assert (r["decision_odds"], r["decision_book"], r["kelly_fraction"], r["recommended_bet"]) == \
        (115.0, "fanduel", 0.01, 10.0)


def test_a_game_before_the_boundary_or_no_shrink_stores_what_it_did(monkeypatch):
    b = _bet(prob=0.6, price=115.0, book="fanduel", dk_price=105.0, night=BEFORE)
    r = card.pick_rows([b], 1000.0)[0]
    assert r["model_probability"] == r["model_probability_cal"] == 0.6
    assert r["decision_edge"] == round(0.6 - implied(115.0), 4)
    assert r["edge"] == round(0.6 - implied(105.0), 4)
    _without_shrink(monkeypatch)
    r = card.pick_rows([_bet(prob=0.6, price=115.0)], 1000.0)[0]
    assert r["model_probability"] == 0.6 and r["decision_edge"] == round(0.6 - implied(115.0), 4)


def _night(rng: random.Random, night: str, n_games: int) -> list[dict]:
    """One night of candidates from both models, several per game, EVs from both models' ranges."""
    rows = []
    for g in range(n_games):
        gid = f"NBA_{night}_G{g:02d}"
        tip = TIP + timedelta(minutes=30 * (g // 3))
        bets = []
        for j in range(rng.randint(1, 6)):
            price = rng.choice([-200, -160, -125, -110, 100, 115, 130, 160, 210, 380])
            floor = rng.choice([0.01, 0.02, 0.04, 0.05])
            ev = floor + rng.random() * 0.4
            prob = (1 + ev) / (1 + (price / 100 if price > 0 else 100 / -price))
            bets.append(_bet(gid=gid, prob=prob, price=float(price), night=night, tip=tip,
                             pid=str(1000 + j), market=rng.choice(list(pj.MARKETS)),
                             side="under", line=0.5 + j))
        rows += card.pick_rows(bets, 1000.0)
        for j in range(rng.randint(0, 3)):
            rows.append({"game_id": gid, "model_id": "nba_prop_market", "game_date": night,
                         "player_id": str(2000 + j), "prop_market": "player_points", "pick_side": "under",
                         "scored_line": 20.5 + j, "_ev": round(rng.random() * 0.1, 4), "_tip": tip.isoformat()})
    return rows


def _replay(rows: list[dict]) -> list[tuple]:
    """The door, one look per tip time in tip order, as a night fills live."""
    looks: dict = {}
    for r in rows:
        looks.setdefault((r["game_date"], r["_tip"]), []).append(r)
    written: dict[str, int] = {}
    chosen = []
    for key in sorted(looks):
        ch, why = door.choose(looks[key], set(), dict(written))
        written[key[0]] = written.get(key[0], 0) + len(ch)
        chosen += [(r["model_id"], r["game_id"], r["player_id"], r["prop_market"], r["pick_side"],
                    r["scored_line"]) for r in ch]
        chosen += [("why", k, tuple(sorted(c.items()))) for k, c in sorted(why.items())]
    return chosen


def test_the_door_chooses_the_same_bets_with_or_without_the_shrink(monkeypatch):
    nights = [f"2026-11-{d:02d}" for d in range(7, 27)]
    assert nights[0] == FROM

    def build():
        rng = random.Random(20261105)
        return [r for n in nights for r in _night(rng, n, rng.randint(2, 12))]

    with_k = build()
    _without_shrink(monkeypatch)
    without = build()
    assert [r["_ev"] for r in with_k] == [r["_ev"] for r in without]
    shown = [r["model_probability"] for r in with_k if r["model_id"] == MODEL]
    assert all(a < b for a, b in zip(shown, [r["model_probability"] for r in without if r["model_id"] == MODEL]))
    chosen = _replay(with_k)
    assert chosen == _replay(without)
    assert sum(1 for c in chosen if c[0] == MODEL) > 20


# ── the readers that must not move ───────────────────────────────────────────

@pytest.mark.parametrize("market", list(pj.MARKETS))
@pytest.mark.parametrize("price", [-200, -130, -110, 100, 112, 125, 150, 200, 380])
@pytest.mark.parametrize("ev_over_floor", [0.0, 0.0004, 0.003, 0.02, 0.15])
def test_discords_good_to_price_is_the_one_the_raw_number_gives(market, price, ev_over_floor):
    """Including exact ties: a bound that lands exactly on a half point is broken by the
    bound's ceiling on the last bit of the float."""
    floor = config.min_ev_for(MODEL, market)
    dec = 1 + (price / 100 if price > 0 else 100 / -price)
    prob = round((1 + floor + ev_over_floor) / dec, 4)
    min_edge = config.ACTION_THRESHOLDS[MODEL]["min_edge"]
    min_odds = config.min_odds_for(MODEL)
    raw_bound = price_bound(prob, MODEL, min_edge, min_odds, price, market)
    for night in (FROM, BEFORE):
        b = _bet(prob=prob, price=float(price), market=market, side="under", night=night)
        stored = float(Decimal(repr(card.pick_rows([b], 1000.0)[0]["model_probability"])))
        assert price_bound(_honest(MODEL, stored, price, night), MODEL, min_edge, min_odds, price,
                           market) == raw_bound


def test_a_row_written_before_the_boundary_keeps_its_good_to_price():
    """"Myles Turner Under 1.5 Blocks", BetParx +110, 2026-11-04: stored raw, 0.5885. Un-shrunk as
    if it were a new row it would read 0.82 and post "good to -200"; it posts -136, as it did."""
    p, price, market = 0.5885, 110.0, "player_blocks"
    assert price_bound(p, MODEL, 0.0, -200, price, market) == -136
    assert price_bound(_honest(MODEL, p, price, BEFORE), MODEL, 0.0, -200, price, market) == -136
    assert price_bound(_honest(MODEL, p, price, FROM), MODEL, 0.0, -200, price, market) == -200
    # and a shrunk row with no date posts no bound rather than a guessed one
    assert _honest(MODEL, p, price) is None


def test_without_the_recovery_the_good_to_price_would_vanish():
    """Steals at +120, EV 0.04 over a 0.02 floor: the shrunk EV is 0.013, under the floor, so
    solving the floor on the stored number finds the posted price already too short."""
    prob, price, market = round(1.04 / 2.2, 4), 120.0, "player_steals"
    stored = hev.shown_probability(MODEL, prob, price, FROM)
    assert price_bound(prob, MODEL, 0.0, -200, price, market) == 116
    assert price_bound(stored, MODEL, 0.0, -200, price, market) is None
    assert price_bound(_honest(MODEL, stored, price, FROM), MODEL, 0.0, -200, price, market) == 116


def test_the_free_picks_good_to_price_is_the_one_the_raw_number_gives():
    """The free channel reads the probability the opening-signal capture copied from the picks
    row and bounds it at DraftKings' price. It recovers the decided number at the bet's own
    decision price for a shrunk game date, and leaves an earlier one as it is."""
    from tracking import discord_notifier as dn
    prob, price, dk = 0.4727, 120.0, 118.0

    def row(p, model=MODEL):
        return ("k1", "LeBron James Under 1.5 Steals", "NBA", dk, 0.01, "LAL", "GSW", None, None,
                "betparx", price, model, p, 0.0, -200, "under", 1.5, "player_steals", "betparx", price)

    class _Rows:
        def __init__(self, r):
            self.r = r

        def execute(self, sql, params=()):
            rows = [self.r]

            class _R:
                def fetchall(self):
                    return rows
            return _R()

    want = price_bound(prob, MODEL, 0.0, -200, dk, "player_steals")
    assert want == 116
    shrunk = row(hev.shown_probability(MODEL, prob, price, FROM))
    assert dn._free_pick_candidates(_Rows(shrunk), FROM)[0]["good_to"] == want
    assert dn._free_pick_candidates(_Rows(row(prob)), BEFORE)[0]["good_to"] == want
    # every other model's free "good to" is what it was: the stored number, no map
    other = dn._free_pick_candidates(_Rows(row(prob, "nba_prop_market")), FROM)[0]["good_to"]
    assert other == price_bound(prob, "nba_prop_market", 0.0, -200, dk, "player_steals")


def test_the_good_to_tie_case_is_exact():
    prob, price, market = 0.48, 120.0, "player_steals"
    assert config.min_ev_for(MODEL, market) == 0.02
    raw = price_bound(prob, MODEL, 0.0, -200, price, market)
    stored = hev.shown_probability(MODEL, prob, price, FROM)
    assert price_bound(_honest(MODEL, stored, price, FROM), MODEL, 0.0, -200, price, market) == raw


def test_another_models_good_to_price_ignores_the_new_arguments():
    for p, odds in ((0.55, -110), (0.6, 120)):
        assert _honest("nba_prop_market", p, odds, FROM) == _honest("nba_prop_market", p) == p


@pytest.mark.parametrize("market", list(pj.MARKETS))
@pytest.mark.parametrize("price", [-200, -110, 100, 150, 380, 1000])
def test_every_written_bet_clears_the_action_filters_edge_cut(market, price):
    """The app, Discord and push keep a BET only if COALESCE(decision_edge, edge) >= min_edge
    (0.0 for this model). The thinnest bet the card can write sits exactly on its market's
    floor; its shrunk decision edge must still be positive."""
    floor = config.min_ev_for(MODEL, market)
    dec = 1 + (price / 100 if price > 0 else 100 / -price)
    prob = (1 + floor) / dec + 1e-4
    r = card.pick_rows([_bet(prob=prob, price=float(price), market=market, side="under")], 1000.0)[0]
    assert r["decision_edge"] > 0
    assert r["decision_edge"] >= config.ACTION_THRESHOLDS[MODEL]["min_edge"]
    assert config.ACTION_THRESHOLDS[MODEL]["min_prob"] == 0.0


# ── the replay on every stored graded bet ────────────────────────────────────

RESEARCH = Path(os.environ.get("NBA_RESEARCH_DIR", "C:/Users/micha/AppData/Local/Temp/nba_rebuild"))
PROJ_BETS = RESEARCH / "proj/bets_card_arriving5.parquet"
MARKET_BETS = RESEARCH / "results/props_market_bets_sharp_ALL_under_prop_0.00.parquet"
SCHEDULE = Path(os.environ.get("NBA_SCHEDULE_PARQUET",
                               "C:/Users/micha/Documents/bm-nba/data/local/nba/nba_schedule.parquet"))


@pytest.mark.skipif(not (PROJ_BETS.exists() and MARKET_BETS.exists() and SCHEDULE.exists()),
                    reason="the graded NBA prop bet lists live on the build machine")
def test_every_stored_graded_bet_replays_to_the_same_door_and_the_same_good_to(monkeypatch):
    """Both models' graded bets, 2023-24..2025-26, loaded as the cap grade loads them
    (docs/nba_models_2026.md section 14): 66,588 projection bets, 24,572 market bets. Their game
    dates are before the boundary, so they are replayed with it moved to 2000-01-01."""
    import pandas as pd

    def dec(a):
        a = np.asarray(a, float)
        return np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))

    m = pd.read_parquet(MARKET_BETS)
    m = m[~m.market.isin(["player_double_double", "player_triple_double"]) & (m.price >= -200)]
    p = pd.read_parquet(PROJ_BETS)
    p = p[~((p.market == "player_assists") & (p.side == "over")) & p.result.isin(["W", "L", "P"])]
    s = pd.read_parquet(SCHEDULE, columns=["game_id", "commence_time"]).dropna().drop_duplicates("game_id")
    tips = dict(zip(s.game_id, pd.to_datetime(s.commence_time, utc=True, format="ISO8601")))
    far = datetime(2100, 1, 1, tzinfo=UTC)
    assert (len(p), len(m)) == (66588, 24572)
    p = p.assign(prob=(p.ev + 1) / dec(p.price), night=pd.to_datetime(p.game_date).dt.strftime("%Y-%m-%d"))
    bets = [pj.ProjectionBet(
        game_id=r.game_id, game_date=r.night, tip=tips.get(r.game_id, far).isoformat(), player="Test Player",
        player_id=str(r.player_id), market=r.market, side=r.side, line=float(r.line), book=r.book,
        price=float(r.price), prob=round(float(r.prob), 4), ev=round(float(r.ev), 4), mu=1.0, link=None,
        fetch="", book_last_update=None, dk_price=float(r.price) if r.book == "draftkings" else None,
        dk_link=None) for r in p.itertuples(index=False)]
    market_rows = [{"game_id": r.game_id, "model_id": "nba_prop_market",
                    "game_date": pd.Timestamp(r.game_date).strftime("%Y-%m-%d"), "player_id": str(r.player_id),
                    "prop_market": r.market, "pick_side": r.side, "scored_line": float(r.line),
                    "_ev": round(float(r.ev), 4), "_tip": tips.get(r.game_id, far).isoformat()}
                   for r in m.itertuples(index=False)]
    min_edge = config.ACTION_THRESHOLDS[MODEL]["min_edge"]
    min_odds = config.min_odds_for(MODEL)

    def bounds(rows):
        return [price_bound(_honest(MODEL, float(Decimal(repr(r["model_probability"]))), r["decision_odds"],
                                    r["game_date"]), MODEL, min_edge, min_odds, r["decision_odds"],
                            r["prop_market"]) for r in rows]

    with monkeypatch.context() as mp:
        mp.setattr(config, "MODEL_PROB_SHRINK", {})
        old = card.pick_rows(bets, 1000.0)
        bound_old = bounds(old)
    as_live = card.pick_rows(bets, 1000.0)              # every game before the boundary: raw
    _shrink_everything(monkeypatch)
    new = card.pick_rows(bets, 1000.0)
    assert len(new) == len(old) == len(as_live) == len(bets)
    assert [r["model_probability"] for r in as_live] == [r["model_probability"] for r in old]

    # the door: bet for bet, in order, with the same reasons for every drop, at 4 and 6 a night
    for night_cap in (4, 6):
        monkeypatch.setattr(door, "MAX_NBA_PROP_BETS_PER_NIGHT", night_cap)
        assert _replay(new + market_rows) == _replay(old + market_rows)

    # the row: the shrunk number, the raw EV as the door's key, every edge over the filter's cut
    i = np.array([implied(r["decision_odds"]) for r in new])
    raw = np.array([b.prob for b in bets])
    assert np.allclose([r["model_probability"] for r in new], i + K * (raw - i), atol=1e-15, rtol=0)
    assert [r["_ev"] for r in new] == [r["_ev"] for r in old] == [b.ev for b in bets]
    assert min(r["decision_edge"] for r in new) > 0

    # Discord's "good to": printed identically on every bet, from the stored number
    assert bounds(new) == bound_old
