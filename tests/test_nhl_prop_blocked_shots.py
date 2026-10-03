"""nhl_prop_blocked_shots: one function builds a training row and tonight's, and the
card writes a pick only when the model's own number clears its own floor.

The model's evidence is a walk-forward backtest (scripts/nhl_prop_blocked_shots_backtest.py).
That evidence only transfers to production if the row scored tonight is built
the way the backtested rows were -- which is what the first class pins.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
import models.nhl_prop_blocked_shots as bs
from scripts import nhl_prop_card as card

ROOT = Path(__file__).resolve().parents[1]


def _log(n_games: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two teams playing each other every other day; two skaters a side."""
    rng = np.random.default_rng(7)
    sk, tm = [], []
    for g in range(n_games):
        date = (pd.Timestamp("2025-10-10") + pd.Timedelta(days=2 * g)).strftime("%Y-%m-%d")
        gid = 2025020000 + g
        for team, opp, home in (("BOS", "NYR", g % 2), ("NYR", "BOS", 1 - g % 2)):
            tm.append({"nhl_game_id": gid, "game_id": f"NHL_{date}_X", "team": team, "opponent": opp,
                       "game_date": date, "shots_for": int(rng.integers(20, 40))})
            for k in range(2):
                pid = (1 if team == "BOS" else 3) + k
                sk.append({"nhl_game_id": gid, "player_id": pid, "player_name": f"Player {pid}",
                           "position": "D" if k == 0 else "C", "season": 2026, "game_date": date,
                           "team": team, "opponent": opp, "is_home": home,
                           "blocked_shots": int(rng.integers(0, 5)),
                           "toi_seconds": int(rng.integers(600, 1500)),
                           "pp_toi_seconds": int(rng.integers(0, 200))})
    return pd.DataFrame(sk), pd.DataFrame(tm)


class TestTonightsRowIsATrainingRow:
    def test_an_upcoming_row_carries_exactly_what_the_played_row_carried(self):
        """Take the last game out of the log, hand it back as an upcoming game,
        and every input must equal what the full log gave that game."""
        sk, tm = _log()
        last = sk.nhl_game_id.max()
        played = bs.build_frame(sk, tm)
        want = played[played.nhl_game_id == last].set_index("player_id")[bs.FEATURES]

        held = sk[sk.nhl_game_id == last]
        up = held[["player_id", "player_name", "position", "season", "game_date", "team",
                   "opponent", "is_home"]].assign(game_id="NHL_tonight")
        frame = bs.build_frame(sk[sk.nhl_game_id != last], tm[tm.nhl_game_id != last], up)
        got = frame[frame.upcoming].set_index("player_id")[bs.FEATURES]

        assert len(got) == 4
        pd.testing.assert_frame_equal(got.sort_index(), want.sort_index(), check_dtype=False)

    def test_the_game_itself_is_never_in_its_own_inputs(self):
        sk, tm = _log()
        base = bs.build_frame(sk, tm)
        loud = sk.copy()
        last = loud.nhl_game_id.max()
        loud.loc[loud.nhl_game_id == last, "blocked_shots"] = 40          # an absurd night
        after = bs.build_frame(loud, tm)
        a = base[base.nhl_game_id == last].set_index("player_id")[bs.FEATURES]
        b = after[after.nhl_game_id == last].set_index("player_id")[bs.FEATURES]
        pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())

    def test_a_player_under_ten_games_is_not_scored(self):
        sk, tm = _log(n_games=8)
        frame = bs.build_frame(sk, tm)
        assert bs.usable(frame).empty

    def test_the_under_probability_is_the_poisson_mass_at_or_below_the_line(self):
        from scipy.stats import poisson
        assert 1 - float(bs.p_over(1.2, 1.5)) == pytest.approx(poisson.cdf(1, 1.2))
        assert float(bs.p_over(1.2, 2.5)) == pytest.approx(poisson.sf(2, 1.2))


GAMES = {"NHL_2026-10-01_BOS_NYR": {"home": "NYR", "away": "BOS",
                                    "commence_time": "2026-10-01T23:10:00Z"}}


def _scored(mu: float, under: float = 105, over: float = -135, line: float = 1.5) -> pd.DataFrame:
    return pd.DataFrame([{"player_id": 1, "game_id": "NHL_2026-10-01_BOS_NYR", "mu": mu,
                          "quote_player": "Charlie McAvoy", "line": line, "over": over, "under": under,
                          "over_link": "o", "under_link": "u"}])


