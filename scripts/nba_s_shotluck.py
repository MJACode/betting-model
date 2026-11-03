"""NBA search: shooting luck from shot location.

docs/nba_search_shotluck.md registers the 48 cells and fixes every choice,
committed BEFORE this lab existed and before any cell was graded (2026-10-30).
This lab EMITS cells through the shared harness (scripts/nba_game_harness, H);
the pass/fail script judges them (scripts/nba_game2_verdict.py --house5: section
9.1 of docs/nba_models_2026.md). Nothing here grades a real bet except --full,
and no cut, constant or rule below was chosen from a betting result.

  ZONES     every shot, by stored value first and location second (basket at
            (25, 0) in feet): restricted area, paint, mid-range, corner three,
            above-the-break three, heave, free throw (zone_of).
  RATE      the league's points per attempt in a zone, this season's games
            before the date; a zone under 200 attempts so far reads last
            season's whole-season rate (league_rates).
  LUCK      luck_for / luck_against: actual points from shots minus attempts x
            the zone's rate on the date, this season, strictly before the date
            (as_of_luck). A game whose plays do not add up to its stored final
            is left out of every sum (team_game_zones).
  GAP       the live model's own arithmetic (models/nba_total_luck: team_box,
            as_of_ratings, pair_ratings, project_ratings), with luck removed
            from both the offence and the defence (rating_variants, project).
            gap_total, gap_margin, and each team's part of gap_total.
  CELLS     48: full-game total (over, under) and spread (home, away) at A and
            C, gap >= 1 / 2 / 3 / 4 (32); home and away team total (over, under)
            at the per-game purchase D, the team's part >= 1 / 2 / 3 / 4 (16).
            Both teams need 10+ games. Best deciding offer under the market's
            fair line; the gap is the cut.
  BAD ROWS  drop_impossible (40+ points from the game's stored median) and
            drop_off_market (a deciding book's full-game number 5+ points from
            the deciding median at the decision).
  PLACEBO   200 runs, seeds 1-200: the gap moved between games on the same date
            in the same market (H.shuffle_within_date), every game with a gap
            and an offer; each game keeps its prices and result.
  CONTROLS  control_SL_shipped / _added / _against / _for, same cells, no
            placebo, never judged.
  TIMING    --full prints a progress line per group and per placebo pass.

    python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_shotluck --pull
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -W ignore -m scripts.nba_s_shotluck --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets NBA_RESEARCH_CACHE=<cache> \
        PYTHONPATH=. python -W ignore -m scripts.nba_s_shotluck --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
    PYTHONPATH=. python -W ignore -m scripts.nba_s_shotluck --report <folder>

--smoke runs the synthetic checks, then prints on the real cache the seasons each
group asks for and what the 95% check at D keeps (it and --full refuse if one would
drop), coverage, the extremes of every number and price, the rows each rule removes, the highest-EV
offers, the gaps, the counts each cell would bet, the overlap with the live
models, the placebo's share of different bets, and the timing. It never grades
a real bet: the timing grades real offers against SCRAMBLED final scores
(scrambled_games) and reads only the clock. --full writes
<NBA_GAME2_RESULTS>/cells_*.parquet, population_*.parquet and the per-game gaps.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from models import nba_book_numbers as NB  # noqa: E402
from models import nba_total_luck as tl  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game2_market import team_total_dist  # noqa: E402
from models.nba_team_total_luck import GAP_CUT as LIVE_TT_CUT  # noqa: E402
from scripts.nba_ingame_data import HEAVE_CLOCK_S, HEAVE_FEET  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
SHOTS_ENV = "NBA_SHOTS_CACHE"
DEFAULT_SHOTS = "C:/Users/micha/AppData/Local/Temp/nba_s/shotluck"
SHOTS_FILE, SHOT_GAMES_FILE = "nba_pbp_shots.parquet", "nba_pbp_shot_games.parquet"
MANIFEST_FILE = "nba_pbp_shots_manifest.json"

FAMILY = "SL"
CONTROLS = {"shipped": "control_SL_shipped", "added": "control_SL_added",
            "against": "control_SL_against", "for": "control_SL_for"}
CUTS = (1.0, 2.0, 3.0, 4.0)
FULL_POINTS = ("A", "C")
FULL_SIDES = {"totals": ("over", "under"), "spreads": ("home", "away")}
TT_POINT = "D"
TT_SIDES = {"team_totals_home": ("over", "under"), "team_totals_away": ("over", "under")}
TT_GRADED = (2024, 2025, 2026)                     # 2023-24 .. 2025-26
EXPECTED_CELLS = len(FULL_POINTS) * 4 * len(CUTS) + 2 * 2 * len(CUTS)
assert EXPECTED_CELLS == 48, EXPECTED_CELLS
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))

# the registered geometry (section 4): feet, basket at (25, 0)
ZONES = ("ra", "paint", "mid", "corner", "above", "heave", "ft")
RA_FEET, KEY_HALF_WIDTH, FT_LINE_Y, CORNER_Y, CORNER_DX = 4.0, 8.0, 13.75, 9.0, 20.0
MIN_ZONE_ATT = 200
ATT, PTS, OATT, RATE = ([f"{p}_{z}" for z in ZONES] for p in ("att", "pz", "oatt", "rate"))

# section 6's impossible numbers
IMPOSSIBLE_GAP, OFF_MARKET_GAP = 40.0, 5.0
LIVE_OVER_CUT = tl.GAP_CUT                           # the live over's cut; the team-total's is imported above

_T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _T0:7.0f}s] {msg}", flush=True)


# ── the pull: a cache of Supabase, read once ────────────────────────────────

PULL_CHUNK, PULL_PAUSE_S, PULL_MAX_ACTIVE = 40, 0.15, 12
QUIET_UTC = ((10, 0), (10, 45))                    # the 6am pipeline's read window: never touched
SHOT_SQL = ("SELECT espn_game_id, play_no, period, clock_s, team_side, shot_value, points, coord_x, coord_y, "
            "substring(text from '([0-9]+)-foot')::int AS feet_text FROM nba_pbp "
            "WHERE espn_game_id = ANY(%s) AND shot_value IS NOT NULL")
LEDGER_SQL = ("SELECT espn_game_id, game_id, season, season_type, game_date, home_team, away_team, in_games, "
              "sides_swapped, n_plays, espn_home_final, espn_away_final, pbp_home_pts, pbp_away_pts, "
              "points_mismatch, source FROM nba_pbp_games WHERE season_type = 2 AND in_games ORDER BY espn_game_id")


def _frame(conn, sql, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    raw = getattr(cur, "_cur", cur)
    return pd.DataFrame(rows, columns=[d[0] for d in raw.description])


def _active(conn) -> int:
    return int(conn.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'").fetchone()[0])


def pull(out: Path, limit: int | None = None) -> dict:
    """Every regular-season shot row of nba_pbp, read-only, by primary key, in
    chunks, into `out`. Waits out the 6am read window and a busy database."""
    from data.db import get_connection
    out.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    log(f"active queries at start: {_active(conn)}")
    led = _frame(conn, LEDGER_SQL)
    ids = [int(x) for x in led["espn_game_id"]]
    if limit:
        ids = ids[:limit]
        led = led[led["espn_game_id"].isin(ids)]
    log(f"games {len(led)} {led.groupby('season').size().to_dict()}")
    parts = []
    for i in range(0, len(ids), PULL_CHUNK):
        now = datetime.now(timezone.utc)
        while QUIET_UTC[0] <= (now.hour, now.minute) < QUIET_UTC[1]:
            log("the 6am read window: waiting")
            time.sleep(120)
            now = datetime.now(timezone.utc)
        if i and (i // PULL_CHUNK) % 25 == 0:
            n = _active(conn)
            while n > PULL_MAX_ACTIVE:
                log(f"{n} active queries: waiting 30 s")
                time.sleep(30)
                n = _active(conn)
            log(f"{i:,}/{len(ids):,} games, {sum(map(len, parts)):,} rows, {n} active")
        parts.append(_frame(conn, SHOT_SQL, (ids[i:i + PULL_CHUNK],)))
        time.sleep(PULL_PAUSE_S)
    conn.close()
    shots = pd.concat(parts, ignore_index=True).astype(
        {"espn_game_id": "int64", "play_no": "int32", "period": "int16", "clock_s": "float32",
         "shot_value": "int8", "points": "int8", "coord_x": "float32", "coord_y": "float32"})
    shots.to_parquet(out / SHOTS_FILE)
    led.to_parquet(out / SHOT_GAMES_FILE)
    man = {"pulled_at": datetime.now(timezone.utc).isoformat(), "rows": int(len(shots)), "games": len(ids),
           "by_season_games": {str(k): int(v) for k, v in led.groupby("season").size().items()}}
    (out / MANIFEST_FILE).write_text(json.dumps(man), encoding="utf-8")
    log(f"done: {man}")
    return man


def shots_dir() -> Path:
    return Path(os.environ.get(SHOTS_ENV, DEFAULT_SHOTS))


def load_shots(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [f for f in (SHOTS_FILE, SHOT_GAMES_FILE) if not (folder / f).exists()]
    if missing:
        raise RuntimeError(f"{folder} has no {missing}: run --pull (it reads Supabase once, read-only)")
    return pd.read_parquet(folder / SHOTS_FILE), pd.read_parquet(folder / SHOT_GAMES_FILE)


# ── zones and the team-game table ───────────────────────────────────────────

def zone_of(value, x, y, clock_s, feet_text) -> np.ndarray:
    """The zone of each shot (section 4). The stored value decides two, three or
    free throw; the location only splits within it. A shot with no location is
    mid-range (a two) or above the break (a three). A heave is a three with
    HEAVE_CLOCK_S or less on the clock and HEAVE_FEET or more from the basket,
    by the text's distance else the coordinates, made or missed."""
    v = np.asarray(value, float)
    x, y = np.asarray(x, float), np.asarray(y, float)
    clock = np.asarray(clock_s, float)
    feet_txt = pd.to_numeric(pd.Series(feet_text), errors="coerce").astype(float).to_numpy()
    with np.errstate(invalid="ignore"):
        dx = np.abs(x - 25.0)
        d = np.hypot(dx, y)
        feet = np.where(np.isfinite(feet_txt), feet_txt, d)
        heave = (v == 3) & (clock <= HEAVE_CLOCK_S) & (feet >= HEAVE_FEET)
        ra = (v == 2) & (d <= RA_FEET)
        paint = (v == 2) & (dx <= KEY_HALF_WIDTH) & (y <= FT_LINE_Y)
        corner = (v == 3) & (y <= CORNER_Y) & (dx >= CORNER_DX)
    return np.select([v == 1, ra, paint, v == 2, heave, corner, v == 3],
                     ["ft", "ra", "paint", "mid", "heave", "corner", "above"], default="none")


