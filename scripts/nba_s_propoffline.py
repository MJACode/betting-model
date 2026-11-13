"""NBA search: props off Pinnacle's line, the soft-book consensus, and a market-anchored prop model.

docs/nba_search_propoffline.md registers the cells and fixes every choice, written and committed
BEFORE this lab and before any cell was graded. This lab EMITS cells through the shared harness
(scripts/nba_game_harness, H.run_cells); the pass/fail script judges them
(scripts/nba_game2_verdict.py --house5: section 9.1's bars of docs/nba_models_2026.md). Nothing here
judges a cell, and no cut, constant or rule below was chosen from a betting result.

36 cells (asserted), at each game's one prop snapshot 45-75 minutes before tip:

  OL   the first search's off-line rule: a deciding book hangs a line other than Pinnacle's; the
       side the gap favours, EV >= 0.00 .. 0.05, fair price from Pinnacle through the first search's
       negative-binomial count (nb_alpha, NBTable, imported unchanged). 2023-24 .. 2025-26 pooled.
  CS   the first search's soft-consensus rule: no Pinnacle quote on the proposition; each book's
       price against the median no-vig of the OTHER books at the same line, at least 3 of them,
       EV >= 0.00 .. 0.05. 2023-24 .. 2025-26 pooled.
  AN   the market-anchored model: Pinnacle's no-vig (else the deciding books' median at their main
       line) as an unpenalised offset, moved by the projection's disagreement and its inputs
       (OffsetLogit, choose_C from models/nhl_moneyline_anchored.py, imported unchanged), one model
       per (market, reference kind), fitted on seasons before the graded one. Offers at the
       reference line only. EV >= 0.01 / 0.02 / 0.04. 2024-25 and 2025-26 pooled; 2023-24 is a
       fitting season only. An injury report counts as known 30 minutes after its printed time.

  A PROPOSITION IS ONE "GAME" TO THE HARNESS. (game, player, market) gets an integer id, a row in
  the games table with its settling stat as the home score and 0 as the away score, and its offers
  are filed under the harness's total market, so H.choose takes one bet per proposition and H.settle
  gives over when the stat is above the line. `props` maps the id back to the game, player and market.

  PLACEBO  200 runs, seeds 1-200. OL and CS: each proposition takes another's whole reading on the
           same date and market (the best EV on each side, and whether the rule bets there); every
           offer keeps its real price and carries the donor's best EV less its own shortfall from
           the proposition's best offer. AN: each proposition takes another's move and is re-priced.
           The identity permutation returns the real bets exactly.
  CONTROLS control_OL_blind, control_AN_lean, control_same_line: graded, reported, never judged.

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_propoffline --smoke
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_s_propoffline --full

--smoke runs the synthetic checks, then on the real cache prints only counts, extremes, the
highest-EV offers, the placebo's difference share, and a timed run on results set to zero. It never
grades a real bet. --full refuses without all three variables and writes, per group,
cells_<family>_<ref>_<side>.parquet (a stopped run resumes), the bets, props.parquet, beside_*.parquet and
credit_AN.parquet.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")            # see FOLD_THREADS: set before numpy loads

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_prop_projection as pj  # noqa: E402
import models.nba_props as nb  # noqa: E402
from models import nhl_moneyline_anchored as NA  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game2_verdict as V  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_prop_market_lab as PM  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS"
WORK = Path(os.environ.get("NBA_S_WORK", Path(tempfile.gettempdir()) / "nba_s" / "propoffline" / "work"))
POINT, HMARKET, LABEL = "D", "totals", "props"
SEASONS = (2024, 2025, 2026)              # 2023-24 .. 2025-26
AN_GRADED = (2025, 2026)                  # 2023-24 fits only: no priced season before it
CHOOSE_ALL, CHOOSE_AN = (2024, 2025), (2025,)
FOLDS = (2023, 2024, 2025, 2026)          # the projection: fold S fitted on 2018-19 .. S-1
EV_CUTS = (0.00, 0.01, 0.02, 0.03, 0.04, 0.05)
EV_LOWEST = -0.01
AN_CUTS = (0.01, 0.02, 0.04)
AN_LOWEST = 0.00
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
EXPECTED_CELLS = 36
PRICE_LIMIT = 10000.0
EDGE_BESIDE = 0.20                        # config.MAX_EDGE_CAP's size: reported beside, never a rule
SHIPPED_MARKETS = ("player_points", "player_rebounds", "player_assists", "player_threes",
                   "player_points_rebounds_assists")
DD_TD = ("player_double_double", "player_triple_double")
COUNT_MARKETS = tuple(PM.GAP_MARKETS)
PICK_COLS = ["game_id", "market", "side", "book", "price", "line", "season", "game_date", "T"]
FAMILY_OL, FAMILY_CS, FAMILY_AN = "OL", "CS", "AN"
CONTROL_OL, CONTROL_AN, CONTROL_SAME = "control_OL_blind", "control_AN_lean", "control_same_line"
MIN_MODEL_ROWS = 300                      # record 8.1's line
LOW_SHARE = 0.5                           # a placebo run below this repeats more real bets than it changes
DISAGREE_LIMIT = 3.0
REPORT_LAG_MIN = 30                       # section 6.1 of the record: a report is known 30 minutes after print
# Report inputs read 0 where no report covers the game; the others read the training mean.
REPORT_INPUTS = ("tm_o_min", "d_o_min", "tm_q_min", "opp_o_min", "own_q")
OTHER_INPUTS = ("disagree", "min_hat", "is_home", "rest", "b2b", "pace_l", "opp_pace_l")
INPUTS = OTHER_INPUTS + REPORT_INPUTS
FRAME_KEEP = ("game_id", "player_id", "season", "played", "status", "is_home", "rest", "b2b", "pace_l",
              "opp_pace_l", "tm_o_min", "d_o_min", "tm_q_min", "opp_o_min", "own_q") + tuple(nb.BASE_STATS)


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── quotes: the first search's table, then the rows this search may read ────

def load_quotes(cache: Path = H.CACHE, work: Path = WORK) -> pd.DataFrame:
    """scripts/nba_prop_market_lab.build_quotes, unchanged, cached in `work` (a local cache of the
    research cache) and rebuilt when the research cache's prop file is newer."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    PM.CACHE, PM.WORK, PM.OUT = Path(cache), work, work
    f = work / "quotes.parquet"
    stale = not f.exists() or f.stat().st_mtime < (Path(cache) / "nba_props.parquet").stat().st_mtime
    return PM.load_quotes(stale)[0]


def box_ceilings(log: pd.DataFrame) -> dict:
    """The highest number any player has posted in each market's stat in the stored box scores."""
    out = {m: float(log[cols].sum(axis=1).max()) for m, cols in PM.BOX_STAT.items()}
    out.update({m: 1.0 for m in DD_TD})
    return out


def eligible(q: pd.DataFrame, ceilings: dict) -> tuple[pd.DataFrame, dict]:
    """The rows this search may read, each rule from the doc's list, each one counted.

    Names and void: the first search's `usable` (a player on one of the two teams, no namesake, one
    row per book, took the court) and a stat line. Then the 45-75 minute window, a coherent two-way
    quote, both prices inside +-10,000, and the line at or under the market's box-score ceiling."""
    notes = {"rows": int(len(q))}
    r = q[q["usable"] & q["x"].notna()]
    notes["after_names_and_void"] = int(len(r))
    lo, hi = H.POINTS[POINT]
    r = r[r["lead_min"].between(lo, hi)]
    notes["after_window"] = int(len(r))
    r = r[r["coherent"].astype(bool)]
    notes["after_coherent"] = int(len(r))
    ok = (r["over_price"].abs() <= PRICE_LIMIT) & (r["under_price"].abs() <= PRICE_LIMIT)
    notes["removed_price_limit"] = int((~ok).sum())
    r = r[ok]
    ceil = r["market"].map(ceilings).astype(float)
    ok = r["line"] <= ceil
    notes["removed_line_ceiling"] = int((~ok).sum())
    r = r[ok].copy()
    notes["eligible"] = int(len(r))
    r["player_id"] = r["player_id"].astype(str)
    r["p"] = (1.0 / r["od"]) / (1.0 / r["od"] + 1.0 / r["ud"])    # the book's proportional no-vig over
    return r.drop(columns=[c for c in ("over_win", "created_at", "void", "action", "minutes", "box_team",
                                       "namesake", "tier", "usable", "two_way", "has_o", "has_u", "isum")
                           if c in r]), notes


KEY = ["game_id", "player_id", "market"]


