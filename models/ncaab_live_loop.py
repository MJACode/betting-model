"""
NCAAB in-play loop: the three live rules of models/ncaab_live_ig (first-half
spread, second-half spread, second-half total), the best few a night.

    python -m models.ncaab_live_loop              # the real thing
    python -m models.ncaab_live_loop --dry-run    # decide and log; write nothing, no paid call
    python -m models.ncaab_live_loop --once       # one pass, then exit

Run from the REPO ROOT. scheduler.py relaunches it every 10 minutes from 11am
to 2:50am ET (max_instances=1); it exits by itself after a few idle ticks with
no NCAAB game in progress.

THE CADENCE IS THE GRADE'S HALF-HOUR PURCHASE. The graded decision is "the
first fetch in the phase holding an eligible quote". The purchase was every
:00 and :30, and the feed served the market 261-263 s before each instant
asked for (2022-23 on), so the loop fetches the board at each :00 and :30
minus M.FETCH_OFFSET_SEC and at no other time (a loop polling every few
seconds would decide every game in the first minute of each phase: a
population never graded). A window lasts FETCH_WINDOW_SEC; an attempt that
could not be read is retried every RETRY_GAP_SEC inside it, each failure a
'skipped' row with its reason. A fetch with no eligible quote decides nothing
('carried'); the next window tries again. A fetch with one decides the rule
for the game, bet or not.

THE NIGHT (mike, 2026-11-07: "3-5 best per night"). A decision bets only at or
above M.night_cut for its rule on its slate (the EV the graded decisions
exceeded M.NIGHT_TARGET times per expected decision on a slate that size,
never under the rule's own floor), and only while its slate night holds fewer
than M.NIGHT_CAP live NCAAB bets. Decisions of one fetch are taken in EV order,
the order the grade took them. A decision under the cut, or over it with the
night full, SPENDS the rule (no_bet), as in the grade.

ONE PASS (every NCAAB_LIVE_POLL_SEC, default 20 s)
  1. ESPN's Division I scoreboard for each slate date (config.live_slate_dates()).
  2. No game in progress for IDLE_EXIT_TICKS ticks: announce standing bets and exit.
  3. Inside a fetch window, while a game in progress has an undecided rule: ONE
     bulk Odds API call (spreads + totals, the ten books the history was bought
     at; 2 credits), its rows to `odds` as in_play (source ncaab_live_loop).
  4. Wait PBP_WAIT_SEC after the fetch, read every game's ESPN summary at once,
     wait PBP_RECHECK_SEC and read them all again (ESPN served NCAAB scoring plays a
     median 37 s after their wallclock, 99th percentile 55 s, longest 58 s;
     2026-11-07, 433 scoring plays). Fail closed: a play logged at or before
     the served time that only the second read carries, ESPN's header score
     ahead of its newest play (after a re-read), or a play list that stopped
     while the clock runs, skips that game at that attempt.
  5. Per game and undecided rule: models.ncaab_live_ig.quote_states /
     eligible_quotes / decision_offers / choose, the grade's code. Every
     decision is written to ncaab_live_decisions FIRST (one per game and rule,
     never replaced), then a BET to `picks` under the first-signal live lock,
     then announced (push, then #ncaab-live; no other channel).

WHAT IS NOT HERE, AND WHY (each a named difference from the house's other
live loops; docs/sports/ncaab.md, "In play"):
  * No BookMoveClock: it anchors a book's number between changes in our state
    and needs a series of quotes; this loop sees one quote per book per half
    hour. The grade's freshness rule (no point between a quote's stamp and the
    fetch) is applied instead, on ESPN's logged plays up to the served time.
  * No Pinnacle pairing: in-play NCAAB Pinnacle quotes too few games (6 of 26
    at 2026-01-23 00:55Z); the grade decided on the deciding quote's own freshness.
  * No 10-game wait: the prior is the market's pre-game line.
  * One game never carries two bets that cannot both win (mike, 2026-10-17).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from models import cbb_pairs  # noqa: E402
from models import ncaab_live_ig as M  # noqa: E402

log = logging.getLogger("models.ncaab_live_loop")

SPORT = "NCAAB"
POLL_SEC = float(os.environ.get("NCAAB_LIVE_POLL_SEC", "20"))
# ESPN's NCAAB publication lag (module docstring): the first read waits past the
# longest scoring-play lag measured (58 s) with room, the second a minute later.
PBP_WAIT_SEC = float(os.environ.get("NCAAB_LIVE_PBP_WAIT_SEC", "90"))
PBP_RECHECK_SEC = float(os.environ.get("NCAAB_LIVE_PBP_RECHECK_SEC", "60"))
FETCH_OFFSET_SEC = float(os.environ.get("NCAAB_LIVE_FETCH_OFFSET_SEC", str(M.FETCH_OFFSET_SEC)))
FETCH_WINDOW_SEC = float(os.environ.get("NCAAB_LIVE_FETCH_WINDOW_SEC", "240"))
RETRY_GAP_SEC = float(os.environ.get("NCAAB_LIVE_RETRY_GAP_SEC", "60"))
HEADER_RECHECK_SEC = float(os.environ.get("NCAAB_LIVE_HEADER_RECHECK_SEC", "20"))
# Summaries of a fetch's games are read at once on this many threads (Loop.summaries).
SUMMARY_THREADS = int(os.environ.get("NCAAB_LIVE_SUMMARY_THREADS", "16"))
# THE FAST PATH: DraftKings' own board (models/ncaab_live_dk.py), read every
# DK_TICK_SEC while a window has a DraftKings game to settle. A game whose
# DraftKings quote is not yet confirmed waits a read, at most DK_MAX_WAIT_SEC,
# then is skipped for the window. NCAAB_LIVE_DK=0 turns the fast path off.
DK_TICK_SEC = float(os.environ.get("NCAAB_LIVE_DK_TICK_SEC", "1.0"))
DK_MAX_WAIT_SEC = float(os.environ.get("NCAAB_LIVE_DK_MAX_WAIT_SEC", "20"))
DK_ON = os.environ.get("NCAAB_LIVE_DK", "1") != "0"
BOARD_REUSE_SEC = 5.0
# While ESPN's clock runs, a newest play older than this means its play list
# has stopped: the scoring 99th-percentile lag (55 s) plus a minute between plays.
PLAY_LAG_MAX_SEC = float(os.environ.get("NCAAB_LIVE_PLAY_LAG_MAX_SEC", "120"))
HEARTBEAT_EVERY_SEC = 300.0
IDLE_EXIT_TICKS = int(os.environ.get("NCAAB_LIVE_IDLE_EXIT_TICKS", "3"))
FEED_FAIL_EXIT_TICKS = int(os.environ.get("NCAAB_LIVE_FEED_FAIL_EXIT_TICKS", "45"))
# A slate spans at most ~30 half-hour windows, each tried at most
# FETCH_WINDOW_SEC / RETRY_GAP_SEC + 1 = 5 times: 150 calls; 2 credits a call.
CALL_CAP = int(os.environ.get("NCAAB_LIVE_CALL_CAP", "200"))
CREDIT_CAP = int(os.environ.get("NCAAB_LIVE_CREDIT_CAP", "600"))
LEDGER = "ncaab_live_decisions"
BULK_PURPOSE = "ncaab_live_bulk:spreads,totals"
DONE_STATUSES = ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_FORFEIT")


def deciding_books() -> tuple:
    import config
    return tuple(config.BEST_LINE_BOOKMAKERS)


# ─── the cadence ──────────────────────────────────────────────────────────────

class Slots:
    """The grade's half-hour purchase: every :00 and :30 minus `offset` seconds.
    instant() is the window `now` is in, else None. Never built from a tip."""

    def __init__(self, offset: float = FETCH_OFFSET_SEC, window: float = FETCH_WINDOW_SEC,
                 cadence_min: int = M.CADENCE_MIN):
        self.offset, self.window, self.cadence = float(offset), float(window), int(cadence_min)

    def instant(self, now: datetime) -> datetime | None:
        base = now.astimezone(timezone.utc) + timedelta(seconds=self.offset)
        floored = base.replace(minute=base.minute - base.minute % self.cadence, second=0, microsecond=0)
        inst = floored - timedelta(seconds=self.offset)
        return inst if 0.0 <= (now - inst).total_seconds() <= self.window else None


@dataclass
class SlotState:
    pending: set | None = None
    last_attempt: datetime | None = None
    attempts: int = 0
    closed: bool = False
    dk_done: set = field(default_factory=set)      # games DraftKings' board decided or carried this window
    dk_noted: set = field(default_factory=set)     # games whose DraftKings 'skipped' row is written this window
    dk_first: datetime | None = None               # this window's first DraftKings attempt


# ─── platform context ─────────────────────────────────────────────────────────

@dataclass
class GameCtx:
    game_id: str
    game_date: str
    season: int
    home: str
    away: str
    tip: pd.Timestamp
    espn_event_id: int
    home_espn_id: int | None
    away_espn_id: int | None
    prior: pd.DataFrame | None = None       # one row: game_id, mu_pre, T_pre, prior_src
    refused: str | None = None


def slate_games(conn, dates) -> dict:
    """{espn_event_id: GameCtx} for the NCAAB games of the slate dates."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.game_date, g.season, g.home_team, g.away_team, g.commence_time,
                   e.espn_event_id, e.home_espn_id, e.away_espn_id
              FROM games g JOIN ncaab_events e USING (game_id)
             WHERE g.sport = 'NCAAB' AND g.game_date = ANY(%s)
        """, (list(dates),)).fetchall()
    finally:
        release_read(conn)
    out = {}
    for gid, gd, season, home, away, ct, eid, hid, aid in rows:
        tip = pd.to_datetime(ct, utc=True, format="mixed", errors="coerce") if ct else None
        if tip is None or pd.isna(tip):
            continue
        out[int(eid)] = GameCtx(str(gid), str(gd)[:10], int(season), str(home), str(away), tip, int(eid),
                                None if hid is None else int(hid), None if aid is None else int(aid))
    return out


def slate_size(conn, game_date: str) -> int:
    """The NCAAB games ESPN lists on a slate date, less the postponed and
    cancelled: the N the night's cut is read for (M.night_cut)."""
    from data.db import release_read
    try:
        row = conn.execute("""
            SELECT COUNT(*) FROM ncaab_events
             WHERE game_date = %s AND COALESCE(status, '') <> ALL(%s)
        """, (game_date, list(DONE_STATUSES))).fetchone()
    finally:
        release_read(conn)
    return int(row[0] or 0)