def team_game_zones(shots: pd.DataFrame, ledger: pd.DataFrame, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(tz, untrusted). tz: one row per (game, team) in `games`: attempts per
    zone (att_*), points per zone (pz_*), points from shots, and the opponent's
    attempts (oatt_*) and points. `team_side` H is the home team of our games
    row (the ingestor flips swapped sides). untrusted: the games left out because
    the plays do not add up to the stored final for either team (or a side is
    missing), and games with no plays at all, with the season."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team", "home_score", "away_score"]]
    s = shots.merge(ledger[["espn_game_id", "game_id"]], on="espn_game_id")
    s = s[s["game_id"].isin(set(g["game_id"])) & s["team_side"].isin(["H", "A"])]
    z = zone_of(s["shot_value"], s["coord_x"], s["coord_y"], s["clock_s"], s["feet_text"])
    if (z == "none").any():
        raise ValueError(f"{int((z == 'none').sum())} shot rows with a value that is not 1, 2 or 3")
    s = s.assign(zone=z, points=s["points"].astype("int64"))
    by = s.groupby(["game_id", "team_side", "zone"]).agg(a=("points", "size"), p=("points", "sum")).unstack(
        "zone", fill_value=0)
    att = by["a"].reindex(columns=list(ZONES), fill_value=0).add_prefix("att_")
    pts = by["p"].reindex(columns=list(ZONES), fill_value=0).add_prefix("pz_")
    w = pd.concat([att, pts], axis=1).reset_index()
    w["pts_shots"] = w[PTS].sum(axis=1)
    w = w.merge(g, on="game_id")
    home = (w["team_side"] == "H").to_numpy()
    w["team"] = np.where(home, w["home_team"], w["away_team"])
    w["opp"] = np.where(home, w["away_team"], w["home_team"])
    final = np.where(home, w["home_score"], w["away_score"])
    sides = w.groupby("game_id")["team_side"].transform("nunique").to_numpy()
    off = (w["pts_shots"].to_numpy(float) != np.asarray(final, float)) | (sides != 2)
    bad = set(w.loc[off, "game_id"])
    none = set(g["game_id"]) - set(w["game_id"])
    why = {**{i: "plays_do_not_add_up" for i in bad}, **{i: "no_plays" for i in none}}
    untrusted = g[g["game_id"].isin(set(why))][["game_id", "season"]].assign(
        why=lambda d: d["game_id"].map(why)).reset_index(drop=True)
    keep = w[~w["game_id"].isin(bad)]
    opp = keep[["game_id", "team", *ATT, "pts_shots"]].rename(
        columns={"team": "opp", "pts_shots": "opts_shots", **{f"att_{z}": f"oatt_{z}" for z in ZONES}})
    tz = keep.merge(opp, on=["game_id", "opp"])
    cols = ["game_id", "season", "game_date", "team", "opp", *ATT, *PTS, "pts_shots", *OATT, "opts_shots"]
    return tz[cols].reset_index(drop=True), untrusted


