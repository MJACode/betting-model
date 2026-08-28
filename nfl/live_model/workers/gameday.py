"""
The always-on gameday worker.

    python -m live_model.workers.gameday --dry-run
    python -m live_model.workers.gameday --once

Runs the loop the build spec describes: poll ESPN for state (free), decide
which games are in a hunt state, and only then spend Odds API credits on the
markets that game's state makes worth pricing.

THE ORDER OF OPERATIONS IS THE COST CONTROL. State is free and odds are not,
so nothing is fetched until a free signal says the fetch is worth making. A
worker that polls every market for every game every minute would work exactly
as well and cost twenty times as much.

DEGRADE LOUDLY. ESPN is undocumented and has broken this repo's ingestors
twice. A feed that goes dark raises an explicit alert; it never quietly serves
stale state, because a stale state priced against a live quote is the one way
this system can lose money fast rather than slowly.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..models import pass_attempt_bias as pab
from ..recorder import JsonlRecorder
from ..state import from_extract
from ..config import (
    ANCHOR_MARKETS, DERIVATIVE_MARKETS, POLL_ANCHOR_SEC, POLL_DERIVATIVE_SEC,
    POLL_PROP_SEC, POLL_PROP_TRIGGERED_SEC, POLL_STATE_SEC, PROP_MARKETS,
)
from ..executor import Executor, is_hunt_state, script_trigger_fired
from ..feeds import espn, espn_core
from ..feeds.odds_live import CreditBudgetExceeded, CreditMeter, LiveOddsClient

log = logging.getLogger("live_model.gameday")

# Consecutive idle ticks before run() returns so the */10 supervisor cron can
# relaunch. Four ticks is roughly 40 seconds at the 10s state cadence, long
# enough that one empty feed response does not end a slate, short enough that
# the process is not parked between kickoffs.
IDLE_EXIT_TICKS = int(os.getenv("LIVE_IDLE_EXIT_TICKS", "4"))


@dataclass
class GameTracker:
    """Per game bookkeeping: when we last paid for each family of markets."""
    event_id: str
    home: str
    away: str
    last_anchor: float = 0.0
    last_deriv: float = 0.0
    last_prop: float = 0.0
    last_anchor_prob: float | None = None
    last_deriv_prob: float | None = None
    consecutive_state_failures: int = 0
    # The state a prop decision is priced against. Held on the tracker so the
    # executor's staleness guard sees the real feed timestamp rather than an
    # invented one.
    state: object | None = None
    # The EXTRACTED state dict this tick, from whichever host answered. Both
    # feed paths store the same shape here so _state_from has one input.
    payload: dict | None = None
    notes: list = field(default_factory=list)

    def due(self, kind: str, now: float, triggered: bool = False) -> bool:
        if kind == "anchor":
            return now - self.last_anchor >= POLL_ANCHOR_SEC
        if kind == "deriv":
            return now - self.last_deriv >= POLL_DERIVATIVE_SEC
        cadence = POLL_PROP_TRIGGERED_SEC if triggered else POLL_PROP_SEC
        return now - self.last_prop >= cadence


class GamedayWorker:
    def __init__(self, *, dry_run: bool = False, recorder=None, alerter=None,
                 odds_client=None, meter: CreditMeter | None = None):
        self.dry_run = dry_run
        self.meter = meter or CreditMeter()
        # BUY ONLY WHAT A DEPLOYED LANE READS. PROP_MARKETS lists nine; the
        # one surviving lane prices exactly one of them, and _price_props
        # filters the rest straight into the bin. The Odds API charges a
        # per event call per market, so asking for all nine was paying nine
        # times over for eight markets nothing scores. Derived from the lane
        # rather than written out, so adding a second lane cannot forget to
        # buy its market and a cut lane cannot keep costing money.
        self.prop_markets = tuple(dict.fromkeys([pab.MARKET]))
        self.odds = odds_client
        if self.odds is None and not dry_run:
            self.odds = LiveOddsClient(meter=self.meter)
        self.executor = Executor(recorder=recorder, alerter=alerter)
        self.trackers: dict[str, GameTracker] = {}
        self.alerter = alerter
        self._last_anchor = 0.0
        self._feed_host: str | None = None
        self._self_check_done = False

    # ------------------------------------------------------------ one pass
    def tick(self, now: float | None = None) -> dict:
        """
        One pass. Returns a summary so the caller can log or test it without
        reaching inside.
        """
        now = now or time.time()
        summary = {"live": 0, "hunting": 0, "anchor_polls": 0,
                   "deriv_polls": 0, "prop_polls": 0, "errors": []}

        try:
            live, host = espn.live_events()
        except Exception as e:                          # noqa: BLE001
            self._alert_ops(f"BOTH ESPN hosts unreachable: {e}")
            summary["errors"].append(f"feed:{e}")
            return summary

        if host != self._feed_host:
            # A host switch is worth knowing about: it means the primary path
            # changed under us, which is how the WNBA feed silently lost a week
            # of finals in August.
            if self._feed_host is not None:
                self._alert_ops(f"ESPN feed host changed {self._feed_host} to {host}")
            self._feed_host = host
        summary["host"] = host
        summary["live"] = len(live)
        seen = set()

        # The anchor fetch is SLATE WIDE: one call returns the main lines for
        # every live game. Charging it per game would multiply the largest
        # recurring cost in the system by the size of the slate, which on a
        # 1pm Sunday is a factor of nine.
        if live and not self.dry_run and (now - self._last_anchor) >= POLL_ANCHOR_SEC:
            got = self._safe_poll(lambda: self.odds.fetch_anchor(), summary,
                                  "anchor_polls")
            if got:
                self._anchor_quotes = got
            self._last_anchor = now

        for ev in live:
            eid = ev["event_id"]
            seen.add(eid)
            tr = self.trackers.setdefault(
                eid, GameTracker(eid, ev["home"], ev["away"]))

            # On the core path the event listing already carries the full
            # state, so there is no second document to fetch.
            if host == "sports.core":
                parsed = {k: v for k, v in ev.items()}
                self._run_self_check(parsed, summary)
                # WITHOUT THESE TWO LINES THE LANE CANNOT PRICE ANYTHING ON
                # CORE. _price_props returns immediately when tr.state is
                # None, so the prop poll would spend credits and discard every
                # quote, which is precisely the "fetching and discarding" the
                # poll comment says it stopped doing. core is the only host
                # that answers the Railway worker, so this was the whole lane.
                tr.payload = parsed
                tr.state = self._state_from(tr, eid)
                hunting, why = self._hunt_decision(parsed)
                if hunting:
                    summary["hunting"] += 1
                    tr.notes.append(why)
                if not self.dry_run:
                    self._poll_for(eid, hunting, why, tr, now, summary)
                continue

            try:
                summary_payload = espn.fetch_summary(eid)
            except Exception as e:                      # noqa: BLE001
                tr.consecutive_state_failures += 1
                if tr.consecutive_state_failures in (3, 10):
                    self._alert_ops(
                        f"ESPN summary failing for {ev['away']} at {ev['home']} "
                        f"({tr.consecutive_state_failures} in a row): {e}")
                summary["errors"].append(f"summary:{eid}")
                continue

            parsed = espn.extract_summary_state(summary_payload)
            if parsed is None:
                tr.consecutive_state_failures += 1
                if tr.consecutive_state_failures in (3, 10):
                    self._alert_ops(
                        f"ESPN summary shape unreadable for {eid}: a required "
                        f"field is missing. The feed has probably changed.")
                summary["errors"].append(f"unparsed:{eid}")
                continue
            tr.consecutive_state_failures = 0
            self._run_self_check(parsed, summary)
            # The EXTRACT, not the raw summary: _state_from takes one shape so
            # the two hosts cannot drift into needing different handling.
            tr.payload = parsed
            tr.state = self._state_from(tr, eid)

            hunting, why = self._hunt_decision(parsed)
            if hunting:
                summary["hunting"] += 1
                tr.notes.append(why)

            if self.dry_run:
                continue
            self._poll_for(eid, hunting, why, tr, now, summary)

        for gone in set(self.trackers) - seen:
            self.trackers.pop(gone, None)
        return summary

    def _poll_for(self, eid: str, hunting: bool, why: str, tr: "GameTracker",
                  now: float, summary: dict) -> None:
        # The derivative lane is NOT deployed, so it stays hunt gated: its
        # premise is a quote that has failed to keep up with a repriced main
        # line, which is a hunt state by definition.
        if hunting and tr.due("deriv", now):
            self._safe_poll(
                lambda: self.odds.fetch_event_markets(eid, DERIVATIVE_MARKETS),
                summary, "deriv_polls")
            tr.last_deriv = now

        # PROPS ARE POLLED CONTINUOUSLY, FIRST SNAP TO LAST, AND THE HUNT
        # STATE ONLY CHANGES THE CADENCE.
        #
        # This used to require a hunt state, which meant halftime or a ten
        # point lead in the second half. That gate deployed something other
        # than what was validated: the surviving lane is the book centring the
        # pass attempt line about 2.33 attempts low, measured across 1,682
        # quotes taken all through games on the archive's five minute grid. It
        # is a property of the whole game, not of the halftime window, so
        # sampling only at halftime tests a different population than the one
        # that passed the kill criterion, and throws away most of the quotes
        # the lane was shown to work on.
        triggered = why == "script_trigger"
        if tr.due("prop", now, triggered):
            quotes = self._safe_poll(
                lambda: self.odds.fetch_event_markets(eid, self.prop_markets),
                summary, "prop_polls")
            tr.last_prop = now
            # Fetching and discarding is what this used to do. A poll that
            # never reaches a decision costs credits and proves nothing.
            if quotes:
                self._price_props(quotes, tr, summary)

    def _state_from(self, tr: "GameTracker", eid: str):
        """
        Build the GameState this tick's prop decisions are priced against.

        The pregame spread and total are REQUIRED by from_espn and are taken
        from the slate anchor, never defaulted. from_espn's own docstring is
        explicit that a game must never be priced off defaults, and this
        session has already produced three confident wrong answers from
        exactly that class of shortcut. No anchor yet means no prop decision
        this tick, which costs a poll and nothing else.

        Returns None rather than raising: a shape change should cost the lane
        its tick, not take down the worker. The self check alerts on shape, so
        a None here is not a silent failure.
        """
        if tr.payload is None:
            return None
        spread = self._anchor_value(eid, "spreads")
        total = self._anchor_value(eid, "totals")
        if spread is None or total is None:
            return None
        try:
            return from_extract(tr.payload, game_id=eid, pregame_spread=spread,
                                pregame_total=total, wind_mph=None,
                                is_dome=False)
        except Exception as e:                          # noqa: BLE001
            log.warning("state build failed for %s: %s", eid, e)
            return None

    def _anchor_value(self, eid: str, market: str) -> float | None:
        """The slate anchor's line for this game, or None if it is not there."""
        for q in getattr(self, "_anchor_quotes", None) or []:
            if getattr(q, "game_id", None) == eid and q.market == market:
                if q.line is not None:
                    return float(q.line)
        return None

    def _price_props(self, quotes, tr: "GameTracker", summary: dict) -> None:
        """
        Run the one validated lane over this event's prop quotes.

        BOTH arms are recorded on every qualifying quote: the priced read and
        the blind "take every over". The whole finding of the validation was
        that a model free rule captured most of the edge, so a paper trade that
        records only the model's arm cannot answer the question it exists to
        answer.
        """
        state = tr.state
        if state is None:
            return
        for q in quotes:
            if q.market != pab.MARKET or q.side != "over":
                continue
            # accrued is not on the ESPN state, so the stale line guard is
            # skipped rather than faked. It fired on under 0.2% of measured
            # quotes and the too_late gate covers the case that matters.
            read = pab.over_prob(q.line, None, state.seconds_remaining)
            if read.over_prob is None:
                summary.setdefault("prop_skips", []).append(read.reason)
                continue
            for model_prob, arm in ((read.over_prob, "priced"),
                                    (pab.blind_over_prob(), "blind")):
                d = self.executor.evaluate(
                    state=state, quote=q, model_prob=model_prob,
                    model_id=pab.MODEL_ID,
                    context={"arm": arm, "lane": "pass_attempt_bias",
                             "player": q.player,
                             # PRESEASON REPS ARE NOT A TRACK RECORD. The lane
                             # is a bias measured on regular season football,
                             # and in preseason the starters play a quarter. A
                             # log that cannot tell them apart is how a
                             # plumbing test gets quoted as a result later.
                             "season_type": (tr.payload or {}).get("season_type")})
                summary["prop_decisions"] = summary.get("prop_decisions", 0) + 1
                if d.bet:
                    summary["prop_bets"] = summary.get("prop_bets", 0) + 1

    # ------------------------------------------------------- feed self check
    def _run_self_check(self, parsed: dict, summary: dict) -> None:
        """
        Validate the feed's shape against the model's assumptions, once per
        run, on the first real payload of the day.

        THIS IS WHY THE CHECK IS NOT A SCRIPT SOMEONE REMEMBERS TO RUN. ESPN
        changes shape without notice and has broken this repo's ingestors
        twice. A one-time manual blessing goes stale the moment it passes, and
        the failure it is meant to catch is silent: a feed that returns a
        plausible looking payload with one field renamed prices every game off
        a default. Running it in the worker means a shape change surfaces as an
        alert on the first poll of the day instead of as a quiet losing Sunday.
        """
        if self._self_check_done:
            return
        self._self_check_done = True
        problems = check_feed_assumptions(parsed)
        if problems:
            summary["errors"].append("feed_assumptions")
            self._alert_ops(
                "ESPN feed assumptions BROKEN, live pricing is not safe: "
                + "; ".join(problems))
        else:
            log.info("feed self check passed on host %s", self._feed_host)

    def _hunt_decision(self, parsed: dict) -> tuple[bool, str]:
        """
        Hunt-state decision from the parsed ESPN payload alone.

        Deliberately does not build a full GameState: this runs before any
        credit is spent, and the three entry conditions (halftime, a lagging
        derivative, a script change) need only the score and the clock.
        """
        period = parsed.get("period") or 0
        clock = parsed.get("clock_seconds")
        diff = abs((parsed.get("home_score") or 0) - (parsed.get("away_score") or 0))
        if period == 2 and clock is not None and clock <= 0:
            return True, "halftime"
        if period >= 3 and diff >= 10:
            return True, "script_trigger"
        return False, "no_hunt_state"

    def _safe_poll(self, fn, summary: dict, counter: str):
        try:
            out = fn()
            summary[counter] += 1
            return out
        except CreditBudgetExceeded as e:
            # Not an error: the cap did its job. Alert once so it is visible
            # that the day stopped early rather than silently going quiet.
            self._alert_ops(f"live credit cap reached: {e}")
            summary["errors"].append("credit_cap")
        except Exception as e:                          # noqa: BLE001
            log.exception("odds poll failed")
            summary["errors"].append(f"odds:{e}")
        return None

    def _alert_ops(self, message: str) -> None:
        log.error(message)
        if self.alerter:
            try:
                self.alerter({"ops": message})
            except Exception:                           # noqa: BLE001
                log.exception("ops alerter failed")

    # ------------------------------------------------------------ the loop
    def run(self, max_ticks: int | None = None, sleep_sec: int = POLL_STATE_SEC,
            idle_exit_ticks: int | None = IDLE_EXIT_TICKS):
        """
        Poll until the slate is over, then exit so the supervisor can relaunch.

        THE EXIT IS THE POINT, not a nicety. The scheduler runs this every ten
        minutes with max_instances=1, which makes ticks during a live slate
        no-ops and relaunches after the process ends. A run() that never
        returned would turn that cron into a launch-once: the first process
        would hold the slot forever, and a wedged socket would cost the whole
        season instead of one ten minute gap, with no relaunch and no alert.

        Idle means the feed reports no game in progress and none being hunted.
        A feed outage reads as idle on purpose: exiting hands the next attempt
        a fresh process, session and DNS, which is the cheapest useful response
        to a host that has stopped answering.
        """
        ticks = 0
        idle = 0
        while max_ticks is None or ticks < max_ticks:
            started = time.time()
            summary = self.tick(started)
            # states= and dec= are here because without them a quiet tick is
            # unreadable: a hunt that buys a prop card and records nothing
            # could be a missing anchor, an unbuildable state, or a card with
            # no qualifying quote, and those want three different fixes.
            log.info("tick live=%d hunting=%d states=%d polls a/d/p=%d/%d/%d "
                     "dec=%d bets=%d skips=%s credits=%d",
                     summary["live"], summary["hunting"],
                     sum(1 for t in self.trackers.values() if t.state is not None),
                     summary["anchor_polls"], summary["deriv_polls"],
                     summary["prop_polls"],
                     summary.get("prop_decisions", 0),
                     summary.get("prop_bets", 0),
                     ",".join(sorted(set(summary.get("prop_skips", [])))) or "-",
                     self.meter.spent)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break

            idle = 0 if (summary["live"] or summary["hunting"]) else idle + 1
            if idle_exit_ticks and idle >= idle_exit_ticks:
                log.info("no live or hunted game for %d ticks, exiting for the "
                         "supervisor to relaunch", idle)
                break

            time.sleep(max(0.0, sleep_sec - (time.time() - started)))
        return ticks


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LIVE_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="poll ESPN and report hunt states, spend no credits")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--ticks", type=int, default=None)
    args = ap.parse_args()

    # A dry run spends nothing and reaches no decision, so it gets no
    # recorder: an empty audit log is honest, a log of nothing labelled as a
    # slate is not.
    recorder = None if args.dry_run else JsonlRecorder()
    worker = GamedayWorker(dry_run=args.dry_run, recorder=recorder)
    if recorder is not None:
        log.info("recording decisions to %s", recorder.path)
    if args.once:
        print(worker.tick())
        if recorder is not None:
            log.info("%d decision(s) recorded", len(recorder.read_back()))
        return
    worker.run(max_ticks=args.ticks)


