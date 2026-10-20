"""NBA projection card: project, price and write `nba_prop_projection` bets (models/nba_prop_projection.py).

TWO STEPS, because the frame takes a minute or more and the decision must not
wait for it.

  --project G1 G2 ...   (the window job, at the tick ~60 minutes before tip)
      Reads the worker's inputs (every box line since 2018-19, the schedule,
      the stored injury status of every past game, and the newest ESPN pull),
      builds the frame for tonight's rosters, and stores each player's
      projected mean per card market in nba_prop_projections. It stores the
      ESPN statuses it used in nba_injury_asof, so tonight's game is a past
      game with known injuries tomorrow.

  --publish            (the window job, right after nba_prop_market's card)
      Prices the stored projections against the game's newest prop fetch from
      inside the decision window, and writes each decided game once -- its
      ledger row (nba_prop_projection_decisions) and its bets in one
      transaction, under the model's lock.

FULL HISTORY, NOT RECENT SEASONS. The frame is built from every season since
2018-19, as it was graded. Built from 2022-23 on instead, the projected mean
moved by under 1% for the typical player but by 5-7% for one in a hundred,
enough to flip a bet at the margin (measured 2026-10-16 on 2025-26).

THE INJURY HISTORY. A past game's teammate-absence inputs need the injury
list as it stood at that game's decision. nba_injury_asof holds it, small:
one COVERED row per game that had a report, and the Out / Day-To-Day rows of
each team's report. 2018-19..2025-26 come from the official league report
(the graded source, collapsed to the two ESPN statuses; written once by
--backfill-official); 2026-27 games from the ESPN pull each projection used,
or, for a game never projected, the newest ESPN pull 55 minutes or more
before its tip.

BET ROWS ONLY in picks, as nba_prop_market: a decision with no bet lives in
the ledger, and the per-look diagnostic line is how an empty card is told
apart from a broken one.

    python -m scripts.nba_prop_projection_card                     # print the card, write nothing
    python -m scripts.nba_prop_projection_card --project G1 G2     # project these games and store it
    python -m scripts.nba_prop_projection_card --publish           # write new decisions and bets
    python -m scripts.nba_prop_projection_card --backfill-official # the 2018-19..2025-26 injury history
"""
from __future__ import annotations

import argparse
import bisect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_prop_projection as pj  # noqa: E402
import models.nba_props as nb  # noqa: E402
import scripts.nba_prop_market_card as rule_card  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from models.nba_prop_market import DECISION_WINDOW_MIN, minutes_to_tip, parse_ts  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = pj.MODEL_ID
SPORT = pj.SPORT
RULE_ID = "nba_prop_market"
_ET = ZoneInfo("America/New_York")

# A game is projected at the window job's tick 63-67 minutes before its tip
# (65 for any tip on a five-minute mark), two ticks before its decision at 55.
# Measured 2026-10-16 from this machine against production: 139 seconds to read
# every input and project three games. Projected at 60, a slow frame could hold
# the job past the decision tick, which max_instances=1 would then skip. A game
# 45-62 minutes out with no projection at all is projected at once (a failed or
# missed tick).
PROJECT_AHEAD_MIN = (63, 67)
# A projection younger than this is not recomputed on the next tick.
PROJECTION_FRESH_MIN = 8
# The card prices a projection no older than this; older is no projection.
PROJECTION_MAX_AGE_MIN = 30
# The newest ESPN pull a past game's injuries are read from: at least this
# long before its tip (the graded decision sat 54 minutes before tip).
ESPN_HISTORY_LEAD_MIN = 55
# A projection built on an ESPN pull older than this logs a warning: the window
# job pulls right before projecting, so an old pull means that pull failed.
INJURY_PULL_WARN_MIN = 30
FIRST_SEASON_LIVE = 2027           # 2026-27: injuries from ESPN, not the official report

# ── the tables (worker-only: data/anon_readable.WORKER_ONLY_TABLES) ───────────

