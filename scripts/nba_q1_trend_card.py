"""NBA first-quarter spread card: write `nba_q1_trend` bets (models/nba_q1_trend.py).

Runs in the NBA pre-game window job, right after this model's own first-quarter fetch (scheduler
.run_nba_total_luck_window; step nba-q1-trend). LIVE, with no default-off write switch, as the first-half card
(scripts/nba_first_half_total_luck_card.py), whose slate, decision timing and row shape it follows.

WHEN A GAME IS DECIDED. A run decides a game when its newest first-quarter fetch (the newest ok 'open' call in the
fetch ledger, data/ingestors/nba_first_quarter_odds.py) landed 45-66 minutes before tip and is at most 5 minutes old
(models.nba_team_total_luck.timing). A 200 with no first-quarter spread is still a fetch: the game is decided with
nothing offered. A failed call is not, and the next tick fetches again.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to nba_q1_trend_decisions in the same
transaction as the game's bet, under the model's advisory lock. A game with a decision row, or with any nba_q1_trend
BET, is never looked at again. The decision row carries the game's number, both teams' venue records, the check and
the best hot-side offer, so the live record can be read against the graded one.

WHAT IS READ. Today: this feed's pre-game ('open') first-quarter spreads at the deciding books and Pinnacle, from
fetches up to 70 minutes before the decision fetch, main numbers only. Earlier games (this season and the last, the
regular season): every first-quarter spread stored for them, the purchase's (odds_api_nba_derivative_history) and
this feed's, each game's number taken from its own decision fetch (models.nba_q1_trend.history_numbers); and their
first-quarter scores from nba_period_scores through the first search's check (scripts.nba_game_harness
.with_periods).

ROW SHAPE: the first-half card's. pick_side is the hot team's side ('home' or 'away'); scored_line is the HOME number
at the book taken (CLAUDE.md section 4); dk_odds / dk_implied_prob / edge are DraftKings' own price on that side at
this number in this fetch, else NULL / 0.0 / 0.0 with line_book naming the book taken. The label is the platform's
("DEN @ LAC — First Quarter DEN +1.5", models.scorer._build_pick_label), checked against side, line and market
before it is written (tracking/pick_integrity.pick_problems). The price floor (config.min_odds_for) and the model's
own EV floor (models.honest_ev.gate, a push scored as a loss) are applied here.

    python -m scripts.nba_q1_trend_card              # print the card, write nothing
    python -m scripts.nba_q1_trend_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.ingestors.nba_first_quarter_odds as feed  # noqa: E402
import models.nba_q1_trend as q1  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = q1.MODEL_ID
SPORT = q1.SPORT

# ── the decisions ledger (worker-only: data/anon_readable.WORKER_ONLY_TABLES) ──────
DECISIONS_TABLE = "nba_q1_trend_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "lead_min", "n_bets", "detail", "number", "pick", "k",
                  "h5", "a5", "h10", "a10", "check_passed", "book", "line", "price", "p_fair", "p_model",
                  "fair_ref", "fair_mu", "book_ages")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_q1_trend_decisions (
    game_id      TEXT PRIMARY KEY,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at     TEXT NOT NULL,
    lead_min     REAL,
    n_bets       INTEGER NOT NULL,
    detail       TEXT,
    number       REAL,
    pick         TEXT,
    k            REAL,
    h5           REAL,
    a5           REAL,
    h10          REAL,
    a10          REAL,
    check_passed BOOLEAN,
    book         TEXT,
    line         REAL,
    price        REAL,
    p_fair       REAL,
    p_model      REAL,
    fair_ref     TEXT,
    fair_mu      REAL,
    book_ages    TEXT
)
"""
_DECISION_VALUES = DECISIONS_COLS[:1] + DECISIONS_COLS[2:]
_INSERT_DECISION = (
    f"INSERT INTO nba_q1_trend_decisions ({', '.join(_DECISION_VALUES)}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in _DECISION_VALUES)}) "
    f"ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

READ_BOOKS = tuple(dict.fromkeys((*q1.config.BEST_LINE_BOOKMAKERS, "pinnacle")))
READ_BACK = timedelta(minutes=70)
HISTORY_SOURCES = (q1.HISTORY_SOURCE, q1.LIVE_SOURCE)


def slate(conn, now: datetime, skipped: list | None = None) -> dict[str, dict]:
    return tlcard.slate(conn, now, skipped, horizon_min=q1.DECISION_LEAD_MIN[1] + 5)


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
        (DECISIONS_TABLE,)).fetchone())


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games with a decision row, or with any nba_q1_trend BET whatever became of it: none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)", (list(game_ids),)).fetchall()}
    return done | games_with_a_bet(conn, game_ids)


