"""SQL over the PC copy: the DuckDB views read exactly what each manifest lists.

scripts/local_mirror_duckdb.py (mike, 2026-11-15: "Yes, set it up") writes a
DuckDB file of views over scripts/local_mirror.py's Parquet folders. These
tests build a small copy on disk, the way local_mirror lays it out, and check:
  * a view counts only the files its manifest lists, not a stray file;
  * numeric, jsonb and uuid come back typed, and a value that will not
    convert keeps its column as text, named, instead of becoming NULL;
  * rows the copy kept in vanished/ have their own view;
  * an empty table is still there to query;
  * Supabase's own schemas stay out unless asked for;
  * the nightly run script refreshes and runs it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")
duckdb = pytest.importorskip("duckdb")

from scripts import local_mirror_duckdb as ldb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

COLUMNS = [
    {"name": "id", "pg_type": "bigint", "arrow": "int64"},
    {"name": "price", "pg_type": "numeric", "arrow": "string"},
    {"name": "meta", "pg_type": "jsonb", "arrow": "string"},
    {"name": "uid", "pg_type": "uuid", "arrow": "string"},
    {"name": "label", "pg_type": "text", "arrow": "string"},
]
UID = "47744bc7-86c1-443e-921d-f2bf55cf72cd"


def _rows(ids, price="1.5"):
    return pa.table({
        "id": pa.array(ids, pa.int64()),
        "price": pa.array([price] * len(ids), pa.string()),
        "meta": pa.array(['{"book": "dk"}'] * len(ids), pa.string()),
        "uid": pa.array([UID] * len(ids), pa.string()),
        "label": pa.array([f"r{i}" for i in ids], pa.string()),
    })


def _table(mirror: Path, fq: str, chunks: list, *, stray=None, vanished=None, rows=None):
    d = mirror / "tables" / fq
    d.mkdir(parents=True)
    listed = []
    for i, tbl in enumerate(chunks, start=1):
        name = f"chunk_{i:07d}.parquet"
        pq.write_table(tbl, d / name)
        listed.append({"id": i, "file": name, "rows": tbl.num_rows})
    if stray is not None:  # a file the copy wrote but the manifest does not list
        pq.write_table(stray, d / f"chunk_{len(chunks) + 1:07d}.parquet")
    if vanished is not None:
        (d / "vanished").mkdir()
        pq.write_table(vanished, d / "vanished" / "vanished_20261115T140030Z_chunk_0000013.parquet")
    total = sum(t.num_rows for t in chunks) if rows is None else rows
    (d / "manifest.json").write_text(json.dumps({
        "table": fq, "mode": "incremental", "columns": COLUMNS, "chunks": listed,
        "rows": total, "last_run": "2026-11-15T12:37:34+00:00"}), encoding="utf-8")


@pytest.fixture
def copy(tmp_path):
    mirror = tmp_path / "supabase_mirror"
    _table(mirror, "public.prices", [_rows([1, 2]), _rows([3])], stray=_rows([4, 5, 6]),
           vanished=_rows([90]))
    _table(mirror, "public.bad_numeric", [_rows([1], price="not a number"), _rows([2])])
    _table(mirror, "public.empty", [], rows=0)
    _table(mirror, "auth.users", [_rows([1])])
    return mirror, tmp_path / "betting.duckdb"


def _con(db):
    return duckdb.connect(str(db), read_only=True)


def test_a_view_counts_only_the_files_its_manifest_lists(copy):
    mirror, db = copy
    ldb.build(mirror, db, log=lambda *_: None)
    con = _con(db)
    assert con.sql("select count(*) from prices").fetchone()[0] == 3
    assert con.sql("select view_rows, manifest_rows, note from mirror_tables "
                   "where table_name = 'prices'").fetchone() == (3, 3, "")


def test_text_stored_columns_read_back_typed(copy):
    mirror, db = copy
    ldb.build(mirror, db, log=lambda *_: None)
    con = _con(db)
    types = dict(con.sql("select column_name, column_type from (describe prices)").fetchall())
    assert types == {"id": "BIGINT", "price": "DOUBLE", "meta": "JSON",
                     "uid": "UUID", "label": "VARCHAR"}
    assert con.sql("select sum(price), max(meta->>'book') from prices").fetchone() == (4.5, "dk")


def test_a_value_that_will_not_convert_keeps_its_column_as_text(copy):
    mirror, db = copy
    report = ldb.build(mirror, db, log=lambda *_: None)
    con = _con(db)
    assert dict(con.sql("select column_name, column_type from (describe bad_numeric)")
                .fetchall())["price"] == "VARCHAR"
    assert sorted(con.sql("select price from bad_numeric").fetchall()) == [
        ("1.5",), ("not a number",)]
    assert [r["text_columns"] for r in report if r["table"] == "bad_numeric"] == ["price"]
    # the other text-stored columns of that table still convert
    assert dict(con.sql("select column_name, column_type from (describe bad_numeric)")
                .fetchall())["uid"] == "UUID"


def test_rows_kept_in_vanished_have_their_own_view(copy):
    mirror, db = copy
    ldb.build(mirror, db, log=lambda *_: None)
    assert _con(db).sql("select id from prices__vanished").fetchall() == [(90,)]


def test_an_empty_table_is_still_there_to_query(copy):
    mirror, db = copy
    ldb.build(mirror, db, log=lambda *_: None)
    con = _con(db)
    assert con.sql("select count(*) from empty").fetchone()[0] == 0
    assert dict(con.sql("select column_name, column_type from (describe empty)")
                .fetchall())["price"] == "DOUBLE"


def test_supabase_schemas_stay_out_unless_asked_for(copy):
    mirror, db = copy
    ldb.build(mirror, db, log=lambda *_: None)
    assert "users" not in {r[0] for r in _con(db).sql("show tables").fetchall()}
    ldb.build(mirror, db, schemas=("public", "auth"), log=lambda *_: None)
    assert _con(db).sql("select count(*) from auth.users").fetchone()[0] == 1


def test_a_count_that_disagrees_with_the_manifest_is_reported(copy, tmp_path):
    mirror, db = copy
    man = mirror / "tables" / "public.prices" / "manifest.json"
    m = json.loads(man.read_text(encoding="utf-8"))
    m["rows"] = 99
    man.write_text(json.dumps(m), encoding="utf-8")
    report = ldb.build(mirror, db, log=lambda *_: None)
    assert [r["note"] for r in report if r["table"] == "prices"] == [
        "view has 3 rows, manifest says 99"]
    assert ldb.main(["build", "--mirror", str(mirror), "--db", str(db)]) == 1


def test_the_nightly_run_refreshes_and_runs_the_build():
    ps1 = (ROOT / "scripts" / "local_mirror_run.ps1").read_text(encoding="utf-8")
    assert '"local_mirror_duckdb.py"' in ps1  # refreshed from origin/master
    assert "local_mirror_duckdb.py`\"\", \"build\"" in ps1
    # it runs after the Supabase copy has finished, not alongside it
    assert ps1.index("local_mirror.py`\"\", \"run\"") < ps1.index("local_mirror_duckdb.py`\"\", \"build\"")
