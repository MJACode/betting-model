"""
NBA in-play loop: the live IG-2 rules (models/nba_live_ig2.RULES: the quarters 1-2 spread).

    python -m models.nba_live_loop              # the real thing
    python -m models.nba_live_loop --dry-run    # decide and log; write nothing
    python -m models.nba_live_loop --once       # one pass, then exit

Run from the REPO ROOT. scheduler.py relaunches it every 10 minutes from 11am
to 2:50am ET (max_instances=1); it exits by itself after a few idle ticks with
no NBA game in progress, so an idle launch costs a few free ESPN reads.

THE CADENCE IS THE GRADE'S HOURLY PURCHASE. The graded decision is "the first
fetch in the phase holding an eligible quote" (G.decision_quotes). The loop
fetches the board at each HOUR MINUS 264 SECONDS and at no other time: the
archive's hourly purchases (ledger why='hourly', requested on the hour) served
the market as it stood 264 s before the hour in 2022-23 .. 2025-26 (553 s in
2020-21, 549 s in 2021-22; scripts/nba_ingame_data.load_quotes' grid offset). The
archive's :30 purchases were gap fills (53.5% exactly 30 minutes before a
listed tip, 19.4% at one), not a schedule a loop can follow, and
games.commence_time in 2026-27 holds the actual start (:10, :40, off-minute
values), so no fetch time is ever built from a tip. The three graded rules
were re-graded on the hourly purchases alone (scripts/nba_live_ig2_regrade.py;
docs/sports/nba.md, "In play"); only the quarters 1-2 spread passed, and the
loop decides only M.RULES (the quarter-3 rules are M.HELD_OUT_RULES). A loop polling every few seconds would decide
every game in the first minute of each phase: a population never graded.

A fetch window is FETCH_WINDOW_SEC long. A game the loop could not decide on
at its first attempt (the odds feed or the credit cap, ESPN unreadable or
publishing late, starters unknown, an error) is retried inside the window,
every RETRY_GAP_SEC, and each failed attempt writes a 'skipped' row to
nba_live_decisions with the reason. A fetch with no eligible quote decides
nothing (no retry: the grade would have had none either); the next hour tries
again. A fetch with one decides the rule for the game, bet or not.

ONE PASS (every NBA_LIVE_POLL_SEC, default 20 s)
  1. ESPN's scoreboard for each slate date (config.live_slate_dates(): a late
     tip keeps its own game_date past midnight). Free.
  2. No game in progress for IDLE_EXIT_TICKS ticks: announce standing bets and
     exit.
  3. Inside a fetch window, while some game in progress still has an undecided
     rule: ONE bulk Odds API call (h2h + spreads, the eight deciding books and
     Pinnacle; 2 credits, x-requests-last logged), its rows logged to `odds`
     as in_play with source nba_live_loop, its credits to
     live_credit_telemetry.
  4. Wait NBA_LIVE_PBP_WAIT_SEC after the fetch, read each game's ESPN summary,
     wait NBA_LIVE_PBP_RECHECK_SEC more and read it again. The freshness rule
     asks whether a point was scored between a quote's stamp and the fetch's
     served time, by ESPN's play wallclock (when ESPN LOGGED the play: 74 plays
     of NBA_2026-10-23_LAC_LAL carry 02:35:53-54, docs/nba_search_ingame27.md
     3.2), which is what the grade read. A play logged before the served time
     but published after the read would be missing and a stale quote would
     read fresh, so the loop FAILS CLOSED: if the second read carries a play
     logged at or before the served time that the first did not, ESPN is
     publishing late and that game is skipped at that attempt. The wait and the
     recheck are set from ESPN's measured publication lag (docs/sports/nba.md).
     The decision's play_lag_s (decision time minus the newest play's
     wallclock) is stored with every decision.
  5. Per game and undecided rule: models.nba_live_ig2.prepare / eligible_for /
     decide. Every decision is written to nba_live_decisions FIRST (one
     decision row per game and rule, never replaced), then a BET to `picks`
     under the first-signal live lock, then announced (push, then the NBA live
     Discord channel, the ncaaf_live/NFL path).

WHAT IS NOT HERE, AND WHY (each a named difference from the house's other live
loops; docs/live_betting.md, "NBA in-play"):
  * No BookMoveClock. It anchors a book's number between changes in our
    state and needs a series of quotes between them; this loop sees one quote
    per book per hour. The grade's own freshness rule
    (record 7.1) is applied instead, on the same information the grade had:
    ESPN's logged plays up to the served time.
  * No quote-age, edge or settled-state cap: none existed in the grade.
  * No 10-game wait: IG-2's prior is Pinnacle's pre-game spread, which has no
    early-season gap; the grade had none.
  * Rule 6 (a 45-minute clock jump) is applied to the plays known so far. The
    grade dropped a game whose jump came after its decision; live, that is not
    knowable when the bet is made.
  * One game never carries two bets that cannot both win (mike, 2026-10-17):
    a later rule's bet that cannot win alongside a standing one is declined,
    two decided in one pass that cannot both win are both declined. On the
    graded seasons that declines 66 of 3,181 bets (+15.98 units).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from models import nba_live_ig2 as M  # noqa: E402

log = logging.getLogger("models.nba_live_loop")

SPORT = "NBA"
POLL_SEC = float(os.environ.get("NBA_LIVE_POLL_SEC", "20"))
# ESPN's publication lag, measured on the 2026-11-04 slate (free summary reads
# every 5 s; %TEMP%/nba_live_build/espn_lag3.py): a SCORING play was served a
# median 39 s after its wallclock, 90th percentile 58 s, 99th 168 s, longest
# 219 s (134 scoring plays, 8 games); every play: median 34 s, 99th 251-600 s,
# the tail being inserted rebounds, substitutions and technicals. The first
# read waits the scoring 99th percentile; the second, a minute later, catches
# a play published in between. Replayed on that slate's plays at 340 fetch
# times: 5.6% of fetches skipped, none with a scoring play still unseen.
PBP_WAIT_SEC = float(os.environ.get("NBA_LIVE_PBP_WAIT_SEC", "170"))
PBP_RECHECK_SEC = float(os.environ.get("NBA_LIVE_PBP_RECHECK_SEC", "60"))
# The archive's hourly purchase served the market 264 s before the hour.
FETCH_OFFSET_SEC = float(os.environ.get("NBA_LIVE_FETCH_OFFSET_SEC", "264"))
FETCH_WINDOW_SEC = float(os.environ.get("NBA_LIVE_FETCH_WINDOW_SEC", "240"))
RETRY_GAP_SEC = float(os.environ.get("NBA_LIVE_RETRY_GAP_SEC", "60"))
# ESPN's header score ahead of its play list: re-read once after this many
# seconds, then refuse the fetch for that game if they still differ.
HEADER_RECHECK_SEC = float(os.environ.get("NBA_LIVE_HEADER_RECHECK_SEC", "20"))
# While ESPN's clock is running, a newest play older than this means its play
# list has stopped: the fetch is refused for that game. The scoring plays'
# 99th-percentile publication lag (168 s) plus a minute between plays.
PLAY_LAG_MAX_SEC = float(os.environ.get("NBA_LIVE_PLAY_LAG_MAX_SEC", "230"))
HEARTBEAT_EVERY_SEC = 300.0
IDLE_EXIT_TICKS = int(os.environ.get("NBA_LIVE_IDLE_EXIT_TICKS", "3"))
FEED_FAIL_EXIT_TICKS = int(os.environ.get("NBA_LIVE_FEED_FAIL_EXIT_TICKS", "45"))
# A slate spans at most ~10 hourly fetch windows, each tried at most
# FETCH_WINDOW_SEC / RETRY_GAP_SEC + 1 = 5 times, so 100 calls is a ceiling no
# honest slate reaches; at the measured 2 credits a call that is 200 credits.
CALL_CAP = int(os.environ.get("NBA_LIVE_CALL_CAP", "100"))
CREDIT_CAP = int(os.environ.get("NBA_LIVE_CREDIT_CAP", "200"))
PRIOR_LOOKBACK_H = 36           # Pinnacle's pre-game rows read for the close (the search's pull)
LEDGER = "nba_live_decisions"
BULK_PURPOSE = "nba_live_bulk:h2h,spreads"


# ─── the cadence ──────────────────────────────────────────────────────────────

class Slots:
    """The grade's hourly purchase: every hour minus `offset` seconds. A fetch
    window opens at that instant and lasts `window` seconds; instant() is the
    window `now` is in, else None. Never built from a tip."""

    def __init__(self, offset: float = FETCH_OFFSET_SEC, window: float = FETCH_WINDOW_SEC):
        self.offset, self.window = float(offset), float(window)

    def instant(self, now: datetime) -> datetime | None:
        base = now.astimezone(timezone.utc) + timedelta(seconds=self.offset)
        inst = base.replace(minute=0, second=0, microsecond=0) - timedelta(seconds=self.offset)
        return inst if 0.0 <= (now - inst).total_seconds() <= self.window else None


@dataclass
class SlotState:
    """One fetch window: the games still to try (None until the first
    attempt), when the last attempt started, whether it is finished."""
    pending: set | None = None
    last_attempt: datetime | None = None
    attempts: int = 0
    closed: bool = False


# ─── platform context ─────────────────────────────────────────────────────────

@dataclass
class GameCtx:
    game_id: str
    game_date: str
    season: int
    home: str
    away: str
    tip: pd.Timestamp                 # games.commence_time, the listed tip
    espn_event_id: int | None = None
    mu_pre: float | None = None
    close: tuple | None = None        # (line, fa, close_at) of Pinnacle's pre-tip spread
    top: pd.DataFrame | None = None
    refused: str | None = None


def slate_games(conn, dates) -> dict[tuple, GameCtx]:
    """{(game_date, away, home): GameCtx} for the NBA games of the slate."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT game_id, game_date, season, home_team, away_team, commence_time
            FROM games WHERE sport = 'NBA' AND game_date = ANY(%s)
        """, (list(dates),)).fetchall()
    finally:
        release_read(conn)
    out = {}
    for gid, gd, season, home, away, ct in rows:
        tip = pd.to_datetime(ct, utc=True, format="mixed", errors="coerce") if ct else None
        if tip is None or pd.isna(tip):
            continue
        out[(str(gd)[:10], away, home)] = GameCtx(str(gid), str(gd)[:10], int(season), home, away, tip)
    return out


def load_prior(conn, ctx: GameCtx, art: M.Artifact) -> None:
    """Pinnacle's last coherent pre-tip spread -> ctx.mu_pre (M.pinnacle_close_spread).
    The SQL bound is loose text on purpose (stamps are mixed-format TEXT); the
    exact bound is applied on parsed timestamps by H.frame_quotes."""
    from data.db import release_read
    lo = (ctx.tip - timedelta(hours=PRIOR_LOOKBACK_H + 1)).strftime("%Y-%m-%dT%H:%M:%S")
    hi = (ctx.tip + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        cur = conn.execute("""
            SELECT bookmaker, market, snapshot_at, created_at, source, home_price, away_price,
                   spread_home, total_line, over_price, under_price
            FROM odds
            WHERE game_id = %s AND market = 'spreads' AND bookmaker = 'pinnacle'
              AND snapshot_at >= %s AND snapshot_at <= %s
        """, (ctx.game_id, lo, hi))
        rows = cur.fetchall()
    finally:
        release_read(conn)
    cols = ["bookmaker", "market", "snapshot_at", "created_at", "source", "home_price", "away_price",
            "spread_home", "total_line", "over_price", "under_price"]
    df = pd.DataFrame(rows, columns=cols)
    df["created_at"] = df["created_at"].astype(str)
    got = M.pinnacle_close_spread(df, {"game_id": ctx.game_id, "season": ctx.season,
                                       "game_date": ctx.game_date, "tip": ctx.tip})
    if got is None:
        ctx.refused = "no Pinnacle pre-tip spread close: no prior"
        return
    ctx.close = got
    ctx.mu_pre = M.prior_margin(art, got[0], got[1])


def load_top(conn, ctx: GameCtx, starters: pd.DataFrame) -> None:
    """IG-2's top players for this game: the live box's starters ranked by
    their minutes per game this season before today, else last season
    (nba_pbp_box of regular-season games)."""
    from data.db import release_read
    if starters is None or len(starters) == 0 or starters.groupby("side").size().min() < 3 \
            or starters["side"].nunique() < 2:
        return
    try:
        rows = conn.execute("""
            SELECT b.espn_id, b.minutes, g.game_date, b.season
            FROM nba_pbp_box b JOIN nba_pbp_games g ON g.espn_game_id = b.espn_game_id
            WHERE b.season = ANY(%s) AND g.season_type = 2 AND b.espn_id = ANY(%s)
        """, ([ctx.season - 1, ctx.season], [int(x) for x in starters["espn_id"]])).fetchall()
    finally:
        release_read(conn)
    hist = pd.DataFrame(rows, columns=["espn_id", "minutes", "game_date", "season"])
    ctx.top = M.top_players(ctx.game_id, int(ctx.espn_event_id), starters, hist, ctx.game_date, ctx.season)


# ─── the ledger, the picks, the gates ─────────────────────────────────────────

def ledger_ready(conn) -> bool:
    from data.db import release_read
    try:
        row = conn.execute("SELECT to_regclass('public.nba_live_decisions')").fetchone()
        return bool(row and row[0])
    finally:
        release_read(conn)


def decided_keys(conn, game_ids) -> set:
    """(game_id, model_id) of every DECISION the ledger holds (a 'skipped' or
    'carried' row is not one)."""
    from data.db import release_read
    if not game_ids:
        return set()
    try:
        rows = conn.execute(f"SELECT game_id, model_id FROM {LEDGER} "
                            f"WHERE game_id = ANY(%s) AND outcome IN ('bet', 'no_bet', 'declined')",
                            (sorted(game_ids),)).fetchall()
        return {(str(a), str(b)) for a, b in rows}
    finally:
        release_read(conn)


def seen_from_odds(conn, game_ids) -> set:
    """The earlier-fetch dedupe's memory across restarts: (game, market, book,
    stamp) of the loop's own in-play rows in `odds` (source nba_live_loop),
    read through idx_odds_source_inplay."""
    from data.db import release_read
    from data.ingestors.nba_live_feed import LIVE_SOURCE
    if not game_ids:
        return set()
    try:
        rows = conn.execute("""
            SELECT game_id, market, bookmaker, snapshot_at FROM odds
            WHERE source = %s AND snapshot_type = 'in_play'
              AND game_id = ANY(%s) AND market IN ('h2h', 'spreads')
        """, (LIVE_SOURCE, sorted(game_ids))).fetchall()
    finally:
        release_read(conn)
    out = set()
    for gid, mk, book, at in rows:
        t = pd.to_datetime(str(at), utc=True, format="mixed", errors="coerce")
        if pd.notna(t):
            out.add((str(gid), str(mk), str(book), t))
    return out


def ledger_row(ctx: GameCtx, rule: M.Rule, d: M.Decision | None, outcome: str, reason: str,
               fetch_at, state: dict, play_lag, version: str) -> dict:
    p = (d.pick if d is not None else None) or {}
    offers = None
    if d is not None and d.offers is not None and len(d.offers):
        keep = [c for c in ("book", "side", "line", "price", "ev", "p_win", "p_push", "side_pick", "stamp")
                if c in d.offers]
        recs = d.offers[keep].astype(object).where(d.offers[keep].notna(), None).to_dict("records")
        offers = json.dumps(recs, default=str)          # a missing value is null, never "None"

    def num(x):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(v) else v
    return {"game_id": ctx.game_id, "model_id": rule.model_id, "game_date": ctx.game_date,
            "fetch_at": fetch_at, "outcome": outcome, "reason": reason[:500], "phase": rule.phase,
            "market": rule.market, "book": p.get("book"), "side": p.get("side"),
            "line": num(p.get("line")), "price": num(p.get("price")), "ev": num(p.get("ev")),
            "p_win": num(p.get("p_win")), "p_push": num(p.get("p_push")),
            "model_mean": num(p.get("mean", state.get("mean"))), "model_sd": num(p.get("sd", state.get("sd"))),
            "p_home": num(p.get("p_home", state.get("p_home"))), "mu_pre": num(ctx.mu_pre),
            "period": state.get("period"), "clock_s": num(state.get("clock_s")),
            "h_pts": state.get("h_pts"), "a_pts": state.get("a_pts"),
            "play_lag_s": num(play_lag), "artifact_version": version, "offers": offers}


LEDGER_COLS = ("game_id", "model_id", "game_date", "fetch_at", "outcome", "reason", "phase", "market",
               "book", "side", "line", "price", "ev", "p_win", "p_push", "model_mean", "model_sd",
               "p_home", "mu_pre", "period", "clock_s", "h_pts", "a_pts", "play_lag_s",
               "artifact_version", "offers")


def insert_ledger(conn, row: dict) -> bool:
    """One row. A decision returns False when (game, model) already holds one:
    the first decision stands, nothing is replaced. A 'skipped' or 'carried'
    row is always written (one per attempt)."""
    cols = ", ".join(LEDGER_COLS)
    vals = ", ".join(f"%({c})s" for c in LEDGER_COLS)
    params = {c: row.get(c) for c in LEDGER_COLS}
    if row.get("outcome") in ("skipped", "carried"):
        cur = conn.execute(f"INSERT INTO {LEDGER} ({cols}) VALUES ({vals}) RETURNING game_id", params)
    else:
        cur = conn.execute(f"INSERT INTO {LEDGER} ({cols}) VALUES ({vals}) "
                           f"ON CONFLICT (game_id, model_id) WHERE outcome IN ('bet', 'no_bet', 'declined') "
                           f"DO NOTHING RETURNING game_id", params)
    return cur.fetchone() is not None


def live_destination() -> str | None:
    """Where an NBA live pick posts: DISCORD_WEBHOOK_LIVE_NBA or
    DISCORD_CHANNEL_LIVE_NBA, else None. NBA live picks never fall back to the
    shared live channel or the pre-game #nba channel
    (config.DISCORD_LIVE_CHANNEL_REQUIRED), so with neither set a bet would
    never post: the loop refuses to decide."""
    import config
    if config.DISCORD_WEBHOOKS_LIVE.get(SPORT):
        return "DISCORD_WEBHOOK_LIVE_NBA"
    if (getattr(config, "DISCORD_CHANNELS_LIVE", None) or {}).get(SPORT):
        return "DISCORD_CHANNEL_LIVE_NBA"
    return None


def platform_gates(model_id: str, prob: float, price: float) -> str | None:
    """The platform's own gates on top of the rule, read at call time. None =
    clears. Set in config.py so neither can bind beyond the rule; consulted so
    a later change there reaches this loop."""
    import config
    if price < config.min_odds_for(model_id):
        return f"price {price:+.0f} under the floor {config.min_odds_for(model_id):+.0f}"
    ev = config.expected_value(prob, price)
    if ev is not None and ev < config.min_ev_for(model_id):
        return f"EV {ev:.3f} under the floor {config.min_ev_for(model_id):.3f}"
    cut = config.ACTION_THRESHOLDS.get(model_id, {})
    if prob < float(cut.get("min_prob", 0.0)):
        return f"probability {prob:.3f} under min_prob {cut.get('min_prob')}"
    if model_id in getattr(config, "PAUSED_MODELS", ()):
        return "model is paused (config.PAUSED_MODELS)"
    return None


def standing_bets(conn, game_id: str) -> list[dict]:
    """This game's standing live BETs of the live rules, as conflict dicts."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT model_id, pick_side, scored_line, pick_label FROM picks
            WHERE game_id = %s AND is_live = TRUE AND signal_type = 'BET'
              AND model_id = ANY(%s)
              AND condition_status IS DISTINCT FROM 'VOID'
        """, (game_id, list(M.MODEL_IDS))).fetchall()
    finally:
        release_read(conn)
    return [{"model_id": m, "market": M.RULE_BY_ID[m].market, "side": s,
             "line": None if ln is None else float(ln), "label": lb} for m, s, ln, lb in rows]


def build_pick(ctx: GameCtx, rule: M.Rule, d: M.Decision, state: dict, links: dict,
               bankroll: float) -> dict:
    """One `picks` row from one BET (the NFL live loop's dict shape; every key
    _insert_picks binds by name present). model_probability is P(win | no
    push); the DraftKings columns keep their reference meaning (DraftKings'
    own quote on the same side at the same number in this fetch). With no
    such quote, dk_odds is NULL and dk_implied_prob and edge are 0.0, the
    scorer's line_book convention (models/scorer.py): picks.dk_implied_prob
    is NOT NULL in production, and a NULL there lost UTA +5.5 at Hard Rock
    on the 2026-11-06 slate (the insert failed, so neither the pick nor its
    ledger row was written)."""
    from models.scorer import _confidence_tier, quarter_kelly
    p = d.pick
    side, book, price = p["side"], p["book"], float(p["price"])
    line = None if rule.market == "h2h" else float(p["line"])
    prob = M.prob_no_push(p["p_win"], p.get("p_push", 0.0))
    implied = 1.0 / M.american_to_decimal(price)
    dk = None
    if d.offers is not None:
        o = d.offers[(d.offers["book"] == "draftkings") & (d.offers["side"] == side)]
        if rule.market == "spreads" and len(o):
            o = o[(o["line"] - line).abs() < 1e-9]
        if len(o):
            dk = o.sort_values("ev", ascending=False).iloc[0]
    dk_odds = None if dk is None else float(dk["price"])
    dk_implied = None if dk is None else 1.0 / M.american_to_decimal(dk_odds)
    dk_prob = None if dk is None else M.prob_no_push(dk["p_win"], dk.get("p_push", 0.0))
    edge = 0.0 if dk is None else dk_prob - dk_implied
    kf, rec = quarter_kelly(prob, implied, bankroll)
    link = links.get((book, side))
    return {
        "game_id": ctx.game_id, "model_id": rule.model_id, "sport": SPORT,
        "game_date": ctx.game_date, "game_time": ctx.tip.isoformat(),
        "pick_side": side, "pick_label": M.pick_label(rule, side, line, ctx.home, ctx.away),
        "model_probability": round(prob, 4),
        "dk_implied_prob": 0.0 if dk_implied is None else round(dk_implied, 4),
        "edge": round(edge, 4), "dk_odds": dk_odds,
        "scored_line": line,                      # the HOME number (CLAUDE.md section 4)
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "injury_flag": None, "injury_detail": None,
        "signal_type": "BET", "confidence_tier": _confidence_tier(prob - implied),
        "is_live": True,
        "inning_at_pick": state.get("period"),     # the quarter, in the shared column
        "score_diff_at_pick": state.get("diff"),   # home minus away
        "dk_bet_link": links.get(("draftkings", side)) if dk is not None else None,
        "best_book": book, "best_odds": price, "best_implied_prob": round(implied, 4),
        "best_edge": round(prob - implied, 4), "best_bet_link": link,
        # NULL = DraftKings set the line: true of a moneyline, and of a spread
        # DraftKings hangs at the same number in this fetch.
        "line_book": None if (rule.market == "h2h" or dk is not None or book == "draftkings") else book,
        "decision_book": book, "decision_odds": price,
        "decision_implied_prob": round(implied, 4), "decision_edge": round(prob - implied, 4),
    }


def write_bet(conn, pick: dict) -> bool:
    """Insert one BET under the first-signal live lock. False when this game
    already carries the model's unsettled live BET (it stands; nothing is
    deleted or replaced, ever)."""
    from data.db import release_read
    from models.scorer import _insert_picks, _locked_live_lanes
    if _locked_live_lanes(conn, pick["game_id"], (pick["model_id"],)):
        log.info("SKIPPED %s %s - locked at its first BET", pick["model_id"], pick["pick_label"])
        release_read(conn)
        return False
    _insert_picks(conn, [pick])
    return True


def unsettled_bet_dates(conn) -> set[str]:
    """Slate dates holding an unsettled live BET of the live rules: every
    launch announces them, so a post that failed is retried until graded."""
    from data.db import release_read
    since = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
    try:
        rows = conn.execute("""
            SELECT DISTINCT game_date FROM picks
            WHERE model_id = ANY(%s) AND is_live = TRUE
              AND signal_type = 'BET' AND result IS NULL AND game_date >= %s
        """, (list(M.MODEL_IDS), since)).fetchall()
        return {str(r[0])[:10] for r in rows}
    finally:
        release_read(conn)


def notify_live(target_date: str) -> None:
    """Push, then Discord's NBA live channel (DISCORD_WEBHOOK_LIVE_NBA, the
    fallback chain in tracking.discord_notifier). Both dedupe through their
    ledgers; neither may break the loop."""
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


def record_credits(conn, credits: int | None) -> None:
    if credits is None:
        return
    from data.ingestors.live_odds_ingestor import record_credits as rec
    rec(conn, BULK_PURPOSE, int(credits))
    conn.commit()


def under_daily_cap(conn, cost: int) -> bool:
    """The platform's shared in-play cap (config.LIVE_DAILY_CREDIT_CAP over
    live_credit_telemetry): the MLB loop's guard, respected here."""
    from data.db import release_read
    from data.ingestors.live_odds_ingestor import credits_used_today
    from data.ingestors.live_trigger_orchestrator import under_credit_cap
    try:
        return under_credit_cap(credits_used_today(conn), cost)
    finally:
        release_read(conn)