def league_rates(tz: pd.DataFrame, targets: pd.DataFrame, min_att: int = MIN_ZONE_ATT) -> pd.DataFrame:
    """(season, game_date, rate_*): points per attempt per zone over the season's
    games strictly before the date; a zone with fewer than `min_att` attempts so
    far reads last season's whole-season rate, when there is one."""
    lg = tz.groupby(["season", "game_date"], as_index=False)[ATT + PTS].sum().sort_values(["season", "game_date"])
    whole = tz.groupby("season")[ATT + PTS].sum()
    cum = lg.copy()
    cum[ATT + PTS] = lg.groupby("season")[ATT + PTS].cumsum()
    t = targets[["season", "game_date"]].drop_duplicates()
    x = tl._before(t, cum, ["season"])
    x[ATT + PTS] = x[ATT + PTS].fillna(0.0)
    last_season = x["season"].astype(int).to_numpy() - 1
    out = x[["season", "game_date"]].copy()
    for z in ZONES:
        a, p = x[f"att_{z}"].to_numpy(float), x[f"pz_{z}"].to_numpy(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            own = p / a
        by_season = (whole[f"pz_{z}"] / whole[f"att_{z}"]).to_dict()      # built once per zone
        prior = np.array([by_season.get(s, np.nan) for s in last_season], float)
        out[f"rate_{z}"] = np.where(a >= min_att, own, np.where(np.isfinite(prior), prior, own))
    out[RATE] = out[RATE].fillna(0.0)
    return out.reset_index(drop=True)


def as_of_luck(tz: pd.DataFrame, targets: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    """(season, team, game_date, luck_for, luck_against) from that team's games of
    the same season strictly before the date, at the zone rates on the date."""
    cols = ATT + OATT + ["pts_shots", "opts_shots"]
    team = tz.groupby(["season", "team", "game_date"], as_index=False)[cols].sum().sort_values(
        ["season", "team", "game_date"])
    team[cols] = team.groupby(["season", "team"])[cols].cumsum()
    x = tl._before(targets[["season", "team", "game_date"]], team, ["season", "team"])
    x[cols] = x[cols].fillna(0.0)
    x = x.merge(rates, on=["season", "game_date"], how="left")
    r = x[RATE].to_numpy(float)
    x["luck_for"] = x["pts_shots"].to_numpy(float) - (x[ATT].to_numpy(float) * r).sum(axis=1)
    x["luck_against"] = x["opts_shots"].to_numpy(float) - (x[OATT].to_numpy(float) * r).sum(axis=1)
    return x[["season", "team", "game_date", "luck_for", "luck_against"]]


def rating_variants(tb: pd.DataFrame, tz: pd.DataFrame, targets: pd.DataFrame, rates: pd.DataFrame) -> dict:
    """{name: ratings shaped like tl.as_of_ratings}: 'zone' (offence and defence
    luck removed, the registered gap), 'against' (defence only), 'for' (offence
    only), 'shipped' (the live models' own). Raw ratings, pace and the league
    rating are the live model's in every one."""
    base = tl.as_of_ratings(tb, targets)
    x = base.merge(as_of_luck(tz, targets, rates), on=["season", "team", "game_date"], how="left")
    poss = (x["pace"] * x["n"]).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        d_for = -100.0 * x["luck_for"].to_numpy(float) / poss
        d_ag = -100.0 * x["luck_against"].to_numpy(float) / poss
    keep = list(base.columns)
    ortg, drtg = x["ortg_raw"].to_numpy(float), x["drtg_raw"].to_numpy(float)

    def make(o, d):
        r = x[keep].copy()
        r["ortg_adj"], r["drtg_adj"] = o, d
        return r
    return {"shipped": base, "zone": make(ortg + d_for, drtg + d_ag),
            "against": make(ortg, drtg + d_ag), "for": make(ortg + d_for, drtg)}


def project(games: pd.DataFrame, ratings: pd.DataFrame) -> pd.DataFrame:
    """Per game with both teams at 10+ games: the live model's raw and adjusted
    numbers, gap_margin, gap_total, and each team's part of gap_total, in that
    team's points."""
    x = tl.pair_ratings(games, ratings)
    x = x[(x["h_n"] >= tl.MIN_GAMES) & (x["a_n"] >= tl.MIN_GAMES)]
    p = tl.project_ratings(x)
    pace = 0.5 * (p["h_pace"] + p["a_pace"]) / 100.0
    p["part_home"] = pace * ((p["h_ortg_adj"] - p["h_ortg_raw"]) + (p["a_drtg_adj"] - p["a_drtg_raw"]))
    p["part_away"] = pace * ((p["a_ortg_adj"] - p["a_ortg_raw"]) + (p["h_drtg_adj"] - p["h_drtg_raw"]))
    return p


def signal_of(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, season, market, strength) toward side A: home for a spread, over
    for a total or team total."""
    parts = [proj[["game_id", "season"]].assign(market=m, strength=proj[c].to_numpy(float))
             for m, c in (("totals", "gap_total"), ("spreads", "gap_margin"),
                          ("team_totals_home", "part_home"), ("team_totals_away", "part_away"))]
    s = pd.concat(parts, ignore_index=True)
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


def added_signal(zone: pd.DataFrame, shipped: pd.DataFrame, min_prior: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(signal, betas): what the new gap adds after removing the shipped gap: per
    market and season S, new - b x shipped, b by least squares through the origin
    on the seasons before S. A season with under `min_prior` earlier rows gets no
    number. No result enters b."""
    m = zone.merge(shipped[["game_id", "market", "strength"]], on=["game_id", "market"], suffixes=("", "_shipped"))
    out, betas = [], []
    for market, g in m.groupby("market", sort=False):
        for S in sorted(int(v) for v in g["season"].unique()):
            prior = g[g["season"].astype(int) < S]
            if len(prior) < min_prior:
                continue
            x, y = prior["strength_shipped"].to_numpy(float), prior["strength"].to_numpy(float)
            b = float((x * y).sum() / (x * x).sum())
            cur = g[g["season"].astype(int) == S]
            out.append(cur[["game_id", "season", "market"]].assign(
                strength=cur["strength"].to_numpy(float) - b * cur["strength_shipped"].to_numpy(float)))
            betas.append({"market": market, "season": S, "b": b, "rows_before": int(len(prior))})
    return pd.concat(out, ignore_index=True), pd.DataFrame(betas)


# ── impossible numbers (section 6) ──────────────────────────────────────────

def drop_impossible(q: pd.DataFrame, gap: float = IMPOSSIBLE_GAP) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(kept, removed): a number `gap` or more points from the median of the game's
    stored numbers in that market is not that market (record 10.8)."""
    has = q["line"].notna().to_numpy()
    med = q.loc[has].groupby(["game_id", "market"])["line"].transform("median").to_numpy(float)
    far = np.zeros(len(q), bool)
    far[has] = np.abs(q.loc[has, "line"].to_numpy(float) - med) >= gap
    return q[~far].reset_index(drop=True), q[far].reset_index(drop=True)


def drop_off_market(vis: pd.DataFrame, gap: float = OFF_MARKET_GAP) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(kept, removed): at a decision, a deciding book's full-game spread or total
    `gap` or more points from the median of the deciding books' coherent numbers.
    Pinnacle and every other non-deciding book are never removed."""
    deciding = vis["book"].isin(H.BETTABLE).to_numpy() & vis["market"].isin(list(FULL_SIDES)).to_numpy()
    m = vis[deciding & vis["coherent"].to_numpy(bool)]
    med = m.groupby(["game_id", "market"])["line"].median().rename("_med").reset_index()
    x = vis[["game_id", "market"]].merge(med, on=["game_id", "market"], how="left")
    far = deciding & (np.abs(vis["line"].to_numpy(float) - x["_med"].to_numpy(float)) >= gap)
    return vis[~far].reset_index(drop=True), vis[far].reset_index(drop=True)


# ── offers at each decision ─────────────────────────────────────────────────

def full_offers(data: H.Data, point: str, sig: dict) -> dict:
    """Times, visible quotes, the off-market rows removed, and every full-game offer
    priced at the market's fair line, at one decision point (F4's frames, with
    section 6's rule applied before the fair line and the offers read them)."""
    t = H.decision_times(data.fetches, data.games, point)
    vis, removed = drop_off_market(H.visible(data.quotes, t))
    neutral = H.fair_offers(H.offers(vis), H.market_fair(vis, sig))
    return {"times": t, "vis": vis, "removed": removed,
            "neutral": neutral[neutral["market"].isin(list(FULL_SIDES))].reset_index(drop=True)}


def assemble(data: H.Data, all_games: pd.DataFrame, games_p: pd.DataFrame, pe: pd.DataFrame, graded, tb: pd.DataFrame,
             shots: pd.DataFrame, ledger: pd.DataFrame, min_prior: int = P3.MIN_PRIOR_GAMES) -> dict:
    """Every frame the cells read, real or synthetic. No result of a bet is read:
    the pricing tables read seasons before S, as every lab's do."""
    raw_q = data.quotes[data.quotes["market"].isin(list(FULL_SIDES))].reset_index(drop=True)
    q, removed_full = drop_impossible(raw_q)
    dat = H.Data(games=data.games, quotes=q, fetches=data.fetches, notes=data.notes)
    close = H.pinnacle_close(dat)
    sig = H.close_dist(close, dat.games)
    log("pricing tables built")
    at = {p: full_offers(dat, p, sig) for p in FULL_POINTS}
    log(f"full-game offers built: { {p: len(v['neutral']) for p, v in at.items()} }")
    raw_pe = pe[pe["market"].isin(list(TT_SIDES))].reset_index(drop=True)
    pe2, removed_tt = drop_impossible(raw_pe)
    # every per-game purchase, not only those holding team totals: the 95% check at D reads
    # these times, and 2023-24 has team totals on 1,138 of 1,230 games (section 5's dated line)
    times_d = H.per_event_times(pe, TT_POINT)
    vis_d = NB.visible_numbers(pe2, times_d)
    gp_full = games_p[games_p["season"].isin(data.games["season"])]
    # F6d's team-total table, which P3.market_pricing also returns; its period tables are not read here
    pricing = {k: v for k, v in team_total_dist(close, gp_full, min_games=min_prior).items()
               if int(k[0]) in {int(s) for s in graded}}
    P3.require_pricing(pricing, graded, tuple(TT_SIDES), "the market's own pricing")
    neutral_d = P3.neutral_offers(vis_d, pricing)
    dd = P3.derivative_data(gp_full[gp_full["season"].isin(graded)], pe2)
    log(f"team-total offers built: {len(neutral_d)}")
    tz, untrusted = team_game_zones(shots, ledger, all_games)
    targets = tl.team_targets(all_games)
    rates = league_rates(tz, targets)
    variants = rating_variants(tb, tz, targets, rates)
    proj = {k: project(all_games, r) for k, r in variants.items()}
    signals = {k: signal_of(p) for k, p in proj.items()}
    signals["added"], betas = added_signal(signals["zone"], signals["shipped"])
    log(f"gaps built: { {k: len(v) for k, v in proj.items()} }")
    return {"data": dat, "dd": dd, "close": close, "sig": sig, "at": at, "raw_q": raw_q, "raw_pe": raw_pe,
            "removed_full": removed_full, "removed_tt": removed_tt, "times_d": times_d, "vis_d": vis_d,
            "neutral_d": neutral_d, "tz": tz, "untrusted": untrusted, "rates": rates, "proj": proj,
            "signals": signals, "betas": betas, "graded": tuple(graded), "choose_tt": P3.choosing(graded)}


def groups(prep: dict):
    """(point, market, sides, neutral, data, choose_seasons, times, close, sig): the
    six groups of cells, each decision and market once."""
    for point in FULL_POINTS:
        for market, sides in FULL_SIDES.items():
            yield (point, market, sides, prep["at"][point]["neutral"], prep["data"], H.CHOOSE, None,
                   prep["close"], prep["sig"])
    for market, sides in TT_SIDES.items():
        yield (TT_POINT, market, sides, prep["neutral_d"], prep["dd"], prep["choose_tt"], prep["times_d"],
               None, None)


def group_frames(neutral: pd.DataFrame, signal: pd.DataFrame, market: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(nm, s, cand): the market's offers on games with a number, the numbers on
    games with an offer, and the offers carrying the number toward their side."""
    s_all = signal[signal["market"] == market]
    nm = neutral[(neutral["market"] == market) & neutral["game_id"].isin(set(s_all["game_id"]))].reset_index(drop=True)
    s = s_all[s_all["game_id"].isin(set(nm["game_id"]))].reset_index(drop=True)
    return nm, s, tl.side_strength(nm, s)


BEST_COLS = ["game_id", "season", "game_date", "T", "market", "side", "book", "line", "price", "ev", "p_win", "p_push"]


def best_offers(nm: pd.DataFrame, sides) -> pd.DataFrame:
    """One row per (game, side): the offer H.choose takes on that side. Prices never
    move and every offer on a side carries the same number, so at ANY cut and under ANY
    shuffle the cell's choice among these rows is its choice among all of them. The
    placebo runs and the bands read this frame, about an eighth of the size of the
    offers: it is what keeps 200 runs over 48 cells inside the time limit (lesson 1 of
    this week: build once, never look up per key)."""
    parts = [H.choose(nm, -np.inf, sides=[s]) for s in sides]
    b = pd.concat(parts, ignore_index=True)
    return b[[c for c in BEST_COLS if c in b]]


def run_group(dat: H.Data, family: str, point: str, market: str, sides, cand: pd.DataFrame, nm: pd.DataFrame,
              best: pd.DataFrame, signal: pd.DataFrame, placebo, choose, times, close, sig,
              extra: dict | None = None) -> list[dict]:
    """One decision and market through H.run_cells, each row with its bands (G5's
    arithmetic). The bands read `best`: the same bets, far fewer rows."""
    rows = H.run_cells(dat, family, point, cand, nm, list(CUTS), {market: list(sides)}, close=close, sig=sig,
                       placebo=placebo, strength="strength", choose_seasons=choose, times=times)
    best_cand = tl.side_strength(best, signal)
    for r in rows:
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(G5.band_columns(best_cand, r["side"], "strength", G5.band_bounds(CUTS, r["cut_index"]), dat.games, pool))
        r.update(extra or {})
    return rows


class ProgressFrames(G5.LazyFrames):
    """Placebo frames built on demand, printing a line after each pass."""

    def __init__(self, items, build, label: str):
        super().__init__(items, build)
        self.label, self.passes = label, 0

    def __iter__(self):
        t = time.time()
        for f in super().__iter__():
            yield f
        self.passes += 1
        log(f"{self.label}: placebo pass {self.passes} ({len(self.items)} runs) in {time.time() - t:.0f}s")


def emit(prep: dict, name: str, family: str, seeds=(), progress: bool = False, only=None) -> tuple[list[dict], list[pd.DataFrame]]:
    """One family's 48 rows through H.run_cells (G5.run_market adds the bands), and
    its population counts. `only`: {(point, market)}, the synthetic checks' subset."""
    rows, pops = [], []
    signal = prep["signals"][name]
    for point, market, sides, neutral, dat, choose, times, close, sig in groups(prep):
        if only is not None and (point, market) not in only:
            continue
        t0 = time.time()
        nm, s, cand = group_frames(neutral, signal, market)
        best = best_offers(nm, sides)
        lazy = None
        if len(seeds):
            label = f"{family} {point} {market}"
            shuffles = G5.gap_shuffles(s, dat.games, seeds)
            build = lambda sh, best=best: tl.side_strength(best, sh)  # noqa: E731
            lazy = (ProgressFrames(shuffles, build, label) if progress else G5.LazyFrames(shuffles, build))
        # the group's own market's quotes: next_fetch_check reads no other
        one_market = H.Data(games=dat.games, quotes=dat.quotes[dat.quotes["market"] == market], fetches=dat.fetches)
        got = run_group(one_market, family, point, market, sides, cand, nm, best, s, lazy, choose, times, close, sig,
                        extra={"signal_meaning": f"{name}: expected points by shot zone"})
        rows += got
        if point == TT_POINT:
            off = H.offers(prep["vis_d"])
            pops.append(P3.population(family, got, dat, times, off, cand, "strength", prep["graded"]))
        else:
            pops.append(L.population(dat.games, point, neutral[neutral["market"] == market],
                                     s[["game_id", "market", "strength"]], got).assign(family=family))
        if progress:
            log(f"{family} {point} {market}: {len(got)} cells in {time.time() - t0:.0f}s")
    assert only is not None or len(rows) == EXPECTED_CELLS, (family, len(rows))
    return rows, pops


# ── the seasons each group is judged on ─────────────────────────────────────

def _seasons_text(seasons) -> str:
    return ",".join(str(int(s)) for s in seasons)


def season_gate(prep: dict) -> pd.DataFrame:
    """Per group: the seasons it asks to choose on, each season's coverage, and what the
    95% check keeps and drops, through the same objects emit hands H.run_cells. A drop
    there is silent: the row records it, and the cell is judged on fewer seasons."""
    out = []
    for point, market, _sides, _n, dat, choose, times, _c, _s in groups(prep):
        cov = H.point_coverage(dat, point, times)
        kept, dropped = H.gated_seasons(cov, choose, point)
        out.append({"point": point, "market": market, "asked": _seasons_text(choose), "kept": _seasons_text(kept),
                    "dropped": _seasons_text(dropped), **{f"cov_{s}": v for s, v in sorted(cov.items())}})
    return pd.DataFrame(out)


def gate_refusals(gate: pd.DataFrame) -> list[str]:
    """A cell is judged on the seasons section 5 registers, or the run does not start."""
    return [f"{r['point']} {r['market']}: asks to choose on {r['asked']}, the 95% check drops {r['dropped']}; "
            "its cells would be judged on other seasons than section 5 registers"
            for _, r in gate[gate["dropped"] != ""].iterrows()]


def require_registered_seasons(prep: dict) -> pd.DataFrame:
    """Prints what season_gate read, then stops --smoke or --full if a season would drop."""
    gate = season_gate(prep)
    print("THE SEASONS EACH GROUP CHOOSES ON, AND WHAT THE 95% CHECK KEEPS:\n", gate.round(4).to_string(index=False), flush=True)
    why = gate_refusals(gate)
    if why:
        P.refuse(why)
    return gate


def team_total_reach(prep: dict) -> pd.DataFrame:
    """Per graded season: games, games with any team-total row, games with a decision
    time, the same if only the purchases holding team totals counted, and how many
    decision times differ between the two. Counts only."""
    from_rows = H.per_event_times(prep["raw_pe"], TT_POINT)
    both = prep["times_d"].merge(from_rows, on="game_id", suffixes=("", "_rows"))
    games = prep["dd"].games
    out = []
    for s, ids in games.groupby(games["season"].astype(int))["game_id"]:
        ids = set(ids)
        shared = both[both["game_id"].isin(ids)]
        out.append({"season": s, "games": len(ids), "team_total_games": int(prep["raw_pe"].loc[prep["raw_pe"]["game_id"].isin(ids), "game_id"].nunique()),
                    "decision_games": int(prep["times_d"]["game_id"].isin(ids).sum()),
                    "decision_games_counting_team_total_purchases_only": int(from_rows["game_id"].isin(ids).sum()),
                    "decision_times_that_differ": int((shared["T"] != shared["T_rows"]).sum())})
    return pd.DataFrame(out)


# ── what is counted before grading (nothing here reads a result) ────────────

def cell_list():
    for point in FULL_POINTS:
        for market, sides in FULL_SIDES.items():
            for side in sides:
                for cut in CUTS:
                    yield point, market, side, cut
    for market, sides in TT_SIDES.items():
        for side in sides:
            for cut in CUTS:
                yield TT_POINT, market, side, cut


def _pick(cand: pd.DataFrame, cut: float, side: str) -> pd.DataFrame:
    return H.choose(cand[cand["strength"] >= cut], -np.inf, sides=[side])


def counts(prep: dict) -> pd.DataFrame:
    """Per cell and season, the games it would bet with a deciding offer at or
    above the floor."""
    out = []
    for point, market, sides, neutral, dat, choose, _t, _c, _s in groups(prep):
        _, _, cand = group_frames(neutral, prep["signals"]["zone"], market)
        season = dat.games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)
        pool = tuple(choose) + (H.CONFIRM,)
        for side in sides:
            for cut in CUTS:
                b = _pick(cand, cut, side)
                by = season.reindex(b["game_id"]).value_counts().to_dict()
                out.append({"point": point, "market": market, "side": side, "cut": cut,
                            **{f"bets_{s}": int(by.get(s, 0)) for s in (H.REGIME, *H.CHOOSE, H.CONFIRM)},
                            "bets_pooled": int(sum(by.get(s, 0) for s in pool))})
    return pd.DataFrame(out)


def live_bets(prep: dict) -> tuple[set, set]:
    """(same-bet keys, games) of the two live models, rebuilt by the harness from
    the shipped gap: the full-game over at C at gap >= 3, the home team-total
    under at D at the home part <= -2."""
    shipped = prep["signals"]["shipped"]
    _, _, c1 = group_frames(prep["at"]["C"]["neutral"], shipped, "totals")
    _, _, c2 = group_frames(prep["neutral_d"], shipped, "team_totals_home")
    b = pd.concat([_pick(c1, LIVE_OVER_CUT, "over"), _pick(c2, LIVE_TT_CUT, "under")], ignore_index=True)
    return set(zip(b["game_id"], b["market"], b["side"])), set(b["game_id"])


def overlap(prep: dict) -> pd.DataFrame:
    """Per cell, the share of its bets the live models make too: the same bet (game,
    market, side), and the same game. Counted, never graded."""
    same_bet, same_game = live_bets(prep)
    out = []
    for point, market, sides, neutral, _d, _ch, _t, _c, _s in groups(prep):
        _, _, cand = group_frames(neutral, prep["signals"]["zone"], market)
        for side in sides:
            for cut in CUTS:
                b = _pick(cand, cut, side)
                n = len(b)
                keys = zip(b["game_id"], b["market"], b["side"])
                a = sum(k in same_bet for k in keys)
                g = int(b["game_id"].isin(same_game).sum())
                out.append({"point": point, "market": market, "side": side, "cut": cut, "bets": n,
                            "same_bet": a, "share_same_bet": a / n if n else np.nan,
                            "same_game": g, "share_same_game": g / n if n else np.nan})
    return pd.DataFrame(out)


def share_different_at_random(fired_by_date: pd.Series, games_by_date: pd.Series) -> float:
    """What a perfect within-date shuffle gives. If k of a date's N games fire for real,
    a shuffled gap lands on one of the k with chance k/N, whatever the shuffle does; so
    this share is the most any within-date placebo can differ from a cell that broad."""
    k = fired_by_date.to_numpy(float)
    if not k.sum():
        return float("nan")
    n = games_by_date.reindex(fired_by_date.index).to_numpy(float)
    return 1.0 - float((k * k / n).sum() / k.sum())


def placebo_null(prep: dict, seeds=tuple(range(1, 21))) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per cell, per decision): the share of placebo bets that are not the real
    cell's bets, by the harness's own shuffle, what a perfect shuffle would give, and
    how crowded the dates are."""
    cells, dates = [], []
    for point, market, sides, neutral, dat, _ch, _t, _c, _s in groups(prep):
        nm, s, cand = group_frames(neutral, prep["signals"]["zone"], market)
        by_date = s.merge(dat.games[["game_id", "game_date"]], on="game_id").groupby("game_date").size()
        by_date_ids = set(s["game_id"])
        date_of = dict(zip(dat.games["game_id"], dat.games["game_date"]))
        dates.append({"point": point, "market": market, "games": int(by_date.sum()), "dates": int(len(by_date)),
                      "games_per_date": float(by_date.mean()),
                      "share_alone_on_their_date": float(by_date[by_date == 1].sum() / by_date.sum())})
        best = best_offers(nm, sides)
        frames = [tl.side_strength(best, sh) for sh in G5.gap_shuffles(s, dat.games, seeds)]
        for side in sides:
            for cut in CUTS:
                real = _pick(cand, cut, side)
                real_keys = set(real["game_id"])
                n = same = 0
                for f in frames:
                    b = _pick(f, cut, side)
                    n += len(b)
                    same += int(b["game_id"].isin(real_keys).sum())
                # the base rate: a shuffled gap lands on a firing game this often even if it moves every time
                fired = len(real) / max(len(by_date_ids), 1)
                cells.append({"point": point, "market": market, "side": side, "cut": cut, "real_bets": len(real),
                              "placebo_bets": n, "placebo_same": same,
                              "share_different": 1.0 - same / n if n else np.nan,
                              "share_different_at_random": share_different_at_random(
                                  real["game_id"].map(date_of).value_counts(), by_date),
                              "share_of_games_firing": fired})
    return pd.DataFrame(cells), pd.DataFrame(dates)


def scrambled_games(games: pd.DataFrame, seed: int = 20261030) -> pd.DataFrame:
    """Copies of the games with invented final scores and no period scores: the
    timing below runs the whole grading path on these, so no real result is read."""
    rng = np.random.default_rng(seed)
    g = games.drop(columns=[c for c in H.PERIOD_COLS if c in games])
    return g.assign(home_score=rng.integers(90, 131, len(g)).astype(float),
                    away_score=rng.integers(90, 131, len(g)).astype(float))


def timing(prep: dict, setup_seconds: float = 0.0, n_seeds: int = 5) -> dict:
    """The clock on one placebo run and one group's cells, on the REAL offers against
    SCRAMBLED final scores, and the projected --full time. Nothing here reads a result."""
    measured = {("A", "totals"), ("C", "spreads"), (TT_POINT, "team_totals_home")}
    by = {}
    saved = os.environ.pop(BETS_ENV, None)                   # never write a bet graded on invented scores
    for point, market, sides, neutral, dat, choose, times, close, sig in groups(prep):
        if (point, market) not in measured:
            continue
        fake = H.Data(games=scrambled_games(dat.games), quotes=dat.quotes[dat.quotes["market"] == market],
                      fetches=dat.fetches, notes=dat.notes)
        nm, s, cand = group_frames(neutral, prep["signals"]["zone"], market)
        best = best_offers(nm, sides)
        t = time.time()
        shuffles = G5.gap_shuffles(s, dat.games, PLACEBO_SEEDS[:n_seeds])
        per_shuffle = (time.time() - t) / n_seeds
        t = time.time()
        for sh in shuffles:                                  # exactly run_cells' placebo loop
            for side in sides:
                for cut in CUTS:
                    f = tl.side_strength(best, sh)
                    gp = H.grade(_pick(f[f["market"].isin([market])], cut, side), fake.games)
                    H.roi(gp[gp["season"].isin(choose)])
        per_run = (time.time() - t) / n_seeds                # one placebo run across the group's 8 cells
        t = time.time()
        run_group(fake, FAMILY, point, market, sides, cand, nm, best, s, None, choose, times, close, sig)
        per_group_no_placebo = time.time() - t
        by[point] = {"market": market, "offers": int(len(nm)), "best_offers": int(len(best)),
                     "seconds_per_shuffle": per_shuffle, "seconds_per_placebo_run_8_cells": per_run,
                     "seconds_8_cells_no_placebo": per_group_no_placebo}
        log(f"timed {point} {market}: {by[point]}")
    if saved is not None:
        os.environ[BETS_ENV] = saved
    # two markets at each decision, each measured on one of the two
    reg = sum(2 * (v["seconds_8_cells_no_placebo"]
                   + N_PLACEBO * (v["seconds_per_shuffle"] + v["seconds_per_placebo_run_8_cells"]))
              for v in by.values())
    ctl = sum(2 * len(CONTROLS) * v["seconds_8_cells_no_placebo"] for v in by.values())
    return {"by_decision": by, "registered_seconds": reg, "controls_seconds": ctl,
            "setup_seconds": setup_seconds, "projected_full_hours": (setup_seconds + reg + ctl) / 3600.0}


def peak_memory_gb() -> float:
    import psutil
    m = psutil.Process().memory_info()
    return float(getattr(m, "peak_wset", m.rss)) / 2 ** 30


# ── the report --smoke prints ───────────────────────────────────────────────

def coverage(shots: pd.DataFrame, ledger: pd.DataFrame, untrusted: pd.DataFrame) -> pd.DataFrame:
    s = shots.merge(ledger[["espn_game_id", "season"]], on="espn_game_id")
    fg = s[s["shot_value"].isin([2, 3])]
    out = pd.DataFrame({"games": ledger.groupby("season").size(),
                        "field_goals": fg.groupby("season").size(),
                        "with_coordinates": fg[fg["coord_x"].notna() & fg["coord_y"].notna()].groupby("season").size(),
                        "free_throws": s[s["shot_value"] == 1].groupby("season").size(),
                        "ft_with_coordinates": s[(s["shot_value"] == 1) & s["coord_x"].notna()].groupby("season").size(),
                        "rows_without_a_side": s[~s["team_side"].isin(["H", "A"])].groupby("season").size(),
                        "games_left_out": untrusted.groupby("season").size()}).fillna(0).astype(int)
    out["share_with_coordinates"] = (out["with_coordinates"] / out["field_goals"]).round(5)
    return out


def zone_table(tz: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = tz.groupby("season")[ATT + PTS].sum()
    n = tz.groupby("season").size()
    a = pd.DataFrame({z: t[f"att_{z}"] / n for z in ZONES})
    p = pd.DataFrame({z: t[f"pz_{z}"] / t[f"att_{z}"] for z in ZONES})
    return a.round(2), p.round(3)


def gap_table(prep: dict) -> pd.DataFrame:
    """Per season: the gaps' centre and spread, the share of games past each cut on the
    positive and negative side, and how closely the new gap follows the shipped one."""
    z, sh = prep["proj"]["zone"], prep["proj"]["shipped"]
    m = z.merge(sh[["game_id", "gap_total", "gap_margin", "part_home", "part_away"]], on="game_id", suffixes=("", "_sh"))
    rows = []
    for season, g in m.groupby("season"):
        for c in ("gap_total", "gap_margin", "part_home", "part_away"):
            v = g[c].to_numpy(float)
            rows.append({"season": int(season), "number": c, "games": len(v), "mean": v.mean(), "sd": v.std(),
                         **{f"ge{int(k)}": float((v >= k).mean()) for k in CUTS},
                         **{f"le_{int(k)}": float((v <= -k).mean()) for k in CUTS},
                         "corr_with_shipped": float(np.corrcoef(v, g[f"{c}_sh"].to_numpy(float))[0, 1])})
    return pd.DataFrame(rows)


def extremes(prep: dict) -> dict:
    """Section 6's printout: every number and price read, before and after the rules,
    and the highest-EV offers. Nothing here reads a result."""
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)

    def span(q):
        return q.groupby("market").agg(rows=("line", "size"), games=("game_id", "nunique"), line_min=("line", "min"),
                                       line_max=("line", "max"), a_min=("price_a", "min"), a_max=("price_a", "max"),
                                       b_min=("price_b", "min"), b_max=("price_b", "max"))
    print("STORED, before the rules:")
    print(span(pd.concat([prep["raw_q"], prep["raw_pe"]], ignore_index=True)).to_string())
    rem = prep["removed_full"]
    print(f"RULE 1 (40+ from the game's stored median): {len(rem)} full-game rows, {len(prep['removed_tt'])} team-total rows")
    if len(rem):
        print(rem[["game_id", "market", "book", "line", "price_a", "price_b", "snapshot_at"]].to_string(index=False))
    out = {"rule1_full": int(len(rem)), "rule1_team_totals": int(len(prep["removed_tt"]))}
    for p in FULL_POINTS:
        r = prep["at"][p]["removed"]
        print(f"RULE 2 at {p} (a deciding book 5+ from the deciding median): {len(r)} rows")
        if len(r):
            print(r[["game_id", "market", "book", "line", "price_a", "price_b", "snapshot_at", "T"]].to_string(index=False))
        out[f"rule2_{p}"] = int(len(r))
    frames = {**{p: prep["at"][p]["neutral"] for p in FULL_POINTS}, TT_POINT: prep["neutral_d"]}
    for p, n in frames.items():
        x = n[n["book"].isin(H.BETTABLE) & (n["price"] >= H.PRICE_FLOOR)]
        print(f"\nDECISION {p}, offers at deciding books at or above the floor:")
        print(x.groupby(["market", "side"]).agg(offers=("line", "size"), line_min=("line", "min"), line_max=("line", "max"),
                                                price_min=("price", "min"), price_max=("price", "max"),
                                                ev_max=("ev", "max")).round(3).to_string())
        far = x[x["price"] > 200]
        print(f"offers past +200: {len(far)}")
        if len(far):
            print(far[["game_id", "market", "book", "side", "line", "price", "ev"]].head(15).to_string(index=False))
        for m in sorted(set(x["market"])):
            t = x[x["market"] == m].sort_values("ev", ascending=False).head(15)
            print(f"highest EV, {m}, at {p}:")
            print(t[["game_id", "book", "side", "line", "price", "ev", "mu"]].round(3).to_string(index=False))
    # could a removed row reach a decision at all? (F4 and the live over read these frames unfiltered)
    for p in FULL_POINTS:
        v = H.visible(prep["raw_q"], prep["at"][p]["times"])
        med = v.groupby(["game_id", "market"])["line"].transform("median")
        hit = v[(v["line"] - med).abs() >= IMPOSSIBLE_GAP]
        print(f"rule 1's rows visible at {p} without the rule: {len(hit)}")
        if len(hit):
            print(hit[["game_id", "market", "book", "line", "price_a", "price_b", "T"]].to_string(index=False))
        out[f"rule1_visible_{p}"] = int(len(hit))
    return out


def smoke(cache: Path = H.CACHE) -> dict:
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
    print(json.dumps(synthetic_checks()))
    log("synthetic checks pass; loading the real cache")
    t_setup = time.time()
    shots, ledger = load_shots(shots_dir())
    real = G5.load_real(cache, require=False)
    if tuple(real["graded"]) != TT_GRADED:
        raise RuntimeError(f"derivative seasons {real['graded']}, the search grades exactly {TT_GRADED}")
    prep = assemble(real["data"], real["all_games"], real["games_p"], real["pe"], real["graded"], real["tb"], shots, ledger)
    setup_seconds = time.time() - t_setup
    log(f"assembled in {setup_seconds:.0f}s; peak memory {peak_memory_gb():.1f} GB")
    gate = require_registered_seasons(prep)
    reach = team_total_reach(prep)
    print("TEAM TOTALS, games and decision times per season (no result read):\n", reach.to_string(index=False))
    cov = coverage(shots, ledger, prep["untrusted"])
    print("COVERAGE PER SEASON:\n", cov.to_string())
    print("games left out:", prep["untrusted"].groupby(["season", "why"]).size().to_dict())
    a, p = zone_table(prep["tz"])
    print("ATTEMPTS PER TEAM GAME:\n", a.to_string())
    print("LEAGUE POINTS PER ATTEMPT:\n", p.to_string())
    ext = extremes(prep)
    gaps = gap_table(prep)
    print("GAPS PER SEASON (mean near zero is section 4's check):\n", gaps.round(3).to_string(index=False))
    print("WHAT THE RESIDUAL REMOVES, b per market and season:\n", prep["betas"].round(3).to_string(index=False))
    c = counts(prep)
    print("COUNTS, games each cell would bet (no result read):\n", c.to_string(index=False))
    o = overlap(prep)
    print("OVERLAP WITH THE LIVE MODELS (no result read):\n", o.round(3).to_string(index=False))
    log("counting the placebo")
    pc, pd_ = placebo_null(prep)
    print("PLACEBO ON THE REAL DATA, 20 runs, share of placebo bets not in the real cell:\n", pc.round(3).to_string(index=False))
    print("DATES:\n", pd_.round(3).to_string(index=False))
    summary = pc.groupby("point")[["placebo_bets", "placebo_same"]].sum()
    summary["share_different"] = 1.0 - summary["placebo_same"] / summary["placebo_bets"]
    print("PLACEBO BY DECISION:\n", summary.round(3).to_string())
    print("lowest cell:", pc.sort_values("share_different").head(5).round(3).to_string(index=False))
    away = (pc["share_different"] - pc["share_different_at_random"]).abs()
    print(f"farthest any cell sits from a perfect within-date shuffle: {away.max():.3f}")
    log("timing on real offers, scrambled scores")
    tm = timing(prep, setup_seconds)
    print("TIMING:", json.dumps(tm, indent=1, default=float))
    mem = peak_memory_gb()
    print(f"PEAK MEMORY OF THIS RUN: {mem:.1f} GB")
    out = {"extremes": ext, "coverage": cov.reset_index().to_dict("records"), "timing": tm, "peak_memory_gb": mem,
           "season_gate": gate.to_dict("records"), "team_total_reach": reach.to_dict("records"),
           "placebo_by_decision": summary.reset_index().to_dict("records"),
           "untrusted": prep["untrusted"].groupby(["season", "why"]).size().reset_index().to_dict("records")}
    folder = shots_dir()
    save_parquet(c, folder / "smoke_counts.parquet")
    save_parquet(o, folder / "smoke_overlap.parquet")
    save_parquet(pc, folder / "smoke_placebo.parquet")
    save_parquet(gaps, folder / "smoke_gaps.parquet")
    (folder / "smoke_summary.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    log("smoke done; nothing graded")
    return out


# ── writing: parquet stores numbers and strings only ────────────────────────

def save_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Writes `frame` without any column parquet cannot store (the pricing model the
    offers carry as sigma, sigma1: a ResidDist per row)."""
    bad = [c for c in frame.columns if frame[c].dtype == object
           and frame[c].map(lambda v: v is not None and v == v
                            and not isinstance(v, (str, int, float, bool, np.number, np.bool_))).any()]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=bad).to_parquet(path)


