"""NBA count props: the NHL count-prop recipe, walk-forward, graded at real prices.

Every stage reads the local research cache (data/local/nba, written from
Supabase by scripts/nba_research_cache.py) and writes its output to a work
folder, so a later stage can be re-run without the earlier ones. Nothing here
reads or writes the database, and nothing calls the odds feed.

    python -m scripts.nba_prop_model_lab frame      # the feature frame (models/nba_props.build_frame)
    python -m scripts.nba_prop_model_lab prices     # the priced universe: filters, names, settlement
    python -m scripts.nba_prop_model_lab blind      # blind over / under per market (the lean)
    python -m scripts.nba_prop_model_lab fit [--variant full|no_avail|no_sched|no_lines]
    python -m scripts.nba_prop_model_lab gate       # step 4: does the model beat the naive projections?
    python -m scripts.nba_prop_model_lab grid       # the priced grid, every cell
    python -m scripts.nba_prop_model_lab report     # the markdown report

THE RULES OF THE SEARCH, fixed before the first priced cell was read:

  * Walk-forward: season S (2024, 2025, 2026 = 2023-24, 2024-25, 2025-26) is
    scored by models fitted on box seasons 2019..S-1. The negative-binomial
    width for S is fitted on season S-1 as predicted by the S-1 fold.
  * Every CHOICE -- two-stage or direct, Poisson or negative binomial, the
    side, the EV floor, the cap -- is made on 2024 + 2025 only. 2026 is the
    confirmation season and is printed, never optimised.
  * A market whose model does not beat the season average, the last ten and
    the weighted mean on log-likelihood AND on Brier at the book's line, on
    2024 + 2025, is closed before any price is read for it.
  * The deciding price is the best price among config.BEST_LINE_BOOKMAKERS at
    the same line in the same snapshot (one snapshot a game, ~54 minutes
    before tip, every book at the same instant); DraftKings alone beside it.
    Price floor -200. Units: one unit to win, risk capped at 3.
  * A void (did not play) takes its slot: the card decides before it knows.
  * The card skips a player listed Out or Doubtful at the decision.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import models.nba_props as nb  # noqa: E402

TEMP = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild")
RESULTS = TEMP / "results"
WORK = RESULTS / "props_model_work"
SEASONS = (2024, 2025, 2026)
CHOOSE = (2024, 2025)
CONFIRM = 2026
FOLDS = (2023, 2024, 2025, 2026)
COHERENT = (1.00, 1.15)
PRICE_FLOOR = -200.0
EV_CUTS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25)
LAST_RESEARCH_DATE = "2026-10-20"          # rows on or after this are the live 2026-27 collection

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── frame ────────────────────────────────────────────────────────────────────

LINE_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)   # the seasons the bought game lines cover


def stage_frame(with_lines: bool = False) -> None:
    """The frame. WITHOUT game lines unless asked for AND the bought lines cover every season whole:
    a feature present for some games and missing for others by purchase order would bias the fit."""
    data = nb.load_cache(with_props=True, with_lines=with_lines)
    props = data["nba_props"]
    props = props[props.game_date < LAST_RESEARCH_DATE]
    dec = nb.decisions_for(data, props)
    if with_lines:
        g = data["nba_games"].set_index("game_id").season
        o = data["nba_odds"]
        per = (o[(o.market == "spreads") & (o.snapshot_type != "in_play")].drop_duplicates("game_id")
               .game_id.map(g).value_counts().reindex(LINE_SEASONS).fillna(0).astype(int))
        n = data["nba_games"].groupby("season").size().reindex(LINE_SEASONS)
        log(f"games with a spread, by season: {per.to_dict()} of {n.to_dict()}")
        if (per / n).min() < 0.97:
            raise SystemExit("game lines are not complete for every season; not building the lines frame")
    log(f"building frame (lines: {with_lines})")
    fr = nb.build_frame(data, dec, with_lines=with_lines)
    WORK.mkdir(parents=True, exist_ok=True)
    fr.to_parquet(WORK / ("frame_lines.parquet" if with_lines else "frame.parquet"))
    dec.to_parquet(WORK / "decisions.parquet")
    log(f"frame {fr.shape}; usable played rows by season "
        f"{fr[nb.usable(fr) & fr.played].groupby('season').size().to_dict()}")


def load_frame(lines: bool = False) -> pd.DataFrame:
    return pd.read_parquet(WORK / ("frame_lines.parquet" if lines else "frame.parquet"))


# ── the priced universe ──────────────────────────────────────────────────────

def stage_prices() -> None:
    """Every quote that could be bet, with its player, his status at the decision, and what happened."""
    data = nb.load_cache(with_props=True, with_lines=False)
    fr = load_frame()
    games = data["nba_games"].set_index("game_id")
    px = data["nba_props"]
    notes = {}
    px = px[(px.game_date < LAST_RESEARCH_DATE) & px.market.isin(nb.BY_MARKET)].copy()
    px["season"] = px.game_id.map(games.season)
    px = px[px.season.isin(SEASONS)]
    notes["quotes_14_markets_3_seasons"] = len(px)
    tip = nb._utc(px.game_id.map(games.commence_time))
    snap = nb._utc(px.snapshot_at)
    late = snap >= tip
    notes["dropped_snapshot_at_or_after_tip"] = {"quotes": int(late.sum()), "games": int(px[late].game_id.nunique())}
    px = px[~late]
    inbox = px.game_id.isin(set(fr.game_id))
    notes["dropped_game_without_regular_box"] = {"quotes": int((~inbox).sum()),
                                                 "games": sorted(px[~inbox].game_id.unique().tolist())}
    px = px[inbox]
    two = px.over_price.notna() & px.under_price.notna()
    s = nb.implied(px.over_price) + nb.implied(px.under_price)
    bad = two & ~((s >= COHERENT[0]) & (s <= COHERENT[1]))
    notes["dropped_incoherent_pairs"] = {"total": int(bad.sum()),
                                         "by_book": px[bad].bookmaker.value_counts().to_dict()}
    px = px[~bad]
    px["two_sided"] = px.over_price.notna() & px.under_price.notna()
    kind = px.market.map(lambda m: nb.BY_MARKET[m].kind)
    one = (kind == "count") & ~px.two_sided
    notes["one_sided_count_quotes_not_decided_on"] = px[one].groupby(["market", "bookmaker"]).size().unstack(
        fill_value=0).to_dict()
    # ── names: both teams' players, this season and last ──
    ros = fr[["season", "team", "player_id", "player_name"]].drop_duplicates(["season", "team", "player_id"])
    g = px[["game_id", "season"]].drop_duplicates().copy()
    g["home"], g["away"] = g.game_id.map(games.home_team), g.game_id.map(games.away_team)
    sides = pd.concat([g.rename(columns={"home": "team"})[["game_id", "season", "team"]],
                       g.rename(columns={"away": "team"})[["game_id", "season", "team"]]])
    sides = pd.concat([sides, sides.assign(season=sides.season - 1)])
    roster = sides.merge(ros, on=["season", "team"])[["game_id", "player_id", "player_name"]]
    m = nb.match_names(px[["game_id", "player_name"]].drop_duplicates(), roster)
    how = m.how.value_counts().to_dict()
    notes["name_match_by_rule"] = how
    notes["refused_shared_names"] = m[m.how == "shared"].player_name.value_counts().head(30).to_dict()
    notes["unmatched_names_top"] = m[m.how == "none"].player_name.value_counts().head(40).to_dict()
    un = px.merge(m, on=["game_id", "player_name"])
    notes["unmatched_quote_share_by_book"] = un.groupby("bookmaker").player_id.apply(
        lambda s_: round(float(s_.isna().mean()), 4)).to_dict()
    px = un[un.player_id.notna()].copy()
    # ── his row in this game: played?, status at the decision, what he did ──
    keep = ["game_id", "player_id", "team", "opponent", "played", "status", "covered", "gp",
            "min_l"] + list(nb.BASE_STATS)
    row = fr[keep].drop_duplicates(["game_id", "player_id"])
    px = px.merge(row, on=["game_id", "player_id"], how="left")
    px["in_box"] = px.played.notna()
    px["played"] = px.played.fillna(False).astype(bool)
    px["usable"] = (px.gp >= nb.MIN_GAMES) & px.min_l.notna()
    for mk, spec in nb.BY_MARKET.items():
        sel = px.market == mk
        px.loc[sel, "actual"] = nb.settle_value(spec, px[sel]).values
    px["actual"] = px.actual.where(px.played)
    notes["matched_quotes"] = len(px)
    notes["void_share_by_status"] = px.drop_duplicates(["game_id", "player_id"]).groupby(
        px.status.fillna("no report")).played.apply(lambda s_: round(1 - float(s_.mean()), 4)).to_dict()
    px = px.drop(columns=list(nb.BASE_STATS) + ["min_l"])
    px.to_parquet(WORK / "quotes.parquet")
    (WORK / "prices_notes.json").write_text(json.dumps(notes, indent=1, default=str), encoding="utf-8")
    log(json.dumps({k: v for k, v in notes.items() if k not in ("one_sided_count_quotes_not_decided_on",)},
                   indent=1, default=str)[:6000])


def load_quotes() -> pd.DataFrame:
    return pd.read_parquet(WORK / "quotes.parquet")


# ── units ────────────────────────────────────────────────────────────────────

def grade(b: pd.DataFrame) -> pd.DataFrame:
    """result W/L/P/V, risk and units for bets with side, line, price, actual, played."""
    b = b.copy()
    risk, win = nb.stake(b.price.values)
    over = b.side.values == "over"
    act = b.actual.values
    w = np.where(over, act > b.line.values, act < b.line.values)
    push = act == b.line.values
    void = ~b.played.values | np.isnan(act)
    b["result"] = np.where(void, "V", np.where(push, "P", np.where(w, "W", "L")))
    b["risk"] = np.where(void | push, 0.0, risk)
    b["units"] = np.where(void | push, 0.0, np.where(w, win, -risk))
    return b


def summary(b: pd.DataFrame) -> dict:
    s = b[b.result.isin(["W", "L", "P"])]
    n, risk, u = len(s), float(s.risk.sum()), float(s.units.sum())
    return {"bets": n, "units": round(u, 2), "roi%": round(100 * u / risk, 2) if risk > 0 else np.nan,
            "win%": round(100 * float((s.result == "W").mean()), 1) if n else np.nan,
            "voids": int((b.result == "V").sum())}


def day_ci(b: pd.DataFrame, n: int = 4000, level: float = 0.90) -> tuple[float, float]:
    """Whole-day bootstrap of ROI (units / risk), 4,000 resamples, seed 7."""
    s = b[b.result.isin(["W", "L", "P"])]
    if s.empty:
        return (np.nan, np.nan)
    d = s.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    u, r = d.u.values, d.r.values
    idx = np.random.default_rng(7).integers(0, len(d), size=(n, len(d)))
    roi = u[idx].sum(axis=1) / r[idx].sum(axis=1)
    a = (1 - level) / 2
    lo, hi = np.percentile(roi, [100 * a, 100 * (1 - a)])
    return round(100 * lo, 2), round(100 * hi, 2)


# ── the propositions: best price at one line, per side ───────────────────────

def propositions(q: pd.DataFrame, dk_only: bool = False, book_set: tuple | None = None) -> pd.DataFrame:
    """One row per (game, player, market, line, side): the best bettable price at that line.

    Count markets decide only on two-sided coherent quotes; double- and
    triple-doubles take the one-sided Yes the books post. Price floor -200.
    """
    bk = ["draftkings"] if dk_only else list(book_set or nb.books())
    rank = {b: i for i, b in enumerate(nb.books())}
    q = q[q.bookmaker.isin(bk)]
    kind = q.market.map(lambda m: nb.BY_MARKET[m].kind)
    q = q[(kind != "count") | q.two_sided]
    parts = []
    for side, col in (("over", "over_price"), ("under", "under_price")):
        s = q[q[col].notna()].copy()
        s["side"], s["price"] = side, s[col]
        parts.append(s)
    s = pd.concat(parts, ignore_index=True)
    s = s[s.price >= PRICE_FLOOR]
    s["_r"] = s.bookmaker.map(rank)
    s = s.sort_values(["price", "_r"], ascending=[False, True], kind="mergesort")
    s = s.drop_duplicates(["game_id", "player_id", "market", "line", "side"])
    return s.rename(columns={"bookmaker": "book"}).drop(columns=["_r"])


def main_lines(q: pd.DataFrame, dk_only: bool = False) -> pd.DataFrame:
    """The ONE line per (game, player, market) a blind bettor would take: DraftKings' two-sided line,
    else the line most bettable books hang (ties: the lower line)."""
    bk = ["draftkings"] if dk_only else list(nb.books())
    q = q[q.bookmaker.isin(bk) & (q.two_sided | (q.market.map(lambda m: nb.BY_MARKET[m].kind) != "count"))]
    dk = q[q.bookmaker == "draftkings"].drop_duplicates(["game_id", "player_id", "market"])
    dk = dk.set_index(["game_id", "player_id", "market"]).line
    mode = (q.groupby(["game_id", "player_id", "market", "line"]).size().rename("n").reset_index()
            .sort_values(["n", "line"], ascending=[False, True])
            .drop_duplicates(["game_id", "player_id", "market"]).set_index(["game_id", "player_id", "market"]).line)
    out = mode.to_frame("line")
    out["line"] = dk.reindex(out.index).fillna(out.line)
    return out.reset_index()


# ── blind baselines ──────────────────────────────────────────────────────────

def stage_blind() -> None:
    q = load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"])]
    rows = []
    keep = {}
    for dk_only in (False, True):
        P = propositions(q, dk_only)
        L = main_lines(q, dk_only)
        P = P.merge(L, on=["game_id", "player_id", "market", "line"])
        for mk in nb.BY_MARKET:
            for side in ("over", "under"):
                b = grade(P[(P.market == mk) & (P.side == side)])
                for season in (None,) + SEASONS:
                    bb = b if season is None else b[b.season == season]
                    r = summary(bb)
                    rows.append({"market": mk, "price": "DK" if dk_only else "best", "side": side,
                                 "season": str(season or "all"), **r})
                if not dk_only:
                    keep[(mk, side)] = b
    t = pd.DataFrame(rows)
    t.to_parquet(WORK / "blind.parquet")
    for (mk, side), b in keep.items():
        out = b.assign(model_prob=np.nan, ev=np.nan)
        out[BET_COLS].to_parquet(RESULTS / f"props_model_blind_{mk}_{side}.parquet")
    piv = t[t.season == "all"].pivot_table(index="market", columns=["price", "side"], values=["roi%", "bets"])
    print(piv.round(2).to_string())
    print(t[(t.price == "best")].pivot_table(index=["market", "side"], columns="season", values="roi%").round(2))


BET_COLS = ["game_id", "game_date", "season", "player_name", "player_id", "market", "side", "line", "book",
            "price", "model_prob", "ev", "result", "risk", "units"]


# ── walk-forward fits ────────────────────────────────────────────────────────

VARIANTS = {"full": (), "no_avail": ("avail",), "no_sched": ("sched",), "no_team": ("team",),
            "lines": (), "lines_no_avail": ("avail",)}
KEY_COLS = ["game_id", "player_id", "player_name", "season", "game_date", "team", "opponent", "played",
            "status", "minutes_exact", "tm_o_min", "d_o_min", "tm_r_min", "own_q"] + list(nb.BASE_STATS)


def stage_fit(variant: str = "full", methods: str = "all", folds: tuple = FOLDS) -> None:
    """Season S (each of FOLDS) predicted by models fitted on 2019..S-1.

    two-stage: minutes model + per-minute rate per base stat (mean = minutes x rate);
    direct: one Poisson mean per count market; binary: double- and triple-double.
    `methods`: 'all' or 'two_stage' (the ablations refit only the two-stage model).
    """
    lines = variant.startswith("lines")
    drop = VARIANTS[variant] + (() if lines else ("lines",))
    fr = load_frame(lines)
    use = nb.usable(fr)
    for S in folds:
        out_path = WORK / f"pred_{variant}_{S}.parquet"
        if out_path.exists():
            log(f"{variant} {S}: exists, skipped")
            continue
        tr = fr[use & fr.played & fr.season.between(nb.FIRST_TRAIN_SEASON, S - 1)]
        te = fr[use & (fr.season == S)]
        log(f"{variant} {S}: train {len(tr):,} rows, score {len(te):,} (played {int(te.played.sum()):,})")
        P = te[KEY_COLS].copy()
        fitted = {}
        fitted["minutes"] = fm = nb.fit_minutes(tr, drop)
        P["min_hat"] = nb.predict_minutes(fm, te)
        for s in nb.BASE_STATS:
            fitted[f"rate_{s}"] = nb.fit_rate(tr, s, drop)
            P[f"mu2_{s}"] = nb.predict_rate_mean(fitted[f"rate_{s}"], te, P.min_hat.values)
        log(f"{variant} {S}: two-stage done")
        if methods == "all":
            for spec in nb.COUNT_SPECS:
                fitted[f"direct_{spec.market}"] = nb.fit_direct(tr, spec, drop)
                P[f"mud_{spec.market}"] = nb.predict_direct(fitted[f"direct_{spec.market}"], te)
            for spec in nb.SPECS:
                if spec.kind != "count":
                    fitted[f"binary_{spec.market}"] = nb.fit_binary(tr, spec, drop)
                    P[f"pb_{spec.market}"] = nb.predict_binary(fitted[f"binary_{spec.market}"], te)
            # the naive projections (step 4), carried for the same rows
            for s in nb.BASE_STATS:
                for b in ("sa", "l10", "ew"):
                    P[f"{b}_{s}"] = te[f"{b}_{s}"].values
            log(f"{variant} {S}: direct + binary done")
        pd.to_pickle(fitted, WORK / f"models_{variant}_{S}.pkl")
        P.to_parquet(out_path)
    log(f"{variant}: all folds written")


def load_pred(variant: str = "full") -> pd.DataFrame:
    return pd.concat([pd.read_parquet(WORK / f"pred_{variant}_{S}.parquet") for S in FOLDS], ignore_index=True)


# ── step 4: the model against the naive projections, before any price ───────

COUNT_METHODS = ("two_stage", "direct")
NAIVE = ("sa", "l10", "ew")
MU_FLOOR = 0.05


def market_mu(P: pd.DataFrame, spec: nb.Spec, method: str) -> np.ndarray:
    if method == "two_stage":
        mu = sum(P[f"mu2_{s}"].values for s in spec.parts)
    elif method == "direct":
        mu = P[f"mud_{spec.market}"].values
    else:
        mu = sum(P[f"{method}_{s}"].values for s in spec.parts)
    return np.clip(np.asarray(mu, dtype=float), MU_FLOOR, None)


def binary_baselines() -> pd.DataFrame:
    """Season-to-date, last-ten and weighted double- and triple-double rates, as of before each game."""
    fr = load_frame()[["game_id", "player_id", "season", "tip", "played"] + list(nb.BASE_STATS)]
    pl = fr[fr.played].sort_values(["player_id", "tip", "game_id"]).copy()
    for spec in nb.SPECS:
        if spec.kind == "count":
            continue
        k = spec.kind
        pl[k] = nb.settle_value(spec, pl)
        g = pl.groupby("player_id", sort=False)[k]
        pl[f"ew_{k}"] = g.transform(lambda x: x.ewm(halflife=8.0).mean().shift(1))
        pl[f"l10_{k}"] = g.transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
        pl[f"sa_{k}"] = pl.groupby(["player_id", "season"], sort=False)[k].transform(
            lambda x: x.shift(1).expanding().mean())
        pl[f"sa_{k}"] = pl[f"sa_{k}"].fillna(pl[f"ew_{k}"])
    cols = [f"{b}_{k}" for b in NAIVE for k in ("dd", "td")]
    return pl[["game_id", "player_id"] + cols]


def binary_indep(P: pd.DataFrame, alphas: dict, need: int) -> np.ndarray:
    """P(at least `need` of points, rebounds, assists, steals, blocks reach 10), components independent."""
    q = []
    for s in ("points", "rebounds", "assists", "steals", "blocks"):
        q.append(nb.p_over(np.clip(P[f"mu2_{s}"].values, MU_FLOOR, None), 9.5, alphas.get(s, 0.0)))
    q = np.vstack(q)                         # 5 x n
    # distribution of the number of successes, by convolution
    dist = np.zeros((6, q.shape[1]))
    dist[0] = 1.0
    for i in range(5):
        new = np.zeros_like(dist)
        new[1:] += dist[:-1] * q[i]
        new[:] += dist * (1 - q[i])
        dist = new
    return np.clip(dist[need:].sum(axis=0), 1e-5, 1 - 1e-5)


def fit_alphas(pred: pd.DataFrame) -> dict:
    """alpha[(method, market, S)]: fitted on season S-1 as predicted by fold S-1 (out of sample)."""
    out = {}
    for S in SEASONS:
        prev = pred[(pred.season == S - 1) & pred.played]
        for spec in nb.COUNT_SPECS:
            y = nb.settle_value(spec, prev).values
            for method in COUNT_METHODS + NAIVE:
                mu = market_mu(prev, spec, method)
                ok = np.isfinite(y) & np.isfinite(mu)
                out[(method, spec.market, S)] = nb.fit_alpha(y[ok], mu[ok])
        for s in nb.BASE_STATS:
            y = prev[s].values.astype(float)
            mu = np.clip(prev[f"mu2_{s}"].values, MU_FLOOR, None)
            ok = np.isfinite(y)
            out[("two_stage_base", s, S)] = nb.fit_alpha(y[ok], mu[ok])
    return out


def market_lines() -> pd.DataFrame:
    """Per priced (game, player, market): the main line, and the market's own no-vig P(over) there --
    the mean over the bettable books quoting that line two-sided, and Pinnacle's where it does."""
    q = load_quotes()
    q = q[q.usable]
    L = main_lines(q)
    t = q[q.two_sided].merge(L, on=["game_id", "player_id", "market", "line"])
    io, iu = nb.implied(t.over_price), nb.implied(t.under_price)
    t["fair_over"] = io / (io + iu)
    soft = t[t.bookmaker.isin(nb.books())].groupby(["game_id", "player_id", "market"]).fair_over.mean()
    pin = t[t.bookmaker == "pinnacle"].groupby(["game_id", "player_id", "market"]).fair_over.mean()
    L = L.set_index(["game_id", "player_id", "market"])
    L["mkt_over"], L["pin_over"] = soft.reindex(L.index), pin.reindex(L.index)
    yes = q[(q.market.map(lambda m: nb.BY_MARKET[m].kind) != "count")]
    L["yes_only"] = False
    return L.reset_index()


