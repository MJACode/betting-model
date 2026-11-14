"""How the EuroLeague pre-game picks settle and are measured
(tracking/paper_tracker.py), and the labels they carry.

The first half is quarters 1 and 2 of euroleague_period_scores and the first
quarter is quarter 1; overtime never counts in either; a tied half pushes the
two-way moneyline, as the research graded it (docs/euroleague_1h1q_round1.md).
Before this, a EuroLeague period pick would have been read off nba_period_scores
(no rows: pending forever), h2h_h1 had no result arm at all and totals_q1 was in
no totals arm.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from models.scorer import _build_pick_label  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

GID = "EUROLEAGUE_E2026_120"


def test_each_rule_settles_on_its_own_market():
    assert pt._market_for_pick("euroleague_home_ml") == "h2h"
    assert pt._market_for_pick("euroleague_heavy_fav_ml") == "h2h"
    assert pt._market_for_pick("euroleague_home_dog_spread") == "spreads"
    assert pt._market_for_pick("euroleague_h1_dog_ml") == "h2h_h1"
    assert pt._market_for_pick("euroleague_q1_club_share_total") == "totals_q1"


def _res(side, market, h, a, line=None, price=120.0):
    spread = line if market.startswith("spreads") else None
    total = line if market.startswith("totals") else None
    return pt._compute_result(side, market, h, a, None, None, None, price, spread, total, 0.0)[0]


def test_a_tied_first_half_pushes_the_two_way_moneyline():
    assert _res("home", "h2h_h1", 40, 40) == "PUSH"
    assert _res("away", "h2h_h1", 40, 40) == "PUSH"
    assert _res("away", "h2h_h1", 38, 41) == "WIN"
    assert _res("home", "h2h_h1", 38, 41) == "LOSS"


def test_the_first_quarter_total_is_graded_on_its_own_points():
    assert _res("under", "totals_q1", 20, 21, line=41.5) == "WIN"
    assert _res("over", "totals_q1", 20, 21, line=41.5) == "LOSS"
    assert _res("over", "totals_q1", 20, 22, line=42.0) == "PUSH"


class Periods:
    """euroleague_period_scores rows for one game; nba_period_scores empty."""
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._out = self.rows if "euroleague_period_scores" in sql else []
        return self

    def fetchall(self):
        return self._out


Q = [(1, 22, 18), (2, 19, 20), (3, 21, 17), (4, 18, 25)]       # 80-80 after four: overtime
OT = Q + [(5, 9, 6)]


def test_the_first_half_is_quarters_one_and_two_and_overtime_never_counts():
    c = Periods(OT)
    assert pt.first_half_points(c, GID, 89, 86) == (41, 38)
    assert pt._first_quarter_points(c, GID, 89, 86) == (22, 18)
    assert all("nba_period_scores" not in s for s in c.sql)


def test_periods_that_do_not_add_up_to_the_final_keep_the_pick_pending():
    assert pt.first_half_points(Periods(Q), GID, 89, 86) is None          # overtime missing
    assert pt._first_quarter_points(Periods(Q[:3]), GID, 60, 55) is None  # quarter 4 missing
    assert pt._first_quarter_points(Periods([]), GID, 80, 80) is None


def test_the_settle_loop_grades_both_period_markets_on_their_periods(monkeypatch):
    monkeypatch.setattr(pt, "first_half_points", lambda conn, g, h, a: (40, 41))
    monkeypatch.setattr(pt, "_first_quarter_points", lambda conn, g, h, a: (20, 21))

    class Conn:
        def __init__(self):
            self.updates = []
            self._sql = ""

        def execute(self, sql, params=None):
            self._sql = sql
            if sql.lstrip().upper().startswith("UPDATE PICKS"):
                self.updates.append(params)
            return self

        def fetchall(self):
            if "FROM picks" in self._sql and "result IS NULL" in self._sql:
                # pick_id, game_id, model_id, side, dk_odds, rec_bet, home, away, home_win,
                # home_win_reg, went_to_ot, scored_line, f5 home, f5 away. The full game
                # (89-86 home) would settle both the other way.
                return [(1, GID, "euroleague_h1_dog_ml", "away", 130.0, 0.0, 89, 86, 1, None, 1, None,
                         None, None),
                        (2, GID, "euroleague_q1_club_share_total", "under", -120.0, 0.0, 89, 86, 1, None, 1,
                         41.5, None, None)]
            return []

        def fetchone(self):
            return None

        def commit(self):
            pass

    c = Conn()
    pt._settle_game_picks(c, "2026-11-20", "2026-11-21T00:00:00Z")
    assert len(c.updates) == 2
    assert [u[0] for u in c.updates] == ["WIN", "WIN"], c.updates


def test_a_period_close_must_be_pulled_after_the_pick():
    assert pt._ncaab_first_half_market(GID, "h2h_h1")
    assert pt._ncaab_first_half_market(GID, "totals_q1")
    assert not pt._ncaab_first_half_market(GID, "h2h")
    assert not pt._ncaab_first_half_market("NBA_2026-11-20_BOS_MIL", "totals_q1")


def test_the_labels_say_which_period_and_the_integrity_check_holds_them_to_it():
    h1 = _build_pick_label("away", "MAD", "PAN", "h2h_h1")
    q1 = _build_pick_label("over", "MAD", "PAN", "totals_q1", 41.5)
    assert h1 == "PAN @ MAD — First Half PAN ML"
    assert q1 == "PAN @ MAD — First Quarter Over 41.5"
    assert pick_problems(h1, "away", None, "euroleague_h1_dog_ml", "MAD", "PAN") == []
    assert pick_problems(q1, "over", 41.5, "euroleague_q1_club_share_total", "MAD", "PAN") == []
    assert pick_problems("PAN ML", "away", None, "euroleague_h1_dog_ml", "MAD", "PAN")
    assert pick_problems("MAD vs PAN Over 41.5", "over", 41.5, "euroleague_q1_club_share_total", "MAD", "PAN")
    # the full-game ones read as the full game
    assert _build_pick_label("home", "MAD", "PAN", "h2h") == "MAD ML"
    assert pick_problems("MAD +3.5", "home", 3.5, "euroleague_home_dog_spread", "MAD", "PAN") == []
    assert pick_problems("MAD -3.5", "home", 3.5, "euroleague_home_dog_spread", "MAD", "PAN")


@pytest.mark.parametrize("model", ["euroleague_h1_dog_ml", "euroleague_q1_club_share_total"])
def test_the_closing_line_recompute_treats_a_period_pick_like_the_ncaab_first_half(model):
    sql = (Path(pt.__file__).resolve().parents[1] / "data" / "migrations"
           / "clv_standard_v2_2026_10_14.sql").read_text(encoding="utf-8")
    assert sql.count("OR (s.sport_prefix = 'EUROLEAGUE' AND s.game_market IN ('h2h_h1', 'totals_q1')") == 3
    assert sql.count("AND NOT (s.sport_prefix = 'EUROLEAGUE' AND s.game_market IN ('h2h_h1', 'totals_q1'))") == 3
    tail = sql[sql.index("A null close is not a measurement. NCAAB first half stays unmeasured"):]
    assert f"'{model}'" in tail[:600]
