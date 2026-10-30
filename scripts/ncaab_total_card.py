"""NCAAB totals card: write `ncaab_total_blend` bets (models/ncaab_total_blend.py).

LIVE, real money (mike, 2026-10-30: "Yes to the totals model"). Runs in its
own job, hourly at five past the hour UTC (scheduler.run_ncaab_total_card),
and writes picks only; the job then publishes them like every other card.
RUN_NCAAB_TOTAL_CARD=0 stops it before it reads anything; the job keeps
beating, so its silence still means stopped.

WHEN A GAME IS DECIDED. The evidence bet DraftKings' FIRST stored total, and
the totals it bought were the 22:00Z snapshot the evening before, the 15:00Z
snapshot on the day and the hour before tip. So a game's decision hours are
22:00Z on the day before its Eastern date, then 15:00Z on its date and every
hour after it until tip (models.ncaab_total_blend.decision_hour). At the
first of them where DraftKings has a total standing (its newest pre-game row
stored within the last DK_MAX_AGE_MIN minutes), the game is decided, bet or
not, and never looked at again.

AS OF THE QUOTE. The ratings, the 10-game count and the shooting and style
inputs use only finals that had ENDED (tip + 2.5 h) at or before DraftKings'
own time on that row, rounded down to the hour, as the evidence did.

A HOLD IS NOT A DECISION. When a team's earlier game ended before the quote
but its final score or either box score is not stored yet (the ESPN feed fills
them after each final), the game waits for its next decision hour. A box still
missing BOX_WAIT_H hours after its game ended stops holding (the evidence had a
few games with no possessions too), unless a team is missing more than one.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
ncaab_total_decisions in the same transaction as the game's bet, under the
model's transaction-scoped advisory lock. A game with a decision row, or with
any ncaab_total_blend BET, is never decided again: a later hour, a moved line
or a better price writes nothing.

BET ROWS ONLY in picks, at DraftKings' own price on DraftKings' own number:
the evidence priced DraftKings and nothing else, so the line is not shopped.
dk_* and decision_* are that price; best_* is empty. The label is the
platform's ("Duke vs Kansas Over 145.5"), checked against the side and line
before it is written (tracking/pick_integrity.pick_problems).

The per-run diagnostic line counts every slate game by why it did or did not
bet. Under the 10-game rule the model has never bet in November, so a card of
below_10_games and no bets until about December is the normal case.

    python -m scripts.ncaab_total_card              # print the card, write nothing
    python -m scripts.ncaab_total_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
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
import models.ncaab_total_blend as nb  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = nb.MODEL_ID
SPORT = nb.SPORT
_ET = ZoneInfo("America/New_York")

# DraftKings' total counts as standing when its newest pre-game row was stored
# this recently. The refresh passes store every book's NCAAB total every hour
# and the capture job stores each change within five minutes, so a standing
# number is never more than about an hour old; an older one has been taken
# down, or the odds steps have stopped.
DK_MAX_AGE_MIN = 90


def enabled() -> bool:
    """The kill switch: RUN_NCAAB_TOTAL_CARD=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_NCAAB_TOTAL_CARD", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "ncaab_total_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "check_hour", "quote_at", "cutoff", "total_line",
                  "model_total", "edge", "side", "n_bets", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_total_decisions (
    game_id      TEXT PRIMARY KEY,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_hour   TEXT NOT NULL,
    quote_at     TEXT,
    cutoff       TEXT,
    total_line   REAL,
    model_total  REAL,
    edge         REAL,
    side         TEXT,
    n_bets       INTEGER NOT NULL,
    detail       TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO ncaab_total_decisions (game_id, check_hour, quote_at, cutoff, total_line, "
    "model_total, edge, side, n_bets, detail) VALUES (%(game_id)s, %(check_hour)s, "
    "%(quote_at)s, %(cutoff)s, %(total_line)s, %(model_total)s, %(edge)s, %(side)s, "
    "%(n_bets)s, %(detail)s) ON CONFLICT (game_id) DO NOTHING RETURNING game_id")

# The decisions that end a game's wait; the rest wait for its next hour.
FINAL = ("bets", "below_cut", "below_10_games")


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
    """Games with a decision row, or with any ncaab_total_blend BET whatever
    became of it (settled, VOIDed): none is decided again."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            "SELECT game_id FROM ncaab_total_decisions WHERE game_id = ANY(%s)",
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
    """NCAAB games dated today or tomorrow (Eastern) that have not tipped."""
    today = now.astimezone(_ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in (0, 1)]
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAAB' AND game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    for gid, season, gd, ct, home, away in rows:
        tip = _tip(ct)
        if tip is None or tip <= now:
            continue
        out[gid] = {"season": int(season), "game_date": str(gd)[:10], "tip": tip,
                    "commence_time": ct, "home": home, "away": away}
    return out


SEASON_COLS = ["game_id", "season", "game_date", "commence_time", "home_score", "away_score",
               "neutral_site", "espn_event_id", "home_espn_id", "away_espn_id", "status"]
BOX_COLS = ["contest_id", "team", "game_date", "espn_game_id", "team_espn_id", "season",
            *nb.BOX_STATS, "source"]


def load_season(conn, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, box) for one season: every scheduled game with ESPN's ids and
    status, and every stored box row from any source."""
    games = pd.DataFrame(conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.commence_time, g.home_score, g.away_score,
               COALESCE(g.neutral_site, CASE WHEN e.neutral_site THEN 1 ELSE 0 END),
               e.espn_event_id, e.home_espn_id, e.away_espn_id, e.status
        FROM games g
        LEFT JOIN ncaab_events e ON e.game_id = g.game_id
        WHERE g.sport = 'NCAAB' AND g.season = %s
    """, (int(season),)).fetchall(), columns=SEASON_COLS)
    box = pd.DataFrame(conn.execute(f"""
        SELECT {', '.join(BOX_COLS)} FROM ncaab_team_game_stats WHERE season = %s
    """, (int(season),)).fetchall(), columns=BOX_COLS)
    return games, box


def prepare_season(games: pd.DataFrame, box: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The season's games ready for the ratings (possessions, pooled ids,
    end times) and its deduped box rows placed on their games."""
    g = games.drop_duplicates("game_id").copy()
    g["game_date"] = g["game_date"].astype(str).str[:10]
    for c in ("home_score", "away_score"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    for c in ("home_espn_id", "away_espn_id"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["neutral_site"] = pd.to_numeric(g["neutral_site"], errors="coerce").fillna(0)
    b = box.copy()
    for c in nb.BOX_STATS:
        b[c] = pd.to_numeric(b[c], errors="coerce")
    b["team_espn_id"] = pd.to_numeric(b["team_espn_id"], errors="coerce")
    if len(b):
        b = nb.dedupe_box(b)
        ev = dict(zip(pd.to_numeric(g["espn_event_id"], errors="coerce"), g["game_id"]))
        eg = pd.to_numeric(b["espn_game_id"], errors="coerce")
        # A feed row without the column filled still names its event in the
        # contest id ("espn:<event>").
        from_cid = pd.to_numeric(b["contest_id"].astype(str).str.extract(r"^espn:(\d+)$")[0],
                                 errors="coerce")
        b["game_id"] = eg.where(eg.notna(), from_cid).map(ev)
    else:
        b["game_id"] = pd.Series(dtype=object); b["_key"] = pd.Series(dtype=object)
    g["poss"] = g["game_id"].map(nb.game_possessions(b)) if len(b) else np.nan
    teams = pd.concat([g["home_espn_id"], g["away_espn_id"]]).dropna().astype(int)
    n = teams.value_counts()
    g["n_sched_home"] = [int(n.get(int(t), 0)) if pd.notna(t) else 0 for t in g["home_espn_id"]]
    g["n_sched_away"] = [int(n.get(int(t), 0)) if pd.notna(t) else 0 for t in g["away_espn_id"]]
    sg = nb.season_games(g)
    end = dict(zip(sg["game_id"], sg["end_ns"]))
    if len(b):
        fallback = ((pd.to_datetime(b["game_date"].astype(str).str[:10]) + pd.Timedelta(days=2, hours=6))
                    .dt.tz_localize("UTC").dt.as_unit("ns").astype("int64"))
        b["end_ns"] = b["game_id"].map(end)
        b["end_ns"] = b["end_ns"].where(b["end_ns"].notna(), fallback).astype("int64")
    else:
        b["end_ns"] = pd.Series(dtype="int64")
    return sg, b


def load_quotes(conn, games: dict[str, dict], now: datetime) -> dict[str, nb.Quote]:
    """DraftKings' standing total per game: its newest pre-game totals row
    stored at or before now and within DK_MAX_AGE_MIN, with both prices."""
    if not games:
        return {}
    oldest = now - timedelta(minutes=DK_MAX_AGE_MIN)
    rows = conn.execute("""
        WITH g AS (
            SELECT game_id, commence_time::timestamptz AS ct
            FROM games WHERE game_id = ANY(%s) AND commence_time IS NOT NULL
        )
        SELECT DISTINCT ON (o.game_id)
               o.game_id, o.total_line, o.over_price, o.under_price, o.snapshot_at,
               o.created_at::timestamptz, o.over_link, o.under_link
        FROM odds o JOIN g ON g.game_id = o.game_id
        WHERE o.market = 'totals' AND o.bookmaker = %s AND o.snapshot_type = 'open'
          AND o.snapshot_at::timestamptz <= g.ct
          AND o.created_at::timestamptz <= %s
          AND o.created_at::timestamptz >= %s
        ORDER BY o.game_id, o.created_at::timestamptz DESC, o.snapshot_at::timestamptz DESC
    """, (list(games), nb.BOOK, now.isoformat(), oldest.isoformat())).fetchall()
    out = {}
    for gid, line, op, up, snap, created, lo, lu in rows:
        if line is None or implied(op) is None or implied(up) is None:
            continue
        snap_t = _tip(snap) or _tip(created)
        out[gid] = nb.Quote(game_id=gid, line=float(line), over_price=float(op),
                            under_price=float(up), quote_at=min(snap_t, now),
                            fetched_at=_tip(created), link_over=lo, link_under=lu)
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
# own number (config.MODELS_ON_OWN_PROBABILITY).
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


def pick_rows(decisions: list[nb.Decision], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Bet decisions -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs."""
    from models.honest_ev import gate
    from models.scorer import _build_pick_label, _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    rows, refused = [], {}
    for d in decisions:
        if d.status != "bets":
            continue
        pz, q = d.priced, d.quote
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if floor is not None and pz.price < floor:
            refused[d.game_id] = f"below_price_floor:{pz.price:+.0f}"
            continue
        ev = gate(MODEL_ID, pz.prob, pz.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {d.game_id} {pz.side}")
            refused[d.game_id] = ev.reason or "below_ev_floor"
            continue
        label = _build_pick_label(pz.side, home, away, nb.MARKET, float(q.line))
        problems = pick_problems(label, pz.side, float(q.line), MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {d.game_id} {label!r}: {'; '.join(problems)}")
            refused[d.game_id] = "label_mismatch"
            continue
        imp = implied(pz.price)
        edge = round(pz.prob - imp, 4)
        kelly_frac, rec_bet = quarter_kelly(pz.prob, imp, bankroll)
        link = q.link_over if pz.side == "over" else q.link_under
        rows.append({
            "game_id": d.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": pz.side, "pick_label": label,
            # P(win | no push) at DraftKings' line: the number the 0.04 cut
            # was measured on (models/ncaab_total_blend.py, THE PROBABILITY).
            "model_probability": round(pz.prob, 4),
            "model_probability_cal": round(pz.prob, 4),
            "dk_odds": pz.price, "dk_implied_prob": round(imp, 4), "edge": edge,
            "dk_bet_link": link, "line_book": None,
            "scored_line": float(q.line),
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            # MED on every bet, as the other rule cards write: the evidence
            # gives no tier.
            "confidence_tier": "MED",
            "decision_book": nb.BOOK, "decision_odds": pz.price,
            "decision_implied_prob": round(imp, 4), "decision_edge": edge,
            "best_book": None, "best_odds": None, "best_implied_prob": None,
            "best_edge": None, "best_bet_link": None,
            "downgrade_reason": pause,
        })
    return rows, refused


def publish(conn, rows: list[dict], decisions: list[nb.Decision], check_hour: datetime,
            refused: dict[str, str]) -> tuple[int, int]:
    """Write each decided game once: its decision row and its bet in ONE
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
        detail = d.status + ": " + d.detail
        if d.game_id in refused:
            detail += f"; refused {refused[d.game_id]}"
        q, pz = d.quote, d.priced
        got = conn.execute(_INSERT_DECISION, {
            "game_id": d.game_id, "check_hour": check_hour.isoformat(),
            "quote_at": q.quote_at.isoformat() if q else None,
            "cutoff": d.cutoff.isoformat() if d.cutoff else None,
            "total_line": q.line if q else None,
            "model_total": None if d.model_total is None else round(d.model_total, 3),
            "edge": None if pz is None else round(pz.edge, 4),
            "side": None if pz is None else pz.side,
            "n_bets": 1 if row is not None else 0, "detail": detail}).fetchone()
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
        _ART["a"] = nb.load_artifact()
    return _ART["a"]


def render(decisions: list[nb.Decision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAAB totals card ({MODEL_ID}): " + " ".join(f"{k}={diag.get(k, 0)}" for k in nb.DIAG_KEYS)
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for d in sorted(decisions, key=lambda x: x.game_id):
        if d.status in ("bets", "below_cut"):
            q, pz = d.quote, d.priced
            lines.append(f"  {d.game_id:44s} {d.status:9s} {pz.side:5s} {q.line:g} "
                         f"{pz.price:+.0f}  p {pz.prob:.4f} edge {pz.edge:+.4f}  model "
                         f"{d.model_total:.1f} mean {pz.mean:.1f}  games {d.ng[0]}/{d.ng[1]}  "
                         f"quote {q.quote_at.isoformat()}")
        elif d.status != "no_dk_total":
            lines.append(f"  {d.game_id:44s} {d.status}: {d.detail}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not enabled():
        logger.info("NCAAB totals card: RUN_NCAAB_TOTAL_CARD is off; nothing read")
        return {"games": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    hour = now.replace(minute=0, second=0, microsecond=0)
    diag = dict.fromkeys(nb.DIAG_KEYS, 0)
    conn = get_connection()
    try:
        games = slate(conn, now)
        diag["games"] = len(games)
        due = {g: v for g, v in games.items() if nb.decision_hour(v["game_date"], v["tip"], hour)}
        diag["not_decision_hour"] = len(games) - len(due)
        if do_publish and due:
            ensure_decisions_table(conn)
        done = decided_games(conn, sorted(due))
        diag["already_decided"] = len(done)
        due = {g: v for g, v in due.items() if g not in done}
        if not due:
            logger.info(render([], diag))
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "diag": diag}
        art = artifact()
        decisions: list[nb.Decision] = []
        for season in sorted({v["season"] for v in due.values()}):
            gids = sorted(g for g, v in due.items() if v["season"] == season)
            if int(art["season"]) != season:
                logger.error(f"NCAAB totals card: the artifact is for season {art['season']}; "
                             f"season {season} needs one built through {season - 1} "
                             f"(scripts/ncaab_total_blend_build.py). {len(gids)} game(s) not decided.")
                continue
            games_df, box_df = load_season(conn, season)
            sg, box = prepare_season(games_df, box_df)
            quotes = load_quotes(conn, {g: due[g] for g in gids}, now)
            targets = sg[sg["game_id"].isin(gids)]
            got = nb.decide(targets, quotes, sg, box, art, config.MODEL_EDGE_THRESHOLDS[MODEL_ID])
            for d in got:
                diag[d.status] = diag.get(d.status, 0) + 1
                if d.status == "box_missing":
                    logger.error(f"NCAAB totals card: {d.game_id} held, {d.detail}. The ESPN box "
                                 f"feed fills ncaab_team_game_stats after each final; a game it "
                                 f"never filled keeps every game of these teams waiting.")
                elif d.status == "no_blend":
                    logger.error(f"NCAAB totals card: {d.game_id}: {d.detail}; the artifact is incomplete.")
            decisions += got
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            rows, refused = pick_rows(decisions, games, _get_current_bankroll(conn))
            published, n_decided = publish(conn, rows, decisions, hour, refused)
        logger.info("\n" + render(decisions, diag, published if do_publish else None,
                                  n_decided if do_publish else None))
        return {"games": len(games), "bets": diag["bets"], "published": published,
                "decided": n_decided, "diag": diag}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