def stage_gate(variant: str = "full") -> None:
    pred = load_pred(variant)
    alphas = fit_alphas(pred)
    bb = binary_baselines()
    pred = pred.merge(bb, on=["game_id", "player_id"], how="left")
    L = market_lines()
    rows, briers = [], []
    for spec in nb.SPECS:
        Lm = L[L.market == spec.market][["game_id", "player_id", "line", "mkt_over", "pin_over"]]
        for S in SEASONS:
            te = pred[(pred.season == S) & pred.played]
            y = nb.settle_value(spec, te).values
            priced = te[["game_id", "player_id"]].merge(Lm, on=["game_id", "player_id"], how="left")
            has = priced.line.notna().values
            line = priced.line.values
            over = np.where(has, y > line, np.nan)
            if spec.kind == "count":
                cands = {}
                for method in COUNT_METHODS + NAIVE:
                    mu = market_mu(te, spec, method)
                    for dist in ("poisson", "nb"):
                        a = alphas[(method, spec.market, S)] if dist == "nb" else 0.0
                        cands[(method, dist)] = (nb.nb_logpmf(y, mu, a), mu, a)
                ok = np.all([np.isfinite(v[0]) for v in cands.values()], axis=0) & np.isfinite(y)
                for (method, dist), (ll, mu, a) in cands.items():
                    po = nb.p_over(mu, np.where(has, line, 0.5), a)
                    sel = ok & has
                    rows.append({"market": spec.market, "season": S, "method": method, "dist": dist, "alpha": a,
                                 "n_all": int(ok.sum()), "ll_all": float(ll[ok].mean()),
                                 "n_priced": int(sel.sum()), "ll_priced": float(ll[sel].mean()),
                                 "brier": float(np.mean((po[sel] - over[sel]) ** 2)),
                                 "mean_mu": float(mu[sel].mean()), "mean_y": float(y[sel].mean())})
                sel = has & np.isfinite(y)
                m_ok = sel & np.isfinite(priced.mkt_over.values)
                p_ok = sel & np.isfinite(priced.pin_over.values)
                briers.append({"market": spec.market, "season": S,
                               "n_mkt": int(m_ok.sum()),
                               "brier_mkt": float(np.mean((priced.mkt_over.values[m_ok] - over[m_ok]) ** 2)),
                               "over_rate": float(np.nanmean(over[sel])),
                               "mkt_over_mean": float(np.nanmean(priced.mkt_over.values[m_ok])),
                               "n_pin": int(p_ok.sum()),
                               "brier_pin": float(np.mean((priced.pin_over.values[p_ok] - over[p_ok]) ** 2))
                               if p_ok.any() else np.nan})
            else:
                k = spec.kind
                need = 2 if k == "dd" else 3
                a_base = {s: alphas[("two_stage_base", s, S)] for s in nb.BASE_STATS}
                cands = {("binary", "bern"): te[f"pb_{spec.market}"].values,
                         ("indep", "bern"): binary_indep(te, a_base, need)}
                for b in NAIVE:
                    cands[(b, "bern")] = np.clip(te[f"{b}_{k}"].values, 0.005, 0.995)
                ok = np.all([np.isfinite(v) for v in cands.values()], axis=0) & np.isfinite(y)
                for (method, dist), p in cands.items():
                    ll = y * np.log(p) + (1 - y) * np.log(1 - p)
                    sel = ok & has
                    rows.append({"market": spec.market, "season": S, "method": method, "dist": dist, "alpha": 0.0,
                                 "n_all": int(ok.sum()), "ll_all": float(ll[ok].mean()),
                                 "n_priced": int(sel.sum()), "ll_priced": float(ll[sel].mean()),
                                 "brier": float(np.mean((p[sel] - y[sel]) ** 2)),
                                 "mean_mu": float(p[sel].mean()), "mean_y": float(y[sel].mean())})
    G = pd.DataFrame(rows)
    B = pd.DataFrame(briers)
    G.to_parquet(WORK / f"gate_{variant}.parquet")
    B.to_parquet(WORK / f"gate_market_{variant}.parquet")
    (WORK / f"alphas_{variant}.json").write_text(json.dumps({"|".join(map(str, k)): v for k, v in alphas.items()},
                                                            indent=0), encoding="utf-8")
    # ── the choices, on 2024 + 2025 only ──
    decide = {}
    ch = G[G.season.isin(CHOOSE)]
    w = ch.assign(llw=ch.ll_priced * ch.n_priced, bw=ch.brier * ch.n_priced, llaw=ch.ll_all * ch.n_all)
    agg = w.groupby(["market", "method", "dist"]).agg(n=("n_priced", "sum"), llw=("llw", "sum"), bw=("bw", "sum"),
                                                      na=("n_all", "sum"), llaw=("llaw", "sum"))
    agg["ll_priced"], agg["brier"], agg["ll_all"] = agg.llw / agg.n, agg.bw / agg.n, agg.llaw / agg.na
    agg = agg[["n", "ll_priced", "ll_all", "brier"]].reset_index()
    for spec in nb.SPECS:
        a = agg[agg.market == spec.market]
        models = a[a.method.isin(COUNT_METHODS if spec.kind == "count" else ("binary", "indep"))]
        best = models.sort_values("ll_priced", ascending=False).iloc[0]
        naive = a[a.method.isin(NAIVE)]
        nbest = naive.loc[naive.groupby("method").ll_priced.idxmax()]          # each naive at its better width
        beats_ll = bool((best.ll_priced > nbest.ll_priced).all())
        nb_brier = naive.loc[naive.groupby("method").brier.idxmin()]
        beats_brier = bool((best.brier < nb_brier.brier).all())
        decide[spec.market] = {"method": best.method, "dist": best.dist, "ll_priced": round(best.ll_priced, 5),
                               "brier": round(best.brier, 5),
                               "naive_ll": {r.method: round(r.ll_priced, 5) for r in nbest.itertuples()},
                               "naive_brier": {r.method: round(r.brier, 5) for r in nb_brier.itertuples()},
                               "beats_ll": beats_ll, "beats_brier": beats_brier, "pass": beats_ll and beats_brier}
    (WORK / f"gate_decide_{variant}.json").write_text(json.dumps(decide, indent=1), encoding="utf-8")
    print(agg.sort_values(["market", "ll_priced"], ascending=[True, False]).round(5).to_string())
    print(json.dumps(decide, indent=1))
    print(B.round(4).to_string())


