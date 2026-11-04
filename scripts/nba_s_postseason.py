"""NBA postseason search: the two prop models that make money, on games no NBA model was graded on.

docs/nba_search_postseason.md registers every choice below, committed BEFORE this lab and before
any bet in the search was graded. This lab EMITS cells through the shared harness
(scripts/nba_game_harness.run_cells); the pass/fail script judges them
(python -m scripts.nba_game2_verdict --results DIR --house5, section 9.1's bars). No cut, constant
or rule below was chosen from a betting result of a play-in, playoff or Cup final game.

    python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_postseason --pull
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_postseason --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets NBA_RESEARCH_CACHE=<cache> \
        PYTHONPATH=. python -m scripts.nba_s_postseason --full

THE RULES, unchanged:
  nba_prop_market      models/nba_prop_market.py: Pinnacle's proportional no-vig under against
                       every bettable book at Pinnacle's exact line, EV >= 0.00, price >= -200,
                       five markets, one bet per (game, player, market), soft clock no more than
                       10 minutes behind Pinnacle's.
  nba_prop_projection  models/nba_prop_projection.py: six market cells at their shipped floors, the
                       consensus main line only, never a proposition the first rule bets.

HOW A PROP GOES THROUGH THE GAME HARNESS. H.choose keeps one bet per (game_id, market) and H.grade
settles a "totals" row on home_score + away_score. So each proposition is one synthetic game:
game_id = "<real game>|<player id>|<real market>", market = "totals", home_score = the stat,
away_score = 0. An over wins when the stat is above the line, an under when below, a push returns
the stake. A player who did not take the court has no row, so H.grade's inner join drops the bet:
void, out of the record. The whole-day bootstrap reads game_date, which stays real.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from models import nba_prop_market as PM  # noqa: E402
from models import nba_prop_projection as pj  # noqa: E402
from models import nba_props as nb  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV, WORK_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS", "NBA_S_POSTSEASON_WORK"
DEFAULT_WORK = "C:/Users/micha/AppData/Local/Temp/nba_s/postseason"
ESPN_BOX_URL = ("https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
                "espn_nba_player_boxscores/player_box_{season}.parquet")
SEASONS = (2024, 2025, 2026)
CHOOSE = (2024, 2025)                 # P3.choosing's rule: every graded season but 2025-26
POINT = "D"                           # the one snapshot, 54-64 minutes before tip
LEAD_MIN = (45.0, 70.0)               # scripts/nba_prop_projection_lab.LEAD_MIN (regular seasons)
PLACEBO_SEEDS = tuple(range(1, 201))
THIN_KEYS = 5                         # a (date, market) with fewer propositions widens to its round
PROXY_MIN_HAT = 18.0                  # scripts/nba_prop_projection_lab.PROXY_MIN_HAT
ARTIFACT = ROOT / "models" / "saved" / "nba_prop_projection_20261016_091702.pkl"
RULE_BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/"
                 "props_market_bets_sharp_ALL_under_prop_0.00.parquet")
CARD_BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/proj/bets_card_best.parquet")
RULE_ID, PROJECTION_ID = PM.MODEL_ID, pj.MODEL_ID
KEY = ["game_id", "player_id", "market"]
FAM_PM, FAM_PJ = "PM", "PJ"
CTL_CARD, CTL_CAPS = "control_PJ_card", "control_caps_on"
CTL_PM_NOCLOCK, CTL_PJ_NOCLOCK = "control_PM_no_clock", "control_PJ_no_clock"
CTL_FROZEN = "control_PJ_frozen_history"
LABEL_PM = "pm_five_markets"
EXPECTED_CELLS = 7
PM_FLOOR = float(config.MODEL_OWN_EV_FLOOR[RULE_ID])
PM_BANDS = [(-0.01, 0.0), (0.0, 0.01), (0.01, np.inf)]
PJ_BAND_EDGES = (-0.02, 0.0, 0.02, 0.05, 0.10)     # relative to the cell's floor; the top band is open
SIDE_BOTH, SIDE_CARD = "both", "card"
PHASES = ("play_in", "playoffs", "cup_final")
LEADS = {"54": (50.0, 57.0), "59": (57.0, 62.0), "64": (62.0, 70.0)}

# ── the bad-rows rule (docs/nba_search_postseason.md 3.3) ───────────────────
MAX_PRICE = 10000.0
COUNT_MARKETS = tuple(dict.fromkeys(PM.MARKETS + pj.MARKETS))
# No player can be priced outside these: half a point at the bottom, and at the top well past any
# single game on record. Not read from the archive, which itself stores a points line of 113.5.
LINE_RANGE = {"player_points": (0.5, 70.5), "player_rebounds": (0.5, 30.5), "player_assists": (0.5, 25.5),
              "player_threes": (0.5, 14.5), "player_points_rebounds_assists": (0.5, 100.5),
              "player_steals": (0.5, 9.5), "player_blocks": (0.5, 11.5), "player_blocks_steals": (0.5, 15.5),
              "player_rebounds_assists": (0.5, 50.5)}

# ── the play feed ───────────────────────────────────────────────────────────
TURNOVER_TYPES = (62, 63, 64, 65, 66, 67, 71, 72, 73, 74, 75, 76, 77, 78, 80, 81, 82, 84, 86, 87, 90, 206)
OFF_REBOUND, DEF_REBOUND, HEAVE = 156, 155, 282
SETTLED = ("points", "rebounds", "assists", "fg3_made", "blocks", "steals", "turnovers")
BOX_STATS = ("points", "rebounds", "offensive_reb", "defensive_reb", "assists", "steals", "blocks", "turnovers",
             "fg_made", "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att")
ESPN_RENAME = {"field_goals_made": "fg_made", "field_goals_attempted": "fg_att",
               "three_point_field_goals_made": "fg3_made", "three_point_field_goals_attempted": "fg3_att",
               "free_throws_made": "ft_made", "free_throws_attempted": "ft_att",
               "offensive_rebounds": "offensive_reb", "defensive_rebounds": "defensive_reb"}


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def work_dir() -> Path:
    return Path(os.environ.get(WORK_ENV, DEFAULT_WORK))


# ── the one read-only pull ──────────────────────────────────────────────────

def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    raw = getattr(cur, "_cur", cur)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in raw.description])


def pull(out: Path) -> None:
    """Read-only, by indexed key, in chunks with small pauses. Never 10:00-10:45 UTC (the 6am run)."""
    import requests

    from data.db import get_connection
    now = time.gmtime()
    if now.tm_hour == 10 and now.tm_min <= 45:
        raise SystemExit("10:00-10:45 UTC is the daily run: not pulling now")
    out.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    print(_frame(conn, "select state, count(*) n from pg_stat_activity where datname=current_database() group by 1"))
    ids = _frame(conn, "select distinct game_id from nba_postseason_prop_odds")["game_id"].tolist()
    parts = []
    for i in range(0, len(ids), 30):
        parts.append(_frame(conn, "select prop_id, game_id, game_date, player_name, team, market, bookmaker, "
                                  "snapshot_type, snapshot_at, line, over_price, under_price, book_last_update "
                                  "from nba_postseason_prop_odds where game_id = any(%s)", (ids[i:i + 30],)))
        time.sleep(0.2)
    pd.concat(parts, ignore_index=True).to_parquet(out / "nba_postseason_prop_odds.parquet")
    g = _frame(conn, "select espn_game_id, game_id, season, season_type, game_date, home_team, away_team, in_games, "
                     "match_method, sides_swapped, n_plays, n_periods, espn_home_final, espn_away_final, pbp_home_pts, "
                     "pbp_away_pts, points_source, points_mismatch, derivation from nba_pbp_games "
                     "where season between 2019 and 2026")
    g.to_parquet(out / "nba_pbp_games.parquet")
    _frame(conn, "select espn_game_id, espn_id, game_id, season, side, team, name, starter, minutes, did_not_play "
                 "from nba_pbp_box where season between 2024 and 2026").to_parquet(out / "nba_pbp_box.parquet")
    want = g[g.season.isin(SEASONS) & g.season_type.isin([2, 3, 5])].espn_game_id.astype(int).tolist()
    parts = []
    for i in range(0, len(want), 60):
        parts.append(_frame(conn, "select espn_game_id, play_no, sequence_number, game_id, season, season_type, period, "
                                  "type_id, type_text, scoring_play, shooting_play, shot_value, points, "
                                  "espn_score_value, team_side, athlete_id_1, athlete_id_2, athlete_id_3, text "
                                  "from nba_pbp where espn_game_id = any(%s)", (want[i:i + 60],)))
        time.sleep(0.3)
    pd.concat(parts, ignore_index=True).to_parquet(out / "nba_pbp_slim.parquet")
    conn.close()
    dl = out / "espn_box_dl"
    dl.mkdir(parents=True, exist_ok=True)
    for s in SEASONS:
        r = requests.get(ESPN_BOX_URL.format(season=s), timeout=180)
        r.raise_for_status()
        (dl / f"player_box_{s}.parquet").write_bytes(r.content)


# ── settlement: box lines derived from the play feed ────────────────────────

def _count(plays: pd.DataFrame, mask, col: str, name: str) -> pd.Series:
    d = plays.loc[mask & plays[col].notna(), ["espn_game_id", col]]
    return d.groupby(["espn_game_id", col]).size().rename_axis(["espn_game_id", "espn_id"]).rename(name)


def derive_events(plays: pd.DataFrame) -> pd.DataFrame:
    """(espn_game_id, espn_id) -> the counting stats, from ESPN's plays alone.

    A blocked shot's athlete_id_2 is the blocker; a steal's athlete_id_2 is the stealer; a made
    shot's athlete_id_2 is the assister. Team rebounds and team turnovers carry no athlete."""
    free = plays.type_text.str.startswith("Free Throw", na=False).to_numpy()
    made = plays.scoring_play.fillna(False).astype(bool).to_numpy()
    shot = plays.shooting_play.fillna(False).astype(bool).to_numpy()
    fg = shot & ~free & (plays.type_id != HEAVE).to_numpy()
    three = (plays.shot_value == 3).to_numpy()
    text = plays.text.astype(object).fillna("")
    block = text.str.contains(" blocks ", regex=False).to_numpy() & ~made
    steal = text.str.contains(" steals)", regex=False).to_numpy()
    pts = plays.loc[made & plays.athlete_id_1.notna(), ["espn_game_id", "athlete_id_1", "points"]].groupby(
        ["espn_game_id", "athlete_id_1"]).points.sum().rename_axis(["espn_game_id", "espn_id"]).rename("points")
    parts = [pts,
             _count(plays, fg & made, "athlete_id_1", "fg_made"), _count(plays, fg, "athlete_id_1", "fg_att"),
             _count(plays, fg & made & three, "athlete_id_1", "fg3_made"),
             _count(plays, fg & three, "athlete_id_1", "fg3_att"),
             _count(plays, free & made, "athlete_id_1", "ft_made"), _count(plays, free, "athlete_id_1", "ft_att"),
             _count(plays, (plays.type_id == OFF_REBOUND).to_numpy(), "athlete_id_1", "offensive_reb"),
             _count(plays, (plays.type_id == DEF_REBOUND).to_numpy(), "athlete_id_1", "defensive_reb"),
             _count(plays, fg & made, "athlete_id_2", "assists"),
             _count(plays, block, "athlete_id_2", "blocks"),
             _count(plays, steal, "athlete_id_2", "steals"),
             _count(plays, plays.type_id.isin(TURNOVER_TYPES).to_numpy(), "athlete_id_1", "turnovers")]
    out = pd.concat(parts, axis=1).fillna(0.0).reset_index()
    out["rebounds"] = out.offensive_reb + out.defensive_reb
    out["espn_id"] = out.espn_id.astype("int64")
    return out


