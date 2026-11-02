"""NBA first-half total card: write `nba_first_half_total_luck` bets
(models/nba_first_half_total_luck.py).

Runs in the NBA totals window job, right after this model's own first-half
fetch (scheduler.run_nba_total_luck_window; step nba-first-half-total-luck,
under a time limit there). LIVE, with no default-off write switch, like the
full-game totals card (scripts/nba_total_luck_card.py), whose slate, season
loader and model lock it uses rather than copies.

WHEN A GAME IS DECIDED. A run decides a game when its newest first-half fetch
-- the newest ok 'open' call in the fetch ledger (data/ingestors/
nba_first_half_odds.py), whose instant is the stored rows' created_at -- landed
45-66 minutes before tip and is at most 5 minutes old
(models.nba_first_half_total_luck.timing, the home team total's). A call that
came back with no first-half total at any book is still a fetch: the game is
decided with nothing offered, as the lab's one purchase a game would have been.
A failed call is not a fetch, and the next tick fetches again. A season the
artifact does not end just before is not decided, and the run raises after
writing every other season, so the step fails and the job reports it.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
nba_first_half_total_luck_decisions in the same transaction as the game's bet,
under the model's transaction-scoped advisory lock (a run by hand can overlap
the job's). A game with a decision row, or with any nba_first_half_total_luck
BET, is never looked at again: a later tick, a moved line or a better price
writes nothing. The decision row carries the gap and the best over offer on
every decided game, bet or not, so the cut can be swept on live data (CLAUDE.md
1b), and each book's last_update age at the fetch.

WHAT IS READ. Only stored rows: this feed's (nba_first_half_odds.SOURCE)
pre-game ('open') first-half rows at the deciding books and Pinnacle, from
fetches up to 70 minutes before the decision fetch. Each book's MAIN number only:
the fetch files any other rung under totals_h1_alternate. The closing snapshot
('close') is never read here.

EVERY GAME PRESENT, REGULAR SEASON ONLY, A PAUSED MODEL'S ROWS, BET ROWS ONLY:
exactly as the full-game card (its docstring).

ROW SHAPE: the full-game card's. pick_side 'over'; scored_line is the first
half's points line as quoted; dk_odds / dk_implied_prob / edge are DraftKings'
own over at this number in this fetch, else NULL / 0.0 / 0.0 with line_book
naming the book taken; decision_* is the book taken, always set; best_* only
when the bet is not at DraftKings. The label is the platform's ("BOS @ MIL —
First Half Over 112.5", models.scorer._build_pick_label), checked against side,
line and market before it is written (tracking/pick_integrity.pick_problems).
The price floor (config.min_odds_for) and the model's own EV floor
(models.honest_ev.gate, a push scored as a loss) are applied here.

    python -m scripts.nba_first_half_total_luck_card              # print the card, write nothing
    python -m scripts.nba_first_half_total_luck_card --publish    # write new decisions and bets
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

import data.ingestors.nba_first_half_odds as feed  # noqa: E402
import models.nba_first_half_total_luck as fh  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = fh.MODEL_ID
SPORT = fh.SPORT

# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "nba_first_half_total_luck_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "lead_min", "gap_total",
                  "n_bets", "detail", "book", "line", "price", "p_fair", "p_model",
                  "fair_ref", "fair_mu", "book_ages")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_first_half_total_luck_decisions (
    game_id     TEXT PRIMARY KEY,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at    TEXT NOT NULL,
    lead_min    REAL,
    gap_total   REAL,
    n_bets      INTEGER NOT NULL,
    detail      TEXT,
    book        TEXT,
    line        REAL,
    price       REAL,
    p_fair      REAL,
    p_model     REAL,
    fair_ref    TEXT,
    fair_mu     REAL,
    book_ages   TEXT
)
"""
_DECISION_VALUES = DECISIONS_COLS[:1] + DECISIONS_COLS[2:]
_INSERT_DECISION = (
    f"INSERT INTO nba_first_half_total_luck_decisions ({', '.join(_DECISION_VALUES)}) "
    f"VALUES ({', '.join('%(' + c + ')s' for c in _DECISION_VALUES)}) "
    f"ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that
    (data/ddl_guard.schema_is_current). Committed on its own, before the
    model's lock is taken."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

# The books the rule reads: the deciding books and Pinnacle, whose no-vig line
# is the market's fair line (scripts.nba_game_harness.market_fair and choose
# read only these).
READ_BOOKS = tuple(dict.fromkeys((*fh.config.BEST_LINE_BOOKMAKERS, "pinnacle")))
# How far before the decision fetch a book's quote can still be its number:
# the harness's 60-minute staleness rule, judged on the fetch instant, plus slack.
READ_BACK = timedelta(minutes=70)


def slate(conn, now: datetime, skipped: list | None = None) -> dict[str, dict]:
    """The regular-season NBA games that have not tipped and tip within the
    far end of the decision window, plus 5 (the full-game card's slate)."""
    return tlcard.slate(conn, now, skipped, horizon_min=fh.DECISION_LEAD_MIN[1] + 5)


def ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    """Games holding any nba_first_half_total_luck BET, whatever became of it."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games with a decision row, or with any nba_first_half_total_luck BET
    whatever became of it (settled, VOIDed): none is decided again. Reads only."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    return done | games_with_a_bet(conn, game_ids)


def newest_fetch(conn, games: dict[str, dict], now: datetime) -> dict[str, datetime]:
    """Each game's newest first-half decision fetch at or before now, from the
    fetch ledger, kept only when it landed before tip."""
    got = feed.fetches(conn, sorted(games), "open", now)
    return {gid: t for gid, t in got.items()
            if pd.Timestamp(t) < pd.Timestamp(games[gid]["tip"])}


def load_quote_rows(conn, game_ids: list[str], since: datetime) -> pd.DataFrame:
    """This feed's pre-game first-half rows of these games at the books the rule
    reads, from fetches since `since`. Main numbers only: the alternates are
    stored under another market name."""
    cols = list(fh.QUOTE_ROW_COLS)
    rows = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM odds
        WHERE game_id = ANY(%s) AND market = %s AND snapshot_type = 'open'
          AND bookmaker = ANY(%s) AND source = %s
          AND created_at::timestamptz >= %s
    """, (list(game_ids), fh.MARKET, list(READ_BOOKS), feed.SOURCE,
          since.astimezone(timezone.utc).isoformat())).fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: fh.FirstHalfBet, home: str, away: str) -> str:
    from models.scorer import _build_pick_label
    return _build_pick_label(fh.SIDE, home, away, fh.MARKET, float(bet.line))