# ── the priced grid ──────────────────────────────────────────────────────────

STRUCTURES = ("player", "game", "cap6", "cap4", "cap2")     # ordered: the plateau's neighbours are adjacent
SIDES = {"over": ("over",), "under": ("under",), "both": ("over", "under")}
N_PLACEBO = 20                 # real ROI above all 20 shuffles = p < 0.05


def load_alphas(variant: str) -> dict:
    raw = json.loads((WORK / f"alphas_{variant}.json").read_text(encoding="utf-8"))
    return {tuple(k.split("|")[:2]) + (int(k.split("|")[2]),): v for k, v in raw.items()}


def scored_propositions(variant: str = "full", dk_only: bool = False, book_set: tuple | None = None) -> pd.DataFrame:
    """Every bettable proposition with the chosen model's probability, EV, and its grade."""
    q = load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"])]
    P = propositions(q, dk_only, book_set)
    pred = load_pred(variant)
    decide = json.loads((WORK / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    alphas = load_alphas(variant)
    keep = ["game_id", "player_id"] + [c for c in pred.columns if c.startswith(("mu2_", "mud_", "pb_"))] + \
        ["tm_o_min", "d_o_min", "tm_r_min", "own_q", "min_hat"]
    P = P.merge(pred[keep], on=["game_id", "player_id"], how="inner")
    parts = []
    for mk, spec in nb.BY_MARKET.items():
        s = P[P.market == mk].copy()
        if s.empty:
            continue
        d = decide[mk]
        if spec.kind == "count":
            mu = market_mu(s, spec, d["method"])
            a = np.array([alphas[(d["method"], mk, int(S))] if d["dist"] == "nb" else 0.0 for S in s.season])
            po = np.array([float(nb.p_over(m_, l_, a_)) for m_, l_, a_ in zip(mu, s.line.values, a)]) \
                if len(s) < 50 else _p_over_vec(mu, s.line.values, a)
            s["mu"], s["alpha"] = mu, a
        else:
            if d["method"] == "binary":
                po = s[f"pb_{mk}"].values
            else:
                need = 2 if spec.kind == "dd" else 3
                po = np.empty(len(s))
                for S in SEASONS:
                    sel = (s.season == S).values
                    a_base = {b: alphas[("two_stage_base", b, S)] for b in nb.BASE_STATS}
                    po[sel] = binary_indep(s[sel], a_base, need)
            s["mu"], s["alpha"] = po, np.nan
        s["p_over"] = po
        parts.append(s)
    P = pd.concat(parts, ignore_index=True)
    P["model_prob"] = np.where(P.side == "over", P.p_over, 1 - P.p_over)
    P["ev"] = nb.expected_value(P.model_prob, P.price)
    P["game_date"] = pd.to_datetime(P.game_date)
    P = grade(P)
    # Pinnacle's no-vig at the same line, same snapshot (the stand-in for a closing price)
    pin = q[(q.bookmaker == "pinnacle") & q.two_sided][["game_id", "player_id", "market", "line", "over_price",
                                                         "under_price"]]
    io, iu = nb.implied(pin.over_price), nb.implied(pin.under_price)
    pin = pin.assign(pin_over=io / (io + iu))[["game_id", "player_id", "market", "line", "pin_over"]]
    P = P.merge(pin.drop_duplicates(["game_id", "player_id", "market", "line"]),
                on=["game_id", "player_id", "market", "line"], how="left")
    P["pin_fair"] = np.where(P.side == "over", P.pin_over, 1 - P.pin_over)
    P["ev_pin"] = P.pin_fair * nb.decimal(P.price) - 1
    # the season's early / late half
    med = P.groupby("season").game_date.transform(lambda d: d.min() + (d.max() - d.min()) / 2)
    P["half"] = np.where(P.game_date <= med, "early", "late")
    return P


def _p_over_vec(mu, line, alpha) -> np.ndarray:
    out = np.empty(len(mu))
    for a in np.unique(alpha):
        sel = alpha == a
        out[sel] = nb.p_over(mu[sel], line[sel], float(a))
    return out


def apply_rule(C: pd.DataFrame, cut: float, structure: str) -> pd.DataFrame:
    """C sorted by EV descending. Best EV per player-market, then the structure."""
    b = C[C.ev >= cut]
    b = b.drop_duplicates(["game_id", "player_id", "market"])
    if structure == "player":
        return b
    b = b.drop_duplicates("game_id")
    if structure == "game":
        return b
    n = int(structure[3:])
    return b.groupby("game_date", sort=False).head(n)


def cell_stats(b: pd.DataFrame, with_ci: bool = True) -> dict:
    s = b[b.result.isin(["W", "L", "P"])]
    out = {"bets": len(s), "voids": int((b.result == "V").sum())}
    for S in SEASONS:
        x = s[s.season == S]
        out[f"n_{S}"], out[f"u_{S}"] = len(x), round(float(x.units.sum()), 2)
        out[f"roi_{S}"] = round(100 * float(x.units.sum() / x.risk.sum()), 2) if len(x) else np.nan
    ch = s[s.season.isin(CHOOSE)]
    out["n_choose"], out["u_choose"] = len(ch), round(float(ch.units.sum()), 2)
    out["roi_choose"] = round(100 * float(ch.units.sum() / ch.risk.sum()), 2) if len(ch) else np.nan
    out["units"] = round(float(s.units.sum()), 2)
    out["roi"] = round(100 * float(s.units.sum() / s.risk.sum()), 2) if len(s) else np.nan
    out["u_per_season"] = round(out["units"] / len(SEASONS), 2)
    for h in ("early", "late"):
        x = s[s.half == h]
        out[f"u_{h}"] = round(float(x.units.sum()), 2)
    out["under_share"] = round(float((s.side == "under").mean()), 3) if len(s) else np.nan
    wl = s[s.result.isin(["W", "L"])]
    out["claimed"] = round(float(wl.model_prob.mean()), 4) if len(wl) else np.nan
    out["won"] = round(float((wl.result == "W").mean()), 4) if len(wl) else np.nan
    if with_ci and len(s) >= 30:
        out["ci_lo"], out["ci_hi"] = day_ci(s)
    return out


def scopes(decide: dict) -> dict:
    sc = {mk: (mk,) for mk in nb.BY_MARKET}
    sc["pooled_pass"] = tuple(mk for mk, d in decide.items() if d["pass"])
    sc["pooled_all"] = tuple(nb.BY_MARKET)
    return sc


def stage_grid(variant: str = "full") -> None:
    decide = json.loads((WORK / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    rows = []
    for price in ("best", "DK"):
        P = scored_propositions(variant, dk_only=(price == "DK"))
        P.to_parquet(WORK / f"scored_{variant}_{price}.parquet")
        for scope, mks in scopes(decide).items():
            if not mks:
                continue
            for side, which in SIDES.items():
                C = P[P.market.isin(mks) & P.side.isin(which)].sort_values(
                    ["ev", "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")
                if C.empty:
                    continue
                for structure in STRUCTURES:
                    for cut in EV_CUTS:
                        b = apply_rule(C, cut, structure)
                        rows.append({"variant": variant, "price": price, "scope": scope, "side": side,
                                     "structure": structure, "cut": cut, **cell_stats(b, with_ci=(price == "best"))})
        log(f"grid {variant} {price}: {len(rows)} cells so far")
    G = pd.DataFrame(rows)
    G.to_parquet(WORK / f"grid_{variant}.parquet")
    log(f"grid {variant}: {len(G)} cells written")


# ── choosing on 2024 + 2025, judging on all three ────────────────────────────

def choose_cut(G: pd.DataFrame) -> pd.DataFrame:
    """Per (scope, side, structure) at the best price: the cut with the most units a season on 2024 + 2025
    among cuts where both seasons have >= 30 bets and are positive. 2026 plays no part."""
    out = []
    g = G[(G.price == "best")]
    for (scope, side, structure), x in g.groupby(["scope", "side", "structure"]):
        ok = x[(x.n_2024 >= 30) & (x.n_2025 >= 30) & (x.u_2024 > 0) & (x.u_2025 > 0)]
        if ok.empty:
            continue
        best = ok.sort_values(["u_choose", "cut"], ascending=[False, True]).iloc[0]
        out.append(best)
    return pd.DataFrame(out)


def neighbours(G: pd.DataFrame, r) -> pd.DataFrame:
    g = G[(G.price == "best") & (G.scope == r.scope) & (G.side == r.side)]
    i = EV_CUTS.index(r.cut)
    j = STRUCTURES.index(r.structure)
    cuts = [EV_CUTS[k] for k in (i - 1, i + 1) if 0 <= k < len(EV_CUTS)]
    structs = [STRUCTURES[k] for k in (j - 1, j + 1) if 0 <= k < len(STRUCTURES)]
    a = g[(g.structure == r.structure) & g.cut.isin(cuts)]
    b = g[(g.cut == r.cut) & g.structure.isin(structs)]
    return pd.concat([a, b])


def placebo(P: pd.DataFrame, mks: tuple, which: tuple, cut: float, structure: str, n: int = N_PLACEBO) -> list[float]:
    """The same rule on probabilities shuffled within (night, market): each player's model mean over his
    middle line (counts) or his model probability (yes/no markets) handed to another player priced in
    the same market that night, then every line re-priced from the shuffled number."""
    rng = np.random.default_rng(7)
    C = P[P.market.isin(mks)]
    C = C.merge(main_lines_from(C), on=["game_id", "player_id", "market"], how="left")
    pl = (C.drop_duplicates(["game_id", "player_id", "market"])
          [["game_date", "market", "game_id", "player_id", "mu", "main_line"]]
          .sort_values(["game_date", "market"], kind="mergesort").reset_index(drop=True))
    cnt_pl = pl.market.map(lambda m: nb.BY_MARKET[m].kind == "count").values
    val = np.where(cnt_pl, pl.mu.values / pl.main_line.values, pl.mu.values)
    dcode = pl.game_date.rank(method="dense").values
    mcode = pl.market.astype("category").cat.codes.values
    key = pd.MultiIndex.from_frame(C[["game_id", "player_id", "market"]])
    pos = pd.Series(np.arange(len(pl)), index=pd.MultiIndex.from_frame(pl[["game_id", "player_id", "market"]]))
    idx = pos.reindex(key).values
    cnt = C.market.map(lambda m: nb.BY_MARKET[m].kind == "count").values
    rois = []
    for _ in range(n):
        order = np.lexsort((rng.random(len(pl)), mcode, dcode))   # same blocks, shuffled inside each
        v = val[order]
        mu_p = np.where(cnt_pl, v * pl.main_line.values, v)[idx]
        po = np.where(cnt, _p_over_vec(mu_p, C.line.values, np.nan_to_num(C.alpha.values)), mu_p)
        mp = np.where(C.side.values == "over", po, 1 - po)
        Y = C.assign(model_prob=mp, ev=nb.expected_value(mp, C.price.values))
        Y = Y[Y.side.isin(which)].sort_values(["ev", "market", "player_id", "line"],
                                               ascending=[False, True, True, True], kind="mergesort")
        b = apply_rule(Y, cut, structure)
        s = b[b.result.isin(["W", "L", "P"])]
        rois.append(100 * float(s.units.sum() / s.risk.sum()) if len(s) else np.nan)
    return rois


def main_lines_from(C: pd.DataFrame) -> pd.DataFrame:
    """Each priced player's middle line across the propositions (the line the ratio is taken against)."""
    m = C.groupby(["game_id", "player_id", "market"]).line.median().rename("main_line").reset_index()
    return m


def blind_same(P: pd.DataFrame, mks: tuple, side: str) -> dict:
    """A blind bet on `side` for every player priced in these markets, at his main line and the best price."""
    q = load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"]) & q.market.isin(mks)]
    L = main_lines(q)
    b = P[P.market.isin(mks) & (P.side == side)].merge(L, on=["game_id", "player_id", "market", "line"])
    return summary(b)


PIN_MIN = 30          # the Pinnacle stand-in counts only on at least this many priced bets


def rebar(J: pd.DataFrame) -> pd.DataFrame:
    """Re-read the Pinnacle stand-in with its minimum coverage, and the all-bars flag, on saved judgements."""
    if J.empty:
        return J
    J = J.copy()
    J["b11_pinnacle_fair_median_positive"] = (J.pin_covered >= PIN_MIN) & (J.pin_median_ev > 0)
    bars = [c for c in J.columns if c.startswith("b") and c[1:2].isdigit()]
    J["passes_all"] = J[bars].all(axis=1)
    J["passes_all_but_b11"] = J[[b for b in bars if not b.startswith("b11")]].all(axis=1)
    return J


def blind_structured(P: pd.DataFrame, mks: tuple, side: str, structure: str) -> dict:
    """Blind bets on `side` in the SAME structure as the rule (one a player-market / a game / N a night),
    ordered by something that is not the model: the highest price on offer, and at random (mean of 10)."""
    U = P[P.market.isin(mks) & (P.side == side)]
    Cp = U.assign(ev=U.price).sort_values(["ev", "market", "player_id", "line"],
                                           ascending=[False, True, True, True], kind="mergesort")
    hp = cell_stats(apply_rule(Cp, -1e9, structure), with_ci=False)
    rr = []
    for k in range(10):
        Cr = U.assign(ev=np.random.default_rng(k).random(len(U))).sort_values("ev", ascending=False)
        rr.append(cell_stats(apply_rule(Cr, -1.0, structure), with_ci=False)["roi"])
    return {"highest_price_roi": hp["roi"], "highest_price_bets": hp["bets"],
            "highest_price_by_season": [hp[f"roi_{S}"] for S in SEASONS], "random_roi": round(float(np.mean(rr)), 2)}


def stage_judge(variant: str = "full", only: str = "all") -> None:
    """Every chosen candidate against every bar. The costly checks (placebo, structured blinds) run
    only where the cheap bars (5-8 and the scope's step-4 gate) already pass."""
    G = pd.read_parquet(WORK / f"grid_{variant}.parquet")
    decide = json.loads((WORK / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    P = pd.read_parquet(WORK / f"scored_{variant}_best.parquet")
    PD = pd.read_parquet(WORK / f"scored_{variant}_DK.parquet")
    sc = scopes(decide)
    ch = choose_cut(G)
    if only == "pooled":
        ch = ch[ch.scope.str.startswith("pooled")]
    elif only == "markets":
        ch = ch[~ch.scope.str.startswith("pooled")]
    elif only == "markets_best":
        # each market's single candidate: the side, structure and floor with the most units on 2024 + 2025
        ch = ch[~ch.scope.str.startswith("pooled")]
        ch = ch.sort_values("u_choose", ascending=False).drop_duplicates("scope")
    out = []
    for r in ch.itertuples():
        mks = sc[r.scope]
        gate_ok = all(decide[m]["pass"] for m in mks) if r.scope != "pooled_all" else False
        nb_ = neighbours(G, r)
        which = SIDES[r.side]
        C = P[P.market.isin(mks) & P.side.isin(which)].sort_values(
            ["ev", "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")
        bets = apply_rule(C, r.cut, r.structure)
        s = bets[bets.result.isin(["W", "L", "P"])]
        side_share = max(r.under_share, 1 - r.under_share)
        lean_side = "under" if r.under_share >= 0.5 else "over"
        bars = {
            "b4_confirm_2026_positive": bool(r.u_2026 > 0),
            "b5_every_season_positive": all((getattr(r, f"u_{S}") > 0) or (getattr(r, f"n_{S}") < 30) for S in SEASONS),
            "b6_200_bets_ci_above_zero": bool(r.bets >= 200 and r.ci_lo > 0),
            "b7_plateau": bool(len(nb_) > 0 and (nb_.units > 0).all()),
            "b8_both_halves": bool(r.u_early > 0 and r.u_late > 0),
            "b13_gate_step4": gate_ok,
        }
        cheap = all(bars.values())
        blind = blind_same(P, mks, lean_side)
        bs = blind_structured(P, mks, lean_side, r.structure) if cheap else {}
        bars["b9_beats_blind_side"] = bool(side_share <= 0.70 or (
            r.roi > blind["roi%"] and bool(bs) and r.roi > bs["highest_price_roi"] and r.roi > bs["random_roi"]))
        pl = placebo(P, mks, which, r.cut, r.structure) if (cheap and bars["b9_beats_blind_side"]) else []
        bars["b10_placebo"] = bool(len(pl) and np.nanmax(pl) < r.roi)
        pin = s[s.ev_pin.notna()]
        bars["b11_pinnacle_fair_median_positive"] = bool(len(pin) >= PIN_MIN and pin.ev_pin.median() > 0)
        CD = PD[PD.market.isin(mks) & PD.side.isin(which)].sort_values(
            ["ev", "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")
        dk = cell_stats(apply_rule(CD, r.cut, r.structure), with_ci=False)
        rec = {**r._asdict(), "neighbours": nb_[["structure", "cut", "bets", "units", "roi"]].to_dict("records"),
               "blind_side": lean_side, "blind": blind, "blind_structured": bs,
               "placebo_mean": float(np.nanmean(pl)) if pl else np.nan,
               "placebo_max": float(np.nanmax(pl)) if pl else np.nan,
               "dk_only": dk, "pin_covered": int(len(pin)),
               "pin_median_ev": float(pin.ev_pin.median()) if len(pin) else np.nan,
               "pin_share_positive": float((pin.ev_pin > 0).mean()) if len(pin) else np.nan,
               **bars, "passes_all": all(bars.values())}
        out.append(rec)
        name = f"{r.scope}_{r.side}_{r.structure}_ev{r.cut:.2f}"
        bets[BET_COLS + ["ev_pin", "half", "mu", "status"]].to_parquet(
            RESULTS / f"props_model_{variant}_{name}.parquet")
        log(f"judged {name}: {r.bets} bets, roi {r.roi}, cheap bars {'pass' if cheap else 'fail'}"
            f"{', placebo max %.2f' % np.nanmax(pl) if pl else ''}")
    J = pd.DataFrame(out)
    J.to_pickle(WORK / f"judge_{variant}_{only}.pkl")
    show = ["scope", "side", "structure", "cut", "bets", "units", "roi", "u_per_season", "u_2024", "u_2025", "u_2026",
            "ci_lo", "ci_hi", "u_early", "u_late", "under_share", "claimed", "won", "placebo_max", "pin_median_ev",
            "passes_all"]
    print(J[show].to_string())


# ── feature groups, tested by removal (and lines, by addition) ───────────────

def _two_stage_props(variant: str, P0: pd.DataFrame) -> pd.DataFrame:
    """P0's count-market propositions re-priced with `variant`'s two-stage means and widths."""
    pred = load_pred(variant)
    al = {}
    for S in SEASONS:
        prev = pred[(pred.season == S - 1) & pred.played]
        for spec in nb.COUNT_SPECS:
            y = nb.settle_value(spec, prev).values
            mu = market_mu(prev, spec, "two_stage")
            ok = np.isfinite(y) & np.isfinite(mu)
            al[(spec.market, S)] = nb.fit_alpha(y[ok], mu[ok])
    keep = ["game_id", "player_id"] + [f"mu2_{s}" for s in nb.BASE_STATS]
    X = P0.drop(columns=[c for c in P0.columns if c.startswith("mu2_")], errors="ignore").merge(
        pred[keep], on=["game_id", "player_id"], how="inner")
    parts = []
    for spec in nb.COUNT_SPECS:
        s = X[X.market == spec.market].copy()
        mu = market_mu(s, spec, "two_stage")
        a = np.array([al[(spec.market, int(S))] for S in s.season])
        po = _p_over_vec(mu, s.line.values, a)
        s["mu"], s["alpha"], s["p_over"] = mu, a, po
        parts.append(s)
    X = pd.concat(parts, ignore_index=True)
    X["model_prob"] = np.where(X.side == "over", X.p_over, 1 - X.p_over)
    X["ev"] = nb.expected_value(X.model_prob, X.price)
    return X, al


def stage_ablate() -> None:
    """Each group's contribution: deviance on the player-games priced, and the pooled count-market under
    rule (one a game; four a night) re-graded with the variant's probabilities, everything else equal."""
    P0 = pd.read_parquet(WORK / "scored_full_best.parquet")
    P0 = P0[P0.market.isin([s.market for s in nb.COUNT_SPECS])]
    rows, dev, base_keys = [], [], {}
    for v in ("full", "no_avail", "no_sched", "lines"):
        if not (WORK / f"pred_{v}_2026.parquet").exists():
            continue
        X, al = _two_stage_props(v, P0)
        pred = load_pred(v)
        for S in SEASONS:
            te = pred[(pred.season == S) & pred.played]
            for spec in nb.COUNT_SPECS:
                y = nb.settle_value(spec, te).values
                mu = market_mu(te, spec, "two_stage")
                ok = np.isfinite(y)
                dev.append({"variant": v, "season": S, "market": spec.market, "n": int(ok.sum()),
                            "ll": float(nb.nb_logpmf(y[ok], mu[ok], al[(spec.market, S)]).mean())})
        for st in ("game", "cap4", "cap2"):
            C = X[X.side == "under"].sort_values(["ev", "market", "player_id", "line"],
                                                 ascending=[False, True, True, True], kind="mergesort")
            sel = apply_rule(C, 0.0, st)
            keys = set(zip(sel.game_id, sel.player_id, sel.market))
            if v == "full":
                base_keys[st] = keys
            overlap = len(keys & base_keys.get(st, set())) / max(len(keys), 1)
            rows.append({"variant": v, "rule": f"under {st}", "overlap_with_full": round(overlap, 3),
                         **cell_stats(sel, with_ci=True)})
        log(f"ablate {v} done")
    A = pd.DataFrame(rows)
    D = pd.DataFrame(dev)
    A.to_parquet(WORK / "ablate_priced.parquet")
    D.to_parquet(WORK / "ablate_dev.parquet")
    d = D.pivot_table(index=["market"], columns=["variant"], values="ll", aggfunc="mean")
    print((d.sub(d["full"], axis=0) * 1000).round(3).to_string())
    print(A[["variant", "rule", "overlap_with_full", "bets", "units", "roi", "u_2024", "u_2025", "u_2026", "ci_lo",
             "ci_hi"]].to_string())


# ── diagnostics for the report ───────────────────────────────────────────────

def _agg(y: pd.DataFrame) -> pd.Series:
    s = y[y.result.isin(["W", "L", "P"])]
    return pd.Series({"bets": len(s), "units": round(float(s.units.sum()), 1),
                      "roi%": round(100 * float(s.units.sum() / s.risk.sum()), 2) if len(s) else np.nan,
                      "claimed": round(float(s.model_prob.mean()), 3) if len(s) else np.nan,
                      "won": round(float((s.result == "W").mean()), 3) if len(s) else np.nan})


def stage_diag(variant: str = "full") -> None:
    decide = json.loads((WORK / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    P = pd.read_parquet(WORK / f"scored_{variant}_best.parquet")
    mks = scopes(decide)["pooled_pass"]
    U = P[P.market.isin(mks) & (P.side == "under")].sort_values(
        ["ev", "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")
    sec = {}
    # 1. floors above the pre-registered range (diagnostic only)
    rows = []
    for st in ("game", "cap4"):
        for cut in (0.0, 0.25, 0.30, 0.40, 0.50, 0.75, 1.0):
            b = apply_rule(U, cut, st)
            rows.append({"structure": st, "EV floor": cut, **cell_stats(b, with_ci=False)})
    T = pd.DataFrame(rows)[["structure", "EV floor", "bets", "units", "roi", "u_2024", "u_2025", "u_2026",
                            "claimed", "won"]]
    sec["Diagnostic: floors above the pre-registered 0.25 (pooled unders)"] = (
        "Inside 0.00-0.25 the floor does not bind once there is one bet a game: the best under in almost "
        "every game already has EV above 0.25. Higher floors, shown for diagnosis only (not a candidate, "
        "not chosen on):\n\n" + _md(T))
    # 2. what the one-a-game bets are
    b = apply_rule(U, 0.0, "game")
    b = b.assign(price_band=pd.cut(b.price, [-201, -150, -120, -100, 100, 150, 200, 400, 5000]).astype(str),
                 ev_band=pd.cut(b.ev, [-1, 0.25, 0.35, 0.5, 0.75, 1.0, 10]).astype(str))
    q = load_quotes()
    q = q[q.bookmaker.isin(nb.books()) & q.two_sided]
    io, iu = nb.implied(q.over_price), nb.implied(q.under_price)
    k = ["game_id", "player_id", "market", "line"]
    cons = q.assign(fu=iu / (io + iu)).groupby(k).agg(n_books=("bookmaker", "size"), fair=("fu", "median"))
    b = b.join(cons, on=k)
    b["gap_pp"] = 100 * (b.fair - 1 / nb.decimal(b.price))
    b["n_books_at_line"] = b.n_books.clip(upper=5).astype("Int64").astype(str)
    parts = []
    for col, title in (("market", "market"), ("price_band", "price"), ("book", "deciding book"),
                       ("status", "his status at the decision"), ("n_books_at_line", "bettable books hanging that line"),
                       ("ev_band", "EV band"), ("season", "season")):
        t = b.groupby(col).apply(_agg).reset_index()
        parts.append(f"\nBy {title}:\n\n" + _md(t))
    x = b[b.gap_pp <= 2]
    parts.append(f"\nOnly bets whose price is within 2pp of the bettable books' median no-vig at that line "
                 f"(not an out-of-line quote): {_agg(x).to_dict()}; by season "
                 f"{ {S: round(100 * x[(x.season == S) & x.result.isin(['W','L','P'])].units.sum() / x[(x.season == S) & x.result.isin(['W','L','P'])].risk.sum(), 2) for S in SEASONS} }")
    y = b[b.n_books >= 2]
    parts.append(f"\nOnly bets at a line at least two bettable books hang: {_agg(y).to_dict()}; by season "
                 f"{ {S: round(100 * y[(y.season == S) & y.result.isin(['W','L','P'])].units.sum() / y[(y.season == S) & y.result.isin(['W','L','P'])].risk.sum(), 2) for S in SEASONS} }")
    sec["What the pooled one-a-game unders are"] = "".join(parts)
    # 3. calibration in the band that gets bet
    s = b[b.result.isin(["W", "L"])]
    cal = s.groupby(pd.cut(s.model_prob, [0, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.0]), observed=True).apply(
        lambda y: pd.Series({"bets": len(y), "claimed": round(y.model_prob.mean(), 3),
                             "won": round((y.result == "W").mean(), 3),
                             "price implied (vig in)": round(float((1 / nb.decimal(y.price)).mean()), 3)})).reset_index()
    cal["model_prob"] = cal.model_prob.astype(str)
    sec["Calibration in the band that gets bet (pooled one-a-game unders)"] = (
        "The model claims far more than it wins on the bets it makes (selection on its own error, as in "
        "NHL). The bet still pays because it wins more often than the PRICE implies:\n\n" + _md(cal))
    # 4. which books: every bettable book / the five DraftKings-region books / DraftKings alone
    import config
    region = tuple(config.LIVE_FEED_BOOKMAKERS)
    sets = {"all bettable (8)": None, f"DraftKings region ({len(region)})": region, "DraftKings alone": ("draftkings",)}
    rows = []
    for label, bs in sets.items():
        PP = P if bs is None else scored_propositions(variant, dk_only=(bs == ("draftkings",)),
                                                      book_set=None if bs == ("draftkings",) else bs)
        UU = PP[PP.market.isin(mks) & (PP.side == "under")].sort_values(
            ["ev", "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")
        for st in ("game", "cap6", "cap4", "cap2"):
            c = cell_stats(apply_rule(UU, 0.0, st), with_ci=True)
            rows.append({"books": label, "structure": st, **{k: c.get(k) for k in (
                "bets", "units", "roi", "u_per_season", "u_2024", "u_2025", "u_2026", "ci_lo", "ci_hi",
                "u_early", "u_late")}})
    sec["Which books: the same pooled under rule on three book sets"] = (
        f"The live 2026-27 prop collection is configured by the lead; `config.LIVE_FEED_BOOKMAKERS` = {list(region)}. "
        "The bought history has every bettable book; BetRivers, Hard Rock and BetParx (the second region) "
        "decide many of the backtest bets. Rows: the rule re-run with only these books shopped.\n\n"
        + _md(pd.DataFrame(rows)))
    # 5. Pinnacle coverage of the bets (the stand-in for a closing price)
    pc = b[b.result.isin(["W", "L", "P"])]
    cov = pc.ev_pin.notna()
    sec["Pinnacle at the same line (the stand-in for CLV)"] = (
        f"One snapshot a game exists, so no later price exists for props. Pinnacle's no-vig at the same line in the "
        f"same snapshot covers {int(cov.sum())} of {len(pc)} one-a-game bets ({100 * cov.mean():.1f}%); on those, "
        f"median EV against it {pc[cov].ev_pin.median():+.4f}, share positive {(pc[cov].ev_pin > 0).mean():.3f}, ROI on "
        f"the covered bets {100 * pc[cov].units.sum() / pc[cov].risk.sum():+.2f}%. Pinnacle quotes no line for the "
        f"other {100 * (1 - cov.mean()):.1f}% (it does not post PR/PA/RA/blocks/steals/stocks/turnovers/DD, and "
        "rarely the single-book lines). This bar is under-powered and is not counted as a pass.")
    (WORK / "diag_sections.json").write_text(json.dumps(sec, indent=1), encoding="utf-8")
    for k_, v in sec.items():
        print("##", k_)
        print(v[:3000])


# ── the teammate hypothesis, with no model: do the books under-adjust? ───────

AVAIL_BINS = [-np.inf, -20, -5, 5, 20, 40, np.inf]


def stage_avail() -> None:
    """At each player's main line: realised over rate minus the books' no-vig over probability, by how
    many MORE teammate minutes are out tonight than in his recent games (d_o_min). A book that
    under-adjusts for absences shows a residual that rises with d_o_min. Blind sides by bucket too."""
    fr = load_frame()[["game_id", "player_id", "d_o_min", "tm_o_min", "tm_r_min", "own_q", "covered"]]
    L = market_lines()
    q = load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"])]
    act = q.drop_duplicates(["game_id", "player_id", "market"])[["game_id", "player_id", "market", "actual",
                                                                 "played", "season", "game_date"]]
    x = L.merge(act, on=["game_id", "player_id", "market"]).merge(fr, on=["game_id", "player_id"], how="left")
    x = x[x.played & x.mkt_over.notna() & x.actual.notna() & x.covered.fillna(False)]
    x["over"] = (x.actual > x.line).astype(float)
    x["resid"] = x.over - x.mkt_over
    x["bin"] = pd.cut(x.d_o_min, AVAIL_BINS)
    rows = []
    for mk in [s.market for s in nb.COUNT_SPECS] + ["ALL"]:
        y = x if mk == "ALL" else x[x.market == mk]
        for b, z in y.groupby("bin", observed=True):
            se = z.resid.std() / np.sqrt(len(z)) if len(z) > 1 else np.nan
            rows.append({"market": mk, "d_o_min": str(b), "n": len(z), "over_rate": round(z.over.mean(), 4),
                         "priced_over": round(z.mkt_over.mean(), 4), "resid_pp": round(100 * z.resid.mean(), 2),
                         "se_pp": round(100 * se, 2)})
    T = pd.DataFrame(rows)
    T.to_parquet(WORK / "avail_resid.parquet")
    print(T.pivot_table(index="market", columns="d_o_min", values="resid_pp", sort=False).round(2).to_string())
    print(T[T.market == "ALL"].to_string())
    # the same, by season, for the top bucket, so a pooled number is not one season
    top = x[x.d_o_min > 20]
    print("d_o_min > 20, residual by season (pp):",
          top.groupby("season").resid.agg(lambda r: round(100 * r.mean(), 2)).to_dict(),
          "n:", top.groupby("season").size().to_dict())
    # blind OVER at the best price when d_o_min > 20, per market
    P = propositions(q)
    P = P.merge(L[["game_id", "player_id", "market", "line"]], on=["game_id", "player_id", "market", "line"])
    P = P.merge(fr[["game_id", "player_id", "d_o_min"]], on=["game_id", "player_id"], how="left")
    out = []
    for lo, hi in ((20, np.inf), (40, np.inf), (-np.inf, -20)):
        for side in ("over", "under"):
            b = grade(P[(P.d_o_min > lo) & (P.d_o_min <= hi) & (P.side == side)])
            for mk in [s.market for s in nb.COUNT_SPECS] + ["ALL"]:
                bb = b if mk == "ALL" else b[b.market == mk]
                r = summary(bb)
                out.append({"d_o_min": f"({lo},{hi}]", "side": side, "market": mk, **r,
                            **{f"roi_{S}": summary(bb[bb.season == S])["roi%"] for S in SEASONS}})
    B = pd.DataFrame(out)
    B.to_parquet(WORK / "avail_blind.parquet")
    print(B[B.market == "ALL"].to_string())
    print(B[(B.d_o_min == "(20,inf]") & (B.side == "over")].to_string())


# ── as-of checks (bar 12) ────────────────────────────────────────────────────

def stage_checks() -> None:
    """Each input as of the decision, measured on the priced games."""
    data = nb.load_cache(with_props=True, with_lines=True)
    dec = pd.read_parquet(WORK / "decisions.parquet")
    q = load_quotes()
    priced = dec[dec.game_id.isin(q.game_id)]
    g = data["nba_games"].set_index("game_id")
    lead = (nb._utc(priced.game_id.map(g.commence_time)) - priced.decision_ts).dt.total_seconds() / 60
    checks = {}
    checks["decision = the prop snapshot; minutes before the stored tip (priced games)"] = \
        lead.describe()[["count", "min", "50%", "max"]].round(1).to_dict()
    rep = nb.injury_asof(data["nba_injury_report"], priced)
    rep = rep.merge(priced, on="game_id")
    checks["injury rows read for priced games / any filed after the decision"] = \
        f"{len(rep):,} / {int((rep.report_ts > rep.decision_ts).sum())}"
    used = rep.groupby("game_id").apply(lambda x: (x.decision_ts.iloc[0] - x.report_ts.max()).total_seconds() / 60)
    checks["minutes between the report used and the decision (priced games)"] = \
        used.describe()[["count", "min", "50%", "max"]].round(1).to_dict()
    cov = nb.injury_coverage(data["nba_injury_report"], priced)
    checks["priced games with a report filed before the decision"] = f"{int(cov.sum())} of {len(priced)}"
    # what the bound changes: the same read with every report up to tip
    late = priced.assign(decision_ts=nb._utc(priced.game_id.map(g.commence_time)))
    rep_tip = nb.injury_asof(data["nba_injury_report"], late)
    a = rep[rep.status.isin(["Out", "Doubtful"])][["game_id", "player_id"]].drop_duplicates()
    b = rep_tip[rep_tip.status.isin(["Out", "Doubtful"])][["game_id", "player_id"]].drop_duplicates()
    m = b.merge(a, how="left", indicator=True)
    checks["players Out/Doubtful at tip but NOT at the decision (what reading up to tip would leak)"] = \
        int((m._merge == "left_only").sum())
    fr = load_frame()
    p = fr[fr.played & nb.usable(fr) & fr.season.isin(SEASONS)]
    checks["usable played rows whose previous game is not strictly earlier (days_since <= 0)"] = \
        int((p.days_since <= 0).sum())
    if "nba_odds" in data:
        ln = nb.lines_asof(data["nba_odds"], priced)
        checks["priced games with a spread at the decision (lines frame)"] = f"{int(ln.spread_home.notna().sum())}"
        frl = load_frame(lines=True).drop_duplicates(["game_id", "team"])
        frl = frl[frl.season.isin(SEASONS)]
        hs, as_ = frl.game_id.map(g.home_score), frl.game_id.map(g.away_score)
        margin = np.where(frl.is_home == 1, hs - as_, as_ - hs)
        checks["corr(team-side spread, team margin) - negative means the sign is right"] = \
            round(float(pd.Series(frl.spread_team.values).corr(pd.Series(margin))), 3)
    tp = data["nba_player_game_log"].groupby(["game_id", "team"]).points.sum().reset_index()
    x = tp.merge(data["nba_games"][["game_id", "home_team", "home_score", "away_score", "season"]], on="game_id")
    x = x[x.season.isin(SEASONS)]
    sc = np.where(x.team == x.home_team, x.home_score, x.away_score)
    checks["team-games where box points sum to the final score (2023-24..2025-26)"] = \
        f"{int((x.points == sc).sum())} of {len(x)}"
    st = fr[fr.covered & (fr.gp >= nb.MIN_GAMES) & ~fr.upcoming].groupby("status").played.agg(["mean", "size"])
    checks["P(played | own status at the decision), training frame"] = \
        {k: f"{v['mean']:.3f} (n={int(v['size'])})" for k, v in st.iterrows()}
    extra = json.loads((WORK / "report_extra.json").read_text(encoding="utf-8")) \
        if (WORK / "report_extra.json").exists() else {}
    extra["checks"] = {k: (v if isinstance(v, str) else json.dumps(v, default=str)) for k, v in checks.items()}
    (WORK / "report_extra.json").write_text(json.dumps(extra, indent=1), encoding="utf-8")
    print(json.dumps(checks, indent=1, default=str))


# ── the report ───────────────────────────────────────────────────────────────

def _md(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else format(v, floatfmt))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in d.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    return "\n".join(lines)


def grid_table(G: pd.DataFrame, scope: str, seasons: str = "choose") -> str:
    """One scope's grid at the best price: rows side x structure, columns EV floor,
    each cell 'ROI% (bets)' on the seasons named."""
    g = G[(G.price == "best") & (G.scope == scope)]
    if g.empty:
        return "(no cells)"
    n, roi = ("n_choose", "roi_choose") if seasons == "choose" else (f"n_{seasons}", f"roi_{seasons}")
    g = g.assign(cell=[f"{r:+.1f} ({int(k)})" if k > 0 and pd.notna(r) else "-" for r, k in zip(g[roi], g[n])])
    t = g.pivot_table(index=["side", "structure"], columns="cut", values="cell", aggfunc="first")
    t = t.reindex([(s, st) for s in SIDES for st in STRUCTURES if (s, st) in t.index])
    t.columns = [f"EV>={c:.2f}" for c in t.columns]
    return _md(t.reset_index())


def stage_report(variant: str = "full") -> None:
    notes = json.loads((WORK / "prices_notes.json").read_text(encoding="utf-8"))
    decide = json.loads((WORK / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    Gt = pd.read_parquet(WORK / f"gate_{variant}.parquet")
    Bm = pd.read_parquet(WORK / f"gate_market_{variant}.parquet")
    G = pd.read_parquet(WORK / f"grid_{variant}.parquet")
    J = rebar(pd.concat([pd.read_pickle(f) for f in sorted(WORK.glob(f"judge_{variant}_*.pkl"))],
                        ignore_index=True)) if list(WORK.glob(f"judge_{variant}_*.pkl")) else pd.DataFrame()
    blind = pd.read_parquet(WORK / "blind.parquet")
    av = pd.read_parquet(WORK / "avail_resid.parquet")
    avb = pd.read_parquet(WORK / "avail_blind.parquet")
    extra = json.loads((WORK / "report_extra.json").read_text(encoding="utf-8")) \
        if (WORK / "report_extra.json").exists() else {}
    out = []
    w = out.append
    w("# NBA count props: the NHL count-prop recipe, walk-forward, at real prices\n")
    w(f"Key `props_model`. Code: `scripts/nba_prop_model_lab.py` (stages), `models/nba_props.py` (the frame, "
      f"the models, the distributions). Data: the local research cache `data/local/nba/*.parquet`, read only. "
      f"No Odds API call, no database write. Variant reported: `{variant}`.\n")
    w(extra.get("headline", ""))
    # ── 1. data checks
    w("\n## 1. Data checks\n")
    w("**The priced universe** (`stage_prices`, every count market plus double- and triple-double, "
      "2023-24 to 2025-26, game_date < 2026-10-20):\n")
    w(f"- quotes in the 14 markets: {notes['quotes_14_markets_3_seasons']:,}; matched to a player: "
      f"{notes['matched_quotes']:,}")
    w(f"- dropped, snapshot at or after tip: {notes['dropped_snapshot_at_or_after_tip']}")
    w(f"- dropped, two-way implied sum outside 1.00-1.15: {notes['dropped_incoherent_pairs']}")
    w(f"- names matched by rule (distinct game-name pairs): {notes['name_match_by_rule']}")
    w(f"- refused, the name fits two players on the two rosters: {notes['refused_shared_names']}")
    w(f"- unmatched: {notes['unmatched_names_top']}")
    w(f"- unmatched quote share by book: {notes['unmatched_quote_share_by_book']}")
    w(f"- void share (did not play) by his own status at the decision: {notes['void_share_by_status']}")
    one = pd.DataFrame(notes["one_sided_count_quotes_not_decided_on"]).fillna(0).astype(int)
    w("\nOne-sided count-market quotes (over only; cannot be coherence-checked or bet under), excluded "
      "from every decision:\n")
    w(_md(one.reset_index().rename(columns={"index": "market"})))
    for k, v in extra.get("checks", {}).items():
        w(f"- {k}: {v}")
    # ── 2. blind
    w("\n## 2. Blind baselines: the over-lean, measured\n")
    w("Every player priced, one bet at his main line (DraftKings' two-sided line, else the line most "
      "bettable books hang), at the best bettable price there / at DraftKings alone. Units to win 1, "
      "risk capped at 3; ROI = units / units risked. Players listed Out or Doubtful at the decision excluded.\n")
    b = blind[blind.season == "all"].pivot_table(index="market", columns=["price", "side"], values="roi%")
    b.columns = [f"{p} {s} ROI%" for p, s in b.columns]
    n = blind[(blind.season == "all") & (blind.price == "best")].pivot_table(index="market", columns="side",
                                                                            values="bets")
    n.columns = [f"best {c} bets" for c in n.columns]
    w(_md(b.join(n).reset_index()))
    bs = blind[(blind.price == "best") & (blind.season != "all")].pivot_table(index=["market", "side"],
                                                                          columns="season", values="roi%")
    w("\nBy season, best price (ROI %):\n")
    w(_md(bs.reset_index()))
    # ── 3. the teammate hypothesis
    w("\n## 3. The NBA-specific hypothesis, with no model: do books under-adjust for absences?\n")
    w("At each player's main line: realised over rate minus the bettable books' mean no-vig over "
      "probability, in percentage points, by `d_o_min` = teammate minutes listed Out/Doubtful at the "
      "decision MINUS the same quantity averaged over his recent games (positive = more teammates out "
      "than he has been playing with). A book that under-adjusts shows a residual rising with "
      "`d_o_min`.\n")
    t = av.pivot_table(index="market", columns="d_o_min", values="resid_pp", sort=False)
    w(_md(t.reset_index()))
    w("\nAll markets pooled, with standard errors:\n")
    w(_md(av[av.market == "ALL"].drop(columns="market")))
    w("\nBlind sides by bucket, best price, all count markets pooled:\n")
    w(_md(avb[avb.market == "ALL"].drop(columns=["market", "voids"])))
    # ── 4. step 4
    w("\n## 4. Step 4: the model against the naive projections, before any price\n")
    w("Log-likelihood of the actual count (mean per player-game, on priced player-games; higher is "
      "better) and Brier of P(over) at the book's main line (lower is better). Naive projections: season "
      "average to date (last season's where none), last ten, weighted mean (half-life 8 games), each given "
      "its better of Poisson and negative binomial. Choices made on 2023-24 + 2024-25 only.\n")
    rows = []
    for mk, d in decide.items():
        rows.append({"market": mk, "chosen": f"{d['method']}/{d['dist']}", "LL model": d["ll_priced"],
                     **{f"LL {k}": v for k, v in d["naive_ll"].items()}, "Brier model": d["brier"],
                     **{f"Brier {k}": v for k, v in d["naive_brier"].items()}, "beats LL": d["beats_ll"],
                     "beats Brier": d["beats_brier"], "PASS": d["pass"]})
    w(_md(pd.DataFrame(rows), ".4f"))
    w("\nThe market's own no-vig probability at the same line (the bar a model must clear to have an "
      "edge), Brier per season:\n")
    mm = Gt[(Gt.dist.isin(["nb", "bern"]))].copy()
    sel = []
    for mk, d in decide.items():
        x = Gt[(Gt.market == mk) & (Gt.method == d["method"]) & (Gt.dist == d["dist"])][["market", "season",
                                                                                        "n_priced", "brier"]]
        sel.append(x)
    mb = pd.concat(sel).merge(Bm[["market", "season", "brier_mkt", "n_mkt", "brier_pin", "n_pin", "over_rate",
                                   "mkt_over_mean"]], on=["market", "season"], how="left")
    w(_md(mb, ".4f"))
    w("\nEvery method, every season (two-stage = minutes x per-minute rate; direct = one Poisson mean per "
      "market; binary = logistic for yes/no; indep = the five components treated as independent):\n")
    w(_md(Gt[["market", "season", "method", "dist", "alpha", "n_priced", "ll_priced", "ll_all", "brier",
              "mean_mu", "mean_y"]], ".4f"))
    # ── 5. the grid
    w("\n## 5. The priced grid, as neighbourhoods\n")
    w("Cell = ROI % (bets). Best bettable price at the same line, price floor -200, own probability. "
      "Structures: `player` = best EV per player per market; `game` = one bet a game (best EV); `capN` = "
      "one a game and at most N a night, best EV first. Voids take their slot. First table per scope: "
      "2023-24 + 2024-25 (where every choice is made); second: 2025-26 (confirmation, never used to "
      "choose). Scopes: each market; `pooled_pass` = the markets that passed step 4; `pooled_all` = every "
      "market (diagnostic).\n")
    for scope in [mk for mk in nb.BY_MARKET] + ["pooled_pass", "pooled_all"]:
        if not (G.scope == scope).any():
            continue
        tag = "" if scope.startswith("pooled") else ("" if decide[scope]["pass"] else
                                                      " (CLOSED at step 4: shown for completeness, not a candidate)")
        w(f"\n### {scope}{tag}\n")
        w("2023-24 + 2024-25:\n")
        w(grid_table(G, scope, "choose"))
        w("\n2025-26:\n")
        w(grid_table(G, scope, "2026"))
    # ── 6. candidates
    w("\n## 6. Candidates and the bars\n")
    w("For each scope, side and structure: the EV floor with the most units a season on 2023-24 + 2024-25 "
      "among floors where both seasons have >= 30 bets and are positive. Then every bar on all three "
      "graded seasons. `b10` placebo: each player's model-to-line ratio (yes/no: his probability) shuffled "
      "among players priced in the same market that night, 20 shuffles; passes when the real ROI beats "
      "all 20. It is run only where bars 4-8, the step-4 gate and bar 9 already pass; an empty placebo cell "
      "means not run. `b11`: no later price exists for props (one "
      "snapshot a game), so the stand-in is Pinnacle's no-vig at the same line in the same snapshot: the "
      "median bet must have positive EV against it.\n")
    if len(J):
        show = ["scope", "side", "structure", "cut", "bets", "units", "roi", "u_per_season", "u_2024", "u_2025",
                "u_2026", "ci_lo", "ci_hi", "u_early", "u_late", "under_share", "claimed", "won",
                "placebo_mean", "placebo_max", "pin_covered", "pin_median_ev"]
        bars = [c for c in J.columns if c.startswith("b") and c[1:2].isdigit()]
        Jg = J.sort_values("u_choose", ascending=False)
        w(_md(Jg[show + bars + ["passes_all_but_b11", "passes_all"]], ".3f"))
        w("\nDraftKings alone, same rule:\n")
        dk = pd.DataFrame([{"scope": r.scope, "side": r.side, "structure": r.structure, "cut": r.cut,
                            **{k: r.dk_only.get(k) for k in ("bets", "units", "roi", "u_2024", "u_2025", "u_2026")}}
                           for r in Jg.itertuples()])
        w(_md(dk))
    else:
        w("No scope, side and structure has a floor where 2023-24 and 2024-25 are both positive with 30+ bets.")
    for k, v in extra.get("sections", {}).items():
        w(f"\n## {k}\n")
        w(v)
    (RESULTS / "props_model.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    log(f"report written: {RESULTS / 'props_model.md'}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["frame", "prices", "blind", "avail", "checks", "fit", "gate", "grid", "judge",
                                      "ablate", "diag", "report"])
    ap.add_argument("--variant", default="full")
    ap.add_argument("--lines", action="store_true", help="frame: the frame with game lines")
    ap.add_argument("--methods", default="all", choices=["all", "two_stage"])
    ap.add_argument("--folds", default=",".join(map(str, FOLDS)))
    ap.add_argument("--only", default="all", choices=["all", "pooled", "markets", "markets_best"],
                    help="judge: which scopes")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.stage == "frame":
        stage_frame(a.lines)
    elif a.stage == "fit":
        stage_fit(a.variant, a.methods, tuple(int(x) for x in a.folds.split(",")))
    elif a.stage == "judge":
        stage_judge(a.variant, a.only)
    elif a.stage in ("gate", "grid", "diag", "report"):
        {"gate": stage_gate, "grid": stage_grid, "diag": stage_diag, "report": stage_report}[a.stage](a.variant)
    else:
        {"prices": stage_prices, "blind": stage_blind, "avail": stage_avail, "checks": stage_checks,
         "ablate": stage_ablate}[a.stage]()
    log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
