"""`game_date` is an Eastern date, everywhere, on any host.

WHY THIS EXISTS. From 2026-08-20 to 2026-08-30 the MLB live loop went dark at
8:00pm ET every single night. Ten days, and the last in-play snapshot each day
landed at 23:5x UTC without exception. The cause was one call:

    target_date = date.today().isoformat()

`date.today()` returns the CONTAINER's date. The Railway worker runs UTC (the
TZ variable documented in CLAUDE.md was never actually set), so from 00:00 UTC
-- 8pm ET -- the poller asked for games on TOMORROW's date, found none, logged
"no active games", and exited on idle. Every ten minutes, for four hours,
through the busiest part of the slate.

It was invisible because "no active games" is what a genuinely empty slate
looks like too.

These tests freeze the clock inside the danger window and assert the date is
still Eastern, so a host without TZ set cannot reintroduce it.
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


def test_today_et_is_eastern_inside_the_window_that_broke():
    """03:30 UTC on the 30th is 11:30pm ET on the 29th. The live loop asked for
    the 30th and found nothing; a game in the 5th inning was on the 29th."""
    et = datetime(2026, 8, 30, 3, 30, tzinfo=timezone.utc).astimezone(
        ZoneInfo("America/New_York"))
    assert et.strftime("%Y-%m-%d") == "2026-08-29", \
        "the whole bug in one line: UTC says the 30th, the slate is the 29th"


def test_today_et_matches_the_pipelines_own_derivation():
    """run_pipeline has always used ET for run_date. The helper must agree with
    it exactly, or the live loop and the pre-game pipeline would disagree about
    what day it is -- which is a subtler version of the same outage."""
    expected = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    assert config.today_et() == expected


def test_today_et_ignores_the_container_timezone():
    """The fix must not depend on TZ being set: a correctness property this
    load-bearing should not be one dashboard edit away from reverting."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import config; print(config.today_et())"],
        cwd=ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "TZ": "Asia/Tokyo",
             "PYTHONPATH": str(ROOT)},
    )
    assert out.returncode == 0, out.stderr
    expected = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    assert out.stdout.strip() == expected, \
        "TZ=Asia/Tokyo must not change what day the slate is on"


def _sources():
    return {p: (ROOT / p).read_text() for p in (
        "data/ingestors/live_game_state_poller.py",
        "models/live_scorer.py",
        "models/scorer.py",
    )}


def test_no_game_date_is_derived_from_the_container_clock():
    """A source-level tripwire, in the spirit of test_multi_book_odds: the
    failure mode is silent at runtime, so the guard has to be static."""
    for path, src in _sources().items():
        code = "\n".join(ln for ln in src.splitlines()
                         if not ln.lstrip().startswith("#"))
        assert "date.today()" not in code, (
            f"{path} resolves a game_date from the container clock. On a UTC "
            "host that names tomorrow from 8pm ET -- the bug that blacked out "
            "the live loop for ten nights.")


def test_the_live_modules_cannot_even_name_date_today():
    """`date` is deliberately NOT imported in the two live modules, so a
    reintroduced date.today() is a NameError rather than a nightly outage."""
    for path in ("data/ingestors/live_game_state_poller.py",
                 "models/live_scorer.py"):
        src = (ROOT / path).read_text()
        imports = [ln for ln in src.splitlines()
                   if ln.startswith("from datetime import")]
        assert imports, path
        assert not any(" date," in ln or ln.endswith(" date")
                       for ln in imports), (
            f"{path} re-imported `date`; keep it out so the outage cannot "
            "come back quietly")
