"""nhl_prop_saves / nhl_prop_shots_on_goal / nhl_prop_assists: the row scored tonight is a
training row, the card bets the rule the backtest graded, and a pick settles as that bet would.

The evidence for all three is a walk-forward backtest (scripts/nhl_prop_backtest.py).
It only transfers to production if (a) tonight's inputs are built the way the
backtested rows' were, (b) the card places the bet the backtest placed -- unders
only, the best price in ONE fetch, one bet a player -- and (c) settlement voids
what the backtest never counted (a goalie who did not start).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
import models.nhl_props as P
import scripts.nhl_prop_backtest as bt
from data.db_setup import SCHEMA_SQL
from scripts import nhl_props_card as card
from tracking import paper_tracker as pt
from tracking.pick_integrity import pick_problems

ROOT = Path(__file__).resolve().parents[1]
GAME = "NHL_2026-10-01_BOS_NYR"
GAMES = {GAME: {"home": "NYR", "away": "BOS", "commence_time": "2026-10-01T23:00:00Z"}}


def _log(n_games: int = 30) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Two teams playing each other every other day: two skaters and a starter a side, plus one relief appearance."""
    rng = np.random.default_rng(7)
    sk, go, tm = [], [], []
    for g in range(n_games):
        date = (pd.Timestamp("2025-10-10") + pd.Timedelta(days=2 * g)).strftime("%Y-%m-%d")
        gid = 2025020000 + g
        for team, opp, home in (("BOS", "NYR", g % 2), ("NYR", "BOS", 1 - g % 2)):
            tm.append({"nhl_game_id": gid, "game_id": f"NHL_{date}_X", "team": team, "opponent": opp,
                       "game_date": date, "shots_for": int(rng.integers(20, 40)),
                       "shots_against": int(rng.integers(20, 40)), "goals_against": int(rng.integers(0, 6)),
                       "times_shorthanded": int(rng.integers(0, 6))})
            base = 1 if team == "BOS" else 3
            for k in range(2):
                a = int(rng.integers(0, 3))
                sk.append({"nhl_game_id": gid, "player_id": base + k, "player_name": f"Skater {base + k}",
                           "position": "D" if k == 0 else "C", "season": 2026, "game_date": date,
                           "team": team, "opponent": opp, "is_home": home,
                           "shots": int(rng.integers(0, 6)), "shot_attempts": int(rng.integers(0, 10)),
                           "assists": a, "points": a + int(rng.integers(0, 2)),
                           "toi_seconds": int(rng.integers(600, 1500)), "pp_toi_seconds": int(rng.integers(0, 200))})
            go.append({"nhl_game_id": gid, "player_id": 30 + base, "player_name": f"Goalie {30 + base}",
                       "season": 2026, "game_date": date, "team": team, "opponent": opp, "is_home": home,
                       "started": 1, "saves": int(rng.integers(15, 40)), "shots_against": int(rng.integers(18, 44))})
            if g == 5:        # the backup mops up one night: a row, with saves, that is NOT a start
                go.append({"nhl_game_id": gid, "player_id": 30 + base, "player_name": "relief",
                           "season": 2026, "game_date": date, "team": team, "opponent": opp, "is_home": home,
                           "started": 0, "saves": 99, "shots_against": 99})
    return pd.DataFrame(sk), pd.DataFrame(go), pd.DataFrame(tm)


def _players(spec: P.Spec) -> pd.DataFrame:
    sk, go, _ = _log()
    return go if spec.kind == "goalie" else sk


