"""The in-app notifications inbox (Matt, 2026-11-14).

Three halves are pinned here:

* the worker saves every push to notification_inbox word for word, whether or
  not any phone has push on (Matt chose "unread + muted"), puts the row's id in
  the push as `inboxId`, and never lets the inbox write touch the push_sent
  ledger -- a missing table or a failed insert still ledgers and still sends;
* the migration: RLS on, table grants revoked, four device-keyed SECURITY
  DEFINER functions granted to the app, a 30-day window, and a catalog-read
  early return so the worker's every-pass run takes no lock;
* the app's pure logic, mobile/scripts/verify_notification_inbox.ts, under node.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from tracking import push_notifier  # noqa: E402

MIGRATION = ROOT / "data" / "migrations" / "notification_inbox_2026_11_14.sql"
MOBILE = ROOT / "mobile"

SIG = {"lock_key": "k1", "label": "BUF +1", "sport": "NFL", "pick_id": 7,
       "model_id": "nfl_opener_spread", "side": "away", "line": -1.0,
       "home": "HOU", "away": "BUF"}


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Records every statement. `table` says whether notification_inbox
    exists; `fail_insert` makes the inbox INSERT raise."""

    def __init__(self, tokens=(), table=True, fail_insert=False):
        self.tokens = list(tokens)
        self.table = table
        self.fail_insert = fail_insert
        self.calls: list[tuple[str, tuple]] = []
        self.next_id = 100

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if "to_regclass('public.notification_inbox')" in sql:
            return _Res([(self.table,)])
        if "INSERT INTO notification_inbox" in sql:
            if self.fail_insert:
                raise RuntimeError("boom")
            self.next_id += 1
            return _Res([(self.next_id,)])
        if "FROM device_push_tokens" in sql:
            return _Res([(t,) for t in self.tokens])
        return _Res([])

    def commit(self):
        pass

    def close(self):
        pass

    def inbox(self):
        return [p for sql, p in self.calls if "INSERT INTO notification_inbox" in sql]

    def ledgered(self):
        return {p[0] for sql, p in self.calls if "INSERT INTO push_sent" in sql}


@pytest.fixture
def sent(monkeypatch):
    out: list[dict] = []
    monkeypatch.setattr(push_notifier, "_expo_send",
                        lambda msgs, conn=None: out.extend(msgs) or len(msgs))
    monkeypatch.setattr(push_notifier, "_new_bet_signals", lambda c, d: [SIG])
    monkeypatch.setattr(push_notifier, "_dropped_signals", lambda c, d: [])
    return out


def test_a_push_is_saved_word_for_word_and_carries_its_inbox_id(sent):
    conn = _Conn(tokens=["ExponentPushToken[abcdefghijkl]"])
    push_notifier._send_signal_changes(conn, "2026-11-14", False)
    [row] = conn.inbox()
    device_id, kind, title, body, _data = row
    [msg] = sent
    assert (device_id, kind) == (None, "new_bets")
    assert (title, body) == (msg["title"], msg["body"])
    assert msg["data"]["inboxId"] == 101
    assert conn.ledgered() == {"k1"}


def test_with_no_phone_registered_the_inbox_still_gets_it(sent):
    """Matt's "unread + muted": a phone with push off still sees what it missed."""
    conn = _Conn(tokens=[])
    push_notifier._send_signal_changes(conn, "2026-11-14", False)
    assert len(conn.inbox()) == 1
    assert sent == []
    assert conn.ledgered() == {"k1"}


def test_before_the_migration_the_push_still_goes_and_still_ledgers(sent):
    conn = _Conn(tokens=["ExponentPushToken[abcdefghijkl]"], table=False)
    push_notifier._send_signal_changes(conn, "2026-11-14", False)
    assert conn.inbox() == []
    [msg] = sent
    assert "inboxId" not in msg["data"]
    assert conn.ledgered() == {"k1"}


def test_a_failed_inbox_write_rolls_back_to_its_savepoint_only(sent):
    conn = _Conn(tokens=["ExponentPushToken[abcdefghijkl]"], fail_insert=True)
    push_notifier._send_signal_changes(conn, "2026-11-14", False)
    stmts = [sql for sql, _ in conn.calls]
    assert "ROLLBACK TO SAVEPOINT notification_inbox" in stmts
    assert len(sent) == 1 and "inboxId" not in sent[0]["data"]
    assert conn.ledgered() == {"k1"}


def test_a_dry_run_saves_nothing(sent):
    conn = _Conn(tokens=["ExponentPushToken[abcdefghijkl]"])
    push_notifier._send_signal_changes(conn, "2026-11-14", True)
    assert conn.inbox() == []


