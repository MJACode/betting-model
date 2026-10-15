"""
NFL in-play leader moneyline loop (`nfl_live_leader_ml`).

    python -m nfl_live_leader.gameday              # the real thing
    python -m nfl_live_leader.gameday --dry-run    # decide and log, write nothing
    python -m nfl_live_leader.gameday --once       # one pass, then exit

Run from the REPO ROOT. scheduler.py relaunches it every 10 minutes from 9am to
midnight ET (max_instances=1); it exits by itself after a few idle ticks with
no game in progress, so an idle launch costs a handful of free ESPN reads and
no Odds API credit.

ONE PASS (every NFL_LIVE_LEADER_POLL_STATE_SEC, default 20 s)
  1. ESPN core status for each of the day's games (free); for games in the 4th
     quarter, the situation and the last real play (state.py).
  2. A game is IN WINDOW when the 4th quarter is in progress, the last real
     play's SNAP clock is <= 10:00 and the lead is 4-16.
  3. Each in-window game is EVALUATED on a 5-minute cadence -- the first time
     it is in the window with an evaluable state, then every 300 s -- to
     mirror the backtest's 5-minute snapshot grid (NFL_LIVE_LEADER_EVAL_SEC).
     A transitional state (after a score, a kickoff in flight, possession
     unknown) does not consume a slot; it waits for the next 20 s tick.
  4. Only when at least one game is due: ONE bulk DraftKings h2h call
     (odds.py) for every due game at once. Each DraftKings quote used is
     logged to `odds` as in_play (data/ingestors/live_price_log).
  5. Per due game: skip a quote DraftKings stamped before the last score
     change WE saw (data/live_quote_guard.quote_predates_score); otherwise
     model.decide(). The first BET per game is written and locked; the game
     is not evaluated again.
  6. Every pass asks the notifiers (push, then Discord's NFL live channel, the
     ncaaf_live path) about each slate date that carries a BET of record, so a
     failed post is retried; their ledgers make the repeats no-ops.

Regular season and playoffs only (ESPN core season type 2 or 3): the model
was trained on nothing else, and a preseason 4th quarter is backups.

WHAT IS NOT HERE, ON PURPOSE. No price floor or ceiling, no edge cap, no
book-move or settled-state guard: none existed in the backtest, so each would
bet a population whose return was never measured. The platform's own gates
(min_odds_for, min_ev_for, the pause list) are still consulted; config.py is
set so the first two cannot bind on this rule (see its comments). Overtime is
never priced. Decided and settled at DraftKings only: the evidence holds at
DraftKings, and a best-of-books price is a different, cross-book-latency effect
the backtest measured separately and did not support.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.live_quote_guard import ScoreClock, parse_book_ts, quote_predates_score  # noqa: E402
from nfl_live_leader import model as M  # noqa: E402
from nfl_live_leader.odds import LiveOddsFeed, parse_h2h  # noqa: E402
from nfl_live_leader.state import CoreClient, EventMeta, LiveState, in_window  # noqa: E402
from nfl_live_leader.teams import abbrev  # noqa: E402

log = logging.getLogger("nfl_live_leader.gameday")

MODEL_ID = M.MODEL_ID
SPORT = "NFL"
SNAPSHOT_BOOK = "draftkings"
POLL_STATE_SEC = float(os.environ.get("NFL_LIVE_LEADER_POLL_STATE_SEC", "20"))
EVAL_EVERY_SEC = float(os.environ.get("NFL_LIVE_LEADER_EVAL_SEC", "300"))
IDLE_EXIT_TICKS = int(os.environ.get("NFL_LIVE_LEADER_IDLE_EXIT_TICKS", "3"))
FEED_FAIL_EXIT_TICKS = int(os.environ.get("NFL_LIVE_LEADER_FEED_FAIL_EXIT_TICKS", "45"))
EVENT_REFRESH_SEC = 300.0
SEASON_TYPES = (2, 3)        # ESPN core: 1 preseason, 2 regular season, 3 postseason


# ─── the cadence ──────────────────────────────────────────────────────────────

class Cadence:
    """Per-game evaluation slots on an EPOCH-ALIGNED wall-clock grid of
    `every` seconds (:00, :05, :10 ... for 300 s).

    The evidence was measured on the Odds API's own 5-minute snapshot grid,
    which ignores game state. So a game is evaluated at most once per grid
    slot, at the first tick inside it, and a slot whose state is not
    evaluable (a score not yet followed by a snap, a timeout) is SPENT, not
    carried forward to a later tick in the same slot -- carrying it would
    bunch evaluations just after plays post, a population the study never
    sampled (review of the build, 2026-10-13). `now` is wall-clock seconds."""

    def __init__(self, every: float = EVAL_EVERY_SEC):
        self.every = float(every)
        self._last: dict = {}

    def slot(self, now: float) -> int:
        return int(now // self.every)

    def due(self, key, now: float) -> bool:
        return self._last.get(key) != self.slot(now)

    def mark(self, key, now: float) -> None:
        self._last[key] = self.slot(now)


# ─── platform context ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GameContext:
    game_id: str
    game_date: str
    home: str                     # platform abbreviations (games.home_team)
    away: str
    commence_time: str | None
    spread_home: float | None     # DraftKings' last pre-kickoff HOME handicap
    spread_source: str | None


def _parse_ts(v) -> datetime | None:
    return parse_book_ts(v.isoformat() if isinstance(v, datetime) else v)


def resolve_game(conn, home: str | None, away: str | None,
                 kickoff: datetime | None) -> tuple[str, str, str | None] | None:
    """(game_id, game_date, commence_time) for ESPN's (home, away) around the
    kickoff, or None. Exactly one row or nothing: a guessed game_id writes a
    bet that joins to no game and never settles. +/- 1 day because
    games.game_date is the ET day and a night kickoff is the next UTC day."""
    if not home or not away or kickoff is None:
        log.warning("cannot resolve game: home=%r away=%r kickoff=%r", home, away, kickoff)
        return None
    day = kickoff.astimezone(timezone.utc).date()
    rows = conn.execute("""
        SELECT game_id, game_date, commence_time FROM games
        WHERE sport = 'NFL' AND home_team = %s AND away_team = %s
          AND game_date BETWEEN %s AND %s
        ORDER BY game_date
        LIMIT 2
    """, (home, away, (day - timedelta(days=1)).isoformat(),
          (day + timedelta(days=1)).isoformat())).fetchall()
    if len(rows) != 1:
        swapped = conn.execute("""
            SELECT game_id FROM games
            WHERE sport = 'NFL' AND home_team = %s AND away_team = %s
              AND game_date BETWEEN %s AND %s LIMIT 2
        """, (away, home, (day - timedelta(days=1)).isoformat(),
              (day + timedelta(days=1)).isoformat())).fetchall()
        log.warning("game resolution found %d rows for %s @ %s around %s%s - refusing",
                    len(rows), away, home, day,
                    f" (the SWAPPED pair matches {[r[0] for r in swapped]}: ESPN and the "
                    "platform disagree on which team is home)" if swapped else "")
        return None
    return str(rows[0][0]), str(rows[0][1]), (None if rows[0][2] is None else str(rows[0][2]))


def pregame_spread(conn, game_id: str, commence_time: str | None) -> tuple[float, str] | None:
    """DraftKings' LAST PRE-KICKOFF spread for the game, as the HOME handicap
    (negative = home favoured), and where it came from. None when there is
    none -- the caller skips the game, never defaults to 0.

    `odds` first: the latest DraftKings `spreads` row with snapshot_type <>
    'in_play' and snapshot_at <= commence_time (the evening refresh keeps
    writing 'open' rows after kickoff, so the time bound is what keeps a live
    line out). snapshot_at is TEXT in mixed ISO formats, so the index is
    walked backwards from a text bound one minute past kickoff and the exact
    bound is applied on the parsed timestamps. Fallback: nfl_odds_history,
    keyed on the nflverse id (the platform id minus 'NFL_'), same bound -- that
    table also holds in-play rows."""
    ct = _parse_ts(commence_time)
    if ct is None:
        return None
    bound = (ct + timedelta(minutes=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    rows = conn.execute("""
        SELECT spread_home, snapshot_at FROM odds
        WHERE game_id = %s AND market = 'spreads' AND bookmaker = 'draftkings'
          AND snapshot_at <= %s
          AND spread_home IS NOT NULL
          AND snapshot_type <> 'in_play'
        ORDER BY snapshot_at DESC
        LIMIT 20
    """, (game_id, bound)).fetchall()
    best = None
    for sp, at in rows:
        t = _parse_ts(at)
        if t is not None and t <= ct and (best is None or t > best[1]):
            best = (float(sp), t)
    if best is not None:
        return best[0], f"odds draftkings {best[1].isoformat()}"
    nv = game_id[4:] if game_id.startswith("NFL_") else game_id
    row = conn.execute("""
        SELECT point, snapshot_at FROM nfl_odds_history
        WHERE game_id = %s AND market = 'spreads' AND bookmaker = 'draftkings'
          AND point IS NOT NULL AND snapshot_at <= commence_time
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (nv,)).fetchone()
    if row is not None and row[0] is not None:
        return float(row[0]), f"nfl_odds_history draftkings {row[1]}"
    return None


