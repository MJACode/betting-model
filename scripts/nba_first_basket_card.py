"""NBA first-basket card: write `nba_first_basket` bets (models/nba_first_basket.py).

Runs on the five-minute NBA prop window job (scheduler.run_nba_prop_window) right after that job's
fetch of the games 3-22 minutes from tip (scripts/nba_prop_window.plan, `first_basket`), and as the
run_pipeline step `nba-first-basket`. It decides only games whose tip is 5-20 minutes away
(models/nba_first_basket.DECISION_WINDOW_MIN): the graded snapshot was ten minutes before tip, after
the books list the confirmed starters.

ITS OWN DOOR, NOT THE NBA PROP DOOR. scripts/nba_props_card.py keeps one bet a game and six a night
across the two stat-prop models. This model was graded on its own, one first-basket bet a game, so it
does not compete with them for those slots, and they do not compete with it.

EACH GAME DECIDED ONCE (CLAUDE.md 1c, and fidelity to the grade, which looked at every game once).
The first look inside the window whose newest fetch holds first-basket quotes IS the decision, bet
or not, written to nba_first_basket_decisions in the same transaction as the bet, under the model's
advisory lock, with the ledger and the picks re-read inside the lock. A game with a decision row or a
BET is never looked at again: a later price, a moved line or a changed lineup writes nothing.

ROW SHAPE: the NBA prop cards' (scripts/nba_prop_market_card.pick_rows). The bet is the Yes, stored
as Over 0.5 like every Yes-only prop ("<player> Over 0.5 First Basket"). dk_odds / dk_implied_prob /
edge are DraftKings' own Yes price for that player in this fetch, else NULL / 0.0 / 0.0; decision_*
is the book taken; line_book names it only when DraftKings did not list the player. player_key is the
bet book's spelling, player_id the NBA.com id the stat-prop picks carry (nba_player_game_log), else
'espn:<id>'. model_probability is the blend the bet was decided on (config.MODELS_ON_OWN_PROBABILITY).

    python -m scripts.nba_first_basket_card              # print the card, write nothing
    python -m scripts.nba_first_basket_card --publish    # decide and write
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_first_basket as fbm  # noqa: E402
import models.nba_prop_market as mk  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = fbm.MODEL_ID
SPORT = fbm.SPORT
_ET = ZoneInfo("America/New_York")

DECISIONS_TABLE = "nba_first_basket_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "n_quotes", "n_bets", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_first_basket_decisions (
    game_id     TEXT PRIMARY KEY,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at    TEXT NOT NULL,
    n_quotes    INTEGER NOT NULL,
    n_bets      INTEGER NOT NULL,
    detail      TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO nba_first_basket_decisions (game_id, fetch_at, n_quotes, n_bets, detail) "
    "VALUES (%(game_id)s, %(fetch_at)s, %(n_quotes)s, %(n_bets)s, %(detail)s) "
    "ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down; free after that (data/ddl_guard)."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

def slate(conn, now: datetime, skipped: list | None = None, horizon_min: int | None = None) -> dict:
    """Regular-season NBA games that have not tipped and tip within the window's far end (the
    totals card's slate: the graded population is regular-season games)."""
    return tlcard.slate(conn, now, skipped,
                        horizon_min=horizon_min if horizon_min is not None else fbm.DECISION_WINDOW_MIN[1])


def decided_games(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    ensure_decisions_table(conn)
    return {r[0] for r in conn.execute(
        "SELECT game_id FROM nba_first_basket_decisions WHERE game_id = ANY(%s)",
        (list(game_ids),)).fetchall()}


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM picks WHERE model_id = %s AND signal_type = 'BET' "
        "AND game_id = ANY(%s)", (MODEL_ID, list(game_ids))).fetchall()}


def load_quotes(conn, games: dict[str, dict], now: datetime) -> dict[str, list[dict]]:
    """{game_id: the rows of its NEWEST pre-tip fetch inside the window}, deciding books only."""
    if not games:
        return {}
    earliest = min(g["tip"] for g in games.values())
    lower = earliest - timedelta(minutes=fbm.DECISION_WINDOW_MIN[1] + 5)
    rows = conn.execute("""
        SELECT game_id, player_name, bookmaker, over_price, snapshot_at, over_link
          FROM player_prop_odds
         WHERE game_id = ANY(%s) AND market = %s AND bookmaker = ANY(%s)
           AND snapshot_type = 'open' AND over_price IS NOT NULL AND snapshot_at >= %s
    """, (list(games), fbm.MARKET, list(fbm.deciding_books()),
          lower.astimezone(timezone.utc).isoformat())).fetchall()
    return newest_fetch(rows, games, now)


