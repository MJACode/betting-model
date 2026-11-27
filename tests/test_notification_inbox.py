"""Notification inbox: mute filter, one row per alert, 7-day delete gate.

The hand migration is not applied here. These tests run the pure filter and
the deletion gate. A scratch cluster, when initdb is installed, checks that
RLS hides another user's rows.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "notification_inbox_2026_11_19.sql"


def test_the_migration_is_hand_applied():
    from data.view_migrations import ACTIVE_MIGRATIONS

    sql = MIG.read_text(encoding="utf-8")
    assert MIG.name not in ACTIVE_MIGRATIONS
    assert "HAND APPLIED" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "user_id = (SELECT auth.uid())" in sql
    assert "REVOKE ALL ON public.notification_inbox FROM PUBLIC, anon, authenticated" in sql
    assert "GRANT SELECT, INSERT, UPDATE ON public.notification_inbox TO authenticated" in sql
    assert "notification_sport_prefs" in sql
    assert "EUROLEAGUE" in sql
    assert "p_user_id uuid DEFAULT NULL" in sql
    # The 5-arg overload would make PostgREST return 300. It is dropped.
    assert "DROP FUNCTION IF EXISTS public.save_device_push_token(text, text, text, boolean, text)" in sql
    assert "v_uid := auth.uid()" in sql
    assert "p_user_id IS DISTINCT FROM v_uid" in sql
    assert "ERRCODE = '42501'" in sql
    assert "user_id   = v_uid" in sql
    assert "forget_my_notifications" in sql
    assert "ON DELETE CASCADE" in sql
    assert "ON DELETE SET NULL" in sql


def test_a_muted_sport_is_dropped_and_an_empty_batch_sends_nothing():
    from tracking.notification_inbox import visible_signals

    signals = [
        {"sport": "NBA", "label": "a", "pick_id": 1},
        {"sport": "NFL", "label": "b", "pick_id": 2},
        {"sport": "UFC", "label": "c", "pick_id": 3},
    ]
    kept = visible_signals(signals, {"UFC"})
    assert [s["sport"] for s in kept] == ["NBA", "NFL"]
    assert visible_signals(signals, {"NBA", "NFL", "UFC"}) == []
    # No sport (feedback, the Settings test) is not a mute.
    assert visible_signals([{"label": "reply"}], {"NBA"}) == [{"label": "reply"}]


def test_one_remaining_pick_keeps_a_single_pick_route():
    from tracking.notification_inbox import visible_signals
    from tracking.push_notifier import _build_messages

    signals = [
        {"sport": "NCAAB", "label": "First Half Charleston Southern +2.5", "pick_id": 9},
        {"sport": "UFC", "label": "muted fighter", "pick_id": 10},
    ]
    kept = visible_signals(signals, {"UFC"})
    messages = _build_messages(["ExponentPushToken[abcdefghij]"], kept)
    assert len(messages) == 1
    assert messages[0]["title"] == "🟢 1 new BET signal"
    assert messages[0]["data"]["pickId"] == 9
    assert messages[0]["data"]["sport"] == "NCAAB"
    assert "data" in messages[0]


def test_a_multi_sport_remainder_does_not_name_one_sport():
    from tracking.notification_inbox import visible_signals
    from tracking.push_notifier import _build_messages

    signals = [
        {"sport": "NBA", "label": "A", "pick_id": 1},
        {"sport": "NFL", "label": "B", "pick_id": 2},
        {"sport": "UFC", "label": "C", "pick_id": 3},
    ]
    kept = visible_signals(signals, {"UFC"})
    msg = _build_messages(["ExponentPushToken[abcdefghij]"], kept)[0]
    assert msg["title"] == "🟢 2 new BET signals"
    assert "pickId" not in msg["data"]
    assert "sport" not in msg["data"]


def test_attach_inbox_writes_one_row_per_alert_and_shares_it_across_devices():
    from tracking.notification_inbox import attach_inbox

    messages = [
        {"to": "a", "title": "🟢 1 new BET signal", "body": "Lakers", "data": {"v": 1, "type": "new_bets", "pickId": 4, "sport": "NBA"}},
        {"to": "b", "title": "🟢 1 new BET signal", "body": "Lakers", "data": {"v": 1, "type": "new_bets", "pickId": 4, "sport": "NBA"}},
    ]
    rows: list[dict] = []
    attach_inbox("user-1", messages, rows, {"user-1": 2})
    assert len(rows) == 1
    assert rows[0]["user_id"] == "user-1"
    assert rows[0]["kind"] == "new_bets"
    assert rows[0]["sport"] == "NBA"
    assert messages[0]["data"]["inboxId"] == rows[0]["notification_id"]
    assert messages[1]["data"]["inboxId"] == rows[0]["notification_id"]
    assert messages[0]["badge"] == 3
    assert messages[1]["badge"] == 3


def test_a_device_with_no_user_is_not_given_an_inbox_row():
    from tracking.notification_inbox import attach_inbox

    messages = [{"to": "a", "title": "t", "body": "b", "data": {"type": "new_bets"}}]
    rows: list[dict] = []
    attach_inbox(None, messages, rows, {})
    assert rows == []
    assert "badge" not in messages[0]
    assert "inboxId" not in messages[0]["data"]


def test_line_change_mute_skips_that_sport_only():
    from tracking.notification_inbox import sport_is_muted

    mutes = {"user-1": {"UFC"}}
    assert sport_is_muted("user-1", "UFC", mutes) is True
    assert sport_is_muted("user-1", "NBA", mutes) is False
    assert sport_is_muted(None, "UFC", mutes) is False
    assert sport_is_muted("user-1", None, mutes) is False


def test_prune_deletes_nothing_without_approval():
    from tracking.notification_inbox import prune_notification_inbox

    class Conn:
        def __init__(self):
            self.sql: list[str] = []

        def execute(self, sql, params=None):
            self.sql.append(sql)
            raise AssertionError("the gated prune must not touch the database")

    conn = Conn()
    assert prune_notification_inbox(conn) == 0
    assert conn.sql == []


def test_inbox_ready_is_false_when_the_probe_returns_nothing():
    from tracking.notification_inbox import inbox_ready

    class Conn:
        def execute(self, sql, params=None):
            class R:
                def fetchone(self):
                    return None
            return R()

    assert inbox_ready(Conn()) is False


def test_the_same_alert_keeps_one_id_when_the_keys_are_reordered():
    from tracking.notification_inbox import bind_inbox_id, make_row, stable_notification_id

    user = "11111111-1111-4111-8111-111111111111"
    first = stable_notification_id(user, "new_bets", ["k-ufc", "k-nba"])
    second = stable_notification_id(user, "new_bets", ["k-nba", "k-ufc"])
    assert first == second
    assert stable_notification_id(user, "new_bets", ["k-nba"]) != first
    data = bind_inbox_id(user, "line_change", ["9", "line_change_1", "-130"], {"type": "line_change", "pickId": 9})
    row = make_row(user, "line_change", "t", "b", data)
    again = make_row(user, "line_change", "t", "b", dict(data))
    assert row["notification_id"] == again["notification_id"] == data["inboxId"]


class _Recorder:
    def __init__(self):
        self.sql: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.sql.append((str(sql), tuple(params or ())))

        class _R:
            rowcount = 1

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        return _R()

    def commit(self):
        self.sql.append(("COMMIT", ()))

    def close(self):
        pass


def _plan_two_users():
    from tracking.notification_inbox import group_by_user

    user_a = "11111111-1111-4111-8111-111111111111"
    user_b = "22222222-2222-4222-8222-222222222222"
    devices = [
        {"token": "tok-a", "device_id": "device-a-1111", "user_id": user_a},
        {"token": "tok-b", "device_id": "device-b-2222", "user_id": user_b},
        {"token": "tok-n", "device_id": "device-n-3333", "user_id": None},
    ]
    # A hides UFC. B hides every sport in the batch.
    mutes = {user_a: {"UFC"}, user_b: {"NBA", "UFC"}}
    unread = {user_a: 1, user_b: 4}
    return (group_by_user(devices), mutes, unread), user_a, user_b


def _signals():
    return [
        {"sport": "NBA", "label": "Lakers -4.5", "pick_id": 11, "lock_key": "k-nba"},
        {"sport": "UFC", "label": "Fighter A", "pick_id": 22, "lock_key": "k-ufc"},
    ]


def test_send_signal_changes_filters_mutes_and_ledgers_them(monkeypatch):
    import tracking.push_notifier as pn

    plan, user_a, _user_b = _plan_two_users()
    sent: list[list[dict]] = []
    monkeypatch.setattr(pn, "refuse_mismatched", lambda rows, *_a, **_k: rows)
    monkeypatch.setattr(pn, "_new_bet_signals", lambda _c, _d: _signals())
    monkeypatch.setattr(pn, "_inbox_plan", lambda _c: plan)
    monkeypatch.setattr(pn, "_expo_send", lambda messages, conn=None: sent.append(messages) or len(messages))
    conn = _Recorder()
    assert pn._send_signal_changes(conn, "2026-11-18", False) == 2
    messages = sent[0]
    by_token = {m["to"]: m for m in messages}
    assert set(by_token) == {"tok-a", "tok-n"}
    assert by_token["tok-a"]["title"] == "🟢 1 new BET signal"
    assert by_token["tok-a"]["data"]["pickId"] == 11
    assert by_token["tok-a"]["badge"] == 2
    assert "inboxId" in by_token["tok-a"]["data"]
    assert by_token["tok-n"]["title"] == "🟢 2 new BET signals"
    assert "pickId" not in by_token["tok-n"]["data"]
    assert "badge" not in by_token["tok-n"]
    assert "inboxId" not in by_token["tok-n"]["data"]
    inbox = [params for sql, params in conn.sql if "INSERT INTO notification_inbox" in sql]
    assert len(inbox) == 1
    assert inbox[0][0] == user_a
    assert "ON CONFLICT (user_id, notification_id) DO NOTHING" in conn.sql[0][0] or any(
        "ON CONFLICT (user_id, notification_id) DO NOTHING" in sql for sql, _p in conn.sql
    )
    ledger = {params[0] for sql, params in conn.sql if "INSERT INTO push_sent" in sql}
    assert ledger == {"k-nba", "k-ufc"}
    # The inbox write is after the send and before the ledger commit.
    kinds = ["send" if sql == "COMMIT" else "inbox" if "notification_inbox" in sql else "ledger" if "push_sent" in sql else "" for sql, _p in conn.sql]
    assert kinds.index("inbox") < kinds.index("ledger")


def test_live_and_line_change_skip_a_muted_sport(monkeypatch):
    import tracking.push_notifier as pn

    plan, user_a, _user_b = _plan_two_users()
    sent: list[list[dict]] = []
    monkeypatch.setattr(pn, "refuse_mismatched", lambda rows, *_a, **_k: rows)
    monkeypatch.setattr(pn, "_new_live_signals", lambda _c, _d: _signals())
    monkeypatch.setattr(pn, "_inbox_plan", lambda _c: plan)
    monkeypatch.setattr(pn, "_expo_send", lambda messages, conn=None: sent.append(list(messages)) or len(messages))
    monkeypatch.setattr(pn, "get_connection", lambda: _Recorder())
    assert pn.notify_live_signals("2026-11-18") == 2
    live = {m["to"]: m for m in sent[0]}
    assert set(live) == {"tok-a", "tok-n"}
    assert live["tok-a"]["title"] == "🔴 1 live pick"
    assert live["tok-a"]["badge"] == 2
    assert "badge" not in live["tok-n"]

    def alert(device, sport, pick):
        return {
            "device_id": device, "lock_key": f"track:{device}:{pick}", "kind": "line_change_1",
            "pick_id": pick, "label": f"{sport} side", "locked": -110, "current": -130,
            "against": True, "sport": sport,
        }

    sent.clear()
    conn = _Recorder()
    monkeypatch.setattr(pn, "get_connection", lambda: conn)
    monkeypatch.setattr(pn, "_line_change_alerts", lambda _c, _d: [
        alert("device-a-1111", "UFC", 22),
        alert("device-a-1111", "NBA", 11),
        alert("device-n-3333", "UFC", 22),
    ])
    assert pn.notify_line_changes("2026-11-18") == 2
    line = {m["to"]: m for m in sent[0]}
    # A's UFC alert is muted. A's NBA alert is sent. The unsigned device
    # still gets the UFC alert, with no badge.
    assert set(line) == {"tok-a", "tok-n"}
    assert line["tok-a"]["data"]["pickId"] == 11
    assert line["tok-a"]["badge"] == 2
    assert "badge" not in line["tok-n"]
    ledger = {params[0] for sql, params in conn.sql if "INSERT INTO push_sent" in sql}
    assert ledger == {
        "track:device-a-1111:22",
        "track:device-a-1111:11",
        "track:device-n-3333:22",
    }


def test_feedback_inbox_row_uses_the_reply_key(monkeypatch):
    import tracking.push_notifier as pn

    plan, user_a, _user_b = _plan_two_users()
    monkeypatch.setattr(pn, "_inbox_plan", lambda _c: plan)
    replies = [{
        "lock_key": "feedback:9", "device_id": "device-a-1111", "token": "tok-a",
        "subject": "s", "body": "hello", "thread_id": 9,
    }]
    messages = [{
        "to": "tok-a",
        "title": "💬 We replied to your feedback",
        "body": "hello",
        "data": {"v": 1, "type": "feedback_reply", "threadId": 9},
    }]
    rows = pn._feedback_inbox_rows(_Recorder(), replies, messages)
    assert len(rows) == 1
    assert rows[0]["user_id"] == user_a
    assert rows[0]["notification_id"] == messages[0]["data"]["inboxId"]
    again = pn._feedback_inbox_rows(_Recorder(), replies, [{
        "to": "tok-a", "title": "t", "body": "b",
        "data": {"v": 1, "type": "feedback_reply", "threadId": 9},
    }])
    assert again[0]["notification_id"] == rows[0]["notification_id"]


def test_unread_counts_drop_muted_sports_and_keep_sportless_rows():
    from tracking.notification_inbox import unread_counts

    class Conn:
        def execute(self, sql, params=None):
            class R:
                def fetchall(self):
                    return [("u1", "UFC"), ("u1", None), ("u1", "NBA"), ("u2", "UFC")]
            return R()

    assert unread_counts(Conn(), {"u1": {"UFC"}}) == {"u1": 2, "u2": 1}


def test_insert_rows_is_conflict_safe():
    from tracking.notification_inbox import insert_rows, make_row

    conn = _Recorder()
    row = make_row("u", "new_bets", "t", "b", {"type": "new_bets", "inboxId": "same"})
    insert_rows(conn, [row])
    sql = conn.sql[1][0]
    assert "ON CONFLICT (user_id, notification_id) DO NOTHING" in sql
    assert conn.sql[1][1][-1] == "same"


def test_delete_flow_opts_the_token_out_with_a_null_user():
    """Opt-out before the login delete, and a save after the user is gone.

    The late save is what the phone still does once the local wipe runs.
    It must not raise on the user foreign key, and it must leave the token
    disabled with no user.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    user_a = "11111111-1111-4111-8111-111111111111"
    token = "ExponentPushToken[delete-flow-tokenxx]"
    device = "22222222-bbbb-4bbb-8bbb-222222222222"
    cluster = ScratchPostgres()
    conn = None
    try:
        try:
            dsn = cluster.start()
        except Exception as exc:
            pytest.skip(f"scratch cluster did not start: {exc}")
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
                CREATE ROLE postgres SUPERUSER;
              END IF;
            END $$;
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE TABLE auth.users (id uuid PRIMARY KEY);
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
            GRANT USAGE ON SCHEMA public TO anon, authenticated;
            CREATE TABLE public.device_push_tokens (
                token text PRIMARY KEY,
                platform text,
                device_id text,
                enabled boolean DEFAULT true,
                last_seen text
            );
        """)
        cur.execute("INSERT INTO auth.users (id) VALUES (%s)", (user_a,))
        cur.execute(MIG.read_text(encoding="utf-8"))
        cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_a,))
        cur.execute("SET ROLE authenticated")
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', true, 'seen', %s)",
            (token, device, user_a),
        )
        cur.execute(
            "INSERT INTO public.notification_inbox "
            "(id, user_id, kind, title, body, route, notification_id) "
            "VALUES ('33333333-cccc-4ccc-8ccc-333333333333', %s, 'test', 't', 'b', '{}', 'del-1')",
            (user_a,),
        )
        cur.execute("SELECT public.forget_my_notifications()")
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', false, 'seen', %s)",
            (token, device, user_a),
        )
        cur.execute("RESET ROLE")
        cur.execute("DELETE FROM auth.users WHERE id = %s", (user_a,))
        cur.execute("SET ROLE authenticated")
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', false, 'seen', %s)",
            (token, device, user_a),
        )
        cur.execute("RESET ROLE")
        cur.execute(
            "SELECT enabled, user_id IS NULL, "
            "(SELECT count(*) FROM public.notification_inbox) "
            "FROM public.device_push_tokens WHERE token = %s",
            (token,),
        )
        enabled, user_is_null, inbox_rows = cur.fetchone()
        assert enabled is False
        assert user_is_null is True
        assert inbox_rows == 0
    finally:
        if conn is not None:
            conn.close()
        cluster.stop()


def test_rls_hides_another_users_inbox_rows():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    user_a = "11111111-1111-4111-8111-111111111111"
    user_b = "22222222-2222-4222-8222-222222222222"
    cluster = ScratchPostgres()
    conn = None
    try:
        try:
            dsn = cluster.start()
        except Exception as exc:
            pytest.skip(f"scratch cluster did not start: {exc}")
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
                CREATE ROLE postgres SUPERUSER;
              END IF;
            END $$;
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
            GRANT USAGE ON SCHEMA public TO anon, authenticated;
            CREATE TABLE public.device_push_tokens (
                token text PRIMARY KEY,
                platform text,
                device_id text,
                enabled boolean DEFAULT true,
                last_seen text
            );
        """)
        cur.execute(MIG.read_text(encoding="utf-8"))
        cur.execute(MIG.read_text(encoding="utf-8"))
        cur.execute(
            """
            INSERT INTO public.notification_inbox
                (user_id, kind, title, body, sport, route, notification_id)
            VALUES
                (%s, 'new_bets', 'A', 'a', 'NBA', '{}', 'na'),
                (%s, 'new_bets', 'B', 'b', 'NFL', '{}', 'nb')
            """,
            (user_a, user_b),
        )
        cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_a,))
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT title FROM public.notification_inbox ORDER BY title")
        assert [r[0] for r in cur.fetchall()] == ["A"]
        cur.execute(
            "UPDATE public.notification_inbox SET read_at = now() WHERE notification_id = 'nb'"
        )
        assert cur.rowcount == 0
        with pytest.raises(psycopg2.Error):
            cur.execute(
                """
                INSERT INTO public.notification_inbox
                    (user_id, kind, title, body, route, notification_id)
                VALUES (%s, 'test', 'nope', 'nope', '{}', 'stolen')
                """,
                (user_b,),
            )
        cur.execute("RESET ROLE")
        cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_a,))
        cur.execute("SET ROLE authenticated")
        cur.execute(
            "UPDATE public.notification_inbox SET read_at = now() WHERE notification_id = 'na'"
        )
        assert cur.rowcount == 1
        with pytest.raises(psycopg2.Error) as frozen:
            cur.execute(
                "UPDATE public.notification_inbox SET title = 'rewritten' WHERE notification_id = 'na'"
            )
        assert frozen.value.pgcode == "42501"
        cur.execute("RESET ROLE")
        cur.execute("SET ROLE anon")
        with pytest.raises(psycopg2.Error):
            cur.execute("SELECT * FROM public.notification_inbox")
        cur.execute("RESET ROLE")
        # Anon cannot attach the token to a user. A mismatched signed-in id
        # is the same refusal. A signed-out save stores no user.
        cur.execute("SELECT set_config('request.jwt.claim.sub', '', false)")
        token = "ExponentPushToken[inbox-probe-tokenxx]"
        device = "11111111-aaaa-4aaa-8aaa-111111111111"
        cur.execute("SET ROLE anon")
        with pytest.raises(psycopg2.Error) as anon_link:
            cur.execute(
                "SELECT public.save_device_push_token(%s, %s, 'ios', true, 'seen', %s)",
                (token, device, user_b),
            )
        assert anon_link.value.pgcode == "42501"
        cur.execute("RESET ROLE")
        cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_a,))
        cur.execute("SET ROLE authenticated")
        with pytest.raises(psycopg2.Error) as mismatch:
            cur.execute(
                "SELECT public.save_device_push_token(%s, %s, 'ios', true, 'seen', %s)",
                (token, device, user_b),
            )
        assert mismatch.value.pgcode == "42501"
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', true, 'seen', %s)",
            (token, device, user_a),
        )
        cur.execute("RESET ROLE")
        cur.execute("SELECT user_id::text FROM public.device_push_tokens WHERE token = %s", (token,))
        assert cur.fetchone()[0] == user_a
        cur.execute("SELECT set_config('request.jwt.claim.sub', '', false)")
        cur.execute("SET ROLE anon")
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', true, 'seen', NULL)",
            (token, device),
        )
        cur.execute("RESET ROLE")
        cur.execute("SELECT user_id FROM public.device_push_tokens WHERE token = %s", (token,))
        assert cur.fetchone()[0] is None
    finally:
        if conn is not None:
            conn.close()
        cluster.stop()


