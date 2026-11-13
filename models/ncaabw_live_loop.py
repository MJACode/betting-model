"""
Women's college basketball halftime loop: the one rule of models/ncaabw_live_ht
(the full-game total, bet during the halftime break).

    python -m models.ncaabw_live_loop              # the real thing
    python -m models.ncaabw_live_loop --dry-run    # look and log; write nothing, no paid call
    python -m models.ncaabw_live_loop --once       # one pass, then exit

Run from the REPO ROOT. scheduler.py relaunches it every 10 minutes from 11am
to 2:50am ET (max_instances=1); it exits by itself after a few idle ticks with
no women's game in progress.

THE CADENCE IS THE GRADE'S FIVE-MINUTE SNAPSHOT. The graded decision is "the
first read of the halftime break holding an eligible quote", and the history
it was graded on holds one snapshot every five minutes, stamped 36 to 39
seconds after the mark. So the loop reads the board at each five-minute mark
plus M.FETCH_AFTER_SEC and at no other time: a loop reading every few seconds
would decide every game in the first seconds of its break, on the first book
to re-post, a population never graded. A break lasts about fifteen minutes, so
a game gets two or three reads.

ONE PASS (every NCAABW_LIVE_POLL_SEC, default 15 s)
  1. ESPN's women's Division I scoreboard for each slate date
     (config.live_slate_dates()).
  2. No game in progress for IDLE_EXIT_TICKS ticks: announce standing bets and exit.
  3. At a read instant, while an undecided game is in its second quarter, at
     halftime or in its third quarter on the scoreboard: ONE bulk Odds API call
     (moneylines, spreads and totals at the seventeen books the history was
     bought at; 6 credits), its rows to `odds` as in_play (source
     ncaabw_live_loop).
  4. Wait PBP_WAIT_SEC after the read, fetch each game's ESPN summary, wait
     PBP_RECHECK_SEC and fetch it again (the waits are the men's loop's: ESPN
     served men's college scoring plays a median 37 s after their wallclock,
     58 s at the longest, 2026-11-07; the women's lag is logged per decision as
     play_lag_s and not yet measured). Fail closed: a play logged at or before
     the read that only the second fetch carries, or ESPN's header score
     differing from the play list's, skips that game at that read.
  5. Per game: models.ncaabw_live_ht.read_break, the grade's code. Before the
     half has ended: nothing. In the break with no eligible quote: a 'carried'
     row, and the next read tries again. In the break with one: the decision,
     written to ncaabw_live_decisions FIRST (one final row a game, never
     replaced), then a BET to `picks` under the first-signal live lock, then
     announced (push, then #ncaabw-live; no other channel). Third quarter under
     way with nothing decided: a final 'missed' row.

WHAT IS NOT HERE, AND WHY (each a named difference from the house's other
live loops):
  * No BookMoveClock: it anchors a book's number between changes in our state
    and needs a series of quotes; this loop sees one quote per book per five
    minutes. The grade's freshness rule (no point between a quote's stamp and
    the read) is applied instead.
  * No 10-game wait: the prior is the market's pre-game total.
  * No nightly count: every decision at or above the cut is bet (mike has not
    set a number; the graded seasons made a median 3 bets on a day with one,
    25 at the most).
  * One game never carries two bets that cannot both win (mike, 2026-10-17):
    a halftime bet that cannot win together with the game's standing pre-game
    total bet is declined.
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

from models import cbb_pairs  # noqa: E402
from models import ncaabw_live_ht as M  # noqa: E402
from models.ncaab_live_ig import cannot_both_win  # noqa: E402
from models.ncaab_live_loop import (Slots, SlotState, _num, _recycle, platform_gates,  # noqa: E402
                                    quotes_frame, under_daily_cap, write_bet)

log = logging.getLogger("models.ncaabw_live_loop")

SPORT = M.SPORT
POLL_SEC = float(os.environ.get("NCAABW_LIVE_POLL_SEC", "15"))
PBP_WAIT_SEC = float(os.environ.get("NCAABW_LIVE_PBP_WAIT_SEC", "90"))
PBP_RECHECK_SEC = float(os.environ.get("NCAABW_LIVE_PBP_RECHECK_SEC", "60"))
# A read whose call failed is tried again inside this window; one that reached
# ESPN's two fetches has used the window up and waits for the next mark.
FETCH_WINDOW_SEC = float(os.environ.get("NCAABW_LIVE_FETCH_WINDOW_SEC", "120"))
RETRY_GAP_SEC = float(os.environ.get("NCAABW_LIVE_RETRY_GAP_SEC", "45"))
HEARTBEAT_EVERY_SEC = 300.0
IDLE_EXIT_TICKS = int(os.environ.get("NCAABW_LIVE_IDLE_EXIT_TICKS", "3"))
FEED_FAIL_EXIT_TICKS = int(os.environ.get("NCAABW_LIVE_FEED_FAIL_EXIT_TICKS", "60"))
# A slate day spans at most ~16 hours of five-minute marks (192), each tried at
# most three times: 6 credits a call.
CALL_CAP = int(os.environ.get("NCAABW_LIVE_CALL_CAP", "600"))
CREDIT_CAP = int(os.environ.get("NCAABW_LIVE_CREDIT_CAP", "3600"))
CALL_CREDITS = 6
LEDGER = "ncaabw_live_decisions"
FINAL = ("bet", "no_bet", "declined", "missed")
BULK_PURPOSE = "ncaabw_live_bulk:h2h,spreads,totals"
# THE FAST WAY (mike, 2026-11-13: "Move everything over to the fast way"). The
# break's score is frozen, so ESPN's two waits buy nothing once every play of
# the first half is published: a read at least HT_SETTLED_SEC after the half's
# last play is judged on ESPN's summary read at once (ESPN published a college
# play at most 92 s after its wallclock, 2026-11-12/13). And DraftKings' total
# in the read is DraftKings' own board's (models/ncaab_live_dk.py), stamped
# where the board first showed it, while that feed is seconds old; the other
# books stay the provider's (the rule needs two of them beside the decider).
HT_SETTLED_SEC = float(os.environ.get("NCAABW_LIVE_HT_SETTLED_SEC", "120"))
DK_ON = os.environ.get("NCAABW_LIVE_DK", "1") != "0"
SUMMARY_THREADS = 16

# The models that bet a women's full-game total: no two of their bets on one
# game may be unable to win together.
FULL_GAME_TOTAL_MODELS = ("ncaabw_total_blend", M.MODEL_ID)


def deciding_books() -> tuple:
    import config
    return tuple(config.BEST_LINE_BOOKMAKERS)


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
    espn_event_id: int
    home_espn_id: int | None
    away_espn_id: int | None
    prior: tuple | None = None              # (expected home margin, pre-game total)
    refused: str | None = None


def slate_games(conn, dates) -> dict:
    """{espn_event_id: GameCtx} for the women's games of the slate dates."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.game_date, g.season, g.home_team, g.away_team, g.commence_time,
                   e.espn_event_id, e.home_espn_id, e.away_espn_id
              FROM games g JOIN ncaabw_events e USING (game_id)
             WHERE g.sport = 'NCAABW' AND g.game_date = ANY(%s)
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


