"""The NFL live loop announces its own picks (2026-09-09, mike).

Until today the worker wrote a live BET to `picks` and told nobody: the mobile
push and the Discord live room only saw it if the MLB or NCAAF loop happened to
end a pass in the same window and swept the row up. The other two loops call
both notifiers at the end of every pass; this pins that this one does too.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from nfl.live_model.workers.gameday import GamedayWorker  # noqa: E402


def _worker_with_tick(monkeypatch, summary):
    w = GamedayWorker(odds_client=object())
    monkeypatch.setattr(w, "tick", lambda now=None: dict(summary))
    return w


def _capture_notifiers(monkeypatch):
    import tracking.push_notifier as pn
    import tracking.discord_notifier as dn
    calls: list = []
    monkeypatch.setattr(pn, "notify_live_signals",
                        lambda target_date, dry_run: calls.append(("push", target_date, dry_run)))
    monkeypatch.setattr(dn, "notify_discord_live",
                        lambda target_date, dry_run: calls.append(("discord", target_date, dry_run)))
    return calls


def test_a_tick_that_bet_announces_on_both_surfaces(monkeypatch):
    calls = _capture_notifiers(monkeypatch)
    w = _worker_with_tick(monkeypatch, {"live": 1, "hunting": 0, "anchor_polls": 0,
                                        "deriv_polls": 0, "prop_polls": 1,
                                        "errors": [], "prop_bets": 1})
    w.run(max_ticks=1, sleep_sec=0, idle_exit_ticks=None)
    assert [c[0] for c in calls] == ["push", "discord"]
    assert all(c[2] is False for c in calls)
    # Same date the pick writer stamps on the row: today, UTC.
    from datetime import datetime, timezone
    assert {c[1] for c in calls} == {datetime.now(timezone.utc).date().isoformat()}


def test_a_quiet_tick_announces_nothing(monkeypatch):
    calls = _capture_notifiers(monkeypatch)
    w = _worker_with_tick(monkeypatch, {"live": 1, "hunting": 0, "anchor_polls": 0,
                                        "deriv_polls": 0, "prop_polls": 1,
                                        "errors": [], "prop_bets": 0})
    w.run(max_ticks=1, sleep_sec=0, idle_exit_ticks=None)
    assert calls == []


def test_dry_run_never_announces(monkeypatch):
    calls = _capture_notifiers(monkeypatch)
    w = GamedayWorker(dry_run=True)
    monkeypatch.setattr(w, "tick", lambda now=None: {"live": 1, "hunting": 0,
                                                      "anchor_polls": 0, "deriv_polls": 0,
                                                      "prop_polls": 0, "errors": [],
                                                      "prop_bets": 1})
    w.run(max_ticks=1, sleep_sec=0, idle_exit_ticks=None)
    assert calls == []


def test_a_notifier_that_raises_cannot_break_the_loop(monkeypatch):
    import tracking.push_notifier as pn
    import tracking.discord_notifier as dn
    seen: list = []

    def boom(target_date, dry_run):
        raise RuntimeError("discord is down")
    monkeypatch.setattr(pn, "notify_live_signals", boom)
    monkeypatch.setattr(dn, "notify_discord_live",
                        lambda target_date, dry_run: seen.append(target_date))
    w = _worker_with_tick(monkeypatch, {"live": 1, "hunting": 0, "anchor_polls": 0,
                                        "deriv_polls": 0, "prop_polls": 1,
                                        "errors": [], "prop_bets": 2})
    assert w.run(max_ticks=1, sleep_sec=0, idle_exit_ticks=None) == 1
    assert len(seen) == 1, "a push failure must not suppress the Discord post"