def load_prior(conn, ctx: GameCtx) -> None:
    """The grade's prior (M.PRIOR_CLOSE_SQL, M.priors_from_closes) for one game."""
    from data.db import release_read
    try:
        cur = conn.execute(M.PRIOR_CLOSE_SQL.format(where="g.game_id = %s"), (ctx.game_id,))
        rows = cur.fetchall()
    finally:
        release_read(conn)
    q = pd.DataFrame(rows, columns=["game_id", "market", "bookmaker", "spread_home", "total_line"])
    p = M.priors_from_closes(q, deciding_books())
    if p.empty:
        ctx.refused = "no pre-tip spread and total close: no prior"
        return
    ctx.prior = p


# ─── the ledger, the picks, the gates ─────────────────────────────────────────

LEDGER_COLS = ("game_id", "model_id", "game_date", "fetch_at", "outcome", "reason", "phase", "market",
               "book", "side", "line", "price", "ev", "p_win", "p_push", "model_mean", "model_sd",
               "mu_pre", "t_pre", "night_cut", "slate_games", "night_bets_before", "period", "clock_s",
               "h_pts", "a_pts", "play_lag_s", "artifact_version", "offers")


def ledger_ready(conn) -> bool:
    from data.db import release_read
    try:
        row = conn.execute(f"SELECT to_regclass('public.{LEDGER}')").fetchone()
        return bool(row and row[0])
    finally:
        release_read(conn)


def decided_keys(conn, game_ids) -> set:
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


