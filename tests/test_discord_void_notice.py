"""A Discord void notice is the publish state. The original message stays.

The eight NCAAF totals mike voided on 2026-10-09 were already in the channel.
There was no path that could say so, and v_discord_published kept a posted
VOID on the board. These tests are the contract for that path: validate the
whole list before any post, ledger discord_void only after Discord accepts
the message, and drop that lock from the published join. A published VOID
with no notice stays visible.
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

from tracking import discord_notifier as dn
from tracking.discord_publish import (
    discord_led_visible, discord_published_exists_sql,
)
from tracking.publish_keys import (
    SIGNAL_LEDGER_SQL, channel_lock_held_sql, posted_sql,
    void_notice_exclusion_sql,
)

ROOT = Path(__file__).parent.parent
NEW_MIG = ROOT / "data/migrations/discord_void_notice_2026_10_09.sql"
WEBHOOK = "https://discord.com/api/webhooks/999/super-secret-token"


def _row(pick_id, *, status="VOID", signal=True, voided=False,
         message_id="1553713576831885365", sport="NCAAF", live=False,
         label="Georgia vs Auburn Under 54.5",
         lock="NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"):
    return (
        pick_id, sport, "ncaaf_over_under", "NCAAF_2026-10-17_auburn_georgia",
        "2026-10-17", "under", label, status,
        -105, -105, "draftkings",
        1 if live else 0, None, None, None,
        "2026-09-27 10:22:17+00:00",
        "Georgia", "Auburn",
        lock,
        message_id if signal else None,
        "2026-09-27T06:23:03-04:00" if signal else None,
        1 if signal else 0,
        1 if voided else 0,
    )


class Ledger:
    """Serves the void SELECT and records inserts. close() keeps the rows.

    `siblings` maps a pregame lock_key to the pick_id of a posted sibling.
    The sibling query is the only fetchone. Default is no sibling, so a
    void that used to post still posts.
    """

    def __init__(self, rows, siblings=None):
        self.rows = [list(r) for r in rows]
        self.siblings = dict(siblings or {})
        self.statements: list[tuple] = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if "INSERT INTO push_sent" in sql:
            lock = params[0]
            for row in self.rows:
                if row[18] == lock:
                    row[22] = 1
        outer = self

        class Result:
            def fetchall(self):
                if "FROM picks p" in sql:
                    return [tuple(r) for r in outer.rows]
                return []

            def fetchone(self):
                if "sib.pick_id" in sql:
                    sib = outer.siblings.get(params[1])
                    return None if sib is None else (sib,)
                return None

        return Result()

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass

    @property
    def inserts(self):
        return [s for s in self.statements if "INSERT INTO push_sent" in s[0]]


def _bind(monkeypatch, rows, post=None, siblings=None):
    ledger = Ledger(rows, siblings=siblings)
    monkeypatch.setattr(dn, "get_connection", lambda: ledger)
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: WEBHOOK)
    calls = []

    def _post(url, payload):
        calls.append((url, payload))
        if post is None:
            return "9001"
        return post(url, payload)

    monkeypatch.setattr(dn, "_post", _post)
    return ledger, calls


def _view_select() -> str:
    sql = NEW_MIG.read_text(encoding="utf-8")
    rest = sql.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    body = rest[rest.upper().rfind(" AS") + 4:]
    return body.replace("public.", "").strip().rstrip(";")


def test_a_voided_lock_drops_from_the_view_and_the_python_join():
    """The notice is the publish state. A posted VOID with no notice stays."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT)")
    db.executemany(
        "INSERT INTO push_sent VALUES (?, ?, ?)",
        [
            ("stay", "discord_signal", "2026-09-01T00:00:00-04:00"),
            ("drop", "discord_signal", "2026-09-01T00:00:00-04:00"),
            ("drop", "discord_void", "2026-10-09T00:00:00-04:00"),
            ("phone", "new_bet", "2026-09-01T00:00:00-04:00"),
            ("live-stay", "discord_live", "2026-09-01T00:00:00-04:00"),
        ],
    )
    select = _view_select()
    assert "discord_void" in select
    assert "VOID" not in select
    got = db.execute(select + " ORDER BY 1").fetchall()
    assert got == [("live-stay", "discord_live"), ("stay", "discord_signal")]

    db.execute(
        "CREATE TABLE p (game_id TEXT, model_id TEXT, player_id TEXT, "
        "player_key TEXT, prop_market TEXT, pick_side TEXT, is_live INT)")
    db.execute(
        "INSERT INTO p VALUES ('G', 'm', NULL, NULL, NULL, 'under', 0)")
    db.execute(
        "INSERT INTO push_sent VALUES ('G:m', 'discord_signal', "
        "'2026-09-01T00:00:00-04:00')")
    assert db.execute(f"SELECT {posted_sql('p')} FROM p").fetchone()[0] == 1
    assert db.execute(
        f"SELECT {discord_published_exists_sql(repr('G:m'))}"
    ).fetchone()[0] == 1
    # The boolean is unchanged: published still means visible. The join is
    # what stops returning the lock once the notice exists.
    assert discord_led_visible("VOID", True) is True
    db.execute(
        "INSERT INTO push_sent VALUES ('G:m', 'discord_void', "
        "'2026-10-09T00:00:00-04:00')")
    assert db.execute(f"SELECT {posted_sql('p')} FROM p").fetchone()[0] == 0
    assert db.execute(
        f"SELECT {discord_published_exists_sql(repr('G:m'))}"
    ).fetchone()[0] == 0
    assert void_notice_exclusion_sql("s") in posted_sql("p")
    assert void_notice_exclusion_sql("s") in discord_published_exists_sql("k")


