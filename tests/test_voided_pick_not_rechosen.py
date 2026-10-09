"""A voided pick is never chosen again from the captured-signals table.

scripts/void_picks.py writes only to `picks`. The pick's row in
`opening_signals` (the capture taken when it was first a BET) stays, and two
public surfaces choose from that capture:

  * the free pick of the day (Discord's free channel; X mirrors the same pick)
  * the public parlay record on the app's Track Record screen

Until 2026-10-09 neither checked for a void. That mattered from the day mike
lifted the posted-pick lock ("Change the rule, void them"): the eight posted
NCAAF unders decided on DraftKings prices 15 to 28 days old were 3 of the 4
free-pick candidates for 2026-10-17 (measured that day, read-only).

These run the REAL producers' REAL SQL against sqlite, the same way
tests/test_live_publish_parity.py does, because the thing under test is the
WHERE clause. The one rewrite is the free pick's LATERAL join, which sqlite
cannot run: it only fetches display columns (when the pick was made, and its
best book and price), and it is replaced by a row of NULLs. Every condition
that decides WHICH signals are candidates is left exactly as written.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking import discord_notifier, parlay_track_record  # noqa: E402

DATE = "2026-10-17"
MODEL = "ncaaf_over_under"

_LATERAL = re.compile(r"LEFT JOIN LATERAL \(.*?\) pk ON TRUE", re.S)
_DISPLAY_ONLY = ("LEFT JOIN (SELECT NULL AS created_at, NULL AS best_book, "
                 "NULL AS best_odds) pk ON 1 = 1")


class _Conn:
    """sqlite behind the psycopg surface the producers use: %s -> ?, %% -> %."""

    def __init__(self, raw: sqlite3.Connection):
        self.raw = raw
        self.lateral_rewrites = 0

    def execute(self, sql, params=()):
        sql, n = _LATERAL.subn(_DISPLAY_ONLY, sql)
        self.lateral_rewrites += n
        return self.raw.execute(sql.replace("%%", "%").replace("%s", "?"), params)

    def commit(self):
        self.raw.commit()

    def close(self):
        pass


# (game_id, home, away, label, line, edge, the pick's condition_status)
GAMES = [
    ("NCAAF_2026-10-17_kansas_kansas-state", "Kansas State", "Kansas",
     "Kansas State vs Kansas Under 54.5", 54.5, 0.12, "VOID"),
    ("NCAAF_2026-10-17_north-carolina_duke", "Duke", "North Carolina",
     "Duke vs North Carolina Under 47.5", 47.5, 0.08, None),
    # nfl_pick_monitor writes health states to the same column on STANDING
    # picks. Only 'VOID' is a void, so this one must stay a candidate.
    ("NCAAF_2026-10-17_auburn_georgia", "Georgia", "Auburn",
     "Georgia vs Auburn Under 49.5", 49.5, 0.06, "DEGRADED"),
]


def _db() -> _Conn:
    raw = sqlite3.connect(":memory:")
    raw.executescript("""
        CREATE TABLE opening_signals (
            lock_key TEXT PRIMARY KEY, game_id TEXT, model_id TEXT, sport TEXT,
            game_date TEXT, player_id TEXT, pick_side TEXT, pick_label TEXT,
            model_probability REAL, edge REAL, dk_odds REAL,
            kelly_fraction REAL, scored_line REAL);
        CREATE TABLE picks (
            pick_id INTEGER PRIMARY KEY, game_id TEXT, model_id TEXT,
            game_date TEXT, pick_side TEXT, player_id TEXT, player_key TEXT,
            prop_market TEXT, created_at TEXT, best_book TEXT, best_odds REAL,
            condition_status TEXT);
        CREATE TABLE games (game_id TEXT, home_team TEXT, away_team TEXT,
                            commence_time TEXT);
        CREATE TABLE model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL, min_edge REAL,
            min_odds REAL, paused INTEGER, prob_only INTEGER);
        CREATE TABLE parlay_track_record (
            parlay_key TEXT PRIMARY KEY, sport TEXT, game_date TEXT,
            n_legs INTEGER, leg_keys TEXT, leg_labels TEXT, leg_odds TEXT,
            combined_decimal REAL, combined_american REAL, model_prob REAL,
            dk_implied_prob REAL, edge REAL, locked_at TEXT);
    """)
    raw.execute("INSERT INTO model_action_thresholds VALUES (?, 0.5, 0.03, -200, 0, 0)",
                (MODEL,))
    for i, (game_id, home, away, label, line, edge, status) in enumerate(GAMES, 1):
        raw.execute("INSERT INTO games VALUES (?, ?, ?, ?)",
                    (game_id, home, away, f"{DATE}T16:00:00+00:00"))
        raw.execute(
            "INSERT INTO opening_signals VALUES (?, ?, ?, 'NCAAF', ?, NULL, "
            "'under', ?, 0.6, ?, -110, 0.02, ?)",
            (f"{game_id}:{MODEL}", game_id, MODEL, DATE, label, edge, line))
        raw.execute(
            "INSERT INTO picks VALUES (?, ?, ?, ?, 'under', NULL, NULL, NULL, "
            "'2026-09-27 10:22:15+00', 'draftkings', -110, ?)",
            (i, game_id, MODEL, DATE, status))
    # A VOID on a DIFFERENT pick in the Duke game must not hide the totals
    # signal: the match is the pick's own key, not the game.
    raw.execute(
        "INSERT INTO picks VALUES (99, ?, 'ncaaf_spread', ?, 'home', NULL, NULL, "
        "NULL, '2026-09-27 10:22:15+00', 'draftkings', -110, 'VOID')",
        (GAMES[1][0], DATE))
    return _Conn(raw)


VOIDED_KEY = f"{GAMES[0][0]}:{MODEL}"
STANDING_KEYS = sorted(f"{g[0]}:{MODEL}" for g in GAMES[1:])


def test_a_voided_pick_is_not_a_free_pick_candidate():
    conn = _db()
    got = discord_notifier._free_pick_candidates(conn, DATE)
    assert conn.lateral_rewrites == 1, "the display join changed shape; update the test"
    keys = sorted(c["lock_key"] for c in got)
    assert VOIDED_KEY not in keys, "a voided pick can still be the free pick of the day"
    assert keys == STANDING_KEYS


def test_a_voided_pick_is_not_a_parlay_leg(monkeypatch):
    conn = _db()
    monkeypatch.setattr(parlay_track_record, "get_connection", lambda: conn)
    parlay_track_record.capture_parlay_track_record(target_date=DATE)
    (leg_keys,) = conn.raw.execute(
        "SELECT leg_keys FROM parlay_track_record WHERE parlay_key = ?",
        (f"NCAAF:{DATE}",)).fetchone()
    assert VOIDED_KEY not in leg_keys, "a voided pick became a public parlay leg"
    assert sorted(json.loads(leg_keys)) == STANDING_KEYS
