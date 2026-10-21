"""Replacing a game's box score with NBA.com's (data/ingestors/nba_stats_ingestor
replace_game_boxes / boxes_to_repair).

nba_total_luck declines every later game of the season while any box is missing
or does not add up to its final score (models/nba_total_luck.missing_inputs).
The old remedy the card's log named, `--game-log-date <date>`, upserts every
game of the date on (player_id, game_id): a player the results ingestor stored
as 'espn:<id>' gets a second row under his NBA.com id and counts twice. The
repair replaces exactly the games named, deletes before it inserts, and writes
nothing for a game whose NBA.com box does not add up.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.nba_stats_ingestor as ing  # noqa: E402

G1 = "NBA_2026-11-14_NYK_BOS"      # NYK at BOS
G2 = "NBA_2026-11-14_MIA_ORL"      # same night, not named


def _logs(bos_pts=(60, 50), nyk_pts=(55, 45)):
    """NBA.com's league logs for two games on one night."""
    team = pd.DataFrame([
        {"GAME_ID": "0022600101", "TEAM_ABBREVIATION": "BOS", "TEAM_NAME": "Boston Celtics",
         "MATCHUP": "BOS vs. NYK", "PTS": sum(bos_pts), "GAME_DATE": "2026-11-14"},
        {"GAME_ID": "0022600101", "TEAM_ABBREVIATION": "NYK", "TEAM_NAME": "New York Knicks",
         "MATCHUP": "NYK @ BOS", "PTS": sum(nyk_pts), "GAME_DATE": "2026-11-14"},
        {"GAME_ID": "0022600102", "TEAM_ABBREVIATION": "ORL", "TEAM_NAME": "Orlando Magic",
         "MATCHUP": "ORL vs. MIA", "PTS": 100, "GAME_DATE": "2026-11-14"},
        {"GAME_ID": "0022600102", "TEAM_ABBREVIATION": "MIA", "TEAM_NAME": "Miami Heat",
         "MATCHUP": "MIA @ ORL", "PTS": 90, "GAME_DATE": "2026-11-14"},
    ])
    rows = []
    for gid, team_abbr, pts in (("0022600101", "BOS", bos_pts), ("0022600101", "NYK", nyk_pts),
                                ("0022600102", "ORL", (100,)), ("0022600102", "MIA", (90,))):
        for i, p in enumerate(pts):
            rows.append({"GAME_ID": gid, "PLAYER_ID": f"{team_abbr}{i}", "PLAYER_NAME": f"{team_abbr} {i}",
                         "TEAM_ABBREVIATION": team_abbr, "TEAM_NAME": "", "GAME_DATE": "2026-11-14",
                         "MIN": 30, "PTS": p, "REB": 5, "OREB": 1, "DREB": 4, "AST": 3, "STL": 1,
                         "BLK": 0, "TOV": 2, "FGM": 10, "FGA": 20, "FG3M": 3, "FG3A": 8,
                         "FTM": 4, "FTA": 5})
    return team, pd.DataFrame(rows)


class _Conn:
    def __init__(self, finals):
        self.finals, self.sql, self.inserted, self.commits, self.rollbacks = finals, [], [], 0, 0

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        self.sql.append((q, params))
        if q.startswith("SELECT game_id, season, home_team"):
            out = [(g, 2027, *v) for g, v in self.finals.items() if g in params[0]]
        elif q.startswith("SELECT player_id, is_starter"):
            out = [("BOS0", 1), ("espn:4433", 1)]
        else:
            out = []
        return type("R", (), {"fetchall": lambda self_: out})()

    def executemany(self, sql, rows):
        self.inserted.extend(rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _run(monkeypatch, finals, ids, **logs):
    team, player = _logs(**logs)
    monkeypatch.setattr(ing, "_fetch_league_game_log",
                        lambda season, kind: team if kind == "T" else player)
    monkeypatch.setattr(ing, "REQUEST_SLEEP", 0)
    conn = _Conn(finals)
    return ing.replace_game_boxes(ids, conn=conn), conn


def test_only_the_named_game_is_replaced_delete_first(monkeypatch):
    out, conn = _run(monkeypatch, {G1: ("BOS", "NYK", 110, 100), G2: ("ORL", "MIA", 100, 90)},
                     [G1])
    assert out == {"replaced": [G1], "refused": {}}
    deletes = [p for q, p in conn.sql if q.startswith("DELETE FROM nba_player_game_log")]
    assert deletes == [(G1,)], "the named game's rows go, and no other game's"
    assert {r["game_id"] for r in conn.inserted} == {G1}
    assert len(conn.inserted) == 4 and conn.commits == 1
    # the league log carries no starter flag: kept from the rows replaced
    assert {r["player_id"]: r["is_starter"] for r in conn.inserted}["BOS0"] == 1


def test_a_box_that_does_not_add_up_is_never_written(monkeypatch):
    """NBA.com's own box must equal the final stored in games, or the game is
    left exactly as it was and reported."""
    out, conn = _run(monkeypatch, {G1: ("BOS", "NYK", 112, 100)}, [G1])
    assert out["replaced"] == [] and "final is" in out["refused"][G1]
    assert not any(q.startswith("DELETE") for q, _ in conn.sql) and conn.inserted == []


def test_a_game_nba_com_does_not_list_is_refused(monkeypatch):
    out, conn = _run(monkeypatch, {"NBA_2026-11-14_LAL_GSW": ("GSW", "LAL", 100, 99)},
                     ["NBA_2026-11-14_LAL_GSW", "NBA_2026-11-14_XXX_YYY"])
    assert out["replaced"] == []
    assert set(out["refused"]) == {"NBA_2026-11-14_LAL_GSW", "NBA_2026-11-14_XXX_YYY"}
    assert conn.inserted == []


def test_the_season_repair_names_every_missing_or_wrong_box(monkeypatch):
    """boxes_to_repair uses the model's own definition (load_season, team_box,
    box_mismatches): a short box, a doubled player and a game with no box."""
    import scripts.nba_total_luck_card as card
    final = pd.DataFrame([
        {"game_id": g, "season": 2027, "game_date": "2026-11-14", "home_team": h,
         "away_team": a, "home_score": 100, "away_score": 90}
        for g, h, a in (("OK", "BOS", "NYK"), ("SHORT", "ORL", "MIA"), ("DOUBLE", "LAL", "GSW"),
                        ("NOBOX", "PHX", "DEN"))])
    rows = []
    for g, h, a in (("OK", "BOS", "NYK"), ("SHORT", "ORL", "MIA"), ("DOUBLE", "LAL", "GSW")):
        rows += [{"game_id": g, "team": h, "points": 100}, {"game_id": g, "team": a, "points": 90}]
    rows[2]["points"] = 91                                   # SHORT: ORL's box sums 91
    rows.append({"game_id": "DOUBLE", "team": "GSW", "points": 12})   # a player twice
    box = pd.DataFrame(rows)
    for c in ("fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att", "offensive_reb", "turnovers"):
        box[c] = 1
    monkeypatch.setattr(card, "load_season", lambda conn, s, before: (final, box, None))
    assert ing.boxes_to_repair(2027, conn=object()) == ["DOUBLE", "NOBOX", "SHORT"]


def test_the_card_s_decline_log_names_the_repair_not_the_date_load():
    src = (Path(__file__).parent.parent / "scripts" / "nba_total_luck_card.py").read_text(
        encoding="utf-8")
    assert "--repair-boxes" in src and "--game-log-date" not in src
