"""
Tests for the UFC phantom-event filter in odds_ingestor (session 116).

The Odds API's mma_mixed_martial_arts feed lists every promotion; ufcstats
(our only results source) covers UFC only, so fights where NEITHER fighter is
UFC-known can never score — they used to accumulate as phantom NULL-score
games rows (session 96b) and trip the health check's missing-finals WARN.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.odds_ingestor import (
    _filter_ufc_phantom,
    _is_known_ufc_matchup,
)

KNOWN = {"islam-makhachev", "ian-garry", "neil-magny", "edson-barboza"}


def _game(game_id):
    return {"game_id": game_id, "sport": "UFC"}


def _odds(game_id, market="h2h"):
    return {"game_id": game_id, "market": market}


class TestIsKnownUfcMatchup:
    def test_both_known(self):
        assert _is_known_ufc_matchup(
            "UFC_2026-08-15_ian-garry_islam-makhachev", KNOWN)

    def test_one_known_kept(self):
        # Real UFC debutant vs a veteran — kept via the veteran.
        assert _is_known_ufc_matchup(
            "UFC_2026-08-15_some-debutant_neil-magny", KNOWN)

    def test_neither_known_dropped(self):
        # The 8/11 Contender Series card pattern.
        assert not _is_known_ufc_matchup(
            "UFC_2026-08-11_mridul-saikia_bilal-hasan", KNOWN)

    def test_empty_slug_set_fails_open(self):
        assert _is_known_ufc_matchup(
            "UFC_2026-08-11_mridul-saikia_bilal-hasan", set())

    def test_unexpected_shape_fails_open(self):
        assert _is_known_ufc_matchup("MLB_2026-08-11_NYY_BOS", KNOWN)
        assert _is_known_ufc_matchup("garbage", KNOWN)


class TestFilterUfcPhantom:
    def test_drops_phantom_and_its_odds(self):
        games = [
            _game("UFC_2026-08-15_ian-garry_islam-makhachev"),
            _game("UFC_2026-08-11_mridul-saikia_bilal-hasan"),
        ]
        odds = [
            _odds("UFC_2026-08-15_ian-garry_islam-makhachev"),
            _odds("UFC_2026-08-11_mridul-saikia_bilal-hasan"),
            _odds("UFC_2026-08-11_mridul-saikia_bilal-hasan", market="totals"),
        ]
        kept_games, kept_odds, dropped = _filter_ufc_phantom(games, odds, KNOWN)
        assert dropped == 1
        assert [g["game_id"] for g in kept_games] == [
            "UFC_2026-08-15_ian-garry_islam-makhachev"]
        # No orphan odds rows — an odds insert for a filtered game would
        # FK-violate and kill the whole UFC batch.
        assert all(o["game_id"] == "UFC_2026-08-15_ian-garry_islam-makhachev"
                   for o in kept_odds)

    def test_empty_slugs_is_a_noop(self):
        games = [_game("UFC_2026-08-11_mridul-saikia_bilal-hasan")]
        odds = [_odds("UFC_2026-08-11_mridul-saikia_bilal-hasan")]
        kept_games, kept_odds, dropped = _filter_ufc_phantom(games, odds, set())
        assert dropped == 0
        assert kept_games == games and kept_odds == odds