def load_context(conn, meta: EventMeta) -> GameContext | None:
    home, away = abbrev(meta.home_abbr), abbrev(meta.away_abbr)
    got = resolve_game(conn, home, away, _parse_ts(meta.date))
    if got is None:
        return None
    gid, gdate, ct = got
    sp = pregame_spread(conn, gid, ct or meta.date)
    if sp is None:
        log.warning("%s: no DraftKings pre-kickoff spread - the game will not be priced", gid)
    return GameContext(game_id=gid, game_date=gdate, home=home, away=away,
                       commence_time=ct or meta.date,
                       spread_home=None if sp is None else sp[0],
                       spread_source=None if sp is None else sp[1])


# ─── quotes ───────────────────────────────────────────────────────────────────

QUOTE_KICKOFF_TOL = timedelta(hours=6)


def quotes_by_teams(events: list) -> dict[frozenset, list]:
    """{frozenset({abbr, abbr}): [{"prices": {abbr: price}, "ts": last_update,
    "commence": datetime}, ...]}, one entry per EVENT. Priced per TEAM, so a
    neutral-site game the two feeds list with opposite home teams still gets
    the right price per side; a list, so a later meeting of the same two teams
    in the feed never overwrites the game in progress."""
    out: dict[frozenset, list] = {}
    for (h, a, ct), q in parse_h2h(events).items():
        ha, aa = abbrev(h), abbrev(a)
        if not ha or not aa:
            continue
        out.setdefault(frozenset((ha, aa)), []).append(
            {"prices": {ha: q.home_price, aa: q.away_price}, "ts": q.last_update,
             "commence": _parse_ts(ct), "quote": q})
    return out


