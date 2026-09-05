"""
A BET is published by whoever WROTE it, not by whoever happens to run next.

THE BUG THIS PINS (2026-09-05). The pre-game line poller re-scores every 30
seconds and, until this change, notified nobody: publishing waited for the next
hourly refresh pass. On the 2026-09-05 UFC card that gap ate a real pick —

    18:27:16Z  poller writes mario-pinto/ryan-spann ufc_moneyline -195 BET
    18:40:00Z  the fight starts
    19:23:24Z  the hourly pass locks the signal, 43 minutes too late
               -> the started-game guard drops it, correctly and forever

— and it is why exactly ONE UFC signal reached Discord between 2026-08-23
(when Discord posting shipped) and 2026-09-05.

The properties below are the two halves of the fix. The poller must publish
what it writes, and publishing must never be able to kill the loop that calls
it: a stopped poller and a quiet market look identical from the outside (§7).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from data.ingestors.pregame_line_poller import PRICE_COLS, poll_once  # noqa: E402
from tracking import signal_publisher  # noqa: E402


def _row(game_id="UFC_2026-09-05_mario-pinto_ryan-spann", market="h2h", **over):
    r = {"game_id": game_id, "market": market,
         "bookmaker": config.ODDS_API_BOOKMAKER, "snapshot_type": "open"}
    for c in PRICE_COLS:
        r[c] = None
    r.update(over)
    return r


class _Conn:
    """Enough of a connection for a tick. Reads return empty / zero."""

    def execute(self, sql, params=None):
        class C:
            def fetchall(self_inner):
                return []

            def fetchone(self_inner):
                return (0,)
        return C()

    def commit(self):
        pass

    def rollback(self):
        pass


def _tick(monkeypatch, bets: int, publish):
    """One poll_once with the network and the scorer stubbed, a moved price on
    the wire, and `publish` standing in for the real publisher."""
    import data.ingestors.odds_ingestor as oi
    monkeypatch.setattr(oi, "fetch_pregame_rows",
                        lambda sports: [_row(home_price="-195")], raising=False)
    monkeypatch.setattr(oi, "_insert_odds", lambda conn, rows: None, raising=False)

    scorer = types.ModuleType("models.scorer")
    scorer.run_scorer = lambda **kw: {"bets": bets, "total_picks": bets + 4}
    monkeypatch.setitem(sys.modules, "models.scorer", scorer)

    monkeypatch.setattr(signal_publisher, "publish_new_signals", publish)
    return poll_once(_Conn(), sports=["UFC"], known={})


# ── the poller publishes what it writes ──────────────────────────────────────

def test_a_tick_that_writes_a_bet_publishes_it(monkeypatch):
    """The whole fix. Without this the pick waits up to an hour for the pass,
    and a fight that starts inside that hour is never posted at all."""
    calls = []
    _tick(monkeypatch, bets=1, publish=lambda **kw: calls.append(kw) or {})
    assert len(calls) == 1, (
        "a tick that wrote a BET did not publish it — the pick now waits for "
        "the next hourly pass, which is the 2026-09-05 UFC bug")


def test_a_tick_that_writes_no_bet_publishes_nothing(monkeypatch):
    """95% of ticks find nothing. Publishing on those would spend three
    database reads every 30 seconds to discover there is nothing to say."""
    calls = []
    _tick(monkeypatch, bets=0, publish=lambda **kw: calls.append(kw) or {})
    assert calls == []


def test_the_tick_publishes_for_the_date_it_scored(monkeypatch):
    """Publishing a different date than the one just scored would lock and post
    yesterday's board off today's price move."""
    calls = []
    _tick(monkeypatch, bets=2, publish=lambda **kw: calls.append(kw) or {})
    assert calls[0].get("target_date") == config.today_et()


def test_a_publish_failure_does_not_kill_the_tick(monkeypatch):
    """§7: a poller that dies on one bad payload is worse than no poller — it
    looks exactly like a quiet market."""
    def _boom(**kw):
        raise RuntimeError("discord webhook 500")

    result = _tick(monkeypatch, bets=1, publish=_boom)
    assert result["picks"] == 5, "a failed publish swallowed the tick's result"


def test_the_poller_no_longer_claims_it_does_not_notify():
    """The docstring said 'It does not settle, notify, or health-check'. That
    sentence is why nobody looked here for a month."""
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "pregame_line_poller.py").read_text(encoding="utf-8")
    assert "does not settle, notify, or health-check" not in src


# ── the publisher itself ─────────────────────────────────────────────────────

def _surfaces(monkeypatch, order, fail=()):
    """Stub the three delivery functions, recording call order."""
    def _make(name, ret):
        def _fn(target_date=None, dry_run=False):
            order.append(name)
            if name in fail:
                raise RuntimeError(f"{name} is down")
            return ret
        return _fn

    osig = types.ModuleType("tracking.opening_signals")
    osig.capture_opening_signals = _make("capture", 2)
    push = types.ModuleType("tracking.push_notifier")
    push.notify_signal_changes = _make("push", 1)
    disc = types.ModuleType("tracking.discord_notifier")
    disc.notify_discord_signals = _make("discord", 3)

    monkeypatch.setitem(sys.modules, "tracking.opening_signals", osig)
    monkeypatch.setitem(sys.modules, "tracking.push_notifier", push)
    monkeypatch.setitem(sys.modules, "tracking.discord_notifier", disc)


def test_capture_runs_before_either_notifier(monkeypatch):
    """Both notifiers read opening_signals. Deliver first and the cross that
    just landed is invisible to them."""
    order = []
    _surfaces(monkeypatch, order)
    out = signal_publisher.publish_new_signals(target_date="2026-09-05")
    assert order == ["capture", "push", "discord"]
    assert out == {"locked": 2, "pushed": 1, "discord": 3}


def test_a_failed_capture_still_delivers(monkeypatch):
    """Signals locked on an earlier tick may still be unposted — a capture
    failure must not decide that there is nothing to deliver."""
    order = []
    _surfaces(monkeypatch, order, fail={"capture"})
    out = signal_publisher.publish_new_signals(target_date="2026-09-05")
    assert order == ["capture", "push", "discord"]
    assert out["locked"] == 0 and out["pushed"] == 1 and out["discord"] == 3


def test_a_broken_webhook_does_not_suppress_the_push(monkeypatch):
    """Two delivery channels, one trigger. Discord failing is not push failing."""
    order = []
    _surfaces(monkeypatch, order, fail={"discord"})
    out = signal_publisher.publish_new_signals(target_date="2026-09-05")
    assert out["pushed"] == 1 and out["discord"] == 0


def test_publish_never_raises(monkeypatch):
    """Its caller is a loop. Anything else and the price watcher stops."""
    order = []
    _surfaces(monkeypatch, order, fail={"capture", "push", "discord"})
    assert signal_publisher.publish_new_signals(target_date="2026-09-05") == {
        "locked": 0, "pushed": 0, "discord": 0}


def test_the_publisher_does_not_fire_the_pass_only_surfaces():
    """The daily free pick, the restatement and the X post belong to a
    scheduled pass. A 30-second loop must not be able to reach them."""
    src = (Path(__file__).parent.parent / "tracking"
           / "signal_publisher.py").read_text(encoding="utf-8")
    for forbidden in ("notify_discord_free_pick", "notify_discord_restate",
                      "notify_x_free_pick", "notify_line_changes"):
        assert f"{forbidden}(" not in src, (
            f"{forbidden} is reachable from a 30-second loop")


# ── the other writers outside the refresh pass ───────────────────────────────

def _body(src: str, name: str) -> str:
    start = src.index(f"def {name}(")
    rest = src[start:]
    end = rest.find("\ndef ", 1)
    return rest if end < 0 else rest[:end]


@pytest.mark.parametrize("job", ["run_nfl_poll", "run_nfl_prop_card"])
def test_every_pick_writing_scheduler_job_publishes(job):
    """§1b: assess an operational change against every model, not the one that
    broke. The pre-game poller is not the only writer that runs outside the
    refresh pass — the NFL card jobs write picks on their own cadence, and
    inside the 3-hour fast window that lag can outlast the kickoff."""
    src = (Path(__file__).parent.parent / "scheduler.py").read_text(
        encoding="utf-8")
    assert "_publish_new_signals(" in _body(src, job), (
        f"{job} writes picks and never publishes them — they wait for the "
        "next :17 pass, which is the 2026-09-05 UFC bug in another lane")
