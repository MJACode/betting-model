"""The low-volume NBA plan (mike, 2026-11-22: "yes for now").

NBA bets only the three shooting-luck game-total models (full-game over, first-half over, home
team-total under), once both teams have played 20 games and at most ten
a week across the three, the first-quarter spread, and first basket (kept live: mike, 2026-11-22,
"Keep the 1st basket model though"). The two stat-prop models, the in-play first-half spread and the
first-quarter moneyline are paused. Evidence:
data/local/research/nba_research/reassess/studies/2026-11-21-stake-tiers/RESULT.md.
"""
import inspect

import config
import models.nba_first_half_total_luck as fh
import models.nba_team_total_luck as tt
import models.nba_total_luck as tl
from scripts import nba_game_totals_door as door

PAUSED = ("nba_prop_projection", "nba_prop_market", "nba_live_spread_q12", "nba_q1_trend_ml")
# First basket stays live (mike, 2026-11-22: "Keep the 1st basket model though").
LIVE = ("nba_total_luck", "nba_first_half_total_luck", "nba_team_total_luck", "nba_q1_trend",
        "nba_prop_first_basket")


def test_the_four_are_paused_and_the_five_bet():
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


def test_a_paused_nba_prop_card_marks_every_row_it_writes():
    """The prop cards keep running while paused (as every rule card does); each row they write carries
    config.PAUSED_NOTE, the marker every publisher and record query keys on, so a bet written while
    paused is never posted and never counted (the UX review of PR #1580 found the marker missing)."""
    import scripts.nba_first_basket_card as fbc
    import scripts.nba_prop_market_card as mkc
    import scripts.nba_prop_projection_card as pjc
    from tests.test_nba_prop_market import _bet
    (row,) = mkc.pick_rows([_bet()], bankroll=1000.0)
    assert row["downgrade_reason"] == config.PAUSED_NOTE
    for card in (mkc, pjc, fbc):
        assert "downgrade_reason" in card._COLS, card.__name__
        # nba_prop_market_card.pick_rows takes the id it writes under (its own by default, or the
        # 10-hour paper card's, 2026-11-26), so its marker is read under that id.
        marker = ('"downgrade_reason": _pause_note(model_id)' if card is mkc
                  else '"downgrade_reason": _pause_note(MODEL_ID)')
        assert marker in inspect.getsource(card.pick_rows), card.__name__