@pytest.mark.parametrize("spec", list(P.SPECS.values()), ids=lambda s: s.model_id)
class TestTonightsRowIsATrainingRow:
    def test_an_upcoming_row_carries_exactly_what_the_played_row_carried(self, spec):
        """Take the last game out of the log, hand it back as an upcoming game,
        and every input must equal what the full log gave that game."""
        pl, tm = _players(spec), _log()[2]
        last = pl.nhl_game_id.max()
        played = P.build_frame(spec, pl, tm)
        feats = list(spec.features)
        want = played[played.nhl_game_id == last].set_index("player_id")[feats]

        held = pl[(pl.nhl_game_id == last) & (pl.get("started", 1) == 1)]
        keep = [c for c in ("player_id", "player_name", "position", "season", "game_date", "team",
                            "opponent", "is_home") if c in held.columns]
        up = held[keep].assign(game_id="NHL_tonight")
        frame = P.build_frame(spec, pl[pl.nhl_game_id != last], tm[tm.nhl_game_id != last], up)
        got = frame[frame.upcoming].set_index("player_id")[feats]

        assert len(got) == len(want) > 0
        pd.testing.assert_frame_equal(got.sort_index().astype(float), want.sort_index().astype(float),
                                      check_names=False)
        assert set(frame[frame.upcoming].game_id) == {"NHL_tonight"}

    def test_a_games_own_result_is_not_one_of_its_inputs(self, spec):
        """Rewrite the last game's numbers: that game's inputs must not move."""
        pl, tm = _players(spec), _log()[2]
        last = pl.nhl_game_id.max()
        feats = list(spec.features)
        before = P.build_frame(spec, pl, tm)
        loud = pl.copy()
        for c in ("shots", "shot_attempts", "assists", "points", "saves", "shots_against", "toi_seconds"):
            if c in loud.columns:
                loud.loc[loud.nhl_game_id == last, c] = 500
        loud_tm = tm.copy()
        for c in ("shots_for", "shots_against", "goals_against", "times_shorthanded"):
            loud_tm.loc[loud_tm.nhl_game_id == last, c] = 500
        after = P.build_frame(spec, loud, loud_tm)
        a = before[before.nhl_game_id == last].sort_values("player_id")[feats].astype(float).values
        b = after[after.nhl_game_id == last].sort_values("player_id")[feats].astype(float).values
        np.testing.assert_allclose(a, b)

    def test_ten_career_games_not_ten_this_season(self, spec):
        """MIN_GAMES counts the player's rows in the log, across seasons: a
        within-season count would be an early-season hold nobody asked for."""
        pl, tm = _players(spec), _log()[2]
        nxt = pl[pl.nhl_game_id == pl.nhl_game_id.max()].copy()
        nxt = nxt[nxt.get("started", 1) == 1] if "started" in nxt.columns else nxt
        keep = [c for c in ("player_id", "player_name", "position", "team", "opponent", "is_home") if c in nxt.columns]
        up = nxt[keep].assign(season=2027, game_date="2026-10-01", game_id="NHL_opener")
        frame = P.build_frame(spec, pl, tm, up)
        opener = frame[frame.upcoming]
        assert (opener.gp >= P.MIN_GAMES).all()
        assert len(P.usable(spec, opener)) == len(opener) > 0


class TestTheGoalieFrame:
    def test_a_relief_appearance_is_neither_history_nor_a_row(self):
        sk, go, tm = _log()
        f = P.build_goalie_frame(go, tm)
        assert (f.saves != 99).all()
        assert f.groupby("player_id").size().eq(30).all()            # 30 starts, the relief row gone
        assert f.saves_l.max() < 45                                  # 99 never entered a weighted mean

    def test_a_priced_goalie_is_scored_as_a_starter(self):
        sk, go, tm = _log()
        up = pd.DataFrame([{"player_id": 31, "player_name": "Goalie 31", "season": 2027, "game_date": "2026-10-01",
                            "team": "BOS", "opponent": "NYR", "is_home": 0, "game_id": GAME}])
        f = P.build_goalie_frame(go, tm, up)
        row = f[f.upcoming]
        assert len(row) == 1 and int(row.started.iloc[0]) == 1 and row[list(P.SAVES.features)].notna().all(axis=None)


class TestTheDistribution:
    def test_no_excess_variance_is_exactly_poisson(self):
        from scipy.stats import poisson
        assert float(P.p_over(2.2, 2.5)) == pytest.approx(float(poisson.sf(2, 2.2)))
        assert float(P.p_over(2.2, 2.5, 0.0)) == pytest.approx(float(P.p_over(2.2, 2.5, 1e-12)))

    def test_wider_counts_pull_a_confident_under_toward_even(self):
        tight, wide = 1 - float(P.p_over(23.0, 26.5)), 1 - float(P.p_over(23.0, 26.5, 0.033))
        assert tight > wide > 0.5

    def test_the_excess_is_measured_and_is_zero_for_poisson_counts(self):
        rng = np.random.default_rng(3)
        mu = np.full(20000, 24.0)
        assert P.excess_variance(rng.poisson(mu), mu) < 0.003
        wide = rng.negative_binomial(1 / 0.03, (1 / 0.03) / (1 / 0.03 + mu))
        assert 0.02 < P.excess_variance(wide, mu) < 0.04

    def test_saves_is_the_one_market_that_uses_it(self):
        assert P.SAVES.overdispersed and not P.SHOTS.overdispersed and not P.ASSISTS.overdispersed


def _quotes(rows: list[tuple]) -> pd.DataFrame:
    """(player_id, book, line, over, under)"""
    return pd.DataFrame([{"game_id": GAME, "player": f"Skater {pid}", "player_id": pid, "book": book,
                          "line": line, "over": over, "under": under,
                          "over_link": f"{book}/o", "under_link": f"{book}/u"}
                         for pid, book, line, over, under in rows])