def newest_fetch(rows, games: dict[str, dict], now: datetime) -> dict[str, list[dict]]:
    """Pure half of load_quotes: per game, the rows of the latest fetch at or before `now`, before
    the tip and inside the decision window."""
    by: dict[str, list[dict]] = {}
    for gid, player, book, price, snap, *rest in rows:
        g = games.get(gid)
        t = mk.parse_ts(snap)
        if g is None or t is None or t > now or t >= g["tip"]:
            continue
        lead = mk.minutes_to_tip(g["tip"], t)
        if not (fbm.DECISION_WINDOW_MIN[0] <= lead <= fbm.DECISION_WINDOW_MIN[1]):
            continue
        by.setdefault(gid, []).append({"book": book, "player": player, "price": float(price),
                                       "fetch": t.isoformat(), "_t": t,
                                       "link": rest[0] if rest else None})
    out = {}
    for gid, qs in by.items():
        last = max(q["_t"] for q in qs)
        out[gid] = [q for q in qs if q["_t"] == last]
    return out


def nba_ids(conn, teams: list[str], seasons: list[int]) -> mk.Roster:
    """The NBA.com ids the stat-prop picks carry, for picks.player_id (nba_player_game_log)."""
    if not teams or not seasons:
        return mk.Roster([])
    return mk.Roster(conn.execute(
        "SELECT DISTINCT player_id, player_name, team FROM nba_player_game_log "
        "WHERE team = ANY(%s) AND season = ANY(%s) AND player_id IS NOT NULL",
        (sorted(set(teams)), sorted(set(seasons)))).fetchall())


# ── the day's prepared state: a cache of Supabase ────────────────────────────
# Reading the history and learning it took 56.3 s and 27.0 s (2026-11-20, production): far too much
# to repeat on every five-minute look. It changes only when a day's games are stored, so it is built
# once per game date and kept under data/local (the declared, regenerable cache of Supabase; the
# worker's disk is wiped on a deploy, and the next look simply rebuilds it).
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "local" / "cache" / "nba_first_basket"


def cache_path(game_date: str) -> Path:
    return CACHE_DIR / f"prepared_{str(game_date)[:10]}.pkl"


def prepared_for(conn, game_date: str) -> fbm.Prepared:
    import pickle
    path = cache_path(game_date)
    if path.exists():
        try:
            with path.open("rb") as fh:
                prep = pickle.load(fh)
            if isinstance(prep, fbm.Prepared) and prep.game_date == str(game_date)[:10]:
                return prep
        except Exception as exc:  # noqa: BLE001 - a bad cache file is rebuilt, never trusted
            logger.warning(f"{MODEL_ID}: rebuilding the prepared state for {game_date}: {exc}")
    games, box = fbm.load_history(conn)
    prep = fbm.prepare(games, box, str(game_date)[:10])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(prep, fh)
    tmp.replace(path)
    logger.info(f"{MODEL_ID}: prepared the state for {game_date} from games through {prep.history_through}")
    return prep


def warm(now: datetime | None = None) -> str:
    """Build today's prepared state ahead of the first decision (the window job calls this while a
    game is 22-62 minutes from tip and the file is missing)."""
    now = now or datetime.now(timezone.utc)
    d = now.astimezone(_ET).date().isoformat()
    conn = get_connection()
    try:
        prep = prepared_for(conn, d)
        return f"{d}: through {prep.history_through}"
    finally:
        conn.close()


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: fbm.FirstBasketBet) -> str:
    return f"{bet.player} Over {fbm.LINE:g} {fbm.LABEL}"


def pick_rows(bets: list[fbm.FirstBasketBet], bankroll: float, ids: dict | None = None) -> list[dict]:
    """Bets -> picks rows. `ids`: {game_id: NBA.com player id} where one resolved."""
    rows = []
    for b in bets:
        label = pick_label(b)
        problems = pick_problems(label, fbm.SIDE, fbm.LINE, MODEL_ID, prop_market=fbm.MARKET)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.prob - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == fbm.REFERENCE_BOOK
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": b.game_date, "game_time": b.tip.isoformat() if hasattr(b.tip, "isoformat") else b.tip,
            "pick_side": fbm.SIDE, "pick_label": label,
            "model_probability": round(b.prob, 4), "model_probability_cal": round(b.prob, 4),
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.prob - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": fbm.LINE,
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET", "confidence_tier": "MED",
            "prop_market": fbm.MARKET, "player_key": b.player,
            "player_id": (ids or {}).get(b.game_id) or f"espn:{b.espn_id}",
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4), "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book, "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
            "_ev": round(b.ev, 4),
        })
    return rows


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "prop_market", "player_key", "player_id", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link")
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


