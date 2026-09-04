"""Is a live book price safe to DECIDE on, given what we already know?

Sport-agnostic on purpose (CLAUDE.md 1b): NCAAF, NFL and MLB all price against
an in-play book quote, so the staleness question is asked three times and must
not have three answers. `data/ingestors/live_price_log.py` is the shape this
follows -- stdlib only, no platform imports, so a standalone loop can use it.

IT LIVES UNDER `data/`, NOT `models/`, AND THAT IS LOAD-BEARING. `nfl/` carries
its own `models/` directory and runs with cwd=nfl/, so a bare `from models.x`
there resolves to the wrong package or none at all -- pinned by
`tests/test_nfl_model_imports.py`, which this helper tripped on its first
attempt. `data/` is the namespace the NFL worker already bootstraps into for
`data.ingestors.nfl_live_price_log`, so putting the guard beside it is the one
placement all three sports can reach.

THE FAILURE THIS EXISTS FOR, measured end to end on 2026-09-03.
Akron @ Wake Forest, `ncaaf_live_total`:

    23:51:42Z  DraftKings publishes its live total at 44.5, Over -105
    ~23:52:2xZ Wake Forest scores a touchdown (ESPN drive wallclock)
    23:52:43.6 the loop SEES the score and collapses the odds cadence to its
               3s floor -- POLL_ODDS_TRIGGER_SEC working exactly as designed
    23:52:44.2 we price the NEW score against DraftKings' OLD 44.5 and post
               Over 44.5 at -105, edge +15.77%
    23:53:21Z  DraftKings re-hangs the total at 50.5. The edge never existed.

Both existing guards passed it, and neither was wrong to:

  * the quote was 62.2s old at the book, inside LIVE_QUOTE_MAX_AGE_SEC (90)
  * the edge was 0.1577, inside MAX_EDGE_CAP (0.18)

Because both are CLOCK-relative. A 62-second-old quote is a perfectly good
price in a quiet game and a fiction 14 seconds after a touchdown, and no bound
on its AGE can tell those apart. The missing measure is EVENT-relative: the
book's own publish clock versus the moment the score changed.

Note the sharp edge here -- the score trigger did not merely fail to prevent
this, it CAUSED it. Pulling odds within 0.6s of seeing a score is the fastest
possible way to read a price the book has not yet corrected. "The cached price
is most wrong" is the reason not to bet it, not the reason to bet it sooner.
The trigger is still right (it is how we see the re-hang quickly); what was
missing is the refusal to decide in the gap.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def parse_book_ts(ts) -> datetime | None:
    """The book's own `last_update`, as an aware UTC datetime.

    None means we cannot tell -- absent, wrong type, or unparseable. Callers
    treat that as NOT stale, deliberately and in line with the existing
    `quote_age_seconds` contract: a feed shape change must never silently blank
    the board. It is logged instead, so the blindness is visible.
    """
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if not isinstance(ts, str):
        return None
    try:
        pub = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return pub if pub.tzinfo else pub.replace(tzinfo=timezone.utc)


def quote_predates_score(quote_ts, score_seen_at,
                         tolerance_sec: float = 0.0) -> bool:
    """True when the book has NOT republished since the score changed.

    `score_seen_at` is when OUR state feed first showed the new score, not when
    the play happened -- we cannot know the latter, and our observation is
    necessarily at or after it. That asymmetry is the safe one: it widens the
    blocked window slightly rather than narrowing it.

    TOLERANCE DEFAULTS TO ZERO, and the cost of that is real and accepted. When
    DraftKings reprices faster than the score feed reports (measured here: the
    book re-hung 37.6s after we saw the score, but the play itself was ~14s
    before that), a genuinely post-score quote can be declined until the book
    publishes again. The alternative is worse: any tolerance big enough to fix
    that -- 10s or more -- is also big enough to admit a number the book
    stamped seconds BEFORE a touchdown, which is the exact bug this closes.
    Left as a knob so it can be moved on measurement rather than on argument.

    Unknown on either side is NOT stale (see `parse_book_ts`).
    """
    if score_seen_at is None:
        return False
    pub = parse_book_ts(quote_ts)
    if pub is None:
        return False
    seen = parse_book_ts(score_seen_at)
    if seen is None:
        return False
    return (seen - pub).total_seconds() > tolerance_sec


class ScoreClock:
    """When did each game's score last change, by our own clock?

    Keyed by whatever the caller already uses for a game (game_id, or the
    loop's resolved key). Per game rather than per pass: the NCAAF loop's
    pass-level `scores_moved` is CFBD-only, and the ESPN fallback path resolves
    scores per game AFTER that point -- hanging the guard on the pass-level
    bool would leave the fallback unguarded.

    A game seen for the FIRST TIME records its score and reports no event, the
    same rule `scores_moved` already applies: first sight has no prior price to
    be stale against, and treating it as a score would decline every market at
    kickoff.

    A restart re-enters first-sight for every game, so the guard is blind until
    each game's next score. That is a deliberate floor, not an oversight: the
    90s age cap still applies throughout, which is exactly the protection that
    existed before this class.
    """

    __slots__ = ("_score", "_changed_at")

    def __init__(self) -> None:
        self._score: dict = {}
        self._changed_at: dict = {}

    def observe(self, key, score, now: datetime | None = None):
        """Record `score` for `key`; return when it last changed, or None.

        `score` is any equatable snapshot of the scoreboard -- the NCAAF loop
        passes (home_score, away_score). A None score is ignored rather than
        recorded, so a feed that drops the field for one pass does not read as
        a change when it comes back.
        """
        if score is None or (isinstance(score, tuple) and None in score):
            return self._changed_at.get(key)
        now = now or datetime.now(timezone.utc)
        prev = self._score.get(key, _UNSET)
        if prev is _UNSET:
            self._score[key] = score
            return None
        if prev != score:
            self._score[key] = score
            self._changed_at[key] = now
        return self._changed_at.get(key)

    def last_change(self, key):
        return self._changed_at.get(key)


class _Unset:
    __slots__ = ()


_UNSET = _Unset()
