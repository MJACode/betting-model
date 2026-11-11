"""NCAAB first-post moneyline card: write `ncaab_moneyline_first_post` bets
(models/ncaab_moneyline_first_post.py).

LIVE, real money (mike, 2026-11-03; "-200 max"). Runs every minute, 24x7
(scheduler.run_ncaab_moneyline_first_post): one cheap planning read in the
scheduler (plan(), below) and, only when a bettable book has a moneyline on a
game that this card has not seen yet, this script with --publish; the job then
publishes what it wrote. RUN_NCAAB_MONEYLINE_FIRST_POST=0 stops it before it
reads anything; the job keeps beating, so its silence still means stopped.

WHERE A FIRST POST COMES FROM. The NCAAB odds capture (every five minutes,
change-only, scripts/ncaab_odds_capture.py) and the refresh passes store a row
in `odds` the first time a book lists a moneyline for a game; the AFTER INSERT
trigger keeps latest_odds current. A (game, book) with a moneyline in
latest_odds and no row in this card's ledger is a NEW first post. The card
reads that book's first complete moneyline row, and decides it within the
minute after the capture stored it.

A FIRST POST IS DECIDED ONCE, AT THE MOMENT THE CARD FIRST SEES IT
(CLAUDE.md 1c). Every bettable (game, book) gets one row in
ncaab_moneyline_first_post_decisions, bet or not, written with its bet in one
transaction; a (game, book) with a row is never decided again, and a moved
price writes nothing. The statuses:
  bets / below_cut / too_few_books / no_clean_quote / not_best /
  book_not_bettable    the rule's verdict (models/ncaab_moneyline_first_post)
  edge_cap             the moment's largest edge is above the data-error cap
                       (models/ncaab_quote_bounds.EDGE_CAP): no bet, and the
                       run fails, as on the 15:00 UTC card
  game_already_bet     this model bet the game on an earlier post
  other_model_bet      the 15:00 UTC moneyline model (ncaab_moneyline_own_spread)
                       bet the game first: one bet a game across the two
  moved_before_seen    the book's standing moneyline is no longer its first
                       number (it moved before the card saw it): not a first post
  tipped               less than five minutes before tip
  pre_model            stored before this card's first run (the ledger did not
                       exist): never decided on a stale quote
  before_window        stored while the game was more than LOOK_AHEAD away
  missed               stored more than MAX_LAG before this run although the
                       game was inside the window: the card was not running.
                       Written with no bet, and the run fails (exit 1), so the
                       heartbeat records "error" and the failure alerter
                       reports it. Never a late bet.

A FEED TYPO NEVER BECOMES A BET (models/ncaab_quote_bounds.py), exactly as
on the 15:00 UTC card: a moneyline priced beyond +/-100000, and a spread
beyond +/-60 or priced beyond +/-100000, is dropped before any flag, count or
price reads it. Each is logged with its game, book and value, counted as
quotes_dropped on the run's line, and kept in the ledger row's quotes as
out_of_range. A posting book whose own first moneyline is a data error is
written no_clean_quote.

ONE BET A GAME ACROSS BOTH MONEYLINE MODELS, whichever writes its bet first.
Both cards take BOTH models' publish locks (sorted, so neither can deadlock
the other) and re-read the other model's BETs inside them before writing.

BET ROWS ONLY in picks (no NONE rows, unlike the other NCAAB cards: one game
is decided once per book's first post, and a NONE row from an early post
would hold the unique key a later post's BET needs), at the posting book's price (decision_* and best_*),
scored_line NULL and line_book NULL; DraftKings' own moneyline, when it had a
clean one, as the reference (dk_odds). The rows are built by the 15:00 UTC
card's own pick_rows (scripts/ncaab_moneyline_card.pick_rows, model_id this
model's): the label from the platform's formatter, checked by
tracking/pick_integrity, the price floor applied again against
config.min_odds_for, and the model's own EV floor.

THE FILL MEASUREMENT. The capture's next poll after a bet writes, on the bet's
ledger row, whether that book still listed the moneyline at the bet's two
prices (scripts/ncaab_first_post_fill.py).

    python -m scripts.ncaab_moneyline_first_post_card              # print, write nothing
    python -m scripts.ncaab_moneyline_first_post_card --publish    # write decisions and bets
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from models import ncaab_stake  # noqa: E402
import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_moneyline_first_post as fp  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from scripts.ncaab_first_post_fill import DECISIONS_TABLE  # noqa: E402

MODEL_ID = fp.MODEL_ID
SPORT = fp.SPORT
_ET = ZoneInfo("America/New_York")

# How far ahead a game's first posts are decided. The research's latest bet
# came 120 hours before tip; a first post stored while its game was further out
# is written `before_window` when the game comes into range.
LOOK_AHEAD = timedelta(days=7)
# How old a first post may be when the card first sees it. The card runs every
# minute and the capture every five, so a post is normally seen within a
# minute or two; anything older means the card was not running.
MAX_LAG = timedelta(minutes=15)


def enabled() -> bool:
    """The kill switch: RUN_NCAAB_MONEYLINE_FIRST_POST=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_NCAAB_MONEYLINE_FIRST_POST", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the ledger ────────────────────────────────────────────────────────────────
