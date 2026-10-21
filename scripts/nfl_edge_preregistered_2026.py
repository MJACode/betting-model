"""
The repo's pre-registered NFL rules, read on 2026 for the first time.

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_preregistered_2026

Reads ONLY the local cache (scripts/nfl_edge_lib.CACHE). No database, no Odds
API. The one network call is the free Open-Meteo historical-forecast endpoint
for part E (issued wind forecasts), cached under CACHE/openmeteo/.

=============================================================================
CONSTRUCTIONS -- written before any 2026 outcome was read. Every rule is the
EXISTING one, called through the production code where it can be imported
offline, with nothing re-tuned. 2026 is the hold-out of every part and is
read ONCE. The fit seasons are the ones each rule was built on (named below).
=============================================================================

THE 2026 SAMPLE. Results exist for weeks 1-4 (64 games) plus two week-5 games
(TB@DAL Thursday, PHI@JAX London). The player stat log holds weeks 1-4 and
TB@DAL only, so props are graded on 65 games and game lines on 66.

COMMON INFERENCE (all parts)
  * Units: 1 unit = one flat bet; a win at +150 pays +1.5u; push = 0.
  * ROI CI: 90%, bootstrap resampling GAMES (scripts.nfl_edge_lib.boot_ci).
  * Effective sample: games (clusters) and n_eff = n / deff, where
    deff = clustered variance of the mean / iid variance of the mean.
  * Consistency: z of the 2026 mean profit against (i) zero and (ii) the
    backtest ROI, using the cluster-robust standard error; two-sided p.
  * Power: bets needed for 2026 ALONE to separate the backtest ROI r from 0
    at one-sided alpha 0.05 with 80% power: n = ((1.645+0.842) sd / r)^2,
    sd = per-bet sd of the cell (and x deff for the clustered version).
  * Multiplicity: Benjamini-Hochberg at q = 0.10 over every 2026 cell each
    part searched (p vs zero, two-sided).

A. nfl_prop_market (models/nfl_prop_market.py, unmodified)
  Fit seasons 2023-25 (the shipped record). Hold-out 2026 weeks 1-5.
  * Board at lead L in {24, 12, 6, 3, 1.5}: props_2026 rows with
    lead_label >= L (lead_label -1 dropped), then per (game, market, player,
    book) the row with the latest snapshot_at across lines -- exactly the
    production loader (load_nfl_prop_quotes: latest row per key wins, whatever
    line it sits on). The cache has no snapshot_type, so production's
    ('open',) filter cannot be applied; pre-game = lead >= 0.
  * Selection: mk.find_bets(min_edge=0.05, soft_books=mk.SOFT_BOOKS,
    min_edge_by_side=config.NFL_PROP_MARKET_SIDE_EDGE (over 6 / under 5),
    no Kalshi ladders) -> injury veto (ESPN Out/Doubtful with status_ts <=
    quote, index built from the cached injuries table exactly as
    load_nfl_injury_index builds it, as_of = decision date) ->
    mk.best_per_prop. References pinnacle + betonlineag (either), equal lines,
    proportional de-vig. Graded at the selecting book's price.
  * Variants: DraftKings-only (soft_books = draftkings); the production EV
    gate (EV = fair x decimal - 1 >= config.min_ev_for = 0.20, on the RAW
    probability -- the calibration map lives in the database and is not read);
    the first-qualifying-read lock across labels 24..0 (production's pre-09-19
    hourly behaviour); the 13:xx UTC game-day read (production's publish pass
    since 09-19: T = 13:30 UTC on the ET game date, 2h <= lead <= 24h, latest
    quote at or before T from the cache -- approximate where the cache bucket
    holds a later quote, the exact-hit share is printed).
  * Neighbourhood: base cut 3..8pp, single floor and paired (over = base+1pp),
    at every label. The shipped cell is paired 5pp.
  * Placebo: FanDuel's own de-vig as the only reference, betting the other
    soft books (models.market_relative.find_bets, same cuts) -- must not work.
  * Extreme-props single-board-read cells (scripts/nfl_edge_extreme_props
    Part 1, its functions unmodified): one synchronous poll per (game,
    market) = the latest poll at or before kick - L, BETTABLE books, either
    reference, pooled sides, cut 6pp and 7pp, best bettable price at the line.
    Its 2023-25 numbers: 6pp 423 bets +19.3%, 7pp 72 bets +21.3%.
  * Actuals: 2026 stat log, joined on norm_player_name. A nickname rule
    (same game, same normalised surname, first names sharing their first
    three letters or in {josh/joshua, kenny/kenneth, chig/chigoziem}, unique
    candidate) rescues feed/log name mismatches; the count it affects is
    printed. There are no 2026 snap counts, so an active player with zero
    touches cannot be told from an inactive one: a missing actual is VOID
    (production grade() behaviour); count printed, with an "all = 0"
    sensitivity.
  * Backtest expectation: shipped paired record 1,248 bets +13.33% (open read,
    2023-25); synchronous Part-1 version 972 bets +14.3%.

B. Soft-book learned sharp stack, pass attempts
  (scripts/nfl_prop_market_stack, `--soft`, design 'sharp', cut 5%).
  The weights were never persisted, so the same offset-ridge logistic is
  re-fitted with the module's own _design/_fit/_bets on soft-book rows
  rebuilt from the cache (every soft book's tightest two-way `open` quote per
  DraftKings-quoted proposition, SOFT books as of 2026-09-12). STEP 1 is a
  reproduction gate: walk-forward 2024 and 2025 must land near the published
  109 / 150 bets (+16.5% / +16.4%) at 5%. Only if they do is the model
  re-fitted on 2023-25 and read on the 2026 boards (labels 24..1.5 and the
  13:xx read). Expectation: +16.4% (2025).

C. nfl_opener_spread (nfl/models/opener_spread.py, unmodified functions)
  Fit seasons 2020-25 (scripts/opener_cut_sweep.py: |dev| >= 2.0 on bettable
  books, 125 bets, +3.97%, CI -11.8..+19.1). Hold-out 2026.
  * Board: odds_2026 spreads, pre-game; Pinnacle + config.BETTABLE_BOOKS that
    the archive carries. A book's quote is its latest row at or before the
    decision time and at most 6h old (1h sensitivity).
  * dev = soft HOME point - Pinnacle HOME point; |dev| >= 2.0; bet the side
    Pinnacle favours at the soft number (home if dev > 0); price = that side's
    price at the soft book; om.model_prob_for_dev; skip if om.stake_units == 0;
    platform gates min_prob 0.55 and EV >= 0.01 (raw probability: the model
    is in config.MODELS_ON_OWN_PROBABILITY). One bet per game, the largest
    |dev| at the FIRST qualifying observation, never re-priced.
  * Window T-7..T-2 days (the backtested span) and T-10..T-2 (live default).
  * Observation schedules: daily 09:30 ET (the original card) and every
    archive minute (the card since 2026-09-06).
  * Neighbours |dev| 1.0 / 1.5 / 2.5 (sweep gates: Kelly skip, edge >= 0, no
    min_prob -- the sweep's own selection).
  * Single book: DraftKings only. Placebo: DraftKings as the reference,
    betting the other bettable books -- the repo's documented placebo.
  * The age of the soft number at the fire (minutes it had stood) is printed,
    with a >= 60-minute sensitivity.
  * The same code on odds_hist 2020-25 at snapshot resolution reproduces the
    expectation, so the 2026 read is compared like for like.

D. Wong teaser legs (scripts/nfl_edge_wong_teaser.py sets, unmodified)
  WONG: dogs x in {+1.5,+2,+2.5}, favourites {-7.5,-8,-8.5}; PLACEBO: dogs
  +3.5..+5.5, favourites -3.5..-6.5; teased 6: win if margin + x + 6 > 0.
  Line: DraftKings' own spread at its latest snapshot >= 1h before kickoff
  (odds_2026). Also the best bettable line and the nflverse close. Win rate
  vs the 2-team break-evens 73.85% (-120) and 75.79% (-135), exact binomial.
  Kickoff-order 2-team tickets per week. Expectation: 2020-25 bettable 75.66%
  (456 legs); the DraftKings-line 2020-25 rate is recomputed here.

E. nfl_wind_totals (nfl/models/wind_totals.py, unmodified)
  Production 2026 record from picks (settled BETs, units = profit_flat/100,
  priced rows only). The rule replayed: open-air (open_air_mask), Open-Meteo
  forecast for the kickoff hour ISSUED d days earlier (previous_day d), fire
  at the first d in 4,3,2,1 with forecast >= 11 mph (DEPLOY_THRESHOLD,
  MAX_FIRE_LEAD 4), model_under_prob(d, 11), price = the nflverse CLOSING
  total and under price (no 2026 totals board exists in the cache, so the
  line is the close, not the decision-time line), edge >= 0.03 vs the
  de-vigged close and EV >= 0.05. Placebo: calm open-air games and domes at
  the same close. Expectation: the model's own lead-4 probability 0.5634 at
  -110 is +7.6% ROI.

CHANGED AFTER THE FIRST RUN (disclosed; no selection rule moved)
  The first full run crashed in part D. Before it did, it printed parts A and
  C. Three mechanical bugs were fixed, then the script was run again in full:
  (1) nfl_edge_lib.odds_2026 strips the NFL_ prefix from game ids, so parts C
      and D joined no results (C printed zero bets everywhere);
  (2) the publish-pass clock was 13:25:00 UTC, which is BEFORE the 13:25:20
      poll it was meant to read; it is now 13:30;
  (3) cells under 10 bets or 5 games no longer get a normal-approximation p
      (they printed p = 0.000 on 2-3 winning bets) and stay out of the
      Benjamini-Hochberg family; power uses sd 1.0 and deff 1 below 30 bets.
  Cells ADDED after the first full run (all additive, none replaces a cell):
  part B's FanDuel placebo, DraftKings-only rows, 4/6% cuts and early/late;
  the FanDuel placebo for the extreme-props cells; the opener early/late
  split; the Wong per-line grid; the wind threshold neighbourhood
  (9..15 mph), its DraftKings-only production subset and early/late.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import config
import models.nfl_prop_market as mk
from models import market_relative as mr
from scripts import nfl_edge_lib as L
from scripts import nfl_edge_extreme_props as X

sys.path.append(str(ROOT / "nfl"))   # appended: repo `models` must win
from data_ingest.weather import open_air_mask, STADIUM_COORDS  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


om = _load("nfl_model_opener_spread", "nfl/models/opener_spread.py")
wt = _load("nfl_model_wind_totals", "nfl/models/wind_totals.py")

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)

C = L.CACHE
OM_DIR = C / "openmeteo"
LABELS = [24.0, 12.0, 6.0, 3.0, 1.5]
ALL_LABELS = [24.0, 12.0, 6.0, 3.0, 1.5, 0.75, 0.0]
SIDE = dict(config.NFL_PROP_MARKET_SIDE_EDGE)          # over .06 / under .05
EV_FLOOR_PROP = float(config.min_ev_for("nfl_prop_market"))
SOFT_0912 = ("draftkings", "fanduel", "betmgm", "williamhill_us",
             "betrivers", "fliff", "hardrockbet")
BH_Q = 0.10
Z_A, Z_B = 1.6449, 0.8416
MIN_N, MIN_G = 10, 5
FAMILY: dict[str, list] = {}          # part -> [(label, p)]

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def norm_name(s) -> str:
    """data.ingestors.nfl_props_data_ingestor.norm_player_name, byte for byte
    (checked against the imported function in main())."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = _SUFFIX.sub("", s.lower().strip())
    return re.sub(r"[^a-z]", "", s)


