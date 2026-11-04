"""NBA search: the in-play game-state model on 2026-27's live prices, and a late-game leader cell.

docs/nba_search_ingame27.md registers both steps and fixes every choice, committed BEFORE this lab
and before any cell was graded. This lab EMITS cells through the shared harness
(scripts/nba_game_harness, H, run_cells); the pass/fail script judges them
(scripts/nba_game2_verdict.py --house5, record 9.1's bars). IG-2's own functions
(scripts/nba_ingame_ig2, G) and the in-play table builder's (scripts/nba_ingame_data, D) are
called, never copied, wherever the doc says "unchanged".

24 cells (asserted):

  STEP 1   S1_IG2_live27: IG-2's 18 cells (moneyline, spread x Q1-Q2, Q3, Q4 6:00+ x EV >= .02,
           .05, .08) on 2026-27's live in-play prices, the model fit on 2020-21 .. 2025-26.
  STEP 2   S2_lead_held: the leader's moneyline, period 4, live, 0 < clock <= 6:00, lead 4-16,
           EV >= .02, .05, .08, first fresh quote; IG-2's model form refit on the last six
           minutes; graded on the held 2020-21 .. 2025-26 quotes. S2_lead_live27: the same three
           on 2026-27.

  LIVE ROWS  odds rows with source NULL (the worker's live fetches): fetch = created_at; served =
             created_at, never before the fetch's newest stamp; in play by the play-by-play
             clock AND stamped after the listed tip. Same stamp in a later fetch dropped for the
             decision (IG-2 unchanged); kept for "still offered at the next fetch".
  BAD ROWS   rule 1: a price strictly between -100 and +100, or not a number, is dropped;
             rule 2: the harness's coherent 1.00-1.15; rule 3: a deciding spread more than 6
             points from its paired Pinnacle number is dropped; rule 4: a deciding moneyline
             whose no-vig home chance is more than 0.25 from Pinnacle's paired no-vig is dropped.
  PLACEBO    200 runs, seeds 1-200: the model's disagreement with Pinnacle at Pinnacle's own
             state, moved between games on the same date and market (IG-2's placebo), built one
             frame at a time.

    PYTHONPATH=. python %TEMP%/q1trend/run_with_db.py scripts.nba_s_ingame27 --pull
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_ingame27 --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_ingame27 --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5

--smoke computes no result of any bet: every grade inside it reads scores replaced by random
numbers, only_random_scores() raises if a grade is handed real scores, and the quote tables'
final scores are blanked. Only the model fits read real scores, of seasons before the one they
score.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402
from scripts import nba_ingame_ig2 as G  # noqa: E402
from scripts.nba_game_market_lab import imp  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS"
SCRATCH = Path(tempfile.gettempdir()) / "nba_s" / "ingame27"
HELD_DIR = D.OUT_DIR                                  # the third search's folder: read only
HELD_QUOTES = D.OUT
TRAIN_HELD = HELD_DIR / "ig2_train_states.parquet"    # 2020-21 .. 2024-25, IG-2's graded run
TRAIN_2026 = HELD_DIR / "ig2_train_states_2026.parquet"
PRIOR_HELD = HELD_DIR / "ig2_prior.parquet"
LATE_TRAIN = SCRATCH / "late_train_states_v2.parquet"      # v2: rule 6 applied (doc 3.2)
HELD_RESTATED = SCRATCH / "held_h2h_restated.parquet"     # the held quotes, this lab's state join
PULL_FILES = {"games": "games_2027.parquet", "odds": "odds_2027.parquet",
              "pbp": "pbp_2027.parquet", "box": "pbp_box_2027.parquet"}

LIVE = 2027                                           # 2026-27, ending-year label
HELD_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
HELD_GRADED = (*H.CHOOSE, H.CONFIRM)                  # 2021-22 .. 2025-26
FAM_S1, FAM_S2H, FAM_S2L = "S1_IG2_live27", "S2_lead_held", "S2_lead_live27"
PT_LATE = "Q4-last6"
LEADER = "leader"
CUTS = G.CUTS                                         # 0.02, 0.05, 0.08
LOWEST = 0.0                                          # the lowest cut's lower band starts here
LATE_CLOCK_S = 360.0
LEAD_MIN, LEAD_MAX = 4, 16
LATE_TRAIN_SECS = (0, 360)
MAX_SPREAD_GAP, MAX_ML_GAP = 6.0, 0.25
EARLY_CLOCK_MIN = 15.0
JUMP_MIN = 45.0
STALL_S = 180.0
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
DIFFER_SEEDS = tuple(range(1, 21))
EXPECTED = {FAM_S1: 18, FAM_S2H: 3, FAM_S2L: 3}
TARGET_BETS = 200
BLINDED = "scores_are_random"
PULL_CHUNK, PULL_PAUSE_S = 60, 1.0
QUIET_UTC = ((10, 0), (10, 45))


def log(msg: str, t0: float | None = None) -> None:
    print(msg + (f" ({time.time() - t0:.0f}s)" if t0 is not None else ""), flush=True)


# ── the cells ───────────────────────────────────────────────────────────────

def cell_specs() -> list[tuple]:
    """(family, point, market, side, cut_index, cut) for every judged cell."""
    out = [(FAM_S1, ph, mk, "model", k, c) for ph in G.PHASES for mk in G.MARKETS
           for k, c in enumerate(CUTS)]
    out += [(fam, PT_LATE, "h2h", LEADER, k, c) for fam in (FAM_S2H, FAM_S2L) for k, c in enumerate(CUTS)]
    return out


def check_rows(rows: list[dict]) -> None:
    got = sorted((r["family"], r["point"], r["market"], r["side"], int(r["cut_index"]), float(r["cut"]))
                 for r in rows)
    want = sorted((f, p, m, s, int(k), float(c)) for f, p, m, s, k, c in cell_specs())
    assert got == want, "the cells emitted are not the cells registered"


# ── impossible numbers (doc section 3) ──────────────────────────────────────

def impossible_price(p) -> np.ndarray:
    """Rule 1: strictly between -100 and +100, or not a number."""
    a = pd.to_numeric(pd.Series(np.asarray(p, dtype=object)), errors="coerce").to_numpy(float)
    return ~np.isfinite(a) | ((a > -100.0) & (a < 100.0))


def pin_gap_bad(q: pd.DataFrame) -> pd.Series:
    """Rules 3 and 4: a deciding quote paired with a coherent Pinnacle quote whose spread is more
    than MAX_SPREAD_GAP points, or whose no-vig home chance is more than MAX_ML_GAP, from
    Pinnacle's."""
    dec = q["book"].isin(H.BETTABLE) & q["pin_fa"].notna()
    sp = dec & (q["market"] == "spreads") & ((q["line"] - q["pin_line"]).abs() > MAX_SPREAD_GAP)
    ml = dec & (q["market"] == "h2h") & ((q["fa"] - q["pin_fa"]).abs() > MAX_ML_GAP)
    return sp | ml


# ── the 2026-27 live rows (doc section 2) ───────────────────────────────────

def games_frame(g: pd.DataFrame) -> pd.DataFrame:
    """Pulled `games` rows in H.load_games' shape (final games only)."""
    g = g[g["home_score"].notna() & g["commence_time"].notna()].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True, format="mixed")
    g["season"] = g["season"].astype(int)
    for c in ("home_score", "away_score"):
        g[c] = pd.to_numeric(g[c]).astype(float)
    return g[["game_id", "season", "game_date", "tip", "home_team", "away_team",
              "home_score", "away_score"]].reset_index(drop=True)


def served_times(o: pd.DataFrame) -> pd.DataFrame:
    """fetch_at = created_at; served_newest = the fetch's newest stamp; served_at = created_at,
    never before it (doc section 2)."""
    o = o.assign(fetch_at=o["created_at"])
    newest = o.groupby("fetch_at")["snapshot_at"].transform("max")
    served = o["fetch_at"].where(o["fetch_at"] >= newest, newest)
    return o.assign(served_newest=newest, served_at=served)