def night_bets(conn, game_date: str) -> int:
    """Live NCAAB BETs of the live rules already written for this slate date."""
    from data.db import release_read
    try:
        row = conn.execute("""
            SELECT COUNT(*) FROM picks
             WHERE sport = 'NCAAB' AND is_live = TRUE AND signal_type = 'BET'
               AND model_id = ANY(%s) AND game_date = %s
               AND condition_status IS DISTINCT FROM 'VOID'
        """, (list(M.MODEL_IDS), game_date)).fetchone()
    finally:
        release_read(conn)
    return int(row[0] or 0)


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def ledger_row(ctx: GameCtx, rule: M.Rule, pick: dict | None, offers: pd.DataFrame | None, outcome: str,
               reason: str, fetch_at, state: dict, extra: dict, version: str) -> dict:
    p = pick or {}
    js = None
    if offers is not None and len(offers):
        keep = [c for c in ("book", "side", "line", "price", "ev", "p_win", "p_push", "stamp") if c in offers]
        recs = offers[keep].astype(object).where(offers[keep].notna(), None).to_dict("records")
        js = json.dumps(recs, default=str)
    prior = ctx.prior.iloc[0] if ctx.prior is not None and len(ctx.prior) else {}
    return {"game_id": ctx.game_id, "model_id": rule.model_id, "game_date": ctx.game_date,
            "fetch_at": fetch_at, "outcome": outcome, "reason": (reason or "")[:500], "phase": rule.phase,
            "market": rule.market, "book": p.get("book"), "side": p.get("side"), "line": _num(p.get("line")),
            "price": _num(p.get("price")), "ev": _num(p.get("ev")), "p_win": _num(p.get("p_win")),
            "p_push": _num(p.get("p_push")), "model_mean": _num(p.get("mean")), "model_sd": _num(p.get("sd")),
            "mu_pre": _num(prior.get("mu_pre") if len(prior) else None),
            "t_pre": _num(prior.get("T_pre") if len(prior) else None),
            "night_cut": _num(extra.get("night_cut")), "slate_games": extra.get("slate_games"),
            "night_bets_before": extra.get("night_bets_before"), "period": state.get("period"),
            "clock_s": _num(state.get("clock_s")), "h_pts": state.get("h_pts"), "a_pts": state.get("a_pts"),
            "play_lag_s": _num(extra.get("play_lag_s")), "artifact_version": version, "offers": js}


def insert_ledger(conn, row: dict) -> bool:
    """One row. A decision returns False when (game, model) already holds one:
    the first decision stands. A 'skipped' or 'carried' row is always written."""
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
    """Where an NCAAB live pick posts, else None (config.DISCORD_LIVE_CHANNEL_REQUIRED:
    no fallback to the shared live channel or #ncaab)."""
    import config
    if config.DISCORD_WEBHOOKS_LIVE.get(SPORT):
        return "DISCORD_WEBHOOK_LIVE_NCAAB"
    if (getattr(config, "DISCORD_CHANNELS_LIVE", None) or {}).get(SPORT):
        return "DISCORD_CHANNEL_LIVE_NCAAB"
    return None


def platform_gates(model_id: str, prob: float, price: float) -> str | None:
    """The platform's own gates, read at call time; None = clears. Set in
    config so neither binds beyond the rule."""
    import config
    if price < config.min_odds_for(model_id):
        return f"price {price:+.0f} under the floor {config.min_odds_for(model_id):+.0f}"
    ev = config.expected_value(prob, price)
    if ev is not None and ev < config.min_ev_for(model_id):
        return f"EV {ev:.3f} under the floor {config.min_ev_for(model_id):.3f}"
    if model_id in getattr(config, "PAUSED_MODELS", ()):
        return "model is paused (config.PAUSED_MODELS)"
    return None


