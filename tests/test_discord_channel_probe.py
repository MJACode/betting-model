"""The probe answers "which channel does this webhook post to" — and nothing else.

mike, 2026-09-05: "there are NO UFC picks in the channel", against a ledger row
that says one was posted, with a Discord message_id. Both can be true if the
webhook points somewhere else. The webhook URL lives only in the worker's
environment, so the question can only be asked from there — and it must be
asked WITHOUT posting anything to a member-facing channel.

Two properties, and the second is the safety one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tracking.job_queue as jq  # noqa: E402


class _Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


def test_the_probe_reports_the_channel_behind_each_sport(monkeypatch):
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS",
                        {"MLB": "https://discord.com/api/webhooks/1/mlbtoken",
                         "UFC": "https://discord.com/api/webhooks/2/ufctoken"},
                        raising=False)
    for attr in ("DISCORD_WEBHOOK_DEFAULT", "DISCORD_WEBHOOK_LIVE",
                 "DISCORD_WEBHOOK_RESULTS", "DISCORD_WEBHOOK_FREE",
                 "DISCORD_WEBHOOK_OPS"):
        monkeypatch.setattr(config, attr, "", raising=False)

    seen = []

    def _get(url, timeout=None):
        seen.append(url)
        chan = "111" if "mlbtoken" in url else "222"
        return _Resp(body={"channel_id": chan, "guild_id": "g", "name": "hook"})

    import requests
    monkeypatch.setattr(requests, "get", _get)

    out = jq._job_discord_probe()
    assert out["sport:MLB"]["channel_id"] == "111"
    assert out["sport:UFC"]["channel_id"] == "222"
    assert out["_summary"]["distinct_channels"] == 2
    assert out["_summary"]["collisions"] == []


def test_two_sports_sharing_a_channel_are_flagged(monkeypatch):
    """The failure this exists to catch: UFC's webhook pointing at some other
    sport's channel, or at the free channel. Every symptom is identical to a
    correct setup except the channel id."""
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS",
                        {"MLB": "https://discord.com/api/webhooks/1/a",
                         "UFC": "https://discord.com/api/webhooks/2/b"},
                        raising=False)
    for attr in ("DISCORD_WEBHOOK_DEFAULT", "DISCORD_WEBHOOK_LIVE",
                 "DISCORD_WEBHOOK_RESULTS", "DISCORD_WEBHOOK_FREE",
                 "DISCORD_WEBHOOK_OPS"):
        monkeypatch.setattr(config, attr, "", raising=False)

    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=None: _Resp(
                            body={"channel_id": "same", "name": "hook"}))
    out = jq._job_discord_probe()
    assert out["_summary"]["collisions"] == ["same"]


def test_the_probe_never_posts_and_never_returns_the_url(monkeypatch):
    """A webhook URL is a bearer credential and a job result is read by humans
    out of Postgres. And a diagnostic that publishes to a paid channel is not a
    diagnostic."""
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS",
                        {"UFC": "https://discord.com/api/webhooks/2/SECRETTOKEN"},
                        raising=False)
    for attr in ("DISCORD_WEBHOOK_DEFAULT", "DISCORD_WEBHOOK_LIVE",
                 "DISCORD_WEBHOOK_RESULTS", "DISCORD_WEBHOOK_FREE",
                 "DISCORD_WEBHOOK_OPS"):
        monkeypatch.setattr(config, attr, "", raising=False)

    import requests

    def _boom(*a, **k):
        raise AssertionError("the probe must never POST to a webhook")

    monkeypatch.setattr(requests, "post", _boom)
    monkeypatch.setattr(requests, "delete", _boom)
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=None: _Resp(
                            body={"channel_id": "c", "name": "hook"}))

    out = jq._job_discord_probe()
    assert "SECRETTOKEN" not in repr(out)


def test_the_probe_is_registered_and_takes_no_arguments():
    fn, validate = jq.JOBS["discord_probe"]
    assert fn is jq._job_discord_probe
    assert validate({"anything": "ignored"}) == {}
