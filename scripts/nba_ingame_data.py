"""In-play NBA quotes joined to the game state at each quote's stamp.

docs/nba_models_2026.md section 7.1. ONE table, one row per (game, market,
book, quote stamp), that every in-game family (IG-1, IG-2, HT-1) reads; the
staleness gate (scripts/nba_ingame_staleness.py) reads it too.

DEFINITIONS (stated once, used everywhere):

  STAMP      a stored quote's `snapshot_at`: the book's own `last_update` for
             that market (data/ingestors/odds_ingestor._process_events). It is
             when the book last changed or confirmed the price.
  FETCH      the purchase that returned the quote: the ledger instant whose
             pulled_at = the row's created_at (nba_game_harness.attach_fetch).
  SERVED     `served_at`: when the feed served the quote. The feed's snapshot
             time is not stored. Per fetch, fetch_at minus the newest stamp any
             row of that fetch carries (every game, book and market) sits on a
             grid: about 549-553 s in 2020-21 and 2021-22 (10-minute
             snapshots), 264 s from 2022-23 (5-minute snapshots, the feed's
             :x0:38 / :x5:38). served_at = fetch_at minus the season's 1st
             percentile of that gap, and never earlier than the fetch's newest
             stamp (three fetches carry a stamp past the grid).
             `served_newest` (the newest stamp alone) is kept beside it.
  IN-PLAY    by the play-by-play clock, never by the stored label or
             `games.commence_time`: stamp at or after the game's first play
             (its earliest ESPN wallclock) and before the end of its final
             period. A quote stamped before the first play is excluded
             (`phase` = pregame), however it is labelled.
  STATE      everything ESPN had logged AT OR BEFORE the stamp: the plays with
             wallclock <= stamp, whatever their play order (0.78% of
             consecutive plays run backwards in wallclock). Period and clock
             come from the latest such play. Plays are the nba_pbp rows, built
             by the same code that wrote that table (nba_pbp.slim_plays), so
             team sides are already in OUR home/away and the running score
             follows its POINTS rule.
  PHASE      live; break (from a period's end to the next period's start);
             halftime (that gap after period 2); pregame; postgame (at or
             after the end of the final period).
  PERIODS    a period ends at its End Period row. It starts at its first play
             with the game clock running (or the jump ball), backed off by the
             game time that play shows; ESPN logs the next period's opening
             substitutions at 12:00 as the previous period ends, so the
             earliest row is not the start (phase_bounds).
  FOULS      a personal foul (PF) is a foul row other than technicals and "No
             Foul"; an "Offensive Foul Turnover" counts as one only when no
             "Offensive Foul" row by the same player sits at the same period
             and clock (ESPN logs a charge either way). A TEAM foul (toward
             the bonus) is a PF that is not offensive and not a double foul.
  SHOOTING   3PA, 3PM, FTA, FTM by team so far. A missed end-of-period heave
             (3 s or less on the clock, 36 ft or more by the text's distance,
             else the shot coordinates) is left out of 3PA in EVERY season and
             counted in `heave3`: from 2025-26 the official count leaves it
             out (measured: the play-by-play matches ESPN's box on 97.3% of
             2025-26 team-games without them, 62% with them; through 2024-25
             it matches with them). A made heave stays a make.
  WALLCLOCK  a game with any play logged more than 4 h from the game's median
             wallclock is left out whole. In 13 games of late October 2025
             ESPN stamped a whole half about 24 h off, and in others one late
             play 11-24 h off; dropping only the far plays would delete a real
             half from the score whenever the wrong half is the larger one.
  TOP PLAYERS each side's three starters (known at tip) with the most minutes
             per game in their earlier games this season (else last season's
             average, else 0) -- never this game's minutes.
  PINNACLE   Pinnacle's quote on the same game and market in the SAME fetch,
             stamped within 60 s of the quote (nearest); its no-vig side-A
             probability is proportional (nba_game_harness.pinnacle_close's
             convention), set only when its two-way quote is coherent.
  SIDE A     home (h2h, spreads) or over (totals); `line` is the stored side-A
             number (spread_home, or the total), as in the harness.

Inputs (read only): the research cache (NBA_RESEARCH_CACHE: nba_odds,
nba_fetch_ledger, nba_games, nba_stints for the ESPN id map), and the
sportsdataverse ESPN release files the nba_pbp ingestor downloaded (the same
rows it wrote to Supabase `nba_pbp` / `nba_pbp_box`). Every input is a cache of
Supabase, so the output is regenerable and is written to the temp dir only.

    PYTHONPATH=. python -m scripts.nba_ingame_data            # build + checks
    PYTHONPATH=. python -m scripts.nba_ingame_data --seasons 2024
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game_market_lab import imp  # noqa: E402

OUT_DIR = Path(tempfile.gettempdir()) / "nba_game_edge" / "ingame"
OUT = OUT_DIR / "quotes_state.parquet"
TIMELINE = OUT_DIR / "score_timeline.parquet"
PBP_ROOT = Path(tempfile.gettempdir()) / "nba_free_data" / "sportsdataverse_espn"
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
PIN_WINDOW_S = 60
GRID_Q = 0.01              # the feed grid's offset: 1st percentile of fetch_at - newest stamp
PREFILTER_MIN = 90          # quotes stamped > 90 min before the listed tip cannot be in play
HOME, AWAY = "H", "A"
HEAVE_CLOCK_S, HEAVE_FEET = 3.0, 36.0
HEAVE_RULE_SEASON = 2026     # the first season whose official 3PA leaves missed heaves out
WILD_HOURS = 4.0
_FEET_RE = re.compile(r"(\d+)-foot")

PF_EXCLUDE = ("Technical", "No Foul")
OFFENSIVE = ("Offensive Foul", "Offensive Charge Foul")
OFT = "Offensive Foul Turnover"
DOUBLE = "Double Personal Foul"
BOX_COLS = ["game_id", "season_type", "game_date", "athlete_id", "team_id", "home_away",
            "minutes", "starter", "did_not_play", "fouls", "three_point_field_goals_made",
            "three_point_field_goals_attempted", "free_throws_made", "free_throws_attempted"]


# ── plays ───────────────────────────────────────────────────────────────────

def foul_flags(plays: pd.DataFrame) -> pd.DataFrame:
    """pf (personal foul on athlete_id_1, by team_side) and tf (team foul
    toward the bonus) per play, by the FOULS rule in the module docstring."""
    t = plays["type_text"].fillna("")
    is_foul = t.str.contains("Foul") & ~t.str.startswith("Free Throw")
    excl = np.zeros(len(t), bool)
    for w in PF_EXCLUDE:
        excl |= t.str.contains(w).to_numpy()
    pf = is_foul & ~excl & (t != OFT)
    # a charge logged only as a turnover is still a personal foul
    key = ["game_id", "period", "clock_s", "athlete_id_1"]
    off_rows = plays.loc[t.isin(OFFENSIVE), key].drop_duplicates()
    oft = plays.loc[t == OFT, key].reset_index().merge(off_rows, on=key, how="left", indicator=True)
    lone = set(oft.loc[oft["_merge"] == "left_only", "index"])
    lone_mask = plays.index.isin(lone)
    pf = pf | lone_mask
    offensive = t.isin(OFFENSIVE) | lone_mask
    tf = pf & ~offensive & (t != DOUBLE)
    return plays.assign(pf=pf.astype(int), tf=tf.astype(int))


def shot_feet(text, x, y) -> float:
    """A shot's distance in feet: the text's "N-foot", else the raw ESPN
    coordinates (basket at (25, 0), as nba_stints.classify_field_goal reads
    them), else NaN."""
    m = _FEET_RE.search(text or "")
    if m:
        return float(m.group(1))
    if x is None or y is None or x != x or y != y:
        return float("nan")
    return float(((float(x) - 25.0) ** 2 + float(y) ** 2) ** 0.5)


def is_heave(made: bool, value, clock_s, feet) -> bool:
    """A missed end-of-period heave (HEAVES in the module docstring)."""
    return (not made) and value == 3 and clock_s is not None and clock_s <= HEAVE_CLOCK_S         and feet == feet and feet >= HEAVE_FEET


def plays_frame(rows: list[dict]) -> pd.DataFrame:
    """nba_pbp-shaped rows (nba_pbp.slim_plays) -> the per-play frame this
    module counts from: wallclock, period, clock, side, points, shots, fouls."""
    from data.ingestors import nba_stints as st
    out = []
    for p in rows:
        sv = p.get("shot_value")
        ft = st.is_ft(p)
        fga = (not ft) and st.is_fga(p)
        made = p["points"] > 0
        heave = fga and is_heave(made, sv, p["clock_s"],
                                 shot_feet(p.get("text"), p.get("coord_x"), p.get("coord_y")))
        out.append((p["game_id"], p["play_no"], p.get("wallclock"), p["period"], p["clock_s"],
                    p["game_s"], p.get("type_text"), p.get("team_side"), p["points"],
                    int(fga and sv == 3 and not heave), int(fga and sv == 3 and made), int(heave),
                    int(ft), int(ft and made), p.get("athlete_id_1")))
    df = pd.DataFrame(out, columns=["game_id", "play_no", "wallclock", "period", "clock_s", "game_s",
                                    "type_text", "team_side", "points", "fg3a", "fg3m", "heave3",
                                    "fta", "ftm", "athlete_id_1"])
    df["wc"] = pd.to_datetime(df["wallclock"], utc=True, errors="coerce")
    return foul_flags(df.drop(columns="wallclock"))


def drop_wild_wallclocks(plays: pd.DataFrame, hours: float = WILD_HOURS) -> tuple[pd.DataFrame, list]:
    """Drop every game with a play logged more than `hours` from the game's
    median wallclock (WALLCLOCK in the module docstring). Returns (kept plays,
    the dropped game ids)."""
    med = plays.groupby("game_id")["wc"].transform("median")
    wild = (plays["wc"] - med).abs() > pd.Timedelta(hours=hours)
    bad = sorted(set(plays.loc[wild, "game_id"]))
    return plays[~plays["game_id"].isin(bad)].copy(), bad


NOT_ACTION = ("Substitution", "Timeout", "Technical", "End Period", "End Game", "Ejection")


def period_length(period) -> np.ndarray:
    return np.where(np.asarray(period) <= 4, 720.0, 300.0)


def phase_bounds(plays: pd.DataFrame) -> pd.DataFrame:
    """Per (game, period): START and END (PERIODS in the module docstring).

    start: the period's first ACTION play by wallclock -- the jump ball, or a
    play with the game clock already running that is not a substitution,
    timeout, technical or period marker -- backed off by the game time it shows
    (wallclock - (period length - clock)). ESPN logs the next period's opening
    substitutions at 12:00 the moment a period ends, so the period's earliest
    row is not its start. Wall time never runs slower than the game clock, so
    this estimate is never before the true start. No action play: the period's
    earliest wallclock.
    end: the period's End Period row (latest, if logged twice), else its latest
    wallclock."""
    p = plays.dropna(subset=["wc"])
    t = p["type_text"].fillna("")
    na = np.zeros(len(p), bool)
    for w in NOT_ACTION:
        na |= t.str.contains(w).to_numpy()
    act = ((t == "Jumpball") | (p["clock_s"] < period_length(p["period"]))) & ~na
    a = p[act].sort_values(["game_id", "period", "wc"]).drop_duplicates(["game_id", "period"])
    a = a.assign(start_act=a["wc"] - pd.to_timedelta(period_length(a["period"]) - a["clock_s"], unit="s"))
    b = p.groupby(["game_id", "period"])["wc"].agg(first="min", last="max").reset_index()
    b = b.merge(a[["game_id", "period", "start_act"]], on=["game_id", "period"], how="left")
    ep = p[t == "End Period"].groupby(["game_id", "period"])["wc"].max().rename("ep")
    b = b.merge(ep.reset_index(), on=["game_id", "period"], how="left")
    b["end"] = b["ep"].fillna(b["last"])
    b["start"] = b["start_act"].fillna(b["first"])
    # never before the previous period ended
    prev_end = b.sort_values(["game_id", "period"]).groupby("game_id")["end"].shift(1)
    b["start"] = b["start"].where(prev_end.isna() | (b["start"] >= prev_end), prev_end)
    return b[["game_id", "period", "start", "end"]]


def label_phase(q: pd.DataFrame, bounds: pd.DataFrame, at: str = "stamp") -> pd.Series:
    """Phase of each quote at column `at` (see PHASE)."""
    first = bounds.groupby("game_id")["start"].min()
    last_p = bounds.sort_values("period").groupby("game_id").tail(1).set_index("game_id")
    t = q[at]
    g = q["game_id"]
    phase = pd.Series("live", index=q.index, dtype=object)
    no_pbp = ~g.isin(first.index)
    phase[t < g.map(first)] = "pregame"
    phase[t >= g.map(last_p["end"])] = "postgame"
    nxt = bounds.assign(period=bounds["period"] - 1)[["game_id", "period", "start"]].rename(
        columns={"start": "next_start"})
    gaps = bounds.merge(nxt, on=["game_id", "period"])
    for per, grp in gaps.groupby("period"):
        e = g.map(grp.set_index("game_id")["end"])
        s = g.map(grp.set_index("game_id")["next_start"])
        inside = (t >= e) & (t < s) & (phase == "live")
        phase[inside] = "halftime" if per == 2 else "break"
    phase[no_pbp] = "no_pbp"
    return phase


IN_PLAY_PHASES = ("live", "break", "halftime")


def keep_in_play(q: pd.DataFrame, bounds: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Quotes in play by the play-by-play clock (IN-PLAY), whatever their
    stored label; the phase is attached. Returns (kept, counts)."""
    q = q.assign(phase=label_phase(q, bounds, "stamp"))
    counts = {"phase_counts_all": q["phase"].value_counts().to_dict(),
              "label_vs_phase": {f"{a}|{b}": int(n) for (a, b), n in
                                 q.groupby(["label", "phase"]).size().items()}}
    return q[q["phase"].isin(IN_PLAY_PHASES)].reset_index(drop=True), counts