# ─── one slot ─────────────────────────────────────────────────────────────────

def state_of(el: pd.DataFrame) -> dict:
    r = el.sort_values("stamp").iloc[0]
    return {"period": int(r["period"]) if pd.notna(r.get("period")) else None,
            "clock_s": r.get("clock_s"), "h_pts": int(r["h_pts"]), "a_pts": int(r["a_pts"]),
            "diff": int(r["h_pts"] - r["a_pts"])}


def evaluate_game(ctx: GameCtx, art: M.Artifact, q: pd.DataFrame, summary: dict,
                  undecided: list[M.Rule], games_frame: pd.DataFrame,
                  now: datetime | None = None) -> tuple[list, dict]:
    """Every undecided rule of one game against one fetch. `q` is this game's
    quotes of the fetch (M.fetch_quotes, run ONCE per fetch for every game, so
    the earlier-fetch dedupe never sees a sibling game's rows as old).
    Returns ([(rule, Decision, state)], notes); a rule with no eligible quote
    in this fetch is absent (not a decision)."""
    from data.ingestors.nba_live_feed import plays_from_summary
    from scripts import nba_s_ingame27 as L
    notes: dict = {}
    got = plays_from_summary(summary, ctx.espn_event_id, ctx.game_id, ctx.season, ctx.game_date,
                             ctx.home, ctx.away)
    if got is None:
        return [], {"refused": "ESPN summary unreadable for this game"}
    play_rows, _swapped = got
    pbp = pd.DataFrame(play_rows)
    if pbp.empty:
        return [], {"refused": "no plays yet"}
    newest = pd.to_datetime(pbp["wallclock"], utc=True, format="mixed", errors="coerce").max()
    now = now or datetime.now(timezone.utc)
    notes["play_lag_s"] = (now - newest).total_seconds() if pd.notna(newest) else None
    plays, wild = L.live_plays(pbp)
    if wild:
        return [], {**notes, "refused": f"a play 4+ hours from the game's median wallclock: {wild}"}
    q = q[q["game_id"] == ctx.game_id]
    if q.empty:
        return [], {**notes, "refused": "no quote for this game in the fetch"}
    qt, pn = M.prepare(q, plays, pbp, ctx.top, games_frame)
    notes.update({k: v for k, v in pn.items() if k in ("games_first_play_before_listed_tip",
                                                       "games_wallclock_jump", "rule34_dropped")})
    out = []
    for rule in undecided:
        el = M.eligible_for(qt, rule)
        if el.empty:
            continue
        d = M.decide(el, rule, art.models, ctx.mu_pre)
        if d is not None:
            # a bet's state is its own quote's (each quote is priced at the state
            # at its own stamp); a no-bet records the fetch's earliest quote's
            st = state_of(pd.DataFrame([d.pick])) if d.pick else state_of(el)
            if d.pick:
                st.update({"mean": d.pick.get("mean"), "sd": d.pick.get("sd"), "p_home": d.pick.get("p_home")})
            out.append((rule, d, st))
    return out, notes


