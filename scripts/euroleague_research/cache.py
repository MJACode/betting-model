"""The research cache: one read, by game id, of what Supabase holds for
EuroLeague, written as parquet under _paths.CACHE.

  games.parquet           games + euroleague_events (clubs, start, phase,
                          round, neutral, venue, attendance, referees, score)
  periods.parquet         euroleague_period_scores (periods 1-4, overtimes 5+)
  period_quotes.parquet   every `odds` row of the period purchase, with the
                          time before tip it was bought at (`mark`, joined to
                          euroleague_period_fetches on the shared transaction
                          time: rows and ledger row are written together)

Read in batches of game ids through the odds game_id index, never a scan of
`odds` by source (that timed out twice on 2026-11-12/13).

    python -m scripts.euroleague_research.cache
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.euroleague_research._paths import CACHE  # noqa: E402

from data.db import get_connection  # noqa: E402
from data.ingestors import euroleague_period_history as ep  # noqa: E402

BATCH = 60
QUOTE_COLS = ["game_id", "market", "bookmaker", "snapshot_at", "home_price", "away_price",
              "draw_price", "spread_home", "total_line", "over_price", "under_price",
              "created_at"]


def main() -> None:
    with get_connection() as conn:
        g = pd.DataFrame([tuple(r) for r in conn.execute("""
            SELECT e.game_id, e.season, e.season_code, e.game_code, e.phase, e.round,
                   e.game_date, e.commence_time, e.home_code, e.away_code, e.neutral_site,
                   e.status, e.played, e.venue_code, e.venue_name, e.audience,
                   array_to_string(e.referees, '|') AS referees,
                   g.home_score, g.away_score, g.went_to_ot, g.regulation_tie
              FROM euroleague_events e LEFT JOIN games g ON g.game_id = e.game_id
        """).fetchall()], columns=[
            "game_id", "season", "season_code", "game_code", "phase", "round", "game_date",
            "commence_time", "home_code", "away_code", "neutral_site", "status", "played",
            "venue_code", "venue_name", "audience", "referees", "home_score", "away_score",
            "went_to_ot", "regulation_tie"])
        p = pd.DataFrame([tuple(r) for r in conn.execute(
            "SELECT game_id, period, home_points, away_points, season "
            "FROM euroleague_period_scores").fetchall()],
            columns=["game_id", "period", "home_points", "away_points", "season"])
        led = pd.DataFrame([tuple(r) for r in conn.execute(
            f"SELECT game_id, mark, asked_at, fetched_at, status FROM {ep.LEDGER}").fetchall()],
            columns=["game_id", "mark", "asked_at", "fetched_at", "status"])
        conn.commit()
        ids = sorted(led["game_id"].unique())
        parts = []
        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            rows = conn.execute(
                f"SELECT {', '.join(QUOTE_COLS)} FROM odds "
                "WHERE game_id = ANY(%s) AND source = %s", (chunk, ep.SOURCE)).fetchall()
            conn.commit()
            parts.append(pd.DataFrame([tuple(r) for r in rows], columns=QUOTE_COLS))
    q = pd.concat(parts, ignore_index=True)
    for c in ["home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price"]:
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q["created_at"] = pd.to_datetime(q["created_at"], utc=True)
    led["fetched_at"] = pd.to_datetime(led["fetched_at"], utc=True)
    led["asked_at"] = pd.to_datetime(led["asked_at"], utc=True)
    q = q.merge(led[["game_id", "fetched_at", "mark", "asked_at"]],
                left_on=["game_id", "created_at"], right_on=["game_id", "fetched_at"],
                how="left").drop(columns=["fetched_at"])
    g.to_parquet(CACHE / "games.parquet", index=False)
    p.to_parquet(CACHE / "periods.parquet", index=False)
    q.to_parquet(CACHE / "period_quotes.parquet", index=False)
    led.to_parquet(CACHE / "period_fetches.parquet", index=False)
    print("games", len(g), g.groupby("season").size().to_dict())
    print("period rows", len(p), "| period quotes", len(q), "| without a mark",
          int(q["mark"].isna().sum()))
    print("quotes by market (top 20):", q["market"].value_counts().head(20).to_dict())


if __name__ == "__main__":
    main()
