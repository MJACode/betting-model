"""
EuroLeague halftime loop: the one rule of models/euroleague_live_ht (the
full-game spread, bet during the halftime break).

    python -m models.euroleague_live_loop              # the real thing
    python -m models.euroleague_live_loop --dry-run    # look and log; write nothing, no paid call
    python -m models.euroleague_live_loop --once       # one pass, then exit

Run from the REPO ROOT. scheduler.py relaunches it every 10 minutes from 9am
to 5:50pm ET (max_instances=1); it exits by itself after a few idle ticks with
no EuroLeague game in progress. Tips run 14:00-20:00 UTC (every stored game,
2020-21 to 2026-27); the half ends a median 48 minutes after the tip (1st-99th
percentile 38-102).

THE CADENCE IS THE GRADE'S FIVE-MINUTE SNAPSHOT. The graded decision is "the
first read of the halftime break holding an eligible quote", and the history
it was graded on holds one in-play snapshot every five minutes, stamped 36-40
seconds after the mark. So the loop reads the board at each five-minute mark
plus M.FETCH_AFTER_SEC and at no other time: a loop reading every few seconds
would decide every game in the first seconds of its break, on the first book
to re-post, a population never graded. A break lasts about fifteen minutes, so
a game gets two or three reads.

ONE PASS (every EUROLEAGUE_LIVE_POLL_SEC, default 15 s)
  1. The slate from `games` (EuroLeague's own schedule): a game is in
     progress from its tip for IN_PROGRESS_MIN minutes. None for
     IDLE_EXIT_TICKS ticks: announce standing bets and exit.
  2. At a read instant, for each undecided game NEAR_HALF_MIN after its tip:
     EuroLeague's free API (data/ingestors/euroleague_live_feed), one game at a
     time: the half is over ('EP' in the second quarter), the third has not
     begun ('BP' in it, or a shot of minute 21+), and the half-time score on
     the shot chart equals the play-by-play's and the header's. The third
     quarter under way with nothing decided: a final 'missed' row.
  3. Pinnacle's last coherent pre-game spread and total from `odds`
     (M.PRIOR_CLOSE_SQL), stamped before min(tip, first shot). None: the game
     is refused (the grade dropped such games).
  4. ONE bulk Odds API call (moneylines, spreads and totals at the ten books
     the history was bought at; 3 credits), its rows of games under way to
     `odds` as in_play (source euroleague_live_loop) through the live price log.
  5. EuroLeague's API again for each break game, after the call: still the
     break, the same score and the same last shot, else the read is skipped.
  6. Per game: models.euroleague_live_ht.read_break, the grade's code. Not a
     minute past the half's last shot: nothing. In the break with no eligible
     quote: a 'carried' row, and the next read tries again. In the break with
     one: the decision, written to euroleague_live_decisions FIRST (one final
     row a game, never replaced), then a BET to `picks` under the first-signal
     live lock, then announced (push, then the EuroLeague live channel; no
     other channel).

WHAT IS NOT HERE, AND WHY
  * DraftKings' own board (data/ingestors/dk_live_board.py) is not read: on
    2026-11-13 at 23:1x UTC DraftKings' navigation for Ohio, New Jersey and
    Massachusetts listed no EuroLeague league (the next EuroLeague game was 89
    hours away, and DraftKings lists a league while it has offers), so its id
    could not be read. The graded population is the odds feed's anyway
    (docs/sports/euroleague.md, "Halftime spread").
  * No nightly count: every decision at or above the cut is bet.
  * One game never carries two bets that cannot both win (mike, 2026-10-17):
    a halftime spread is checked against the game's standing full-game
    EuroLeague BETs, its own and the pre-game rules' (the home underdog spread
    and the two full-game moneylines, models/euroleague_pregame.py; a
    moneyline is checked as the spread at -0.5 for the home side, +0.5 for the
    away side, since a full game cannot end level).
"""
from __future__ import annotations

import argparse
import json
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

import pandas as pd  # noqa: E402

from models import euroleague_live_ht as M  # noqa: E402
from models.ncaab_live_ig import cannot_both_win  # noqa: E402
from models.ncaab_live_loop import (Slots, SlotState, _num, _recycle, notify_live,  # noqa: E402,F401
                                    platform_gates, quotes_frame, under_daily_cap, write_bet)

log = logging.getLogger("models.euroleague_live_loop")