def resolve_conflicts(decisions: list, standing: list[dict]) -> dict:
    """{model_id: reason} for this pass's bets that the one-game rule declines
    (mike, 2026-10-17: "It can't be both")."""
    bets = [(r, d) for r, d, _s in decisions if d.bet]
    why = {}
    for r, d in bets:
        mine = {"market": r.market, "side": d.pick["side"],
                "line": None if r.market == "h2h" else float(d.pick["line"])}
        held = next((s for s in standing if M.cannot_both_win(mine, s)), None)
        if held is not None:
            why[r.model_id] = f"cannot both win with {held['label']}, already bet on this game"
    rest = [(r, d) for r, d in bets if r.model_id not in why]
    for i, (ra, da) in enumerate(rest):
        for rb, db in rest[i + 1:]:
            a = {"market": ra.market, "side": da.pick["side"],
                 "line": None if ra.market == "h2h" else float(da.pick["line"])}
            b = {"market": rb.market, "side": db.pick["side"],
                 "line": None if rb.market == "h2h" else float(db.pick["line"])}
            if M.cannot_both_win(a, b):
                why.setdefault(ra.model_id, f"cannot both win with {rb.model_id}, decided in the same pass")
                why.setdefault(rb.model_id, f"cannot both win with {ra.model_id}, decided in the same pass")
    return why


