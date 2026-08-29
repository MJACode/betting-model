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
  3. one debounced bulk in-play odds fetch (~4 credits/min worst case,
     session-capped)
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from ncaaf_live.feeds.cfbd_scoreboard import (  # noqa: E402
    extract_live_states_cfbd, fetch_scoreboard_cfbd, fetch_team_ids)
from ncaaf_live.feeds.espn import (  # noqa: E402
    check_feed_assumptions, extract_live_events, extract_summary_state,
    fetch_scoreboard, fetch_summary)
from ncaaf_live.feeds.odds_live import LiveOddsFeed, parse_event_odds  # noqa: E402
from ncaaf_live.serve import GameContext, LiveEngine  # noqa: E402

log = logging.getLogger("ncaaf_live.gameday")

# State polling cadence. ESPN/CFBD scoreboard reads are FREE, so this is not a
# credit knob: LiveOddsFeed.fetch debounces the priced bulk call at 60s on its
# own clock and carries a session credit cap, so tightening the poll cannot
# increase Odds API spend. What it buys is reaction time — at 45s a scoring
# drive could move the live total before the loop looked again, and the pick we
# publish is the one standing at that moment.
POLL_SECONDS = 10
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
    # calling them on every ~45s pass is safe: a signal posts once and the
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
    ap.add_argument("--source", choices=["auto", "espn", "cfbd"], default="auto",
                    help="live-state source. auto = ESPN site.api first, flip "
                         "to CFBD /scoreboard when it fails (site.api is "
                         "403-blocked from the Railway worker)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

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
        cfbd_states: dict[tuple[str, str], dict] = {}
        if not use_cfbd:
            sb = fetch_scoreboard()
            live = extract_live_events(sb) if sb else []
            if sb is None and a.source == "auto":
                log.warning("ESPN scoreboard unreachable - flipping to the "
                            "CFBD source for the rest of this run")
                use_cfbd = True
                team_ids = fetch_team_ids(season)
        if use_cfbd:
            if not team_ids:
                team_ids = fetch_team_ids(season)   # retry a failed load
            payload = fetch_scoreboard_cfbd()
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
        elif datetime.now(timezone.utc) - last_live > timedelta(minutes=IDLE_EXIT_MINUTES):
            log.info("no live games for %d min - exiting (%d decisions written)",
                     IDLE_EXIT_MINUTES, decisions)
            return 0

        odds_raw = odds_feed.fetch() if live else None
        odds_map = resolve_odds_teams(parse_event_odds(odds_raw or []))

        for ev in live:
            key = (_fold(ev.get("home_location") or ""),
                   _fold(ev.get("away_location") or ""))
            ctx = ctx_map.get(key)
            if ctx is None:
                log.debug("no platform game for %s @ %s - skipping",
                          ev.get("away_location"), ev.get("home_location"))
                continue
            if use_cfbd:
                state = cfbd_states.get(key)
            else:
                summary = fetch_summary(ev["event_id"])
                state = extract_summary_state(summary) if summary else None
                time.sleep(0.2)
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
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