def pick_rows(bets: list[fh.FirstHalfBet], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Card bets -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs, so it is testable."""
    from models.honest_ev import gate
    from models.scorer import _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    rows, refused = [], {}
    for b in bets:
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if b.price < (fh.config.min_odds_for(MODEL_ID) or -1e9):
            refused[b.game_id] = f"below_price_floor:{b.price:+.0f}"
            continue
        # The floor reads p x decimal - 1, a push scored as a loss: the
        # quantity every publisher filters on (models/nba_first_half_total_luck.py,
        # THE PROBABILITY).
        ev = gate(MODEL_ID, b.p_model, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} over @{b.book}")
            refused[b.game_id] = ev.reason
            continue
        line = float(b.line)
        label = pick_label(b, home, away)
        problems = pick_problems(label, fh.SIDE, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            refused[b.game_id] = "label_mismatch"
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.p_model - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == fh.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.p_model, dec_implied, bankroll)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g["tip"].isoformat() if g.get("tip") is not None else None,
            "pick_side": fh.SIDE, "pick_label": label,
            # The market-fair P(over wins) at this line and price, plus the
            # bucket's walk-forward uplift (models/nba_first_half_total_luck.py).
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
            # MED on every bet, as the full-game card writes: the evidence
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
            # config.PAUSED_NOTE while the model is paused: the row's own
            # marker, which every publisher and record query keys on.
            "downgrade_reason": pause,
        })
    return rows, refused


# The full-game card's column list: its own, NOT models.scorer._insert_picks,
# which stamps model_probability_cal from the promoted map (this model decides
# on its own number).
_COLS = tlcard._COLS
_INSERT = tlcard._INSERT


def _num(x, nd):
    return None if x is None else round(float(x), nd)


def publish(conn, rows: list[dict], decisions: list[fh.FirstHalfDecision],
            leads: dict[str, float], refused: dict[str, str]) -> tuple[int, int]:
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
            "gap_total": _num(d.gap_total, 3),
            "n_bets": 1 if row is not None else 0, "detail": detail,
            "book": d.book, "line": d.line, "price": d.price,
            "p_fair": _num(d.p_fair, 4), "p_model": _num(d.p_model, 4),
            "fair_ref": d.fair_ref, "fair_mu": _num(d.fair_mu, 2),
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
        _ART["a"] = fh.load_artifact()
    return _ART["a"]


def render(bets, diag: dict, written: int | None = None,
           decisions_written: int | None = None) -> str:
    head = f"NBA first-half card ({MODEL_ID}): " + " ".join(f"{k}={v}" for k, v in diag.items())
    if decisions_written is not None:
        head += f" decisions_written={decisions_written}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in bets:
        lines.append(f"  {b.game_id:26s} Over {b.line:g} @{b.book} {b.price:+.0f}  "
                     f"gap {b.gap_total:+.2f}  fair {b.p_fair:.4f} "
                     f"({b.uplift:+.4f}) -> {b.p_model:.4f}  fair line {b.fair_mu:.1f} "
                     f"({b.fair_ref}), fetch {pd.Timestamp(b.fetch_at).isoformat()}")
    return "\n".join(lines)


TIMING_KEYS = ("too_early", "stale_fetch", "too_late", "no_fetch", "already_decided")


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        skipped: list[str] = []
        games = slate(conn, now, skipped)
        if skipped:
            logger.info(f"nba-first-half-total-luck: not a regular-season game, not priced: {skipped}")
        timing = dict.fromkeys(TIMING_KEYS, 0)
        if not games:
            logger.info(f"NBA first-half card ({MODEL_ID}): no NBA game tips in the next "
                        f"{fh.DECISION_LEAD_MIN[1] + 5:.0f} minutes")
            return {"games": 0, "bets": 0, "published": 0, "decided": 0, "timing": timing}
        if do_publish:
            ensure_decisions_table(conn)
        elif not ledger_exists(conn):
            logger.info(f"nba-first-half-total-luck: {DECISIONS_TABLE} does not exist yet; a dry "
                        "run reads no ledger and creates none")
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
            why = fh.timing(g["tip"], t, now)
            if why == "decide":
                due[gid] = t
                continue
            timing[why] += 1
            if why == "too_late":
                logger.warning(f"nba-first-half-total-luck: {gid} tips {g['tip'].isoformat()} and "
                               f"was never decided: no first-half fetch landed "
                               f"{fh.DECISION_LEAD_MIN[0]:.0f}-{fh.DECISION_LEAD_MIN[1]:.0f} "
                               f"minutes before tip (the window job, "
                               f"scheduler.run_nba_total_luck_window, missed every tick)")
        if not due:
            logger.info(f"NBA first-half card ({MODEL_ID}): nothing to decide this run; {timing}")
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0,
                    "timing": timing}

        by_season: dict[int, list[str]] = {}
        for gid in due:
            if games[gid].get("season") is not None:
                by_season.setdefault(int(games[gid]["season"]), []).append(gid)
        art = artifact()
        bets_all, decisions_all, diag_all = [], [], dict.fromkeys(fh.DIAG_KEYS, 0)
        leads = {gid: fh.lead_minutes(games[gid]["tip"], t) for gid, t in due.items()}
        # Seasons the artifact cannot price. Their games are left undecided and
        # the run raises once the other seasons are written: a model that
        # decides nothing for a season must not report healthy.
        stale: dict[int, list[str]] = {}
        for season, gids in sorted(by_season.items()):
            if fh.newest_season(art) != season - 1:
                logger.error(f"nba-first-half-total-luck: the artifact ends with "
                             f"{fh.newest_season(art)}; season {season} needs one refitted "
                             f"through {season - 1} (scripts/nba_first_half_total_luck_build.py). "
                             f"Nothing decided.")
                stale[season] = gids
                continue
            tg = pd.DataFrame([{"game_id": g, "season": season,
                                "game_date": games[g]["game_date"],
                                "home_team": games[g]["home"], "away_team": games[g]["away"],
                                "tip": pd.Timestamp(games[g]["tip"])} for g in gids])
            final, box, scheduled = tlcard.load_season(conn, season, max(tg["game_date"]))
            since = min(due[g] for g in gids) - READ_BACK
            quotes = fh.quote_frame(load_quote_rows(conn, gids, since), tg)
            times = pd.DataFrame({"game_id": gids,
                                  "T": [pd.Timestamp(due[g]) for g in gids]})
            bets, decisions, diag = fh.decide(tg.drop(columns="tip"), quotes, box, final,
                                              times, art, scheduled=scheduled)
            bets_all += bets
            decisions_all += decisions
            presumed = diag.pop("presumed_unplayed", [])
            if presumed:
                logger.warning(
                    f"nba-first-half-total-luck: {len(presumed)} game(s) of {season} still have "
                    f"no final score {fh.UNPLAYED_AFTER_DAYS}+ days after their date and are "
                    f"treated as not played: {presumed}. If one WAS played, its score and box are "
                    f"missing and every gap since is off.")
            for d in decisions:
                if d.detail.startswith(("score_missing", "box_missing", "box_mismatch")):
                    logger.error(f"nba-first-half-total-luck: {d.game_id} declined, {d.detail}: "
                                 f"the gap would not be the lab's. The repair is the full-game "
                                 f"card's (scripts/nba_total_luck_card.py): the results step "
                                 f"retries every started game; a box that never adds up is "
                                 f"replaced with python -m data.ingestors.nba_stats_ingestor "
                                 f"--repair-boxes {season} from a residential machine")
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
        if stale:
            raise RuntimeError(
                f"nba-first-half-total-luck: the artifact ends with {fh.newest_season(art)}, so "
                f"{sum(len(g) for g in stale.values())} due game(s) of season(s) "
                f"{sorted(stale)} were not decided: {sorted(g for v in stale.values() for g in v)}. "
                f"Refit it (scripts/nba_first_half_total_luck_build.py).")
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