def quote_for_game(quotes: dict, ctx: "GameContext") -> dict | None:
    """The one event for THIS game: same two teams AND a kickoff within
    QUOTE_KICKOFF_TOL of the game's own commence_time. Anything else -- no
    match, or two -- is None: pricing a game at another game's line writes a
    bet at a price that never existed for it."""
    ct = _parse_ts(ctx.commence_time)
    cands = quotes.get(frozenset((ctx.home, ctx.away))) or []
    if ct is None:
        return None
    hits = [q for q in cands if q.get("commence") is not None
            and abs(q["commence"] - ct) <= QUOTE_KICKOFF_TOL]
    if len(hits) != 1:
        if len(cands) > 1 or len(hits) > 1:
            log.warning("%s: %d DraftKings events for %s/%s, %d at this kickoff - not priced",
                        ctx.game_id, len(cands), ctx.away, ctx.home, len(hits))
        return None
    return hits[0]


def side_prices(ctx: GameContext, q: dict | None) -> tuple:
    if not q:
        return None, None, None
    p = q["prices"]
    return p.get(ctx.home), p.get(ctx.away), q.get("ts")


# ─── writing ──────────────────────────────────────────────────────────────────

def build_pick(ctx: GameContext, st: LiveState, d: M.Decision, bankroll: float) -> dict:
    """One `picks` row from one BET decision -- the NCAAF live dict shape, every
    key _insert_picks binds by name present."""
    from models.scorer import _confidence_tier, quarter_kelly
    team = ctx.home if d.side == "home" else ctx.away
    kf, rec = quarter_kelly(d.wp, d.implied, bankroll)
    return {
        "game_id": ctx.game_id, "model_id": MODEL_ID, "sport": SPORT,
        "game_date": ctx.game_date, "game_time": ctx.commence_time,
        "pick_side": d.side, "pick_label": f"{team} ML (live)",
        "model_probability": round(d.wp, 4),
        "dk_implied_prob": round(d.implied, 4),
        "edge": round(d.edge, 4),
        "dk_odds": float(d.price),
        "scored_line": None,
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "injury_flag": None, "injury_detail": None,
        "signal_type": "BET", "confidence_tier": _confidence_tier(d.edge),
        "is_live": True,
        "inning_at_pick": int(st.period),           # the quarter, in the shared column
        "score_diff_at_pick": int(st.home_score - st.away_score),   # home minus away
    }


