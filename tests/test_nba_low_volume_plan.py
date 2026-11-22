"""The low-volume NBA plan (mike, 2026-11-22: "yes for now").

NBA bets only the three game-total over models, once both teams have played 20 games and at most ten
a week across the three, and the first-quarter spread. The prop models, first basket, the in-play
first-half spread and the first-quarter moneyline are paused. Evidence:
data/local/research/nba_research/reassess/studies/2026-11-21-stake-tiers/RESULT.md.
"""
import inspect

import config
import models.nba_first_half_total_luck as fh
import models.nba_team_total_luck as tt
import models.nba_total_luck as tl
from scripts import nba_game_totals_door as door

PAUSED = ("nba_prop_projection", "nba_prop_market", "nba_prop_first_basket",
          "nba_live_spread_q12", "nba_q1_trend_ml")
LIVE = ("nba_total_luck", "nba_first_half_total_luck", "nba_team_total_luck", "nba_q1_trend")


def test_the_five_are_paused_and_the_four_bet():
    for m in PAUSED:
        assert m in config.PAUSED_MODELS, m
    for m in LIVE:
        assert m not in config.PAUSED_MODELS, m


def test_every_game_total_model_waits_twenty_games():
    assert tl.LIVE_MIN_GAMES == 20
    for mod in (tl, tt, fh):
        assert inspect.signature(mod.decide).parameters["min_games"].default == 20, mod.__name__


def test_a_week_runs_monday_to_sunday_by_game_date():
    assert door.week_of("NBA_2026-12-07_BOS_NYK") == "2026-12-07"      # a Monday
    assert door.week_of("NBA_2026-12-13_BOS_NYK") == "2026-12-07"      # the Sunday after
    assert door.week_of("NBA_2026-12-14_BOS_NYK") == "2026-12-14"


class _Conn:
    def __init__(self, ids):
        self.ids, self.sql = ids, []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        ids = self.ids

        class _R:
            def fetchall(self_inner):
                return [(g, None) for g in ids] + [("NBA_2026-12-09_V_W", "VOID")]
        return _R()


def test_the_cap_counts_the_week_and_fills_at_ten():
    week = [f"NBA_2026-12-0{d}_A{i}_B{i}" for d in (7, 8, 9) for i in range(3)]   # 9 bets this week
    conn = _Conn(week + ["NBA_2026-12-15_X_Y"])                                   # and 1 the next
    cap = door.WeeklyCap(conn, ["NBA_2026-12-10_C_D"])
    sql, params = conn.sql[0]
    assert "signal_type = 'BET'" in sql
    assert params[0] == list(door.MODEL_IDS) and params[1:] == ("2026-12-07", "2026-12-13")
    assert not cap.full("NBA_2026-12-10_C_D")            # 9 written (a VOIDed tenth not counted): allowed
    cap.add("NBA_2026-12-10_C_D")
    assert cap.full("NBA_2026-12-11_E_F")                 # 10 written: the 11th is refused
    assert not cap.full("NBA_2026-12-14_G_H")             # a new week starts empty of this week's bets
    assert cap.reason("NBA_2026-12-11_E_F") == "weekly_cap:10_a_week_from_2026-12-07"


def test_each_game_total_card_consults_the_cap_before_it_writes_a_bet():
    import scripts.nba_first_half_total_luck_card as fhc
    import scripts.nba_team_total_luck_card as ttc
    import scripts.nba_total_luck_card as tlc
    for card in (tlc, fhc, ttc):
        src = inspect.getsource(card.publish)
        assert "door.WeeklyCap(conn, gids)" in src, card.__name__
        assert "cap.full(d.game_id)" in src and "cap.add(d.game_id)" in src, card.__name__
