"""NCAABW totals card: write `ncaabw_total_blend` bets (models/ncaabw_total_blend.py).

LIVE, real money (mike, 2026-11-09: build the women's models from the men's
learnings). A fork of scripts/ncaab_total_card.py (2026-11-10), the men's
card, on the women's games, box scores and prices. Runs in its own job every
five minutes, three minutes after each women's odds capture tick
(scheduler.run_ncaabw_total_card), and writes picks only; the job then
publishes them like every other card. RUN_NCAABW_TOTAL_CARD=0 stops it before
it reads anything; the job keeps beating, so its silence still means stopped.

WHEN A GAME IS DECIDED. At DraftKings' FIRST POSTED full-game total: its
earliest pre-game totals row stored for the game, by DraftKings' own time on
the row (snapshot_at), with a total inside
models.ncaabw_total_blend.TOTAL_RANGE and both prices (a total outside it is a
feed error and is skipped, so the next row is the first post). The odds
capture (scripts/ncaabw_odds_capture.py) stores DraftKings' first total within
one five-minute poll, and this card runs three minutes after each poll, so a
game is decided minutes after DraftKings posts it. The evidence graded every
priced game at that quote (docs/sports/ncaabw.md "Research"). DraftKings'
first women's total stood a median 114 minutes in 2024-25 and 2025-26, and
one in ten changed within 10 minutes.

ONLY WHILE THE FIRST POST STANDS. The bet is placed at the first post's total
and prices only while that is still DraftKings' standing number (its newest
pre-game row stored within DK_MAX_AGE_MIN, same total, same two prices). When
it is not, the game is decided `first_post_gone`, with no bet: the research
graded the first post, and a number no longer on the board cannot be bet. It
is never decided at a later number instead.

AS OF THE QUOTE. The ratings, the games-played count and the shooting and style
inputs use only finals that had ENDED (tip + 2.5 h) at or before DraftKings'
own time on the first post, rounded down to the hour, as the evidence did.

A HOLD IS NOT A DECISION. When a team's earlier game ended before the first
post but its final score or either box score is not stored yet (the ESPN feed
fills them after each final, data/ingestors/ncaabw_espn_box.py), the game
waits and is looked at again on every run. When the box lands it is decided at
the same first post, as of the same hour, if that is still DraftKings'
standing number, and is `first_post_gone` if not. A box still missing
BOX_WAIT_H hours after its game ended (counted to now) stops holding, unless
a team is missing more than one. In the evidence no priced game of 2024-25 or
2025-26 had a team missing two earlier boxes at its quote, and one had a team
missing one.

TWO BOX SOURCES. This season's box rows come from the ESPN feed and from
NCAA's file (data/ingestors/ncaabw_sdv_import.py, step ncaabw-ncaa-box).
NCAA's rows for the current season carry no ESPN game id, so
models.ncaabw_total_blend.place_box puts every row on its game and keeps one
source per game, NCAA's where it holds the game.

THE WHOLE SEASON'S SCHEDULE MUST BE STORED. The model pools a team with
fewer than 10 games on this season's schedule into one "other" team, as the
evidence did on finished seasons. The daily schedule step stores 14 days
ahead, so a season whose schedule was never loaded whole shows every team
under 10 games in November and would price every game off the pooled team. A
due game with a Division I team under 10 stored games is not decided
(`schedule_short`) and fails the run; the fix is one command,
python -m data.ingestors.ncaabw_espn_ingestor --backfill <first> <last>.
This was caught on the first run against the stored tables (2026-11-10: 1,245
women's games stored to 2026-11-23, against the men's 6,009 to 2027-03-07).

A RUN THAT CANNOT DECIDE ITS GAMES FAILS. A due game skipped because the
artifact is for another season, held as schedule_short, held as box_missing (a team missing two or
more old boxes, which can hold it all season), missing its blend, or held as
edge_cap (an edge above the data-error cap, models/ncaabw_quote_bounds.py)
makes the run raise CardIncomplete AFTER every other game is decided and
written, so the script exits 1, the job's heartbeat records "error" and the
failure alerter reports it. It never stops quietly with the heartbeat green.

A FEED TYPO NEVER BECOMES A BET (models/ncaabw_quote_bounds.py). A total
outside 90-200 is never a first post (load_first_posts skips the row, so the
next row is the first post, the research's rule). A standing total outside it,
or a first post priced beyond +/-100000, makes the game wait: out_of_range,
not final, logged with its game, book and value and counted on the
diagnostic line; it is looked at again on the next run.

EACH GAME DECIDED ONCE (CLAUDE.md 1c). The decision, bet or not, is written to
ncaabw_total_decisions in the same transaction as the game's bet, under the
model's transaction-scoped advisory lock. A game with a decision row, or with
any ncaabw_total_blend BET, is never decided again: a later hour, a moved line
or a better price writes nothing.

A game priced below the cut is a NONE row (no stake) in the same
transaction, so the app's All board shows every scored game; nothing
publishes or settles a NONE row.
BET ROWS in picks, at DraftKings' own price on DraftKings' own number:
the evidence priced DraftKings and nothing else, so the line is not shopped.
dk_* and decision_* are that price; best_* is empty. Every bet is the flat
stake (stake_units is not written): one women's model, so there is no second
bet to agree with. The label is the platform's ("Duke vs Kansas Over 145.5"),
checked against the side and line before it is written
(tracking/pick_integrity.pick_problems).

The per-run diagnostic line counts every slate game by why it did or did not
bet.

    python -m scripts.ncaabw_total_card              # print the card, write nothing
    python -m scripts.ncaabw_total_card --publish    # write new decisions and bets
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import models.ncaabw_total_blend as nb  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = nb.MODEL_ID
SPORT = nb.SPORT
_ET = ZoneInfo("America/New_York")

# DraftKings' total counts as standing when its newest pre-game row was stored
# this recently. The refresh passes store every book's NCAABW total every hour
# and the capture job stores each change within five minutes, so a standing
# number is never more than about an hour old; an older one has been taken
# down, or the odds steps have stopped.
DK_MAX_AGE_MIN = 90

# How many Eastern dates past today the slate reads. DraftKings' first
# women's total came 1 to 6 Eastern dates before the game's date in 155 of the
# 1,772 priced games of 2024-25 to 2026-27 (8.7%), never more than 6, so a
# game is on the slate before its first post can land.
SLATE_DAYS = 7


def enabled() -> bool:
    """The kill switch: RUN_NCAABW_TOTAL_CARD=0 (or false/off/no). Default on."""
    return (os.environ.get("RUN_NCAABW_TOTAL_CARD", "1").strip().lower()
            not in ("0", "false", "off", "no"))


# ── the decisions ledger ─────────────────────────────────────────────────────
# One row per game the card has decided. Worker-only
# (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "ncaabw_total_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "check_hour", "quote_at", "cutoff", "total_line",
                  "model_total", "edge", "side", "n_bets", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS ncaabw_total_decisions (
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
    "INSERT INTO ncaabw_total_decisions (game_id, check_hour, quote_at, cutoff, total_line, "
    "model_total, edge, side, n_bets, detail) VALUES (%(game_id)s, %(check_hour)s, "
    "%(quote_at)s, %(cutoff)s, %(total_line)s, %(model_total)s, %(edge)s, %(side)s, "
    "%(n_bets)s, %(detail)s) ON CONFLICT (game_id) DO NOTHING RETURNING game_id")

# The decisions that end a game's wait; the rest are looked at again next run.
FINAL = ("bets", "below_cut", "first_post_gone")


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


def decided_games(conn, game_ids: list[str], bets: bool = True) -> set[str]:
    """Games with a decision row, or with any ncaabw_total_blend BET whatever
    became of it (settled, VOIDed): none is decided again. bets=False reads
    the ledger only (by its primary key), for the whole slate every run; the
    picks read is then made for the few games with a first post."""
    if not game_ids:
        return set()
    done: set[str] = set()
    if ledger_exists(conn):
        done = {r[0] for r in conn.execute(
            "SELECT game_id FROM ncaabw_total_decisions WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchall()}
    if not bets:
        return done
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
    """NCAABW games dated today through SLATE_DAYS ahead (Eastern) that have
    not tipped."""
    today = now.astimezone(_ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in range(SLATE_DAYS + 1)]
    rows = conn.execute("""
        SELECT game_id, season, game_date, commence_time, home_team, away_team
        FROM games WHERE sport = 'NCAABW' AND game_date = ANY(%s)
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
BOX_COLS = ["contest_id", "team", "game_date", "espn_game_id", "team_espn_id", "is_home",
            "home_espn_id", "away_espn_id", "season", *nb.BOX_STATS, "source"]


