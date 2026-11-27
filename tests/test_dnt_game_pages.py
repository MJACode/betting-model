"""Dunks & Threes' free game pages (data/ingestors/dnt_game_pages.py): the pure pieces.

The payload shape is the one measured on 2026-11-27 (scripts/research_probe_dnt_free.py
--decode): a devalue-encoded node holding `game_info` (p_home_score, p_away_score,
win_prob) and `box` (one row a player; p_stl free, p_pts null without a subscription).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.dnt_game_pages as dnt  # noqa: E402


def test_their_ids_from_our_season_label():
    """Our label is the ENDING year (CLAUDE.md §4); their id carries the STARTING year."""
    assert dnt.dnt_ids(2024, upto=2) == [22300001, 22300002]
    assert dnt.dnt_ids(2025)[-1] == 22401230
    assert dnt.dnt_ids(2026)[1000 - 1] == 22501000
    assert dnt.dnt_ids(2027, upto=1) == [22600001]


def _encoded():
    """A devalue array as SvelteKit serves it: index 0 is the root, values are indices."""
    data = [
        {"game_info": 1, "box": 4, "has_access": 13},
        {"game_dt": 2, "home_alias": 3, "away_alias": 12, "p_home_score": 14, "p_away_score": 15,
         "win_prob": 16, "status_id": 17, "season": 18, "game_dttm": 19},
        "2024-03-20", "OKC",
        [5],
        {"player_id": 6, "player_name": 7, "p_stl": 8, "p_pts": -1, "stl": 9, "mp": 10,
         "status": 11},
        1628983, "Shai Gilgeous-Alexander", 1.74, 2, 33.1667, "ACTIVE",
        "UTA", 0, 125.646, 111.248, 0.889067, 3, 2024, "2024-03-20 20:00:00",
    ]
    return {"type": "data", "nodes": [{"type": "data", "data": [{"user": 1}, None]},
                                      {"type": "data", "data": data}]}


def test_the_page_node_is_decoded_and_a_missing_value_is_none():
    node = dnt.page_node(_encoded())
    assert node["game_info"]["p_home_score"] == 125.646
    assert node["game_info"]["home_alias"] == "OKC" and node["has_access"] == 0
    row = node["box"][0]
    assert row["p_stl"] == 1.74 and row["p_pts"] is None        # -1 is devalue's undefined


def test_a_game_matches_ours_by_date_and_both_teams_with_the_standard_aliases():
    by_date = {"2024-03-20": [{"game_id": "NBA_2024-03-20_UTA_OKC", "home": "OKC", "away": "UTA"},
                              {"game_id": "NBA_2024-03-20_SAS_GSW", "home": "GSW", "away": "SAS"}]}
    ours = {"OKC", "UTA", "GSW", "SAS"}
    assert dnt.match_game({"game_dt": "2024-03-20", "home_alias": "OKC", "away_alias": "UTA"},
                          by_date, ours) == "NBA_2024-03-20_UTA_OKC"
    assert dnt.match_game({"game_dt": "2024-03-20", "home_alias": "GS", "away_alias": "SA"},
                          by_date, ours) == "NBA_2024-03-20_SAS_GSW"
    # home and away swapped is a different game, never a match
    assert dnt.match_game({"game_dt": "2024-03-20", "home_alias": "UTA", "away_alias": "OKC"},
                          by_date, ours) is None
    assert dnt.match_game({"game_dt": "2024-03-21", "home_alias": "OKC", "away_alias": "UTA"},
                          by_date, ours) is None


def test_rows_keep_the_free_predictions_and_the_actuals():
    node = dnt.page_node(_encoded())
    game, players = dnt.rows_for(22301000, node, "NBA_2024-03-20_UTA_OKC")
    assert game["source"] == dnt.SOURCE and game["game_id"] == "NBA_2024-03-20_UTA_OKC"
    assert (game["p_home_score"], game["p_away_score"], game["win_prob"]) == (125.646, 111.248, 0.889067)
    assert game["status_id"] == 3 and game["season"] == 2024
    assert '"p_home_score": 125.646' in game["game_info"]          # kept whole
    (p,) = players
    assert p["player_id"] == 1628983 and p["p_stl"] == 1.74 and p["stl"] == 2.0
    assert p["pts"] is None and p["mp"] == 33.1667
    assert set(dnt.PLAYER_COLS) <= set(p)


def test_a_box_row_without_a_player_id_is_skipped():
    node = {"game_info": {"game_dt": "2024-03-20"}, "box": [{"player_name": "Team"}, None]}
    assert dnt.rows_for(1, node, None)[1] == []


def test_a_429_is_waited_out_on_the_same_page_and_the_wait_follows_retry_after():
    assert dnt.backoff_s("30", 1) == 30.0
    assert dnt.backoff_s(None, 1) == dnt.BACKOFF_S and dnt.backoff_s(None, 3) == dnt.BACKOFF_S * 4
    assert dnt.backoff_s(None, 20) == 900.0 and dnt.backoff_s("soon", 2) == dnt.BACKOFF_S * 2

    class _R:
        def __init__(self, code):
            self.status_code, self.headers = code, {"Retry-After": "1"}

    class _S:
        def __init__(self, codes):
            self.codes, self.asked = list(codes), []

        def get(self, url, **kw):
            self.asked.append(url)
            return _R(self.codes.pop(0))

    slept = []
    import data.ingestors.dnt_game_pages as mod
    orig = mod.time.sleep
    mod.time.sleep = slept.append
    try:
        s = _S([429, 429, 200])
        stats = {"http_429_waits": 0}
        r = dnt.get_page(s, 22300010, stats)
        assert r.status_code == 200 and len(set(s.asked)) == 1 and stats["http_429_waits"] == 2
        s = _S([429] * dnt.MAX_429)
        assert dnt.get_page(s, 22300011, {"http_429_waits": 0}) is None   # the run stops
    finally:
        mod.time.sleep = orig
    assert slept and all(x == 1.0 for x in slept)