# ── a synthetic world (the only place a cell is run before --full) ──────────

_SHOT_SPEC = {"ra": (2, 25.0, 25.0, 2.0, 700.0, 0.65), "paint": (2, 18.0, 29.0, 8.0, 700.0, 0.43),
              "mid": (2, 10.0, 10.0, 12.0, 700.0, 0.42), "corner": (3, 9.0, 2.0, 5.0, 700.0, 0.385),
              "above": (3, 26.0, 25.0, 26.0, 700.0, 0.355), "heave": (3, 0.4, 25.0, 60.0, 1.0, 0.04),
              "ft": (1, 22.0, 25.0, 13.75, 300.0, 0.78)}
_SYN_BOOKS = ("pinnacle", "fanduel", "draftkings", "betmgm")


def _half(v: float) -> float:
    return float(np.floor(v)) + 0.5


def synthetic_world(seed: int = 0, seasons=(2020, 2021, 2022, 2023, 2024, 2025, 2026), days: int = 36,
                    n_teams: int = 10) -> dict:
    """Random, never real: every market the cells read (full-game totals and spreads at
    A and C from 2021 on, both team totals at D from 2024 on), a shot table consistent
    with the box scores and final scores, league make rates that DRIFT between seasons,
    and one impossible total, one flipped spread and one impossible team total. As on the
    real data, a per-game purchase holds more than team totals, and in 2023-24 about one
    game in twelve has a purchase with no team total (the real count is 1,138 of 1,230)."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    own = dict(zip(teams, rng.normal(0.0, 0.012, n_teams)))
    alw = dict(zip(teams, rng.normal(0.0, 0.012, n_teams)))
    games, box, ledger, per, quotes, pe, other_pe = [], [], [], [], [], [], []
    shot_cols = {c: [] for c in ("espn_game_id", "play_no", "clock_s", "team_side", "shot_value", "points",
                                 "coord_x", "coord_y")}
    bad = {}
    eid = 1000
    for s in seasons:
        drift = 0.012 * (s - seasons[0])                 # the league's rim shots improve every season
        for d in range(days):
            day = pd.Timestamp(f"{s - 1}-11-01") + pd.Timedelta(days=d)
            date = day.strftime("%Y-%m-%d")
            tip = (day + pd.Timedelta(hours=24)).tz_localize("UTC")
            perm = rng.permutation(teams)
            for j in range(0, n_teams, 2):
                h, a = str(perm[j]), str(perm[j + 1])
                gid = f"S{s}_{d}_{h}_{a}"
                eid += 1
                scores = {}
                for side, team, opp in (("H", h, a), ("A", a, h)):
                    fga = fg3a = fg3m = fta = ftm = pts = 0
                    no = 0
                    for z, (val, mean, x, y, clock, p) in _SHOT_SPEC.items():
                        n = int(rng.poisson(mean))
                        if n == 0:
                            continue
                        pz = p + own[team] + alw[opp] + (drift if z == "ra" else 0.0)
                        made = rng.random(n) < pz
                        points = made.astype("int64") * val
                        for c, v in (("espn_game_id", np.full(n, eid)), ("play_no", np.arange(no, no + n)),
                                     ("clock_s", np.full(n, clock)), ("team_side", np.full(n, side)),
                                     ("shot_value", np.full(n, val)), ("points", points),
                                     ("coord_x", np.full(n, x)), ("coord_y", np.full(n, y))):
                            shot_cols[c].append(v)
                        no += n
                        pts += int(points.sum())
                        if val == 1:
                            fta, ftm = fta + n, ftm + int(made.sum())
                        else:
                            fga += n
                            if val == 3:
                                fg3a, fg3m = fg3a + n, fg3m + int(made.sum())
                    scores[side] = pts
                    box.append({"game_id": gid, "team": team, "points": pts, "fg_att": fga, "fg3_made": fg3m,
                                "fg3_att": fg3a, "ft_made": ftm, "ft_att": fta, "offensive_reb": 10,
                                "turnovers": 14})
                hs, as_ = float(scores["H"]), float(scores["A"])
                games.append({"game_id": gid, "season": s, "game_date": date, "tip": tip, "home_team": h,
                              "away_team": a, "home_score": hs, "away_score": as_})
                ledger.append({"espn_game_id": eid, "game_id": gid, "season": s})
                qs = np.floor(np.array([hs, as_]) / 4.0)
                per += [{"game_id": gid, "period": k + 1, "home_points": qs[0] + (hs - 4 * qs[0] if k == 3 else 0),
                         "away_points": qs[1] + (as_ - 4 * qs[1] if k == 3 else 0)} for k in range(4)]
                if s == seasons[0]:
                    continue
                total = _half(226.0 + rng.normal(0.0, 6.0))
                spread = _half(rng.normal(-2.0, 6.0))
                for at in (pd.Timestamp(f"{date}T15:00:00Z"), tip - pd.Timedelta(minutes=90)):
                    base = {"game_id": gid, "season": s, "game_date": date, "tip": tip,
                            "snapshot_at": at - pd.Timedelta(minutes=2), "fetch_at": at, "coherent": True}
                    for b in _SYN_BOOKS:
                        jt, js = float(rng.integers(-1, 2)) * 0.5, float(rng.integers(-1, 2)) * 0.5
                        quotes += [{**base, "book": b, "market": "totals", "line": total + jt,
                                    "price_a": -110.0, "price_b": -110.0},
                                   {**base, "book": b, "market": "spreads", "line": spread + js,
                                    "price_a": -110.0, "price_b": -110.0}]
                if s < 2024:
                    continue
                at2 = tip - pd.Timedelta(minutes=55)
                b2 = {"game_id": gid, "season": s, "game_date": date, "tip": tip, "snapshot_at": at2,
                      "fetch_at": at2, "coherent": True}
                for b in _SYN_BOOKS:
                    jt = float(rng.integers(-1, 2)) * 0.5
                    pe += [{**b2, "book": b, "market": "team_totals_home", "line": _half((total - spread) / 2) + jt,
                            "price_a": -110.0, "price_b": -110.0},
                           {**b2, "book": b, "market": "team_totals_away", "line": _half((total + spread) / 2) + jt,
                            "price_a": -110.0, "price_b": -110.0}]
                other_pe.append({**b2, "book": "pinnacle", "market": "totals_h1", "line": _half(total / 2),
                                 "price_a": -110.0, "price_b": -110.0})
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    tt = pd.DataFrame(pe)
    # the bad rows, each on a game of 2025 past the 10-game mark, at the C fetch
    c_at = q[(q["season"] == 2025) & (q["book"] == "betmgm") & (q["market"] == "totals")
             & (q["fetch_at"] != pd.to_datetime(q["game_date"] + "T15:00:00", utc=True))]
    gid_t = str(c_at["game_id"].iloc[len(c_at) // 2])
    q.loc[(q["game_id"] == gid_t) & (q["book"] == "betmgm") & (q["market"] == "totals")
          & (q["fetch_at"] == q.loc[q["game_id"] == gid_t, "fetch_at"].max()), "line"] = 9.5
    bad["total"] = (gid_t, "betmgm", 9.5)
    sp = q[(q["season"] == 2025) & (q["book"] == "fanduel") & (q["market"] == "spreads") & (q["line"].abs() >= 4)
           & (q["game_id"] != gid_t) & (q["fetch_at"] != pd.to_datetime(q["game_date"] + "T15:00:00", utc=True))]
    r = sp.iloc[len(sp) // 2]
    q.loc[(q["game_id"] == r["game_id"]) & (q["book"] == "fanduel") & (q["market"] == "spreads")
          & (q["fetch_at"] == r["fetch_at"]), "line"] = -float(r["line"])
    bad["spread"] = (str(r["game_id"]), "fanduel", -float(r["line"]))
    gid_tt = str(tt[(tt["season"] == 2025)]["game_id"].iloc[len(tt[tt["season"] == 2025]) // 2])
    tt.loc[(tt["game_id"] == gid_tt) & (tt["book"] == "betmgm") & (tt["market"] == "team_totals_home"), "line"] = 9.5
    bad["team_total"] = (gid_tt, "betmgm", 9.5)
    no_team_totals = sorted(tt.loc[tt["season"] == 2024, "game_id"].unique())[::12]
    tt = pd.concat([tt[~tt["game_id"].isin(no_team_totals)], pd.DataFrame(other_pe)], ignore_index=True)
    fetches = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    fetches = fetches.assign(lead_min=(fetches["tip"] - fetches["fetch_at"]).dt.total_seconds() / 60.0)
    priced = g[g["season"] > seasons[0]].reset_index(drop=True)
    data = H.Data(games=priced, quotes=q[H.QUOTE_COLS].reset_index(drop=True), fetches=fetches.reset_index(drop=True))
    shots = pd.DataFrame({c: np.concatenate(v) for c, v in shot_cols.items()}).assign(period=1, feet_text=np.nan)
    return {"data": data, "all_games": g, "games_p": H.with_periods(g, periods=pd.DataFrame(per)),
            "pe": tt[H.QUOTE_COLS].reset_index(drop=True), "graded": TT_GRADED, "box": pd.DataFrame(box),
            "shots": shots, "ledger": pd.DataFrame(ledger), "bad": bad, "no_team_totals": set(no_team_totals)}


def assemble_world(world: dict) -> dict:
    tb = tl.team_box(world["box"], world["all_games"])
    return assemble(world["data"], world["all_games"], world["games_p"], world["pe"], world["graded"], tb,
                    world["shots"], world["ledger"], min_prior=100)


def bet_list(rows_from: dict, name: str = "zone") -> pd.DataFrame:
    """Every registered cell's bets on a prepared frame, without a grade."""
    parts = []
    for point, market, sides, neutral, _d, _ch, _t, _c, _s in groups(rows_from):
        _, _, cand = group_frames(neutral, rows_from["signals"][name], market)
        for side in sides:
            for cut in CUTS:
                parts.append(_pick(cand, cut, side).assign(point=point, cut=cut))
    return pd.concat(parts, ignore_index=True)