def load_prior(conn, ctx: GameCtx) -> None:
    """The grade's pre-game numbers for one game (M.PRIOR_CLOSE_SQL, M.prior_from_closes)."""
    from data.db import release_read
    try:
        rows = conn.execute(M.PRIOR_CLOSE_SQL, (ctx.game_id,)).fetchall()
    finally:
        release_read(conn)
    p = M.prior_from_closes(rows)
    if p is None:
        ctx.refused = "no pre-game spread and total stored: no prior"
        return
    ctx.prior = p


# ─── the ledger, the picks ────────────────────────────────────────────────────

LEDGER_COLS = ("game_id", "model_id", "game_date", "fetch_at", "outcome", "reason", "market", "book",
               "side", "line", "price", "ev", "p_win", "p_push", "model_mean", "model_sd", "mu_pre",
               "t_pre", "quote_at", "h_pts", "a_pts", "play_lag_s", "artifact_version", "offers")


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


def ledger_row(ctx: GameCtx, best: dict | None, offers: pd.DataFrame | None, outcome: str, reason: str,
               fetch_at, state: dict, lag, version: str) -> dict:
    b = best or {}
    js = None
    if offers is not None and len(offers):
        keep = [c for c in M.OFFER_COLS if c in offers and c not in ("mean", "sd")]
        recs = offers[keep].astype(object).where(offers[keep].notna(), None).to_dict("records")
        js = json.dumps(recs, default=str)
    stamp = b.get("stamp")
    if stamp is not None:
        stamp = pd.Timestamp(stamp)
        stamp = (stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp).to_pydatetime()
    return {"game_id": ctx.game_id, "model_id": M.MODEL_ID, "game_date": ctx.game_date,
            "fetch_at": fetch_at, "outcome": outcome, "reason": (reason or "")[:500], "market": M.MARKET,
            "book": b.get("book"), "side": b.get("side"), "line": _num(b.get("line")),
            "price": _num(b.get("price")), "ev": _num(b.get("ev")), "p_win": _num(b.get("prob")),
            "p_push": _num(b.get("p_push")), "model_mean": _num(b.get("mean")),
            "model_sd": _num(b.get("sd")),
            "mu_pre": _num(ctx.prior[0]) if ctx.prior else None,
            "t_pre": _num(ctx.prior[1]) if ctx.prior else None,
            "quote_at": stamp,
            "h_pts": state.get("h_pts"), "a_pts": state.get("a_pts"), "play_lag_s": _num(lag),
            "artifact_version": version, "offers": js}


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
    """Where a women's live pick posts, else None (config.DISCORD_LIVE_CHANNEL_REQUIRED:
    no fallback to the shared live channel or #ncaabw)."""
    import config
    if config.DISCORD_WEBHOOKS_LIVE.get(SPORT):
        return "DISCORD_WEBHOOK_LIVE_NCAABW"
    if (getattr(config, "DISCORD_CHANNELS_LIVE", None) or {}).get(SPORT):
        return "DISCORD_CHANNEL_LIVE_NCAABW"
    return None