# One row per (game, book) first post the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_COLS = ("game_id", "bookmaker", "decided_at", "instant", "first_ts", "first_stored_at",
                  "status", "p1", "p2", "side", "price", "prob", "edge", "own_line", "mean",
                  "n_books", "dk_price", "n_bets", "quotes", "detail",
                  "fill_status", "fill_checked_at", "fill_p1", "fill_p2")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_moneyline_first_post_decisions (
    game_id          TEXT NOT NULL,
    bookmaker        TEXT NOT NULL,
    decided_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    instant          TEXT NOT NULL,
    first_ts         TEXT,
    first_stored_at  TEXT,
    status           TEXT NOT NULL,
    p1               REAL,
    p2               REAL,
    side             TEXT,
    price            REAL,
    prob             REAL,
    edge             REAL,
    own_line         REAL,
    mean             REAL,
    n_books          INTEGER,
    dk_price         REAL,
    n_bets           INTEGER NOT NULL,
    quotes           TEXT,
    detail           TEXT,
    fill_status      TEXT,
    fill_checked_at  TEXT,
    fill_p1          REAL,
    fill_p2          REAL,
    PRIMARY KEY (game_id, bookmaker)
)
"""
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} (game_id, bookmaker, instant, first_ts, first_stored_at, "
    "status, p1, p2, side, price, prob, edge, own_line, mean, n_books, dk_price, n_bets, quotes, "
    "detail) VALUES (%(game_id)s, %(bookmaker)s, %(instant)s, %(first_ts)s, %(first_stored_at)s, "
    "%(status)s, %(p1)s, %(p2)s, %(side)s, %(price)s, %(prob)s, %(edge)s, %(own_line)s, %(mean)s, "
    "%(n_books)s, %(dk_price)s, %(n_bets)s, %(quotes)s, %(detail)s) "
    "ON CONFLICT (game_id, bookmaker) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())


def ledger_keys(conn, game_ids) -> set[tuple[str, str]]:
    if not game_ids or not ledger_exists(conn):
        return set()
    return {(r[0], r[1]) for r in conn.execute(
        f"SELECT game_id, bookmaker FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)",
        (sorted(game_ids),)).fetchall()}


def bet_games(conn, game_ids, model_id: str) -> set[str]:
    """Games with any BET of `model_id`, whatever became of it (settled,
    VOIDed): the game is closed to both moneyline models."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (model_id, sorted(game_ids))).fetchall()}


def lock_both(conn) -> None:
    """Both moneyline models' publish locks, in sorted order: one bet a game
    across the two, and neither card can deadlock the other."""
    from scripts.nfl_wind_publisher import _lock_model
    for m in sorted((fp.MODEL_ID, fp.OTHER_MODEL_ID)):
        _lock_model(conn, m)


# ── the reads ─────────────────────────────────────────────────────────────────

def _tip(text) -> datetime | None:
    try:
        t = pd.Timestamp(str(text))
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return _utc(t).to_pydatetime()


def slate(conn, now: datetime) -> dict[str, dict]:
    """NCAAB games still to tip and tipping within LOOK_AHEAD. One read of
    games by date."""
    today = now.astimezone(_ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in range(-1, LOOK_AHEAD.days + 2)]
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAAB' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away in rows:
        tip = _tip(ct)
        if tip is None or tip <= now or tip > now + LOOK_AHEAD:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": tip,
                    "commence_time": ct, "home": home, "away": away}
    return out


