"""Copy the free data the NFL edge search fetched into Supabase, file by file.

mike, 2026-10-12: "5) yes". CLAUDE.md §1b: a local file is a cache of
Supabase or it is a bug. docs/nfl_edge_search.md (2026-10-11) graded on data
that lived only in %TEMP%/nfl_edge:

  kalshi      Kalshi NFL winner markets, 1-minute candles + raw responses (2025, 2026)
  weather     Open-Meteo ERA5 and issued-forecast responses for NFL venues
  pbp         nflverse play-by-play 2011-2026 and the 1999-2025 weather extract

One row per file in `nfl_research_data_backup`, gzipped, sha256 of the RAW
bytes, the shape nfl_live_prop_snapshots already uses. Resumable: a file whose
rel_path is stored with the same checksum is skipped (`source LIKE` reads the
marker back for the summary).

    python -m scripts.nfl_research_backup                 # back up
    python -m scripts.nfl_research_backup --verify        # checksums vs disk
    python -m scripts.nfl_research_backup --restore DIR   # write files back
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection  # noqa: E402

ROOT = Path(os.environ.get("NFL_EDGE_CACHE", Path(os.environ.get("TEMP", "/tmp")) / "nfl_edge"))
TABLE = "nfl_research_data_backup"
SOURCE_PREFIX = "nfl_edge_search|"
BATCH_BYTES = 40_000_000          # one transaction per ~40 MB of gzip

# (kind, glob under ROOT). Derived scratch files (agent outputs, verifier
# parquets) are not data and are not copied.
PATTERNS = [
    ("kalshi", "kalshi/raw/*.json"),
    ("kalshi", "kalshi/candles_1m_nflgame.parquet"),
    ("kalshi", "kalshi/markets_nfl.parquet"),
    ("kalshi", "kalshi/series_sports.json"),
    ("weather", "wx_fetch/**/*"),
    ("weather", "openmeteo/**/*"),
    ("weather", "era5_kick_1999_2025.parquet"),
    ("weather", "era5_wind_stadiums_2023_2026.parquet"),
    ("weather", "issued_wx_2024_2025.parquet"),
    ("pbp", "pbp_20[0-9][0-9].parquet"),
    ("pbp", "pbp_weather_1999_2025.parquet"),
]


def files(root: Path):
    seen = set()
    for kind, pat in PATTERNS:
        for p in sorted(root.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield kind, p


def backup(conn, root: Path) -> None:
    stored = {r[0]: r[1] for r in conn.execute(
        f"SELECT rel_path, sha256 FROM {TABLE} WHERE source LIKE %s",
        (SOURCE_PREFIX + "%",)).fetchall()}
    batch, size, n_new, n_skip, raw_total, gz_total = [], 0, 0, 0, 0, 0
    sql = (f"INSERT INTO {TABLE} (rel_path, source, sha256, raw_bytes, gz_bytes, content_gz) "
           f"VALUES (%s, %s, %s, %s, %s, %s) "
           f"ON CONFLICT (rel_path) DO UPDATE SET source = EXCLUDED.source, "
           f"sha256 = EXCLUDED.sha256, raw_bytes = EXCLUDED.raw_bytes, "
           f"gz_bytes = EXCLUDED.gz_bytes, content_gz = EXCLUDED.content_gz, backed_up_at = now()")

    def flush():
        nonlocal batch, size
        if batch:
            conn.executemany(sql, batch)
            conn.commit()
            batch, size = [], 0

    import psycopg2
    for kind, p in files(root):
        rel = p.relative_to(root).as_posix()
        raw = p.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if stored.get(rel) == sha:
            n_skip += 1
            continue
        gz = gzip.compress(raw, compresslevel=6)
        batch.append((rel, SOURCE_PREFIX + kind, sha, len(raw), len(gz), psycopg2.Binary(gz)))
        size += len(gz)
        n_new += 1
        raw_total += len(raw)
        gz_total += len(gz)
        if size >= BATCH_BYTES:
            flush()
            print(f"  ... {n_new} files, {gz_total / 1e6:.0f} MB gz so far", flush=True)
    flush()
    print(f"backed up {n_new} files ({raw_total / 1e6:.1f} MB raw, {gz_total / 1e6:.1f} MB gz); "
          f"{n_skip} already stored")


def verify(conn, root: Path) -> int:
    stored = {r[0]: r[1] for r in conn.execute(
        f"SELECT rel_path, sha256 FROM {TABLE} WHERE source LIKE %s",
        (SOURCE_PREFIX + "%",)).fetchall()}
    bad = missing = 0
    for _kind, p in files(root):
        rel = p.relative_to(root).as_posix()
        if rel not in stored:
            missing += 1
        elif stored[rel] != hashlib.sha256(p.read_bytes()).hexdigest():
            bad += 1
    by = conn.execute(f"SELECT source, count(*), sum(raw_bytes), sum(gz_bytes) FROM {TABLE} "
                      f"WHERE source LIKE %s GROUP BY source ORDER BY source",
                      (SOURCE_PREFIX + "%",)).fetchall()
    for s, n, rb, gb in by:
        print(f"  {s}: {n} files, {rb / 1e6:.1f} MB raw, {gb / 1e6:.1f} MB gz")
    print(f"verify: {len(stored)} stored, {missing} on disk but not stored, {bad} checksum mismatches")
    return missing + bad


def restore(conn, dest: Path) -> None:
    rows = conn.execute(f"SELECT rel_path, sha256, content_gz FROM {TABLE} WHERE source LIKE %s",
                        (SOURCE_PREFIX + "%",)).fetchall()
    for rel, sha, blob in rows:
        raw = gzip.decompress(bytes(blob))
        if hashlib.sha256(raw).hexdigest() != sha:
            raise SystemExit(f"checksum mismatch on {rel}")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
    print(f"restored {len(rows)} files to {dest}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", type=Path)
    a = ap.parse_args()
    conn = get_connection()
    try:
        if a.restore:
            restore(conn, a.restore)
        elif a.verify:
            raise SystemExit(1 if verify(conn, a.root) else 0)
        else:
            backup(conn, a.root)
            verify(conn, a.root)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