def standing_totals(conn, game_id: str) -> list[dict]:
    """The game's standing full-game total bets, pre-game and live."""
    from data.db import release_read
    try:
        rows = conn.execute("""
            SELECT model_id, pick_side, scored_line, pick_label FROM picks
             WHERE game_id = %s AND signal_type = 'BET' AND model_id = ANY(%s)
               AND condition_status IS DISTINCT FROM 'VOID' AND scored_line IS NOT NULL
        """, (game_id, list(FULL_GAME_TOTAL_MODELS))).fetchall()
    finally:
        release_read(conn)
    return [{"model_id": m, "market": M.MARKET, "side": s, "line": float(ln), "label": lb}
            for m, s, ln, lb in rows if s in ("over", "under")]


def paired_bet(conn, game_id: str, model_id: str, side: str, line: float) -> str | None:
    """Why this bet would sit beside its opposite number on the game (an under
    beside a big favourite's spread bet, either order; models.cbb_pairs), or
    None. One read of `picks`, released."""
    from data.db import release_read
    try:
        return cbb_pairs.clash(conn, game_id, model_id, side, line)
    finally:
        release_read(conn)


def build_pick(ctx: GameCtx, best: dict, offers: pd.DataFrame, state: dict, links: dict,
               bankroll: float) -> dict:
    """One `picks` row from one BET. model_probability is P(win | no push); the
    DraftKings columns are DraftKings' own quote on the same side at the same
    total in this read, else NULL."""
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
        "scored_line": line,                         # the total taken
        "kelly_fraction": kf, "recommended_bet": rec, "bankroll_at_pick": bankroll,
        "injury_flag": None, "injury_detail": None,
        "signal_type": "BET", "confidence_tier": _confidence_tier(prob - implied),
        "is_live": True,
        "inning_at_pick": 2,                         # the quarter just played, in the shared column
        "score_diff_at_pick": int(state["h_pts"] - state["a_pts"]),      # home minus away
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