def test_a_line_change_goes_to_the_tracking_devices_inbox_only(monkeypatch):
    out: list[dict] = []
    monkeypatch.setattr(push_notifier, "_expo_send",
                        lambda msgs, conn=None: out.extend(msgs) or len(msgs))
    alert = dict(SIG, device_id="dev-12345678", kind="line_change_1",
                 locked=-115, current=-130, against=True)
    monkeypatch.setattr(push_notifier, "_line_change_alerts", lambda c, d: [alert])

    class _LC(_Conn):
        def execute(self, sql, params=()):
            if "SELECT device_id, token FROM device_push_tokens" in sql:
                self.calls.append((sql, tuple(params)))
                return _Res([])  # push is off on that phone
            return super().execute(sql, params)

    conn = _LC()
    monkeypatch.setattr(push_notifier, "get_connection", lambda: conn)
    push_notifier.notify_line_changes("2026-11-14")
    [row] = conn.inbox()
    assert row[0] == "dev-12345678" and row[1] == "line_change"
    assert out == []


def test_the_live_and_feedback_producers_save_too():
    src = (ROOT / "tracking" / "push_notifier.py").read_text(encoding="utf-8")
    assert '_save_to_inbox(conn, "live_signals"' in src
    assert '"feedback_reply", title, body, data, device_id=r["device_id"]' in src


# ── the migration ────────────────────────────────────────────────────────────

def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_the_migration_runs_on_the_worker():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIGRATION.name in ACTIVE_MIGRATIONS


def test_the_tables_are_closed_to_the_app():
    sql = _sql()
    for t in ("notification_inbox", "notification_reads", "notification_read_marks"):
        assert f"ALTER TABLE public.{t}" in sql and "ENABLE ROW LEVEL SECURITY" in sql
        assert re.search(rf"REVOKE ALL ON public\.{t}\s+FROM anon, authenticated", sql), t


def test_the_app_functions_are_definer_keyed_and_granted():
    from data.anon_readable import RPC_ANON_CALLABLE
    sql = _sql()
    for fn in ("notification_inbox_for_device", "notification_unread_count",
               "notification_mark_read", "notification_mark_all_read"):
        assert fn in RPC_ANON_CALLABLE, fn
        body = sql[sql.index(f"FUNCTION public.{fn}("):]
        body = body[:body.index("$fn$;")]
        assert "SECURITY DEFINER" in body and "SET search_path = ''" in body, fn
        assert "p_device_id" in body, fn
        assert re.search(rf"GRANT EXECUTE ON FUNCTION public\.{fn}\(", sql), fn
        assert re.search(rf"REVOKE ALL ON FUNCTION public\.{fn}\([^)]*\) FROM PUBLIC", sql), fn


def test_the_window_is_thirty_days_and_rows_are_never_deleted_by_age():
    sql = _sql()
    assert sql.count("interval '30 days'") == 2  # the list and the badge
    assert "DELETE FROM public.notification_inbox" not in sql


def test_a_second_pass_returns_on_a_catalog_read():
    sql = _sql()
    head = sql[sql.index("DO $mig$"):sql.index("CREATE TABLE")]
    assert "RETURN;" in head and "to_regclass('public.notification_inbox')" in head


# ── the app's logic ──────────────────────────────────────────────────────────

def test_the_inbox_helpers_hold():
    from tests._node import NODE, node_strips_types
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    script = (MOBILE / "scripts" / "verify_notification_inbox.ts").read_text(encoding="utf-8")
    script = script.replace("from '../src/lib/notificationInboxHelpers';",
                            "from './notificationInboxHelpers.ts';")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify.ts").write_text(script, encoding="utf-8")
        (folder / "notificationInboxHelpers.ts").write_text(
            (MOBILE / "src" / "lib" / "notificationInboxHelpers.ts").read_text(encoding="utf-8"),
            encoding="utf-8")
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run([NODE, "--experimental-strip-types", "verify.ts"],
                              cwd=folder, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[FAIL]" not in proc.stdout
    assert "[PASS] today is the ET day, not the UTC one" in proc.stdout


def test_the_helpers_import_nothing():
    src = (MOBILE / "src" / "lib" / "notificationInboxHelpers.ts").read_text(encoding="utf-8")
    assert not re.search(r"^import ", src, flags=re.M)


def test_tapping_the_push_clears_its_inbox_row():
    src = (MOBILE / "src" / "hooks" / "usePushDeepLink.ts").read_text(encoding="utf-8")
    assert "inboxIdFromPush(pushData)" in src and "markNotificationRead(inboxId)" in src


def test_the_bell_sits_with_every_settings_gear():
    src = (MOBILE / "src" / "components" / "SettingsButton.tsx").read_text(encoding="utf-8")
    assert "<NotificationsButton />" in src
