"""The full-game half of the research cache: one read, by game id, of the
full-game history the purchase stored, written as parquet under _paths.CACHE.

  fullgame_quotes.parquet  every pre-game `odds` row of the purchase (source
                           euroleague_odds_history.PREGAME_SOURCE): a book's
                           first quote on a game and market and every change
                           (change-only), snapshot_at the market's own
                           last_update, created_at the store time
  inplay_quotes.parquet    euroleague_inplay_quotes: every in-play quote of
                           every snapshot, keyed on the snapshot's own time
  snapshots.parquet        the purchase ledger (one row a snapshot)

Read in batches of game ids through the indexes, never a scan by source.

    python -m scripts.euroleague_research.cache_fullgame
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.euroleague_research._paths import CACHE  # noqa: E402

from data.db import get_connection  # noqa: E402
from data.ingestors import euroleague_odds_history as eh  # noqa: E402

BATCH = 40
NUM = ["home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"]
PRE_COLS = ["game_id", "market", "bookmaker", "snapshot_at", "created_at", *NUM]
INPLAY_COLS = ["snapshot_ts", "game_id", "bookmaker", "market", "last_update", *NUM]


def main() -> None:
    with get_connection() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT game_id FROM euroleague_events WHERE COALESCE(status, '') <> 'Cancelled' "
            "ORDER BY game_id").fetchall()]
        conn.commit()
        pre, inp = [], []
        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            pre += [tuple(r) for r in conn.execute(
                f"SELECT {', '.join(PRE_COLS)} FROM odds WHERE game_id = ANY(%s) AND source = %s",
                (chunk, eh.PREGAME_SOURCE)).fetchall()]
            inp += [tuple(r) for r in conn.execute(
                f"SELECT {', '.join(INPLAY_COLS)} FROM {eh.INPLAY_TABLE} WHERE game_id = ANY(%s)",
                (chunk,)).fetchall()]
            conn.commit()
        snaps = pd.DataFrame([tuple(r) for r in conn.execute(
            f"SELECT snapshot_ts, events, events_in_play, pregame_rows, inplay_rows, credits "
            f"FROM {eh.LEDGER}").fetchall()],
            columns=["snapshot_ts", "events", "events_in_play", "pregame_rows", "inplay_rows",
                     "credits"])
    p = pd.DataFrame(pre, columns=PRE_COLS)
    q = pd.DataFrame(inp, columns=INPLAY_COLS)
    for df in (p, q):
        for c in NUM:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    p["snapshot_at"] = pd.to_datetime(p["snapshot_at"], utc=True, errors="coerce")
    p["created_at"] = pd.to_datetime(p["created_at"], utc=True, errors="coerce")
    q["snapshot_ts"] = pd.to_datetime(q["snapshot_ts"], utc=True)
    q["last_update"] = pd.to_datetime(q["last_update"], utc=True, errors="coerce")
    p.to_parquet(CACHE / "fullgame_quotes.parquet", index=False)
    q.to_parquet(CACHE / "inplay_quotes.parquet", index=False)
    snaps.to_parquet(CACHE / "snapshots.parquet", index=False)
    print("pre-game rows", len(p), "games", p["game_id"].nunique(),
          "by market", p["market"].value_counts().to_dict())
    print("in-play rows", len(q), "games", q["game_id"].nunique())
    print("ledger snapshots", len(snaps))


if __name__ == "__main__":
    main()