def live_quotes(odds: pd.DataFrame, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """(quotes, raw, dropped, notes). quotes: in-play candidates in nba_ingame_data.load_quotes'
    shape, same stamp in a later fetch dropped. raw: the same rows before that drop (still
    offered at the next fetch). dropped: rule-1 rows."""
    notes = {"rows_pulled": int(len(odds)),
             "pulled_by_source_label": {f"{s}|{lb}": int(n) for (s, lb), n in
                                        odds.groupby([odds["source"].fillna("NULL"), "snapshot_type"]).size().items()}}
    o = odds[odds["market"].isin(G.MARKETS) & odds["source"].isna()].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o["created_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    o = served_times(o)
    o = o[o["snapshot_at"] >= o["tip"] - pd.Timedelta(minutes=D.PREFILTER_MIN)].copy()
    o = o.rename(columns={"bookmaker": "book", "snapshot_at": "stamp", "snapshot_type": "label"})
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        if c in o:
            o[c] = pd.to_numeric(o[c], errors="coerce")
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"], np.nan)
    o["price_a"], o["price_b"] = o["home_price"], o["away_price"]
    bad = impossible_price(o["price_a"]) | impossible_price(o["price_b"])
    dropped = o[bad].copy()
    o = o[~bad].copy()
    ia, ib = imp(o["price_a"]), imp(o["price_b"])
    o["implied_sum"] = ia + ib
    o["coherent"] = (o["implied_sum"] >= H.COHERENT[0]) & (o["implied_sum"] <= H.COHERENT[1])
    o["fa"] = ia / (ia + ib)
    keep = ["game_id", "season", "game_date", "tip", "market", "book", "label", "stamp", "fetch_at",
            "served_at", "served_newest", "line", "price_a", "price_b", "implied_sum", "coherent", "fa"]
    o = o[keep].reset_index(drop=True)
    raw = o.copy()
    k = ["game_id", "market", "book", "stamp", "fetch_at"]
    notes["rows_candidate"] = int(len(o))
    notes["rows_exact_duplicate"] = int(o.duplicated(k).sum())
    o = o.drop_duplicates(k)
    k2 = ["game_id", "market", "book", "stamp"]
    o = o.sort_values([*k2, "fetch_at"])
    notes["rows_same_stamp_later_fetch"] = int(o.duplicated(k2).sum())
    o = o.drop_duplicates(k2, keep="first").reset_index(drop=True)
    notes["rule1_dropped"] = int(len(dropped))
    return o, raw, dropped, notes


def _plain(df: pd.DataFrame) -> list[dict]:
    """Records with every missing value as None (a NaN is truthy, and is_fga reads
    `not shooting_play`)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


def live_plays(pbp: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """nba_pbp rows -> nba_ingame_data's per-play frame, wild-wallclock games dropped."""
    p = pbp.sort_values(["game_id", "play_no"]).copy()
    p["wallclock"] = pd.to_datetime(p["wallclock"], utc=True, format="mixed")
    return D.drop_wild_wallclocks(D.plays_frame(_plain(p)))


def box_prior_minutes(box: pd.DataFrame) -> pd.DataFrame:
    """(espn_game_id, athlete_id, prior_min) from nba_pbp_box rows carrying season and game_date:
    minutes per game in the player's earlier games of the same season, else his previous
    season's average, else 0 -- nba_ingame_data.prior_minutes, read from nba_pbp_box (the rows
    the ingestor wrote from the release files that function read)."""
    b = box.rename(columns={"espn_id": "athlete_id"}).copy()
    b["athlete_id"] = pd.to_numeric(b["athlete_id"], errors="coerce").astype("int64")
    b["season"] = b["season"].astype(int)
    b["m"] = pd.to_numeric(b["minutes"], errors="coerce")
    played = b["m"].fillna(0) > 0
    b = b.sort_values(["athlete_id", "game_date", "game_id"])
    b["_m"] = b["m"].where(played)
    b["prior_min"] = b.groupby(["athlete_id", "season"])["_m"].transform(lambda x: x.shift(1).expanding().mean())
    last = b[played].groupby(["athlete_id", "season"])["m"].mean().rename("last_season_min").reset_index()
    last["season"] = last["season"] + 1
    b = b.merge(last, on=["athlete_id", "season"], how="left")
    b["prior_min"] = b["prior_min"].fillna(b["last_season_min"]).fillna(0.0)
    return b[["espn_game_id", "athlete_id", "prior_min"]].astype({"espn_game_id": "int64"})


def box_top_players(box: pd.DataFrame, prior: pd.DataFrame) -> pd.DataFrame:
    """nba_ingame_data.top_players on nba_pbp_box rows (side is already our H / A)."""
    b = box.rename(columns={"espn_id": "athlete_id"}).copy()
    b["athlete_id"] = pd.to_numeric(b["athlete_id"], errors="coerce").astype("int64")
    b["espn_game_id"] = b["espn_game_id"].astype("int64")
    return D.top_players(b[["game_id", "espn_game_id", "athlete_id", "side", "starter"]], prior)


def all_box(scratch: Path = SCRATCH) -> pd.DataFrame:
    """nba_pbp_box for 2019-20 .. 2026-27 with each game's date: the held pull and the 2026-27
    pull (regular season only)."""
    hg = pd.read_parquet(scratch / HELD_PULL["games"])
    hb = pd.read_parquet(scratch / HELD_PULL["box"]).merge(hg[["game_id", "game_date"]], on="game_id", how="left")
    lb = pd.read_parquet(scratch / PULL_FILES["box"])
    lg = pd.read_parquet(scratch / PULL_FILES["games"])[["game_id", "game_date"]]
    lb = lb.merge(lg, on="game_id", how="left")
    cols = ["espn_game_id", "espn_id", "game_id", "season", "side", "starter", "minutes", "game_date"]
    return pd.concat([hb[cols], lb[cols]], ignore_index=True).drop_duplicates(["espn_game_id", "espn_id"])


TL_NOT_STATE = ("game_id", "wc", "play_no", "type_text")


def state_at_stable(q: pd.DataFrame, tl: pd.DataFrame, at: str, cols, suffix: str = "") -> pd.DataFrame:
    """Record 7.1's STATE: for each quote, the timeline row of the LAST play, in play order, with
    wallclock <= q[at] (same game). nba_ingame_data.state_at re-sorts by wallclock alone with an
    unstable sort and drops play_no, so among plays logged in the same second it can take one
    that is not the last (doc 3.2, 2026-11-04). This keeps play_no and sorts by (wallclock,
    play_no), stable; merge_asof then takes the last of the tied rows."""
    left = q[["game_id", at]].reset_index().rename(columns={at: "_t"}).dropna(subset=["_t"])
    left["_t"] = left["_t"].astype("datetime64[ns, UTC]")
    left = left.sort_values("_t", kind="stable")
    right = tl[["game_id", "wc", "play_no", *cols]].dropna(subset=["wc"])
    right = right.assign(wc=right["wc"].astype("datetime64[ns, UTC]")).sort_values(["wc", "play_no"], kind="stable")
    m = pd.merge_asof(left, right, left_on="_t", right_on="wc", by="game_id", direction="backward",
                      allow_exact_matches=True)
    out = m.set_index("index").reindex(q.index)[list(cols)]
    return out.add_suffix(suffix) if suffix else out


def derived_state_cols(tl: pd.DataFrame) -> list[str]:
    """Every column restate() writes, so a stored table can be re-joined from scratch."""
    sc = [c for c in tl.columns if c not in TL_NOT_STATE]
    extra = [f"{x}{suf}" for suf in ("_m60", "_m120", "_served", "_served_newest") for x in ("h_pts", "a_pts")]
    return sc + ["secs_left", "last_play_at", *extra, "pts_since_stamp", "pts_since_stamp_newest"]


def restate(q: pd.DataFrame, tl: pd.DataFrame) -> pd.DataFrame:
    """The state block of nba_ingame_data.build, through state_at_stable: the game state at the
    stamp, the time left, the last logged play, the score 60 and 120 s before the stamp and at
    serving, and the points scored between stamp and serving. A stored table's own state
    columns are dropped first."""
    q = q.drop(columns=[c for c in derived_state_cols(tl) if c in q]).reset_index(drop=True)
    state_cols = [c for c in tl.columns if c not in TL_NOT_STATE]
    q = pd.concat([q, state_at_stable(q, tl, "stamp", state_cols)], axis=1)
    reg = q["period"] <= 4
    q["secs_left"] = np.where(reg, q["clock_s"] + 720 * (4 - q["period"]), q["clock_s"])
    q["last_play_at"] = state_at_stable(q, tl.assign(lp=tl["wc"]), "stamp", ["lp"])["lp"]
    for at, suf in (("stamp_m60", "_m60"), ("stamp_m120", "_m120"), ("served_at", "_served"),
                    ("served_newest", "_served_newest")):
        if at.startswith("stamp_m"):
            q[at] = q["stamp"] - pd.Timedelta(seconds=int(at[7:]))
        q = pd.concat([q, state_at_stable(q, tl, at, ["h_pts", "a_pts"], suf).fillna(0)], axis=1)
    q = q.drop(columns=["stamp_m60", "stamp_m120"])
    q["pts_since_stamp"] = (q["h_pts_served"] + q["a_pts_served"]) - (q["h_pts"] + q["a_pts"])
    q["pts_since_stamp_newest"] = (q["h_pts_served_newest"] + q["a_pts_served_newest"]) - (q["h_pts"] + q["a_pts"])
    return q


def in_play_state(q: pd.DataFrame, plays: pd.DataFrame, top: pd.DataFrame,
                  games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """nba_ingame_data.build after its quote load, with this lab's own state join (restate),
    plus the listed-tip bound."""
    tl = D.timeline(plays, top)
    bounds = D.phase_bounds(plays)
    first = bounds.groupby("game_id")["start"].min().rename("first_play_at")
    last = bounds.sort_values("period").groupby("game_id").tail(1).set_index("game_id")["end"].rename("final_end_at")
    q = q.merge(first.reset_index(), on="game_id", how="left").merge(last.reset_index(), on="game_id", how="left")
    q, counts = D.keep_in_play(q, bounds)
    notes = dict(counts)
    early = q["stamp"] <= q["tip"]
    notes["in_play_by_clock_not_after_listed_tip"] = int(early.sum())
    q = q[~early].reset_index(drop=True)
    q = restate(q, tl)
    q["halftime"] = q["phase"] == "halftime"
    q = D.attach_pinnacle(q)
    g = games.set_index("game_id")
    q["final_home"] = q["game_id"].map(g["home_score"])
    q["final_away"] = q["game_id"].map(g["away_score"])
    notes["rows_out"] = int(len(q))
    return q, tl, notes


def jump_games(pbp: pd.DataFrame, minutes: float = JUMP_MIN) -> dict:
    """Rule 6 (doc 3.2, 2026-11-04): games with two consecutive plays, in play order, whose ESPN
    wallclocks are `minutes` or more apart, either way: game -> the largest such jump (minutes,
    signed). A clock that shifts part of a game, or a feed that stalls and back-fills, shows as
    such a jump; rule 5 sees only the first play."""
    p = pbp[["game_id", "play_no", "wallclock"]].copy()
    p["wc"] = pd.to_datetime(p["wallclock"], utc=True, format="mixed", errors="coerce")
    p = p.dropna(subset=["wc"]).sort_values(["game_id", "play_no"], kind="stable")
    d = p.groupby("game_id")["wc"].diff().dt.total_seconds() / 60.0
    p = p.assign(d=d)
    big = p[p["d"].abs() >= minutes]
    if big.empty:
        return {}
    idx = big.groupby("game_id")["d"].apply(lambda x: x.abs().idxmax())
    return {g: round(float(big.loc[i, "d"]), 1) for g, i in idx.items()}


def apply_bad_rows(q: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rules 3 and 4 on a table carrying the Pinnacle pairing; (kept, dropped)."""
    bad = pin_gap_bad(q)
    return q[~bad].reset_index(drop=True), q[bad].copy()


class Live:
    """Everything the 2026-27 side reads."""

    def __init__(self, games, q, raw, tl, dropped1, dropped34, notes, sched):
        self.games, self.q, self.raw, self.tl = games, q, raw, tl
        self.dropped1, self.dropped34, self.notes, self.sched = dropped1, dropped34, notes, sched


def load_live(scratch: Path = SCRATCH) -> Live:
    """The pulled 2026-27 rows -> the in-play table IG-2's functions read."""
    p = {k: pd.read_parquet(scratch / v) for k, v in PULL_FILES.items()}
    sched = p["games"][["game_id", "game_date", "home_score"]].copy()
    games = games_frame(p["games"])
    games = games[games["game_id"].isin(set(p["pbp"]["game_id"]))].reset_index(drop=True)
    q, raw, dropped1, notes = live_quotes(p["odds"], games)
    plays, wild = live_plays(p["pbp"][p["pbp"]["game_id"].isin(set(games["game_id"]))])
    notes["games_clock_broken"] = wild
    top = box_top_players(p["box"][p["box"]["game_id"].isin(set(games["game_id"]))], box_prior_minutes(all_box(scratch)))
    q, tl, n2 = in_play_state(q, plays, top, games)
    notes.update(n2)
    q, early = drop_early_clocks(q)
    notes["games_first_play_before_listed_tip"] = early
    jumps = jump_games(p["pbp"][p["pbp"]["game_id"].isin(set(games["game_id"]))])
    notes["games_wallclock_jump"] = jumps
    notes["games_wallclock_jump_dropped"] = sorted(set(jumps) & set(q["game_id"]))
    q = q[~q["game_id"].isin(set(jumps))].reset_index(drop=True)
    q_all = q
    q, dropped34 = apply_bad_rows(q)
    notes["rule34_dropped"] = int(len(dropped34))
    lv = Live(games, q, raw, tl[["game_id", "wc", "h_pts", "a_pts", "period", "clock_s"]], dropped1, dropped34, notes, sched)
    lv.q_all = q_all
    return lv


def drop_early_clocks(q: pd.DataFrame, minutes: float = EARLY_CLOCK_MIN) -> tuple[pd.DataFrame, dict]:
    """Rule 5 (doc 3.1, 2026-11-03): a game whose first ESPN play is more than `minutes` before
    its listed tip is left out whole. A game does not start before its listed tip; its ESPN clock
    is early, so the state joined to a quote would come from plays after the quote."""
    fp = q.drop_duplicates("game_id").set_index("game_id")
    off = (fp["first_play_at"] - fp["tip"]).dt.total_seconds() / 60.0
    bad = off[off < -minutes]
    return q[~q["game_id"].isin(set(bad.index))].reset_index(drop=True), {k: round(float(v), 1) for k, v in bad.items()}


def load_held(markets=("h2h",), refresh: bool = False):
    """The held in-play table with this lab's own state join (held_restated), rules 1, 3, 4, 5
    and 6 applied; (kept, rule-1 rows, rule-3/4 rows, the table before rules 3-4, notes)."""
    q, notes = held_restated(refresh=refresh)
    q = q[q["market"].isin(markets)].copy()
    q, early = drop_early_clocks(q)
    assert not early, f"held games with an early ESPN clock: {early}"
    jumps = notes["games_wallclock_jump"]
    notes["games_wallclock_jump_in_table"] = sorted(set(jumps) & set(q["game_id"]))
    q = q[~q["game_id"].isin(set(jumps))]
    bad1 = impossible_price(q["price_a"]) | impossible_price(q["price_b"])
    d1 = q[bad1].copy()
    q = q[~bad1].reset_index(drop=True)
    q_all = q
    q, d34 = apply_bad_rows(q)
    return q, d1, d34, q_all, notes


# ── the models ──────────────────────────────────────────────────────────────

def step1_train() -> pd.DataFrame:
    """IG-2's stored training states, 2020-21 .. 2025-26 (read, never rebuilt into its folder)."""
    t = pd.concat([pd.read_parquet(TRAIN_HELD), pd.read_parquet(TRAIN_2026)], ignore_index=True)
    assert sorted(t["season"].unique()) == list(HELD_SEASONS), sorted(t["season"].unique())
    return t


TRAIN_KEEP = ["game_id", "season", "period", "clock_s", "secs_left", "h_pts", "a_pts", "mu_pre",
              "final_margin", "f", "m", *G.FEATURES]


def held_timelines(cache: Path = H.CACHE, seasons=HELD_SEASONS, scratch: Path = SCRATCH):
    """season -> (timeline with top players' fouls, games whose play-by-play final equals the
    official final), from the held nba_pbp pull through nba_ingame_data's own functions (as
    IG-2's training_states built them from the release files)."""
    games = H.load_games(cache)
    pbp = pd.read_parquet(scratch / HELD_PULL["pbp"])
    pbp = pbp[pbp["season_type"] == 2]
    prior = box_prior_minutes(all_box(scratch))
    box = pd.read_parquet(scratch / HELD_PULL["box"])
    out = {}
    for s in seasons:
        plays, wild = live_plays(pbp[pbp["season"] == s])
        top = box_top_players(box[(box["season"] == s) & box["game_id"].isin(set(plays["game_id"]))], prior)
        tl = D.timeline(plays, top)
        fin = plays.groupby(["game_id", "team_side"])["points"].sum().unstack()
        gg = games.set_index("game_id").reindex(fin.index)
        ok = set(fin.index[(fin[D.HOME] == gg["home_score"]) & (fin[D.AWAY] == gg["away_score"])])
        out[s] = (tl, ok, len(wild))
    return out, games


def states_from(tl: pd.DataFrame, ok: set, games: pd.DataFrame, mu: pd.DataFrame, season: int,
                secs) -> pd.DataFrame:
    """IG-2's training_states body for one season and one window of time left."""
    st = G.grid_states(tl, secs=secs)
    st = st[st["game_id"].isin(ok)].merge(mu[["game_id", "mu_pre"]], on="game_id", how="inner")
    g2 = games.set_index("game_id")
    st["season"] = season
    st["final_margin"] = st["game_id"].map(g2["home_score"] - g2["away_score"])
    return G.features(st)[TRAIN_KEEP]


def held_build(cache: Path = H.CACHE, seasons=HELD_SEASONS) -> dict:
    """One pass over the held play-by-play pull, written to scratch only:
      * step 2's training states: IG-2's grid (every 30 s of game time) with 6:00 or less left in
        regulation, games with a rule-6 clock jump left out (LATE_TRAIN);
      * the held quotes' game state re-joined with state_at_stable (HELD_RESTATED, moneylines),
        and how many held quotes of every market read a different score than the stored table
        (IG-2's graded run used the stored one);
      * IG-2's own window (6:00 to 47:30 left) rebuilt for 2024-25 and compared with IG-2's
        stored states (`reproduce_2025`)."""
    t0 = time.time()
    tls, games = held_timelines(cache, seasons)
    pbp = pd.read_parquet(SCRATCH / HELD_PULL["pbp"], columns=["game_id", "play_no", "wallclock", "season_type"])
    jumps = jump_games(pbp[pbp["season_type"] == 2])
    mu = pd.read_parquet(PRIOR_HELD)
    held = pd.read_parquet(HELD_QUOTES)
    frames, qs, notes = [], [], {"games_wallclock_jump": jumps, "late_states": {}, "restate": {}}
    for s in seasons:
        tl, ok, wild = tls[s]
        st = states_from(tl, ok - set(jumps), games, mu, s, LATE_TRAIN_SECS)
        frames.append(st)
        notes["late_states"][str(s)] = {"games_kept": int(st["game_id"].nunique()), "states": int(len(st)),
                                        "games_clock_broken": wild, "games_final_matches": len(ok),
                                        "games_jump_left_out": len((ok & set(jumps)))}
        hq = held[held["season"] == s]
        rq = restate(hq, tl)
        moved = ~((rq["h_pts"].to_numpy() == hq["h_pts"].to_numpy()) & (rq["a_pts"].to_numpy() == hq["a_pts"].to_numpy()))
        notes["restate"][str(s)] = {"quotes": int(len(hq)), "score_differs": int(moved.sum()),
                                    "no_state_in_pull": int(rq["h_pts"].isna().sum())}
        qs.append(rq[rq["market"] == "h2h"])
        log(f"held season {s}: {notes['late_states'][str(s)]} {notes['restate'][str(s)]}", t0)
    r = pd.concat([pd.DataFrame(v, index=[k]) for k, v in notes["restate"].items()])
    notes["restate_all"] = {"quotes": int(r["quotes"].sum()), "score_differs": int(r["score_differs"].sum()),
                            "share": float(r["score_differs"].sum() / r["quotes"].sum())}
    s = 2025
    mine = states_from(*tls[s][:2], games, mu, s, G.TRAIN_SECS)
    ig2 = pd.read_parquet(TRAIN_HELD)
    ig2 = ig2[ig2["season"] == s]
    j = mine.merge(ig2, on=["game_id", "secs_left", "h_pts", "a_pts"], suffixes=("", "_ig2"))
    notes["reproduce_2025"] = {"states_rebuilt": int(len(mine)), "states_ig2": int(len(ig2)),
                               "matched_on_game_time_and_score": int(len(j)),
                               "features_equal_share": {c: float(np.isclose(j[c], j[f"{c}_ig2"]).mean())
                                                        for c in G.FEATURES}}
    log(f"held build done: {notes['restate_all']}; reproduce {notes['reproduce_2025']}", t0)
    LATE_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_parquet(LATE_TRAIN, index=False)
    pd.concat(qs, ignore_index=True).to_parquet(HELD_RESTATED, index=False)
    for path in (LATE_TRAIN, HELD_RESTATED):
        path.with_suffix(".json").write_text(json.dumps(notes, indent=1, default=str), encoding="utf-8")
    return notes


def late_states(cache: Path = H.CACHE, refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """Step 2's training states (held_build), read from scratch once built."""
    if refresh or not LATE_TRAIN.exists():
        held_build(cache)
    return pd.read_parquet(LATE_TRAIN), json.loads(LATE_TRAIN.with_suffix(".json").read_text(encoding="utf-8"))


def held_restated(cache: Path = H.CACHE, refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """The held moneyline quotes with this lab's state join (held_build), read from scratch."""
    if refresh or not HELD_RESTATED.exists():
        held_build(cache)
    return pd.read_parquet(HELD_RESTATED), json.loads(HELD_RESTATED.with_suffix(".json").read_text(encoding="utf-8"))


def live_prior(cache: Path, live: Live) -> pd.DataFrame:
    """(game_id, season, mu_pre) for 2026-27: Pinnacle's last pre-tip coherent spread from the
    live rows, solved through the harness's empirical distribution fit on 2020-21 .. 2025-26."""
    hist = H.load(cache, seasons=HELD_SEASONS)
    close_h = H.pinnacle_close(hist)
    dist = H.dist_by_season(H.close_resid(close_h, hist.games), [LIVE])
    o = pd.read_parquet(SCRATCH / PULL_FILES["odds"])
    o = o[(o["bookmaker"] == H.SHARP) & o["source"].isna() & o["market"].isin(H.MARKETS)].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o["created_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o = o.merge(live.games[["game_id", "season", "game_date", "tip"]], on="game_id")
    o["fetch_at"] = o["created_at"]
    qq = H.frame_quotes(o)
    close = H.pinnacle_close(H.Data(games=live.games, quotes=qq, fetches=pd.DataFrame()))
    c = close[close["market"] == "spreads"].copy()
    sig = np.array([dist[(LIVE, "spreads")]] * len(c), dtype=object)
    c["mu_pre"] = H.solve_any(G.threshold("spreads", c["close_line"]), c["close_fa"].to_numpy(), sig)
    return c[["game_id", "season", "mu_pre"]].reset_index(drop=True)


# ── decisions ───────────────────────────────────────────────────────────────

def late_label(q: pd.DataFrame) -> pd.Series:
    """PT_LATE where the quote's own state is in step 2's population: period 4, live,
    0 < clock <= 6:00, lead 4-16; else ''."""
    lead = (q["h_pts"] - q["a_pts"]).abs()
    m = ((q["period"] == 4) & (q["phase"] == "live") & (q["clock_s"] > 0) & (q["clock_s"] <= LATE_CLOCK_S)
         & (lead >= LEAD_MIN) & (lead <= LEAD_MAX))
    return pd.Series(np.where(m, PT_LATE, ""), index=q.index)


def late_table(q: pd.DataFrame) -> pd.DataFrame:
    """The h2h quotes with Pinnacle's freshness attached and step 2's label as the phase."""
    q = q[q["market"] == "h2h"].copy()
    if "pin_pts_since" not in q:
        q = G.with_pin_freshness(q)
    return q.assign(phase_ig2=late_label(q))


def late_decisions(q: pd.DataFrame) -> pd.DataFrame:
    """Step 2: the first fetch per game holding an eligible deciding moneyline quote in the
    population (IG-2's eligibility and first-fetch rule, unchanged)."""
    el = G.eligible(q)
    el = el[el["market"] == "h2h"]
    return G.decision_quotes(el)


def leader_side(df: pd.DataFrame) -> np.ndarray:
    return np.where(df["h_pts"] > df["a_pts"], "home", "away")


def step1_table(q: pd.DataFrame) -> pd.DataFrame:
    q = q[q["market"].isin(G.MARKETS)].copy()
    return G.with_pin_freshness(q).assign(phase_ig2=lambda d: G.phase_label(d))


# ── frames for the cells ────────────────────────────────────────────────────

class Frames:
    """One phase's offers: cand (the model), neutral (Pinnacle's live no-vig), and a placebo
    builder seed -> frame."""

    def __init__(self, cand, neutral, dev, build, off):
        self.cand, self.neutral, self.dev, self.build, self.off = cand, neutral, dev, build, off

    def placebo(self, seeds) -> G5.LazyFrames:
        return G5.LazyFrames(seeds, self.build)


def _strength(first: pd.DataFrame) -> np.ndarray:
    mu_f, _ = G.market_fair_inplay(first.assign(sd=first["pin_sd"]))
    return np.where(first["market"] == "spreads", first["pin_mean"] - mu_f,
                    G._logit(first["pin_p_home"]) - G._logit(first["pin_fa"]))


def step1_frames(dec: pd.DataFrame, models: dict, games: pd.DataFrame) -> Frames:
    """G.grid_frames, with the placebo built on demand from any seed (IG-2 built seeds 0..19)."""
    d = G.apply_model(G.features(dec), models)
    off = G.offer_rows(d)
    mu_m, ph_m = G.market_fair_inplay(off)
    cand = G.with_side_pick(G.priced(off, off["mean"], off["sd"], off["p_home"]))
    neutral = G.priced(off, mu_m, off["sd"], ph_m).assign(mu=mu_m, p_home=ph_m)
    neutral = neutral.drop(columns="side_pick", errors="ignore").merge(
        cand[["game_id", "market", "side_pick"]].drop_duplicates(["game_id", "market"]),
        on=["game_id", "market"], how="left")
    first = off.drop_duplicates(["game_id", "market"])
    dev = pd.DataFrame({"game_id": first["game_id"].to_numpy(), "market": first["market"].to_numpy(),
                        "strength": _strength(first)})
    sp = (off["market"] == "spreads").to_numpy()
    logit_pin = G._logit(off["pin_fa"])

    def build(seed: int) -> pd.DataFrame:
        sh = H.shuffle_within_date(dev, games, np.random.default_rng(seed))
        s = off[["game_id", "market"]].merge(sh, on=["game_id", "market"], how="left")["strength"].to_numpy()
        mean_p = np.where(sp, mu_m + s, np.nan)
        ph_p = np.where(sp, np.nan, G._expit(logit_pin + s))
        return G.with_side_pick(G.priced(off, mean_p, off["sd"], ph_p))
    return Frames(cand, neutral, dev, build, off)


def step2_frames(dec: pd.DataFrame, models: dict, games: pd.DataFrame) -> Frames:
    """The leader's moneyline: offers priced by the refit model, side fixed to the leader."""
    d = G.apply_model(G.features(dec), models)
    off = G.offer_rows(d)
    lead = leader_side(off)
    mu_m, ph_m = G.market_fair_inplay(off)
    cand = G.priced(off, off["mean"], off["sd"], off["p_home"]).assign(side_pick=lead)
    neutral = G.priced(off, mu_m, off["sd"], ph_m).assign(mu=mu_m, p_home=ph_m, side_pick=lead)
    first = off.drop_duplicates(["game_id", "market"])
    dev = pd.DataFrame({"game_id": first["game_id"].to_numpy(), "market": first["market"].to_numpy(),
                        "strength": _strength(first)})
    logit_pin = G._logit(off["pin_fa"])
    nan = np.full(len(off), np.nan)

    def build(seed: int) -> pd.DataFrame:
        sh = H.shuffle_within_date(dev, games, np.random.default_rng(seed))
        s = off[["game_id", "market"]].merge(sh, on=["game_id", "market"], how="left")["strength"].to_numpy()
        return G.priced(off, nan, off["sd"], G._expit(logit_pin + s)).assign(side_pick=lead)
    return Frames(cand, neutral, dev, build, off)


def phase_decisions(qt: pd.DataFrame, prior: pd.DataFrame, models: dict, step: int) -> pd.DataFrame:
    """Decision quotes with the prior and the model at Pinnacle's state attached."""
    if step == 1:
        dec = G.decision_quotes(G.eligible(qt))
    else:
        dec = late_decisions(qt)
    dec = dec.merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
    if dec.empty:
        return dec
    pin_m = G.pin_state_model(qt, dec, models, prior)
    return dec.merge(pin_m, on=["game_id", "market", "phase_ig2"], how="inner")


def empty_data(games: pd.DataFrame) -> H.Data:
    """IG-2's run_grid's Data: games only (in play there is no slate fetch frame)."""
    empty_q = pd.DataFrame({c: pd.Series(dtype=object) for c in
                            ("game_id", "season", "game_date", "tip", "market", "book", "snapshot_at",
                             "line", "price_a", "price_b", "coherent")})
    empty_q["fetch_at"] = pd.Series(dtype="datetime64[ns, UTC]")
    empty_f = pd.DataFrame({"game_id": pd.Series(dtype=object), "tip": pd.Series(dtype="datetime64[ns, UTC]"),
                            "fetch_at": pd.Series(dtype="datetime64[ns, UTC]"),
                            "lead_min": pd.Series(dtype=float)})
    return H.Data(games=games, quotes=empty_q, fetches=empty_f)


# ── still offered at the next fetch (doc section 2) ─────────────────────────

def still_offered(bets: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Per bet: `still` (same book, next fetch holding any row of the game, same market, same
    number for a spread, price on the bet's side at least as good) and `identical` (the same
    price). Read on raw rows, before the same-stamp drop."""
    if len(bets) == 0:
        return pd.DataFrame({"still": pd.Series(dtype=bool), "identical": pd.Series(dtype=bool)})
    f = raw[["game_id", "fetch_at"]].drop_duplicates().sort_values(["game_id", "fetch_at"])
    f["next_fetch"] = f.groupby("game_id")["fetch_at"].shift(-1)
    b = bets.reset_index()[["index", "game_id", "market", "book", "side", "line", "price", "fetch_at"]]
    b = b.merge(f, on=["game_id", "fetch_at"], how="left")
    r = raw[["game_id", "market", "book", "fetch_at", "line", "price_a", "price_b"]].rename(
        columns={"fetch_at": "next_fetch", "line": "line_next"})
    x = b.merge(r, on=["game_id", "market", "book", "next_fetch"], how="left")
    side_a = x["side"].isin(["home", "over"])
    p_next = np.where(side_a, x["price_a"], x["price_b"])
    same_no = np.where(x["market"] == "h2h", True,
                       np.isclose(x["line"].fillna(0), x["line_next"].fillna(np.inf)))
    ok = same_no & np.isfinite(p_next.astype(float))
    still = ok & (np.nan_to_num(p_next.astype(float), nan=-1e9) >= x["price"].to_numpy(float))
    ident = ok & np.isclose(np.nan_to_num(p_next.astype(float), nan=-1e9), x["price"].to_numpy(float))
    out = pd.DataFrame({"index": x["index"], "still": still, "identical": ident})
    out = out.groupby("index")[["still", "identical"]].any()
    return out.reindex(bets.index, fill_value=False)


# ── reported beside each cell (doc 3.2) ──────────────────────────────────────

def decisions_changed(q_kept: pd.DataFrame, q_all: pd.DataFrame, decide) -> dict:
    """How many decisions (game x market x phase) rules 3 and 4 change: decided with and without
    the rules, decided only one way, and decided at a different fetch."""
    keys = ["game_id", "market", "phase_ig2"]
    a = decide(q_kept).drop_duplicates(keys)[keys + ["fetch_at"]]
    b = decide(q_all).drop_duplicates(keys)[keys + ["fetch_at"]]
    m = a.merge(b, on=keys, how="outer", suffixes=("_with", "_without"), indicator=True)
    both = m["_merge"] == "both"
    return {"decisions_with_rules": int(len(a)), "decisions_without_rules": int(len(b)),
            "only_without": int((m["_merge"] == "right_only").sum()),
            "only_with": int((m["_merge"] == "left_only").sum()),
            "different_fetch": int((both & (m["fetch_at_with"] != m["fetch_at_without"])).sum())}


def step1_decide(q: pd.DataFrame) -> pd.DataFrame:
    return G.decision_quotes(G.eligible(step1_table(q)))


def step2_decide(q: pd.DataFrame) -> pd.DataFrame:
    return late_decisions(late_table(q))


def stall_stats(picks: pd.DataFrame) -> dict:
    """Seconds from the last play ESPN logged to the decision quote's stamp: median, 90th
    percentile, and how many are over STALL_S. A quote priced during a logging stall passes the
    freshness rule against a frozen state. Reported, never judged."""
    if not len(picks):
        return {"since_last_play_median_s": np.nan, "since_last_play_p90_s": np.nan,
                "since_last_play_over_180": 0}
    gap = (picks["stamp"] - picks["last_play_at"]).dt.total_seconds()
    return {"since_last_play_median_s": float(gap.median()), "since_last_play_p90_s": float(gap.quantile(0.9)),
            "since_last_play_over_180": int((gap > STALL_S).sum())}


def outlier_columns(bets: pd.DataFrame, cand: pd.DataFrame) -> dict:
    """Units without outlier prices and the outlier share, on the bets given (the cell's pooled
    seasons only: a reported-only season never enters)."""
    if not len(bets):
        return {"units_without_outliers": 0.0, "share_outlier": np.nan}
    out = H.outlier_flag(bets, cand).to_numpy()
    return {"units_without_outliers": float(bets.loc[~out, "units"].sum()), "share_outlier": float(out.mean())}


# ── one family through the harness ──────────────────────────────────────────

def emit(data: H.Data, family: str, point: str, fr: Frames, sides: dict, seeds, choose_seasons,
         pool_seasons) -> list[dict]:
    """run_cells (IG-2's call, choose_seasons named), then each row's bands (bar 5)."""
    times = fr.cand.drop_duplicates("game_id")[["game_id", "T"]]
    rows = H.run_cells(data, family, point, fr.cand, fr.neutral, list(CUTS), sides, close=None, sig=None,
                       placebo=fr.placebo(seeds), times=times, choose_seasons=choose_seasons)
    for r in rows:
        cm = fr.cand[fr.cand["market"] == r["market"]]
        r.update(G5.band_columns(cm, r["side"], "ev", G5.band_bounds(CUTS, int(r["cut_index"]), lowest=LOWEST),
                                 data.games, pool_seasons))
        r.update(pooled_outliers(fr, r, data.games, pool_seasons))
        picks = H.choose(cm, r["cut"], sides=[r["side"]])
        r.update(stall_stats(picks[picks["season"].isin(pool_seasons)] if len(picks) else picks))
        for c in ("clv_median", "clv_share_positive", "pool_clv_median"):
            r[c] = np.nan
        r["clv_n"] = 0
        r["share_still_offered"] = np.nan
        r["units_still_offered"] = np.nan
    return rows


def cell_bets(fr: Frames, row: dict, games: pd.DataFrame, pool_seasons) -> pd.DataFrame:
    """The cell's own bets, rebuilt by the same choose and grade run_cells used."""
    cm = fr.cand[fr.cand["market"] == row["market"]]
    b = H.grade(H.choose(cm, row["cut"], sides=[row["side"]]), games)
    return b[b["season"].isin(pool_seasons)].reset_index(drop=True) if len(b) else b


def pooled_outliers(fr: Frames, row: dict, games: pd.DataFrame, pool_seasons) -> dict:
    """Units without outliers and the outlier share on the cell's pooled seasons only (doc 3.2:
    run_cells counts every season, 2020-21 included, which step 2 reports only)."""
    return outlier_columns(cell_bets(fr, row, games, pool_seasons), fr.cand[fr.cand["market"] == row["market"]])


def beside(fr: Frames, row: dict, games: pd.DataFrame, pool_seasons, raw: pd.DataFrame | None) -> dict:
    """Doc section 9, from a graded cell's bets (run in --full only)."""
    b = cell_bets(fr, row, games, pool_seasons)
    out = {"bets": int(len(b))}
    if not len(b):
        return out
    side_pts = np.where(b["side"] == "home", b["pts120_h"] - b["pts120_a"], b["pts120_a"] - b["pts120_h"])
    hot = side_pts > 0
    dog = (b["price"] > 0).to_numpy()
    out.update({
        "n_hot": int(hot.sum()), "units_hot": float(b.loc[hot, "units"].sum()),
        "roi_hot": H.roi(b[hot]) if hot.any() else np.nan,
        "n_other": int((~hot).sum()), "units_other": float(b.loc[~hot, "units"].sum()),
        "roi_other": H.roi(b[~hot]) if (~hot).any() else np.nan,
        "price_min": float(b["price"].min()), "price_median": float(b["price"].median()),
        "price_max": float(b["price"].max()),
        "n_underdog": int(dog.sum()), "units_underdog": float(b.loc[dog, "units"].sum()),
        "units_by_book": {k: round(float(v), 2) for k, v in b.groupby("book")["units"].sum().items()},
        "bets_by_book": {k: int(v) for k, v in b["book"].value_counts().items()}})
    if raw is not None:
        s = still_offered(b, raw)
        out.update({"share_still_offered": float(s["still"].mean()),
                    "units_still_offered": float(b.loc[s["still"].to_numpy(), "units"].sum()),
                    "share_still_identical": float(s["identical"].mean())})
    return out


# ── counts before grading (prices only) ─────────────────────────────────────

def count_bets(fr: Frames, market: str, side: str, seasons) -> list[dict]:
    out = []
    cm = fr.cand[fr.cand["market"] == market]
    for k, cut in enumerate(CUTS):
        b = G5._pick(cm, cut, side, "ev")
        by = b["season"].value_counts().to_dict() if len(b) else {}
        out.append({"market": market, "cut": cut, **{f"bets_{s}": int(by.get(s, 0)) for s in seasons},
                    "games_decided": int(cm["game_id"].nunique())})
    return out


def differ_share(fr: Frames, market: str, side: str, cut: float, seasons, seeds=DIFFER_SEEDS) -> dict:
    """Of the placebo bets on `seasons`, the share on a game the cell itself does not bet; and the
    mean correlation of the moved disagreement with the real one."""
    cm = fr.cand[fr.cand["market"] == market]
    real = G5._pick(cm, cut, side, "ev")
    ids = set(real.loc[real["season"].isin(seasons), "game_id"]) if len(real) else set()
    total = same = 0
    for s in seeds:
        pc = fr.build(s)
        b = G5._pick(pc[pc["market"] == market], cut, side, "ev")
        b = b[b["season"].isin(seasons)] if len(b) else b
        total += len(b)
        same += int(b["game_id"].isin(ids).sum()) if len(b) else 0
    games = None
    dv = fr.dev[fr.dev["market"] == market]
    corr = []
    if len(dv) > 2:
        gm = fr.cand.drop_duplicates("game_id").set_index("game_id")["game_date"]
        games = pd.DataFrame({"game_id": gm.index, "game_date": gm.to_numpy()})
        for s in seeds:
            sh = H.shuffle_within_date(dv, games, np.random.default_rng(s)).set_index("game_id")["strength"]
            a = dv.set_index("game_id")["strength"]
            corr.append(float(np.corrcoef(a.to_numpy(), sh.reindex(a.index).to_numpy())[0, 1]))
    return {"market": market, "cut": cut, "real_bets": int(len(ids)),
            "differ": (1.0 - same / total) if total else np.nan,
            "mean_corr_moved_vs_real": float(np.nanmean(corr)) if corr else np.nan}


def single_dates(fr: Frames, market: str) -> dict:
    """Decisions alone on their date and market: the shuffle cannot move them."""
    d = fr.cand[fr.cand["market"] == market].drop_duplicates("game_id")
    n = d.groupby("game_date").size()
    return {"decisions": int(len(d)), "dates": int(len(n)), "alone_on_date": int((n == 1).sum())}


def projection_date(bets: int, games_seen: int, sched: pd.DataFrame, after: str,
                    target: int = TARGET_BETS) -> str:
    """The schedule date the cell reaches `target` bets at its measured bets per game, counting
    the scheduled games per date after `after`; 'reached', or 'not this season'."""
    if bets >= target:
        return "reached"
    if games_seen == 0 or bets == 0:
        return "no bets yet: cannot project"
    rate = bets / games_seen
    s = sched[sched["game_date"] > after].groupby("game_date").size().sort_index()
    cum = bets + rate * s.cumsum()
    hit = cum[cum >= target]
    return str(hit.index[0]) if len(hit) else "not this season"


# ── guards for a run that must not read a result ────────────────────────────

def blind_scores(games: pd.DataFrame, seed: int = 20261103) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    g = games.copy()
    home = rng.integers(90, 130, len(g)).astype(float)
    away = rng.integers(90, 130, len(g)).astype(float)
    g["home_score"], g["away_score"] = home + (home == away), away
    g.attrs[BLINDED] = True
    return g


@contextmanager
def only_random_scores():
    """Inside, a grade handed real scores stops the run."""
    real = H.grade

    def guarded(bets, games):
        if not games.attrs.get(BLINDED):
            raise RuntimeError("a grade was handed real scores inside a no-result run")
        return real(bets, games)
    H.grade = guarded
    try:
        yield
    finally:
        H.grade = real


def blank_finals(q: pd.DataFrame) -> pd.DataFrame:
    return q.assign(final_home=np.nan, final_away=np.nan)


# ── the pull (doc section 1.1) ──────────────────────────────────────────────

def quiet_window(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    (h0, m0), (h1, m1) = QUIET_UTC
    t = now.hour * 60 + now.minute
    return h0 * 60 + m0 <= t < h1 * 60 + m1


def _frame(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    raw = getattr(cur, "_cur", cur)
    return pd.DataFrame(rows, columns=[d[0] for d in raw.description])


def _connect_checked():
    """A read-only session, refused in the 6am window or when the database is busy."""
    if quiet_window():
        sys.exit("10:00-10:45 UTC: the 6am pipeline window; the pull waits")
    from data.db import get_connection
    conn = get_connection()
    conn.execute("SET default_transaction_read_only = on")
    act = _frame(conn, "SELECT count(*) FILTER (WHERE state = 'active') AS active, "
                       "EXTRACT(EPOCH FROM max(now() - query_start) FILTER (WHERE state = 'active')) AS longest_s "
                       "FROM pg_stat_activity WHERE datname = current_database()")
    log(f"pg_stat_activity: {act.to_dict('records')}")
    if int(act["active"].iloc[0]) > 15 or float(act["longest_s"].fillna(0).iloc[0]) > 120:
        conn.close()
        sys.exit("the database is busy; the pull waits")
    return conn


def _write(df: pd.DataFrame, path: Path) -> None:
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: v if v is None or isinstance(v, (str, bool, int, float)) else str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    log(f"wrote {path} ({len(df):,} rows)")


# nba_pbp's only index is (espn_game_id, play_no): every read goes through it.
PBP_SQL = "SELECT {cols} FROM nba_pbp WHERE espn_game_id = ANY(%s)"
HELD_PBP_COLS = ("game_id, espn_game_id, play_no, season, season_type, period, clock_s, game_s, wallclock, "
                 "type_text, scoring_play, shooting_play, shot_value, points, team_side, athlete_id_1")


def pull(out: Path = SCRATCH) -> None:
    """2026-27, read-only, once, by indexed key in chunks; never 10:00-10:45 UTC."""
    conn = _connect_checked()
    try:
        g = _frame(conn, "SELECT game_id, season, game_date, commence_time, home_team, away_team, "
                         "home_score, away_score FROM games WHERE sport = 'NBA' AND season = %s", (LIVE,))
        final = g.loc[g["home_score"].notna(), "game_id"].tolist()
        log(f"2026-27 games scheduled {len(g)}, final {len(final)}")
        odds, pbp, box = [], [], []
        for i in range(0, len(final), PULL_CHUNK):
            ids = final[i:i + PULL_CHUNK]
            odds.append(_frame(conn, """
                SELECT o.game_id, o.market, o.bookmaker, o.snapshot_type, o.snapshot_at, o.source,
                       o.created_at, o.home_price, o.away_price, o.spread_home, o.total_line,
                       o.over_price, o.under_price
                  FROM odds o JOIN games g ON g.game_id = o.game_id
                 WHERE o.game_id = ANY(%s) AND o.market IN ('h2h', 'spreads')
                   AND (o.snapshot_at::timestamptz >= g.commence_time::timestamptz - interval '90 minutes'
                        OR (o.bookmaker = 'pinnacle'
                            AND o.snapshot_at::timestamptz >= g.commence_time::timestamptz - interval '36 hours'))
            """, (ids,)))
            time.sleep(PULL_PAUSE_S)
            eids = _frame(conn, "SELECT espn_game_id FROM nba_pbp_games WHERE game_id = ANY(%s)", (ids,))
            pbp.append(_frame(conn, PBP_SQL.format(cols="*"), ([int(x) for x in eids["espn_game_id"]],)))
            time.sleep(PULL_PAUSE_S)
            box.append(_frame(conn, "SELECT * FROM nba_pbp_box WHERE game_id = ANY(%s)", (ids,)))
            time.sleep(PULL_PAUSE_S)
            log(f"  chunk {i // PULL_CHUNK + 1}: {len(ids)} games, {len(odds[-1]):,} odds rows, "
                f"{len(pbp[-1]):,} plays")
    finally:
        conn.close()
    for name, df in (("games", g), ("odds", pd.concat(odds, ignore_index=True)),
                     ("pbp", pd.concat(pbp, ignore_index=True)), ("box", pd.concat(box, ignore_index=True))):
        _write(df, out / PULL_FILES[name])


HELD_PULL = {"games": "held_pbp_games.parquet", "pbp": "held_pbp.parquet", "box": "held_pbp_box.parquet"}
HELD_PULL_SEASONS = (2020, *HELD_SEASONS)       # 2019-20 only for 2020-21's last-season minutes


def pull_held(out: Path = SCRATCH, chunk: int = PULL_CHUNK) -> None:
    """The held seasons' play-by-play for step 2's training states (doc 3.1, 2026-11-03): the
    ESPN release files IG-2 read are gone from this machine, and nba_pbp holds the same rows
    (the ingestor wrote them from those files). Regular season, 2020-21 .. 2025-26 plays;
    2019-20 .. 2025-26 box rows. Read-only, by indexed key, in chunks with a pause."""
    conn = _connect_checked()
    try:
        games = _frame(conn, "SELECT espn_game_id, game_id, season, season_type, game_date, home_team, "
                             "away_team, in_games FROM nba_pbp_games WHERE season = ANY(%s)",
                       (list(HELD_PULL_SEASONS),))
        reg = games[(games["season_type"] == 2) & games["in_games"].astype(bool)]
        want = reg[reg["season"].isin(HELD_SEASONS)]
        eids = [int(x) for x in want["espn_game_id"]]
        log(f"held regular-season games to read: {len(eids)}")
        pbp, box = [], []
        for i in range(0, len(eids), chunk):
            pbp.append(_frame(conn, PBP_SQL.format(cols=HELD_PBP_COLS), (eids[i:i + chunk],)))
            time.sleep(PULL_PAUSE_S)
            if (i // chunk) % 10 == 0:
                log(f"  plays chunk {i // chunk + 1}/{(len(eids) + chunk - 1) // chunk}: {sum(len(x) for x in pbp):,} rows")
        gids = reg["game_id"].dropna().tolist()
        for i in range(0, len(gids), chunk * 4):
            box.append(_frame(conn, "SELECT espn_game_id, espn_id, game_id, season, side, starter, minutes, "
                                    "did_not_play FROM nba_pbp_box WHERE game_id = ANY(%s)", (gids[i:i + chunk * 4],)))
            time.sleep(PULL_PAUSE_S)
    finally:
        conn.close()
    _write(games, out / HELD_PULL["games"])
    _write(pd.concat(pbp, ignore_index=True), out / HELD_PULL["pbp"])
    _write(pd.concat(box, ignore_index=True), out / HELD_PULL["box"])


# ── synthetic checks (each rule watched failing in the tests) ───────────────

def synthetic_checks() -> dict:
    """The rules this lab adds, on hand-made rows (the tests pin each one)."""
    out = {}
    assert impossible_price([-99, 99, -100, 100, np.nan, -50000]).tolist() == [True, True, False, False, True, False]
    q = pd.DataFrame({"book": ["fanduel", "fanduel", "betmgm", "betmgm", "pinnacle"],
                      "market": ["spreads", "spreads", "h2h", "h2h", "spreads"],
                      "line": [-6.0, -6.5, np.nan, np.nan, 9.0], "pin_line": [0.0, 0.0, np.nan, np.nan, 0.0],
                      "fa": [.5, .5, .76, .74, .5], "pin_fa": [.5, .5, .5, .5, .5]})
    assert pin_gap_bad(q).tolist() == [False, True, True, False, False]
    st = pd.DataFrame({"period": [4, 4, 4, 4, 4, 3, 4], "phase": ["live"] * 6 + ["break"],
                       "clock_s": [360.0, 361.0, 0.0, 100.0, 100.0, 100.0, 100.0],
                       "h_pts": [90, 90, 90, 93, 107, 90, 90], "a_pts": [80, 80, 80, 90, 90, 80, 80]})
    assert late_label(st).tolist() == [PT_LATE, "", "", "", "", "", ""]
    st2 = pd.DataFrame({"period": 4, "phase": "live", "clock_s": 100.0,
                        "h_pts": [94, 106, 80, 96], "a_pts": [90, 90, 96, 79]})
    assert late_label(st2).tolist() == [PT_LATE, PT_LATE, PT_LATE, ""]
    assert leader_side(st2).tolist() == ["home", "home", "away", "home"]
    t0 = pd.Timestamp("2026-11-01T01:00:00Z")
    o = pd.DataFrame({"created_at": [t0, t0, t0 + pd.Timedelta(minutes=10)],
                      "snapshot_at": [t0 - pd.Timedelta(seconds=30), t0 + pd.Timedelta(seconds=4),
                                      t0 + pd.Timedelta(minutes=9)]})
    s = served_times(o)
    assert s["served_at"].tolist() == [t0 + pd.Timedelta(seconds=4)] * 2 + [t0 + pd.Timedelta(minutes=10)]
    out["rules"] = "pass"
    return out


# ── smoke (no result of any bet) ────────────────────────────────────────────

def _q(x, p):
    return float(np.nanpercentile(np.asarray(x, float), p)) if len(x) else np.nan


def data_report(live: Live) -> dict:
    """What 2026-27 in-play data exists, under record 7.1's rule."""
    q, raw = live.q, live.raw
    inplay = q[q["phase"].isin(D.IN_PLAY_PHASES)]
    per = inplay.groupby(["game_id", "book", "market"]).size().rename("n").reset_index()
    by = per.groupby(["market", "book"])["n"].describe(percentiles=[.5])[["count", "min", "50%", "max"]]
    f = inplay[["game_id", "fetch_at"]].drop_duplicates().sort_values(["game_id", "fetch_at"])
    gap = f.groupby("game_id")["fetch_at"].diff().dt.total_seconds().div(60).dropna()
    pin_since = G.with_pin_freshness(inplay)["pin_pts_since"]
    dec = inplay[inplay["book"].isin(H.BETTABLE)]
    paired = dec["pin_fa"].notna()
    rule_ok = (paired & dec["coherent"].astype(bool) & (dec["pts_since_stamp"] == 0)
               & (pin_since.loc[dec.index] == 0))
    age = (inplay["served_at"] - inplay["stamp"]).dt.total_seconds()
    return {
        "games_final_with_pbp": int(live.games["game_id"].nunique()),
        "games_with_in_play_rows": int(inplay["game_id"].nunique()),
        "first_game_date": str(live.games["game_date"].min()), "last_game_date": str(live.games["game_date"].max()),
        "in_play_rows": int(len(inplay)), "raw_rows_kept_for_next_fetch": int(len(raw)),
        "quotes_per_book_per_game": by.round(1).to_string(),
        "fetch_spacing_min": {"n": int(len(gap)), "p10": _q(gap, 10), "median": _q(gap, 50), "p90": _q(gap, 90)},
        "in_play_fetches_per_game": f.groupby("game_id").size().describe().round(1).to_dict(),
        "quote_age_at_served_s": {"median": _q(age, 50), "p90": _q(age, 90), "p99": _q(age, 99)},
        "deciding_quotes": int(len(dec)), "deciding_with_pinnacle_60s": float(paired.mean()) if len(dec) else np.nan,
        "deciding_passing_7_1_rule": float(rule_ok.mean()) if len(dec) else np.nan,
        "phase_counts": inplay["phase"].value_counts().to_dict(),
        "notes": {k: v for k, v in live.notes.items() if k not in ("label_vs_phase",)},
        "label_vs_phase": live.notes.get("label_vs_phase"),
    }


def clock_check(q: pd.DataFrame, prior: pd.DataFrame) -> dict:
    """Pinnacle's live home spread against minus (margin + the prior's share of the time left):
    per game median gap. A broken clock join shows as a wide gap (reported, filters nothing)."""
    p = q[(q["book"] == H.SHARP) & (q["market"] == "spreads") & (q["phase"] == "live") & (q["period"] <= 4)]
    p = p.merge(prior[["game_id", "mu_pre"]], on="game_id")
    resid = -p["line"] - ((p["h_pts"] - p["a_pts"]) + p["mu_pre"] * p["secs_left"] / 2880.0)
    gm = resid.groupby(p["game_id"]).median().dropna()
    return {"games": int(len(gm)), "p01": _q(gm, 1), "median": _q(gm, 50), "p99": _q(gm, 99),
            "games_beyond_12": {k: round(float(v), 1) for k, v in gm[gm.abs() > 12].items()}}


def extremes(q: pd.DataFrame, label: str) -> str:
    x = q.groupby(["season", "market"]).agg(line_min=("line", "min"), line_max=("line", "max"),
                                            a_min=("price_a", "min"), a_max=("price_a", "max"),
                                            b_min=("price_b", "min"), b_max=("price_b", "max"), n=("price_a", "size"))
    return f"{label}:\n{x.to_string()}"


def gap_report(q: pd.DataFrame) -> dict:
    d = q[q["book"].isin(H.BETTABLE) & q["pin_fa"].notna()]
    sp = d[d["market"] == "spreads"]
    ml = d[d["market"] == "h2h"]
    gs = (sp["line"] - sp["pin_line"]).abs()
    gm = (ml["fa"] - ml["pin_fa"]).abs()
    return {"spread_gap_pts": {"n": int(len(gs)), "p50": _q(gs, 50), "p99": _q(gs, 99), "max": float(gs.max()) if len(gs) else np.nan},
            "ml_gap_chance": {"n": int(len(gm)), "p50": _q(gm, 50), "p99": _q(gm, 99), "max": float(gm.max()) if len(gm) else np.nan}}


def top_offers(frame: pd.DataFrame, side: str, n: int = 10) -> str:
    c = frame[frame["book"].isin(H.BETTABLE)]
    x = c[H.side_mask(c, [side])].sort_values("ev", ascending=False).drop_duplicates("game_id").head(n)
    cols = [k for k in ("game_id", "phase_ig2", "book", "side", "line", "price", "p_win", "ev", "period", "clock_s",
                        "h_pts", "a_pts", "pin_line", "pin_fa", "fetch_at") if k in x]
    return x[cols].to_string(index=False)


def placebo_cost(run, extra: int = 30) -> float:
    """Seconds for one placebo run of one cell: the same cells with 1 + extra seeds against one."""
    t = time.perf_counter()
    run(tuple(range(1, extra + 2)))
    many = time.perf_counter() - t
    t = time.perf_counter()
    run((1,))
    return max(many - (time.perf_counter() - t), 0.0) / extra


def smoke(cache: Path = H.CACHE) -> dict:
    t0 = time.time()
    os.environ.pop(BETS_ENV, None)
    H.check()
    print(json.dumps(synthetic_checks()), flush=True)
    res: dict = {"times": {}}
    T = res["times"]

    # 2026-27 ------------------------------------------------------------------
    t1 = time.time()
    live = load_live()
    T["load_live"] = time.time() - t1
    rep = data_report(live)
    print("\n2026-27 IN-PLAY DATA:")
    for k, v in rep.items():
        print(f"  {k}: {v}")
    print(f"\nRULE 1 dropped (2026-27): {len(live.dropped1)}")
    if len(live.dropped1):
        print(live.dropped1[["game_id", "market", "book", "stamp", "line", "price_a", "price_b"]].head(40).to_string(index=False))
    print(f"RULES 3-4 dropped (2026-27): {len(live.dropped34)}")
    if len(live.dropped34):
        print(live.dropped34[["game_id", "market", "book", "stamp", "line", "pin_line", "price_a", "price_b", "fa",
                              "pin_fa", "pts_since_stamp"]].head(60).to_string(index=False))
    print("\nRULE 6 (a clock jump of 45 minutes or more between consecutive plays), 2026-27:",
          json.dumps(live.notes["games_wallclock_jump"]), "; dropped from the table:",
          live.notes["games_wallclock_jump_dropped"])
    print("RULES 3-4, decisions they change, step 1 (2026-27):", json.dumps(decisions_changed(live.q, live.q_all, step1_decide)))
    print("RULES 3-4, decisions they change, step 2 (2026-27):", json.dumps(decisions_changed(live.q, live.q_all, step2_decide)))
    print("\n" + extremes(live.q, "EXTREMES, 2026-27 in-play rows kept"))
    print("gap to the paired Pinnacle quote, 2026-27 deciding rows kept:", json.dumps(gap_report(live.q)))
    t1 = time.time()
    prior27 = live_prior(cache, live)
    T["prior_2027"] = time.time() - t1
    print(f"\n2026-27 pre-game prior: {len(prior27)} games; mu_pre min {prior27['mu_pre'].min():.2f} "
          f"max {prior27['mu_pre'].max():.2f}")
    print("clock check, 2026-27:", json.dumps(clock_check(live.q, prior27)))

    # models ------------------------------------------------------------------
    t1 = time.time()
    train1 = step1_train()
    m1 = G.models_by_season(train1, G.FEATURES, seasons=(LIVE,))
    T["model_step1"] = time.time() - t1
    print(f"\nstep 1 model for 2026-27: fit on {m1[LIVE].n_train:,} states, seasons "
          f"{sorted(train1['season'].unique())}; coefs {dict(zip(G.FEATURES, np.round(m1[LIVE].beta, 4)))}, "
          f"s1 {m1[LIVE].s1:.2f}, s0 {m1[LIVE].s0:.2f}")
    t1 = time.time()
    late, late_notes = late_states(cache)
    T["late_states"] = time.time() - t1
    m2 = G.models_by_season(late, G.FEATURES, seasons=HELD_SEASONS + (LIVE,))
    print(f"step 2 late training states: {late_notes}")
    for S, mdl in m2.items():
        print(f"  step 2 model {S}: n {mdl.n_train:,}, s1 {mdl.s1:.2f}, s0 {mdl.s0:.2f}, "
              f"coefs {dict(zip(G.FEATURES, np.round(mdl.beta, 3)))}")

    # held step-2 table ---------------------------------------------------------
    t1 = time.time()
    held, h1, h34, held_all, hnotes = load_held()
    T["load_held"] = time.time() - t1
    print(f"\nHELD h2h quotes: {len(held):,} kept; rule 1 dropped {len(h1)}; rules 3-4 dropped {len(h34)}")
    print("held quotes re-joined with this lab's state join, score differs from the stored table:",
          json.dumps(hnotes["restate_all"]), json.dumps(hnotes["restate"]))
    print("RULE 6, held pull:", json.dumps(hnotes["games_wallclock_jump"]))
    print("RULE 6, held games dropped from the moneyline table:", hnotes["games_wallclock_jump_in_table"])
    print("RULES 3-4, decisions they change, step 2 (held):", json.dumps(decisions_changed(held, held_all, step2_decide)))
    if len(h1):
        print(h1[["game_id", "book", "stamp", "price_a", "price_b"]].head(20).to_string(index=False))
    if len(h34):
        print(h34[["game_id", "book", "stamp", "price_a", "price_b", "fa", "pin_fa", "period", "clock_s"]].head(40).to_string(index=False))
    print(extremes(held, "EXTREMES, held h2h in-play rows kept"))
    print("gap to the paired Pinnacle quote, held deciding h2h rows kept:", json.dumps(gap_report(held)))
    prior_h = pd.read_parquet(PRIOR_HELD)

    games_h = H.load_games(cache)
    blind_h = blind_scores(games_h)
    blind_l = blind_scores(live.games)
    q27 = blank_finals(live.q)
    held_b = blank_finals(held)
    counts, differs, alone, proj, tops = [], [], [], [], []
    with only_random_scores():
        # step 1
        qt1 = step1_table(q27)
        dec_all = phase_decisions(qt1, prior27, m1, step=1)
        d27 = empty_data(blind_l)
        print(f"\nSTEP 1 decisions on 2026-27 (game x market x phase): {len(dec_all.drop_duplicates(['game_id', 'market', 'phase_ig2']))}")
        print(dec_all.drop_duplicates(["game_id", "market", "phase_ig2"]).groupby(["phase_ig2", "market"]).size().to_string())
        fr1 = {}
        for ph in G.PHASES:
            t1 = time.time()
            dec = dec_all[dec_all["phase_ig2"] == ph]
            fr1[ph] = step1_frames(dec, m1, blind_l)
            T[f"frames_s1_{ph}"] = time.time() - t1
            for mk in G.MARKETS:
                for r in count_bets(fr1[ph], mk, "model", (LIVE,)):
                    counts.append({"family": FAM_S1, "point": ph, **r})
                for cut in CUTS:
                    differs.append({"family": FAM_S1, "point": ph, **differ_share(fr1[ph], mk, "model", cut, (LIVE,))})
                alone.append({"family": FAM_S1, "point": ph, "market": mk, **single_dates(fr1[ph], mk)})
                tops.append(f"HIGHEST-EV, step 1, {ph} {mk}:\n{top_offers(fr1[ph].cand[fr1[ph].cand['market'] == mk], 'model')}")
        # one phase's six cells through the harness with one placebo run, and the placebo's cost
        t1 = time.perf_counter()
        rows = emit(d27, FAM_S1, "Q3", fr1["Q3"], {mk: ["model"] for mk in G.MARKETS}, (1,), (LIVE,), (LIVE,))
        T["s1_phase_6_cells_1_placebo"] = time.perf_counter() - t1
        assert len(rows) == 6 and all(np.isfinite(r["pool_n"]) for r in rows)
        T["placebo_s1_per_phase_run"] = placebo_cost(
            lambda seeds: emit(d27, FAM_S1, "Q3", fr1["Q3"], {mk: ["model"] for mk in G.MARKETS}, seeds, (LIVE,), (LIVE,)))
        print("step 1 Q3 cells on random scores, pool_n:", [r["pool_n"] for r in rows])

        # step 2, held
        qt2 = late_table(held_b)
        dec_h = phase_decisions(qt2, prior_h, m2, step=2)
        dh = empty_data(blind_h)
        frh = step2_frames(dec_h, m2, blind_h)
        T["frames_s2_held"] = 0.0
        late_report("held", qt2, dec_h, frh)
        for r in count_bets(frh, "h2h", LEADER, HELD_SEASONS):
            counts.append({"family": FAM_S2H, "point": PT_LATE, **r})
        for cut in CUTS:
            differs.append({"family": FAM_S2H, "point": PT_LATE, **differ_share(frh, "h2h", LEADER, cut, HELD_GRADED)})
        alone.append({"family": FAM_S2H, "point": PT_LATE, "market": "h2h", **single_dates(frh, "h2h")})
        tops.append(f"HIGHEST-EV, step 2 held, leader:\n{top_offers(frh.cand, LEADER)}")
        t1 = time.perf_counter()
        rows = emit(dh, FAM_S2H, PT_LATE, frh, {"h2h": [LEADER]}, (1,), H.CHOOSE, HELD_GRADED)
        T["s2_held_3_cells_1_placebo"] = time.perf_counter() - t1
        T["placebo_s2_held_run"] = placebo_cost(
            lambda seeds: emit(dh, FAM_S2H, PT_LATE, frh, {"h2h": [LEADER]}, seeds, H.CHOOSE, HELD_GRADED))

        # step 2, 2026-27
        qt3 = late_table(q27)
        dec_l = phase_decisions(qt3, prior27, m2, step=2)
        frl = None
        if len(dec_l):
            frl = step2_frames(dec_l, m2, blind_l)
            late_report("2026-27", qt3, dec_l, frl)
            for r in count_bets(frl, "h2h", LEADER, (LIVE,)):
                counts.append({"family": FAM_S2L, "point": PT_LATE, **r})
            for cut in CUTS:
                differs.append({"family": FAM_S2L, "point": PT_LATE, **differ_share(frl, "h2h", LEADER, cut, (LIVE,))})
            alone.append({"family": FAM_S2L, "point": PT_LATE, "market": "h2h", **single_dates(frl, "h2h")})
            tops.append(f"HIGHEST-EV, step 2 2026-27, leader:\n{top_offers(frl.cand, LEADER)}")
            t1 = time.perf_counter()
            emit(d27, FAM_S2L, PT_LATE, frl, {"h2h": [LEADER]}, (1,), (LIVE,), (LIVE,))
            T["s2_live_3_cells_1_placebo"] = time.perf_counter() - t1
        else:
            print("step 2 on 2026-27: no decision yet")
        # still offered at the next fetch, and the time since the last logged play, on the picks
        # (prices and clocks only, no result)
        so = []
        for ph in G.PHASES:
            for mk in G.MARKETS:
                for cut in CUTS:
                    b = G5._pick(fr1[ph].cand[fr1[ph].cand["market"] == mk], cut, "model", "ev")
                    s = still_offered(b, live.raw)
                    so.append({"family": FAM_S1, "point": ph, "market": mk, "cut": cut, "bets": int(len(b)),
                               "share_still_offered": float(s["still"].mean()) if len(b) else np.nan,
                               "share_identical": float(s["identical"].mean()) if len(b) else np.nan,
                               **stall_stats(b)})
        for fam, frx, seasons in ((FAM_S2H, frh, HELD_GRADED), (FAM_S2L, frl, (LIVE,))):
            if frx is None:
                continue
            for cut in CUTS:
                b = G5._pick(frx.cand, cut, LEADER, "ev")
                b = b[b["season"].isin(seasons)] if len(b) else b
                so.append({"family": fam, "point": PT_LATE, "market": "h2h", "cut": cut, "bets": int(len(b)),
                           **stall_stats(b)})
        res["still_offered"] = so

    for t in tops:
        print("\n" + t)
    cnt = pd.DataFrame(counts)
    print("\nCOUNTS (bets each cell would place, from prices alone):")
    print(cnt.to_string(index=False))
    games_seen = int(live.games["game_id"].nunique())
    last = str(live.games["game_date"].max())
    sched = live.sched
    for _, r in cnt.iterrows():
        if r["family"] in (FAM_S1, FAM_S2L):
            n = int(r.get(f"bets_{LIVE}", 0))
            proj.append({"family": r["family"], "point": r["point"], "market": r["market"], "cut": r["cut"],
                         "bets_so_far": n, "games_seen": games_seen, "bets_per_game": n / games_seen,
                         "reaches_200_on": projection_date(n, games_seen, sched, last)})
    print(f"\nWHEN EACH 2026-27 CELL REACHES {TARGET_BETS} BETS (schedule after {last}; "
          f"{int(sched['game_date'].gt(last).sum())} games left; last scheduled {sched['game_date'].max()}):")
    print(pd.DataFrame(proj).round(3).to_string(index=False))
    print("\nSTILL OFFERED AT THE NEXT FETCH (step 1, 2026-27) AND SECONDS SINCE THE LAST LOGGED PLAY (prices and clocks only):")
    print(pd.DataFrame(res["still_offered"]).round(3).to_string(index=False))
    d = pd.DataFrame(differs)
    print(f"\nPLACEBO: share of placebo bets on a game the cell does not bet ({len(DIFFER_SEEDS)} seeds), "
          "and the moved disagreement's correlation with the real one:")
    print(d.round(3).to_string(index=False))
    thin = d[(d["real_bets"] >= 30) & (d["differ"] < 0.5)]
    print("cells with 30+ real bets under 50%:", "none" if thin.empty else thin.to_string(index=False))
    print("\nDECISIONS ALONE ON THEIR DATE (the shuffle cannot move them):")
    print(pd.DataFrame(alone).to_string(index=False))
    p = projection(T)
    print("\nTIMES (seconds):", json.dumps({k: round(v, 3) for k, v in T.items()}))
    print("PROJECTED --full:", json.dumps(p))
    log("smoke done", t0)
    res.update({"counts": counts, "differ": differs, "projection": p, "reach": proj})
    return res


def late_report(label: str, qt: pd.DataFrame, dec: pd.DataFrame, fr: Frames) -> None:
    """Step 2's population, the leader's best price, and what the -200 floor removes (prices only)."""
    pop = qt[qt["phase_ig2"] == PT_LATE]
    print(f"\nSTEP 2 ({label}): h2h quotes in the window and lead range {len(pop):,} on "
          f"{pop['game_id'].nunique()} games; decisions {dec['game_id'].nunique()}")
    print("decisions by season:", dec.drop_duplicates("game_id").groupby("season").size().to_dict())
    c = fr.cand[H.side_mask(fr.cand, [LEADER]) & fr.cand["book"].isin(H.BETTABLE)]
    best = c.groupby("game_id")["price"].max()
    if len(best):
        print(f"leader's best deciding price per decision: min {best.min():.0f}, p10 {_q(best, 10):.0f}, "
              f"median {_q(best, 50):.0f}, p90 {_q(best, 90):.0f}, max {best.max():.0f}")
        season = fr.cand.drop_duplicates("game_id").set_index("game_id")["season"]
        under = best[best < H.PRICE_FLOOR]
        print(f"decisions whose best leader price is shorter than -200 (the floor removes them): {len(under)} of "
              f"{len(best)}; by season {season.reindex(under.index).value_counts().sort_index().to_dict()}")
        lead = (dec.drop_duplicates("game_id")["h_pts"] - dec.drop_duplicates("game_id")["a_pts"]).abs()
        print("lead at the decision:", lead.value_counts().sort_index().to_dict())
        clk = dec.drop_duplicates("game_id")["clock_s"]
        print(f"clock at the decision (s): min {clk.min():.0f}, median {clk.median():.0f}, max {clk.max():.0f}")


def projection(T: dict) -> dict:
    """--full from this run's measured times: each cell's report plus 200 placebo runs."""
    s1 = 3 * (T["s1_phase_6_cells_1_placebo"] + (N_PLACEBO - 1) * T["placebo_s1_per_phase_run"])
    s1 += sum(v for k, v in T.items() if k.startswith("frames_s1_"))
    s2h = T["s2_held_3_cells_1_placebo"] + (N_PLACEBO - 1) * T["placebo_s2_held_run"]
    s2l = T.get("s2_live_3_cells_1_placebo", 0.0) * N_PLACEBO
    loads = T["load_live"] + T["prior_2027"] + T["model_step1"] + T["load_held"]
    out = {"step1_s": s1, "step2_held_s": s2h, "step2_live_s_upper": s2l, "loads_s": loads,
           "late_states_s_this_run": T["late_states"]}
    out["total_minutes"] = (s1 + s2h + s2l + loads + T["late_states"]) / 60.0
    try:
        import psutil
        info = psutil.Process().memory_info()
        out["peak_working_set_gb"] = getattr(info, "peak_wset", info.rss) / 1e9
    except ImportError:
        out["peak_working_set_gb"] = None
    return out


# ── full (the owner runs it) ────────────────────────────────────────────────

def refuse_full() -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's own results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for k, v in {**PULL_FILES, **{f"held_{a}": b for a, b in HELD_PULL.items()}}.items():
        if not (SCRATCH / v).exists():
            why.append(f"{SCRATCH / v} does not exist: run --pull and --pull-held first")
    return why


def write_cells(rows: list[dict], path: Path) -> None:
    df = pd.DataFrame(rows)
    df["placebo_rois"] = df["placebo_rois"].apply(lambda v: [float(x) for x in v])
    df["thin"] = df["pool_n"] < TARGET_BETS
    df["reading"] = np.where(df["thin"], "too few games to tell", "")
    df.to_parquet(path, index=False)


def full(cache: Path = H.CACHE) -> None:
    why = refuse_full()
    if why:
        print("REFUSED:\n  " + "\n  ".join(why), flush=True)
        sys.exit(2)
    out = Path(os.environ[RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    H.check()
    print(json.dumps(synthetic_checks()), flush=True)
    live = load_live()
    prior27 = live_prior(cache, live)
    m1 = G.models_by_season(step1_train(), G.FEATURES, seasons=(LIVE,))
    late, _ = late_states(cache)
    m2 = G.models_by_season(late, G.FEATURES, seasons=HELD_SEASONS + (LIVE,))
    held = load_held()[0]
    prior_h = pd.read_parquet(PRIOR_HELD)
    games_h = H.load_games(cache)
    rows, side = {FAM_S1: [], FAM_S2H: [], FAM_S2L: []}, []
    d27 = empty_data(live.games)
    qt1 = step1_table(live.q)
    dec_all = phase_decisions(qt1, prior27, m1, step=1)
    for ph in G.PHASES:
        fr = step1_frames(dec_all[dec_all["phase_ig2"] == ph], m1, live.games)
        r = emit(d27, FAM_S1, ph, fr, {mk: ["model"] for mk in G.MARKETS}, PLACEBO_SEEDS, (LIVE,), (LIVE,))
        for x in r:
            b = beside(fr, x, live.games, (LIVE,), live.raw)
            x.update({k: v for k, v in b.items() if not isinstance(v, dict)})
            side.append({"family": FAM_S1, "point": ph, "market": x["market"], "cut": x["cut"], **b})
        rows[FAM_S1] += r
        log(f"step 1 {ph}: {len(r)} cells", t0)
    qt2 = late_table(held)
    dec_h = phase_decisions(qt2, prior_h, m2, step=2)
    frh = step2_frames(dec_h, m2, games_h)
    r = emit(empty_data(games_h), FAM_S2H, PT_LATE, frh, {"h2h": [LEADER]}, PLACEBO_SEEDS, H.CHOOSE, HELD_GRADED)
    for x in r:
        b = beside(frh, x, games_h, HELD_GRADED, None)
        x.update({k: v for k, v in b.items() if not isinstance(v, dict)})
        side.append({"family": FAM_S2H, "point": PT_LATE, "market": "h2h", "cut": x["cut"], **b})
    rows[FAM_S2H] = r
    log("step 2 held: 3 cells", t0)
    qt3 = late_table(live.q)
    dec_l = phase_decisions(qt3, prior27, m2, step=2)
    if len(dec_l):
        frl = step2_frames(dec_l, m2, live.games)
        r = emit(d27, FAM_S2L, PT_LATE, frl, {"h2h": [LEADER]}, PLACEBO_SEEDS, (LIVE,), (LIVE,))
        for x in r:
            b = beside(frl, x, live.games, (LIVE,), live.raw)
            x.update({k: v for k, v in b.items() if not isinstance(v, dict)})
            side.append({"family": FAM_S2L, "point": PT_LATE, "market": "h2h", "cut": x["cut"], **b})
        rows[FAM_S2L] = r
    else:
        rows[FAM_S2L] = [empty_row(FAM_S2L, k, c) for k, c in enumerate(CUTS)]
    log("step 2 2026-27: 3 cells", t0)
    check_rows([x for v in rows.values() for x in v])
    write_cells(rows[FAM_S1], out / "cells_S1.parquet")
    write_cells(rows[FAM_S2H], out / "cells_S2held.parquet")
    write_cells(rows[FAM_S2L], out / "cells_S2live.parquet")
    (out / "beside.json").write_text(json.dumps(side, indent=1, default=float), encoding="utf-8")
    log(f"cells written to {out}", t0)


def empty_row(family: str, k: int, cut: float) -> dict:
    """A 2026-27 step-2 cell with no decision yet: reported, every count zero."""
    r = {"family": family, "point": PT_LATE, "market": "h2h", "side": LEADER, "cut_index": k, "cut": cut,
         "pool_n": 0, "pool_units": 0.0, "pool_roi": np.nan, "pool_ci95_lo": np.nan, "pool_ci95_hi": np.nan,
         "pool_seasons_counted": 0, "pool_seasons_positive": 0, "roi_choose": np.nan, "n_choose": 0,
         "placebo_rois": [0.0] * N_PLACEBO, "seasons_positive": False}
    for i in range(G5.BAND_SLOTS):
        r.update({f"band{i}_n": 0, f"band{i}_roi": np.nan})
    return r


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pull", action="store_true", help="read the 2026-27 rows once into scratch")
    g.add_argument("--pull-held", action="store_true", help="read the held seasons' play-by-play once")
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every cell (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    pd.set_option("display.width", 250)
    if a.pull:
        pull()
    elif a.pull_held:
        pull_held()
    elif a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