DECISIONS_TABLE = "nba_prop_projection_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "projected_at", "n_quotes", "n_bets", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_prop_projection_decisions (
    game_id       TEXT PRIMARY KEY,
    decided_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at      TEXT NOT NULL,
    projected_at  TEXT,
    n_quotes      INTEGER NOT NULL,
    n_bets        INTEGER NOT NULL,
    detail        TEXT
)
"""
PROJECTIONS_TABLE = "nba_prop_projections"
PROJECTIONS_COLS = ("game_id", "player_id", "market", "player_name", "team", "status", "min_hat",
                    "mu", "projected_at", "injuries_at", "artifact_version")
PROJECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_prop_projections (
    game_id           TEXT NOT NULL,
    player_id         TEXT NOT NULL,
    market            TEXT NOT NULL,
    player_name       TEXT,
    team              TEXT,
    status            TEXT,
    min_hat           DOUBLE PRECISION,
    mu                DOUBLE PRECISION NOT NULL,
    projected_at      TEXT NOT NULL,
    injuries_at       TEXT,
    artifact_version  TEXT,
    PRIMARY KEY (game_id, player_id, market)
)
"""
ASOF_TABLE = "nba_injury_asof"
ASOF_COLS = ("game_id", "team", "report_ts", "player_id", "player_name", "status", "source")
ASOF_DDL = """
CREATE TABLE IF NOT EXISTS nba_injury_asof (
    game_id      TEXT NOT NULL,
    team         TEXT NOT NULL,
    report_ts    TIMESTAMPTZ NOT NULL,
    player_id    TEXT,
    player_name  TEXT NOT NULL,
    status       TEXT NOT NULL,
    source       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nba_injury_asof_game ON nba_injury_asof (game_id)
"""


def ensure_tables(conn) -> None:
    """Create the three tables once, locked down; nothing after that (data/ddl_guard)."""
    for name, cols, ddl in ((DECISIONS_TABLE, DECISIONS_COLS, DECISIONS_DDL),
                            (PROJECTIONS_TABLE, PROJECTIONS_COLS, PROJECTIONS_DDL),
                            (ASOF_TABLE, ASOF_COLS, ASOF_DDL)):
        if schema_is_current(conn, name, columns=cols, rls=True, revoked_from=API_ROLES):
            continue
        for stmt in ddl.split(";"):
            if stmt.strip():
                conn.execute(stmt)
        lock_down(conn, name)
        conn.commit()


def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    raw = getattr(cur, "_cur", cur)
    return pd.DataFrame(rows, columns=[d[0] for d in raw.description])


# ── the worker's inputs ───────────────────────────────────────────────────────

LOG_COLS = ("game_id", "player_id", "player_name", "team", "season", "game_date", "minutes", "is_starter",
            "points", "rebounds", "offensive_reb", "defensive_reb", "assists", "steals", "blocks",
            "turnovers", "fg_made", "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att")


def load_history(conn) -> dict:
    """Every input the frame reads that is not tonight's: games, schedule, box lines, injury history."""
    games = _frame(conn, """
        SELECT game_id, season, game_date, home_team, away_team, commence_time
        FROM games WHERE sport = 'NBA' AND season >= %s
    """, (nb.FIRST_TRAIN_SEASON,))
    # season and game_date: models.nba_props.regular_game_ids dates a game the schedule does not list
    schedule = _frame(conn, "SELECT game_id, season, game_date, game_type, commence_time FROM nba_schedule")
    log = _frame(conn, f"SELECT {', '.join(LOG_COLS)} FROM nba_player_game_log WHERE season >= %s",
                 (nb.FIRST_TRAIN_SEASON,))
    for c in LOG_COLS[6:]:
        log[c] = pd.to_numeric(log[c], errors="coerce")
    log["player_id"] = log.player_id.astype(str)
    asof = _frame(conn, f"SELECT {', '.join(ASOF_COLS)} FROM {ASOF_TABLE}")
    asof["report_ts"] = pd.to_datetime(asof.report_ts, utc=True)
    games["season"] = games.season.astype(int)
    return {"games": games, "schedule": schedule, "log": log, "asof": asof}


def history_decisions(games: pd.DataFrame, asof: pd.DataFrame) -> pd.DataFrame:
    """A past game's decision time: the newest stored injury row's time where one is stored (every
    stored row is at or before the decision it was read for), else tip minus an hour."""
    tip = nb._utc(games.set_index("game_id").commence_time)
    dec = (tip - pd.Timedelta(minutes=nb.DECISION_LEAD_MIN)).rename("decision_ts")
    stored = asof.groupby("game_id").report_ts.max()
    dec.loc[stored.index.intersection(dec.index)] = stored.reindex(dec.index).dropna()
    return dec.reset_index()


def pull_time(raw) -> datetime | None:
    """A stored injuries.created_at ('2026-10-16 12:17:30.660504+00', TEXT) as aware UTC. pandas,
    not datetime.fromisoformat: a bare '+00' offset only parses there from Python 3.11."""
    try:
        t = pd.Timestamp(str(raw))
    except (ValueError, TypeError):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.to_pydatetime()