SPORT = M.SPORT
POLL_SEC = float(os.environ.get("EUROLEAGUE_LIVE_POLL_SEC", "15"))
# A read whose call failed is tried again inside this window; one that reached
# the bulk call has used the window up and waits for the next mark.
FETCH_WINDOW_SEC = float(os.environ.get("EUROLEAGUE_LIVE_FETCH_WINDOW_SEC", "120"))
RETRY_GAP_SEC = float(os.environ.get("EUROLEAGUE_LIVE_RETRY_GAP_SEC", "45"))
HEARTBEAT_EVERY_SEC = 300.0
IDLE_EXIT_TICKS = int(os.environ.get("EUROLEAGUE_LIVE_IDLE_EXIT_TICKS", "3"))
SLATE_EVERY_SEC = 60.0
# A game is in progress from its tip for this long (a stored game's half ends
# 38-102 minutes after the tip at the 1st-99th percentile; overtime games run ~2h15).
IN_PROGRESS_MIN = 180.0
# EuroLeague's API is read for a game only between these minutes after its tip.
NEAR_HALF_MIN = (30.0, 120.0)
# A day holds at most ~12 games and ~18 five-minute marks inside one game's
# near-half span, each tried at most FETCH_WINDOW_SEC / RETRY_GAP_SEC + 1 = 3
# times: well under 200 calls. 3 credits a call (ten books, one region).
CALL_CAP = int(os.environ.get("EUROLEAGUE_LIVE_CALL_CAP", "300"))
CREDIT_CAP = int(os.environ.get("EUROLEAGUE_LIVE_CREDIT_CAP", "900"))
CALL_CREDITS = 3
LEDGER = "euroleague_live_decisions"
FINAL = ("bet", "no_bet", "declined", "missed")
BULK_PURPOSE = "euroleague_live_bulk:h2h,spreads,totals"
# The models that bet a EuroLeague full-game spread: no two of their bets on one
# game may be unable to win together.
FULL_GAME_SPREAD_MODELS = (M.MODEL_ID, "euroleague_home_dog_spread")
# The pre-game full-game moneylines (models/euroleague_pregame.py): read as the
# spread at -0.5 (home) / +0.5 (away).
FULL_GAME_MONEYLINE_MODELS = ("euroleague_home_ml", "euroleague_heavy_fav_ml")


def deciding_books() -> tuple:
    """The research's five books a pick may name, less any the platform has
    taken out of config.BEST_LINE_BOOKMAKERS."""
    import config
    allowed = set(config.BEST_LINE_BOOKMAKERS)
    return tuple(b for b in M.DECIDABLE if b in allowed)


def slots() -> Slots:
    """Every five-minute mark plus M.FETCH_AFTER_SEC: the history's snapshot instants."""
    return Slots(offset=-M.FETCH_AFTER_SEC, window=FETCH_WINDOW_SEC, cadence_min=M.CADENCE_MIN)


# ─── platform context ─────────────────────────────────────────────────────────

@dataclass
class GameCtx:
    game_id: str
    game_date: str
    season: int
    home: str
    away: str
    tip: pd.Timestamp
    season_code: str
    game_code: int
    prior: tuple | None = None              # (prior_m, Pinnacle's pre-game total)
    refused: str | None = None


