"""The NHL prop collector buys two pre-game snapshots a game and no more.

The refresh pass runs hourly and then every ten minutes through the evening.
The collector is safe on every pass only because `due()` answers from what is
already stored; without it a slate is bought ~20 times a day.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.ingestors import nhl_prop_odds_ingestor as ing

ROOT = Path(__file__).resolve().parents[1]
START = datetime(2026, 10, 1, 23, 10, tzinfo=timezone.utc)      # 7:10pm ET puck drop
MORNING = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)


def test_a_game_with_nothing_stored_is_owed_its_open():
    assert ing.due(START, MORNING, [], window_min=70) == "open"


def test_an_opened_game_is_owed_nothing_until_the_closing_window():
    stored = [MORNING]
    for hours in range(1, 8):                                   # every hourly pass to 21:00Z
        now = MORNING + timedelta(hours=hours)
        assert ing.due(START, now, stored, window_min=70) is None, now


def test_the_first_pass_inside_the_window_buys_the_close_and_the_next_does_not():
    stored = [MORNING]
    first_inside = START - timedelta(minutes=65)
    assert ing.due(START, first_inside, stored, window_min=70) == "close"
    stored.append(first_inside)
    for minutes in (55, 45, 35, 25, 15, 5):                     # the ten-minute evening passes
        assert ing.due(START, START - timedelta(minutes=minutes), stored, window_min=70) is None


def test_a_game_first_priced_inside_the_window_gets_one_snapshot():
    late = START - timedelta(minutes=30)
    assert ing.due(START, late, [], window_min=70) == "open"
    assert ing.due(START, late + timedelta(minutes=10), [late], window_min=70) is None


def test_nothing_is_bought_once_the_puck_has_dropped():
    assert ing.due(START, START, [], window_min=70) is None
    assert ing.due(START, START + timedelta(minutes=20), [MORNING], window_min=70) is None


def test_a_whole_day_of_passes_buys_exactly_two():
    """Hourly from 10:00Z, every ten minutes from 22:00Z, to an hour past the start."""
    stored, bought, now = [], [], datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    while now <= START + timedelta(hours=1):
        which = ing.due(START, now, stored, window_min=70)
        if which:
            bought.append(which)
            stored.append(now)
        now += timedelta(minutes=10 if now.hour >= 22 or now.day == 2 else 60)
    assert bought == ["open", "close"]


def test_the_step_is_wired_into_the_refresh_pass_sequentially():
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert "\nstep nhl-prop-odds\n" in sh
    assert "par nhl-prop-odds" not in sh                         # the session pool is sized for group 1 as it is
    rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"nhl-prop-odds": lambda: step_nhl_prop_odds()' in rp
    assert '"nhl-prop-odds"' in rp.split("choices=[", 1)[1].split("]", 1)[0]


def test_the_markets_are_the_ones_the_priced_history_holds():
    import config
    from data.ingestors.nhl_prop_odds_history import PROP_MARKETS
    assert sorted(config.PROP_MARKETS_NHL) == sorted(PROP_MARKETS)