class _CoarsePricing:
    """Synthetic worlds only: H.ResidDist's table on a 0.25-point grid instead of 0.01,
    which makes the checks run in minutes. The real path never enters this."""

    def __enter__(self):
        self.step = H.ResidDist.STEP
        H.ResidDist.STEP = 0.25

    def __exit__(self, *exc):
        H.ResidDist.STEP = self.step


_SYNTHETIC_RUN: dict = {}


def synthetic_run(n_placebo: int = 2) -> dict:
    """All 48 cells, and each control on one full-game group and one team-total group,
    through run_cells on a synthetic world. Run once per process (the tests share it).
    NBA_GAME2_BETS is unset while it runs: run_cells writes every cell's bets wherever
    it points."""
    if n_placebo in _SYNTHETIC_RUN:
        return _SYNTHETIC_RUN[n_placebo]
    saved = os.environ.pop(BETS_ENV, None)
    try:
        world = synthetic_world()
        with _CoarsePricing():
            prep = assemble_world(world)
        rows, pops = emit(prep, "zone", FAMILY, seeds=PLACEBO_SEEDS[:n_placebo])
        ctl = []
        for name, fam in CONTROLS.items():
            ctl += emit(prep, name, fam, only={("C", "totals"), (TT_POINT, "team_totals_away")})[0]
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved
    _SYNTHETIC_RUN[n_placebo] = {"world": world, "prep": prep, "rows": rows, "ctl": ctl, "pops": pops}
    return _SYNTHETIC_RUN[n_placebo]