def derive_lines(plays: pd.DataFrame, box: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, player) who played: ESPN's box (who, team, minutes, starter) with the
    derived counts; a played player with no event is all zeros. A player with events and no box row
    is kept with in_box False, so the cross-check sees it."""
    ev = derive_events(plays)
    b = box[~box.did_not_play.fillna(False).astype(bool)].copy()
    b["espn_id"] = b.espn_id.astype("int64")
    b["espn_game_id"] = b.espn_game_id.astype("int64")
    keep = ["espn_game_id", "espn_id", "game_id", "season", "team", "name", "starter", "minutes"]
    x = b[keep].merge(ev, on=["espn_game_id", "espn_id"], how="outer", indicator=True)
    x["in_box"] = x["_merge"] != "right_only"
    x = x.drop(columns="_merge")
    stats = [c for c in BOX_STATS if c in x]
    x[stats] = x[stats].fillna(0.0)
    meta = box.drop_duplicates("espn_game_id").set_index("espn_game_id")
    x["game_id"] = x.game_id.fillna(x.espn_game_id.map(meta.game_id))
    x["season"] = x.season.fillna(x.espn_game_id.map(meta.season))
    m = id_map[id_map.player_id.notna()].drop_duplicates("espn_id")
    x["player_id"] = x.espn_id.map(dict(zip(m.espn_id.astype("int64"), m.player_id.astype(str))))
    return x


def espn_box_lines(paths, games: pd.DataFrame) -> pd.DataFrame:
    """ESPN's own public box score, every played line (the postseason's second source)."""
    e = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    e = e[e.season_type.isin([2, 3, 5]) & (e.did_not_play != True)].rename(columns=ESPN_RENAME)  # noqa: E712
    gm = dict(zip(games.espn_game_id.astype("int64"), games.game_id))
    e["espn_game_id"] = e.game_id.astype("int64")
    e["game_id"] = e.espn_game_id.map(gm)
    e = e[e.game_id.notna() & e.athlete_id.notna()].copy()
    e["espn_id"] = e.athlete_id.astype("int64")
    return e[["game_id", "espn_id", *BOX_STATS]].astype({c: float for c in BOX_STATS})


def compare_lines(a: pd.DataFrame, b: pd.DataFrame, on: list[str], stats=SETTLED) -> dict:
    """Every stat of every player in either frame; a line only one side holds counts as zeros there.
    -> {"by_stat": {stat: (rows, games)}, "games": set of games with any difference}."""
    x = a[[*on, *stats]].merge(b[[*on, *stats]], on=on, how="outer", suffixes=("_a", "_b"))
    out, bad = {}, set()
    for s in stats:
        d = x[s + "_a"].fillna(0.0).to_numpy(float) != x[s + "_b"].fillna(0.0).to_numpy(float)
        games = set(x.loc[d, on[0]])
        out[s] = (int(d.sum()), len(games))
        bad |= games
    return {"by_stat": out, "games": bad}


# ── the games ───────────────────────────────────────────────────────────────

ROUND_RX = (("first round", "first_round"), ("semifinal", "conf_semis"), ("conf. final", "conf_finals"),
            ("nba finals", "finals"))


def round_of(label) -> str | None:
    s = str(label).lower()
    for needle, name in ROUND_RX:
        if needle in s:
            return name
    return None


def postseason_games(schedule: pd.DataFrame, props: pd.DataFrame) -> pd.DataFrame:
    """The games the purchase holds: phase, round, tip, and which season's models price them."""
    want = set(props.game_id)
    g = schedule[schedule.game_id.isin(want) & schedule.game_type.isin(["playoff", "playin", "cup_final"])].copy()
    if g.game_id.duplicated().any() or set(g.game_id) != want:
        raise RuntimeError(f"schedule holds {g.game_id.nunique()} of the purchase's {len(want)} games")
    g["phase"] = g.game_type.map({"playoff": "playoffs", "playin": "play_in", "cup_final": "cup_final"})
    g["round"] = [round_of(x) if p == "playoffs" else p for x, p in zip(g.game_label, g.phase)]
    if g["round"].isna().any():
        raise RuntimeError(f"unknown playoff round: {sorted(set(g.loc[g['round'].isna(), 'game_label']))}")
    return g[["game_id", "season", "game_date", "commence_time", "home_team", "away_team", "phase", "round"]
             ].reset_index(drop=True)


def refuse_bad_rows(q: pd.DataFrame, bounds: dict = LINE_RANGE) -> tuple[pd.DataFrame, dict]:
    """The rule for impossible numbers, written before any offer was read: a line outside LINE_RANGE,
    an American price of size under 100 or over MAX_PRICE, or a two-way quote whose implied sum is
    outside 1.00-1.15. Refused and counted, never repaired."""
    lo = q.market.map(lambda m: bounds[m][0]).to_numpy(float)
    hi = q.market.map(lambda m: bounds[m][1]).to_numpy(float)
    line = q.line.to_numpy(float)
    bad_line = (line < lo) | (line > hi)
    over, under = q.over_price.to_numpy(float), q.under_price.to_numpy(float)
    bad_px = np.zeros(len(q), bool)
    for px in (over, under):
        with np.errstate(invalid="ignore"):
            bad_px |= np.isfinite(px) & ((np.abs(px) < 100) | (np.abs(px) > MAX_PRICE))
    two = np.isfinite(over) & np.isfinite(under)
    s = np.where(two, nb.implied(np.nan_to_num(over, nan=100.0)) + nb.implied(np.nan_to_num(under, nan=100.0)), np.nan)
    with np.errstate(invalid="ignore"):
        bad_sum = two & ((s < PM.COHERENT[0]) | (s > PM.COHERENT[1]))
    bad = bad_line | bad_px | bad_sum
    return q[~bad].copy(), {"line_outside_range": int(bad_line.sum()), "impossible_price": int(bad_px.sum()),
                            "incoherent_two_way": int(bad_sum.sum()), "one_sided_not_decided_on": int((~two).sum()),
                            "refused": int(bad.sum()), "kept": int((~bad).sum())}


def archive_outside(reg_props: pd.DataFrame) -> dict:
    """The regular-season archive read through the same range, reported only: neither rule's
    regular-season record is touched here."""
    r = reg_props[reg_props.market.isin(COUNT_MARKETS)]
    lo, hi = r.market.map(lambda m: LINE_RANGE[m][0]), r.market.map(lambda m: LINE_RANGE[m][1])
    bad = r[(r.line < lo) | (r.line > hi)]
    return {"rows": int(len(bad)), "by_market": bad.market.value_counts().to_dict(),
            "highest": {m: float(g.max()) for m, g in bad.groupby("market").line}}


def extremes(q: pd.DataFrame) -> pd.DataFrame:
    """The lowest and highest line and price the search reads, per market."""
    return q.groupby("market").agg(rows=("line", "size"), line_min=("line", "min"), line_max=("line", "max"),
                                   over_min=("over_price", "min"), over_max=("over_price", "max"),
                                   under_min=("under_price", "min"), under_max=("under_price", "max"))


# ── nba_prop_market: quotes through the research code, offers per the rule ──

def market_quotes(props: pd.DataFrame, games: pd.DataFrame, log: pd.DataFrame, adv: pd.DataFrame, ina: pd.DataFrame,
                  folder: Path) -> pd.DataFrame:
    """scripts/nba_prop_market_lab.build_quotes, unchanged, pointed at these tables: name matching,
    the namesake refusal, the 'did he take the court' rule (minutes or seconds), the settle value."""
    from scripts import nba_prop_market_lab as ML
    folder.mkdir(parents=True, exist_ok=True)
    props.to_parquet(folder / "nba_props.parquet")
    games.to_parquet(folder / "nba_games.parquet")
    log.to_parquet(folder / "nba_player_game_log.parquet")
    adv.to_parquet(folder / "nba_player_game_adv.parquet")
    ina.to_parquet(folder / "nba_game_inactives.parquet")
    ML.CACHE, ML.WORK = folder, folder
    return ML.build_quotes()


def fair_under_of(over_price, under_price) -> np.ndarray:
    """Pinnacle's proportional no-vig under, bit for bit models.nba_prop_market.fair_under. The floor
    is EV >= 0.00, so an offer worth exactly nothing is a bet, and which side of zero it lands on is
    decided by this arithmetic: 1 / decimal lands some of them one rounding step below it."""
    o, u = nb.implied(over_price), nb.implied(under_price)
    return u / (o + u)


def market_rows(q: pd.DataFrame, clock: bool) -> pd.DataFrame:
    """Every bettable book's under at Pinnacle's exact line, both quotes coherent, one row per offer.
    `clock`: refuse a book more than STALE_SOFT_MAX_MIN behind Pinnacle (a quote with no clock counts)."""
    u = q[q.usable & q.x.notna() & q.market.isin(PM.MARKETS)]
    pin = u[(u.bookmaker == PM.SHARP_BOOK) & u.coherent][[*KEY, "line", "over_price", "under_price", "game_date", "season"]
                                                         + (["book_last_update"] if "book_last_update" in u else [])].copy()
    pin = pin.rename(columns={"line": "pin_line", "book_last_update": "pin_clock"})
    pin["fair_under"] = fair_under_of(pin.over_price, pin.under_price)
    soft = u[u.bookmaker.isin(H.BETTABLE) & u.coherent & u.has_u]
    m = soft.merge(pin[[*KEY, "pin_line", "fair_under"] + (["pin_clock"] if "pin_clock" in pin else [])], on=KEY)
    m = m[m.line == m.pin_line].copy()
    if clock and "pin_clock" in m:
        soft_c, pin_c = pd.to_datetime(m.book_last_update, utc=True, format="mixed", errors="coerce"), \
            pd.to_datetime(m.pin_clock, utc=True, format="mixed", errors="coerce")
        stale = (pin_c - soft_c).dt.total_seconds() / 60 > PM.STALE_SOFT_MAX_MIN
        m = m[~stale.fillna(False).to_numpy()]
    m["price"] = m.under_price.to_numpy(float)
    m["side"] = PM.SIDE
    m["book"] = m.bookmaker
    m["dec"] = nb.decimal(m.price.to_numpy())
    return m


# ── synthetic games and offers: how a proposition passes through the harness ─

def pid_of(game_id, player_id, market) -> pd.Series:
    """The synthetic game's id, by position. `market` may be one name for every row."""
    g, p = list(game_id), list(player_id)
    m = [market] * len(g) if isinstance(market, str) else list(market)
    if not len(g) == len(p) == len(m):
        raise ValueError(f"pid_of: {len(g)} games, {len(p)} players, {len(m)} markets")
    return pd.Series([f"{a}|{b}|{c}" for a, b, c in zip(g, p, m)], dtype=object)


def stat_of(rows: pd.DataFrame, market: str) -> pd.Series:
    return rows[list(nb.BY_MARKET[market].parts)].sum(axis=1, min_count=len(nb.BY_MARKET[market].parts))


def settled_games(lines: pd.DataFrame, action: pd.DataFrame, games: pd.DataFrame, keep_games, markets=COUNT_MARKETS,
                  blind: bool = False) -> pd.DataFrame:
    """One synthetic game per (real game, player, market) of a player who took the court, in a game
    the cross-check kept. `blind`: every stat 0, so a timing run can grade without reading a result."""
    x = lines[lines.game_id.isin(set(keep_games))].merge(action[["game_id", "player_id", "action"]],
                                                         on=["game_id", "player_id"], how="left")
    x = x[x.action.fillna(False).astype(bool)]
    meta = games.set_index("game_id")
    parts = []
    for m in markets:
        v = stat_of(x, m).to_numpy(float)
        parts.append(pd.DataFrame({"game_id": pid_of(x.game_id.values, x.player_id.values, m).values,
                                   "real_game": x.game_id.values, "season": x.game_id.map(meta.season).values,
                                   "game_date": x.game_id.map(meta.game_date).values, "real_market": m,
                                   "home_score": 0.0 if blind else v, "away_score": 0.0}))
    return pd.concat(parts, ignore_index=True)


def offers_frame(rows: pd.DataFrame, meta: pd.DataFrame, model: str) -> pd.DataFrame:
    """rows: game_id, player_id, market, side, book, line, price -> the harness's offer columns."""
    g = meta.set_index("game_id")
    out = pd.DataFrame({
        "game_id": pid_of(rows.game_id.values, rows.player_id.values, rows.market.values).values,
        "real_game": rows.game_id.values, "player_id": rows.player_id.astype(str).values,
        "real_market": rows.market.values, "market": "totals", "side": rows.side.values,
        "book": rows.book.values, "line": rows.line.to_numpy(float), "price": rows.price.to_numpy(float),
        "season": rows.game_id.map(g.season).to_numpy(), "game_date": rows.game_id.map(g.game_date).values,
        "T": rows.snapshot_at.values, "lead_min": rows.lead_min.to_numpy(float),
        "phase": rows.game_id.map(g.phase).values, "round": rows.game_id.map(g["round"]).values,
        "mu": np.nan, "p_home": np.nan, "model": model, "p_push": 0.0})
    return out.reset_index(drop=True)


def with_lead(rows: pd.DataFrame, tips: dict) -> pd.DataFrame:
    tip = pd.to_datetime(rows.game_id.map(tips), utc=True, format="mixed")
    snap = pd.to_datetime(rows.snapshot_at, utc=True, format="mixed")
    return rows.assign(lead_min=((tip - snap).dt.total_seconds() / 60).to_numpy())