def _mus(pairs: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame([{"player_id": pid, "game_id": GAME, "mu": mu} for pid, mu in pairs])


class TestTheCard:
    def test_it_bets_the_under_at_the_best_book(self):
        """Same line, three books: the pick is the best under price, and says where."""
        q = _quotes([(1, "draftkings", 2.5, -140, 105), (1, "betmgm", 2.5, -150, 120), (1, "hardrockbet", 2.5, -135, 100)])
        rows = card.pick_rows(P.SHOTS, _mus([(1, 1.6)]), q, GAMES, "2026-10-01", 1000.0, 0.0)
        assert len(rows) == 1
        r = rows[0]
        assert (r["decision_book"], r["decision_odds"], r["pick_side"], r["scored_line"]) == (
            "betmgm", 120.0, "under", 2.5)
        assert r["pick_label"] == "Skater 1 Under 2.5 Shots on Goal"
        assert r["player_id"] == "1" and r["prop_market"] == "player_shots_on_goal"
        # DraftKings quoted the same line: its columns carry ITS number, not BetMGM's.
        assert (r["dk_odds"], r["dk_bet_link"], r["line_book"]) == (105.0, "draftkings/u", None)
        assert r["dk_implied_prob"] == round(P.implied(105), 4)
        assert r["edge"] == round(r["model_probability"] - P.implied(105), 4) < r["decision_edge"]
        # and the better price travels with its own betslip link
        assert (r["best_book"], r["best_odds"], r["best_bet_link"]) == ("betmgm", 120.0, "betmgm/u")

    def test_the_same_price_at_two_books_names_the_earlier_one(self):
        q = _quotes([(1, "betmgm", 2.5, -150, 120), (1, "draftkings", 2.5, -150, 120)])
        r = card.pick_rows(P.SHOTS, _mus([(1, 1.6)]), q, GAMES, "2026-10-01", 1000.0, 0.0)[0]
        assert r["decision_book"] == "draftkings" and r["dk_bet_link"] == "draftkings/u"
        assert (r["dk_odds"], r["decision_odds"], r["best_book"], r["best_bet_link"]) == (120.0, 120.0, None, None)

    def test_a_higher_line_can_beat_a_better_price(self):
        """Books hang different numbers. Under 3.5 at -125 is the better bet than under 2.5 at +100."""
        q = _quotes([(1, "draftkings", 2.5, -130, 100), (1, "hardrockbet", 3.5, 100, -125)])
        r = card.pick_rows(P.SHOTS, _mus([(1, 2.2)]), q, GAMES, "2026-10-01", 1000.0, 0.0)[0]
        assert (r["decision_book"], r["scored_line"], r["pick_label"]) == (
            "hardrockbet", 3.5, "Skater 1 Under 3.5 Shots on Goal")
        # DraftKings hangs 2.5, not 3.5: it has no price for THIS bet, so its
        # columns are empty and the row says whose line it is. Its 2.5 price in
        # dk_odds would put a different bet's number on the betslip.
        assert (r["dk_odds"], r["dk_bet_link"], r["line_book"]) == (None, None, "hardrockbet")
        assert (r["dk_implied_prob"], r["edge"]) == (0.0, 0.0) and r["decision_edge"] > 0.1
        assert (r["best_book"], r["best_bet_link"]) == ("hardrockbet", "hardrockbet/u")

    def test_it_never_bets_an_over_however_good_it_looks(self):
        q = _quotes([(1, "draftkings", 1.5, 150, -190)])
        assert 1 - float(P.p_over(4.0, 1.5)) < 0.15           # the model loves the over
        assert card.pick_rows(P.SHOTS, _mus([(1, 4.0)]), q, GAMES, "2026-10-01", 1000.0, 0.0) == []
        assert all(s.sides == ("under",) for s in P.SPECS.values())

    def test_the_cut_is_the_models_own_ev_floor_on_its_own_probability(self):
        for spec in P.LIVE:
            assert config.min_ev_for(spec.model_id) == config.MODEL_OWN_EV_FLOOR[spec.model_id] == 0.10
            assert spec.model_id in config.MODELS_ON_OWN_PROBABILITY
        p = 1 - float(P.p_over(0.42, 0.5))                     # P(no assist) = exp(-0.42) = 0.657
        just_under = _quotes([(1, "draftkings", 0.5, 130, -150)])   # EV = 0.657 * 1.667 - 1 = +0.095
        just_over = _quotes([(1, "draftkings", 0.5, 130, -145)])    # EV = 0.657 * 1.690 - 1 = +0.110
        assert P.expected_value(p, -150) < 0.10 < P.expected_value(p, -145)
        assert card.pick_rows(P.ASSISTS, _mus([(1, 0.42)]), just_under, GAMES, "2026-10-01", 1000.0, 0.0) == []
        assert len(card.pick_rows(P.ASSISTS, _mus([(1, 0.42)]), just_over, GAMES, "2026-10-01", 1000.0, 0.0)) == 1

    def test_a_price_shorter_than_the_floor_is_passed_for_the_next_best(self):
        """-260 clears on EV and is under the -200 price floor; the bet is the book that is not."""
        q = _quotes([(1, "draftkings", 0.5, 200, -260), (1, "betmgm", 0.5, 170, -200)])
        r = card.pick_rows(P.ASSISTS, _mus([(1, 0.10)]), q, GAMES, "2026-10-01", 1000.0, 0.0)
        assert [(x["decision_book"], x["decision_odds"], x["dk_odds"]) for x in r] == [("betmgm", -200.0, -260.0)]
        only_short = _quotes([(1, "draftkings", 0.5, 200, -260)])
        assert card.pick_rows(P.ASSISTS, _mus([(1, 0.10)]), only_short, GAMES, "2026-10-01", 1000.0, 0.0) == []

    def test_saves_are_priced_on_the_wider_distribution_the_artifact_carries(self):
        q = _quotes([(31, "draftkings", 26.5, -115, -110)])
        tight = card.pick_rows(P.SAVES, _mus([(31, 23.0)]), q, GAMES, "2026-10-01", 1000.0, 0.0)[0]
        wide = card.pick_rows(P.SAVES, _mus([(31, 23.0)]), q, GAMES, "2026-10-01", 1000.0, 0.033)[0]
        assert tight["model_probability"] > wide["model_probability"] > 0.6
        src = (ROOT / "scripts" / "nhl_props_card.py").read_text(encoding="utf-8")
        assert 'float(art.get("dispersion", 0.0))' in src

    def test_fanduel_is_not_shopped(self):
        assert "fanduel" in config.BEST_LINE_BOOKMAKERS and "fanduel" not in P.books()
        assert P.books()[0] == "draftkings" and set(P.books()) <= set(config.BEST_LINE_BOOKMAKERS)

    def test_every_pick_it_writes_passes_the_publishers_own_check(self):
        q = _quotes([(1, "draftkings", 2.5, -140, 105), (2, "hardrockbet", 1.5, -160, 125)])
        rows = card.pick_rows(P.SHOTS, _mus([(1, 1.5), (2, 0.9)]), q, GAMES, "2026-10-01", 1000.0, 0.0)
        assert len(rows) == 2
        for r in rows:
            assert pick_problems(r["pick_label"], r["pick_side"], r["scored_line"], r["model_id"],
                                 home="NYR", away="BOS", prop_market=r["prop_market"]) == []
            # no book suffix: the book is on the row, and a suffix is how the
            # closing-line capture would be told dk_odds is another book's
            assert pt._book_from_label(r["pick_label"]) == "draftkings"
            assert pt._PICK_LABEL_RE.match(r["pick_label"]).group(1) == r["player_key"]
            # the price every surface filters and settles on is the deciding one
            assert (r["decision_odds"] is not None and r["decision_edge"] >= 0.0
                    and r["decision_odds"] >= config.min_odds_for(r["model_id"]))


def _row(gid: str, pid: str, ev: float) -> dict:
    return {"game_id": gid, "player_id": pid, "_ev": ev}


class TestTheLimitPerGame:
    """Shots on goal: at most three bets a game (mike, 2026-10-01: "Limit 3")."""

    def test_shots_on_goal_is_limited_to_three_and_the_others_are_not(self):
        assert P.SHOTS.max_per_game == 3
        assert P.SAVES.max_per_game is None and P.ASSISTS.max_per_game is None

    def test_it_keeps_the_three_best_in_each_game(self):
        rows = [_row("A", str(i), ev) for i, ev in enumerate([0.11, 0.30, 0.12, 0.25, 0.20])] + \
               [_row("B", "9", 0.10), _row("B", "8", 0.40)]
        kept = card.limit_per_game(P.SHOTS, rows)
        assert sorted(r["player_id"] for r in kept if r["game_id"] == "A") == ["1", "3", "4"]
        assert sorted(r["player_id"] for r in kept if r["game_id"] == "B") == ["8", "9"]

    def test_picks_already_written_hold_their_slots(self):
        """Two written on an earlier pass: one slot left, and a player already
        picked is not a new pick however much better his EV now looks."""
        rows = [_row("A", "1", 0.50), _row("A", "2", 0.30), _row("A", "3", 0.20)]
        kept = card.limit_per_game(P.SHOTS, rows, {"A": {"1", "7"}})
        assert [r["player_id"] for r in kept] == ["2"]
        assert card.limit_per_game(P.SHOTS, rows, {"A": {"5", "6", "7"}}) == []

    def test_an_unlimited_market_passes_every_row(self):
        rows = [_row("A", str(i), 0.2) for i in range(8)]
        assert card.limit_per_game(P.ASSISTS, rows, {"A": {"x", "y", "z"}}) == rows

    def test_the_card_applies_it_with_the_written_picks(self):
        src = (ROOT / "scripts" / "nhl_props_card.py").read_text(encoding="utf-8")
        assert "rows = limit_per_game(spec, rows, existing_picks(conn, spec.model_id, sorted(games)))" in src

    def test_the_eleven_pick_game_becomes_three(self):
        """2026-10-01, EDM at VAN: eleven shots-on-goal unders cleared. Through
        the limit, the three best by EV are the picks."""
        evs = [0.305, 0.285, 0.262, 0.256, 0.246, 0.226, 0.298, 0.157, 0.158, 0.157, 0.117]
        rows = [_row("NHL_2026-10-01_EDM_VAN", str(i), ev) for i, ev in enumerate(evs)]
        kept = card.limit_per_game(P.SHOTS, rows)
        assert sorted(r["_ev"] for r in kept) == [0.285, 0.298, 0.305]


class TestTheBacktestGradesTheRuleTheCardPlays:
    def test_one_slate_both_ways_with_the_limit(self):
        """The 40-player slate below, through both, with the shots limit on: the same three."""
        rows, mus = [], []
        rng = np.random.default_rng(5)
        for pid in range(1, 41):
            mu = float(rng.uniform(0.8, 3.2))
            mus.append((pid, mu))
            for book in ("draftkings", "betmgm", "hardrockbet", "fanduel"):
                line = float(rng.choice([1.5, 2.5, 3.5]))
                u = int(rng.choice([-320, -260, -230, -150, -125, -110, 100, 115, 130]))
                rows.append((pid, book, line, -u - 20 if u > 0 else 100, u))
        q = _quotes(rows)
        live = card.limit_per_game(P.SHOTS, card.pick_rows(
            P.SHOTS, _mus(mus), q[q.book.isin(P.books())], GAMES, "2026-10-01", 1000.0, 0.0))
        df = q.merge(_mus(mus), on=["player_id", "game_id"]).assign(
            pkey=lambda d: d.player_id.astype(str), alpha=0.0, actual=0, season=2026, game_date="2026-10-01")
        s = bt.sides(df[df.book.isin(P.books())])
        graded = bt.card(s, config.MODEL_OWN_EV_FLOOR[P.SHOTS.model_id], P.SHOTS.sides,
                         per_game=P.SHOTS.max_per_game)
        want = {(r.pkey, r.book, r.line, r.price) for r in graded.itertuples()}
        got = {(r["player_id"], r["decision_book"], r["scored_line"], r["decision_odds"]) for r in live}
        assert got == want and len(got) == 3

    def test_one_slate_both_ways(self):
        """The same priced slate through the backtest's `card` and the live card's
        `pick_rows`: the same players, at the same book, line and price (before
        the per-game limit, which the test above covers)."""
        rng = np.random.default_rng(5)
        rows, mus = [], []
        for pid in range(1, 41):
            mu = float(rng.uniform(0.8, 3.2))
            mus.append((pid, mu))
            for book in ("draftkings", "betmgm", "hardrockbet", "fanduel"):
                line = float(rng.choice([1.5, 2.5, 3.5]))
                u = int(rng.choice([-320, -260, -230, -150, -125, -110, 100, 115, 130]))   # some under the -200 floor
                rows.append((pid, book, line, -u - 20 if u > 0 else 100, u))
        q = _quotes(rows)
        live = card.pick_rows(P.SHOTS, _mus(mus), q[q.book.isin(P.books())], GAMES, "2026-10-01", 1000.0, 0.0)

        df = q.merge(_mus(mus), on=["player_id", "game_id"]).assign(
            pkey=lambda d: d.player_id.astype(str), alpha=0.0, actual=0, season=2026, game_date="2026-10-01")
        s = bt.sides(df[df.book.isin(P.books())])
        graded = bt.card(s, config.MODEL_OWN_EV_FLOOR[P.SHOTS.model_id], P.SHOTS.sides)
        want = {(r.pkey, r.book, r.line, r.price) for r in graded.itertuples()}
        got = {(r["player_id"], r["decision_book"], r["scored_line"], r["decision_odds"]) for r in live}
        assert got == want and 3 < len(got) < 40
        assert (s[(s.side == "under") & (s.ev >= 0.10)].price < -200).any()      # the floor had something to refuse
        assert not any(b == "fanduel" for _, b, _, _ in got)


class _Conn:
    """player_prop_odds rows in, whatever the query asks for out."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        rows = self.rows

        class R:
            def fetchall(self):
                return rows
        return R()


class TestOnlyTheNewestFetchIsShopped:
    def _rows(self):
        early, late = "2026-10-01T18:08:24+00:00", "2026-10-01T22:11:31+00:00"
        return [
            (GAME, "Skater 1", "draftkings", 2.5, -140, 105, early, None, None),
            (GAME, "Skater 1", "betmgm", 2.5, -160, 135, early, None, None),      # gone from the newer fetch
            (GAME, "Skater 1", "draftkings", 2.5, -150, 110, late, None, None),
            (GAME, "Skater 1", "hardrockbet", 2.5, -145, 108, late, None, None),
            (GAME, "Skater 1", "hardrockbet", 2.5, -120, 150, "2026-10-01T23:30:00+00:00", None, None),  # in play
        ]

    def test_a_book_that_left_the_newest_fetch_is_not_carried_forward(self):
        q = card.latest_quotes(_Conn(self._rows()), GAMES, "player_shots_on_goal")
        assert sorted(zip(q.book, q.under)) == [("draftkings", 110.0), ("hardrockbet", 108.0)]

    def test_an_incoherent_two_way_quote_is_dropped(self):
        rows = [(GAME, "Skater 1", "draftkings", 2.5, 120, 130, "2026-10-01T22:11:31+00:00", None, None),
                (GAME, "Skater 2", "draftkings", 2.5, -140, 105, "2026-10-01T22:11:31+00:00", None, None)]
        q = card.latest_quotes(_Conn(rows), GAMES, "player_shots_on_goal")
        assert list(q.player) == ["Skater 2"]

    def test_the_query_names_only_the_books_it_may_bet(self):
        src = (ROOT / "scripts" / "nhl_props_card.py").read_text(encoding="utf-8")
        assert "bookmaker = ANY(%s)" in src and "list(np_.books())" in src


class TestWhoThePlayerIs:
    WHO = pd.DataFrame([
        {"player_id": 1, "player_name": "Mitchell Marner", "team": "BOS", "position": "R", "pkey": "mitchellmarner"},
        {"player_id": 2, "player_name": "Elias Pettersson", "team": "NYR", "position": "C", "pkey": "eliaspettersson"},
        {"player_id": 3, "player_name": "Elias Pettersson", "team": "NYR", "position": "D", "pkey": "eliaspettersson"},
        {"player_id": 4, "player_name": "Moved Away", "team": "TOR", "position": "C", "pkey": "movedaway"},
    ])

    def _q(self, *names):
        return pd.DataFrame([{"game_id": GAME, "player": n, "book": b, "line": 2.5, "over": -140.0, "under": 105.0,
                              "over_link": None, "under_link": None} for n in names for b in ("draftkings", "betmgm")])

    def test_two_books_quoting_one_player_make_one_row(self):
        up, priced, skipped = card.upcoming_rows(self._q("Mitchell Marner"), GAMES, self.WHO, "2026-10-01", 2027)
        assert len(up) == 1 and len(priced) == 2 and skipped == []
        assert set(priced.player_id) == {1} and int(up.is_home.iloc[0]) == 0 and up.opponent.iloc[0] == "NYR"

    def test_a_shared_name_or_a_player_on_neither_team_is_skipped_and_named(self):
        up, priced, skipped = card.upcoming_rows(self._q("Elias Pettersson", "Moved Away", "Nobody Atall"),
                                                 GAMES, self.WHO, "2026-10-01", 2027)
        assert up.empty and priced.empty and len(skipped) == 3
        assert any("2 match" in s for s in skipped) and sum("no match" in s for s in skipped) == 2


# ── the picks table: insert-once, and settlement end to end ───────────────────

class _Shim:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        if isinstance(params, dict):
            import re
            names = re.findall(r"%\((\w+)\)s", sql)
            return self._c.execute(re.sub(r"%\(\w+\)s", "?", sql), [params[n] for n in names])
        return self._c.execute(sql.replace("%s", "?"), params or [])

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    have = {r[1] for r in c.execute("PRAGMA table_info(picks)")}
    for col in ("player_id TEXT", "is_live BOOLEAN DEFAULT 0", "model_probability_cal REAL", "decision_book TEXT",
                "decision_odds REAL", "decision_implied_prob REAL", "decision_edge REAL", "dk_bet_link TEXT",
                "game_time TEXT", "confidence_tier TEXT", "prop_market TEXT", "player_key TEXT"):
        if col.split()[0] not in have:
            c.execute(f"ALTER TABLE picks ADD COLUMN {col}")
    c.execute("CREATE TABLE IF NOT EXISTS nhl_skater_game_log (nhl_game_id INTEGER, player_id INTEGER, "
              "player_name TEXT, team TEXT, game_date TEXT, blocked_shots INTEGER, shots INTEGER, "
              "assists INTEGER, toi_seconds INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS nhl_goalie_game_log (nhl_game_id INTEGER, player_id INTEGER, "
              "player_name TEXT, game_id TEXT, team TEXT, game_date TEXT, started INTEGER, saves INTEGER, "
              "shots_against INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS nhl_team_game_log (nhl_game_id INTEGER, team TEXT, game_id TEXT)")
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, home_score, "
              "away_score, home_win) VALUES (?, 'NHL', 2027, '2026-10-01', 'NYR', 'BOS', 3, 2, 1)", (GAME,))
    for team in ("BOS", "NYR"):
        c.execute("INSERT INTO nhl_team_game_log VALUES (2026020010, ?, ?)", (team, GAME))
    yield c
    c.close()


def _bet(c, model_id: str, player_id: str, name: str, line: float, odds: float, stat: str, market: str,
         book: str = "draftkings") -> int:
    """A pick as the card writes it: decided at `book`; DraftKings' columns empty when it is not DraftKings."""
    away = book != "draftkings"
    c.execute("""INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label,
                 model_probability, dk_implied_prob, edge, dk_odds, scored_line, kelly_fraction,
                 recommended_bet, bankroll_at_pick, signal_type, prop_market, player_key, player_id,
                 decision_book, decision_odds, line_book)
                 VALUES (?, ?, 'NHL', '2026-10-01', 'under', ?, 0.62, ?, ?, ?, ?, 0.01, 10.0, 1000.0,
                         'BET', ?, ?, ?, ?, ?, ?)""",
              (GAME, model_id, f"{name} Under {line:g} {stat}", 0.0 if away else 0.4878, 0.0 if away else 0.13,
               None if away else odds, line, market, name, player_id, book, odds, book if away else None))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def _skated(c, player_id: int, name: str, team: str, shots: int, assists: int) -> None:
    c.execute("INSERT INTO nhl_skater_game_log VALUES (2026020010, ?, ?, ?, '2026-10-01', 0, ?, ?, 1200)",
              (player_id, name, team, shots, assists))


def _in_goal(c, player_id: int, name: str, team: str, started: int, saves: int, date: str = "2026-10-01") -> None:
    c.execute("INSERT INTO nhl_goalie_game_log VALUES (2026020010, ?, ?, ?, ?, ?, ?, ?, ?)",
              (player_id, name, GAME, team, date, started, saves, saves + 2))


def _result(c, pick_id: int):
    return c.execute("SELECT result, profit_flat FROM picks WHERE pick_id = ?", (pick_id,)).fetchone()


class TestInsertOnce:
    def _row(self, **over) -> dict:
        q = _quotes([(1, "betmgm", 2.5, -150, 120)])
        r = card.pick_rows(P.SHOTS, _mus([(1, 1.6)]), q, GAMES, "2026-10-01", 1000.0, 0.0)[0]
        return {**r, **over}

    def test_a_second_pass_writes_nothing_even_at_a_new_book_under_a_new_spelling(self, db):
        """A pick is a pick: a later pass that finds a better book, a moved line,
        or the same player spelled another way must not write him again."""
        conn = _Shim(db)
        assert card.publish(conn, [self._row()]) == 1
        moved = self._row(decision_book="hardrockbet", decision_odds=140.0, scored_line=3.5,
                          player_key="Mitch Marner", pick_label="Mitch Marner Under 3.5 Shots on Goal")
        assert card.publish(conn, [moved]) == 0
        rows = db.execute("SELECT pick_label, decision_book, decision_odds, scored_line, dk_odds, line_book "
                          "FROM picks").fetchall()
        assert rows == [("Skater 1 Under 2.5 Shots on Goal", "betmgm", 120.0, 2.5, None, "betmgm")]

    def test_the_same_player_in_another_market_is_another_pick(self, db):
        conn = _Shim(db)
        assert card.publish(conn, [self._row()]) == 1
        other = self._row(model_id="nhl_prop_assists", prop_market="player_assists",
                          pick_label="Skater 1 Under 0.5 Assists")
        assert card.publish(conn, [other]) == 1


class TestSettlement:
    def test_skater_unders_grade_on_the_stat_their_market_names(self, db):
        shots = _bet(db, "nhl_prop_shots_on_goal", "8479325", "Charlie McAvoy", 2.5, 120.0, "Shots on Goal",
                     "player_shots_on_goal", book="betmgm")           # no DraftKings price on the row at all
        assists = _bet(db, "nhl_prop_assists", "8479325", "Charlie McAvoy", 0.5, -150.0, "Assists", "player_assists")
        _skated(db, 8479325, "Charlie McAvoy", "BOS", shots=2, assists=1)
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, shots) == ("WIN", 120.0)            # 2 shots under 2.5, +1.20 units
        assert _result(db, assists) == ("LOSS", -100.0)        # one assist beats under 0.5

    def test_a_starter_is_graded_on_his_saves(self, db):
        won = _bet(db, "nhl_prop_saves", "8478048", "Igor Shesterkin", 25.5, -125.0, "Saves", "player_total_saves",
                   book="hardrockbet")
        lost = _bet(db, "nhl_prop_saves", "8476883", "Jeremy Swayman", 24.5, -110.0, "Saves", "player_total_saves")
        _in_goal(db, 8478048, "Igor Shesterkin", "NYR", 1, 22)
        _in_goal(db, 8476883, "Jeremy Swayman", "BOS", 1, 31)
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, won) == ("WIN", 80.0)               # +0.80 units at -125
        assert _result(db, lost) == ("LOSS", -100.0)

    def test_a_goalie_who_did_not_start_is_void_even_if_he_played(self, db):
        """The books void saves when he does not start. A backup who came on in
        relief has a row and a save count; grading him on it would turn a void
        into a win the backtest never counted."""
        relief = _bet(db, "nhl_prop_saves", "8478048", "Igor Shesterkin", 25.5, -125.0, "Saves", "player_total_saves")
        sat = _bet(db, "nhl_prop_saves", "8476999", "Linus Ullmark", 25.5, -110.0, "Saves", "player_total_saves")
        _in_goal(db, 8478048, "Igor Shesterkin", "NYR", 0, 4)   # relieved the starter: four saves, under 25.5
        _in_goal(db, 8470000, "The Starter", "NYR", 1, 12)
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, relief) == ("NO_ACTION", 0)
        assert _result(db, sat) == ("NO_ACTION", 0)

    def test_a_game_with_no_goalie_log_yet_waits(self, db):
        waiting = _bet(db, "nhl_prop_saves", "8478048", "Igor Shesterkin", 25.5, -125.0, "Saves", "player_total_saves")
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, waiting) == (None, None)

    def test_the_game_settler_leaves_all_three_alone(self, db):
        ids = [_bet(db, "nhl_prop_saves", "8478048", "Igor Shesterkin", 25.5, -125.0, "Saves", "player_total_saves"),
               _bet(db, "nhl_prop_assists", "1", "A B", 0.5, -150.0, "Assists", "player_assists"),
               _bet(db, "nhl_prop_shots_on_goal", "1", "A B", 2.5, 120.0, "Shots on Goal", "player_shots_on_goal")]
        pt._settle_game_picks(_Shim(db), "2026-10-01", "TS")
        assert [_result(db, i) for i in ids] == [(None, None)] * 3