def test_a_noticed_void_releases_the_lock_and_a_later_pick_reholds_it():
    """The pre-game key has no side. A notice releases it for a new pick
    on the same game:model. No notice, the signal still blocks."""
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT, "
        "message_id TEXT, UNIQUE (lock_key, kind))")
    held = channel_lock_held_sql("'G:m'", "discord_signal")
    other = channel_lock_held_sql("'H:m'", "discord_signal")
    db.execute(
        "INSERT INTO push_sent VALUES ('G:m', 'discord_signal', "
        "'2026-09-27T06:23:00-04:00', '111')")
    db.execute(
        "INSERT INTO push_sent VALUES ('H:m', 'discord_signal', "
        "'2026-10-01T00:00:00-04:00', '222')")
    assert db.execute(f"SELECT {held}").fetchone()[0] == 1
    assert db.execute(f"SELECT {other}").fetchone()[0] == 1

    db.execute(
        "INSERT INTO push_sent VALUES ('G:m', 'discord_void', "
        "'2026-10-09T12:00:00-04:00', 'notice')")
    assert db.execute(f"SELECT {held}").fetchone()[0] == 0
    assert db.execute(f"SELECT {other}").fetchone()[0] == 1

    sql = SIGNAL_LEDGER_SQL.replace("%s", "?")
    db.execute(sql, ("G:m", "discord_signal", "2026-10-12T18:00:00-04:00", "333"))
    row = db.execute(
        "SELECT sent_at, message_id FROM push_sent "
        "WHERE lock_key = 'G:m' AND kind = 'discord_signal'"
    ).fetchone()
    assert row == ("2026-10-12T18:00:00-04:00", "333")
    assert db.execute(f"SELECT {held}").fetchone()[0] == 1
    assert db.execute(
        "SELECT 1 FROM push_sent WHERE lock_key = 'G:m' AND kind = 'discord_void'"
    ).fetchone() is not None
    # A second write with no release left must not replace the message.
    db.execute(sql, ("H:m", "discord_signal", "2026-10-12T18:00:00-04:00", "999"))
    kept = db.execute(
        "SELECT message_id FROM push_sent "
        "WHERE lock_key = 'H:m' AND kind = 'discord_signal'"
    ).fetchone()[0]
    assert kept == "222"
    src = inspect.getsource(dn._new_signals)
    assert "channel_lock_held_sql" in src