def first_last(name: str) -> tuple[str, str]:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = _SUFFIX.sub("", s.lower().strip())
    toks = [re.sub(r"[^a-z]", "", t) for t in s.replace(".", " ").split()]
    toks = [t for t in toks if t]
    if not toks:
        return "", ""
    return toks[0], toks[-1]


NICK = {("josh", "joshua"), ("kenny", "kenneth"), ("chig", "chigoziem")}


# ─── inference ────────────────────────────────────────────────────────────

def pnorm2(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2)) if np.isfinite(z) else float("nan")


def cell(profit, cluster, roi_b: float | None = None) -> dict:
    p = np.asarray(profit, float)
    cl = np.asarray(cluster)
    n = len(p)
    if n == 0:
        return {"n": 0}
    roi, (lo, hi) = L.boot_ci(p, cl)
    m = p.mean()
    s = pd.DataFrame({"p": p, "g": cl}).groupby("g")["p"].agg(["sum", "size"])
    G = len(s)
    sd = p.std(ddof=1) if n > 1 else float("nan")
    var_iid = sd ** 2 / n if n > 1 else float("nan")
    resid = s["sum"] - s["size"] * m
    var_cl = (resid ** 2).sum() / n ** 2 * (G / (G - 1)) if G > 1 else float("nan")
    deff = var_cl / var_iid if (n > 1 and var_iid > 0) else float("nan")
    se = math.sqrt(var_cl) if np.isfinite(var_cl) and var_cl > 0 else float("nan")
    # a normal-approximation p is meaningless on a handful of bets: none below
    # MIN_N bets or MIN_G games (those cells are printed, never tested)
    testable = n >= MIN_N and G >= MIN_G
    z0 = m / se if (testable and se and np.isfinite(se)) else float("nan")
    out = {"n": n, "units": p.sum(), "roi": 100 * roi, "lo": 100 * lo, "hi": 100 * hi,
           "win": 100 * (p > 0).mean(), "games": G,
           "n_eff": n / deff if np.isfinite(deff) and deff > 0 else float("nan"),
           "deff": deff, "sd": sd, "z0": z0, "p0": pnorm2(z0)}
    if roi_b is not None:
        zb = (m - roi_b) / se if (testable and se and np.isfinite(se)) else float("nan")
        out["zb"], out["pb"] = zb, pnorm2(zb)
        # power: the cell's own sd and deff only when it has >= 30 bets, else
        # sd 1.0 (a -110..+100 bet) and deff 1
        big = n >= 30 and np.isfinite(sd)
        sd_use = sd if big else 1.0
        n_iid = ((Z_A + Z_B) * sd_use / roi_b) ** 2 if roi_b > 0 else float("nan")
        out["need_iid"] = n_iid
        out["need_cl"] = n_iid * (deff if big and np.isfinite(deff) and deff > 1 else 1.0)
    return out


HDR = (f"{'bets':>5} {'games':>5} {'n_eff':>5} {'units':>8} {'ROI':>7} {'90% CI':>15} "
       f"{'win%':>5} {'p(0)':>6}")
HDRB = HDR + f" {'p(bt)':>6} {'need':>6} {'need_cl':>7}"


def fmt(c: dict, with_b: bool = False) -> str:
    if c.get("n", 0) == 0:
        return f"{0:>5}"
    s = (f"{c['n']:>5} {c['games']:>5} {c['n_eff']:>5.0f} {c['units']:>+8.2f} "
         f"{c['roi']:>+6.1f}% ({c['lo']:>+6.1f},{c['hi']:>+6.1f}) {c['win']:>5.1f} "
         f"{c['p0']:>6.3f}")
    if with_b and "pb" in c:
        s += f" {c['pb']:>6.3f} {c['need_iid']:>6.0f} {c['need_cl']:>7.0f}"
    return s


def fam(part: str, label: str, c: dict):
    if np.isfinite(c.get("p0", np.nan)):
        FAMILY.setdefault(part, []).append((label, c["p0"], c["n"], c["roi"]))


def bh(part: str):
    rows = FAMILY.get(part, [])
    if not rows:
        print(f"  {part}: no testable cells")
        return
    ps = np.array([r[1] for r in rows])
    m = len(ps)
    order = np.argsort(ps)
    q = np.empty(m)
    prev = 1.0
    for rank, i in list(enumerate(order, start=1))[::-1]:
        prev = min(prev, ps[i] * m / rank)
        q[i] = prev
    sig = [(rows[i], q[i]) for i in order if q[i] <= BH_Q]
    print(f"  {part}: {m} cells tested, smallest raw p = {ps.min():.4f}, "
          f"BH-adjusted min q = {q.min():.3f}; cells significant at q <= {BH_Q}: {len(sig)}")
    for (lab, p, n, roi), qq in sig:
        print(f"      {lab}: n={n} ROI {roi:+.1f}% p={p:.4f} q={qq:.3f}")


def bar(t: str, ch: str = "="):
    print("\n" + ch * 110)
    print(t)
    if ch == "=":
        print(ch * 110)


def payout(price):
    p = np.asarray(price, dtype=float)
    return np.where(p > 0, p / 100.0, 100.0 / np.abs(p))


# ─── shared data ──────────────────────────────────────────────────────────

def nflverse_2026() -> pd.DataFrame:
    g = L.games()
    g = g[(g.season == 2026) & (g.week <= 5)].copy()
    g["gid"] = "NFL_" + g["game_id"]
    return g