class TestTheCard:
    def test_an_under_that_clears_the_floor_is_written_with_a_label_that_matches_it(self):
        from tracking.pick_integrity import pick_problems
        rows = card.pick_rows(_scored(mu=0.9), GAMES, "2026-10-01", bankroll=1000.0)
        assert len(rows) == 1
        r = rows[0]
        assert r["pick_side"] == "under" and r["scored_line"] == 1.5 and r["dk_odds"] == 105
        assert r["pick_label"] == "Charlie McAvoy Under 1.5 Blocked Shots (DK)"
        assert r["prop_market"] == bs.MARKET and r["player_id"] == "1" and r["signal_type"] == "BET"
        assert not pick_problems(r["pick_label"], r["pick_side"], r["scored_line"], r["model_id"],
                                 prop_market=r["prop_market"])
        assert r["_ev"] >= config.min_ev_for(bs.MODEL_ID)

    def test_it_decides_on_the_models_own_probability(self):
        """The cut was measured on the raw Poisson probability; the correction a
        model with no record is handed turned the same three seasons into a loss."""
        r = card.pick_rows(_scored(mu=0.9), GAMES, "2026-10-01", bankroll=1000.0)[0]
        assert bs.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
        assert r["model_probability_cal"] == r["model_probability"]

    def test_an_edge_under_the_floor_is_not_a_pick(self):
        # mean 1.55 -> P(under 1.5) about 0.54; at +105 the EV is about 0.11... at -110 it is ~0.03
        assert card.pick_rows(_scored(mu=1.55, under=-110, over=-110), GAMES, "2026-10-01", 1000.0) == []

    def test_an_ev_the_old_gate_would_publish_with_decision_edge_under_the_floor_is_not_a_bet(self):
        """Mean 1.40, under 1.5 at -110: EV is about +0.13, so the old gate
        publishes it, and the stored decision_edge is about +0.068. Not a BET.
        The same player's over at +300 has the higher EV and still is not a BET.
        """
        from models.honest_ev import gate
        p = 1 - float(bs.p_over(1.40, 1.5))
        assert gate(bs.MODEL_ID, p, -110).clears
        assert round(p - (110 / 210), 4) < config.min_ev_for(bs.MODEL_ID)
        assert card.pick_rows(_scored(mu=1.40, under=-110, over=300), GAMES, "2026-10-01", 1000.0) == []

    def test_an_over_that_clears_the_floor_is_not_a_bet(self):
        """Live publishing stays unders. A mean of 3.0 at under 1.5 -110 is an
        over the old card would take, and it is not a BET."""
        assert card.pick_rows(_scored(mu=3.0, under=-110, over=-110), GAMES, "2026-10-01", 1000.0) == []

    def test_the_floor_is_the_models_own_and_is_the_swept_number(self):
        assert config.MODEL_OWN_EV_FLOOR[bs.MODEL_ID] == 0.10
        assert config.min_ev_for(bs.MODEL_ID) == 0.10          # not the global 0.20
        assert config.ACTION_THRESHOLDS[bs.MODEL_ID] == {"min_prob": 0.0, "min_edge": 0.0}

    def test_a_one_sided_quote_is_priced_on_the_side_it_has(self):
        rows = card.pick_rows(_scored(mu=0.9, over=float("nan")), GAMES, "2026-10-01", 1000.0)
        assert len(rows) == 1 and rows[0]["pick_side"] == "under"

    def test_a_second_pass_does_not_touch_a_pick_that_exists(self):
        class Conn:
            def __init__(self):
                self.inserted, self.commits = [], 0

            def execute(self, sql, params=None):
                class R:
                    def __init__(s, row): s.row = row
                    def fetchone(s): return s.row
                if sql.lstrip().upper().startswith("SELECT"):
                    return R((1,) if any(i["player_key"] == params[2] for i in self.inserted) else None)
                self.inserted.append(params)
                return R(None)

            def commit(self):
                self.commits += 1

        conn = Conn()
        rows = card.pick_rows(_scored(mu=0.9), GAMES, "2026-10-01", 1000.0)
        assert card.publish(conn, rows) == 1
        moved = card.pick_rows(_scored(mu=0.9, under=130), GAMES, "2026-10-01", 1000.0)   # the price moved
        assert card.publish(conn, moved) == 0
        assert len(conn.inserted) == 1 and conn.inserted[0]["dk_odds"] == 105