def newest_fetch(conn, games: dict[str, dict], now: datetime) -> dict[str, datetime]:
    got = feed.fetches(conn, sorted(games), "open", now)
    return {gid: t for gid, t in got.items() if pd.Timestamp(t) < pd.Timestamp(games[gid]["tip"])}


def _quote_rows(conn, game_ids: list[str], sources, since: datetime | None = None,
                markets=(q1.MARKET,)) -> pd.DataFrame:
    """Stored pre-game first-quarter rows of these games. `markets`: this model's spread unless given; the
    moneyline card (scripts/nba_q1_trend_ml_card.py) reads the spread and the moneyline."""
    cols = list(q1.QUOTE_ROW_COLS)
    bound, params = "", [list(game_ids), list(markets), list(READ_BOOKS), list(sources)]
    if since is not None:
        bound = "AND created_at::timestamptz >= %s"
        params.append(since.astimezone(timezone.utc).isoformat())
    rows = conn.execute(f"""
        SELECT {', '.join(cols)} FROM odds
        WHERE game_id = ANY(%s) AND market = ANY(%s) AND snapshot_type = 'open'
          AND bookmaker = ANY(%s) AND source = ANY(%s) {bound}
    """, tuple(params)).fetchall()
    return pd.DataFrame(rows, columns=cols)


def history(conn, season: int, before: str) -> pd.DataFrame:
    """The earlier games' team rows the rule reads (scripts.nba_game8_q1_trends.team_games): this season's and the
    last season's regular-season games dated before `before` with a final, each with its own first-quarter number
    and its trusted first-quarter scores."""
    from scripts import nba_game8_q1_trends as G8
    from scripts import nba_game_harness as H
    import models.nba_total_luck as tl
    seasons = [int(season) - 1, int(season)]
    g = pd.DataFrame(conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.commence_time, g.home_team, g.away_team,
               g.home_score, g.away_score, s.game_type
        FROM games g LEFT JOIN nba_schedule s ON s.game_id = g.game_id
        WHERE g.sport = 'NBA' AND g.season = ANY(%s) AND g.game_date < %s AND g.home_score IS NOT NULL
    """, (seasons, before)).fetchall(), columns=["game_id", "season", "game_date", "commence_time", "home_team",
                                                 "away_team", "home_score", "away_score", "game_type"])
    if g.empty:
        return pd.DataFrame(columns=["game_id", "season", "game_date", "tip", "team", "venue", "ats", "ou", "pf",
                                     "pa"])
    g = g.drop_duplicates("game_id")
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["season"] = g["season"].astype(int)
    keep = set(tl.regular_season(g[["game_id", "season", "game_date", "game_type"]],
                                 tlcard.schedule_days(conn, seasons))["game_id"])
    g = g[g["game_id"].isin(keep)].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True, format="mixed")
    per = pd.DataFrame(conn.execute(
        "SELECT game_id, period, home_points, away_points FROM nba_period_scores WHERE game_id = ANY(%s)",
        (list(g["game_id"]),)).fetchall(), columns=["game_id", "period", "home_points", "away_points"])
    gp = H.with_periods(g[["game_id", "season", "game_date", "tip", "home_team", "away_team", "home_score",
                           "away_score"]], periods=per)
    rows = _quote_rows(conn, list(g["game_id"]), HISTORY_SOURCES)
    quotes = q1.quote_frame(rows, g[["game_id", "season", "game_date", "tip"]])
    return G8.team_games(gp, q1.history_numbers(quotes))


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: q1.Q1Bet, home: str, away: str) -> str:
    from models.scorer import _build_pick_label
    return _build_pick_label(bet.side, home, away, q1.MARKET, float(bet.line))


def pick_rows(bets: list[q1.Q1Bet], games: dict[str, dict], bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Card bets -> picks rows, and {game_id: why} for a bet refused here. Pure given its inputs."""
    from models.honest_ev import gate
    from models.scorer import _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    rows, refused = [], {}
    for b in bets:
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if b.price < (q1.config.min_odds_for(MODEL_ID) or -1e9):
            refused[b.game_id] = f"below_price_floor:{b.price:+.0f}"
            continue
        ev = gate(MODEL_ID, b.p_model, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} {b.side} @{b.book}")
            refused[b.game_id] = ev.reason
            continue
        line = float(b.line)
        label = pick_label(b, home, away)
        problems = pick_problems(label, b.side, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            refused[b.game_id] = "label_mismatch"
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.p_model - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == q1.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.p_model, dec_implied, bankroll)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g["tip"].isoformat() if g.get("tip") is not None else None,
            "pick_side": b.side, "pick_label": label,
            # The market-fair P(the hot side wins) at this line and price, plus the cell's walk-forward uplift
            # (models/nba_q1_trend.py, THE PROBABILITY). The model decides on it (config.MODELS_ON_OWN_PROBABILITY).
            "model_probability": round(b.p_model, 4),
            "model_probability_cal": round(b.p_model, 4),
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.p_model - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": line,
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4),
            "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
            "downgrade_reason": pause,
        })
    return rows, refused


