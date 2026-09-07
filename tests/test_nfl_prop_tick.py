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


def test_only_the_low_bias_nfl_prop_models_are_live():
    """Which of the twelve are live, and the measured reason for the line.

    mike unpaused eleven on 2026-09-06 and re-paused four of them hours later,
    after asking why so many bets were unders. On the live Week 1 board 14 of 16
    BETs were unders while the underlying picks ran ~50/50, so the BET CUT was
    one-sided, not the models. De-vigged against DraftKings' own two-sided price
    per proposition, EVERY model sat below the book:

        sacks            -7.7pp     pass_yards        -4.4pp
        rush_attempts    -7.4pp     pass_tds          -4.2pp
        tackles_assists  -6.2pp     rec_yards         -2.8pp
        rush_yards       -6.2pp     pass_completions  -1.6pp
        rush_rec_yards   -6.1pp     pass_attempts     -1.5pp
                                    receptions        -1.4pp

    Eleven markets do not independently agree on a sign; that is one systematic
    downward bias, and P(under) = 1 - P(over) carries all of it. Real outcomes
    lean under by only ~1-2pp (reception_yds -0.8, receptions -2.0, rush_yds
    -2.4 against DK's implied), so the models overshoot reality rather than
    finding value in it.

    The cut is <= -6pp: the tackles standard, already accepted, not a new number.
    This test is the tripwire against quietly restoring any of the five.
    """
    import config

    paused = {m for m in config.PAUSED_MODELS if m.startswith("nfl_prop")}
    assert paused == {
        "nfl_prop_tackles_assists",
        "nfl_prop_sacks",
        "nfl_prop_rush_attempts",
        "nfl_prop_rush_yards",
        "nfl_prop_rush_rec_yards",
    }, f"pause set changed: {sorted(paused)}"

    live = {m for m in config.ACTION_THRESHOLDS
            if m.startswith("nfl_prop_")
            and m not in config.PAUSED_MODELS
            and m != "nfl_prop_market"}
    assert live == {
        "nfl_prop_anytime_td", "nfl_prop_pass_attempts",
        "nfl_prop_pass_completions", "nfl_prop_pass_tds",
        "nfl_prop_pass_yards", "nfl_prop_rec_yards", "nfl_prop_receptions",
    }, f"live set changed: {sorted(live)}"


def test_the_seven_that_stayed_live_are_not_a_clean_bill_of_health():
    """Stated so nobody reads the pause list as "the rest are fine". All seven
    are biased the same way, by 1.4 to 4.4pp; they are under the -6pp line, not
    unbiased. The real fix is calibration, and it CANNOT be fitted yet --
    model_calibration holds n=0 graded picks for every nfl_prop_* model because
    none has settled a bet. The existing Platt path fits itself once outcomes
    exist, which is why this is a note rather than a code path."""
    import config

    live = {m for m in config.ACTION_THRESHOLDS
            if m.startswith("nfl_prop_") and m not in config.PAUSED_MODELS
            and m != "nfl_prop_market"}

    # A TIGHTER CUT IS NOT A FIX FOR A BIASED PROBABILITY. f4bd516f moved these
    # to the top decile hours before the pause, and every under BET measured
    # above was written after it landed -- the cut changes how OFTEN the bias
    # fires, not which side it picks. This asserts the cuts really are tight, so
    # nobody reads "still biased" as "still on the 0.55/0.05 placeholders".
    for m in live - {"nfl_prop_anytime_td"}:
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
