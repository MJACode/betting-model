"""Store each new Betfair Australia thoroughbred file in Supabase the day it is published.

Betfair Australia publishes, free and with no login, one CSV a month of every
Australian and New Zealand thoroughbred market, and rolls each finished year
into an annual zip (listing: LISTING below). The racing audit stored 2020-01 to
2026-10 by hand (`scripts/horse/store_files.py`). This keeps that copy complete
without a session: the worker runs it once a day
(`scheduler.run_betfair_monthly_store`). Issue #1371.

WHAT ONE RUN DOES
  * Reads the listing and every `ANZ_Thoroughbreds_*` file it names. A listing
    that names none is an error, not "nothing new": a page that moved and a
    quiet month must not look the same.
  * A monthly CSV with no stored row: downloads and stores it.
  * A monthly CSV already stored: asks the server for its size (HEAD). If the
    size is not the size of any stored version, downloads it. The two newest
    monthly files are downloaded and hashed every day as well, so a correction
    that keeps the file's size is still caught. New bytes are stored as a NEW
    VERSION beside the old one, `<stem>.v<UTC stamp>-<sha 8>.csv` in the same
    folder. A stored row is never overwritten or deleted (CLAUDE.md section
    1b). If the server gives no size for any stored month, the run fails: a
    size check that has stopped working must not look like a quiet day.
  * An annual zip not seen before: downloads it. A member whose bytes are
    already stored anywhere under this source is not stored again (a finished
    year rolled into a zip repeats its monthly files). A member that differs
    from a month already stored as a monthly file is stored as a new version
    of that month. Any other member is stored under the zip's folder, as
    `store_files` stored 2020-2025. A `_manifest.json` row records every member
    and where it went, and marks the zip as seen.
  * Writes each file's rows in ONE transaction, reads every row back inside it
    (decompress and match the sha256), and commits only if all match. A file
    is stored whole or not at all, so a failed run leaves nothing half done,
    and the next run tries it again.

WHICH VERSION A STUDY READS. `anz_study.load` takes one file per month: the
newest version by its stamp, else the original. It never reads two copies of
one month.

WHERE ROWS GO. `nfl_research_data_backup`, `source =
'horse_racing|betfair_anz_thoroughbreds'`, `rel_path =
'horse/betfair-<file name>/<member>'`, exactly as `store_files` writes them, so
`store_files --restore` and the nightly PC copy see one set.

    python -m scripts.horse.betfair_monthly            # store what is new
    python -m scripts.horse.betfair_monthly --dry-run  # say what it would fetch; download and write nothing
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

LISTING = "https://betfair-datascientists.github.io/data/dataListing/"
TABLE = "nfl_research_data_backup"
SOURCE = "horse_racing|betfair_anz_thoroughbreds"
PART_BYTES = 32 * 1024 * 1024          # the same split store_files uses
USER_AGENT = "betting-model-research/1.0 (free public data listing)"
TIMEOUT_S = 120
HASH_NEWEST = 2                        # newest monthly files downloaded and hashed every day
MANIFEST = "_manifest.json"

_LINK = re.compile(r"""["'(]([^"'()\s<>]*ANZ_Thoroughbreds_\d{4}(?:_\d{2})?\.(?:csv|zip))""")
_NAME = re.compile(r"^ANZ_Thoroughbreds_\d{4}(?:_\d{2})?\.(csv|zip)$")
_PART = re.compile(r"#part\d{4}of\d{4}$")
# A month's file, original or a stored version: ANZ_Thoroughbreds_2026_10.csv or
# ANZ_Thoroughbreds_2026_10.v20261201T154300Z-1a2b3c4d.csv
MONTH_FILE = re.compile(r"^ANZ_Thoroughbreds_(\d{4})_(\d{2})(?:\.v(\d{8}T\d{6}Z)-[0-9a-f]{8})?\.csv$")


# ------------------------------------------------------------------ the listing

def listed_files(html: str, base: str = LISTING) -> list[dict]:
    """Every ANZ thoroughbred file the listing links to, once each, in name order:
    {name, url, kind} with kind 'csv' (a month) or 'zip' (a year)."""
    out: dict[str, dict] = {}
    for href in _LINK.findall(html):
        url = urllib.parse.urljoin(base, href)
        name = url.rsplit("/", 1)[-1]
        m = _NAME.match(name)
        if m and name not in out:
            out[name] = {"name": name, "url": url, "kind": m.group(1)}
    return [out[k] for k in sorted(out)]


def folder(name: str) -> str:
    return f"horse/betfair-{name}/"


def logical_files(stored: dict[str, tuple[str, int]], prefix: str) -> dict[str, int]:
    """The files stored under one folder, with parts joined: logical rel -> total bytes."""
    out: dict[str, int] = {}
    for rel, (_, n) in stored.items():
        if rel.startswith(prefix):
            key = _PART.sub("", rel)
            out[key] = out.get(key, 0) + n
    return out


def fingerprints(stored: dict[str, tuple[str, int]], prefix: str = "horse/") -> dict[tuple, str]:
    """Each stored logical file under `prefix` as the ordered tuple of its rows'
    sha256 (one for a whole file, one per part for a split one) -> its rel_path.
    A download is compared through the same split, so a split file matches."""
    parts: dict[str, list[tuple[str, str]]] = {}
    for rel, (sha, _) in stored.items():
        if rel.startswith(prefix):
            parts.setdefault(_PART.sub("", rel), []).append((rel, sha))
    return {tuple(sha for _, sha in sorted(rows)): key for key, rows in parts.items()}


def blob_fingerprint(raw: bytes) -> tuple:
    return tuple(hashlib.sha256(chunk).hexdigest() for _, chunk in _split("x", raw))


def version_name(member: str, sha: str, stamp: str) -> str:
    stem = member[:-4] if member.lower().endswith(".csv") else member
    return f"{stem}.v{stamp}-{sha[:8]}.csv"


# ------------------------------------------------------------------ the plan

def plan(listed: list[dict], stored: dict[str, tuple[str, int]],
         sizes: dict[str, int | None]) -> list[dict]:
    """What to fetch. `stored` is rel_path -> (sha256, raw_bytes) for this source;
    `sizes` is a stored monthly CSV's size on the server (None when it gave none)."""
    todo = []
    stored_months = [f["name"] for f in listed
                     if f["kind"] == "csv" and logical_files(stored, folder(f["name"]))]
    newest = set(sorted(stored_months)[-HASH_NEWEST:]) if HASH_NEWEST else set()
    for f in listed:
        held = logical_files(stored, folder(f["name"]))
        if not held:
            todo.append({**f, "why": "new"})
            continue
        if f["kind"] != "csv":
            continue                                   # a zip already seen is not refetched
        size = sizes.get(f["name"])
        if size is not None and size not in set(held.values()):
            todo.append({**f, "why": f"size {size:,} on the server is not a stored version's size"})
        elif f["name"] in newest:
            todo.append({**f, "why": "one of the newest months: hashed daily"})
    return todo


def rows_for(item: dict, blob: bytes, stored: dict[str, tuple[str, int]],
             stamp: str) -> list[tuple[str, bytes]]:
    """(rel_path, raw bytes) for each row this file adds; empty if nothing is new.
    Never a rel_path already stored."""
    everywhere = fingerprints(stored)
    if item["kind"] == "csv":
        sha = hashlib.sha256(blob).hexdigest()
        prefix = folder(item["name"])
        if blob_fingerprint(blob) in fingerprints(stored, prefix):
            return []
        base = prefix + item["name"]
        rel = base if not logical_files(stored, prefix) else prefix + version_name(item["name"], sha, stamp)
        return _split(rel, blob)

    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members = [(Path(n).name, z.read(n)) for n in sorted(z.namelist())
                   if n.lower().endswith(".csv") and not n.endswith("/")]
    if not members:
        raise ValueError(f"{item['name']}: the zip holds no CSV")
    zprefix = folder(item["name"])
    out: list[tuple[str, bytes]] = []
    record = []
    for member, raw in members:
        sha = hashlib.sha256(raw).hexdigest()
        entry = {"member": member, "sha256": sha, "bytes": len(raw)}
        fp = blob_fingerprint(raw)
        if fp in everywhere:
            entry["identical_to"] = everywhere[fp]
        elif logical_files(stored, folder(member)):
            rel = folder(member) + version_name(member, sha, stamp)
            entry["stored_as"] = rel
            out += _split(rel, raw)
        else:
            rel = zprefix + member
            entry["stored_as"] = rel
            out += _split(rel, raw)
        everywhere.setdefault(fp, entry.get("stored_as") or entry.get("identical_to"))
        record.append(entry)
    manifest = {"zip": item["name"], "url": item["url"], "read_at": stamp,
                "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob), "members": record}
    out.append((zprefix + MANIFEST, json.dumps(manifest, indent=1, sort_keys=True).encode("utf-8")))
    return out


def _split(rel: str, raw: bytes) -> list[tuple[str, bytes]]:
    if len(raw) <= PART_BYTES:
        return [(rel, raw)]
    n = (len(raw) + PART_BYTES - 1) // PART_BYTES
    return [(f"{rel}#part{i + 1:04d}of{n:04d}", raw[i * PART_BYTES:(i + 1) * PART_BYTES])
            for i in range(n)]


# ------------------------------------------------------------------ the database

INSERT_SQL = (f"INSERT INTO {TABLE} (rel_path, source, sha256, raw_bytes, gz_bytes, content_gz) "
              f"VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (rel_path) DO NOTHING")


def stored_rows(conn) -> dict[str, tuple[str, int]]:
    rows = conn.execute(f"SELECT rel_path, sha256, raw_bytes FROM {TABLE} WHERE source = %s",
                        (SOURCE,)).fetchall()
    return {r[0]: (r[1], int(r[2])) for r in rows}


def store_file(conn, rows: list[tuple[str, bytes]], binary=bytes) -> None:
    """Insert one file's rows and read each back, in ONE transaction; commit only if
    every row decompresses to its sha256. On any mismatch or error, roll back."""
    try:
        for rel, raw in rows:
            sha = hashlib.sha256(raw).hexdigest()
            gz = gzip.compress(raw, compresslevel=6)
            conn.execute(INSERT_SQL, (rel, SOURCE, sha, len(raw), len(gz), binary(gz)))
        for rel, raw in rows:
            sha = hashlib.sha256(raw).hexdigest()
            got = conn.execute(f"SELECT sha256, content_gz FROM {TABLE} WHERE rel_path = %s",
                               (rel,)).fetchone()
            if (got is None or got[0] != sha
                    or hashlib.sha256(gzip.decompress(bytes(got[1]))).hexdigest() != sha):
                raise RuntimeError(f"{rel}: the stored row does not read back to its sha256")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ------------------------------------------------------------------ the web
# Through `requests`, so the worker's traffic probe (monitoring/probe.py, which
# wraps requests.Session) records every call on the monitoring dashboard.

_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        import requests
        _SESSION = requests.Session()
        _SESSION.headers["User-Agent"] = USER_AGENT
    return _SESSION


def fetch_text(url: str) -> str:
    r = _session().get(url, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str) -> bytes:
    r = _session().get(url, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.content


def head_size(url: str) -> int | None:
    """The file's size in raw bytes. `identity` matters: with requests' default
    Accept-Encoding the server answers with the GZIPPED size (measured
    2026-11-16: 1,204,719 for a 4,535,977-byte month), which never matches a
    stored file and would refetch every month every day."""
    try:
        r = _session().head(url, timeout=TIMEOUT_S, allow_redirects=True,
                            headers={"Accept-Encoding": "identity"})
        n = r.headers.get("Content-Length")
        return int(n) if r.ok and n and n.isdigit() else None
    except Exception:                                  # noqa: BLE001 - counted by run()
        return None


# ------------------------------------------------------------------ one run

def run(conn, *, dry_run: bool = False, get_text=fetch_text, get_bytes=fetch_bytes,
        get_size=head_size, binary=bytes, say=print, now=None) -> dict:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    listed = listed_files(get_text(LISTING))
    if not listed:
        raise RuntimeError(f"the listing at {LISTING} names no ANZ_Thoroughbreds file; "
                           "the page may have moved")
    stored = stored_rows(conn)
    held_months = [f for f in listed
                   if f["kind"] == "csv" and logical_files(stored, folder(f["name"]))]
    sizes = {f["name"]: get_size(f["url"]) for f in held_months}
    if held_months and all(v is None for v in sizes.values()):
        raise RuntimeError(f"the server gave no size for any of {len(held_months)} stored months; "
                           "the republished-file check cannot run")
    todo = plan(listed, stored, sizes)
    say(f"betfair listing: {len(listed)} files ({sum(f['kind'] == 'csv' for f in listed)} monthly, "
        f"{sum(f['kind'] == 'zip' for f in listed)} annual); {len(stored)} rows stored; "
        f"{sum(v is None for v in sizes.values())} stored months with no size from the server; "
        f"{len(todo)} to fetch")
    written = 0
    size_flagged = sum(item["why"].startswith("size") for item in todo)
    size_false = 0
    for item in todo:
        say(f"  fetch {item['name']} ({item['why']})")
        if dry_run:
            continue
        rows = rows_for(item, get_bytes(item["url"]), stored, stamp)
        if not rows:
            size_false += item["why"].startswith("size")
            say(f"    nothing new in {item['name']}: its bytes are already stored")
            continue
        store_file(conn, rows, binary=binary)
        for rel, raw in rows:
            stored[rel] = (hashlib.sha256(raw).hexdigest(), len(raw))
            say(f"    stored {rel} ({len(raw) / 1e6:.1f} MB), read back and matched")
        written += len(rows)
    say(f"betfair monthly: {written} row(s) stored" + (" (dry run: nothing downloaded)" if dry_run else ""))
    if len(held_months) >= 3 and size_flagged == len(held_months) and size_false == size_flagged:
        # Every stored month looked changed and none was: the server's size is not
        # the raw size (a compressed Content-Length did exactly this on 2026-11-16).
        raise RuntimeError(f"all {size_flagged} stored months had a different size on the server "
                           "and identical bytes: the size check is not measuring the file")
    return {"listed": len(listed), "to_fetch": len(todo), "written": written}


def _install_probe() -> None:
    """The worker's traffic probe, so this job's requests show on the monitoring
    dashboard. A monitoring failure must never stop the store."""
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("betfair-monthly-store")
    except Exception:                                  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="say what it would fetch; download and write nothing")
    a = ap.parse_args(argv)
    _install_probe()
    import psycopg2
    from data.db import get_connection
    conn = get_connection()
    try:
        run(conn, dry_run=a.dry_run, binary=psycopg2.Binary)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