def test_release_is_strictly_newer_and_a_null_void_stamp_does_not_stick():
    """Equal stamps hold. A null void sent_at does not release a stamped
    signal, and it does not keep a later stamp unpublished."""
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT, "
        "message_id TEXT, UNIQUE (lock_key, kind))")
    select = _view_select()
    assert "v.sent_at > s.sent_at" in select
    assert ">=" not in select
    rows = [
        ("newer", "discord_signal", "2026-09-01T00:00:00Z", "1"),
        ("newer", "discord_void", "2026-10-09T00:00:00Z", "2"),
        ("equal", "discord_signal", "2026-10-09T00:00:00Z", "3"),
        ("equal", "discord_void", "2026-10-09T00:00:00Z", "4"),
        ("older", "discord_signal", "2026-10-12T00:00:00Z", "5"),
        ("older", "discord_void", "2026-10-09T00:00:00Z", "6"),
        ("nullvoid", "discord_signal", "2026-09-01T00:00:00Z", "7"),
        ("nullvoid", "discord_void", None, "8"),
        ("bothnull", "discord_signal", None, "9"),
        ("bothnull", "discord_void", None, "10"),
        ("unstamped", "discord_signal", None, "11"),
        ("unstamped", "discord_void", "2026-10-09T00:00:00Z", "12"),
    ]
    db.executemany("INSERT INTO push_sent VALUES (?, ?, ?, ?)", rows)
    published = [r[0] for r in db.execute(select + " ORDER BY 1").fetchall()]
    assert published == ["equal", "nullvoid", "older"]

    sql = SIGNAL_LEDGER_SQL.replace("%s", "?")
    # Equal: the post that shares the notice's instant is not replaced.
    db.execute(sql, ("equal", "discord_signal", "2026-10-12T00:00:00Z", "99"))
    assert db.execute(
        "SELECT message_id FROM push_sent WHERE lock_key = 'equal' "
        "AND kind = 'discord_signal'"
    ).fetchone()[0] == "3"
    # Null void stamp: the existing signal stays, and stays in the view.
    db.execute(sql, ("nullvoid", "discord_signal", "2026-10-12T00:00:00Z", "99"))
    assert db.execute(
        "SELECT message_id FROM push_sent WHERE lock_key = 'nullvoid' "
        "AND kind = 'discord_signal'"
    ).fetchone()[0] == "7"
    # Both stamps missing: the notice releases once. The rehold's stamp
    # then holds, and a second write does not replace it.
    db.execute(sql, ("bothnull", "discord_signal", "2026-10-12T18:00:00Z", "33"))
    assert db.execute(
        "SELECT sent_at, message_id FROM push_sent WHERE lock_key = 'bothnull' "
        "AND kind = 'discord_signal'"
    ).fetchone() == ("2026-10-12T18:00:00Z", "33")
    db.execute(sql, ("bothnull", "discord_signal", "2026-10-13T00:00:00Z", "99"))
    assert db.execute(
        "SELECT message_id FROM push_sent WHERE lock_key = 'bothnull' "
        "AND kind = 'discord_signal'"
    ).fetchone()[0] == "33"
    published = [r[0] for r in db.execute(select + " ORDER BY 1").fetchall()]
    assert "bothnull" in published
    assert "newer" not in published
    assert db.execute(
        f"SELECT {channel_lock_held_sql(repr('bothnull'), 'discord_signal')}"
    ).fetchone()[0] == 1
    assert db.execute(
        f"SELECT {channel_lock_held_sql(repr('nullvoid'), 'discord_signal')}"
    ).fetchone()[0] == 1
    assert db.execute(
        f"SELECT {channel_lock_held_sql(repr('newer'), 'discord_signal')}"
    ).fetchone()[0] == 0