# ── Delete from the list (notification_inbox_hide_2026_11_26.sql) ───────────

HIDE = ROOT / "data" / "migrations" / "notification_inbox_hide_2026_11_26.sql"


def test_delete_is_a_hide_not_a_delete():
    """CLAUDE.md section 1b: no data is ever deleted. The app's Delete stamps
    deleted_at; neither the migration nor the app issues a DELETE."""
    from data.view_migrations import ACTIVE_MIGRATIONS

    sql = HIDE.read_text(encoding="utf-8")
    # Matt, 2026-11-26: "You do the db action". The worker applies it.
    assert HIDE.name in ACTIVE_MIGRATIONS
    assert "ADD COLUMN IF NOT EXISTS deleted_at timestamptz" in sql
    assert "DELETE FROM" not in sql.upper().replace("ON DELETE", "")
    # A hidden alert cannot be un-hidden by a client update.
    assert "a deleted alert stays deleted" in sql
    # Every column the original freeze protected is still frozen.
    for col in ("id", "user_id", "kind", "title", "body", "sport", "route",
                "notification_id", "sent_at"):
        assert f"NEW.{col} IS DISTINCT FROM OLD.{col}" in sql

    hook = (ROOT / "mobile" / "src" / "hooks" / "useNotificationInbox.ts").read_text(encoding="utf-8")
    assert ".delete()" not in hook  # the PostgREST delete; Set.delete(x) is fine
    assert "deleted_at: now" in hook
    assert ".is('deleted_at', null)" in hook


