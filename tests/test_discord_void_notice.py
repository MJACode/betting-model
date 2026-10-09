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
from tracking.publish_keys import posted_sql, void_notice_exclusion_sql

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
    """Serves the void SELECT and records inserts. close() keeps the rows."""

    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
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
                if "FROM picks" in sql:
                    return [tuple(r) for r in outer.rows]
                return []

            def fetchone(self):
                return (True,)

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


def _bind(monkeypatch, rows, post=None):
    ledger = Ledger(rows)
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
    db.execute("CREATE TABLE push_sent (lock_key TEXT, kind TEXT)")
    db.executemany(
        "INSERT INTO push_sent VALUES (?, ?)",
        [
            ("stay", "discord_signal"),
            ("drop", "discord_signal"),
            ("drop", "discord_void"),
            ("phone", "new_bet"),
            ("live-stay", "discord_live"),
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
    db.execute("INSERT INTO push_sent VALUES ('G:m', 'discord_signal')")
    assert db.execute(f"SELECT {posted_sql('p')} FROM p").fetchone()[0] == 1
    assert db.execute(
        f"SELECT {discord_published_exists_sql(repr('G:m'))}"
    ).fetchone()[0] == 1
    # The boolean is unchanged: published still means visible. The join is
    # what stops returning the lock once the notice exists.
    assert discord_led_visible("VOID", True) is True
    db.execute("INSERT INTO push_sent VALUES ('G:m', 'discord_void')")
    assert db.execute(f"SELECT {posted_sql('p')} FROM p").fetchone()[0] == 0
    assert db.execute(
        f"SELECT {discord_published_exists_sql(repr('G:m'))}"
    ).fetchone()[0] == 0
    assert void_notice_exclusion_sql("s") in posted_sql("p")
    assert void_notice_exclusion_sql("s") in discord_published_exists_sql("k")


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
    assert "original post 1553713576831885365" in field["value"]
    blob = json.dumps(out)
    assert "super-secret-token" not in blob
    assert "api/webhooks" not in blob
    assert seen == [(WEBHOOK, "1553713576831885365")]
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

    calls = []

    def fake(pick_ids, reason=None, dry_run=True):
        calls.append((list(pick_ids), reason, dry_run))
        return {"posted": 0, "dry_run": dry_run}

    monkeypatch.setattr(dn, "notify_discord_void", fake)
    out = q._job_publish_discord_void(pick_ids=[2992290], dry_run=False)
    assert calls == [([2992290], None, False)]
    assert out["dry_run"] is False


def test_the_migration_is_one_statement():
    code = NEW_MIG.read_text(encoding="utf-8")
    sql = "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    assert sql.strip().startswith("DO $mig$")
    assert sql.strip().endswith("$mig$;")
    assert sql.count("$mig$") == 2
    assert "UPDATE public.picks" not in code
    assert "DELETE FROM" not in code