def timeline(plays: pd.DataFrame, top: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cumulative state after each play, in wallclock order (ties: play order).
    `top` (game_id, side, rank, athlete_id) adds each top player's fouls."""
    p = plays.dropna(subset=["wc"]).sort_values(["game_id", "wc", "play_no"]).reset_index(drop=True)
    gk = p["game_id"]
    out = p[["game_id", "wc", "play_no", "period", "clock_s", "game_s", "type_text"]].copy()
    for side, pre in ((HOME, "h"), (AWAY, "a")):
        m = (p["team_side"] == side)
        for c in ("points", "fg3a", "fg3m", "heave3", "fta", "ftm", "pf"):
            name = f"{pre}_{'pts' if c == 'points' else c}"
            out[name] = (p[c] * m).groupby(gk).cumsum()
        tf = p["tf"] * m
        out[f"{pre}_tf_period"] = tf.groupby([gk, p["period"]]).cumsum()
    if top is not None and len(top):
        t = top.copy()
        for (side, rank), grp in t.groupby(["side", "rank"]):
            pre = "h" if side == HOME else "a"
            pid = gk.map(grp.set_index("game_id")["athlete_id"])
            hit = (p["pf"] == 1) & (p["athlete_id_1"] == pid)
            out[f"{pre}_top{rank}_pf"] = hit.astype(int).groupby(gk).cumsum()
    return out


def state_at(q: pd.DataFrame, tl: pd.DataFrame, at: str, cols, suffix: str = "") -> pd.DataFrame:
    """As-of join: for each quote, the timeline row of the latest play with
    wallclock <= q[at] (same game). A quote before the game's first play gets
    zeros for counts and no period."""
    left = q[["game_id", at]].reset_index().rename(columns={at: "_t"})
    left = left.dropna(subset=["_t"])
    left["_t"] = left["_t"].astype("datetime64[ns, UTC]")
    left = left.sort_values("_t")
    right = tl[["game_id", "wc", *cols]].dropna(subset=["wc"])
    right = right.assign(wc=right["wc"].astype("datetime64[ns, UTC]")).sort_values("wc")
    m = pd.merge_asof(left, right, left_on="_t", right_on="wc", by="game_id",
                      direction="backward", allow_exact_matches=True)
    m = m.set_index("index").reindex(q.index)
    out = m[list(cols)]
    if suffix:
        out = out.add_suffix(suffix)
    return out


def attach_pinnacle(q: pd.DataFrame, window_s: float = PIN_WINDOW_S) -> pd.DataFrame:
    """Pinnacle's quote in the same fetch, same game and market, stamped within
    `window_s` of each quote (the nearest); NaN where none is."""
    pin = q[q["book"] == H.SHARP][["game_id", "market", "fetch_at", "stamp", "line", "price_a",
                                   "price_b", "coherent", "fa"]]
    pin = pin.rename(columns={"stamp": "pin_stamp", "line": "pin_line", "price_a": "pin_price_a",
                              "price_b": "pin_price_b", "coherent": "pin_coherent", "fa": "pin_fa"})
    x = q[["game_id", "market", "fetch_at", "stamp"]].reset_index().merge(
        pin, on=["game_id", "market", "fetch_at"], how="inner")
    x["pin_dt_s"] = (x["stamp"] - x["pin_stamp"]).dt.total_seconds()
    x = x[x["pin_dt_s"].abs() <= window_s]
    x = x.assign(_a=x["pin_dt_s"].abs()).sort_values(["index", "_a"]).drop_duplicates("index")
    cols = ["pin_stamp", "pin_dt_s", "pin_line", "pin_price_a", "pin_price_b", "pin_coherent", "pin_fa"]
    att = x.set_index("index")[cols].reindex(q.index)
    att.loc[att["pin_coherent"] != True, "pin_fa"] = np.nan  # noqa: E712
    return pd.concat([q, att], axis=1)


# ── quotes ──────────────────────────────────────────────────────────────────

def load_quotes(cache: Path, games: pd.DataFrame, seasons) -> tuple[pd.DataFrame, dict]:
    """Every full-game quote that could be in play (stamp later than 90 min
    before the listed tip), with fetch_at and served_at; duplicates dropped."""
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[o["market"].isin(H.MARKETS) & (o["source"] == "odds_api_historical")].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    led = pd.read_parquet(cache / "nba_fetch_ledger.parquet")
    o, notes = H.attach_fetch(o, led)
    # served_at (SERVED in the docstring): the fetch's snapshot on the feed's
    # grid, never earlier than the newest stamp the fetch carries.
    newest = o.groupby("fetch_at")["snapshot_at"].max().rename("served_newest")
    o = o.merge(newest.reset_index(), on="fetch_at", how="left")
    per_fetch = o[["season", "fetch_at", "served_newest"]].drop_duplicates("fetch_at")
    per_fetch_gap = (per_fetch["fetch_at"] - per_fetch["served_newest"]).dt.total_seconds()
    offset = per_fetch_gap.groupby(per_fetch["season"]).quantile(GRID_Q)
    notes["grid_offset_s"] = {int(k): float(v) for k, v in offset.items()}
    notes["grid_gap_min_s"] = {int(k): float(v) for k, v in per_fetch_gap.groupby(per_fetch["season"]).min().items()}
    on_grid = o["fetch_at"] - pd.to_timedelta(o["season"].map(offset), unit="s")
    o["served_at"] = on_grid.where(on_grid > o["served_newest"], o["served_newest"])
    o = o[o["season"].isin(list(seasons))
          & (o["snapshot_at"] >= o["tip"] - pd.Timedelta(minutes=PREFILTER_MIN))].copy()
    o = o.rename(columns={"bookmaker": "book", "snapshot_at": "stamp", "snapshot_type": "label"})
    notes["rows_candidate"] = int(len(o))
    k = ["game_id", "market", "book", "stamp", "fetch_at"]
    notes["rows_exact_duplicate"] = int(o.duplicated(k).sum())
    o = o.drop_duplicates(k)
    k2 = ["game_id", "market", "book", "stamp"]
    o = o.sort_values([*k2, "fetch_at"])
    notes["rows_same_stamp_later_fetch"] = int(o.duplicated(k2).sum())
    o = o.drop_duplicates(k2, keep="first")
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"],
                         np.where(o["market"] == "totals", o["total_line"], np.nan))
    o["price_a"] = np.where(o["market"] == "totals", o["over_price"], o["home_price"])
    o["price_b"] = np.where(o["market"] == "totals", o["under_price"], o["away_price"])
    o = o[o["price_a"].notna() & o["price_b"].notna()].copy()
    ia, ib = imp(o["price_a"]), imp(o["price_b"])
    o["implied_sum"] = ia + ib
    o["coherent"] = (o["implied_sum"] >= H.COHERENT[0]) & (o["implied_sum"] <= H.COHERENT[1])
    o["fa"] = ia / (ia + ib)
    keep = ["game_id", "season", "game_date", "tip", "market", "book", "label", "stamp", "fetch_at",
            "served_at", "served_newest", "line", "price_a", "price_b", "implied_sum", "coherent", "fa"]
    return o[keep].reset_index(drop=True), notes


