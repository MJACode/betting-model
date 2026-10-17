"""Parsing and derivation rules of data/ingestors/nba_public_splits_ingestor.py.

The fixtures are cut from real Action Network responses fetched 2026-10-16
(HOU @ PHI 2024-01-15, the 2023-24 opening-night v2 zero pairs, tonight's
in-progress preseason games). No network, no database.
"""

from datetime import datetime, timezone

import pytest

from data.ingestors import nba_public_splits_ingestor as ing

KNOWN = {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
         "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
         "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"}


def _entry(kind, side, value, odds, tix, money, live=False):
    return {"type": kind, "side": side, "value": value, "odds": odds,
            "is_live": live, "book_id": 15,
            "bet_info": {"tickets": {"value": 0, "percent": tix},
                         "money": {"value": 0, "percent": money}}}


def _v2_game(entries, *, start="2024-01-15T18:00:00.000Z", season=2023,
             home=("PHI", "Philadelphia 76ers"), away=("HOU", "Houston Rockets"),
             gid=205736, gtype="reg", num_bets=32405):
    market = {"moneyline": [], "spread": [], "total": []}
    for e in entries:
        market[e["type"]].append(e)
    return {"id": gid, "start_time": start, "season": season, "type": gtype,
            "status": "complete", "num_bets": num_bets,
            "home_team_id": 1, "away_team_id": 2,
            "teams": [{"id": 1, "abbr": home[0], "full_name": home[1]},
                      {"id": 2, "abbr": away[0], "full_name": away[1]}],
            "markets": {"15": {"event": market}}}


# The real HOU @ PHI 2024-01-15 consensus split (v2).
HOU_PHI = [
    _entry("moneyline", "away", 0, 285, 5, 9),
    _entry("moneyline", "home", 0, -360, 95, 91),
    _entry("spread", "home", -8.5, -110, 37, 49),
    _entry("spread", "away", 8.5, -110, 63, 51),
    _entry("total", "over", 228.5, -112, 41, 64),
    _entry("total", "under", 228.5, -108, 59, 36),
]

INDEX = {("2024-01-15", "HOU", "PHI"): ("NBA_2024-01-15_HOU_PHI", 2024),
         ("2024-01-15", "OKC", "LAL"): ("NBA_2024-01-15_OKC_LAL", 2024)}


# ── percentages ───────────────────────────────────────────────────────────────

def test_a_one_percent_side_is_not_inflated_to_100():
    """The MLB parser's fractional rule would turn 1 into 100."""
    assert ing.an_pct(1) == 1.0
    assert ing.an_pct(0) == 0.0
    assert ing.an_pct(100) == 100.0
    assert ing.an_pct(37) == 37.0


@pytest.mark.parametrize("raw", [None, -1, 100.5, "x", True, {}])
def test_out_of_range_or_junk_percentages_are_refused(raw):
    assert ing.an_pct(raw) is None


# ── pair validation ───────────────────────────────────────────────────────────

def test_a_zero_zero_pair_is_missing_not_zero():
    assert ing.clean_pair(0.0, 0.0) == (None, None, "missing")


def test_a_valid_pair_sums_to_100_within_rounding():
    assert ing.clean_pair(65.0, 35.0) == (65.0, 35.0, "ok")
    assert ing.clean_pair(50.0, 49.0) == (50.0, 49.0, "ok")
    assert ing.clean_pair(100.0, 0.0) == (100.0, 0.0, "ok")


def test_a_pair_that_does_not_sum_to_100_is_dropped():
    assert ing.clean_pair(60.0, 30.0) == (None, None, "bad_sum")


def test_a_lone_side_is_kept_as_served():
    assert ing.clean_pair(None, 40.0) == (None, 40.0, "one_side")


def test_v2_opening_night_zero_pairs_produce_no_rows():
    """2023-10-24: v1 holds 65/35, v2 serves 0/0 on every side."""
    zeros = [_entry(e["type"], e["side"], e["value"], e["odds"], 0, 0) for e in HOU_PHI]
    rows, info = ing.build_rows(_v2_game(zeros), "v2", INDEX, KNOWN,
                                capture_kind=ing.ARCHIVE, fetched_at="t")
    assert rows == []
    assert info["match_kind"] == "exact"


# ── dates and seasons ────────────────────────────────────────────────────────

def test_a_late_west_coast_tip_belongs_to_the_previous_et_date():
    assert ing.et_game_date("2024-01-16T03:30:00.000Z") == "2024-01-15"
    assert ing.et_game_date("2024-01-15T18:00:00.000Z") == "2024-01-15"
    assert ing.et_game_date("2024-07-01T03:59:00Z") == "2024-06-30"    # EDT


def test_the_season_comes_from_our_games_row_not_action_network():
    """AN labels 2023-24 as 2023 (start year); ours is 2024 (end year)."""
    game = _v2_game(HOU_PHI, season=2023)
    rows, info = ing.build_rows(game, "v2", INDEX, KNOWN,
                                capture_kind=ing.ARCHIVE, fetched_at="t")
    assert info["an_season"] == 2023
    assert {r["season"] for r in rows} == {2024}
    assert {r["game_id"] for r in rows} == {"NBA_2024-01-15_HOU_PHI"}


