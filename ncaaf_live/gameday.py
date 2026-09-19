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
import json
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
    SNAPSHOT_BOOK,
    POLL_IDLE_SEC, POLL_ODDS_SEC, POLL_ODDS_TRIGGER_SEC, POLL_STATE_SEC,
    SUMMARY_FETCH_WORKERS)
from ncaaf_live.feeds.odds_live import LiveOddsFeed, parse_event_odds  # noqa: E402
# DATES, plural. A game keeps the game_date of its KICKOFF, and a Saturday
# 8pm ET kick is in the fourth quarter at 00:15 ET on Sunday -- at which point
# asking for "today's games" returns nothing and the loop goes quiet with no
# error. That is exactly how MLB lost the last 77 minutes of 2026-08-29 (#296
# fixed the 8pm UTC-rollover half of it, not this one), and NCAAF plays more
# games across midnight ET than MLB does. Shared helper on purpose: a fix that
# lands in one sport's loop and not the others is how this repo accumulates
# work (CLAUDE.md section 1b).
from config import live_slate_dates  # noqa: E402
from data.live_quote_guard import ScoreClock  # noqa: E402
from data.ingestors.live_price_log import (  # noqa: E402
    now_iso, record_live_prices, rows_from_quote)
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
# The market each live model prices, for the cross-book best-price lookup.
# Declared HERE rather than imported from config at call time, matching the
# line above: _write_picks runs under a stubbed `config` in the notify tests,
# and a new import there breaks them. tests/test_best_line_live.py pins this
# map against config.LIVE_MODELS so the two cannot drift.
LIVE_MODEL_MARKETS = {"ncaaf_live_win_prob": "h2h",
                      "ncaaf_live_total": "totals"}


def _fold(v: str) -> str:
    import unicodedata
    v = unicodedata.normalize("NFD", (v or "").strip().lower())
    return "".join(ch for ch in v if ch.isalnum() or ch == " ").replace("  ", " ")


def _has_pregame_lines(ctx: GameContext) -> bool:
    """The first gate serve.price already applies before it will emit a pick."""
    return ctx.pregame_spread is not None and ctx.pregame_total is not None


def _choose_context(ctxs: list[GameContext]) -> GameContext | None:
    """One GameContext for one folded (home, away), or none if we would guess.

    Night-game twins are by design (docs/sports/ncaaf.md): the odds ingestor
    dates by ET, CFBD by UTC, so a ~8pm-ET kick exists twice under the same
    school names. load_context used to last-wins overwrite on that pair.
    live_slate_dates() includes yesterday until LIVE_SLATE_LOOKBACK_UNTIL_HOUR_ET
    — exactly when a Saturday night game is still live. A silent pick can
    attach a BET to the CFBD id (no odds history) or keep the row with no
    pregame line (serve.price then declines; the live game is not priced).

    NFL live resolve_game_id refuses when it does not find exactly one row.
    Same here when more than one context has pregame lines — that is not the
    designed twin, and writing a BET to a guessed game_id is worse than
    writing none. When exactly one of the rows has the lines serve.price
    already requires, that one is the odds row the rest of the platform
    attaches picks to. Not a new product rule; the other rows would return
    [] at the existing gate.
    """
    if len(ctxs) == 1:
        return ctxs[0]
    ids = [c.game_id for c in ctxs]
    home = ctxs[0].home
    away = ctxs[0].away
    log.warning("context: %d games rows for %s @ %s; not picking silently: %s",
                len(ctxs), away, home, ids)
    priceable = [c for c in ctxs if _has_pregame_lines(c)]
    if len(priceable) == 1:
        log.warning("context: using %s — the only row with pregame lines "
                    "(picks attach to the odds row)", priceable[0].game_id)
        return priceable[0]
    log.error("context: dropping %s @ %s — %d of %d rows have pregame lines "
              "(%s). Refusing rather than guessing a game_id",
              away, home, len(priceable), len(ctxs), ids)
    return None