def standing_bets(conn, game_id: str) -> list[dict]:
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT model_id, pick_side, scored_line, pick_label FROM picks
             WHERE game_id = %s AND is_live = TRUE AND signal_type = 'BET'
               AND model_id = ANY(%s) AND condition_status IS DISTINCT FROM 'VOID'
        """, (game_id, list(M.MODEL_IDS))).fetchall()
    finally:
        release_read(conn)
    return [{"model_id": m, "market": M.RULE_BY_ID[m].market, "side": s,
             "line": None if ln is None else float(ln), "label": lb} for m, s, ln, lb in rows]


def paired_bet(conn, game_id: str, model_id: str, side: str, line: float) -> str | None:
    """Why this bet would sit beside its opposite number on the game (an under
    beside a big favourite's spread bet, either order; models.cbb_pairs), or
    None. One read of `picks`, released."""
    from data.db import release_read
    try:
        return cbb_pairs.clash(conn, game_id, model_id, side, line)
    finally:
        release_read(conn)


def build_pick(ctx: GameCtx, rule: M.Rule, pick: dict, offers: pd.DataFrame, state: dict, links: dict,
               bankroll: float) -> dict:
    """One `picks` row from one BET. model_probability is P(win | no push);
    the DraftKings columns are DraftKings' own quote on the same side at the
    same number in this fetch, else NULL."""
    from models.scorer import _confidence_tier, quarter_kelly
    side, book, price, line = pick["side"], pick["book"], float(pick["price"]), float(pick["line"])
    prob = M.prob_no_push(pick["p_win"], pick.get("p_push", 0.0))
    implied = 1.0 / M.american_to_decimal(price)
    dk = None
    if offers is not None and len(offers):
        o = offers[(offers["book"] == "draftkings") & (offers["side"] == side)
                   & ((offers["line"] - line).abs() < 1e-9)]
        if len(o):
            dk = o.sort_values("ev", ascending=False).iloc[0]
    dk_odds = None if dk is None else float(dk["price"])
    dk_implied = None if dk is None else 1.0 / M.american_to_decimal(dk_odds)
    dk_prob = None if dk is None else M.prob_no_push(dk["p_win"], dk.get("p_push", 0.0))
    edge = 0.0 if dk is None else dk_prob - dk_implied
    kf, rec = quarter_kelly(prob, implied, bankroll)
    return {
        "game_id": ctx.game_id, "model_id": rule.model_id, "sport": SPORT,
        "game_date": ctx.game_date, "game_time": ctx.tip.isoformat(),
        "pick_side": side, "pick_label": M.pick_label(rule, side, line, ctx.home, ctx.away),
        "model_probability": round(prob, 4),
        "dk_implied_prob": None if dk_implied is None else round(dk_implied, 4),
        "edge": round(edge, 4), "dk_odds": dk_odds,
        "scored_line": line,                 # spreads: the HOME number (CLAUDE.md section 4); totals: the total
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "injury_flag": None, "injury_detail": None,
        "signal_type": "BET", "confidence_tier": _confidence_tier(prob - implied),
        "is_live": True,
        "inning_at_pick": state.get("period"),      # the half, in the shared column
        "score_diff_at_pick": state.get("diff"),    # home minus away
        "dk_bet_link": links.get(("draftkings", side)) if dk is not None else None,
        "best_book": book, "best_odds": price, "best_implied_prob": round(implied, 4),
        "best_edge": round(prob - implied, 4), "best_bet_link": links.get((book, side)),
        "line_book": None if (dk is not None or book == "draftkings") else book,
        "decision_book": book, "decision_odds": price,
        "decision_implied_prob": round(implied, 4), "decision_edge": round(prob - implied, 4),
    }


def write_bet(conn, pick: dict) -> bool:
    """Insert one BET under the first-signal live lock; False when the game
    already carries this model's unsettled live BET (it stands, never replaced)."""
    from data.db import release_read
    from models.scorer import _insert_picks, _locked_live_lanes
    if _locked_live_lanes(conn, pick["game_id"], (pick["model_id"],)):
        log.info("SKIPPED %s %s - locked at its first BET", pick["model_id"], pick["pick_label"])
        release_read(conn)
        return False
    _insert_picks(conn, [pick])
    return True


def unsettled_bet_dates(conn) -> set:
    from data.db import release_read
    since = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
    try:
        rows = conn.execute("""
            SELECT DISTINCT game_date FROM picks
             WHERE model_id = ANY(%s) AND is_live = TRUE AND signal_type = 'BET'
               AND result IS NULL AND game_date >= %s
        """, (list(M.MODEL_IDS), since)).fetchall()
        return {str(r[0])[:10] for r in rows}
    finally:
        release_read(conn)


def notify_live(target_date: str) -> None:
    """Push and #ncaab-live at the same time (tracking.discord_notifier: NCAAB
    is in config.DISCORD_LIVE_CHANNEL_REQUIRED, so no other channel). Each
    opens its own connection and claims its own push_sent key; neither may
    break the loop. One after the other, the post waited on the push."""
    import threading

    def push():
        try:
            from tracking.push_notifier import notify_live_signals
            notify_live_signals(target_date=target_date, dry_run=False)
        except Exception as exc:                      # noqa: BLE001
            log.error("live push failed (non-fatal): %s", exc)

    def discord():
        try:
            from tracking.discord_notifier import notify_discord_live
            notify_discord_live(target_date=target_date, dry_run=False)
        except Exception as exc:                      # noqa: BLE001
            log.error("live Discord post failed (non-fatal): %s", exc)

    threads = [threading.Thread(target=f, daemon=True) for f in (push, discord)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)


def seconds_to_next_window(slots: Slots, now: datetime) -> float:
    """Seconds until the next window opens (0 inside one): the loop wakes at
    the window's first second instead of on its next 20 s tick."""
    if slots.instant(now) is not None:
        return 0.0
    base = now.astimezone(timezone.utc) + timedelta(seconds=slots.offset)
    floored = base.replace(minute=base.minute - base.minute % slots.cadence, second=0, microsecond=0)
    nxt = floored + timedelta(minutes=slots.cadence) - timedelta(seconds=slots.offset)
    return max(0.0, (nxt - now).total_seconds())


def record_credits(conn, credits: int | None) -> None:
    if credits is None:
        return
    from data.ingestors.live_odds_ingestor import record_credits as rec
    rec(conn, BULK_PURPOSE, int(credits))
    conn.commit()


def under_daily_cap(conn, cost: int) -> bool:
    from data.db import release_read
    from data.ingestors.live_odds_ingestor import credits_used_today
    from data.ingestors.live_trigger_orchestrator import under_credit_cap
    try:
        return under_credit_cap(credits_used_today(conn), cost)
    finally:
        release_read(conn)


# ─── one game at one fetch ────────────────────────────────────────────────────

def quotes_frame(rows: list[dict], served_at: datetime) -> pd.DataFrame:
    """This fetch's `odds` rows as the grade's quote frame."""
    cols = ["game_id", "market", "book", "stamp", "fetch_at", "home_price", "away_price", "spread_home",
            "total_line", "over_price", "under_price"]
    if not rows:
        return pd.DataFrame(columns=cols)
    q = pd.DataFrame(rows).rename(columns={"bookmaker": "book"})
    q["stamp"] = pd.to_datetime(q["snapshot_at"], utc=True, format="mixed", errors="coerce")
    q["fetch_at"] = pd.Timestamp(served_at)
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        q[c] = pd.to_numeric(q.get(c), errors="coerce").astype(float)
    q = q[q["stamp"].notna() & (q["stamp"] <= q["fetch_at"])]
    return q[cols].reset_index(drop=True)


def plays_frame(summary: dict, ctx: GameCtx) -> pd.DataFrame:
    from data.ingestors.ncaab_pbp import summary_rows
    rows = summary_rows(summary, espn_game_id=ctx.espn_event_id, game_id=ctx.game_id, season=ctx.season,
                        home_espn_id=ctx.home_espn_id, away_espn_id=ctx.away_espn_id)
    p = pd.DataFrame(rows)
    if p.empty:
        return p
    p = p.rename(columns={"home_score": "h_pts", "away_score": "a_pts"})
    p["wallclock"] = pd.to_datetime(p["wallclock"], utc=True, errors="coerce")
    return M.with_team_fouls(p)


def evaluate_game(ctx: GameCtx, art: M.Artifact, q: pd.DataFrame, summary: dict, rules: list,
                  now: datetime) -> tuple[list, dict]:
    """[(rule, chosen offer dict, offers frame, state dict)] for every open rule
    with an eligible quote at this fetch, and notes. A rule without one is
    absent (not a decision)."""
    notes: dict = {}
    plays = plays_frame(summary, ctx)
    if plays.empty:
        return [], {"refused": "no plays yet"}
    newest = plays["wallclock"].max()
    notes["play_lag_s"] = (now - newest).total_seconds() if pd.notna(newest) else None
    gaps = plays.sort_values("play_no")["wallclock"].diff().dt.total_seconds()
    if (gaps > 45 * 60).any():
        return [], {**notes, "refused_game": "a 45-minute gap between two ESPN plays (a feed restart)"}
    q = q[q["game_id"] == ctx.game_id]
    if q.empty:
        return [], {**notes, "carry": "no quote for this game in the fetch"}
    return evaluate_states(ctx, art, M.quote_states(q, plays), rules, deciding_books()), notes


def evaluate_states(ctx: GameCtx, art: M.Artifact, qs: pd.DataFrame, rules: list, books: tuple) -> list:
    """The grade's decision on quotes already carrying their state at the
    stamp and the points since (M.quote_states' shape): ESPN's plays on the
    provider's quotes, or DraftKings' own board (models/ncaab_live_dk.py)."""
    el = M.eligible_quotes(qs, ctx.prior, books)
    out = []
    for rule in rules:
        er = el[el["rule"] == rule.key]
        if er.empty:
            continue
        off = M.decision_offers(er, art.models)
        best = M.choose(off.assign(rule=rule.key), -math.inf, books)
        if best.empty:
            continue
        b = best.iloc[0].to_dict()
        is_tot = rule.market == "totals"
        b["mean"] = b.get("mu_t") if is_tot else b.get("mu_m")
        b["sd"] = b.get("sd_t") if is_tot else b.get("sd_m")
        st = {"period": int(b["period"]) if pd.notna(b.get("period")) else None, "clock_s": b.get("clock_s"),
              "h_pts": int(b["h_pts"]), "a_pts": int(b["a_pts"]), "diff": int(b["h_pts"] - b["a_pts"])}
        out.append((rule, b, off, st))
    return out


# ─── the loop ─────────────────────────────────────────────────────────────────

class Loop:
    """One process's state across a slate. tick() is one pass; the feeds, the
    connection factory and the clock are injected so a test can drive a window."""

    def __init__(self, art: M.Artifact, espn, feed, connect, *, dry_run: bool = False,
                 wait: float = PBP_WAIT_SEC, recheck: float = PBP_RECHECK_SEC, sleep=time.sleep,
                 clock=None, slate_dates=None, slots: Slots | None = None, resolver_factory=None,
                 dk=None):
        self.art, self.espn, self.feed, self.connect = art, espn, feed, connect
        # DraftKings' own board (models/ncaab_live_dk.py): the fast path, tried
        # first in every window; None turns it off.
        self.dk = dk
        self._boards = None
        self._fast = False                     # the last tick asked for a fast next one
        self.dry_run, self.wait, self.recheck, self.sleep = dry_run, float(wait), float(recheck), sleep
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.slate_dates = slate_dates
        self.slots = slots or Slots()
        self.resolver_factory = resolver_factory
        self.conn = None
        self.windows: dict = {}
        self.ctxs: dict = {}                   # espn_event_id -> GameCtx
        self.decided: set = set()
        self.bet_dates: set = set()
        self.bets_written = 0
        self.bankroll = None
        self.last_slate_read = 0.0
        self.last_beat = None
        self.blocked = None
        self.sizes: dict = {}

    def c(self):
        if self.conn is None:
            self.conn = self.connect()
        return self.conn

    def recycle(self):
        self.conn = _recycle(self.conn)

    def dates(self) -> list:
        import config
        return list(self.slate_dates() if self.slate_dates else config.live_slate_dates())

    def scoreboards(self) -> list | None:
        # Fast ticks (one a second while a DraftKings quote waits a read) reuse a
        # scoreboard read for BOARD_REUSE_SEC: which games are in progress does
        # not change that fast, and ESPN is read every tick otherwise.
        if self._fast and self._boards is not None and time.monotonic() - self._boards[0] < BOARD_REUSE_SEC:
            return self._boards[1]
        got = self._scoreboards()
        self._boards = None if got is None else (time.monotonic(), got)
        return got

    def _scoreboards(self) -> list | None:
        boards, answered = [], 0
        for d in self.dates():
            b = self.espn.scoreboard(d)
            if b is not None:
                answered += 1
                boards.extend(b)
        return boards if answered else None

    def match(self, live: list) -> list:
        """(GameCtx, EspnGame) for every ESPN game in progress that is ours, by event id."""
        if any(g.event_id not in self.ctxs for g in live) and time.monotonic() - self.last_slate_read >= 60:
            try:
                self.ctxs.update({k: v for k, v in slate_games(self.c(), self.dates()).items()
                                  if k not in self.ctxs})
                self.last_slate_read = time.monotonic()
            except Exception as exc:                  # noqa: BLE001
                log.error("slate read failed: %s", exc)
                self.recycle()
        return [(self.ctxs[g.event_id], g) for g in live if g.event_id in self.ctxs]

    def heartbeat(self, in_play: int) -> None:
        if self.dry_run:
            return
        t = time.monotonic()
        if self.last_beat is not None and t - self.last_beat < HEARTBEAT_EVERY_SEC:
            return
        self.last_beat = t
        try:
            from tracking.job_heartbeat import beat
            beat("ncaab_live", "ok", f"running: {in_play} game(s) in play, {self.bets_written} bet(s) written")
        except Exception as exc:                      # noqa: BLE001
            log.warning("heartbeat failed (non-fatal): %s", exc)

    def open_rules(self, ctx: GameCtx, g) -> list:
        """Rules not yet decided whose phase can still hold a fresh quote: a
        first-half quote can sit in a fetch early in the second half."""
        return [r for r in M.RULES if (ctx.game_id, r.model_id) not in self.decided
                and (g.period is None or g.period <= 3)]

    def summary(self, event_id, tries: int = 3, gap_s: float = 5.0):
        for k in range(tries):
            got = self.espn.summary(event_id)
            if got is not None:
                return got
            if k + 1 < tries:
                self.sleep(gap_s)
        return None

    def summaries(self, ctxs: list) -> dict:
        """{game_id: summary or None} for every game, read at the same time.
        Read one after another, every game's reads plus two other games' 20 s
        header re-reads held the 2026-11-12 Indiana decision 43 s past the
        designed 150 s (fetch 23:55:54.8, decided 23:59:07.9)."""
        if len(ctxs) <= 1:
            return {c.game_id: self.summary(c.espn_event_id) for c in ctxs}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(SUMMARY_THREADS, len(ctxs))) as ex:
            got = list(ex.map(lambda c: self.summary(c.espn_event_id), ctxs))
        return {c.game_id: s for c, s in zip(ctxs, got)}

    def note(self, c: GameCtx, g, outcome: str, reason: str, fetch_at=None) -> str:
        rules = self.open_rules(c, g)
        (log.warning if outcome == "skipped" else log.info)(
            "%s %s (%s): %s", outcome.upper(), c.game_id, ", ".join(r.model_id for r in rules), reason)
        if not self.dry_run:
            try:
                for r in rules:
                    insert_ledger(self.c(), ledger_row(c, r, None, None, outcome, reason, fetch_at, {}, {},
                                                       self.art.version))
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("could not record the %s row for %s: %s", outcome, c.game_id, exc)
                self.recycle()
        return outcome

    def size_of(self, game_date: str) -> int:
        if game_date not in self.sizes:
            self.sizes[game_date] = slate_size(self.c(), game_date)
        return self.sizes[game_date]

    def tick(self) -> dict:
        res = self._tick()
        self._fast = bool(res.get("fast"))
        return res

    def _tick(self) -> dict:
        now = self.clock()
        boards = self.scoreboards()
        if boards is None:
            return {"live": None}
        live = [g for g in boards if g.state == "in"]
        if not live:
            return {"live": 0}
        in_play = self.match(live)
        self.heartbeat(len(in_play))
        inst = self.slots.instant(now)
        res = {"live": len(live), "slot": inst, "decisions": 0}
        if inst is None:
            self.warm(in_play)
            return res
        if live_destination() is None:
            self.blocked = ("neither DISCORD_WEBHOOK_LIVE_NCAAB nor DISCORD_CHANNEL_LIVE_NCAAB is set on this "
                            "service: an NCAAB live bet would never post, so none is decided")
            res["blocked"] = self.blocked
            return res
        st = self.windows.setdefault(inst, SlotState())
        slow_due = st.last_attempt is None or (now - st.last_attempt).total_seconds() >= RETRY_GAP_SEC
        if st.closed or (self.dk is None and not slow_due):
            return res
        if not self.dry_run:
            try:
                self.decided |= decided_keys(self.c(), {c.game_id for c, _g in in_play})
            except Exception as exc:                  # noqa: BLE001
                log.error("ledger read failed - window %s not tried this tick: %s", inst.isoformat(), exc)
                self.recycle()
                return res
        todo = [(c, g) for c, g in in_play if c.refused is None and self.open_rules(c, g)
                and c.game_id not in st.dk_done]
        if not todo:
            st.closed = True
            return res
        if self.dk is not None:
            got = self.dk_slot(st, todo, now)
            if got is not None:
                n, done, waiting = got
                res["decisions"] += n
                if waiting:
                    # a DraftKings quote waits one read for its confirmation: the
                    # slow path (minutes of ESPN waits) does not run until it is settled
                    res["fast"] = True
                    return res
                todo = [(c, g) for c, g in todo if c.game_id not in done]
        todo = [(c, g) for c, g in todo if st.pending is None or c.game_id in st.pending]
        if not todo:
            st.closed = True
            return res
        if not slow_due:
            return res
        st.last_attempt = now
        st.attempts += 1
        n, outcomes = self.run_slot(inst, todo)
        st.pending = {gid for gid, o in outcomes.items() if o == "skipped"}
        st.closed = not st.pending
        res["decisions"] += n
        return res

    def warm(self, in_play: list) -> None:
        """Between windows: each game's prior and its slate's size, so the
        window's first DraftKings read is decided without those reads (they
        were most of the 4.7 s from read to decision in the 2026-11-12 dry run)."""
        for c, _g in in_play:
            if c.prior is None and c.refused is None:
                try:
                    load_prior(self.c(), c)
                except Exception as exc:              # noqa: BLE001
                    log.warning("prior read failed for %s (retried at the window): %s", c.game_id, exc)
                    self.recycle()
            try:
                self.size_of(c.game_date)
            except Exception as exc:                  # noqa: BLE001
                log.warning("slate size read failed for %s: %s", c.game_date, exc)
                self.recycle()

    def dk_slot(self, st: SlotState, todo: list, now: datetime):
        """The window decided on DraftKings' own board (models/ncaab_live_dk.py):
        (decisions, games done this window, games waiting a read), or None when
        the feed is not live (mike's machine off) and the slow path decides."""
        from models import ncaab_live_dk as DK
        try:
            last = self.dk.last_read()
        except Exception as exc:                      # noqa: BLE001
            log.warning("DraftKings feed read failed (the slow path decides): %s", exc)
            self.recycle()
            return None
        if not DK.feed_is_live(last, now):
            return None
        fetch_at = last[0]
        try:
            reads = self.dk.reads({c.game_id for c, _g in todo})
        except Exception as exc:                      # noqa: BLE001
            log.warning("DraftKings reads failed (the slow path decides): %s", exc)
            self.recycle()
            return None
        have = set(reads["game_id"]) if len(reads) else set()
        mine = [(c, g) for c, g in todo if c.game_id in have]
        if not mine:
            return 0, set(), set()
        if st.dk_first is None:
            st.dk_first = now
        give_up = (now - st.dk_first).total_seconds() > DK_MAX_WAIT_SEC
        done, waiting, ready = set(), set(), []

        def hold(c, g, why):
            if give_up:
                if c.game_id not in st.dk_noted:
                    self.note(c, g, "skipped", f"DraftKings board: {why}, still after {DK_MAX_WAIT_SEC:.0f} s",
                              fetch_at.to_pydatetime())
                    st.dk_noted.add(c.game_id)
                done.add(c.game_id)
            else:
                waiting.add(c.game_id)

        for c, g in mine:
            if c.prior is None and c.refused is None:
                try:
                    load_prior(self.c(), c)
                except Exception as exc:              # noqa: BLE001
                    self.recycle()
                    hold(c, g, f"prior read failed: {type(exc).__name__}")
                    continue
            if c.refused is not None:
                done.add(c.game_id)
                continue
            ready.append((c, g))
        sums = self.summaries([c for c, _g in ready])
        plays = {}
        for c, _g in ready:
            s = sums.get(c.game_id)
            p = plays_frame(s, c) if s is not None else pd.DataFrame()
            if len(p):
                plays[c.game_id] = p
        qs = DK.quote_states_dk(reads, fetch_at, plays)
        decisions = []
        for c, g in ready:
            if c.game_id not in plays:
                hold(c, g, "ESPN summary unreadable (team fouls)")
                continue
            rules = self.open_rules(c, g)
            q = qs[(qs["game_id"] == c.game_id) & qs["market"].isin({r.market for r in rules})]
            if len(q) and not q["held"].all():
                hold(c, g, "a quote first seen on the feed's newest read")
                continue
            if len(q) and (q["pts_since"] > 0).any():
                # DraftKings moved its score and not yet its line (41 of 180
                # baskets on 2026-11-12, repriced a read or two later)
                hold(c, g, "a basket DraftKings has not repriced yet")
                continue
            try:
                decs = evaluate_states(c, self.art, q, rules, (DK.BOOK,)) if len(q) else []
            except Exception as exc:                  # noqa: BLE001
                log.exception("%s DraftKings evaluation failed: %s", c.game_id, exc)
                hold(c, g, f"evaluation failed: {type(exc).__name__}")
                continue
            done.add(c.game_id)
            if not decs:
                self.note(c, g, "carried", "no eligible quote on DraftKings' board", fetch_at.to_pydatetime())
                continue
            newest = plays[c.game_id]["wallclock"].max()
            notes = {"play_lag_s": (now - newest).total_seconds() if pd.notna(newest) else None, "links": {},
                     "source": "DraftKings board"}
            for rule, b, off, stt in decs:
                decisions.append((c, g, rule, b, off, stt, notes))
        n = self.decide(decisions, fetch_at.to_pydatetime()) if decisions else 0
        st.dk_done |= done
        return n, done, waiting

    def run_slot(self, slot: datetime, todo: list) -> tuple:
        out: dict = {}
        for c, g in todo:
            if c.prior is None and c.refused is None:
                try:
                    load_prior(self.c(), c)
                except Exception as exc:              # noqa: BLE001
                    self.recycle()
                    out[c.game_id] = self.note(c, g, "skipped", f"prior read failed: {type(exc).__name__}")
                    continue
                if c.refused:
                    log.warning("%s refused: %s", c.game_id, c.refused)
                    out[c.game_id] = "refused"
        todo = [(c, g) for c, g in todo if c.game_id not in out and c.refused is None and c.prior is not None]
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
                    out[c.game_id] = self.note(c, g, "skipped", why)
                return 0, out
        if self.dry_run:
            log.info("[dry-run] window %s: would fetch the board for %s", slot.isoformat(),
                     ", ".join(c.game_id for c, _g in todo))
            return 0, {**out, **{c.game_id: "carried" for c, _g in todo}}
        fetch = self.feed.fetch()
        if fetch is None:
            for c, g in todo:
                out[c.game_id] = self.note(c, g, "skipped", "no odds from the feed (call failed or a cap)")
            return 0, out
        try:
            return self._after_fetch(todo, fetch, out)
        except Exception as exc:                      # noqa: BLE001
            log.exception("window %s failed after the fetch: %s", slot.isoformat(), exc)
            self.recycle()
            for c, g in todo:
                if c.game_id not in out:
                    out[c.game_id] = self.note(c, g, "skipped", f"the fetch could not be read: {type(exc).__name__}",
                                               fetch.fetched_at)
            return 0, out

    def _resolver(self):
        if self.resolver_factory is not None:
            return self.resolver_factory()
        from data.ingestors.ncaab_teams import make_resolver
        return make_resolver(self.c(), self.dates()[0])

    def _after_fetch(self, todo: list, fetch, out: dict) -> tuple:
        from data.ingestors.ncaab_live_feed import clock_running, late_plays, rows_from_events, score_mismatch
        try:
            record_credits(self.c(), fetch.credits)
        except Exception as exc:                      # noqa: BLE001
            log.warning("credit telemetry failed (non-fatal): %s", exc)
            self.recycle()
        known = {c.game_id for c in self.ctxs.values()}
        rows = [r for r in rows_from_events(fetch.events, fetch.fetched_at, self._resolver())
                if r["game_id"] in known]
        if rows:
            try:
                from data.ingestors.live_price_log import record_live_prices
                record_live_prices(self.c(), rows, known_game_ids=known)
            except Exception as exc:                  # noqa: BLE001
                log.warning("live price log failed (non-fatal): %s", exc)
                self.recycle()
        served = fetch.fetched_at
        q_all = quotes_frame(rows, served)
        links: dict = {}
        for r_ in rows:
            for side in ("home", "away", "over", "under"):
                if r_.get(f"{side}_link"):
                    links.setdefault((r_["game_id"], r_.get("bookmaker"), side), r_.get(f"{side}_link"))
        have = set(q_all["game_id"])
        for c, g in todo:
            if c.game_id not in have:
                out[c.game_id] = self.note(c, g, "carried", "no quote for this game in the fetch", served)
        todo = [(c, g) for c, g in todo if c.game_id in have]
        if not todo:
            return 0, out
        left = self.wait - (self.clock() - served).total_seconds()
        if left > 0:
            self.sleep(left)
        ctxs = [c for c, _g in todo]
        first = self.summaries(ctxs)
        if self.recheck > 0:
            self.sleep(self.recheck)
        seconds = self.summaries(ctxs)
        # Every game whose header is ahead of its plays is re-read once, together:
        # one game's re-read never holds another game's decision back.
        ahead = [c for c in ctxs if first.get(c.game_id) is not None and seconds.get(c.game_id) is not None
                 and not late_plays(first[c.game_id], seconds[c.game_id], served)
                 and score_mismatch(seconds[c.game_id])]
        thirds: dict = {}
        if ahead:
            self.sleep(HEADER_RECHECK_SEC)
            thirds = self.summaries(ahead)
        decisions = []                                 # (ctx, g, rule, best, offers, state, notes)
        for c, g in todo:
            try:
                second = seconds.get(c.game_id)
                if first.get(c.game_id) is None or second is None:
                    out[c.game_id] = self.note(c, g, "skipped", "ESPN summary unreadable", served)
                    continue
                late = late_plays(first[c.game_id], second, served)
                if late:
                    out[c.game_id] = self.note(
                        c, g, "skipped", f"ESPN served {len(late)} play(s) logged at or before the served time only "
                                         f"on the second read (publishing late)", served)
                    continue
                why = score_mismatch(second)
                if why:
                    third = thirds.get(c.game_id)
                    why = "ESPN summary unreadable" if third is None else score_mismatch(third)
                    if not why and late_plays(second, third, served):
                        why = "ESPN served a play logged before the served time only on the header re-read"
                    if why:
                        out[c.game_id] = self.note(c, g, "skipped", f"{why}, still after {HEADER_RECHECK_SEC:.0f} s",
                                                   served)
                        continue
                    second = third
                running = clock_running(first[c.game_id], second)
                decs, notes = evaluate_game(c, self.art, q_all, second, self.open_rules(c, g), self.clock())
                if notes.get("refused_game"):
                    c.refused = notes["refused_game"]
                    out[c.game_id] = "refused"
                    continue
                if notes.get("refused"):
                    out[c.game_id] = self.note(c, g, "skipped", notes["refused"], served)
                    continue
                lag = notes.get("play_lag_s")
                if running and lag is not None and lag > PLAY_LAG_MAX_SEC:
                    out[c.game_id] = self.note(c, g, "skipped", f"ESPN's newest play is {lag:.0f} s old while its "
                                                              f"clock runs: its play list has stopped", served)
                    continue
                if not decs:
                    out[c.game_id] = self.note(c, g, "carried", notes.get("carry") or "no eligible quote", served)
                    continue
                notes["links"] = {(bk, sd): ln for (gid, bk, sd), ln in links.items() if gid == c.game_id}
                for rule, b, off, stt in decs:
                    decisions.append((c, g, rule, b, off, stt, notes))
                out[c.game_id] = "decided"
            except Exception as exc:                  # noqa: BLE001
                log.exception("%s failed: %s", c.game_id, exc)
                self.recycle()
                out[c.game_id] = self.note(c, g, "skipped", f"evaluation failed: {type(exc).__name__}: {exc}",
                                           served)
        return self.decide(decisions, served), out

    def decide(self, decisions: list, served) -> int:
        """Record every decision of this fetch, best EV first (the grade's
        order), betting those at or above the night's cut while the night has room."""
        decisions = sorted(decisions, key=lambda d: -float(d[3]["ev"]))
        night_count: dict = {}
        written = 0
        standing_cache: dict = {}
        this_pass: dict = {}
        for c, g, rule, b, off, stt, notes in decisions:
            n_games = self.size_of(c.game_date)
            cut = M.night_cut(self.art, n_games, rule)
            if c.game_date not in night_count:
                night_count[c.game_date] = 0 if self.dry_run else night_bets(self.c(), c.game_date)
            before = night_count[c.game_date]
            extra = {"night_cut": cut, "slate_games": n_games, "night_bets_before": before,
                     "play_lag_s": notes.get("play_lag_s")}
            pick = None
            if float(b["ev"]) < cut:
                outcome, reason = "no_bet", f"EV {float(b['ev']):.3f} under tonight's cut {cut:.3f} ({n_games} games)"
            elif before >= M.NIGHT_CAP:
                outcome, reason = "no_bet", f"the night already holds {before} bets (cap {M.NIGHT_CAP})"
            else:
                outcome, reason = "bet", "BET"
                mine = {"market": rule.market, "side": b["side"], "line": float(b["line"])}
                if c.game_id not in standing_cache:
                    standing_cache[c.game_id] = [] if self.dry_run else standing_bets(self.c(), c.game_id)
                held = next((s for s in standing_cache[c.game_id] + this_pass.get(c.game_id, [])
                             if M.cannot_both_win(mine, s)), None)
                # An under beside a big favourite's spread bet (models/cbb_pairs.py; mike,
                # 2026-11-11), from any NCAAB model. `picks` is read fresh each time, and a
                # bet of this pass is written before the next decision is taken, so two
                # decisions of one fetch see each other.
                paired = None if (held is not None or self.dry_run) else paired_bet(
                    self.c(), c.game_id, rule.model_id, b["side"], float(b["line"]))
                if held is not None:
                    outcome, reason = "declined", f"cannot both win with {held.get('label') or held['model_id']}"
                elif paired:
                    outcome, reason = "declined", paired
                else:
                    if self.bankroll is None and not self.dry_run:
                        try:
                            from models.scorer import _get_current_bankroll
                            self.bankroll = float(_get_current_bankroll(self.c()))
                        except Exception as exc:  # noqa: BLE001
                            log.warning("bankroll read failed (sizing at 0): %s", exc)
                            self.recycle()
                    try:
                        pick = build_pick(c, rule, b, off, stt, notes.get("links") or {}, self.bankroll or 0.0)
                        why = platform_gates(rule.model_id, pick["model_probability"], pick["decision_odds"])
                        if not why:
                            from models.ncaab_quote_bounds import edge_problem
                            why = edge_problem(pick["decision_edge"], rule.model_id)
                    except Exception as exc:      # noqa: BLE001
                        log.exception("building the %s pick failed: %s", rule.model_id, exc)
                        pick, why = None, f"the pick could not be built: {type(exc).__name__}: {exc}"
                    if why:
                        outcome, reason, pick = "declined", why, None
            if notes.get("source"):
                reason = f"{reason} ({notes['source']})"
            log.info("DECIDED %s %s %s @ %s H%s %s-%s cut=%.3f (%d games, %d bet before): %s %s", rule.model_id,
                     c.game_id, c.away, c.home, stt.get("period"), stt.get("h_pts"), stt.get("a_pts"), cut, n_games,
                     before, outcome.upper(),
                     f"{pick['pick_label']} {pick['decision_book']} {pick['decision_odds']:+.0f}" if pick else reason)
            self.decided.add((c.game_id, rule.model_id))
            if outcome == "bet":
                night_count[c.game_date] = before + 1
                this_pass.setdefault(c.game_id, []).append({**mine, "model_id": rule.model_id,
                                                            "label": pick["pick_label"] if pick else None})
            if self.dry_run:
                continue
            try:
                row = ledger_row(c, rule, b, off, outcome, reason, served, stt, extra, self.art.version)
                if not insert_ledger(self.c(), row):
                    self.c().rollback()
                    log.info("%s %s already decided - nothing written", c.game_id, rule.model_id)
                    if outcome == "bet":
                        night_count[c.game_date] = before
                    continue
                if pick is not None and write_bet(self.c(), pick):
                    self.bets_written += 1
                    self.bet_dates.add(c.game_date)
                    written += 1
                    log.info("WROTE BET %s %s at %s %+.0f", rule.model_id, pick["pick_label"],
                             pick["decision_book"], pick["decision_odds"])
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("write failed for %s %s (non-fatal): %s", c.game_id, rule.model_id, exc)
                self.recycle()
        return len(decisions)


