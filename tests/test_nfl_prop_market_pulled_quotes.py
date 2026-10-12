"""A prop the book has pulled is not on the board (docs/nfl_edge_search.md §5).

The prop loader keeps each (game, player, market, book)'s latest row however
old it is. On 2026-09-09 hardrockbet stopped quoting Tyjae Spears' receptions
while it kept quoting the rest of the game, and nfl_prop_market locked
"Tyjae Spears Under 2.5 Rec (hardrockbet)" 66 hours later at the stale price.
"""
from models.nfl_prop_market import drop_pulled_quotes

G = "NFL_2026_02_TEN_LA"
M = "player_receptions"


def _q(ts, line=2.5):
    return {"line": line, "over_price": -110, "under_price": -110, "snapshot_at": ts}


def test_a_player_the_book_stopped_quoting_is_dropped():
    quotes = {
        (G, "tyjaespears", M, "hardrockbet"): _q("2026-09-09T22:25:59Z"),
        (G, "calvinridley", M, "hardrockbet"): _q("2026-09-12T16:25:05Z"),
        (G, "tyjaespears", M, "pinnacle"): _q("2026-09-12T16:25:05Z"),
    }
    kept, dropped = drop_pulled_quotes(quotes)
    assert dropped == 1
    assert (G, "tyjaespears", M, "hardrockbet") not in kept
    assert (G, "calvinridley", M, "hardrockbet") in kept
    # the other book still quoting him is untouched
    assert (G, "tyjaespears", M, "pinnacle") in kept


def test_a_book_on_its_own_cadence_is_not_penalised_inside_three_hours():
    quotes = {
        (G, "a", M, "pinnacle"): _q("2026-09-12T14:05:00Z"),
        (G, "b", M, "pinnacle"): _q("2026-09-12T14:05:00Z"),
        (G, "a", M, "draftkings"): _q("2026-09-12T16:25:05Z"),
    }
    kept, dropped = drop_pulled_quotes(quotes)
    assert dropped == 0 and len(kept) == 3


def test_a_whole_market_the_book_pulled_is_dropped():
    """The book still returns the game (another market is fresh) but no longer
    quotes receptions at all: every receptions row is the stale one."""
    quotes = {
        (G, "a", M, "betmgm"): _q("2026-09-12T08:25:05Z"),
        (G, "b", M, "betmgm"): _q("2026-09-12T08:25:05Z"),
        (G, "a", "player_reception_yds", "betmgm"): _q("2026-09-12T16:25:05Z"),
    }
    kept, dropped = drop_pulled_quotes(quotes)
    assert dropped == 2
    assert (G, "a", "player_reception_yds", "betmgm") in kept


def test_a_book_that_stopped_returning_the_game_is_dropped():
    quotes = {
        (G, "a", M, "hardrockbet"): _q("2026-09-09T22:25:59Z"),
        (G, "a", M, "draftkings"): _q("2026-09-12T16:25:05Z"),
    }
    kept, dropped = drop_pulled_quotes(quotes)
    assert dropped == 1 and (G, "a", M, "draftkings") in kept


def test_rows_from_one_fetch_minutes_apart_are_kept_and_a_line_move_is_not_a_pull():
    quotes = {
        (G, "a", M, "betmgm"): _q("2026-09-12 16:25:05+00:00"),
        (G, "b", M, "betmgm"): _q("2026-09-12T16:04:00+00:00", line=3.5),
        (G, "d", M, "betmgm"): {"line": 1.5, "snapshot_at": None},
    }
    kept, dropped = drop_pulled_quotes(quotes)
    assert dropped == 0 and len(kept) == 3