def test_a_late_tip_matches_its_et_dated_game_id():
    game = _v2_game(HOU_PHI, start="2024-01-16T03:30:00.000Z",
                    home=("LAL", "Los Angeles Lakers"),
                    away=("OKC", "Oklahoma City Thunder"))
    rows, info = ing.build_rows(game, "v2", INDEX, KNOWN,
                                capture_kind=ing.ARCHIVE, fetched_at="t")
    assert info["game_id"] == "NBA_2024-01-15_OKC_LAL"


# ── v2 parsing ────────────────────────────────────────────────────────────────

def test_v2_values_land_on_the_right_side():
    sides = ing.parse_v2_sides(_v2_game(HOU_PHI))
    assert sides[("h2h", "home")] == {"value": None, "odds": -360,
                                      "tickets": 95.0, "money": 91.0}
    assert sides[("spreads", "away")] == {"value": 8.5, "odds": -110,
                                          "tickets": 63.0, "money": 51.0}
    assert sides[("totals", "under")]["tickets"] == 59.0


@pytest.mark.parametrize("live_first", [True, False])
def test_live_entries_of_an_in_progress_game_are_ignored(live_first):
    """In play, AN serves a live 0/0 entry beside the pre-game one."""
    live = [_entry("moneyline", "home", 0, -600, 0, 0, live=True),
            _entry("moneyline", "away", 0, 350, 0, 0, live=True)]
    entries = live + HOU_PHI if live_first else HOU_PHI + live
    sides = ing.parse_v2_sides(_v2_game(entries))
    assert sides[("h2h", "home")]["tickets"] == 95.0
    assert sides[("h2h", "home")]["odds"] == -360


# ── v1 parsing ────────────────────────────────────────────────────────────────

V1_ODDS = {
    "book_id": 15, "type": "game", "inserted": "2024-01-15T18:14:50.582246+00:00",
    "ml_away": 285, "ml_home": -360, "ml_away_public": 5, "ml_home_public": 95,
    "ml_away_money": 9, "ml_home_money": 91,
    "spread_away": 8.5, "spread_home": -8.5, "spread_away_line": -110,
    "spread_home_line": -110, "spread_away_public": 63, "spread_home_public": 37,
    "spread_away_money": 51, "spread_home_money": 49,
    "total": 228.5, "over": -112, "under": -108,
    "total_over_public": 41, "total_under_public": 59,
    "total_over_money": 64, "total_under_money": 36, "num_bets": 32405,
}


def _v1_game(odds_rows):
    g = _v2_game([])
    g.pop("markets")
    g["odds"] = odds_rows
    return g


def test_v1_flat_fields_map_to_market_side_and_metric():
    sides = ing.parse_v1_sides(_v1_game([{**V1_ODDS, "book_id": 30}, V1_ODDS]))
    assert sides[("h2h", "away")] == {"value": None, "odds": 285,
                                      "tickets": 5.0, "money": 9.0}
    assert sides[("spreads", "home")] == {"value": -8.5, "odds": -110,
                                          "tickets": 37.0, "money": 49.0}
    assert sides[("totals", "over")] == {"value": 228.5, "odds": -112,
                                         "tickets": 41.0, "money": 64.0}
    assert sides[("totals", "under")]["odds"] == -108


def test_v1_reads_only_the_consensus_book():
    other = {**V1_ODDS, "book_id": 30, "ml_home_public": 1, "ml_away_public": 99}
    assert ing.parse_v1_sides(_v1_game([other])) == {}


def test_v1_inserted_lag_is_minutes_after_the_listed_start():
    assert ing.inserted_minus_start_min(
        "2024-01-15T18:14:50.582246+00:00", "2024-01-15T18:00:00.000Z") == 14.8
    assert ing.inserted_minus_start_min(
        "2024-01-15T17:00:00+00:00", "2024-01-15T18:00:00.000Z") == -60.0
    assert ing.inserted_minus_start_min(None, "2024-01-15T18:00:00.000Z") is None


def test_v1_rows_carry_the_inserted_stamp_and_its_lag():
    rows, _ = ing.build_rows(_v1_game([V1_ODDS]), "v1", INDEX, KNOWN,
                             capture_kind=ing.ARCHIVE, fetched_at="t")
    assert len(rows) == 6
    assert {r["inserted_minus_start_min"] for r in rows} == {14.8}
    assert {r["num_bets"] for r in rows} == {32405}


# ── matching ──────────────────────────────────────────────────────────────────

def test_match_kinds():
    assert ing.match_game(INDEX, "2024-01-15", "HOU", "PHI")[2] == "exact"
    assert ing.match_game(INDEX, "2024-01-15", "PHI", "HOU")[2] == "swapped"
    assert ing.match_game(INDEX, "2024-01-16", "HOU", "PHI")[2] == "not_found"
    assert ing.match_game(INDEX, "2024-01-15", None, "PHI")[2] == "team_unknown"


