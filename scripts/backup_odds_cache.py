"""
Copy `nfl/data/odds_cache/` into Supabase, byte for byte.

WHY. The cache is ~45,000 Odds API credits of spend and, as of 2026-09-03,
**6,769 files / 668 MB — 71% of everything tracked in this repo**. Its only
protection is that it is committed to git, which has no integrity verification:
a silently corrupted blob reads as a successful checkout. Meanwhile
`nfl/live_model/backtest/backup_snaps.py` already solved exactly this problem
for the live prop snapshots — one gzipped, checksummed row per file, verifiable
and selectively restorable — and its own docstring names this cache as the thing
with four times less protection than it deserves.

This is that scheme, pointed at this directory. It is deliberately a SEPARATE
script rather than an edit to `backup_snaps.py`: that module is stable, several
branches are in flight against this tree, and the two caches have different
roots, different tables and different lifecycles.

    python -m scripts.backup_odds_cache             # upload (idempotent, resumable)
    python -m scripts.backup_odds_cache --verify    # decompress + checksum every row
    python -m scripts.backup_odds_cache --restore   # write the files back to disk
    python -m scripts.backup_odds_cache --limit 50  # pilot a small batch first

UPLOAD FIRST, DELETE NEVER (not by this script). Nothing here removes a file
from git or from disk. `docs/sports/nfl.md` says "never delete, never gitignore",
and that stays true until a `--verify` pass over the full set has run green and
a person decides otherwise.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402

CACHE_DIR = ROOT / "nfl" / "data" / "odds_cache"
TABLE = "nfl_odds_cache_backup"
BATCH = 100


DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    rel_path    TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    raw_bytes   BIGINT NOT NULL,
    gz_bytes    BIGINT NOT NULL,
    content_gz  BYTEA NOT NULL,
    backed_up_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _files() -> list[Path]:
    return sorted(p for p in CACHE_DIR.glob("*.json") if p.is_file())


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ensure_table(conn) -> None:
    # GUARDED. Re-running this block unconditionally is not the cheap no-op it
    # looks like: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS
    # EXCLUSIVE whether or not RLS is already on, and every statement here fires
    # Supabase's `pgrst_ddl_watch` trigger, which makes PostgREST answer 503 to
    # every request while it rebuilds its schema cache. Measured on production
    # 2026-09-01: 11.6 hours of database time and ~3,600 forced cache reloads
    # from exactly this pattern. `schema_is_current` is one indexed catalog
    # SELECT that fails closed. See data/ddl_guard.py — and note this script
    # shipped WITHOUT the guard and `tests/test_ddl_guard.py` caught it.
    if schema_is_current(conn, TABLE, rls=True,
                         revoked_from=("anon", "authenticated")):
        return

    conn.executescript(DDL)
    # Same rule as every other object in `public`: default privileges hand anon
    # and authenticated EXECUTE/ALL, and `REVOKE ... FROM PUBLIC` does not undo
    # it. Revoke BY NAME. (CLAUDE.md, Supabase trap.)
    for role in ("anon", "authenticated"):
        try:
            conn.executescript(f"REVOKE ALL ON {TABLE} FROM {role};")
        except Exception as exc:  # pragma: no cover - role may not exist locally
            print(f"  note: could not revoke from {role}: {exc}")

    # Belt and braces, and the same shape `tracking/run_ledger.py` uses: the
    # revoke above is what actually protects the table, but RLS with no policy
    # means a LATER accidental `GRANT SELECT TO anon` still reads nothing.
    # service_role bypasses RLS, so the backup/verify/restore paths are
    # unaffected. This repo has already had anon hold SELECT+INSERT+UPDATE+DELETE
    # on a 2.2M-row irreplaceable archive; this one is 45,000 credits of spend.
    try:
        conn.executescript(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;")
    except Exception as exc:  # pragma: no cover
        print(f"  note: could not enable RLS: {exc}")

    # COMMIT THE DDL HERE, don't rely on the upload loop's per-batch commit.
    # First time round this was missed, and a run with nothing left to upload
    # issued the grants and the RLS statement and then committed nothing — so
    # the table sat with RLS disabled while the script had printed no error at
    # all. Verified after, not assumed: `SELECT relrowsecurity FROM pg_class`.
    conn.commit()


def backup(limit: int | None = None) -> int:
    files = _files()
    if limit:
        files = files[:limit]
    if not files:
        print(f"no files under {CACHE_DIR}")
        return 0

    with get_connection() as conn:
        _ensure_table(conn)
        done = {
            r[0] for r in conn.execute(f"SELECT rel_path FROM {TABLE}").fetchall()
        }
        todo = [p for p in files if p.name not in done]
        print(f"{len(files)} file(s) in scope | {len(done)} already stored | "
              f"{len(todo)} to upload")

        sent = 0
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            for path in chunk:
                raw = path.read_bytes()
                gz = gzip.compress(raw, compresslevel=9)
                conn.execute(
                    f"INSERT INTO {TABLE} "
                    "(rel_path, sha256, raw_bytes, gz_bytes, content_gz) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (rel_path) DO NOTHING",
                    (path.name, _digest(raw), len(raw), len(gz), gz),
                )
            conn.commit()
            sent += len(chunk)
            print(f"  {sent}/{len(todo)} uploaded", flush=True)
    return sent


def verify(limit: int | None = None) -> int:
    """Decompress every stored row and compare against the checksum AND, where
    the file is still on disk, against the original bytes."""
    bad = 0
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT rel_path, sha256, raw_bytes, content_gz FROM {TABLE} "
            "ORDER BY rel_path" + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()
        print(f"verifying {len(rows)} row(s)")
        for rel, sha, nbytes, gz in rows:
            raw = gzip.decompress(bytes(gz))
            if _digest(raw) != sha or len(raw) != nbytes:
                print(f"  CHECKSUM MISMATCH: {rel}")
                bad += 1
                continue
            disk = CACHE_DIR / rel
            if disk.exists() and disk.read_bytes() != raw:
                print(f"  DIFFERS FROM DISK: {rel}")
                bad += 1
    print(f"{'FAILED' if bad else 'OK'} — {bad} problem(s)")
    return bad


def restore() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    with get_connection() as conn:
        for rel, gz in conn.execute(
            f"SELECT rel_path, content_gz FROM {TABLE}"
        ).fetchall():
            (CACHE_DIR / rel).write_bytes(gzip.decompress(bytes(gz)))
            n += 1
    print(f"restored {n} file(s) to {CACHE_DIR}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="only touch the first N files — use for a pilot run")
    args = ap.parse_args()

    if args.restore:
        restore()
    elif args.verify:
        sys.exit(1 if verify(args.limit) else 0)
    else:
        backup(args.limit)


if __name__ == "__main__":
    main()
