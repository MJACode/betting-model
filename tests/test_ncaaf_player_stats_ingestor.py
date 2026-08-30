"""
Tests for the NCAAF player box-score parser (the mobile Stats-tab leaderboard).

The parser reads the SAME /games/players payload as the QB log, wider. Three
things are silent when wrong:

  * ONE ROW PER PLAYER. CFBD reports a player once per category he appears in,
    so a running quarterback is in both `passing` and `rushing`. Emitting a row
    per category would double-count him on the leaderboard and split his game
    log in half.

  * stat-name reading. Categories -> types -> athletes, read by NAME at every
    level. Reading by index maps yards onto attempts the first time CFBD
    reorders a payload, and the numbers still look plausible.

  * the all-zero skip. Kickers, punters and returners appear in categories this
    table does not store; kept, they would go 12-for-12 on an "at most N yards"
    board and bury the players actually in that market.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.cfbd_ingestor import (  # noqa: E402
    parse_player_game_stats, parse_qb_game_stats)


def _cat(name: str, types: dict) -> dict:
    """{'YDS': [(id, name, stat), ...]} -> one CFBD category block."""
    return {"name": name, "types": [
        {"name": tname, "athletes": [
            {"id": pid, "name": nm, "stat": val} for pid, nm, val in rows]}
        for tname, rows in types.items()]}


def _team(school: str, *categories: dict, home: str = "home") -> dict:
    return {"school": school, "homeAway": home, "categories": list(categories)}


def _payload(*teams: dict, cfbd_id: int = 101) -> list:
    return [{"id": cfbd_id, "teams": list(teams)}]


_IDMAP = {101: "NCAAF_2024-09-07_alabama_georgia"}
_META = {"NCAAF_2024-09-07_alabama_georgia": {
    "season": 2024, "week": 2, "season_type": "regular",
    "game_date": "2024-09-07"}}


def _parse(*teams: dict) -> list[dict]:
    return parse_player_game_stats(_payload(*teams), _IDMAP, _META)


_PASSING = _cat("passing", {
    "C/ATT": [("1", "Quinn Ewers", "18/30")],
    "YDS":   [("1", "Quinn Ewers", "240")],
    "TD":    [("1", "Quinn Ewers", "2")],
    "INT":   [("1", "Quinn Ewers", "1")],
})
_RUSHING = _cat("rushing", {
    "CAR": [("1", "Quinn Ewers", "4"), ("2", "Jonathon Brooks", "17")],
    "YDS": [("1", "Quinn Ewers", "-6"), ("2", "Jonathon Brooks", "104")],
    "TD":  [("1", "Quinn Ewers", "0"), ("2", "Jonathon Brooks", "1")],
})
_RECEIVING = _cat("receiving", {
    "REC": [("2", "Jonathon Brooks", "3"), ("3", "Xavier Worthy", "7")],
    "YDS": [("2", "Jonathon Brooks", "22"), ("3", "Xavier Worthy", "118")],
    "TD":  [("2", "Jonathon Brooks", "1"), ("3", "Xavier Worthy", "1")],
})


# ── One row per player ───────────────────────────────────────────────────────

def test_a_player_gets_one_row_across_every_category():
    rows = _parse(_team("Texas", _PASSING, _RUSHING, _RECEIVING))
    assert len(rows) == 3, [r["player_name"] for r in rows]
    assert len({r["player_id"] for r in rows}) == 3

    qb = next(r for r in rows if r["player_id"] == "1")
    assert qb["attempts"] == 30 and qb["completions"] == 18
    assert qb["passing_yards"] == 240 and qb["passing_tds"] == 2
    assert qb["interceptions"] == 1
    # ...and his rushing line is on the SAME row, not a second one.
    assert qb["carries"] == 4 and qb["rushing_yards"] == -6

    rb = next(r for r in rows if r["player_id"] == "2")
    assert rb["carries"] == 17 and rb["rushing_yards"] == 104
    assert rb["receptions"] == 3 and rb["receiving_yards"] == 22
    assert rb["rushing_tds"] == 1 and rb["receiving_tds"] == 1


def test_negative_rushing_yards_survive():
    """A sack is a rush attempt in NCAA scoring — the loss is real data."""
    rows = _parse(_team("Texas", _PASSING, _RUSHING))
    assert next(r for r in rows if r["player_id"] == "1")["rushing_yards"] == -6


def test_metadata_comes_from_the_schedule_not_the_box_score():
    rows = _parse(_team("Texas", _PASSING), _team("Michigan", _PASSING, home="away"))
    for r in rows:
        assert r["game_id"] == "NCAAF_2024-09-07_alabama_georgia"
        assert r["season"] == 2024 and r["week"] == 2
        assert r["game_date"] == "2024-09-07"
        assert r["season_type"] == "regular"
    assert {r["team"] for r in rows} == {"Texas", "Michigan"}
    assert {r["opponent"] for r in rows} == {"Texas", "Michigan"}
    texas = next(r for r in rows if r["team"] == "Texas")
    assert texas["opponent"] == "Michigan"


def test_a_game_missing_from_the_id_map_is_skipped_not_guessed():
    assert parse_player_game_stats(_payload(_team("Texas", _PASSING), cfbd_id=999),
                                   _IDMAP, _META) == []


# ── Defense ──────────────────────────────────────────────────────────────────

def test_defensive_halves_and_interceptions_are_kept_apart():
    """
    A shared tackle is charged as a half, and a defender's INT is a PICK — the
    `interceptions` category — not the `passing` INT, which is a pick THROWN.
    Collapsing the two would credit every quarterback with takeaways.
    """
    defense = _cat("defensive", {
        "TOT":   [("7", "Anthony Hill", "9.5")],
        "SOLO":  [("7", "Anthony Hill", "5")],
        "SACKS": [("7", "Anthony Hill", "1.5")],
        "TFL":   [("7", "Anthony Hill", "2.5")],
        "PD":    [("7", "Anthony Hill", "1")],
    })
    picks = _cat("interceptions", {"INT": [("7", "Anthony Hill", "1")]})
    rows = _parse(_team("Texas", _PASSING, defense, picks))
    lb = next(r for r in rows if r["player_id"] == "7")
    assert lb["def_tackles"] == 9.5 and lb["def_solo"] == 5.0
    assert lb["def_sacks"] == 1.5 and lb["def_tfl"] == 2.5
    assert lb["def_pd"] == 1
    assert lb["def_interceptions"] == 1
    assert lb["interceptions"] is None      # he threw none

    qb = next(r for r in rows if r["player_id"] == "1")
    assert qb["interceptions"] == 1         # thrown
    assert qb["def_interceptions"] is None  # not a takeaway


# ── The all-zero skip ────────────────────────────────────────────────────────

def test_a_player_with_nothing_we_track_is_skipped():
    """A kicker's only line is in a category this table does not store."""
    kicking = _cat("kicking", {
        "FG":  [("9", "Bert Auburn", "3/4")],
        "PTS": [("9", "Bert Auburn", "11")],
    })
    rows = _parse(_team("Texas", _PASSING, kicking))
    assert {r["player_id"] for r in rows} == {"1"}