def test_a_swapped_listing_flips_team_sides_into_our_orientation():
    """AN lists PHI away / HOU home; our row has PHI at home. PHI's 95% ML
    tickets must land on OUR home side, and PHI's -8.5 with it."""
    swapped = []
    for e in HOU_PHI:
        side = {"home": "away", "away": "home"}.get(e["side"], e["side"])
        swapped.append({**e, "side": side})
    game = _v2_game(swapped, home=("HOU", "Houston Rockets"),
                    away=("PHI", "Philadelphia 76ers"))
    rows, info = ing.build_rows(game, "v2", INDEX, KNOWN,
                                capture_kind=ing.ARCHIVE, fetched_at="t")
    assert info["match_kind"] == "swapped"
    by = {(r["market"], r["side"]): r for r in rows}
    assert by[("h2h", "home")]["tickets_pct"] == 95.0
    assert by[("spreads", "home")]["line_value"] == -8.5
    assert by[("totals", "over")]["tickets_pct"] == 41.0
    assert {(r["home_team"], r["away_team"]) for r in rows} == {("PHI", "HOU")}


def test_team_ids_come_from_the_abbr_then_the_full_name():
    assert ing.team_abbr({"abbr": "BKN", "full_name": "Brooklyn Nets"}, KNOWN) == "BKN"
    assert ing.team_abbr({"abbr": "BRK", "full_name": "x"}, KNOWN) == "BKN"
    assert ing.team_abbr({"abbr": "", "full_name": "LA Clippers"}, KNOWN) == "LAC"
    assert ing.team_abbr({"abbr": "XYZ", "full_name": "Seattle SuperSonics"}, KNOWN) is None


def test_an_unknown_team_is_reported_not_invented():
    game = _v2_game(HOU_PHI, away=("SEA", "Seattle SuperSonics"))
    rows, info = ing.build_rows(game, "v2", INDEX, KNOWN,
                                capture_kind=ing.ARCHIVE, fetched_at="t")
    assert info["match_kind"] == "team_unknown"
    assert {r["game_id"] for r in rows} == {None}


# ── capture kinds ─────────────────────────────────────────────────────────────

def test_archive_rows_carry_no_observation_time():
    rows, _ = ing.build_rows(_v2_game(HOU_PHI), "v2", INDEX, KNOWN,
                             capture_kind=ing.ARCHIVE, fetched_at="t")
    assert {r["observed_at"] for r in rows} == {None}
    assert {r["snapshot_key"] for r in rows} == {"archive"}


def test_poll_rows_are_keyed_by_their_fetch_time():
    t = "2026-10-21T22:00:00+00:00"
    rows, _ = ing.build_rows(_v2_game(HOU_PHI), "v2", INDEX, KNOWN,
                             capture_kind=ing.POLL, fetched_at=t, observed_at=t)
    assert {r["observed_at"] for r in rows} == {t}
    assert {r["snapshot_key"] for r in rows} == {t}


def test_the_poll_refuses_a_game_at_or_past_its_listed_start():
    now = datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc)
    games = [{"id": 1, "start_time": "2026-10-17T02:00:00.000Z"},   # at start
             {"id": 2, "start_time": "2026-10-17T01:00:00.000Z"},   # in play
             {"id": 3, "start_time": "2026-10-17T02:30:00.000Z"},   # upcoming
             {"id": 4, "start_time": "garbage"}]
    keep, started = ing.not_started(games, now)
    assert [g["id"] for g in keep] == [3]
    assert started == 3


def test_the_poll_skips_preseason_only_when_it_matches_nothing_of_ours():
    """AN labelled the rescheduled regular-season GSW @ UTA of 2024-02-15 'pre'."""
    assert ing.keep_for_poll({"an_game_type": "pre", "game_id": None}) is False
    assert ing.keep_for_poll({"an_game_type": "pre",
                              "game_id": "NBA_2024-02-15_GSW_UTA"}) is True
    assert ing.keep_for_poll({"an_game_type": "reg", "game_id": None}) is True
    assert ing.keep_for_poll({"an_game_type": "post", "game_id": None}) is True


# ── the write is idempotent ───────────────────────────────────────────────────

def test_the_conflict_target_is_the_unique_constraint():
    """ON CONFLICT DO NOTHING on exactly the UNIQUE columns is what makes a
    re-run write nothing already stored; a mismatch is a Postgres error."""
    key = "(an_game_id, market, side, endpoint, capture_kind, snapshot_key)"
    assert f"UNIQUE\n        {key}" in ing._CREATE_SQL
    assert f"ON CONFLICT {key}\nDO NOTHING" in ing._INSERT_SQL


def test_every_inserted_column_exists_in_the_table():
    rows, _ = ing.build_rows(_v2_game(HOU_PHI), "v2", INDEX, KNOWN,
                             capture_kind=ing.ARCHIVE, fetched_at="t")
    assert set(rows[0]) == set(ing.ROW_COLS)
    for col in ing.ROW_COLS:
        assert f"\n    {col} " in ing._CREATE_SQL, col
        assert f"%({col})s" in ing._INSERT_SQL, col
