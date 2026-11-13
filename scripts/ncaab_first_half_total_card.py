"""NCAAB first-half total card: write `ncaab_first_half_total` bets
(models/ncaab_first_half_total.py).

LIVE, real money (mike, 2026-11-03). Runs in the NCAAB first-half window job
(scheduler.run_ncaab_first_half_window, every minute) right after the tick's
fetches, beside the first-half spread card, and writes picks only; the job then
publishes them like every other card. RUN_NCAAB_FIRST_HALF=0 stops it before it
reads anything.

WHEN A GAME IS DECIDED. On its decision fetch: the newest ok first-half call
made for the tip-minus-60 time (data/ingestors/ncaab_first_half_odds.py,
TOTAL_DECISION_MARK) that landed DECISION_LEAD_MIN (55 to 60.5) minutes before
tip. The research graded the purchase an hour before tip (its stamp about 64
minutes before) and no other time this model was chosen at; a call that failed
at tip minus 60 is retried every minute, and one that lands up to five minutes
later still decides. With none by 55 minutes before tip the game is not
decided, and the run raises after writing every other game, so the job's
heartbeat records an error. The 50-minute fetch is not used instead. A
decision fetch is decided on only within MAX_DECISION_DELAY_MIN (5) of landing:
the card normally runs in the same tick, and a bet written later would carry a
price that may be gone, so a run that comes too late treats the game as missed.

A FEED TYPO NEVER BECOMES A BET (models/ncaab_quote_bounds.py). A first-half
total outside 40-120, or priced beyond +/-100000, is not priced, and a
full-game total outside 90-220 never enters the consensus; that book's older
row is not used instead. Each dropped quote is logged with its game, book and
value, counted as quotes_dropped on the diagnostic line, and named in the
decision row's detail. A best edge above the data-error cap is decided as
edge_cap with no bet, and the run raises after writing every other game.

WHAT IS READ, as of the decision fetch's instant (its fetch_at, the stored
rows' created_at):
  * the first-half totals that fetch stored (the feed's SOURCE, market
    totals_h1, each book's main number), at the model's books that
    config.BEST_LINE_BOOKMAKERS still lists;
  * each bettable book's newest full-game total stored at or before that
    instant (any source, pre-game rows), whose median is the consensus T;
  * the season's finished games' halves and closing consensus lines, the
    ncaab_first_half_team_games rows the first-half spread card keeps (this
    card adds any it finds missing, the same rows by the same code); and last
    season's sums, frozen in the artifact.
A finished game whose period scores are not stored yet is left out of the
team term and counted in the decision row (missing_halves). The term is small
(236 games of shrinkage), so the game is decided anyway: holding it would lose
the only graded moment.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
ncaab_first_half_total_decisions in the same transaction as the game's bet,
under the model's transaction-scoped advisory lock. A game with a decision row,
or with any ncaab_first_half_total BET, is never decided again: a later tick,
a moved line or a better price writes nothing. The row keeps every book's
priced quote and each book's own update age, so the cut can be swept on live
data (CLAUDE.md 1b).

A game priced below the cut is a NONE row (no stake) in the same
transaction, so the app's All board shows every scored game (Matt,
2026-11-04); nothing publishes or settles a NONE row.
BET ROWS in picks, at the bet book's own number and price: scored_line is
the first half's total, pick_side 'over' / 'under', decision_* the book taken;
dk_* / edge are DraftKings' own price for the same side at the same number in
the same fetch, else NULL / 0.0 / 0.0 with line_book naming the book taken;
best_* only when the bet is not at DraftKings. The label is the platform's
("Duke @ Kansas — First Half Under 70.5", models.scorer._build_pick_label),
checked against side, line and market before it is written
(tracking/pick_integrity.pick_problems). The price floor
(config.min_odds_for, -200) is applied in the decision itself, before the best
book is chosen (models/ncaab_first_half_total.best_offer), and again here; the
model's own EV floor (models.honest_ev.gate) is applied here.

    python -m scripts.ncaab_first_half_total_card              # print the card, write nothing
    python -m scripts.ncaab_first_half_total_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from models import cbb_pairs  # noqa: E402
from models import ncaab_stake  # noqa: E402
import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402
import models.ncaab_quote_bounds as qb  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from scripts.ncaab_first_half_spread_card import (  # noqa: E402
    _cuts_sql, _log_dropped, _num, _table_exists, missing_halves, team_games,
)
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = ft.MODEL_ID
SPORT = ft.SPORT
# A decision fetch landed this many minutes before tip (module docstring).
DECISION_LEAD_MIN = (55.0, 60.5)
# ...and is decided on only this many minutes after it landed, at most.
MAX_DECISION_DELAY_MIN = 5.0


def enabled() -> bool:
    from scripts.ncaab_first_half_window import enabled as on
    return on()


def bet_books() -> tuple[str, ...]:
    """The model's books that are still bettable (config.BEST_LINE_BOOKMAKERS)."""
    return tuple(b for b in ft.BOOKS if b in config.BEST_LINE_BOOKMAKERS)


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "ncaab_first_half_total_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "lead_min", "status", "detail", "n_bets",
                  "book", "side", "line", "price", "p_side", "edge", "mu", "fg_total",
                  "fg_books", "tau_home", "tau_away", "n_home", "n_away", "missing_halves",
                  "offers", "book_ages")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_first_half_total_decisions (
    game_id         TEXT PRIMARY KEY,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at        TEXT NOT NULL,
    lead_min        REAL,
    status          TEXT NOT NULL,
    detail          TEXT,
    n_bets          INTEGER NOT NULL,
    book            TEXT,
    side            TEXT,
    line            REAL,
    price           REAL,
    p_side          REAL,
    edge            REAL,
    mu              REAL,
    fg_total        REAL,
    fg_books        INTEGER,
    tau_home        REAL,
    tau_away        REAL,
    n_home          INTEGER,
    n_away          INTEGER,
    missing_halves  INTEGER,
    offers          TEXT,
    book_ages       TEXT
)
"""
_DECISION_VALUES = DECISIONS_COLS[:1] + DECISIONS_COLS[2:]
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} ({', '.join(_DECISION_VALUES)}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in _DECISION_VALUES)}) "
    f"ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games with a decision row, or with any ncaab_first_half_total BET
    whatever became of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if _table_exists(conn, DECISIONS_TABLE):
        done = {r[0] for r in conn.execute(
            f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    return done | games_with_a_bet(conn, game_ids)


def first_decision(conn) -> datetime | None:
    """When this model first decided a game (its ledger's oldest row), None
    before it has: the failure alerter counts only games after it
    (scripts/ncaab_first_half_window.undecided_games)."""
    if not _table_exists(conn, DECISIONS_TABLE):
        return None
    row = conn.execute(f"SELECT MIN(decided_at) FROM {DECISIONS_TABLE}").fetchone()
    return feed._aware(row[0]) if row and row[0] is not None else None


# ── the decision reads ───────────────────────────────────────────────────────

def fg_consensus(conn, cuts: dict[str, datetime]) -> dict[str, dict]:
    """{game_id: {"cons", "nb"}}: the bettable books' full-game total median
    as of each game's decision fetch (ft.asof_consensus on each book's newest
    pre-game row stored by then)."""
    if not cuts:
        return {}
    gids, ts = _cuts_sql(cuts)
    rows = conn.execute("""
        WITH t AS (SELECT * FROM unnest(%s::text[], %s::timestamptz[]) AS t(game_id, cut))
        SELECT DISTINCT ON (o.game_id, o.bookmaker)
               o.game_id, o.bookmaker, o.snapshot_at, o.total_line
        FROM odds o JOIN t ON t.game_id = o.game_id
        WHERE o.market = 'totals' AND o.bookmaker = ANY(%s) AND o.snapshot_type <> 'in_play'
          AND o.total_line IS NOT NULL
          AND o.created_at::timestamptz <= t.cut AND o.snapshot_at::timestamptz <= t.cut
        ORDER BY o.game_id, o.bookmaker, o.snapshot_at::timestamptz DESC,
                 o.created_at::timestamptz DESC
    """, (gids, ts, list(ft.BOOKS))).fetchall()
    df = pd.DataFrame(rows, columns=["game_id", "bookmaker", "snapshot_at", "line"])
    if not len(df):
        return {}
    df["line"] = pd.to_numeric(df["line"], errors="coerce")
    df["ts"] = pd.to_datetime(df["snapshot_at"], utc=True, format="mixed", errors="coerce")
    cut = pd.DataFrame({"game_id": gids, "cutoff": pd.to_datetime(ts, utc=True)})
    # One row per book already (DISTINCT ON): a data error here is that book's
    # newest total, so the book leaves the consensus (asof_consensus drops it).
    _log_dropped(qb.split(df, "totals", "line", ())[1], "full-game", "line", ())
    c = ft.asof_consensus(df, cut, market="totals")
    return {r.game_id: {"cons": float(r.cons), "nb": int(r.nb)} for r in c.itertuples(index=False)}


QUOTE_COLS = ["game_id", "bookmaker", "total_line", "over_price", "under_price", "over_link",
              "under_link", "snapshot_at"]


def decision_quotes(conn, cuts: dict[str, datetime]) -> pd.DataFrame:
    """The first-half total rows the decision fetch stored (its created_at),
    each book's main number. Every book this feed stores; the decision prices
    only the model's bettable ones."""
    if not cuts:
        return pd.DataFrame(columns=QUOTE_COLS)
    gids, ts = _cuts_sql(cuts)
    rows = conn.execute(f"""
        WITH t AS (SELECT * FROM unnest(%s::text[], %s::timestamptz[]) AS t(game_id, cut))
        SELECT {', '.join('o.' + c for c in QUOTE_COLS)}
        FROM odds o JOIN t ON t.game_id = o.game_id
        WHERE o.market = %s AND o.source = %s AND o.snapshot_type = %s
          AND o.created_at::timestamptz = t.cut
    """, (gids, ts, ft.MARKET, feed.SOURCE, feed.SNAPSHOT_TYPE)).fetchall()
    df = pd.DataFrame(rows, columns=QUOTE_COLS)
    for c in ("total_line", "over_price", "under_price"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def favourite_lays(conn, cuts: dict[str, datetime]) -> dict[str, float]:
    """{game_id: the points the favourite lays in the first half}: the median
    over the books of the absolute first-half spread the decision fetch itself
    stored. A game no book quoted a first-half spread for is absent."""
    if not cuts:
        return {}
    gids, ts = _cuts_sql(cuts)
    rows = conn.execute("""
        WITH t AS (SELECT * FROM unnest(%s::text[], %s::timestamptz[]) AS t(game_id, cut))
        SELECT o.game_id, o.spread_home
        FROM odds o JOIN t ON t.game_id = o.game_id
        WHERE o.market = 'spreads_h1' AND o.source = %s AND o.snapshot_type = %s
          AND o.created_at::timestamptz = t.cut AND o.spread_home IS NOT NULL
    """, (gids, ts, feed.SOURCE, feed.SNAPSHOT_TYPE)).fetchall()
    df = pd.DataFrame(rows, columns=["game_id", "spread_home"])
    df["lays"] = pd.to_numeric(df["spread_home"], errors="coerce").abs()
    df = df[df["lays"].notna() & (df["lays"] <= 45.0)]
    return {g: float(v) for g, v in df.groupby("game_id")["lays"].median().items()}


def book_ages(quotes: pd.DataFrame, fetch_at: datetime) -> dict[str, float]:
    """{book: minutes from its first-half total's own last update to the
    fetch}, from the stored rows' snapshot_at (the market's last_update)."""
    out = {}
    for r in quotes.itertuples(index=False):
        t = feed._when(r.snapshot_at) if r.snapshot_at else None
        if t is not None:
            out[str(r.bookmaker)] = round((fetch_at - t).total_seconds() / 60.0, 1)
    return out


# ── rows ──────────────────────────────────────────────────────────────────────

_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link",
         "downgrade_reason",
         "stake_units", "stake_reason")