def _pg_bin(name):
    from tests._pg import pg_bin
    return pg_bin(name)


def _swap_dbname(dsn, name):
    if "://" in dsn:
        from urllib.parse import urlparse, urlunparse
        parts = urlparse(dsn)
        return urlunparse(parts._replace(path="/" + name))
    out = []
    seen = False
    for tok in dsn.split():
        if tok.startswith("dbname="):
            out.append("dbname=" + name)
            seen = True
        else:
            out.append(tok)
    if not seen:
        out.append("dbname=" + name)
    return " ".join(out)


def test_anon_reads_both_discord_views():
    """security_invoker runs the view as anon. The published view reads
    sent_at, so that column has to be granted or the board read fails.
    Same shape as tests/test_latest_line_state.py: SET ROLE anon on a
    scratch cluster. Skips when no Postgres binary and no
    LATEST_LINE_TEST_DSN."""
    import os
    import shutil
    import socket
    import subprocess
    import tempfile

    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2.errors import InsufficientPrivilege

    dsn = os.environ.get("LATEST_LINE_TEST_DSN")
    owned = None
    if not dsn:
        initdb = _pg_bin("initdb")
        pg_ctl = _pg_bin("pg_ctl")
        if not initdb or not pg_ctl:
            pytest.skip(
                "LATEST_LINE_TEST_DSN not set and initdb is missing -- "
                "needs a scratch Postgres")
        # tests/_pg.py: UTF-8, trusted, TCP on a free port, output to the
        # cluster log (a captured pipe hangs pg_ctl on Windows). `owned`
        # is the ExitStack that stops and deletes it.
        import contextlib
        from tests._pg import scratch_cluster
        owned = contextlib.ExitStack()
        dsn = owned.enter_context(scratch_cluster("discord-void-pg-"))

    conn = None
    try:
        if owned is None:
            admin = psycopg2.connect(dsn)
            admin.autocommit = True
            acur = admin.cursor()
            acur.execute(
                "SELECT 1 FROM pg_database WHERE datname = 'discord_void_anon'")
            if acur.fetchone() is None:
                acur.execute("CREATE DATABASE discord_void_anon")
            admin.close()
            dsn = _swap_dbname(dsn, "discord_void_anon")
        conn = psycopg2.connect(dsn)
        conn.set_client_encoding("UTF8")
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
            END $$
        """)
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("CREATE SCHEMA public")
        cur.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated")
        cur.execute("""
            CREATE TABLE public.push_sent (
              lock_key text NOT NULL,
              kind text NOT NULL,
              sent_at timestamptz,
              message_id text,
              UNIQUE (lock_key, kind)
            )
        """)
        cur.execute("ALTER TABLE public.push_sent ENABLE ROW LEVEL SECURITY")
        cur.execute(NEW_MIG.read_text(encoding="utf-8"))
        cur.execute(NEW_MIG.read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO public.push_sent (lock_key, kind, sent_at, message_id) VALUES
             ('stay', 'discord_signal', '2026-09-01T00:00:00Z', '111'),
             ('drop', 'discord_signal', '2026-09-01T00:00:00Z', '222'),
             ('drop', 'discord_void', '2026-10-09T00:00:00Z', '333'),
             ('equal', 'discord_signal', '2026-10-09T00:00:00Z', '444'),
             ('equal', 'discord_void', '2026-10-09T00:00:00Z', '555'),
             ('nullvoid', 'discord_signal', '2026-09-01T00:00:00Z', '666'),
             ('nullvoid', 'discord_void', NULL, '777'),
             ('bothnull', 'discord_signal', NULL, '888'),
             ('bothnull', 'discord_void', NULL, '999'),
             ('phone', 'new_bet', '2026-09-01T00:00:00Z', '000')
        """)

        def as_anon(sql):
            cur.execute("SET ROLE anon")
            try:
                cur.execute(sql)
                return cur.fetchall()
            finally:
                cur.execute("RESET ROLE")

        published = as_anon(
            "SELECT lock_key, kind FROM public.v_discord_published ORDER BY 1")
        assert published == [
            ("equal", "discord_signal"),
            ("nullvoid", "discord_signal"),
            ("stay", "discord_signal"),
        ]
        noticed = as_anon(
            "SELECT lock_key FROM public.v_discord_void_notice ORDER BY 1")
        assert noticed == [("bothnull",), ("drop",), ("equal",), ("nullvoid",)]
        visible = as_anon(
            "SELECT lock_key FROM public.push_sent ORDER BY 1")
        assert "phone" not in [r[0] for r in visible]
        with pytest.raises(InsufficientPrivilege):
            as_anon("SELECT message_id FROM public.push_sent")

        cur.execute(
            "REVOKE SELECT (sent_at) ON public.push_sent FROM anon, authenticated")
        with pytest.raises(InsufficientPrivilege):
            as_anon("SELECT lock_key FROM public.v_discord_published")
        assert as_anon(
            "SELECT lock_key FROM public.v_discord_void_notice ORDER BY 1"
        ) == [("bothnull",), ("drop",), ("equal",), ("nullvoid",)]
        cur.execute(
            "GRANT SELECT (sent_at) ON public.push_sent TO anon, authenticated")
        assert ("stay", "discord_signal") in as_anon(
            "SELECT lock_key, kind FROM public.v_discord_published")

        cur.execute(
            "UPDATE public.push_sent SET sent_at = '2026-10-12T18:00:00Z' "
            "WHERE lock_key = 'bothnull' AND kind = 'discord_signal'")
        assert ("bothnull", "discord_signal") in as_anon(
            "SELECT lock_key, kind FROM public.v_discord_published")
    finally:
        if conn is not None:
            conn.close()
        if owned is not None:
            owned.close()