# ─── the loop ─────────────────────────────────────────────────────────────────

class Loop:
    """One process's state across a slate. tick() is one pass; the feeds and
    the connection factory are injected so a test can drive a whole window."""

    def __init__(self, art: M.Artifact, espn, feed, connect, *, dry_run: bool = False,
                 wait: float = PBP_WAIT_SEC, recheck: float = PBP_RECHECK_SEC, sleep=time.sleep,
                 clock=None, slate_dates=None, slots: Slots | None = None):
        self.art, self.espn, self.feed, self.connect = art, espn, feed, connect
        self.dry_run, self.wait, self.recheck, self.sleep = dry_run, float(wait), float(recheck), sleep
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.slate_dates = slate_dates
        self.conn = None
        self.slots = slots or Slots()
        self.windows: dict[datetime, SlotState] = {}
        self.ctxs: dict[tuple, GameCtx] = {}
        self.decided: set = set()             # (game_id, model_id)
        self.seen: set = set()                # (game, market, book, stamp) of earlier fetches
        self.seeded: set = set()              # game ids whose seen-stamps were read from odds
        self.bet_dates: set = set()
        self.bets_written = 0
        self.bankroll = None
        self.last_slate_read = 0.0
        self.last_beat = None
        self.blocked = None                   # why the loop refuses to decide, once known

    # connection helpers
    def c(self):
        if self.conn is None:
            self.conn = self.connect()
        return self.conn

    def recycle(self):
        self.conn = _recycle(self.conn)

    def dates(self) -> list[str]:
        import config
        return list(self.slate_dates() if self.slate_dates else config.live_slate_dates())

    # one pass
    def scoreboards(self) -> list | None:
        boards, answered = [], 0
        for d in self.dates():
            b = self.espn.scoreboard(d)
            if b is not None:
                answered += 1
                boards.extend(b)
        return boards if answered else None

    def match(self, live: list) -> list[tuple[GameCtx, object]]:
        """Our slate game for each ESPN game in progress: the same two teams
        (either way round) and a listed tip within 6 hours. Exactly one or
        the game is not priced: a guessed game_id writes a bet that never
        settles."""
        def unmatched():
            pairs = {(c.home, c.away) for c in self.ctxs.values()}
            return [g for g in live if (g.home, g.away) not in pairs and (g.away, g.home) not in pairs]
        if (not self.ctxs or unmatched()) and time.monotonic() - self.last_slate_read >= 60:
            try:
                for k, ctx in slate_games(self.c(), self.dates()).items():
                    self.ctxs.setdefault(k, ctx)
                self.last_slate_read = time.monotonic()
            except Exception as exc:                  # noqa: BLE001
                log.error("slate read failed: %s", exc)
                self.recycle()
        out = []
        for g in live:
            cands = [c for c in self.ctxs.values()
                     if (c.home, c.away) in ((g.home, g.away), (g.away, g.home))]
            t = pd.to_datetime(g.commence, utc=True, errors="coerce") if g.commence else None
            if t is not None and pd.notna(t):
                cands = [c for c in cands if abs((c.tip - t).total_seconds()) <= 6 * 3600]
            if len(cands) != 1:
                log.warning("ESPN event %s %s @ %s matches %d slate games - not priced",
                            g.event_id, g.away, g.home, len(cands))
                continue
            cands[0].espn_event_id = g.event_id
            out.append((cands[0], g))
        return out

    def heartbeat(self, in_play: int) -> None:
        """The job's heartbeat while a slate runs. The scheduler beats only
        when a launch returns, and one launch runs a whole slate, so the loop
        beats itself every HEARTBEAT_EVERY_SEC: a hang during the slate goes
        silent and tracking.job_heartbeat's active hours flag it that evening."""
        if self.dry_run:
            return
        t = time.monotonic()
        if self.last_beat is not None and t - self.last_beat < HEARTBEAT_EVERY_SEC:
            return
        self.last_beat = t
        try:
            from tracking.job_heartbeat import beat
            beat("nba_live", "ok", f"running: {in_play} game(s) in play, {self.bets_written} bet(s) written")
        except Exception as exc:                      # noqa: BLE001
            log.warning("heartbeat failed (non-fatal): %s", exc)

    def seed_seen(self, game_ids) -> None:
        """The earlier-fetch dedupe survives a restart: stamps the loop already
        fetched for these games, read once per game from its own odds rows."""
        new = set(game_ids) - self.seeded
        if not new:
            return
        try:
            self.seen |= seen_from_odds(self.c(), new)
            self.seeded |= new
        except Exception as exc:                      # noqa: BLE001
            log.warning("could not seed the earlier-fetch dedupe (retried next window): %s", exc)
            self.recycle()

    def open_rules(self, ctx: GameCtx, g) -> list[M.Rule]:
        """The rules not yet decided on this game whose phase can still hold a
        fresh quote (a quarter-3 quote can sit in a fetch early in quarter 4)."""
        last_period = {"Q1-Q2": 3, "Q3": 4}
        return [r for r in M.RULES if (ctx.game_id, r.model_id) not in self.decided
                and (g.period is None or g.period <= last_period[r.phase])]

    def summary(self, event_id, tries: int = 3, gap_s: float = 5.0):
        """ESPN's summary, read up to `tries` times `gap_s` apart (a dropped TLS
        connection is common: 2 of 217 reads on 2026-11-04). None when every
        read failed."""
        for k in range(tries):
            got = self.espn.summary(event_id)
            if got is not None:
                return got
            if k + 1 < tries:
                self.sleep(gap_s)
        return None

    def note(self, c: GameCtx, g, outcome: str, reason: str, fetch_at=None) -> str:
        """A row per open rule for an attempt that decided nothing: 'skipped'
        (could not decide; the window retries) or 'carried' (no eligible
        quote; the next hour tries)."""
        rules = self.open_rules(c, g)
        (log.warning if outcome == "skipped" else log.info)(
            "%s %s (%s): %s", outcome.upper(), c.game_id, ", ".join(r.model_id for r in rules), reason)
        if not self.dry_run:
            try:
                for r in rules:
                    insert_ledger(self.c(), ledger_row(c, r, None, outcome, reason, fetch_at, {}, None,
                                                       self.art.version))
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("could not record the %s row for %s: %s", outcome, c.game_id, exc)
                self.recycle()
        return outcome

    def skip(self, c: GameCtx, g, reason: str, fetch_at=None) -> str:
        return self.note(c, g, "skipped", reason, fetch_at)

    def carry(self, c: GameCtx, g, reason: str, fetch_at=None) -> str:
        return self.note(c, g, "carried", reason, fetch_at)

    def tick(self) -> dict:
        """One pass. Returns {'live': n, 'slot': window or None, 'decisions': n}
        or {'live': None} when no scoreboard answered."""
        now = self.clock()
        boards = self.scoreboards()
        if boards is None:
            return {"live": None}
        live = [g for g in boards if g.state == "in" and g.season_type in (2, None)]
        if not live:
            return {"live": 0}
        in_play = self.match(live)
        self.heartbeat(len(in_play))
        inst = self.slots.instant(now)
        res = {"live": len(live), "slot": inst, "decisions": 0}
        if inst is None:
            return res
        if live_destination() is None:
            self.blocked = ("neither DISCORD_WEBHOOK_LIVE_NBA nor DISCORD_CHANNEL_LIVE_NBA is set on this "
                            "service: an NBA live bet would never post, so none is decided")
            res["blocked"] = self.blocked
            return res
        st = self.windows.setdefault(inst, SlotState())
        if st.closed or (st.last_attempt is not None
                         and (now - st.last_attempt).total_seconds() < RETRY_GAP_SEC):
            return res
        if not self.dry_run:
            try:
                self.decided |= decided_keys(self.c(), {c.game_id for c, _g in in_play})
            except Exception as exc:                  # noqa: BLE001
                # Nothing can be recorded either: the window retries next tick.
                log.error("ledger read failed - window %s not tried this tick: %s", inst.isoformat(), exc)
                self.recycle()
                return res
        todo = [(c, g) for c, g in in_play if c.refused is None and self.open_rules(c, g)
                and (st.pending is None or c.game_id in st.pending)]
        if not todo:
            st.closed = True
            return res
        self.seed_seen({c.game_id for c, _g in todo})
        st.last_attempt = now
        st.attempts += 1
        n, outcomes = self.run_slot(inst, todo)
        st.pending = {gid for gid, o in outcomes.items() if o == "skipped"}
        st.closed = not st.pending
        res["decisions"] = n
        return res

    # one attempt in a window
    def run_slot(self, slot: datetime, todo: list) -> tuple[int, dict]:
        out: dict = {}
        for c, g in todo:
            if c.mu_pre is None and c.refused is None:
                try:
                    load_prior(self.c(), c, self.art)
                except Exception as exc:              # noqa: BLE001
                    self.recycle()
                    out[c.game_id] = self.skip(c, g, f"prior read failed: {type(exc).__name__}")
                    continue
                if c.refused:
                    log.warning("%s refused: %s", c.game_id, c.refused)
                    out[c.game_id] = "refused"
        todo = [(c, g) for c, g in todo if c.game_id not in out and c.refused is None and c.mu_pre is not None]
        if not todo:
            return 0, out
        if not self.dry_run:
            try:
                ok = under_daily_cap(self.c(), 2)
            except Exception as exc:                  # noqa: BLE001
                self.recycle()
                ok, why = False, f"credit cap read failed: {type(exc).__name__}"
            else:
                why = "LIVE_DAILY_CREDIT_CAP would be exceeded"
            if not ok:
                for c, g in todo:
                    out[c.game_id] = self.skip(c, g, why)
                return 0, out
        if self.dry_run:
            # A dry run makes no paid call: it names the window and the games
            # it would fetch for, and decides nothing.
            log.info("[dry-run] window %s: would fetch the board for %s", slot.isoformat(),
                     ", ".join(c.game_id for c, _g in todo))
            return 0, {**out, **{c.game_id: "carried" for c, _g in todo}}
        fetch = self.feed.fetch()
        if fetch is None:
            for c, g in todo:
                out[c.game_id] = self.skip(c, g, "no odds from the feed (call failed, a cap, or the quota floor)")
            return 0, out
        try:
            return self._after_fetch(slot, todo, fetch, out)
        except Exception as exc:                      # noqa: BLE001
            log.exception("window %s failed after the fetch: %s", slot.isoformat(), exc)
            self.recycle()
            for c, g in todo:
                if c.game_id not in out:
                    out[c.game_id] = self.skip(c, g, f"the fetch could not be read: {type(exc).__name__}: {exc}",
                                               fetch.fetched_at)
            return 0, out

    def _after_fetch(self, slot: datetime, todo: list, fetch, out: dict) -> tuple[int, dict]:
        from data.ingestors.nba_live_feed import clock_running, late_plays, rows_from_events, score_mismatch
        if not self.dry_run:
            try:
                record_credits(self.c(), fetch.credits)
            except Exception as exc:                  # noqa: BLE001
                log.warning("credit telemetry failed (non-fatal): %s", exc)
                self.recycle()
        known = {c.game_id for c in self.ctxs.values()}
        rows_all = [r for r in rows_from_events(fetch.events, fetch.fetched_at) if r["game_id"] in known]
        if rows_all and not self.dry_run:
            try:
                from data.ingestors.live_price_log import record_live_prices
                record_live_prices(self.c(), rows_all, known_game_ids=known)
            except Exception as exc:                  # noqa: BLE001
                log.warning("live price log failed (non-fatal): %s", exc)
                self.recycle()
        rows = pd.DataFrame(rows_all)
        if rows.empty:
            for c, g in todo:
                out[c.game_id] = self.carry(c, g, "the fetch holds no row for this game", fetch.fetched_at)
            return 0, out
        rows["created_at"] = fetch.fetched_at.isoformat()
        gframe = pd.DataFrame([{"game_id": c.game_id, "season": c.season, "game_date": c.game_date,
                                "tip": c.tip} for c in self.ctxs.values()])
        # The earlier-fetch dedupe learns this fetch's stamps only for the games
        # this attempt settles (decided or carried). A skipped game's quotes were
        # never evaluated, so its retry inside the window must still see them.
        seen_now = set(self.seen)
        q_all, _dropped, _qn = M.fetch_quotes(rows, gframe, seen_now)
        fresh_stamps = seen_now - self.seen
        served = q_all["served_at"].max() if len(q_all) else pd.Timestamp(fetch.fetched_at)
        served = pd.Timestamp(served).to_pydatetime()
        have = set(q_all["game_id"]) if len(q_all) else set()
        for c, g in todo:
            if c.game_id not in have:
                out[c.game_id] = self.carry(c, g, "no quote for this game in the fetch", fetch.fetched_at)
        todo = [(c, g) for c, g in todo if c.game_id in have]
        if not todo:
            return 0, out
        left = self.wait - (self.clock() - fetch.fetched_at).total_seconds()
        if left > 0:
            self.sleep(left)
        first = {c.game_id: self.summary(c.espn_event_id) for c, _g in todo}
        if self.recheck > 0:
            self.sleep(self.recheck)
        n = 0
        for c, g in todo:
            try:
                second = self.summary(c.espn_event_id)
                if first.get(c.game_id) is None or second is None:
                    out[c.game_id] = self.skip(c, g, "ESPN summary unreadable", fetch.fetched_at)
                    continue
                late = late_plays(first[c.game_id], second, served)
                if late:
                    out[c.game_id] = self.skip(
                        c, g, f"ESPN served {len(late)} play(s) logged at or before the served time only on "
                              f"the second read, {self.recheck:.0f} s after the first (publishing late)",
                        fetch.fetched_at)
                    continue
                why = score_mismatch(second)
                if why:
                    self.sleep(HEADER_RECHECK_SEC)
                    third = self.summary(c.espn_event_id)
                    why = "ESPN summary unreadable" if third is None else score_mismatch(third)
                    if not why and late_plays(second, third, served):
                        why = "ESPN served a play logged before the served time only on the header re-read"
                    if why:
                        out[c.game_id] = self.skip(c, g, f"{why}, still after {HEADER_RECHECK_SEC:.0f} s",
                                                   fetch.fetched_at)
                        continue
                    second = third
                running = clock_running(first[c.game_id], second)
                k, outcome = self.decide_game(slot, fetch, c, g, rows, q_all, gframe, second, running)
            except Exception as exc:                  # noqa: BLE001
                log.exception("%s failed: %s", c.game_id, exc)
                self.recycle()
                k, outcome = 0, self.skip(c, g, f"evaluation failed: {type(exc).__name__}: {exc}",
                                          fetch.fetched_at)
            n += k
            out[c.game_id] = outcome
        settled = {gid for gid, o in out.items() if o != "skipped"}
        self.seen |= {k for k in fresh_stamps if k[0] in settled}
        return n, out

    def decide_game(self, slot, fetch, c: GameCtx, g, rows: pd.DataFrame, q_all: pd.DataFrame,
                    gframe: pd.DataFrame, summary: dict, running: bool = False) -> tuple[int, str]:
        """(decisions written, 'decided' | 'carried' | 'refused' | 'skipped')."""
        if c.top is None:
            try:
                load_top(self.c(), c, _starters(summary, c, g))
            except Exception as exc:                  # noqa: BLE001
                self.recycle()
                return 0, self.skip(c, g, f"top players failed: {type(exc).__name__}", fetch.fetched_at)
        if c.top is None:
            return 0, self.skip(c, g, "fewer than 3 starters a side in ESPN's box", fetch.fetched_at)
        try:
            decs, notes = evaluate_game(c, self.art, q_all, summary, self.open_rules(c, g), gframe,
                                        now=self.clock())
        except Exception as exc:                      # noqa: BLE001
            log.exception("evaluation failed for %s: %s", c.game_id, exc)
            return 0, self.skip(c, g, f"evaluation failed: {type(exc).__name__}: {exc}", fetch.fetched_at)
        if notes.get("games_first_play_before_listed_tip") or notes.get("games_wallclock_jump"):
            c.refused = (f"clock rule: first play before tip {notes.get('games_first_play_before_listed_tip')}, "
                         f"jump {notes.get('games_wallclock_jump')}")
            log.warning("%s refused for the rest of the game: %s", c.game_id, c.refused)
            return 0, "refused"
        if notes.get("refused"):
            # an unreadable or wild ESPN play-by-play: retried inside the window
            return 0, self.skip(c, g, notes["refused"], fetch.fetched_at)
        lag = notes.get("play_lag_s")
        if running and lag is not None and lag > PLAY_LAG_MAX_SEC:
            return 0, self.skip(c, g, f"ESPN's newest play is {lag:.0f} s old while its clock is running "
                                      f"(bound {PLAY_LAG_MAX_SEC:.0f} s): its play list has stopped",
                                fetch.fetched_at)
        if not decs:
            return 0, self.carry(c, g, f"no eligible quote (play_lag {notes.get('play_lag_s')} s)",
                                 fetch.fetched_at)
        try:
            standing = [] if self.dry_run else standing_bets(self.c(), c.game_id)
        except Exception as exc:                      # noqa: BLE001
            self.recycle()
            return 0, self.skip(c, g, f"standing-bet read failed: {type(exc).__name__}", fetch.fetched_at)
        conflicts = resolve_conflicts(decs, standing)
        links = {}
        for r_ in rows[rows["game_id"] == c.game_id].to_dict("records"):
            links.setdefault((r_["bookmaker"], "home"), r_.get("home_link"))
            links.setdefault((r_["bookmaker"], "away"), r_.get("away_link"))
        n = 0
        for rule, d, st in decs:
            outcome, reason, pick = ("bet", "BET", None) if d.bet else ("no_bet", d.reason, None)
            if d.bet:
                if rule.model_id in conflicts:
                    outcome, reason = "declined", conflicts[rule.model_id]
                else:
                    if self.bankroll is None and not self.dry_run:
                        try:
                            from models.scorer import _get_current_bankroll
                            self.bankroll = float(_get_current_bankroll(self.c()))
                        except Exception as exc:      # noqa: BLE001
                            log.warning("bankroll read failed (sizing at 0): %s", exc)
                            self.recycle()
                    try:
                        pick = build_pick(c, rule, d, st, links, self.bankroll or 0.0)
                        why = platform_gates(rule.model_id, pick["model_probability"], pick["decision_odds"])
                    except Exception as exc:          # noqa: BLE001
                        log.exception("building the %s pick failed: %s", rule.model_id, exc)
                        pick, why = None, f"the pick could not be built: {type(exc).__name__}: {exc}"
                    if why:
                        outcome, reason, pick = "declined", why, None
            log.info("DECIDED %s %s %s @ %s Q%s %s-%s mu_pre=%.2f play_lag=%s: %s %s", rule.model_id,
                     c.game_id, c.away, c.home, st.get("period"), st.get("h_pts"), st.get("a_pts"), c.mu_pre,
                     notes.get("play_lag_s"), outcome.upper(),
                     f"{pick['pick_label']} {pick['decision_book']} {pick['decision_odds']:+.0f}" if pick else reason)
            self.decided.add((c.game_id, rule.model_id))
            n += 1
            if self.dry_run:
                continue
            try:
                row = ledger_row(c, rule, d, outcome, reason, fetch.fetched_at, st,
                                 notes.get("play_lag_s"), self.art.version)
                if not insert_ledger(self.c(), row):
                    self.c().rollback()
                    log.info("%s %s already decided - nothing written", c.game_id, rule.model_id)
                    continue
                if pick is not None and write_bet(self.c(), pick):
                    self.bets_written += 1
                    self.bet_dates.add(c.game_date)
                    log.info("WROTE BET %s %s at %s %+.0f", rule.model_id, pick["pick_label"],
                             pick["decision_book"], pick["decision_odds"])
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("write failed for %s %s (non-fatal): %s", c.game_id, rule.model_id, exc)
                self.recycle()
        return n, "decided"


