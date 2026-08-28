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

from ..config import (
    ANCHOR_MARKETS, DERIVATIVE_MARKETS, POLL_ANCHOR_SEC, POLL_DERIVATIVE_SEC,
    POLL_PROP_SEC, POLL_PROP_TRIGGERED_SEC, POLL_STATE_SEC, PROP_MARKETS,
)
from ..executor import Executor, is_hunt_state, script_trigger_fired
from ..feeds import espn, espn_core
from ..feeds.odds_live import CreditBudgetExceeded, CreditMeter, LiveOddsClient

log = logging.getLogger("live_model.gameday")


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
            self._safe_poll(lambda: self.odds.fetch_anchor(), summary,
                            "anchor_polls")
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
        if hunting and tr.due("deriv", now):
            self._safe_poll(
                lambda: self.odds.fetch_event_markets(eid, DERIVATIVE_MARKETS),
                summary, "deriv_polls")
            tr.last_deriv = now
        triggered = why == "script_trigger"
        if hunting and tr.due("prop", now, triggered):
            self._safe_poll(
                lambda: self.odds.fetch_event_markets(eid, PROP_MARKETS),
                summary, "prop_polls")
            tr.last_prop = now

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

    def _safe_poll(self, fn, summary: dict, counter: str) -> None:
        try:
            fn()
            summary[counter] += 1
        except CreditBudgetExceeded as e:
            # Not an error: the cap did its job. Alert once so it is visible
            # that the day stopped early rather than silently going quiet.
            self._alert_ops(f"live credit cap reached: {e}")
            summary["errors"].append("credit_cap")
        except Exception as e:                          # noqa: BLE001
            log.exception("odds poll failed")
            summary["errors"].append(f"odds:{e}")

    def _alert_ops(self, message: str) -> None:
        log.error(message)
        if self.alerter:
            try:
                self.alerter({"ops": message})
            except Exception:                           # noqa: BLE001
                log.exception("ops alerter failed")

    # ------------------------------------------------------------ the loop
    def run(self, max_ticks: int | None = None, sleep_sec: int = POLL_STATE_SEC):
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            started = time.time()
            summary = self.tick(started)
            log.info("tick live=%d hunting=%d polls a/d/p=%d/%d/%d credits=%d",
                     summary["live"], summary["hunting"],
                     summary["anchor_polls"], summary["deriv_polls"],
                     summary["prop_polls"], self.meter.spent)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            time.sleep(max(0.0, sleep_sec - (time.time() - started)))


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

    worker = GamedayWorker(dry_run=args.dry_run)
    if args.once:
        print(worker.tick())
        return
    worker.run(max_ticks=args.ticks)


if __name__ == "__main__":
    main()


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