# ── play-by-play per season ─────────────────────────────────────────────────

def espn_map(cache: Path) -> pd.DataFrame:
    s = pd.read_parquet(cache / "nba_stints.parquet", columns=["espn_game_id", "game_id"])
    s = s.dropna().drop_duplicates()
    s["espn_game_id"] = s["espn_game_id"].astype(int)
    return s


def season_plays(season: int, want: pd.DataFrame, games: pd.DataFrame):
    """(plays, box, notes) for the regular-season games in `want` (espn_game_id,
    game_id), through nba_pbp.slim_plays, sides in OUR home/away."""
    import pyarrow.parquet as pq
    from data.ingestors import nba_pbp as P
    path = PBP_ROOT / f"pbp_{season}" / f"play_by_play_{season}.parquet"
    bpath = PBP_ROOT / f"box_{season}" / f"player_box_{season}.parquet"
    have = set(pq.read_schema(path).names)
    pbp = pd.read_parquet(path, columns=[c for c in P.PBP_SOURCE_COLS if c in have])
    pbp = pbp[(pbp["season_type"] == 2) & pbp["game_id"].astype(int).isin(set(want["espn_game_id"]))]
    pbp = pbp.astype(object).where(pbp.notna(), None)
    gmap = want.set_index("espn_game_id")["game_id"]
    ours = games.set_index("game_id")[["home_team", "away_team"]]
    rows, swaps, bad = [], {}, []
    for eid, grp in pbp.groupby(pbp["game_id"].astype(int), sort=False):
        recs = grp.to_dict("records")
        meta = P.espn_game_meta(eid, recs)
        gid = gmap[eid]
        h, a = ours.loc[gid, "home_team"], ours.loc[gid, "away_team"]
        if meta and meta["home"] == h and meta["away"] == a:
            sw = False
        elif meta and meta["home"] == a and meta["away"] == h:
            sw = True
        else:
            bad.append(gid)
            continue
        swaps[gid] = sw
        rows.extend(P.slim_plays(recs, espn_game_id=eid, game_id=gid, season=season,
                                 season_type=2, swapped=sw))
    plays, wild = drop_wild_wallclocks(plays_frame(rows))
    plays["espn_game_id"] = plays["game_id"].map(want.set_index("game_id")["espn_game_id"])
    box = pd.read_parquet(bpath, columns=BOX_COLS)
    box = box[box["season_type"] == 2].copy()
    box["espn_game_id"] = box["game_id"].astype(int)
    box = box.merge(want, on="espn_game_id", suffixes=("_espn", ""))
    box = box[~box["game_id"].isin(wild)]
    sw = box["game_id"].map(swaps)
    ha = box["home_away"].str.lower()
    box["side"] = np.where((ha == "home") ^ sw.fillna(False).astype(bool), HOME, AWAY)
    notes = {"games_pbp": int(plays["game_id"].nunique()), "games_swapped": int(sum(swaps.values())),
             "games_team_mismatch": len(bad), "plays": int(len(plays)), "games_clock_broken": len(wild),
             "wallclock_null": int(plays["wc"].isna().sum())}
    return plays, box, notes


