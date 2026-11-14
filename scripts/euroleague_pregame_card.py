"""EuroLeague pre-game card: write the four EuroLeague rule cards' picks
(models/euroleague_pregame.py).

LIVE, real money (mike, 2026-11-14: "I told you to build all the models"),
knowing each rule MISSED part of the research bar (docs/sports/euroleague.md).
Run by the EuroLeague pre-game window job every minute
(scheduler.run_euroleague_pregame_window, scripts/euroleague_pregame_window.py)
once a game is 10.5 minutes or less from tip; the job then publishes what it
wrote. RUN_EUROLEAGUE_PREGAME=0 stops the job before anything is read or
bought. Each model has its own switch, read here before that model decides a
game: RUN_EUROLEAGUE_HOME_ML, RUN_EUROLEAGUE_HOME_DOG_SPREAD,
RUN_EUROLEAGUE_H1_DOG_ML, RUN_EUROLEAGUE_Q1_SHARE_TOTAL (=0, false, off or
no). A switched-off model
writes nothing, not even a decision row.

WHEN A GAME IS DECIDED: on the decision fetch, the per-event call made ten
minutes before tip (data/ingestors/euroleague_period_odds.DECISION_MARK), when
it landed 5 to 10.5 minutes before tip (DECISION_LEAD_MIN). The research
graded that one instant for all four rules: the full-game rules on the board
at the last five-minute snapshot at or before tip minus 10, the period rules on
the purchase's call made at tip minus 10. The full-game rules read the BOARD
at the fetch instant (every stored pre-game quote, the fetch's own included,
stamped at or before it); the period rules read the fetch's own rows.

WHEN THE DECISION FETCH IS MISSING. From 5 minutes before tip, with no
decision fetch landed, the full-game rules decide on the stored board as of
tip minus 10 (the hourly refresh passes' quotes; the row says so), and the two
period rules record `missed` (no bet): the research supports no other fetch for
them. A game that tipped with a model undecided is recorded `missed` too. A
`missed` fails the run AFTER every other write, so the job's heartbeat records
"error" and the failure alerter reports it. The one exception is the card's
first run ever (no ledger yet): games that tipped before the card existed are
written `missed` without failing.

EACH GAME DECIDED ONCE PER MODEL (CLAUDE.md 1c). The decision, bet or not, is
written to euroleague_pregame_decisions in the same transaction as the game's
pick, under each model's advisory lock. A (game, model) with a decision row, or
with any BET of that model, is never decided again: a moved price writes
nothing.

ONE GAME NEVER CARRIES TWO BETS THAT CANNOT BOTH WIN
(.claude/rules/picks-and-publishing.md). A full-game moneyline or spread
that cannot win beside a standing EuroLeague full-game BET (the two here, the
halftime spread) is written NONE; the standing BET keeps the game. The two
full-game rules here both bet the home side, so they never conflict with each
other, and a first-half or first-quarter bet and a full-game bet can always
both win.

ROWS. A bet is a BET row at the best deciding-book price (CLAUDE.md 6); a game
a rule priced and did not bet is a NONE row at the side and price it would have
taken, no stake, so the whole universe can be graded; nothing publishes or
settles a NONE row. The gates, each turning a bet into a NONE row with the
reason: the price floor (config.min_odds_for), the model's own EV floor
(models.honest_ev.gate on its own probability), the edge and probability cut
(config.MODEL_EDGE_THRESHOLDS / MODEL_PROB_THRESHOLDS: every surface applies
it, so a bet under it would never post), the data-error edge cap
(models/euroleague_quote_bounds.py), the pick-integrity check
(tracking/pick_integrity.pick_problems) and the conflict rule above.
scored_line is the HOME number for the spread (CLAUDE.md 4), the total for the
first-quarter total, NULL for a moneyline. dk_odds / dk_implied_prob / edge are
DraftKings' own quote on the side (the same number), else NULL / 0.0 / 0.0
with line_book naming the bet book. The label is the platform's
(models.scorer._build_pick_label). The stake is the flat one.

    python -m scripts.euroleague_pregame_card              # print the card, write nothing
    python -m scripts.euroleague_pregame_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import data.ingestors.euroleague_period_odds as feed  # noqa: E402
import models.euroleague_pregame as R  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

SPORT = R.SPORT
MODELS = R.MODELS
SWITCHES = {
    R.HOME_ML: "RUN_EUROLEAGUE_HOME_ML",
    R.HOME_DOG_SPREAD: "RUN_EUROLEAGUE_HOME_DOG_SPREAD",
    R.H1_DOG_ML: "RUN_EUROLEAGUE_H1_DOG_ML",
    R.Q1_SHARE_TOTAL: "RUN_EUROLEAGUE_Q1_SHARE_TOTAL",
}
# A decision fetch counts when it landed this many minutes before tip.
DECISION_LEAD_MIN = (5.0, 10.5)
# The card looks at games this close to tip, and back this far for misses.
CARD_LEAD_MIN = 10.5
LOOKBACK_HOURS = 3.0
# The research's decision instant: tip minus 10 (models/euroleague_pregame.py).
CLOSE_LEAD = timedelta(minutes=10)
# Every full-game EuroLeague model a pre-game bet may conflict with.
FULL_GAME_MODELS = R.FULL_GAME_MODELS + ("euroleague_live_spread_ht",)


def _on(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() not in ("0", "false", "off", "no")


def enabled() -> bool:
    """The whole job's switch: RUN_EUROLEAGUE_PREGAME=0 (or false/off/no)."""
    return _on("RUN_EUROLEAGUE_PREGAME")


