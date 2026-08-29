"""
NCAAF live gameday loop - run on Matt's machine during a slate.

    python -m ncaaf_live.gameday              # the real thing
    python -m ncaaf_live.gameday --dry-run    # price and log, write nothing
    python -m ncaaf_live.gameday --once       # one pass then exit

What one pass does:
  1. ESPN scoreboard (site.api, free) -> which games are live
  2. per live game: ESPN summary (free) -> state; first payload of the day
     runs check_feed_assumptions and a FAILED CHECK STOPS PRICING - a payload
     that parses plausibly with one renamed field prices every game off
     defaults, which is worse than pricing nothing
  3. one debounced bulk in-play odds fetch on its OWN cadence - state is free
     and polled fast, odds are metered and polled slower (session-capped)
  4. LiveEngine.price() per game - the lane licenses live in serve.py
  5. picks written to the platform DB under the first-signal lock: a lane's
     FIRST live BET is the bet of record (locked - never re-priced or
     deleted; it is what settles). Unlocked lanes are delete-and-replaced
     each pass, the MLB live convention. BET/AVOID only, never NONE.

Identity: ESPN team `location` == CFBD school name (verified on the live
scoreboard), matched through the platform's accent-folding resolver. The Odds
API names go through the same resolver the pregame ingestor uses, so this
loop cannot disagree with the platform about which game is which.

Exits when no game has been live for ~30 minutes and none starts within the
lookahead - safe to start early and forget.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from ncaaf_live.feeds.cfbd_scoreboard import (  # noqa: E402
    extract_live_states_cfbd, fetch_scoreboard_cfbd, fetch_team_ids)
from ncaaf_live.feeds.espn import (  # noqa: E402
    check_feed_assumptions, extract_live_events, extract_summary_state,
    fetch_scoreboard, fetch_summary)
from ncaaf_live.config import (  # noqa: E402
    POLL_ODDS_SEC, POLL_STATE_SEC, SUMMARY_FETCH_WORKERS)
from ncaaf_live.feeds.odds_live import LiveOddsFeed, parse_event_odds  # noqa: E402
from ncaaf_live.serve import GameContext, LiveEngine  # noqa: E402

log = logging.getLogger("ncaaf_live.gameday")

# Cadence lives in config.py (POLL_STATE_SEC / POLL_ODDS_SEC), which is what
# lets #267's reasoning stay true while the two feeds move independently:
# ESPN/CFBD scoreboard reads are FREE, so polling state fast is pure reaction
# time - at 45s a scoring drive could move the live total before the loop
# looked again, and the pick we publish is the one standing at that moment.
#
# #267 noted that tightening the poll could not raise Odds API spend, because
# the priced bulk call debounced on its own fixed 60s clock. That is still the
# shape - the two clocks are separate - but the odds clock is now SETTABLE
# rather than hard-coded, so it is a spend decision and is sized as one: see
# the credit-cap and staleness notes in config.py. Setting
# NCAAF_LIVE_POLL_ODDS_SEC=60 restores exactly #267's behaviour.
IDLE_EXIT_MINUTES = 30
LIVE_MODEL_IDS = ("ncaaf_live_win_prob", "ncaaf_live_total")


def _fold(v: str) -> str:
    import unicodedata
    v = unicodedata.normalize("NFD", (v or "").strip().lower())
    return "".join(ch for ch in v if ch.isalnum() or ch == " ").replace("  ", " ")


def load_context(conn=None, date: str | None = None) -> dict[tuple[str, str], GameContext]:
    """
    Today's (ET) NCAAF games from the platform: identity, pregame DK lines
    (latest PRE-KICKOFF snapshot - the post-start 'open' rows are the session
    106 leak and are excluded by timestamp), weather, dome flag.
    """
    from data.db import get_connection

    owned = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.home_team, g.away_team, g.commence_time,
                   g.game_date,
                   sp.spread_home, tl.total_line,
                   w.wind_mph, COALESCE(v.dome, 0)
            FROM games g
            LEFT JOIN ncaaf_venues v ON v.venue_id = g.venue_id
            LEFT JOIN game_weather w ON w.game_id = g.game_id
            LEFT JOIN LATERAL (
                SELECT o.spread_home FROM odds o
                WHERE o.game_id = g.game_id AND o.market = 'spreads'
                  AND o.bookmaker = 'draftkings'
                  AND o.spread_home IS NOT NULL
                  AND o.snapshot_type != 'in_play'
                  AND o.snapshot_at <= g.commence_time
                ORDER BY o.snapshot_at DESC LIMIT 1
            ) sp ON TRUE
            LEFT JOIN LATERAL (
                SELECT o.total_line FROM odds o
                WHERE o.game_id = g.game_id AND o.market = 'totals'
                  AND o.bookmaker = 'draftkings'
                  AND o.total_line IS NOT NULL
                  AND o.snapshot_type != 'in_play'
                  AND o.snapshot_at <= g.commence_time
                ORDER BY o.snapshot_at DESC LIMIT 1
            ) tl ON TRUE
            WHERE g.sport = 'NCAAF'
              AND g.game_date = %(d)s
        """, {"d": date or datetime.now(
            ZoneInfo("America/New_York")).date().isoformat()}).fetchall()
    finally:
        if owned:
            conn.close()

    out = {}
    for gid, home, away, ct, gd, sp, tl, wind, dome in rows:
        ctx = GameContext(
            game_id=gid, home=home, away=away, commence_time=ct,
            pregame_spread=None if sp is None else float(sp),
            pregame_total=None if tl is None else float(tl),
            wind_mph=None if wind is None else float(wind),
            is_dome=bool(dome), game_date=gd)
        out[(_fold(home), _fold(away))] = ctx
    log.info("context: %d platform games today, %d with a pregame total",
             len(out), sum(1 for c in out.values() if c.pregame_total is not None))
    return out


