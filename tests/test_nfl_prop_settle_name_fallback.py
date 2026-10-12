"""An NFL prop settles on the player who played, not on his spelling -- and a
scratch is never graded on somebody else.

2026-09-17 DET@BUF: "Joshua Palmer Under 1.5 Rec (MGM)" and "Joshua Palmer
Under 11.5 Rec Yds (betrivers)" settled NO_ACTION because the stat log spells
him "Josh Palmer". He played (43 receiving yards).

The review of #920 measured the other side: with only surname + initial, 130
absences on the 2023-25 log matched a DIFFERENT player in the same game
(Ty Johnson -> Taron Johnson, Michael Wilson -> Marco Wilson), turning a void
into a WIN or LOSS.
"""
from tracking.paper_tracker import _nfl_name_fallback, _same_first_name

G = "NFL_2026_02_DET_BUF"


def _row(name, rec=1, yds=43.0):
    return {"player_name": name, "game_id": G, "receptions": rec, "receiving_yards": yds}


def _never(_k):
    return False


def test_a_first_name_the_stat_log_spells_differently_still_matches():
    actuals = {("joshpalmer", G): _row("Josh Palmer"),
               ("joshallen", G): _row("Josh Allen", 0, 0.0)}
    hit = _nfl_name_fallback(actuals, G, "Joshua Palmer", known_elsewhere=_never)
    assert hit is not None and hit["player_name"] == "Josh Palmer"


def test_a_scratched_player_is_not_graded_on_a_teammate_with_his_initial():
    """Ty Johnson did not play; Taron Johnson (a corner, 0 receptions) did."""
    actuals = {("taronjohnson", G): _row("Taron Johnson", 0, 0.0)}
    assert _nfl_name_fallback(actuals, G, "Ty Johnson", known_elsewhere=_never) is None
    actuals = {("marcowilson", G): _row("Marco Wilson", 0, 0.0)}
    assert _nfl_name_fallback(actuals, G, "Michael Wilson", known_elsewhere=_never) is None


def test_a_spelling_the_log_already_knows_is_a_scratch_not_a_spelling():
    """Keenan Allen has rows elsewhere under exactly that name, so his absence
    from this game is a DNP even though a 'K. Allen' played."""
    actuals = {("kenallen", G): _row("Ken Allen")}
    assert _nfl_name_fallback(actuals, G, "Kenneth Allen",
                              known_elsewhere=lambda k: k == "kennethallen") is None
    assert _nfl_name_fallback(actuals, G, "Kenneth Allen", known_elsewhere=_never) is not None


def test_two_candidates_is_a_miss_not_a_guess():
    actuals = {("joshpalmer", G): _row("Josh Palmer"),
               ("joshuapalmer2", G): _row("Josh. Palmer")}
    assert _nfl_name_fallback(actuals, G, "Joshua Palmer", known_elsewhere=_never) is None


def test_another_game_and_another_initial_never_match():
    actuals = {("joshpalmer", "NFL_2026_02_OTHER"): _row("Josh Palmer"),
               ("kpalmer", G): _row("Kyle Palmer")}
    assert _nfl_name_fallback(actuals, G, "Joshua Palmer", known_elsewhere=_never) is None
    assert _nfl_name_fallback(actuals, G, None) is None
    assert _nfl_name_fallback(actuals, G, "Palmer") is None


def test_first_name_rule():
    assert _same_first_name("josh", "joshua")
    assert _same_first_name("matt", "matthew")
    assert _same_first_name("kenny", "kenneth")
    assert not _same_first_name("ty", "taron")
    assert not _same_first_name("michael", "marco")
    assert not _same_first_name("david", "danthony")
