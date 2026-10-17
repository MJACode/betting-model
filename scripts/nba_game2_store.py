"""Store a graded run of the second NBA game-market search in Supabase.

The labs write their cells and populations as parquet files (NBA_GAME2_RESULTS).
Those took hours of compute, so they go into the database before anything
reads them (CLAUDE.md §1b: everything goes in Supabase; a local file is a
cache). One row per cell or population row, the whole row as JSON, keyed on
the run's name so a re-run of the same run writes nothing twice.

    python -m scripts.nba_game2_store --results DIR --run 2026-10-17-full
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from data.anon_readable import lock_down
from data.db import get_connection

CELLS_DDL = """
CREATE TABLE IF NOT EXISTS nba_game2_cells (
    run_id     TEXT NOT NULL,
    family     TEXT NOT NULL,
    cell_key   TEXT NOT NULL,
    row        JSONB NOT NULL,
    stored_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, cell_key)
)
"""
POP_DDL = """
CREATE TABLE IF NOT EXISTS nba_game2_population (
    run_id     TEXT NOT NULL,
    family     TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    row        JSONB NOT NULL,
    stored_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, family, seq)
)
"""


def _plain(v):
    """A JSON-safe value: NaN and infinities become null, arrays become lists."""
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_plain(x) for x in list(v)]
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    return v


def cell_rows(cells: pd.DataFrame, run_id: str) -> list[tuple]:
    from scripts.nba_game2_verdict import axes_of, cell_key
    axes = axes_of(cells)
    out = []
    for _, r in cells.iterrows():
        row = {k: _plain(v) for k, v in r.items()}
        out.append((run_id, str(r["family"]), cell_key(r, axes), json.dumps(row)))
    keys = [k for _, _, k, _ in out]
    assert len(set(keys)) == len(keys), "two cells share a key"
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    cells = pd.concat([pd.read_parquet(p) for p in sorted(a.results.glob("cells_*.parquet"))],
                      ignore_index=True)
    rows = cell_rows(cells, a.run)
    pops = []
    for p in sorted(a.results.glob("population_*.parquet")):
        fam = p.stem.removeprefix("population_")
        df = pd.read_parquet(p)
        pops += [(a.run, fam, i, json.dumps({k: _plain(v) for k, v in r.items()}))
                 for i, (_, r) in enumerate(df.iterrows())]
    conn = get_connection()
    try:
        conn.execute(CELLS_DDL)
        lock_down(conn, "nba_game2_cells")
        conn.execute(POP_DDL)
        lock_down(conn, "nba_game2_population")
        conn.executemany("INSERT INTO nba_game2_cells (run_id, family, cell_key, row) "
                         "VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT DO NOTHING", rows)
        conn.executemany("INSERT INTO nba_game2_population (run_id, family, seq, row) "
                         "VALUES (%s, %s, %s, %s::jsonb) ON CONFLICT DO NOTHING", pops)
        conn.commit()
        n = conn.execute("SELECT count(*) FROM nba_game2_cells WHERE run_id = %s",
                         (a.run,)).fetchone()[0]
        m = conn.execute("SELECT count(*) FROM nba_game2_population WHERE run_id = %s",
                         (a.run,)).fetchone()[0]
        print(f"run {a.run}: {n} cells and {m} population rows stored "
              f"(files held {len(rows)} and {len(pops)})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