def synthetic_checks(n_placebo: int = 2) -> dict:
    """Before any real data is read (--smoke, --full). Raises on a fault."""
    H.check()
    run = synthetic_run(n_placebo)
    world, prep, rows, ctl = run["world"], run["prep"], run["rows"], run["ctl"]
    assert len(rows) == EXPECTED_CELLS and len(ctl) == 16 * len(CONTROLS), (len(rows), len(ctl))
    # lesson 4: the world really holds every market and decision, with bets in each
    by = pd.DataFrame(rows).groupby(["point", "market"])["pool_n"].sum()
    want = {(p, m) for p in FULL_POINTS for m in FULL_SIDES} | {(TT_POINT, m) for m in TT_SIDES}
    assert set(by.index) == want and (by > 0).all(), by
    # section 5's seasons: the world holds a season the 95% check would lose if only purchases
    # holding team totals counted, and the cells keep it
    only_rows = H.point_coverage(prep["dd"], TT_POINT, H.per_event_times(prep["raw_pe"], TT_POINT))
    assert only_rows[2024] < H.GATE_MIN, only_rows
    why = gate_refusals(season_gate(prep))
    assert not why, why
    # section 6: the bad rows reach no offer, no fair line and no bet
    assert len(prep["removed_full"]) >= 1 and len(prep["removed_tt"]) >= 1
    assert sum(len(v["removed"]) for v in prep["at"].values()) >= 1
    offers_all = pd.concat([prep["at"]["A"]["neutral"], prep["at"]["C"]["neutral"], prep["neutral_d"]], ignore_index=True)
    for _k, (gid, book, line) in world["bad"].items():
        assert not ((offers_all["game_id"] == gid) & (offers_all["book"] == book)
                    & (offers_all["line"] == line)).any(), (gid, book, line)
    # the parts add up
    z = prep["proj"]["zone"]
    assert np.allclose(z["part_home"] + z["part_away"], z["gap_total"]), "home part + away part != gap_total"
    assert np.allclose(z["part_home"] - z["part_away"], z["gap_margin"]), "home part - away part != gap_margin"
    # the league's drift stays out of the gap
    centre = z.groupby("season")["gap_total"].mean()
    assert (centre.abs() < 1.0).all(), centre
    return {"synthetic_checks": "pass", "cells": len(rows), "control_rows_run": len(ctl)}


