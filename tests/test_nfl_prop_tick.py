"""The NFL prop tick: how far out it runs, and what it prices when it does.

Two properties, both of which were broken or nearly broken on 2026-09-06.

THE WINDOW. `NFL_PROP_WINDOW_HOURS` was 30, so the tick returned free until
T-30h. Week 1's first kickoff was 2026-09-10T00:20Z and the job would not have
run until 2026-09-08T18:20Z — the reason no NFL prop pick existed for Week 1
while the wind and opener cards, which watch a 10-day horizon, had been firing
for days. mike widened it to match them.

THE `--days` COUPLING. The tick passed a hardcoded `--days 2`, tuned to the old
30h window. Widening the window alone would have left the job running hourly
for ten days while still only fetching and pricing the next 48 hours: a change
that looks applied, costs the credits, and quietly does a fraction of the work.
The two numbers are now derived from one.
"""

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import scheduler  # noqa: E402


def test_the_window_reaches_at_least_the_ten_day_horizon_the_other_nfl_jobs_use():
    """Props must not start later than the wind/opener cards they share a slate
    with. 30h did, which is what this pins."""
    assert scheduler.NFL_PROP_WINDOW_HOURS >= scheduler.NFL_POLL_HORIZON_DAYS * 24


def test_days_is_derived_from_the_window_not_pinned():
    """The property, stated as arithmetic rather than as the literal 10: a
    window change must move --days with it or the fetch silently under-covers."""
    for window in (30.0, 48.0, 240.0, 336.0):
        days = max(2, math.ceil(window / 24))
        assert days * 24 >= window, f"--days {days} does not cover a {window}h window"


def test_the_tick_passes_a_days_that_covers_the_whole_window(monkeypatch):
    """End to end through the real function: whatever the window is set to, the
    argv handed to the card must cover it."""
    calls = []
    monkeypatch.setattr(scheduler, "_nfl_lead_hours", lambda: 100.0)
    monkeypatch.setattr(scheduler, "_run", lambda argv, label: calls.append((argv, label)))
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: None)

    scheduler.run_nfl_prop_card()

    card = next(a for a, _ in calls if "scripts.nfl_prop_market_card" in a)
    days = int(card[card.index("--days") + 1])
    assert days * 24 >= scheduler.NFL_PROP_WINDOW_HOURS
    assert "--fetch" in card and "--publish" in card


def test_the_tick_returns_free_outside_the_window(monkeypatch):
    """The cheap half of the contract: most of the year this must spend nothing."""
    calls = []
    monkeypatch.setattr(scheduler, "_nfl_lead_hours",
                        lambda: scheduler.NFL_PROP_WINDOW_HOURS + 1)
    monkeypatch.setattr(scheduler, "_run", lambda argv, label: calls.append(label))
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: calls.append(label))

    scheduler.run_nfl_prop_card()
    assert calls == []


def test_the_twelve_distributional_models_score_off_the_ticks_own_fetch(monkeypatch):
    """The unpaused twelve have no fetch of their own — the card's `--fetch` is
    the only NFL prop odds producer. If the scoring step is ever dropped from
    this tick they go dark without erroring, because a model with no odds
    simply writes no pick."""
    calls = []
    monkeypatch.setattr(scheduler, "_nfl_lead_hours", lambda: 100.0)
    monkeypatch.setattr(scheduler, "_run", lambda argv, label: calls.append((argv, label)))
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: None)

    scheduler.run_nfl_prop_card()

    labels = [l for _, l in calls]
    assert "nfl-prop-card" in labels
    assert "nfl-prop-scoring" in labels
    # Order matters: the scorer reads what the fetch just wrote.
    assert labels.index("nfl-prop-card") < labels.index("nfl-prop-scoring")