def player_actuals_2026(prop_names: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Long actuals keyed (game_id, norm, market) + the alias diagnostics."""
    b = pd.read_parquet(C / "player_game_log_2025_2026.parquet",
                        columns=["player_name", "game_id", "season", "week", "attempts",
                                 "completions", "passing_yards", "passing_tds", "carries",
                                 "rushing_yards", "rushing_tds", "receptions",
                                 "receiving_yards", "receiving_tds"])
    b = b[b.season == 2026].copy()
    b["norm"] = b.player_name.map(norm_name)
    b["any_td"] = ((b.rushing_tds.fillna(0) + b.receiving_tds.fillna(0)) > 0).astype(float)
    b = b.drop_duplicates(["game_id", "norm"], keep="last")
    games_logged = set(b.game_id)
    # alias: feed name -> log name inside the same game
    fl = b.player_name.map(first_last)
    b["first"], b["last"] = [f for f, _ in fl], [l_ for _, l_ in fl]
    have = set(zip(b.game_id, b.norm))
    alias = {}
    pn = prop_names.drop_duplicates(["game_id", "norm"])
    for r in pn.itertuples(index=False):
        if r.game_id not in games_logged or (r.game_id, r.norm) in have:
            continue
        f, l_ = first_last(r.player_name)
        cand = b[(b.game_id == r.game_id) & (b["last"] == l_)]
        cand = cand[[(c[:3] == f[:3]) or ((c, f) in NICK) or ((f, c) in NICK)
                     for c in cand["first"]]]
        if len(cand) == 1:
            alias[(r.game_id, r.norm)] = cand.iloc[0]["norm"]
    stat = {m: s for m, s in mk.MARKET_STAT.items() if m in mk.SHARP_MARKETS}
    stat["player_anytime_td"] = "any_td"
    long = []
    for m, s in stat.items():
        x = b[["game_id", "norm", s]].rename(columns={s: "actual"})
        x["market"] = m
        long.append(x)
    act = pd.concat(long, ignore_index=True)
    # alias rows: copy the log row under the feed's norm
    if alias:
        extra = []
        for (gid, feed_norm), log_norm in alias.items():
            y = act[(act.game_id == gid) & (act.norm == log_norm)].copy()
            y["norm"] = feed_norm
            y["alias"] = True
            extra.append(y)
        act = pd.concat([act.assign(alias=False)] + extra, ignore_index=True)
    else:
        act["alias"] = False
    return act, {"alias_pairs": len(alias), "games_logged": len(games_logged),
                 "alias_examples": list(alias.items())[:8]}


def injury_index_by_date():
    """{as_of_date: {norm: [{status, status_ts}]}} exactly as
    load_nfl_injury_index builds it (latest report_date <= as_of, scenario A)."""
    d = pd.read_parquet(C / "injuries_nfl.parquet",
                        columns=["player_name", "status", "status_ts", "report_date", "scenario"])
    d = d[d.scenario == "A"].copy()
    d["rd"] = d.report_date.astype(str).str[:10]
    dates = sorted(d.rd.unique())
    cache = {}

    def get(as_of: str) -> dict:
        prior = [x for x in dates if x <= as_of]
        if not prior:
            return {}
        rd = prior[-1]
        if rd not in cache:
            out: dict = {}
            for r in d[d.rd == rd].itertuples(index=False):
                k = norm_name(r.player_name)
                if k:
                    out.setdefault(k, []).append({"status": r.status, "status_ts": r.status_ts,
                                                  "player_name": r.player_name})
            cache[rd] = out
        return cache[rd]
    return get, dates


# ─── A. nfl_prop_market ───────────────────────────────────────────────────

def load_props_2026() -> pd.DataFrame:
    cols = ["game_id", "game_date", "player_name", "market", "bookmaker", "line",
            "over_price", "under_price", "snapshot_at", "lead_h", "lead_label", "kick"]
    p = pd.read_parquet(C / "props_2026.parquet", columns=cols)
    books = set(mk.SOFT_BOOKS) | set(mk.SHARP_BOOKS) | set(L.BETTABLE) | set(SOFT_0912)
    p = p[p.market.isin(mk.SHARP_MARKETS) & p.bookmaker.isin(books)
          & (p.lead_label >= 0) & p.line.notna()].copy()
    p["ts"] = pd.to_datetime(p.snapshot_at, utc=True, format="mixed")
    p["norm"] = p.player_name.map(norm_name)
    p["week"] = p.game_id.str.split("_").str[2].astype(int)
    p["season"] = 2026
    return p


def latest_per_book(x: pd.DataFrame) -> pd.DataFrame:
    return x.sort_values("ts", kind="stable").groupby(
        ["game_id", "market", "norm", "bookmaker"], as_index=False).tail(1)


def to_quotes(b: pd.DataFrame) -> dict:
    out = {}
    for r in b.itertuples(index=False):
        out[(r.game_id, r.norm, r.market, r.bookmaker)] = {
            "line": float(r.line), "over_price": r.over_price, "under_price": r.under_price,
            "snapshot_at": r.ts.isoformat(), "player_name": r.player_name}
    return out


def select_prop(quotes: dict, inj_get, as_of: str, soft=None, base=0.05, side=None,
                ref: str | None = None, veto=True):
    """The shipped selection. ref=None -> mk.find_bets (pinnacle OR betonlineag);
    ref='fanduel' -> the placebo through models.market_relative.find_bets."""
    soft = soft or mk.SOFT_BOOKS
    side = SIDE if side is None else side
    if ref is None:
        bets, diag = mk.find_bets(quotes, min_edge=base, soft_books=soft,
                                  min_edge_by_side=side, kalshi_ladders={}, game_dates={})
    else:
        bets, diag = mr.find_bets(quotes, ref, base, soft_books=soft, min_edge_by_side=side)
    n_veto = 0
    if veto and bets:
        idx = inj_get(as_of)
        bets, vd = mk.apply_injury_veto(bets, quotes, idx)
        n_veto = vd.get("injury_veto", 0)
    return mk.best_per_prop(bets), diag, n_veto


BET_COLS = ["game_id", "norm", "market", "side", "book", "line", "price", "fair", "edge",
            "quote_ts", "label"]


def bets_frame(bets, quotes, label) -> pd.DataFrame:
    rows = []
    for b in bets:
        q = quotes.get((b.game_id, b.player, b.market, b.book), {})
        rows.append({"game_id": b.game_id, "norm": b.player, "market": b.market,
                     "side": b.side, "book": b.book, "line": b.line, "price": b.price,
                     "fair": b.fair, "edge": b.edge, "quote_ts": q.get("snapshot_at"),
                     "label": label})
    return pd.DataFrame(rows, columns=BET_COLS)


def grade_props(df: pd.DataFrame, act: pd.DataFrame, missing_as_zero=False) -> pd.DataFrame:
    if df is None or len(df) == 0:
        df = pd.DataFrame(columns=BET_COLS)
    d = df.merge(act[["game_id", "norm", "market", "actual", "alias"]],
                 on=["game_id", "norm", "market"], how="left")
    d["actual"] = pd.to_numeric(d.actual, errors="coerce")
    d["line"] = pd.to_numeric(d.line, errors="coerce")
    d["price"] = pd.to_numeric(d.price, errors="coerce")
    d["fair"] = pd.to_numeric(d.fair, errors="coerce")
    d["alias"] = d.alias.fillna(False).astype(bool)
    d["void"] = d.actual.isna()
    if missing_as_zero:
        d["actual"] = d.actual.fillna(0.0)
        d["void"] = False
    won = np.where(d.side == "over", d.actual > d.line, d.actual < d.line)
    push = d.actual == d.line
    d["profit"] = np.where(push, 0.0, np.where(won, payout(d.price), -1.0))
    d.loc[d.void, "profit"] = np.nan
    d["week"] = d.game_id.str.split("_").str[2].astype(int)
    d["ev_raw"] = d.fair * (1 + payout(d.price)) - 1
    return d


def part_a(P: pd.DataFrame, act: pd.DataFrame, inj_get, g26: pd.DataFrame):
    bar("A. nfl_prop_market on the 2026 board (models/nfl_prop_market, unmodified)")
    graded_games = set(act.game_id)
    print(f"board: {P.game_id.nunique()} games with prop quotes; graded games (stat log): "
          f"{len(graded_games)}; markets {sorted(P.market.unique())}")
    wk_lab = pd.crosstab(P.week, P.lead_label)
    print("rows per week x lead label (8 shipped markets, needed books):")
    print(wk_lab.to_string())
    print("NOTE week 3: the cache holds almost no quotes under 12h for week-3 games "
          "(labels 6..0 near-empty) -- a data gap, not a quiet market.")
    ROI_B = 0.1333
    kick = P.drop_duplicates("game_id").set_index("game_id")["kick"]

    # -- the shipped cell at each label, + DK-only, + EV gate, + placebo --
    sel = {}
    diag_rows = []
    for Lh in LABELS:
        b = latest_per_book(P[P.lead_label >= Lh])
        q = to_quotes(b)
        out = {}
        for name, kw in (("shipped", {}),
                         ("DK only", {"soft": ("draftkings",)}),
                         ("PLACEBO fanduel ref", {"ref": "fanduel",
                                                  "soft": tuple(x for x in mk.SOFT_BOOKS if x != "fanduel")})):
            parts = []
            nveto = 0
            for gid, gq in _by_game(q).items():
                as_of = (kick[gid] - pd.Timedelta(hours=Lh)).strftime("%Y-%m-%d")
                bets, diag, nv = select_prop(gq, inj_get, as_of, **kw)
                nveto += nv
                parts.append(bets_frame(bets, gq, Lh))
                if name == "shipped":
                    diag_rows.append({"label": Lh, **{k: diag.get(k, 0) for k in
                                                      ("compared", "line_mismatch", "one_way", "no_sharp")}})
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            out[name] = (grade_props(df, act), nveto)
        sel[Lh] = out
    dg = pd.DataFrame(diag_rows).groupby("label").sum()
    print("\nshipped find_bets diagnostics summed over games (comparisons made, soft quotes "
          "dropped for a different line, one-way, no sharp quote):")
    print(dg.to_string())

    bar("A1. The shipped rule (either sharp ref, over 6pp / under 5pp, 6 soft books, injury veto, "
        "one bet per proposition), 2026, by lead label", "-")
    print(f"backtest expectation +13.33% (2023-25 open read, 1,248 bets). 'need' = bets for "
          f"2026 alone to separate +13.3% from 0 (80% power, one-sided 5%); need_cl x deff.")
    print(f"  {'label':>6} {'variant':24s} {HDRB}   void  veto  alias  EV>={EV_FLOOR_PROP:.2f}")
    for Lh in LABELS:
        for name in ("shipped", "DK only", "PLACEBO fanduel ref"):
            d, nveto = sel[Lh][name]
            gd = d[~d.void] if len(d) else d
            c = cell(gd.profit, gd.game_id, ROI_B) if len(gd) else {"n": 0}
            if name == "shipped":
                fam("A", f"shipped L={Lh}", c)
            nv = int(d.void.sum()) if len(d) else 0
            na = int(gd.alias.fillna(False).sum()) if len(gd) else 0
            nev = int((gd.ev_raw >= EV_FLOOR_PROP).sum()) if len(gd) else 0
            print(f"  {Lh:>6} {name:24s} {fmt(c, True)}   {nv:>4} {nveto:>5} {na:>6} {nev:>8}")

    bar("A2. Shipped rule split: side, early (weeks 1-2) / late (weeks 3-5), each week", "-")
    print(f"  {'label':>6} {'group':18s} {HDR}")
    for Lh in LABELS:
        d = sel[Lh]["shipped"][0]
        d = d[~d.void] if len(d) else d
        for lab, m in (("over", d.side == "over"), ("under", d.side == "under"),
                       ("early wk1-2", d.week <= 2), ("late wk3-5", d.week >= 3)) + tuple(
                (f"week {w}", d.week == w) for w in range(1, 6)):
            c = cell(d[m].profit, d[m].game_id) if m.sum() else {"n": 0}
            print(f"  {Lh:>6} {lab:18s} {fmt(c)}")

    bar("A3. Neighbourhood: base cut x (single floor | paired over = base+1pp), every label. "
        "Shipped = paired 5pp. '*' strict cell (<= 30 bets in 2026)", "-")
    print(f"  {'label':>6} {'cut':>4} | SINGLE {HDR} | PAIRED {HDR}")
    for Lh in LABELS:
        b = latest_per_book(P[P.lead_label >= Lh])
        q = to_quotes(b)
        for base in (0.03, 0.04, 0.05, 0.06, 0.07, 0.08):
            cs = []
            for side in ({"over": base, "under": base}, {"over": base + 0.01, "under": base}):
                parts = []
                for gid, gq in _by_game(q).items():
                    as_of = (kick[gid] - pd.Timedelta(hours=Lh)).strftime("%Y-%m-%d")
                    bets, _, _ = select_prop(gq, inj_get, as_of, base=base, side=side)
                    parts.append(bets_frame(bets, gq, Lh))
                d = grade_props(pd.concat(parts, ignore_index=True), act)
                d = d[~d.void] if len(d) else d
                cs.append(cell(d.profit, d.game_id) if len(d) else {"n": 0})
            for k, c in zip(("single", "paired"), cs):
                if not (base == 0.05 and k == "paired"):
                    fam("A", f"grid L={Lh} {k} {int(base*100)}pp", c)
            tag = " *" if 0 < cs[1].get("n", 0) <= 30 else ""
            print(f"  {Lh:>6} {int(base*100):>3}p | {fmt(cs[0])} | {fmt(cs[1])}{tag}")

    # -- first-qualifying lock across labels (production's hourly harvest, coarse)
    lock = []
    seen = set()
    for Lh in ALL_LABELS:
        b = latest_per_book(P[P.lead_label >= Lh])
        q = to_quotes(b)
        for gid, gq in _by_game(q).items():
            as_of = (kick[gid] - pd.Timedelta(hours=Lh)).strftime("%Y-%m-%d")
            bets, _, _ = select_prop(gq, inj_get, as_of)
            for bt in bets:
                k = (bt.game_id, bt.player, bt.market)
                if k in seen:
                    continue
                seen.add(k)
                lock.append(bets_frame([bt], gq, Lh))
    lockd = grade_props(pd.concat(lock, ignore_index=True), act) if lock else pd.DataFrame()

    # -- the 13:xx UTC game-day read --
    pub = publish_read(P, g26)
    pq = to_quotes(pub["board"])
    parts = []
    for gid, gq in _by_game(pq).items():
        bets, _, _ = select_prop(gq, inj_get, pub["as_of"][gid])
        parts.append(bets_frame(bets, gq, "13:30Z"))
    pubd = grade_props(pd.concat(parts, ignore_index=True), act) if parts else pd.DataFrame()
    if len(pubd):
        T = pubd.game_id.map(pub["T"])
        qts = pd.to_datetime(pubd.quote_ts, utc=True)
        pubd["exact"] = (T - qts).dt.total_seconds().abs() <= 600

    bar("A4. Production-shaped populations, 2026", "-")
    print(f"  {'population':44s} {HDRB}   void")
    for lab, d in (("first-qualifying read lock, labels 24..0", lockd),
                   ("13:30Z game-day read (publish pass)", pubd)):
        gd = d[~d.void] if len(d) else d
        c = cell(gd.profit, gd.game_id, ROI_B) if len(gd) else {"n": 0}
        fam("A", lab, c)
        print(f"  {lab:44s} {fmt(c, True)}   {int(d.void.sum()) if len(d) else 0:>4}")
    if len(pubd):
        print(f"  13:30Z read: {pub['n_games']} games eligible (2h <= lead <= 24h), "
              f"{pub['skipped']} skipped (London / lead < 2h); selected quotes stamped at the "
              f"13:30Z poll itself: {int(pubd.exact.sum())} of {len(pubd)} "
              f"(the rest come from an earlier poll -- the cache keeps one quote per lead bucket)")
        gd = pubd[~pubd.void]
        for lab, m in (("  13:30Z exact-poll quotes only", gd.exact),
                       ("  13:30Z over", gd.side == "over"), ("  13:30Z under", gd.side == "under"),
                       ("  13:30Z early wk1-2", gd.week <= 2), ("  13:30Z late wk3-5", gd.week >= 3)):
            c = cell(gd[m].profit, gd[m].game_id) if m.sum() else {"n": 0}
            print(f"  {lab:44s} {fmt(c)}")
    if len(lockd):
        print("  lock: bets by the label at which they first qualified: "
              + ", ".join(f"{k}h {v}" for k, v in lockd.label.value_counts().sort_index(ascending=False).items()))

    # -- sensitivity: missing actual = 0
    d6 = sel[6.0]["shipped"][0]
    if len(d6):
        z = grade_props(d6.drop(columns=["profit", "actual", "void", "alias", "week", "ev_raw"]),
                        act, missing_as_zero=True)
        print(f"\n  sensitivity, label 6h: grading the {int(d6.void.sum())} void bets (no stat row) "
              f"as actual = 0 -> {fmt(cell(z.profit, z.game_id))}")

    # -- production comparison --
    prod_compare(sel, lockd, pubd, act)
    return sel


def _by_game(q: dict) -> dict:
    out: dict = {}
    for k, v in q.items():
        out.setdefault(k[0], {})[k] = v
    return out


def publish_read(P: pd.DataFrame, g26: pd.DataFrame) -> dict:
    """Board as of 13:30 UTC on the ET game date (the publish pass), per game."""
    gd = g26.set_index("gid")["gameday"].to_dict()
    kick = P.drop_duplicates("game_id").set_index("game_id")["kick"]
    boards, Tm, as_of = [], {}, {}
    skipped = 0
    for gid, k in kick.items():
        day = gd.get(gid)
        if day is None:
            continue
        # the publish pass is the hourly :25 tick (picks stamped 13:26-13:27); its
        # fetch lands at ~13:25:20, so the board is everything up to 13:30.
        T = pd.Timestamp(f"{day} 13:30", tz="UTC")
        lead = (k - T).total_seconds() / 3600
        if not (config.NFL_PROP_PUBLISH_MIN_LEAD_HOURS <= lead <= config.NFL_PROP_MAX_LEAD_HOURS):
            skipped += 1
            continue
        x = P[(P.game_id == gid) & (P.ts <= T)]
        boards.append(latest_per_book(x))
        Tm[gid] = T
        as_of[gid] = T.strftime("%Y-%m-%d")
    return {"board": pd.concat(boards, ignore_index=True), "T": Tm, "as_of": as_of,
            "n_games": len(Tm), "skipped": skipped}


def prod_compare(sel, lockd, pubd, act):
    bar("A5. Production nfl_prop_market picks (picks_nfl) against the replay", "-")
    pk = pd.read_parquet(C / "picks_nfl.parquet")
    pk = pk[(pk.model_id == "nfl_prop_market") & (pk.signal_type == "BET")].copy()
    pk["profit_u"] = pd.to_numeric(pk.profit_flat, errors="coerce") / 100.0
    pk["price"] = pd.to_numeric(pk.dk_odds, errors="coerce")
    pk["created"] = pd.to_datetime(pk.created_at, utc=True, format="mixed")
    pk["void"] = pk.condition_status.astype(str).eq("VOID")
    pk["settled"] = pk.result.isin(["WIN", "LOSS", "PUSH"]) & pk.price.notna()
    print(f"production BET rows: {len(pk)}; created {pk.created.min():%Y-%m-%d %H:%M} .. "
          f"{pk.created.max():%Y-%m-%d %H:%M} UTC; VOID {int(pk.void.sum())}; settled "
          f"(WIN/LOSS/PUSH, priced) {int(pk.settled.sum())}; other NO_ACTION "
          f"{int((pk.result.eq('NO_ACTION') & ~pk.void).sum())}")
    print("production wrote NO nfl_prop_market BET after 2026-09-19 20:27 UTC. The EV floor "
          f"for this model is {EV_FLOOR_PROP:.2f} (config.MODEL_OWN_EV_FLOOR) since 2026-09-19.")
    s = pk[pk.settled]
    c = cell(s.profit_u, s.game_id, 0.1333)
    print(f"  {'production settled record':44s} {HDRB}")
    print(f"  {'all settled BETs':44s} {fmt(c, True)}")
    for lab, m in (("  over", s.pick_side == "over"), ("  under", s.pick_side == "under"),
                   ("  week 1", s.game_id.str.contains("_01_")), ("  week 2", s.game_id.str.contains("_02_"))):
        print(f"  {lab:44s} {fmt(cell(s[m].profit_u, s[m].game_id))}")
    na = pk[pk.result.eq("NO_ACTION") & ~pk.void]
    if len(na):
        print("  production NO_ACTION rows that are NOT voids (settlement found no stat):")
        print(na[["game_id", "pick_label", "player_key", "prop_market"]].to_string(index=False))
        aj = na.merge(act, left_on=["game_id", "player_key", "prop_market"],
                      right_on=["game_id", "norm", "market"], how="left")
        print("  the same rows through this script's alias join -> actual:",
              aj[["player_key", "prop_market", "actual", "alias"]].values.tolist())
    # overlap
    pk["key"] = list(zip(pk.game_id, pk.player_key, pk.prop_market))
    sp = pk[~pk.void]
    print(f"\n  overlap of production's {len(sp)} non-void BETs with the replay populations "
          "(same game, player, market; same side in brackets):")
    pops = {f"label {Lh}h": sel[Lh]["shipped"][0] for Lh in LABELS}
    pops["first-qualifying lock"] = lockd
    pops["13:30Z read"] = pubd
    for name, d in pops.items():
        if d is None or len(d) == 0:
            print(f"    {name:24s} replay 0 bets")
            continue
        rk = dict(zip(zip(d.game_id, d.norm, d.market), d.side))
        hit = [k for k in sp.key if k in rk]
        same = [k for k, sd in zip(sp.key, sp.pick_side) if rk.get(k) == sd]
        wk12 = d[d.week <= 2]
        print(f"    {name:24s} replay {len(d):>4} bets ({len(wk12)} in weeks 1-2); production "
              f"found in replay {len(hit):>3} ({len(same)} same side)")
    print("  why production and replay differ (measured above, not inferred): production weeks 1-2 "
          "ran hourly with no single-read rule (ceiling only from 09-08), fliff was a soft book "
          "until 09-20, a Kalshi reference wrote the 09-19 17:27 batch (all VOID), and from 09-19 "
          "the 0.20 EV floor stopped every write.")


def part_a_extreme(P: pd.DataFrame, act: pd.DataFrame):
    bar("A6. scripts/nfl_edge_extreme_props Part 1 'single board read' cells on 2026 "
        "(its functions, unmodified; either ref, pooled sides, best bettable price)", "-")
    print("2023-25 (its own run): 6pp 423 bets +19.3% (+11.9,+26.9); 7pp 72 bets +21.3% (+1.5,+40.6)")
    a = act.rename(columns={})[["norm", "game_id", "market", "actual"]]
    a = a.drop_duplicates(["norm", "game_id", "market"])
    print(f"  {'read':>12} {'cut':>4} {HDRB}")
    for Lh in LABELS + [0.0]:
        x = P[P.lead_label >= Lh]
        T = x.groupby(["game_id", "market"])["ts"].max().rename("T").reset_index()
        b = x.merge(T, on=["game_id", "market"])
        b = b[b.ts == b["T"]].drop(columns=["T"])
        b = b.drop_duplicates(["game_id", "market", "norm", "line", "bookmaker"], keep="last")
        b = b.assign(snapshot_at=b.ts, lead_h=b.lead_h)
        c = X.add_modes(X.candidates(b, X.REFS, tuple(L.BETTABLE), tuple(L.BETTABLE)), X.REFS)
        c = X.grade(c, a)
        soft_pl = tuple(x for x in L.BETTABLE if x != "fanduel")
        pc = X.grade(X.add_modes(X.candidates(b, ("fanduel",), soft_pl, soft_pl), ("fanduel",)), a)
        for cut, rb in ((0.06, 0.193), (0.07, 0.213)):
            z = X.one_per_prop(c, "m_either", cut=cut)
            cc = cell(z.profit, z.game_id, rb) if len(z) else {"n": 0}
            fam("A-extreme", f"L={Lh} {int(cut*100)}pp", cc)
            print(f"  {('poll<=' + str(Lh) + 'h'):>12} {int(cut*100):>3}p {fmt(cc, True)}")
            zp = X.one_per_prop(pc, "m_either", cut=cut)
            cp = cell(zp.profit, zp.game_id) if len(zp) else {"n": 0}
            print(f"  {'  PLACEBO fd':>12} {int(cut*100):>3}p {fmt(cp)}")


# ─── B. soft-book learned sharp stack, pass attempts ──────────────────────

def part_b(P: pd.DataFrame, act: pd.DataFrame, g26):
    bar("B. Soft-book learned sharp stack, player_pass_attempts (scripts/nfl_prop_market_stack "
        "--soft, design 'sharp', 5% cut)")
    import scripts.nfl_prop_market_stack as S
    from sklearn.preprocessing import StandardScaler
    h = L.props_market("player_pass_attempts")
    h = h[h.snapshot_type.astype(str).isin(["open", "t48", "t72"])].copy()
    h["norm"] = h.player_name.map(norm_name)
    h["ts"] = pd.to_datetime(h.snapshot_at, utc=True, format="mixed")
    h["season"] = h.game_id.str.split("_").str[1].astype(int)
    h = h[h.season.isin([2023, 2024, 2025])]
    ko = X.kickoffs().set_index("game_id")["kick"]
    h = h[h.ts <= h.game_id.map(ko)]
    lg = pd.read_parquet(C / "local_nfl_player_game_log.parquet",
                         columns=["player_name", "game_id", "attempts"])
    lg["norm"] = lg.player_name.map(norm_name)
    lg = lg.drop_duplicates(["norm", "game_id"], keep="last").set_index(["game_id", "norm"])["attempts"]
    a26 = act[act.market == "player_pass_attempts"].drop_duplicates(["game_id", "norm"]).set_index(
        ["game_id", "norm"])["actual"]

    def build(df, act_map, sharp, season_of, dk_types=("open",)) -> pd.DataFrame:
        """soft_rows + market_features, the stack module's own row construction:
        DK rows = DraftKings' newest `open` quote per proposition; soft rows =
        each soft book's tightest two-way `open` quote at or before it."""
        soft_books = tuple(b for b in SOFT_0912 if b not in sharp)
        out = []
        for (gid, nm), g in df.groupby(["game_id", "norm"], sort=False):
            dk = g[(g.bookmaker == "draftkings") & g.snapshot_type.isin(dk_types)]
            if dk.empty:
                continue
            dts = dk.ts.max()
            actual = act_map(gid, nm)
            if actual is None or not np.isfinite(actual):
                continue
            ctx = S._context(g, dts, sharp)
            gg = g[(g.ts <= dts) & (g.snapshot_type == "open") & g.bookmaker.isin(soft_books)]
            for bk, gb in gg.groupby("bookmaker"):
                qd = S._book_quotes(gb)
                ml = S._main_line(qd)
                if ml is None:
                    continue
                line, fo = ml
                op, up = qd[line]
                row = {"season": season_of(gid), "game_id": gid, "player": nm, "book": bk,
                       "line": line, "fair_over": fo, "over_price": op, "under_price": up,
                       "actual": float(actual)}
                row.update(S._features_from(ctx, float(line), sharp, bk))
                out.append(row)
        R = pd.DataFrame(out)
        if len(R):
            R = R[R.actual != R.line].copy()          # pushes carry no outcome (stack.evaluate)
            R["y"] = (R.actual > R.line).astype(float)
        return R

    def hist_act(gid, nm):
        try:
            return float(lg.loc[(gid, nm)])
        except KeyError:
            return None

    def act26(gid, nm):
        try:
            return float(a26.loc[(gid, nm)])
        except KeyError:
            return None

    def fit_pred(tr, te, sharp):
        sd_line = float(tr.line.std() or 1.0)
        Xtr = S._design(tr, sd_line, 1.0, sharp, "sharp")
        sc = StandardScaler().fit(Xtr)
        w = S._fit(np.clip(sc.transform(Xtr), -4, 4), tr.y.values, S.logit(tr.fair_over))
        Xte = np.clip(sc.transform(S._design(te, sd_line, 1.0, sharp, "sharp")), -4, 4)
        return S.sigmoid(S.logit(te.fair_over) + Xte @ w)

    def stack_bets(p, R, cut, books=None):
        """S._bets, with the game id kept for clustering: one bet per
        (proposition, side), the book with the largest edge vs its own price."""
        best = {}
        for pb, r in zip(p, R.itertuples(index=False)):
            if books is not None and r.book not in books:
                continue
            for sd_, pp, price in (("over", pb, r.over_price), ("under", 1 - pb, r.under_price)):
                if price is None or not np.isfinite(float(price)):
                    continue
                e = pp - mr.implied(price)
                if e >= cut:
                    won = (r.actual > r.line) if sd_ == "over" else (r.actual < r.line)
                    k = (r.game_id, r.player, sd_)
                    if k not in best or e > best[k][0]:
                        best[k] = (e, S.profit(price, won), r.game_id,
                                   int(r.game_id.split("_")[2]))
        return pd.DataFrame(list(best.values()), columns=["edge", "profit", "game_id", "week"])

    x26 = P[P.market == "player_pass_attempts"].copy()
    pubb = publish_read(x26, g26)["board"]
    for sharp, tag in ((tuple(S.SHARP), "SHARP REFERENCES (the lead)"),
                       (("fanduel",), "PLACEBO: fanduel as the only reference")):
        t0 = time.time()
        H = build(h, hist_act, sharp, lambda g: int(g.split("_")[1]))
        print(f"\n[{tag}] rebuilt soft rows 2023-25: {len(H):,} ({time.time()-t0:.0f}s); by season "
              f"{H.season.value_counts().sort_index().to_dict()}")
        print("STEP 1, walk-forward reproduction (published, sharp refs: 2023 +3.1% (152), "
              "2024 +16.5% (109), 2025 +16.4% (150) at 5%; placebo 2024 +9.7% (78), 2025 +15.8% (37)):")
        rep = {}
        for test in (2023, 2024, 2025):
            tr = H[H.season < test] if test > 2023 else H[H.season > test]
            te = H[H.season == test]
            p = fit_pred(tr, te, sharp)
            prof = S._bets(p, te, 0.05)
            rule = S._rule_bets(te, 0.05, sharp)
            rep[test] = len(prof)
            print(f"  {test}: rows {len(te):>5}  stack 5%: {len(prof):>4} bets "
                  f"ROI {100*np.mean(prof) if prof else float('nan'):+6.1f}%  | rule 5pp on same rows: "
                  f"{len(rule)} bets {100*np.mean(rule) if rule else float('nan'):+.1f}%")
        if sharp == tuple(S.SHARP):
            ok = all(abs(rep[s] - t) <= 0.25 * t for s, t in ((2024, 109), (2025, 150)))
            if not ok:
                print("  REPRODUCTION FAILED (counts > 25% off 109 / 150): no 2026 read.")
                return
            print("  reproduction within 25% on counts (the pre-declared gate): reading 2026")
        print(f"  fit on 2023-25 ({len(H):,} rows), read on each 2026 board:")
        print(f"  {'board':>8} {'cut':>4} {'books':8s} {HDRB}")
        for Lh in LABELS + ["13:30Z"]:
            b = (pubb.copy() if Lh == "13:30Z" else latest_per_book(x26[x26.lead_label >= Lh]).copy())
            b["snapshot_type"] = "open"
            b["ts"] = b.groupby("game_id").ts.transform("max")    # one read per game
            R = build(b, act26, sharp, lambda g: 2026)
            if R.empty:
                print(f"  {str(Lh):>8} no rows")
                continue
            p = fit_pred(H, R, sharp)
            for cut in (0.04, 0.05, 0.06):
                for books, bl in ((None, "soft"), (("draftkings",), "DK only")):
                    z = stack_bets(p, R, cut, books)
                    cc = cell(z.profit, z.game_id, 0.164) if len(z) else {"n": 0}
                    if sharp == tuple(S.SHARP) and books is None:
                        fam("B", f"stack {Lh} {int(cut*100)}%", cc)
                    print(f"  {str(Lh):>8} {int(cut*100):>3}% {bl:8s} {fmt(cc, True)}")
            z = stack_bets(p, R, 0.05)
            for lab, m in (("early wk1-2", z.week <= 2), ("late wk3-5", z.week >= 3)):
                cc = cell(z[m].profit, z[m].game_id) if m.sum() else {"n": 0}
                print(f"  {str(Lh):>8}   5% {lab:8s} {fmt(cc)}")


# ─── C. opener ────────────────────────────────────────────────────────────

def opener_board_2026(o: pd.DataFrame) -> pd.DataFrame:
    keep = set(config.BETTABLE_BOOKS) | {om.REFERENCE}
    o = o[o.bookmaker.isin(keep) & ~o.bookmaker.isin(om.DEFECTIVE_BOOKS | om.EXCHANGES)]
    o = o[(o.lead_hours >= 0) & (o.lead_hours <= 240.5)]
    o = o.dropna(subset=["point"]).copy()
    return o[["snapshot_at", "game_id", "commence_time", "bookmaker", "point",
              "price_home", "price_away", "lead_hours"]]


def opener_grade(sel: pd.DataFrame, res: dict) -> pd.DataFrame:
    if sel.empty:
        return sel.assign(profit=[])
    sel = sel.assign(margin=sel.game_id.map(res))
    sel = sel[sel.margin.notna()].copy()
    s = np.where(sel.bet_home, sel.margin + sel.point, -(sel.margin + sel.point))
    sel["profit"] = np.where(s > 0, payout(sel.price), np.where(s == 0, 0.0, -1.0))
    return sel


def opener_candidates(state: pd.DataFrame, ref: str, soft: set) -> pd.DataFrame:
    """state: one row per (t, game_id, book) with point/price_home/price_away.
    -> per (t, game, soft book): dev vs the reference and the priced side."""
    pin = state[state.bookmaker == ref].groupby(["t", "game_id"])["point"].median().rename("pin")
    s = state[state.bookmaker.isin(soft) & (state.bookmaker != ref)].join(pin, on=["t", "game_id"], how="inner")
    s["dev"] = s.point - s.pin
    s["adev"] = s.dev.abs()
    s["bet_home"] = s.dev > 0
    s["price"] = np.where(s.bet_home, s.price_home, s.price_away)
    s = s[s.price.notna() & (s.adev >= 0.999)]
    s["model_prob"] = [om.model_prob_for_dev(d) for d in s.dev]
    s["mkt"] = [om.american_to_prob(float(p)) for p in s.price]
    s["edge"] = s.model_prob - s.mkt
    s["units"] = [om.stake_units(mp, int(p)) for mp, p in zip(s.model_prob, s.price)]
    s["ev"] = s.model_prob * (1 + payout(s.price)) - 1
    return s


def opener_select(c: pd.DataFrame, thr: float, platform: bool) -> pd.DataFrame:
    q = c[(c.adev >= thr) & (c.units > 0) & (c.edge >= 0)]
    if platform:
        q = q[(q.model_prob >= 0.55) & (q.ev >= float(config.min_ev_for("nfl_opener_spread")))]
    if q.empty:
        return q
    return (q.sort_values(["game_id", "t", "adev", "bookmaker"], ascending=[True, True, False, True])
            .groupby("game_id", as_index=False).first())


def state_at(o: pd.DataFrame, times: pd.DataFrame, max_age_h: float) -> pd.DataFrame:
    """times: (game_id, t). Latest row per (game, book) at or before t, <= max_age."""
    o = o.sort_values("snapshot_at")
    out = []
    for gid, tt in times.groupby("game_id"):
        og = o[o.game_id == gid]
        if og.empty:
            continue
        for bk, ob in og.groupby("bookmaker"):
            m = pd.merge_asof(tt.sort_values("t"), ob.rename(columns={"snapshot_at": "ts"}),
                              left_on="t", right_on="ts", direction="backward",
                              tolerance=pd.Timedelta(hours=max_age_h))
            m = m[m.ts.notna()]
            m["game_id"] = gid
            m["bookmaker"] = bk
            out.append(m[["t", "game_id", "bookmaker", "point", "price_home", "price_away",
                           "ts", "commence_time"]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def held_minutes(o: pd.DataFrame, sel: pd.DataFrame) -> list:
    """Minutes the selected soft book had shown its point before the fire."""
    out = []
    for r in sel.itertuples(index=False):
        ob = o[(o.game_id == r.game_id) & (o.bookmaker == r.bookmaker) & (o.snapshot_at <= r.t)]
        ob = ob.sort_values("snapshot_at")
        diff = ob[(ob.point - r.point).abs() > 1e-9]
        start = ob[ob.snapshot_at > diff.snapshot_at.max()] if len(diff) else ob
        out.append((r.t - start.snapshot_at.min()).total_seconds() / 60 if len(start) else np.nan)
    return out


def part_c(g26, O26):
    bar("C. nfl_opener_spread replayed on the 2026 per-minute archive (nfl/models/opener_spread.py)")
    res = dict(zip(g26.gid, g26.result))
    o = opener_board_2026(O26)
    books = sorted(o.bookmaker.unique())
    print(f"books in the archive used: {books}; config.BETTABLE_BOOKS not in the archive: "
          f"{sorted(set(config.BETTABLE_BOOKS) - set(books))}")
    # sign check: Pinnacle's last pre-kick home point vs nflverse -spread_line
    pin_last = o[o.bookmaker == "pinnacle"].sort_values("snapshot_at").groupby("game_id").tail(1)
    chk = pin_last.merge(g26[["gid", "spread_line"]], left_on="game_id", right_on="gid")
    agree = (np.sign(chk.point) == np.sign(-chk.spread_line)) | (chk.spread_line == 0)
    print(f"sign check: Pinnacle last pre-kick HOME point vs nflverse -spread_line agree in sign "
          f"on {int(agree.sum())}/{len(chk)} games; mean |diff| "
          f"{(chk.point + chk.spread_line).abs().mean():.2f} pts")

    o["min"] = o.snapshot_at.dt.floor("min")
    kick = o.groupby("game_id").commence_time.first()
    # decision times
    minutes = o[["game_id", "min"]].drop_duplicates().rename(columns={"min": "t"})
    daily = []
    for gid, k in kick.items():
        for d in range(0, 11):
            t = (k.tz_convert("America/New_York").normalize() - pd.Timedelta(days=d)
                 + pd.Timedelta(hours=9, minutes=30)).tz_convert("UTC")
            daily.append({"game_id": gid, "t": t})
    daily = pd.DataFrame(daily)
    soft = set(config.BETTABLE_BOOKS)
    t0 = time.time()
    states = {}
    for sched, tt in (("daily 09:30 ET", daily), ("every minute", minutes)):
        for age in (6.0, 1.0):
            st = state_at(o, tt, age)
            st["lead_d"] = (st.commence_time - st.t).dt.total_seconds() / 86400
            states[(sched, age)] = st
    print(f"board states built ({time.time()-t0:.0f}s)")

    rows = []
    sel_main = {}
    for (sched, age), st in states.items():
        for hi in (7.0, 10.0):
            w = st[(st.lead_d > 2.0) & (st.lead_d <= hi)]
            variants = [("pinnacle", soft, "rule")]
            if age == 6.0:
                variants += [("pinnacle", {"draftkings"}, "DK only"),
                             ("draftkings", soft - {"draftkings"}, "PLACEBO dk ref")]
            for ref, soft_set, lab in variants:
                cnd = opener_candidates(w, ref, soft_set)
                for thr in (1.0, 1.5, 2.0, 2.5):
                    platform = thr >= 2.0
                    s = opener_select(cnd, thr, platform)
                    gs = opener_grade(s, res)
                    rows.append((sched, age, hi, lab, thr, gs))
                    if lab == "rule" and thr == 2.0:
                        sel_main[(sched, age, hi)] = gs
    ROI_B = 0.0397
    bar("C1. 2026 opener record. thr 2.0 = the live rule with platform gates; 1.0/1.5/2.5 = the "
        "sweep's selection. Backtest 2.0: 125 bets +3.97% (2020-25)", "-")
    print(f"  {'schedule':15s} {'age':>4} {'win':>5} {'variant':16s} {'dev':>4} {HDRB}")
    for sched, age, hi, lab, thr, gs in rows:
        c = cell(gs.profit, gs.game_id, ROI_B if thr == 2.0 else None) if len(gs) else {"n": 0}
        if lab == "rule":
            fam("C", f"{sched} age{age} T-{hi:.0f} dev{thr}", c)
        print(f"  {sched:15s} {age:>4.0f} T-{hi:<3.0f} {lab:16s} {thr:>4} {fmt(c, thr == 2.0)}")

    print("\n  early (weeks 1-2) / late (weeks 3-5), every minute, 6h age, T-10, rule:")
    for sched, age, hi, lab, thr, gs in rows:
        if (sched, age, hi, lab) != ("every minute", 6.0, 10.0, "rule") or not len(gs):
            continue
        wk = gs.game_id.str.split("_").str[2].astype(int)
        for nm, m in (("early", wk <= 2), ("late", wk >= 3)):
            c = cell(gs[m].profit, gs[m].game_id) if m.sum() else {"n": 0}
            print(f"    dev {thr} {nm:6s} {fmt(c)}")
    bar("C2. The bets, |dev| >= 2.0, every-minute and daily schedules (6h max quote age)", "-")
    for key in (("every minute", 6.0, 10.0), ("every minute", 6.0, 7.0),
                ("daily 09:30 ET", 6.0, 10.0), ("daily 09:30 ET", 6.0, 7.0)):
        gs = sel_main.get(key)
        if gs is None or gs.empty:
            print(f"  {key}: no bets")
            continue
        gs = gs.copy()
        gs["held_min"] = held_minutes(o, gs)
        print(f"  {key}:")
        print(gs[["game_id", "t", "bookmaker", "point", "pin", "dev", "price", "model_prob",
                  "units", "held_min", "profit"]].to_string(index=False))
        h60 = gs[gs.held_min >= 60]
        print(f"    soft number stood >= 60 min before the fire: {fmt(cell(h60.profit, h60.game_id))}")

    # production
    pk = pd.read_parquet(C / "picks_nfl.parquet")
    pk = pk[(pk.model_id == "nfl_opener_spread") & (pk.signal_type == "BET")].copy()
    pk["profit_u"] = pd.to_numeric(pk.profit_flat, errors="coerce") / 100
    pk["void"] = pk.condition_status.astype(str).eq("VOID")
    s = pk[pk.result.isin(["WIN", "LOSS", "PUSH"]) & pk.dk_odds.notna()]
    print("\n  production nfl_opener_spread BETs:")
    print(pk[["game_id", "pick_label", "result", "profit_u", "void", "created_at"]].to_string(index=False))
    print(f"  production settled: {fmt(cell(s.profit_u, s.game_id, ROI_B), True)}")
    rep = sel_main.get(("every minute", 6.0, 10.0))
    if rep is not None:
        both = set(rep.game_id) & set(pk.game_id)
        print(f"  games in both the every-minute T-10 replay ({len(rep)}) and production BETs "
              f"({pk.game_id.nunique()}): {sorted(both)}")

    # expectation from odds_hist with the same code
    bar("C3. The same code on odds_hist 2020-25 at snapshot resolution (T-7..T-2), the expectation", "-")
    h = L.odds_hist(["spreads"])
    keep = set(config.BETTABLE_BOOKS) | {"pinnacle"}
    h = h[h.bookmaker.isin(keep) & h.lead_hours.between(48, 168)].dropna(subset=["point"]).copy()
    h = h.rename(columns={"snapshot_at": "t"})
    h["game_id"] = "NFL_" + h.game_id.str.replace("^NFL_", "", regex=True)
    gh = L.games()
    resh = dict(zip("NFL_" + gh.game_id, gh.result))
    print(f"  books present 2020-25: {sorted(h.bookmaker.unique())}")
    for thr in (1.0, 1.5, 2.0, 2.5):
        cnd = opener_candidates(h, "pinnacle", set(config.BETTABLE_BOOKS))
        s = opener_grade(opener_select(cnd, thr, thr >= 2.0), resh)
        s["season"] = s.game_id.str.split("_").str[1].astype(int)
        c = cell(s.profit, s.game_id)
        per = " ".join(f"{y}:{100*v.mean():+.1f}%/{len(v)}" for y, v in s.groupby("season").profit)
        s23 = s[s.season >= 2023]
        print(f"  dev {thr}: 2020-25 {fmt(c)}  | 2023-25 {fmt(cell(s23.profit, s23.game_id))}\n"
              f"           {per}")


# ─── D. Wong teaser legs ──────────────────────────────────────────────────

WONG_DOG = [1.5, 2.0, 2.5]
WONG_FAV = [-7.5, -8.0, -8.5]
PLAC_DOG = [3.5, 4.0, 4.5, 5.0, 5.5]
PLAC_FAV = [-3.5, -4.0, -4.5, -5.0, -5.5, -6.0, -6.5]


def legs_from_line(df: pd.DataFrame) -> pd.DataFrame:
    """df: game_id, home_point, result, kick, week -> two legs per game."""
    a = df.assign(side="home", x=df.home_point, margin=df.result)
    b = df.assign(side="away", x=-df.home_point, margin=-df.result)
    out = pd.concat([a, b], ignore_index=True)
    out["set"] = np.select([out.x.isin(WONG_DOG + WONG_FAV), out.x.isin(PLAC_DOG + PLAC_FAV)],
                           ["WONG", "PLACEBO"], "other")
    s = out.margin + out.x + 6
    out["win"] = (s > 0).astype(float)
    out["push"] = (s == 0).astype(float)
    return out


def binom_line(w: int, n: int, p0: float) -> str:
    from scipy.stats import binomtest
    if n == 0:
        return "n=0"
    bt = binomtest(w, n, p0)
    ci = bt.proportion_ci(0.90)
    return (f"{w}/{n} = {100*w/n:.1f}% (90% CI {100*ci.low:.1f}-{100*ci.high:.1f}); "
            f"p vs {100*p0:.2f}% = {bt.pvalue:.3f}")


def part_d(g26, O26):
    bar("D. Wong teaser legs, 2026 (DraftKings' own line, latest snapshot >= 1h before kickoff)")
    from scipy.stats import binomtest
    o = O26[O26.lead_hours >= 1.0].dropna(subset=["point"])
    res = g26.set_index("gid")
    sets = {}
    dk = o[o.bookmaker == "draftkings"].sort_values("snapshot_at").groupby("game_id").tail(1)
    sets["DraftKings line"] = dk[["game_id", "point"]].rename(columns={"point": "home_point"})
    bett = o[o.bookmaker.isin(L.BETTABLE)]
    last = bett.sort_values("snapshot_at").groupby(["game_id", "bookmaker"]).tail(1)
    sets["close (nflverse)"] = pd.DataFrame({"game_id": res.index, "home_point": -res.spread_line.values})
    out = {}
    for lab, d in sets.items():
        d = d.merge(res[["result", "week", "kick"]], left_on="game_id", right_index=True)
        d = d[d.result.notna()]
        out[lab] = legs_from_line(d)
    # best bettable line per side: the most favourable point any bettable book shows
    lb = last.merge(res[["result", "week", "kick"]], left_on="game_id", right_index=True)
    lb = lb[lb.result.notna()]
    best_home = lb.groupby("game_id").point.max()
    best_away = (-lb.point).groupby(lb.game_id).max()
    bl = []
    for gid in best_home.index:
        r = res.loc[gid]
        bl.append({"game_id": gid, "side": "home", "x": best_home[gid], "margin": r.result,
                   "week": r.week, "kick": r.kick})
        bl.append({"game_id": gid, "side": "away", "x": best_away[gid], "margin": -r.result,
                   "week": r.week, "kick": r.kick})
    bl = pd.DataFrame(bl)
    bl["set"] = np.select([bl.x.isin(WONG_DOG + WONG_FAV), bl.x.isin(PLAC_DOG + PLAC_FAV)],
                          ["WONG", "PLACEBO"], "other")
    s = bl.margin + bl.x + 6
    bl["win"], bl["push"] = (s > 0).astype(float), (s == 0).astype(float)
    out["best bettable line"] = bl
    print(f"graded games: {int(res.result.notna().sum())}")
    print("expectation (scripts/nfl_edge_wong_teaser hold-out 2020-25): bettable best line WONG 75.66% "
          "(456 legs), close 75.84% (447); placebo 71.87% / 71.55%")
    for lab, legs in out.items():
        for st in ("WONG", "PLACEBO"):
            z = legs[legs.set == st]
            w, n = int(z.win.sum()), len(z)
            print(f"  {lab:20s} {st:8s} legs {n:>3} pushes {int(z.push.sum())}  "
                  f"{binom_line(w, n, 0.7385)} | p vs 75.79% = "
                  f"{(binomtest(w, n, 0.7579).pvalue if n else float('nan')):.3f}")
            if st == "WONG" and n:
                FAMILY.setdefault("D", []).append((f"{lab} WONG vs 73.85%",
                                                   binomtest(w, n, 0.7385).pvalue,
                                                   n, 100 * (w / n)))
        z = legs[legs.set == "WONG"]
        if len(z):
            print(f"      WONG dogs {int(z[z.x > 0].win.sum())}/{int((z.x > 0).sum())}, "
                  f"favourites {int(z[z.x < 0].win.sum())}/{int((z.x < 0).sum())}; by week: "
                  + ", ".join(f"w{w}: {int(v.win.sum())}/{len(v)}" for w, v in z.groupby("week")))
    z = out["DraftKings line"]
    gx = z[z.x.abs() <= 10.5].groupby("x").agg(legs=("win", "size"), won=("win", "sum"))
    gx["rate%"] = (100 * gx.won / gx.legs).round(1)
    print("  neighbourhood, DraftKings line, every starting point x (6-pt teased legs; WONG = "
          "+1.5..+2.5 and -7.5..-8.5):")
    print("    " + gx.T.to_string().replace("\n", "\n    "))
    for be_, lab in ((0.7385, "-120"), (0.7579, "-135")):
        r = 0.7566
        if r > be_:
            n_need = ((Z_A * math.sqrt(be_ * (1 - be_)) + Z_B * math.sqrt(r * (1 - r))) / (r - be_)) ** 2
            print(f"  legs needed for 2026 alone to show the 2020-25 bettable-best rate 75.66% "
                  f"beats {100*be_:.2f}% ({lab}): {n_need:.0f}")
        else:
            print(f"  the 2020-25 bettable-best rate 75.66% does not exceed {100*be_:.2f}% ({lab})")
    # 2-team tickets, kickoff order within week, DraftKings line
    z = out["DraftKings line"]
    z = z[z.set == "WONG"].sort_values(["week", "kick", "game_id"])
    tickets = []
    for wk, g in z.groupby("week"):
        g = g.drop_duplicates("game_id")
        rows = g.to_dict("records")
        for i in range(0, len(rows) - 1, 2):
            a, b = rows[i], rows[i + 1]
            lose = (a["win"] == 0 and a["push"] == 0) or (b["win"] == 0 and b["push"] == 0)
            tickets.append({"week": wk, "win": float(a["win"] == 1 and b["win"] == 1),
                            "refund": float((not lose) and not (a["win"] == 1 and b["win"] == 1))})
    T = pd.DataFrame(tickets)
    if len(T):
        for price in (-120, -135):
            d = float(L.am_to_dec(price))
            prof = np.where(T.win == 1, d - 1, np.where(T.refund == 1, 0.0, -1.0))
            c = cell(prof, T.week)
            print(f"  2-team tickets, DraftKings line, kickoff order, at {price}: {fmt(c)}")
    # DK-line expectation 2020-25 with the same code
    h = L.odds_hist(["spreads"])
    h = h[(h.bookmaker == "draftkings") & (h.lead_hours >= 1.0)].dropna(subset=["point"])
    h = h.sort_values("snapshot_at").groupby("game_id").tail(1)
    gh = L.games()
    gh["gid"] = gh.game_id
    h["gid"] = h.game_id.str.replace("^NFL_", "", regex=True)
    d = h.merge(gh[["gid", "result", "week", "kick", "season"]], on="gid")
    d = d[d.result.notna()].rename(columns={"point": "home_point"})
    lh = legs_from_line(d)
    zz = lh[lh.set == "WONG"]
    print(f"  expectation recomputed: DraftKings line 2020-25 WONG legs "
          f"{binom_line(int(zz.win.sum()), len(zz), 0.7385)}")
    rate = zz.win.mean()
    for be_, lab in ((0.7385, "-120"), (0.7579, "-135")):
        delta = rate - be_
        if delta > 0:
            n_need = ((Z_A * math.sqrt(be_ * (1 - be_)) + Z_B * math.sqrt(rate * (1 - rate))) / delta) ** 2
            print(f"  legs needed for 2026 alone to show {100*rate:.2f}% beats {100*be_:.2f}% ({lab}): "
                  f"{n_need:.0f}")
        else:
            print(f"  the 2020-25 DraftKings-line rate {100*rate:.2f}% does not exceed the {lab} "
                  f"break-even {100*be_:.2f}%: no sample size separates them")


# ─── E. wind totals ──────────────────────────────────────────────────────

def issued_forecast(sid: str, start: str, end: str) -> pd.DataFrame:
    import requests
    OM_DIR.mkdir(parents=True, exist_ok=True)
    f = OM_DIR / f"issued_{sid}_{start}_{end}.json"
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
    else:
        lat, lon = STADIUM_COORDS[sid]
        hourly = ["wind_speed_10m"] + [f"wind_speed_10m_previous_day{i}" for i in range(1, 8)]
        p = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
             "hourly": ",".join(hourly), "wind_speed_unit": "mph", "timezone": "UTC"}
        r = requests.get("https://historical-forecast-api.open-meteo.com/v1/forecast",
                         params=p, timeout=120)
        r.raise_for_status()
        d = r.json()
        f.write_text(json.dumps(d), encoding="utf-8")
        time.sleep(0.5)
    h = pd.DataFrame(d["hourly"])
    h["ts"] = pd.to_datetime(h.time, utc=True)
    h["stadium_id"] = sid
    return h


def part_e(g26):
    bar("E. nfl_wind_totals: production 2026 record and what the rule would have bet")
    pk = pd.read_parquet(C / "picks_nfl.parquet")
    pk = pk[(pk.model_id == "nfl_wind_totals") & (pk.signal_type == "BET")].copy()
    pk["profit_u"] = pd.to_numeric(pk.profit_flat, errors="coerce") / 100
    pk["price"] = pd.to_numeric(pk.dk_odds, errors="coerce")
    pk["line"] = pd.to_numeric(pk.scored_line, errors="coerce")
    pk["void"] = pk.condition_status.astype(str).eq("VOID")
    pk["lead_d"] = (pd.to_datetime(pk.game_time, utc=True, format="mixed")
                    - pd.to_datetime(pk.created_at, utc=True, format="mixed")).dt.total_seconds() / 86400
    tot = g26.set_index("gid")["total"]
    pk["final_total"] = pk.game_id.map(tot)
    s = pk[pk.result.isin(["WIN", "LOSS", "PUSH"]) & pk.price.notna()]
    ROI_B = 0.5634 * 1.9091 - 1
    print(f"production BET rows {len(pk)}: settled {len(s)}, VOID {int(pk.void.sum())}, "
          f"unsettled {int(pk.result.isna().sum())}")
    print(f"  {'production':40s} {HDRB}")
    print(f"  {'settled BETs (flat units)':40s} {fmt(cell(s.profit_u, s.game_id, ROI_B), True)}")
    v = pk[pk.void & pk.final_total.notna()].copy()
    if len(v):
        won = v.final_total < v.line
        push = v.final_total == v.line
        v["p_re"] = np.where(push, 0, np.where(won, payout(v.price), -1.0))
        v["ev"] = pd.to_numeric(v.model_probability, errors="coerce") * (1 + payout(v.price)) - 1
        print(f"  {'VOIDed week-2 picks graded from results':40s} {fmt(cell(v.p_re, v.game_id))}"
              f"   (EV at the price: {', '.join(f'{x:+.3f}' for x in v.ev)}; floor now "
              f"{config.min_ev_for('nfl_wind_totals'):.2f})")
        sv = pd.concat([s.assign(pp=s.profit_u), v.assign(pp=v.p_re)])
        print(f"  {'settled + voided, all graded':40s} {fmt(cell(sv.pp, sv.game_id, ROI_B), True)}")
    dk = s[s.pick_label.astype(str).str.contains(", DK)", regex=False)]
    print(f"  {'settled BETs placed at DraftKings only':40s} {fmt(cell(dk.profit_u, dk.game_id))}")
    wk = s.game_id.str.split("_").str[2].astype(int)
    for nm, m in (("settled, early weeks 1-2", wk <= 2), ("settled, late weeks 3-5", wk >= 3)):
        print(f"  {nm:40s} {fmt(cell(s[m].profit_u, s[m].game_id)) if m.sum() else 0}")
    print(pk[["game_id", "pick_label", "price", "result", "profit_u", "void", "lead_d", "final_total"]]
          .to_string(index=False))

    # the rule from issued forecasts
    g = g26.copy()
    g["kick_utc"] = g.kick
    oa = g[open_air_mask(g)]
    miss = sorted(set(oa.stadium_id) - set(STADIUM_COORDS))
    print(f"\nopen-air games weeks 1-5 (open_air_mask): {len(oa)}; stadiums without coordinates "
          f"(cannot be priced, as production): {miss}")
    oa = oa[oa.stadium_id.isin(STADIUM_COORDS)]
    fc = []
    for sid in sorted(oa.stadium_id.unique()):
        try:
            fc.append(issued_forecast(sid, "2026-09-08", "2026-10-13"))
        except Exception as exc:  # noqa: BLE001
            print(f"  forecast fetch failed for {sid}: {exc}")
    fc = pd.concat(fc, ignore_index=True)
    oa = oa.assign(hr=oa.kick.dt.floor("h"))
    m = oa.merge(fc, left_on=["stadium_id", "hr"], right_on=["stadium_id", "ts"], how="left")
    rows = []
    for r in m.itertuples(index=False):
        fire = None
        for d in (4, 3, 2, 1):
            v_ = getattr(r, f"wind_speed_10m_previous_day{d}")
            if v_ is not None and np.isfinite(v_) and v_ >= 11.0:
                fire = (d, v_)
                break
        fc_all = {d: getattr(r, f"wind_speed_10m_previous_day{d}") for d in (1, 2, 3, 4)}
        rows.append({"game_id": r.gid, "fire_d": fire[0] if fire else np.nan,
                     "fc": fire[1] if fire else max([x for x in fc_all.values() if x is not None
                                                     and np.isfinite(x)], default=np.nan),
                     **{f"fc_d{d}": fc_all[d] for d in (1, 2, 3, 4)},
                     "obs_wind": r.wind, "total_line": r.total_line, "under_odds": r.under_odds,
                     "over_odds": r.over_odds, "total": r.total})
    W = pd.DataFrame(rows)
    W["p_model"] = [wt.model_under_prob(d, 11.0) if np.isfinite(d) else np.nan for d in W.fire_d]
    W["p_mkt"] = [wt.devig_two_way(u, o_)[0] for u, o_ in zip(W.under_odds, W.over_odds)]
    W["edge"] = W.p_model - W.p_mkt
    W["ev"] = W.p_model * (1 + payout(W.under_odds)) - 1
    W["qual"] = W.fire_d.notna() & (W.edge >= 0.03) & (W.ev >= float(config.min_ev_for("nfl_wind_totals")))
    W["graded"] = W.total.notna()
    won = W.total < W.total_line
    push = W.total == W.total_line
    W["profit"] = np.where(push, 0.0, np.where(won, payout(W.under_odds), -1.0))
    W.loc[~W.graded, "profit"] = np.nan
    print("\nrule replay (issued forecast at kickoff hour, first d in 4..1 with >= 11 mph; price = "
          "nflverse CLOSE):")
    print(W[W.fire_d.notna()][["game_id", "fire_d", "fc", "fc_d4", "fc_d3", "fc_d2", "fc_d1",
                               "obs_wind", "total_line", "under_odds", "edge", "ev", "qual",
                               "total", "profit"]].round(3).to_string(index=False))
    q = W[W.qual & W.graded]
    c = cell(q.profit, q.game_id, ROI_B)
    fam("E", "rule replay at close", c)
    print(f"  {'rule replay, qualifying games, graded':40s} {fmt(c, True)}")
    calm = W[W.fire_d.isna() & W.graded]
    print(f"  {'PLACEBO calm open-air (no fire), under':40s} {fmt(cell(calm.profit, calm.game_id))}")
    dome = g26[~open_air_mask(g26.assign(kick_utc=g26.kick)) & g26.total.notna()]
    dw = dome.total < dome.total_line
    dp = np.where(dome.total == dome.total_line, 0.0, np.where(dw, payout(dome.under_odds), -1.0))
    print(f"  {'PLACEBO domes / closed / unknown roof, under':40s} {fmt(cell(dp, dome.gid))}")
    print("  neighbourhood: forecast threshold (fire at the first d in 4..1 with fc >= thr; "
          "model_under_prob(d, thr); same edge/EV gates; close price):")
    for thr in (9.0, 10.0, 11.0, 12.0, 13.0, 15.0):
        rr = []
        for r in m.itertuples(index=False):
            fd = next((d for d in (4, 3, 2, 1)
                       if np.isfinite(getattr(r, f"wind_speed_10m_previous_day{d}"))
                       and getattr(r, f"wind_speed_10m_previous_day{d}") >= thr), None)
            if fd is None or not np.isfinite(r.total):
                continue
            pm = wt.model_under_prob(fd, thr)
            pmk = wt.devig_two_way(r.under_odds, r.over_odds)[0]
            ev = pm * (1 + float(payout(r.under_odds))) - 1
            if pm - pmk < 0.03 or ev < float(config.min_ev_for("nfl_wind_totals")):
                continue
            pr = 0.0 if r.total == r.total_line else (float(payout(r.under_odds)) if r.total < r.total_line else -1.0)
            rr.append((r.gid, pr, int(r.gid.split("_")[2])))
        z = pd.DataFrame(rr, columns=["game_id", "profit", "week"])
        cc = cell(z.profit, z.game_id) if len(z) else {"n": 0}
        if thr != 11.0:
            fam("E", f"thr {thr}", cc)
        e_ = z[z.week <= 2]
        l_ = z[z.week >= 3]
        print(f"    >= {thr:>4.0f} mph {fmt(cc)}  | early {len(e_)} bets {e_.profit.sum():+.2f}u, "
              f"late {len(l_)} bets {l_.profit.sum():+.2f}u")
    rep = set(W[W.qual].game_id)
    prod = set(pk.game_id)
    print(f"  rule-qualifying games {len(rep)}, production BET games {len(prod)}; both "
          f"{len(rep & prod)}; production only {sorted(prod - rep)}; replay only {sorted(rep - prod)}")


# ─── main ────────────────────────────────────────────────────────────────

def main():
    from data.ingestors.nfl_props_data_ingestor import norm_player_name
    for s in ("Marvin Harrison Jr.", "Ja'Kobi Lane", "Amon-Ra St. Brown", "Kenneth Walker III"):
        assert norm_name(s) == norm_player_name(s), s
    g26 = nflverse_2026()
    print(f"2026 games weeks 1-5 in nflverse: {len(g26)}; with a final score: "
          f"{int(g26.result.notna().sum())} (weeks 1-4 all 64 + "
          f"{sorted(g26[(g26.week == 5) & g26.result.notna()].gid)})")
    P = load_props_2026()
    act, adiag = player_actuals_2026(P[["game_id", "norm", "player_name"]])
    print(f"stat log 2026: {adiag['games_logged']} games; feed->log alias pairs found by the "
          f"nickname rule: {adiag['alias_pairs']} e.g. {adiag['alias_examples'][:6]}")
    snaps = pd.read_parquet(C / "local_nfl_snap_counts.parquet", columns=["game_id"])
    print(f"snap-count rows for 2026 games: {int(snaps.game_id.str.startswith('NFL_2026').sum())} "
          f"(none -> an active player with zero touches has no row and is VOID)")
    inj_get, inj_dates = injury_index_by_date()
    print(f"injury reports cached: {inj_dates[0]} .. {inj_dates[-1]} (decisions before the first "
          f"report date fail open, as production does with no rows)")

    part_a(P, act, inj_get, g26)
    part_a_extreme(P, act)
    O26 = L.odds_2026(["spreads"])
    O26["game_id"] = "NFL_" + O26.game_id      # the lib strips the prefix; picks/props keep it
    O26["bookmaker"] = O26.bookmaker.astype("category")
    print(f"odds_2026 spreads, pre-game rows: {len(O26):,}")
    part_c(g26, O26)
    part_d(g26, O26)
    del O26
    part_e(g26)
    try:
        part_b(P, act, g26)
    except Exception as exc:  # noqa: BLE001
        print(f"\nB. FAILED at runtime: {type(exc).__name__}: {exc}")

    bar("MULTIPLICITY: Benjamini-Hochberg (q = 0.10) over every 2026 cell searched, per part")
    for part in ("A", "A-extreme", "B", "C", "D", "E"):
        bh(part)
    allrows = [r for v in FAMILY.values() for r in v]
    print(f"  all parts pooled: {len(allrows)} cells")
    FAMILY["ALL"] = allrows
    bh("ALL")


if __name__ == "__main__":
    main()