def test_the_migration_grants_sent_at_and_not_message_id():
    """The role read above skips with no Postgres. This pin is what CI runs."""
    code = NEW_MIG.read_text(encoding="utf-8")
    stmts = "\n".join(
        ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    grant = stmts.split("GRANT SELECT (", 1)[1].split(")", 1)[0]
    assert grant == "lock_key, kind, sent_at"
    assert "message_id" not in grant
    assert "has_column_privilege" in stmts
    view = code.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    assert "message_id" not in view
    assert "v.sent_at > s.sent_at" in view
    assert ">=" not in view
    from tracking.publish_keys import void_notice_is_newer_sql
    frag = " ".join(void_notice_is_newer_sql("s").split())
    body = " ".join(view.replace("public.", "").split())
    assert frag in body


def test_a_known_channel_is_a_jump_link_and_an_unknown_one_is_omitted():
    guild, channel, mid = "111", "222", "1553713576831885365"
    url = dn._discord_jump_line(mid, guild, channel)
    assert url == f"https://discord.com/channels/{guild}/{channel}/{mid}"
    assert dn._discord_jump_line(mid, "", channel) is None
    assert dn._discord_jump_line(mid, guild, "") is None
    assert dn._known_channel_ids("NCAAF") == ("", "")
    pick = {
        "label": "Georgia vs Auburn Under 54.5",
        "sport": "NCAAF", "home": "Georgia", "away": "Auburn",
        "dk_odds": -105, "best_odds": -105, "best_book": "draftkings",
        "game_date": "2026-10-17", "posted_at": "2026-09-27T06:23:03-04:00",
        "message_id": mid,
    }
    plain = dn._void_field(pick, WEBHOOK)
    assert "discord.com" not in plain["value"]
    assert mid not in plain["value"]
    assert "api/webhooks" not in plain["value"]


def test_the_notice_quotes_the_label_and_does_not_carry_the_webhook(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    seen = []
    real = dn._message_url

    def spy(url, message_id):
        seen.append((url, message_id))
        return real(url, message_id)

    monkeypatch.setattr(dn, "_message_url", spy)
    out = dn.notify_discord_void([2992290], dry_run=True)
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0
    assert out["posted"] == 0
    body = out["payloads"][0]["payload"]
    embed = body["embeds"][0]
    assert embed["title"] == "\U0001f3c8 NCAAF \u00b7 Voided picks"
    assert embed["description"] == dn.VOID_NOTICE_REASON
    assert embed["color"] == dn._COLOR_VOID
    field = embed["fields"][0]
    assert field["name"] == "Georgia vs Auburn Under 54.5"
    assert "Auburn @ Georgia" in field["value"]
    assert "-105 @ DraftKings" in field["value"]
    assert "game 2026-10-17" in field["value"]
    assert dn._posted_et("2026-09-27T06:23:03-04:00") in field["value"]
    assert "original post" not in field["value"]
    assert "1553713576831885365" not in field["value"]
    assert "discord.com/channels" not in field["value"]
    blob = json.dumps(out)
    assert "super-secret-token" not in blob
    assert "api/webhooks" not in blob
    assert seen == []
    assert dn._void_title("MLB") == f"{dn._SPORT_EMOJI['MLB']} MLB \u00b7 Voided picks"


def test_a_rerun_skips_locks_that_already_have_a_notice(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    first = dn.notify_discord_void([2992290], dry_run=False)
    assert first["posted"] == 1
    assert len(calls) == 1
    assert len(ledger.inserts) == 1
    assert ledger.inserts[0][1][0].endswith(":ncaaf_over_under")
    assert ledger.inserts[0][1][2] == "9001"
    assert "discord_void" in ledger.inserts[0][0]
    assert "ON CONFLICT" in ledger.inserts[0][0]
    assert ledger.commits == 1
    second = dn.notify_discord_void([2992290], dry_run=False)
    assert second["posted"] == 0
    assert second["payloads"] == []
    assert second["skipped_lock_keys"] == [
        "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"]
    assert len(calls) == 1
    assert len(ledger.inserts) == 1
    assert ledger.commits == 1


def test_a_rejected_post_and_a_raised_post_record_nothing(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)], post=lambda url, payload: None)
    with pytest.raises(dn.DiscordVoidRejected):
        dn.notify_discord_void([2992290], dry_run=False)
    assert len(calls) == 1
    assert ledger.inserts == []
    assert ledger.commits == 0

    def explode(url, payload):
        raise RuntimeError("webhook down")

    ledger2, calls2 = _bind(monkeypatch, [_row(2992283, lock="other:ncaaf_over_under",
                                                label="Kansas State vs Kansas Under 54.5")],
                            post=explode)
    with pytest.raises(RuntimeError, match="webhook down"):
        dn.notify_discord_void([2992283], dry_run=False)
    assert len(calls2) == 1
    assert ledger2.inserts == []
    assert ledger2.commits == 0


def test_a_non_2xx_response_and_a_request_exception_record_nothing(monkeypatch):
    """Through the real _post: a 400 and a raised request write no ledger row."""
    ledger = Ledger([_row(2992290)])
    monkeypatch.setattr(dn, "get_connection", lambda: ledger)
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: WEBHOOK)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)

    class Resp:
        status_code = 400
        text = "rejected"

        def json(self):
            return {}

    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: Resp())
    with pytest.raises(dn.DiscordVoidRejected):
        dn.notify_discord_void([2992290], dry_run=False)
    assert ledger.inserts == []
    assert ledger.commits == 0

    ledger2 = Ledger([_row(2992290)])
    monkeypatch.setattr(dn, "get_connection", lambda: ledger2)

    def down(*_a, **_k):
        raise dn.requests.RequestException("connection reset")

    monkeypatch.setattr(dn.requests, "post", down)
    with pytest.raises(dn.DiscordVoidRejected):
        dn.notify_discord_void([2992290], dry_run=False)
    assert ledger2.inserts == []
    assert ledger2.commits == 0