def posted_keys(conn, game_ids) -> set[tuple[str, str]]:
    """(game, book) pairs with a complete pre-game moneyline in latest_odds,
    bettable books only. Keyed on the game ids (latest_odds' primary key)."""
    if not game_ids:
        return set()
    return {(r[0], r[1]) for r in conn.execute("""
        SELECT game_id, bookmaker FROM latest_odds
        WHERE game_id = ANY(%s) AND market = 'h2h' AND bookmaker = ANY(%s)
          AND home_price IS NOT NULL AND away_price IS NOT NULL
    """, (sorted(game_ids), list(bq.BOOKS))).fetchall()}


def first_rows(conn, keys) -> dict[tuple[str, str], dict]:
    """Each key's FIRST complete pre-game moneyline row: its stamp, when it was
    stored and its two prices. Keyed read on (game_id, market, bookmaker)."""
    if not keys:
        return {}
    gids = sorted({g for g, _ in keys})
    books = sorted({b for _, b in keys})
    got = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.bookmaker) o.game_id, o.bookmaker, o.snapshot_at,
               o.created_at::timestamptz, o.home_price, o.away_price
        FROM odds o
        WHERE o.game_id = ANY(%s) AND o.market = 'h2h' AND o.bookmaker = ANY(%s)
          AND o.snapshot_type IS DISTINCT FROM 'in_play'
          AND o.home_price IS NOT NULL AND o.away_price IS NOT NULL
        ORDER BY o.game_id, o.bookmaker, o.snapshot_at::timestamptz, o.created_at::timestamptz,
                 o.odds_id
    """, (gids, books)).fetchall()
    out = {}
    for gid, book, snap, stored, p1, p2 in got:
        if (gid, book) not in keys:
            continue
        out[(gid, book)] = {"ts": _utc(snap), "stored": _utc(stored), "p1": _f(p1), "p2": _f(p2)}
    return out


def _utc(v) -> pd.Timestamp:
    t = pd.Timestamp(v if isinstance(v, datetime) else str(v))
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def standing_rows(conn, games: dict[str, dict], instant: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every book's newest complete pre-game moneyline (REF_BOOKS) and spread
    (the bettable books) stamped at or before the instant, for these games:
    the rows models.ncaab_moneyline_first_post.read takes. One keyed read."""
    cols = ["game_id", "market", "bookmaker", "snapshot_at", "stored_at", "line", "p1", "p2",
            "link1", "link2"]
    if not games:
        empty = pd.DataFrame(columns=bq.QUOTE_COLS + ["instant", "tip", "link1", "link2"])
        return empty, empty.copy()
    got = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker) o.game_id, o.market, o.bookmaker,
               o.snapshot_at, o.created_at::timestamptz, o.spread_home, o.home_price, o.away_price,
               o.home_link, o.away_link
        FROM odds o
        WHERE o.game_id = ANY(%s) AND o.market IN ('h2h', 'spreads') AND o.bookmaker = ANY(%s)
          AND o.snapshot_type IS DISTINCT FROM 'in_play'
          AND o.snapshot_at::timestamptz <= %s
          AND o.home_price IS NOT NULL AND o.away_price IS NOT NULL
          AND (o.market = 'h2h' OR o.spread_home IS NOT NULL)
        ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at::timestamptz DESC,
                 o.created_at::timestamptz DESC, o.odds_id DESC
    """, (sorted(games), list(fp.REF_BOOKS), instant.isoformat())).fetchall()
    d = pd.DataFrame(got, columns=cols)
    for c in ("line", "p1", "p2"):
        d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
    d["ts"] = pd.to_datetime(d["snapshot_at"], utc=True, format="mixed") if len(d) else \
        pd.Series(dtype="datetime64[ns, UTC]")
    st = pd.to_datetime(d["stored_at"], utc=True, format="mixed") if len(d) else \
        pd.Series(dtype="datetime64[ns, UTC]")
    d["order"] = st.dt.as_unit("ns").astype("int64") if len(d) else pd.Series(dtype="int64")
    d["instant"] = pd.Timestamp(instant)
    d["tip"] = d["game_id"].map({g: pd.Timestamp(v["tip"]) for g, v in games.items()})
    ml = d[d["market"] == "h2h"].drop(columns="market").copy()
    ml["line"] = np.nan
    sp = d[d["market"] == "spreads"].drop(columns="market").copy()
    return ml.reset_index(drop=True), sp.reset_index(drop=True)


# ── the plan (in the scheduler, every minute) ─────────────────────────────────

def plan(now: datetime | None = None, conn=None) -> list[tuple[str, str]]:
    """The new first posts a run would decide now: (game, book) pairs with a
    moneyline in latest_odds and no ledger row, for the games in the window.
    Three keyed reads; [] when the kill switch is off."""
    if not enabled():
        return []
    now = now or datetime.now(timezone.utc)
    own = conn is None
    conn = conn or get_connection()
    try:
        games = slate(conn, now)
        new = posted_keys(conn, set(games)) - ledger_keys(conn, set(games))
        return sorted(new)
    finally:
        if own:
            conn.close()


# ── the decisions ─────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A first post the card could not decide in time, or a pick at a book no
    longer bettable: raised after the rest of the run is written."""


