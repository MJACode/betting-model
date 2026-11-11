"""NCAAF moneyline card: write `ncaaf_moneyline_market` bets (models/ncaaf_moneyline_market.py).

LIVE, real money (mike, 2026-11-10: "ML model yes"). Runs in its own job,
hourly at five past the hour UTC (scheduler.run_ncaaf_moneyline_card), and
writes picks only; the job then publishes them like every other card.
RUN_NCAAF_MONEYLINE_CARD=0 stops it before it reads anything; the job keeps
beating, so its silence still means stopped.

WHEN A GAME IS DECIDED: at 14:00 UTC on its Eastern date, and only then. The
run whose hour is 14:00 UTC reads each of the ten fetched books' moneyline and
spread as of 14:00 UTC (the newest pre-game row stamped 13:00-14:00 UTC) and
decides each of the day's games that kicks off at least five minutes after
14:00 UTC, bet or not. A run later in the 14:00 hour reads the same
as-of-14:00 quotes. The research read was the stored 13:55 UTC pull.

WHICH GAMES. NCAAF rows of `games` that kick off (commence_time, read in
Eastern time) yesterday or today, after their 14:00 UTC, and that one of the
ten books had priced by then. The kickoff decides the date, not game_date: a
night game can be stored twice, as the odds feed's Eastern-dated row, which
carries the prices and takes the pick, and as CFBD's UTC-dated row, which
carries the score and no prices. A row no book has priced is not the card's.
Where two priced rows are one game (the same two teams, kicking off within a
day), the one with more quotes in the hour is decided and the other is
recorded as `duplicate_game` with no bet.

A MISSED CHECK IS A FAILURE, NEVER A LATE BET. When a run after 14:59 UTC
finds one of the day's games with no decision, it writes the game's decision
as `missed` with no bet and the run exits 1: the job's heartbeat records
"error" and the failure alerter reports it. The one exception is the card's
first run ever (no ledger table yet): games whose 14:00 UTC came before the
card existed are written as `missed` without failing.

A RUN THAT CANNOT DECIDE ITS GAMES FAILS, after writing every game it could:
an artifact for another season (the game is then `missed` next hour); every
due game with no deciding book's moneyline at all (the odds steps have
stopped); a best side at a book config.BEST_LINE_BOOKMAKERS no longer lists
(except a state-limited one, config.STATE_LIMITED_BOOKMAKERS: that game is an
ordinary no-bet).

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
ncaaf_moneyline_decisions in the same transaction as the game's pick, under
the model's transaction-scoped advisory lock. A game with a decision row, or
with any ncaaf_moneyline_market BET, is never decided again: a moved price
writes nothing.

ONE GAME NEVER CARRIES TWO BETS THAT CANNOT BOTH WIN
(.claude/rules/picks-and-publishing.md). A game on which the NCAAF opening
spread model (ncaaf_spread, ncaaf_spread_premium) already holds a BET is
written here as `other_model_bet` and not priced.

A game priced and not bet (below the cut, or with too few books in the
consensus) is a NONE row (no stake) in the same transaction, so the board
shows every scored game; nothing publishes or settles a NONE row.
BET ROWS in picks, at the BET book's price: decision_* and best_* are that
book's moneyline, scored_line is NULL (a moneyline has no line), and line_book
is NULL. When DraftKings had a priced moneyline at 14:00 UTC, dk_odds /
dk_implied_prob / edge are DraftKings' own price on the bet side, the
reference; otherwise dk_odds is NULL and dk_implied_prob and edge 0.0. The
stake is the flat one (no stake_units). The label is the platform's
("Ohio State ML"), checked against the side before it is written
(tracking/pick_integrity.pick_problems). The price floor is applied twice:
inside the decision, before the pick (models/ncaaf_moneyline_market step 5),
and again here against config.min_odds_for.

    python -m scripts.ncaaf_moneyline_card              # print the card, write nothing
    python -m scripts.ncaaf_moneyline_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaaf_moneyline_market as mm  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = mm.MODEL_ID
SPORT = mm.SPORT
_ET = ZoneInfo("America/New_York")

# The NCAAF pre-game side models whose standing BET closes a game to this one.
OTHER_SIDE_MODELS = ("ncaaf_spread", "ncaaf_spread_premium")


def enabled() -> bool:
    """The kill switch: RUN_NCAAF_MONEYLINE_CARD=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_NCAAF_MONEYLINE_CARD", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it. `quotes`