def with_props(r: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """(rows with prop_id, the table of propositions, the settling stat by prop_id)."""
    r = r.sort_values(KEY).reset_index(drop=True)
    r["prop_id"] = r.groupby(KEY, sort=False).ngroup().astype(np.int64)
    r["T"] = pd.to_datetime(r["snapshot_at"], utc=True, format="ISO8601")
    p = r.drop_duplicates("prop_id").sort_values("prop_id")
    stat = p["x"].to_numpy(float)
    props = p[["prop_id", "game_id", "player_id", "player_name", "market", "season", "game_date", "lead_min", "T"]]
    return r.drop(columns="x"), props.reset_index(drop=True), stat


def games_table(props: pd.DataFrame, stat: np.ndarray | None) -> pd.DataFrame:
    """The harness's games: one row per proposition. stat None: every score 0, nothing real is read
    (the timed smoke run)."""
    n = len(props)
    return pd.DataFrame({"game_id": props["prop_id"].to_numpy(np.int64), "season": props["season"].astype(int).to_numpy(),
                         "game_date": props["game_date"].astype(str).to_numpy(), "tip": props["T"].values,
                         "home_team": "", "away_team": "",
                         "home_score": np.zeros(n) if stat is None else np.asarray(stat, float),
                         "away_score": np.zeros(n)})


def times_table(props: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"game_id": props["prop_id"].to_numpy(np.int64), "T": props["T"].values,
                         "lead_min": props["lead_min"].to_numpy(float)})


NO_QUOTES = pd.DataFrame({"game_id": pd.Series(dtype="int64")})
NO_FETCHES = pd.DataFrame({"game_id": pd.Series(dtype="int64"),
                           "fetch_at": pd.Series(dtype="datetime64[ns]"),
                           "lead_min": pd.Series(dtype="float64")})


def long_offers(q: pd.DataFrame, fair_over: np.ndarray, extra=()) -> pd.DataFrame:
    """Two rows per quote, one per real side, in the shape H.choose and H.grade read."""
    n = len(q)
    fair_over = np.asarray(fair_over, float)
    base = {"game_id": q["prop_id"].to_numpy(np.int64), "market": np.full(n, HMARKET, dtype=object),
            "book": q["bookmaker"].to_numpy(dtype=object), "line": q["line"].to_numpy(float),
            "season": q["season"].astype(int).to_numpy(), "game_date": q["game_date"].astype(str).to_numpy(dtype=object),
            "T": q["T"].values, "prop_market": q["market"].to_numpy(dtype=object),
            **{c: q[c].to_numpy() for c in extra}}
    over = pd.DataFrame({**base, "side": np.full(n, "over", dtype=object), "price": q["over_price"].to_numpy(float),
                         "p_win": fair_over})
    under = pd.DataFrame({**base, "side": np.full(n, "under", dtype=object), "price": q["under_price"].to_numpy(float),
                          "p_win": 1.0 - fair_over})
    out = pd.concat([over, under], ignore_index=True)
    out["p_push"] = 0.0
    out["ev"] = out["p_win"].to_numpy() * H.dec(out["price"].to_numpy()) - 1.0
    out["mu"], out["p_home"] = np.nan, np.nan            # the harness's favourite split selects them
    return out


# ── OL: the off-line rule ───────────────────────────────────────────────────

def count_tables(log: pd.DataFrame, rows: pd.DataFrame) -> dict:
    """(market, season) -> the first search's count table, width fitted on seasons before the season."""
    out = {}
    for m, gm in rows.groupby("market", sort=False):
        lines = gm["line"].to_numpy(float)
        for s in sorted(int(x) for x in gm["season"].unique()):
            out[(m, s)] = PM.NBTable(PM.nb_alpha(log, m, s), lines)
    return out


def _by_table(rows: pd.DataFrame, tabs: dict, fn: str, value: np.ndarray) -> np.ndarray:
    out = np.full(len(rows), np.nan)
    lines = rows["line"].to_numpy(float)
    for (m, s), idx in rows.groupby(["market", "season"], sort=False).indices.items():
        t = tabs[(m, int(s))]
        out[idx] = getattr(t, fn)(lines[idx], value[idx])
    return out


@dataclass
class PinnacleQuotes:
    rows: pd.DataFrame    # the deciding books' quotes on propositions Pinnacle quotes, with Lref, p_ref, gap, fair_over


def pinnacle_quotes(r: pd.DataFrame, tabs: dict) -> PinnacleQuotes:
    """Pinnacle's line and implied mean per proposition, and each deciding book's fair over at its own
    line through the count distribution (first search, section 5)."""
    cnt = r[r["market"].isin(COUNT_MARKETS)]
    pin = cnt[cnt["bookmaker"] == H.SHARP].copy()
    pin["mu_ref"] = _by_table(pin, tabs, "mu_from", pin["p"].to_numpy(float))
    ref = pin[["prop_id", "line", "p", "mu_ref"]].rename(columns={"line": "Lref", "p": "p_ref"})
    q = cnt[cnt["bookmaker"].isin(H.BETTABLE)].merge(ref, on="prop_id")
    q["gap"] = q["line"] - q["Lref"]
    q["fair_over"] = _by_table(q, tabs, "p_over", q["mu_ref"].to_numpy(float))
    return PinnacleQuotes(q.reset_index(drop=True))


def gap_side(side: np.ndarray, gap: np.ndarray) -> np.ndarray:
    """True on the side the gap favours: under when the book's line is above Pinnacle's, over below."""
    return ((side == "under") & (gap > 0)) | ((side == "over") & (gap < 0))