def load_known_schools() -> set[str]:
    """The platform's ncaaf_teams schools - the mascot-strip vocabulary."""
    from data.db import get_connection
    conn = get_connection()
    try:
        return {r[0] for r in conn.execute(
            "SELECT school FROM ncaaf_teams").fetchall()}
    except Exception:                                # noqa: BLE001
        return set()
    finally:
        conn.close()


def resolve_odds_teams(odds_by_pair: dict) -> dict[tuple[str, str], dict]:
    """The Odds API names -> folded school pairs, via the platform resolver."""
    from data.ingestors.cfbd_ingestor import resolve_odds_api_school
    out = {}
    for (home, away), rec in odds_by_pair.items():
        try:
            h = resolve_odds_api_school(home)
            a = resolve_odds_api_school(away)
        except Exception:                            # noqa: BLE001
            continue
        if h and a:
            out[(_fold(h), _fold(a))] = rec
    return out


def resolve_live_states(live: list[dict], ctx_map: dict, use_cfbd: bool,
                       cfbd_states: dict, workers: int = SUMMARY_FETCH_WORKERS
                       ) -> list[tuple[dict, tuple, GameContext, dict | None]]:
    """(event, key, ctx, state) for every live game the platform knows about.

    Games with no platform row are dropped FIRST, so an unknown matchup never
    costs a fetch.

    ESPN needs one summary call per game, and doing them one at a time is what
    put the cadence out of reach on a real slate: 20 games x (~0.3s round trip
    + the old 0.2s politeness gap) spent ~10s of a 10s budget before any
    pricing happened. They are independent GETs against a stateless helper, so
    a small pool collapses the fan-out to roughly one round trip. CFBD already
    has every game's state from its single scoreboard call and does no
    per-game work at all.
    """
    pairs = []
    for ev in live:
        key = (_fold(ev.get("home_location") or ""),
               _fold(ev.get("away_location") or ""))
        ctx = ctx_map.get(key)
        if ctx is None:
            log.debug("no platform game for %s @ %s - skipping",
                      ev.get("away_location"), ev.get("home_location"))
            continue
        pairs.append((ev, key, ctx))

    if use_cfbd:
        return [(ev, key, ctx, cfbd_states.get(key)) for ev, key, ctx in pairs]
    if not pairs:
        return []

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pairs)))) as pool:
        summaries = list(pool.map(
            lambda p: fetch_summary(p[0]["event_id"]), pairs))
    return [(ev, key, ctx, extract_summary_state(sm) if sm else None)
            for (ev, key, ctx), sm in zip(pairs, summaries)]


