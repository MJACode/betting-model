import json

import config
import scripts.post_record_correction as rc
import tracking.job_queue as jq


class Conn:
    def __init__(self, row=None):
        self.row, self.writes = row, []

    def execute(self, sql, params=()):
        if sql.startswith("INSERT"):
            self.writes.append(params)
            self.row = (params[3],)
        conn = self

        class R:
            def fetchone(self_inner):
                return conn.row
        return R()

    def commit(self):
        pass


def test_posts_once_and_ledgers(monkeypatch):
    monkeypatch.setattr(rc, "_results_url", lambda: "https://hook")
    sent = []
    c = Conn()
    out = rc.publish_full_record(c, post=lambda u, t: sent.append(t) or "123",
                                 place=lambda u: ("g", "c"))
    assert sent == [rc.FULL_RECORD_TEXT]
    assert out["discord_url"] == "https://discord.com/channels/g/c/123"
    again = rc.publish_full_record(c, post=lambda u, t: sent.append(t) or "9",
                                   place=lambda u: ("g", "c"))
    assert len(sent) == 1 and again["discord_message_id"] == "123"


def test_text_and_job_declared_once():
    assert "431-375-2, +16.92u" in rc.FULL_RECORD_TEXT
    assert len(rc.FULL_RECORD_TEXT) <= 2000
    fn, validate = jq.JOBS["publish_full_record"]
    assert fn is jq._job_publish_full_record and validate({}) == {}
    entries = json.loads((config.ROOT / "jobs" / "declared_jobs.json").read_text())
    m = [e for e in entries if e["key"] == "full-record-2026-10-14"]
    assert len(m) == 1 and m[0]["job_type"] == "publish_full_record"


def test_standard_post_uses_given_embed_once(monkeypatch):
    monkeypatch.setattr(rc, "_results_url", lambda: "https://hook")
    sent = []
    c = Conn()
    emb = {"title": "x", "fields": []}
    out = rc.publish_full_record_standard(
        c, post=lambda u, p: sent.append(p) or "55", place=lambda u: ("g", "c"),
        embed=emb)
    assert sent == [{"embeds": [emb]}] and out["discord_message_id"] == "55"
    rc.publish_full_record_standard(c, post=lambda u, p: sent.append(p) or "9",
                                    place=lambda u: ("g", "c"), embed=emb)
    assert len(sent) == 1