def slate_games(conn, now: datetime) -> dict:
    """{game_id: GameCtx} for EuroLeague games tipping from IN_PROGRESS_MIN
    before `now` to an hour after it, with no final score yet."""
    from data.db import release_read
    lo = (now - timedelta(minutes=IN_PROGRESS_MIN)).isoformat()
    hi = (now + timedelta(hours=1)).isoformat()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.game_date, g.season, g.home_team, g.away_team, g.commence_time,
                   e.season_code, e.game_code
              FROM games g JOIN euroleague_events e USING (game_id)
             WHERE g.sport = 'EUROLEAGUE' AND g.home_score IS NULL
               AND g.commence_time::timestamptz BETWEEN %s::timestamptz AND %s::timestamptz
        """, (lo, hi)).fetchall()
    finally:
        release_read(conn)
    out = {}
    for gid, gd, season, home, away, ct, code, n in rows:
        tip = pd.to_datetime(ct, utc=True, format="mixed", errors="coerce") if ct else None
        if tip is None or pd.isna(tip) or not code or n is None:
            continue
        out[str(gid)] = GameCtx(str(gid), str(gd)[:10], int(season), str(home), str(away), tip, str(code).strip(),
                                int(n))
    return out


def load_prior(conn, ctx: GameCtx, first_shot) -> None:
    """Pinnacle's pre-game numbers for one game (M.PRIOR_CLOSE_SQL, M.prior_from_pinnacle),
    stamped at or before min(tip, the game's first shot)."""
    from data.db import release_read
    try:
        rows = conn.execute(M.PRIOR_CLOSE_SQL, (ctx.game_id,)).fetchall()
    finally:
        release_read(conn)
    before = ctx.tip if first_shot is None else min(ctx.tip, pd.Timestamp(first_shot))
    p = M.prior_from_pinnacle(rows, before=before)
    if p is None:
        ctx.refused = "no coherent Pinnacle pre-game spread and total stored: no pre-game number"
        return
    ctx.prior = p


# ─── the ledger, the picks ────────────────────────────────────────────────────

LEDGER_COLS = ("game_id", "model_id", "game_date", "fetch_at", "outcome", "reason", "market", "book",
               "side", "line", "price", "ev", "p_win", "p_push", "model_mean", "model_sd", "prior_m",
               "prior_t", "quote_at", "h_pts", "a_pts", "first_shot", "last_q2_shot", "api_read_at",
               "artifact_version", "offers")


def ledger_ready(conn) -> bool:
    from data.db import release_read
    try:
        row = conn.execute(f"SELECT to_regclass('public.{LEDGER}')").fetchone()
        return bool(row and row[0])
    finally:
        release_read(conn)


def decided_games(conn, game_ids) -> set:
    from data.db import release_read
    if not game_ids:
        return set()
    try:
        rows = conn.execute(f"SELECT game_id FROM {LEDGER} WHERE game_id = ANY(%s) AND model_id = %s "
                            f"AND outcome = ANY(%s)", (sorted(game_ids), M.MODEL_ID, list(FINAL))).fetchall()
        return {str(r[0]) for r in rows}
    finally:
        release_read(conn)


def _py_ts(x):
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return None
    t = pd.Timestamp(x)
    return (t.tz_localize("UTC") if t.tzinfo is None else t).to_pydatetime()


def ledger_row(ctx: GameCtx, best: dict | None, offers: pd.DataFrame | None, outcome: str, reason: str,
               fetch_at, half=None, api_read_at=None, version: str = "") -> dict:
    b = best or {}
    js = None
    if offers is not None and len(offers):
        keep = [c for c in M.OFFER_COLS if c in offers and c not in ("mean", "sd")]
        recs = offers[keep].astype(object).where(offers[keep].notna(), None).to_dict("records")
        js = json.dumps(recs, default=str)
    return {"game_id": ctx.game_id, "model_id": M.MODEL_ID, "game_date": ctx.game_date,
            "fetch_at": fetch_at, "outcome": outcome, "reason": (reason or "")[:500], "market": M.MARKET,
            "book": b.get("book"), "side": b.get("side"), "line": _num(b.get("line")),
            "price": _num(b.get("price")), "ev": _num(b.get("ev")), "p_win": _num(b.get("prob")),
            "p_push": _num(b.get("p_push")), "model_mean": _num(b.get("mean")), "model_sd": _num(b.get("sd")),
            "prior_m": _num(ctx.prior[0]) if ctx.prior else None,
            "prior_t": _num(ctx.prior[1]) if ctx.prior else None,
            "quote_at": _py_ts(b.get("stamp")),
            "h_pts": None if half is None else half.ht_home, "a_pts": None if half is None else half.ht_away,
            "first_shot": None if half is None else _py_ts(half.first_shot),
            "last_q2_shot": None if half is None else _py_ts(half.last_q2_shot),
            "api_read_at": api_read_at, "artifact_version": version, "offers": js}


def insert_ledger(conn, row: dict) -> bool:
    """One row. A final row returns False when the game already holds one: the
    first stands. A 'skipped' or 'carried' row is always written."""
    cols = ", ".join(LEDGER_COLS)
    vals = ", ".join(f"%({c})s" for c in LEDGER_COLS)
    params = {c: row.get(c) for c in LEDGER_COLS}
    if row.get("outcome") not in FINAL:
        cur = conn.execute(f"INSERT INTO {LEDGER} ({cols}) VALUES ({vals}) RETURNING game_id", params)
    else:
        cur = conn.execute(f"INSERT INTO {LEDGER} ({cols}) VALUES ({vals}) "
                           f"ON CONFLICT (game_id, model_id) WHERE outcome IN ('bet', 'no_bet', 'declined', "
                           f"'missed') DO NOTHING RETURNING game_id", params)
    return cur.fetchone() is not None


def live_destination() -> str | None:
    """Where a EuroLeague live pick posts, else None (config.DISCORD_LIVE_CHANNEL_REQUIRED:
    no fallback to the shared live channel or the sport's pre-game channel)."""
    import config
    if config.DISCORD_WEBHOOKS_LIVE.get(SPORT):
        return "DISCORD_WEBHOOK_LIVE_EUROLEAGUE"
    if (getattr(config, "DISCORD_CHANNELS_LIVE", None) or {}).get(SPORT):
        return "DISCORD_CHANNEL_LIVE_EUROLEAGUE"
    return None


def standing_spreads(conn, game_id: str) -> list[dict]:
    """The game's standing full-game spread and moneyline bets, pre-game and
    live, each as a spread (a moneyline at -0.5 home / +0.5 away)."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT model_id, pick_side, scored_line, pick_label FROM picks
             WHERE game_id = %s AND signal_type = 'BET' AND model_id = ANY(%s)
               AND condition_status IS DISTINCT FROM 'VOID'
        """, (game_id, list(FULL_GAME_SPREAD_MODELS + FULL_GAME_MONEYLINE_MODELS))).fetchall()
    finally:
        release_read(conn)
    out = []
    for m, s, ln, lb in rows:
        if s not in ("home", "away"):
            continue
        if m in FULL_GAME_MONEYLINE_MODELS:
            out.append({"model_id": m, "market": M.MARKET, "side": s,
                        "line": -0.5 if s == "home" else 0.5, "label": lb})
        elif ln is not None:
            out.append({"model_id": m, "market": M.MARKET, "side": s, "line": float(ln), "label": lb})
    return out