def models_on() -> tuple[str, ...]:
    return tuple(m for m in MODELS if _on(SWITCHES[m]))


def deciding_books() -> tuple:
    """The research's five books a pick may name, less any the platform has
    taken out of config.BEST_LINE_BOOKMAKERS."""
    allowed = set(config.BEST_LINE_BOOKMAKERS)
    return tuple(b for b in R.DECIDABLE if b in allowed)


# ── the decisions ledger (worker-only: data/anon_readable.WORKER_ONLY_TABLES) ──
DECISIONS_TABLE = "euroleague_pregame_decisions"
DECISIONS_COLS = ("game_id", "model_id", "decided_at", "decision_at", "fetch_at", "lead_min",
                  "status", "side", "book", "price", "line", "p_fair", "uplift", "p_model", "ev",
                  "edge", "dk_price", "n_books", "n_bets", "detail", "extra")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_pregame_decisions (
    game_id      TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_at  TIMESTAMPTZ,
    fetch_at     TIMESTAMPTZ,
    lead_min     REAL,
    status       TEXT NOT NULL,
    side         TEXT,
    book         TEXT,
    price        REAL,
    line         REAL,
    p_fair       REAL,
    uplift       REAL,
    p_model      REAL,
    ev           REAL,
    edge         REAL,
    dk_price     REAL,
    n_books      INTEGER,
    n_bets       INTEGER NOT NULL,
    detail       TEXT,
    extra        TEXT,
    PRIMARY KEY (game_id, model_id)
)
"""
_VALUES = tuple(c for c in DECISIONS_COLS if c != "decided_at")
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} ({', '.join(_VALUES)}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in _VALUES)}) "
    f"ON CONFLICT (game_id, model_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down; free after that."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True,
                         revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())


def decided(conn, game_ids: list[str]) -> set[tuple[str, str]]:
    """(game, model) pairs with a decision row, or with any BET of that model
    whatever became of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[tuple[str, str]] = set()
    if ledger_exists(conn):
        done = {(g, m) for g, m in conn.execute(
            f"SELECT game_id, model_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    done |= {(g, m) for g, m in conn.execute("""
        SELECT DISTINCT game_id, model_id FROM picks
        WHERE model_id = ANY(%s) AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (list(MODELS), list(game_ids))).fetchall()}
    return done