_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = fp.load_artifact()
    return _ART["a"]


def _plain(gid, book, status, detail) -> fp.PostDecision:
    return fp.PostDecision(gid, book, status, detail)


def decide(conn, now: datetime, games: dict[str, dict], new: list[tuple[str, str]],
           first_run: bool) -> tuple[list[fp.PostDecision], dict, list[str]]:
    """Decide every new first post. -> (decisions, {key: first row}, problems)."""
    problems: list[str] = []
    out: list[fp.PostDecision] = _Decisions()
    if first_run:
        for gid, book in new:
            out.append(_plain(gid, book, "pre_model", "stored before this card's first run"))
        return out, {}, problems
    firsts = first_rows(conn, set(new))
    fresh: list[tuple[str, str]] = []
    missed = []
    for key in new:
        gid, book = key
        f = firsts.get(key)
        g = games[gid]
        if f is None or f["p1"] is None or f["p2"] is None:
            out.append(_plain(gid, book, "no_clean_quote", "no complete pre-game moneyline row"))
            continue
        if f["stored"] < pd.Timestamp(now) - MAX_LAG:
            if pd.Timestamp(g["tip"]) - f["stored"] > LOOK_AHEAD:
                out.append(_plain(gid, book, "before_window",
                                  f"stored {f['stored']:%Y-%m-%d %H:%M}Z, more than "
                                  f"{LOOK_AHEAD.days} days before tip"))
            else:
                out.append(_plain(gid, book, "missed",
                                  f"stored {f['stored']:%Y-%m-%d %H:%M}Z, first seen by this card "
                                  f"{now:%H:%M}Z: more than {int(MAX_LAG.total_seconds() // 60)} "
                                  f"minutes late"))
                missed.append(f"{gid} {book}")
            continue
        if fp.too_close(g["tip"], now):
            out.append(_plain(gid, book, "tipped", "less than 5 minutes before tip"))
            continue
        fresh.append(key)
    if missed:
        problems.append(f"{len(missed)} first post(s) missed (the card was not running): "
                        + ", ".join(missed[:20]))
    if not fresh:
        return out, firsts, problems
    gids = sorted({g for g, _ in fresh})
    own_bet = bet_games(conn, gids, fp.MODEL_ID)
    other_bet = bet_games(conn, gids, fp.OTHER_MODEL_ID)
    part = {g: games[g] for g in gids}
    ml_rows, sp_rows = standing_rows(conn, part, now)
    art = artifact()
    # Feed typos out first, as on the 15:00 UTC card (models/ncaab_quote_bounds).
    drops = pd.concat([bq.dropped_quotes(ml_rows, window_min=None, books=fp.REF_BOOKS,
                                         need_line=False),
                       bq.dropped_quotes(sp_rows, window_min=None)], ignore_index=True)
    log_dropped(drops)
    n_dropped = len(drops)
    ml, sp = fp.read(ml_rows, sp_rows, art["table"])
    posting = []
    for gid, book in fresh:
        f = firsts[(gid, book)]
        if gid in own_bet:
            out.append(_plain(gid, book, "game_already_bet", f"{MODEL_ID} bet this game on an earlier post"))
            continue
        if gid in other_bet:
            out.append(_plain(gid, book, "other_model_bet", f"{fp.OTHER_MODEL_ID} bet this game first"))
            continue
        if int(games[gid]["season"]) != int(art["season"]):
            problems.append(f"the artifact is for season {art['season']}; {gid} is season "
                            f"{games[gid]['season']} (scripts/ncaab_moneyline_first_post_build.py)")
            continue                                   # undecided: seen again next run, then missed
        q = ml[(ml["game_id"] == gid) & (ml["bookmaker"] == book)]
        if not len(q):
            own = drops[(drops["game_id"] == gid) & (drops["bookmaker"] == book)
                        & (drops["market"] == "h2h")] if len(drops) else drops
            why = (f"its moneyline is a data error ({own['why'].iloc[0]})" if len(own) else
                   "its moneyline is not price-valid (a price inside -100..+100)")
            out.append(_plain(gid, book, "no_clean_quote", why))
            continue
        if not (_same(q["p1"].iloc[0], f["p1"]) and _same(q["p2"].iloc[0], f["p2"])):
            out.append(_plain(gid, book, "moved_before_seen",
                              f"first {f['p1']:+.0f}/{f['p2']:+.0f}, standing now "
                              f"{q['p1'].iloc[0]:+.0f}/{q['p2'].iloc[0]:+.0f}"))
            continue
        posting.append((gid, book))
    if posting:
        got = fp.decide_posts(pd.DataFrame(posting, columns=["game_id", "bookmaker"]), ml, sp,
                              config.MODEL_EDGE_THRESHOLDS[MODEL_ID],
                              bettable=tuple(config.BEST_LINE_BOOKMAKERS),
                              min_price=float(art["min_price"]),
                              min_other=int(art["min_other_books"]), dropped=drops)
        for d in got:
            if d.status == "book_not_bettable":
                problems.append(f"book_not_bettable {d.game_id} {d.bookmaker} ({d.detail})")
            elif d.status == "edge_cap":
                logger.error(f"NCAAB first-post moneyline card: {d.game_id} {d.bookmaker} not bet, "
                             f"its edge is a data error: {d.detail}")
                problems.append(f"edge_cap {d.game_id} {d.bookmaker} ({d.detail})")
        out += got
    out.dropped = n_dropped                          # counted on the run's line
    return out, firsts, problems