def prior_minutes(seasons) -> pd.DataFrame:
    """(espn game id, athlete_id, prior_min): minutes per game in the player's
    earlier games of the same season; else his previous season's average."""
    frames = []
    for s in sorted(set(seasons) | {min(seasons) - 1}):
        path = PBP_ROOT / f"box_{s}" / f"player_box_{s}.parquet"
        if not path.exists():
            continue
        b = pd.read_parquet(path, columns=["game_id", "season_type", "game_date", "athlete_id",
                                           "minutes", "did_not_play"])
        b = b[b["season_type"] == 2].assign(season=s)
        frames.append(b)
    b = pd.concat(frames, ignore_index=True)
    b["game_date"] = pd.to_datetime(b["game_date"])
    b["m"] = pd.to_numeric(b["minutes"], errors="coerce")
    played = b["m"].fillna(0) > 0
    b = b.sort_values(["athlete_id", "game_date", "game_id"])
    b["_m"] = b["m"].where(played)
    grp = b.groupby(["athlete_id", "season"])["_m"]
    b["prior_min"] = grp.transform(lambda x: x.shift(1).expanding().mean())
    last = b[played].groupby(["athlete_id", "season"])["m"].mean().rename("last_season_min").reset_index()
    last["season"] = last["season"] + 1
    b = b.merge(last, on=["athlete_id", "season"], how="left")
    b["prior_min"] = b["prior_min"].fillna(b["last_season_min"]).fillna(0.0)
    b["espn_game_id"] = b["game_id"].astype(int)
    return b[["espn_game_id", "athlete_id", "prior_min"]]