def main(argv=None) -> int:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-live")
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
    from data.ingestors.ncaab_live_feed import Espn, odds_feed
    for mid in M.MODEL_IDS:
        if mid not in config.LIVE_MODELS:
            log.error("%s is not in config.LIVE_MODELS: it would never settle - exiting", mid)
            return 1
    art = M.load_artifact()
    log.info("artifact %s; rules %s; floors %s; night target %s, cap %s; fetch at each :00/:30 minus %.0fs "
             "(window %.0fs); ESPN read %.0fs after a fetch and again %.0fs later", art.version,
             ", ".join(M.MODEL_IDS), {r.model_id: r.floor for r in M.RULES}, M.NIGHT_TARGET, M.NIGHT_CAP,
             FETCH_OFFSET_SEC, FETCH_WINDOW_SEC, a.wait, a.recheck)
    use_poller_session()
    loop = Loop(art, Espn(), odds_feed(CALL_CAP, CREDIT_CAP), get_connection,
                dry_run=a.dry_run, wait=a.wait, recheck=a.recheck)
    if DK_ON:
        from models.ncaab_live_dk import DbSource
        loop.dk = DbSource(loop.c)
        log.info("fast path on: DraftKings' own board (dk_live_feed / dk_live_reads), read every %.1f s "
                 "while a window waits on it", DK_TICK_SEC)
    if not a.dry_run:
        try:
            if not ledger_ready(loop.c()):
                log.error("table %s is missing (data/migrations/ncaab_live_decisions_2026_11_07.sql, applied by "
                          "data.view_migrations): no decision can be recorded, so none is made - exiting", LEDGER)
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
                log.error("NCAAB LIVE DECIDES NOTHING: %s. Set one of them on this service and redeploy "
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
                    log.info("no NCAAB game in progress for %d tick(s) - exiting (%d BETs written, %d odds "
                             "calls, %d credits)", idle, loop.bets_written, loop.feed.calls, loop.feed.credits_used)
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
            gap = DK_TICK_SEC if res.get("fast") else a.interval
            gap = min(gap, seconds_to_next_window(loop.slots, datetime.now(timezone.utc)) + 0.05)
            time.sleep(max(0.0, gap - (time.monotonic() - started)))
    finally:
        if loop.conn is not None:
            try:
                loop.conn.close()
            except Exception:                         # noqa: BLE001
                pass


def _recycle(conn):
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