def offline_offers(pq: PinnacleQuotes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(every off-line quote on both sides, flagged where the rule bets; the blind population)."""
    q = pq.rows
    off = q[q["gap"] != 0]
    uni = long_offers(off, off["fair_over"].to_numpy(float), extra=("gap", "Lref"))
    uni["cand"] = gap_side(uni["side"].to_numpy(dtype=object), uni["gap"].to_numpy(float))
    neutral = long_offers(q[q["prop_id"].isin(off["prop_id"])],
                          q.loc[q["prop_id"].isin(off["prop_id"]), "fair_over"].to_numpy(float), extra=("gap", "Lref"))
    return uni, neutral


def same_line_offers(pq: PinnacleQuotes) -> pd.DataFrame:
    """The shipped rule's population: deciding books at Pinnacle's line, Pinnacle's own no-vig."""
    q = pq.rows
    s = q[(q["gap"] == 0) & q["market"].isin(SHIPPED_MARKETS)]
    return long_offers(s, s["p_ref"].to_numpy(float), extra=("gap", "Lref"))


# ── CS: the soft-consensus rule ─────────────────────────────────────────────

def consensus_offers(r: pd.DataFrame, min_others: int = 3) -> pd.DataFrame:
    """On propositions with no Pinnacle quote, each deciding book's quote with the median no-vig over
    of the OTHER books at the same line (first search, section 4). Bovada counts among the others."""
    has_pin = r.loc[r["bookmaker"] == H.SHARP, "prop_id"].unique()
    u = r[~r["prop_id"].isin(has_pin)]
    soft = u[u["bookmaker"].isin(H.BETTABLE)].reset_index(drop=True)
    soft["rid"] = np.arange(len(soft))
    j = soft[["rid", "prop_id", "line", "bookmaker"]].merge(
        u[["prop_id", "line", "bookmaker", "p"]].rename(columns={"bookmaker": "other"}), on=["prop_id", "line"])
    j = j[j["other"] != j["bookmaker"]]
    agg = j.groupby("rid")["p"].agg(["median", "size"])
    soft = soft.join(agg, on="rid")
    soft = soft[soft["size"] >= min_others]
    out = long_offers(soft, soft["median"].to_numpy(float))
    out["cand"] = True
    return out


# ── AN: the market-anchored model ───────────────────────────────────────────

def references(r: pd.DataFrame, min_books: int = 3) -> pd.DataFrame:
    """Per count-market proposition: the reference kind, its line and its no-vig over."""
    cnt = r[r["market"].isin(COUNT_MARKETS)]
    pin = cnt[cnt["bookmaker"] == H.SHARP]
    a = pin[["prop_id", "line", "p"]].rename(columns={"line": "Lref", "p": "p_ref"}).assign(ref="pinnacle")
    rest = cnt[~cnt["prop_id"].isin(pin["prop_id"]) & cnt["bookmaker"].isin(H.BETTABLE)]
    main = PM.main_line_table(rest.assign(coherent=True))
    at = rest.merge(main[KEY + ["line"]], on=KEY + ["line"])
    g = at.groupby("prop_id")["p"].agg(["median", "size"])
    g = g[g["size"] >= min_books]
    b = at.drop_duplicates("prop_id")[["prop_id", "line"]].rename(columns={"line": "Lref"})
    b = b.merge(g["median"].rename("p_ref"), left_on="prop_id", right_index=True).assign(ref="consensus")
    return pd.concat([a, b], ignore_index=True)


def logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def expit(z) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def market_mean(preds: pd.DataFrame, market: str) -> np.ndarray:
    """The projected mean of a market: its base stats' fold means summed."""
    return np.clip(sum(preds[f"mu_{s}"].to_numpy(float) for s in nb.BY_MARKET[market].parts), pj.MU_FLOOR, None)


def fold_widths(preds: pd.DataFrame) -> dict:
    """(market, S) -> negative-binomial width fitted on season S-1 as predicted by the fold that never
    saw it, as record 5 fitted each graded season's."""
    out = {}
    for S in SEASONS:
        te = preds[(preds["season"] == S - 1) & preds["played"].astype(bool)]
        for m in COUNT_MARKETS:
            y = nb.settle_value(nb.BY_MARKET[m], te).to_numpy(float)
            out[(m, S)] = nb.fit_alpha(y, market_mean(te, m))
    return out


def anchored_table(ref: pd.DataFrame, props: pd.DataFrame, preds: pd.DataFrame, widths: dict) -> pd.DataFrame:
    """One row per proposition with a reference and a projection: the offset and every input as of the
    snapshot, a report read REPORT_LAG_MIN after print (lab_inputs). Out players and players under 10 career
    games have no row (fold predictions hold only nb.usable rows)."""
    p = props[["prop_id", "game_id", "player_id", "market", "season", "game_date"]].merge(ref, on="prop_id")
    pr = preds[preds["season"].isin(SEASONS)].drop_duplicates(["game_id", "player_id"])
    pr = pr[pr["status"].astype(object) != "Out"]
    t = p.merge(pr.drop(columns="season"), on=["game_id", "player_id"])
    t["offset"] = logit(t["p_ref"].to_numpy(float))
    d = np.full(len(t), np.nan)
    for (m, s), idx in t.groupby(["market", "season"], sort=False).indices.items():
        sub = t.iloc[idx]
        pn = nb.p_over(market_mean(sub, m), sub["Lref"].to_numpy(float), float(widths[(m, int(s))]))
        d[idx] = np.clip(logit(pn) - sub["offset"].to_numpy(float), -DISAGREE_LIMIT, DISAGREE_LIMIT)
    t["disagree"] = d
    t["is_home"] = t["is_home"].astype(float)
    return t


def fill_inputs(train: pd.DataFrame, rows: pd.DataFrame, inputs) -> np.ndarray:
    """Report inputs read 0 where no report covers the game; every other missing input reads the
    training rows' mean. By position: the frames carry their own indexes."""
    out = np.empty((len(rows), len(inputs)))
    for j, c in enumerate(inputs):
        v = rows[c].to_numpy(float)
        seen = train[c].to_numpy(float)
        seen = seen[np.isfinite(seen)]
        fill = 0.0 if c in REPORT_INPUTS or not len(seen) else float(seen.mean())
        out[:, j] = np.where(np.isfinite(v), v, fill)
    return out


def fit_moves(table: pd.DataFrame, stat: np.ndarray, inputs=INPUTS, graded=AN_GRADED,
              min_rows: int = MIN_MODEL_ROWS) -> tuple[np.ndarray, list[dict]]:
    """Each graded row's move: the fit's log-odds less the offset. One model per (market, reference
    kind, graded season), fitted on earlier seasons only. `stat` is read at earlier seasons' rows only."""
    inputs = list(inputs)
    move = np.full(len(table), np.nan)
    notes = []
    season = table["season"].to_numpy(int)
    x = np.asarray(stat, float)[table["prop_id"].to_numpy(np.int64)]
    line = table["Lref"].to_numpy(float)
    offset = table["offset"].to_numpy(float)
    groups = table.groupby(["market", "ref"], sort=False).indices
    for S in graded:
        for (m, ref), idx in groups.items():
            test = idx[season[idx] == S]
            train = idx[season[idx] < S]
            if not len(test) or len(train) < min_rows:
                notes.append({"season": S, "market": m, "ref": ref, "train": int(len(train)), "test": int(len(test)),
                              "C": np.nan, "fitted": False})
                continue
            tr = table.iloc[train]
            X = fill_inputs(tr, tr, inputs)
            assert np.isfinite(X).all(), f"an input stayed missing in {m} {ref} {S}"
            y = (x[train] > line[train]).astype(float)
            d = pd.DataFrame(X, columns=inputs)
            d["season"], d["y"], d["mkt_logit"] = season[train], y, offset[train]
            C = NA.choose_C(d, inputs) if inputs else NA.C_GRID[0]
            model = NA.OffsetLogit(C).fit(X, y, offset[train])
            p = model.predict_proba(fill_inputs(tr, table.iloc[test], inputs), offset[test])[:, 1]
            move[test] = logit(p) - offset[test]
            notes.append({"season": S, "market": m, "ref": ref, "train": int(len(train)), "test": int(len(test)),
                          "C": float(C), "fitted": True})
    return move, notes


def anchored_offers(r: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """The deciding books' quotes at the reference line: one row per side, with the proposition's
    position in `table` (tidx). The market's own number, no move, gives the blind population's EV."""
    t = table[["prop_id", "Lref", "p_ref"]].assign(tidx=np.arange(len(table)))
    q = r[r["bookmaker"].isin(H.BETTABLE)].merge(t, on="prop_id")
    q = q[q["line"] == q["Lref"]]
    q = q[q["season"].isin(AN_GRADED)]
    return long_offers(q, q["p_ref"].to_numpy(float), extra=("tidx",))


# ── the placebos ────────────────────────────────────────────────────────────

def permute_within(groups: np.ndarray, rng) -> np.ndarray:
    """out[i] = the position whose reading position i takes: a random permutation inside each group."""
    groups = np.asarray(groups)
    base = np.argsort(groups, kind="stable")
    order = np.lexsort((rng.random(len(groups)), groups))
    out = np.empty(len(groups), dtype=np.int64)
    out[base] = order
    return out


class Reading:
    """OL, CS: each proposition's reading moves whole to another on the same date and market.

    `uni`: the family's offers, both sides, `cand` True where the real rule bets. Only offers at or
    above the price floor exist for it, as for H.choose. On a side where the proposition has a real
    candidate only those offers are in play, so the identity permutation returns the real bets; on a
    side where it has none, all its offers there are in play, and a donor can send it there."""

    def __init__(self, uni: pd.DataFrame, lowest: float):
        u = uni[uni["price"] >= H.PRICE_FLOOR].reset_index(drop=True)
        self.lowest = float(lowest)
        ids = np.unique(u["game_id"].to_numpy())
        idx = np.searchsorted(ids, u["game_id"].to_numpy())
        first = np.zeros(len(ids), dtype=np.int64)
        first[idx[::-1]] = np.arange(len(u))[::-1]
        self.groups = pd.DataFrame({"d": u["game_date"].to_numpy()[first], "m": u["prop_market"].to_numpy()[first]}
                                   ).groupby(["d", "m"], sort=False).ngroup().to_numpy()
        self.n = len(ids)
        side, ev, cand = u["side"].to_numpy(dtype=object), u["ev"].to_numpy(float), u["cand"].to_numpy(bool)
        self.parts = {}
        for s in ("over", "under"):
            on = side == s
            has = np.zeros(self.n, bool)
            has[idx[on & cand]] = True
            keep = on & (cand | ~has[idx])
            best = np.full(self.n, -np.inf)
            np.maximum.at(best, idx[keep], ev[keep])
            strength = np.where(has, best, np.nan)
            self.parts[s] = {"rows": u.loc[keep, PICK_COLS].reset_index(drop=True), "idx": idx[keep],
                             "short": best[idx[keep]] - ev[keep], "strength": strength}
        self.cache: dict = {}

    def perm(self, seed: int | None) -> np.ndarray:
        return np.arange(self.n) if seed is None else permute_within(self.groups, np.random.default_rng(seed))

    def frame(self, side: str, seed: int | None) -> pd.DataFrame:
        k = (side, seed)
        if k not in self.cache:
            part = self.parts[side]
            ev = part["strength"][self.perm(seed)][part["idx"]] - part["short"]
            hit = np.nonzero(np.isfinite(ev) & (ev >= self.lowest - 1e-12))[0]
            self.cache[k] = (hit.astype(np.int32), ev[hit])
        hit, ev = self.cache[k]
        return self.parts[side]["rows"].iloc[hit].assign(ev=ev)

    def clear(self) -> None:
        self.cache.clear()


class MoveShuffle:
    """AN: each proposition's move goes to another on the same date, in the same market, with the same
    reference kind. It is added to the proposition's own offset and the offers are re-priced."""

    def __init__(self, offers: pd.DataFrame, table: pd.DataFrame, move: np.ndarray, lowest: float):
        ok = np.isfinite(move)
        tidx = offers["tidx"].to_numpy(np.int64)
        o = offers[ok[tidx]].reset_index(drop=True)
        ids, pos = np.unique(o["tidx"].to_numpy(np.int64), return_inverse=True)
        self.n, self.lowest = len(ids), float(lowest)
        self.pos, self.offset, self.move = pos, table["offset"].to_numpy(float)[ids], np.asarray(move, float)[ids]
        t = table.iloc[ids]
        self.groups = pd.DataFrame({"d": t["game_date"].to_numpy(), "m": t["market"].to_numpy(), "r": t["ref"].to_numpy()}
                                   ).groupby(["d", "m", "r"], sort=False).ngroup().to_numpy()
        self.offers = o
        self.dec = H.dec(o["price"].to_numpy(float))
        self.over = o["side"].to_numpy(dtype=object) == "over"
        self.cache: dict = {}

    def perm(self, seed: int | None) -> np.ndarray:
        return np.arange(self.n) if seed is None else permute_within(self.groups, np.random.default_rng(seed))

    def priced(self, seed: int | None) -> tuple[np.ndarray, np.ndarray]:
        """(the chance of the row's side, its EV) with the move read through the permutation."""
        p_over = expit(self.offset + self.move[self.perm(seed)])[self.pos]
        p = np.where(self.over, p_over, 1.0 - p_over)
        return p, p * self.dec - 1.0

    def real(self, side: str) -> pd.DataFrame:
        p, ev = self.priced(None)
        keep = (self.offers["side"] == side).to_numpy()
        return self.offers[keep].assign(p_win=p[keep], ev=ev[keep], p_push=0.0).reset_index(drop=True)

    def frame(self, side: str, seed: int | None) -> pd.DataFrame:
        k = (side, seed)
        if k not in self.cache:
            _, ev = self.priced(seed)
            on = self.over if side == "over" else ~self.over
            hit = np.nonzero(on & (ev >= self.lowest - 1e-12) & (self.offers["price"].to_numpy(float) >= H.PRICE_FLOOR))[0]
            self.cache[k] = (hit.astype(np.int32), ev[hit])
        hit, ev = self.cache[k]
        return self.offers.iloc[hit][PICK_COLS].assign(ev=ev)

    def clear(self) -> None:
        self.cache.clear()


# ── the groups of cells ─────────────────────────────────────────────────────

@dataclass
class Group:
    family: str
    ref: str
    rule: str
    side: str
    cuts: tuple
    lowest: float
    choose: tuple
    cand: pd.DataFrame
    neutral: pd.DataFrame
    placebo: object | None
    meaning: str
    bands: bool = True

    @property
    def name(self) -> str:
        return f"{self.family}_{self.ref}_{self.side}"


def ol_groups(pq: PinnacleQuotes) -> list[Group]:
    uni, neutral = offline_offers(pq)
    rd = Reading(uni, EV_LOWEST)
    out = []
    for side in ("under", "over"):
        cand = uni[uni["cand"] & (uni["side"] == side)].reset_index(drop=True)
        out.append(Group(FAMILY_OL, "pinnacle", "off_line", side, EV_CUTS, EV_LOWEST, CHOOSE_ALL, cand, neutral, rd,
                         "a deciding book off Pinnacle's line, the side the gap favours, priced from Pinnacle"))
        out.append(Group(CONTROL_OL, "pinnacle", "off_line_blind", side, (-np.inf,), EV_LOWEST, CHOOSE_ALL, cand, neutral,
                         None, "control: every offer on the side the gap favours, no EV floor", bands=False))
    return out


def same_line_group(pq: PinnacleQuotes) -> Group:
    s = same_line_offers(pq)
    cand = s[s["side"] == "under"].reset_index(drop=True)
    return Group(CONTROL_SAME, "pinnacle", "same_line", "under", (0.00,), EV_LOWEST, CHOOSE_ALL, cand, s, None,
                 "control: the shipped same-line unders against Pinnacle", bands=False)


def cs_groups(r: pd.DataFrame) -> list[Group]:
    uni = consensus_offers(r)
    rd = Reading(uni, EV_LOWEST)
    return [Group(FAMILY_CS, "consensus", "same_line", side, EV_CUTS, EV_LOWEST, CHOOSE_ALL,
                  uni[uni["side"] == side].reset_index(drop=True), uni, rd,
                  "no Pinnacle quote: a book's price against the other books' median at the same line")
            for side in ("under", "over")]


def an_groups(r: pd.DataFrame, table: pd.DataFrame, move: np.ndarray, lean: np.ndarray) -> list[Group]:
    offers = anchored_offers(r, table)
    refs = table["ref"].to_numpy(dtype=object)
    out = []
    for ref in ("pinnacle", "consensus"):
        keep = refs[offers["tidx"].to_numpy(np.int64)] == ref
        off = offers[keep].reset_index(drop=True)
        ms = MoveShuffle(off, table, move, AN_LOWEST)
        lean_ms = MoveShuffle(off, table, lean, AN_LOWEST)
        for side in ("under", "over"):
            out.append(Group(FAMILY_AN, ref, "anchored", side, AN_CUTS, AN_LOWEST, CHOOSE_AN, ms.real(side), off, ms,
                             "the market's no-vig as an offset, moved by the projection and its inputs"))
            out.append(Group(CONTROL_AN, ref, "anchored_lean", side, AN_CUTS, AN_LOWEST, CHOOSE_AN, lean_ms.real(side),
                             off, None, "control: the anchored model with its inputs removed, the intercept alone"))
    return out


# ── cells ───────────────────────────────────────────────────────────────────

def _placebo_frames(g: Group, seeds) -> G5.LazyFrames:
    """H.run_cells walks the runs once per cut: a progress line after each cut, since one group can take many
    minutes."""
    done = [0]

    def build(seed):
        done[0] += 1
        if done[0] % len(seeds) == 0:
            say(f"{g.name}: placebo, cut {done[0] // len(seeds)} of {len(g.cuts)}")
        return g.placebo.frame(g.side, seed)
    return G5.LazyFrames(seeds, build)


def emit(g: Group, games: pd.DataFrame, times: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[dict]:
    """One group's cells through H.run_cells, each row with its bands (section 9.1's bar 5)."""
    ids = set(g.cand["game_id"]) | set(g.neutral["game_id"])
    gm = games[games["game_id"].isin(ids)].reset_index(drop=True)
    dd = H.Data(games=gm, quotes=NO_QUOTES, fetches=NO_FETCHES)
    t = times[times["game_id"].isin(ids)].reset_index(drop=True)
    frames = None
    if g.placebo is not None and seeds:
        frames = _placebo_frames(g, seeds)
    # H.p_one_sided re-draws a small p with 400,000 resamples for the first search's false-discovery bar, about 40
    # seconds each under this machine's load. Section 9.1's bars do not read that p, and a zero-result smoke run
    # would never show the cost. Off for this search only: put back as soon as the harness returns.
    refine = H.P_REFINE_BELOW
    H.P_REFINE_BELOW = 0.0
    try:
        rows = H.run_cells(dd, g.family, POINT, g.cand, g.neutral, list(g.cuts), {LABEL: [g.side]}, placebo=frames,
                           strength="ev", choose_seasons=g.choose, times=t, market_groups={LABEL: (HMARKET,)})
    finally:
        H.P_REFINE_BELOW = refine
    for r in rows:
        if g.bands:
            bounds = G5.band_bounds(g.cuts, r["cut_index"], lowest=g.lowest)
            pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
            r.update(G5.band_columns(g.cand, r["side"], "ev", bounds, gm, pool))
        r.update({"axis_ref": g.ref, "axis_rule": g.rule, "signal_meaning": g.meaning})
    if g.placebo is not None:
        g.placebo.clear()
    return rows


def write_group(g: Group, rows: list[dict], beside: list[dict], out: Path) -> None:
    """The cell file comes last: it marks the group finished, so a stopped run redoes a part-written one."""
    pd.DataFrame(beside).to_parquet(out / f"beside_{g.name}.parquet")
    L.write_cells(rows, out / f"cells_{g.name}.parquet")


def write_model_files(prep, b: dict, out: Path) -> None:
    prep.props.drop(columns="T").to_parquet(out / "props.parquet")
    b["table"].drop(columns=[c for c in b["table"] if c.startswith("mu_")]).assign(move=b["move"], lean=b["lean"]).to_parquet(
        out / "model_rows.parquet")
    pd.DataFrame(b["fit_notes"]).to_parquet(out / "model_fits.parquet")


def registered_cells() -> list[tuple]:
    """(family, ref, side, cut): the 36 cells of the doc's table."""
    cells = [(FAMILY_OL, "pinnacle", s, c) for s in ("under", "over") for c in EV_CUTS]
    cells += [(FAMILY_CS, "consensus", s, c) for s in ("under", "over") for c in EV_CUTS]
    cells += [(FAMILY_AN, r, s, c) for r in ("pinnacle", "consensus") for s in ("under", "over") for c in AN_CUTS]
    assert len(cells) == EXPECTED_CELLS, len(cells)
    return cells


# ── reported beside, never a bar ────────────────────────────────────────────

def _line(g: Group, cut: float, what: str, b: pd.DataFrame) -> dict:
    return {"family": g.family, "ref": g.ref, "side": g.side, "cut": cut, "what": what, "bets": int(len(b)),
            "units": float(b["units"].sum()) if len(b) else 0.0,
            "risk": float(b["risk"].sum()) if len(b) else 0.0, "roi": H.roi(b) if len(b) else np.nan}


def beside_rows(g: Group, games: pd.DataFrame, props: pd.DataFrame, shipped: set, card: set) -> list[dict]:
    """The doc's reported-beside list, every cut. Runs on what `games` holds: the graded run's stats,
    or zeros in the timed smoke run (whose rows are thrown away)."""
    rows = []
    lead = props.set_index("prop_id")["lead_min"]
    cand = g.cand
    for cut in g.cuts:
        b = H.grade(H.choose(cand, cut, sides=[g.side]), games)
        rows.append(_line(g, cut, "all", b))
        if not len(b):
            continue
        ld = b["game_id"].map(lead).to_numpy(float)
        rows.append(_line(g, cut, "lead 50-60", b[(ld >= 50) & (ld < 60)]))
        rows.append(_line(g, cut, "lead 60-70", b[(ld >= 60) & (ld <= 70)]))
        for bk in ("hardrockbet", "fanduel"):
            books = tuple(x for x in H.BETTABLE if x != bk)
            rows.append(_line(g, cut, f"without {bk}", H.grade(H.choose(cand, cut, books=books, sides=[g.side]), games)))
        for bk, d in b.groupby("book"):
            rows.append(_line(g, cut, f"at {bk}", d))
        if "gap" in cand:
            a = b["gap"].abs().to_numpy(float)
            rows += [_line(g, cut, "gap 1", b[a <= 1]), _line(g, cut, "gap 2", b[(a > 1) & (a <= 2)]),
                     _line(g, cut, "gap 3 and more", b[a > 2])]
        edge = cand["p_win"].to_numpy(float) - H.imp(cand["price"].to_numpy(float))
        wild = set(cand.loc[edge > EDGE_BESIDE, "game_id"])
        rows.append(_line(g, cut, f"without offers more than {EDGE_BESIDE} above the implied chance",
                          H.grade(H.choose(cand[~cand["game_id"].isin(wild)], cut, sides=[g.side]), games)))
        ids = b["game_id"]
        rows.append(_line(g, cut, "on propositions the same-line rule holds", b[ids.isin(shipped)]))
        rows.append(_line(g, cut, "on propositions the projection card holds", b[ids.isin(card)]))
        rows.append(_line(g, cut, "on propositions neither holds", b[~ids.isin(shipped) & ~ids.isin(card)]))
        for s in sorted(b["season"].unique()):
            rows.append(_line(g, cut, f"season {int(s)}", b[b["season"] == s]))
        q = np.percentile(b["price"].to_numpy(float), [0, 5, 50, 95, 100])
        rows.append({"family": g.family, "ref": g.ref, "side": g.side, "cut": cut, "what": "prices laid",
                     "bets": int(len(b)), "price_min": q[0], "price_p5": q[1], "price_median": q[2],
                     "price_p95": q[3], "price_max": q[4]})
    if "gap" in g.neutral and g.family == FAMILY_OL:
        pop = set(g.cand["game_id"])
        at_ref = g.neutral[(g.neutral["gap"] == 0) & g.neutral["game_id"].isin(pop)]
        rows.append(_line(g, np.nan, "blind, best price at Pinnacle's own line",
                          H.grade(H.choose(at_ref, -np.inf, sides=[g.side]), games)))
    return rows


def card_propositions(r: pd.DataFrame, props: pd.DataFrame, preds: pd.DataFrame, widths: dict,
                      stat: np.ndarray, shipped: set) -> set:
    """The propositions the shipped projection card holds in 2024-25 and 2025-26, for the overlap
    column only: its six markets, its floors, the main line, Platt maps fitted on earlier seasons'
    main-line pairs. Earlier seasons' stats are read for the maps; 2023-24 has no map."""
    mk = list(pj.MARKETS)
    q = r[r["market"].isin(mk) & r["bookmaker"].isin(H.BETTABLE)]
    dk = q[q["bookmaker"] == H.DK].drop_duplicates("prop_id").set_index("prop_id")["line"]
    mode = (q.groupby(["prop_id", "line"]).size().rename("n").reset_index().sort_values(["n", "line"], ascending=[False, True])
            .drop_duplicates("prop_id").set_index("prop_id")["line"])
    main = dk.combine_first(mode)
    q = q[q["line"].to_numpy(float) == q["prop_id"].map(main).to_numpy(float)]
    p = props[["prop_id", "game_id", "player_id", "market", "season"]].merge(
        preds[preds["season"].isin(SEASONS)].drop_duplicates(["game_id", "player_id"]).drop(columns="season"),
        on=["game_id", "player_id"])
    p = p[p["status"].astype(object) != "Out"]
    p["main"] = p["prop_id"].map(main)
    p = p[p["main"].notna()]
    p["p_raw"] = np.nan
    for (m, s), idx in p.groupby(["market", "season"], sort=False).indices.items():
        sub = p.iloc[idx]
        p.iloc[idx, p.columns.get_loc("p_raw")] = nb.p_over(market_mean(sub, m), sub["main"].to_numpy(float),
                                                            float(widths[(m, int(s))]))
    y = (np.asarray(stat, float)[p["prop_id"].to_numpy(np.int64)] > p["main"].to_numpy(float)).astype(float)
    held: set = set()
    for S in AN_GRADED:
        pairs = pd.DataFrame({"season": p["season"].to_numpy(int), "market": p["market"].to_numpy(), "p": p["p_raw"].to_numpy(),
                              "y": y})
        if not (pairs["season"] < S).any():
            continue
        maps = nb.fit_calibration(pairs, S)       # reads seasons before S only
        cur = p[p["season"] == S]
        cal = np.empty(len(cur))
        for m, idx in cur.groupby("market", sort=False).indices.items():
            cal[idx] = nb.apply_calibration(cur["p_raw"].to_numpy(float)[idx], maps[m])
        fair = dict(zip(cur["prop_id"].to_numpy(np.int64), cal))
        s = q[q["prop_id"].isin(fair)]
        fo = s["prop_id"].map(fair).to_numpy(float)
        ov = H.dec(s["over_price"].to_numpy(float)) * fo - 1.0
        un = H.dec(s["under_price"].to_numpy(float)) * (1.0 - fo) - 1.0
        for m, (sides, floor) in pj.CARD.items():
            on = (s["market"] == m).to_numpy()
            if "over" in sides:
                held |= set(s.loc[on & (ov >= floor) & (s["over_price"].to_numpy(float) >= H.PRICE_FLOOR), "prop_id"])
            if "under" in sides:
                held |= set(s.loc[on & (un >= floor) & (s["under_price"].to_numpy(float) >= H.PRICE_FLOOR), "prop_id"])
    return held - shipped


# ── the projection folds: refit, cached, regenerable from the research cache ──

# One thread. Measured 2026-10-31 on this machine under its shared load, 20 trees on 90,000 rows: one
# thread 10 seconds, two threads 178 seconds; eight threads took 2,004 seconds for one 300-tree model.
# Threads waiting on each other are what costs, so the speed comes from one thread per process.
FOLD_THREADS = int(os.environ.get("NBA_S_FOLD_THREADS", "1"))


def report_as_known(report: pd.DataFrame, decisions: pd.DataFrame, lag_min: int = REPORT_LAG_MIN) -> pd.DataFrame:
    """The compact report the projection reads, each row stamped with when it could be known: printed time plus
    lag_min. The shift has to land before pj.compact_report, which keeps only each team's latest report at or before
    the decision: shifted after it, the earlier report a late one displaced is already gone. (The shape of
    scripts/nba_prop_model_verify.collapse_report's lag. Everything downstream compares these stamps with the decision,
    so nothing else adds a lag.)"""
    r = pj.collapse_official(report)
    r["report_ts"] = r["report_ts"] + pd.Timedelta(minutes=lag_min)
    return pj.compact_report(r, decisions)


def lab_inputs(cache: Path, lag_min: int = REPORT_LAG_MIN) -> tuple[dict, pd.DataFrame]:
    """scripts/nba_prop_projection_train.research_inputs, but for reading the report through report_as_known. The
    shipped file is not this lab's to change, and a test holds this copy to it at lag 0."""
    from scripts.nba_prop_projection_train import LAST_RESEARCH_DATE
    raw = nb.load_cache(cache, with_props=True, with_lines=False)
    props = raw["nba_props"]
    decisions = nb.decisions_for(raw, props[props.game_date < LAST_RESEARCH_DATE])
    report = report_as_known(raw["nba_injury_report"], decisions, lag_min)
    data = pj.worker_data(raw["nba_games"], raw["nba_schedule"], raw["nba_player_game_log"], report, decisions)
    return data, decisions


def fold_file(work: Path, season: int) -> Path:
    """A fold is named for the report lag it was fitted on, so no other read can ever load it."""
    return Path(work) / f"pred_{season}_lag{REPORT_LAG_MIN}.parquet"


def part_file(work: Path, season: int, what: str) -> Path:
    """One model's predictions inside a fold, named for the lag too: a stopped refit resumes from these."""
    return Path(work) / f"part_{season}_lag{REPORT_LAG_MIN}_{what}.npy"


def fold_predictions(cache: Path = H.CACHE, work: Path = WORK) -> pd.DataFrame:
    """Season S's rostered rows predicted by a fold fitted on 2018-19 .. S-1: minutes and all seven base
    stats' means on the worker's inputs (record 4.5), reading a report REPORT_LAG_MIN after print. The earlier
    stored folds are gone, so each model's predictions are refitted once and cached in `work`, one file per
    fold and model, so a stopped refit resumes. Threads are held to FOLD_THREADS: the model is unchanged, only
    how many cores fit it."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    files = {S: fold_file(work, S) for S in FOLDS}
    if not all(f.exists() for f in files.values()):
        t0 = time.time()
        for d in (nb.XGB_MIN, nb.XGB_COUNT):
            d["n_jobs"] = FOLD_THREADS
        data, dec = lab_inputs(Path(cache))
        fr = nb.build_frame(data, dec, with_lines=False)
        say(f"projection frame {fr.shape} in {time.time() - t0:.0f}s; fitting on {FOLD_THREADS} threads")
        use = nb.usable(fr)
        for S, f in files.items():
            if f.exists():
                continue
            tr = fr[use & fr.played & fr.season.between(nb.FIRST_TRAIN_SEASON, S - 1)]
            te = fr[use & (fr.season == S)]
            part = part_file(work, S, "minutes")
            if part.exists():
                mins = np.load(part)
            else:
                mins = nb.predict_minutes(nb.fit_minutes(tr, cols=pj.minutes_cols()), te)
                np.save(part, mins)
                say(f"fold {S} minutes at {time.time() - t0:.0f}s: train {len(tr):,}, scored {len(te):,}")
            out = te[list(FRAME_KEEP)].copy()
            out["min_hat"] = mins
            for st in nb.BASE_STATS:
                part = part_file(work, S, st)
                if part.exists():
                    out[f"mu_{st}"] = np.load(part)
                    continue
                out[f"mu_{st}"] = nb.predict_rate_mean(nb.fit_rate(tr, st, cols=pj.rate_cols(st)), te, mins)
                np.save(part, out[f"mu_{st}"].to_numpy())
                say(f"fold {S} {st} at {time.time() - t0:.0f}s")
            out.to_parquet(f)
    cols = list(FRAME_KEEP) + ["min_hat"] + [f"mu_{st}" for st in nb.BASE_STATS]
    out = pd.concat([pd.read_parquet(files[S], columns=cols) for S in FOLDS], ignore_index=True)
    out["player_id"] = out["player_id"].astype(str)
    return out


# ── synthetic world (each rule's test is watched failing with the rule broken) ──

def _american(p: float) -> float:
    p = float(np.clip(p, 0.02, 0.98))
    return float(round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p))


def synthetic_world(seed: int = 1, days: int = 25, edge: bool = True, projection_sd: float = 0.03,
                    market_sd: float = 0.15) -> dict:
    """A small invented prop history holding every kind of proposition a family reads: Pinnacle-quoted
    props with a deciding book off its line, and Pinnacle-absent props with five books at one line. The
    stat is drawn from a known mean. The market's number is that mean with noise of size market_sd.

    edge=True: the off-line book's price stays near even, so it under-adjusts for its gap and the side
    the gap favours has a real edge. edge=False: the books price their own lines from the market's mean
    and Pinnacle's price carries noise that knows nothing, so its disagreement with a book is worth nothing
    (a flat world also wants market_sd=0: a book priced off a noisy mean is a mispriced book). projection_sd:
    how far the projection sits from the truth (small: it knows more than the market; large: it is noise)."""
    rng = np.random.default_rng(seed)
    rows, box, preds = [], [], []
    for season, year in zip((2023, 2024, 2025, 2026), (2022, 2023, 2024, 2025)):
        for d in range(days):
            date = str(pd.Timestamp(f"{year}-11-01") + pd.Timedelta(days=d))[:10]
            for g in range(3):
                gid, snap = f"NBA_{date}_G{g}", f"{date}T23:05:00Z"
                for pl in range(10):
                    pid, base = f"{g}{pl}", 8.0 + 2.0 * pl
                    truth = base * float(rng.lognormal(0.0, 0.18))
                    stat, other = float(rng.poisson(truth)), float(rng.poisson(4.0))
                    box.append({"game_id": gid, "player_id": pid, "season": season, "minutes": 30.0, "points": stat,
                                "rebounds": 5.0, "assists": other, "fg3_made": 1.0, "blocks": 0.0, "steals": 1.0,
                                "turnovers": 1.0})
                    quoted = pl % 2 == 0
                    preds.append({"game_id": gid, "player_id": pid, "season": season, "played": True,
                                  "status": "Listed none", "is_home": float(pl % 2), "rest": 2.0, "b2b": 0.0,
                                  "pace_l": 100.0, "opp_pace_l": np.nan if pl == 0 else 100.0 + float(rng.normal(0, 3)), "tm_o_min": float(rng.integers(0, 2)) * 20.0,
                                  "d_o_min": 0.0, "tm_q_min": 0.0, "opp_o_min": np.nan, "own_q": 0.0, "min_hat": 30.0,
                                  **{f"mu_{s}": 1.0 for s in nb.BASE_STATS},
                                  "mu_points": truth * float(rng.lognormal(0.0, projection_sd)), "mu_assists": 4.0,
                                  "points": stat, "rebounds": 5.0, "assists": other, "fg3_made": 1.0, "steals": 1.0,
                                  "blocks": 0.0, "turnovers": 1.0})
                    if season < 2024:
                        continue
                    market_mean_ = truth * float(rng.lognormal(0.0, market_sd))
                    main = np.floor(base) + 0.5
                    pm = "player_points" if quoted else "player_points_assists"
                    x = stat if quoted else stat + other
                    shift = 0.0 if quoted else 4.0
                    fair_at = lambda ln: float(np.clip(nb.p_over(np.array([market_mean_ + shift]), np.array([ln]), 0.0)[0],
                                                       0.15, 0.85))
                    q = []
                    if quoted:
                        q.append(("pinnacle", main, fair_at(main) if edge
                                  else float(np.clip(fair_at(main) + rng.normal(0, 0.06), 0.15, 0.85))))
                        for bk in ("draftkings", "fanduel", "betmgm"):
                            q.append((bk, main, float(np.clip(fair_at(main) + rng.normal(0, 0.01), 0.15, 0.85))))
                        ln = main + float(rng.choice([-1.0, 1.0]))
                        off = float(np.clip(0.5 + 0.2 * (fair_at(main) - 0.5), 0.15, 0.85)) if edge else fair_at(ln)
                        q.append(("betrivers", ln, off))
                    else:
                        for bk in ("draftkings", "fanduel", "betmgm", "betrivers", "fanatics"):
                            q.append((bk, main + shift, float(np.clip(fair_at(main + shift) + rng.normal(0, 0.02), 0.15, 0.85))))
                    for bk, ln, pf in q:
                        op, up = _american(pf * 1.035), _american((1 - pf) * 1.035)
                        rows.append({"game_id": gid, "game_date": date, "season": season, "player_id": pid,
                                     "player_name": f"P{g}{pl}", "market": pm, "bookmaker": bk, "line": ln,
                                     "over_price": op, "under_price": up, "od": float(H.dec(op)), "ud": float(H.dec(up)),
                                     "lead_min": 54.4, "snapshot_at": snap, "x": x, "usable": True,
                                     "coherent": bool(1.0 <= H.imp(op) + H.imp(up) <= 1.15)})
    return {"quotes": pd.DataFrame(rows), "log": pd.DataFrame(box),
            "preds": pd.DataFrame(preds).assign(player_id=lambda f: f["player_id"].astype(str))}


def world_prep(world: dict) -> Prep:
    """The invented world as prepare() would hand it to build_all()."""
    ceil = {m: 500.0 for m in (*COUNT_MARKETS, *DD_TD)}
    rows, notes = eligible(world["quotes"], ceil)
    r, props, stat = with_props(rows)
    return Prep(r, props, stat, notes, ceil, world["log"])


def world_groups(world: dict) -> tuple[list[Group], pd.DataFrame, np.ndarray, pd.DataFrame]:
    """Every group, from the same builder the real data goes through."""
    prep = world_prep(world)
    b = build_all(prep, world["preds"])
    return b["groups"], prep.props, prep.stat, b["table"]


def _assert_identity(g: Group) -> None:
    """The identity permutation returns the real bets at every cut."""
    frame = g.placebo.frame(g.side, None)
    for cut in g.cuts:
        a = H.choose(g.cand, cut, sides=[g.side])[["game_id", "book"]].sort_values("game_id").to_numpy()
        b = H.choose(frame, cut, sides=[g.side])[["game_id", "book"]].sort_values("game_id").to_numpy()
        assert len(a) == len(b) and (a == b).all(), (g.name, cut, len(a), len(b))
    g.placebo.clear()


def synthetic_checks(n_placebo: int = 3) -> dict:
    """Arithmetic and plumbing on the invented world. Raises on a fault. Asserts the world holds every
    family before believing a check that says it covers one."""
    world = synthetic_world()
    groups, props, stat, _ = world_groups(world)
    games, times = games_table(props, stat), times_table(props)
    seen = {}
    for g in groups:
        seen[g.name] = int(len(g.cand))
        assert len(g.cand) > 0, f"the synthetic world holds no offers for {g.name}"
        if g.placebo is not None:
            _assert_identity(g)
    cells = sum(len(g.cuts) for g in groups if g.family in (FAMILY_OL, FAMILY_CS, FAMILY_AN))
    assert cells == EXPECTED_CELLS, cells
    seeds = tuple(range(1, n_placebo + 1))
    rows = []
    for g in groups:
        rows += emit(g, games, times, seeds=seeds if g.placebo is not None else ())
    t = pd.DataFrame(rows)
    assert (t.loc[t["family"].isin((FAMILY_OL, FAMILY_CS, FAMILY_AN)), "pool_n"] > 0).any()
    return {"synthetic_checks": "pass", "offers": seen}


# ── real data ───────────────────────────────────────────────────────────────

@dataclass
class Prep:
    rows: pd.DataFrame
    props: pd.DataFrame
    stat: np.ndarray
    notes: dict
    ceilings: dict
    log: pd.DataFrame


def prepare(cache: Path = H.CACHE, work: Path = WORK) -> Prep:
    t0 = time.time()
    q = load_quotes(cache, work)
    q = q.drop(columns=[c for c in ("over_win",) if c in q])
    log = pd.read_parquet(Path(cache) / "nba_player_game_log.parquet")
    ceilings = box_ceilings(log)
    rows, notes = eligible(q, ceilings)
    r, props, stat = with_props(rows)
    say(f"rows ready in {time.time() - t0:.0f}s: {notes}")
    return Prep(r, props, stat, notes, ceilings, log)


def build_all(prep: Prep, preds: pd.DataFrame) -> dict:
    """Every group, the shipped keys and the card's keys, with the model's fit notes. Reads earlier
    seasons' stats for the model and the card's maps; grades nothing."""
    t0 = time.time()
    r = prep.rows
    tabs = count_tables(prep.log, r[r["market"].isin(r.loc[r["bookmaker"] == H.SHARP, "market"].unique())
                                    & r["market"].isin(COUNT_MARKETS)])
    say(f"count tables in {time.time() - t0:.0f}s")
    pq = pinnacle_quotes(r, tabs)
    say(f"Pinnacle-quoted deciding quotes {len(pq.rows):,} at {time.time() - t0:.0f}s")
    widths = fold_widths(preds)
    table = anchored_table(references(r), prep.props, preds, widths)
    move, notes = fit_moves(table, prep.stat)
    lean, _ = fit_moves(table, prep.stat, inputs=())
    say(f"anchored table {len(table):,}, fits done at {time.time() - t0:.0f}s")
    same = same_line_group(pq)
    shipped = set(H.choose(same.cand, 0.00, sides=["under"])["game_id"])
    card = card_propositions(r, prep.props, preds, widths, prep.stat, shipped)
    groups = ol_groups(pq) + [same] + cs_groups(r) + an_groups(r, table, move, lean)
    say(f"{len(groups)} groups at {time.time() - t0:.0f}s")
    return {"groups": groups, "shipped": shipped, "card": card, "fit_notes": notes, "table": table, "move": move, "lean": lean}


def extremes(prep: Prep) -> None:
    """Every line and price this search reads, the ceilings, and what each rule removed."""
    r = prep.rows
    print(json.dumps({"rule_counts": prep.notes, "ceilings": prep.ceilings}, indent=1))
    t = r.groupby("market").agg(rows=("line", "size"), line_min=("line", "min"), line_max=("line", "max"),
                                over_min=("over_price", "min"), over_max=("over_price", "max"),
                                under_min=("under_price", "min"), under_max=("under_price", "max"))
    print(t.to_string())
    print(r.groupby(["season", "bookmaker"]).size().unstack(0).to_string())


def top_offers(g: Group, n: int = 12) -> pd.DataFrame:
    return g.cand.sort_values("ev", ascending=False).head(n)


def counts_table(groups: list[Group]) -> pd.DataFrame:
    """The bets each cell would place: counted, never graded."""
    out = []
    for g in groups:
        for cut in g.cuts:
            b = H.choose(g.cand, cut, sides=[g.side])
            by = b["season"].value_counts().to_dict()
            out.append({"family": g.family, "ref": g.ref, "side": g.side, "cut": cut,
                        **{f"bets_{s}": int(by.get(s, 0)) for s in SEASONS}, "bets_pooled": int(len(b))})
    return pd.DataFrame(out)


def placebo_difference(groups: list[Group], seeds=(1, 2, 3)) -> pd.DataFrame:
    """By cell, on the real data: the share of a placebo run's bets not among the real bets (same
    proposition, side and book), and the run's bet count against the real count."""
    out = []
    for g in groups:
        if g.placebo is None:
            continue
        for cut in g.cuts:
            real = H.choose(g.cand, cut, sides=[g.side])
            rk = set(zip(real["game_id"], real["book"]))
            sh, n = [], []
            for s in seeds:
                pb = H.choose(g.placebo.frame(g.side, s), cut, sides=[g.side])
                same = np.fromiter(((a, b) in rk for a, b in zip(pb["game_id"], pb["book"])), bool, len(pb))
                sh.append(float(1 - same.mean()) if len(pb) else np.nan)
                n.append(len(pb))
            out.append({"family": g.family, "ref": g.ref, "side": g.side, "cut": cut, "real_bets": int(len(real)),
                        "placebo_bets": float(np.mean(n)), "share_differ": float(np.nanmean(sh))})
        g.placebo.clear()
    return pd.DataFrame(out)


def low_share_note(pl: pd.DataFrame) -> str:
    """The doc's promise: a cell whose placebo mostly repeats the real bets is named, in words."""
    low = pl[pl["share_differ"] < LOW_SHARE]
    if low.empty:
        return f"Every cell's placebo changes at least {LOW_SHARE:.0%} of its bets."
    names = ", ".join(f"{r.family} {r.ref} {r.side} EV >= {r.cut:.2f} ({r.share_differ:.2f})" for r in low.itertuples())
    return (f"LOW: in {len(low)} cells a placebo run changes under {LOW_SHARE:.0%} of the bets: {names}. Most of such a run "
            "is the real bets, so only the bets it changes can separate the real return from the placebo's. Read a pass "
            "or fail of the placebo bar in these cells with that in mind.")


def timed_runs(groups: list[Group], games0: pd.DataFrame, times: pd.DataFrame, props: pd.DataFrame,
               shipped: set, card: set, scratch: Path) -> pd.DataFrame:
    """Each group once with no placebo, then three placebo runs through the same steps H.run_cells takes
    per run (the frame, the market filter, the choice, the grade, the choosing seasons' return, per cut),
    on results set to zero, so the time is the real code path's and nothing real is graded. The projection
    uses the median run, so one stall on this shared machine does not read as 200 stalls. Each group's files are
    written to `scratch` through --full's own writer and thrown away, so a column parquet refuses shows here and
    not an hour into --full. placebo_cache_mb: what 200 runs of this group hold in memory until the group ends."""
    out = []
    for g in groups:
        t0 = time.time()
        write_group(g, emit(g, games0, times, seeds=()), beside_rows(g, games0, props, shipped, card), scratch)
        base = time.time() - t0
        run, cache_mb = 0.0, 0.0
        if g.placebo is not None:
            ids = set(g.cand["game_id"]) | set(g.neutral["game_id"])
            gm = games0[games0["game_id"].isin(ids)].reset_index(drop=True)
            runs = []
            for seed in (1, 2, 3):
                t1 = time.time()
                for cut in g.cuts:
                    pc = g.placebo.frame(g.side, seed)
                    gp = H.grade(H.choose(pc[pc["market"].isin((HMARKET,))], cut, sides=[g.side]), gm)
                    if len(gp):
                        H.roi(gp[gp["season"].isin(g.choose)])
                runs.append(time.time() - t1)
            run = float(np.median(runs))
            hit, ev = g.placebo.cache[(g.side, 1)]
            cache_mb = N_PLACEBO * (hit.nbytes + ev.nbytes) / 2**20
            g.placebo.clear()
        out.append({"group": g.name, "seconds_without_placebo": round(base, 1), "seconds_one_placebo_all_cuts": round(run, 3),
                    "projected_seconds": round(base + N_PLACEBO * run, 1), "placebo_cache_mb": round(cache_mb, 1)})
    return pd.DataFrame(out)


def smoke_report(prep: Prep, preds: pd.DataFrame) -> dict:
    """Everything --smoke prints from a prepared cache. Nothing here grades on a real stat: the only
    H.grade calls are the timed runs, on games_table(props, None), whose scores are all zero."""
    os.environ.pop(BETS_ENV, None)                    # the timed runs must not write a bet file
    b = build_all(prep, preds)
    groups = b["groups"]
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 200)
    print(f"Injury reports read {REPORT_LAG_MIN} minutes after their printed time (AN, its control and the card's overlap).")
    extremes(prep)
    print("\nGames with a decision by season:",
          prep.props.drop_duplicates("game_id").groupby("season").size().to_dict())
    print("\nPropositions by reference kind and season (model rows):")
    print(b["table"].groupby(["ref", "season"]).size().unstack(1).to_string())
    print("\nModel fits (rows and penalty, no result):")
    print(pd.DataFrame(b["fit_notes"]).to_string(index=False))
    m = b["move"][np.isfinite(b["move"])]
    if not len(m):
        raise RuntimeError("the anchored model priced nothing: stop and find out why")
    print("\nMove off the market, log-odds, percentiles 1 / 50 / 99:", np.percentile(m, [1, 50, 99]).round(3).tolist())
    counts = counts_table(groups)
    print("\nCOUNTS BEFORE GRADING (bets each cell would place; no result read):")
    print(counts.to_string(index=False))
    want = {(FAMILY_OL, "under", 0.02): 7123, (FAMILY_CS, "under", 0.00): 17386, (CONTROL_SAME, "under", 0.00): 24572}
    print("\nAgainst the first search's counts (they had no -200 floor or 45-75 window except the shipped row):")
    for (f, sd, c), n in want.items():
        got = counts[(counts["family"] == f) & (counts["side"] == sd) & (counts["cut"] == c)]["bets_pooled"].sum()
        print(f"  {f} {sd} EV >= {c:.2f}: {int(got):,} here, {n:,} in the record")
    print("\nHighest-EV offers per family (no result read):")
    for g in groups:
        if g.family in (FAMILY_OL, FAMILY_CS, FAMILY_AN):
            t = top_offers(g, 8).merge(prep.props[["prop_id", "player_name", "game_date"]], left_on="game_id",
                                       right_on="prop_id", suffixes=("", "_p"))
            cols = [c for c in ("game_date", "player_name", "prop_market", "book", "line", "Lref", "gap", "side", "price",
                                "p_win", "ev") if c in t]
            print(g.name)
            print(t[cols].round(3).to_string(index=False))
    for g in groups:
        if g.placebo is not None:
            _assert_identity(g)
    print("\nPlacebo: the identity permutation returns the real bets in every group.")
    seen = {}
    for g in groups:
        if g.placebo is not None and id(g.placebo) not in seen:
            seen[id(g.placebo)] = 1
            sizes = pd.Series(g.placebo.groups).value_counts()
            print(f"  {g.family} {g.ref}: {g.placebo.n:,} propositions in {len(sizes):,} (date, market) groups; "
                  f"{float((sizes == 1).sum()) / max(g.placebo.n, 1):.2%} of propositions are alone in their group")
    pl = placebo_difference(groups)
    print("\nPLACEBO: share of placebo bets differing from the real bets, by cell, real data:")
    print(pl.round(3).to_string(index=False))
    print(low_share_note(pl))
    ot = {}
    for g in groups:
        if g.family in (FAMILY_OL, FAMILY_CS, FAMILY_AN):
            b0 = H.choose(g.cand, g.cuts[0], sides=[g.side])
            ids = b0["game_id"]
            ot[g.name] = {"bets_at_lowest_cut": int(len(b0)),
                          "share_same_line_rule": round(float(ids.isin(b["shipped"]).mean()), 3) if len(b0) else np.nan,
                          "share_projection_card": round(float(ids.isin(b["card"]).mean()), 3) if len(b0) else np.nan}
    print("\nOverlap with the shipped models (counts only):")
    print(pd.DataFrame(ot).T.to_string())
    games0 = games_table(prep.props, None)
    with tempfile.TemporaryDirectory() as scratch:
        write_model_files(prep, b, Path(scratch))
        tm = timed_runs(groups, games0, times_table(prep.props), prep.props, b["shipped"], b["card"], Path(scratch))
    print("\nTIMED on results set to zero (nothing real graded; every file --full writes was written once on these"
          " real shapes, and removed):")
    print(tm.to_string(index=False))
    return {"counts": counts, "placebo": pl, "timed": tm, "groups": groups}


def smoke(cache: Path = H.CACHE, work: Path = WORK) -> dict:
    t0 = time.time()
    print(json.dumps({k: v for k, v in synthetic_checks().items() if k == "synthetic_checks"}))
    say(f"synthetic checks done at {time.time() - t0:.0f}s")
    prep = prepare(cache, work)
    preds = fold_predictions(cache, work)
    used = time.time() - t0
    out = smoke_report(prep, preds)
    total = float(out["timed"]["projected_seconds"].sum())
    print(f"\nPROJECTED --full: {total / 60:.0f} minutes of cells, plus {used / 60:.0f} minutes of loading here "
          "(the folds are cached after the first run). Measured on this machine under its load at this moment.")
    extra = float(out["timed"]["placebo_cache_mb"].max()) / 1024
    try:
        import psutil
        print(f"peak memory of this process: {psutil.Process().memory_info().peak_wset / 2**30:.1f} GB; "
              f"--full adds at most {extra:.1f} GB for one group's 200 placebo runs")
    except (ImportError, AttributeError):
        print(f"peak memory not read: psutil is not installed; --full adds at most {extra:.1f} GB for one group's "
              "200 placebo runs")
    print(f"smoke took {(time.time() - t0) / 60:.0f} minutes")
    return out


def credit_table(cells: pd.DataFrame) -> pd.DataFrame:
    """The doc's credit rule for AN. The verdict's own credit map keys on market, side and cut with no
    reference kind, so it cannot read this control: Pinnacle's and the consensus's rows would collide. One
    row per AN cell: its pooled return against the control's at the same reference kind, side and cut (a
    control with no bet counts as 0). A cell is credited when it passes the verdict AND beats_control."""
    a = cells[cells["family"].astype(str) == FAMILY_AN]
    ctl = cells[cells["family"].astype(str) == CONTROL_AN].set_index(["axis_ref", "side", "cut_index"])["pool_roi"]
    got = np.array([ctl.get(k, np.nan) for k in zip(a["axis_ref"], a["side"], a["cut_index"])], dtype=float)
    return pd.DataFrame({"axis_ref": a["axis_ref"].to_numpy(), "side": a["side"].to_numpy(), "cut": a["cut"].to_numpy(),
                         "pool_roi": a["pool_roi"].to_numpy(float), "control_pool_roi": got,
                         "beats_control": a["pool_roi"].to_numpy(float) > np.nan_to_num(got, nan=0.0)})


def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    if not (Path(cache) / "nba_props.parquet").exists():
        why.append(f"{Path(cache) / 'nba_props.parquet'} does not exist: refresh the cache")
    return why


def full(cache: Path = H.CACHE, work: Path = WORK) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    synthetic_checks()
    say("synthetic checks pass")
    prep = prepare(cache, work)
    preds = fold_predictions(cache, work)
    b = build_all(prep, preds)
    groups = b["groups"]
    write_model_files(prep, b, out)
    games, times = games_table(prep.props, prep.stat), times_table(prep.props)
    t_cells, done = time.time(), 0
    for i, g in enumerate(groups, start=1):
        f = out / f"cells_{g.name}.parquet"
        if f.exists():
            say(f"group {i}/{len(groups)} {g.name}: already written, skipped")
            continue
        H._BET_FILES[0] = 1000 * i                    # bet files stay unique across a resumed run
        t1 = time.time()
        rows = emit(g, games, times, seeds=PLACEBO_SEEDS if g.placebo is not None else ())
        write_group(g, rows, beside_rows(g, games, prep.props, b["shipped"], b["card"]), out)
        done += 1
        left = (time.time() - t_cells) / done * (len(groups) - i) / 60
        say(f"group {i}/{len(groups)} {g.name}: {len(rows)} cells in {time.time() - t1:.0f}s; "
            f"{(time.time() - t0) / 60:.0f} minutes so far, about {left:.0f} left")
    credit_table(V.load_cells(out)).to_parquet(out / "credit_AN.parquet")
    say(f"cells written to {out}: judge with python -m scripts.nba_game2_verdict --results {out} --house5; "
        "the verdict's 'credited' column does not know the anchored control, so read credit_AN.parquet for that")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1, {RESULTS_ENV}, {BETS_ENV})")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
