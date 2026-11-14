"""Tennis settlement: how each book grades a retirement, and how a score reads.

The rules under test are each book's own (models/tennis_common.py cites them).
A grader that treats every book alike turns DraftKings' retirement rule into a
phantom edge or hides a real one, so each case is pinned.
"""
from models import tennis_common as tc


def test_archive_score_complete_match_lists_the_winner_first():
    r = tc.from_archive_score("6-3 3-6 7-6(4)")
    assert r.status == "complete"
    assert r.a_games == [6, 3, 7] and r.b_games == [3, 6, 6]
    assert r.total_games == 31
    assert r.sets_complete == 3


def test_a_super_tiebreak_counts_as_one_game():
    r = tc.from_archive_score("2-6 6-4 [11-9]")
    assert r.total_games == 6 + 4 + 1 + 2 + 6 + 0      # the match tiebreak is one game
    assert r.super_tb_last


def test_retirement_after_the_first_set():
    r = tc.from_archive_score("6-3 2-1 RET")
    assert r.status == "retired" and r.retired_side == "b"
    assert r.sets_complete == 1 and r.first_set_complete


def test_retirement_inside_the_first_set():
    r = tc.from_archive_score("3-1 RET")
    assert r.status == "retired" and not r.first_set_complete


def test_walkover_voids_every_book():
    r = tc.from_archive_score("W/O")
    for book in ("draftkings", "pinnacle", "fanduel", "williamhill_us", "betrivers"):
        assert tc.grade_moneyline(r, "a", book) == tc.VOID
        assert tc.grade_moneyline(r, "b", book) == tc.VOID


def test_draftkings_voids_a_bet_on_the_player_who_retires():
    r = tc.from_archive_score("6-3 2-1 RET")          # B retired after set one
    assert tc.grade_moneyline(r, "b", "draftkings") == tc.VOID
    assert tc.grade_moneyline(r, "a", "draftkings") == tc.WIN


def test_pinnacle_fanduel_betmgm_grade_the_retiring_player_a_loser():
    r = tc.from_archive_score("6-3 2-1 RET")
    for book in ("pinnacle", "fanduel", "betmgm"):
        assert tc.grade_moneyline(r, "b", book) == tc.LOSS
        assert tc.grade_moneyline(r, "a", book) == tc.WIN


def test_caesars_and_unread_books_void_any_retirement():
    r = tc.from_archive_score("6-3 2-1 RET")
    for book in ("williamhill_us", "betrivers", "fanatics", "hardrockbet"):
        assert tc.grade_moneyline(r, "a", book) == tc.VOID
        assert tc.grade_moneyline(r, "b", book) == tc.VOID


def test_retirement_before_the_first_set_voids_draftkings_too():
    r = tc.from_archive_score("3-1 RET")
    assert tc.grade_moneyline(r, "a", "draftkings") == tc.VOID
    assert tc.grade_moneyline(r, "a", "pinnacle") == tc.VOID


def test_draftkings_itf_match_voids_on_any_retirement():
    r = tc.from_archive_score("6-3 2-1 RET")
    assert tc.grade_moneyline(r, "a", "draftkings", itf=True) == tc.VOID


def test_totals_and_spreads_grade_completed_matches_and_push_on_the_number():
    r = tc.from_archive_score("6-4 6-4")
    assert tc.grade_total(r, 19.5, over=True) == tc.WIN
    assert tc.grade_total(r, 20.0, over=True) == tc.PUSH
    assert tc.grade_total(r, 20.5, over=False) == tc.WIN
    assert tc.grade_games_spread(r, "a", -3.5) == tc.WIN      # won by 4 games
    assert tc.grade_games_spread(r, "b", 3.5) == tc.LOSS
    assert tc.grade_games_spread(r, "a", -4.0) == tc.PUSH


def test_totals_void_on_a_retirement():
    r = tc.from_archive_score("6-3 2-1 RET")
    assert tc.grade_total(r, 20.5, over=False) == tc.VOID


def test_units_follow_the_published_stake():
    assert abs(tc.units(tc.WIN, 200) - 1.0) < 1e-9          # risk 0.5 to win 1
    assert abs(tc.units(tc.LOSS, 200) + 0.5) < 1e-9
    assert abs(tc.units(tc.LOSS, -150) + 1.5) < 1e-9
    assert abs(tc.units(tc.LOSS, -500) + 3.0) < 1e-9        # risk capped at 3
    assert abs(tc.units(tc.WIN, -500) - 0.6) < 1e-9
    assert tc.units(tc.VOID, -150) == 0.0


def test_name_key_ignores_order_case_and_accents():
    assert tc.name_key("Sun Fajing") == tc.name_key("Fajing Sun")
    assert tc.name_key("Alex de Minaur") == tc.name_key("Alex De Minaur")
    assert tc.name_key("Félix Auger-Aliassime") == tc.name_key("Felix Auger Aliassime")