def test_an_all_zero_line_is_skipped():
    """A receiver targeted but never caught one has a real zero row in CFBD."""
    zeros = _cat("receiving", {
        "REC": [("5", "A Decoy", "0")],
        "YDS": [("5", "A Decoy", "0")],
        "TD":  [("5", "A Decoy", "0")],
    })
    rows = _parse(_team("Texas", _PASSING, zeros))
    assert {r["player_id"] for r in rows} == {"1"}


def test_a_single_catch_survives_the_zero_filter():
    one = _cat("receiving", {
        "REC": [("5", "A Decoy", "1")],
        "YDS": [("5", "A Decoy", "0")],
        "TD":  [("5", "A Decoy", "0")],
    })
    rows = _parse(_team("Texas", one))
    assert {r["player_id"] for r in rows} == {"5"}


# ── Reading by name, and agreement with the QB log ───────────────────────────

def test_reordered_types_do_not_shuffle_stats_onto_each_other():
    shuffled = _cat("passing", {
        "INT":   [("1", "Quinn Ewers", "1")],
        "TD":    [("1", "Quinn Ewers", "2")],
        "YDS":   [("1", "Quinn Ewers", "240")],
        "C/ATT": [("1", "Quinn Ewers", "18/30")],
    })
    rows = _parse(_team("Texas", shuffled))
    qb = rows[0]
    assert (qb["completions"], qb["attempts"]) == (18, 30)
    assert qb["passing_yards"] == 240 and qb["passing_tds"] == 2


def test_both_parsers_read_the_same_passer_off_one_payload():
    """
    The two tables are filled from ONE fetch, so they must not disagree about
    what the passer did — that is the whole reason the fetch is shared.
    """
    payload = _payload(_team("Texas", _PASSING, _RUSHING, _RECEIVING))
    qb_rows = parse_qb_game_stats(payload, _IDMAP, _META)
    player_rows = parse_player_game_stats(payload, _IDMAP, _META)
    qb = next(r for r in qb_rows if r["player_id"] == "1")
    player = next(r for r in player_rows if r["player_id"] == "1")
    assert qb["attempts"] == player["attempts"]
    assert qb["completions"] == player["completions"]
    assert qb["pass_yards"] == player["passing_yards"]
    assert qb["pass_td"] == player["passing_tds"]
    assert qb["interceptions"] == player["interceptions"]
    assert qb["rush_yards"] == player["rushing_yards"]
    # The QB log keeps ONLY passers; the player log keeps everyone.
    assert {r["player_id"] for r in qb_rows} == {"1"}
    assert {r["player_id"] for r in player_rows} == {"1", "2", "3"}


def test_row_order_is_stable_across_re_ingests():
    payload = _payload(_team("Texas", _PASSING, _RUSHING, _RECEIVING))
    first = parse_player_game_stats(payload, _IDMAP, _META)
    second = parse_player_game_stats(payload, _IDMAP, _META)
    assert [r["player_id"] for r in first] == [r["player_id"] for r in second]


def test_empty_payload_is_a_clean_no_op():
    assert parse_player_game_stats(None, _IDMAP, _META) == []
    assert parse_player_game_stats([], _IDMAP, _META) == []
