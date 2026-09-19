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


def american_to_implied(price) -> float | None:
    """American price -> implied probability, or None when there is no price.
    Local rather than imported: this module stays stdlib-only so the NFL
    worker can reach it from cwd=nfl/ (see the module docstring)."""
    try:
        a = float(price)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return (-a) / ((-a) + 100.0) if a < 0 else 100.0 / (a + 100.0)


class BookMoveClock:
    """How far has the book's number moved since OUR state last changed?

    THE FAILURE THIS EXISTS FOR, measured end to end on 2026-09-19.
    Coastal Carolina at Delaware, `ncaaf_live_win_prob`:

        15:41:51Z  DraftKings live: Delaware -174, spread Delaware -3.5
        15:43:32Z  FanDuel flips to Delaware +102 / Coastal -130
        15:44:21Z  DraftKings re-hangs: Delaware +100, spread Delaware +2.5
        15:44:29   the loop WRITES BET Delaware ML +100 (model 0.659) on a
                   state that still says 0-0 in the first quarter
        15:44:44   the CFBD score feed reports the touchdown -- 15s after the
                   bet, 23s after DraftKings, 72s after FanDuel
        15:44:44+  `quote_predates_score` now declines the exact quote that
                   was just bet, because a score has finally been seen

    Every guard above passed and none was wrong to: 8s old against a 90s
    cap, edge 0.159 against a 0.18 cap, and `quote_predates_score` can only
    fire once WE have seen a score. All three protect against the book being
    behind us. This one protects against us being behind the book, which is
    the common case: the book prices the play from a courtside feed and we
    read a scoreboard endpoint every few seconds. The model's 0.659 was the
    pregame prior carried into a tied first quarter; the "edge" was a
    touchdown our feed had not reported.

    THE RULE. Per key (game and market), anchor the book's number -- an
    implied probability for a moneyline, the line for a total, spread or prop
    -- at the moment OUR state last changed. While the state stays the same,
    report how far the book has moved from that anchor; the caller declines
    past a cap. A book that reprices with no change in what we can see has
    information we do not have, and that is true whether the move is a
    touchdown, a turnover or an injury.

    SELF-CLEARING, IN THE RIGHT ORDER. When the state changes the anchor is
    dropped and the next quote that POSTDATES the change becomes the new
    one. A quote stamped before the change is not a baseline (it is the
    pre-score number `quote_predates_score` is already declining), so a
    re-hang landing after a late score report is not read as a move.

    FIRST SIGHT RECORDS AND REPORTS NOTHING, the same rule as ScoreClock: a
    game seen for the first time -- or every game after a restart -- has no
    anchor to move from. The age bound applies throughout, so this is a
    floor, not a hole. It is NOT why Delaware was bet: the loop had watched
    that game since 15:34:39 and every DraftKings publish from 15:34:22 to
    15:42:40 sat between -167 and -217 (0.626-0.685 implied), so whichever of
    them was the anchor, +100 is a move of 0.126-0.185 against a 0.08 cap.
    The guard fires on the production timeline. The control test in
    tests/test_live_book_move_guard.py bets the number at first sight to
    prove the decline test is testing the guard and not the cuts.

    A None INSIDE the state is a legitimate value, not a reason to skip: the
    CFBD scoreboard's `possession` parses defensively and can be None for a
    whole game, and a clock that refused to anchor on it would be dead for
    exactly the games it is for.

    AND A None IS NEVER A CHANGE. Measured on the first slate this ran
    (2026-09-19, North Texas at Texas State): CFBD blanks `possession` around
    every scoring play -- 'away' at 17:37:51, None at 17:38:55, then the
    touchdown. The blank READ AS A STATE CHANGE, the anchor was dropped, the
    first quote after it was DraftKings' post-touchdown -129, and the loop
    bet Texas State on that "baseline" 44 seconds before the feed reported
    the score: the Delaware failure through a side door. So a None position
    in a tuple state is filled from the last state seen for that key before
    it is compared or stored -- a field the feed stopped reporting keeps its
    last value until the feed reports a new one.

    `state` is any equatable snapshot of what the MODEL consumes and that
    changes on an event rather than every tick -- the NCAAF loop passes
    (home_score, away_score, period, possession); clock, down and distance
    would reset the anchor every play and make the guard dead code.
    """

    __slots__ = ("_state", "_anchor", "_changed_at", "_quiet_since",
                 "_last_number")

    def __init__(self) -> None:
        self._state: dict = {}
        self._anchor: dict = {}
        self._changed_at: dict = {}
        # THE SETTLED-STATE CLOCK (2026-09-19, the second fix of the day, mike:
        # "I said to fix it not pause it"). The cap above catches a LOUD move.
        # It cannot catch the quiet version of the same defect: a book that
        # has re-hung for an event 30 seconds ago, on a state feed 20-70s
        # behind it, is a book whose number is "stable" by the time we see it
        # and whose move was already inside the anchor. The only thing that
        # separates a lag from a disagreement is TIME: if the book's number
        # and our state have BOTH been unchanged for longer than the worst
        # feed lag, whatever the book knew has reached us too, and an edge
        # that survives that is a real disagreement on the same facts.
        # `_quiet_since[key]` is the later of the last state change and the
        # last book move larger than the tolerance; `quiet_seconds` is how
        # long ago that was. First sight starts the clock, so a restart
        # waits a window rather than betting blind.
        self._quiet_since: dict = {}
        self._last_number: dict = {}

    def observe(self, key, state, number, quote_ts=None,
                now: datetime | None = None,
                tolerance_sec: float = 0.0,
                move_tol: float = 0.0) -> float | None:
        """Record the book's `number` for `key` under `state`; return how far
        it has moved since the anchor, or None when there is nothing to
        compare against (first sight, a state change awaiting a post-change
        quote, or a missing state or number).

        `move_tol`: a change in `number` no larger than this is juice drift,
        not a move, for the settled-state clock (DraftKings republishes a
        moneyline every ~50s with a median 0.4-point wobble; a clock reset by
        that would never read settled)."""
        if state is None or number is None:
            return None
        now = now or datetime.now(timezone.utc)
        number = float(number)
        prev = self._state.get(key, _UNSET)
        if (prev is not _UNSET and isinstance(state, tuple)
                and isinstance(prev, tuple) and len(prev) == len(state)
                and None in state):
            state = tuple(p if s is None else s for s, p in zip(state, prev))
        last = self._last_number.get(key)
        if last is None or abs(number - last) > move_tol:
            self._quiet_since[key] = now
            self._last_number[key] = number
        if prev is _UNSET:
            self._state[key] = state
            self._anchor[key] = (state, number)
            self._quiet_since[key] = now
            return None
        if prev != state:
            self._state[key] = state
            self._changed_at[key] = now
            self._quiet_since[key] = now
            self._anchor.pop(key, None)
        anchor = self._anchor.get(key)
        if anchor is None:
            if quote_predates_score(quote_ts, self._changed_at.get(key),
                                    tolerance_sec):
                return None
            self._anchor[key] = (state, number)
            return None
        return abs(number - anchor[1])

    def quiet_seconds(self, key, now: datetime | None = None) -> float | None:
        """Seconds since the later of: first sight, the last state change,
        and the last book move past `move_tol`. None for an unseen key."""
        since = self._quiet_since.get(key)
        if since is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - since).total_seconds()
