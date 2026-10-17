"""NBA totals card: write `nba_total_luck` bets (models/nba_total_luck.py).

Runs on every refresh pass right after the odds fetch (step nba-total-luck in
scripts/refresh_pass.sh, under a time limit), so the fetch it reads is the one
the pass just stored. LIVE, with no default-off write switch: the MLB cards'
switches flipped off on a redeploy and those models went dark without a trace
(config.py, MLB_*_PUBLISH).

WHEN A GAME IS DECIDED. Decision point C is "the newest fetch 60-180 minutes
before tip". A pass decides a game only when its newest odds fetch is 60-180
minutes out AND no later scheduled refresh pass can still fetch it 60 or more
minutes out (models.nba_total_luck.timing / is_last_look). Every earlier pass
in the window defers; every pass after it is too late.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
nba_total_luck_decisions in the same transaction as the game's bet, under the
model's transaction-scoped advisory lock (the refresh pass and a boot catch-up
pass can overlap). A game with a decision row, or with any nba_total_luck BET,
is never looked at again: a later pass, a moved line or a better price writes
nothing.

BET ROWS ONLY in picks. The scorer deletes every model's unsettled non-BET
rows on each pass, so a "declined" row would not survive there. A decision
with no bet lives in the ledger with its reason; the per-pass diagnostic line
in the worker log is how an empty card is told apart from a broken one.

ROW SHAPE: the NHL totals card's (scripts/nhl_totals_card.py). dk_odds /
dk_implied_prob / edge are DraftKings' own over at this number in this fetch,
else NULL / 0.0 / 0.0; decision_* is the book taken, always set; line_book
names that book only when DraftKings did not hang the number; best_* is set
only when the bet is not at DraftKings. The label is the platform's
("BOS vs NYK Over 225.5"), checked against the side and line before it is
written (tracking/pick_integrity.pick_problems).

    python -m scripts.nba_total_luck_card              # print the card, write nothing
    python -m scripts.nba_total_luck_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_total_luck as tl  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = tl.MODEL_ID
SPORT = tl.SPORT

# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "nba_total_luck_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "lead_min", "gap_total", "n_bets",
                  "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_total_luck_decisions (
    game_id     TEXT PRIMARY KEY,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at    TEXT NOT NULL,
    lead_min    REAL,
    gap_total   REAL,
    n_bets      INTEGER NOT NULL,
    detail      TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO nba_total_luck_decisions (game_id, fetch_at, lead_min, gap_total, n_bets, detail) "
    "VALUES (%(game_id)s, %(fetch_at)s, %(lead_min)s, %(gap_total)s, %(n_bets)s, %(detail)s) "
    "ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that
    (data/ddl_guard.schema_is_current: a CREATE ... IF NOT EXISTS still fires
    Supabase's pgrst_ddl_watch). Committed on its own, before the model's
    lock is taken."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

def slate(conn, now: datetime, skipped: list | None = None) -> dict[str, dict]:
    """Regular-season NBA games that have not tipped and tip within the far end
    of the decision window. The NBA prop card's slate: the tip is the earlier of
    nba_schedule's and games' start, and a game the schedule does not list as
    'regular' (the NBA Cup final, play-in, playoffs) is skipped and named."""
    from scripts.nba_prop_market_card import slate as nba_slate
    return nba_slate(conn, now, skipped, horizon_min=int(tl.DECISION_LEAD_MIN[1]) + 5)


# The books the rule reads: the deciding books and Pinnacle, whose no-vig line
# is the market's fair line. No other book can change a decision
# (scripts.nba_game_harness.market_fair and choose read only these).
READ_BOOKS = tuple(dict.fromkeys((*tl.config.BEST_LINE_BOOKMAKERS, "pinnacle")))
# How far before the window a read reaches by the books' own clock
# (odds.snapshot_at, TEXT): a coarse bound that lets idx_odds_book_snap
# (game_id, market, bookmaker, snapshot_at) do the work. The exact window is
# applied on created_at afterwards. Measured 2026-10-17 on ten 2026-27 games:
# 12.8 s and 143,301 rows read without it, 0.08 s and 612 rows with it. A
# book's clock sits within minutes of the fetch (docs/nba_models_2026.md 6.1),
# so hours of slack lose nothing.
SNAPSHOT_SLACK = timedelta(hours=6)


def _snap_bound(t: datetime) -> str:
    """A snapshot_at lower bound in the stored text shape ('...T..:..:..Z')."""
    return (t - SNAPSHOT_SLACK).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def newest_fetch(conn, games: dict[str, dict], now: datetime) -> dict[str, datetime]:
    """Each game's newest pre-game totals fetch (odds.created_at) at or before now."""
    if not games:
        return {}
    rows = conn.execute("""
        SELECT game_id, MAX(created_at::timestamptz)
        FROM odds
        WHERE game_id = ANY(%s) AND market = 'totals' AND bookmaker = ANY(%s)
          AND snapshot_at >= %s AND snapshot_type = 'open'
          AND created_at::timestamptz <= %s
        GROUP BY game_id
    """, (list(games), list(READ_BOOKS), _snap_bound(now),
          now.astimezone(timezone.utc).isoformat())).fetchall()
    out = {}
    for gid, ts in rows:
        t = pd.Timestamp(ts)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        if t < pd.Timestamp(games[gid]["tip"]):
            out[gid] = t.to_pydatetime()
    return out


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games with a decision row, or with any nba_total_luck BET whatever became
    of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            "SELECT game_id FROM nba_total_luck_decisions WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    bet = {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}
    return done | bet