class TestWhoThePlayerIs:
    WHO = pd.DataFrame([
        {"player_id": 1, "player_name": "Charlie McAvoy", "team": "BOS", "position": "D"},
        {"player_id": 2, "player_name": "Adam Fox", "team": "NYR", "position": "D"},
        {"player_id": 3, "player_name": "Sebastian Aho", "team": "BOS", "position": "C"},
        {"player_id": 4, "player_name": "Sebastian Aho", "team": "NYR", "position": "D"},
        {"player_id": 5, "player_name": "Traded Guy", "team": "SEA", "position": "D"},
    ]).assign(pkey=lambda d: d.player_name.map(bs.name_key))

    def _quotes(self, *names):
        return pd.DataFrame([{"game_id": "NHL_2026-10-01_BOS_NYR", "player": n} for n in names])

    def test_a_player_is_placed_on_his_side_of_the_game(self):
        up, skipped = card.upcoming_rows(self._quotes("Charlie McAvoy", "Adam Fox"), GAMES, self.WHO,
                                         "2026-10-01", 2027)
        assert not skipped
        by = up.set_index("player_id")
        assert (by.loc[1, "team"], by.loc[1, "opponent"], by.loc[1, "is_home"]) == ("BOS", "NYR", 0)
        assert (by.loc[2, "team"], by.loc[2, "opponent"], by.loc[2, "is_home"]) == ("NYR", "BOS", 1)

    def test_a_name_two_players_in_the_game_share_is_skipped_not_guessed(self):
        up, skipped = card.upcoming_rows(self._quotes("Sebastian Aho"), GAMES, self.WHO, "2026-10-01", 2027)
        assert up.empty and len(skipped) == 1 and "2 match" in skipped[0]

    def test_a_player_whose_last_team_is_neither_side_is_skipped(self):
        up, skipped = card.upcoming_rows(self._quotes("Traded Guy", "Nobody Atall"), GAMES, self.WHO,
                                         "2026-10-01", 2027)
        assert up.empty and len(skipped) == 2

    def test_accents_do_not_lose_a_player(self):
        who = self.WHO.assign(player_name=self.WHO.player_name.replace({"Adam Fox": "Ádam Fox"}))
        who["pkey"] = who.player_name.map(bs.name_key)
        up, _ = card.upcoming_rows(self._quotes("Adam Fox"), GAMES, who, "2026-10-01", 2027)
        assert list(up.player_id) == [2]


class TestItSettlesAsAPropNotAsAGame:
    def test_the_prop_settler_takes_it_and_the_game_settler_leaves_it(self):
        from tracking import paper_tracker as pt
        assert pt._PROP_STAT_MAP[bs.MODEL_ID] == ("nhl_skater", "blocked_shots")
        assert "nhl_prop_%%" in pt._GAME_LEVEL_MODEL_FILTER
        src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
        assert "OR p.model_id LIKE 'nhl_prop_%%'" in src              # the prop settler's own filter
        assert src.count("AND p.model_id NOT LIKE 'nhl_prop_%%'") == 2  # the constant and the game settle query
        assert pt._PROP_MARKET_FOR_MODEL[bs.MODEL_ID] == bs.MARKET

    def test_a_skater_with_no_row_in_a_logged_game_is_a_dnp(self):
        """DraftKings voids a skater prop only when he does not dress: no row in
        a game whose log has landed is exactly that, and settles NO_ACTION."""
        src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
        assert '"nhl_skater":  nhl_logged_games' in src

    def test_the_card_runs_right_after_the_prices_it_reads(self):
        sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
        assert sh.index("\nstep nhl-prop-odds\n") < sh.index("\nstep nhl-prop-scoring\n")
        rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
        assert '"nhl-prop-scoring": lambda: step_nhl_prop_scoring(dry_run=args.dry_run)' in rp


def test_the_committed_artifact_is_the_model_this_module_describes():
    import pickle
    files = sorted((ROOT / "models" / "saved").glob(f"{bs.MODEL_ID}_*.pkl"))
    assert files, "no nhl_prop_blocked_shots artifact is committed"
    art = pickle.loads(files[-1].read_bytes())
    assert art["model_id"] == bs.MODEL_ID and art["feature_cols"] == bs.FEATURES
    assert art["market"] == bs.MARKET
    x = np.array([[1.2, 1.0, 30.0, 1200.0, 1200.0, 60.0, 60.0, 1, 2, 1, 200]], dtype=float)
    assert 0.2 < float(art["model"].predict(x)[0]) < 4.0