def build_pick(ctx: GameCtx, best: dict, offers: pd.DataFrame, half, links: dict, bankroll: float) -> dict:
    """One `picks` row from one BET. scored_line is the HOME number taken
    (CLAUDE.md 4); model_probability is P(win | no push). The DraftKings
    columns are DraftKings' own quote on the same side at the same home number
    in this read, else NULL."""
    from models.scorer import _confidence_tier, quarter_kelly
    side, book, price, line = best["side"], best["book"], float(best["price"]), float(best["line"])
    prob = float(best["prob"])
    implied = 1.0 / float(M.decimal(price))
    dk = None
    if offers is not None and len(offers):
        o = offers[(offers["book"] == "draftkings") & ((offers["line"] - line).abs() < 1e-9)]
        o = o[o[f"{side}_price"].notna()]
        if len(o):
            dk = o.iloc[0]
    dk_odds = None if dk is None else float(dk[f"{side}_price"])
    dk_implied = None if dk is None else 1.0 / float(M.decimal(dk_odds))
    dk_prob = None if dk is None else float(dk["prob"] if dk["side"] == side else 1.0 - dk["prob"])
    edge = 0.0 if dk is None else dk_prob - dk_implied
    kf, rec = quarter_kelly(prob, implied, bankroll)
    return {
        "game_id": ctx.game_id, "model_id": M.MODEL_ID, "sport": SPORT,
        "game_date": ctx.game_date, "game_time": ctx.tip.isoformat(),
        "pick_side": side, "pick_label": M.pick_label(side, line, ctx.home, ctx.away),
        "model_probability": round(prob, 4),
        "dk_implied_prob": None if dk_implied is None else round(dk_implied, 4),
        "edge": round(edge, 4), "dk_odds": dk_odds,
        "scored_line": line,                         # the HOME number taken (CLAUDE.md 4)
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "injury_flag": None, "injury_detail": None,
        "signal_type": "BET", "confidence_tier": _confidence_tier(prob - implied),
        "is_live": True,
        "inning_at_pick": 2,                         # the quarter just played, in the shared column
        "score_diff_at_pick": int(half.ht_home - half.ht_away),      # home minus away
        "dk_bet_link": links.get(("draftkings", side)) if dk is not None else None,
        "best_book": book, "best_odds": price, "best_implied_prob": round(implied, 4),
        "best_edge": round(prob - implied, 4), "best_bet_link": links.get((book, side)),
        "line_book": None if (dk is not None or book == "draftkings") else book,
        "decision_book": book, "decision_odds": price,
        "decision_implied_prob": round(implied, 4), "decision_edge": round(prob - implied, 4),
    }


def unsettled_bet_dates(conn) -> set:
    from data.db import release_read
    since = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
    try:
        rows = conn.execute("""
            SELECT DISTINCT game_date FROM picks
             WHERE model_id = %s AND is_live = TRUE AND signal_type = 'BET'
               AND result IS NULL AND game_date >= %s
        """, (M.MODEL_ID, since)).fetchall()
        return {str(r[0])[:10] for r in rows}
    finally:
        release_read(conn)


