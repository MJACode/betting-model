"""NBA first-quarter moneyline card: write `nba_q1_trend_ml` bets (models/nba_q1_trend_ml.py).

Runs in the NBA pre-game window job right after the first-quarter spread card, on the SAME fetch (scheduler
.run_nba_total_luck_window; step nba-q1-trend-ml after nba-q1-trend). LIVE, with no default-off write switch, on mike's
instruction (2026-11-07, "Build it anyway"). Its slate, decision timing, history read and row shape are the spread
card's (scripts/nba_q1_trend_card.py), imported; its ledger and its picks are its own.

WHEN A GAME IS DECIDED. Exactly when the spread card decides it: the newest ok 'open' first-quarter fetch (one call
holds both markets, data/ingestors/nba_first_quarter_odds.py) landed 45-66 minutes before tip and is at most 5 minutes
old (models.nba_team_total_luck.timing).

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to nba_q1_trend_ml_decisions in the same
transaction as the game's bet, under this model's advisory lock. A game with a decision row, or with any
nba_q1_trend_ml BET, is never looked at again. The spread model's decision does not decide this model's: each model
reads its own ledger.

WHAT IS READ. Today: this feed's pre-game ('open') first-quarter spreads AND moneylines at the deciding books and
Pinnacle, from fetches up to 70 minutes before the decision fetch, main numbers only. Earlier games: the spread card's
history read exactly (scripts.nba_q1_trend_card.history), since the rule is the spread model's.

ROW SHAPE: the spread card's. pick_side is the hot team's side; scored_line is NULL (a moneyline has no number);
dk_odds / dk_implied_prob / edge are DraftKings' own first-quarter moneyline on that side in this fetch, else NULL /
0.0 / 0.0 with line_book naming the book taken. The label is the platform's ("DEN @ LAC — First Quarter DEN ML",
models.scorer._build_pick_label), checked before it is written (tracking/pick_integrity.pick_problems). The price
floor (config.min_odds_for) and the model's own EV floor (models.honest_ev.gate) are applied here.

    python -m scripts.nba_q1_trend_ml_card              # print the card, write nothing
    python -m scripts.nba_q1_trend_ml_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_q1_trend_ml as ml  # noqa: E402
import scripts.nba_q1_trend_card as q1card  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = ml.MODEL_ID
SPORT = ml.SPORT

# ── the decisions ledger (worker-only: data/anon_readable.WORKER_ONLY_TABLES) ──────
# The spread card's columns: line and fair_mu stay NULL on a moneyline.
DECISIONS_TABLE = "nba_q1_trend_ml_decisions"
DECISIONS_COLS = q1card.DECISIONS_COLS
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_q1_trend_ml_decisions (
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
    f"INSERT INTO {DECISIONS_TABLE} ({', '.join(_DECISION_VALUES)}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in _DECISION_VALUES)}) "
    f"ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

slate = q1card.slate
newest_fetch = q1card.newest_fetch
history = q1card.history
READ_BACK = q1card.READ_BACK
TIMING_KEYS = q1card.TIMING_KEYS


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
    """Games with a decision row, or with any nba_q1_trend_ml BET whatever became of it: none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)", (list(game_ids),)).fetchall()}
    return done | games_with_a_bet(conn, game_ids)


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: ml.Q1MLBet, home: str, away: str) -> str:
    from models.scorer import _build_pick_label
    return _build_pick_label(bet.side, home, away, ml.MARKET, None)


def pick_rows(bets: list[ml.Q1MLBet], games: dict[str, dict], bankroll: float
              ) -> tuple[list[dict], dict[str, str]]:
    """Card bets -> picks rows, and {game_id: why} for a bet refused here. Pure given its inputs."""
    from models.honest_ev import gate
    from models.scorer import _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    rows, refused = [], {}
    for b in bets:
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if b.price < (ml.config.min_odds_for(MODEL_ID) or -1e9):
            refused[b.game_id] = f"below_price_floor:{b.price:+.0f}"
            continue
        ev = gate(MODEL_ID, b.p_model, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} {b.side} @{b.book}")
            refused[b.game_id] = ev.reason
            continue
        label = pick_label(b, home, away)
        problems = pick_problems(label, b.side, None, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            refused[b.game_id] = "label_mismatch"
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.p_model - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == ml.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.p_model, dec_implied, bankroll)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g["tip"].isoformat() if g.get("tip") is not None else None,
            "pick_side": b.side, "pick_label": label,
            # The market-fair P(the hot side wins | not level) at this price, plus the cell's walk-forward uplift
            # (models/nba_q1_trend_ml.py, THE PROBABILITY). The model decides on it (config.MODELS_ON_OWN_PROBABILITY).
            "model_probability": round(b.p_model, 4),
            "model_probability_cal": round(b.p_model, 4),
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.p_model - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": None,
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


