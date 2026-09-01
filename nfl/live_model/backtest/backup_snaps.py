"""
Copy the paid prop snapshot cache into Supabase, byte for byte.

WHY THIS EXISTS. The snapshots represent 100,116 Odds API credits and they
lived in exactly one place: a Railway volume attached to a single service. No
copy in the repo, none on any machine, no second region. Detach that volume or
delete that service and the pull has to be bought again. The nfl package
already treats its far cheaper pregame odds cache as precious enough to commit
to git, calling it IRREPLACEABLE; the live snapshots are four times the credit
value with none of the protection.

Supabase is the platform's system of record for everything else -- picks,
odds, games, play by play, even this package's own line history -- so the
snapshots belong there too rather than in a third storage scheme.

ONE ROW PER FILE, not one blob for the archive. A tarball would have to be
restored whole to read one game, could not be queried, and would silently
rot as a single corrupt object. Per file rows can be verified individually,
restored selectively, and re-uploaded incrementally when the pull grows.

The content is stored gzipped and checksummed against the RAW bytes, so a
restore proves it reproduced the original file rather than merely a file.

    python -m live_model.backtest.backup_snaps            # back up
    python -m live_model.backtest.backup_snaps --verify   # checksums only
    python -m live_model.backtest.backup_snaps --restore  # write files back
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
from pathlib import Path

from ..config import ARTIFACT_DIR

from data.ddl_guard import schema_is_current

SNAP_DIR = ARTIFACT_DIR / "prop_snaps"
TABLE = "nfl_live_prop_snapshots"
# Rows per transaction. Small enough that a dropped connection loses seconds
# of work rather than the whole upload, large enough not to pay round trip
# latency per file across several thousand files.
BATCH = 100

DDL = f"""
CREATE TABLE IF NOT EXISTS public.{TABLE} (
    id           BIGSERIAL PRIMARY KEY,
    rel_path     TEXT NOT NULL UNIQUE,
    sha256       TEXT NOT NULL,
    raw_bytes    INTEGER NOT NULL,
    gz_bytes     INTEGER NOT NULL,
    content_gz   BYTEA NOT NULL,
    backed_up_at TEXT NOT NULL
);
ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.{TABLE} FROM anon, authenticated;
"""


def _connect():
    import psycopg2
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is not set. The backup writes to Supabase, which is "
            "where every other extracted dataset in this project already "
            "lives.")
    return psycopg2.connect(url)


def iter_files(root: Path):
    """Every file under the cache, in a stable order."""
    if not root.exists():
        raise SystemExit(f"{root} does not exist, nothing to back up")
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def back_up(conn, root: Path = SNAP_DIR) -> dict:
    """
    Upload every file that is absent or has changed.

    Idempotent by sha256: a file already stored with the same digest is
    skipped, so a re-run after a crash costs one comparison per file rather
    than a second upload of the archive.
    """
    cur = conn.cursor()
    # ALTER TABLE ... ENABLE ROW LEVEL SECURITY takes ACCESS EXCLUSIVE and
    # forces PostgREST to rebuild its schema cache (503 to the app while it
    # does), whether or not RLS is already on. Skip once the table matches --
    # data/ddl_guard.py, and the outage that made it necessary.
    if not schema_is_current(conn, TABLE, rls=True,
                             revoked_from=("anon", "authenticated")):
        cur.execute(DDL)
        conn.commit()

    cur.execute(f"SELECT rel_path, sha256 FROM public.{TABLE}")
    have = dict(cur.fetchall())

    sent = skipped = raw_total = gz_total = 0
    batch = []
    for p in iter_files(root):
        rel = str(p.relative_to(root))
        raw = p.read_bytes()
        sha = digest(raw)
        raw_total += len(raw)
        if have.get(rel) == sha:
            skipped += 1
            continue
        gz = gzip.compress(raw, 6)
        gz_total += len(gz)
        batch.append((rel, sha, len(raw), len(gz), psycopg2_bytes(gz)))
        if len(batch) >= BATCH:
            _flush(conn, cur, batch)
            sent += len(batch)
            batch = []
    if batch:
        _flush(conn, cur, batch)
        sent += len(batch)
    return {"uploaded": sent, "unchanged": skipped,
            "raw_bytes": raw_total, "gz_bytes": gz_total}


def psycopg2_bytes(b: bytes):
    import psycopg2
    return psycopg2.Binary(b)


def _flush(conn, cur, batch) -> None:
    from psycopg2.extras import execute_values
    execute_values(
        cur,
        f"""INSERT INTO public.{TABLE}
              (rel_path, sha256, raw_bytes, gz_bytes, content_gz, backed_up_at)
            VALUES %s
            ON CONFLICT (rel_path) DO UPDATE SET
              sha256 = EXCLUDED.sha256,
              raw_bytes = EXCLUDED.raw_bytes,
              gz_bytes = EXCLUDED.gz_bytes,
              content_gz = EXCLUDED.content_gz,
              backed_up_at = EXCLUDED.backed_up_at""",
        # FIVE values per row against FIVE placeholders. backed_up_at is a
        # SQL literal in the template, not a bound parameter: an earlier
        # version passed a sixth element for it and execute_values would have
        # thrown on the first batch. The tests monkeypatched this function, so
        # nothing exercised the arity until it ran for real.
        list(batch),
        template="(%s, %s, %s, %s, %s, NOW()::TEXT)")
    conn.commit()


def verify(conn, root: Path = SNAP_DIR) -> dict:
    """
    Decompress what was stored and check it against the file on disk.

    A backup nobody has read back is a belief, not a backup, so this
    decompresses every row rather than trusting the stored digest.
    """
    cur = conn.cursor()
    cur.execute(f"SELECT rel_path, sha256, content_gz FROM public.{TABLE}")
    rows = cur.fetchall()
    ok = corrupt = missing_local = 0
    for rel, sha, blob in rows:
        raw = gzip.decompress(bytes(blob))
        if digest(raw) != sha:
            corrupt += 1
            continue
        p = root / rel
        if p.exists() and digest(p.read_bytes()) != sha:
            corrupt += 1
            continue
        if not p.exists():
            missing_local += 1
        ok += 1
    local = sum(1 for _ in iter_files(root)) if root.exists() else 0
    return {"stored": len(rows), "verified": ok, "corrupt": corrupt,
            "on_disk": local, "in_backup_only": missing_local}


def restore(conn, root: Path = SNAP_DIR) -> dict:
    """Write every stored file back to disk, checking each digest first."""
    cur = conn.cursor()
    cur.execute(f"SELECT rel_path, sha256, content_gz FROM public.{TABLE}")
    written = 0
    for rel, sha, blob in cur.fetchall():
        raw = gzip.decompress(bytes(blob))
        if digest(raw) != sha:
            raise SystemExit(f"refusing to restore {rel}: checksum mismatch")
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        written += 1
    return {"restored": written}


def _mb(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    conn = _connect()
    try:
        if args.restore:
            print(restore(conn, SNAP_DIR))
            return
        if not args.verify:
            r = back_up(conn, SNAP_DIR)
            print(f"uploaded {r['uploaded']:,} file(s), "
                  f"{r['unchanged']:,} already current")
            print(f"cache on disk {_mb(r['raw_bytes'])}, "
                  f"new bytes stored {_mb(r['gz_bytes'])} gzipped")
        v = verify(conn, SNAP_DIR)
        print(f"\nVERIFY: {v['verified']:,}/{v['stored']:,} rows decompress to "
              f"their recorded checksum, {v['corrupt']} corrupt")
        print(f"        {v['on_disk']:,} files on the volume, "
              f"{v['in_backup_only']:,} in the backup but not on disk")
        if v["corrupt"]:
            raise SystemExit("BACKUP IS NOT TRUSTWORTHY: checksum mismatches")
        if v["stored"] < v["on_disk"]:
            raise SystemExit(
                f"INCOMPLETE: {v['on_disk'] - v['stored']:,} file(s) on the "
                "volume are not in the backup")
        print("\nthe cache is now recoverable from Supabase alone")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