def notify_live(target_date: str) -> None:
    """Push, then #ncaabw-live (tracking.discord_notifier: NCAABW is in
    config.DISCORD_LIVE_CHANNEL_REQUIRED, so no other channel). Neither may
    break the loop."""
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


# ─── one game at one read ─────────────────────────────────────────────────────

def our_header(summary: dict, ctx: GameCtx) -> dict | None:
    """ESPN's header for the game with the score in OUR orientation
    (h_pts, a_pts), its status and period; None when it cannot be read."""
    from data.ingestors.ncaabw_live_feed import header_state
    hs = header_state(summary)
    if hs is None:
        return None
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    ids = {}
    for c in comp.get("competitors") or []:
        try:
            ids[c.get("homeAway")] = int((c.get("team") or {}).get("id"))
        except (TypeError, ValueError):
            pass
    swapped = (ctx.home_espn_id is not None and ids.get("away") == ctx.home_espn_id
               and ids.get("home") == ctx.away_espn_id)
    h, a = (hs["away"], hs["home"]) if swapped else (hs["home"], hs["away"])
    return {"h_pts": h, "a_pts": a, "status": hs["status"], "period": hs["period"]}


def why_none(offers: pd.DataFrame | None) -> str:
    """Why a read inside the break held no eligible quote, in words."""
    if offers is None or not len(offers):
        return "no total quoted for this game in the read"
    n = len(offers)
    bettable = int(offers["book"].isin(deciding_books()).sum())
    after = int(offers["half_over"].sum())
    return (f"{n} total quote(s), {bettable} at a bettable book, {after} stamped after the half ended; "
            f"none passed every check")


def evaluate_game(ctx: GameCtx, art: M.Artifact, q_totals: pd.DataFrame, summary: dict, served: datetime,
                  now: datetime) -> tuple[M.Read | None, dict]:
    """(M.Read, notes) for one game at one read; (None, {'refused': why}) when
    the play list cannot carry a decision."""
    from data.ingestors.ncaabw_pbp import summary_rows
    rows = summary_rows(summary, espn_game_id=ctx.espn_event_id, game_id=ctx.game_id, season=ctx.season,
                        home_espn_id=ctx.home_espn_id, away_espn_id=ctx.away_espn_id)
    st = M.states_from_rows(rows)
    if st is None:
        return None, {"refused": f"ESPN's play list holds fewer than {M.MIN_PLAYS} usable plays"}
    notes = {"play_lag_s": (now - pd.Timestamp(int(st.wall[-1]), tz="UTC").to_pydatetime()).total_seconds()}
    q = q_totals[q_totals["game_id"] == ctx.game_id]
    return M.read_break(q, st, served, ctx.prior[1], art.total, deciding_books()), notes


def half_settled(summary: dict, ctx: GameCtx, served) -> bool:
    """True when ESPN's play list reached halftime (game seconds at the half)
    at least HT_SETTLED_SEC before the read and has not gone past it: every
    play of the first half has been published, and the break's score is frozen."""
    from data.ingestors.ncaabw_pbp import summary_rows
    rows = summary_rows(summary, espn_game_id=ctx.espn_event_id, game_id=ctx.game_id, season=ctx.season,
                        home_espn_id=ctx.home_espn_id, away_espn_id=ctx.away_espn_id)
    st = M.states_from_rows(rows)
    if st is None or not len(st.gs):
        return False
    at_half = [k for k, g in enumerate(st.gs) if g >= M.HALF_S]
    if not at_half or float(st.gs[-1]) > M.HALF_S:
        return False
    reached = pd.Timestamp(int(st.wall[at_half[0]]), tz="UTC")
    return (pd.Timestamp(served) - reached).total_seconds() >= HT_SETTLED_SEC


