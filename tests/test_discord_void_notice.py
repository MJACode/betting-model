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
         lock="NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under",
         attempted=False):
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
        1 if attempted else 0,
    )


# pg_get_viewdef / pg_get_expr text as production printed it on 2026-10-10,
# before the void migration (the 2026-09-23 view and policy) ...
OLD_VIEW = (" SELECT lock_key,\n    kind\n   FROM push_sent s\n  WHERE kind = "
            "ANY (ARRAY['discord_signal'::text, 'discord_live'::text]);")
OLD_POLICY = "(kind = ANY (ARRAY['discord_signal'::text, 'discord_live'::text]))"
# ... and the view and policy the void migration creates. Not yet read back
# from production (it has not run there); the check only needs the word.
NEW_VIEW = (" SELECT lock_key,\n    kind\n   FROM push_sent s\n  WHERE (kind = "
            "ANY (ARRAY['discord_signal'::text, 'discord_live'::text])) AND NOT "
            "(EXISTS ( SELECT 1\n           FROM push_sent v\n          WHERE "
            "v.lock_key = s.lock_key AND v.kind = 'discord_void'::text));")
NEW_POLICY = ("(kind = ANY (ARRAY['discord_signal'::text, 'discord_live'::text, "
              "'discord_void'::text]))")


class Ledger:
    """Serves the void SELECT and records inserts. close() keeps the rows."""

    def __init__(self, rows, view=NEW_VIEW, policy=NEW_POLICY):
        self.rows = [list(r) for r in rows]
        self.statements: list[tuple] = []
        self.commits = 0
        self.view = view
        self.policy = policy
        # How many discord_void INSERTs raise before one succeeds.
        self.fail_void_inserts = 0

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if "INSERT INTO push_sent" in sql and "'discord_void'" in sql:
            if self.fail_void_inserts:
                self.fail_void_inserts -= 1
                raise RuntimeError("server closed the connection")
        if "INSERT INTO push_sent" in sql:
            lock = params[0]
            column = 22 if "'discord_void'" in sql else 23
            for row in self.rows:
                if row[18] == lock:
                    row[column] = 1
        outer = self

        class Result:
            def fetchall(self):
                if "FROM picks" in sql:
                    return [tuple(r) for r in outer.rows]
                return []

            def fetchone(self):
                if "pg_get_viewdef" in sql:
                    return (outer.view, outer.policy)
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
        """discord_void rows: the notice's record, written after Discord took it."""
        return [s for s in self.statements
                if "INSERT INTO push_sent" in s[0] and "'discord_void'" in s[0]]

    @property
    def attempts(self):
        """void_notice_attempt rows, committed before each send."""
        return [s for s in self.statements
                if "INSERT INTO push_sent" in s[0] and "'void_notice_attempt'" in s[0]]


def _bind(monkeypatch, rows, post=None, migrate=None):
    ledger = Ledger(rows)
    monkeypatch.setattr(dn, "get_connection", lambda: ledger)
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: WEBHOOK)
    ledger.migrations = 0

    def _migrate(conn):
        # Each real file commits; here the call is only counted, so the
        # commit counts below stay about the notice's own writes.
        assert conn is ledger
        ledger.migrations += 1
        if migrate is not None:
            migrate(conn)

    monkeypatch.setattr(dn, "_apply_app_view_migrations", _migrate)
    calls = []

    def _post_void_once(url, payload):
        calls.append((url, payload))
        if post is None:
            return {"outcome": "posted", "message_id": "9001",
                    "detail": "HTTP 200"}
        return post(url, payload)

    monkeypatch.setattr(dn, "_post_void_once", _post_void_once)

    def forbid(*_a, **_k):
        raise AssertionError("the void notice used the resending _post")

    monkeypatch.setattr(dn, "_post", forbid)
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
    assert "-105 @ DraftKings" in field["value"]
    assert dn._posted_et("2026-09-27 10:22:17+00:00") in field["value"]
    blob = json.dumps(out)
    assert "super-secret-token" not in blob
    assert "api/webhooks" not in blob
    assert dn._void_title("MLB") == f"{dn._SPORT_EMOJI['MLB']} MLB \u00b7 Voided picks"