_COLS = q1card._COLS
_INSERT = q1card._INSERT
_num = q1card._num


def publish(conn, rows: list[dict], decisions: list[ml.Q1Decision], leads: dict[str, float],
            refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its bet in ONE transaction, under this model's lock, the
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
            "check_passed": d.check, "book": d.book, "line": None, "price": d.price,
            "p_fair": _num(d.p_fair, 4), "p_model": _num(d.p_model, 4), "fair_ref": d.fair_ref,
            "fair_mu": None,
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
        _ART["a"] = ml.load_artifact()
    return _ART["a"]


def render(bets, diag: dict, written: int | None = None, decisions_written: int | None = None) -> str:
    head = f"NBA first-quarter moneyline card ({MODEL_ID}): " + " ".join(f"{k}={v}" for k, v in diag.items())
    if decisions_written is not None:
        head += f" decisions_written={decisions_written}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in bets:
        lines.append(f"  {b.game_id:26s} {b.side} ML @{b.book} {b.price:+.0f}  k {b.k:+.0f}  number {b.number:+g}  "
                     f"fair {b.p_fair:.4f} ({b.uplift:+.4f}) -> {b.p_model:.4f} ({b.fair_ref}), "
                     f"fetch {pd.Timestamp(b.fetch_at).isoformat()}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        skipped: list[str] = []
        games = slate(conn, now, skipped)
        if skipped:
            logger.info(f"nba-q1-trend-ml: not a regular-season game, not priced: {skipped}")
        timing = dict.fromkeys(TIMING_KEYS, 0)
        if not games:
            logger.info(f"NBA first-quarter moneyline card ({MODEL_ID}): no NBA game tips in the next "
                        f"{ml.DECISION_LEAD_MIN[1] + 5:.0f} minutes")
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
            why = ml.timing(g["tip"], t, now)
            if why == "decide":
                due[gid] = t
                continue
            timing[why] += 1
            if why == "too_late":
                logger.warning(f"nba-q1-trend-ml: {gid} tips {g['tip'].isoformat()} and was never decided: no "
                               f"first-quarter fetch landed {ml.DECISION_LEAD_MIN[0]:.0f}-"
                               f"{ml.DECISION_LEAD_MIN[1]:.0f} minutes before tip")
        if not due:
            logger.info(f"NBA first-quarter moneyline card ({MODEL_ID}): nothing to decide this run; {timing}")
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "timing": timing}

        by_season: dict[int, list[str]] = {}
        for gid in due:
            if games[gid].get("season") is not None:
                by_season.setdefault(int(games[gid]["season"]), []).append(gid)
        art = artifact()
        bets_all, decisions_all, diag_all = [], [], dict.fromkeys(ml.DIAG_KEYS, 0)
        leads = {gid: ml.lead_minutes(games[gid]["tip"], t) for gid, t in due.items()}
        stale: dict[int, list[str]] = {}
        for season, gids in sorted(by_season.items()):
            if ml.newest_season(art) != season - 1:
                logger.error(f"nba-q1-trend-ml: the artifact ends with {ml.newest_season(art)}; season {season} "
                             f"needs one refitted through {season - 1} (scripts/nba_q1_trend_ml_build.py). "
                             f"Nothing decided.")
                stale[season] = gids
                continue
            tg = pd.DataFrame([{"game_id": g, "season": season, "game_date": games[g]["game_date"],
                                "home_team": games[g]["home"], "away_team": games[g]["away"],
                                "tip": pd.Timestamp(games[g]["tip"])} for g in gids])
            hist = history(conn, season, min(tg["game_date"]))
            since = min(due[g] for g in gids) - READ_BACK
            rows = q1card._quote_rows(conn, gids, (ml.LIVE_SOURCE,), since, markets=ml.MARKETS)
            quotes = ml.quote_frame(rows, tg)
            times = pd.DataFrame({"game_id": gids, "T": [pd.Timestamp(due[g]) for g in gids]})
            bets, decisions, diag = ml.decide(tg.drop(columns="tip"), quotes, hist, times, art)
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
            raise RuntimeError(f"nba-q1-trend-ml: the artifact ends with {ml.newest_season(art)}, so "
                               f"{sum(len(g) for g in stale.values())} due game(s) were not decided. Refit it "
                               f"(scripts/nba_q1_trend_ml_build.py).")
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