def top_players(box: pd.DataFrame, prior: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """(game_id, side, rank 1..k, athlete_id): each side's starters ranked by
    prior minutes (ties by athlete id)."""
    s = box[box["starter"] == True].merge(prior, on=["espn_game_id", "athlete_id"], how="left")  # noqa: E712
    s["prior_min"] = s["prior_min"].fillna(0.0)
    s = s.sort_values(["game_id", "side", "prior_min", "athlete_id"], ascending=[True, True, False, True])
    s["rank"] = s.groupby(["game_id", "side"]).cumcount() + 1
    s = s[s["rank"] <= k]
    return s[["game_id", "side", "rank", "athlete_id"]].assign(athlete_id=lambda d: d["athlete_id"].astype(float))


def box_checks(plays: pd.DataFrame, box: pd.DataFrame, games: pd.DataFrame, season: int) -> dict:
    """Game-end counts from the plays against ESPN's box score and our final."""
    b = box.copy()
    for c in ("fouls", "three_point_field_goals_made", "three_point_field_goals_attempted",
              "free_throws_made", "free_throws_attempted"):
        b[c] = pd.to_numeric(b[c], errors="coerce")
    bt = b.groupby(["game_id", "side"]).agg(
        fg3m=("three_point_field_goals_made", "sum"), fg3a=("three_point_field_goals_attempted", "sum"),
        ftm=("free_throws_made", "sum"), fta=("free_throws_attempted", "sum"), pf=("fouls", "sum"))
    pt = plays.groupby(["game_id", "team_side"])[["fg3m", "fg3a", "heave3", "ftm", "fta", "pf"]].sum()
    pt.index = pt.index.set_names(["game_id", "side"])
    if season < HEAVE_RULE_SEASON:      # the official count still included missed heaves
        pt["fg3a"] = pt["fg3a"] + pt["heave3"]
    j = bt.join(pt, rsuffix="_pbp", how="inner")
    out = {f"team_{c}_exact": round(float((j[c] == j[f"{c}_pbp"]).mean()), 4)
           for c in ("fg3m", "fg3a", "ftm", "fta", "pf")}
    out["team_games_compared"] = int(len(j))
    b["athlete_id"] = pd.to_numeric(b["athlete_id"], errors="coerce").astype(float)
    pp = b[b["fouls"].notna()].groupby(["game_id", "athlete_id"])["fouls"].sum()
    pf = plays[plays["pf"] == 1].groupby(["game_id", "athlete_id_1"]).size()
    pf.index = pf.index.set_names(["game_id", "athlete_id"])
    jj = pp.to_frame().join(pf.rename("pbp").reindex(pp.index), how="left").fillna({"pbp": 0})
    out["player_pf_exact"] = round(float((jj["fouls"] == jj["pbp"]).mean()), 4)
    fin = plays.groupby(["game_id", "team_side"])["points"].sum().unstack()
    g = games.set_index("game_id").reindex(fin.index)
    out["final_score_exact"] = round(float(((fin[HOME] == g["home_score"]) & (fin[AWAY] == g["away_score"])).mean()), 4)
    return out


# ── build ───────────────────────────────────────────────────────────────────

def build(cache: Path = H.CACHE, seasons=SEASONS) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    t0 = time.time()
    games = H.load_games(cache)
    games = games[games["season"].isin(list(seasons))]
    q, notes = load_quotes(cache, games, seasons)
    print(f"quotes loaded {len(q):,} ({time.time() - t0:.0f}s)", flush=True)
    emap = espn_map(cache)
    emap = emap[emap["game_id"].isin(set(q["game_id"]))]
    prior = prior_minutes(seasons)
    plays_all, tls, bounds_all, checks = [], [], [], {}
    for s in seasons:
        want = emap[emap["game_id"].isin(set(games.loc[games["season"] == s, "game_id"]))]
        plays, box, n = season_plays(s, want, games)
        top = top_players(box, prior)
        tl = timeline(plays, top)
        tls.append(tl)
        bounds_all.append(phase_bounds(plays))
        checks[s] = {**n, **box_checks(plays, box, games, s)}
        plays_all.append(plays[["game_id", "wc", "period", "type_text"]])
        print(f"season {s}: {checks[s]} ({time.time() - t0:.0f}s)", flush=True)
    tl = pd.concat(tls, ignore_index=True)
    bounds = pd.concat(bounds_all, ignore_index=True)
    notes["season_checks"] = checks
    e2 = bounds[bounds["period"] == 2].set_index("game_id")["end"]
    s3 = bounds[bounds["period"] == 3].set_index("game_id")["start"]
    ht = ((s3 - e2).dt.total_seconds() / 60).dropna()
    hs = ht.groupby(ht.index.map(games.set_index("game_id")["season"])).describe(
        percentiles=[.01, .05, .5, .95, .99]).round(1)
    notes["halftime_minutes_by_season"] = hs.to_dict("index")
    # listed tip vs first play
    first = bounds.groupby("game_id")["start"].min().rename("first_play_at")
    last = bounds.sort_values("period").groupby("game_id").tail(1).set_index("game_id")["end"].rename("final_end_at")
    q = q.merge(first.reset_index(), on="game_id", how="left").merge(last.reset_index(), on="game_id", how="left")
    q, counts = keep_in_play(q, bounds)
    notes.update(counts)
    state_cols = [c for c in tl.columns if c not in ("game_id", "wc", "play_no", "type_text")]
    st_ = state_at(q, tl, "stamp", state_cols)
    q = pd.concat([q, st_], axis=1)
    reg = q["period"] <= 4
    q["secs_left"] = np.where(reg, q["clock_s"] + 720 * (4 - q["period"]), q["clock_s"])
    q["halftime"] = q["phase"] == "halftime"
    q["last_play_at"] = state_at(q, tl.assign(lp=tl["wc"]), "stamp", ["lp"])["lp"]
    for at, suf in (("stamp_m60", "_m60"), ("stamp_m120", "_m120"), ("served_at", "_served"),
                    ("served_newest", "_served_newest")):
        if at.startswith("stamp_m"):
            q[at] = q["stamp"] - pd.Timedelta(seconds=int(at[7:]))
        s2 = state_at(q, tl, at, ["h_pts", "a_pts"], suf)
        q = pd.concat([q, s2.fillna(0)], axis=1)
    q = q.drop(columns=["stamp_m60", "stamp_m120"])
    q["pts_since_stamp"] = (q["h_pts_served"] + q["a_pts_served"]) - (q["h_pts"] + q["a_pts"])
    q["pts_since_stamp_newest"] = (q["h_pts_served_newest"] + q["a_pts_served_newest"]) - (q["h_pts"] + q["a_pts"])
    q = attach_pinnacle(q)
    g = games.set_index("game_id")
    q["final_home"] = q["game_id"].map(g["home_score"])
    q["final_away"] = q["game_id"].map(g["away_score"])
    q["espn_game_id"] = q["game_id"].map(emap.set_index("game_id")["espn_game_id"])
    notes["rows_out"] = int(len(q))
    tl_out = tl[["game_id", "wc", "h_pts", "a_pts", "period", "clock_s"]]
    return q, tl_out, notes


def report(q: pd.DataFrame, notes: dict) -> None:
    print("\nnotes:")
    for k, v in notes.items():
        if k != "season_checks":
            print(f"  {k}: {v}")
    print("\nrows by season x market:")
    print(q.groupby(["season", "market"]).size().unstack().to_string())
    print("\nphase x season:")
    print(q.groupby(["phase", "season"]).size().unstack().fillna(0).astype(int).to_string())
    fp = q.drop_duplicates("game_id")
    d = (fp["first_play_at"] - fp["tip"]).dt.total_seconds() / 60
    print("\nfirst play minus listed tip (min), by season:")
    print(d.groupby(fp["season"]).describe(percentiles=[0.01, .05, .5, .95, .99]).round(1).to_string())
    print("games with first play > 60 min after listed tip:", int((d > 60).sum()),
          " before listed tip:", int((d < 0).sum()))
    # clock check (reported, filters nothing): Pinnacle's live total against
    # points so far + its pre-game close scaled by the game time left
    close = H.pinnacle_close(H.load(H.CACHE))
    ct = close[close["market"] == "totals"].set_index("game_id")["close_line"]
    p = q[(q["book"] == H.SHARP) & (q["market"] == "totals") & (q["phase"] == "live") & (q["period"] <= 4)]
    resid = p["line"] - p["h_pts"] - p["a_pts"] - p["game_id"].map(ct) * p["secs_left"] / 2880.0
    gm = resid.groupby(p["game_id"]).median().dropna()
    print("\nclock check, per game median of (Pinnacle live total - points so far - pre-game close x time "
          "left share):", gm.describe(percentiles=[.01, .5, .99]).round(1).to_dict(),
          " games beyond 25 points:", int((gm.abs() > 25).sum()))
    pin = q[q["book"] == H.SHARP]
    print("\nPinnacle in-play implied sum:", pin["implied_sum"].describe(percentiles=[.01, .5, .99]).round(4).to_dict(),
          " coherent share:", round(float(pin["coherent"].mean()), 4))
    print("all books coherent share:", q.groupby("book")["coherent"].mean().round(4).to_dict())
    has = q["pin_dt_s"].notna()
    print("\nquotes with Pinnacle within 60 s (same fetch), by book:")
    print(q.assign(has=has).groupby("book")["has"].mean().round(3).to_string())
    print("\nquote age at served (s):", ((q["served_at"] - q["stamp"]).dt.total_seconds())
          .describe(percentiles=[.5, .9, .99]).round(0).to_dict())
    print("last play before stamp (s):", ((q["stamp"] - q["last_play_at"]).dt.total_seconds())
          .describe(percentiles=[.5, .9, .99]).round(0).to_dict())
    print("points since stamp to served >0 share:", round(float((q["pts_since_stamp"] > 0).mean()), 4),
          " (served = newest stamp in fetch):", round(float((q["pts_since_stamp_newest"] > 0).mean()), 4),
          " quotes that flip between the two definitions:",
          int(((q["pts_since_stamp"] > 0) != (q["pts_since_stamp_newest"] > 0)).sum()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default=",".join(map(str, SEASONS)))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    seasons = tuple(int(s) for s in a.seasons.split(","))
    q, tl, notes = build(H.CACHE, seasons)
    report(q, notes)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    q.to_parquet(out, index=False)
    tl.to_parquet(out.parent / TIMELINE.name, index=False)
    print(f"\nwrote {out} ({len(q):,} rows) and {out.parent / TIMELINE.name} ({len(tl):,} plays)")


if __name__ == "__main__":
    main()