class _Decisions(list):
    """The run's decisions, with how many quotes the read dropped as data
    errors (`dropped`)."""
    dropped = 0


def log_dropped(drops) -> None:
    """One warning per quote dropped as a data error: game, book and value."""
    from models.ncaab_quote_bounds import describe
    for line in describe(drops):
        logger.warning(f"NCAAB first-post moneyline card: dropped a data-error quote, {line}")


def _same(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return False


def _num(v):
    return None if v is None or (isinstance(v, float) and v != v) else round(float(v), 4)


def decision_row(d: fp.PostDecision, instant: datetime, first: dict | None, bet_written: bool,
                 refused: str | None) -> dict:
    b = d.best or {}
    side = b.get("side")
    detail = d.status + ": " + d.detail + (f"; refused {refused}" if refused else "")
    return {"game_id": d.game_id, "bookmaker": d.bookmaker, "instant": instant.isoformat(),
            "first_ts": first["ts"].isoformat() if first else None,
            "first_stored_at": first["stored"].isoformat() if first else None,
            "status": d.status,
            "p1": _num(first["p1"]) if first else None, "p2": _num(first["p2"]) if first else None,
            "side": side, "price": _num(b.get("price")), "prob": _num(b.get("prob")),
            "edge": _num(b.get("edge")), "own_line": _num(b.get("own_line")),
            "mean": _num(b.get("mu")), "n_books": d.n_books if d.quotes else None,
            "dk_price": (_num(d.dk["p1"] if side == "home" else d.dk["p2"]) if d.dk and side else None),
            "n_bets": 1 if bet_written else 0,
            "quotes": json.dumps(d.quotes) if d.quotes else None, "detail": detail[:2000]}


def publish(conn, rows: list[dict], decisions: list[fp.PostDecision], instant: datetime,
            firsts: dict, refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided first post once, and the game's bet with it, in ONE
    transaction under both moneyline models' locks; the ledger and both
    models' BETs re-read inside them. -> (bets written, decisions written)."""
    if not decisions:
        return 0, 0
    from scripts.ncaab_moneyline_card import _INSERT, _COLS
    lock_both(conn)
    gids = sorted({d.game_id for d in decisions})
    done = ledger_keys(conn, gids)
    own_bet = bet_games(conn, gids, fp.MODEL_ID)
    other_bet = bet_games(conn, gids, fp.OTHER_MODEL_ID)
    by_game = {r["game_id"]: r for r in rows}
    n_bets = n_decided = 0
    for d in sorted(decisions, key=lambda x: (x.game_id, x.bookmaker)):
        if (d.game_id, d.bookmaker) in done:
            continue
        row = by_game.get(d.game_id) if d.status == "bets" else None
        if d.status == "bets" and (d.game_id in own_bet or d.game_id in other_bet):
            # A bet another run or the other model wrote while this one priced.
            who = fp.MODEL_ID if d.game_id in own_bet else fp.OTHER_MODEL_ID
            d.status = "game_already_bet" if d.game_id in own_bet else "other_model_bet"
            d.detail += f"; {who} bet this game first"
            row = None
        got = conn.execute(_INSERT_DECISION, decision_row(
            d, instant, firsts.get((d.game_id, d.bookmaker)), row is not None,
            refused.get(d.game_id) if d.status == "bets" else None)).fetchone()
        if not got:
            continue
        n_decided += 1
        # A bet an earlier NCAAB bet on this game and side agrees with is
        # staked at NCAAB_AGREEMENT_STAKE_UNITS (models/ncaab_stake.py).
        if row is not None and conn.execute(_INSERT, ncaab_stake.stamp(conn, row, _COLS)).fetchone():
            n_bets += 1
            own_bet.add(d.game_id)
    conn.commit()
    return n_bets, n_decided


def render(decisions: list[fp.PostDecision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAAB first-post moneyline card ({MODEL_ID}): " + \
        " ".join(f"{k}={v}" for k, v in diag.items())
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: (x.game_id, x.bookmaker)):
        lines.append(f"  {d.game_id:44s} {d.bookmaker:14s} {d.status}: {d.detail}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("NCAAB first-post moneyline card: RUN_NCAAB_MONEYLINE_FIRST_POST is off; nothing read")
        return {"posts": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    conn = get_connection()
    try:
        games = slate(conn, now)
        first_run = not ledger_exists(conn)
        new = plan(now, conn)
        diag = {"games": len(games), "new_posts": len(new)}
        if not new:
            logger.info(render([], diag))
            return {"posts": 0, "bets": 0, "published": 0, "decided": 0, "diag": diag}
        if do_publish:
            ensure_decisions_table(conn)
        decisions, firsts, problems = decide(conn, now, games, new, first_run)
        for d in decisions:
            diag[d.status] = diag.get(d.status, 0) + 1
        if getattr(decisions, "dropped", 0):
            diag["quotes_dropped"] = decisions.dropped
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            from scripts.ncaab_moneyline_card import pick_rows
            bets = [d for d in decisions if d.status == "bets"]
            prows, refused = pick_rows(bets, games, _get_current_bankroll(conn), model_id=MODEL_ID,
                                      scored=False)
            published, n_decided = publish(conn, prows, decisions, now, firsts, refused)
        logger.info("\n" + render(decisions, diag, published if do_publish else None,
                                  n_decided if do_publish else None))
        if problems:
            raise CardIncomplete(f"{len(problems)} problem(s): " + "; ".join(problems)[:1500])
        return {"posts": len(new), "bets": diag.get("bets", 0), "published": published,
                "decided": n_decided, "diag": diag}
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args(argv)
    try:
        print(run_card(do_publish=a.publish))
    except CardIncomplete as exc:
        # exit 1: scheduler.run_ncaab_moneyline_first_post then raises, so the
        # job's heartbeat records "error" and the failure alerter reports it.
        logger.error(f"NCAAB first-post moneyline card did not decide every first post: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). The card reads the
    # database only; installed so the scheduler runs no uninstrumented script.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-moneyline-first-post")
    except Exception:  # noqa: BLE001
        pass
    main()