def platform_gates(d: M.Decision) -> str | None:
    """The platform's own gates on top of the rule, read at call time. None =
    clears. Configured (config.py) so neither can bind on this rule; consulted
    anyway so a later change there reaches this loop."""
    import config
    if d.price < config.min_odds_for(MODEL_ID):
        return f"price {d.price:+.0f} under the floor {config.min_odds_for(MODEL_ID):+.0f}"
    ev = config.expected_value(d.wp, d.price)
    if ev is not None and ev < config.min_ev_for(MODEL_ID):
        return f"EV {ev:.3f} under the floor {config.min_ev_for(MODEL_ID):.3f}"
    cut = config.ACTION_THRESHOLDS.get(MODEL_ID, {})
    if d.wp < float(cut.get("min_prob", 0.0)):
        return f"probability {d.wp:.3f} under min_prob {cut.get('min_prob')}"
    if MODEL_ID in getattr(config, "PAUSED_MODELS", ()):
        return "model is paused (config.PAUSED_MODELS)"
    return None


def write_bet(conn, pick: dict) -> bool:
    """Insert one BET under the first-signal lock. False when this game
    already carries an unsettled live BET for the model (the bet of record
    stands; nothing is deleted or replaced, ever)."""
    from models.scorer import _insert_picks, _locked_live_lanes
    if _locked_live_lanes(conn, pick["game_id"], (MODEL_ID,)):
        log.info("SKIPPED %s %s - locked at its first BET (bet of record stands)",
                 MODEL_ID, pick["pick_label"])
        return False
    _insert_picks(conn, [pick])
    conn.commit()
    return True


def is_locked(conn, game_id: str) -> bool:
    from models.scorer import _locked_live_lanes
    return bool(_locked_live_lanes(conn, game_id, (MODEL_ID,)))


def unsettled_bet_dates(conn) -> set[str]:
    """Slate dates holding an unsettled live BET of this model. Every launch
    announces them, so a post that failed -- a webhook error, the Discord live
    lock held by another loop, or a deploy that killed the process between
    the insert and the post -- is retried by the next launch until the pick is
    graded (both notifiers then skip it). A posted bet is a no-op: the ledgers
    dedupe. Bounded to the last few days."""
    since = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
    rows = conn.execute("""
        SELECT DISTINCT game_date FROM picks
        WHERE model_id = %s AND is_live = TRUE
          AND signal_type = 'BET' AND result IS NULL
          AND game_date >= %s
    """, (MODEL_ID, since)).fetchall()
    return {str(r[0])[:10] for r in rows}


def notify_live(target_date: str) -> None:
    """Push, then Discord live (DISCORD_WEBHOOK_LIVE_NFL for NFL) -- the
    ncaaf_live path. Both dedupe through their ledgers; neither may break the
    loop."""
    try:
        from tracking.push_notifier import notify_live_signals
        notify_live_signals(target_date=target_date, dry_run=False)
    except Exception as exc:                          # noqa: BLE001
        log.error("live push failed (non-fatal): %s", exc)
    try:
        from tracking.discord_notifier import notify_discord_live
        notify_discord_live(target_date=target_date, dry_run=False)
    except Exception as exc:                          # noqa: BLE001
        log.error("live Discord post failed (non-fatal): %s", exc)


# ─── one evaluation ───────────────────────────────────────────────────────────