def test_a_field_reads_like_a_slate_field_for_a_member(monkeypatch):
    """The game day as the slate title prints it, the price, the post time.

    No raw date and no message id: a member can use neither.
    """
    _bind(monkeypatch, [_row(2992290)])
    out = dn.notify_discord_void([2992290], dry_run=True)
    value = out["payloads"][0]["payload"]["embeds"][0]["fields"][0]["value"]
    # "Posted" is when the pick was written (created_at, 6:22 AM ET), the
    # minute the slate card printed. The bot sent it at 6:23; that minute
    # would not match the card a member saw.
    posted = dn._posted_et("2026-09-27 10:22:17+00:00")
    assert "6:22 AM ET" in posted
    assert value.endswith(f"`-105 @ DraftKings` \u00b7 posted {posted}")
    assert "6:23" not in value
    assert "Sat Oct 17" in value
    assert "2026-10-17" not in value
    assert "1553713576831885365" not in value
    assert "original post" not in value
    # The slate title and the notice print the same day.
    title = dn._picks_embed("NCAAF", [], "2026-10-17")["title"]
    assert title.endswith(dn._slate_day("2026-10-17"))
    assert dn._slate_day("2026-11-07") == "Sat Nov 7"


def test_the_matchup_line_shows_only_when_the_label_lacks_a_team(monkeypatch):
    """'Georgia vs Auburn Under 54.5' already says who plays. 'Auburn @
    Georgia' under it repeats the label, so it is left off."""
    _bind(monkeypatch, [_row(2992290)])
    out = dn.notify_discord_void([2992290], dry_run=True)
    value = out["payloads"][0]["payload"]["embeds"][0]["fields"][0]["value"]
    assert "Auburn @ Georgia" not in value
    assert value.startswith("Sat Oct 17\n")

    base = {
        "sport": "NCAAF", "home": "Kansas", "away": "Kansas State",
        "dk_odds": -110, "best_odds": -110, "best_book": "draftkings",
        "game_date": "2026-10-17", "posted_at": None,
    }
    prop = dn._void_field({**base, "label": "Avery Johnson Over 1.5 Pass TDs"})
    assert prop["value"].startswith("Kansas State @ Kansas \u00b7 Sat Oct 17\n")
    # "Kansas State" is cut out before "Kansas" is looked for, so a label
    # naming only Kansas State does not count as naming both.
    side = dn._void_field({**base, "label": "Kansas State ML"})
    assert side["value"].startswith("Kansas State @ Kansas \u00b7 ")
    total = dn._void_field({**base, "label": "Kansas State vs Kansas Under 54.5"})
    assert total["value"] == "Sat Oct 17\n`-110 @ DraftKings`"


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
    assert first["complete"] is True
    assert [m["outcome"] for m in first["messages"]] == ["posted"]
    # The attempt row is committed before the send, the record after it.
    assert len(ledger.attempts) == 1
    assert ledger.statements.index(ledger.attempts[0]) < \
        ledger.statements.index(ledger.inserts[0])
    assert ledger.commits == 2
    second = dn.notify_discord_void([2992290], dry_run=False)
    assert second["posted"] == 0
    assert second["payloads"] == []
    assert second["skipped_lock_keys"] == [
        "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"]
    assert len(calls) == 1
    assert len(ledger.inserts) == 1
    assert ledger.commits == 2


