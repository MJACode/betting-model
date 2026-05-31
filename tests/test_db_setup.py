"""
test_db_setup.py — Tests for database schema creation and idempotency.

These tests run against an in-memory SQLite database using SCHEMA_SQL
(the legacy SQLite DDL kept in db_setup.py for this purpose).
The Postgres schema is in data/supabase_schema.sql and is tested via
integration tests that require a live DATABASE_URL connection.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from data.db_setup import SCHEMA_SQL


EXPECTED_TABLES = {
    "games", "odds", "injuries",
    "mlb_team_stats", "mlb_pitcher_stats", "mlb_bullpen_stats",
    "nhl_team_stats", "nhl_goalie_stats", "nhl_skater_stats",
    # WNBA stats (added for WNBA game + prop betting)
    "wnba_team_stats", "wnba_player_game_log",
    "picks", "model_registry", "pipeline_log",
    # Player-prop infrastructure (added sessions 14-19)
    "player_game_log", "player_prop_odds", "player_savant_stats",
    "umpires", "lineup_slots",
    # Live (in-play) betting (Phase 1 scaffolding)
    "live_game_state", "live_trigger_events",
    # PBP training corpus (Phase 2a)
    "plays",
    # SQLite auto-creates this for AUTOINCREMENT tables
    "sqlite_sequence",
}


def _get_columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_schema_creates_all_tables(db_conn):
    tables = {row[0] for row in db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert EXPECTED_TABLES == tables


def test_schema_is_idempotent(db_conn):
    """Running SCHEMA_SQL a second time must not raise."""
    db_conn.executescript(SCHEMA_SQL)
    db_conn.commit()
    tables = {row[0] for row in db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert EXPECTED_TABLES == tables


def test_games_table_columns(db_conn):
    cols = _get_columns(db_conn, "games")
    required = {
        "game_id", "sport", "season", "game_date", "home_team", "away_team",
        "home_score", "away_score", "home_win", "home_win_reg",
        "went_to_ot", "regulation_tie", "data_source",
    }
    assert required.issubset(cols)


def test_odds_table_columns(db_conn):
    cols = _get_columns(db_conn, "odds")
    required = {
        "game_id", "market", "bookmaker", "snapshot_type", "snapshot_at",
        "home_price", "away_price", "total_line", "over_price", "under_price",
    }
    assert required.issubset(cols)


def test_picks_table_columns(db_conn):
    cols = _get_columns(db_conn, "picks")
    required = {
        "game_id", "model_id", "sport", "game_date", "pick_side",
        "model_probability", "dk_implied_prob", "edge", "kelly_fraction",
        "recommended_bet", "signal_type", "result", "profit_flat", "profit_kelly",
    }
    assert required.issubset(cols)


def test_injuries_table_columns(db_conn):
    cols = _get_columns(db_conn, "injuries")
    required = {
        "sport", "team", "player_name", "status", "scenario",
        "severity_weight", "return_ramp_factor", "report_date",
    }
    assert required.issubset(cols)


def test_games_game_id_is_primary_key(db_conn):
    pk_info = db_conn.execute("PRAGMA table_info(games)").fetchall()
    pk_cols = {row[1] for row in pk_info if row[5] == 1}
    assert "game_id" in pk_cols