def evaluate(art: M.Artifact, st: LiveState, ctx: GameContext, q: dict | None,
             score_seen_at, edge_cut: float) -> tuple[M.Decision | None, str]:
    """(decision, note) for one due game against this pass's quote. A None
    decision means the quote was not decidable (missing or stale)."""
    hp, ap, ts = side_prices(ctx, q)
    if hp is None and ap is None:
        return None, "no DraftKings moneyline in the feed"
    if quote_predates_score(ts, score_seen_at):
        return None, (f"DraftKings quote {ts} predates the score change we saw at "
                      f"{score_seen_at.isoformat() if hasattr(score_seen_at, 'isoformat') else score_seen_at}")
    d = M.decide(art, period=st.period, secs=st.secs, home_score=st.home_score,
                 away_score=st.away_score, possession=st.possession,
                 spread_home=ctx.spread_home, home_price=hp, away_price=ap,
                 final=st.final, edge_cut=edge_cut)
    return d, d.reason


# ─── the loop ─────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nfl-live-leader")
    except Exception:                                 # noqa: BLE001
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=POLL_STATE_SEC)
    ap.add_argument("--eval-every", type=float, default=EVAL_EVERY_SEC)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    import config
    art = M.load_artifact()
    cut = config.ACTION_THRESHOLDS[MODEL_ID]
    edge_cut = float(cut["min_edge"])
    log.info("artifact %s (built %s, seasons %s-%s); cut edge >= %.3f; state every %.0fs, "
             "evaluation every %.0fs", art.version, art.identity.get("built_at"),
             (art.training.get("seasons") or ["?"])[0], (art.training.get("seasons") or ["?"])[-1],
             edge_cut, a.interval, a.eval_every)

    client = CoreClient()
    feed = LiveOddsFeed()
    cadence = Cadence(a.eval_every)
    score_clock = ScoreClock()
    metas: dict[str, EventMeta] = {}
    contexts: dict[str, GameContext | None] = {}
    done: set[str] = set()                        # games with their BET of record
    finished: set[str] = set()                    # games ESPN reports final
    # Slate dates that carry a BET of record from this model. Announced on
    # EVERY pass, not only the pass that wrote it: a push 5xx or a webhook
    # added mid-game would otherwise leave the bet unposted for the rest of the
    # slate. Both notifiers dedupe through their ledgers, so a repeat is a
    # no-op (ncaaf_live.gameday.write_picks has the same rule).
    bet_dates: set[str] = set()
    skipped: set[str] = set()                     # event refs outside REG/POST
    listed = False
    bankroll: float | None = None
    last_list = 0.0
    idle = fails = 0
    bets_written = 0
    fetch_backoff_until = 0.0                     # monotonic; after a failed odds call
    fetch_failures = 0
    last_notify = None                            # monotonic; standing-bet re-announce

    from data.db import get_connection
    conn = None

    def _conn():
        nonlocal conn
        if conn is None:
            conn = get_connection()
        return conn

    if not a.dry_run:
        # The published record counts a settled BET only while Discord holds
        # its post (CLAUDE.md section 1c), so a bet that never posted is a bet
        # that silently leaves the record. Pick up any this model still owes.
        try:
            bet_dates |= unsettled_bet_dates(_conn())
            if bet_dates:
                log.info("standing BETs to announce: %s", ", ".join(sorted(bet_dates)))
        except Exception as exc:                      # noqa: BLE001
            log.warning("could not read standing BETs (non-fatal): %s", exc)
            conn = _recycle(conn)

    try:
        while True:
            started = time.monotonic()
            now = datetime.now(timezone.utc)
            if not listed or started - last_list >= EVENT_REFRESH_SEC:
                refs = client.list_event_refs(now)
                if refs is None:
                    fails += 1
                    log.warning("ESPN core event list did not answer (%d in a row)", fails)
                    if fails >= FEED_FAIL_EXIT_TICKS:
                        log.error("ESPN core unreachable for %d ticks - exiting", fails)
                        return 1
                    time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
                    continue
                fails = 0
                last_list = started
                listed = True
                for ref in refs:
                    if ref not in metas and ref not in skipped:
                        m = client.event_meta(ref)
                        if m is None:
                            continue
                        if m.season_type not in SEASON_TYPES:
                            # Trained on regular season and playoffs only. A
                            # preseason 4th quarter is backups, and a missing
                            # season type is a shape change, not a REG game.
                            skipped.add(ref)
                            log.info("%s %s @ %s: season type %s is not regular season or "
                                     "playoffs - not priced", m.event_id, m.away_abbr,
                                     m.home_abbr, m.season_type)
                            continue
                        metas[ref] = m

            states = [client.poll(m) for m in metas.values()
                      if m.event_id not in done and m.event_id not in finished]
            finished.update(s.event_id for s in states if s.final)
            live = [s for s in states if s.status_state == "in"]
            if states and all(s.reason == "status unavailable" for s in states):
                # Every status read failed: an unanswered feed is not an empty
                # slate, so it does not advance the idle clock.
                fails += 1
                log.warning("no ESPN status answered this tick (%d in a row)", fails)
                if fails >= FEED_FAIL_EXIT_TICKS:
                    log.error("ESPN core unreachable for %d ticks - exiting", fails)
                    return 1
                time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
                continue
            if not live:
                idle += 1
                if idle >= IDLE_EXIT_TICKS or a.once:
                    if bet_dates and not a.dry_run:
                        # Its game has left the board (final, or this process
                        # started after it), so this is the bet's last chance in
                        # this process; the next launch, ten minutes on, retries.
                        for d_ in sorted(bet_dates):
                            notify_live(d_)
                    log.info("no NFL game in progress for %d tick(s) - exiting (%d BETs written)",
                             idle, bets_written)
                    return 0
                time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
                continue
            idle = 0

            for s in live:
                score_clock.observe(s.event_id, s.score, now)

            wall = time.time()
            due: list[LiveState] = []
            for s in live:
                if not in_window(s):
                    continue
                if not cadence.due(s.event_id, wall):
                    continue
                if not s.evaluable:
                    # The slot is spent: the evidence sampled a fixed grid and
                    # a refused state there was simply no bet at that snapshot.
                    cadence.mark(s.event_id, wall)
                    log.info("%s in window, slot spent, not evaluable: %s", s.event_id, s.reason)
                    continue
                due.append(s)

            if due:
                meta_by_id = {m.event_id: m for m in metas.values()}
                ready: list[tuple[LiveState, GameContext]] = []
                for s in due:
                    if s.event_id not in contexts:
                        try:
                            contexts[s.event_id] = load_context(_conn(), meta_by_id[s.event_id])
                            ctx = contexts[s.event_id]
                            if ctx is not None and is_locked(_conn(), ctx.game_id):
                                log.info("%s already carries its BET of record - not "
                                         "evaluating again", ctx.game_id)
                                done.add(s.event_id)
                                bet_dates.add(ctx.game_date)
                        except Exception as exc:          # noqa: BLE001
                            log.error("context load failed for %s: %s", s.event_id, exc)
                            conn = _recycle(conn)
                            continue
                    ctx = contexts.get(s.event_id)
                    if ctx is None or s.event_id in done:
                        continue
                    if ctx.spread_home is None:
                        continue
                    ready.append((s, ctx))

                payload = None
                if ready and time.monotonic() < fetch_backoff_until:
                    log.info("odds fetch backing off %.0fs more after %d failure(s)",
                             fetch_backoff_until - time.monotonic(), fetch_failures)
                elif ready:
                    payload = feed.fetch()
                    if payload is None:
                        fetch_failures += 1
                        wait = (60, 120, 300)[min(fetch_failures, 3) - 1]
                        fetch_backoff_until = time.monotonic() + wait
                        log.warning("no odds this pass for %d due game(s) - backing off %ds "
                                    "(failure %d)", len(ready), wait, fetch_failures)
                    else:
                        fetch_failures = 0
                if ready and payload is not None:
                    quotes = quotes_by_teams(payload)
                    priced_at = datetime.now(timezone.utc).isoformat()
                    price_rows = []
                    for s, ctx in ready:
                        cadence.mark(s.event_id, wall)          # this slot is consumed
                        q = quote_for_game(quotes, ctx)
                        hp, apx, ts = side_prices(ctx, q)
                        if hp is not None or apx is not None:
                            from data.ingestors.live_price_log import rows_from_quote
                            price_rows.extend(rows_from_quote(
                                ctx.game_id, SPORT, {"h2h": {"home": hp, "away": apx, "ts": ts}},
                                SNAPSHOT_BOOK, priced_at))
                        d, note = evaluate(art, s, ctx, q, score_clock.last_change(s.event_id),
                                           edge_cut)
                        # Posting delay, measured live: now minus ESPN's wallclock
                        # for the last real play. The evidence assumed 0 s; the
                        # 2025 return fell from +1.84u to -0.50u as the state
                        # lagged the quote by 0 -> 45 s (review of the build).
                        wc = _parse_ts(s.last_play_wallclock)
                        lag = None if wc is None else (datetime.now(timezone.utc) - wc).total_seconds()
                        log.info("EVAL %s %s @ %s Q%s secs=%s score %s-%s poss=%s spread_home=%s "
                                 "DK %s/%s play_lag=%s: %s%s", ctx.game_id, ctx.away, ctx.home, s.period,
                                 s.secs, s.home_score, s.away_score, s.possession,
                                 ctx.spread_home, hp, apx,
                                 "?" if lag is None else f"{lag:.0f}s", note,
                                 "" if d is None or d.wp is None else
                                 f" (wp {d.wp:.4f} implied {d.implied:.4f} edge {d.edge:+.4f})")
                        if d is None or not d.bet:
                            continue
                        why = platform_gates(d)
                        if why:
                            log.warning("BET %s on %s not written: %s", MODEL_ID, ctx.game_id, why)
                            continue
                        if a.dry_run:
                            log.info("[dry-run] BET %s ML (live) at %+.0f", ctx.home if d.side ==
                                     "home" else ctx.away, d.price)
                            done.add(s.event_id)
                            continue
                        try:
                            if bankroll is None:
                                from models.scorer import _get_current_bankroll
                                bankroll = float(_get_current_bankroll(_conn()))
                            pick = build_pick(ctx, s, d, bankroll)
                            if write_bet(_conn(), pick):
                                bets_written += 1
                                log.info("WROTE BET %s %s at %+.0f wp=%.4f edge=%+.4f",
                                         MODEL_ID, pick["pick_label"], d.price, d.wp, d.edge)
                            bet_dates.add(ctx.game_date)
                            done.add(s.event_id)
                        except Exception as exc:          # noqa: BLE001
                            log.error("write failed for %s (non-fatal): %s", ctx.game_id, exc)
                            conn = _recycle(conn)
                    if price_rows and not a.dry_run:
                        try:
                            from data.ingestors.live_price_log import record_live_prices
                            record_live_prices(_conn(), price_rows,
                                               known_game_ids={r["game_id"] for r in price_rows})
                        except Exception as exc:          # noqa: BLE001
                            log.warning("live price log failed (non-fatal): %s", exc)
                            conn = _recycle(conn)

            # Announce: right after a pass that wrote a bet, and otherwise
            # re-ask at most every 5 minutes for the standing bets (a push 5xx
            # or a webhook added mid-game). Both notifiers dedupe through their
            # ledgers; the throttle keeps this loop from calling them every 20 s.
            wrote_now = bets_written > getattr(main, "_announced", 0)
            if not a.dry_run and bet_dates and (wrote_now or last_notify is None
                                                or time.monotonic() - last_notify >= 300):
                for d_ in sorted(bet_dates):
                    notify_live(d_)
                last_notify = time.monotonic()
                main._announced = bets_written

            if a.once:
                log.info("--once: %d live, %d due, %d BETs written; ESPN calls %d, odds "
                         "credits %d", len(live), len(due), bets_written, client.calls,
                         feed.credits_used)
                return 0
            elapsed = time.monotonic() - started
            if elapsed > a.interval:
                log.warning("pass took %.1fs, over the %.0fs target", elapsed, a.interval)
            time.sleep(max(0.0, a.interval - elapsed))
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:                         # noqa: BLE001
                pass


def _recycle(conn):
    """Roll a failed connection back, or drop it so the next use reopens."""
    if conn is None:
        return None
    try:
        conn.rollback()
        return conn
    except Exception:                                 # noqa: BLE001
        try:
            conn.close()
        except Exception:                             # noqa: BLE001
            pass
        return None


if __name__ == "__main__":
    sys.exit(main())