def record_credits(conn, credits: int | None) -> None:
    if credits is None:
        return
    from data.ingestors.live_odds_ingestor import record_credits as rec
    rec(conn, BULK_PURPOSE, int(credits))
    conn.commit()


def why_none(offers: pd.DataFrame | None) -> str:
    """Why a read inside the break held no eligible quote, in words."""
    if offers is None or not len(offers):
        return "no spread quoted for this game in the read"
    n = len(offers)
    bettable = int(offers["book"].isin(deciding_books()).sum())
    fresh = int(offers["fresh"].sum())
    return (f"{n} spread quote(s), {bettable} at a bettable book, {fresh} re-hung after the half's last shot; "
            f"none passed every check")


def near_half(ctx: GameCtx, now: datetime) -> bool:
    m = (pd.Timestamp(now) - ctx.tip).total_seconds() / 60
    return NEAR_HALF_MIN[0] <= m <= NEAR_HALF_MIN[1]


def in_progress(ctx: GameCtx, now: datetime) -> bool:
    m = (pd.Timestamp(now) - ctx.tip).total_seconds() / 60
    return 0.0 <= m <= IN_PROGRESS_MIN


def same_half(a, b) -> bool:
    return (a.ht_home, a.ht_away) == (b.ht_home, b.ht_away) and a.last_q2_shot == b.last_q2_shot


# ─── the loop ─────────────────────────────────────────────────────────────────