class MarketPricer:
    """nba_prop_market's EV on a frame of offers, from one fair under per proposition."""

    def __init__(self, offers: pd.DataFrame, fair: np.ndarray):
        self.offers = offers.reset_index(drop=True)
        self.keys = self.offers.drop_duplicates("game_id")[["game_id", "game_date", "season", "real_market", "round"]
                                                           ].reset_index(drop=True)
        pos = pd.Series(np.arange(len(self.keys)), index=self.keys.game_id.values)
        self.kid = pos.reindex(self.offers.game_id.values).to_numpy()
        first = self.offers.drop_duplicates("game_id").index.to_numpy()
        self.fair = np.asarray(fair, float)[first]
        self.dec = nb.decimal(self.offers.price.to_numpy())
        self.groups = placebo_groups(self.keys)

    def priced(self, fair_keys: np.ndarray | None = None) -> pd.DataFrame:
        f = self.fair if fair_keys is None else fair_keys
        p = f[self.kid]
        return self.offers.assign(p_win=p, ev=p * self.dec - 1.0)

    def placebo(self, seed: int) -> pd.DataFrame:
        return self.priced(shuffled(self.fair, self.groups, seed))


class ProjectionPricer:
    """nba_prop_projection's calibrated EV on a frame of offers, from one mean per proposition.
    Every offer carries its proposition's width and map, so the placebo reprices exactly as the rule."""

    def __init__(self, offers: pd.DataFrame):
        self.offers = offers.reset_index(drop=True)
        k = self.offers.drop_duplicates("game_id").reset_index(drop=True)
        self.keys = k
        pos = pd.Series(np.arange(len(k)), index=k.game_id.values)
        self.kid = pos.reindex(self.offers.game_id.values).to_numpy()
        self.mu, self.line = k.model_mu.to_numpy(float), k.line.to_numpy(float)
        self.alpha, self.a, self.b = k.alpha.to_numpy(float), k.cal_a.to_numpy(float), k.cal_b.to_numpy(float)
        self.val = self.mu / self.line
        self.dec = nb.decimal(self.offers.price.to_numpy())
        self.over = (self.offers.side == "over").to_numpy()
        self.ok_px = (self.offers.price >= H.PRICE_FLOOR).to_numpy()
        self.floor = self.offers.floor.to_numpy(float)
        self.groups = placebo_groups(k)

    def p_over(self, mu: np.ndarray) -> np.ndarray:
        out = np.empty(len(mu))
        for al in np.unique(self.alpha):
            s = self.alpha == al
            out[s] = nb.p_over(mu[s], self.line[s], float(al))
        return 1.0 / (1.0 + np.exp(-(self.a + self.b * nb._logit(out))))

    def priced(self, mu: np.ndarray | None = None) -> pd.DataFrame:
        po = self.p_over(self.mu if mu is None else mu)[self.kid]
        p = np.where(self.over, po, 1.0 - po)
        ev = p * self.dec - 1.0
        # the proposition's side: the higher EV of its two best offers, a tie to the over (the model's order)
        n = len(self.keys)
        best_o, best_u = np.full(n, -np.inf), np.full(n, -np.inf)
        s = self.over & self.ok_px
        np.maximum.at(best_o, self.kid[s], ev[s])
        s = ~self.over & self.ok_px
        np.maximum.at(best_u, self.kid[s], ev[s])
        pick = np.where(best_o >= best_u, "over", "under")[self.kid]
        return self.offers.assign(p_win=p, ev=ev, side_pick=pick, margin=ev - self.floor)

    def placebo(self, seed: int) -> pd.DataFrame:
        return self.priced(shuffled(self.val, self.groups, seed) * self.line)


def placebo_groups(keys: pd.DataFrame) -> np.ndarray:
    """Shuffle group per proposition: (date, market); a (date, market) with fewer than THIN_KEYS
    propositions joins the other thin propositions of its (season, round, market)."""
    d = keys.game_date.astype(str) + "|" + keys.real_market.astype(str)
    n = d.map(d.value_counts()).to_numpy()
    wide = keys.season.astype(str) + "|" + keys["round"].astype(str) + "|" + keys.real_market.astype(str)
    return pd.factorize(np.where(n < THIN_KEYS, "R|" + wide, "D|" + d))[0]


def shuffled(values: np.ndarray, groups: np.ndarray, seed: int) -> np.ndarray:
    """Each proposition takes another's value from its own group, by position."""
    rng = np.random.default_rng(int(seed))
    base = np.argsort(groups, kind="stable")
    order = np.lexsort((rng.random(len(groups)), groups))
    out = np.empty(len(values))
    out[base] = np.asarray(values, float)[order]
    return out


def differing_share(real: pd.DataFrame, placebo: pd.DataFrame) -> float:
    """The share of a placebo run's bets that are not real bets (another proposition or side)."""
    if not len(placebo):
        return np.nan
    a = set(zip(real.game_id, real.side))
    return float(np.mean([k not in a for k in zip(placebo.game_id, placebo.side)]))


# ── the caps (scripts/nba_props_card: one a game across both models, four a night) ──

def cap_rows(bets: pd.DataFrame) -> list[dict]:
    return [{"model_id": m, "_ev": float(e), "player_id": str(pl), "prop_market": mk, "pick_side": s,
             "scored_line": float(ln), "game_id": gm, "game_date": str(d)[:10], "pid": pid}
            for m, e, pl, mk, s, ln, gm, d, pid in zip(
                bets.model, bets.ev, bets.player_id, bets.real_market, bets.side, bets.line, bets.real_game,
                bets.game_date, bets.game_id)]


def apply_caps(bets: pd.DataFrame) -> dict:
    """{proposition: side} the shipped door writes, strongest first by each model's own EV percentile.
    Games are taken one date at a time; no game or date has been written before."""
    from scripts.nba_props_card import choose
    chosen, _ = choose(cap_rows(bets), set(), {})
    return {r["pid"]: r["pick_side"] for r in chosen}


def rule_keys_of(bets: pd.DataFrame) -> set:
    """(game, player, market) of every nba_prop_market bet: the projection cells never bet one (4.2)."""
    return {tuple(k.split("|")) for k in bets.game_id}


def qualifying(cand: pd.DataFrame, cut: float, side: str, strength: str = "ev") -> pd.DataFrame:
    if strength == "ev":
        return H.choose(cand, cut, sides=[side])
    return H.choose(cand[cand[strength] >= cut], -np.inf, sides=[side])


def capped_frame(pm_cand: pd.DataFrame, pj_cand: pd.DataFrame) -> pd.DataFrame:
    """Both models' offers with `capped` 1 on the propositions the door writes, `side_pick` its side."""
    bets = pd.concat([qualifying(pm_cand, PM_FLOOR, "under"),
                      qualifying(pj_cand, 0.0, SIDE_CARD, "margin")], ignore_index=True)
    picks = apply_caps(bets) if len(bets) else {}
    keep = ["game_id", "real_game", "player_id", "real_market", "market", "side", "book", "line", "price", "season",
            "game_date", "T", "lead_min", "phase", "round", "mu", "p_home", "model", "p_push", "p_win", "ev"]
    c = pd.concat([pm_cand[keep], pj_cand[keep]], ignore_index=True)
    c["capped"] = c.game_id.isin(set(picks)).astype(float)
    c["side_pick"] = c.game_id.map(picks).astype(object)
    return c


# ── nba_prop_projection: the frames, the folds, the widths, the maps ────────

OUT_STATUS = ("Out", "Doubtful")


def fold_path(work: Path, through: int) -> Path:
    return work / f"fold_{through}.pkl"