# Its own column list, NOT models.scorer._insert_picks: that one stamps
# model_probability_cal from the promoted map, and this model decides on its
# own number (config.MODELS_ON_OWN_PROBABILITY).
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


# Priced, and its best side did not clear the cut: written as a NONE row.
# Priced and not bet: a NONE row at the same book, side and number. An under
# set aside for a big favourite is one, so it can still be graded later.
SCORED_NO_BET = ("below_cut", "big_favourite")


def pick_label(side: str, home: str, away: str, line: float) -> str:
    from models.scorer import _build_pick_label
    return _build_pick_label(side, home, away, ft.MARKET, float(line))


def pick_rows(decisions: list[ft.Decision], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Decisions -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs.

    A bet is a BET row. A game priced below the cut (SCORED_NO_BET), or a bet
    the price or EV floor refused, is a NONE row at the same book, side and
    number with no stake (Matt, 2026-11-04: the All board shows every scored
    pick, not only the bets). Nothing publishes or settles a NONE row."""
    from models.honest_ev import gate
    from models.scorer import _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    rows, refused = [], {}
    for d in decisions:
        if d.best is None or d.status not in ("bets",) + SCORED_NO_BET:
            continue
        is_bet = d.status == "bets"
        b, price = d.best, float(d.price)
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if is_bet and floor is not None and price < floor:
            refused[d.game_id] = f"below_price_floor:{price:+.0f}"
            is_bet = False
        if is_bet:
            ev = gate(MODEL_ID, b.prob, price)
            if not ev.clears:
                logger.info(f"{MODEL_ID}: {ev.reason} - dropped {d.game_id} {b.side} @{b.book}")
                refused[d.game_id] = ev.reason or "below_ev_floor"
                is_bet = False
        label = pick_label(b.side, home, away, b.line)
        problems = pick_problems(label, b.side, float(b.line), MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {d.game_id} {label!r}: {'; '.join(problems)}")
            if d.game_id not in refused and is_bet:
                refused[d.game_id] = "label_mismatch"
            continue
        imp = implied(price)
        decision_edge = round(b.prob - imp, 4)
        dk = next((o for o in d.offers if o.book == ft.REFERENCE_BOOK), None)
        dk_price = None
        if dk is not None and abs(dk.line - b.line) < 1e-9:
            dk_price = dk.over_price if b.side == "over" else dk.under_price
        dk_implied = implied(dk_price) if dk_price is not None else None
        at_dk = b.book == ft.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.prob, imp, bankroll) if is_bet else (0.0, 0.0)
        rows.append({
            "game_id": d.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"), "game_time": g.get("commence_time"),
            "pick_side": b.side, "pick_label": label,
            # P(side wins | no push) at this number: the number the cut
            # was measured on (models/ncaab_first_half_total.py).
            "model_probability": round(b.prob, 4),
            "model_probability_cal": round(b.prob, 4),
            "dk_odds": dk_price,
            "dk_implied_prob": round(dk_implied, 4) if dk_implied is not None else 0.0,
            "edge": round(b.prob - dk_implied, 4) if dk_implied is not None else 0.0,
            "dk_bet_link": dk.link_for(b.side) if dk_price is not None else None,
            "line_book": None if dk_price is not None else b.book,
            "scored_line": float(b.line),
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
            # MED on every bet, as the other rule cards write: the evidence
            # gives no tier.
            "confidence_tier": "MED",
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(imp, 4), "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(imp, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link_for(b.side),
            "downgrade_reason": pause,
        })
    return rows, refused


def decision_row(d: ft.Decision, fetch_at: datetime, lead: float, ages: dict, missing: int,
                 has_bet: bool, refused: str | None) -> dict:
    b = d.best
    detail = d.status + ": " + d.detail + (f"; refused {refused}" if refused else "")
    offers = [{"book": o.book, "line": o.line, "over": o.over_price, "under": o.under_price,
               "side": o.side, "edge": round(o.edge, 5), "p": round(o.prob, 5)}
              for o in sorted(d.offers, key=lambda o: o.book)]
    return {"game_id": d.game_id, "fetch_at": fetch_at.isoformat(), "lead_min": round(lead, 2),
            "status": d.status, "detail": detail[:1000], "n_bets": 1 if has_bet else 0,
            "book": b.book if b else None, "side": b.side if b else None,
            "line": b.line if b else None, "price": d.price,
            "p_side": _num(b.prob, 5) if b else None, "edge": _num(b.edge, 5) if b else None,
            "mu": _num(d.mu, 4), "fg_total": _num(d.fg_total, 3), "fg_books": d.fg_books,
            "tau_home": _num(d.tau_home, 6), "tau_away": _num(d.tau_away, 6),
            "n_home": d.n_home, "n_away": d.n_away, "missing_halves": int(missing),
            "offers": json.dumps(offers) if offers else None,
            "book_ages": json.dumps(ages, sort_keys=True) if ages else None}


def publish(conn, rows: list[dict], decided: list[dict]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its pick (BET or
    NONE) in ONE
    transaction, under the model's lock, the ledger and the picks re-read
    inside it. -> (bets written, decisions written)."""
    if not decided:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    done = decided_games(conn, sorted({r["game_id"] for r in decided}))
    by_game = {r["game_id"]: r for r in rows}
    n_bets = n_decided = 0
    for rec in sorted(decided, key=lambda r: r["game_id"]):
        if rec["game_id"] in done:
            continue
        got = conn.execute(_INSERT_DECISION, {c: rec.get(c) for c in _DECISION_VALUES}).fetchone()
        if not got:
            continue
        n_decided += 1
        row = by_game.get(rec["game_id"])
        # A bet an earlier NCAAB bet on this game and side agrees with is
        # staked at NCAAB_AGREEMENT_STAKE_UNITS (models/ncaab_stake.py).
        if row is not None and conn.execute(_INSERT, ncaab_stake.stamp(conn, row, _COLS)).fetchone():
            n_bets += row["signal_type"] == "BET"
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A game the card could not decide: raised after the rest is written."""


_ART: dict = {}


def artifact(season: int) -> dict | None:
    if season not in _ART:
        try:
            _ART[season] = ft.load_artifact(season)
        except FileNotFoundError:
            _ART[season] = None
    return _ART[season]


def render(decisions: list[ft.Decision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAAB first-half total card ({MODEL_ID}): " + " ".join(
        f"{k}={v}" for k, v in diag.items())
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: x.game_id):
        lines.append(f"  {d.game_id:52s} {d.status:11s} {d.detail}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    from scripts.ncaab_first_half_window import lead_minutes, listed, slate
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("NCAAB first-half total card: RUN_NCAAB_FIRST_HALF is off; nothing read")
        return {"games": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    diag = {"games": 0, "already_decided": 0, "no_fetch_yet": 0, "missed": 0,
            "wrong_season": 0, "bets": 0, "below_cut": 0, "below_floor": 0, "no_quote": 0,
            "no_fg_line": 0, "edge_cap": 0, "big_favourite": 0, "quotes_dropped": 0}
    conn = get_connection()
    try:
        games = slate(conn, now)
        near = {g: v for g, v in games.items()
                if lead_minutes(v["tip"], now) <= DECISION_LEAD_MIN[1]}
        diag["games"] = len(near)
        if not near:
            logger.info(render([], diag))
            return {"games": 0, "bets": 0, "published": 0, "decided": 0, "diag": diag}
        if do_publish:
            ensure_decisions_table(conn)
        done = decided_games(conn, sorted(near))
        diag["already_decided"] = len(done)
        fetched = feed.decision_fetches(conn, sorted(set(near) - done), now,
                                        mark=feed.TOTAL_DECISION_MARK)
        due: dict[str, tuple[datetime, dict]] = {}
        problems: list[str] = []
        for gid, g in sorted(near.items()):
            if gid in done:
                continue
            f = fetched.get(gid)
            landed = (f is not None
                      and DECISION_LEAD_MIN[0] <= lead_minutes(g["tip"], f[0]) <= DECISION_LEAD_MIN[1])
            fresh = landed and (now - f[0]).total_seconds() / 60.0 <= MAX_DECISION_DELAY_MIN
            if fresh:
                due[gid] = f
            elif landed or lead_minutes(g["tip"], now) < DECISION_LEAD_MIN[0]:
                diag["missed"] += 1
                problems.append(gid)
            else:
                diag["no_fetch_yet"] += 1
        if problems:
            # Only games the feed lists for a full-game spread are planned a
            # fetch (scripts/ncaab_first_half_window.plan); a game it never
            # listed was never this model's to decide.
            have = listed(conn, problems)
            gone = [g for g in problems if g not in have]
            diag["missed"] -= len(gone)
            problems = [g for g in problems if g in have]
        decisions, records = [], []
        cuts = {g: f[0] for g, f in due.items()}
        quotes = decision_quotes(conn, cuts)
        fgc = fg_consensus(conn, cuts)
        lays = favourite_lays(conn, cuts)
        books = bet_books()
        floor = config.min_odds_for(MODEL_ID)
        stale: list[str] = []
        capped: list[str] = []
        for season in sorted({games[g]["season"] for g in due}):
            gids = sorted(g for g in due if games[g]["season"] == season)
            art = artifact(season)
            if art is None:
                diag["wrong_season"] += len(gids)
                stale += gids
                logger.error(f"NCAAB first-half total card: no artifact for season {season} "
                             f"(scripts/ncaab_first_half_total_build.py --last-season "
                             f"{season - 1}); {len(gids)} game(s) not decided")
                continue
            tg, sgames = team_games(conn, season, now, write=do_publish)
            res = ft.team_game_residuals(tg, art["tilt"]["alpha"], art["tilt"]["beta"])
            targets = pd.DataFrame({"game_id": gids,
                                    "home_team": [games[g]["home"] for g in gids],
                                    "away_team": [games[g]["away"] for g in gids],
                                    "stamp": [pd.Timestamp(due[g][0]) for g in gids]})
            tau = ft.team_effects(res, season, art["prior_team_sums"], targets,
                                  art["tilt"]["k"], art["tilt"]["w_prev"]).set_index("game_id")
            for gid in gids:
                q = quotes[quotes["game_id"] == gid]
                t = tau.loc[gid].to_dict() if gid in tau.index else None
                d = ft.decide(gid, q, fgc.get(gid), t, art, config.MODEL_EDGE_THRESHOLDS[MODEL_ID],
                              books=books, min_price=floor, fav_lays=lays.get(gid))
                diag[d.status] = diag.get(d.status, 0) + 1
                diag["quotes_dropped"] += _log_dropped(
                    ft.out_of_range(q, books), "first-half", "total_line", ft.QUOTE_PRICES)
                if d.status == "edge_cap":
                    logger.error(f"NCAAB first-half total card: {gid} not bet, its edge is a "
                                 f"data error: {d.detail}")
                    capped.append(gid)
                miss = (missing_halves(sgames, tg, games[gid]["home"], due[gid][0])
                        + missing_halves(sgames, tg, games[gid]["away"], due[gid][0]))
                decisions.append(d)
                records.append((d, due[gid][0], lead_minutes(games[gid]["tip"], due[gid][0]),
                                book_ages(q, due[gid][0]), miss))
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            rows, refused = pick_rows(decisions, games, _get_current_bankroll(conn))
            # An under beside a big favourite's spread bet on the same game is not bet.
            cbb_pairs.hold_back(conn, rows, refused)
            bet_ids = {r["game_id"] for r in rows if r["signal_type"] == "BET"}
            decided = [decision_row(d, fa, lead, ages, miss, d.game_id in bet_ids,
                                    refused.get(d.game_id))
                       for d, fa, lead, ages, miss in records]
            published, n_decided = publish(conn, rows, decided)
        logger.info("\n" + render(decisions, diag, published if do_publish else None,
                                  n_decided if do_publish else None))
        why = []
        if problems:
            why.append(f"no decision fetch landed {DECISION_LEAD_MIN[0]:g}-{DECISION_LEAD_MIN[1]:g} "
                       f"minutes before tip, or the card ran more than "
                       f"{MAX_DECISION_DELAY_MIN:g} minutes after it, not decided: {problems}")
        if stale:
            why.append(f"no artifact for the season of {stale}")
        if capped:
            why.append(f"edge above the data-error cap, decided with no bet: {capped}")
        if why:
            raise CardIncomplete("; ".join(why)[:1500])
        return {"games": len(near), "bets": diag["bets"], "published": published,
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
        logger.error(f"NCAAB first-half total card did not decide every due game: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-first-half-total-card")
    except Exception:  # noqa: BLE001
        pass
    main()