def test_slate_only_holds_games_that_have_not_started():
    class Conn:
        def execute(self, sql, params=None):
            class R:
                def fetchall(s):
                    return [("G1", "NYR", "BOS", "2026-10-01T23:10:00Z"),
                            ("G2", "VAN", "EDM", "2026-10-02T02:10:00Z")]
            return R()

    now = datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)
    assert list(card.slate(Conn(), "2026-10-01", now)) == ["G2"]


# ── settlement, end to end on a real (in-memory) schema ───────────────────────

import sqlite3  # noqa: E402

from data.db_setup import SCHEMA_SQL  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402


class _Shim:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        return self._c.execute(sql.replace("%s", "?"), params or [])

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    for col in ("player_id TEXT", "is_live BOOLEAN DEFAULT 0"):
        try:
            c.execute(f"ALTER TABLE picks ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    c.execute("CREATE TABLE IF NOT EXISTS nhl_skater_game_log (nhl_game_id INTEGER, player_id INTEGER, "
              "player_name TEXT, team TEXT, game_date TEXT, blocked_shots INTEGER, shots INTEGER, "
              "toi_seconds INTEGER, assists INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS nhl_team_game_log (nhl_game_id INTEGER, team TEXT, game_id TEXT)")
    gid = "NHL_2026-10-01_BOS_NYR"
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, home_score, "
              "away_score, home_win) VALUES (?, 'NHL', 2027, '2026-10-01', 'NYR', 'BOS', 3, 2, 1)", (gid,))
    for team in ("BOS", "NYR"):
        c.execute("INSERT INTO nhl_team_game_log VALUES (2026020010, ?, ?)", (team, gid))
    yield c
    c.close()


def _bet(c, player_id: str, name: str, side: str = "under", line: float = 1.5, odds: float = 105.0) -> int:
    c.execute("""INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label,
                 model_probability, dk_implied_prob, edge, dk_odds, scored_line, kelly_fraction,
                 recommended_bet, bankroll_at_pick, signal_type, prop_market, player_key, player_id)
                 VALUES ('NHL_2026-10-01_BOS_NYR', 'nhl_prop_blocked_shots', 'NHL', '2026-10-01', ?, ?,
                         0.62, 0.4878, 0.13, ?, ?, 0.01, 10.0, 1000.0, 'BET', 'player_blocked_shots', ?, ?)""",
              (side, f"{name} {side.title()} {line:g} Blocked Shots (DK)", odds, line, name, player_id))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def _played(c, player_id: int, name: str, team: str, blocks: int, date: str = "2026-10-01") -> None:
    c.execute("INSERT INTO nhl_skater_game_log VALUES (2026020010, ?, ?, ?, ?, ?, 2, 1200, 0)",
              (player_id, name, team, date, blocks))


def _result(c, pick_id: int):
    return c.execute("SELECT result, profit_flat FROM picks WHERE pick_id = ?", (pick_id,)).fetchone()


class TestSettlement:
    def test_an_under_wins_on_one_block_and_loses_on_two(self, db):
        won, lost = _bet(db, "8479325", "Charlie McAvoy"), _bet(db, "8479323", "Adam Fox")
        _played(db, 8479325, "Charlie McAvoy", "BOS", 1)
        _played(db, 8479323, "Adam Fox", "NYR", 2)
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, won) == ("WIN", 105.0)          # +1.05 units at +105
        assert _result(db, lost) == ("LOSS", -100.0)

    def test_a_scratched_skater_is_no_action_once_the_game_is_logged(self, db):
        scratched = _bet(db, "8479325", "Charlie McAvoy")
        _played(db, 8479323, "Adam Fox", "NYR", 2)          # the game's log has landed; he is not in it
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, scratched) == ("NO_ACTION", 0)

    def test_a_game_with_no_log_yet_waits(self, db):
        waiting = _bet(db, "8479325", "Charlie McAvoy")
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, waiting) == (None, None)

    def test_the_game_settler_does_not_grade_it_as_a_moneyline(self, db):
        """The trap nfl_prop_% fell into: the game path runs first, maps an
        unknown prop to 'h2h' and stamps it NO_ACTION before the prop path looks."""
        pid = _bet(db, "8479325", "Charlie McAvoy")
        pt._settle_game_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, pid) == (None, None)

    def test_a_late_start_logged_under_the_next_date_still_settles(self, db):
        pid = _bet(db, "8479325", "Charlie McAvoy")
        _played(db, 8479325, "Charlie McAvoy", "BOS", 0, date="2026-10-02")
        pt._settle_prop_picks(_Shim(db), "2026-10-01", "TS")
        assert _result(db, pid)[0] == "WIN"