def test_a_refused_or_lost_send_records_no_notice_and_does_not_raise(monkeypatch):
    """After a send is tried nothing raises: a raise would make the queue run
    the job again and post the notice twice."""
    refuse = {"outcome": "refused", "message_id": None, "detail": "HTTP 400: bad"}
    ledger, calls = _bind(monkeypatch, [_row(2992290)],
                          post=lambda url, payload: refuse)
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert len(calls) == 1
    assert out["complete"] is False
    assert out["posted"] == 0
    assert [m["outcome"] for m in out["messages"]] == ["refused"]
    assert "nothing was posted" in out["next_step"]
    assert ledger.inserts == []
    assert len(ledger.attempts) == 1      # the attempt row, before the send
    assert ledger.commits == 1

    def explode(url, payload):
        raise RuntimeError("webhook down")

    ledger2, calls2 = _bind(monkeypatch, [_row(2992283, lock="other:ncaaf_over_under",
                                                label="Kansas State vs Kansas Under 54.5")],
                            post=explode)
    out2 = dn.notify_discord_void([2992283], dry_run=False)
    assert len(calls2) == 1
    assert [m["outcome"] for m in out2["messages"]] == ["unknown"]
    assert "check the channel before queueing again" in out2["next_step"]
    assert ledger2.inserts == []


class _Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text

    def json(self):
        return self._body