# ── the graded run ──────────────────────────────────────────────────────────

def refuse_full(cache: Path, shots: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    if not (Path(cache) / P.LEDGER_FILE).exists():
        why.append(f"{Path(cache) / P.LEDGER_FILE} does not exist: refresh the cache")
    for f in (SHOTS_FILE, SHOT_GAMES_FILE):
        if not (Path(shots) / f).exists():
            why.append(f"{Path(shots) / f} does not exist: run --pull")
    return why


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    folder = shots_dir()
    why = refuse_full(cache, folder)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    print(json.dumps(synthetic_checks()), flush=True)
    log("synthetic checks pass; loading the real cache")
    shots, ledger = load_shots(folder)
    try:
        real = G5.load_real(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    if tuple(real["graded"]) != TT_GRADED:
        P.refuse([f"derivative seasons {real['graded']}, the search grades exactly {TT_GRADED}"])
    prep = assemble(real["data"], real["all_games"], real["games_p"], real["pe"], real["graded"], real["tb"], shots, ledger)
    log(f"assembled; peak memory {peak_memory_gb():.1f} GB")
    require_registered_seasons(prep)
    rows, pops = emit(prep, "zone", FAMILY, seeds=PLACEBO_SEEDS, progress=True)
    ctl = {}
    for name, fam in CONTROLS.items():
        ctl[fam], _ = emit(prep, name, fam, progress=True)
    ov = overlap(prep)
    # every table is written only once everything is built
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, out / f"cells_{FAMILY}.parquet")
    for fam, r in ctl.items():
        L.write_cells(r, out / f"cells_{fam}.parquet")
    save_parquet(pd.concat(pops, ignore_index=True), out / f"population_{FAMILY}.parquet")
    save_parquet(ov, out / "overlap_SL.parquet")
    keep = ["game_id", "season", "game_date", "home_team", "away_team", "gap_total", "gap_margin", "part_home", "part_away"]
    for name, p in prep["proj"].items():
        save_parquet(p[keep], out / f"gaps_{name}.parquet")
    save_parquet(prep["signals"]["added"], out / "gaps_added.parquet")
    save_parquet(prep["betas"], out / "betas_added.parquet")
    save_parquet(prep["rates"], out / "zone_rates.parquet")
    save_parquet(prep["untrusted"], out / "games_left_out.parquet")
    save_parquet(pd.concat([prep["removed_full"], prep["removed_tt"]], ignore_index=True), out / "rule1_removed.parquet")
    save_parquet(pd.concat([v["removed"].assign(point=p) for p, v in prep["at"].items()], ignore_index=True),
                 out / "rule2_removed.parquet")
    log(f"cells written to {out}: {len(rows)} registered, {sum(map(len, ctl.values()))} controls; peak memory {peak_memory_gb():.1f} GB")


def report(results: Path, n_placebo: int = N_PLACEBO) -> pd.DataFrame:
    """After --full: every cell with its bars, each control beside it and the overlap
    with the live models, from the files --full wrote. A cell under 200 pooled bets
    reads "too few games to tell", not a loss. Never read before the run is stored."""
    from scripts import nba_game2_verdict as V
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
    cells = V.load_cells(results)
    v = V.house_verdict_bands(cells, n_placebo=n_placebo)
    v = v.assign(reading=np.where(v["house5_passes"], "pass",
                                  np.where(v["pool_n"] < V.MIN_BETS, "too few games to tell", "fails")))
    keys = ["point", "market", "side", "cut"]
    out = v[keys + ["pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi", "pool_seasons_positive",
                    "pool_seasons_counted", "roi_choose", "placebo_p95", "dk_n_choose", "dk_roi_choose",
                    "reading", "house5_failed"]].copy()
    fam = cells["family"].astype(str)
    for name, f in CONTROLS.items():
        c = cells[fam == f]
        if len(c):
            out = out.merge(c[keys + ["pool_n", "pool_roi"]].rename(
                columns={"pool_n": f"{name}_n", "pool_roi": f"{name}_roi"}), on=keys, how="left")
    if (results / "overlap_SL.parquet").exists():
        o = pd.read_parquet(results / "overlap_SL.parquet")
        out = out.merge(o[keys + ["share_same_bet", "share_same_game"]], on=keys, how="left")
    print(out.round(3).to_string(index=False))
    print(f"{int(v['house5_passes'].sum())} of {len(v)} pass; {int(v['h2_ci95'].sum())} clear the 95% interval alone, "
          f"about {0.025 * len(v):.1f} expected by chance before correlation")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    g.add_argument("--pull", action="store_true", help="read the shots from Supabase once, read-only")
    g.add_argument("--report", type=Path, default=None, help="after --full: the cells, controls and overlap from this folder")
    ap.add_argument("--pull-limit", type=int, default=None, help="pull only this many games (a check of the path)")
    ap.add_argument("--pull-out", type=Path, default=None, help="the folder --pull writes (default NBA_SHOTS_CACHE)")
    a = ap.parse_args(argv)
    if a.pull:
        pull(a.pull_out or shots_dir(), a.pull_limit)
    elif a.report:
        report(a.report)
    elif a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