def load_season(conn, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, box) for one season: every scheduled game with ESPN's ids and
    status, and every stored box row from any source."""
    games = pd.DataFrame(conn.execute("""
        SELECT g.game_id, g.season, g.game_date, g.commence_time, g.home_score, g.away_score,
               COALESCE(g.neutral_site, CASE WHEN e.neutral_site THEN 1 ELSE 0 END),
               e.espn_event_id, e.home_espn_id, e.away_espn_id, e.status
        FROM games g
        LEFT JOIN ncaabw_events e ON e.game_id = g.game_id
        WHERE g.sport = 'NCAABW' AND g.season = %s
    """, (int(season),)).fetchall(), columns=SEASON_COLS)
    box = pd.DataFrame(conn.execute(f"""
        SELECT {', '.join(BOX_COLS)} FROM ncaabw_team_game_stats WHERE season = %s
    """, (int(season),)).fetchall(), columns=BOX_COLS)
    return games, box


def prepare_season(games: pd.DataFrame, box: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The season's games ready for the ratings (possessions, pooled ids,
    end times) and its box rows placed on their games, one source per game
    (models.ncaabw_total_blend.place_box)."""
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
    for c in ("team_espn_id", "home_espn_id", "away_espn_id"):
        b[c] = pd.to_numeric(b[c], errors="coerce")
    b = nb.place_box(b, g)
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