def _through_requests(monkeypatch, rows, replies):
    """The real _post_void_once; requests.post answers from `replies`."""
    ledger = Ledger(rows)
    monkeypatch.setattr(dn, "get_connection", lambda: ledger)
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: WEBHOOK)
    monkeypatch.setattr(dn, "_apply_app_view_migrations", lambda conn: None)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    sends = []

    def post(url, **kw):
        sends.append(url)
        reply = replies[min(len(sends), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(dn.requests, "post", post)
    return ledger, sends


@pytest.mark.parametrize("reply", [
    dn.requests.exceptions.ReadTimeout("read timed out"),
    dn.requests.exceptions.ConnectionError("connection reset"),
    _Resp(502, text="bad gateway"),
    _Resp(500, text="internal"),
])
def test_a_lost_reply_is_sent_exactly_once(monkeypatch, reply):
    """Discord may have taken it. _post would send it three more times."""
    ledger, sends = _through_requests(monkeypatch, [_row(2992290)], [reply])
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert len(sends) == 1
    assert out["complete"] is False
    assert out["messages"][0]["outcome"] == "unknown"
    assert "check the channel before queueing again" in out["next_step"]
    assert ledger.inserts == []
    blob = json.dumps(out)
    assert "super-secret-token" not in blob and "api/webhooks" not in blob


def test_a_refusal_is_sent_once_and_a_429_is_the_only_retry(monkeypatch):
    ledger, sends = _through_requests(
        monkeypatch, [_row(2992290)], [_Resp(400, text="Invalid Form Body")])
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert len(sends) == 1
    assert out["messages"][0]["outcome"] == "refused"
    assert "Invalid Form Body" in out["messages"][0]["detail"]
    assert ledger.inserts == []

    # 429: Discord did not take it, so trying again cannot double-post.
    ledger2, sends2 = _through_requests(
        monkeypatch, [_row(2992290)],
        [_Resp(429, {"retry_after": 0.1}), _Resp(200, {"id": "4242"})])
    out2 = dn.notify_discord_void([2992290], dry_run=False)
    assert len(sends2) == 2
    assert out2["complete"] is True
    assert out2["message_ids"] == ["4242"]
    assert len(ledger2.inserts) == 1


def test_a_post_whose_save_fails_keeps_its_id_and_never_posts_again(monkeypatch):
    """Discord took it, then the database dropped. The id is in the result,
    nothing raises, and the next run refuses instead of posting again."""
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    ledger.fail_void_inserts = 2          # this connection, then the fresh one
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert len(calls) == 1
    assert out["complete"] is False
    assert out["message_ids"] == ["9001"]
    m = out["messages"][0]
    assert m["outcome"] == "posted_not_recorded"
    assert m["message_id"] == "9001"
    assert "again on a fresh connection" in m["detail"]
    assert "9001" in out["next_step"]
    # The rerun: the attempt row has no notice row beside it.
    with pytest.raises(dn.DiscordVoidUnresolved, match="may already be in the channel"):
        dn.notify_discord_void([2992290], dry_run=False)
    assert len(calls) == 1


def test_a_failed_save_is_tried_once_more_on_a_fresh_connection(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    ledger.fail_void_inserts = 1
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert out["complete"] is True
    assert out["posted"] == 1
    assert len(calls) == 1
    # Two INSERT tries: the failed one and the one that saved.
    assert len(ledger.inserts) == 2


def test_a_reclaimed_run_with_an_attempt_on_record_sends_nothing(monkeypatch):
    """The worker died between the send and the save. The job comes back with
    its attempt given back; the attempt row stops it."""
    ledger, calls = _bind(monkeypatch, [_row(2992290, attempted=True)])
    with pytest.raises(dn.DiscordVoidUnresolved):
        dn.notify_discord_void([2992290], dry_run=False)
    assert calls == []
    assert ledger.inserts == [] and ledger.attempts == []
    assert ledger.commits == 0
    assert ledger.migrations == 0          # refused before anything else
    # A dry run shows it rather than refusing.
    dry = dn.notify_discord_void([2992290], dry_run=True)
    assert dry["unresolved_attempt_lock_keys"] == [
        "NCAAF_2026-10-17_auburn_georgia:ncaaf_over_under"]


def test_a_check_that_fails_before_the_send_still_raises(monkeypatch):
    """Before a send nothing is in the channel, so the ordinary retry is safe."""
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: None)
    with pytest.raises(dn.DiscordVoidRejected, match="no webhook"):
        dn.notify_discord_void([2992290], dry_run=False)
    assert calls == [] and ledger.attempts == []

    # The attempt row cannot be saved: nothing is sent, and it raises.
    ledger2, calls2 = _bind(monkeypatch, [_row(2992290)])
    real = ledger2.execute

    def no_attempt(sql, params=None):
        if "INSERT INTO push_sent" in sql and "'void_notice_attempt'" in sql:
            raise RuntimeError("read-only transaction")
        return real(sql, params)

    ledger2.execute = no_attempt
    with pytest.raises(dn.DiscordVoidRejected, match="so nothing was sent"):
        dn.notify_discord_void([2992290], dry_run=False)
    assert calls2 == []


# ── The queue never reruns a send by itself ─────────────────────────────────

class _JobConn:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def commit(self):
        pass


def _run_job(monkeypatch, notify):
    from tracking import job_queue as q

    announced = []
    monkeypatch.setattr(q, "_announce",
                        lambda job, ok, detail: announced.append((ok, detail)))
    monkeypatch.setattr(dn, "notify_discord_void", notify)
    conn = _JobConn()
    job = {"job_id": 7, "job_type": "publish_discord_void", "attempts": 1,
           "args": {"pick_ids": [2992290], "dry_run": False}}
    out = q._execute(conn, job)
    update = [s for s in conn.statements if "UPDATE worker_jobs" in s[0]]
    return out, update, announced


def test_an_incomplete_post_fails_the_job_on_its_first_attempt(monkeypatch):
    """Without this the half-sent notice is "done" with a green check, or a
    raise puts it back to pending and the next tick posts it again."""
    result = {"dry_run": False, "posted": 0, "complete": False,
              "message_ids": [], "messages": [{"outcome": "unknown"}],
              "next_step": "Discord may have accepted it; check the channel "
                           "before queueing again."}
    out, update, announced = _run_job(
        monkeypatch, lambda pick_ids, reason=None, dry_run=True: result)
    assert out["status"] == "failed" and out["final"] is True
    sql, params = update[0]
    assert "status = 'failed'" in sql
    assert "pending" not in json.dumps(params)
    assert json.loads(params[0])["complete"] is False
    assert announced and announced[0][0] is False
    assert "check the channel" in announced[0][1]


def test_an_unresolved_attempt_fails_the_job_without_a_retry(monkeypatch):
    def unresolved(pick_ids, reason=None, dry_run=True):
        raise dn.DiscordVoidUnresolved(["an earlier void notice may already "
                                        "be in the channel"])

    out, update, announced = _run_job(monkeypatch, unresolved)
    assert out["final"] is True
    assert "status = 'failed'" in update[0][0]
    assert announced and announced[0][0] is False


def test_a_check_before_the_send_keeps_the_ordinary_retry(monkeypatch):
    def rejected(pick_ids, reason=None, dry_run=True):
        raise dn.DiscordVoidRejected(["no webhook for NCAAF"])

    out, update, announced = _run_job(monkeypatch, rejected)
    assert out["final"] is False
    assert update[0][1][0] == "pending"
    assert announced == []


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
    embeds = dn.void_notice_embeds("NCAAF", picks, dn.VOID_NOTICE_REASON)
    assert [len(e["fields"]) for e in embeds] == [25, 1]
    assert all(e["color"] == dn._COLOR_VOID for e in embeds)
    fat = [{
        **picks[0], "label": f"Fat {i}",
    } for i in range(20)]
    # A long value still under the per-field cap, over the embed cap well
    # before 25 fields.
    long = "x" * 400

    real = dn._void_field

    def bulky(pick):
        field = real(pick)
        field["value"] = long
        return field

    dn._void_field = bulky
    try:
        chunked = dn.void_notice_embeds("NCAAF", fat, dn.VOID_NOTICE_REASON)
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


# The 15 labels as stored on the picks, in the order the notice lists them:
# the 8 voided 2026-10-09 by game date, then the 7 voided 2026-09-19.
_STALE_LABELS = [
    "Kansas State vs Kansas Under 54.5", "Georgia vs Auburn Under 54.5",
    "BYU vs Notre Dame Under 54.5", "Ohio State vs Oregon Under 52.5",
    "LSU vs Alabama Under 54.5", "Texas A&M vs Tennessee Under 55.5",
    "Clemson vs South Carolina Under 53.5", "Vanderbilt vs Tennessee Under 57.5",
    "Clemson vs Miami Under 55.5", "Alabama vs Texas A&M Under 54.5",
    "Michigan vs Michigan State Under 50.5", "Oklahoma vs Ole Miss Under 53.5",
    "Ole Miss vs Mississippi State Over 57.5", "Ohio State vs Michigan Under 46.5",
    "Navy vs Army Over 37.5",
]


def _stale_picks(n):
    return [{
        "sport": "NCAAF", "label": label,
        "home": label.split(" vs ")[0], "away": label.split(" vs ")[1].rsplit(" ", 2)[0],
        "dk_odds": -112, "best_odds": -112, "best_book": "draftkings",
        "game_date": "2026-11-28", "posted_at": "2026-09-27T06:23:03-04:00",
    } for label in _STALE_LABELS[:n]]


@pytest.mark.parametrize("name, n", [
    ("VOID_NOTICE_NCAAF_STALE_8", 8), ("VOID_NOTICE_NCAAF_STALE_15", 15),
])
def test_the_ncaaf_stale_notice_is_one_message_and_true_after_it_posts(name, n):
    """mike's fuller text, as the description of one embed.

    The fields are the list, so the text has none. The app sentence says what
    the app shows once the notice is the publish state; the draft's "they'll
    still show in the app for now" would be false by then.
    """
    from tracking import job_queue as q

    text = getattr(dn, name)
    assert "\u2022" not in text and "\n- " not in text
    assert "still show in the app" not in text
    assert "The app no longer shows them as picks." in text
    assert 'under Tracked picks, marked "Not graded."' in text
    assert "DraftKings took these games down in early September" in text
    assert "That's on us." in text
    assert text.startswith(f"We've voided the {n} college football picks below")
    assert text.endswith("If DraftKings takes a game down, we stop making "
                         "picks on it.")
    # A dry run may still carry the text as `reason` (capped at 4000); a
    # real post names it with reason_key (see the job tests below).
    assert q._validate_publish_discord_void(
        {"pick_ids": [1], "reason": text})["reason"] == text
    embeds = dn.void_notice_embeds("NCAAF", _stale_picks(n), text)
    assert len(embeds) == 1
    embed = embeds[0]
    # mike's draft title: "Correction" and the count, not "Voided picks".
    assert embed["title"] == f"\U0001f3c8 NCAAF \u00b7 Correction: {n} picks voided"
    assert embed["description"] == text
    assert [f["name"] for f in embed["fields"]] == _STALE_LABELS[:n]
    assert dn._embed_size(embed["title"], text, embed["fields"]) < 6000


def test_the_15_notice_says_which_7_were_already_off_the_record():
    text = dn.VOID_NOTICE_NCAAF_STALE_15
    assert "8 posted Sep 20 \u2013 Oct 4, and 7 posted Sep 7\u201313" in text
    assert "already taken off the record on Sep 19 and never counted" in text
    assert "None of the 8 has been played." in text
    assert "Clemson vs Miami was played Oct 3 and never counted" in text
    assert "15" not in dn.VOID_NOTICE_NCAAF_STALE_8
    assert "Sep 7" not in dn.VOID_NOTICE_NCAAF_STALE_8
    # The short default stays for any other void notice.
    assert dn.VOID_NOTICE_REASON == (
        "Voided: priced off a stale sportsbook line after our odds feed dropped "
        "the game. These picks are void and do not count in the record. The "
        "original posts are left as they were.")


# ── A written text and the list it describes ────────────────────────────────

_EIGHT = sorted(dn.VOID_NOTICE_PICK_IDS["ncaaf_stale_8"])
_FIFTEEN = sorted(dn.VOID_NOTICE_PICK_IDS["ncaaf_stale_15"])


def _rows_for(ids, voided=()):
    return [_row(i, voided=i in voided, lock=f"L{i}:ncaaf_over_under",
                 label=f"Georgia vs Auburn Under {50 + n}.5")
            for n, i in enumerate(ids)]


def _forbid_http(monkeypatch):
    def forbid(*_a, **_k):
        raise AssertionError("an HTTP call was made")

    monkeypatch.setattr(dn.requests, "post", forbid)


def test_the_named_texts_carry_their_exact_picks():
    assert dn.VOID_NOTICE_TEXTS == {
        "ncaaf_stale_8": dn.VOID_NOTICE_NCAAF_STALE_8,
        "ncaaf_stale_15": dn.VOID_NOTICE_NCAAF_STALE_15,
    }
    assert set(_EIGHT) == {2558703, 2558736, 2935576, 2992283, 2992290,
                           2992474, 3020766, 3204788}
    assert set(_FIFTEEN) == set(_EIGHT) | {1769626, 1769753, 1769812, 1992830,
                                           2109187, 2109205, 2109285}


def test_a_written_text_goes_out_only_over_its_own_picks(monkeypatch):
    """The 15 text sent with the 8 ids is false in its first sentence."""
    ledger, calls = _bind(monkeypatch, _rows_for(_FIFTEEN))
    _forbid_http(monkeypatch)
    with pytest.raises(dn.DiscordVoidRejected, match="exactly 15 picks"):
        dn.notify_discord_void(_EIGHT, reason=dn.VOID_NOTICE_NCAAF_STALE_15,
                               dry_run=False)
    with pytest.raises(dn.DiscordVoidRejected, match="exactly 8 picks"):
        dn.notify_discord_void(_FIFTEEN, reason=dn.VOID_NOTICE_NCAAF_STALE_8,
                               dry_run=True)
    with pytest.raises(dn.DiscordVoidRejected, match="not in that text: 1"):
        dn.notify_discord_void(_EIGHT + [1], reason=dn.VOID_NOTICE_NCAAF_STALE_8,
                               dry_run=True)
    # Refused before the database is read, so nothing is sent or written.
    assert calls == []
    assert ledger.statements == []
    assert ledger.commits == 0
    out = dn.notify_discord_void(_EIGHT, reason=dn.VOID_NOTICE_NCAAF_STALE_8,
                                 dry_run=True)
    assert len(out["payloads"][0]["payload"]["embeds"][0]["fields"]) == 8


def test_a_written_text_is_not_posted_over_part_of_its_list(monkeypatch):
    """The 8 already noticed, then the 15 run: the bot would post "We've
    voided the 15 ... below" over a message that lists 7."""
    ledger, calls = _bind(monkeypatch, _rows_for(_FIFTEEN, voided=set(_EIGHT)))
    _forbid_http(monkeypatch)
    for dry_run in (False, True):
        with pytest.raises(dn.DiscordVoidRejected,
                           match="8 of these picks already have a void notice"):
            dn.notify_discord_void(_FIFTEEN, reason=dn.VOID_NOTICE_NCAAF_STALE_15,
                                   dry_run=dry_run)
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0
    # The short default names no count, so it still fits the 7 left.
    out = dn.notify_discord_void(_FIFTEEN, dry_run=True)
    embeds = [e for item in out["payloads"] for e in item["payload"]["embeds"]]
    assert len(embeds) == 1
    assert len(embeds[0]["fields"]) == 7
    assert embeds[0]["description"] == dn.VOID_NOTICE_REASON
    assert len(out["skipped_lock_keys"]) == 8
    # A finished list is still a no-op, written text or not.
    done = _rows_for(_FIFTEEN, voided=set(_FIFTEEN))
    _bind(monkeypatch, done)
    again = dn.notify_discord_void(_FIFTEEN, reason=dn.VOID_NOTICE_NCAAF_STALE_15,
                                   dry_run=False)
    assert again["posted"] == 0 and again["payloads"] == []


# ── The job takes a reviewed text by name ───────────────────────────────────

# The draft's paragraph that is false once the notice is the publish state.
_OLD_DRAFT_SENTENCE = (
    "None has been played, so nothing already in the record changes, and none "
    "was the free pick. They'll still show in the app for now, marked \"not "
    "counted\" on the pick's page.")


def test_the_job_hands_the_notice_the_constant_by_name(monkeypatch):
    """The job stores the name and looks the text up when it runs, so the
    words that go out are the reviewed constant, character for character."""
    from tracking import job_queue as q

    calls = []

    def fake(pick_ids, reason=None, dry_run=True):
        calls.append((list(pick_ids), reason, dry_run))
        return {"posted": 0, "dry_run": dry_run}

    monkeypatch.setattr(dn, "notify_discord_void", fake)
    for key, ids in (("ncaaf_stale_8", _EIGHT), ("ncaaf_stale_15", _FIFTEEN)):
        for dry_run in (True, False):
            args = q._validate_publish_discord_void(
                {"pick_ids": ids, "reason_key": key, "dry_run": dry_run})
            assert args == {"pick_ids": ids, "dry_run": dry_run,
                            "reason_key": key}
            q._job_publish_discord_void(**args)
            assert calls[-1] == (ids, dn.VOID_NOTICE_TEXTS[key], dry_run)


def test_the_job_refuses_a_text_nobody_reviewed_for_a_real_post():
    from tracking import job_queue as q

    validate = q._validate_publish_discord_void
    with pytest.raises(ValueError, match="unknown reason_key"):
        validate({"pick_ids": _EIGHT, "reason_key": "ncaaf_stale_9"})
    with pytest.raises(ValueError, match="unknown reason_key"):
        validate({"pick_ids": _EIGHT, "reason_key": ["ncaaf_stale_8"]})
    with pytest.raises(ValueError, match="not both"):
        validate({"pick_ids": _EIGHT, "reason_key": "ncaaf_stale_8",
                  "reason": dn.VOID_NOTICE_NCAAF_STALE_8})
    # The 15 text with the 8 ids would say 15 over a list of 8.
    with pytest.raises(ValueError, match="exactly 15 picks"):
        validate({"pick_ids": _EIGHT, "reason_key": "ncaaf_stale_15"})
    with pytest.raises(ValueError, match="exactly 8 picks"):
        validate({"pick_ids": _FIFTEEN, "reason_key": "ncaaf_stale_8"})
    # Pasted text cannot make a real post, not even a perfect copy.
    for text in (_OLD_DRAFT_SENTENCE, dn.VOID_NOTICE_NCAAF_STALE_8):
        with pytest.raises(ValueError, match="takes reason_key"):
            validate({"pick_ids": _EIGHT, "reason": text, "dry_run": False})
    # A dry run may still try out a text, and the short default still posts.
    assert validate({"pick_ids": _EIGHT, "reason": _OLD_DRAFT_SENTENCE}) == {
        "pick_ids": _EIGHT, "dry_run": True, "reason": _OLD_DRAFT_SENTENCE}
    assert validate({"pick_ids": [5], "dry_run": False}) == {
        "pick_ids": [5], "dry_run": False}


def test_every_declared_void_notice_names_a_reviewed_text():
    """The declared job is what posts. It must carry a name, not pasted
    text, and exactly that text's picks. (None is declared yet: the entry
    waits for mike's final OK. This holds it to the rule when it lands.)"""
    from tracking import job_queue as q

    entries = json.loads((ROOT / "jobs/declared_jobs.json").read_text(
        encoding="utf-8"))
    for entry in entries:
        if entry.get("job_type") != "publish_discord_void":
            continue
        args = entry.get("args") or {}
        assert "reason" not in args, entry.get("key")
        key = args.get("reason_key")
        assert key in dn.VOID_NOTICE_TEXTS, entry.get("key")
        assert set(args.get("pick_ids") or []) == dn.VOID_NOTICE_PICK_IDS[key]
        q._validate_publish_discord_void(args)


# ── The app has to drop the picks before the notice says it does ────────────

@pytest.mark.parametrize("view, policy", [
    (OLD_VIEW, OLD_POLICY),     # production on 2026-10-10
    (NEW_VIEW, OLD_POLICY),     # the view runs as the caller: still shows them
    (OLD_VIEW, NEW_POLICY),
    (None, NEW_POLICY),         # no view at all
    (NEW_VIEW, None),           # no policy at all
])
def test_a_real_post_waits_for_the_app_to_drop_voided_picks(monkeypatch, view,
                                                             policy):
    """mike's text says "The app no longer shows them as picks." Until the
    view and its read policy both drop a pick with a void notice, that is
    false, and a post cannot be taken back."""
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    ledger.view, ledger.policy = view, policy
    with pytest.raises(dn.DiscordVoidRejected, match="app would still show"):
        dn.notify_discord_void([2992290], dry_run=False)
    assert ledger.migrations == 1          # it tried to fix it first
    assert calls == []
    assert ledger.inserts == []
    assert ledger.commits == 0


def test_a_real_post_applies_the_migration_then_posts(monkeypatch):
    """A declared job can run before the deploy's migrations have. The
    notice applies them itself, then checks, then posts."""
    def migrate(conn):
        conn.view, conn.policy = NEW_VIEW, NEW_POLICY

    ledger, calls = _bind(monkeypatch, [_row(2992290)], migrate=migrate)
    ledger.view, ledger.policy = OLD_VIEW, OLD_POLICY
    out = dn.notify_discord_void([2992290], dry_run=False)
    assert ledger.migrations == 1
    assert len(calls) == 1
    assert out["posted"] == 1


def test_a_dry_run_reports_the_app_view_and_changes_nothing(monkeypatch):
    ledger, calls = _bind(monkeypatch, [_row(2992290)])
    ledger.view, ledger.policy = OLD_VIEW, OLD_POLICY
    out = dn.notify_discord_void([2992290], dry_run=True)
    assert out["app_view_ready"] is False
    assert ledger.migrations == 0
    assert ledger.commits == 0
    assert calls == []
    ledger.view, ledger.policy = NEW_VIEW, NEW_POLICY
    assert dn.notify_discord_void([2992290])["app_view_ready"] is True


def test_the_readiness_read_is_the_migrations_own_skip_check():
    """The guard reads what the migration's skip clause reads: the view text
    and the anon_read_discord_publish policy on push_sent."""
    sql = dn._APP_VIEW_READY_SQL
    assert "pg_get_viewdef(to_regclass('public.v_discord_published'), true)" in sql
    assert "p.polname = 'anon_read_discord_publish'" in sql
    assert "c.relname = 'push_sent'" in sql
    mig = NEW_MIG.read_text(encoding="utf-8")
    assert "p.polname = 'anon_read_discord_publish'" in mig
    assert "position('discord_void' in d) > 0" in mig
    assert "position('discord_void' in pol) > 0" in mig

    class Broken:
        def execute(self, *_a, **_k):
            raise RuntimeError("no such function")

        def rollback(self):
            pass

    assert dn._app_view_ready(Broken()) is False