def load_quote_rows(conn, game_ids: list[str], since: datetime) -> pd.DataFrame:
    """Every pre-game totals row of these games, at the books the rule reads,
    from fetches since `since`."""
    cols = list(tl.QUOTE_ROW_COLS)
    rows = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM odds
        WHERE game_id = ANY(%s) AND market = 'totals' AND bookmaker = ANY(%s)
          AND snapshot_at >= %s AND snapshot_type = 'open'
          AND created_at::timestamptz >= %s
    """, (list(game_ids), list(READ_BOOKS), _snap_bound(since),
          since.astimezone(timezone.utc).isoformat())).fetchall()
    return pd.DataFrame(rows, columns=cols)


def load_season(conn, season: int, before: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(final_games, box) for one season, games before the Eastern date `before`.

    final_games: the season's NBA games with a final score and a start time
    (the lab's population: scripts.nba_game_harness.load_games), less any game
    nba_schedule names as something other than a regular-season game. box: their
    nba_player_game_log rows."""
    g = pd.DataFrame(conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.home_team, g.away_team
        FROM games g
        LEFT JOIN nba_schedule s ON s.game_id = g.game_id
        WHERE g.sport = 'NBA' AND g.season = %s AND g.game_date < %s
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
          AND g.commence_time IS NOT NULL
          AND (s.game_type IS NULL OR s.game_type = 'regular')
    """, (int(season), before)).fetchall(),
        columns=["game_id", "season", "game_date", "home_team", "away_team"])
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["season"] = g["season"].astype(int)
    cols = ["game_id", "team", *tl.BOX_COLS]
    if g.empty:
        return g, pd.DataFrame(columns=cols)
    box = pd.DataFrame(conn.execute(f"""
        SELECT {', '.join(cols)} FROM nba_player_game_log WHERE game_id = ANY(%s)
    """, (g["game_id"].tolist(),)).fetchall(), columns=cols)
    for c in tl.BOX_COLS:
        box[c] = pd.to_numeric(box[c], errors="coerce")
    return g, box


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: tl.TotalLuckBet, home: str, away: str) -> str:
    from models.scorer import _build_pick_label
    return _build_pick_label(tl.SIDE, home, away, tl.MARKET, float(bet.line))


def pick_rows(bets: list[tl.TotalLuckBet], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Card bets -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs, so it is testable."""
    from models.honest_ev import gate
    from models.scorer import quarter_kelly
    rows, refused = [], {}
    for b in bets:
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if b.price < (tl.config.min_odds_for(MODEL_ID) or -1e9):
            refused[b.game_id] = f"below_price_floor:{b.price:+.0f}"
            continue
        ev = gate(MODEL_ID, b.p_model, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} over @{b.book}")
            refused[b.game_id] = ev.reason
            continue
        line = float(b.line)
        label = pick_label(b, home, away)
        problems = pick_problems(label, tl.SIDE, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            refused[b.game_id] = "label_mismatch"
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.p_model - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == tl.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.p_model, dec_implied, bankroll)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g["tip"].isoformat() if g.get("tip") is not None else None,
            "pick_side": tl.SIDE, "pick_label": label,
            # The market-fair P(over wins) at this line and price, plus the
            # gap >= 3 bucket's walk-forward uplift (models/nba_total_luck.py).
            # The model decides on it (config.MODELS_ON_OWN_PROBABILITY).
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
            # MED on every bet, as the NHL totals card writes: the evidence
            # gives no tier.
            "confidence_tier": "MED",
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4),
            "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
        })
    return rows, refused


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link")
# Its own column list, NOT models.scorer._insert_picks: that one stamps
# model_probability_cal from the promoted map, and this model decides on its
# own number (config.MODELS_ON_OWN_PROBABILITY).
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def publish(conn, rows: list[dict], decisions: list[tl.Decision], leads: dict[str, float],
            refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its bet in ONE
    transaction, under the model's lock, the ledger and the picks re-read
    inside it. -> (bets written, decisions written)."""
    if not decisions:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    gids = sorted({d.game_id for d in decisions})
    done = decided_games(conn, gids)
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
            "gap_total": None if d.gap is None else round(float(d.gap), 3),
            "n_bets": 1 if row is not None else 0, "detail": detail}).fetchone()
        if not got:
            continue
        n_decided += 1
        if row is not None and conn.execute(_INSERT, {c: row.get(c) for c in _COLS}).fetchone():
            n_bets += 1
    conn.commit()
    return n_bets, n_decided


# ── the pass ──────────────────────────────────────────────────────────────────

_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = tl.load_artifact()
    return _ART["a"]


def render(bets, diag: dict, written: int | None = None,
           decisions_written: int | None = None) -> str:
    head = f"NBA totals card ({MODEL_ID}): " + " ".join(f"{k}={v}" for k, v in diag.items())
    if decisions_written is not None:
        head += f" decisions_written={decisions_written}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in bets:
        lines.append(f"  {b.game_id:26s} Over {b.line:g} @{b.book} {b.price:+.0f}  gap {b.gap:+.2f}  "
                     f"fair {b.p_fair:.4f} (+{b.uplift:.4f}) -> {b.p_model:.4f}  "
                     f"fair line {b.fair_mu:.1f} ({b.fair_ref}), fetch {b.fetch_at.isoformat()}")
    return "\n".join(lines)


TIMING_KEYS = ("too_early", "deferred", "stale_fetch", "too_late", "no_fetch", "already_decided")


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        skipped: list[str] = []
        games = slate(conn, now, skipped)
        if skipped:
            logger.info(f"nba-total-luck: not a regular-season game, not priced: {skipped}")
        timing = dict.fromkeys(TIMING_KEYS, 0)
        if not games:
            logger.info(f"NBA totals card ({MODEL_ID}): no NBA game tips in the next "
                        f"{tl.DECISION_LEAD_MIN[1]:.0f} minutes")
            return {"games": 0, "bets": 0, "published": 0, "decided": 0, "timing": timing}
        if do_publish:
            ensure_decisions_table(conn)
        elif not ledger_exists(conn):
            logger.info(f"nba-total-luck: {DECISIONS_TABLE} does not exist yet; a dry run "
                        "reads no ledger and creates none")
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
            why = tl.timing(g["tip"], t, now)
            if why == "decide":
                due[gid] = t
                continue
            timing[why] += 1
            if why == "too_late":
                logger.warning(f"nba-total-luck: {gid} tips {g['tip'].isoformat()} and was never "
                               f"decided: no pass fetched it {tl.DECISION_LEAD_MIN[0]:.0f}+ "
                               f"minutes out at its last look")
        if not due:
            logger.info(f"NBA totals card ({MODEL_ID}): nothing to decide this pass; {timing}")
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0,
                    "timing": timing}

        by_season: dict[int, list[str]] = {}
        for gid in due:
            if games[gid].get("season") is not None:
                by_season.setdefault(int(games[gid]["season"]), []).append(gid)
        art = artifact()
        bets_all, decisions_all, diag_all = [], [], dict.fromkeys(tl.DIAG_KEYS, 0)
        leads = {gid: tl.lead_minutes(games[gid]["tip"], t) for gid, t in due.items()}
        for season, gids in sorted(by_season.items()):
            if tl.newest_season(art) != season - 1:
                logger.error(f"nba-total-luck: the artifact ends with {tl.newest_season(art)}; "
                             f"season {season} needs one refitted through {season - 1} "
                             f"(scripts/nba_total_luck_build.py). Nothing decided.")
                continue
            tg = pd.DataFrame([{"game_id": g, "season": season,
                                "game_date": games[g]["game_date"],
                                "home_team": games[g]["home"], "away_team": games[g]["away"],
                                "tip": pd.Timestamp(games[g]["tip"])} for g in gids])
            final, box = load_season(conn, season, max(tg["game_date"]))
            since = min(due[g] for g in gids) - timedelta(minutes=70)
            quotes = tl.quote_frame(load_quote_rows(conn, gids, since), tg)
            times = pd.DataFrame({"game_id": gids,
                                  "T": [pd.Timestamp(due[g]) for g in gids]})
            bets, decisions, diag = tl.decide(tg.drop(columns="tip"), quotes, box, final,
                                              times, art)
            bets_all += bets
            decisions_all += decisions
            for k, v in diag.items():
                diag_all[k] += v
        published = n_decided = 0
        if do_publish and decisions_all:
            from models.scorer import _get_current_bankroll
            rows, refused = pick_rows(bets_all, games, _get_current_bankroll(conn))
            published, n_decided = publish(conn, rows, decisions_all, leads, refused)
        logger.info("\n" + render(bets_all, {**diag_all, **timing},
                                  published if do_publish else None,
                                  n_decided if do_publish else None))
        return {"games": len(games), "bets": len(bets_all), "published": published,
                "decided": n_decided, "timing": timing, "diag": diag_all}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