def standing_full_game(conn, game_ids: list[str]) -> list[dict]:
    """The games' standing full-game EuroLeague BETs, pre-game and live. A BET
    counts unless it is VOID or was written while its model was paused."""
    if not game_ids:
        return []
    rows = conn.execute("""
        SELECT game_id, model_id, pick_side, scored_line, pick_label FROM picks
        WHERE game_id = ANY(%s) AND signal_type = 'BET' AND model_id = ANY(%s)
          AND condition_status IS DISTINCT FROM 'VOID'
          AND downgrade_reason IS DISTINCT FROM %s
    """, (list(game_ids), list(FULL_GAME_MODELS), config.PAUSED_NOTE)).fetchall()
    out = []
    for gid, mid, side, line, label in rows:
        market = "spreads" if mid in ("euroleague_live_spread_ht", R.HOME_DOG_SPREAD) else "h2h"
        if side in ("home", "away"):
            out.append({"game_id": gid, "model_id": mid, "market": market, "side": side,
                        "line": None if line is None else float(line), "label": label})
    return out


# ── reads ─────────────────────────────────────────────────────────────────────

def _ts(v) -> datetime | None:
    return feed._when(v)


def slate(conn, now: datetime) -> dict[str, dict]:
    """EuroLeague games tipping within CARD_LEAD_MIN, or that tipped within
    LOOKBACK_HOURS: the games this run may decide or must report missed."""
    days = [(now + timedelta(days=d)).date().isoformat() for d in (-1, 0, 1)]
    rows = conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.commence_time, g.home_team, g.away_team,
               e.neutral_site, e.venue_name
        FROM games g LEFT JOIN euroleague_events e ON e.game_id = g.game_id
        WHERE g.sport = %s AND g.game_date = ANY(%s)
    """, (SPORT, days)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away, neutral, venue in rows:
        tip = _ts(ct)
        if tip is None:
            continue
        lead = (tip - now).total_seconds() / 60.0
        if lead > CARD_LEAD_MIN or lead < -LOOKBACK_HOURS * 60:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": tip,
                    "commence_time": ct, "home": home, "away": away,
                    "neutral_site": bool(neutral), "venue_name": venue}
    return out


_ODDS_COLS = ("game_id", "market", "bookmaker", "snapshot_at", "created_at", "source",
              "home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price", "home_link", "away_link", "over_link", "under_link")


def odds_rows(conn, game_ids: list[str], markets: tuple, source: str | None = None) -> pd.DataFrame:
    """The games' stored pre-game rows in `markets` (and of `source` when
    given), snapshot_at and created_at as instants."""
    if not game_ids:
        return pd.DataFrame(columns=list(_ODDS_COLS))
    src = "AND source = %s" if source else ""
    params = [list(game_ids), list(markets)] + ([source] if source else [])
    rows = conn.execute(f"""
        SELECT game_id, market, bookmaker, snapshot_at::timestamptz, created_at, source,
               home_price, away_price, draw_price, spread_home, total_line,
               over_price, under_price, home_link, away_link, over_link, under_link
        FROM odds WHERE game_id = ANY(%s) AND market = ANY(%s)
          AND snapshot_type IS DISTINCT FROM 'in_play' {src}
    """, tuple(params)).fetchall()
    df = pd.DataFrame([tuple(r) for r in rows], columns=list(_ODDS_COLS))
    for c in ("snapshot_at", "created_at"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
    return df


def share_history(conn) -> pd.DataFrame:
    """Every scored EuroLeague game's first-quarter share
    (models/euroleague_pregame.share_history), from games and
    euroleague_period_scores."""
    g = pd.DataFrame([tuple(r) for r in conn.execute("""
        SELECT game_id, commence_time, home_team, away_team, home_score, away_score
        FROM games WHERE sport = %s AND home_score IS NOT NULL AND away_score IS NOT NULL
    """, (SPORT,)).fetchall()], columns=["game_id", "commence_time", "home_code", "away_code",
                                         "home_score", "away_score"])
    p = pd.DataFrame([tuple(r) for r in conn.execute(
        "SELECT game_id, period, home_points, away_points FROM euroleague_period_scores "
        "WHERE period = 1").fetchall()], columns=["game_id", "period", "home_points", "away_points"])
    g["played"] = True
    return R.share_history(g, p)


# ── deciding ─────────────────────────────────────────────────────────────────

def due_games(games: dict, fetched: dict, now: datetime, todo: dict) -> tuple[dict, dict, list]:
    """Split the slate: {game: (T, fetch_at|None)} to decide now, {game: why}
    to record missed, and the games still waiting. `todo`: game -> the models
    not yet decided."""
    due, missed, waiting = {}, {}, []
    for gid, g in sorted(games.items()):
        if not todo.get(gid):
            continue
        lead = (g["tip"] - now).total_seconds() / 60.0
        f = fetched.get(gid)
        flead = None if f is None else (g["tip"] - f).total_seconds() / 60.0
        if lead <= 0:
            missed[gid] = "tipped before it was decided"
        elif f is not None and DECISION_LEAD_MIN[0] <= flead <= DECISION_LEAD_MIN[1]:
            due[gid] = (f, f)
        elif lead <= DECISION_LEAD_MIN[0]:
            due[gid] = (g["tip"] - CLOSE_LEAD, None)
        else:
            waiting.append(gid)
    return due, missed, waiting


def decide(games: dict, due: dict, todo: dict, fg: pd.DataFrame, per: pd.DataFrame,
           hist: pd.DataFrame | None, arts: dict, books: tuple) -> list[R.Decision]:
    """Every due (game, model) decision. Pure given its inputs."""
    out: list[R.Decision] = []
    tips = pd.Series({g: v["tip"] for g, v in games.items()})
    prepared = R.prepare_fullgame(fg, tips)
    for gid, (T, fetch_at) in sorted(due.items()):
        g = games[gid]
        want = todo.get(gid, ())
        art = arts.get(g["season"])
        if art is None:
            for m in want:
                out.append(R.Decision(gid, m, "no_artifact",
                                      f"no artifact for season {g['season']} "
                                      f"(scripts/euroleague_pregame_build.py)"))
            continue
        gf = pd.DataFrame([{"game_id": gid, "season": g["season"], "home_code": g["home"],
                            "away_code": g["away"], "neutral_site": g["neutral_site"],
                            "venue_name": g["venue_name"], "tip": g["tip"]}])
        p = prepared[prepared.game_id == gid]
        if fetch_at is not None:
            p = p[(p.created_at.isna()) | (p.created_at <= pd.Timestamp(fetch_at))] if "created_at" in p else p
        board = R.board_at(p, pd.Series({gid: pd.Timestamp(T)}))
        got: list[R.Decision] = []
        if R.HOME_ML in want:
            got += R.decide_home_ml(board, gf, art, books)
        if R.HOME_DOG_SPREAD in want:
            got += R.decide_home_dog(board, gf, art, books)
        if fetch_at is None:
            for m in (R.H1_DOG_ML, R.Q1_SHARE_TOTAL):
                if m in want:
                    got.append(R.Decision(gid, m, "missed",
                                          "no decision fetch landed 5-10.5 minutes before tip"))
        else:
            rows = per[(per.game_id == gid) & (per.created_at == pd.Timestamp(fetch_at))]
            pq = R.prepare_period(rows)
            if R.H1_DOG_ML in want:
                got += R.decide_h1_dog(pq, gf, art, books)
            if R.Q1_SHARE_TOTAL in want:
                got += R.decide_q1_share(pq, rows, board, hist if hist is not None else
                                         pd.DataFrame(columns=["game_id", "tip", "home_code", "away_code",
                                                               "share"]), gf, art, books)
        for d in got:
            d.extra.setdefault("decision_at", pd.Timestamp(T).isoformat())
            if fetch_at is None and d.model_id in R.FULL_GAME_MODELS:
                d.detail += "; no decision fetch: the stored board at tip minus 10"
            if d.scored:
                R.finish(d, art["models"][d.model_id]["uplift"])
        out += got
    return out


# ── rows ──────────────────────────────────────────────────────────────────────

_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link",
         "downgrade_reason")
# Its own column list: these models decide on their own number
# (config.MODELS_ON_OWN_PROBABILITY). No stake_units: the flat stake.
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def _link(rows: pd.DataFrame, d: R.Decision, book: str | None) -> str | None:
    """The stored deep link for the side at `book` (the same number)."""
    if rows is None or rows.empty or book is None:
        return None
    r = rows[(rows.game_id == d.game_id) & (rows.market == R.MARKET[d.model_id]) & (rows.bookmaker == book)]
    if d.line is not None:
        col = "spread_home" if R.MARKET[d.model_id].startswith("spreads") else "total_line"
        r = r[pd.to_numeric(r[col], errors="coerce") == d.line]
    if r.empty:
        return None
    col = {"home": "home_link", "away": "away_link", "over": "over_link", "under": "under_link"}[d.side]
    v = r.sort_values("snapshot_at").iloc[-1][col]
    return None if v is None or (isinstance(v, float) and v != v) else str(v)


def bet_problem(d: R.Decision, label: str, home: str, away: str) -> str | None:
    """Why a decided BET may not be written as one, or None."""
    from models.euroleague_quote_bounds import edge_problem
    from models.honest_ev import gate
    floor = config.min_odds_for(d.model_id)
    if floor is not None and d.price < floor:
        return f"below_price_floor:{d.price:+.0f}"
    if d.p_model is None:
        return "no_probability"
    ev = gate(d.model_id, d.p_model, d.price)
    if not ev.clears:
        return ev.reason or "below_ev_floor"
    if d.p_model < float(config.MODEL_PROB_THRESHOLDS[d.model_id]):
        return f"below_prob_cut:{d.p_model:.3f}"
    if d.edge < float(config.MODEL_EDGE_THRESHOLDS[d.model_id]):
        return f"below_edge_cut:{d.edge:+.4f}"
    why = edge_problem(d.edge, d.model_id)
    if why:
        return why
    problems = pick_problems(label, d.side, d.line, d.model_id, home, away)
    if problems:
        return "label_mismatch: " + "; ".join(problems)
    return None


def pick_rows(decisions: list[R.Decision], games: dict, bankroll: float,
              link_rows: pd.DataFrame | None = None) -> tuple[list[dict], dict]:
    """Decisions -> picks rows (BET or NONE), and {(game, model): why} for a
    bet turned into a NONE row here. Pure given its inputs."""
    from models.scorer import _build_pick_label, _pause_note, quarter_kelly
    rows, refused = [], {}
    for d in decisions:
        if not d.scored or d.price is None or d.side is None:
            continue
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        label = _build_pick_label(d.side, home, away, R.MARKET[d.model_id], d.line)
        is_bet = d.status == "bet"
        if is_bet:
            why = bet_problem(d, label, home, away)
            if why:
                logger.info(f"{d.model_id}: {d.game_id} {d.side} not bet: {why}")
                refused[(d.game_id, d.model_id)] = why
                is_bet = False
        if pick_problems(label, d.side, d.line, d.model_id, home, away):
            continue      # never a row whose label disagrees with its side and number
        price = float(d.price)
        imp = implied(price)
        p_model = d.p_model if d.p_model is not None else d.p_fair
        edge = round(float(p_model) - imp, 4) if p_model is not None else 0.0
        kelly_frac, rec_bet = quarter_kelly(p_model, imp, bankroll) if is_bet else (0.0, 0.0)
        dk = d.dk_price
        link = _link(link_rows, d, d.book)
        dk_link = _link(link_rows, d, R.REFERENCE_BOOK) if dk is not None else None
        rows.append({
            "game_id": d.game_id, "model_id": d.model_id, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g["tip"].isoformat() if g.get("tip") is not None else None,
            "pick_side": d.side, "pick_label": label,
            # The market's no-vig chance of the side plus the rule's walk-forward
            # uplift (models/euroleague_pregame.py, THE PROBABILITY); the model
            # decides on it (config.MODELS_ON_OWN_PROBABILITY).
            "model_probability": None if p_model is None else round(float(p_model), 4),
            "model_probability_cal": None if p_model is None else round(float(p_model), 4),
            "dk_odds": dk,
            "dk_implied_prob": round(implied(dk), 4) if dk is not None else 0.0,
            "edge": round(float(p_model) - implied(dk), 4) if dk is not None and p_model is not None else 0.0,
            "dk_bet_link": dk_link,
            "line_book": None if dk is not None else d.book,
            "scored_line": d.line,
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
            "confidence_tier": "MED",
            "decision_book": d.book, "decision_odds": price,
            "decision_implied_prob": round(imp, 4), "decision_edge": edge,
            "best_book": d.book, "best_odds": price, "best_implied_prob": round(imp, 4),
            "best_edge": edge, "best_bet_link": link,
            "downgrade_reason": _pause_note(d.model_id),
        })
    return rows, refused


def _num(v, nd: int = 6):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), nd)


def decision_row(d: R.Decision, games: dict, bet_written: bool, refused: str | None) -> dict:
    g = games.get(d.game_id, {})
    T = d.extra.get("decision_at")
    fetch = d.extra.get("fetch_at")
    tip = g.get("tip")
    lead = (tip - pd.Timestamp(T)).total_seconds() / 60.0 if (tip is not None and T) else None
    detail = d.detail + (f"; refused {refused}" if refused else "")
    return {"game_id": d.game_id, "model_id": d.model_id, "decision_at": T, "fetch_at": fetch,
            "lead_min": _num(lead, 2), "status": d.status, "side": d.side, "book": d.book,
            "price": _num(d.price), "line": _num(d.line), "p_fair": _num(d.p_fair),
            "uplift": _num(d.uplift), "p_model": _num(d.p_model), "ev": _num(d.ev),
            "edge": _num(d.edge), "dk_price": _num(d.dk_price), "n_books": d.n_books,
            "n_bets": 1 if bet_written else 0, "detail": detail[:2000],
            "extra": json.dumps(d.extra, sort_keys=True, default=str) if d.extra else None}


def publish(conn, rows: list[dict], decisions: list[R.Decision], games: dict,
            refused: dict) -> tuple[int, int]:
    """Write each decided (game, model) once: its decision row and its pick
    (BET or NONE) in ONE transaction, under each model's lock, the ledger and
    the picks re-read inside it. A conflict with a BET that landed since the
    decision turns this one into a NONE row. -> (bets written, decisions)."""
    if not decisions:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    for m in sorted({d.model_id for d in decisions}):
        _lock_model(conn, m)
    ids = sorted({d.game_id for d in decisions})
    done = decided(conn, ids)
    standing = standing_full_game(conn, ids)
    by_key = {(r["game_id"], r["model_id"]): r for r in rows}
    n_bets = n_decided = 0
    for d in sorted(decisions, key=lambda x: (x.game_id, x.model_id)):
        if (d.game_id, d.model_id) in done:
            continue
        row = by_key.get((d.game_id, d.model_id))
        if row is not None and row["signal_type"] == "BET":
            mine = {"market": R.MARKET[d.model_id], "side": d.side, "line": d.line}
            held = next((s for s in standing if s["game_id"] == d.game_id
                         and R.cannot_both_win(mine, s)), None)
            if held is not None:
                why = f"cannot both win with {held['label']}, already bet"
                refused[(d.game_id, d.model_id)] = why
                row = {**row, "signal_type": "NONE", "kelly_fraction": 0.0, "recommended_bet": 0.0}
        bet = row is not None and row["signal_type"] == "BET"
        got = conn.execute(_INSERT_DECISION, decision_row(
            d, games, bet, refused.get((d.game_id, d.model_id)))).fetchone()
        if not got:
            continue
        n_decided += 1
        if row is not None and conn.execute(_INSERT, {c: row.get(c) for c in _COLS}).fetchone():
            n_bets += bet
            if bet:
                standing.append({"game_id": d.game_id, "model_id": d.model_id,
                                 "market": R.MARKET[d.model_id], "side": d.side, "line": d.line,
                                 "label": row["pick_label"]})
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A (game, model) the card could not decide on its decision fetch:
    raised after every other write."""