class Loop:
    """One process's state across a slate. tick() is one pass; the feeds, the
    connection factory and the clock are injected so a test can drive a read."""

    def __init__(self, art: M.Artifact, api, feed, connect, *, dry_run: bool = False, clock=None,
                 read_slots: Slots | None = None, resolver_factory=None):
        self.art, self.api, self.feed, self.connect = art, api, feed, connect
        self.dry_run = dry_run
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.slots = read_slots or slots()
        self.resolver_factory = resolver_factory
        self.conn = None
        self.windows: dict = {}
        self.ctxs: dict = {}                   # game_id -> GameCtx
        self.decided: set = set()              # game ids holding a final row
        self.bet_dates: set = set()
        self.bets_written = 0
        self.bankroll = None
        self.last_slate_read = None
        self.last_beat = None
        self.blocked = None

    def c(self):
        if self.conn is None:
            self.conn = self.connect()
        return self.conn

    def recycle(self):
        self.conn = _recycle(self.conn)

    def slate(self, now: datetime) -> list:
        t = time.monotonic()
        if self.last_slate_read is None or t - self.last_slate_read >= SLATE_EVERY_SEC:
            try:
                fresh = slate_games(self.c(), now)
                for k, v in fresh.items():
                    self.ctxs.setdefault(k, v)
                for k in [k for k in self.ctxs if k not in fresh]:
                    self.ctxs.pop(k)           # a final score stored, or out of the window
                self.last_slate_read = t
            except Exception as exc:                  # noqa: BLE001
                log.error("slate read failed: %s", exc)
                self.recycle()
                if self.last_slate_read is None:
                    return None
        return [c for c in self.ctxs.values() if in_progress(c, now)]

    def heartbeat(self, in_play: int) -> None:
        if self.dry_run:
            return
        t = time.monotonic()
        if self.last_beat is not None and t - self.last_beat < HEARTBEAT_EVERY_SEC:
            return
        self.last_beat = t
        try:
            from tracking.job_heartbeat import beat
            beat("euroleague_live", "ok", f"running: {in_play} game(s) in play, {self.bets_written} bet(s) written")
        except Exception as exc:                      # noqa: BLE001
            log.warning("heartbeat failed (non-fatal): %s", exc)

    def note(self, c: GameCtx, outcome: str, reason: str, fetch_at=None, half=None, offers=None,
             api_read_at=None) -> str:
        (log.warning if outcome == "skipped" else log.info)("%s %s: %s", outcome.upper(), c.game_id, reason)
        if outcome in FINAL:
            self.decided.add(c.game_id)
        if not self.dry_run:
            try:
                insert_ledger(self.c(), ledger_row(c, None, offers, outcome, reason, fetch_at, half, api_read_at,
                                                   self.art.version))
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("could not record the %s row for %s: %s", outcome, c.game_id, exc)
                self.recycle()
        return "retry" if outcome == "skipped" else outcome

    def tick(self) -> dict:
        now = self.clock()
        live = self.slate(now)
        if live is None:
            return {"live": None}
        if not live:
            return {"live": 0}
        self.heartbeat(len(live))
        inst = self.slots.instant(now)
        res = {"live": len(live), "slot": inst, "decisions": 0}
        if inst is None:
            return res
        if live_destination() is None:
            self.blocked = ("neither DISCORD_WEBHOOK_LIVE_EUROLEAGUE nor DISCORD_CHANNEL_LIVE_EUROLEAGUE is set on "
                            "this service: a EuroLeague live bet would never post, so none is decided")
            res["blocked"] = self.blocked
            return res
        st = self.windows.setdefault(inst, SlotState())
        if st.closed or (st.last_attempt is not None
                         and (now - st.last_attempt).total_seconds() < RETRY_GAP_SEC):
            return res
        if not self.dry_run:
            try:
                self.decided |= decided_games(self.c(), {c.game_id for c in live})
            except Exception as exc:                  # noqa: BLE001
                log.error("ledger read failed - read %s not tried this tick: %s", inst.isoformat(), exc)
                self.recycle()
                return res
        todo = [c for c in live if c.refused is None and c.game_id not in self.decided and near_half(c, now)
                and (st.pending is None or c.game_id in st.pending)]
        if not todo:
            st.closed = True
            return res
        st.last_attempt = now
        st.attempts += 1
        n, outcomes = self.run_slot(inst, todo)
        st.pending = {gid for gid, o in outcomes.items() if o == "retry"}
        st.closed = not st.pending
        res["decisions"] = n
        return res

    def read_half(self, c: GameCtx):
        """(HalfRead or None, when it was read)."""
        from data.ingestors.euroleague_live_feed import read_half
        ans = self.api.game(c.season_code, c.game_code)
        at = self.clock()
        return (None if ans is None else read_half(ans, c.home, c.away)), at

    def run_slot(self, slot: datetime, todo: list) -> tuple:
        out: dict = {}
        brk = []                                       # (ctx, HalfRead, read at)
        for c in todo:
            h, at = self.read_half(c)
            if h is None:
                out[c.game_id] = self.note(c, "skipped", "EuroLeague's API did not answer", api_read_at=at)
            elif h.status == "unreadable":
                out[c.game_id] = self.note(c, "skipped", f"EuroLeague's API: {h.problem}", api_read_at=at)
            elif h.status == "first_half":
                out[c.game_id] = "early"
            elif h.status == "second_half":
                out[c.game_id] = self.note(c, "missed", "the third quarter began with no eligible quote seen",
                                           half=h, api_read_at=at)
            elif h.problem:
                out[c.game_id] = self.note(c, "skipped", h.problem, half=h, api_read_at=at)
            elif self.clock() <= h.last_q2_shot + pd.Timedelta(seconds=M.BUFFER_S):
                out[c.game_id] = "early"
            else:
                brk.append((c, h, at))
        for c, h, at in brk:
            if c.prior is None and c.refused is None:
                try:
                    load_prior(self.c(), c, h.first_shot)
                except Exception as exc:              # noqa: BLE001
                    self.recycle()
                    out[c.game_id] = self.note(c, "skipped", f"the pre-game number could not be read: "
                                                             f"{type(exc).__name__}", half=h, api_read_at=at)
                    continue
                if c.refused:
                    out[c.game_id] = self.note(c, "skipped", f"refused: {c.refused}", half=h, api_read_at=at)
                    out[c.game_id] = "refused"
        brk = [(c, h, at) for c, h, at in brk if c.game_id not in out and c.prior is not None]
        if not brk:
            return 0, out
        if self.dry_run:
            log.info("[dry-run] read %s: would fetch the board for %s", slot.isoformat(),
                     ", ".join(c.game_id for c, _h, _a in brk))
            return 0, {**out, **{c.game_id: "carried" for c, _h, _a in brk}}
        try:
            ok, why = under_daily_cap(self.c(), CALL_CREDITS), "LIVE_DAILY_CREDIT_CAP would be exceeded"
        except Exception as exc:                      # noqa: BLE001
            self.recycle()
            ok, why = False, f"credit cap read failed: {type(exc).__name__}"
        fetch = self.feed.fetch() if ok else None
        if fetch is None:
            for c, h, at in brk:
                out[c.game_id] = self.note(c, "skipped", why if not ok else "no odds from the feed (call failed or "
                                                                            "a cap)", half=h, api_read_at=at)
            return 0, out
        try:
            return self._after_fetch(brk, fetch, out)
        except Exception as exc:                      # noqa: BLE001
            log.exception("read %s failed after the fetch: %s", slot.isoformat(), exc)
            self.recycle()
            for c, h, at in brk:
                if c.game_id not in out:
                    out[c.game_id] = self.note(c, "skipped", f"the read could not be used: {type(exc).__name__}",
                                               fetch.fetched_at, h, api_read_at=at)
            return 0, out

    def _resolver(self):
        if self.resolver_factory is not None:
            return self.resolver_factory()
        from data.ingestors import euroleague_teams
        return euroleague_teams.make_resolver(self.c(), self.clock().date().isoformat())

    def _after_fetch(self, brk: list, fetch, out: dict) -> tuple:
        from data.ingestors.euroleague_live_feed import rows_from_events
        try:
            record_credits(self.c(), fetch.credits)
        except Exception as exc:                      # noqa: BLE001
            log.warning("credit telemetry failed (non-fatal): %s", exc)
            self.recycle()
        served = fetch.fetched_at
        started = {c.game_id for c in self.ctxs.values() if c.tip <= pd.Timestamp(served)}
        rows = rows_from_events(fetch.events, served, self._resolver(), started)
        if rows:
            try:
                from data.ingestors.live_price_log import record_live_prices
                record_live_prices(self.c(), rows, known_game_ids=started)
            except Exception as exc:                  # noqa: BLE001
                log.warning("live price log failed (non-fatal): %s", exc)
                self.recycle()
        q_all = quotes_frame(rows, served)
        q_sp = q_all[q_all["market"] == M.MARKET]
        links: dict = {}
        for r_ in rows:
            if r_.get("market") != M.MARKET:
                continue
            for side in ("home", "away"):
                if r_.get(f"{side}_link"):
                    links.setdefault((r_["game_id"], r_.get("bookmaker"), side), r_.get(f"{side}_link"))
        decisions = []                                 # (ctx, Read, half, read at, links)
        for c, h0, _at0 in brk:
            try:
                h, at = self.read_half(c)
                if h is None or h.status == "unreadable" or (h.status == "break" and h.problem):
                    why = "EuroLeague's API did not answer after the call" if h is None else (h.problem or "unreadable")
                    out[c.game_id] = self.note(c, "skipped", f"second read: {why}", served, h0, api_read_at=at)
                    continue
                if h.status == "first_half" or not same_half(h0, h):
                    out[c.game_id] = self.note(c, "skipped", "the half changed between the two reads of EuroLeague's "
                                                             "API", served, h, api_read_at=at)
                    continue
                q3_at = None
                if h.status == "second_half":
                    q3_at = h.q3_at if h.q3_at is not None else pd.Timestamp(served)
                half = M.Half(h.first_shot, h.last_q2_shot, int(h.ht_home), int(h.ht_away), q3_at)
                r = M.read_break(q_sp[q_sp["game_id"] == c.game_id], served, half, c.prior[0], self.art.margin,
                                 deciding_books())
                if r.status == "early":
                    out[c.game_id] = "early"
                elif r.status == "past":
                    out[c.game_id] = self.note(c, "missed", "the third quarter began with no eligible quote seen",
                                               served, h, r.offers, at)
                elif r.status == "none":
                    out[c.game_id] = self.note(c, "carried", why_none(r.offers), served, h, r.offers, at)
                else:
                    decisions.append((c, r, h, at, {(bk, sd): ln for (gid, bk, sd), ln in links.items()
                                                    if gid == c.game_id}))
                    out[c.game_id] = "decided"
            except Exception as exc:                  # noqa: BLE001
                log.exception("%s failed: %s", c.game_id, exc)
                self.recycle()
                out[c.game_id] = self.note(c, "skipped", f"evaluation failed: {type(exc).__name__}: {exc}", served,
                                           h0)
        return self.decide(decisions, served), out

    def decide(self, decisions: list, served) -> int:
        """Record every decision of this read, best EV first, betting those at or above the cut."""
        from models.euroleague_quote_bounds import edge_problem
        cut = self.art.cut
        for c, r, h, at, links in sorted(decisions, key=lambda d: -float(d[1].best["ev"])):
            b, pick = r.best, None
            ev = float(b["ev"])
            if ev < cut:
                outcome, reason = "no_bet", f"EV {ev:.3f} under the cut {cut:.2f}"
            else:
                outcome, reason = "bet", "BET"
                mine = {"market": M.MARKET, "side": b["side"], "line": float(b["line"])}
                # a failed read here raises: the game stays undecided and the next read tries again
                held = None if self.dry_run else next(
                    (s for s in standing_spreads(self.c(), c.game_id) if cannot_both_win(mine, s)), None)
                if held is not None:
                    outcome, reason = "declined", f"cannot both win with {held.get('label') or held['model_id']}"
                else:
                    if self.bankroll is None and not self.dry_run:
                        try:
                            from models.scorer import _get_current_bankroll
                            self.bankroll = float(_get_current_bankroll(self.c()))
                        except Exception as exc:      # noqa: BLE001
                            log.warning("bankroll read failed (sizing at 0): %s", exc)
                            self.recycle()
                    try:
                        pick = build_pick(c, b, r.offers, h, links, self.bankroll or 0.0)
                        why = (platform_gates(M.MODEL_ID, pick["model_probability"], pick["decision_odds"])
                               or edge_problem(pick["decision_edge"], M.MODEL_ID))
                    except Exception as exc:          # noqa: BLE001
                        log.exception("building the pick for %s failed: %s", c.game_id, exc)
                        pick, why = None, f"the pick could not be built: {type(exc).__name__}: {exc}"
                    if why:
                        outcome, reason, pick = "declined", why, None
            log.info("DECIDED %s %s @ %s at the half %s-%s: %s %s", c.game_id, c.away, c.home, h.ht_home, h.ht_away,
                     outcome.upper(),
                     f"{pick['pick_label']} {pick['decision_book']} {pick['decision_odds']:+.0f} (EV {ev:.3f})"
                     if pick else reason)
            self.decided.add(c.game_id)
            if self.dry_run:
                continue
            try:
                if not insert_ledger(self.c(), ledger_row(c, b, r.offers, outcome, reason, served, h, at,
                                                          self.art.version)):
                    self.c().rollback()
                    log.info("%s already decided - nothing written", c.game_id)
                    continue
                if pick is not None and write_bet(self.c(), pick):
                    self.bets_written += 1
                    self.bet_dates.add(c.game_date)
                    log.info("WROTE BET %s at %s %+.0f", pick["pick_label"], pick["decision_book"],
                             pick["decision_odds"])
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("write failed for %s (non-fatal): %s", c.game_id, exc)
                self.recycle()
        return len(decisions)


