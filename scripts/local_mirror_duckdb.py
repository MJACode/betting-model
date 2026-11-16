#!/usr/bin/env python
"""SQL over mike's PC copy of Supabase: one DuckDB file of views.

mike, 2026-11-15: "Yes, set it up" (DuckDB, so the PC copy can be queried with
SQL). The copy itself is unchanged: `scripts/local_mirror.py` writes each table
as Parquet files plus a `manifest.json`. This script writes
`betting_local_copies\\betting.duckdb`, which holds VIEWS only, no rows. Each
view reads exactly the files the table's manifest lists, so a file the copy
has not finished, or one it replaced, is never counted. Rebuilding it takes
seconds and loses nothing.

WHAT A QUERY SEES
  * `public` tables under their own names: `select * from player_prop_odds`.
  * `<table>__vanished` for a table whose `vanished\\` folder holds rows that
    left Supabase (local_mirror.py keeps them; capper_picks is the first).
  * `mirror_tables`: one row per table, with the manifest's row count, the
    view's row count, the file count, when it was last copied, and any column
    left as text.
  * The copy stores `numeric`, `jsonb` and `uuid` columns as text. The views
    read them back as DOUBLE, JSON and UUID. A column with a value that does
    not convert is left as text and named in `mirror_tables.text_columns`;
    nothing is silently turned into NULL. Columns that are text in Supabase
    (games.commence_time, for one) stay text, exactly as there.
  * Supabase's own schemas (auth, storage, realtime, vault) are left out unless
    asked for with --schemas.

USE
  python scripts/local_mirror_duckdb.py build           # rebuild, then check every view
  python scripts/local_mirror_duckdb.py sql "select count(*) from odds"
  In Python: duckdb.connect(r"...\\betting.duckdb", read_only=True).sql("...").df()
  The DuckDB CLI (winget: DuckDB.cli, the same 1.5 line) opens the file too.

The nightly copy (`scripts/local_mirror_run.ps1`) runs `build` after it ends.
While a copy is running, a view can name a file the copy just replaced; the
query then fails with a missing-file error until the next build.

Standalone on purpose: it runs as `python -I bin\\local_mirror_duckdb.py`, so it
imports nothing from the repo. It never connects to Supabase.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\micha\Documents\betting_local_copies")
DEFAULT_MIRROR = DEFAULT_ROOT / "supabase_mirror"
DEFAULT_DB = DEFAULT_ROOT / "betting.duckdb"
DEFAULT_SCHEMAS = ("public",)


def read_as(pg_type: str, arrow: str) -> str | None:
    """The DuckDB type a text-stored column is read back as; None keeps it."""
    if arrow != "string":
        return None
    t = (pg_type or "").lower()
    if t == "numeric" or t.startswith("numeric("):
        return "DOUBLE"
    if t in ("jsonb", "json"):
        return "JSON"
    if t == "uuid":
        return "UUID"
    return None


# How the copy's Parquet types read in DuckDB, for a table with no rows (and so
# no file to read the types from).
ARROW_TO_DUCK = {
    "string": "VARCHAR", "large_string": "VARCHAR", "bool": "BOOLEAN",
    "int16": "SMALLINT", "int32": "INTEGER", "int64": "BIGINT",
    "float": "FLOAT", "double": "DOUBLE", "date32[day]": "DATE",
    "timestamp[us]": "TIMESTAMP", "timestamp[us, tz=UTC]": "TIMESTAMPTZ",
    "binary": "BLOB", "large_binary": "BLOB",
}


def _empty_table_sql(target: str, columns: list[dict]) -> str:
    cols = ", ".join(
        f"{_q(c['name'])} "
        f"{read_as(c.get('pg_type', ''), c.get('arrow', '')) or ARROW_TO_DUCK.get(c.get('arrow', ''), 'VARCHAR')}"
        for c in columns)
    return f"CREATE OR REPLACE TABLE {target} ({cols})"


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(path: Path | str) -> str:
    return "'" + str(path).replace("\\", "/").replace("'", "''") + "'"


def _files_sql(files: list[Path]) -> str:
    return "[" + ", ".join(_lit(f) for f in files) + "]"


def _select(columns: list[dict], present: set[str], keep_text: set[str]) -> str:
    parts = []
    for c in columns:
        name = c["name"]
        if name not in present:
            continue
        to = None if name in keep_text else read_as(c.get("pg_type", ""), c.get("arrow", ""))
        parts.append(f"CAST({_q(name)} AS {to}) AS {_q(name)}" if to else _q(name))
    # Columns in older files that the current manifest no longer lists.
    listed = {c["name"] for c in columns}
    parts += [_q(n) for n in sorted(present - listed)]
    return ", ".join(parts)


def _present_columns(con, files_sql: str) -> set[str]:
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet({files_sql}, union_by_name = true)").fetchall()
    return {r[0] for r in rows}


def _view_target(schema: str, view: str) -> str:
    return _q(view) if schema == "public" else f"{_q(schema)}.{_q(view)}"


def _create_view(con, schema, view, columns, files_sql, keep_text) -> None:
    present = _present_columns(con, files_sql)
    con.execute(
        f"CREATE OR REPLACE VIEW {_view_target(schema, view)} AS "
        f"SELECT {_select(columns, present, keep_text)} "
        f"FROM read_parquet({files_sql}, union_by_name = true)")


def _check(con, schema, view, columns, files_sql, keep_text) -> tuple[int, set[str]]:
    """Read every converted column of every row. Returns (rows, columns that failed)."""
    target = _view_target(schema, view)
    present = _present_columns(con, files_sql)
    cast = [c["name"] for c in columns if c["name"] in present and c["name"] not in keep_text
            and read_as(c.get("pg_type", ""), c.get("arrow", ""))]
    counts = ", ".join(f"count({_q(n)})" for n in cast)
    try:
        n = con.execute(f"SELECT count(*){', ' + counts if counts else ''} FROM {target}").fetchone()[0]
        return n, set()
    except Exception:  # noqa: BLE001 - find which column, below
        failed = set()
        for name in cast:
            try:
                con.execute(f"SELECT count({_q(name)}) FROM {target}").fetchone()
            except Exception:  # noqa: BLE001
                failed.add(name)
        if not failed:
            raise
        return -1, failed


def build(mirror: Path, db: Path, schemas=DEFAULT_SCHEMAS, verify: bool = True,
          log=print) -> list[dict]:
    import duckdb

    mirror, db = Path(mirror), Path(db)
    tables_dir = mirror / "tables"
    if not tables_dir.is_dir():
        raise SystemExit(f"no tables folder at {tables_dir}")
    tmp = db.with_name(db.name + ".new")
    if tmp.exists():
        tmp.unlink()
    con = duckdb.connect(str(tmp))
    report = []
    started = time.time()
    try:
        for d in sorted(p for p in tables_dir.iterdir() if p.is_dir()):
            schema, _, table = d.name.partition(".")
            if schema not in schemas or not table:
                continue
            man_path = d / "manifest.json"
            if not man_path.exists():
                continue
            man = json.loads(man_path.read_text(encoding="utf-8"))
            columns = man.get("columns") or []
            files = [d / c["file"] for c in man.get("chunks") or []]
            missing = [f for f in files if not f.exists()]
            row = {"schema": schema, "table": table, "manifest_rows": man.get("rows"),
                   "view_rows": None, "files": len(files), "last_copied": man.get("last_run"),
                   "text_columns": "", "note": ""}
            report.append(row)
            if schema != "public":
                con.execute(f"CREATE SCHEMA IF NOT EXISTS {_q(schema)}")
            if not files:
                if (man.get("rows") or 0) == 0 and columns:
                    # Empty in Supabase too: an empty table with the same
                    # columns, so a query finds it instead of failing.
                    con.execute(_empty_table_sql(_view_target(schema, table), columns))
                    row["view_rows"] = 0
                else:
                    row["note"] = "no data files"
                continue
            if missing:
                row["note"] = f"{len(missing)} listed files missing; copy still running?"
                continue
            views = [(table, files)]
            vanished = sorted((d / "vanished").glob("*.parquet"))
            if vanished:
                views.append((f"{table}__vanished", vanished))
            for view, vfiles in views:
                files_sql = _files_sql(vfiles)
                keep_text: set[str] = set()
                _create_view(con, schema, view, columns, files_sql, keep_text)
                if not verify:
                    continue
                n, failed = _check(con, schema, view, columns, files_sql, keep_text)
                if failed:
                    keep_text |= failed
                    _create_view(con, schema, view, columns, files_sql, keep_text)
                    n, _ = _check(con, schema, view, columns, files_sql, keep_text)
                    row["text_columns"] = ", ".join(sorted(keep_text))
                if view == table:
                    row["view_rows"] = n
                    if man.get("rows") is not None and n != man["rows"]:
                        row["note"] = f"view has {n:,} rows, manifest says {man['rows']:,}"
        con.execute("""CREATE OR REPLACE TABLE mirror_tables (
            schema_name VARCHAR, table_name VARCHAR, manifest_rows BIGINT, view_rows BIGINT,
            files INTEGER, last_copied VARCHAR, text_columns VARCHAR, note VARCHAR,
            built_at TIMESTAMPTZ DEFAULT now())""")
        con.executemany(
            "INSERT INTO mirror_tables (schema_name, table_name, manifest_rows, view_rows, files,"
            " last_copied, text_columns, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(r["schema"], r["table"], r["manifest_rows"], r["view_rows"], r["files"],
              r["last_copied"], r["text_columns"], r["note"]) for r in report])
    finally:
        con.close()
    os.replace(tmp, db)
    bad = [r for r in report if r["note"]]
    log(f"built {db} in {time.time() - started:.0f} s: {len(report)} tables, "
        f"{sum(r['view_rows'] or 0 for r in report):,} rows checked, {len(bad)} with a note")
    for r in bad:
        log(f"  {r['schema']}.{r['table']}: {r['note']}")
    for r in report:
        if r["text_columns"]:
            log(f"  {r['schema']}.{r['table']}: left as text: {r['text_columns']}")
    return report


def run_sql(db: Path, query: str) -> None:
    import duckdb
    con = duckdb.connect(str(db), read_only=True)
    try:
        con.sql(query).show(max_rows=200)
    finally:
        con.close()


def main(argv=None) -> int:
    # `python -I` ignores PYTHONIOENCODING, and the Windows console default
    # (cp1252) cannot print DuckDB's table borders.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="rebuild the views, then read every one")
    b.add_argument("--mirror", type=Path, default=DEFAULT_MIRROR)
    b.add_argument("--db", type=Path, default=DEFAULT_DB)
    b.add_argument("--schemas", default=",".join(DEFAULT_SCHEMAS),
                   help="comma-separated, e.g. public,auth")
    b.add_argument("--no-verify", action="store_true")
    s = sub.add_parser("sql", help="run one query and print the result")
    s.add_argument("query")
    s.add_argument("--db", type=Path, default=DEFAULT_DB)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        report = build(a.mirror, a.db, tuple(x.strip() for x in a.schemas.split(",") if x.strip()),
                       verify=not a.no_verify)
        return 1 if any("rows, manifest says" in r["note"] for r in report) else 0
    run_sql(a.db, a.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())