def check_feed_assumptions(parsed: dict) -> list[str]:
    """
    The assumptions the engine relies on, checked against one real payload.

    Returns a list of human readable problems, empty when everything holds.
    Shared by the worker's startup self check and by verify_espn.py, so the two
    can never disagree about what "the feed is fine" means.
    """
    problems = []
    period = parsed.get("period")
    if not isinstance(period, int) or not 1 <= period <= 6:
        problems.append(f"period out of range: {period!r}")

    clock = parsed.get("clock_seconds")
    if not isinstance(clock, int) or not 0 <= clock <= 1200:
        problems.append(f"clock not seconds in a period: {clock!r}")

    for side in ("home_score", "away_score"):
        v = parsed.get(side)
        if not isinstance(v, int) or not 0 <= v <= 120:
            problems.append(f"{side} implausible: {v!r}")

    poss = parsed.get("possession")
    if poss not in (None, "home", "away"):
        problems.append(f"possession not resolved to a side: {poss!r}")

    yl = parsed.get("yardline_100")
    if yl is not None and not (0 <= yl <= 100):
        problems.append(f"yardline_100 out of range: {yl!r}")

    for side in ("home_timeouts", "away_timeouts"):
        v = parsed.get(side)
        if v is not None and not 0 <= v <= 3:
            problems.append(f"{side} out of range: {v!r}")

    down = parsed.get("down")
    if down is not None and not 1 <= down <= 4:
        problems.append(f"down out of range: {down!r}")
    return problems


if __name__ == "__main__":
    main()