def test_validation_rejects_the_whole_list_before_any_post(monkeypatch):
    rows = [
        _row(1),
        _row(2, status="BET", label="Not void"),
        _row(3, signal=False, label="Never posted"),
    ]
    ledger, calls = _bind(monkeypatch, rows)
    with pytest.raises(dn.DiscordVoidRejected, match="not VOID") as exc:
        dn.notify_discord_void([1, 2, 3], dry_run=False)
    assert "no discord_signal row" in str(exc.value)
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0

    ledger2, calls2 = _bind(monkeypatch, [_row(1)])
    with pytest.raises(dn.DiscordVoidRejected, match="was not found"):
        dn.notify_discord_void([1, 99], dry_run=True)
    assert calls2 == []
    assert ledger2.inserts == []


def test_dry_run_makes_no_http_call_and_no_write(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)])

    def forbid(*_a, **_k):
        raise AssertionError("dry_run made an HTTP call")

    monkeypatch.setattr(dn.requests, "post", forbid)
    out = dn.notify_discord_void([2992290])
    assert out["dry_run"] is True
    assert out["payloads"][0]["payload"]["embeds"][0]["description"] == dn.VOID_NOTICE_REASON
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0
    assert not any(s[0].lstrip().upper().startswith("INSERT") for s in ledger.statements)