def load_context(conn=None, date: str | None = None) -> dict[tuple[str, str], GameContext]:
    """
    Today's (ET) NCAAF games from the platform: identity, pregame DK lines
    (latest PRE-KICKOFF snapshot - the post-start 'open' rows are the session
    106 leak and are excluded by timestamp), weather, dome flag.

    Keyed by folded (home, away) because that is what the live feeds match
    on. A (home, away) collision is not last-wins: see _choose_context.
    """
    from data.db import get_connection

    owned = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.home_team, g.away_team, g.commence_time,
                   g.game_date,
                   sp.spread_home, tl.total_line,
                   w.wind_mph, COALESCE(v.dome, 0),
                   hs.sp_overall, hs.classification,
                   aw.sp_overall, aw.classification
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
            -- Each team's latest rating snapshot on or before the game: the
            -- row the pre-game FBS gate reads (_get_ncaaf_team_stats takes
            -- this season's latest, else last season's).
            LEFT JOIN LATERAL (
                SELECT s.sp_overall, s.classification FROM ncaaf_team_stats s
                WHERE s.team = g.home_team
                  AND s.as_of_date <= CAST(g.game_date AS TEXT)
                ORDER BY s.season DESC, s.as_of_date DESC LIMIT 1
            ) hs ON TRUE
            LEFT JOIN LATERAL (
                SELECT s.sp_overall, s.classification FROM ncaaf_team_stats s
                WHERE s.team = g.away_team
                  AND s.as_of_date <= CAST(g.game_date AS TEXT)
                ORDER BY s.season DESC, s.as_of_date DESC LIMIT 1
            ) aw ON TRUE
            WHERE g.sport = 'NCAAF'
              AND g.game_date = ANY(%(d)s)
        """, {"d": [date] if date else live_slate_dates()}).fetchall()
    finally:
        if owned:
            conn.close()

    from features.ncaaf_feature_engine import _is_fbs

    grouped: dict[tuple[str, str], list[GameContext]] = {}
    not_fbs = []
    for (gid, home, away, ct, gd, sp, tl, wind, dome,
         h_sp, h_cls, a_sp, a_cls) in rows:
        fbs = (_is_fbs({"sp_overall": h_sp, "classification": h_cls})
               and _is_fbs({"sp_overall": a_sp, "classification": a_cls}))
        if not fbs:
            not_fbs.append(f"{away} @ {home}")
        ctx = GameContext(
            game_id=gid, home=home, away=away, commence_time=ct,
            pregame_spread=None if sp is None else float(sp),
            pregame_total=None if tl is None else float(tl),
            wind_mph=None if wind is None else float(wind),
            is_dome=bool(dome), game_date=gd, fbs_matchup=fbs)
        grouped.setdefault((_fold(home), _fold(away)), []).append(ctx)
    out = {}
    for key, ctxs in grouped.items():
        chosen = _choose_context(ctxs)
        if chosen is not None:
            out[key] = chosen
    if not_fbs:
        log.info("context: %d games are not FBS-vs-FBS and will not be priced "
                 "(same rule as the pre-game models): %s",
                 len(not_fbs), "; ".join(sorted(not_fbs)[:40]))
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


def seconds_to_next_kickoff(ctx_map: dict, now: datetime) -> float | None:
    """Seconds until the earliest kickoff still ahead of us, or None if that
    cannot be determined (no games left today, or unparseable timestamps).

    None means "unknown", and every caller treats unknown as "stay up" - being
    wrong about a kickoff must never cost us a game.
    """
    best = None
    for ctx in ctx_map.values():
        raw = getattr(ctx, "commence_time", None)
        if raw is None:
            continue
        try:
            if isinstance(raw, datetime):
                ct = raw
            else:
                ct = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        delta = (ct - now).total_seconds()
        if delta > 0 and (best is None or delta < best):
            best = delta
    return best


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



def score_fingerprint(states: dict) -> dict:
    """{game key: (home_score, away_score)} for every live game we can see.

    Only the SCORE. Clock and possession tick constantly and would make every
    pass look like a trigger, which is the flat cadence with extra steps.
    """
    return {k: (st.get("home_score"), st.get("away_score"))
            for k, st in (states or {}).items()
            if st.get("home_score") is not None}


def scores_moved(prev: dict, cur: dict) -> bool:
    """True when any game we were already watching has a new score.

    A game APPEARING is not a trigger: its first pass has no cached price to be
    stale against, and treating first-sight as a score change would fire a
    fetch for every game at kickoff.
    """
    return any(k in prev and prev[k] != v for k, v in cur.items())


# ── the state we priced on, kept (2026-09-19) ────────────────────────────────
# The loop read the scoreboard, priced it and threw it away. When the Delaware
# bet was traced, the ONE pick whose state could be shown was the one whose
# minute the poller's log happened to hold; the other 14 moneyline bets that
# followed the same book move could not be checked. `odds` has carried the
# in-play QUOTES since 2026-09-08; `ncaaf_live_states` now carries the STATE
# beside them, one row per change in what the engine's book-move guard keys
# on (score, period, possession) -- the same key, so the two agree on what a
# "change" is. Per-pass rows would be ~30k an hour of identical clock ticks.

_STATE_KEY_FIELDS = ("home_score", "away_score", "period", "possession")
_STATE_COLS = ("game_id", "seen_at", "period", "clock_seconds", "home_score",
               "away_score", "possession", "down", "distance", "yardline_100",
               "source", "raw_state")


def state_key(state: dict) -> tuple:
    """What the engine's book-move guard treats as an event: the score, the
    period and who has the ball. Clock, down and distance tick every play."""
    return tuple(state.get(f) for f in _STATE_KEY_FIELDS)


def state_change_row(seen: dict, game_id: str, state: dict, seen_at: str,
                     source: str) -> dict | None:
    """One `ncaaf_live_states` row when `game_id`'s event-level state differs
    from the last one in `seen` (first sight included); None when it is the
    same state on a later clock. Updates `seen` in place."""
    key = state_key(state)
    if seen.get(game_id) == key:
        return None
    seen[game_id] = key
    return {
        "game_id": game_id, "seen_at": seen_at,
        "period": state.get("period"),
        "clock_seconds": (None if state.get("clock_seconds") is None
                          else int(state["clock_seconds"])),
        "home_score": state.get("home_score"),
        "away_score": state.get("away_score"),
        "possession": state.get("possession"),
        "down": state.get("down"), "distance": state.get("distance"),
        "yardline_100": state.get("yardline_100"),
        "source": source,
        "raw_state": json.dumps(state, default=str, separators=(",", ":")),
    }


def record_live_states(conn, rows: list[dict]) -> int:
    """Append state-change rows. Non-fatal, like record_live_prices: a failed
    audit write must never cost a pass. Returns how many were written."""
    if not rows:
        return 0
    sql = (f"INSERT INTO ncaaf_live_states ({', '.join(_STATE_COLS)}) "
           f"VALUES ({', '.join(['%s'] * len(_STATE_COLS))}) "
           f"ON CONFLICT (game_id, seen_at) DO NOTHING")
    try:
        for r in rows:
            conn.execute(sql, tuple(r.get(c) for c in _STATE_COLS))
        conn.commit()
        return len(rows)
    except Exception as exc:                         # noqa: BLE001
        log.warning("live state log failed (non-fatal): %s", exc)
        try:
            conn.rollback()
        except Exception:                            # noqa: BLE001
            pass
        return 0


def write_picks(picks: list[dict], game_id: str, dry_run: bool,
                conn=None) -> str | None:
    """Write one game's live picks under the first-signal lock
    (config.LOCK_LIVE_PICKS_AT_FIRST_SIGNAL).

    A lane (model_id) with an unsettled live BET is LOCKED: the first BET is
    the bet of record at its line and price. Locked lanes are excluded from
    the per-pass delete AND from new inserts, so the locked row survives lane
    closes (totals shuts in Q4, OT declines everything) and settles into the
    model record. Unlocked lanes keep the delete-and-replace churn (MLB live
    convention).

    Returns the slate date when this game has something worth announcing (a
    BET this pass, or a standing locked bet of record), else None. The CALLER
    announces, ONCE per pass -- see notify_live(). Both notifiers are
    date-scoped, so the first call already covers every game on the slate and
    every later one runs the same query to find nothing. Invisible on a
    one-game Tuesday; 2026-09-05 has 117 NCAAF games.

    `conn` lets the caller own one connection for the whole pass. Opening one
    per game meant a fresh TCP+TLS+auth handshake to the session pooler per
    game per tick -- data.db.get_connection() does not pool -- which is a
    linear tax on the exact cadence the loop is trying to keep."""
    from config import LOCK_LIVE_PICKS_AT_FIRST_SIGNAL
    from data.db import get_connection
    from models.scorer import _insert_picks, _locked_live_lanes

    if dry_run:
        for p in picks:
            log.info("[dry-run] %s %s %s p=%.3f edge=%+.3f DK=%s",
                     p["signal_type"], p["model_id"], p["pick_label"],
                     p["model_probability"], p["edge"], p["dk_odds"])
        return None
    owned = conn is None
    conn = conn or get_connection()
    try:
        locked = (_locked_live_lanes(conn, game_id, LIVE_MODEL_IDS)
                  if LOCK_LIVE_PICKS_AT_FIRST_SIGNAL else set())
        unlocked = tuple(m for m in LIVE_MODEL_IDS if m not in locked)
        if unlocked:
            conn.execute("""
                DELETE FROM picks
                WHERE game_id = %(g)s AND result IS NULL AND is_live = TRUE
                  AND model_id IN %(m)s
                  -- A BET is never deleted (CLAUDE.md 1c). No-op for a single
                  -- writer -- a lane holding a BET is locked -- but it closes
                  -- the read-then-act race the lock cannot close itself.
                  AND signal_type <> 'BET' 
            """, {"g": game_id, "m": unlocked})
        writable = [p for p in picks if p["model_id"] not in locked]
        if writable:
            # Best IN-PLAY price across books, same stamp MLB live gets. NCAAF
            # is wired here rather than left for later because a fix that lands
            # in one loop and not the others is how this repo accumulates work
            # (CLAUDE.md section 1b). Tagged after the decision; the market
            # comes from the model's own registry entry.
            from models.scorer import _tag_live
            for p in writable:
                mkt = LIVE_MODEL_MARKETS.get(p["model_id"])
                if mkt:
                    _tag_live(p, (game_id, mkt))
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
        if owned:
            conn.close()

    if picks and (locked or any(p.get("signal_type") == "BET" for p in picks)):
        return picks[0].get("game_date")
    return None


def _recycle(conn):
    """A failed write leaves the shared connection mid-aborted-transaction, so
    every later game on the pass would fail too. Roll back to make it usable
    again; if even that fails the socket is gone, so drop it and let the next
    game open a fresh one."""
    if conn is None:
        return None
    try:
        conn.rollback()
        return conn
    except Exception:                                # noqa: BLE001
        try:
            conn.close()
        except Exception:                            # noqa: BLE001
            pass
        return None


def notify_live(target_date: str) -> None:
    """Announce the pass's live signals — push, then Discord.

    Called ONCE per pass by main(), not once per game. This worker writes
    picks the app can see, but until #266 nothing told anyone about them:
    models/live_scorer.py (the MLB/in-play loop) has this hook and this one
    never got it, so every NCAAF live BET reached the app and NOTHING else.
    push_sent had zero 'discord_live' rows, ever.

    Both notifiers dedupe per (game, model, side) through that ledger AND
    scope their query to the slate DATE, so calling this every pass is safe at
    any cadence and one call already covers every game on the board.

    A LOCKED lane keeps asking (write_picks returns a date for one even when
    the engine stops emitting a BET). That is load-bearing, not
    belt-and-braces: a locked lane is a standing bet of record, but the engine
    re-prices from scratch each pass and may stop betting that side as the
    number moves. If the notifier had not yet succeeded by then — a webhook
    added mid-game, a 5xx, or the KeyError that meant it had NEVER succeeded
    for anyone — the bet of record would sit unposted for the rest of the game
    with no further attempt. The ledger makes the extra calls no-ops.

    Separate try blocks, and neither may break the loop: a broken webhook must
    not suppress the mobile push, or vice versa, and a notifier must never
    take down pricing."""
    try:
        from tracking.push_notifier import notify_live_signals
        notify_live_signals(target_date=target_date, dry_run=False)
    except Exception as exc:                         # noqa: BLE001
        log.error("Live signal push failed (non-fatal): %s", exc)
    try:
        from tracking.discord_notifier import notify_discord_live
        notify_discord_live(target_date=target_date, dry_run=False)
    except Exception as exc:                         # noqa: BLE001
        log.error("Live signal Discord post failed (non-fatal): %s", exc)


def main() -> int:
    # API telemetry for the live monitor (monitoring/). Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaaf-live")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--date", default=None,
                    help="override the ET slate date (testing before gameday)")
    ap.add_argument("--interval", type=float, default=POLL_STATE_SEC,
                    help=f"seconds between state polls (default "
                         f"{POLL_STATE_SEC}; env NCAAF_LIVE_POLL_STATE_SEC)")
    ap.add_argument("--idle-interval", type=float, default=POLL_IDLE_SEC,
                    help=f"seconds between state polls when NOTHING is live "
                         f"(default {POLL_IDLE_SEC}; env "
                         f"NCAAF_LIVE_POLL_IDLE_SEC). CFBD bills per call and "
                         f"the loop keeps polling between games, so this is "
                         f"what the monthly quota actually pays for")
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

    log.info("cadence: state every %.0fs while live, %.0fs idle; odds every "
             "%.0fs", a.interval, a.idle_interval, a.odds_interval)

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

    from data.db import get_connection

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
    prev_scores: dict = {}
    # PER GAME, deliberately. `scores_moved` below is one bool for the whole
    # pass and is CFBD-only -- the ESPN fallback resolves scores per game
    # further down -- so a guard hung on it would be blind on the fallback.
    # This is keyed by game_id and fed from the same `state` the engine prices.
    score_clock = ScoreClock()
    # The last event-level state written for each game (state_change_row).
    state_seen: dict = {}

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
        now = datetime.now(timezone.utc)
        next_kick = seconds_to_next_kickoff(ctx_map, now)
        if live:
            last_live = now
        elif not feed_answered:
            log.warning("state feed did not answer - holding the idle clock "
                        "(an unanswered feed is not an empty slate)")
        elif next_kick is not None and next_kick > IDLE_EXIT_MINUTES * 60:
            # The docstring has always promised this ("exits when ... none
            # starts within the lookahead") but the code only ever checked how
            # long it had been since a game was live, so a loop launched hours
            # before kickoff sat polling a paid API for 30 minutes to learn
            # what its own context map already knew. Hand the wait back to the
            # */10 supervisor, which is free.
            log.info("nothing live and next kickoff is %.0f min out - exiting "
                     "(%d decisions written)", next_kick / 60, decisions)
            return 0
        elif now - last_live > timedelta(minutes=IDLE_EXIT_MINUTES):
            log.info("no live games for %d min - exiting (%d decisions written)",
                     IDLE_EXIT_MINUTES, decisions)
            return 0

        # A score is what moves a live total, so it is the moment the cached
        # price is most wrong. Collapse the odds cadence to its floor for that
        # pass instead of waiting out the remaining idle interval -- the last
        # real lag between the book moving and the pick reaching Discord.
        # Available on the CFBD source, which carries every game's score in the
        # one scoreboard call; the ESPN path fetches scores per game AFTER this
        # point, so it keeps the flat cadence.
        cur_scores = score_fingerprint(cfbd_states)
        triggered = scores_moved(prev_scores, cur_scores)
        prev_scores = cur_scores or prev_scores
        interval = (min(POLL_ODDS_TRIGGER_SEC, a.odds_interval) if triggered
                    else a.odds_interval)
        if triggered:
            log.info("score change seen - pulling odds now (%.0fs floor)",
                     interval)
        odds_raw = odds_feed.fetch(min_interval=interval) if live else None
        odds_map = resolve_odds_teams(parse_event_odds(odds_raw or []))
        priced_at = now_iso()

        # ONE connection for the whole pass. write_picks used to open its own
        # per game, and data.db does not pool, so a 30-game Saturday paid ~30
        # TCP+TLS+auth handshakes to the session pooler every cadence tick --
        # seconds of pure overhead inside a 10s budget, growing with the slate.
        # Each game still commits its own transaction, so a failure is scoped
        # to that game: roll back and keep pricing the rest of the board rather
        # than dropping the pass (the supervisor is 10 minutes away).
        conn = None
        notify_date = None
        priced_this_pass: list[dict] = []
        states_this_pass: list[dict] = []
        try:
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
                # WHEN did this game's score last change? A quote DraftKings
                # stamped before that has not accounted for the score, however
                # young it is -- the 2026-09-03 Wake Forest total was 62.2s old
                # and already extinct. None at first sight and after a restart,
                # which leaves the age bound as the only defence, as before.
                score_seen_at = score_clock.observe(
                    ctx.game_id,
                    (state.get("home_score"), state.get("away_score")), now)
                # KEEP THE STATE WE ARE ABOUT TO PRICE ON, when it changed.
                changed = state_change_row(
                    state_seen, ctx.game_id, state, priced_at,
                    "cfbd" if use_cfbd else "espn")
                if changed:
                    states_this_pass.append(changed)
                quote = odds_map.get(key)
                # AUDIT THE PRICE WE PRICED ON. This loop read DraftKings'
                # in-play feed, decided on it, and threw it away -- so a
                # published live number could not be shown afterwards, which is
                # exactly the question that got asked of a live total. MLB's
                # loop has always written its in-play snapshots to `odds`;
                # this puts NCAAF on the same footing, through the same table.
                if quote:
                    # Every book the poll returned (2026-09-10), not only
                    # DraftKings: the lanes now decide at the best of them, so
                    # the audit has to show the price that decided. A payload
                    # from before the per-book parser carries no "books".
                    per_book = quote.get("books") or {SNAPSHOT_BOOK: quote}
                    for book, q in per_book.items():
                        priced_this_pass.extend(rows_from_quote(
                            ctx.game_id, "NCAAF", q, book, priced_at))
                picks = engine.price(state, ctx, quote,
                                     score_seen_at=score_seen_at)
                if conn is None and not a.dry_run:
                    conn = get_connection()
                try:
                    notify_date = write_picks(
                        picks, ctx.game_id, a.dry_run, conn) or notify_date
                except Exception as exc:             # noqa: BLE001
                    log.error("write failed for %s (non-fatal): %s",
                              ctx.game_id, exc)
                    conn = _recycle(conn)
                decisions += len(picks)
            # Scoped to the games we actually priced: odds.game_id is a foreign
            # key and the bulk feed carries games with no `games` row.
            if conn is not None and priced_this_pass:
                record_live_prices(
                    conn, priced_this_pass,
                    known_game_ids={r["game_id"] for r in priced_this_pass})
            # The state beside the price. Opens the connection itself when
            # this pass wrote no pick: a state change with no decision is
            # exactly the row the next post-mortem needs.
            if states_this_pass and not a.dry_run:
                if conn is None:
                    conn = get_connection()
                record_live_states(conn, states_this_pass)
        finally:
            if conn is not None:
                conn.close()

        # Once per pass, after every game is written -- the notifiers are
        # date-scoped, so this covers the whole board in one call.
        if notify_date:
            notify_live(notify_date)

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
        # The fast cadence buys reaction time to a live scoring drive; with
        # nothing live there is nothing to react to, and CFBD charges the same
        # per call either way.
        target = a.interval if live else a.idle_interval
        if elapsed > target:
            log.warning("pass took %.1fs, over the %.0fs target - the feeds are "
                        "the bottleneck (%d live games)", elapsed, target,
                        len(live))
        time.sleep(max(0.0, target - elapsed))


if __name__ == "__main__":
    sys.exit(main())