# keeps every book's moneyline and spread at 14:00 UTC, with its flags.
DECISIONS_TABLE = "ncaaf_moneyline_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "check_hour", "instant", "status", "book", "side",
                  "price", "prob", "edge", "consensus", "mean", "n_books", "dk_price",
                  "n_bets", "quotes", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaaf_moneyline_decisions (
    game_id      TEXT PRIMARY KEY,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_hour   TEXT NOT NULL,
    instant      TEXT,
    status       TEXT NOT NULL,
    book         TEXT,
    side         TEXT,
    price        REAL,
    prob         REAL,
    edge         REAL,
    consensus    REAL,
    mean         REAL,
    n_books      INTEGER,
    dk_price     REAL,
    n_bets       INTEGER NOT NULL,
    quotes       TEXT,
    detail       TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO ncaaf_moneyline_decisions (game_id, check_hour, instant, status, book, side, "
    "price, prob, edge, consensus, mean, n_books, dk_price, n_bets, quotes, detail) VALUES "
    "(%(game_id)s, %(check_hour)s, %(instant)s, %(status)s, %(book)s, %(side)s, %(price)s, "
    "%(prob)s, %(edge)s, %(consensus)s, %(mean)s, %(n_books)s, %(dk_price)s, %(n_bets)s, "
    "%(quotes)s, %(detail)s) ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


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


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games with a decision row, or with any ncaaf_moneyline_market BET
    whatever became of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            "SELECT game_id FROM ncaaf_moneyline_decisions WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    bet = {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}
    return done | bet


def side_model_bets(conn, game_ids) -> set[str]:
    """Games on which another NCAAF pre-game side model holds a BET. A BET
    counts unless it is VOID or was written while its model was paused, the
    scorer's own reading of a standing bet (models/scorer._apply_side_conflicts)."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = ANY(%s) AND signal_type = 'BET' AND game_id = ANY(%s)
          AND condition_status IS DISTINCT FROM 'VOID'
          AND downgrade_reason IS DISTINCT FROM %s
    """, (list(OTHER_SIDE_MODELS), sorted(game_ids), config.PAUSED_NOTE)).fetchall()}


# ── reads ─────────────────────────────────────────────────────────────────────

def _kick(text) -> datetime | None:
    try:
        t = pd.Timestamp(str(text))
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.to_pydatetime()


def _priced_by(conn, game_ids: list[str], instant: datetime) -> set[str]:
    """The games one of the ten books had a pre-game moneyline or spread row
    for, stamped at or before `instant`. One index probe a game."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT g.game_id FROM unnest(%s::text[]) AS g(game_id)
        WHERE EXISTS (
            SELECT 1 FROM odds o
            WHERE o.game_id = g.game_id AND o.market = ANY(%s) AND o.bookmaker = ANY(%s)
              AND o.snapshot_type IS DISTINCT FROM 'in_play'
              AND o.snapshot_at::timestamptz <= %s)
    """, (sorted(game_ids), ["h2h", "spreads"], list(mm.CONS_BOOKS),
          instant.isoformat())).fetchall()}


def slate(conn, now: datetime) -> dict[str, dict]:
    """NCAAF games kicking off on yesterday's or today's Eastern date, after
    their 14:00 UTC, that a book had priced by then: the games this run may
    decide or must report missed."""
    today = now.astimezone(_ET).date()
    want = {(today - timedelta(days=d)).isoformat() for d in (1, 0)}
    # game_date is the Eastern date on the odds feed's row and the UTC date on
    # an older CFBD row, so a night game's row can be dated a day later.
    dates = sorted(want | {(today + timedelta(days=1)).isoformat()})
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAAF' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away in rows:
        kick = _kick(ct)
        if kick is None:
            continue
        et_date = mm.eastern_date(kick)
        if et_date not in want:
            continue
        instant = mm.check_instant(et_date)
        if instant >= kick:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": kick,
                    "instant": instant, "commence_time": ct, "home": home, "away": away}
    priced: set[str] = set()
    for instant in sorted({v["instant"] for v in out.values()}):
        priced |= _priced_by(conn, [g for g, v in out.items() if v["instant"] == instant], instant)
    return {g: v for g, v in out.items() if g in priced}


def same_game_groups(games: dict[str, dict]) -> list[list[str]]:
    """Game ids that are one real game: the same two teams, kicking off within
    a day. Only groups of two or more."""
    by_pair: dict = {}
    for gid, v in games.items():
        by_pair.setdefault(frozenset((v["home"], v["away"])), []).append(gid)
    out = []
    for ids in by_pair.values():
        ids = sorted(ids)
        if len(ids) > 1 and all(
                abs((games[a]["tip"] - games[ids[0]]["tip"]).total_seconds()) <= 86400 for a in ids):
            out.append(ids)
    return out


