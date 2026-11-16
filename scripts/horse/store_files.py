"""Copy the free horse racing files into Supabase, one row per file (or part).

CLAUDE.md section 1b: a dataset is stored in Supabase before it is analysed,
and a local file is a cache of Supabase or it is a bug. The files are the ones
`scripts/horse/fetch_datasets.py` downloads into gitignored `data/horse/`.

WHERE THEY GO. `nfl_research_data_backup`, the per-file research backup
(`data/migrations/add_nfl_research_data_backup_2026_10_12.sql`): rel_path
unique, a `source` marker, gzip of the raw bytes, sha256 of the raw bytes.
The table name is historical; the marker is what says whose file it is. Racing
rows carry `source = 'horse_racing|<kind>'` and `rel_path = 'horse/<path>'`,
so no NFL row can collide with one. Using the existing table means no DDL, so
no PostgREST schema reload (data/ddl_guard.py) on the day this first ran, an
NFL Sunday with games live.

WHAT IS STORED.
  * Every `.csv` and `.csv.gz` the fetch script leaves on disk: the Betfair
    Australia/NZ monthly CSVs (the annual zips are extracted to monthly CSVs;
    the zip is not stored twice), the Hong Kong Kaggle CSVs, and the GitHub
    Hong Kong set (`nch015-horserace-data`, gzipped CSVs as published).
  * For a folder in ZIP_FOLDERS, the downloaded zip itself and not its
    extracted CSVs: the UK/Ireland 1988-2026 set is a 1.12 GB zip that
    extracts to about 3.95 GB, and the zip is the exact bytes Kaggle served.
  * A file over PART_BYTES (32 MiB) is stored as parts, `<rel>#partNNNNofMMMM`, each
    gzipped and hashed on its own raw slice, so no row is a 1 GB value and a
    dropped connection loses one part. `--restore` joins them in order.

    python -m scripts.horse.store_files            # store, then verify
    python -m scripts.horse.store_files --verify   # disk vs stored checksums,
                                                   # and a restore-and-hash of every row
    python -m scripts.horse.store_files --restore DIR

Resumable: a row whose rel_path is stored with the same checksum is skipped.
One row per transaction.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

TABLE = "nfl_research_data_backup"
SOURCE_PREFIX = "horse_racing|"
REL_PREFIX = "horse/"
DATA_ROOT = ROOT_DIR / "data" / "horse"
PART_BYTES = 32 * 1024 * 1024
# Folders stored as their downloaded zip rather than the extracted CSVs.
ZIP_FOLDERS = {"deltaromeo-uk-ireland-1988-2026"}
_PART = re.compile(r"^(?P<base>.+)#part(?P<i>\d{4})of(?P<n>\d{4})$")


def kind_for(rel: str) -> str:
    """The source marker's second half, from the path under data/horse."""
    top = rel.split("/", 1)[0]
    if top.startswith("betfair-"):
        return "betfair_anz_thoroughbreds"
    return top.replace("-", "_")


def _wanted(rel: str, p: Path) -> bool:
    top = rel.split("/", 1)[0]
    name = p.name.lower()
    if top in ZIP_FOLDERS:
        return name.endswith(".zip")
    return name.endswith(".csv") or name.endswith(".csv.gz")


def files(root: Path, only: set[str] | None = None):
    """Every file the store takes under the download root, in a stable order.
    `only` limits it to those top-level folders (dataset ids)."""
    if not root.exists():
        raise SystemExit(f"{root} does not exist; run scripts.horse.fetch_datasets first")
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if only is not None and rel.split("/", 1)[0] not in only:
                continue
            if _wanted(rel, p):
                yield rel, p


def units(root: Path, part_bytes: int = PART_BYTES, only: set[str] | None = None):
    """(row key, path, offset, length) for every row the store writes."""
    for rel, p in files(root, only):
        size = p.stat().st_size
        if size <= part_bytes:
            yield rel, p, 0, size
            continue
        n = (size + part_bytes - 1) // part_bytes
        for i in range(n):
            off = i * part_bytes
            yield f"{rel}#part{i + 1:04d}of{n:04d}", p, off, min(part_bytes, size - off)


def _read(p: Path, off: int, length: int) -> bytes:
    with p.open("rb") as handle:
        handle.seek(off)
        return handle.read(length)


def _stored(conn) -> dict[str, str]:
    rows = conn.execute(
        f"SELECT rel_path, sha256 FROM {TABLE} WHERE source LIKE %s",
        (SOURCE_PREFIX + "%",)).fetchall()
    return {r[0]: r[1] for r in rows}