def d1_team_ids(conn) -> set[int]:
    """ESPN ids of the Division I teams (the registry's flag)."""
    return {int(r[0]) for r in conn.execute(
        "SELECT espn_id FROM ncaabw_teams WHERE is_d1").fetchall()}


def schedule_short(sg: pd.DataFrame, game_ids, d1: set[int]) -> dict[str, str]:
    """{game_id: why} for the games whose stored schedule cannot be the whole
    season: a Division I team with fewer than nb.SCHED_MIN games on it. Such a
    team would be pooled with the non-Division I sides and the game priced off
    the pooled rating (the module docstring)."""
    out = {}
    for r in sg[sg["game_id"].isin(set(game_ids))].itertuples(index=False):
        bad = [f"team {int(t)} has {int(n)} game(s) on the stored schedule"
               for t, n in ((r.home_espn_id, r.n_sched_home), (r.away_espn_id, r.n_sched_away))
               if pd.notna(t) and int(t) in d1 and int(n) < nb.SCHED_MIN]
        if bad:
            out[r.game_id] = "; ".join(bad)
    return out


def _quote_rows(rows, now: datetime, keep_bad_total: bool = False) -> dict[str, nb.Quote]:
    out = {}
    for gid, line, op, up, snap, created, lo, lu in rows:
        if line is None or implied(op) is None or implied(up) is None:
            continue
        if not keep_bad_total and not nb.valid_total(line):
            continue
        snap_t = _tip(snap) or _tip(created)
        out[gid] = nb.Quote(game_id=gid, line=float(line), over_price=float(op),
                            under_price=float(up), quote_at=min(snap_t, now),
                            fetched_at=_tip(created), link_over=lo, link_under=lu)
    return out


# A row is a usable total only with a number inside TOTAL_RANGE and both
# prices. The bound is applied BEFORE the first row is chosen, so a feed typo
# is skipped and the next row is the first post, as the evidence read it.
_USABLE = ("AND o.total_line IS NOT NULL AND o.over_price IS NOT NULL "
           "AND o.under_price IS NOT NULL "
           f"AND o.total_line::numeric BETWEEN {nb.TOTAL_RANGE[0]:g} AND {nb.TOTAL_RANGE[1]:g}")