def main(argv=None) -> int:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-live")
    except Exception:                                 # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=POLL_SEC)
    ap.add_argument("--wait", type=float, default=PBP_WAIT_SEC)
    ap.add_argument("--recheck", type=float, default=PBP_RECHECK_SEC)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    import config
    from data.db import get_connection, use_poller_session
    from data.ingestors.nba_live_feed import Espn, LiveOddsFeed
    for mid in M.MODEL_IDS:
        if mid not in config.LIVE_MODELS:
            log.error("%s is not in config.LIVE_MODELS: it would never settle - exiting", mid)
            return 1
    art = M.load_artifact()
    log.info("artifact %s; rules %s; EV cut %s; floor %s; fetch at each hour minus %.0fs (window %.0fs); "
             "ESPN read %.0fs after a fetch and again %.0fs later",
             art.version, ", ".join(M.MODEL_IDS), {m: M.rule_cut(m) for m in M.MODEL_IDS},
             {m: M.rule_floor(m) for m in M.MODEL_IDS}, FETCH_OFFSET_SEC, FETCH_WINDOW_SEC, a.wait, a.recheck)
    use_poller_session()
    loop = Loop(art, Espn(), LiveOddsFeed(CALL_CAP, CREDIT_CAP), get_connection,
                dry_run=a.dry_run, wait=a.wait, recheck=a.recheck)
    if not a.dry_run:
        try:
            if not ledger_ready(loop.c()):
                log.error("table %s is missing (data/migrations/nba_live_decisions_2026_11_04.sql, applied "
                          "by data.view_migrations): no decision can be recorded, so none is made - exiting",
                          LEDGER)
                return 1
            loop.bet_dates |= unsettled_bet_dates(loop.c())
        except Exception as exc:                      # noqa: BLE001
            log.error("startup read failed: %s", exc)
            return 1
    idle = fails = 0
    last_notify = None
    announced = 0
    try:
        while True:
            started = time.monotonic()
            res = loop.tick()
            if res.get("blocked"):
                log.error("NBA LIVE DECIDES NOTHING: %s. Set one of them on this service and redeploy "
                          "(docs/cloud_worker.md). Exiting with code 3 so the job reads failed.", res["blocked"])
                return 3
            if res.get("live") is None:
                fails += 1
                if fails >= FEED_FAIL_EXIT_TICKS:
                    log.error("ESPN scoreboard unreachable for %d ticks - exiting", fails)
                    return 1
            else:
                fails = 0
            if res.get("live") == 0:
                idle += 1
                if idle >= IDLE_EXIT_TICKS or a.once:
                    if loop.bet_dates and not a.dry_run:
                        for d_ in sorted(loop.bet_dates):
                            notify_live(d_)
                    log.info("no NBA game in progress for %d tick(s) - exiting (%d BETs written, %d odds "
                             "calls, %d credits)", idle, loop.bets_written, loop.feed.calls,
                             loop.feed.credits_used)
                    return 0
            elif res.get("live"):
                idle = 0
            if not a.dry_run and loop.bet_dates and (loop.bets_written > announced or last_notify is None
                                                     or time.monotonic() - last_notify >= 300):
                for d_ in sorted(loop.bet_dates):
                    notify_live(d_)
                last_notify = time.monotonic()
                announced = loop.bets_written
            if a.once:
                log.info("--once: %s; %d BETs written; ESPN calls %d, odds calls %d, credits %d", res,
                         loop.bets_written, loop.espn.calls, loop.feed.calls, loop.feed.credits_used)
                return 0
            time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
    finally:
        if loop.conn is not None:
            try:
                loop.conn.close()
            except Exception:                         # noqa: BLE001
                pass


def _starters(summary: dict, c: GameCtx, g) -> pd.DataFrame:
    """The live box's starters with sides in OUR home/away (ESPN's home is
    g.home, our games row's is c.home)."""
    from data.ingestors.nba_live_feed import starters_from_summary
    swapped = (g.home, g.away) == (c.away, c.home) and g.home != c.home
    return starters_from_summary(summary, g.home, swapped)


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