def store(conn, root: Path = DATA_ROOT, pause: float = 0.2, part_bytes: int = PART_BYTES,
          only: set[str] | None = None) -> dict:
    import psycopg2
    have = _stored(conn)
    sql = (f"INSERT INTO {TABLE} (rel_path, source, sha256, raw_bytes, gz_bytes, content_gz) "
           f"VALUES (%s, %s, %s, %s, %s, %s) "
           f"ON CONFLICT (rel_path) DO UPDATE SET source = EXCLUDED.source, "
           f"sha256 = EXCLUDED.sha256, raw_bytes = EXCLUDED.raw_bytes, "
           f"gz_bytes = EXCLUDED.gz_bytes, content_gz = EXCLUDED.content_gz, "
           f"backed_up_at = now()")
    sent = skipped = raw_total = gz_total = 0
    for key, p, off, length in units(root, part_bytes, only):
        row = REL_PREFIX + key
        raw = _read(p, off, length)
        sha = hashlib.sha256(raw).hexdigest()
        if have.get(row) == sha:
            skipped += 1
            continue
        gz = gzip.compress(raw, compresslevel=6)
        conn.execute(sql, (row, SOURCE_PREFIX + kind_for(key), sha, len(raw), len(gz),
                           psycopg2.Binary(gz)))
        conn.commit()
        sent += 1
        raw_total += len(raw)
        gz_total += len(gz)
        print(f"  stored {row} ({len(raw) / 1e6:.1f} MB raw)", flush=True)
        if pause:
            time.sleep(pause)
    print(f"stored {sent} rows ({raw_total / 1e6:.1f} MB raw, {gz_total / 1e6:.1f} MB gz); "
          f"{skipped} already stored")
    return {"stored": sent, "skipped": skipped}


def verify(conn, root: Path = DATA_ROOT, part_bytes: int = PART_BYTES,
           only: set[str] | None = None) -> int:
    """Disk against stored checksums, then every stored row restored and hashed."""
    have = _stored(conn)
    missing = bad = 0
    for key, p, off, length in units(root, part_bytes, only):
        row = REL_PREFIX + key
        if row not in have:
            missing += 1
        elif have[row] != hashlib.sha256(_read(p, off, length)).hexdigest():
            bad += 1
    restored_bad = 0
    for (row,) in conn.execute(
            f"SELECT rel_path FROM {TABLE} WHERE source LIKE %s ORDER BY rel_path",
            (SOURCE_PREFIX + "%",)).fetchall():
        if only is not None and row[len(REL_PREFIX):].split("/", 1)[0] not in only:
            continue
        sha, blob = conn.execute(
            f"SELECT sha256, content_gz FROM {TABLE} WHERE rel_path = %s", (row,)).fetchone()
        if hashlib.sha256(gzip.decompress(bytes(blob))).hexdigest() != sha:
            restored_bad += 1
    by = conn.execute(
        f"SELECT source, count(*), sum(raw_bytes), sum(gz_bytes) FROM {TABLE} "
        f"WHERE source LIKE %s GROUP BY source ORDER BY source",
        (SOURCE_PREFIX + "%",)).fetchall()
    for s, n, rb, gb in by:
        print(f"  {s}: {n} rows, {rb / 1e6:.1f} MB raw, {gb / 1e6:.1f} MB gz")
    print(f"verify: {len(have)} stored, {missing} on disk but not stored, "
          f"{bad} disk checksum mismatches, {restored_bad} rows that do not restore to their checksum")
    return missing + bad + restored_bad


def restore(conn, dest: Path) -> None:
    rows = conn.execute(
        f"SELECT rel_path, sha256 FROM {TABLE} WHERE source LIKE %s ORDER BY rel_path",
        (SOURCE_PREFIX + "%",)).fetchall()
    parts: dict[str, list[tuple[int, int, str, str]]] = {}
    whole = []
    for row, sha in rows:
        m = _PART.match(row)
        if m:
            parts.setdefault(m["base"], []).append((int(m["i"]), int(m["n"]), row, sha))
        else:
            whole.append((row, sha))

    def raw_of(row: str, sha: str) -> bytes:
        (blob,) = conn.execute(
            f"SELECT content_gz FROM {TABLE} WHERE rel_path = %s", (row,)).fetchone()
        raw = gzip.decompress(bytes(blob))
        if hashlib.sha256(raw).hexdigest() != sha:
            raise SystemExit(f"checksum mismatch on {row}")
        return raw

    for row, sha in whole:
        out = dest / row[len(REL_PREFIX):]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw_of(row, sha))
    for base, plist in parts.items():
        plist.sort()
        n = plist[0][1]
        if [i for i, *_ in plist] != list(range(1, n + 1)):
            raise SystemExit(f"{base}: parts {[i for i, *_ in plist]} of {n}")
        out = dest / base[len(REL_PREFIX):]
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as handle:
            for _, _, row, sha in plist:
                handle.write(raw_of(row, sha))
    print(f"restored {len(whole)} files and {len(parts)} multi-part files to {dest}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", type=Path, default=DATA_ROOT)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--restore", type=Path)
    ap.add_argument("--only", action="append", default=[],
                    help="a dataset folder under data/horse; repeatable")
    a = ap.parse_args(argv)
    only = set(a.only) or None
    from data.db import get_connection
    conn = get_connection()
    try:
        if a.restore:
            restore(conn, a.restore)
            return 0
        if a.verify:
            return 1 if verify(conn, a.root, only=only) else 0
        store(conn, a.root, only=only)
        return 1 if verify(conn, a.root, only=only) else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