def test_embeds_chunk_at_the_field_cap_and_the_size_cap():
    picks = [{
        "sport": "NCAAF", "label": f"Pick {i}", "home": "H", "away": "A",
        "dk_odds": -110, "best_odds": -110, "best_book": "draftkings",
        "game_date": "2026-10-17", "posted_at": "2026-09-27T06:23:03-04:00",
        "message_id": None,
    } for i in range(26)]
    embeds = dn.void_notice_embeds("NCAAF", picks, dn.VOID_NOTICE_REASON, None)
    assert [len(e["fields"]) for e in embeds] == [25, 1]
    assert all(e["color"] == dn._COLOR_VOID for e in embeds)
    fat = [{
        **picks[0], "label": f"Fat {i}",
    } for i in range(20)]
    # A long value still under the per-field cap, over the embed cap well
    # before 25 fields.
    long = "x" * 400

    real = dn._void_field

    def bulky(pick, webhook_url):
        field = real(pick, webhook_url)
        field["value"] = long
        return field

    dn._void_field = bulky
    try:
        chunked = dn.void_notice_embeds("NCAAF", fat, dn.VOID_NOTICE_REASON, None)
    finally:
        dn._void_field = real
    assert len(chunked) >= 2
    assert sum(len(e["fields"]) for e in chunked) == 20
    assert all(len(e["fields"]) < 25 for e in chunked)
    for embed in chunked:
        assert dn._embed_size(embed["title"], embed["description"], embed["fields"]) <= 6000


def test_the_notice_never_edits_or_deletes():
    src = inspect.getsource(dn.notify_discord_void)
    assert "_delete_message" not in src
    assert "requests.delete" not in src
    assert "requests.patch" not in src
    assert "DELETE FROM" not in src
    assert "UPDATE picks" not in src


def test_the_worker_job_is_registered_and_defaults_to_dry_run(monkeypatch):
    from tracking import job_queue as q

    assert "publish_discord_void" in q.JOBS
    assert q._validate_publish_discord_void({"pick_ids": [8, 8, 3]}) == {
        "pick_ids": [8, 3], "dry_run": True}
    with pytest.raises(ValueError):
        q._validate_publish_discord_void({"pick_ids": [1], "dry_run": "false"})
    with pytest.raises(ValueError):
        q._validate_publish_discord_void({"pick_ids": []})
    with pytest.raises(ValueError):
        q._validate_publish_discord_void({"pick_ids": [2.7]})
    with pytest.raises(ValueError):
        q._validate_publish_discord_void({"pick_ids": ["8"]})
    with pytest.raises(ValueError):
        q._validate_publish_discord_void({"pick_ids": [True]})

    calls = []

    def fake(pick_ids, reason=None, dry_run=True):
        calls.append((list(pick_ids), reason, dry_run))
        return {"posted": 0, "dry_run": dry_run}

    monkeypatch.setattr(dn, "notify_discord_void", fake)
    out = q._job_publish_discord_void(pick_ids=[2992290], dry_run=False)
    assert calls == [([2992290], None, False)]
    assert out["dry_run"] is False