_COLS = tlcard._COLS
_INSERT = tlcard._INSERT


def _num(x, nd):
    return None if x is None else round(float(x), nd)


def publish(conn, rows: list[dict], decisions: list[q1.Q1Decision], leads: dict[str, float],
            refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its bet in ONE transaction, under the model's lock, the
    ledger and the picks re-read inside it. -> (bets written, decisions written)."""
    if not decisions:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    done = decided_games(conn, sorted({d.game_id for d in decisions}))
    by_game = {r["game_id"]: r for r in rows}
    n_bets = n_decided = 0
    for d in sorted(decisions, key=lambda x: x.game_id):
        if d.game_id in done:
            continue
        row = by_game.get(d.game_id)
        detail = d.detail if d.game_id not in refused else f"{d.detail}; refused {refused[d.game_id]}"
        got = conn.execute(_INSERT_DECISION, {
            "game_id": d.game_id, "fetch_at": pd.Timestamp(d.fetch_at).isoformat(),
            "lead_min": round(leads.get(d.game_id, float("nan")), 2),
            "n_bets": 1 if row is not None else 0, "detail": detail,
            "number": d.number, "pick": d.pick, "k": d.k, "h5": d.h5, "a5": d.a5, "h10": d.h10, "a10": d.a10,
            "check_passed": d.check, "book": d.book, "line": d.line, "price": d.price,
            "p_fair": _num(d.p_fair, 4), "p_model": _num(d.p_model, 4), "fair_ref": d.fair_ref,
            "fair_mu": _num(d.fair_mu, 2),
            "book_ages": json.dumps(d.book_ages, sort_keys=True) if d.book_ages else None,
        }).fetchone()
        if not got:
            continue
        n_decided += 1
        if row is not None and conn.execute(_INSERT, {c: row.get(c) for c in _COLS}).fetchone():
            n_bets += 1
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = q1.load_artifact()
    return _ART["a"]


def render(bets, diag: dict, written: int | None = None, decisions_written: int | None = None) -> str:
    head = f"NBA first-quarter card ({MODEL_ID}): " + " ".join(f"{k}={v}" for k, v in diag.items())
    if decisions_written is not None:
        head += f" decisions_written={decisions_written}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in bets:
        lines.append(f"  {b.game_id:26s} {b.side} {b.line:+g} @{b.book} {b.price:+.0f}  k {b.k:+.0f}  number "
                     f"{b.number:+g}  fair {b.p_fair:.4f} ({b.uplift:+.4f}) -> {b.p_model:.4f}  fair centre "
                     f"{b.fair_mu:+.2f} ({b.fair_ref}), fetch {pd.Timestamp(b.fetch_at).isoformat()}")
    return "\n".join(lines)


TIMING_KEYS = ("too_early", "stale_fetch", "too_late", "no_fetch", "already_decided")


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        skipped: list[str] = []
        games = slate(conn, now, skipped)
        if skipped:
            logger.info(f"nba-q1-trend: not a regular-season game, not priced: {skipped}")
        timing = dict.fromkeys(TIMING_KEYS, 0)
        if not games:
            logger.info(f"NBA first-quarter card ({MODEL_ID}): no NBA game tips in the next "
                        f"{q1.DECISION_LEAD_MIN[1] + 5:.0f} minutes")
            return {"games": 0, "bets": 0, "published": 0, "decided": 0, "timing": timing}
        if do_publish:
            ensure_decisions_table(conn)
        fetched = newest_fetch(conn, games, now)
        done = decided_games(conn, sorted(games))
        due: dict[str, datetime] = {}
        for gid, g in sorted(games.items()):
            if gid in done:
                timing["already_decided"] += 1
                continue
            t = fetched.get(gid)
            if t is None:
                timing["no_fetch"] += 1
                continue
            why = q1.timing(g["tip"], t, now)
            if why == "decide":
                due[gid] = t
                continue
            timing[why] += 1
            if why == "too_late":
                logger.warning(f"nba-q1-trend: {gid} tips {g['tip'].isoformat()} and was never decided: no "
                               f"first-quarter fetch landed {q1.DECISION_LEAD_MIN[0]:.0f}-"
                               f"{q1.DECISION_LEAD_MIN[1]:.0f} minutes before tip")
        if not due:
            logger.info(f"NBA first-quarter card ({MODEL_ID}): nothing to decide this run; {timing}")
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "timing": timing}

        by_season: dict[int, list[str]] = {}
        for gid in due:
            if games[gid].get("season") is not None:
                by_season.setdefault(int(games[gid]["season"]), []).append(gid)
        art = artifact()
        bets_all, decisions_all, diag_all = [], [], dict.fromkeys(q1.DIAG_KEYS, 0)
        leads = {gid: q1.lead_minutes(games[gid]["tip"], t) for gid, t in due.items()}
        stale: dict[int, list[str]] = {}
        for season, gids in sorted(by_season.items()):
            if q1.newest_season(art) != season - 1:
                logger.error(f"nba-q1-trend: the artifact ends with {q1.newest_season(art)}; season {season} "
                             f"needs one refitted through {season - 1} (scripts/nba_q1_trend_build.py). "
                             f"Nothing decided.")
                stale[season] = gids
                continue
            tg = pd.DataFrame([{"game_id": g, "season": season, "game_date": games[g]["game_date"],
                                "home_team": games[g]["home"], "away_team": games[g]["away"],
                                "tip": pd.Timestamp(games[g]["tip"])} for g in gids])
            hist = history(conn, season, min(tg["game_date"]))
            since = min(due[g] for g in gids) - READ_BACK
            quotes = q1.quote_frame(_quote_rows(conn, gids, (q1.LIVE_SOURCE,), since), tg)
            times = pd.DataFrame({"game_id": gids, "T": [pd.Timestamp(due[g]) for g in gids]})
            bets, decisions, diag = q1.decide(tg.drop(columns="tip"), quotes, hist, times, art)
            bets_all += bets
            decisions_all += decisions
            for k, v in diag.items():
                diag_all[k] += v
        published = n_decided = 0
        if do_publish and decisions_all:
            from models.scorer import _get_current_bankroll
            rows, refused = pick_rows(bets_all, games, _get_current_bankroll(conn))
            published, n_decided = publish(conn, rows, decisions_all, leads, refused)
        logger.info("\n" + render(bets_all, {**diag_all, **timing}, published if do_publish else None,
                                  n_decided if do_publish else None))
        if stale:
            raise RuntimeError(f"nba-q1-trend: the artifact ends with {q1.newest_season(art)}, so "
                               f"{sum(len(g) for g in stale.values())} due game(s) were not decided. Refit it "
                               f"(scripts/nba_q1_trend_build.py).")
        return {"games": len(games), "bets": len(bets_all), "published": published, "decided": n_decided,
                "timing": timing, "diag": diag_all}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