_ART: dict = {}


def artifacts(seasons) -> dict:
    out = {}
    for s in sorted(set(seasons)):
        if s not in _ART:
            try:
                _ART[s] = R.load_artifact(s)
            except (FileNotFoundError, ValueError) as exc:
                logger.error(f"EuroLeague pre-game card: {exc}")
                _ART[s] = None
        if _ART[s] is not None:
            out[s] = _ART[s]
    return out


def render(decisions: list[R.Decision], counts: dict, written=None, decided_n=None) -> str:
    head = "EuroLeague pre-game card: " + " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    if decided_n is not None:
        head += f" decisions_written={decided_n}"
    if written is not None:
        head += f" bets_written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: (x.game_id, x.model_id)):
        p = "" if d.p_model is None else f" p {d.p_model:.4f} ev {d.ev:+.4f}"
        lines.append(f"  {d.game_id:26s} {d.model_id:31s} {d.status}: {d.detail}{p}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("EuroLeague pre-game card: RUN_EUROLEAGUE_PREGAME is off; nothing read")
        return {"games": 0, "bets": 0, "decided": 0, "off": True}
    on = models_on()
    conn = get_connection()
    try:
        games = slate(conn, now)
        if not games or not on:
            return {"games": len(games), "bets": 0, "decided": 0}
        first_run = not ledger_exists(conn)
        if do_publish:
            ensure_decisions_table(conn)
        done = decided(conn, sorted(games))
        todo = {g: tuple(m for m in on if (g, m) not in done) for g in games}
        fetched = feed.decision_fetches(conn, sorted(games), now)
        due, missed, waiting = due_games(games, fetched, now, todo)
        decisions: list[R.Decision] = []
        problems: list[str] = []
        for gid, why in sorted(missed.items()):
            for m in todo[gid]:
                decisions.append(R.Decision(gid, m, "missed", why))
            if not first_run:
                problems.append(f"{gid} ({', '.join(todo[gid])}) {why}")
        if due:
            ids = sorted(due)
            fg = odds_rows(conn, ids, R.FULL_GAME_MARKETS)
            per = odds_rows(conn, ids, R.PERIOD_MAIN_MARKETS + (R.LADDER_MARKET,), source=feed.SOURCE)
            hist = share_history(conn) if any(R.Q1_SHARE_TOTAL in todo[g] for g in ids) else None
            arts = artifacts(games[g]["season"] for g in ids)
            got = decide(games, due, todo, fg, per, hist, arts, deciding_books())
            for d in got:
                d.extra.setdefault("fetch_at", None if due[d.game_id][1] is None
                                   else pd.Timestamp(due[d.game_id][1]).isoformat())
                if d.status in ("missed", "no_artifact"):
                    problems.append(f"{d.game_id} {d.model_id}: {d.status} ({d.detail})")
            # one game never carries two bets that cannot both win
            R.resolve_conflicts(got, standing_full_game(conn, ids))
            decisions += got
        counts: dict = {"games": len(games), "waiting": len(waiting)}
        for d in decisions:
            counts[d.status] = counts.get(d.status, 0) + 1
        written = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            ids = sorted({d.game_id for d in decisions})
            links = odds_rows(conn, ids, R.FULL_GAME_MARKETS + R.PERIOD_MAIN_MARKETS)
            rows, refused = pick_rows(decisions, games, _get_current_bankroll(conn), links)
            written, n_decided = publish(conn, rows, decisions, games, refused)
        logger.info("\n" + render(decisions, counts, written if do_publish else None,
                                  n_decided if do_publish else None))
        if problems:
            raise CardIncomplete(f"{len(problems)} problem(s): " + "; ".join(problems)[:1500])
        return {"games": len(games), "bets": counts.get("bet", 0), "written": written,
                "decided": n_decided, "counts": counts}
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args(argv)
    try:
        print(run_card(do_publish=a.publish))
    except CardIncomplete as exc:
        # exit 1: the window job raises, so its heartbeat records "error" and
        # the failure alerter reports it.
        logger.error(f"EuroLeague pre-game card did not decide every game on its decision fetch: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). The card reads the
    # database only; installed so the scheduler runs no uninstrumented script.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("euroleague-pregame-card")
    except Exception:  # noqa: BLE001
        pass
    main()
