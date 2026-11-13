"""NCAAB spread card: write `ncaab_spread_market` bets (models/ncaab_spread_market.py).

LIVE, real money (mike, 2026-11-02: "we need to build 1H and game lines ML and
Spread no matter what"). Runs in its own job, hourly at five past the hour UTC
(scheduler.run_ncaab_spread_card), and writes picks only; the job then
publishes them like every other card. RUN_NCAAB_SPREAD_CARD=0 stops it before
it reads anything; the job keeps beating, so its silence still means stopped.

WHEN A GAME IS DECIDED: at 15:00 UTC on its date, and only then. The evidence
priced the books' quotes at that instant and nothing else held up (22:00 UTC
the evening before failed; the hour before tip made +0.43%). The run whose
hour is 15:00 UTC reads every bettable book's quote as of 15:00 UTC (its
newest pre-game row stamped 14:00-15:00 UTC, models/ncaab_book_quotes.py) and
decides each of the day's games that tips after 15:00 UTC, bet or not. A run
later in the 15:00 hour (the scheduler's misfire grace) reads the same
as-of-15:00 quotes. A game that tips at or before 15:00 UTC is never bet.

A MISSED CHECK IS A FAILURE, NEVER A LATE BET. When a run after 15:59 UTC
finds one of the day's games with no decision (the 15:05 run was missed, died
or was switched off), it writes the game's decision as `missed` with no bet
and the run exits 1: the job's heartbeat records "error" and the failure
alerter reports it. A quote from a later hour is never bet, because nothing
measured supports it. The one exception is the card's first run ever (no
ledger table yet): games whose 15:00 UTC came before the card existed are
written as `missed` without failing.

A RUN THAT CANNOT DECIDE ITS GAMES FAILS, after writing every game it could:
an artifact for another season (the game is then `missed` next hour); every
due game with no quote at all (the odds steps have stopped); a best quote at a
book config.BEST_LINE_BOOKMAKERS no longer lists (except a state-limited one,
config.STATE_LIMITED_BOOKMAKERS: that game is an ordinary no-bet); a best edge above the
data-error cap (models/ncaab_quote_bounds.EDGE_CAP: the game is written as
edge_cap with no bet).

A FEED TYPO NEVER BECOMES A BET (models/ncaab_quote_bounds.py). A book's quote
whose spread is beyond +/-60 or whose price is beyond +/-100000 is dropped
before the consensus reads it, that book has no quote at 15:00 UTC, and the
game is decided on the other books. Each dropped quote is logged with its
game, book and value, counted as quotes_dropped on the diagnostic line, and
kept in the decision row's quotes as out_of_range.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
ncaab_spread_decisions in the same transaction as the game's bet, under the
model's transaction-scoped advisory lock. A game with a decision row, or with
any ncaab_spread_market BET, is never decided again: a moved line or a better
price writes nothing.

A game priced below the cut is a NONE row (no stake) in the same
transaction, so the app's All board shows every scored game (Matt,
2026-11-04); nothing publishes or settles a NONE row.
BET ROWS in picks, at the BET book's line and price: scored_line is that
book's home number, decision_* and best_* its price. When DraftKings quoted the
same line at 15:00 UTC, the line is DraftKings' too: line_book is NULL and
dk_odds / dk_implied_prob / edge are DraftKings' own price on that side, the
reference. Otherwise line_book names the bet book and dk_odds is NULL,
dk_implied_prob and edge 0.0, the scorer's convention for a pick scored off
another book's line. The label is the platform's ("Duke -13.5"), checked
against the side and line before it is written
(tracking/pick_integrity.pick_problems).

    python -m scripts.ncaab_spread_card              # print the card, write nothing
    python -m scripts.ncaab_spread_card --publish    # write new decisions and bets
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
from models import cbb_pairs  # noqa: E402
from models import ncaab_stake  # noqa: E402
import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_spread_market as sm  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = sm.MODEL_ID
SPORT = sm.SPORT
_ET = ZoneInfo("America/New_York")


def enabled() -> bool:
    """The kill switch: RUN_NCAAB_SPREAD_CARD=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_NCAAB_SPREAD_CARD", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it. `quotes`