def overlay_dk(q_tot: pd.DataFrame, dk: pd.DataFrame, served) -> pd.DataFrame:
    """The read's totals with DraftKings' row replaced by DraftKings' own
    board's (a game the board does not carry keeps the provider's)."""
    dk = dk[(dk["market"] == M.MARKET) & dk["game_id"].isin(set(q_tot["game_id"]))]
    if not len(dk):
        return q_tot
    games = set(dk["game_id"])
    keep = q_tot[~((q_tot["book"] == "draftkings") & q_tot["game_id"].isin(games))]
    add = dk.assign(fetch_at=pd.Timestamp(served))[[c for c in q_tot.columns if c in dk.columns or c == "fetch_at"]]
    out = pd.concat([keep, add.reindex(columns=q_tot.columns)], ignore_index=True)
    return out


# ─── the loop ─────────────────────────────────────────────────────────────────

class Loop:
    """One process's state across a slate. tick() is one pass; the feeds, the
    connection factory and the clock are injected so a test can drive a read."""

    def __init__(self, art: M.Artifact, espn, feed, connect, *, dry_run: bool = False,
                 wait: float = PBP_WAIT_SEC, recheck: float = PBP_RECHECK_SEC, sleep=time.sleep,
                 clock=None, slate_dates=None, read_slots: Slots | None = None, resolver_factory=None,
                 dk=None):
        self.art, self.espn, self.feed, self.connect = art, espn, feed, connect
        self.dk = dk                           # DraftKings' own board (models/ncaab_live_dk.DbSource)
        self.dry_run, self.wait, self.recheck, self.sleep = dry_run, float(wait), float(recheck), sleep
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.slate_dates = slate_dates
        self.slots = read_slots or slots()
        self.resolver_factory = resolver_factory
        self.conn = None
        self.windows: dict = {}
        self.ctxs: dict = {}                   # espn_event_id -> GameCtx
        self.decided: set = set()              # game ids holding a final row
        self.bet_dates: set = set()
        self.bets_written = 0
        self.bankroll = None
        self.last_slate_read = 0.0
        self.last_beat = None
        self.blocked = None

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
            beat("ncaabw_live", "ok", f"running: {in_play} game(s) in play, {self.bets_written} bet(s) written")
        except Exception as exc:                      # noqa: BLE001
            log.warning("heartbeat failed (non-fatal): %s", exc)

    def summary(self, event_id, tries: int = 3, gap_s: float = 5.0):
        for k in range(tries):
            got = self.espn.summary(event_id)
            if got is not None:
                return got
            if k + 1 < tries:
                self.sleep(gap_s)
        return None

    def summaries(self, ctxs: list) -> dict:
        """{game_id: summary or None}, every game read at the same time."""
        if len(ctxs) <= 1:
            return {c.game_id: self.summary(c.espn_event_id) for c in ctxs}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(SUMMARY_THREADS, len(ctxs))) as ex:
            got = list(ex.map(lambda c: self.summary(c.espn_event_id), ctxs))
        return {c.game_id: x for c, x in zip(ctxs, got)}

    def dk_totals(self, game_ids: set, served) -> pd.DataFrame | None:
        """DraftKings' own current totals for these games, or None while the
        feed is not live (mike's machine off): the read then stays the provider's."""
        if self.dk is None:
            return None
        from models import ncaab_live_dk as DK
        try:
            last = self.dk.last_read()
            if not DK.feed_is_live(last, self.clock()):
                return None
            reads = self.dk.reads(game_ids)
        except Exception as exc:                      # noqa: BLE001
            log.warning("DraftKings board read failed (the provider's DraftKings quote stands): %s", exc)
            self.recycle()
            return None
        if not len(reads):
            return None
        return DK.current_quotes(reads, max(pd.Timestamp(last[0]), pd.Timestamp(served)), markets=("totals",))

    def note(self, c: GameCtx, outcome: str, reason: str, fetch_at=None, state: dict | None = None,
             offers=None, lag=None) -> str:
        (log.warning if outcome == "skipped" else log.info)("%s %s: %s", outcome.upper(), c.game_id, reason)
        if outcome in FINAL:
            self.decided.add(c.game_id)
        if not self.dry_run:
            try:
                insert_ledger(self.c(), ledger_row(c, None, offers, outcome, reason, fetch_at, state or {},
                                                   lag, self.art.version))
                self.c().commit()
            except Exception as exc:                  # noqa: BLE001
                log.error("could not record the %s row for %s: %s", outcome, c.game_id, exc)
                self.recycle()
        return outcome

    def tick(self) -> dict:
        from data.ingestors.ncaabw_live_feed import near_half
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
            return res
        if live_destination() is None:
            self.blocked = ("neither DISCORD_WEBHOOK_LIVE_NCAABW nor DISCORD_CHANNEL_LIVE_NCAABW is set on this "
                            "service: a women's live bet would never post, so none is decided")
            res["blocked"] = self.blocked
            return res
        st = self.windows.setdefault(inst, SlotState())
        if st.closed or (st.last_attempt is not None
                         and (now - st.last_attempt).total_seconds() < RETRY_GAP_SEC):
            return res
        if not self.dry_run:
            try:
                self.decided |= decided_games(self.c(), {c.game_id for c, _g in in_play})
            except Exception as exc:                  # noqa: BLE001
                log.error("ledger read failed - read %s not tried this tick: %s", inst.isoformat(), exc)
                self.recycle()
                return res
        todo = [(c, g) for c, g in in_play if c.refused is None and c.game_id not in self.decided
                and near_half(g) and (st.pending is None or c.game_id in st.pending)]
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

    def run_slot(self, slot: datetime, todo: list) -> tuple:
        out: dict = {}
        for c, _g in todo:
            if c.prior is None and c.refused is None:
                try:
                    load_prior(self.c(), c)
                except Exception as exc:              # noqa: BLE001
                    self.recycle()
                    self.note(c, "skipped", f"prior read failed: {type(exc).__name__}")
                    out[c.game_id] = "retry"
                    continue
                if c.refused:
                    log.warning("%s refused: %s", c.game_id, c.refused)
                    out[c.game_id] = "refused"
        todo = [(c, g) for c, g in todo if c.game_id not in out and c.refused is None and c.prior is not None]
        if not todo:
            return 0, out
        if self.dry_run:
            log.info("[dry-run] read %s: would fetch the board for %s", slot.isoformat(),
                     ", ".join(c.game_id for c, _g in todo))
            return 0, {**out, **{c.game_id: "carried" for c, _g in todo}}
        try:
            ok, why = under_daily_cap(self.c(), CALL_CREDITS), "LIVE_DAILY_CREDIT_CAP would be exceeded"
        except Exception as exc:                      # noqa: BLE001
            self.recycle()
            ok, why = False, f"credit cap read failed: {type(exc).__name__}"
        fetch = self.feed.fetch() if ok else None
        if fetch is None:
            for c, _g in todo:
                self.note(c, "skipped", why if not ok else "no odds from the feed (call failed or a cap)")
                out[c.game_id] = "retry"
            return 0, out
        try:
            return self._after_fetch(todo, fetch, out)
        except Exception as exc:                      # noqa: BLE001
            log.exception("read %s failed after the fetch: %s", slot.isoformat(), exc)
            self.recycle()
            for c, _g in todo:
                if c.game_id not in out:
                    out[c.game_id] = self.note(c, "skipped", f"the read could not be used: {type(exc).__name__}",
                                               fetch.fetched_at)
            return 0, out

    def _resolver(self):
        if self.resolver_factory is not None:
            return self.resolver_factory()
        from data.ingestors.ncaabw_teams import make_resolver
        return make_resolver(self.c(), self.dates()[0])

    def _after_fetch(self, todo: list, fetch, out: dict) -> tuple:
        from data.ingestors.ncaabw_live_feed import late_plays, rows_from_events
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
        q_tot = q_all[q_all["market"] == M.MARKET]
        dk = self.dk_totals({c.game_id for c, _g in todo}, served)
        if dk is not None and len(dk):
            q_tot = overlay_dk(q_tot, dk, served)
        links: dict = {}
        for r_ in rows:
            if r_.get("market") != M.MARKET:
                continue
            for side in ("over", "under"):
                if r_.get(f"{side}_link"):
                    links.setdefault((r_["game_id"], r_.get("bookmaker"), side), r_.get(f"{side}_link"))
        # A game whose half ended HT_SETTLED_SEC before the read is judged on
        # ESPN's summary read now; the rest wait as graded.
        now_read = self.summaries([c for c, _g in todo])
        settled = {c.game_id for c, _g in todo
                   if now_read.get(c.game_id) is not None and half_settled(now_read[c.game_id], c, served)}
        slow = [(c, g) for c, g in todo if c.game_id not in settled]
        first = {gid: now_read[gid] for gid in settled}
        second_of = {gid: now_read[gid] for gid in settled}
        if slow:
            left = self.wait - (self.clock() - served).total_seconds()
            if left > 0:
                self.sleep(left)
            first.update(self.summaries([c for c, _g in slow]))
            if self.recheck > 0:
                self.sleep(self.recheck)
            second_of.update(self.summaries([c for c, _g in slow]))
        decisions = []                                 # (ctx, Read, lag, links)
        for c, _g in todo:
            try:
                second = second_of.get(c.game_id)
                if first.get(c.game_id) is None or second is None:
                    out[c.game_id] = self.note(c, "skipped", "ESPN summary unreadable", served)
                    continue
                late = late_plays(first[c.game_id], second, served)
                if late:
                    out[c.game_id] = self.note(
                        c, "skipped", f"ESPN served {len(late)} play(s) logged at or before the read only on "
                                      f"its second fetch (publishing late)", served)
                    continue
                r, notes = evaluate_game(c, self.art, q_tot, second, served, self.clock())
                if r is None:
                    out[c.game_id] = self.note(c, "skipped", notes["refused"], served)
                    continue
                lag = notes.get("play_lag_s")
                if r.status == "early":
                    out[c.game_id] = "early"
                    continue
                hd = our_header(second, c)
                if hd is None:
                    out[c.game_id] = self.note(c, "skipped", "ESPN's header score unreadable", served, r.state)
                    continue
                if r.status == "past":
                    if hd["period"] is not None and hd["period"] < 3:
                        out[c.game_id] = self.note(
                            c, "skipped", f"the play list is past the half and ESPN's header says period "
                                          f"{hd['period']}", served, r.state, lag=lag)
                        continue
                    out[c.game_id] = self.note(c, "missed", "the third quarter began with no eligible quote seen",
                                               served, r.state, lag=lag)
                    continue
                if (hd["h_pts"], hd["a_pts"]) != (r.state["h_pts"], r.state["a_pts"]) \
                        or hd["period"] not in (2, 3):
                    out[c.game_id] = self.note(
                        c, "skipped", f"ESPN's header says {hd['h_pts']}-{hd['a_pts']} in period {hd['period']} "
                                      f"and its play list {r.state['h_pts']}-{r.state['a_pts']} at the half "
                                      f"(home-away)", served, r.state, lag=lag)
                    continue
                if r.status == "none":
                    out[c.game_id] = self.note(c, "carried", why_none(r.offers), served, r.state, r.offers, lag)
                    continue
                decisions.append((c, r, lag, {(bk, sd): ln for (gid, bk, sd), ln in links.items()
                                              if gid == c.game_id}))
                out[c.game_id] = "decided"
            except Exception as exc:                  # noqa: BLE001
                log.exception("%s failed: %s", c.game_id, exc)
                self.recycle()
                out[c.game_id] = self.note(c, "skipped", f"evaluation failed: {type(exc).__name__}: {exc}", served)
        return self.decide(decisions, served), out

    def decide(self, decisions: list, served) -> int:
        """Record every decision of this read, best EV first, betting those at or above the cut."""
        from models.ncaabw_quote_bounds import edge_problem
        cut = self.art.cut
        for c, r, lag, links in sorted(decisions, key=lambda d: -float(d[1].best["ev"])):
            b, pick = r.best, None
            ev = float(b["ev"])
            if ev < cut:
                outcome, reason = "no_bet", f"EV {ev:.3f} under the cut {cut:.2f}"
            else:
                outcome, reason = "bet", "BET"
                mine = {"market": M.MARKET, "side": b["side"], "line": float(b["line"])}
                # a failed read here raises: the game stays undecided and the next read tries again
                held = None if self.dry_run else next(
                    (s for s in standing_totals(self.c(), c.game_id) if cannot_both_win(mine, s)), None)
                # An under beside a big favourite's spread bet on the same game
                # (models/cbb_pairs.py; mike, 2026-11-11). No women's spread model
                # exists today, so this reads `picks` and finds nothing.
                paired = None if (held is not None or self.dry_run) else paired_bet(
                    self.c(), c.game_id, M.MODEL_ID, b["side"], float(b["line"]))
                if held is not None:
                    outcome, reason = "declined", f"cannot both win with {held.get('label') or held['model_id']}"
                elif paired:
                    outcome, reason = "declined", paired
                else:
                    if self.bankroll is None and not self.dry_run:
                        try:
                            from models.scorer import _get_current_bankroll
                            self.bankroll = float(_get_current_bankroll(self.c()))
                        except Exception as exc:      # noqa: BLE001
                            log.warning("bankroll read failed (sizing at 0): %s", exc)
                            self.recycle()
                    try:
                        pick = build_pick(c, b, r.offers, r.state, links, self.bankroll or 0.0)
                        why = (platform_gates(M.MODEL_ID, pick["model_probability"], pick["decision_odds"])
                               or edge_problem(pick["decision_edge"], M.MODEL_ID))
                    except Exception as exc:          # noqa: BLE001
                        log.exception("building the pick for %s failed: %s", c.game_id, exc)
                        pick, why = None, f"the pick could not be built: {type(exc).__name__}: {exc}"
                    if why:
                        outcome, reason, pick = "declined", why, None
            log.info("DECIDED %s %s @ %s at the half %s-%s: %s %s", c.game_id, c.away, c.home, r.state["h_pts"],
                     r.state["a_pts"], outcome.upper(),
                     f"{pick['pick_label']} {pick['decision_book']} {pick['decision_odds']:+.0f} (EV {ev:.3f})"
                     if pick else reason)
            self.decided.add(c.game_id)
            if self.dry_run:
                continue
            try:
                if not insert_ledger(self.c(), ledger_row(c, b, r.offers, outcome, reason, served, r.state, lag,
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
        _install_api_probe("ncaabw-live")
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
    from data.ingestors.ncaabw_live_feed import Espn, odds_feed
    if M.MODEL_ID not in config.LIVE_MODELS:
        log.error("%s is not in config.LIVE_MODELS: it would never settle - exiting", M.MODEL_ID)
        return 1
    art = M.load_artifact()
    log.info("artifact %s; %s at EV >= %.2f; a read at each five-minute mark plus %.0fs (window %.0fs); ESPN "
             "fetched %.0fs after a read and again %.0fs later", art.version, M.MODEL_ID, art.cut,
             M.FETCH_AFTER_SEC, FETCH_WINDOW_SEC, a.wait, a.recheck)
    use_poller_session()
    loop = Loop(art, Espn(), odds_feed(CALL_CAP, CREDIT_CAP), get_connection,
                dry_run=a.dry_run, wait=a.wait, recheck=a.recheck)
    if DK_ON:
        from models.ncaab_live_dk import DbSource
        loop.dk = DbSource(loop.c, sport=SPORT)
        log.info("fast path on: a read %.0f s after the half's last play is judged at once; DraftKings' total "
                 "from its own board while that feed is live", HT_SETTLED_SEC)
    if not a.dry_run:
        try:
            if not ledger_ready(loop.c()):
                log.error("table %s is missing (data/migrations/ncaabw_live_decisions_2026_11_11.sql, applied by "
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
                log.error("NCAABW LIVE DECIDES NOTHING: %s. Set one of them on this service and redeploy "
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
                    log.info("no NCAABW game in progress for %d tick(s) - exiting (%d BETs written, %d odds "
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
            time.sleep(max(0.0, a.interval - (time.monotonic() - started)))
    finally:
        if loop.conn is not None:
            try:
                loop.conn.close()
            except Exception:                         # noqa: BLE001
                pass


if __name__ == "__main__":
    sys.exit(main())