def espn_pulls(conn, since: str) -> list[str]:
    """When each NBA ESPN injuries pull since `since` (a date) was taken, as stored (TEXT)."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT created_at FROM injuries WHERE sport = 'NBA' AND report_date >= %s",
        (since,)).fetchall() if r[0]]


def espn_rows(conn, pulls: list[str]) -> pd.DataFrame:
    if not pulls:
        return pd.DataFrame(columns=["team", "player_name", "status", "created_at"])
    return _frame(conn, """
        SELECT team, player_name, status, created_at FROM injuries
        WHERE sport = 'NBA' AND created_at = ANY(%s)
    """, (list(pulls),))


def _game_teams(games: pd.DataFrame, game_ids) -> pd.DataFrame:
    g = games[games.game_id.isin(set(game_ids))]
    return pd.concat([g[["game_id", "home_team"]].rename(columns={"home_team": "team"}),
                      g[["game_id", "away_team"]].rename(columns={"away_team": "team"})], ignore_index=True)


def write_asof(conn, rows: pd.DataFrame, source: str) -> int:
    """Replace the stored injury rows of every game in `rows` with these."""
    if rows.empty:
        return 0
    gids = sorted(rows.game_id.unique())
    conn.execute(f"DELETE FROM {ASOF_TABLE} WHERE game_id = ANY(%s)", (gids,))
    recs = [{"game_id": r.game_id, "team": r.team or "", "report_ts": pd.Timestamp(r.report_ts).isoformat(),
             "player_id": None if pd.isna(r.player_id) else str(r.player_id),
             "player_name": r.player_name or "", "status": r.status, "source": source}
            for r in rows.itertuples()]
    conn.executemany(
        f"INSERT INTO {ASOF_TABLE} ({', '.join(ASOF_COLS)}) VALUES "
        f"({', '.join('%(' + c + ')s' for c in ASOF_COLS)})", recs)
    return len(recs)


def fill_espn_history(conn, hist: dict) -> int:
    """Store injuries for every played 2026-27 game that has none: the newest ESPN pull at least
    ESPN_HISTORY_LEAD_MIN before its tip. A game a projection ran for already has its own."""
    games, asof, log = hist["games"], hist["asof"], hist["log"]
    played = set(log[log.season >= FIRST_SEASON_LIVE].game_id)
    need = sorted(played - set(asof.game_id))
    if not need:
        return 0
    g = games[games.game_id.isin(need)].copy()
    g["tip"] = nb._utc(g.commence_time)
    pulls = sorted({t: p for p in espn_pulls(conn, str(g.game_date.min())[:10])
                    if (t := pull_time(p)) is not None}.items())
    if not pulls:
        return 0
    when = [p[0] for p in pulls]
    chosen = {}
    for r in g.itertuples():
        cut = r.tip.to_pydatetime() - timedelta(minutes=ESPN_HISTORY_LEAD_MIN)
        i = bisect.bisect_right(when, cut) - 1
        if i >= 0:
            chosen[r.game_id] = pulls[i]
    rows = espn_rows(conn, sorted({v[1] for v in chosen.values()}))
    out = []
    for gid, (ts, raw_ts) in chosen.items():
        pull = rows[rows.created_at == raw_ts]
        out.append(pj.espn_compact(pull, ts, _game_teams(games, [gid])))
    if not out:
        return 0
    new = pd.concat(out, ignore_index=True)
    n = write_asof(conn, new, "espn")
    conn.commit()
    hist["asof"] = pd.concat([asof, new.assign(source="espn")], ignore_index=True)
    logger.info(f"nba-prop-projection: stored the ESPN injury list of {len(chosen)} past game(s) ({n} rows)")
    return n


# ── projecting ────────────────────────────────────────────────────────────────

def roster_candidates(log: pd.DataFrame, games: pd.DataFrame, game_ids) -> pd.DataFrame:
    """Everyone logged for either team this season or last, per game: the names a book's spelling
    is matched against (the research's rule), each placed on the side he last played for."""
    g = games[games.game_id.isin(set(game_ids))]
    out = []
    for r in g.itertuples():
        seasons = (int(r.season), int(r.season) - 1)
        lg = log[log.team.isin([r.home_team, r.away_team]) & log.season.isin(seasons)]
        lg = lg.sort_values("game_date").drop_duplicates("player_id", keep="last")
        out.append(lg[["player_id", "player_name", "team"]].assign(game_id=r.game_id))
    if not out:
        return pd.DataFrame(columns=["game_id", "player_id", "player_name", "team"])
    return pd.concat(out, ignore_index=True)


def priced_names(conn, game_ids) -> pd.DataFrame:
    """The players any book prices in these games, from each game's newest pre-game fetch."""
    return _frame(conn, """
        SELECT DISTINCT p.game_id, p.player_name FROM player_prop_odds p
        JOIN (SELECT game_id, max(snapshot_at) AS s FROM player_prop_odds
              WHERE game_id = ANY(%s) AND snapshot_type = 'open' GROUP BY game_id) n
          ON n.game_id = p.game_id AND n.s = p.snapshot_at
        WHERE p.market = ANY(%s)
    """, (list(game_ids), list(pj.MARKETS)))


def upcoming_rows(hist: dict, box: pd.DataFrame, report: pd.DataFrame, decisions: pd.DataFrame,
                  game_ids, priced: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Tonight's rows to project: the pre-game roster (models.nba_prop_projection.asof_roster) and
    every player a book prices, each on his side of the game. -> (rows, counts)."""
    games = hist["games"]
    ros = pj.asof_roster(box, games, report, decisions, game_ids)
    cand = roster_candidates(hist["log"], games, game_ids)
    m = nb.match_names(priced[["game_id", "player_name"]].drop_duplicates(), cand) if len(priced) else \
        pd.DataFrame(columns=["game_id", "player_name", "player_id", "how"])
    counts = {"priced_names": int(len(m)), "matched": int(m.player_id.notna().sum()),
              "refused_shared": int((m.how == "shared").sum()), "unmatched": int((m.how == "none").sum())}
    team_of = cand.drop_duplicates(["game_id", "player_id"]).set_index(["game_id", "player_id"]).team
    got = m.dropna(subset=["player_id"])[["game_id", "player_id"]].drop_duplicates()
    got["team"] = [team_of.get((g, p)) for g, p in zip(got.game_id, got.player_id)]
    who = pd.concat([ros[["game_id", "team", "player_id"]], got], ignore_index=True)
    who = who.dropna(subset=["team"]).drop_duplicates(["game_id", "player_id"])
    g = games.set_index("game_id")
    names = hist["log"].sort_values("game_date").drop_duplicates("player_id", keep="last") \
        .set_index("player_id").player_name
    home = who.game_id.map(g.home_team)
    up = pd.DataFrame({
        "game_id": who.game_id.values, "player_id": who.player_id.astype(str).values,
        "player_name": who.player_id.map(names).values, "team": who.team.values,
        "opponent": np.where(who.team == home, who.game_id.map(g.away_team), home),
        "is_home": (who.team == home).values, "season": who.game_id.map(g.season).values,
        "game_date": who.game_id.map(g.game_date).values})
    counts["roster"] = int(len(ros))
    counts["rows"] = int(len(up))
    return up, counts


def project_core(hist: dict, tonight: pd.DataFrame, game_ids: list[str], now: datetime,
                 priced: pd.DataFrame, art: dict) -> tuple[pd.DataFrame, dict]:
    """The projection, from inputs already read. Pure: no database, so a past night can be replayed
    from the research cache through exactly this code (tests/test_nba_prop_projection_replay.py).

    `hist`: games, schedule, log (box lines strictly before tonight), asof (stored injury rows);
    `tonight`: tonight's compact injury rows; `priced`: game_id, player_name a book prices.
    -> (one row per projected player: game_id, player_id, player_name, team, status, min_hat,
    mu_<market>; counts).
    """
    games = hist["games"]
    asof = hist["asof"][~hist["asof"].game_id.isin(game_ids)]
    report = pd.concat([asof.drop(columns=["source"], errors="ignore"), tonight], ignore_index=True)
    report["report_ts"] = pd.to_datetime(report.report_ts, utc=True)
    decisions = history_decisions(games[~games.game_id.isin(game_ids)], asof)
    decisions = pd.concat([decisions, pd.DataFrame({"game_id": list(game_ids),
                                                    "decision_ts": pd.Timestamp(now)})], ignore_index=True)
    data = pj.worker_data(games, hist["schedule"], hist["log"], report, decisions)
    up, counts = upcoming_rows(hist, data["nba_player_game_adv"], report, decisions, game_ids, priced)
    if up.empty:
        return pd.DataFrame(), counts
    fr = nb.build_frame(data, decisions, upcoming=up, with_lines=False)
    rows = fr[fr.upcoming & nb.usable(fr)].copy()
    means = pj.predict_means(art, rows)
    out = pd.concat([rows[["game_id", "player_id", "player_name", "team", "status"]], means], axis=1)
    counts["projected"] = int(len(out))
    counts["out"] = int((out.status == "Out").sum())
    return out.reset_index(drop=True), counts


def project(conn, game_ids: list[str], now: datetime, art: dict) -> pd.DataFrame:
    """Project tonight's players in `game_ids` and store it. -> the stored rows."""
    ensure_tables(conn)
    hist = load_history(conn)
    fill_espn_history(conn, hist)
    games = hist["games"]
    # tonight's injuries: the newest ESPN pull at or before now
    today = now.astimezone(_ET).date()
    pulls = sorted(((pull_time(p), p) for p in espn_pulls(conn, (today - timedelta(days=1)).isoformat())),
                   key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc))
    pulls = [p for p in pulls if p[0] is not None and p[0] <= now]
    if pulls:
        pull_ts, raw_ts = pulls[-1]
        tonight = pj.espn_compact(espn_rows(conn, [raw_ts]), pull_ts, _game_teams(games, game_ids))
        age = (now - pull_ts).total_seconds() / 60
        if age > INJURY_PULL_WARN_MIN:
            # Projected anyway: an older list beats none (reports read 60 minutes
            # late still graded +3.57%, docs/nba_models_2026.md section 5), and the
            # window's own pull runs right before this. The age is stored with the
            # projection (injuries_at) and said here so a failing pull is seen.
            logger.warning(f"nba-prop-projection: the newest ESPN injury pull is {age:.0f} minutes "
                           f"old ({pull_ts.isoformat()}); projecting {game_ids} on it")
    else:
        pull_ts, tonight = None, pd.DataFrame(columns=list(ASOF_COLS[:-1]))
        logger.warning("nba-prop-projection: no ESPN injury pull today; tonight's games are uncovered")
    rows, counts = project_core(hist, tonight, game_ids, now, priced_names(conn, game_ids), art)
    if rows.empty:
        logger.warning(f"nba-prop-projection: nobody to project for {game_ids} ({counts})")
        return pd.DataFrame()
    stamp = now.astimezone(timezone.utc).isoformat()
    long = []
    for m in pj.MARKETS:
        long.append(rows.assign(market=m, mu=rows[f"mu_{m}"])[
            ["game_id", "player_id", "market", "player_name", "team", "status", "min_hat", "mu"]])
    out = pd.concat(long, ignore_index=True)
    out["projected_at"], out["injuries_at"] = stamp, pull_ts.isoformat() if pull_ts else None
    out["artifact_version"] = str(art.get("version"))
    conn.execute(f"DELETE FROM {PROJECTIONS_TABLE} WHERE game_id = ANY(%s)", (list(game_ids),))
    recs = [{c: (None if (isinstance(v, float) and np.isnan(v)) else v) for c, v in zip(PROJECTIONS_COLS, r)}
            for r in out[list(PROJECTIONS_COLS)].itertuples(index=False)]
    conn.executemany(f"INSERT INTO {PROJECTIONS_TABLE} ({', '.join(PROJECTIONS_COLS)}) VALUES "
                     f"({', '.join('%(' + c + ')s' for c in PROJECTIONS_COLS)})", recs)
    write_asof(conn, tonight, "espn")
    conn.commit()
    logger.info(f"nba-prop-projection: projected {game_ids} at {stamp} "
                f"(ESPN pull {pull_ts.isoformat() if pull_ts else 'none'}): {counts}")
    return out


def to_project(conn, now: datetime) -> list[str]:
    """Games PROJECT_AHEAD_MIN from tip, not yet decided, with no fresh projection; and any game
    closer than that, down to the window's near end, with no projection at all (a missed tick)."""
    ensure_tables(conn)
    games = rule_card.slate(conn, now, horizon_min=PROJECT_AHEAD_MIN[1])
    near = sorted(g for g, v in games.items()
                  if minutes_to_tip(v["tip"], now) >= DECISION_WINDOW_MIN[0])
    if not near:
        return []
    near = [g for g in near if g not in decided_games(conn, near)]
    last = dict(conn.execute(
        f"SELECT game_id, max(projected_at) FROM {PROJECTIONS_TABLE} WHERE game_id = ANY(%s) GROUP BY game_id",
        (near,)).fetchall()) if near else {}
    out = []
    for gid in near:
        lead = minutes_to_tip(games[gid]["tip"], now)
        t = parse_ts(last.get(gid))
        if lead >= PROJECT_AHEAD_MIN[0]:
            if t is None or (now - t) > timedelta(minutes=PROJECTION_FRESH_MIN):
                out.append(gid)
        elif t is None or (now - t) > timedelta(minutes=PROJECTION_MAX_AGE_MIN):
            # closer than the projecting tick with nothing the card may price: the
            # projecting tick failed or never ran, or the only row is too old to
            # use (load_projections). Project now; the next tick decides.
            out.append(gid)
    return out


# ── pricing ───────────────────────────────────────────────────────────────────

def decided_games(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)", (list(game_ids),)).fetchall()}


def rule_state(conn, game_ids: list[str]) -> tuple[set[str], set[tuple[str, str, str]]]:
    """Games nba_prop_market has decided, and every (game, player, market) it holds a BET on."""
    if not game_ids:
        return set(), set()
    decided = rule_card.decided_games(conn, list(game_ids))
    keys = {(g, str(p), m) for g, p, m in conn.execute("""
        SELECT game_id, player_id, prop_market FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (RULE_ID, list(game_ids))).fetchall()}
    return decided, keys


def load_projections(conn, game_ids: list[str], now: datetime) -> pd.DataFrame:
    if not game_ids:
        return pd.DataFrame()
    p = _frame(conn, f"""
        SELECT game_id, player_id, market, status, mu, projected_at FROM {PROJECTIONS_TABLE}
        WHERE game_id = ANY(%s)
    """, (list(game_ids),))
    if p.empty:
        return p
    age = now - pd.to_datetime(p.projected_at, utc=True)
    p = p[age <= pd.Timedelta(minutes=PROJECTION_MAX_AGE_MIN)]
    if p.empty:
        return p
    wide = p.pivot_table(index=["game_id", "player_id"], columns="market", values="mu", aggfunc="first")
    wide.columns = [f"mu_{c}" for c in wide.columns]
    meta = p.drop_duplicates(["game_id", "player_id"]).set_index(["game_id", "player_id"])[["status", "projected_at"]]
    return wide.join(meta).reset_index()


QUOTE_COLS = ("game_id", "player", "market", "book", "line", "over_price", "under_price", "over_link",
              "under_link", "snapshot_at", "book_last_update")


def load_quotes(conn, games: dict[str, dict], books: tuple[str, ...]) -> list[dict]:
    """The card markets' pre-game rows at the bettable books, from just before each window opened,
    each player resolved to an id by the research's name rule (None where refused)."""
    if not games:
        return []
    earliest = min(g["tip"] for g in games.values())
    lower = earliest - timedelta(minutes=DECISION_WINDOW_MIN[1] + 5)
    rows = conn.execute("""
        SELECT game_id, player_name, market, bookmaker, line, over_price, under_price, over_link,
               under_link, snapshot_at, book_last_update
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND market = ANY(%s) AND bookmaker = ANY(%s)
          AND snapshot_type = 'open' AND snapshot_at >= %s
    """, (list(games), list(pj.MARKETS), list(books), lower.astimezone(timezone.utc).isoformat())).fetchall()
    out = [dict(zip(QUOTE_COLS, r)) for r in rows]
    for q in out:
        for k in ("line", "over_price", "under_price"):
            if q[k] is not None:
                q[k] = float(q[k])
    return out


def resolve_players(quotes: list[dict], cand: pd.DataFrame) -> dict:
    """player_id onto each quote; returns the match counts."""
    if not quotes:
        return {}
    priced = pd.DataFrame({"game_id": [q["game_id"] for q in quotes],
                           "player_name": [q["player"] for q in quotes]}).drop_duplicates()
    m = nb.match_names(priced, cand).set_index(["game_id", "player_name"])
    for q in quotes:
        pid = m.player_id.get((q["game_id"], q["player"]))
        q["player_id"] = None if pid is None or (isinstance(pid, float) and np.isnan(pid)) else str(pid)
    return m.how.value_counts().to_dict()


def pick_label(b: pj.ProjectionBet) -> str:
    return f"{b.player} {b.side.capitalize()} {b.line:g} {pj.MARKET_LABEL[b.market]}"


def pick_rows(bets: list[pj.ProjectionBet], bankroll: float) -> list[dict]:
    """Card bets -> picks rows (scripts/nba_prop_market_card.pick_rows's shape, either side)."""
    rows = []
    for b in bets:
        label = pick_label(b)
        problems = pick_problems(label, b.side, b.line, MODEL_ID, prop_market=b.market)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.prob - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == "draftkings"
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": b.game_date, "game_time": b.tip,
            "pick_side": b.side, "pick_label": label,
            # the calibrated probability IS the model's own (config.MODELS_ON_OWN_PROBABILITY)
            "model_probability": round(b.prob, 4), "model_probability_cal": round(b.prob, 4),
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.prob - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": b.line,
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET", "confidence_tier": "MED",
            "prop_market": b.market, "player_key": b.player, "player_id": str(b.player_id),
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4), "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book, "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
        })
    return rows