# keeps every book's quote at 15:00 UTC, so how often the off-market number
# could actually be bet can be measured against the books' next rows.
DECISIONS_TABLE = "ncaab_spread_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "check_hour", "instant", "status", "book", "side",
                  "line", "price", "consensus", "n_books", "edge", "prob", "dk_line",
                  "dk_price", "n_bets", "quotes", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_spread_decisions (
    game_id      TEXT PRIMARY KEY,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_hour   TEXT NOT NULL,
    instant      TEXT,
    status       TEXT NOT NULL,
    book         TEXT,
    side         TEXT,
    line         REAL,
    price        REAL,
    consensus    REAL,
    n_books      INTEGER,
    edge         REAL,
    prob         REAL,
    dk_line      REAL,
    dk_price     REAL,
    n_bets       INTEGER NOT NULL,
    quotes       TEXT,
    detail       TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO ncaab_spread_decisions (game_id, check_hour, instant, status, book, side, line, "
    "price, consensus, n_books, edge, prob, dk_line, dk_price, n_bets, quotes, detail) VALUES "
    "(%(game_id)s, %(check_hour)s, %(instant)s, %(status)s, %(book)s, %(side)s, %(line)s, "
    "%(price)s, %(consensus)s, %(n_books)s, %(edge)s, %(prob)s, %(dk_line)s, %(dk_price)s, "
    "%(n_bets)s, %(quotes)s, %(detail)s) ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


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
    """Games with a decision row, or with any ncaab_spread_market BET whatever
    became of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            "SELECT game_id FROM ncaab_spread_decisions WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    bet = {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}
    return done | bet


# ── reads ─────────────────────────────────────────────────────────────────────

def _tip(text) -> datetime | None:
    try:
        t = pd.Timestamp(str(text))
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.to_pydatetime()


def slate(conn, now: datetime) -> dict[str, dict]:
    """NCAAB games dated yesterday or today (Eastern) that tip after their
    15:00 UTC: the games this run may decide or must report missed."""
    today = now.astimezone(_ET).date()
    dates = [(today - timedelta(days=d)).isoformat() for d in (1, 0)]
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAAB' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away in rows:
        tip = _tip(ct)
        if tip is None:
            continue
        instant = bq.check_instant(gd)
        if instant >= tip:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": tip,
                    "instant": instant, "commence_time": ct, "home": home, "away": away}
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


def _side(best: dict) -> str:
    return "home" if int(best["side"]) == 1 else "away"


def _link(q: dict | None, side: str):
    if not q:
        return None
    v = q.get("link1") if side == "home" else q.get("link2")
    return None if v is None or (isinstance(v, float) and v != v) else v


def _is_bet(row: dict | None) -> bool:
    return row is not None and row["signal_type"] == "BET"


# Priced, and its better side did not clear the cut: written as a NONE row.
SCORED_NO_BET = ("below_cut", "too_few_books")


def pick_rows(decisions: list[sm.Decision], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Decisions -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs.

    A bet is a BET row. A game priced below the cut (SCORED_NO_BET), or a bet
    the price or EV floor refused, is a NONE row at the same book, side and
    line with no stake (Matt, 2026-11-04: the All board shows every scored
    pick, not only the bets). Nothing publishes or settles a NONE row."""
    from models.honest_ev import gate
    from models.scorer import _build_pick_label, _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    rows, refused = [], {}
    for d in decisions:
        is_bet = d.status == "bets"
        if d.best is None or d.status not in ("bets",) + SCORED_NO_BET:
            continue
        b = d.best
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        side = _side(b)
        line, price, prob = float(b["line"]), float(b["price"]), float(b["prob"])
        if is_bet and floor is not None and price < floor:
            refused[d.game_id] = f"below_price_floor:{price:+.0f}"
            is_bet = False
        if is_bet:
            ev = gate(MODEL_ID, prob, price)
            if not ev.clears:
                logger.info(f"{MODEL_ID}: {ev.reason} - dropped {d.game_id} {side}")
                refused[d.game_id] = ev.reason or "below_ev_floor"
                is_bet = False
        label = _build_pick_label(side, home, away, sm.MARKET, line)
        problems = pick_problems(label, side, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {d.game_id} {label!r}: {'; '.join(problems)}")
            if d.game_id not in refused and is_bet:
                refused[d.game_id] = "label_mismatch"
            continue
        imp = implied(price)
        edge = round(prob - imp, 4)
        kelly_frac, rec_bet = quarter_kelly(prob, imp, bankroll) if is_bet else (0.0, 0.0)
        dk = d.dk
        same_line = bool(dk and dk.get("flag") == "ok" and abs(float(dk["line"]) - line) < 1e-9)
        if same_line:
            dk_price = float(dk["p1"] if side == "home" else dk["p2"])
            dk_imp = implied(dk_price)
            dk_cols = {"dk_odds": dk_price, "dk_implied_prob": round(dk_imp, 4),
                       "edge": round(prob - dk_imp, 4), "dk_bet_link": _link(dk, side),
                       "line_book": None}
        else:
            dk_cols = {"dk_odds": None, "dk_implied_prob": 0.0, "edge": 0.0,
                       "dk_bet_link": None, "line_book": b["bookmaker"]}
        rows.append({
            "game_id": d.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"), "game_time": g.get("commence_time"),
            "pick_side": side, "pick_label": label,
            # P(win | no push) at the bet book's line: the number the 0.03 cut
            # was measured on (models/ncaab_spread_market.py, THE PROBABILITY).
            "model_probability": round(prob, 4),
            "model_probability_cal": round(prob, 4),
            "scored_line": line,
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
            # MED on every bet, as the other rule cards write: the evidence
            # gives no tier.
            "confidence_tier": "MED",
            **dk_cols,
            "decision_book": b["bookmaker"], "decision_odds": price,
            "decision_implied_prob": round(imp, 4), "decision_edge": edge,
            # The bet IS the best quote: same line by construction, at a book
            # in config.BEST_LINE_BOOKMAKERS (decide() refuses any other).
            "best_book": b["bookmaker"], "best_odds": price, "best_implied_prob": round(imp, 4),
            "best_edge": edge, "best_bet_link": _link(b, side),
            "downgrade_reason": pause,
        })
    return rows, refused


def _num(v):
    return None if v is None or (isinstance(v, float) and v != v) else round(float(v), 4)


def decision_row(d: sm.Decision, check_hour: datetime, instant: datetime | None,
                 bet_written: bool, refused: str | None) -> dict:
    b = d.best or {}
    detail = d.status + ": " + d.detail + (f"; refused {refused}" if refused else "")
    return {"game_id": d.game_id, "check_hour": check_hour.isoformat(),
            "instant": instant.isoformat() if instant else None, "status": d.status,
            "book": b.get("bookmaker"), "side": _side(b) if b else None,
            "line": _num(b.get("line")), "price": _num(b.get("price")),
            "consensus": _num(b.get("cons")),
            "n_books": int(b["n_ok"]) if b.get("n_ok") is not None else None,
            "edge": _num(b.get("edge")), "prob": _num(b.get("prob")),
            "dk_line": _num((d.dk or {}).get("line")),
            "dk_price": (_num(d.dk["p1"] if _side(b) == "home" else d.dk["p2"])
                         if d.dk and b else None),
            "n_bets": 1 if bet_written else 0,
            "quotes": json.dumps(d.quotes) if d.quotes else None, "detail": detail[:2000]}


FINAL = ("bets", "below_cut", "too_few_books", "book_not_bettable", "edge_cap", "no_quotes",
         "no_clean_quote", "missed", "tipped")


def publish(conn, rows: list[dict], decisions: list[sm.Decision], check_hour: datetime,
            games: dict[str, dict], refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its pick (BET or
    NONE) in ONE
    transaction, under the model's lock, the ledger and the picks re-read
    inside it. -> (bets written, decisions written)."""
    final = [d for d in decisions if d.status in FINAL]
    if not final:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    done = decided_games(conn, sorted({d.game_id for d in final}))
    by_game = {r["game_id"]: r for r in rows}
    n_bets = n_decided = 0
    for d in sorted(final, key=lambda x: x.game_id):
        if d.game_id in done:
            continue
        row = by_game.get(d.game_id)
        g = games.get(d.game_id, {})
        got = conn.execute(_INSERT_DECISION, decision_row(
            d, check_hour, g.get("instant"), _is_bet(row), refused.get(d.game_id))).fetchone()
        if not got:
            continue
        n_decided += 1
        # A bet an earlier NCAAB bet on this game and side agrees with is
        # staked at NCAAB_AGREEMENT_STAKE_UNITS (models/ncaab_stake.py).
        if row is not None and conn.execute(_INSERT, ncaab_stake.stamp(conn, row, _COLS)).fetchone():
            n_bets += row["signal_type"] == "BET"
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A game the card could not decide at 15:00 UTC, or a run that found the
    odds missing: raised after the rest of the run is written."""


def log_dropped(drops) -> None:
    """One warning per quote dropped as a data error: game, book and value."""
    from models.ncaab_quote_bounds import describe
    for line in describe(drops):
        logger.warning(f"NCAAB spread card: dropped a data-error quote, {line}")


_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = sm.load_artifact()
    return _ART["a"]


def render(decisions: list[sm.Decision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAAB spread card ({MODEL_ID}): " + " ".join(f"{k}={diag.get(k, 0)}" for k in sm.DIAG_KEYS)
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: x.game_id):
        lines.append(f"  {d.game_id:44s} {d.status}: {d.detail}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("NCAAB spread card: RUN_NCAAB_SPREAD_CARD is off; nothing read")
        return {"games": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    hour = now.replace(minute=0, second=0, microsecond=0)
    diag = dict.fromkeys(sm.DIAG_KEYS, 0)
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
        decisions: list[sm.Decision] = []
        problems: list[str] = []          # each fails the run, after the writes
        for gid, v in sorted(overdue.items()):
            why = ("the card had not run yet" if first_run else
                   f"no run decided it in the 15:00 UTC hour (this run {now:%H:%M}Z)")
            decisions.append(sm.Decision(gid, "missed", why))
        if overdue and not first_run:
            problems.append(f"{len(overdue)} game(s) missed their 15:00 UTC decision: "
                            + ", ".join(sorted(overdue)[:20]))
        tipped = {g: v for g, v in due.items() if v["tip"] <= now}
        for gid in sorted(tipped):
            decisions.append(sm.Decision(gid, "tipped", "tipped before this run"))
        due = {g: v for g, v in due.items() if g not in tipped}
        if due:
            art = artifact()
            for season in sorted({v["season"] for v in due.values()}):
                gids = sorted(g for g, v in due.items() if v["season"] == season)
                if int(art["season"]) != season:
                    msg = (f"the artifact is for season {art['season']}; season {season} needs one "
                           f"built through {season - 1} (scripts/ncaab_spread_market_build.py). "
                           f"{len(gids)} game(s) not decided")
                    logger.error(f"NCAAB spread card: {msg}.")
                    problems.append(msg)
                    continue
                part = {g: due[g] for g in gids}
                rows = bq.load_rows(conn, part, hour)
                drops = bq.dropped_quotes(rows)
                log_dropped(drops)
                diag["quotes_dropped"] += len(drops)
                snap = sm.snapshot_for(rows, {g: v["game_date"] for g, v in part.items()})
                got = sm.decide(gids, snap, art["c_by_phase"], art["table"],
                                config.MODEL_EDGE_THRESHOLDS[MODEL_ID],
                                min_other_books=int(art["min_other_books"]),
                                bettable=tuple(config.BEST_LINE_BOOKMAKERS), dropped=drops)
                if got and all(d.status == "no_quotes" for d in got):
                    problems.append(f"no bettable book has a spread stamped 14:00-15:00 UTC for any of "
                                    f"the {len(got)} due game(s): the odds refresh and the capture "
                                    f"may have stopped")
                for d in got:
                    if d.status == "book_not_bettable":
                        book = str((d.best or {}).get("bookmaker") or "").lower()
                        if book in config.STATE_LIMITED_BOOKMAKERS:
                            # Expected, not broken: the consensus reads this book and a
                            # pick may never name it (mike, 2026-11-06). The game is a
                            # no-bet, as on the stored seasons' re-grade (docs/sports/ncaab.md).
                            logger.info(f"NCAAB spread card: {d.game_id} not bet, its best "
                                        f"quote is at {book}, which a pick never names")
                        else:
                            problems.append(f"book_not_bettable {d.game_id} ({d.detail})")
                    elif d.status == "edge_cap":
                        logger.error(f"NCAAB spread card: {d.game_id} not bet, its edge is a data "
                                     f"error: {d.detail}")
                        problems.append(f"edge_cap {d.game_id} ({d.detail})")
                decisions += got
        for d in decisions:
            diag[d.status] = diag.get(d.status, 0) + 1
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            prows, refused = pick_rows(decisions, games, _get_current_bankroll(conn))
            # An under beside a big favourite's spread bet on the same game is not bet
            # (models/cbb_pairs.py; mike, 2026-11-11): the later of the two becomes a NONE row.
            cbb_pairs.hold_back(conn, prows, refused)
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
        # exit 1: scheduler.run_ncaab_spread_card then raises, so the job's
        # heartbeat records "error" and the failure alerter reports it.
        logger.error(f"NCAAB spread card did not decide every game at 15:00 UTC: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). The card reads the
    # database only; installed so the scheduler runs no uninstrumented script.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-spread-card")
    except Exception:  # noqa: BLE001
        pass
    main()
