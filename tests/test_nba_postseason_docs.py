"""What the docs say about nba_prop_market on the play-in, playoffs and Cup final.

A claim here is what a person acts on when the first of these bets lands, so each one is pinned to
the thing it describes where it can be: the rest inputs are run through the model's own code, and the
report's query is run on a real Postgres (tests/test_nba_postseason_pg.py). The rest are text checks
on the claim itself, because the number behind them comes from research files outside the repo.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_props as nb  # noqa: E402


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _paragraph(text: str, starts: str) -> str:
    """The paragraph that begins with `starts`, up to the next blank line."""
    at = text.index(starts)
    end = text.find("\n\n", at)
    return text[at:end if end >= 0 else None]


# ── what a Cup final's row changes ───────────────────────────────────────────

_COLS = ["game_id", "season", "game_date", "home_team", "away_team", "commence_time", "game_type"]
_SEMI = ("NBA_2026-12-08_NYK_BOS", 2027, "2026-12-08", "BOS", "NYK", "2026-12-09T00:00:00+00:00", "regular")
_NEXT = ("NBA_2026-12-12_NYK_MIA", 2027, "2026-12-12", "MIA", "NYK", "2026-12-13T01:30:00+00:00", "regular")
_FINAL = ("NBA_2026-12-11_NYK_OKC", 2027, "2026-12-11", "OKC", "NYK", "2026-12-12T01:00:00+00:00", "cup_final")


def _knicks_next_game(final_has_a_row: bool) -> dict[str, float]:
    games = pd.DataFrame([_SEMI, _NEXT, *([_FINAL] if final_has_a_row else [])], columns=_COLS).drop(columns="game_type")
    sched = pd.DataFrame([_SEMI, _NEXT, _FINAL], columns=_COLS)[["game_id", "season", "game_date", "game_type",
                                                                 "commence_time"]]
    t = nb.team_games({"nba_games": games, "nba_schedule": sched, "nba_player_game_adv": pd.DataFrame({"game_id": []})})
    r = t[(t.team == "NYK") & (t.game_id == _NEXT[0])].iloc[0]
    return {k: float(r[k]) for k in ("rest", "b2b", "g4d", "road_trip")}


def test_a_cup_final_row_changes_the_finalists_rest_in_the_projection_model():
    """The doc's numbers, through the model's own code. These columns reach the model (nb.SCHED)."""
    assert _knicks_next_game(False) == {"rest": 4.0, "b2b": 0.0, "g4d": 1.0, "road_trip": 2.0}
    assert _knicks_next_game(True) == {"rest": 1.0, "b2b": 1.0, "g4d": 2.0, "road_trip": 3.0}
    assert {"rest", "b2b", "g4d", "road_trip", "opp_rest", "opp_b2b"} <= set(nb.SCHED)


def test_the_docs_no_longer_say_these_games_change_no_bet():
    sport = _read("docs/sports/nba.md")
    assert "changes no bet" not in sport
    para = _paragraph(sport, "**One regular-season input does move")
    for said in ("nba_prop_projection", "rest 4 becomes 1", "about two teams a season", "mike's call"):
        assert said in para, said
    follow = _read("docs/followups.md")
    assert "it changes no bet" not in follow
    assert "should the Cup final count toward a finalist's rest?" in follow


# ── the neutral-court read ───────────────────────────────────────────────────

def test_the_first_neutral_court_game_has_its_read_written_down():
    """The feed's id for this game is the first evidence on whether it reverses a neutral court, and a
    regular-season game is where a stranded bet would land first."""
    follow = _read("docs/followups.md")
    at = follow.index("a reversed row on a neutral-court regular-season game can strand a bet")
    entry = follow[at:follow.index("\n## ", at)]
    for said in ("NBA_2026-11-07_DEN_IND", "NBA_2026-11-07_IND_DEN", "11-05 to 11-07", "read-only",
                 "flipped_id", "match_game", "listed_twin", "Updated-By: mike"):
        assert said in entry, said


# ── the report ───────────────────────────────────────────────────────────────

def report_sql() -> str:
    """The query docs/thresholds.md gives for reporting these bets apart."""
    text = _read("docs/thresholds.md")
    at = text.index("**To report these bets apart.**")
    m = re.search(r"```sql\n(.*?)```", text[at:], re.S)
    assert m, "the report's query has gone"
    return m.group(1)


def test_the_report_counts_only_graded_bets_and_does_not_read_flat_risk():
    sql = report_sql()
    assert "count(*) AS bets" not in sql and "profit_flat" not in sql
    assert "count(*) FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH')) AS bets" in sql


def test_the_doc_prints_the_flat_risk_figure_beside_the_one_the_query_reproduces():
    text = _read("docs/thresholds.md")
    para = _paragraph(text, "**To report these bets apart.**")
    assert "+23.36" in para and "+21.66" in para and "stake_for" in para


# ── which population the card decides at ─────────────────────────────────────

@pytest.mark.parametrize("rel", ["docs/thresholds.md", "models/nba_prop_market.py"])
def test_the_lead_the_card_decides_at_is_stated_beside_the_pooled_figure(rel):
    text = _read(rel)
    flat = " ".join(text.split())
    assert "+9.71%" in flat, "the pooled figure has gone"
    assert "+3.23%" in flat and "139" in flat and "+4.34" in flat
    assert "population the card decides at" in flat
    assert "The second line is the live expectation" not in flat
    assert "Read the second row as the live expectation" not in flat