def shipped_frame(cache: Path, work: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """The worker re-fit's frame, as scripts/nba_prop_projection_train builds it: regular-season box
    lines only. Everything fitted here is fitted on this frame."""
    from scripts import nba_prop_projection_train as TR
    raw = nb.load_cache(cache, with_props=True, with_lines=False)
    f = work / "frame_shipped.parquet"
    props = raw["nba_props"]
    decisions = nb.decisions_for(raw, props[props.game_date < TR.LAST_RESEARCH_DATE])
    if f.exists():
        return raw, decisions, pd.read_parquet(f)
    report = pj.compact_report(pj.collapse_official(raw["nba_injury_report"]), decisions)
    data = pj.worker_data(raw["nba_games"], raw["nba_schedule"], raw["nba_player_game_log"], report, decisions)
    fr = nb.build_frame(data, decisions, with_lines=False)
    fr.to_parquet(f)
    return raw, decisions, fr


def fit_folds(fr: pd.DataFrame, work: Path, throughs=(2022, 2023, 2024, 2025)) -> dict:
    """The minutes and rate models fitted on regular seasons 2018-19..through (TR.fit_fold), cached."""
    from scripts import nba_prop_projection_train as TR
    out = {}
    for t in throughs:
        p = fold_path(work, t)
        if p.exists():
            with open(p, "rb") as fh:
                out[t] = pickle.load(fh)
            continue
        t0 = time.time()
        out[t] = TR.fit_fold(fr, t)
        with open(p, "wb") as fh:
            pickle.dump(out[t], fh)
        say(f"fold through {t}: {time.time() - t0:.0f}s")
    return out


def fit_widths(fr: pd.DataFrame, folds: dict, work: Path) -> dict:
    """alpha_by[S]: each market's width fitted on regular season S as predicted by the fold through S-1."""
    from scripts import nba_prop_projection_train as TR
    f = work / "alpha_by.json"
    if f.exists():
        return {int(k): v for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
    out = {}
    for s in (2023, 2024, 2025, 2026):
        out[s] = {m: float(a) for m, a in TR.widths(fr, folds[s - 1], s)[0].items()}
    f.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def card_quotes(px: pd.DataFrame, fr: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """scripts/nba_prop_model_lab.stage_prices over the card's six markets: quotes before tip,
    two-way coherent or one-sided, the player matched by name among both teams' players this season
    and last, his row of the frame (played, status, usable), and the value the market settles on."""
    gm = games.drop_duplicates("game_id").set_index("game_id")
    px = px[px.market.isin(pj.MARKETS)].copy()
    px["season"] = px.game_id.map(gm.season)
    px = px[px.season.isin(SEASONS)]
    tip, snap = nb._utc(px.game_id.map(gm.commence_time)), nb._utc(px.snapshot_at)
    px = px[(snap < tip).to_numpy() & px.game_id.isin(set(fr.game_id)).to_numpy()].copy()
    two = px.over_price.notna() & px.under_price.notna()
    s = nb.implied(px.over_price) + nb.implied(px.under_price)
    bad = two.to_numpy() & ~((s >= pj.COHERENT[0]) & (s <= pj.COHERENT[1]))
    px = px[~bad].copy()
    px["two_sided"] = px.over_price.notna() & px.under_price.notna()
    ros = fr[["season", "team", "player_id", "player_name"]].drop_duplicates(["season", "team", "player_id"])
    g = px[["game_id", "season"]].drop_duplicates().copy()
    g["home"], g["away"] = g.game_id.map(gm.home_team).to_numpy(), g.game_id.map(gm.away_team).to_numpy()
    sides = pd.concat([g.rename(columns={"home": "team"})[["game_id", "season", "team"]],
                       g.rename(columns={"away": "team"})[["game_id", "season", "team"]]])
    sides = pd.concat([sides, sides.assign(season=sides.season - 1)])
    roster = sides.merge(ros, on=["season", "team"])[["game_id", "player_id", "player_name"]]
    m = nb.match_names(px[["game_id", "player_name"]].drop_duplicates(), roster)
    px = px.merge(m, on=["game_id", "player_name"])
    px = px[px.player_id.notna()].copy()
    keep = ["game_id", "player_id", "team", "opponent", "played", "status", "covered", "gp", "min_l", *nb.BASE_STATS]
    row = fr[keep].drop_duplicates(["game_id", "player_id"])
    px = px.merge(row, on=["game_id", "player_id"], how="left")
    px["played"] = px.played.astype(object).fillna(False).astype(bool)
    px["usable"] = (px.gp >= nb.MIN_GAMES) & px.min_l.notna()
    px["actual"] = np.nan
    for mk in pj.MARKETS:
        sel = (px.market == mk).to_numpy()
        px.loc[sel, "actual"] = nb.settle_value(nb.BY_MARKET[mk], px[sel]).to_numpy()
    px["actual"] = px.actual.where(px.played)
    px["player_id"] = px.player_id.astype(str)
    return px.drop(columns=[*nb.BASE_STATS, "min_l"])


def means_for(rows: pd.DataFrame, art: dict) -> pd.DataFrame:
    """Each row's projected mean of every card market, under one fitted fold."""
    m = pj.predict_means(art, rows)
    out = pd.DataFrame({"game_id": rows.game_id.to_numpy(), "player_id": rows.player_id.astype(str).to_numpy()})
    for c in m.columns:
        out[c] = m[c].to_numpy()
    return out


def regular_pairs(fr: pd.DataFrame, raw: dict, folds: dict, alpha_by: dict, work: Path) -> pd.DataFrame:
    """The (claimed, outcome) pairs each map is fitted on: season s predicted by the fold through
    s-1 with the width fitted on s-1, at the main line, every proposition at most 70 and at least 45
    minutes before tip with a price at -200 or better. (The projection lab's pairs_real.)"""
    from scripts import nba_prop_model_lab as lab
    from scripts import nba_prop_projection_train as TR
    f = work / "pairs_regular.parquet"
    if f.exists():
        return pd.read_parquet(f)
    props = raw["nba_props"]
    q = card_quotes(props[props.game_date < TR.LAST_RESEARCH_DATE], fr, raw["nba_games"])
    q = q[q.usable & ~q.status.isin(OUT_STATUS)]
    lead = (nb._utc(q.game_id.map(raw["nba_games"].drop_duplicates("game_id").set_index("game_id").commence_time))
            - nb._utc(q.snapshot_at)).dt.total_seconds() / 60
    q = q[lead.between(*LEAD_MIN).to_numpy()]
    main = lab.main_lines(q).rename(columns={"line": "main_line"})
    main["player_id"] = main.player_id.astype(str)
    P = lab.propositions(q).merge(main, on=KEY)
    P = P[P.line == P.main_line]
    parts = []
    for s in SEASONS:
        te = fr[nb.usable(fr) & (fr.season == s)]
        mu = means_for(te, folds[s - 1])
        x = P[P.season == s].merge(mu, on=["game_id", "player_id"], how="inner")
        for mk in pj.MARKETS:
            sel = x[x.market == mk]
            u = sel.drop_duplicates(["game_id", "player_id", "market", "line"])
            u = u[u.played & u.actual.notna()]
            p = nb.p_over(u[f"mu_{mk}"].to_numpy(), u.line.to_numpy(), alpha_by[s - 1][mk])
            parts.append(pd.DataFrame({"season": s, "market": mk, "p": p, "y": (u.actual > u.line).astype(float).to_numpy(),
                                       "game_date": pd.to_datetime(u.game_date).to_numpy(), "game_id": u.game_id.to_numpy(),
                                       "player_id": u.player_id.to_numpy(), "line": u.line.to_numpy()}))
    out = pd.concat(parts, ignore_index=True)
    out.to_parquet(f)
    return out


def season_maps(pairs: pd.DataFrame) -> dict:
    """maps[S]: postseason S's Platt maps, fitted on the pairs of regular seasons up to and including S."""
    return {s: nb.fit_calibration(pairs, s + 1) for s in SEASONS}


def proxy_map(fr: pd.DataFrame, folds: dict, alpha_by: dict) -> dict:
    """The stand-in the graded 2023-24 used where that season had too few pairs yet: 2022-23 as
    predicted by the fit through 2021-22, at a proxy line (the weighted average rounded to the half
    point) over the players a book would price. (scripts/nba_prop_projection_lab.pairs_proxy_2023.)"""
    te = fr[nb.usable(fr) & (fr.season == 2023) & fr.played & ~fr.status.isin(OUT_STATUS)]
    m = pj.predict_means(folds[2022], te)
    keep = (m.min_hat >= PROXY_MIN_HAT).to_numpy()
    te, m = te[keep], m[keep]
    parts = []
    for mk in pj.MARKETS:
        spec = nb.BY_MARKET[mk]
        line = np.floor(sum(te[f"ew_{x}"].to_numpy(float) for x in spec.parts)) + 0.5
        y = nb.settle_value(spec, te).to_numpy(float)
        ok = np.isfinite(line) & np.isfinite(y)
        p = nb.p_over(m[f"mu_{mk}"].to_numpy()[ok], line[ok], alpha_by[2023][mk])
        parts.append(pd.DataFrame({"season": 2023, "market": mk, "p": p, "y": (y[ok] > line[ok]).astype(float)}))
    return nb.fit_calibration(pd.concat(parts, ignore_index=True), 2024)


def cup_map(pairs: pd.DataFrame, season: int, game_date, proxy: dict | None = None) -> dict:
    """A Cup final is played in December, mid regular season: the map a regular-season game of that
    date was graded on. 2023-24 has no earlier priced season: games strictly before that week, and
    the 2022-23 proxy for a market with fewer than 300 such pairs, as that season was graded."""
    if season > SEASONS[0]:
        return nb.fit_calibration(pairs, season)
    d = pd.Timestamp(game_date)
    return {**(proxy or {}), **nb.fit_calibration_before(pairs[pairs.season == season],
                                                         d - pd.Timedelta(days=int(d.weekday())))}


def model_inputs(pg: pd.DataFrame, folds: dict, alpha_by: dict, maps: dict, pairs: pd.DataFrame, artifact: dict,
                 proxy: dict | None = None) -> dict:
    """{game_id: (model, widths, maps)}. A play-in or playoff game follows regular season S, so it reads
    the fit through S (the shipped artifact for 2025-26). A Cup final reads the fit through S-1."""
    out, cup = {}, {}
    for r in pg.itertuples():
        s = int(r.season)
        if r.phase == "cup_final":
            cup[r.game_id] = (folds[s - 1], alpha_by[s - 1], cup_map(pairs, s, r.game_date, proxy))
        else:
            out[r.game_id] = (artifact if s == 2026 else folds[s], alpha_by[s], maps[s])
    return {**out, **cup}


def postseason_data(raw: dict, lines: pd.DataFrame, pg: pd.DataFrame, ps_props: pd.DataFrame, history: bool
                    ) -> tuple[dict, pd.DataFrame]:
    """The worker's inputs with the 272 games added. `history` True: their box lines are history too,
    so every postseason row reads the games its player has played by then. False: the frozen control,
    every row reads his regular season. Games are retyped 'regular' only here, never in the shipped
    frame, so that the frame code keeps them. The official report holds no play-in or playoff game
    (2026-05 holds 8 rows on 4 games of one pull, dropped so those games read as the others do)."""
    g = pg.assign(sport="NBA")[["game_id", "season", "game_date", "home_team", "away_team", "commence_time"]]
    games = pd.concat([raw["nba_games"], g], ignore_index=True)
    sched = raw["nba_schedule"].copy()
    sched.loc[sched.game_id.isin(set(pg.game_id)), "game_type"] = "regular"
    gm = pg.set_index("game_id")
    x = lines[lines.game_id.isin(set(pg.game_id)) & lines.player_id.notna() & lines.in_box].copy()
    add = pd.DataFrame({"player_id": x.player_id.astype(str).to_numpy(), "player_name": x.name.to_numpy(),
                        "team": x.team.to_numpy(), "game_id": x.game_id.to_numpy(),
                        "game_date": x.game_id.map(gm.game_date).to_numpy(), "season": x.game_id.map(gm.season).to_numpy(),
                        "minutes": x.minutes.to_numpy(float), "is_starter": x.starter.fillna(False).astype(float).to_numpy(),
                        **{c: x[c].to_numpy(float) for c in BOX_STATS}})
    base = raw["nba_player_game_log"].copy()
    base["player_id"] = base.player_id.astype(str)
    log = pd.concat([base, add], ignore_index=True) if history else base
    drop = set(pg.game_id[pg.phase != "cup_final"])
    report = pj.collapse_official(raw["nba_injury_report"][~raw["nba_injury_report"].game_id.isin(drop)])
    props = pd.concat([raw["nba_props"][["game_id", "snapshot_at", "game_date"]],
                       ps_props[["game_id", "snapshot_at", "game_date"]]], ignore_index=True)
    from scripts import nba_prop_projection_train as TR
    decisions = nb.decisions_for({"nba_games": games}, props[props.game_date < TR.LAST_RESEARCH_DATE])
    compact = pj.compact_report(report, decisions)
    return pj.worker_data(games, sched, log, compact, decisions), decisions


def postseason_frame(raw: dict, lines: pd.DataFrame, pg: pd.DataFrame, ps_props: pd.DataFrame, work: Path,
                     history: bool = True) -> pd.DataFrame:
    """The postseason rows of the frame, every input as of each game's decision (cached)."""
    f = work / ("frame_postseason.parquet" if history else "frame_frozen.parquet")
    if f.exists():
        return pd.read_parquet(f)
    data, decisions = postseason_data(raw, lines, pg, ps_props, history)
    if history:
        fr = nb.build_frame(data, decisions, with_lines=False)
    else:
        # the frozen control: the players the as-of frame holds, scored as the live card scores tonight
        have = postseason_frame(raw, lines, pg, ps_props, work, True)
        up = have[["game_id", "player_id", "player_name", "team", "opponent", "is_home", "season", "game_date"]]
        fr = nb.build_frame(data, decisions, upcoming=up, with_lines=False)
    out = fr[fr.game_id.isin(set(pg.game_id))].copy()
    out.to_parquet(f)
    return out


def card_rows(q: pd.DataFrame, clock: bool) -> pd.DataFrame:
    """Every bettable book's quote on the card's main line, per the rule's order: usable, not listed
    Out or Doubtful; the main line read from every coherent two-sided quote; then the clock."""
    from scripts import nba_prop_model_lab as lab
    q = q[q.usable & ~q.status.isin(OUT_STATUS)].copy()
    main = lab.main_lines(q).rename(columns={"line": "main_line"})
    main["player_id"] = main.player_id.astype(str)
    at = q[q.bookmaker.isin(H.BETTABLE) & q.two_sided].merge(main, on=KEY)
    if clock and "book_last_update" in q:
        clk = pd.to_datetime(q.book_last_update, utc=True, format="mixed", errors="coerce")
        freshest = clk.groupby([q.game_id, q.market]).max().rename("_fresh").reset_index()
        at = at.merge(freshest, on=["game_id", "market"], how="left")
        behind = (at._fresh - pd.to_datetime(at.book_last_update, utc=True, format="mixed", errors="coerce"))
        at = at[~(behind.dt.total_seconds() / 60 > pj.STALE_MAX_MIN).to_numpy()]
    return at[at.line == at.main_line].copy()


def card_offers(at: pd.DataFrame, means: pd.DataFrame, inputs: dict, rule_keys: set, meta: pd.DataFrame) -> pd.DataFrame:
    """The offers of the card's sides at the main line, each with its proposition's mean, width and map."""
    x = at[[k not in rule_keys for k in zip(at.game_id, at.player_id, at.market)]]
    rows = []
    for side in ("over", "under"):
        s = x[x.market.map(lambda m: side in pj.CARD[m][0]).to_numpy()].copy()
        col = f"{side}_price"
        s = s[s[col].notna()]
        s["side"], s["price"], s["book"] = side, s[col].to_numpy(float), s.bookmaker
        rows.append(s)
    r = pd.concat(rows, ignore_index=True)
    m = means.melt(id_vars=["game_id", "player_id"], value_vars=[f"mu_{k}" for k in pj.MARKETS],
                   var_name="market", value_name="model_mu")
    m["market"] = m.market.str.slice(3)
    r = r.merge(m, on=KEY, how="inner")
    off = offers_frame(r, meta, PROJECTION_ID)
    off["model_mu"] = r.model_mu.to_numpy(float)
    off["floor"] = r.market.map(lambda k: pj.CARD[k][1]).to_numpy(float)
    off["alpha"] = [inputs[g][1][k] for g, k in zip(r.game_id, r.market)]
    off["cal_a"] = [inputs[g][2][k][0] for g, k in zip(r.game_id, r.market)]
    off["cal_b"] = [inputs[g][2][k][1] for g, k in zip(r.game_id, r.market)]
    return off


def postseason_means(frame: pd.DataFrame, pg: pd.DataFrame, inputs: dict) -> pd.DataFrame:
    """Every usable row's mean, under the fold that game reads."""
    parts = []
    fr = frame[nb.usable(frame)]
    fold_of = {g: id(v[0]) for g, v in inputs.items()}
    tag = fr.game_id.map(fold_of)
    arts = {id(v[0]): v[0] for v in inputs.values()}
    for t, sub in fr.groupby(tag, sort=False):
        parts.append(means_for(sub, arts[t]))
    return pd.concat(parts, ignore_index=True).drop_duplicates(["game_id", "player_id"])


# ── the cells ───────────────────────────────────────────────────────────────

def band_rows(cand: pd.DataFrame, side: str, strength: str, bounds, games: pd.DataFrame) -> dict:
    return G5.band_columns(cand, side, strength, bounds, games, SEASONS)


def side_views(g: pd.DataFrame) -> dict:
    """What every row carries beside the bars: the three phases, the three leads."""
    out = {}
    for ph in PHASES:
        x = g[g.phase == ph] if len(g) else g
        out.update({f"phase_{ph}_n": int(len(x)), f"phase_{ph}_units": float(x.units.sum()) if len(x) else 0.0,
                    f"phase_{ph}_roi": H.roi(x) if len(x) else np.nan})
    for name, (lo, hi) in LEADS.items():
        x = g[g.lead_min.between(lo, hi, inclusive="left")] if len(g) else g
        out.update({f"lead_{name}_n": int(len(x)), f"lead_{name}_roi": H.roi(x) if len(x) else np.nan})
    return out


def dk_view(cand: pd.DataFrame, games: pd.DataFrame, cut: float, side: str, strength: str) -> dict:
    """DraftKings alone, its own best side where a cell bets both."""
    c = cand[cand.book == H.DK]
    if side in (SIDE_BOTH, SIDE_CARD) and "side_pick" in c and side != SIDE_CARD:
        best = c[c.price >= H.PRICE_FLOOR].sort_values("ev", ascending=False).drop_duplicates("game_id")
        c = c.assign(side_pick=c.game_id.map(dict(zip(best.game_id, best.side))).astype(object))
    b = H.choose(c, cut, books=(H.DK,), sides=[side]) if strength == "ev" else \
        H.choose(c[c[strength] >= cut], -np.inf, books=(H.DK,), sides=[side])
    g = H.grade(b, games) if len(b) else b
    return {"dk_pool_n": int(len(g)), "dk_pool_units": float(g.units.sum()) if len(g) else 0.0,
            "dk_pool_roi": H.roi(g) if len(g) else np.nan}


def emit(dd: H.Data, times: pd.DataFrame, family: str, label: str, side: str, cut: float, cand: pd.DataFrame,
         placebo, strength: str, bounds, extra: dict) -> dict:
    """One registered or control row through H.run_cells, with its bands and what is read beside it."""
    rows = H.run_cells(dd, family, POINT, cand, cand, [cut], {label: [side]}, placebo=placebo, strength=strength,
                       choose_seasons=CHOOSE, times=times, market_groups={label: ("totals",)})
    assert len(rows) == 1
    r = rows[0]
    r.update(band_rows(cand, side, strength, bounds, dd.games) if bounds else
             {**{"band_slots": 0}, **{f"band{i}_{k}": (0 if k == "n" else np.nan) for i in range(G5.BAND_SLOTS)
                                      for k in ("lo", "hi", "n", "units", "roi")}})
    b = qualifying(cand, cut, side, strength)
    g = H.grade(b, dd.games) if len(b) else b
    r.update(side_views(g))
    r.update(dk_view(cand, dd.games, cut, side, strength))
    r["void_bets"] = int(len(b) - len(g))
    r["share_still_offered"] = np.nan     # one snapshot a game: unknowable, not zero
    r["units_still_offered"] = np.nan
    r.update(extra)
    return r


def pj_bounds(floor: float, card: bool = False) -> list[tuple[float, float]]:
    base = 0.0 if card else floor
    e = [base + x for x in PJ_BAND_EDGES]
    return [(e[i], e[i + 1] if i + 1 < len(e) else np.inf) for i in range(len(e))]


def registered_cells(prep: dict, plc: bool, progress=say) -> tuple[list[dict], list[dict]]:
    """(the 7 judged rows, the control rows). `plc`: 200 placebo runs on each judged row and the card
    and caps rows (a control never judged); False is the synthetic checks' shortcut."""
    dd, times = prep["dd"], prep["times"]
    pm, pjp = prep["pm_pricer"], prep["pj_pricer"]
    pm_real, pj_real = pm.priced(), pjp.priced()
    t0 = time.time()
    rows, ctl = [], []
    lazy = (lambda build: G5.LazyFrames(PLACEBO_SEEDS, build)) if plc else (lambda build: None)
    rows.append(emit(dd, times, FAM_PM, LABEL_PM, "under", PM_FLOOR, pm_real, lazy(pm.placebo), "ev", PM_BANDS,
                     {"signal_meaning": "nba_prop_market as shipped"}))
    progress(f"cell {FAM_PM} done, {time.time() - t0:.0f}s")
    market_pricers = {}
    for mk, (sides, floor) in pj.CARD.items():
        sub = prep["pj_offers"][prep["pj_offers"].real_market == mk]
        p = ProjectionPricer(sub)
        market_pricers[mk] = p
        side = sides[0] if len(sides) == 1 else SIDE_BOTH
        real = p.priced()
        rows.append(emit(dd, times, FAM_PJ, mk, side, float(floor), real, lazy(p.placebo), "ev", pj_bounds(float(floor)),
                         {"signal_meaning": "nba_prop_projection market cell as shipped"}))
        progress(f"cell {FAM_PJ} {mk} done, {time.time() - t0:.0f}s")
    assert len(rows) == EXPECTED_CELLS, len(rows)
    ctl.append(emit(dd, times, CTL_CARD, "pj_six_cells", SIDE_CARD, 0.0, pj_real, lazy(pjp.placebo), "margin",
                    pj_bounds(0.0, card=True), {"signal_meaning": "control: the six cells pooled, caps off"}))
    cap = capped_frame(pm_real, pj_real)

    def cap_placebo(seed):
        return capped_frame(pm.placebo(seed), pjp.placebo(seed))
    ctl.append(emit(dd, times, CTL_CAPS, "both_models", SIDE_CARD, 1.0, cap, lazy(cap_placebo), "capped", None,
                    {"signal_meaning": "control: both models through the shipped caps"}))
    progress(f"controls with placebo done, {time.time() - t0:.0f}s")
    if prep.get("pm_noclock") is not None:
        ctl.append(emit(dd, times, CTL_PM_NOCLOCK, LABEL_PM, "under", PM_FLOOR, prep["pm_noclock"].priced(), None, "ev",
                        None, {"signal_meaning": "control: nba_prop_market without the soft-clock refusal"}))
    if prep.get("pj_noclock") is not None:
        ctl.append(emit(dd, times, CTL_PJ_NOCLOCK, "pj_six_cells", SIDE_CARD, 0.0, prep["pj_noclock"].priced(), None,
                        "margin", None, {"signal_meaning": "control: the six cells without the clock refusal"}))
    if prep.get("pj_frozen") is not None:
        ctl.append(emit(dd, times, CTL_FROZEN, "pj_six_cells", SIDE_CARD, 0.0, prep["pj_frozen"].priced(), None,
                        "margin", None, {"signal_meaning": "control: regular-season history only"}))
    progress(f"all rows done, {time.time() - t0:.0f}s")
    return rows, ctl


# ── everything the cells read ───────────────────────────────────────────────

def load_settlement(work: Path, cache: Path) -> dict:
    """Plays, box and ESPN's box -> the derived lines, the regular-season validation against the log,
    the postseason cross-check against ESPN's box, and who took the court. Results of bets: none read."""
    games = pd.read_parquet(work / "nba_pbp_games.parquet")
    plays = pd.read_parquet(work / "nba_pbp_slim.parquet")
    box = pd.read_parquet(work / "nba_pbp_box.parquet")
    id_map = pd.read_parquet(cache / "nba_player_id_map.parquet")
    lines = derive_lines(plays, box, id_map)
    del plays
    espn_paths = sorted((work / "espn_box_dl").glob("player_box_*.parquet"))
    if len(espn_paths) != len(SEASONS):
        raise RuntimeError(f"{work / 'espn_box_dl'} holds {len(espn_paths)} of ESPN's box files: run --pull")
    espn = espn_box_lines(espn_paths, games)
    log = pd.read_parquet(cache / "nba_player_game_log.parquet")
    log = log[log.season.isin(SEASONS)].copy()
    log["player_id"] = log.player_id.astype(str)
    log[list(BOX_STATS)] = log[list(BOX_STATS)].astype(float)
    reg_ids = set(games[(games.season_type == 2) & games.in_games & games.season.isin(SEASONS)].game_id)
    reg = compare_lines(lines[lines.game_id.isin(reg_ids) & lines.player_id.notna()], log[log.game_id.isin(reg_ids)],
                        ["game_id", "player_id"])
    both = espn.merge(lines[["game_id", "espn_id", "player_id"]], on=["game_id", "espn_id"], how="inner")
    espn_log = compare_lines(both[both.game_id.isin(reg_ids)], log[log.game_id.isin(reg_ids)], ["game_id", "player_id"])
    return {"games": games, "box": box, "lines": lines, "espn": espn, "log": log, "regular": reg, "espn_vs_log": espn_log,
            "regular_games": len(reg_ids)}


def take_court(lines: pd.DataFrame, adv: pd.DataFrame, game_ids) -> pd.DataFrame:
    """The shipped void rule (scripts/nba_prop_market_lab.build_quotes): minutes above zero or any
    seconds in NBA.com's box. A player with no such line is void."""
    a = adv[adv.game_id.isin(set(game_ids))][["game_id", "player_id", "seconds_played"]].copy()
    a["player_id"] = a.player_id.astype(str)
    x = lines[lines.game_id.isin(set(game_ids)) & lines.player_id.notna()][["game_id", "player_id", "minutes"]].merge(
        a, on=["game_id", "player_id"], how="left")
    x["action"] = (x.minutes.fillna(0) > 0) | (x.seconds_played.fillna(0) > 0)
    return x


def prepare(cache: Path, work: Path, frozen: bool = True) -> dict:
    """Every frame the cells read, on the real data. Nothing here joins a stat to a bet."""
    t0 = time.time()
    st = load_settlement(work, cache)
    say(f"settlement loaded, {time.time() - t0:.0f}s")
    raw, decisions, fr = shipped_frame(cache, work)
    say(f"shipped frame {fr.shape}, {time.time() - t0:.0f}s")
    folds = fit_folds(fr, work)
    alpha_by = fit_widths(fr, folds, work)
    pairs = regular_pairs(fr, raw, folds, alpha_by, work)
    maps = season_maps(pairs)
    proxy = proxy_map(fr, folds, alpha_by)
    with open(ARTIFACT, "rb") as fh:
        artifact = pickle.load(fh)
    say(f"folds, widths, pairs {len(pairs):,}, {time.time() - t0:.0f}s")
    del fr

    props = pd.read_parquet(work / "nba_postseason_prop_odds.parquet")
    pg = postseason_games(raw["nba_schedule"], props)
    props_c = props[props.market.isin(COUNT_MARKETS)]
    clean, refused = refuse_bad_rows(props_c)
    tips = dict(zip(pg.game_id, pg.commence_time))

    # the cross-check: ESPN's own box on the very games being settled
    ps_ids = set(pg.game_id)
    ps_lines = st["lines"][st["lines"].game_id.isin(ps_ids)]
    cross = compare_lines(ps_lines, st["espn"][st["espn"].game_id.isin(ps_ids)], ["game_id", "espn_id"])
    kept = ps_ids - cross["games"]
    pts_ok = st["games"][st["games"].game_id.isin(ps_ids)]
    say(f"cross-check: {len(cross['games'])} of {len(ps_ids)} games differ; kept {len(kept)}; {time.time() - t0:.0f}s")
    action = take_court(st["lines"], raw["nba_player_game_adv"], ps_ids)

    # nba_prop_market, through the research code on these tables
    gm = pg.assign(sport="NBA")
    log_ps = ps_lines.merge(action[["game_id", "player_id", "action"]], on=["game_id", "player_id"], how="left")
    log_ps = log_ps[log_ps.player_id.notna()].assign(game_date=lambda x: x.game_id.map(pg.set_index("game_id").game_date),
                                                     is_starter=lambda x: x.starter.astype(float))
    q_pm = market_quotes(clean.assign(created_at=None), gm, log_ps, raw["nba_player_game_adv"], raw["nba_game_inactives"],
                         work / "pm_cache")
    pm_rows = with_lead(market_rows(q_pm, clock=True), tips)
    pm_rows_nc = with_lead(market_rows(q_pm, clock=False), tips)
    pm_rows = pm_rows[pm_rows.game_id.isin(kept)]
    pm_rows_nc = pm_rows_nc[pm_rows_nc.game_id.isin(kept)]
    pm_off = offers_frame(pm_rows, pg, RULE_ID)
    pm_off_nc = offers_frame(pm_rows_nc, pg, RULE_ID)
    pm_pricer = MarketPricer(pm_off, pm_rows.fair_under.to_numpy())
    pm_noclock = MarketPricer(pm_off_nc, pm_rows_nc.fair_under.to_numpy())
    pm_bets = qualifying(pm_pricer.priced(), PM_FLOOR, "under")
    rule_keys = rule_keys_of(pm_bets)
    say(f"nba_prop_market: {len(pm_off):,} offers, {pm_off.game_id.nunique():,} propositions; {time.time() - t0:.0f}s")

    # nba_prop_projection
    inputs = model_inputs(pg, folds, alpha_by, maps, pairs, artifact, proxy)
    frame = postseason_frame(raw, st["lines"], pg, clean, work, history=True)
    say(f"postseason frame {frame.shape}, {time.time() - t0:.0f}s")
    q_pj = with_lead(card_quotes(clean, frame, pd.concat([raw["nba_games"], pg], ignore_index=True)), tips)
    q_pj = q_pj[q_pj.game_id.isin(kept)]
    means = postseason_means(frame, pg, inputs)
    at = card_rows(q_pj, clock=True)
    pj_off = card_offers(at, means, inputs, rule_keys, pg)
    pj_pricer = ProjectionPricer(pj_off)
    at_nc = card_rows(q_pj, clock=False)
    pj_noclock = ProjectionPricer(card_offers(at_nc, means, inputs, rule_keys, pg))
    pj_frozen, frame_frozen = None, None
    if frozen:
        frame_frozen = postseason_frame(raw, st["lines"], pg, clean, work, history=False)
        q_fz = with_lead(card_quotes(clean, frame_frozen, pd.concat([raw["nba_games"], pg], ignore_index=True)), tips)
        q_fz = q_fz[q_fz.game_id.isin(kept)]
        m_fz = postseason_means(frame_frozen, pg, inputs)
        pj_frozen = ProjectionPricer(card_offers(card_rows(q_fz, clock=True), m_fz, inputs, rule_keys, pg))
    say(f"nba_prop_projection: {len(pj_off):,} offers, {pj_off.game_id.nunique():,} propositions; {time.time() - t0:.0f}s")

    sg = settled_games(st["lines"], action, pg, kept)
    empty_q = pd.DataFrame(columns=["game_id", "market", "book", "fetch_at"])
    empty_f = pd.DataFrame({"game_id": pd.Series(dtype=object), "fetch_at": pd.Series(dtype=object),
                            "lead_min": pd.Series(dtype=float)})
    dd = H.Data(games=sg, quotes=empty_q, fetches=empty_f)
    times = sg[["game_id"]].assign(T="")
    return {"st": st, "pg": pg, "props": props, "clean": clean, "refused": refused, "cross": cross,
            "kept": kept, "dd": dd, "times": times, "pm_pricer": pm_pricer, "pm_noclock": pm_noclock, "pj_pricer": pj_pricer,
            "pj_noclock": pj_noclock, "pj_frozen": pj_frozen, "pj_offers": pj_off, "frame": frame,
            "frame_frozen": frame_frozen, "alpha_by": alpha_by, "maps": maps, "artifact": artifact, "means": means,
            "inputs": inputs, "rule_keys": rule_keys, "pts_ok": pts_ok, "q_pm": q_pm, "pairs": pairs,
            "action": action, "pm_off_nc": pm_off_nc, "raw": raw, "folds": folds, "settled_ids": set(sg.game_id)}


# ── the checks --smoke prints: counts, extremes, nulls and the clock, no grade ──

def check_artifact(prep: dict) -> dict:
    """Rebuilt from the cache alone, the fit through 2024-25 must reproduce the shipped artifact's
    widths on 2025-26 and its maps on 2023-24..2025-26: the fit, the pairs and the frame are the shipped ones."""
    art = prep["artifact"]
    out = {}
    for m in pj.MARKETS:
        out[m] = {"width_rebuilt": round(prep["alpha_by"][2026][m], 6), "width_shipped": round(art["alphas"][m], 6),
                  "map_rebuilt": [round(float(x), 5) for x in prep["maps"][2026][m]],
                  "map_shipped": [round(float(x), 5) for x in art["calibration"][m]]}
    out["pairs_rebuilt"] = int(len(prep["pairs"]))
    out["pairs_shipped"] = int(art["calibration_pairs"]["n"])
    return out


def check_regular_rule(work: Path, raw: dict) -> dict:
    """The rule code on the regular seasons: the same bets as the stored graded list, bet for bet.
    Those seasons are the record, not this search; their results are not read here, only who is bet."""
    if not RULE_BETS.exists():
        return {"skipped": f"{RULE_BETS} is not on this machine"}
    raw_games = raw["nba_games"]
    f = work / "pm_regular_quotes.parquet"
    props = raw["nba_props"]
    props = props[props.game_date < "2026-10-20"]
    if f.exists():
        q = pd.read_parquet(f)
    else:
        log = raw["nba_player_game_log"]
        q = market_quotes(props, raw_games, log, raw["nba_player_game_adv"], raw["nba_game_inactives"], work / "pm_reg")
        q.to_parquet(f)
    rows = market_rows(q, clock=False)
    rows = rows[rows.game_id.isin(set(raw_games.game_id))]
    rows = rows.assign(ev=rows.fair_under.to_numpy() * rows.dec.to_numpy() - 1.0)
    rows = rows[(rows.ev >= PM_FLOOR) & (rows.price >= H.PRICE_FLOOR)].copy()
    rows["_r"] = rows.bookmaker.map(H.BOOK_RANK).fillna(99)
    best = rows.sort_values(["ev", "_r"], ascending=[False, True]).drop_duplicates(KEY)
    stored = pd.read_parquet(RULE_BETS, columns=[*KEY, "price"])       # who was bet, never what it won
    stored = stored[stored.market.isin(PM.MARKETS) & (stored.price >= H.PRICE_FLOOR)]
    a = set(zip(best.game_id, best.player_id.astype(str), best.market))
    b = set(zip(stored.game_id, stored.player_id.astype(str), stored.market))
    return {"rebuilt": len(a), "stored": len(b), "in_both": len(a & b), "by_season": best.groupby("season").size().to_dict()}


def shipped_rule_bets(quotes: pd.DataFrame, names: pd.DataFrame, teams: dict) -> pd.DataFrame:
    """models.nba_prop_market.find_bets itself, one game at a time on the raw quotes, each game's tip
    set 54 minutes after its snapshot because the registration lifts the shipped window (section 2).
    `names`: (game_id, player_name, player_id) from the research matching. `teams`: {game: (home, away)}.
    Reads prices and names only."""
    bets = []
    who = {g: list(zip(x.player_id.astype(str), x.player_name)) for g, x in names.groupby("game_id")}
    for gid, g in quotes[quotes.market.isin(PM.MARKETS)].groupby("game_id"):
        now = PM.parse_ts(g.snapshot_at.iloc[0])
        home, away = teams[gid]
        roster = PM.Roster([(p, n, home) for p, n in who.get(gid, [])])
        rows = [{"game_id": gid, "player": r.player_name, "market": r.market, "book": r.bookmaker, "line": r.line,
                 "over_price": None if pd.isna(r.over_price) else float(r.over_price),
                 "under_price": None if pd.isna(r.under_price) else float(r.under_price),
                 "snapshot_at": r.snapshot_at, "snapshot_type": "open",
                 "book_last_update": None if pd.isna(r.book_last_update) else r.book_last_update}
                for r in g.itertuples()]
        info = {gid: {"home": home, "away": away, "tip": now + pd.Timedelta(minutes=54).to_pytimedelta(),
                      "game_date": g.game_date.iloc[0]}}
        bets += PM.find_bets(rows, info, roster, now)[0]
    return pd.DataFrame([{"game_id": f"{b.game_id}|{b.player_id}|{b.market}", "book": b.book, "price": b.price,
                          "line": b.line, "ev": b.ev} for b in bets], columns=["game_id", "book", "price", "line", "ev"])


def compare_to_shipped(lab: pd.DataFrame, shipped: pd.DataFrame) -> dict:
    """Bet for bet: the lab's nba_prop_market bets against the shipped code's."""
    m = shipped.merge(lab[["game_id", "book", "price", "line"]], on="game_id", how="outer", suffixes=("_ship", "_lab"),
                      indicator=True)
    both = m[m._merge == "both"]
    same = (both.book_ship == both.book_lab) & (both.price_ship == both.price_lab) & (both.line_ship == both.line_lab)
    return {"shipped": int(len(shipped)), "lab": int(len(lab)), "in_both": int(len(both)), "same_book_price_line": int(same.sum()),
            "shipped_only": sorted(m.game_id[m._merge == "left_only"]), "lab_only": sorted(m.game_id[m._merge == "right_only"])}


def check_shipped_rule(prep: dict) -> dict:
    """The lab's rule on these games against the shipped code, on the real quotes. check_regular_rule
    compares to the research lab's stored list, which proves research parity and not this."""
    q = prep["q_pm"]
    names = q[q.usable & q.x.notna()][["game_id", "player_name", "player_id"]].drop_duplicates()
    pg = prep["pg"]
    teams = dict(zip(pg.game_id, zip(pg.home_team, pg.away_team)))
    clean = prep["clean"]
    shipped = shipped_rule_bets(clean[clean.game_id.isin(prep["kept"])], names, teams)
    return compare_to_shipped(qualifying(prep["pm_pricer"].priced(), PM_FLOOR, "under"), shipped)


def floor_ties(prep: dict, within: float = 1e-9) -> dict:
    """Offers within a rounding step of their cell's floor: the only offers this arithmetic can decide."""
    ev = prep["pm_pricer"].priced().ev - PM_FLOOR
    out = {LABEL_PM: {"at_the_floor": int(ev.abs().lt(within).sum()), "just_below": int((ev.lt(0) & ev.gt(-within)).sum())}}
    for mk, g in prep["pj_pricer"].priced().groupby("real_market"):
        out[mk] = {"at_the_floor": int(g.margin.abs().lt(within).sum()),
                   "just_below": int((g.margin.lt(0) & g.margin.gt(-within)).sum())}
    return out


def check_regular_card(prep_like: dict) -> dict:
    """The six cells on 2024-25 and 2025-26 (2023-24 ran on weekly maps): the same bets as the stored card."""
    from scripts import nba_prop_model_lab as lab
    from scripts import nba_prop_projection_train as TR
    if not CARD_BETS.exists():
        return {"skipped": f"{CARD_BETS} is not on this machine"}
    fr, raw, folds, alpha_by, pairs = (prep_like[k] for k in ("fr", "raw", "folds", "alpha_by", "pairs"))
    props = raw["nba_props"]
    q = card_quotes(props[props.game_date < TR.LAST_RESEARCH_DATE], fr, raw["nba_games"])
    q = q[q.usable & ~q.status.isin(OUT_STATUS)]
    stored = pd.read_parquet(CARD_BETS, columns=[*KEY, "side", "season", "ev", "is_main", "rule_key"])
    stored = stored[stored.market.isin(pj.MARKETS) & stored.season.isin([2025, 2026])]
    stored = stored[[pj.CARD[m][0] is not None and s in pj.CARD[m][0] for m, s in zip(stored.market, stored.side)]]
    stored = stored[stored.ev >= stored.market.map(lambda m: pj.CARD[m][1])]
    rule = pd.read_parquet(RULE_BETS, columns=KEY)
    rk = set(zip(rule.game_id, rule.player_id.astype(str), rule.market))
    main = lab.main_lines(q).rename(columns={"line": "main_line"})
    main["player_id"] = main.player_id.astype(str)
    P = lab.propositions(q).merge(main, on=KEY)
    P = P[(P.line == P.main_line) & P.season.isin([2025, 2026])]
    lead = (nb._utc(P.game_id.map(raw["nba_games"].drop_duplicates("game_id").set_index("game_id").commence_time))
            - nb._utc(P.snapshot_at)).dt.total_seconds() / 60
    P = P[lead.between(*LEAD_MIN).to_numpy()]
    P = P[[k not in rk for k in zip(P.game_id, P.player_id, P.market)]]
    P = P[[s in pj.CARD[m][0] for m, s in zip(P.market, P.side)]]
    got = []
    for s in (2025, 2026):
        te = fr[nb.usable(fr) & (fr.season == s)]
        mu = means_for(te, folds[s - 1])
        mp = nb.fit_calibration(pairs, s)
        x = P[P.season == s].merge(mu, on=["game_id", "player_id"])
        for mk in pj.MARKETS:
            u = x[x.market == mk]
            po = nb.apply_calibration(nb.p_over(u[f"mu_{mk}"].to_numpy(), u.line.to_numpy(), alpha_by[s - 1][mk]), mp[mk])
            pr = np.where(u.side == "over", po, 1 - po)
            ev = nb.expected_value(pr, u.price.to_numpy())
            u = u.assign(ev=ev)
            u = u[u.ev >= pj.CARD[mk][1]].sort_values("ev", ascending=False).drop_duplicates(KEY)
            got.append(u[[*KEY, "side", "season"]])
    g = pd.concat(got, ignore_index=True)
    a = set(zip(g.game_id, g.player_id, g.market, g.side))
    st_ = stored.sort_values("ev", ascending=False).drop_duplicates(KEY)
    b = set(zip(st_.game_id, st_.player_id.astype(str), st_.market, st_.side))
    return {"rebuilt": len(a), "stored": len(b), "in_both": len(a & b),
            "by_market": g.groupby("market").size().to_dict()}


def regular_checks(prep: dict, cache: Path, work: Path) -> dict:
    """Both rules' code run on the three regular seasons they were graded on, against the stored bet lists."""
    raw = prep["raw"]
    rule = check_regular_rule(work, raw)
    fr = pd.read_parquet(work / "frame_shipped.parquet")
    card = check_regular_card({"fr": fr, "raw": raw, "folds": prep["folds"], "alpha_by": prep["alpha_by"],
                               "pairs": prep["pairs"]})
    return {"nba_prop_market": rule, "nba_prop_projection": card}


def counts(prep: dict) -> dict:
    """Propositions and bets per cell, season and phase. Counted, never graded."""
    pg = prep["pg"]
    phase = dict(zip(pg.game_id, pg.phase))
    pm, pjp = prep["pm_pricer"], prep["pj_pricer"]
    out = []
    real = pm.priced()
    b = qualifying(real, PM_FLOOR, "under")

    def row(fam, label, cand, b, floor):
        byp = b.real_game.map(phase).value_counts().to_dict()
        return {"family": fam, "cell": label, "floor": floor, "propositions": int(cand.game_id.nunique()),
                **{f"bets_{s}": int((b.season == s).sum()) for s in SEASONS}, "bets_pooled": int(len(b)),
                "void_no_court": int((~b.game_id.isin(prep["settled_ids"])).sum()),
                **{f"bets_{p}": int(byp.get(p, 0)) for p in PHASES},
                "unders": int((b.side == "under").sum()), "price_min": float(b.price.min()) if len(b) else np.nan,
                "price_median": float(b.price.median()) if len(b) else np.nan,
                "price_max": float(b.price.max()) if len(b) else np.nan, "ev_max": float(b.ev.max()) if len(b) else np.nan}
    out.append(row(FAM_PM, LABEL_PM, real, b, PM_FLOOR))
    for mk, (sides, floor) in pj.CARD.items():
        sub = prep["pj_offers"][prep["pj_offers"].real_market == mk]
        p = ProjectionPricer(sub).priced()
        side = sides[0] if len(sides) == 1 else SIDE_BOTH
        out.append(row(FAM_PJ, mk, p, qualifying(p, float(floor), side), float(floor)))
    pjr = pjp.priced()
    card = qualifying(pjr, 0.0, SIDE_CARD, "margin")
    out.append(row(CTL_CARD, "pj_six_cells", pjr, card, 0.0))
    cap = capped_frame(real, pjr)
    capb = qualifying(cap, 1.0, SIDE_CARD, "capped")
    out.append(row(CTL_CAPS, "both_models", cap, capb, 1.0))
    return {"cells": out, "cap_by_model": capb.model.value_counts().to_dict(),
            "cap_games_bet": int(capb.real_game.nunique()), "dates_most_games": int(pg.groupby("game_date").size().max())}


def band_counts(prep: dict) -> list[dict]:
    """How many bets sit in each registered band (counted): a band under 30 is not judged."""
    def n(c, lo, hi, side, strength="ev"):
        a = set(qualifying(c, lo, side, strength).game_id)
        return len(a - set(qualifying(c, hi, side, strength).game_id)) if np.isfinite(hi) else len(a)
    out = [{"cell": LABEL_PM, **{f"{lo:+.2f}": n(prep["pm_pricer"].priced(), lo, hi, "under") for lo, hi in PM_BANDS}}]
    for mk, (sides, floor) in pj.CARD.items():
        p = ProjectionPricer(prep["pj_offers"][prep["pj_offers"].real_market == mk]).priced()
        side = sides[0] if len(sides) == 1 else SIDE_BOTH
        out.append({"cell": mk, **{f"{lo:+.2f}": n(p, lo, hi, side) for lo, hi in pj_bounds(float(floor))}})
    return out


def placebo_null(prep: dict, seeds=range(1, 21)) -> dict:
    """Lesson 2: the share of placebo bets that differ from the real bets, per cell, and on the thin
    rounds, and how many propositions are in a group of one. The real data, no result read."""
    out = {}
    pm = prep["pm_pricer"]
    real = qualifying(pm.priced(), PM_FLOOR, "under")

    def run(p, cut, side, label, real):
        shares, by_round = [], {}
        for s in seeds:
            b = qualifying(p.placebo(s), cut, side)
            shares.append(differing_share(real, b))
            for rd, x in b.groupby("round"):
                by_round.setdefault(rd, []).append(differing_share(real[real["round"] == rd], x))
        g = pd.Series(p.groups).value_counts()
        out[label] = {"share_differ": round(float(np.nanmean(shares)), 3),
                      "by_round": {k: round(float(np.nanmean(v)), 3) for k, v in sorted(by_round.items())},
                      "propositions": int(len(p.keys)), "groups": int(g.size), "alone_in_group": int((g == 1).sum())}
    run(pm, PM_FLOOR, "under", LABEL_PM, real)
    for mk, (sides, floor) in pj.CARD.items():
        p = ProjectionPricer(prep["pj_offers"][prep["pj_offers"].real_market == mk])
        side = sides[0] if len(sides) == 1 else SIDE_BOTH
        run(p, float(floor), side, mk, qualifying(p.priced(), float(floor), side))
    return out


def timed_placebo(prep: dict) -> dict:
    """One placebo run of every row on the real data, graded on blinded stats (every stat 0): the
    clock of a real run with no result computed. Printed with the projected --full time."""
    st, pg = prep["st"], prep["pg"]
    blind = settled_games(st["lines"], prep["action"], pg, prep["kept"], blind=True)
    t0 = time.time()
    pm, pjp = prep["pm_pricer"], prep["pj_pricer"]
    H.grade(qualifying(pm.placebo(1), PM_FLOOR, "under"), blind)
    for mk, (sides, floor) in pj.CARD.items():
        p = ProjectionPricer(prep["pj_offers"][prep["pj_offers"].real_market == mk])
        side = sides[0] if len(sides) == 1 else SIDE_BOTH
        H.grade(qualifying(p.placebo(1), float(floor), side), blind)
    H.grade(qualifying(pjp.placebo(1), 0.0, SIDE_CARD, "margin"), blind)
    capf = capped_frame(pm.placebo(1), pjp.placebo(1))
    H.grade(qualifying(capf, 1.0, SIDE_CARD, "capped"), blind)
    one = time.time() - t0
    return {"seconds_one_run_all_rows": round(one, 2), "projected_placebo_minutes": round(one * 200 / 60, 1)}


def highest_ev(prep: dict, n: int = 12) -> dict:
    """The highest-EV offers each model would take, by the rule: read for impossible numbers."""
    a = qualifying(prep["pm_pricer"].priced(), PM_FLOOR, "under").nlargest(n, "ev")
    b = qualifying(prep["pj_pricer"].priced(), 0.0, SIDE_CARD, "margin").nlargest(n, "ev")
    cols = ["game_id", "side", "book", "line", "price", "p_win", "ev"]
    return {"nba_prop_market": a[cols], "nba_prop_projection": b[cols + ["model_mu"]]}


def input_state(prep: dict) -> dict:
    """What the projection reads on postseason rows: report coverage, and the two history choices."""
    fr = prep["frame"]
    fr = fr[nb.usable(fr)]
    rd = fr.game_id.map(prep["pg"].set_index("game_id")["round"])
    out = {"usable_rows": int(len(fr)), "covered_by_a_report": float(fr.covered.mean())}
    out["days_since_median_by_round"] = fr.groupby(rd).days_since.median().round(1).to_dict()
    out["rest_median_by_round"] = fr.groupby(rd).rest.median().round(1).to_dict()
    ff = prep.get("frame_frozen")
    if ff is not None:
        ff = ff[nb.usable(ff)]
        rd2 = ff.game_id.map(prep["pg"].set_index("game_id")["round"])
        out["frozen_days_since_median_by_round"] = ff.groupby(rd2).days_since.median().round(1).to_dict()
        out["frozen_share_days_since_at_30_by_round"] = (ff.days_since >= 30).groupby(rd2).mean().round(3).to_dict()
    return out


# ── synthetic checks (each watched failing when its rule is broken) ─────────

def synthetic_plays() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One game: player 1 (home) and 2 (away), 3 played with no event, 4 did not play."""
    r = []

    def p(type_id, type_text, a1, a2=None, score=False, shot=False, value=None, points=0, text=""):
        r.append({"espn_game_id": 9, "play_no": len(r), "game_id": "G", "season": 2024, "type_id": type_id,
                  "type_text": type_text, "scoring_play": score, "shooting_play": shot, "shot_value": value,
                  "points": points, "athlete_id_1": a1, "athlete_id_2": a2, "text": text})
    p(92, "Jump Shot", 1, 2, True, True, 3, 3, "A makes three point jumper (B assists)")
    p(92, "Jump Shot", 1, None, False, True, 3, 0, "A misses three point jumper")
    p(95, "Layup Shot", 2, 1, False, True, 2, 0, "A blocks B 's 3-foot layup")
    p(95, "Layup Shot", 2, None, True, True, 2, 2, "B makes layup")
    p(98, "Free Throw - 1 of 2", 2, None, True, True, 1, 1, "B makes free throw 1 of 2")
    p(99, "Free Throw - 2 of 2", 2, None, False, True, 1, 0, "B misses free throw 2 of 2")
    p(156, "Offensive Rebound", 2, None, text="B offensive rebound")
    p(155, "Defensive Rebound", 1, None, text="A defensive rebound")
    p(155, "Defensive Rebound", None, None, text="Team defensive team rebound")
    p(62, "Bad Pass\nTurnover", 2, 1, text="B bad pass (A steals)")
    p(84, "Offensive Foul Turnover", 1, None, text="A turnover")
    p(70, "Shot Clock Turnover", None, None, text="shot clock turnover")
    p(61, "No Turnover", 1, None, text="A turnover")
    p(282, "Heave Jump Shot", 1, None, False, True, 3, 0, "A misses heave jump shot")
    p(155, "Defensive Rebound", 2, None, text="B defensive rebound")
    box = pd.DataFrame({"espn_game_id": 9, "espn_id": [1, 2, 3, 4], "game_id": "G", "season": 2024,
                        "side": ["H", "A", "H", "H"], "team": ["AAA", "BBB", "AAA", "AAA"], "name": ["A", "B", "C", "D"],
                        "starter": [True, True, False, False], "minutes": [30.0, 28.0, 2.0, np.nan],
                        "did_not_play": [False, False, False, True]})
    id_map = pd.DataFrame({"espn_id": [1, 2, 3, 4], "player_id": ["101", "102", "103", "104"]})
    return pd.DataFrame(r), box, id_map


def synthetic_market() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A research-shaped quote frame for three propositions with Pinnacle and two books."""
    base = {"game_id": "G", "season": 2024, "game_date": "2024-04-20", "snapshot_at": "2024-04-20T22:06:00Z",
            "usable": True, "x": 10.0, "has_o": True, "has_u": True, "coherent": True}

    def q(player, market, book, line, over, under, clock="2024-04-20T22:05:00Z", **kw):
        return {**base, "player_id": player, "market": market, "bookmaker": book, "line": line, "over_price": over,
                "under_price": under, "od": float(nb.decimal(over)), "ud": float(nb.decimal(under)),
                "book_last_update": clock, **kw}
    rows = [
        # P1: Pinnacle fair under 0.5; DK +105 clears at its line, FanDuel's line is another number
        q("P1", "player_points", "pinnacle", 20.5, -110, -110),
        q("P1", "player_points", "draftkings", 20.5, -125, 105),
        q("P1", "player_points", "fanduel", 21.5, -125, 110),
        # P2: the best price is stale by more than ten minutes, the fresh one does not clear
        q("P2", "player_rebounds", "pinnacle", 8.5, -110, -110),
        q("P2", "player_rebounds", "betmgm", 8.5, -125, 105, clock="2024-04-20T21:40:00Z"),
        q("P2", "player_rebounds", "draftkings", 8.5, -105, -115),
        # P3: a double-double is no market of this rule
        q("P3", "player_double_double", "pinnacle", 0.5, -110, -110),
        q("P3", "player_double_double", "draftkings", 0.5, -125, 105),
        # P4: Pinnacle incoherent
        q("P4", "player_assists", "pinnacle", 5.5, 200, 200, coherent=False),
        q("P4", "player_assists", "draftkings", 5.5, -125, 105),
    ]
    games = pd.DataFrame({"game_id": ["G"], "season": [2024], "game_date": ["2024-04-20"], "phase": ["playoffs"],
                          "round": ["first_round"], "commence_time": ["2024-04-20T23:00:00Z"]})
    return pd.DataFrame(rows), games


def synthetic_harness() -> dict:
    """A small end-to-end cell: each market's offers through H.run_cells and the verdict's contract."""
    from scripts.nba_game2_verdict import house_verdict_bands
    rng = np.random.default_rng(5)
    n = 900
    days = np.array(pd.date_range("2024-04-20", periods=30).strftime("%Y-%m-%d"))
    rows = []
    for i in range(n):
        s = SEASONS[i % 3]
        day = days[i % 30].replace("2024", str(s))
        rows.append({"gid": f"NBA_{day}_A_B", "pl": str(i), "mk": "player_steals", "season": s, "date": day})
    k = pd.DataFrame(rows)
    pid = pid_of(k.gid, k.pl, k.mk)
    won = rng.random(n) < 0.6
    sg = pd.DataFrame({"game_id": pid, "real_game": k.gid, "season": k.season, "game_date": k.date,
                       "real_market": k.mk, "home_score": np.where(won, 0.0, 2.0), "away_score": 0.0})
    off = pd.DataFrame({"game_id": pid, "real_game": k.gid, "player_id": k.pl, "real_market": k.mk, "market": "totals",
                        "side": "under", "book": "draftkings", "line": 0.5, "price": -110.0, "season": k.season,
                        "game_date": k.date, "T": "t", "lead_min": 54.0, "phase": "playoffs", "round": "first_round",
                        "mu": np.nan, "p_home": np.nan, "model": PROJECTION_ID, "p_push": 0.0, "p_win": 0.55,
                        "ev": rng.uniform(-0.03, 0.10, n), "side_pick": "under", "margin": 0.0})
    dd = H.Data(games=sg, quotes=pd.DataFrame(columns=["game_id", "market", "book", "fetch_at"]),
                fetches=pd.DataFrame({"game_id": pd.Series(dtype=object), "fetch_at": pd.Series(dtype=object),
                                      "lead_min": pd.Series(dtype=float)}))
    times = sg[["game_id"]].assign(T="")
    plc = G5.LazyFrames(PLACEBO_SEEDS, lambda seed: off.assign(ev=np.random.default_rng(seed).uniform(-0.03, 0.10, n)))
    r = emit(dd, times, FAM_PJ, "player_steals", "under", 0.02, off, plc, "ev", pj_bounds(0.02), {"signal_meaning": "synthetic"})
    v = house_verdict_bands(pd.DataFrame([r]))
    return {"row": r, "verdict": v.iloc[0], "offers": off, "games": sg}


def synthetic_checks() -> dict:
    """Each line is a rule of the registration, on data that contains what it claims to cover."""
    # 1. the derivation, stat by stat, on a game holding every event type it reads
    plays, box, ids = synthetic_plays()
    x = derive_lines(plays, box, ids).set_index("espn_id")
    assert (x.loc[1, "points"], x.loc[1, "fg3_made"], x.loc[1, "fg3_att"], x.loc[1, "assists"]) == (3, 1, 2, 0)
    assert (x.loc[1, "blocks"], x.loc[1, "steals"], x.loc[1, "turnovers"], x.loc[1, "rebounds"]) == (1, 1, 1, 1)
    assert (x.loc[2, "points"], x.loc[2, "ft_att"], x.loc[2, "rebounds"], x.loc[2, "turnovers"]) == (3, 2, 2, 1)
    assert (x.loc[2, "assists"], x.loc[2, "blocks"], x.loc[2, "steals"]) == (1, 0, 0)
    assert x.loc[3, "points"] == 0 and 4 not in x.index and x.loc[1, "fg_att"] == 2
    # 2. the cross-check leaves out a game differing on one stat of one player
    e = x.reset_index()[["game_id", "espn_id", *BOX_STATS]].copy()
    e2 = pd.concat([e.assign(game_id="H"), e.assign(game_id="G")], ignore_index=True)
    e2.loc[(e2.game_id == "G") & (e2.espn_id == 2), "steals"] = 1.0
    c = compare_lines(e2[e2.game_id == "G"], x.reset_index(), ["game_id", "espn_id"])
    assert c["games"] == {"G"} and c["by_stat"]["steals"] == (1, 1) and c["by_stat"]["points"] == (0, 0)
    # 3. nba_prop_market: exact line, the clock, its five markets, Pinnacle coherent
    q, g = synthetic_market()
    r = market_rows(q, clock=True)
    assert set(zip(r.player_id, r.bookmaker)) == {("P1", "draftkings"), ("P2", "draftkings")}, r
    r2 = market_rows(q, clock=False)
    assert ("P2", "betmgm") in set(zip(r2.player_id, r2.bookmaker))
    # 3b. Pinnacle +116 / -140 against -126 is worth exactly nothing, and the floor takes it
    assert fair_under_of(116.0, -140.0) * nb.decimal(-126.0) - 1.0 == 0.0
    assert fair_under_of(-130.0, 107.0) * nb.decimal(117.0) - 1.0 == 0.0
    # 4. a prop settles through the harness: over, under, push; a void leaves the record
    bets = pd.DataFrame({"game_id": ["a|1|m", "b|1|m", "c|1|m", "d|1|m", "e|1|m"], "market": "totals",
                         "side": ["over", "under", "under", "over", "under"], "line": [5.5, 5.5, 5.0, 5.5, 5.5],
                         "price": -110.0, "season": 2024, "game_date": "d", "book": "draftkings"})
    games = pd.DataFrame({"game_id": ["a|1|m", "b|1|m", "c|1|m", "d|1|m"], "home_score": [6.0, 5.0, 5.0, 5.0],
                          "away_score": 0.0})
    gr = H.grade(bets, games).set_index("game_id")
    assert list(gr.result) == ["W", "W", "P", "L"] and "e|1|m" not in gr.index
    # 4b. a settled table of several players: every id distinct, and an offer's id finds its row
    ln = pd.DataFrame({"game_id": ["A", "A", "A"], "player_id": ["1", "2", "3"], **{c: 2.0 for c in BOX_STATS}})
    ac = pd.DataFrame({"game_id": ["A", "A", "A"], "player_id": ["1", "2", "3"], "action": True})
    gg = pd.DataFrame({"game_id": ["A"], "season": [2024], "game_date": ["d"]})
    sg = settled_games(ln, ac, gg, {"A"}, markets=("player_steals", "player_blocks"))
    assert sg.game_id.is_unique and sg.game_id.notna().all() and len(sg) == 6
    assert "A|2|player_blocks" in set(sg.game_id)
    # 5. the bad-rows rule
    t = pd.DataFrame({"market": "player_points", "line": [20.5, 99.5, 20.5, 20.5, 20.5],
                      "over_price": [-110, -110, -40000, 200, -110], "under_price": [-110, -110, 30000, 200, np.nan]})
    kept, n = refuse_bad_rows(t, {"player_points": (0.5, 60.5)})
    assert len(kept) == 2 and (n["line_outside_range"], n["impossible_price"], n["incoherent_two_way"]) == (1, 1, 1)
    # 6. the placebo is a null on a one-game date, and a thin group widens to its round
    keys = pd.DataFrame({"game_date": ["d1"] * 6 + ["d2"] * 2 + ["d3"] * 2, "real_market": "m", "season": 2024,
                         "round": ["finals"] * 6 + ["conf_finals"] * 4})
    gp = placebo_groups(keys)
    assert gp[0] == gp[5] and gp[6] == gp[8] and gp[0] != gp[6]
    v = np.arange(10.0)
    sh = shuffled(v, gp, 1)
    assert sorted(sh[:6]) == sorted(v[:6]) and sorted(sh[6:]) == sorted(v[6:])
    assert any(not np.array_equal(shuffled(v, gp, s), v) for s in range(1, 4))
    # 7. every cell's row reads the verdict's contract
    h = synthetic_harness()
    assert len(h["row"]["placebo_rois"]) == 200 and h["row"]["pool_n"] > 200 and h["row"]["band0_n"] > 0
    assert h["verdict"]["key"].startswith(FAM_PJ) and "house5_passes" in h["verdict"].index
    return {"synthetic_checks": "pass"}


# ── the two runs ────────────────────────────────────────────────────────────

def peak_memory_gb() -> float | None:
    """This process's peak memory so far, where psutil is installed."""
    try:
        import psutil
    except ImportError:
        return None
    info = psutil.Process().memory_info()
    return round(getattr(info, "peak_wset", info.rss) / 2 ** 30, 2)


def refuse_full() -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    return why


def smoke(cache: Path, work: Path) -> dict:
    print(json.dumps(synthetic_checks()), flush=True)
    prep = prepare(cache, work)
    st = prep["st"]
    print(json.dumps({
        "validation_regular_season_vs_player_log": {
            "games_compared": st["regular_games"],
            "by_stat_rows_games": st["regular"]["by_stat"],
            "games_with_any_difference": len(st["regular"]["games"])},
        "espn_public_box_vs_player_log": {"by_stat_rows_games": st["espn_vs_log"]["by_stat"],
                                          "games_with_any_difference": len(st["espn_vs_log"]["games"])},
        "postseason_cross_check_vs_espn_box": {
            "games": len(prep["pg"]), "by_stat_rows_games": prep["cross"]["by_stat"],
            "games_left_out": sorted(prep["cross"]["games"]), "games_kept": len(prep["kept"]),
            "left_out_by_phase": prep["pg"][prep["pg"].game_id.isin(prep["cross"]["games"])].phase.value_counts().to_dict()},
        "play_points_equal_espn_final_on_every_postseason_game": bool(
            ((prep["pts_ok"].pbp_home_pts == prep["pts_ok"].espn_home_final)
             & (prep["pts_ok"].pbp_away_pts == prep["pts_ok"].espn_away_final)).all()),
        "games_by_phase_season": {str(k): int(v) for k, v in prep["pg"].groupby(["season", "phase"]).size().items()},
        "bad_rows": prep["refused"], "line_range": LINE_RANGE,
        "regular_archive_rows_outside_line_range": archive_outside(prep["raw"]["nba_props"]),
        "artifact_reproduced": check_artifact(prep), "input_state": input_state(prep),
        "regular_season_reproduced": regular_checks(prep, cache, work),
        "nba_prop_market_vs_the_shipped_code": check_shipped_rule(prep),
        "offers_at_a_floor_to_a_rounding_step": floor_ties(prep)}, indent=1, default=str), flush=True)
    print("extremes of every line and price read\n" + extremes(prep["clean"]).to_string(), flush=True)
    print("nba_postseason_prop_odds before the rule\n" + extremes(prep["props"][prep["props"].market.isin(COUNT_MARKETS)]).to_string(),
          flush=True)
    he = highest_ev(prep)
    print("highest-EV offers\n" + he["nba_prop_market"].to_string() + "\n" + he["nba_prop_projection"].to_string(), flush=True)
    c = counts(prep)
    print(pd.DataFrame(c["cells"]).to_string(index=False), flush=True)
    print(json.dumps({k: v for k, v in c.items() if k != "cells"}, indent=1, default=str), flush=True)
    print(pd.DataFrame(band_counts(prep)).to_string(index=False), flush=True)
    print(json.dumps({"placebo_differs_from_real": placebo_null(prep)}, indent=1), flush=True)
    t = timed_placebo(prep)
    print(json.dumps({"timed_placebo": t, "projected_full_minutes": round(t["projected_placebo_minutes"] + 10, 1),
                      "peak_memory_gb_this_run": peak_memory_gb()}, indent=1), flush=True)
    return c


def full(cache: Path, work: Path) -> None:
    why = refuse_full()
    if why:
        raise SystemExit("--full refused: " + "; ".join(why))
    out = Path(os.environ[RESULTS_ENV])
    print(json.dumps(synthetic_checks()), flush=True)
    prep = prepare(cache, work)
    rows, ctl = registered_cells(prep, plc=True)
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, out / "cells_registered.parquet")
    L.write_cells(ctl, out / "cells_controls.parquet")
    print(f"cells written to {out}: {len(rows)} registered, {len(ctl)} controls")


def report(results: Path) -> pd.DataFrame:
    """What every row carries beside the bars, for the owner after --full: the three postseasons,
    the three phases, the three leads, DraftKings alone. Prints only; the verdict judges."""
    from scripts.nba_game2_verdict import load_cells
    c = load_cells(results)
    cols = ["family", "market", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "n_2024", "roi_2024", "n_2025", "roi_2025", "n_confirm", "roi_confirm", "void_bets",
            *[f"phase_{p}_{k}" for p in PHASES for k in ("n", "units", "roi")],
            *[f"lead_{name}_{k}" for name in LEADS for k in ("n", "roi")],
            "dk_pool_n", "dk_pool_units", "dk_pool_roi", "blind_pool_under", "blind_pool_over",
            *[f"band{i}_{k}" for i in range(G5.BAND_SLOTS) for k in ("lo", "hi", "n", "roi")]]
    out = c[[x for x in cols if x in c]]
    print(out.T.to_string())
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", type=Path, help="after --full: what each row carries beside the bars")
    g.add_argument("--pull", action="store_true", help="the one read-only pull into the scratch folder")
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every cell (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    work = work_dir()
    if a.report:
        report(a.report)
    elif a.pull:
        pull(work)
    elif a.full:
        full(H.CACHE, work)
    else:
        smoke(H.CACHE, work)


if __name__ == "__main__":
    main()
