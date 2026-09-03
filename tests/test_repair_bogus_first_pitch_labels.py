"""The label repair must not be able to relabel without a durable backup.

`odds` has no audit trigger and the flip is not self-reversing: once a row
reads 'open' the repair's own query no longer finds it, and widening to
snapshot_type='open' would sweep up rows that were legitimately open. So the
backup table IS the undo, and these tests pin that it is written, counted, and
that a miscount aborts the whole thing rather than half of it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import repair_bogus_first_pitch_labels as R

ROW = dict(zip(R.COLUMNS, (1, "MLB_g", "MLB", "dk", "totals",
                           "2026-08-29T20:00:00Z", "in_play",
                           "2026-08-29T16:50:01Z", "2026-08-29T23:16:00Z")))


class _Conn:
    """Records every statement. `backup_count` is what the verify SELECT sees,
    so a test can make the backup come up short."""

    def __init__(self, backup_count=1):
        self.sql = []
        self.backup_count = backup_count
        self.committed = False
        self.rolled_back = False

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))
        self._last = sql
        return self

    def fetchone(self):
        return (self.backup_count,)

    def fetchall(self):
        return [(1,)] if "UPDATE odds" in self._last else []

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _run(conn, monkeypatch, tmp_path, argv):
    monkeypatch.setattr(R, "get_connection", lambda: conn)
    monkeypatch.setattr(R, "find_rows", lambda c: [ROW] if not conn.committed else [])
    monkeypatch.setattr(sys, "argv", ["x", "--backup-dir", str(tmp_path)] + argv)
    return R.main()


def test_the_backup_is_written_before_the_update(monkeypatch, tmp_path):
    conn = _Conn(backup_count=1)
    assert _run(conn, monkeypatch, tmp_path, ["--apply"]) == 0
    joined = " || ".join(conn.sql)
    create = joined.index("CREATE TABLE")
    update = joined.index("UPDATE odds")
    assert create < update, conn.sql
    assert conn.committed


def test_a_short_backup_rolls_back_and_relabels_nothing(monkeypatch, tmp_path):
    """The whole point of counting it. A CREATE TABLE AS that silently copied
    fewer rows would leave rows with no way back."""
    conn = _Conn(backup_count=0)          # backup came up short
    assert _run(conn, monkeypatch, tmp_path, ["--apply"]) == 1
    assert conn.rolled_back
    assert not conn.committed
    assert not any("UPDATE odds" in s for s in conn.sql), conn.sql


def test_the_backup_table_is_revoked_from_the_public_roles(monkeypatch, tmp_path):
    """Default privileges grant anon/authenticated ALL on a new public table,
    and REVOKE ... FROM PUBLIC does not touch a named role (the ops rule)."""
    conn = _Conn(backup_count=1)
    _run(conn, monkeypatch, tmp_path, ["--apply"])
    assert any("REVOKE ALL ON" in s and "anon, authenticated" in s
               for s in conn.sql), conn.sql


def test_a_dry_run_writes_nothing_at_all(monkeypatch, tmp_path):
    conn = _Conn()
    assert _run(conn, monkeypatch, tmp_path, []) == 0
    assert conn.sql == [], conn.sql
    assert not conn.committed


def test_the_query_is_scoped_to_the_scheduled_start_not_the_derived_one():
    """48,712 rows in this database are labelled in_play by the LIVE LOOP with
    a timestamp at or before their scheduled start. Bounding on the derived
    first pitch instead would sweep those in and manufacture the leak
    relabel_in_play exists to remove."""
    sql = " ".join(R.SELECT_SQL.split())
    assert "o.snapshot_at::timestamptz <= b.commence_time::timestamptz" in sql
    assert f"interval '{R.SUSPICIOUS_EARLY_MINUTES} minutes'" in sql
    assert "o.snapshot_type = 'in_play'" in sql


def test_the_bogus_set_is_computed_never_listed():
    """A hard-coded game list goes stale the next time the derivation misfires."""
    assert "MLB_2026-08-29_ARI_SF" not in R.SELECT_SQL