class TestEveryLiveModelIsWiredEverywhere:
    @pytest.mark.parametrize("spec", P.LIVE, ids=lambda s: s.model_id)
    def test_config_settlement_and_app(self, spec):
        mid = spec.model_id
        assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.0}
        assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.0 and config.MODEL_PROB_THRESHOLDS[mid] == 0.0
        assert config.SCORING_METHODS[mid] == config.SCORING_ARTIFACT
        kind, stat = pt._PROP_STAT_MAP[mid]
        assert kind == ("nhl_goalie" if spec.kind == "goalie" else "nhl_skater") and stat == spec.stat
        assert pt._PROP_MARKET_FOR_MODEL[mid] == spec.market
        assert spec.market in config.PROP_MARKETS_NHL           # the prices it reads are being collected
        meta = (ROOT / "mobile" / "src" / "lib" / "modelMeta.ts").read_text(encoding="utf-8")
        assert f"  {mid}: {{" in meta and f"statLabel: '{spec.label}'" in meta
        markets = (ROOT / "mobile" / "src" / "lib" / "markets.ts").read_text(encoding="utf-8")
        assert f"  {mid}: '{spec.market}'," in markets
        gen = (ROOT / "mobile" / "src" / "lib" / "thresholds.generated.ts").read_text(encoding="utf-8")
        assert f"  {mid}: {{ min_prob: 0, min_edge: 0, min_odds: -200 }}," in gen

    @pytest.mark.parametrize("spec", P.LIVE, ids=lambda s: s.model_id)
    def test_the_committed_artifact_is_the_model_this_module_describes(self, spec):
        import pickle
        files = sorted((ROOT / "models" / "saved").glob(f"{spec.model_id}_*.pkl"))
        assert files, f"no {spec.model_id} artifact is committed"
        art = pickle.loads(files[-1].read_bytes())
        assert art["model_id"] == spec.model_id and art["feature_cols"] == list(spec.features)
        assert art["market"] == spec.market and art["sides"] == ["under"]
        assert (art["dispersion"] > 0.01) == spec.overdispersed
        assert art["train_seasons"][-1] == 2026

    def test_the_step_runs_both_cards_and_one_failing_does_not_stop_the_other(self):
        rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
        body = rp.split("def step_nhl_prop_scoring")[1].split("\ndef ")[0]
        assert "from scripts.nhl_prop_card import run_card" in body
        assert "from scripts.nhl_props_card import run_card as run_props_card" in body
        assert body.count("except Exception") == 2 and "return ok" in body

    def test_the_row_is_written_whole(self):
        """Every column the card computes is one it inserts: a key left out of
        _COLS is a field every surface would read as empty."""
        q = _quotes([(1, "draftkings", 2.5, -140, 105), (1, "betmgm", 2.5, -150, 120)])
        r = card.pick_rows(P.SHOTS, _mus([(1, 1.6)]), q, GAMES, "2026-10-01", 1000.0, 0.0)[0]
        assert {k for k in r if not k.startswith("_")} == set(card._COLS)
        for col in ("line_book", "decision_book", "decision_odds", "decision_edge", "best_book", "best_bet_link"):
            assert col in card._COLS


def test_slate_time_is_utc_and_a_started_game_is_not_scored():
    class Conn:
        def execute(self, sql, params=None):
            class R:
                def fetchall(s):
                    return [("G1", "NYR", "BOS", "2026-10-01T23:10:00Z"), ("G2", "VAN", "EDM", "2026-10-02T02:10:00Z")]
            return R()
    assert list(card.slate(Conn(), "2026-10-01", datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc))) == ["G2"]