# ── rows ──────────────────────────────────────────────────────────────────────

_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link",
         "downgrade_reason")
# Its own column list, NOT models.scorer._insert_picks: that one stamps
# model_probability_cal from the promoted map, and this model decides on its
# own number (config.MODELS_ON_OWN_PROBABILITY). No stake_units: the flat stake.
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def _link(v):
    return None if v is None or (isinstance(v, float) and v != v) else v


def _num(v):
    return None if v is None or (isinstance(v, float) and v != v) else float(v)


def _is_bet(row: dict | None) -> bool:
    return row is not None and row["signal_type"] == "BET"


# Priced, and not bet for a reason of the rule's own: written as a NONE row.
SCORED_NO_BET = ("below_cut", "too_few_books")


def pick_rows(decisions: list[mm.Decision], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Decisions -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs.

    A bet is a BET row. A game priced and not bet (SCORED_NO_BET), or a bet
    the price or EV floor refused, is a NONE row at the same book and side
    with no stake. Nothing publishes or settles a NONE row."""
    from models.honest_ev import gate
    from models.scorer import _build_pick_label, _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    rows, refused = [], {}
    for d in decisions:
        is_bet = d.status == "bets"
        if d.best is None or not (is_bet or d.status in SCORED_NO_BET):
            continue
        b = d.best
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        side = b["side"]
        price, prob = float(b["price"]), float(b["prob"])
        if is_bet and floor is not None and price < floor:
            refused[d.game_id] = f"below_price_floor:{price:+.0f}"
            is_bet = False
        if is_bet:
            ev = gate(MODEL_ID, prob, price)
            if not ev.clears:
                logger.info(f"{MODEL_ID}: {ev.reason} - dropped {d.game_id} {side}")
                refused[d.game_id] = ev.reason or "below_ev_floor"
                is_bet = False
        label = _build_pick_label(side, home, away, mm.MARKET, None)
        problems = pick_problems(label, side, None, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {d.game_id} {label!r}: {'; '.join(problems)}")
            if d.game_id not in refused and is_bet:
                refused[d.game_id] = "label_mismatch"
            continue
        imp = implied(price)
        edge = round(prob - imp, 4)
        kelly_frac, rec_bet = quarter_kelly(prob, imp, bankroll) if is_bet else (0.0, 0.0)
        dk = d.dk
        if dk:
            dk_price = float(dk["p1"] if side == "home" else dk["p2"])
            dk_imp = implied(dk_price)
            dk_cols = {"dk_odds": dk_price, "dk_implied_prob": round(dk_imp, 4),
                       "edge": round(prob - dk_imp, 4),
                       "dk_bet_link": _link(dk.get("link1") if side == "home" else dk.get("link2"))}
        else:
            dk_cols = {"dk_odds": None, "dk_implied_prob": 0.0, "edge": 0.0, "dk_bet_link": None}
        rows.append({
            "game_id": d.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"), "game_time": g.get("commence_time"),
            "pick_side": side, "pick_label": label,
            # The bet side's fair chance of winning from the consensus spread:
            # the number the 0.02 cut was measured on.
            "model_probability": round(prob, 4),
            "model_probability_cal": round(prob, 4),
            "scored_line": None,
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
            # MED on every bet, as the other rule cards write: the evidence
            # gives no tier.
            "confidence_tier": "MED",
            **dk_cols,
            "line_book": None,
            "decision_book": b["bookmaker"], "decision_odds": price,
            "decision_implied_prob": round(imp, 4), "decision_edge": edge,
            # The bet IS the best side, at a book in config.BEST_LINE_BOOKMAKERS
            # (decide() refuses any other).
            "best_book": b["bookmaker"], "best_odds": price, "best_implied_prob": round(imp, 4),
            "best_edge": edge, "best_bet_link": _link(b.get("link")),
            "downgrade_reason": pause,
        })
    return rows, refused


def decision_row(d: mm.Decision, check_hour: datetime, instant: datetime | None,
                 bet_written: bool, refused: str | None) -> dict:
    b = d.best or {}
    detail = d.status + ": " + d.detail + (f"; refused {refused}" if refused else "")
    side = b.get("side")
    return {"game_id": d.game_id, "check_hour": check_hour.isoformat(),
            "instant": instant.isoformat() if instant else None, "status": d.status,
            "book": b.get("bookmaker"), "side": side,
            "price": _num(b.get("price")), "prob": _num(b.get("prob")),
            "edge": _num(b.get("edge")), "consensus": _num(b.get("cons")),
            "mean": _num(b.get("mu")),
            "n_books": int(b["n_ok"]) if b.get("n_ok") is not None else None,
            "dk_price": (_num(d.dk["p1"] if side == "home" else d.dk["p2"])
                         if d.dk and side else None),
            "n_bets": 1 if bet_written else 0,
            "quotes": json.dumps(d.quotes) if d.quotes else None, "detail": detail[:2000]}


FINAL = ("bets", "below_cut", "too_few_books", "book_not_bettable", "no_quotes", "no_consensus",
         "no_clean_quote", "missed", "kicked_off", "other_model_bet", "duplicate_game")


def publish(conn, rows: list[dict], decisions: list[mm.Decision], check_hour: datetime,
            games: dict[str, dict], refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its pick (BET or
    NONE) in ONE transaction, under the model's lock, the ledger and the picks
    re-read inside it. -> (bets written, decisions written)."""
    final = [d for d in decisions if d.status in FINAL]
    if not final:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    ids = sorted({d.game_id for d in final})
    done = decided_games(conn, ids)
    held = side_model_bets(conn, ids)
    by_game = {r["game_id"]: r for r in rows}
    n_bets = n_decided = 0
    for d in sorted(final, key=lambda x: x.game_id):
        if d.game_id in done:
            continue
        row = by_game.get(d.game_id)
        if d.status == "bets" and d.game_id in held:
            # The spread model bet this game while this run priced it.
            d.status = "other_model_bet"
            d.detail += "; the NCAAF spread model bet this game first"
            row = None
        g = games.get(d.game_id, {})
        got = conn.execute(_INSERT_DECISION, decision_row(
            d, check_hour, g.get("instant"), _is_bet(row), refused.get(d.game_id))).fetchone()
        if not got:
            continue
        n_decided += 1
        if row is not None and conn.execute(_INSERT, row).fetchone():
            n_bets += row["signal_type"] == "BET"
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A game the card could not decide at 14:00 UTC, or a run that found the
    odds missing: raised after the rest of the run is written."""


_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = mm.load_artifact()
    return _ART["a"]


def render(decisions: list[mm.Decision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAAF moneyline card ({MODEL_ID}): " + " ".join(f"{k}={diag.get(k, 0)}" for k in mm.DIAG_KEYS)
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: x.game_id):
        lines.append(f"  {d.game_id:52s} {d.status}: {d.detail}")
    return "\n".join(lines)


def _drop_duplicate_rows(part: dict, ml_rows: pd.DataFrame, sp_rows: pd.DataFrame) -> list[mm.Decision]:
    """Where two of the due rows are one real game, keep the row with more
    quotes in the hour (a tie: the lower game id) and decide the others as
    duplicate_game. Removes them from `part` in place."""
    out = []
    n = pd.concat([ml_rows["game_id"], sp_rows["game_id"]]).value_counts().to_dict()
    for ids in same_game_groups(part):
        keep = sorted(ids, key=lambda g: (-n.get(g, 0), g))[0]
        for gid in ids:
            if gid != keep:
                out.append(mm.Decision(gid, "duplicate_game",
                                       f"the same game as {keep}, which holds the quotes"))
                part.pop(gid)
    return out


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("NCAAF moneyline card: RUN_NCAAF_MONEYLINE_CARD is off; nothing read")
        return {"games": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    hour = now.replace(minute=0, second=0, microsecond=0)
    diag = dict.fromkeys(mm.DIAG_KEYS, 0)
    conn = get_connection()
    try:
        games = slate(conn, now)
        diag["games"] = len(games)
        due = {g: v for g, v in games.items() if v["instant"] == hour}
        overdue = {g: v for g, v in games.items() if v["instant"] < hour}
        if not due and not overdue:
            logger.info(render([], diag))
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "diag": diag}
        first_run = not ledger_exists(conn)
        if do_publish:
            ensure_decisions_table(conn)
        done = decided_games(conn, sorted(due) + sorted(overdue))
        diag["already_decided"] = len(done)
        due = {g: v for g, v in due.items() if g not in done}
        overdue = {g: v for g, v in overdue.items() if g not in done}
        decisions: list[mm.Decision] = []
        # One game never carries two bets that cannot both win: a game the
        # spread model has bet is recorded, not priced, and not missed.
        held = side_model_bets(conn, sorted(due) + sorted(overdue))
        for gid in sorted(held):
            decisions.append(mm.Decision(gid, "other_model_bet",
                                         "the NCAAF spread model already holds a bet on this game"))
        due = {g: v for g, v in due.items() if g not in held}
        overdue = {g: v for g, v in overdue.items() if g not in held}
        problems: list[str] = []          # each fails the run, after the writes
        missed = []
        for gid, v in sorted(overdue.items()):
            if mm.too_close(v["tip"], v["instant"]):
                decisions.append(mm.Decision(gid, "kicked_off",
                                             "kicks off less than 5 minutes after 14:00 UTC"))
                continue
            why = ("the card had not run yet" if first_run else
                   f"no run decided it in the 14:00 UTC hour (this run {now:%H:%M}Z)")
            decisions.append(mm.Decision(gid, "missed", why))
            missed.append(gid)
        if missed and not first_run:
            problems.append(f"{len(missed)} game(s) missed their 14:00 UTC decision: "
                            + ", ".join(missed[:20]))
        gone = {g: v for g, v in due.items()
                if v["tip"] <= now or mm.too_close(v["tip"], v["instant"])}
        for gid in sorted(gone):
            decisions.append(mm.Decision(gid, "kicked_off", "kicked off before this run, or less "
                                                            "than 5 minutes after 14:00 UTC"))
        due = {g: v for g, v in due.items() if g not in gone}
        if due:
            art = artifact()
            for season in sorted({v["season"] for v in due.values()}):
                gids = sorted(g for g, v in due.items() if v["season"] == season)
                if int(art["season"]) != season:
                    msg = (f"the artifact is for season {art['season']}; season {season} needs one "
                           f"built through {season - 1} (scripts/ncaaf_moneyline_market_build.py). "
                           f"{len(gids)} game(s) not decided")
                    logger.error(f"NCAAF moneyline card: {msg}.")
                    problems.append(msg)
                    continue
                part = {g: due[g] for g in gids}
                ml_rows = bq.load_rows(conn, part, hour, market="h2h",
                                       window_min=int(art["window_min"]), books=mm.CONS_BOOKS)
                sp_rows = bq.load_rows(conn, part, hour, market="spreads",
                                       window_min=int(art["window_min"]), books=mm.CONS_BOOKS)
                decisions += _drop_duplicate_rows(part, ml_rows, sp_rows)
                q = mm.quotes_at(ml_rows[ml_rows["game_id"].isin(part)],
                                 sp_rows[sp_rows["game_id"].isin(part)], int(art["window_min"]))
                got = mm.decide(sorted(part), q, art["table"], art["offset"],
                                config.MODEL_EDGE_THRESHOLDS[MODEL_ID],
                                bettable=tuple(config.BEST_LINE_BOOKMAKERS),
                                min_price=float(art["min_price"]),
                                min_other=int(art["min_other_books"]))
                if got and all(d.status == "no_quotes" for d in got):
                    problems.append(f"no deciding book has a moneyline stamped 13:00-14:00 UTC for "
                                    f"any of the {len(got)} due game(s): the odds refresh may have "
                                    f"stopped")
                for d in got:
                    if d.status == "book_not_bettable":
                        book = str((d.best or {}).get("bookmaker") or "").lower()
                        if book in config.STATE_LIMITED_BOOKMAKERS:
                            # Expected, not broken: a pick may never name this book.
                            logger.info(f"NCAAF moneyline card: {d.game_id} not bet, its best "
                                        f"quote is at {book}, which a pick never names")
                        else:
                            problems.append(f"book_not_bettable {d.game_id} ({d.detail})")
                decisions += got
        for d in decisions:
            diag[d.status] = diag.get(d.status, 0) + 1
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            prows, refused = pick_rows(decisions, games, _get_current_bankroll(conn))
            published, n_decided = publish(conn, prows, decisions, hour, games, refused)
        logger.info("\n" + render(decisions, diag, published if do_publish else None,
                                  n_decided if do_publish else None))
        if problems:
            # After the writes: every game that could be decided was, and its
            # bet still goes out; this one fails the heartbeat.
            raise CardIncomplete(f"{len(problems)} problem(s): " + "; ".join(problems)[:1500])
        return {"games": len(games), "bets": diag["bets"], "published": published,
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
        # exit 1: scheduler.run_ncaaf_moneyline_card then raises, so the job's
        # heartbeat records "error" and the failure alerter reports it.
        logger.error(f"NCAAF moneyline card did not decide every game at 14:00 UTC: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). The card reads the
    # database only; installed so the scheduler runs no uninstrumented script.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaaf-moneyline-card")
    except Exception:  # noqa: BLE001
        pass
    main()
