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
  * A monthly CSV already stored: asks the server for its size (a HEAD
    request). If the size differs from the stored file, downloads it and, if
    the bytes are new, stores them as a NEW row beside the old one
    (`<rel_path>#v<first 12 of sha256>`). A stored row is never overwritten
    or deleted (CLAUDE.md section 1b: no data is ever deleted).
  * An annual zip with no stored member: downloads it and stores each CSV in
    it, as `store_files` stored 2020-2025. A zip already seen is not fetched.
  * Reads every row it wrote back from the database, decompresses it and
    checks its sha256. Any mismatch fails the run.

WHERE ROWS GO. `nfl_research_data_backup`, `source =
'horse_racing|betfair_anz_thoroughbreds'`, `rel_path =
'horse/betfair-<file name>/<member>'`, exactly as `store_files` writes them, so
`store_files --restore` and the nightly PC copy see one set.

    python -m scripts.horse.betfair_monthly            # store what is new
    python -m scripts.horse.betfair_monthly --dry-run  # say what it would store
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import re
import sys
import urllib.parse
import urllib.request
import zipfile
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

_LINK = re.compile(r"""["'(]([^"'()\s<>]*ANZ_Thoroughbreds_\d{4}(?:_\d{2})?\.(?:csv|zip))""")
_NAME = re.compile(r"^ANZ_Thoroughbreds_\d{4}(?:_\d{2})?\.(csv|zip)$")


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


# ------------------------------------------------------------------ the plan

def plan(listed: list[dict], stored: dict[str, tuple[str, int]],
         sizes: dict[str, int | None]) -> list[dict]:
    """What to fetch. `stored` is rel_path -> (sha256, raw_bytes) for this source;
    `sizes` is a monthly CSV's size on the server (None when the server gave none)."""
    todo = []
    for f in listed:
        prefix = folder(f["name"])
        seen = [r for r in stored if r.startswith(prefix)]
        if not seen:
            todo.append({**f, "why": "new"})
            continue
        if f["kind"] != "csv":
            continue                                   # a zip already seen is not refetched
        size = sizes.get(f["name"])
        base_rel = prefix + f["name"]
        if size is not None and base_rel in stored and size != stored[base_rel][1]:
            sizes_held = {stored[r][1] for r in seen}
            if size not in sizes_held:
                todo.append({**f, "why": f"size {size:,} on the server, {stored[base_rel][1]:,} stored"})
    return todo


def rows_for(item: dict, blob: bytes, stored: dict[str, tuple[str, int]]) -> list[tuple[str, bytes]]:
    """(rel_path, raw bytes) for each row this file adds. Never a rel_path already
    stored; bytes already stored under this file's folder are not stored again."""
    prefix = folder(item["name"])
    shas_here = {sha for r, (sha, _) in stored.items() if r.startswith(prefix)}
    if item["kind"] == "csv":
        members = [(item["name"], blob)]
    else:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            members = [(Path(n).name, z.read(n)) for n in sorted(z.namelist())
                       if n.lower().endswith(".csv") and not n.endswith("/")]
        if not members:
            raise ValueError(f"{item['name']}: the zip holds no CSV")
    out = []
    for member, raw in members:
        sha = hashlib.sha256(raw).hexdigest()
        if sha in shas_here:
            continue
        rel = prefix + member
        if rel in stored or any(r.startswith(rel + "#") for r in stored):
            rel = f"{rel}#v{sha[:12]}"
        if rel in stored:
            continue
        if len(raw) <= PART_BYTES:
            out.append((rel, raw))
            continue
        n = (len(raw) + PART_BYTES - 1) // PART_BYTES
        for i in range(n):
            out.append((f"{rel}#part{i + 1:04d}of{n:04d}", raw[i * PART_BYTES:(i + 1) * PART_BYTES]))
    return out


# ------------------------------------------------------------------ the database

INSERT_SQL = (f"INSERT INTO {TABLE} (rel_path, source, sha256, raw_bytes, gz_bytes, content_gz) "
              f"VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (rel_path) DO NOTHING")


def stored_rows(conn) -> dict[str, tuple[str, int]]:
    rows = conn.execute(f"SELECT rel_path, sha256, raw_bytes FROM {TABLE} WHERE source = %s",
                        (SOURCE,)).fetchall()
    return {r[0]: (r[1], int(r[2])) for r in rows}


def insert_and_check(conn, rel: str, raw: bytes, binary=bytes) -> None:
    """Insert one row, then read it back, decompress it and match its sha256."""
    sha = hashlib.sha256(raw).hexdigest()
    gz = gzip.compress(raw, compresslevel=6)
    conn.execute(INSERT_SQL, (rel, SOURCE, sha, len(raw), len(gz), binary(gz)))
    conn.commit()
    got = conn.execute(f"SELECT sha256, content_gz FROM {TABLE} WHERE rel_path = %s",
                       (rel,)).fetchone()
    if got is None or got[0] != sha or hashlib.sha256(gzip.decompress(bytes(got[1]))).hexdigest() != sha:
        raise RuntimeError(f"{rel}: the stored row does not read back to its sha256")


# ------------------------------------------------------------------ the web

def _request(url: str, method: str = "GET"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method=method)
    return urllib.request.urlopen(req, timeout=TIMEOUT_S)


def fetch_text(url: str) -> str:
    with _request(url) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_bytes(url: str) -> bytes:
    with _request(url) as resp:
        return resp.read()


def head_size(url: str) -> int | None:
    try:
        with _request(url, "HEAD") as resp:
            n = resp.headers.get("Content-Length")
            return int(n) if n and n.isdigit() else None
    except Exception:                                  # noqa: BLE001 - the size check is optional
        return None


# ------------------------------------------------------------------ one run

def run(conn, *, dry_run: bool = False, get_text=fetch_text, get_bytes=fetch_bytes,
        get_size=head_size, binary=bytes, say=print) -> dict:
    listed = listed_files(get_text(LISTING))
    if not listed:
        raise RuntimeError(f"the listing at {LISTING} names no ANZ_Thoroughbreds file; "
                           "the page may have moved")
    stored = stored_rows(conn)
    sizes = {f["name"]: get_size(f["url"]) for f in listed
             if f["kind"] == "csv" and any(r.startswith(folder(f["name"])) for r in stored)}
    todo = plan(listed, stored, sizes)
    say(f"betfair listing: {len(listed)} files ({sum(f['kind'] == 'csv' for f in listed)} monthly, "
        f"{sum(f['kind'] == 'zip' for f in listed)} annual); {len(stored)} rows stored; "
        f"{len(todo)} to fetch")
    written = 0
    for item in todo:
        say(f"  fetch {item['name']} ({item['why']})")
        if dry_run:
            continue
        blob = get_bytes(item["url"])
        rows = rows_for(item, blob, stored)
        if not rows:
            say(f"    nothing new in {item['name']}: its bytes are already stored")
        for rel, raw in rows:
            insert_and_check(conn, rel, raw, binary=binary)
            stored[rel] = (hashlib.sha256(raw).hexdigest(), len(raw))
            written += 1
            say(f"    stored {rel} ({len(raw) / 1e6:.1f} MB), read back and matched")
    say(f"betfair monthly: {written} row(s) stored" + (" (dry run)" if dry_run else ""))
    return {"listed": len(listed), "stored_before": len(stored) - written,
            "to_fetch": len(todo), "written": written}


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
    ap.add_argument("--dry-run", action="store_true", help="say what it would store; write nothing")
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
