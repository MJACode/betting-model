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
    """The twelve distributional models (ten paused, tackles + sacks live)
    have no fetch of their own — the card's `--fetch` is the only NFL prop
    odds producer. Pause does not drop the scoring step: NONE rows still
    score. If scoring is ever dropped from this tick they go dark without
    erroring, because a model with no odds simply writes no pick."""
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


# Same ten / keep-live sets as tests/test_retired_models.py. Duplicated here
# so this file still fails in isolation if the pause set drifts.
_NFL_DISTRIBUTIONAL_PAUSED = frozenset({
    "nfl_prop_pass_yards",
    "nfl_prop_pass_attempts",
    "nfl_prop_pass_completions",
    "nfl_prop_pass_tds",
    "nfl_prop_rush_yards",
    "nfl_prop_rush_attempts",
    "nfl_prop_rec_yards",
    "nfl_prop_receptions",
    "nfl_prop_rush_rec_yards",
    "nfl_prop_anytime_td",
})

_NFL_PROP_KEEP_LIVE = frozenset({
    "nfl_prop_tackles_assists",
    "nfl_prop_sacks",
    "nfl_prop_market",
})


def test_twelve_are_live_and_none_is_paused():
    """Ten distributional nfl_prop_* models are paused (2026-09-14, mike).

    KEEP LIVE: tackles_assists (clean record after the gamebook TOT fix;
    docs/nfl_prop_profitability_search.md §4), sacks (thin / paper-only;
    not in the pause list), and nfl_prop_market (rule lane, not these
    PROP_MODELS). Pause ≠ retire: NONE rows still score; cuts stay in
    ACTION_THRESHOLDS for the unpause.

    The pause is the walk-forward at real DraftKings prices
    (docs/nfl_props_model.md §5b): every market below loses, and a volume
    floor does not create an edge. The name of this test is the 2026-09-09
    empty-pause assertion it replaced — kept so the full-suite failure
    that named it still greps here.
    """
    import config

    paused = {m for m in config.PAUSED_MODELS if m.startswith("nfl_prop")}
    assert paused == _NFL_DISTRIBUTIONAL_PAUSED, (
        f"pause set changed: {sorted(paused)}"
    )
    assert len(paused) == 10

    live = {m for m in config.ACTION_THRESHOLDS
            if m.startswith("nfl_prop_")
            and m not in config.PAUSED_MODELS}
    assert live == _NFL_PROP_KEEP_LIVE, sorted(live)


def test_the_live_ten_are_not_a_clean_bill_of_health():
    """The two live distributional ids are not a clean bill of health.

    On the 2025 re-grade every interval straddled zero: the pooled number
    excluding tackles was -1.18% over 564 bets, CI (-7.7, +5.3). Ten of
    those twelve are now paused (2026-09-14). The two that stay live
    (tackles_assists, sacks) still carry the volume-control floors
    (f4bd516f), not a swept edge — so nobody reads "still live" as
    "loosened".
    """
    import config

    live = {m for m in config.ACTION_THRESHOLDS
            if m.startswith("nfl_prop_") and m not in config.PAUSED_MODELS
            and m != "nfl_prop_market"}
    assert live == {"nfl_prop_tackles_assists", "nfl_prop_sacks"}, sorted(live)
    for m in live:
        assert config.MODEL_PROB_THRESHOLDS[m] >= 0.60, (m, config.MODEL_PROB_THRESHOLDS[m])
        assert config.MODEL_EDGE_THRESHOLDS[m] >= 0.10, (m, config.MODEL_EDGE_THRESHOLDS[m])


def test_every_live_nfl_prop_model_still_carries_its_own_cut():
    """Unpausing must not smuggle a model past the per-model threshold rule --
    a live model reaching the module-level fallback is betting a cut nobody
    chose for it."""
    import config

    for m in config.ACTION_THRESHOLDS:
        if not m.startswith("nfl_prop_") or m in config.PAUSED_MODELS:
            continue
        assert m in config.MODEL_EDGE_THRESHOLDS, f"{m} has no edge cut"
        assert m in config.MODEL_PROB_THRESHOLDS, f"{m} has no prob cut"