def main(argv=None) -> int:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("euroleague-live")
    except Exception:                                 # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=POLL_SEC)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    import config
    from data.db import get_connection, use_poller_session
    from data.ingestors.euroleague_live_feed import EuroleagueApi, odds_feed
    if M.MODEL_ID not in config.LIVE_MODELS:
        log.error("%s is not in config.LIVE_MODELS: it would never settle - exiting", M.MODEL_ID)
        return 1
    art = M.load_artifact()
    log.info("artifact %s; %s at EV >= %.2f; a read at each five-minute mark plus %.0fs (window %.0fs); "
             "EuroLeague's API read before and after each bulk call", art.version, M.MODEL_ID, art.cut,
             M.FETCH_AFTER_SEC, FETCH_WINDOW_SEC)
    use_poller_session()
    loop = Loop(art, EuroleagueApi(), odds_feed(CALL_CAP, CREDIT_CAP), get_connection, dry_run=a.dry_run)
    if not a.dry_run:
        try:
            if not ledger_ready(loop.c()):
                log.error("table %s is missing (data/migrations/euroleague_live_decisions_2026_11_13.sql, applied "
                          "by data.view_migrations): no decision can be recorded, so none is made - exiting", LEDGER)
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
                log.error("EUROLEAGUE LIVE DECIDES NOTHING: %s. Set one of them on this service and redeploy "
                          "(docs/cloud_worker.md). Exiting with code 3 so the job reads failed.", res["blocked"])
                return 3
            if res.get("live") is None:
                fails += 1
                if fails >= 20:
                    log.error("the slate could not be read for %d ticks - exiting", fails)
                    return 1
            else:
                fails = 0
            if res.get("live") == 0:
                idle += 1
                if idle >= IDLE_EXIT_TICKS or a.once:
                    if loop.bet_dates and not a.dry_run:
                        for d_ in sorted(loop.bet_dates):
                            notify_live(d_)
                    log.info("no EuroLeague game in progress for %d tick(s) - exiting (%d BETs written, %d odds "
                             "calls, %d credits, %d EuroLeague API calls)", idle, loop.bets_written, loop.feed.calls,
                             loop.feed.credits_used, loop.api.calls)
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
                log.info("--once: %s; %d BETs written; EuroLeague API calls %d, odds calls %d, credits %d", res,
                         loop.bets_written, loop.api.calls, loop.feed.calls, loop.feed.credits_used)
                return 0
            time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
    finally:
        if loop.conn is not None:
            try:
                loop.conn.close()
            except Exception:                         # noqa: BLE001
                pass


if __name__ == "__main__":
    sys.exit(main())