def test_a_posted_sibling_on_the_sideless_lock_is_not_released(monkeypatch):
    """The pregame key has no side. A void notice on it would release a
    sibling that is still published. Refuse the post and the ledger write."""
    lock = "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"
    other = "NCAAF_2026-10-17_kansas_kansas-state:ncaaf_over_under"
    rows = [
        _row(2992290, lock=lock),
        _row(2992283, lock=other, label="Kansas State vs Kansas Under 54.5"),
    ]
    ledger, calls = _bind(monkeypatch, rows, siblings={lock: 3000001})
    warnings = []
    monkeypatch.setattr(dn.logger, "warning",
                        lambda msg: warnings.append(str(msg)))
    out = dn.notify_discord_void([2992290, 2992283], dry_run=False)
    assert out["posted"] == 1
    assert out["refused_sibling_lock_keys"] == [lock]
    posted_locks = [c[1]["embeds"][0]["fields"][0]["name"] for c in calls]
    assert posted_locks == ["Kansas State vs Kansas Under 54.5"]
    assert ledger.inserts and all(ins[1][0] != lock for ins in ledger.inserts)
    assert any("2992290" in msg and "3000001" in msg and lock in msg
               for msg in warnings)
    assert ledger.commits == 1


def test_a_live_void_still_posts_when_a_pregame_sibling_would_block(monkeypatch):
    """Live keys carry the side. The sideless-lock refusal does not apply."""
    lock = "live:NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under:under"
    ledger, calls = _bind(
        monkeypatch,
        [_row(2992290, live=True, lock=lock)],
        siblings={lock: 3000001},
    )
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert out["posted"] == 1
    assert out["refused_sibling_lock_keys"] == []
    assert len(calls) == 1
    assert len(ledger.inserts) == 1


def test_refusing_the_only_pick_posts_nothing_and_releases_nothing(monkeypatch):
    lock = "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"
    ledger, calls = _bind(monkeypatch, [_row(2992290, lock=lock)],
                          siblings={lock: 3000001})
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert out["posted"] == 0
    assert out["payloads"] == []
    assert out["refused_sibling_lock_keys"] == [lock]
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0

    dry, dry_calls = _bind(monkeypatch, [_row(2992290, lock=lock)],
                           siblings={lock: 3000001})
    dry_out = dn.notify_discord_void([2992290], dry_run=True)
    assert dry_out["payloads"] == []
    assert dry_calls == []
    assert dry.inserts == []


def test_the_auto_void_notice_skips_a_posted_sibling(monkeypatch):
    """scripts/void_picks.announce_posted_voids is the path after a void commits."""
    lock = "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"
    ledger, calls = _bind(monkeypatch, [_row(2992290, lock=lock)],
                          siblings={lock: 3000001})
    from scripts.void_picks import announce_posted_voids
    out = announce_posted_voids(
        [{"pick_id": 2992290, "posted": True}],
        "decided on a price nobody could bet, notice must not release the sibling",
    )
    assert out["posted"] == 0
    assert out["refused_sibling_lock_keys"] == [lock]
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0


def test_the_migration_is_one_statement():
    code = NEW_MIG.read_text(encoding="utf-8")
    sql = "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    assert sql.strip().startswith("DO $mig$")
    assert sql.strip().endswith("$mig$;")
    assert sql.count("$mig$") == 2
    assert "UPDATE public.picks" not in code
    assert "DELETE FROM" not in code
