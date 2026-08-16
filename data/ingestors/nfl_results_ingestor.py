"""
NFL final scores from the hosted nflverse games.csv → the games table.

Fills home_score/away_score/home_win for the NFL games rows the wind-card
publisher created (scripts/nfl_wind_publisher.py), so the standard game-level
settle can grade nfl_wind_totals picks the morning after.

Source: nflverse's canonical games.csv (Lee Sharpe's nfldata), updated nightly
in season. Served from raw.githubusercontent.com — the same host the UFC CSV
mirror already reaches from the Railway worker, so no new egress is needed.
The join key is the nflverse game id, embedded in our game_id as
"NFL_{nflverse_id}" (e.g. NFL_2026_01_NE_SEA) — stable across flex-schedule
date changes, so a moved kickoff can never orphan a result.

Self-healing by construction: every run targets ALL NULL-score NFL games whose
kickoff has passed, however old — the pending set is tiny (~a handful of wind
bets a week), so there is no window to fall out of. No pending games (all of
the off-season) → returns without fetching anything.

Ties: NFL games can end tied. home_win stays NULL on a tie (neither side won);
totals settlement doesn't read home_win, so wind picks settle fine either way.

Usage:
    python -m data.ingestors.nfl_results_ingestor
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from data.db import get_connection

try:
    from loguru import logger
except ImportError:  # pragma: no cover - loguru is always present in prod
    import logging
    logger = logging.getLogger(__name__)


def parse_nflverse_scores(csv_text: str, wanted_ids: set[str]) -> dict[str, tuple[float, float]]:
    """
    Pure parse: nflverse games.csv text -> {nflverse_id: (away_score, home_score)}
    for wanted, COMPLETED games only (both scores present). Unfinished games
    have empty score fields and are skipped.
    """
    out: dict[str, tuple[float, float]] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        gid = (row.get("game_id") or "").strip()
        if gid not in wanted_ids:
            continue
        away_s, home_s = (row.get("away_score") or "").strip(), (row.get("home_score") or "").strip()
        if not away_s or not home_s:
            continue  # not final yet
        try:
            out[gid] = (float(away_s), float(home_s))
        except ValueError:
            continue
    return out


def run_nfl_results_ingestor() -> int:
    """Fill finals for started, unscored NFL games. Returns games updated."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        pending = conn.execute("""
            SELECT game_id FROM games
            WHERE sport = 'NFL'
              AND home_score IS NULL
              AND commence_time IS NOT NULL
              AND commence_time < %s
        """, (now_iso,)).fetchall()
        wanted = {r[0].removeprefix("NFL_") for r in pending}
        if not wanted:
            logger.info("NFL results: no pending finals — skipping fetch")
            return 0

        resp = requests.get(config.NFLVERSE_GAMES_URL, timeout=60)
        resp.raise_for_status()
        scores = parse_nflverse_scores(resp.text, wanted)

        updated = 0
        for nflverse_id, (away_score, home_score) in scores.items():
            home_win = None if home_score == away_score else int(home_score > away_score)
            conn.execute("""
                UPDATE games
                SET home_score = %s, away_score = %s, home_win = %s,
                    updated_at = %s
                WHERE game_id = %s AND home_score IS NULL
            """, (home_score, away_score, home_win, now_iso, f"NFL_{nflverse_id}"))
            updated += 1
        conn.commit()
        logger.info(f"NFL results: {updated} final(s) written "
                    f"({len(wanted) - updated} still pending)")
        return updated
    finally:
        conn.close()


if __name__ == "__main__":
    run_nfl_results_ingestor()