_COLS = rule_card._COLS
_INSERT = rule_card._INSERT
_INSERT_DECISION = (
    f"INSERT INTO {DECISIONS_TABLE} (game_id, fetch_at, projected_at, n_quotes, n_bets, detail) "
    "VALUES (%(game_id)s, %(fetch_at)s, %(projected_at)s, %(n_quotes)s, %(n_bets)s, %(detail)s) "
    "ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def publish(conn, rows: list[dict], decisions: list[dict]) -> tuple[int, int]:
    """Each decided game once -- its ledger row and its bets in ONE transaction, under the model's
    lock, the ledger and nba_prop_market's holdings re-read inside it. -> (bets, decisions)."""
    if not decisions:
        return 0, 0
    from scripts.nfl_wind_publisher import _lock_model
    # nba_prop_market's lock FIRST, then this model's own. The two cards each read the other's
    # holdings before writing; holding the rule's lock serializes this write with the rule's, so
    # the decide-alone path (DECIDE_ALONE_BY_MIN) and a late rule decision cannot both bet one
    # proposition. The rule's card never takes this model's lock, so the order cannot deadlock.
    _lock_model(conn, RULE_ID)
    _lock_model(conn, MODEL_ID)
    gids = sorted({d["game_id"] for d in decisions})
    done = decided_games(conn, gids)
    _, held = rule_state(conn, gids)
    by_game: dict[str, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["game_id"], []).append(r)
    n_bets = n_decided = n_held = 0
    for d in sorted(decisions, key=lambda x: x["game_id"]):
        if d["game_id"] in done:
            continue
        game_rows = [r for r in by_game.get(d["game_id"], [])
                     if (r["game_id"], r["player_id"], r["prop_market"]) not in held]
        n_held += len(by_game.get(d["game_id"], [])) - len(game_rows)
        got = conn.execute(_INSERT_DECISION, {**d, "n_bets": len(game_rows)}).fetchone()
        if not got:
            continue
        n_decided += 1
        for r in game_rows:
            if conn.execute(_INSERT, {c: r[c] for c in _COLS}).fetchone():
                n_bets += 1
    conn.commit()
    logger.info(f"nba-prop-projection: {n_decided} game(s) decided, {n_bets} bet(s) written of "
                f"{len(rows)} on the card; {n_held} skipped as nba_prop_market's; {len(done)} already decided")
    return n_bets, n_decided


def render(bets, diag: dict, written=None, decided=None) -> str:
    head = f"NBA projection card ({MODEL_ID}): " + " ".join(f"{k}={diag.get(k, 0)}" for k in pj.DIAG_KEYS)
    if decided is not None:
        head += f" decisions_written={decided}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in sorted(bets, key=lambda x: -x.ev):
        lines.append(f"  {b.game_id:26s} {pick_label(b)} @{b.book} {b.price:+.0f}  p {b.prob:.4f}  "
                     f"EV {b.ev:+.4f}  mu {b.mu:.2f}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None, art: dict | None = None) -> dict:
    import config
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        games = rule_card.slate(conn, now)
        if not games:
            diag = dict.fromkeys(pj.DIAG_KEYS, 0)
            logger.info(render([], diag, 0 if do_publish else None) +
                        f" (no NBA game tips in the next {DECISION_WINDOW_MIN[1]} minutes)")
            return {"games": 0, "bets": 0, "published": 0, "decided": 0, "diag": diag}
        ensure_tables(conn)
        gids = sorted(games)
        decided = decided_games(conn, gids)
        rule_decided, rule_keys = rule_state(conn, gids)
        open_ = [g for g in gids if g not in decided]
        books = tuple(config.BEST_LINE_BOOKMAKERS)
        quotes = load_quotes(conn, {g: games[g] for g in open_}, books)
        hist_log = _frame(conn, f"""
            SELECT player_id, player_name, team, season, game_date FROM nba_player_game_log
            WHERE team = ANY(%s) AND season = ANY(%s)
        """, (sorted({t for g in open_ for t in (games[g]["home"], games[g]["away"])}),
              sorted({s for g in open_ for s in (games[g]["season"], games[g]["season"] - 1)}))) \
            if open_ else pd.DataFrame(columns=["player_id", "player_name", "team", "season", "game_date"])
        hist_log["player_id"] = hist_log.player_id.astype(str)
        gdf = pd.DataFrame([{"game_id": g, "season": games[g]["season"], "home_team": games[g]["home"],
                             "away_team": games[g]["away"]} for g in open_])
        how = resolve_players(quotes, roster_candidates(hist_log, gdf, open_)) if open_ else {}
        proj = load_projections(conn, open_, now)
        if art is None:
            from models.trainer import load_model
            art = load_model(MODEL_ID)
        if art is None:
            logger.error(f"nba-prop-projection: no active {MODEL_ID} artifact; nothing priced")
            return {"games": len(games), "bets": 0, "published": 0, "decided": 0, "diag": {}}
        bets, diag, decisions = pj.find_bets(
            quotes, proj, games, now, art, rule_keys, decided, rule_decided, books,
            price_floor=float(config.min_odds_for(MODEL_ID)))
        projected_at = dict(zip(proj.game_id, proj.projected_at)) if len(proj) else {}
        for d in decisions:
            d["projected_at"] = projected_at.get(d["game_id"])
        for gid in open_:
            lead = minutes_to_tip(games[gid]["tip"], now)
            if lead < DECISION_WINDOW_MIN[0]:
                logger.warning(f"nba-prop-projection: {gid} tips in {lead:.0f} min and was never decided")
        published = n_decided = 0
        if do_publish and decisions:
            rows: list[dict] = []
            if bets:
                from models.scorer import _get_current_bankroll
                rows = pick_rows(bets, _get_current_bankroll(conn))
            published, n_decided = publish(conn, rows, decisions)
        logger.info("\n" + render(bets, diag, published if do_publish else None,
                                   n_decided if do_publish else None) + f" names={how}")
        return {"games": len(games), "bets": len(bets), "published": published, "decided": n_decided,
                "diag": diag}
    finally:
        conn.close()


def run_project(game_ids: list[str] | None = None, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        gids = game_ids or to_project(conn, now)
        if not gids:
            logger.info("nba-prop-projection: nothing to project")
            return 0
        from models.trainer import load_model
        art = load_model(MODEL_ID)
        if art is None:
            logger.error(f"nba-prop-projection: no active {MODEL_ID} artifact; nothing projected")
            return 0
        out = project(conn, list(gids), now, art)
        return int(out.player_id.nunique()) if len(out) else 0
    finally:
        conn.close()


def backfill_official(cache: str) -> int:
    """The 2018-19..2025-26 injury history from the official report, as graded (research decisions)."""
    raw = nb.load_cache(cache, with_props=True, with_lines=False)
    props = raw["nba_props"]
    decisions = nb.decisions_for(raw, props[props.game_date < "2026-10-20"])
    rows = pj.compact_report(pj.collapse_official(raw["nba_injury_report"]), decisions)
    conn = get_connection()
    try:
        ensure_tables(conn)
        n = 0
        gids = sorted(rows.game_id.unique())
        for i in range(0, len(gids), 500):
            n += write_asof(conn, rows[rows.game_id.isin(gids[i:i + 500])], "official")
            conn.commit()
        logger.success(f"nba_injury_asof: {n:,} official rows for {len(gids):,} games")
        return n
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--project", nargs="*", metavar="GAME_ID",
                    help="project these games (none listed: the games due)")
    ap.add_argument("--backfill-official", action="store_true")
    ap.add_argument("--cache", default=str(nb.CACHE))
    a = ap.parse_args()
    if a.backfill_official:
        backfill_official(a.cache)
        return
    if a.project is not None:
        print(run_project(a.project or None))
        return
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    # Telemetry for the live monitor (monitoring/). Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-prop-projection")
    except Exception:  # noqa: BLE001
        pass

    main()