def write_picks(picks: list[dict], game_id: str, dry_run: bool) -> None:
    """Write one game's live picks under the first-signal lock
    (config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL).

    A lane (model_id) with an unsettled live BET is LOCKED: the first BET is
    the bet of record at its line and price. Locked lanes are excluded from
    the per-pass delete AND from new inserts, so the locked row survives lane
    closes (totals shuts in Q4, OT declines everything) and settles into the
    model record. Unlocked lanes keep the delete-and-replace churn (MLB live
    convention)."""
    from config import LOCK_LIVE_PICKS_AT_FIRST_SIGNAL
    from data.db import get_connection
    from models.scorer import _insert_picks, _locked_live_lanes

    if dry_run:
        for p in picks:
            log.info("[dry-run] %s %s %s p=%.3f edge=%+.3f DK=%s",
                     p["signal_type"], p["model_id"], p["pick_label"],
                     p["model_probability"], p["edge"], p["dk_odds"])
        return
    conn = get_connection()
    try:
        locked = (_locked_live_lanes(conn, game_id, LIVE_MODEL_IDS)
                  if LOCK_LIVE_PICKS_AT_FIRST_SIGNAL else set())
        unlocked = tuple(m for m in LIVE_MODEL_IDS if m not in locked)
        if unlocked:
            conn.execute("""
                DELETE FROM picks
                WHERE game_id = %(g)s AND result IS NULL AND is_live = TRUE
                  AND model_id IN %(m)s
            """, {"g": game_id, "m": unlocked})
        writable = [p for p in picks if p["model_id"] not in locked]
        if writable:
            _insert_picks(conn, writable)
        conn.commit()
        for p in writable:
            log.info("WROTE %s %s %s p=%.3f edge=%+.3f DK=%s",
                     p["signal_type"], p["model_id"], p["pick_label"],
                     p["model_probability"], p["edge"], p["dk_odds"])
        for p in picks:
            if p["model_id"] in locked:
                log.info("SKIPPED %s %s — lane locked at first BET signal "
                         "(bet of record stands)", p["model_id"], p["pick_label"])
    finally:
        conn.close()

    # Notify. This worker writes picks the app can see, but until now nothing
    # told anyone about them -- models/live_scorer.py (the MLB/in-play loop) has
    # this hook and this one never got it, so every NCAAF live BET reached the
    # app and NOTHING else. push_sent had zero 'discord_live' rows, ever.
    #
    # Both notifiers dedupe per (game, model, side) through that ledger, so
    # calling them on every pass is safe at any cadence: a signal posts once and the
    # delete-and-replace above cannot make it post again as the line moves.
    #
    # `or locked` is load-bearing, not belt-and-braces. Gating purely on "this
    # pass produced a BET" was correct before the first-signal lock and became a
    # hole after it: a LOCKED lane is a standing bet of record, but the engine
    # re-prices from scratch every pass and may stop emitting a BET on that side
    # as the live number moves. If the notifier had not yet succeeded by then --
    # a webhook added mid-game, a 5xx, or the KeyError that meant it had NEVER
    # succeeded for anyone -- the bet of record would sit unposted for the rest
    # of the game with no further attempt. A locked lane means there IS a
    # standing BET, so keep asking; the ledger makes the extra calls no-ops.
    #
    # Separate try blocks, and neither may break the loop: a broken webhook must
    # not suppress the mobile push, or vice versa, and a notifier must never
    # take down pricing.
    if picks and (locked or any(p.get("signal_type") == "BET" for p in picks)):
        target_date = picks[0].get("game_date")
        try:
            from tracking.push_notifier import notify_live_signals
            notify_live_signals(target_date=target_date, dry_run=False)
        except Exception as exc:                     # noqa: BLE001
            log.error("Live signal push failed (non-fatal): %s", exc)
        try:
            from tracking.discord_notifier import notify_discord_live
            notify_discord_live(target_date=target_date, dry_run=False)
        except Exception as exc:                     # noqa: BLE001
            log.error("Live signal Discord post failed (non-fatal): %s", exc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--date", default=None,
                    help="override the ET slate date (testing before gameday)")
    ap.add_argument("--interval", type=float, default=POLL_STATE_SEC,
                    help=f"seconds between state polls (default "
                         f"{POLL_STATE_SEC}; env NCAAF_LIVE_POLL_STATE_SEC)")
    ap.add_argument("--odds-interval", type=float, default=POLL_ODDS_SEC,
                    help=f"minimum seconds between METERED odds fetches "
                         f"(default {POLL_ODDS_SEC}; env "
                         f"NCAAF_LIVE_POLL_ODDS_SEC). Independent of "
                         f"--interval: state is free, odds are billed")
    ap.add_argument("--source", choices=["auto", "espn", "cfbd"], default="auto",
                    help="live-state source. auto = ESPN site.api first, flip "
                         "to CFBD /scoreboard when it fails (site.api is "
                         "403-blocked from the Railway worker)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    log.info("cadence: state every %.0fs, odds every %.0fs (>= 1 game live)",
             a.interval, a.odds_interval)

    # A pick is a pick. Before LOCK_LIVE_PICKS_AT_FIRST_SIGNAL existed, this
    # loop delete-and-replaced its picks every pass, so a bet given at one
    # number was silently displaced by a later one at a different number. The
    # audit log kept both; restore the first as the bet of record before pricing
    # anything. Idempotent and a no-op once the lock has covered a whole game,
    # so it stays in the startup path rather than being a one-off script.
    if not a.dry_run:
        try:
            from tracking.first_signal_repair import restore_first_signals
            restore_first_signals(
                game_date=a.date, models=tuple(LIVE_MODEL_IDS))
        except Exception as exc:                     # noqa: BLE001
            log.error("first-signal repair failed (non-fatal): %s", exc)

    engine = LiveEngine()
    odds_feed = LiveOddsFeed()
    ctx_map = load_context(date=a.date)
    feed_blessed = False
    last_live = datetime.now(timezone.utc)
    decisions = 0
    use_cfbd = a.source == "cfbd"
    season = int((a.date or datetime.now(
        ZoneInfo("America/New_York")).date().isoformat())[:4])
    team_ids = fetch_team_ids(season) if use_cfbd else {}
    known_schools = load_known_schools()

    while True:
        started = time.monotonic()
        cfbd_states: dict[tuple[str, str], dict] = {}
        # "no games are live" and "the feed did not answer" both produce an
        # empty list, and conflating them is how a rate-limited loop decides
        # the slate is over. Polling faster makes a 429 likelier, so the two
        # are now distinguished and only an ANSWER advances the idle clock.
        feed_answered = False
        if not use_cfbd:
            sb = fetch_scoreboard()
            live = extract_live_events(sb) if sb else []
            feed_answered = sb is not None
            if sb is None and a.source == "auto":
                log.warning("ESPN scoreboard unreachable - flipping to the "
                            "CFBD source for the rest of this run")
                use_cfbd = True
                team_ids = fetch_team_ids(season)
        if use_cfbd:
            if not team_ids:
                team_ids = fetch_team_ids(season)   # retry a failed load
            payload = fetch_scoreboard_cfbd()
            feed_answered = payload is not None
            states = extract_live_states_cfbd(payload or [], team_ids,
                                              known_schools)
            cfbd_states = {(_fold(st["home_location"]),
                            _fold(st["away_location"])): st for st in states}
            live = [{"event_id": None,
                     "home_location": st["home_location"],
                     "away_location": st["away_location"]}
                    for st in states]
        if live:
            last_live = datetime.now(timezone.utc)
        elif not feed_answered:
            log.warning("state feed did not answer - holding the idle clock "
                        "(an unanswered feed is not an empty slate)")
        elif datetime.now(timezone.utc) - last_live > timedelta(minutes=IDLE_EXIT_MINUTES):
            log.info("no live games for %d min - exiting (%d decisions written)",
                     IDLE_EXIT_MINUTES, decisions)
            return 0

        odds_raw = odds_feed.fetch(min_interval=a.odds_interval) if live else None
        odds_map = resolve_odds_teams(parse_event_odds(odds_raw or []))

        for ev, key, ctx, state in resolve_live_states(
                live, ctx_map, use_cfbd, cfbd_states):
            if state is None:
                continue
            if not feed_blessed:
                problems = [p for p in check_feed_assumptions(state)
                            if "non-fatal" not in p]
                if problems:
                    log.error("FEED CHECK FAILED - refusing to price: %s",
                              problems)
                    continue
                feed_blessed = True
                log.info("feed check passed on first live payload "
                         "(%s @ %s)", ctx.away, ctx.home)
            picks = engine.price(state, ctx, odds_map.get(key))
            write_picks(picks, ctx.game_id, a.dry_run)
            decisions += len(picks)

        if a.once:
            log.info("--once: %d live games seen, %d decisions", len(live),
                     decisions)
            return 0

        # Sleep the REMAINDER, not the full interval: the old code slept a flat
        # 45s after the work, so the real cadence was always interval + however
        # long the feeds took. At 10s that error would dominate. When a pass
        # overruns, the feed - not the loop - is the limit, and saying so out
        # loud is the difference between a visible bottleneck and silent drift.
        elapsed = time.monotonic() - started
        if elapsed > a.interval:
            log.warning("pass took %.1fs, over the %.0fs target - the feeds are "
                        "the bottleneck (%d live games)", elapsed, a.interval,
                        len(live))
        time.sleep(max(0.0, a.interval - elapsed))


if __name__ == "__main__":
    sys.exit(main())
