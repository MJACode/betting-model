"""
Tests for the NCAAF QB box-score parser.

Two things here are load-bearing and silent when wrong:

  * `is_primary` -- our proxy for "the starter". If it picks the wrong passer
    (or flips between identical re-ingests) then every downstream continuity
    feature describes a QB who did not take the snaps, and nothing in aggregate
    metrics would reveal it.

  * stat-name reading. CFBD nests categories -> types -> athletes, and the
    parser must read by NAME at every level. Reading by index would map yards
    onto attempts the first time CFBD reorders a payload, and the numbers would
    still look plausible.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.cfbd_ingestor import (  # noqa: E402
    parse_qb_game_stats, _athlete_stats)


def _team(school, passers, rushers=None, home="home"):
    """passers: [(id, name, 'C/ATT', yds, td, int)]"""
    def typ(name, vals):
        return {"name": name, "athletes": [
            {"id": pid, "name": nm, "stat": v} for pid, nm, v in vals]}
    cats = [{"name": "passing", "types": [
        typ("C/ATT", [(p[0], p[1], p[2]) for p in passers]),
        typ("YDS",   [(p[0], p[1], p[3]) for p in passers]),
        typ("TD",    [(p[0], p[1], p[4]) for p in passers]),
        typ("INT",   [(p[0], p[1], p[5]) for p in passers]),
    ]}]
    if rushers:
        cats.append({"name": "rushing", "types": [
            typ("CAR", [(r[0], r[1], r[2]) for r in rushers]),
            typ("YDS", [(r[0], r[1], r[3]) for r in rushers]),
            typ("TD",  [(r[0], r[1], r[4]) for r in rushers]),
        ]})
    return {"school": school, "homeAway": home, "categories": cats}


def _payload(teams, cfbd_id=101):
    return [{"id": cfbd_id, "teams": teams}]


_IDMAP = {101: "NCAAF_2024-09-07_alabama_georgia"}
_META = {"NCAAF_2024-09-07_alabama_georgia": {
    "season": 2024, "week": 2, "season_type": "regular",
    "game_date": "2024-09-07"}}


def _parse(teams):
    return parse_qb_game_stats(_payload(teams), _IDMAP, _META)


# ── is_primary ────────────────────────────────────────────────────────────────

def test_primary_is_the_passer_with_most_attempts():
    rows = _parse([_team("Georgia", [
        ("1", "Starter", "18/30", "240", "2", "0"),
        ("2", "Backup",  "3/5",   "40",  "0", "1"),
    ])])
    prim = [r for r in rows if r["is_primary"]]
    assert len(prim) == 1
    assert prim[0]["player_name"] == "Starter"


def test_primary_is_attempts_not_yards():
    """
    A backup who comes in and rips two deep balls can out-gain the starter.
    Attempts is the participation signal; yards is performance.
    """
    rows = _parse([_team("Georgia", [
        ("1", "Starter", "12/25", "90",  "0", "2"),
        ("2", "Backup",  "4/6",   "180", "3", "0"),
    ])])
    assert [r["player_name"] for r in rows if r["is_primary"]] == ["Starter"]


def test_exactly_one_primary_per_team_and_both_teams_get_one():
    rows = _parse([
        _team("Georgia", [("1", "A", "20/30", "250", "1", "0")]),
        _team("Alabama", [("3", "C", "15/28", "200", "1", "1")], home="away"),
    ])
    for school in ("Georgia", "Alabama"):
        assert sum(r["is_primary"] for r in rows if r["team"] == school) == 1


def test_tie_break_is_stable_across_reingests():
    """
    Identical attempts AND yards. Without a deterministic final key the flag
    would flip between runs and the upsert would rewrite history each time.
    """
    a = [("1", "A", "10/20", "150", "1", "0"), ("2", "B", "10/20", "150", "1", "0")]
    first = _parse([_team("Georgia", a)])
    second = _parse([_team("Georgia", list(reversed(a)))])
    pid = lambda rs: [r["player_id"] for r in rs if r["is_primary"]]  # noqa: E731
    assert pid(first) == pid(second)


# ── stat extraction ───────────────────────────────────────────────────────────

def test_stats_are_read_by_name_not_position():
    reordered = _team("Georgia", [("1", "A", "18/30", "240", "2", "1")])
    reordered["categories"][0]["types"].reverse()
    r = _parse([reordered])[0]
    assert (r["attempts"], r["completions"]) == (30, 18)
    assert (r["pass_yards"], r["pass_td"], r["interceptions"]) == (240, 2, 1)


def test_rushing_is_joined_by_player_id():
    rows = _parse([_team(
        "Georgia",
        [("1", "QB", "18/30", "240", "2", "0")],
        rushers=[("1", "QB", "9", "55", "1"), ("7", "RB", "20", "130", "2")],
    )])
    qb = [r for r in rows if r["player_id"] == "1"][0]
    assert (qb["rush_att"], qb["rush_yards"], qb["rush_td"]) == (9, 55, 1)
    assert all(r["player_id"] != "7" for r in rows), "a non-passing RB is not a QB row"


def test_missing_rushing_leaves_nulls_not_zeros():
    """A fabricated 0 is indistinguishable from a QB who genuinely never ran."""
    r = _parse([_team("Georgia", [("1", "A", "18/30", "240", "1", "0")])])[0]
    assert r["rush_att"] is None and r["rush_yards"] is None


def test_metadata_is_taken_from_the_schedule_not_guessed():
    r = _parse([_team("Georgia", [("1", "A", "18/30", "240", "1", "0")])])[0]
    assert (r["season"], r["week"], r["game_date"]) == (2024, 2, "2024-09-07")
    assert r["game_id"] == "NCAAF_2024-09-07_alabama_georgia"
    assert r["opponent"] is None       # only one team in this payload


def test_opponent_is_resolved_from_the_other_team():
    rows = _parse([
        _team("Georgia", [("1", "A", "20/30", "250", "1", "0")]),
        _team("Alabama", [("3", "C", "15/28", "200", "1", "1")], home="away"),
    ])
    assert {r["team"]: r["opponent"] for r in rows} == {
        "Georgia": "Alabama", "Alabama": "Georgia"}


# ── robustness ────────────────────────────────────────────────────────────────

def test_game_missing_from_id_map_is_skipped_not_guessed():
    assert parse_qb_game_stats(
        _payload([_team("Georgia", [("1", "A", "18/30", "240", "1", "0")])],
                 cfbd_id=999), _IDMAP, _META) == []


def test_unparseable_attempts_drops_that_passer():
    rows = _parse([_team("Georgia", [
        ("1", "Real",  "18/30", "240", "2", "0"),
        ("2", "Junk",  "--",    "0",   "0", "0"),
    ])])
    assert [r["player_name"] for r in rows] == ["Real"]


def test_team_with_no_passing_category_yields_nothing():
    t = {"school": "Georgia", "homeAway": "home",
         "categories": [{"name": "kicking", "types": []}]}
    assert _parse([t]) == []


def test_empty_and_none_payloads_are_safe():
    assert parse_qb_game_stats(None, _IDMAP, _META) == []
    assert parse_qb_game_stats([], _IDMAP, _META) == []


def test_athlete_without_an_id_is_ignored():
    t = _team("Georgia", [("1", "A", "18/30", "240", "1", "0")])
    t["categories"][0]["types"][0]["athletes"].append({"name": "Ghost", "stat": "5/9"})
    assert len(_parse([t])) == 1


def test_athlete_stats_helper_is_category_scoped():
    t = _team("Georgia", [("1", "A", "18/30", "240", "1", "0")],
              rushers=[("1", "A", "9", "55", "1")])
    p = _athlete_stats(t, "passing")
    assert p["1"]["YDS"] == "240", "rushing yards must not overwrite passing yards"
    assert _athlete_stats(t, "rushing")["1"]["YDS"] == "55"
    assert _athlete_stats(t, "punting") == {}


def test_comp_att_uses_a_slash_not_a_dash():
    """
    Regression: the first implementation reused _split_ratio (dash-separated,
    for third downs) on 'C/ATT'. It returned (None, None) for every passer, so
    the table came out empty -- which reads as an API outage, not a bug.
    """
    from data.ingestors.cfbd_ingestor import _comp_att, _split_ratio
    assert _comp_att("18/30") == (18, 30)
    assert _split_ratio("18/30") == (None, None), "the dash splitter must not parse C/ATT"
    for junk in ("--", "", None, "x/y", 30):
        assert _comp_att(junk) == (None, None)