def test_unread_count_skips_hidden_rows_once_the_column_exists():
    from tracking.notification_inbox import unread_counts

    class Conn:
        def __init__(self, has_column):
            self.has_column = has_column
            self.sql = []

        def execute(self, sql, params=None):
            self.sql.append(sql)
            has = self.has_column

            class R:
                def fetchone(self):
                    return (1,) if has else None

                def fetchall(self):
                    return [("u1", None)]
            return R()

    after = Conn(True)
    assert unread_counts(after, {}) == {"u1": 1}
    assert "deleted_at IS NULL" in after.sql[-1]

    before = Conn(False)
    assert unread_counts(before, {}) == {"u1": 1}
    assert "deleted_at" not in before.sql[-1]


def test_the_hide_migration_returns_before_any_lock_once_applied():
    """It runs on every pass. Once applied, it must return on a catalog read
    before ALTER / DROP INDEX / CREATE take a lock
    (tests/test_view_migration_lock_noop.py)."""
    code = "\n".join(ln.split("--", 1)[0] for ln in HIDE.read_text(encoding="utf-8").splitlines())
    head = code.split("ALTER TABLE", 1)[0]
    assert "DROP INDEX" not in head and "CREATE" not in head
    for prop in ("column_name = 'deleted_at'", "deleted_at IS NULL", "a deleted alert stays deleted"):
        assert prop in head
    assert head.count("RETURN;") == 2