def load_first_posts(conn, games: dict[str, dict], now: datetime) -> dict[str, nb.Quote]:
    """DraftKings' FIRST POSTED total per game: its earliest pre-game totals
    row stored at or before now, by DraftKings' own time on the row
    (snapshot_at; two rows with one stamp keep the one stored last, as the
    research's quote set did), with a total inside TOTAL_RANGE and both
    prices. One read, by game id (idx_odds_book_snap)."""
    if not games:
        return {}
    rows = conn.execute(f"""
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
          {_USABLE}
        ORDER BY o.game_id, o.snapshot_at::timestamptz ASC, o.created_at::timestamptz DESC
    """, (list(games), nb.BOOK, now.isoformat())).fetchall()
    return _quote_rows(rows, now)


def same_quote(a: nb.Quote | None, b: nb.Quote | None) -> bool:
    """The same total and the same two prices."""
    return (a is not None and b is not None and float(a.line) == float(b.line)
            and float(a.over_price) == float(b.over_price)
            and float(a.under_price) == float(b.under_price))


def load_quotes(conn, games: dict[str, dict], now: datetime) -> dict[str, nb.Quote]:
    """DraftKings' standing total per game: its newest pre-game totals row
    stored at or before now and within DK_MAX_AGE_MIN, with both prices. A
    total outside TOTAL_RANGE is returned as it is, so the card can see that
    the standing number is a feed error and wait, rather than read an older
    row or call the first post gone."""
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
    return _quote_rows(rows, now, keep_bad_total=True)


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


def _is_bet(row: dict | None) -> bool:
    return row is not None and row["signal_type"] == "BET"


# Priced, and its better side did not clear the cut: written as a NONE row.
SCORED_NO_BET = ("below_cut",)


