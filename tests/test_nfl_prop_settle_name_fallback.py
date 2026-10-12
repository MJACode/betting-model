"""An NFL prop settles on the player who played, not on his spelling.

2026-09-17 DET@BUF: "Joshua Palmer Under 1.5 Rec (MGM)" and "Joshua Palmer
Under 11.5 Rec Yds (betrivers)" settled NO_ACTION because the stat log spells
him "Josh Palmer". He played (43 receiving yards).
"""
from tracking.paper_tracker import _nfl_name_fallback

G = "NFL_2026_02_DET_BUF"


def _row(name, rec=1, yds=43.0):
    return {"player_name": name, "game_id": G, "receptions": rec, "receiving_yards": yds}


def test_a_first_name_the_stat_log_spells_differently_still_matches():
    actuals = {("joshpalmer", G): _row("Josh Palmer"),
               ("joshallen", G): _row("Josh Allen", 0, 0.0)}
    hit = _nfl_name_fallback(actuals, G, "Joshua Palmer")
    assert hit is not None and hit["player_name"] == "Josh Palmer"


def test_two_candidates_is_a_miss_not_a_guess():
    actuals = {("joshpalmer", G): _row("Josh Palmer"),
               ("jamespalmer", G): _row("James Palmer")}
    assert _nfl_name_fallback(actuals, G, "Joshua Palmer") is None


def test_another_game_and_another_initial_never_match():
    actuals = {("joshpalmer", "NFL_2026_02_OTHER"): _row("Josh Palmer"),
               ("kpalmer", G): _row("Kyle Palmer")}
    assert _nfl_name_fallback(actuals, G, "Joshua Palmer") is None
    assert _nfl_name_fallback(actuals, G, None) is None
    assert _nfl_name_fallback(actuals, G, "Palmer") is None