# ── the pass ──────────────────────────────────────────────────────────────────

def look(conn, now: datetime, history=None) -> dict:
    """One look, no write. -> {"games", "bets", "decisions", "ids"}; `history`: (games, box) to
    price from instead of reading it (the fidelity replay)."""
    skipped: list[str] = []
    games = slate(conn, now, skipped)
    out = {"games": games, "bets": [], "decisions": [], "ids": {}}
    if not games:
        return out
    ensure_decisions_table(conn)
    done = decided_games(conn, sorted(games)) | games_with_a_bet(conn, sorted(games))
    todo = {g: v for g, v in games.items() if g not in done and fbm.in_window(v["tip"], now)}
    if not todo:
        return out
    quotes = load_quotes(conn, todo, now)
    todo = {g: v for g, v in todo.items() if quotes.get(g)}
    if not todo:
        return out
    roster = nba_ids(conn, [t for v in todo.values() for t in (v["home"], v["away"])],
                     [s for v in todo.values() if v.get("season") for s in (v["season"], v["season"] - 1)])
    preps: dict[str, fbm.Prepared] = {}
    for gid, g in sorted(todo.items()):
        d = str(g["game_date"])[:10]
        if d not in preps:
            preps[d] = (fbm.prepare(*history, d) if history is not None else prepared_for(conn, d))
        names = fbm.names_for(preps[d], (g["home"], g["away"]))
        bet, why = fbm.decide({**g, "game_id": gid, "game_date": d}, quotes[gid], preps[d].state, names)
        qs = quotes[gid]
        out["decisions"].append({"game_id": gid, "fetch_at": qs[0]["fetch"], "n_quotes": len(qs),
                                 "detail": why})
        if bet is not None:
            out["bets"].append(bet)
            pid, status = roster.resolve(bet.player, g["home"], g["away"])
            if pid:
                out["ids"][gid] = pid
    return out


def publish(conn, rows: list[dict], decisions: list[dict]) -> dict:
    """Under the model's lock: re-read the ledger and the bets, then write each new decision and its
    bet in ONE transaction. A decision row's n_bets is the number of picks inserts that returned."""
    from scripts.nfl_wind_publisher import _lock_model
    out = {"decided": 0, "written": 0}
    if not decisions:
        return out
    _lock_model(conn, MODEL_ID)
    gids = sorted({d["game_id"] for d in decisions})
    skip = decided_games(conn, gids) | games_with_a_bet(conn, gids)
    for d in sorted(decisions, key=lambda x: x["game_id"]):
        if d["game_id"] in skip:
            continue
        mine = [r for r in rows if r["game_id"] == d["game_id"]]
        got = conn.execute(_INSERT_DECISION, {**d, "n_bets": len(mine)}).fetchone()
        if not got:
            continue
        out["decided"] += 1
        n = sum(1 for r in mine if conn.execute(_INSERT, {c: r[c] for c in _COLS}).fetchone())
        out["written"] += n
        if n != len(mine):
            conn.execute("UPDATE nba_first_basket_decisions SET n_bets = %s WHERE game_id = %s",
                         (n, d["game_id"]))
    conn.commit()
    return out


def render(bets, decisions) -> str:
    lines = [f"NBA first-basket card ({MODEL_ID}): decisions={len(decisions)} bets={len(bets)}"]
    for d in decisions:
        lines.append(f"  {d['game_id']:26s} {d['detail']} (fetch {d['fetch_at']}, {d['n_quotes']} quotes)")
    for b in bets:
        lines.append(f"  BET {b.game_id:22s} {b.player} First Basket @{b.book} {b.price:+.0f}  "
                     f"p {b.prob:.4f} (model {b.p_model:.4f}, books {b.p_market:.4f})  EV {b.ev:+.4f}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        got = look(conn, now)
        logger.info("\n" + render(got["bets"], got["decisions"]))
        result = {"games": len(got["games"]), "decisions": len(got["decisions"]),
                  "bets": len(got["bets"]), "published": 0}
        if do_publish and got["decisions"]:
            rows = []
            if got["bets"]:
                from models.scorer import _get_current_bankroll
                rows = pick_rows(got["bets"], _get_current_bankroll(conn), got["ids"])
            w = publish(conn, rows, got["decisions"])
            result.update(published=w["written"], decided=w["decided"])
        return result
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--warm", action="store_true", help="build today's prepared state and exit")
    a = ap.parse_args()
    if a.warm:
        print(warm())
        return
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/), as every script the scheduler runs carries.
    # Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-first-basket")
    except Exception:  # noqa: BLE001
        pass

    main()