def pick_rows(decisions: list[nb.Decision], games: dict[str, dict],
              bankroll: float) -> tuple[list[dict], dict[str, str]]:
    """Decisions -> picks rows, and {game_id: why} for a bet refused here.
    Pure given its inputs.

    A bet is a BET row. A game priced below the cut (SCORED_NO_BET), or a bet
    the price or EV floor refused, is a NONE row at the same book, side and
    line with no stake (the All board shows every scored pick, not only the
    bets). Nothing publishes or settles a NONE row."""
    from models.honest_ev import gate
    from models.scorer import _build_pick_label, _pause_note, quarter_kelly
    pause = _pause_note(MODEL_ID)
    floor = config.min_odds_for(MODEL_ID)
    rows, refused = [], {}
    for d in decisions:
        is_bet = d.status == "bets"
        if d.priced is None or d.quote is None or d.status not in ("bets",) + SCORED_NO_BET:
            continue
        pz, q = d.priced, d.quote
        g = games.get(d.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        if is_bet and floor is not None and pz.price < floor:
            refused[d.game_id] = f"below_price_floor:{pz.price:+.0f}"
            is_bet = False
        if is_bet:
            ev = gate(MODEL_ID, pz.prob, pz.price)
            if not ev.clears:
                logger.info(f"{MODEL_ID}: {ev.reason} - dropped {d.game_id} {pz.side}")
                refused[d.game_id] = ev.reason or "below_ev_floor"
                is_bet = False
        label = _build_pick_label(pz.side, home, away, nb.MARKET, float(q.line))
        problems = pick_problems(label, pz.side, float(q.line), MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {d.game_id} {label!r}: {'; '.join(problems)}")
            if d.game_id not in refused and is_bet:
                refused[d.game_id] = "label_mismatch"
            continue
        imp = implied(pz.price)
        edge = round(pz.prob - imp, 4)
        kelly_frac, rec_bet = quarter_kelly(pz.prob, imp, bankroll) if is_bet else (0.0, 0.0)
        link = q.link_over if pz.side == "over" else q.link_under
        rows.append({
            "game_id": d.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": pz.side, "pick_label": label,
            # P(win | no push) at DraftKings' line: the number the cut was
            # measured on (models/ncaabw_total_blend.py, THE PROBABILITY).
            "model_probability": round(pz.prob, 4),
            "model_probability_cal": round(pz.prob, 4),
            "dk_odds": pz.price, "dk_implied_prob": round(imp, 4), "edge": edge,
            "dk_bet_link": link, "line_book": None,
            "scored_line": float(q.line),
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll, "signal_type": "BET" if is_bet else "NONE",
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
    """Write each decided game once: its decision row and its pick (BET or
    NONE) in ONE
    transaction, under the model's lock, the ledger and the picks re-read
    inside it. check_hour is the run's instant (the ledger's column name is
    from the hourly rule); decided_at minus quote_at is the lag from the first
    post. -> (bets written, decisions written)."""
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
            "n_bets": 1 if _is_bet(row) else 0, "detail": detail}).fetchone()
        if not got:
            continue
        n_decided += 1
        if row is not None and conn.execute(_INSERT, row).fetchone():
            n_bets += row["signal_type"] == "BET"
    conn.commit()
    return n_bets, n_decided


# ── the run ───────────────────────────────────────────────────────────────────

class CardIncomplete(RuntimeError):
    """A due game the card could not decide for a reason that will not clear
    by itself: raised after the rest of the run is written."""


_ART: dict = {}


def artifact() -> dict:
    if "a" not in _ART:
        _ART["a"] = nb.load_artifact()
    return _ART["a"]


def first_post_gone(q: nb.Quote, standing: nb.Quote | None) -> nb.Decision:
    """The first post is no longer DraftKings' standing number: decided, no
    bet (the module docstring, ONLY WHILE THE FIRST POST STANDS)."""
    now_txt = ("no DraftKings total standing" if standing is None else
               f"standing {standing.line:g} {standing.over_price:+.0f}/{standing.under_price:+.0f}")
    return nb.Decision(q.game_id, "first_post_gone",
                       f"first post {q.line:g} {q.over_price:+.0f}/{q.under_price:+.0f} at "
                       f"{q.quote_at.isoformat()}; {now_txt}", quote=q)


def render(decisions: list[nb.Decision], diag: dict, written=None, decided=None) -> str:
    head = f"NCAABW totals card ({MODEL_ID}): " + " ".join(f"{k}={diag.get(k, 0)}" for k in nb.DIAG_KEYS)
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
        logger.info("NCAABW totals card: RUN_NCAABW_TOTAL_CARD is off; nothing read")
        return {"games": 0, "bets": 0, "published": 0, "decided": 0, "off": True}
    diag = dict.fromkeys(nb.DIAG_KEYS, 0)
    conn = get_connection()
    try:
        games = slate(conn, now)
        diag["games"] = len(games)
        # The ledger by primary key for the whole slate; the first-post read
        # for the games it has not decided; the picks read for the few of
        # those with a first post. Nothing heavier is read on a run where no
        # undecided game has a first post.
        done = decided_games(conn, sorted(games), bets=False)
        undecided = {g: v for g, v in games.items() if g not in done}
        firsts = load_first_posts(conn, undecided, now)
        bet_done = decided_games(conn, sorted(firsts)) if firsts else set()
        diag["already_decided"] = len(done) + len(bet_done)
        due = {g: v for g, v in undecided.items() if g in firsts and g not in bet_done}
        diag["no_dk_total"] = len(undecided) - len(firsts)
        if not due:
            logger.info(render([], diag))
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "diag": diag}
        if do_publish:
            ensure_decisions_table(conn)
        standing = load_quotes(conn, due, now)
        decisions: list[nb.Decision] = []
        live: dict[str, nb.Quote] = {}
        for g in sorted(due):
            q, now_q = firsts[g], standing.get(g)
            if now_q is not None and not nb.valid_total(now_q.line):
                # DraftKings' standing total is a feed error: whether the first
                # post still stands is unknown, so the game waits for the next
                # row, as a hold does. Neither bet nor gone.
                decisions.append(nb.Decision(
                    g, "out_of_range", f"{nb.BOOK} standing total {now_q.line:g} stamped "
                    f"{now_q.quote_at.isoformat()} is outside {nb.TOTAL_RANGE}: a feed error, waits",
                    quote=now_q))
                diag["out_of_range"] += 1
                logger.warning(f"NCAABW totals card: {g} waits, {decisions[-1].detail}")
                continue
            if same_quote(q, now_q):
                # the first post's number and stamp; the standing row's links
                live[g] = replace(q, link_over=now_q.link_over or q.link_over,
                                  link_under=now_q.link_under or q.link_under)
            else:
                decisions.append(first_post_gone(q, now_q))
                diag["first_post_gone"] += 1
        art = artifact() if live else None
        problems: list[str] = []          # why a due game was not decided; fails the run
        for season in sorted({due[g]["season"] for g in live}):
            gids = sorted(g for g in live if due[g]["season"] == season)
            if int(art["season"]) != season:
                msg = (f"the artifact is for season {art['season']}; season {season} needs one "
                       f"built through {season - 1} (scripts/ncaabw_total_blend_build.py). "
                       f"{len(gids)} game(s) not decided")
                logger.error(f"NCAABW totals card: {msg}.")
                diag["wrong_season"] += len(gids)
                problems.append(msg)
                continue
            games_df, box_df = load_season(conn, season)
            sg, box = prepare_season(games_df, box_df)
            short = schedule_short(sg, gids, d1_team_ids(conn))
            for g, why in sorted(short.items()):
                msg = (f"{g}: {why}; the season's schedule is not stored whole "
                       f"(python -m data.ingestors.ncaabw_espn_ingestor --backfill <first> <last>)")
                logger.error(f"NCAABW totals card: not decided, {msg}")
                decisions.append(nb.Decision(g, "schedule_short", why, quote=live[g]))
                diag["schedule_short"] += 1
                problems.append(f"schedule_short {msg}")
            gids = [g for g in gids if g not in short]
            targets = sg[sg["game_id"].isin(gids)]
            got = nb.decide(targets, {g: live[g] for g in gids}, sg, box, art,
                            config.MODEL_EDGE_THRESHOLDS[MODEL_ID], now=now) if gids else []
            for d in got:
                diag[d.status] = diag.get(d.status, 0) + 1
                if d.status == "box_missing":
                    logger.error(f"NCAABW totals card: {d.game_id} held, {d.detail}. The ESPN box "
                                 f"feed and NCAA's file fill ncaabw_team_game_stats; a game "
                                 f"neither filled keeps every game of these teams waiting.")
                    problems.append(f"box_missing {d.game_id} ({d.detail})")
                elif d.status == "no_blend":
                    logger.error(f"NCAABW totals card: {d.game_id}: {d.detail}; the artifact is incomplete.")
                    problems.append(f"no_blend {d.game_id} ({d.detail})")
                elif d.status == "out_of_range":
                    logger.warning(f"NCAABW totals card: dropped a data-error quote, {d.game_id} "
                                   f"{d.detail}")
                elif d.status == "edge_cap":
                    logger.error(f"NCAABW totals card: {d.game_id} not bet, its edge is a data "
                                 f"error: {d.detail}")
                    problems.append(f"edge_cap {d.game_id} ({d.detail})")
            decisions += got
        published = n_decided = 0
        if do_publish and decisions:
            from models.scorer import _get_current_bankroll
            rows, refused = pick_rows(decisions, games, _get_current_bankroll(conn))
            published, n_decided = publish(conn, rows, decisions, now, refused)
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
        # exit 1: scheduler.run_ncaabw_total_card then raises, so the job's
        # heartbeat records "error" and the failure alerter reports it.
        logger.error(f"NCAABW totals card did not decide every due game: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). The card reads the
    # database only; installed so the scheduler runs no uninstrumented script.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaabw-total-card")
    except Exception:  # noqa: BLE001
        pass
    main()
