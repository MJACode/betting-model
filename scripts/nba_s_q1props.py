"""NBA search: first-quarter player props against a projection of first-quarter minutes.

docs/nba_search_q1props.md registers every choice below, committed BEFORE this lab and before any bet
in the search was graded. This lab EMITS cells through the shared harness (scripts/nba_game_harness,
H.run_cells); the pass/fail script judges them (python -m scripts.nba_game2_verdict --results DIR
--house5, section 9.1's bars), and `--verdict DIR` adds the doc's strict reading of the season bar.
No cut, constant or rule below was chosen from a betting result.

18 cells (asserted): first-quarter points, rebounds, assists x over, under x EV >= 0.02 / 0.04 / 0.06,
at each game's one snapshot 45-75 minutes before tip, best deciding offer on a coherent two-way quote,
-200 floor, one unit to win with risk capped at 3. 2024-25 and 2025-26 graded and pooled; 2024-25 is
the choosing season the placebo reads; 2023-24 is history for the fits.

  SETTLEMENT  first-quarter points, rebounds, assists from the plays of period 1
              (scripts/nba_s_postseason.derive_events, unchanged). A game is left out of a market when
              any player's full-game number in that stat differs from nba_player_game_log; out of
              points also when a team's first-quarter points differ from nba_period_scores; out of
              every market when its first-quarter segments miss 60 player-minutes by more than 1, or a
              player has a first-quarter event and no first-quarter court time. A player with no
              first-quarter court time (nba_stints) is void (Caesars' published rule, assumed for all).
  PROJECTION  mean = expected first-quarter minutes when he plays it (recency-weighted, half-life 3,
              of his earlier first-quarter minutes; teammates' absences reallocated to 60 player-minutes)
              x his full-game per-minute rate (season to date, shrunk to his two previous seasons, then
              the league; Kc, Kp fitted on 2023-24) x a first-quarter factor fitted on earlier seasons;
              negative binomial with alpha fitted on earlier seasons (0 = Poisson). Report known 30
              minutes after print. Nothing of the game itself is read.
  PLACEBO     200 runs, seeds 1-200: each proposition's mean over its main line moves to another
              proposition on the same date in the same market and is re-priced at its own lines.

  A PROPOSITION IS ONE "GAME" TO THE HARNESS: (game, player, market) gets an integer id, a row in the
  games table with its first-quarter stat as the home score and 0 as the away score, and its offers are
  filed under the harness's total market, so H.choose takes one bet per proposition and H.settle gives
  over when the stat is above the line. A void has no row.

    python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_q1props --pull [--seed FILE]
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1props --smoke
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \\
        PYTHONPATH=. python -m scripts.nba_s_q1props --full
    PYTHONPATH=. python -m scripts.nba_s_q1props --verdict <folder>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_props as nb  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_verdict as V  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV, WORK_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS", "NBA_S_Q1PROPS_WORK"
DEFAULT_WORK = "C:/Users/micha/AppData/Local/Temp/nba_s/q1props"
POINT, HMARKET = "D", "totals"
Q1_MARKETS = ("player_points_q1", "player_rebounds_q1", "player_assists_q1")
STAT_OF = {"player_points_q1": "points", "player_rebounds_q1": "rebounds", "player_assists_q1": "assists"}
FULL_OF = {"player_points_q1": "player_points", "player_rebounds_q1": "player_rebounds",
           "player_assists_q1": "player_assists"}
STATS = ("points", "rebounds", "assists")
PBP_SEASONS = (2024, 2025, 2026)          # 2023-24 is history (fits); 2024-25 and 2025-26 are graded
PROP_SEASONS = (2025, 2026)               # the feed holds no first-quarter prop before 2024-25
HISTORY = 2024
CHOOSE = (2025,)                          # the choosing season the placebo reads
EV_CUTS = (0.02, 0.04, 0.06)
EV_LOWEST = 0.00
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
EXPECTED_CELLS = 18
LEAD = H.POINTS[POINT]                    # 45-75 minutes before tip
PRICE_MIN, PRICE_MAX = 100.0, 10000.0
LINE_MIN = 0.5
LINE_CEIL = {"points": 35.5, "rebounds": 15.5, "assists": 12.5}
HALF_LIFE = 3.0                           # the rating engine's min_hl, games
MIN_Q1_GAMES = 3
POOL_GAMES = 10
QUARTER_MIN, QUARTER_PLAYER_MIN, COURT_TOL_MIN = 12.0, 60.0, 1.0
E_MIN = 30.0
REPORT_LAG_MIN = 30
REF_LEAD_MIN = 60                         # decision time of a game with no prop snapshot (fits only)
STATUS_FIRST = 2022                       # 2021-22: the first season the report covers every game
FIT_STATUSES = ("Doubtful", "Questionable", "Probable", "Available")
K_GRID = (25.0, 50.0, 100.0, 200.0, 400.0, 800.0, 1600.0)
# doc section 14 (2026-11-03, before any grade): points price through a per-line logistic in log(mean)
POINTS_LINES = tuple(float(x) for x in np.arange(0.5, 16.0, 1.0))
MAP_STATS = ("points",)
MAP_MIN_EVENTS = 30                       # a line needs this many overs and unders to be fitted
R_BANDS = ((0.0, 1.1), (1.1, 1.3), (1.3, np.inf))
THIN = 5
LOW_SHARE = 0.5
FAMILY = "Q1P"
CTL_HR, CTL_FD, CTL_BLIND, CTL_ONE = "control_HR", "control_FD", "control_blind", "control_one_sided"
BOOK_HR, BOOK_FD = "hardrockbet", "fanduel"
# doc section 16: the deciding books and the floor the doc registers; --full refuses any other
REGISTERED_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet", "betparx")
REGISTERED_FLOOR = -200.0
BESIDE_MONTHS = {"10": "October", "02": "February"}     # doc section 16: departed players sit in these months
PICK_COLS = ["game_id", "market", "side", "book", "price", "line", "season", "game_date", "T"]
KEY = ["game_id", "player_id", "market"]
PBP_COLS = ("espn_game_id, play_no, sequence_number, game_id, season, season_type, period, type_id, type_text, "
            "scoring_play, shooting_play, shot_value, points, espn_score_value, team_side, athlete_id_1, "
            "athlete_id_2, athlete_id_3, text")
RULE_BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/"
                 "props_market_bets_sharp_ALL_under_prop_0.00.parquet")
CARD_BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/proj/bets_card_best.parquet")


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def work_dir() -> Path:
    return Path(os.environ.get(WORK_ENV, DEFAULT_WORK))


# ── the one read-only pull ──────────────────────────────────────────────────

def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    raw = getattr(cur, "_cur", cur)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in raw.description])


def pull(out: Path, cache: Path = H.CACHE, seed: Path | None = None) -> dict:
    """Read-only, by indexed key, in chunks of 60 with pauses; never 10:00-10:45 UTC (the daily run).

    1. player_prop_odds, the three first-quarter markets, for every 2024-25 and 2025-26 game the cache
       holds (index game_id, market, ...).
    2. nba_pbp_games and nba_pbp_box for 2023-24 to 2025-26 (small tables).
    3. nba_pbp for every regular-season game of those seasons (primary key espn_game_id, play_no). With
       `seed` (an earlier local pull made by the same SELECT), a game is copied from the seed only when its
       row count equals the fresh nba_pbp_games.n_plays; every other game is pulled. Without a seed, all.
    """
    from data.db import get_connection
    now = time.gmtime()
    if now.tm_hour == 10 and now.tm_min <= 45:
        raise SystemExit("10:00-10:45 UTC is the daily run: not pulling now")
    out.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    notes = {"pg_stat_activity": _frame(conn, "select state, count(*) n from pg_stat_activity "
                                              "where datname=current_database() group by 1").to_dict("records")}
    print(notes)
    g = pd.read_parquet(Path(cache) / "nba_games.parquet")
    ids = sorted(g.loc[(g.sport == "NBA") & g.season.isin(PROP_SEASONS), "game_id"].tolist())
    parts = []
    for i in range(0, len(ids), 60):
        parts.append(_frame(conn, "select prop_id, game_id, game_date, player_name, team, market, bookmaker, "
                                  "snapshot_type, snapshot_at, line, over_price, under_price, created_at, "
                                  "book_last_update from player_prop_odds "
                                  "where game_id = any(%s) and market = any(%s)", (ids[i:i + 60], list(Q1_MARKETS))))
        time.sleep(0.3)
    props = pd.concat(parts, ignore_index=True)
    props.to_parquet(out / "q1_props.parquet")
    notes["q1_prop_rows"] = int(len(props))
    say(f"first-quarter prop rows {len(props):,} over {props.game_id.nunique():,} games")
    pg = _frame(conn, "select espn_game_id, game_id, season, season_type, game_date, home_team, away_team, in_games, "
                      "match_method, sides_swapped, n_plays, n_periods, espn_home_final, espn_away_final, "
                      "pbp_home_pts, pbp_away_pts, points_source, points_mismatch, derivation from nba_pbp_games "
                      "where season between %s and %s", (min(PBP_SEASONS), max(PBP_SEASONS)))
    pg.to_parquet(out / "nba_pbp_games.parquet")
    _frame(conn, "select espn_game_id, espn_id, game_id, season, side, team, name, starter, minutes, did_not_play "
                 "from nba_pbp_box where season between %s and %s",
           (min(PBP_SEASONS), max(PBP_SEASONS))).to_parquet(out / "nba_pbp_box.parquet")
    want = pg[pg.season.isin(PBP_SEASONS) & (pg.season_type == 2)]
    need = dict(zip(want.espn_game_id.astype("int64"), want.n_plays.astype("int64")))
    keep, copied = [], set()
    if seed is not None and Path(seed).exists():
        s = pd.read_parquet(seed)
        s = s[s.espn_game_id.astype("int64").isin(set(need))]
        n = s.groupby("espn_game_id").size()
        copied = {int(k) for k, v in n.items() if need.get(int(k)) == int(v)}
        keep.append(s[s.espn_game_id.astype("int64").isin(copied)])
    todo = sorted(set(need) - copied)
    notes.update({"pbp_games_wanted": len(need), "pbp_games_from_seed_verified": len(copied),
                  "pbp_games_pulled": len(todo)})
    say(f"play-by-play: {len(copied):,} games verified from the seed, {len(todo):,} to pull")
    for i in range(0, len(todo), 60):
        keep.append(_frame(conn, f"select {PBP_COLS} from nba_pbp where espn_game_id = any(%s)", (todo[i:i + 60],)))
        time.sleep(0.3)
    plays = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame()
    plays.to_parquet(out / "nba_pbp_slim.parquet")
    conn.close()
    notes["pbp_rows"] = int(len(plays))
    pd.Series({k: str(v) for k, v in notes.items()}).to_json(out / "pull_notes.json", indent=1)
    say(f"pulled: {notes}")
    return notes


# ── settlement (doc section 3) ──────────────────────────────────────────────

def court_seconds(stints: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """First-quarter court time per (game, team, player) from the regular-season segments of period 1,
    five a side only; and per team-game whether the segments fill 60 player-minutes within 1."""
    s = stints[(stints.season_type == 2) & (stints.period == 1)]
    five = (s.n_home == 5) & (s.n_away == 5)
    notes = {"q1_segments": int(len(s)), "q1_segments_not_five_a_side": int((~five).sum())}
    s = s[five]
    parts = []
    for side in ("home", "away"):
        x = s[["game_id", f"{side}_team", f"{side}_player_ids", "duration_s"]].rename(
            columns={f"{side}_team": "team", f"{side}_player_ids": "player_id"})
        parts.append(x.explode("player_id"))
    e = pd.concat(parts, ignore_index=True)
    e["player_id"] = e.player_id.astype(str)
    sec = e.groupby(["game_id", "team", "player_id"], sort=False).duration_s.sum().rename("q1_sec").reset_index()
    tm = e.groupby(["game_id", "team"], sort=False).duration_s.sum().rename("player_sec").reset_index()
    teams = pd.concat([stints[(stints.season_type == 2)][["game_id", "home_team"]].rename(columns={"home_team": "team"}),
                       stints[(stints.season_type == 2)][["game_id", "away_team"]].rename(columns={"away_team": "team"})]
                      ).drop_duplicates()
    tm = teams.merge(tm, on=["game_id", "team"], how="left").fillna({"player_sec": 0.0})
    tm["court_ok"] = (tm.player_sec / 60.0 - QUARTER_PLAYER_MIN).abs() <= COURT_TOL_MIN
    notes["team_games"] = int(len(tm))
    notes["team_games_court_fail"] = int((~tm.court_ok).sum())
    return sec, tm, notes


def id_lookup(id_map: pd.DataFrame, stints: pd.DataFrame) -> dict:
    """ESPN id -> NBA id: nba_player_id_map, then the segments' own paired lists for any id it lacks
    (a pair counts only when one ESPN id always sits beside one NBA id)."""
    m = id_map[id_map.player_id.notna()].drop_duplicates("espn_id")
    out = dict(zip(m.espn_id.astype("int64"), m.player_id.astype(str)))
    pairs = []
    for side in ("home", "away"):
        a = stints[[f"{side}_espn_ids", f"{side}_player_ids"]]
        e = np.concatenate([np.asarray(v, dtype=object) for v in a[f"{side}_espn_ids"]])
        p = np.concatenate([np.asarray(v, dtype=object) for v in a[f"{side}_player_ids"]])
        pairs.append(pd.DataFrame({"e": e, "p": p}))
    pr = pd.concat(pairs, ignore_index=True).dropna().drop_duplicates()
    pr["e"] = pd.to_numeric(pr.e, errors="coerce")
    pr = pr.dropna()
    one = pr.groupby("e").p.nunique()
    pr = pr[pr.e.isin(one[one == 1].index)].drop_duplicates("e")
    for e, p in zip(pr.e.astype("int64"), pr.p.astype(str)):
        out.setdefault(int(e), p)
    return out


def derive_stats(plays: pd.DataFrame, pbp_games: pd.DataFrame, ids: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(full game, first quarter): game_id, player_id, points, rebounds, assists per player with an event.
    An ESPN id with no NBA id keeps 'espn:<id>' so it never matches a box-score row."""
    from scripts.nba_s_postseason import derive_events
    gmap = pbp_games[(pbp_games.season_type == 2) & pbp_games.in_games.astype(bool)]
    gmap = dict(zip(gmap.espn_game_id.astype("int64"), gmap.game_id))
    p = plays[plays.espn_game_id.astype("int64").isin(set(gmap))]

    def shape(ev: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame({"game_id": ev.espn_game_id.astype("int64").map(gmap).values,
                            "player_id": [ids.get(int(e), f"espn:{int(e)}") for e in ev.espn_id],
                            **{s: ev[s].to_numpy(float) for s in STATS}})
        return out.groupby(["game_id", "player_id"], sort=False)[list(STATS)].sum().reset_index()
    full = shape(derive_events(p))
    q1 = shape(derive_events(p[p.period == 1]))
    return full, q1


def full_game_check(full: pd.DataFrame, log: pd.DataFrame, game_ids) -> tuple[dict, dict]:
    """{stat: games where any player's derived full-game number differs from the box score}, and the
    differing rows per stat. A player only one side holds counts as zeros on the other."""
    ids = set(game_ids)
    a = full[full.game_id.isin(ids)]
    b = log[log.game_id.isin(ids)][["game_id", "player_id", *STATS]]
    x = a.merge(b, on=["game_id", "player_id"], how="outer", suffixes=("_d", "_b"))
    bad, rows = {}, {}
    for s in STATS:
        d = x[s + "_d"].fillna(0.0).to_numpy(float) != x[s + "_b"].fillna(0.0).to_numpy(float)
        bad[s] = set(x.loc[d, "game_id"])
        rows[s] = int(d.sum())
    return bad, rows


def period_points_check(q1: pd.DataFrame, team_of: pd.DataFrame, games: pd.DataFrame, periods: pd.DataFrame,
                        game_ids) -> set:
    """Games whose first-quarter points summed per team from the derived lines differ from
    nba_period_scores period 1, or have no period score, or credit a point to a player with no team."""
    ids = set(game_ids)
    x = q1[q1.game_id.isin(ids)].merge(team_of, on=["game_id", "player_id"], how="left")
    no_team = set(x.loc[x.team.isna() & (x.points > 0), "game_id"])
    g = games.set_index("game_id")
    x = x[x.team.notna()]
    side = np.where(x.team.to_numpy() == x.game_id.map(g.home_team).to_numpy(), "home",
                    np.where(x.team.to_numpy() == x.game_id.map(g.away_team).to_numpy(), "away", "none"))
    no_team |= set(x.loc[(side == "none") & (x.points.to_numpy() > 0), "game_id"])
    x = x.assign(side=side)
    pts = x.groupby(["game_id", "side"]).points.sum().unstack(fill_value=0.0)
    p1 = periods[(periods.period == 1) & periods.game_id.isin(ids)].drop_duplicates("game_id").set_index("game_id")
    bad = set(ids - set(p1.index))
    for gid in ids & set(p1.index):
        h = float(pts.at[gid, "home"]) if gid in pts.index and "home" in pts else 0.0
        a = float(pts.at[gid, "away"]) if gid in pts.index and "away" in pts else 0.0
        if h != float(p1.at[gid, "home_points"]) or a != float(p1.at[gid, "away_points"]):
            bad.add(gid)
    return bad | no_team


@dataclass
class Settled:
    q1: pd.DataFrame              # game_id, player_id, q1_sec, points, rebounds, assists (court time or an event)
    valid: dict                   # market -> set of game ids kept for it
    team_court: pd.DataFrame      # game_id, team, player_sec, court_ok
    notes: dict


def settle(plays: pd.DataFrame, pbp_games: pd.DataFrame, stints: pd.DataFrame, id_map: pd.DataFrame,
           log: pd.DataFrame, games: pd.DataFrame, periods: pd.DataFrame, seasons=PBP_SEASONS) -> Settled:
    """Doc section 3: derive, check, and keep per market only the games every check passes."""
    sec, tm, notes = court_seconds(stints)
    ids = id_lookup(id_map, stints)
    full, q1ev = derive_stats(plays, pbp_games, ids)
    lg = log[log.season.isin(seasons)].copy()
    lg["player_id"] = lg.player_id.astype(str)
    reg = set(games.loc[games.season.isin(seasons), "game_id"]) & set(lg.game_id)
    with_plays = set(full.game_id) & reg
    notes["games_regular"] = len(reg)
    notes["games_without_plays"] = len(reg - with_plays)
    full_bad, rows = full_game_check(full, lg, with_plays)
    notes["full_game_rows_differing"] = rows
    notes["full_game_games_differing"] = {s: len(v) for s, v in full_bad.items()}
    team_of = lg[["game_id", "player_id", "team"]].drop_duplicates(["game_id", "player_id"])
    period_bad = period_points_check(q1ev, team_of, games, periods, with_plays)
    notes["period_points_games_differing"] = len(period_bad)
    court_bad = set(tm.loc[~tm.court_ok, "game_id"]) & with_plays
    notes["court_time_games_failing"] = len(court_bad)
    q1 = sec[sec.game_id.isin(with_plays)].merge(q1ev[q1ev.game_id.isin(with_plays)], on=["game_id", "player_id"],
                                                  how="outer")
    q1[list(STATS)] = q1[list(STATS)].fillna(0.0)
    q1["q1_sec"] = q1.q1_sec.fillna(0.0)
    has_event = q1[list(STATS)].sum(axis=1) > 0
    event_bad = set(q1.loc[has_event & (q1.q1_sec <= 0), "game_id"])
    notes["event_without_court_games"] = len(event_bad)
    every = court_bad | event_bad
    valid = {}
    for m, s in STAT_OF.items():
        out = full_bad[s] | every | (period_bad if s == "points" else set())
        valid[m] = with_plays - out
    season_of = games.set_index("game_id").season
    notes["games_kept"] = {m: {int(se): int(n) for se, n in pd.Series(sorted(v)).map(season_of).value_counts().items()}
                           for m, v in valid.items()}
    notes["games_with_plays_by_season"] = {int(se): int(n) for se, n in
                                           pd.Series(sorted(with_plays)).map(season_of).value_counts().items()}
    notes["games_left_out_by_season"] = {
        m: {"full_game": {int(se): int(n) for se, n in pd.Series(sorted(full_bad[s])).map(season_of).value_counts().items()},
            "period_points": ({int(se): int(n) for se, n in pd.Series(sorted(period_bad)).map(season_of).value_counts().items()}
                              if s == "points" else {}),
            "court_time": {int(se): int(n) for se, n in pd.Series(sorted(court_bad)).map(season_of).value_counts().items()},
            "event_without_court": {int(se): int(n) for se, n in pd.Series(sorted(event_bad)).map(season_of).value_counts().items()}}
        for m, s in STAT_OF.items()}
    notes["unmapped_espn_ids_with_events"] = int(full.player_id.str.startswith("espn:").sum())
    return Settled(q1[["game_id", "player_id", "q1_sec", *STATS]], valid, tm, notes)


# ── quotes (doc section 4) ──────────────────────────────────────────────────

def matched_quotes(cache: Path, work: Path) -> pd.DataFrame:
    """scripts/nba_prop_market_lab.build_quotes, unchanged, on the first-quarter rows filed under the
    full-game market names it knows (name match to one player on the game's two teams, the namesake
    refusal, lead, coherence), then the names put back. Cached in `work`, rebuilt when the pull is newer."""
    from scripts import nba_prop_market_lab as ML
    work = Path(work)
    src = work / "pulled" / "q1_props.parquet"
    f = work / "quotes_q1.parquet"
    if f.exists() and f.stat().st_mtime >= src.stat().st_mtime:
        return pd.read_parquet(f)
    folder = work / "match"
    folder.mkdir(parents=True, exist_ok=True)
    p = pd.read_parquet(src)
    p["market"] = p.market.map(FULL_OF)
    p.to_parquet(folder / "nba_props.parquet")
    for t in ("nba_games", "nba_player_game_log", "nba_player_game_adv", "nba_game_inactives"):
        shutil.copyfile(Path(cache) / f"{t}.parquet", folder / f"{t}.parquet")
    ML.CACHE, ML.WORK = folder, folder
    q = ML.build_quotes()
    back = {v: k for k, v in FULL_OF.items()}
    q["market"] = q.market.map(back)
    q.to_parquet(f)
    return q


def refuse_rows(q: pd.DataFrame, settled: Settled) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    """Doc section 4's rules in order, each counted: names, window, prices, line range; then a
    two-sided quote must be coherent (a one-sided quote goes to the control); then settlement: the game
    kept for the market, and the player on the floor in the first quarter (else void).
    -> (coherent rows, one-sided rows, notes, the propositions before settlement for the beside count)."""
    n = {"rows": int(len(q))}
    r = q.copy()
    r["player_id"] = r.player_id.astype(object).where(r.player_id.notna(), None)
    matched = r.player_id.notna() & ~r.namesake.fillna(False).astype(bool)
    dup = r[matched].duplicated(["game_id", "player_id", "market", "bookmaker"], keep=False)
    ok = matched.copy()
    ok.loc[dup[dup].index] = False
    n["refused_names"] = int((~ok).sum())
    r = r[ok]
    r = r[r.lead_min.between(*LEAD)]
    n["refused_window"] = n["rows"] - n["refused_names"] - int(len(r))
    over, under = r.over_price.to_numpy(float), r.under_price.to_numpy(float)
    bad = np.zeros(len(r), bool)
    for px in (over, under):
        with np.errstate(invalid="ignore"):
            bad |= np.isfinite(px) & ((np.abs(px) < PRICE_MIN) | (np.abs(px) > PRICE_MAX))
    bad |= ~np.isfinite(over)
    n["refused_price"] = int(bad.sum())
    r = r[~bad]
    stat = r.market.map(STAT_OF)
    ceil = stat.map(LINE_CEIL).to_numpy(float)
    bad = (r.line.to_numpy(float) < LINE_MIN) | (r.line.to_numpy(float) > ceil)
    n["refused_line"] = int(bad.sum())
    r = r[~bad].copy()
    two = r.under_price.notna().to_numpy()
    isum = np.where(two, 1.0 / nb.decimal(r.over_price) + 1.0 / nb.decimal(r.under_price.fillna(100.0)), np.nan)
    coh = two & (isum >= H.COHERENT[0]) & (isum <= H.COHERENT[1])
    n["refused_incoherent"] = int((two & ~coh).sum())
    n["one_sided"] = int((~two).sum())
    r["player_id"] = r.player_id.astype(str)
    pre = r[coh | ~two].drop_duplicates(KEY)[[*KEY, "season", "minutes"]].copy()
    keep = np.zeros(len(r), bool)
    for m, ids in settled.valid.items():
        keep |= (r.market.to_numpy() == m) & r.game_id.isin(ids).to_numpy()
    n["left_out_by_settlement"] = int((~keep & (coh | ~two)).sum())
    sec = dict(zip(zip(settled.q1.game_id, settled.q1.player_id), settled.q1.q1_sec))
    court = np.array([sec.get(k, 0.0) for k in zip(r.game_id, r.player_id)], float)
    void = keep & (court <= 0)
    n["void_no_first_quarter_court_time"] = int((void & (coh | ~two)).sum())
    r["q1_sec"] = court
    use = keep & ~void
    co, one = r[use & coh].copy(), r[use & ~two].copy()
    n["coherent_rows"], n["one_sided_rows"] = int(len(co)), int(len(one))
    pre["kept"] = [g in settled.valid[m] for g, m in zip(pre.game_id, pre.market)]
    pre["q1_sec"] = np.array([sec.get(k, 0.0) for k in zip(pre.game_id, pre.player_id)], float)
    return co, one, n, pre


# ── the projection (doc section 5) ──────────────────────────────────────────

def _asof(left: pd.DataFrame, right: pd.DataFrame, cols, by) -> pd.DataFrame:
    """For each left row, right's `cols` from its latest row strictly before left.date (same `by`)."""
    by = [by] if isinstance(by, str) else list(by)
    lft = left.reset_index(drop=True).assign(_i=np.arange(len(left))).sort_values("date")
    rgt = right[["date", *by, *cols]].sort_values("date")
    for c in by:                                  # one key type on both sides (string and object ids mix)
        if lft[c].dtype != rgt[c].dtype:
            lft[c], rgt[c] = lft[c].astype(object), rgt[c].astype(object)
    out = pd.merge_asof(lft, rgt, on="date", by=by, allow_exact_matches=False, direction="backward")
    return out.sort_values("_i").drop(columns="_i").reset_index(drop=True)


def player_games(log: pd.DataFrame, games: pd.DataFrame, sec: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    """Every regular-season box line of a player who played: date, team, minutes, the three stats, his
    first-quarter court seconds and whether his team-game's segments pass the court-time check."""
    reg = set(games.game_id)
    lg = log[log.game_id.isin(reg) & (log.minutes.fillna(0) > 0)].copy()
    lg["player_id"] = lg.player_id.astype(str)
    lg["date"] = pd.to_datetime(lg.game_date)
    x = lg[["game_id", "player_id", "team", "season", "date", "minutes", *STATS]].merge(
        sec, on=["game_id", "team", "player_id"], how="left").merge(tm[["game_id", "team", "court_ok"]],
                                                                    on=["game_id", "team"], how="left")
    x["q1_sec"] = x.q1_sec.fillna(0.0)
    x["court_ok"] = x.court_ok.fillna(False).astype(bool)
    return x


def minutes_history(pg: pd.DataFrame) -> pd.DataFrame:
    """After each of a player's games with first-quarter court time (segment-checked): the
    recency-weighted mean of his first-quarter minutes in such games (half-life HALF_LIFE games), and how
    many there have been."""
    h = pg[(pg.q1_sec > 0) & pg.court_ok].sort_values(["player_id", "date"])[["player_id", "date", "q1_sec"]].copy()
    h["q1_min"] = h.q1_sec / 60.0
    h["m"] = h.groupby("player_id", sort=False).q1_min.transform(lambda s: s.ewm(halflife=HALF_LIFE).mean())
    h["n_q1"] = h.groupby("player_id", sort=False).cumcount() + 1
    return h[["player_id", "date", "m", "n_q1"]]


def team_pools(pg: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """For each target (game, team): the players with first-quarter court time in at least one of the
    team's last POOL_GAMES segment-checked games before the date, with s = the share of those games."""
    tg = pg[["team", "game_id", "date", "court_ok"]].drop_duplicates(["team", "game_id"]).sort_values(["team", "date"])
    tg["k"] = tg.groupby("team").cumcount()
    tg["okn"] = tg.court_ok.astype(float)
    tg["nwin"] = tg.groupby("team").okn.transform(lambda s: s.shift(1).rolling(POOL_GAMES, min_periods=1).sum()).fillna(0.0)
    ap = pg[(pg.q1_sec > 0) & pg.court_ok][["team", "game_id", "player_id"]].merge(tg[["team", "game_id", "k"]],
                                                                                    on=["team", "game_id"])
    want = targets[["game_id", "team"]].drop_duplicates().merge(tg[["team", "game_id", "k", "nwin"]],
                                                                on=["team", "game_id"])
    parts = []
    for off in range(1, POOL_GAMES + 1):
        parts.append(ap.assign(k=ap.k + off)[["team", "k", "player_id"]])
    ex = pd.concat(parts, ignore_index=True)
    ex = ex.merge(want[["team", "k"]], on=["team", "k"])
    c = ex.groupby(["team", "k", "player_id"], sort=False).size().rename("c").reset_index()
    out = want.merge(c, on=["team", "k"])
    out["s"] = out.c / out.nwin.where(out.nwin > 0)
    return out[["game_id", "team", "player_id", "s"]]


def report_at(report: pd.DataFrame, decisions: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """Each team's latest submitted report as known at the decision (printed time + REPORT_LAG_MIN):
    game_id, team, player_id, status. A row with no NBA id takes the one roster player with its name."""
    r = report.copy()
    r["report_ts"] = r.report_ts + pd.Timedelta(minutes=REPORT_LAG_MIN)
    rep = nb.injury_asof(r, decisions)
    rep = nb._attach_report_ids(rep, roster)
    rep["player_id"] = rep.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    return rep.drop_duplicates(["game_id", "player_id"])[["game_id", "team", "player_id", "status"]]


def pool_status_rates(fit: pd.DataFrame, seasons) -> dict:
    """Doc section 16. {season S: {status: the share of POOL players listed with it who played}}, from `fit`
    (season, status, played: one row per pool player of a fit team-game, status at tip minus REF_LEAD_MIN),
    seasons STATUS_FIRST through S-1 only. Out is 0 by rule."""
    out = {}
    for S in seasons:
        x = fit[(fit.season >= STATUS_FIRST) & (fit.season < S)]
        out[int(S)] = {st: float(x.loc[x.status == st, "played"].mean()) for st in FIT_STATUSES}
        out[int(S)]["Out"] = 0.0
        out[int(S)]["_n"] = {st: int((x.status == st).sum()) for st in FIT_STATUSES}
    return out


def roster_events(log: pd.DataFrame, inactives: pd.DataFrame, report: pd.DataFrame, reg: set,
                  roster: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Doc section 16: what says which team a player is on, as it becomes known.
    (box lines and inactive lists: player_id, date, team), read for games strictly before a target's date;
    (report listings: player_id, known, game_date, team), read when printed time + REPORT_LAG_MIN <= T.
    A report row with no NBA id takes the one roster player with its name."""
    lg = log[log.game_id.isin(reg)][["player_id", "game_date", "team"]]
    ina = inactives[inactives.game_id.isin(reg)][["player_id", "game_date", "team"]]
    box = pd.concat([lg, ina], ignore_index=True).dropna(subset=["player_id"])
    box["player_id"] = box.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    box["date"] = pd.to_datetime(box.game_date)
    box = box.drop_duplicates(["player_id", "date", "team"])[["player_id", "date", "team"]]
    r = report[report.status.isin(nb.REAL_STATUS)][["game_id", "team", "report_ts", "player_id", "player_name", "game_date"]]
    r = nb._attach_report_ids(r, roster)
    r = r.assign(player_id=r.player_id.astype(str).str.replace(r"\.0$", "", regex=True),
                 known=r.report_ts + pd.Timedelta(minutes=REPORT_LAG_MIN), rep_date=pd.to_datetime(r.game_date))
    return box, r[["player_id", "known", "rep_date", "team"]].drop_duplicates()


def team_as_of(rows: pd.DataFrame, box: pd.DataFrame, rep: pd.DataFrame) -> np.ndarray:
    """Each row's team as known at its decision: rows (player_id, date, T). The team of the latest of his box
    lines and inactive listings before the date, unless a report known at T lists him for a game on or after
    that one, in which case that report's team."""
    a = _asof(rows[["player_id", "date"]], box.assign(ev_date=box.date), ["team", "ev_date"], "player_id")
    lft = rows[["player_id", "T"]].reset_index(drop=True).assign(_i=np.arange(len(rows)))
    lft["T"] = pd.to_datetime(lft["T"], utc=True).astype("datetime64[ns, UTC]")
    lft = lft.sort_values("T")
    rgt = rep.rename(columns={"team": "rep_team"}).sort_values("known")
    lft["player_id"], rgt["player_id"] = lft.player_id.astype(object), rgt.player_id.astype(object)
    rgt["known"] = pd.to_datetime(rgt.known, utc=True).astype("datetime64[ns, UTC]")
    b = pd.merge_asof(lft, rgt, left_on="T", right_on="known", by="player_id", direction="backward")
    b = b.sort_values("_i").reset_index(drop=True)
    use_rep = b.rep_team.notna().to_numpy() & (a.ev_date.isna().to_numpy()
                                               | (b.rep_date.to_numpy() >= a.ev_date.to_numpy()))
    return np.where(use_rep, b.rep_team.to_numpy(dtype=object), a.team.to_numpy(dtype=object))


def pool_frame(pg: pd.DataFrame, hist: pd.DataFrame, tt: pd.DataFrame, box: pd.DataFrame, rep: pd.DataFrame
               ) -> pd.DataFrame:
    """Doc 5.2 and section 16: each target team-game's pool (tt: game_id, team, date, T, season), with s, m,
    and only players whose team as of the decision is this team."""
    pool = team_pools(pg, tt)
    pool = pool.merge(tt[["game_id", "team", "date", "T", "season"]], on=["game_id", "team"])
    pool = _asof(pool, hist, ["m"], "player_id")
    pool["team_now"] = team_as_of(pool[["player_id", "date", "T"]], box, rep)
    return pool[(pool.team_now == pool.team) & pool.m.notna() & pool.s.notna()].reset_index(drop=True)


def reallocate(tg: pd.DataFrame, pool: pd.DataFrame, st: dict, status: dict) -> pd.DataFrame:
    """Doc 5.2. `pool`: game_id, team, player_id, season, s, m (one row per pool player of a target team-game);
    `st`: {(game_id, player_id): status at T}; `status`: status_rates' {season: {status: rate}}.
    a = 0 if Out, the fitted rate if listed otherwise, 1 if not listed. E = sum a*s*m per team-game, and
    each target's own E counts HIS OWN status as 1 (E - a*s*m + s*m, doc section 16): a void-if-he-sits bet
    is priced given that he plays, so his own status never moves his own minutes. r = 60 / his E, and his
    expected minutes = min(12, his own m * r)."""
    a = np.ones(len(pool))
    for i, (k, se) in enumerate(zip(zip(pool.game_id, pool.player_id), pool.season)):
        sname = st.get(k)
        if isinstance(sname, str):
            a[i] = status[int(se)].get(sname, 1.0)
    pool = pool.assign(a=a)
    term = pool.a * pool.s * pool.m
    E = term.groupby([pool.game_id, pool.team]).sum()
    E = dict(zip(E.index, E.to_numpy(float)))
    own = dict(zip(zip(pool.game_id, pool.player_id), ((1.0 - pool.a) * pool.s * pool.m).to_numpy(float)))
    out = tg.copy()
    out["E"] = np.array([E.get(k, np.nan) for k in zip(out.game_id, out.team)], float) \
        + np.array([own.get(k, 0.0) for k in zip(out.game_id, out.player_id)], float)
    out["r"] = QUARTER_PLAYER_MIN / out.E
    out["mu_min"] = np.minimum(QUARTER_MIN, out.m * out.r)
    return out


def rate_inputs(log: pd.DataFrame, games: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Per target row: his stats and minutes this season before today, over his two previous seasons,
    and the league's per-minute rate last season, for each of the three stats."""
    reg = set(games.game_id)
    lg = log[log.game_id.isin(reg) & (log.minutes.fillna(0) > 0)].copy()
    lg["player_id"] = lg.player_id.astype(str)
    lg["date"] = pd.to_datetime(lg.game_date)
    lg = lg.sort_values(["player_id", "date"])
    cols = ["minutes", *STATS]
    cs = lg.groupby(["player_id", "season"], sort=False)[cols].cumsum()
    right = pd.concat([lg[["player_id", "season", "date"]], cs.add_prefix("cur_")], axis=1)
    t = _asof(targets[["player_id", "season", "date"]], right, [f"cur_{c}" for c in cols], ["player_id", "season"])
    tot = lg.groupby(["player_id", "season"])[cols].sum()
    out = t.copy()
    for c in cols:
        out[f"cur_{c}"] = out[f"cur_{c}"].fillna(0.0)
        prev = np.zeros(len(out))
        for back in (1, 2):
            k = pd.MultiIndex.from_arrays([out.player_id, out.season - back])
            prev += tot[c].reindex(k).fillna(0.0).to_numpy()
        out[f"prev_{c}"] = prev
    lgs = lg.groupby("season")[cols].sum()
    for s in STATS:
        league = (lgs[s] / lgs["minutes"]).to_dict()
        out[f"league_{s}"] = (out.season - 1).map(league).to_numpy(float)
    return out


def shrunk_rate(ri: pd.DataFrame, stat: str, kc: float, kp: float) -> np.ndarray:
    prior = (ri[f"prev_{stat}"] + kp * ri[f"league_{stat}"]) / (ri["prev_minutes"] + kp)
    return ((ri[f"cur_{stat}"] + kc * prior) / (ri["cur_minutes"] + kc)).to_numpy(float)


def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    mu = np.clip(mu, 1e-9, None)
    t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(2.0 * np.sum(t - (y - mu)))


def fit_k(ri: pd.DataFrame, y: pd.DataFrame, minutes: np.ndarray) -> dict:
    """{stat: (Kc, Kp)} by the Poisson deviance of the full-game stat given the minutes played, on the
    rows handed in (2023-24's player-games)."""
    out = {}
    for s in STATS:
        best = None
        for kc in K_GRID:
            for kp in K_GRID:
                d = poisson_deviance(y[s].to_numpy(float), shrunk_rate(ri, s, kc, kp) * minutes)
                if best is None or d < best[0]:
                    best = (d, kc, kp)
        out[s] = (best[1], best[2])
    return out


def fit_line_map(y: np.ndarray, mu: np.ndarray, lines=POINTS_LINES) -> dict:
    """Doc section 14: for each line L, P(over L) = sigmoid(a_L + b_L * log mean), by
    models.nba_props.fit_platt on p = mean / (1 + mean) (whose logit is log mean). A line with fewer than
    MAP_MIN_EVENTS overs or unders is left out, and prices through the negative binomial."""
    y, mu = np.asarray(y, float), np.asarray(mu, float)
    ok = np.isfinite(y) & np.isfinite(mu) & (mu > 0)
    y, mu = y[ok], mu[ok]
    keep, a, b = [], [], []
    for ln in lines:
        over = (y > ln).astype(float)
        if over.sum() < MAP_MIN_EVENTS or (1 - over).sum() < MAP_MIN_EVENTS:
            continue
        ai, bi = nb.fit_platt(mu / (1.0 + mu), over)
        keep.append(float(ln))
        a.append(ai)
        b.append(bi)
    return {"lines": np.array(keep), "a": np.array(a), "b": np.array(b)}


def map_p_over(m: dict, mu: np.ndarray, line: np.ndarray) -> np.ndarray:
    """P(over line) from a line map; NaN where the line is not one of its fitted lines. Non-increasing
    across lines for one mean (the smaller value carried forward)."""
    mu, line = np.asarray(mu, float), np.asarray(line, float)
    out = np.full(len(mu), np.nan)
    if not len(m["lines"]) or not len(mu):
        return out
    z = m["a"][None, :] + m["b"][None, :] * np.log(np.clip(mu, 1e-6, None))[:, None]
    P = np.minimum.accumulate(1.0 / (1.0 + np.exp(-z)), axis=1)
    j = np.searchsorted(m["lines"], line)
    hit = (j < len(m["lines"])) & np.isclose(m["lines"][np.minimum(j, len(m["lines"]) - 1)], line)
    out[hit] = P[np.nonzero(hit)[0], j[hit]]
    return out


def walk_forward(y: np.ndarray, raw: np.ndarray, season: np.ndarray, ok: np.ndarray, stat: str
                 ) -> tuple[dict, dict, dict, np.ndarray]:
    """Doc 5.4 and section 14, one stat. Per season S present: the factor = sum y / sum raw over the `ok`
    rows of 2023-24 .. S-1 (2023-24 itself for S = 2023-24); for each later S, alpha and (points) the line
    map on the same earlier rows, each carrying its own season's factor. A season's own rows never reach
    its own fits. -> ({S: factor}, {S: alpha}, {S: line map}, the mean of every row)."""
    seasons = sorted(int(x) for x in set(season))
    factor, alpha, maps = {}, {}, {}
    for S in seasons:
        fit = ok & (season >= HISTORY) & ((season < S) | ((season == HISTORY) & (S == HISTORY)))
        factor[S] = float(np.nansum(y[fit]) / np.nansum(raw[fit]))
    mu = raw * np.array([factor[int(x)] for x in season], float)
    for S in seasons:
        if S == HISTORY:
            continue
        fit = ok & (season >= HISTORY) & (season < S)
        alpha[S] = float(nb.fit_alpha(y[fit], mu[fit]))
        if stat in MAP_STATS:
            maps[S] = fit_line_map(y[fit], mu[fit])
    return factor, alpha, maps, mu


def map_check(y: np.ndarray, raw: np.ndarray, date: np.ndarray, hist: np.ndarray, lines=(1.5, 2.5, 3.5, 4.5, 5.5, 6.5)
              ) -> list[dict]:
    """Section 14's check on 2023-24 alone (`hist`): the factor, the line map and the negative binomial are all
    fitted on the season's first half of dates (doc section 16: the factor too), and read on its second half."""
    dates = np.sort(np.unique(date[hist]))
    first = hist & (date < dates[len(dates) // 2])
    second = hist & ~first
    f = float(np.nansum(y[first]) / np.nansum(raw[first]))
    mu = raw * f
    mh = fit_line_map(y[first], mu[first])
    a_h = float(nb.fit_alpha(y[first], mu[first]))
    n2 = int(second.sum())
    return [{"line": ln, "games": n2, "factor_first_half": f, "actual": float((y[second] > ln).mean()),
             "line_map": float(np.nanmean(map_p_over(mh, mu[second], np.full(n2, ln)))),
             "negative_binomial": float(np.mean(nb.p_over(mu[second], np.full(n2, ln), a_h)))} for ln in lines]


@dataclass
class Projection:
    table: pd.DataFrame           # per (game_id, player_id): season, has_number, why, mu_min, raw_<stat>
    k: dict
    status: dict
    factor: dict                  # (stat, season) -> first-quarter factor
    alpha: dict                   # (stat, season) -> negative-binomial alpha (graded seasons)
    notes: dict
    maps: dict = None             # (stat, season) -> line map (doc section 14; points only)


def project(data: dict, settled: Settled, targets: pd.DataFrame) -> Projection:
    """Doc section 5. `targets`: game_id, player_id, T (decision time) for every (game, player) to price:
    the propositions, and every 2023-24 to 2025-26 player-game with first-quarter court time (for the
    factor and alpha fits). Reads only games dated before each target's date, and the report as known
    REPORT_LAG_MIN after print at T."""
    t0 = time.time()
    games, log, sched = data["games"], data["log"], data["schedule"]
    reg = nb.regular_game_ids(games.assign(sport="NBA") if "sport" not in games else games, sched)
    rg = games[games.game_id.isin(reg)]
    sec, tm = data["court_sec"], data["team_court"]
    pg = player_games(log, rg, sec, tm)
    g = rg.set_index("game_id")
    tg = targets.copy()
    tg["season"] = tg.game_id.map(g.season).astype(int)
    tg["date"] = pd.to_datetime(tg.game_id.map(g.game_date))
    hist = minutes_history(pg)
    tg = _asof(tg, hist, ["m", "n_q1"], "player_id")
    roster = log[["team", "season", "player_id", "player_name"]].assign(player_id=lambda f: f.player_id.astype(str))
    box, rep_ev = roster_events(log, data["inactives"], data["report"], set(reg), roster)
    tg["team_now"] = team_as_of(tg[["player_id", "date", "T"]], box, rep_ev)
    home, away = tg.game_id.map(g.home_team), tg.game_id.map(g.away_team)
    tg["team"] = np.where((tg.team_now == home) | (tg.team_now == away), tg.team_now, None)
    dec = tg.drop_duplicates("game_id")[["game_id", "T"]].rename(columns={"T": "decision_ts"})
    rep = report_at(data["report"][data["report"].game_id.isin(set(dec.game_id))], dec, roster)
    st = dict(zip(zip(rep.game_id, rep.player_id), rep.status))
    tg["status"] = np.array([st.get(k) for k in zip(tg.game_id, tg.player_id)], dtype=object)
    covered = set(dec.loc[nb.injury_coverage(data["report"].assign(report_ts=data["report"].report_ts
                                                                   + pd.Timedelta(minutes=REPORT_LAG_MIN)),
                                             dec).values, "game_id"])
    # the chance a listed pool player plays: every team-game of STATUS_FIRST .. the last priced season - 1, its
    # pool at tip minus REF_LEAD_MIN, his status then, and whether he played (doc section 16)
    fg = rg[rg.season.between(STATUS_FIRST, int(tg.season.max()) - 1)]
    ftip = pd.to_datetime(fg.commence_time, utc=True) - pd.Timedelta(minutes=REF_LEAD_MIN)
    ftt = pd.concat([pd.DataFrame({"game_id": fg.game_id.values, "team": fg[c].values, "date": pd.to_datetime(fg.game_date).values,
                                   "T": ftip.reset_index(drop=True), "season": fg.season.astype(int).values}) for c in ("home_team", "away_team")],
                    ignore_index=True)
    fpool = pool_frame(pg, hist, ftt, box, rep_ev)
    frep = report_at(data["report"][data["report"].game_id.isin(set(fg.game_id))],
                     pd.DataFrame({"game_id": fg.game_id.to_numpy(), "decision_ts": ftip.reset_index(drop=True)}), roster)
    fst = dict(zip(zip(frep.game_id, frep.player_id), frep.status))
    played = set(zip(log.loc[log.minutes.fillna(0) > 0, "game_id"], log.loc[log.minutes.fillna(0) > 0, "player_id"].astype(str)))
    fit = pd.DataFrame({"season": fpool.season.to_numpy(int),
                        "status": [fst.get(k) for k in zip(fpool.game_id, fpool.player_id)],
                        "played": [k in played for k in zip(fpool.game_id, fpool.player_id)]})
    status = pool_status_rates(fit, sorted(set(tg.season)))
    # the team's pool and its expected first-quarter minutes
    tt = tg[tg.team.notna()][["game_id", "team", "date", "T", "season"]].drop_duplicates(["game_id", "team"])
    pool = pool_frame(pg, hist, tt, box, rep_ev)
    tg = reallocate(tg, pool, st, status)
    why = np.full(len(tg), "", dtype=object)
    why[(tg.n_q1.fillna(0) < MIN_Q1_GAMES).to_numpy()] = "fewer than 3 earlier first-quarter games"
    why[(why == "") & tg.team.isna().to_numpy()] = "latest team is neither side"
    why[(why == "") & (tg.status == "Out").to_numpy()] = "listed Out"
    why[(why == "") & ~(tg.E >= E_MIN).to_numpy()] = "team pool under 30 minutes"
    tg["why"] = why
    tg["has_number"] = why == ""
    tg["report_covered"] = tg.game_id.isin(covered)
    # the per-minute rate
    ri = rate_inputs(log, rg, tg)
    hist_rows = pg[pg.season == HISTORY]
    ri_h = rate_inputs(log, rg, hist_rows[["player_id", "season", "date"]])
    k = fit_k(ri_h, hist_rows[list(STATS)].reset_index(drop=True), hist_rows.minutes.to_numpy(float))
    for s in STATS:
        tg[f"rate_{s}"] = shrunk_rate(ri, s, *k[s])
        tg[f"raw_{s}"] = tg.mu_min * tg[f"rate_{s}"]
    # the first-quarter factor and alpha, walk-forward
    q1 = tg[["game_id", "player_id"]].merge(settled.q1, on=["game_id", "player_id"], how="left")
    tg["q1_sec_actual"] = q1.q1_sec.fillna(0.0).to_numpy()
    factor, alpha, maps, checks = {}, {}, {}, {}
    for s, m in zip(STATS, Q1_MARKETS):
        y = q1[s].to_numpy(float)
        ok = (tg.has_number & (tg.q1_sec_actual > 0) & tg.game_id.isin(settled.valid[m])).to_numpy() & np.isfinite(y)
        f_s, a_s, m_s, mu_all = walk_forward(y, tg[f"raw_{s}"].to_numpy(float), tg.season.to_numpy(int), ok, s)
        factor.update({(s, S): v for S, v in f_s.items()})
        alpha.update({(s, S): v for S, v in a_s.items()})
        maps.update({(s, S): v for S, v in m_s.items()})
        tg[f"mu_{s}"] = mu_all
        if s in MAP_STATS:
            checks[s] = map_check(y, tg[f"raw_{s}"].to_numpy(float), tg.date.to_numpy(),
                                  ok & (tg.season == HISTORY).to_numpy())
    notes = {"seconds": round(time.time() - t0, 1), "targets": int(len(tg)), "with_number": int(tg.has_number.sum()),
             "why_no_number": tg.loc[~tg.has_number, "why"].value_counts().to_dict(),
             "report_covered_share": float(tg.drop_duplicates("game_id").report_covered.mean()),
             "line_map_check_2023_24": checks}
    keep = ["game_id", "player_id", "season", "date", "T", "team", "status", "m", "n_q1", "E", "r", "mu_min", "has_number",
            "why", "report_covered", *[f"rate_{s}" for s in STATS], *[f"raw_{s}" for s in STATS], *[f"mu_{s}" for s in STATS]]
    return Projection(tg[keep], k, status, factor, alpha, notes, maps)


# ── offers, pricing and the placebo ─────────────────────────────────────────

def with_props(co: pd.DataFrame, one: pd.DataFrame, settled: Settled) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(coherent rows, one-sided rows, the proposition table) with an integer prop_id per (game, player,
    market) and the settling first-quarter stat. The main line: the commonest line among the
    proposition's coherent quotes, a tie to the lower (one-sided-only propositions: their own line)."""
    allr = pd.concat([co.assign(two=True), one.assign(two=False)], ignore_index=True).sort_values(KEY)
    allr["prop_id"] = allr.groupby(KEY, sort=False).ngroup().astype(np.int64)
    allr["T"] = pd.to_datetime(allr.snapshot_at, utc=True, format="ISO8601")
    lc = allr[allr.two].groupby(["prop_id", "line"]).size().rename("n").reset_index().sort_values(
        ["prop_id", "n", "line"], ascending=[True, False, True]).drop_duplicates("prop_id").set_index("prop_id").line
    lo = allr[~allr.two].groupby("prop_id").line.min()
    p = allr.drop_duplicates("prop_id").sort_values("prop_id")
    q1 = p[["game_id", "player_id"]].merge(settled.q1, on=["game_id", "player_id"], how="left")
    stat = np.full(len(p), np.nan)
    for m, s in STAT_OF.items():
        sel = (p.market == m).to_numpy()
        stat[sel] = q1[s].to_numpy(float)[sel]
    if not np.isfinite(stat).all():
        raise RuntimeError(f"{int((~np.isfinite(stat)).sum())} kept propositions have no first-quarter line")
    props = pd.DataFrame({"prop_id": p.prop_id.to_numpy(np.int64), "game_id": p.game_id.values, "player_id": p.player_id.values,
                          "player_name": p.player_name.values, "market": p.market.values, "season": p.season.astype(int).values,
                          "game_date": p.game_date.astype(str).values, "T": p["T"].values, "lead_min": p.lead_min.values,
                          "has_two_sided": p.prop_id.isin(lc.index).values})
    props["main_line"] = props.prop_id.map(lc).fillna(props.prop_id.map(lo)).to_numpy(float)
    return allr[allr.two].drop(columns="two"), allr[~allr.two].drop(columns="two"), props.assign(stat=stat)


def attach_means(props: pd.DataFrame, proj: Projection) -> pd.DataFrame:
    t = props[["game_id", "player_id"]].merge(
        proj.table[["game_id", "player_id", "has_number", "why", "r", *[f"mu_{s}" for s in STATS]]],
        on=["game_id", "player_id"], how="left")
    out = props.copy()
    out["has_number"] = t.has_number.fillna(False).astype(bool).to_numpy()
    out["why"] = t.why.fillna("no projection row").to_numpy()
    mu = np.full(len(out), np.nan)
    for m, s in STAT_OF.items():
        sel = (out.market == m).to_numpy()
        mu[sel] = t[f"mu_{s}"].to_numpy(float)[sel]
    out["mu"] = np.where(out.has_number, mu, np.nan)
    out["alpha"] = [proj.alpha.get((STAT_OF[m], int(se)), np.nan) for m, se in zip(out.market, out.season)]
    out["map_key"] = [f"{STAT_OF[m]}|{int(se)}" if STAT_OF[m] in MAP_STATS else "" for m, se in zip(out.market, out.season)]
    out["r"] = t.r.to_numpy(float)
    return out


def long_offers(rows: pd.DataFrame, props: pd.DataFrame, sides=("over", "under")) -> pd.DataFrame:
    """One row per (quote, side) in the shape H.choose and H.grade read; the proposition's mean, alpha
    and main line ride along, and nv_over is the book's own proportional no-vig over (NaN one-sided)."""
    pm = props.set_index("prop_id")
    pid = rows.prop_id.to_numpy(np.int64)
    od = nb.decimal(rows.over_price.to_numpy(float))
    ud = nb.decimal(rows.under_price.fillna(np.nan).to_numpy(float))
    nv = np.where(np.isfinite(ud), (1.0 / od) / (1.0 / od + 1.0 / np.where(np.isfinite(ud), ud, 2.0)), np.nan)
    base = {"game_id": pid, "market": np.full(len(rows), HMARKET, dtype=object),
            "book": rows.bookmaker.to_numpy(dtype=object), "line": rows.line.to_numpy(float),
            "season": rows.season.astype(int).to_numpy(), "game_date": rows.game_date.astype(str).to_numpy(dtype=object),
            "T": rows["T"].values, "prop_market": rows.market.to_numpy(dtype=object),
            "mu_prop": pm.mu.reindex(pid).to_numpy(float), "alpha": pm.alpha.reindex(pid).to_numpy(float),
            "main_line": pm.main_line.reindex(pid).to_numpy(float), "nv_over": nv,
            "map_key": (pm.map_key.reindex(pid).fillna("").to_numpy(dtype=object) if "map_key" in pm
                        else np.full(len(rows), "", dtype=object)),
            "r_team": pm.r.reindex(pid).to_numpy(float) if "r" in pm else np.full(len(rows), np.nan)}
    parts = []
    if "over" in sides:
        parts.append(pd.DataFrame({**base, "side": "over", "price": rows.over_price.to_numpy(float)}))
    if "under" in sides:
        parts.append(pd.DataFrame({**base, "side": "under", "price": rows.under_price.to_numpy(float)}))
    out = pd.concat(parts, ignore_index=True)
    out["p_push"], out["mu"], out["p_home"] = 0.0, np.nan, np.nan
    return out


def model_p_over(mu: np.ndarray, line: np.ndarray, alpha: np.ndarray, keys=None, maps: dict | None = None) -> np.ndarray:
    """P(over) per offer: through its line map where `keys` names one in `maps` and the line is fitted
    (doc section 14), else the negative binomial with its alpha (0 = Poisson)."""
    out = np.full(len(mu), np.nan)
    if keys is not None and maps:
        keys = np.asarray(keys, dtype=object)
        for k in set(keys) - {""}:
            st, se = k.split("|")
            m = maps.get((st, int(se)))
            if m is None:
                continue
            s = keys == k
            out[s] = map_p_over(m, mu[s], line[s])
    ok = np.isfinite(mu) & np.isfinite(alpha) & ~np.isfinite(out)
    for a in np.unique(alpha[ok]):
        s = ok & (alpha == a)
        out[s] = nb.p_over(mu[s], line[s], float(a))
    return out


def map_fallbacks(off: pd.DataFrame, maps: dict) -> int:
    """Offers whose market has a line map and whose line it does not hold: priced by the negative binomial."""
    if not maps or not len(off):
        return 0
    keyed = off.map_key.to_numpy(dtype=object) != ""
    po = model_p_over(off.mu_prop.to_numpy(float), off.line.to_numpy(float), np.full(len(off), np.nan),
                      off.map_key.to_numpy(dtype=object), maps)
    return int((keyed & ~np.isfinite(po) & np.isfinite(off.mu_prop.to_numpy(float))).sum())


def priced(off: pd.DataFrame, maps: dict | None = None) -> pd.DataFrame:
    """The model's chance and EV on every offer (the cells' candidates)."""
    po = model_p_over(off.mu_prop.to_numpy(float), off.line.to_numpy(float), off.alpha.to_numpy(float),
                      off.map_key.to_numpy(dtype=object) if "map_key" in off else None, maps)
    p = np.where(off.side.to_numpy() == "over", po, 1.0 - po)
    o = off.assign(p_win=p)
    o = o[np.isfinite(p)]
    return o.assign(ev=o.p_win.to_numpy() * nb.decimal(o.price.to_numpy()) - 1.0).reset_index(drop=True)


def neutral_of(off: pd.DataFrame) -> pd.DataFrame:
    """The blind bet's prices: each offer at its own book's proportional no-vig (bar 4's chooser)."""
    p = np.where(off.side.to_numpy() == "over", off.nv_over.to_numpy(float), 1.0 - off.nv_over.to_numpy(float))
    o = off.assign(p_win=p)
    o = o[np.isfinite(p)]
    return o.assign(ev=o.p_win.to_numpy() * nb.decimal(o.price.to_numpy()) - 1.0).reset_index(drop=True)


def placebo_groups(keys: pd.DataFrame) -> np.ndarray:
    """(date, market); a (date, market) with fewer than THIN propositions joins the other thin
    propositions of its season and market."""
    d = keys.game_date.astype(str) + "|" + keys.prop_market.astype(str)
    n = d.map(d.value_counts()).to_numpy()
    wide = "S|" + keys.season.astype(str) + "|" + keys.prop_market.astype(str)
    return pd.factorize(np.where(n < THIN, wide, "D|" + d))[0]


def permute_within(groups: np.ndarray, rng) -> np.ndarray:
    """out[i] = the position whose value position i takes: a random permutation inside each group."""
    groups = np.asarray(groups)
    base = np.argsort(groups, kind="stable")
    order = np.lexsort((rng.random(len(groups)), groups))
    out = np.empty(len(groups), dtype=np.int64)
    out[base] = order
    return out


class Pricer:
    """One market's priced offers and its placebo: each proposition's mean over its main line goes to
    another proposition of the same placebo group, times its own main line, and its offers are
    re-priced at their own lines through its alpha. perm None is the real pricing."""

    def __init__(self, cand: pd.DataFrame, maps: dict | None = None):
        self.offers = cand.reset_index(drop=True)
        self.maps = maps or {}
        self.keys_map = (self.offers.map_key.to_numpy(dtype=object) if "map_key" in self.offers
                         else np.full(len(self.offers), "", dtype=object))
        ids, self.kid = np.unique(self.offers.game_id.to_numpy(np.int64), return_inverse=True)
        first = pd.Series(np.arange(len(self.offers))).groupby(self.kid).first().to_numpy()
        k = self.offers.iloc[first]
        self.keys = pd.DataFrame({"game_id": ids, "game_date": k.game_date.to_numpy(), "season": k.season.to_numpy(),
                                  "prop_market": k.prop_market.to_numpy()})
        self.main = k.main_line.to_numpy(float)
        self.ratio = k.mu_prop.to_numpy(float) / self.main
        self.groups = placebo_groups(self.keys)
        self.n = len(ids)
        self.dec = nb.decimal(self.offers.price.to_numpy(float))
        self.over = self.offers.side.to_numpy() == "over"
        self.line = self.offers.line.to_numpy(float)
        self.alpha = self.offers.alpha.to_numpy(float)
        self.ok_px = self.offers.price.to_numpy(float) >= H.PRICE_FLOOR
        self.cache: dict = {}

    def perm(self, seed: int | None) -> np.ndarray:
        return np.arange(self.n) if seed is None else permute_within(self.groups, np.random.default_rng(seed))

    def ev(self, seed: int | None) -> np.ndarray:
        if seed not in self.cache:
            mu = (self.ratio[self.perm(seed)] * self.main)[self.kid]
            po = model_p_over(mu, self.line, self.alpha, self.keys_map, self.maps)
            p = np.where(self.over, po, 1.0 - po)
            self.cache[seed] = (p * self.dec - 1.0).astype(np.float32)
        return self.cache[seed].astype(float)

    def frame(self, side: str, seed: int | None) -> pd.DataFrame:
        ev = self.ev(seed)
        on = self.over if side == "over" else ~self.over
        hit = np.nonzero(on & self.ok_px & (ev >= EV_LOWEST - 1e-12))[0]
        return self.offers.iloc[hit][PICK_COLS].assign(ev=ev[hit])

    def clear(self) -> None:
        self.cache.clear()


# ── the groups of cells ─────────────────────────────────────────────────────

@dataclass
class Group:
    family: str
    market: str                   # the prop market: the cell row's market label
    side: str
    book: str                     # "best", or the one book a control is restricted to
    quotes: str                   # "two_sided" or "one_sided"
    cuts: tuple
    cand: pd.DataFrame
    neutral: pd.DataFrame
    placebo: object | None
    meaning: str
    bands: bool = True

    @property
    def name(self) -> str:
        return f"{self.family}_{self.market}_{self.side}_{self.book}_{self.quotes}"


def build_groups(co_off: pd.DataFrame, one_off: pd.DataFrame, maps: dict | None = None) -> list[Group]:
    """The 18 registered cells' groups (market x side, 3 cuts each), then the controls. `maps`: the points
    line maps (doc section 14); empty prices every market through its negative binomial."""
    groups = []
    for m in Q1_MARKETS:
        o = co_off[co_off.prop_market == m]
        cand = priced(o, maps)
        neu = neutral_of(o)
        pr = Pricer(cand, maps)
        for side in ("over", "under"):
            c = cand[cand.side == side].reset_index(drop=True)
            groups.append(Group(FAMILY, m, side, "best", "two_sided", EV_CUTS, c, neu, pr,
                                "projected first-quarter minutes x per-minute rate against the book's price"))
            groups.append(Group(CTL_HR, m, side, BOOK_HR, "two_sided", EV_CUTS,
                                c[c.book == BOOK_HR].reset_index(drop=True), neu[neu.book == BOOK_HR].reset_index(drop=True),
                                None, "control: the same cells at Hard Rock alone", bands=False))
            if m == "player_points_q1":
                groups.append(Group(CTL_FD, m, side, BOOK_FD, "two_sided", EV_CUTS,
                                    c[c.book == BOOK_FD].reset_index(drop=True),
                                    neu[neu.book == BOOK_FD].reset_index(drop=True),
                                    None, "control: the same cells at FanDuel alone", bands=False))
            groups.append(Group(CTL_BLIND, m, side, "best", "two_sided", (-np.inf,),
                                neu[neu.side == side].reset_index(drop=True), neu, None,
                                "control: every proposition, this side, no model, best offer by its book's no-vig",
                                bands=False))
        oo = one_off[one_off.prop_market == m]
        if len(oo):
            oc = priced(oo, maps)
            groups.append(Group(CTL_ONE, m, "over", "best", "one_sided", EV_CUTS, oc.reset_index(drop=True),
                                oc.assign(p_win=1.0 / nb.decimal(oc.price.to_numpy()), ev=0.0), None,
                                "control: the over cells on one-sided Hard Rock quotes", bands=False))
    return groups


def registered(groups: list[Group]) -> list[tuple]:
    cells = [(g.market, g.side, c) for g in groups if g.family == FAMILY for c in g.cuts]
    assert len(cells) == EXPECTED_CELLS, len(cells)
    return cells


NO_QUOTES = pd.DataFrame({"game_id": pd.Series(dtype="int64")})
NO_FETCHES = pd.DataFrame({"game_id": pd.Series(dtype="int64"), "fetch_at": pd.Series(dtype="datetime64[ns]"),
                           "lead_min": pd.Series(dtype="float64")})


def games_table(props: pd.DataFrame, stat: np.ndarray | None) -> pd.DataFrame:
    """The harness's games: one row per proposition. stat None: every score 0 (the timed smoke run)."""
    n = len(props)
    return pd.DataFrame({"game_id": props.prop_id.to_numpy(np.int64), "season": props.season.astype(int).to_numpy(),
                         "game_date": props.game_date.astype(str).to_numpy(), "tip": props["T"].values,
                         "home_team": "", "away_team": "",
                         "home_score": np.zeros(n) if stat is None else np.asarray(stat, float), "away_score": np.zeros(n)})


def times_table(props: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"game_id": props.prop_id.to_numpy(np.int64), "T": props["T"].values,
                         "lead_min": props.lead_min.to_numpy(float)})


def _placebo_frames(g: Group, seeds) -> G5.LazyFrames:
    done = [0]

    def build(seed):
        done[0] += 1
        if done[0] % len(seeds) == 0:
            say(f"{g.name}: placebo, cut {done[0] // len(seeds)} of {len(g.cuts)}")
        return g.placebo.frame(g.side, seed)
    return G5.LazyFrames(seeds, build)


def emit(g: Group, games: pd.DataFrame, times: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[dict]:
    """One group's cells through H.run_cells, each registered row with its bands (section 9.1's bar 5)."""
    ids = set(g.cand.game_id) | set(g.neutral.game_id)
    gm = games[games.game_id.isin(ids)].reset_index(drop=True)
    dd = H.Data(games=gm, quotes=NO_QUOTES, fetches=NO_FETCHES)
    t = times[times.game_id.isin(ids)].reset_index(drop=True)
    frames = _placebo_frames(g, seeds) if (g.placebo is not None and seeds) else None
    # H.p_one_sided re-draws a p under 0.01 with 400,000 resamples for the first search's false-discovery bar;
    # section 9.1's bars never read that p (the propoffline search's dated line). Off here, put back after.
    refine = H.P_REFINE_BELOW
    H.P_REFINE_BELOW = 0.0
    try:
        rows = H.run_cells(dd, g.family, POINT, g.cand, g.neutral, list(g.cuts), {g.market: [g.side]}, placebo=frames,
                           strength="ev", choose_seasons=CHOOSE, times=t, market_groups={g.market: (HMARKET,)})
    finally:
        H.P_REFINE_BELOW = refine
    for r in rows:
        if g.bands:
            bounds = G5.band_bounds(g.cuts, r["cut_index"], lowest=EV_LOWEST)
            pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
            r.update(G5.band_columns(g.cand, r["side"], "ev", bounds, gm, pool))
        r.update({"axis_book": g.book, "axis_quotes": g.quotes, "signal_meaning": g.meaning})
    return rows


# ── reported beside, never a bar ────────────────────────────────────────────

def live_keys() -> dict:
    """The live full-game prop models' bets, keys only: nba_prop_market's graded bets of record 4.3 (its five
    markets) and nba_prop_projection's graded card at its six cells' sides and floors (price >= -200), for
    2024-25 and 2025-26. -> {"any": {(game, player)}, "stat": {(game, player, stat)}, "side": {(game, player, stat, side)}}."""
    import config
    from models import nba_prop_market as PMk
    from models import nba_prop_projection as pj
    out = {"any": set(), "stat": set(), "side": set(), "rows": {}}
    if RULE_BETS.exists():
        a = pd.read_parquet(RULE_BETS, columns=["game_id", "player_id", "market", "side", "season"])
        a = a[a.market.isin(PMk.MARKETS) & a.season.isin(PROP_SEASONS)]
        out["rows"]["nba_prop_market"] = int(len(a))
        out["_a"] = a
    if CARD_BETS.exists():
        b = pd.read_parquet(CARD_BETS, columns=["game_id", "player_id", "market", "side", "season", "ev", "price"])
        keep = np.zeros(len(b), bool)
        for m, (sides, floor) in pj.CARD.items():
            keep |= (b.market == m).to_numpy() & b.side.isin(sides).to_numpy() & (b.ev >= floor).to_numpy() \
                & (b.price >= float(config.DEFAULT_MIN_ODDS)).to_numpy()
        b = b[keep & b.season.isin(PROP_SEASONS).to_numpy()]
        out["rows"]["nba_prop_projection"] = int(len(b))
        out["_b"] = b
    for f in (out.pop("_a", None), out.pop("_b", None)):
        if f is None:
            continue
        pid = f.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
        st = f.market.str.replace("player_", "", regex=False)
        out["any"] |= set(zip(f.game_id, pid))
        out["stat"] |= set(zip(f.game_id, pid, st))
        out["side"] |= set(zip(f.game_id, pid, st, f.side))
    return out


def overlap(b: pd.DataFrame, props: pd.DataFrame, live: dict) -> dict:
    pm = props.set_index("prop_id")
    g, pl = pm.game_id.reindex(b.game_id).to_numpy(), pm.player_id.reindex(b.game_id).astype(str).to_numpy()
    st = pm.market.reindex(b.game_id).map(STAT_OF).to_numpy()
    if not len(b):
        return {"share_live_any": np.nan, "share_live_same_stat": np.nan, "share_live_same_stat_side": np.nan}
    return {"share_live_any": float(np.mean([(a, c) in live["any"] for a, c in zip(g, pl)])),
            "share_live_same_stat": float(np.mean([(a, c, s) in live["stat"] for a, c, s in zip(g, pl, st)])),
            "share_live_same_stat_side": float(np.mean([(a, c, s, sd) in live["side"]
                                                        for a, c, s, sd in zip(g, pl, st, b.side)]))}


def _line(g: Group, cut: float, what: str, b: pd.DataFrame) -> dict:
    return {"family": g.family, "market": g.market, "side": g.side, "book_axis": g.book, "cut": cut, "what": what,
            "bets": int(len(b)), "units": float(b["units"].sum()) if len(b) else 0.0,
            "risk": float(b["risk"].sum()) if len(b) else 0.0, "roi": H.roi(b) if len(b) else np.nan}


def beside_rows(g: Group, games: pd.DataFrame, props: pd.DataFrame, live: dict) -> list[dict]:
    """The doc's beside list, every cut. Runs on what `games` holds: the graded run's stats, or zeros in
    the timed smoke run (whose rows are thrown away)."""
    rows = []
    lead = props.set_index("prop_id").lead_min
    for cut in g.cuts:
        b = H.grade(H.choose(g.cand, cut, sides=[g.side]), games)
        rows.append(_line(g, cut, "all", b))
        if not len(b):
            continue
        for s in sorted(b.season.unique()):
            rows.append(_line(g, cut, f"season {int(s)}", b[b.season == s]))
            for bk, d in b[b.season == s].groupby("book"):
                rows.append(_line(g, cut, f"season {int(s)} at {bk}", d))
        mon = b.game_date.astype(str).str[5:7].to_numpy()
        for mm, nm in BESIDE_MONTHS.items():
            rows.append(_line(g, cut, f"month {nm}", b[mon == mm]))
        rows.append(_line(g, cut, "other months", b[~np.isin(mon, list(BESIDE_MONTHS))]))
        ld = b.game_id.map(lead).to_numpy(float)
        rows.append(_line(g, cut, "lead 50-60", b[(ld >= 50) & (ld < 60)]))
        rows.append(_line(g, cut, "lead 60-70", b[(ld >= 60) & (ld <= 70)]))
        if "r_team" in b:
            r = b.r_team.to_numpy(float)
            for lo, hi in R_BANDS:
                rows.append(_line(g, cut, f"reallocation r {lo}-{hi}", b[(r >= lo) & (r < hi)]))
        q = np.percentile(b.price.to_numpy(float), [0, 5, 50, 95, 100])
        rows.append({**_line(g, cut, "prices laid", b), "price_min": q[0], "price_p5": q[1], "price_median": q[2],
                     "price_p95": q[3], "price_max": q[4], **overlap(b, props, live)})
    return rows


def write_group(g: Group, rows: list[dict], beside: list[dict], out: Path) -> None:
    """The cell file comes last: it marks the group finished, so a stopped run redoes a part-written one."""
    pd.DataFrame(beside).to_parquet(out / f"beside_{g.name}.parquet")
    L.write_cells(rows, out / f"cells_{g.name}.parquet")


# ── real data ───────────────────────────────────────────────────────────────

@dataclass
class Prep:
    props: pd.DataFrame
    co: pd.DataFrame
    one: pd.DataFrame
    co_off: pd.DataFrame
    one_off: pd.DataFrame
    settled: Settled
    proj: Projection
    notes: dict
    pre: pd.DataFrame


def load_data(cache: Path, work: Path) -> dict:
    cache, pulled = Path(cache), Path(work) / "pulled"
    rd = lambda t: pd.read_parquet(cache / f"{t}.parquet")  # noqa: E731
    games = rd("nba_games")
    games = games[(games.sport == "NBA") & games.home_score.notna()].copy()
    return {"games": games, "schedule": rd("nba_schedule"), "log": rd("nba_player_game_log"),
            "report": rd("nba_injury_report"), "stints": rd("nba_stints"), "id_map": rd("nba_player_id_map"),
            "inactives": rd("nba_game_inactives"),
            "periods": rd("nba_period_scores"),
            "plays": pd.read_parquet(pulled / "nba_pbp_slim.parquet"), "pbp_games": pd.read_parquet(pulled / "nba_pbp_games.parquet")}


def prepare(cache: Path = H.CACHE, work: Path | None = None) -> Prep:
    """Every frame the cells read, on the real data. Reads earlier games' results for the fits and the
    first-quarter stats for settlement; joins no stat to a bet."""
    t0 = time.time()
    work = work_dir() if work is None else Path(work)
    data = load_data(cache, work)
    reg = nb.regular_game_ids(data["games"], data["schedule"])
    rg = data["games"][data["games"].game_id.isin(reg)]
    settled = settle(data["plays"], data["pbp_games"], data["stints"], data["id_map"], data["log"], rg, data["periods"])
    data["court_sec"], data["team_court"], _ = court_seconds(data["stints"])
    del data["plays"]
    say(f"settlement built at {time.time() - t0:.0f}s")
    q = matched_quotes(cache, work)
    co, one, notes, pre = refuse_rows(q, settled)
    say(f"quotes ready at {time.time() - t0:.0f}s: {notes}")
    co, one, props = with_props(co, one, settled)
    tips = rg.set_index("game_id").commence_time
    hist = settled.q1[settled.q1.q1_sec > 0][["game_id", "player_id"]]
    hist = hist[hist.game_id.map(rg.set_index("game_id").season).isin([HISTORY, 2025])]
    snap = props.drop_duplicates("game_id").set_index("game_id")["T"]
    tgt = pd.concat([props[["game_id", "player_id"]], hist], ignore_index=True).drop_duplicates()
    T = tgt.game_id.map(snap)
    ref = pd.to_datetime(tgt.game_id.map(tips), utc=True) - pd.Timedelta(minutes=REF_LEAD_MIN)
    tgt["T"] = pd.to_datetime(T, utc=True).fillna(ref)
    proj = project(data, settled, tgt)
    say(f"projection at {time.time() - t0:.0f}s: {proj.notes}")
    props = attach_means(props, proj)
    co_off = long_offers(co[co.prop_id.isin(props.loc[props.has_number, "prop_id"])], props)
    one_off = long_offers(one[one.prop_id.isin(props.loc[props.has_number, "prop_id"])], props, sides=("over",))
    return Prep(props, co, one, co_off, one_off, settled, proj, notes, pre)


# ── synthetic world: the harness path, with and without a planted edge ──────

def _american(p: float) -> float:
    p = float(np.clip(p, 0.03, 0.97))
    return float(round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p))


def synthetic_world(seed: int = 1, days: int = 30, edge: bool = True) -> dict:
    """Invented propositions for both graded seasons, all three markets, two books (one two-sided, one
    one-sided). The stat is Poisson with a known mean. edge=True: the book prices from a noisy mean and the
    model knows the truth; edge=False: the model is the noisy one and the book knows the truth."""
    rng = np.random.default_rng(seed)
    rows, props = [], []
    pid = 0
    for season, year in ((2025, 2024), (2026, 2025)):
        for d in range(days):
            date = str(pd.Timestamp(f"{year}-12-01") + pd.Timedelta(days=d))[:10]
            for m, base in (("player_points_q1", 4.0), ("player_rebounds_q1", 1.3), ("player_assists_q1", 0.9)):
                for k in range(12):
                    truth = base * float(rng.lognormal(0.0, 0.35))
                    noisy = truth * float(rng.lognormal(0.0, 0.30))
                    book_mu, model_mu = (noisy, truth) if edge else (truth, noisy)
                    line = float(np.floor(book_mu) + 0.5)
                    pf = float(nb.p_over(np.array([book_mu]), np.array([line]), 0.0)[0])
                    props.append({"prop_id": pid, "game_id": f"G{season}{d}{k}", "player_id": str(k), "player_name": f"P{k}",
                                  "market": m, "season": season, "game_date": date,
                                  "T": pd.Timestamp(f"{date}T23:05:00Z"), "lead_min": 54.4, "has_two_sided": True,
                                  "main_line": line, "stat": float(rng.poisson(truth)), "has_number": True, "why": "",
                                  "mu": model_mu, "alpha": 0.0})
                    for bk, two in ((BOOK_HR, True), (BOOK_FD, True), ("betmgm", False)):
                        rows.append({"prop_id": pid, "bookmaker": bk, "line": line, "season": season, "game_date": date,
                                     "T": pd.Timestamp(f"{date}T23:05:00Z"), "market": m, "two": two,
                                     "over_price": _american(pf * 1.04),
                                     "under_price": _american((1 - pf) * 1.04) if two else np.nan})
                    pid += 1
    r = pd.DataFrame(rows)
    return {"props": pd.DataFrame(props), "co": r[r.two].drop(columns="two"), "one": r[~r.two].drop(columns="two")}


def world_groups(world: dict) -> list[Group]:
    p = world["props"]
    return build_groups(long_offers(world["co"], p), long_offers(world["one"], p, sides=("over",)))


def assert_identity(g: Group) -> None:
    """The identity permutation returns the real bets at every cut."""
    for cut in g.cuts:
        a = H.choose(g.cand, cut, sides=[g.side])[["game_id", "book"]].sort_values("game_id").to_numpy()
        b = H.choose(g.placebo.frame(g.side, None), cut, sides=[g.side])[["game_id", "book"]].sort_values("game_id").to_numpy()
        assert len(a) == len(b) and (a == b).all(), (g.name, cut, len(a), len(b))


def synthetic_checks(n_placebo: int = 3) -> dict:
    """Plumbing on the invented world, through the same builders and H.run_cells. Raises on a fault, and
    asserts the world holds every group before believing a check that says it covers one."""
    world = synthetic_world()
    groups = world_groups(world)
    registered(groups)
    games, times = games_table(world["props"], world["props"].stat.to_numpy()), times_table(world["props"])
    rows = []
    for g in groups:
        assert len(g.cand) > 0, f"the synthetic world holds no offers for {g.name}"
        if g.placebo is not None:
            assert_identity(g)
        rows += emit(g, games, times, seeds=tuple(range(1, n_placebo + 1)) if g.placebo is not None else ())
        if g.placebo is not None:
            g.placebo.clear()
    t = pd.DataFrame(rows)
    assert (t.loc[t.family == FAMILY, "pool_n"] > 0).all()
    assert t.loc[t.family == FAMILY, "band0_n"].notna().all()
    return {"synthetic_checks": "pass", "rows": int(len(t))}


# ── smoke and full ──────────────────────────────────────────────────────────

def counts_table(groups: list[Group]) -> pd.DataFrame:
    """The bets each cell would place: counted, never graded."""
    out = []
    for g in groups:
        for cut in g.cuts:
            b = H.choose(g.cand, cut, sides=[g.side])
            by = b.season.value_counts().to_dict()
            out.append({"family": g.family, "market": g.market, "side": g.side, "book": g.book, "cut": cut,
                        **{f"bets_{s}": int(by.get(s, 0)) for s in PROP_SEASONS}, "bets_pooled": int(len(b))})
    return pd.DataFrame(out)


def placebo_difference(groups: list[Group], seeds=(1, 2, 3)) -> pd.DataFrame:
    """By registered cell, on the real data: the share of a placebo run's bets not among the real bets
    (same proposition, side and book), and the run's bet count against the real count."""
    out = []
    for g in groups:
        if g.placebo is None:
            continue
        for cut in g.cuts:
            real = H.choose(g.cand, cut, sides=[g.side])
            rk = set(zip(real.game_id, real.book))
            sh, n = [], []
            for s in seeds:
                pb = H.choose(g.placebo.frame(g.side, s), cut, sides=[g.side])
                same = np.fromiter(((a, b) in rk for a, b in zip(pb.game_id, pb.book)), bool, len(pb))
                sh.append(float(1 - same.mean()) if len(pb) else np.nan)
                n.append(len(pb))
            out.append({"market": g.market, "side": g.side, "cut": cut, "real_bets": int(len(real)),
                        "placebo_bets": float(np.mean(n)), "share_differ": float(np.nanmean(sh))})
    for g in groups:
        if g.placebo is not None:
            g.placebo.clear()
    return pd.DataFrame(out)


def low_share_note(pl: pd.DataFrame) -> str:
    low = pl[pl.share_differ < LOW_SHARE]
    if low.empty:
        return f"Every registered cell's placebo changes at least {LOW_SHARE:.0%} of its bets."
    names = ", ".join(f"{r.market} {r.side} EV >= {r.cut:.2f} ({r.share_differ:.2f})" for r in low.itertuples())
    return (f"LOW: in {len(low)} cells a placebo run changes under {LOW_SHARE:.0%} of the bets: {names}. Most of such a "
            "run is the real bets, so only the bets it changes can separate the real return from the placebo's.")


def timed_runs(groups: list[Group], games0: pd.DataFrame, times: pd.DataFrame, props: pd.DataFrame, live: dict,
               scratch: Path) -> pd.DataFrame:
    """Each group once with no placebo through --full's own writer (files thrown away), then three placebo runs
    through the steps H.run_cells takes per run, on results set to zero: the real code path's time, nothing
    real graded. The projection uses the median run."""
    out = []
    for g in groups:
        t0 = time.time()
        write_group(g, emit(g, games0, times, seeds=()), beside_rows(g, games0, props, live), scratch)
        base = time.time() - t0
        run, mb = 0.0, 0.0
        if g.placebo is not None:
            ids = set(g.cand.game_id) | set(g.neutral.game_id)
            gm = games0[games0.game_id.isin(ids)].reset_index(drop=True)
            runs = []
            for seed in (1, 2, 3):
                t1 = time.time()
                for cut in g.cuts:
                    pc = g.placebo.frame(g.side, seed)
                    gp = H.grade(H.choose(pc[pc.market.isin((HMARKET,))], cut, sides=[g.side]), gm)
                    if len(gp):
                        H.roi(gp[gp.season.isin(CHOOSE)])
                runs.append(time.time() - t1)
            run = float(np.median(runs))
            mb = N_PLACEBO * g.placebo.cache[1].nbytes / 2**20
            g.placebo.clear()
        out.append({"group": g.name, "seconds_without_placebo": round(base, 1), "seconds_one_placebo_all_cuts": round(run, 3),
                    "projected_seconds": round(base + N_PLACEBO * run, 1), "placebo_cache_mb": round(mb, 1)})
    return pd.DataFrame(out)


def peak_gb() -> float | None:
    try:
        import psutil
        return psutil.Process().memory_info().peak_wset / 2**30
    except (ImportError, AttributeError):
        return None


def smoke_report(prep: Prep) -> dict:
    """Everything --smoke prints from a prepared run. Nothing here grades a real bet: the only H.grade calls
    are the timed runs, on games_table(props, None), whose scores are all zero."""
    os.environ.pop(BETS_ENV, None)
    pd.set_option("display.width", 230)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 300)
    s = prep.settled.notes
    print("\nSETTLEMENT (doc section 3):")
    print(json.dumps(s, indent=1, default=str))
    pre = prep.pre
    print("\nRow rules (doc section 4):", json.dumps(prep.notes, indent=1))
    played_not_q1 = pre[pre.kept & (pre.minutes.fillna(0) > 0) & (pre.q1_sec <= 0)]
    print("\nPropositions (after the row rules, in a kept game) where the player played the game and had no "
          f"first-quarter court time: {len(played_not_q1):,} of {int(pre.kept.sum()):,}; by season and market:")
    print(played_not_q1.groupby(["season", "market"]).size().to_string())
    p = prep.props
    print("\nPropositions by season and market (settled, not void), with a number:")
    print(p.groupby(["season", "market"]).agg(props=("prop_id", "size"), with_number=("has_number", "sum"),
                                              two_sided=("has_two_sided", "sum")).to_string())
    print("Why no number:", p.loc[~p.has_number, "why"].value_counts().to_dict())
    pj_ = prep.proj
    print("\nPROJECTION (no result of a priced game read):")
    print("  Kc, Kp by stat (2023-24):", pj_.k)
    print("  P(plays | status) by priced season:", json.dumps(pj_.status, indent=1))
    print("  first-quarter factor (stat, season):", {f"{k[0]} {k[1]}": round(v, 4) for k, v in pj_.factor.items()})
    print("  alpha (stat, season):", {f"{k[0]} {k[1]}": round(v, 4) for k, v in pj_.alpha.items()})
    print("  notes:", pj_.notes)
    t = pj_.table[pj_.table.has_number]
    print("  expected first-quarter minutes when he plays it, percentiles 1/25/50/75/99:",
          np.percentile(t.mu_min, [1, 25, 50, 75, 99]).round(2).tolist(), " r:", np.percentile(t.r, [1, 50, 99]).round(3).tolist())
    pn = p[p.has_number]
    print("  mean over main line by market (median, 5th, 95th):",
          {m: np.percentile(g.mu / g.main_line, [50, 5, 95]).round(3).tolist() for m, g in pn.groupby("market")})
    print("\nEXTREMES of every line and price read (coherent / one-sided):")
    for nm, r in (("coherent", prep.co), ("one-sided", prep.one)):
        print(nm)
        print(r.groupby("market").agg(rows=("line", "size"), line_min=("line", "min"), line_max=("line", "max"),
                                      over_min=("over_price", "min"), over_max=("over_price", "max"),
                                      under_min=("under_price", "min"), under_max=("under_price", "max")).to_string())
        print(r.groupby(["season", "market", "bookmaker"]).size().unstack(-1).fillna(0).astype(int).to_string())
    live = live_keys()
    maps = prep.proj.maps or {}
    groups = build_groups(prep.co_off, prep.one_off, maps)
    registered(groups)
    print("\nPOINTS LINE MAP (doc section 14): its check on 2023-24 alone, fitted on the first half of dates, read on "
          "the second half:")
    print(pd.DataFrame(pj_.notes["line_map_check_2023_24"].get("points", [])).round(3).to_string(index=False))
    print("  lines fitted by priced season:", {f"{k[0]} {k[1]}": v["lines"].tolist() for k, v in maps.items()})
    print("  offers priced by the negative binomial because their line is outside the map: coherent",
          map_fallbacks(prep.co_off, maps), "; one-sided", map_fallbacks(prep.one_off, maps))
    print("\nTwo-sided propositions with a number, by season and book:")
    tw = prep.co_off.drop_duplicates(["game_id", "book"])
    print(tw.groupby(["season", "prop_market", "book"]).size().unstack(-1).fillna(0).astype(int).to_string())
    print("\nHighest-EV offers per registered group (no result read):")
    meta = p.set_index("prop_id")
    for g in groups:
        if g.family == FAMILY:
            top = g.cand.sort_values("ev", ascending=False).head(6)
            top = top.assign(player=top.game_id.map(meta.player_name), date=top.game_id.map(meta.game_date),
                             mu=top.game_id.map(meta.mu))
            print(g.name)
            print(top[["date", "player", "book", "line", "side", "price", "mu", "p_win", "ev"]].round(3).to_string(index=False))
    counts = counts_table(groups)
    print("\nCOUNTS BEFORE GRADING (bets each cell would place; no result read):")
    print(counts.to_string(index=False))
    for g in groups:
        if g.placebo is not None:
            assert_identity(g)
    print("\nPlacebo: the identity permutation returns the real bets in every registered group.")
    seen = set()
    for g in groups:
        if g.placebo is not None and id(g.placebo) not in seen:
            seen.add(id(g.placebo))
            sizes = pd.Series(g.placebo.groups).value_counts()
            print(f"  {g.market}: {g.placebo.n:,} propositions in {len(sizes):,} groups; median group "
                  f"{int(sizes.median())}; {float((sizes == 1).sum()) / max(g.placebo.n, 1):.2%} alone")
    pl = placebo_difference(groups)
    print("\nPLACEBO: share of placebo bets differing from the real bets, by cell, real data (3 runs):")
    print(pl.round(3).to_string(index=False))
    print(low_share_note(pl))
    print("\nOVERLAP with the live full-game prop models (counts only; rows read:", live["rows"], "):")
    ov = []
    for g in groups:
        if g.family == FAMILY:
            for cut in g.cuts:
                b = H.choose(g.cand, cut, sides=[g.side])
                ov.append({"market": g.market, "side": g.side, "cut": cut, "bets": len(b), **overlap(b, p, live)})
    print(pd.DataFrame(ov).round(3).to_string(index=False))
    print("\nBets each registered cell would place in October and in February (beside, never judged; counts only):")
    mrows = []
    for g in groups:
        if g.family == FAMILY:
            for cut in g.cuts:
                b = H.choose(g.cand, cut, sides=[g.side])
                mon = b.game_date.astype(str).str[5:7]
                mrows.append({"market": g.market, "side": g.side, "cut": cut,
                              **{f"{nm} of {s - 1}-{str(s)[2:]}": int(((mon == mm) & (b.season == s)).sum())
                                 for mm, nm in BESIDE_MONTHS.items() for s in PROP_SEASONS}})
    print(pd.DataFrame(mrows).to_string(index=False))
    print("\nBets at the lowest cut by reallocation band r (counts only):")
    rb = []
    for g in groups:
        if g.family == FAMILY:
            b = H.choose(g.cand, g.cuts[0], sides=[g.side])
            r = b.r_team.to_numpy(float)
            rb.append({"market": g.market, "side": g.side, **{f"r {lo}-{hi}": int(((r >= lo) & (r < hi)).sum())
                                                             for lo, hi in R_BANDS}})
    print(pd.DataFrame(rb).to_string(index=False))
    print("\nPRICES each registered cell would lay (no result read):")
    pr = []
    for g in groups:
        if g.family == FAMILY:
            for cut in g.cuts:
                b = H.choose(g.cand, cut, sides=[g.side])
                if len(b):
                    q = np.percentile(b.price, [0, 5, 50, 95, 100])
                    pr.append({"market": g.market, "side": g.side, "cut": cut, "bets": len(b), "min": q[0], "p5": q[1],
                               "median": q[2], "p95": q[3], "max": q[4]})
    print(pd.DataFrame(pr).to_string(index=False))
    games0 = games_table(p, None)
    with tempfile.TemporaryDirectory() as scratch:
        tm = timed_runs(groups, games0, times_table(p), p, live, Path(scratch))
    print("\nTIMED on results set to zero (nothing real graded; every file --full writes was written once and removed):")
    print(tm.to_string(index=False))
    return {"counts": counts, "placebo": pl, "timed": tm, "groups": groups}


def smoke(cache: Path = H.CACHE) -> dict:
    t0 = time.time()
    print(json.dumps(synthetic_checks()))
    say(f"synthetic checks done at {time.time() - t0:.0f}s")
    prep = prepare(cache)
    used = time.time() - t0
    out = smoke_report(prep)
    total = float(out["timed"].projected_seconds.sum())
    print(f"\nPROJECTED --full: {total / 60:.1f} minutes of cells, plus {used / 60:.1f} minutes of loading. "
          "Measured on this machine under its load at this moment.")
    extra = float(out["timed"].placebo_cache_mb.max()) / 1024
    pk = peak_gb()
    print(f"peak memory of this process: {pk:.1f} GB" if pk is not None else "peak memory not read (no psutil)",
          f"; --full adds at most {extra:.2f} GB for one market's 200 placebo runs")
    print(f"smoke took {(time.time() - t0) / 60:.1f} minutes")
    return out


def refuse_full(cache: Path, work: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for f in ("q1_props", "nba_pbp_slim", "nba_pbp_games"):
        if not (Path(work) / "pulled" / f"{f}.parquet").exists():
            why.append(f"{Path(work) / 'pulled' / f}.parquet does not exist: run --pull")
    if not (Path(cache) / "nba_stints.parquet").exists():
        why.append(f"{Path(cache) / 'nba_stints.parquet'} does not exist: refresh the cache")
    import config
    books = (tuple(config.BEST_LINE_BOOKMAKERS), tuple(H.BETTABLE))
    if any(b != REGISTERED_BOOKS for b in books):
        why.append(f"the deciding books {books} are not the registered {REGISTERED_BOOKS}: an override (an .env or "
                   "environment variable) changed BEST_LINE_BOOKMAKERS")
    floors = (float(config.DEFAULT_MIN_ODDS), float(H.PRICE_FLOOR))
    if any(f != REGISTERED_FLOOR for f in floors):
        why.append(f"the price floor {floors} is not the registered {REGISTERED_FLOOR}: an override changed DEFAULT_MIN_ODDS")
    return why


def full(cache: Path = H.CACHE) -> None:
    work = work_dir()
    why = refuse_full(cache, work)
    if why:
        for x in why:
            print("REFUSED:", x)
        raise SystemExit(2)
    out = Path(os.environ[RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    saved = os.environ.pop(BETS_ENV)
    synthetic_checks()                                # never writes a bet file: the variable is unset while it runs
    os.environ[BETS_ENV] = saved
    say("synthetic checks pass")
    prep = prepare(cache, work)
    prep.props.drop(columns="T").to_parquet(out / "props.parquet")
    prep.proj.table.drop(columns=["T", "date"]).to_parquet(out / "projection.parquet")
    (out / "fits.json").write_text(json.dumps({"k": prep.proj.k, "status": prep.proj.status,
                                               "factor": {f"{a}|{b}": v for (a, b), v in prep.proj.factor.items()},
                                               "alpha": {f"{a}|{b}": v for (a, b), v in prep.proj.alpha.items()},
                                               "line_maps": {f"{a}|{b}": {k2: v2.tolist() for k2, v2 in m.items()}
                                                             for (a, b), m in (prep.proj.maps or {}).items()},
                                               "settlement": prep.settled.notes, "rows": prep.notes},
                                              indent=1, default=str), encoding="utf-8")
    live = live_keys()
    groups = build_groups(prep.co_off, prep.one_off, prep.proj.maps or {})
    registered(groups)
    games, times = games_table(prep.props, prep.props.stat.to_numpy()), times_table(prep.props)
    t_cells, done = time.time(), 0
    for i, g in enumerate(groups, start=1):
        if (out / f"cells_{g.name}.parquet").exists():
            say(f"group {i}/{len(groups)} {g.name}: already written, skipped")
            continue
        H._BET_FILES[0] = 1000 * i
        t1 = time.time()
        rows = emit(g, games, times, seeds=PLACEBO_SEEDS if g.placebo is not None else ())
        write_group(g, rows, beside_rows(g, games, prep.props, live), out)
        if g.placebo is not None and g.side == "under":
            g.placebo.clear()
        done += 1
        left = (time.time() - t_cells) / done * (len(groups) - i) / 60
        say(f"group {i}/{len(groups)} {g.name}: {len(rows)} cells in {time.time() - t1:.0f}s; "
            f"{(time.time() - t0) / 60:.0f} minutes so far, about {left:.0f} left")
    say(f"cells written to {out}: judge with python -m scripts.nba_game2_verdict --results {out} --house5, "
        f"then python -m scripts.nba_s_q1props --verdict {out}")


def strict_verdict(cells: pd.DataFrame) -> pd.DataFrame:
    """The verdict's own bars (house_verdict_bands), then the doc's reading of bar 3: both graded seasons,
    each with 30 or more bets, positive."""
    h = V.house_verdict_bands(cells)
    reg = h[~h.family.astype(str).str.startswith(V.CONTROL_PREFIX)].copy()
    n1, r1 = reg.get(f"n_{CHOOSE[0]}", 0), reg.get(f"roi_{CHOOSE[0]}", np.nan)
    reg["h3_both_seasons"] = (n1 >= 30) & (r1 > 0) & (reg.n_confirm >= 30) & (reg.roi_confirm > 0)
    reg["passes_strict"] = reg.house5_passes & reg.h3_both_seasons
    return reg


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pull", action="store_true", help="the one read-only pull (run through run_with_db.py)")
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1, {RESULTS_ENV}, {BETS_ENV})")
    g.add_argument("--verdict", type=Path, help="the verdict with the doc's strict season bar")
    ap.add_argument("--seed", type=Path, default=None, help="--pull: an earlier local pull of nba_pbp to verify and reuse")
    a = ap.parse_args(argv)
    if a.pull:
        pull(work_dir() / "pulled", H.CACHE, a.seed)
    elif a.smoke:
        smoke(H.CACHE)
    elif a.full:
        full(H.CACHE)
    else:
        v = strict_verdict(V.load_cells(a.verdict))
        v.drop(columns=["placebo_rois"], errors="ignore").to_parquet(a.verdict / "verdict_q1props.parquet")
        print(f"{len(v)} registered cells; {int(v.house5_passes.sum())} pass section 9.1's bars as coded; "
              f"{int(v.passes_strict.sum())} pass with both seasons positive (this search's reading)")
        print(v[["market", "side", "cut", "pool_n", "pool_roi", "pool_ci95_lo", "house5_failed", "h3_both_seasons",
                 "passes_strict"]].to_string(index=False))


if __name__ == "__main__":
    main()
