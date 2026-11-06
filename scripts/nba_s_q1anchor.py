"""NBA search: first-quarter player props anchored to the market's full-game number for the same player.

docs/nba_search_q1anchor.md registers every choice below, committed BEFORE this lab and before any bet in the
search was graded. The population, settlement, pricing at each book's line, the harness path, the bands and the
placebo are the props search's (scripts/nba_s_q1props.py), imported unchanged. What is new is the mean:

  ANCHOR  the same player's full-game quote on the same stat IN THE SAME FETCH (snapshot_at equal to the
          first-quarter quote's). Kind P: Pinnacle's coherent two-way quote, its proportional no-vig over at its
          line turned into a full-game mean through the full-game searches' negative-binomial table
          (scripts.nba_prop_market_lab.NBTable, width nb_alpha on box scores of earlier seasons). Kind C, only where
          Pinnacle has no coherent quote: the median of the other books' means from the same fetch, 3 or more books.
  SHARE   his recency-weighted first-quarter minutes over his recency-weighted full-game minutes, over the same
          earlier games with first-quarter court time (segment-checked), half-life 3 games, strictly before the
          game's date; fewer than 3 such games: no number.
  MEAN    anchor x share x a first-quarter factor per stat, kind and season, with the distribution, fitted
          walk-forward (scripts.nba_s_q1props.walk_forward, unchanged) on every player-game with an anchor and a
          share: a proposition's own fetch, else the game's latest full-game fetch 45-75 minutes before tip.

36 cells (asserted): Q1AP and Q1AC x points, rebounds, assists x over, under x EV >= 0.02 / 0.04 / 0.06. Controls,
never judged: the share replaced by 1 (control_league_P / _C), and the blind bet (control_blind_P / _C).

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1anchor --counts
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets \\
        PYTHONPATH=. python -m scripts.nba_s_q1anchor --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <dir> --house5
    PYTHONPATH=. python -m scripts.nba_s_q1anchor --verdict <dir>

The props search's pulled play-by-play and first-quarter quotes are read from its work folder
(NBA_S_Q1PROPS_WORK, default C:/Users/micha/AppData/Local/Temp/nba_s/q1props); this lab's own files go to
NBA_S_Q1ANCHOR_WORK.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_prop_market_lab as ML  # noqa: E402
from scripts import nba_s_q1props as Q  # noqa: E402

H, G5, V, nb = Q.H, Q.G5, Q.V, Q.nb

WORK_ENV = "NBA_S_Q1ANCHOR_WORK"
DEFAULT_WORK = "C:/Users/micha/AppData/Local/Temp/nba_s/q1anchor"
KINDS = ("pinnacle", "consensus")
FAMILIES = {"pinnacle": "Q1AP", "consensus": "Q1AC"}
CTL_LEAGUE = {"pinnacle": "control_league_P", "consensus": "control_league_C"}
CTL_BLIND = {"pinnacle": "control_blind_P", "consensus": "control_blind_C"}
VARIANTS = ("model", "league")
EXPECTED_CELLS = 36
EV_CUTS = Q.EV_CUTS
STATS = Q.STATS
Q1_MARKETS = tuple(Q.STAT_OF)                       # player_points_q1, player_rebounds_q1, player_assists_q1
BASE_OF = dict(Q.FULL_OF)                           # first-quarter market -> full-game market
STAT_OF_BASE = {BASE_OF[m]: Q.STAT_OF[m] for m in Q1_MARKETS}
SHARP = "pinnacle"
MIN_CONSENSUS = 3
MIN_SHARE_GAMES = 3
HALF_LIFE = Q.HALF_LIFE
LEAD = Q.LEAD
FIT_SEASONS = (2024, 2025, 2026)
ANCHOR_KEY = ["game_id", "player_id", "base", "T"]


def say(msg: str) -> None:
    Q.say(msg)


def work_dir() -> Path:
    return Path(os.environ.get(WORK_ENV, DEFAULT_WORK))


# ── the anchor (doc section 3) ──────────────────────────────────────────────

def full_quotes(cache: Path, work: Path) -> pd.DataFrame:
    """The full-game prop quotes through scripts.nba_prop_market_lab.build_quotes, unchanged (its name match,
    lead and coherence), cached in `work`/full_match. -> the three base markets' matched, coherent two-way quotes
    with one row per (game, player, market, book, fetch); a duplicated key is refused, as the props search does."""
    folder = Path(work) / "full_match"
    f = folder / "quotes.parquet"
    if not f.exists():
        folder.mkdir(parents=True, exist_ok=True)
        ML.CACHE, ML.WORK = Path(cache), folder
        ML.build_quotes()
    cols = ["game_id", "player_id", "player_name", "market", "bookmaker", "snapshot_at", "line", "od", "ud",
            "coherent", "namesake", "season", "lead_min"]
    q = pd.read_parquet(f, columns=cols)
    return clean_full_quotes(q)


def clean_full_quotes(q: pd.DataFrame) -> pd.DataFrame:
    q = q[q.market.isin(list(STAT_OF_BASE)) & q.player_id.notna() & ~q.namesake.fillna(False).astype(bool)
          & q.coherent.fillna(False).astype(bool)].copy()
    q = q[q.lead_min.between(*LEAD) & np.isfinite(q.line) & np.isfinite(q.od) & np.isfinite(q.ud)]
    q["player_id"] = q.player_id.astype(str)
    q["T"] = pd.to_datetime(q.snapshot_at, utc=True, format="ISO8601")
    dup = q.duplicated(["game_id", "player_id", "market", "bookmaker", "T"], keep=False)
    q = q[~dup].rename(columns={"market": "base"})
    return q.reset_index(drop=True)


def quote_means(q: pd.DataFrame, log: pd.DataFrame) -> pd.DataFrame:
    """Each coherent full-game quote's mean: the negative-binomial mean whose chance of over at the quote's line is
    its proportional no-vig over (width fitted on box scores of seasons strictly before the quote's season)."""
    out = q.copy()
    p = (1.0 / out.od) / (1.0 / out.od + 1.0 / out.ud)
    mu = np.full(len(out), np.nan)
    for (b, s), idx in out.groupby(["base", "season"], sort=False).indices.items():
        lines = out.line.to_numpy(float)[idx]
        tab = ML.NBTable(ML.nb_alpha(log, b, int(s)), lines)
        mu[idx] = tab.mu_from(lines, p.to_numpy(float)[idx])
    out["mu"] = mu
    return out


def anchors(qm: pd.DataFrame) -> pd.DataFrame:
    """Per (game, player, base market, fetch): mu_P from Pinnacle's quote; mu_C the median of the other books'
    means, NaN under MIN_CONSENSUS books; n_C the number of those books."""
    pin = qm[qm.bookmaker == SHARP].groupby(ANCHOR_KEY).mu.first().rename("mu_P")
    soft = qm[qm.bookmaker != SHARP].groupby(ANCHOR_KEY).agg(mu_C=("mu", "median"), n_C=("bookmaker", "nunique"))
    a = soft.join(pin, how="outer").reset_index()
    a["n_C"] = a.n_C.fillna(0).astype(int)
    a.loc[a.n_C < MIN_CONSENSUS, "mu_C"] = np.nan
    return a


# ── the share (doc section 4) ───────────────────────────────────────────────

def share_history(pg: pd.DataFrame) -> pd.DataFrame:
    """After each of a player's games with first-quarter court time (segment-checked) and full-game minutes:
    the recency-weighted first-quarter minutes, the recency-weighted full-game minutes over the same games, and
    how many such games there have been."""
    h = pg[(pg.q1_sec > 0) & pg.court_ok & (pg.minutes.fillna(0) > 0)].sort_values(["player_id", "date"])
    h = h[["player_id", "date", "q1_sec", "minutes"]].copy()
    h["q1_min"] = h.q1_sec / 60.0
    g = h.groupby("player_id", sort=False)
    h["m_q1"] = g.q1_min.transform(lambda s: s.ewm(halflife=HALF_LIFE).mean())
    h["m_full"] = g.minutes.transform(lambda s: s.ewm(halflife=HALF_LIFE).mean())
    h["n_sh"] = g.cumcount() + 1
    return h[["player_id", "date", "m_q1", "m_full", "n_sh"]]


def shares(targets: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    """targets: player_id, date (+ any columns). Adds share and n_sh as of strictly before the date; a player with
    fewer than MIN_SHARE_GAMES earlier games has share NaN."""
    t = Q._asof(targets, hist, ["m_q1", "m_full", "n_sh"], "player_id")
    t["n_sh"] = t.n_sh.fillna(0).astype(int)
    t["share"] = np.where(t.n_sh >= MIN_SHARE_GAMES, t.m_q1 / t.m_full, np.nan)
    return t.drop(columns=["m_q1", "m_full"])


# ── the fit table and the means ─────────────────────────────────────────────

def fit_anchors(fit: pd.DataFrame, anc: pd.DataFrame, props: pd.DataFrame) -> pd.DataFrame:
    """fit: one row per (game_id, player_id, stat). Each row's anchors: a proposition's own fetch when the row is
    a proposition of that stat's first-quarter market, else the game's latest fetch holding that kind."""
    base = fit.stat.map({v: k for k, v in STAT_OF_BASE.items()})
    f = fit.assign(base=base.to_numpy())
    # with_props holds T as naive UTC (its .values drop the zone); the anchors' T is UTC
    own = props[["game_id", "player_id", "market"]].assign(stat=props.market.map(Q.STAT_OF),
                                                           T=pd.to_datetime(props["T"], utc=True))
    f = f.merge(own[["game_id", "player_id", "stat", "T"]], on=["game_id", "player_id", "stat"], how="left")
    is_prop = f["T"].notna().to_numpy()
    a_own = f.loc[is_prop, ["game_id", "player_id", "base", "T"]].merge(anc, on=ANCHOR_KEY, how="left")
    out = {"mu_P": np.full(len(f), np.nan), "mu_C": np.full(len(f), np.nan)}
    for k in ("mu_P", "mu_C"):
        out[k][is_prop] = a_own[k].to_numpy(float)
        latest = (anc[anc[k].notna()].sort_values("T").groupby(["game_id", "player_id", "base"]).tail(1)
                  [["game_id", "player_id", "base", k]])
        rest = f.loc[~is_prop, ["game_id", "player_id", "base"]].merge(latest, on=["game_id", "player_id", "base"],
                                                                        how="left")
        out[k][~is_prop] = rest[k].to_numpy(float)
    f["mu_P"], f["mu_C"] = out["mu_P"], out["mu_C"]
    f["is_prop"] = is_prop
    return f.drop(columns="T")


@dataclass
class Fits:
    factor: dict        # (kind, variant, stat, season) -> factor
    alpha: dict         # (kind, variant, stat, season) -> alpha
    maps: dict          # (kind, variant) -> {(stat, season): line map}


def means(f: pd.DataFrame) -> tuple[pd.DataFrame, Fits]:
    """f: the fit table with y (first-quarter stat), ok_settled, share, season, mu_P, mu_C. Adds mu_<kind>_<variant>
    for both kinds and both variants (the share, or 1 for the league control), walk-forward per stat."""
    f = f.copy()
    fac, alp, maps = {}, {}, {}
    share_ok = np.isfinite(f.share.to_numpy(float))
    for kind, col in (("pinnacle", "mu_P"), ("consensus", "mu_C")):
        anchor = f[col].to_numpy(float)
        for variant in VARIANTS:
            raw = anchor * (f.share.to_numpy(float) if variant == "model" else 1.0)
            mu = np.full(len(f), np.nan)
            vmaps = {}
            for s in STATS:
                sel = (f.stat == s).to_numpy()
                y = f.y.to_numpy(float)[sel]
                ok = (f.ok_settled.to_numpy(bool) & share_ok & np.isfinite(anchor))[sel] & np.isfinite(y)
                fs, a_s, m_s, mu_s = Q.walk_forward(y, raw[sel], f.season.to_numpy(int)[sel], ok, s)
                mu[sel] = mu_s
                fac.update({(kind, variant, s, S): v for S, v in fs.items()})
                alp.update({(kind, variant, s, S): v for S, v in a_s.items()})
                vmaps.update({(s, S): v for S, v in m_s.items()})
            f[f"mu_{kind}_{variant}"] = np.where(share_ok, mu, np.nan)
            maps[(kind, variant)] = vmaps
    return f, Fits(fac, alp, maps)


def kind_props(props: pd.DataFrame, f: pd.DataFrame, fits: Fits, kind: str, variant: str) -> pd.DataFrame:
    """The propositions of one anchor kind with that variant's mean, alpha and line-map key. Kind C holds only
    propositions with no coherent Pinnacle quote in their fetch."""
    cols = ["game_id", "player_id", "stat", "mu_P", f"mu_{kind}_{variant}"]
    t = props[["game_id", "player_id"]].assign(stat=props.market.map(Q.STAT_OF).to_numpy()).merge(
        f.loc[f.is_prop, cols], on=["game_id", "player_id", "stat"], how="left")
    out = props.copy()
    mu = t[f"mu_{kind}_{variant}"].to_numpy(float)
    if kind == "consensus":
        mu = np.where(np.isfinite(t.mu_P.to_numpy(float)), np.nan, mu)
    out["has_number"] = np.isfinite(mu)
    out["mu"] = mu
    out["alpha"] = [fits.alpha.get((kind, variant, Q.STAT_OF[m], int(se)), np.nan)
                    for m, se in zip(out.market, out.season)]
    out["map_key"] = [f"{Q.STAT_OF[m]}|{int(se)}" if Q.STAT_OF[m] in Q.MAP_STATS else ""
                      for m, se in zip(out.market, out.season)]
    return out


# ── the groups of cells (doc sections 5 and 8) ──────────────────────────────

MEANING = {"pinnacle": "Pinnacle's full-game number x his first-quarter minutes share, against the book's price",
           "consensus": "the soft books' median full-game number (Pinnacle absent) x his first-quarter minutes share"}


def build_groups(co: pd.DataFrame, kp: dict, maps: dict) -> list:
    """kp: (kind, variant) -> kind_props frame; maps: (kind, variant) -> line maps. The 36 registered cells'
    groups, then the controls."""
    groups = []
    for kind in KINDS:
        for variant in VARIANTS:
            pk = kp[(kind, variant)]
            mp = maps.get((kind, variant)) or {}
            off = Q.long_offers(co[co.prop_id.isin(pk.loc[pk.has_number, "prop_id"])], pk)
            for m in Q1_MARKETS:
                o = off[off.prop_market == m]
                cand, neu = Q.priced(o, mp), Q.neutral_of(o)
                pr = Q.Pricer(cand, mp) if variant == "model" else None
                for side in ("over", "under"):
                    c = cand[cand.side == side].reset_index(drop=True)
                    if variant == "model":
                        groups.append(Q.Group(FAMILIES[kind], m, side, "best", "two_sided", EV_CUTS, c, neu, pr,
                                              MEANING[kind]))
                        groups.append(Q.Group(CTL_BLIND[kind], m, side, "best", "two_sided", (-np.inf,),
                                              neu[neu.side == side].reset_index(drop=True), neu, None,
                                              "control: every proposition of this kind, this side, no model",
                                              bands=False))
                    else:
                        groups.append(Q.Group(CTL_LEAGUE[kind], m, side, "best", "two_sided", EV_CUTS, c, neu, None,
                                              "control: the full-game number x one factor, no player share",
                                              bands=False))
    return groups


def registered(groups: list) -> list:
    cells = [(g.family, g.market, g.side, c) for g in groups if g.family in FAMILIES.values() for c in g.cuts]
    assert len(cells) == EXPECTED_CELLS, len(cells)
    return cells


# ── real data ───────────────────────────────────────────────────────────────

@dataclass
class Prep:
    props: pd.DataFrame
    co: pd.DataFrame
    fit: pd.DataFrame
    fits: Fits
    kp: dict
    notes: dict


def prepare(cache: Path = H.CACHE, qwork: Path | None = None, work: Path | None = None) -> Prep:
    """Every frame the cells read. Reads earlier seasons' first-quarter results for the walk-forward fits and the
    first-quarter stats for settlement; joins no stat to a bet."""
    t0 = time.time()
    qwork = Q.work_dir() if qwork is None else Path(qwork)
    work = work_dir() if work is None else Path(work)
    data = Q.load_data(cache, qwork)
    reg = nb.regular_game_ids(data["games"], data["schedule"])
    rg = data["games"][data["games"].game_id.isin(reg)]
    settled = Q.settle(data["plays"], data["pbp_games"], data["stints"], data["id_map"], data["log"], rg,
                       data["periods"])
    sec, tm, _ = Q.court_seconds(data["stints"])
    del data["plays"]
    say(f"settlement built at {time.time() - t0:.0f}s")
    q = Q.matched_quotes(cache, qwork)
    co, _one, qnotes, _pre = Q.refuse_rows(q, settled)
    co, _one, props = Q.with_props(co, _one, settled)
    say(f"first-quarter quotes ready at {time.time() - t0:.0f}s: {len(props)} propositions")
    fq = full_quotes(cache, work)
    qm = quote_means(fq, data["log"])
    anc = anchors(qm)
    say(f"anchors at {time.time() - t0:.0f}s: {len(anc)} (game, player, market, fetch) keys")
    # the fit table: every regular-season player-game from 2023-24 on with first-quarter court time, per stat
    g = rg.set_index("game_id")
    s1 = settled.q1[(settled.q1.q1_sec > 0) & settled.q1.game_id.isin(rg.game_id)].copy()
    s1["season"] = s1.game_id.map(g.season).astype(int)
    s1 = s1[s1.season.isin(FIT_SEASONS)]
    s1["date"] = pd.to_datetime(s1.game_id.map(g.game_date))
    fit = pd.concat([s1[["game_id", "player_id", "season", "date"]].assign(stat=s, y=s1[s].to_numpy(float),
                                                                           ok_settled=s1.game_id.isin(
                                                                               settled.valid[m]).to_numpy())
                     for m, s in Q.STAT_OF.items()], ignore_index=True)
    pg = Q.player_games(data["log"], rg, sec, tm)
    fit = shares(fit, share_history(pg))
    fit = fit_anchors(fit, anc, props)
    fit, fits = means(fit)
    kp = {(k, v): kind_props(props, fit, fits, k, v) for k in KINDS for v in VARIANTS}
    notes = {"seconds": round(time.time() - t0, 1), "quotes": qnotes,
             "full_quotes": int(len(fq)), "anchor_keys": int(len(anc)),
             "fit_rows": int(len(fit))}
    return Prep(props, co, fit, fits, kp, notes)


# ── counts before grading ───────────────────────────────────────────────────

def counts(prep: Prep) -> dict:
    """Counts only: propositions with a number by kind, market and season; the fits; the offers each cell would
    take. Nothing is graded and no proposition's result is read."""
    out = {}
    for k in KINDS:
        pk = prep.kp[(k, "model")]
        out[f"propositions_{k}"] = pk.groupby(["season", "market"]).has_number.agg(["size", "sum"]).reset_index().to_dict("records")
    f = prep.fit
    out["fit_rows_with_share"] = int(np.isfinite(f.share).sum())
    out["fit_rows_by_season_kind"] = {
        f"{int(s)}": {"rows": int((f.season == s).sum()),
                      "pinnacle_anchor": int(((f.season == s) & f.mu_P.notna()).sum()),
                      "consensus_anchor": int(((f.season == s) & f.mu_C.notna()).sum())}
        for s in sorted(f.season.unique())}
    out["share_quantiles"] = np.nanquantile(f.share.to_numpy(float), [0.05, 0.25, 0.5, 0.75, 0.95]).round(3).tolist()
    out["factor"] = {"|".join(map(str, k)): round(v, 4) for k, v in prep.fits.factor.items()}
    out["alpha"] = {"|".join(map(str, k)): round(v, 4) for k, v in prep.fits.alpha.items()}
    groups = build_groups(prep.co, prep.kp, prep.fits.maps)
    registered(groups)
    rows = []
    for gr in groups:
        if gr.family not in FAMILIES.values():
            continue
        for cut in gr.cuts:
            b = H.choose(gr.cand, cut, sides=[gr.side])
            px = b.price.to_numpy(float) if len(b) else np.array([np.nan])
            rows.append({"family": gr.family, "market": gr.market, "side": gr.side, "cut": cut, "bets": int(len(b)),
                         "by_season": b.season.value_counts().sort_index().to_dict() if len(b) else {},
                         "price_min": float(np.nanmin(px)), "price_median": float(np.nanmedian(px)),
                         "price_max": float(np.nanmax(px))})
    out["cells"] = rows
    return out


# ── synthetic plumbing check ────────────────────────────────────────────────

def synthetic_checks(n_placebo: int = 3) -> dict:
    """The props search's invented world, fed through this lab's own group builder for both kinds and both
    variants, then H.run_cells: raises on a fault."""
    world = Q.synthetic_world()
    p = world["props"]
    kp = {(k, v): p.assign(map_key="") for k in KINDS for v in VARIANTS}
    groups = build_groups(world["co"], kp, {})
    registered(groups)
    games, times = Q.games_table(p, p.stat.to_numpy()), Q.times_table(p)
    rows = []
    for gr in groups:
        assert len(gr.cand) > 0, f"the synthetic world holds no offers for {gr.name}"
        if gr.placebo is not None:
            Q.assert_identity(gr)
        rows += Q.emit(gr, games, times, seeds=tuple(range(1, n_placebo + 1)) if gr.placebo is not None else ())
        if gr.placebo is not None:
            gr.placebo.clear()
    t = pd.DataFrame(rows)
    reg = t[t.family.isin(list(FAMILIES.values()))]
    assert len(reg) == EXPECTED_CELLS and (reg.pool_n > 0).all() and reg.band0_n.notna().all()
    return {"synthetic_checks": "pass", "rows": int(len(t))}


# ── full ────────────────────────────────────────────────────────────────────

def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(Q.GO_ENV) != "1":
        why.append(f"{Q.GO_ENV}=1 is not set")
    for env in (Q.RESULTS_ENV, Q.BETS_ENV):
        if not os.environ.get(env):
            why.append(f"{env} is not set")
    for fname in ("q1_props", "nba_pbp_slim", "nba_pbp_games"):
        if not (Q.work_dir() / "pulled" / f"{fname}.parquet").exists():
            why.append(f"{Q.work_dir() / 'pulled' / fname}.parquet does not exist")
    import config
    if tuple(config.BEST_LINE_BOOKMAKERS) != Q.REGISTERED_BOOKS or tuple(H.BETTABLE) != Q.REGISTERED_BOOKS:
        why.append("the deciding books are not the registered ones: an override changed BEST_LINE_BOOKMAKERS")
    if float(config.DEFAULT_MIN_ODDS) != Q.REGISTERED_FLOOR or float(H.PRICE_FLOOR) != Q.REGISTERED_FLOOR:
        why.append("the price floor is not the registered -200")
    return why


def full(cache: Path = H.CACHE) -> None:
    why = refuse_full(cache)
    if why:
        for x in why:
            print("REFUSED:", x)
        raise SystemExit(2)
    out = Path(os.environ[Q.RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    saved = os.environ.pop(Q.BETS_ENV)
    synthetic_checks()
    os.environ[Q.BETS_ENV] = saved
    say("synthetic checks pass")
    prep = prepare(cache)
    prep.props.drop(columns="T").to_parquet(out / "props.parquet")
    prep.fit.drop(columns=["date"]).to_parquet(out / "fit.parquet")
    (out / "fits.json").write_text(json.dumps({
        "factor": {"|".join(map(str, k)): v for k, v in prep.fits.factor.items()},
        "alpha": {"|".join(map(str, k)): v for k, v in prep.fits.alpha.items()},
        "notes": prep.notes}, indent=1, default=str), encoding="utf-8")
    live = Q.live_keys()
    groups = build_groups(prep.co, prep.kp, prep.fits.maps)
    registered(groups)
    games, times = Q.games_table(prep.props, prep.props.stat.to_numpy()), Q.times_table(prep.props)
    for i, gr in enumerate(groups, start=1):
        if (out / f"cells_{gr.name}.parquet").exists():
            say(f"group {i}/{len(groups)} {gr.name}: already written, skipped")
            continue
        H._BET_FILES[0] = 1000 * i
        t1 = time.time()
        rows = Q.emit(gr, games, times, seeds=Q.PLACEBO_SEEDS if gr.placebo is not None else ())
        Q.write_group(gr, rows, Q.beside_rows(gr, games, prep.props, live), out)
        if gr.placebo is not None and gr.side == "under":
            gr.placebo.clear()
        say(f"group {i}/{len(groups)} {gr.name}: {len(rows)} cells in {time.time() - t1:.0f}s; "
            f"{(time.time() - t0) / 60:.0f} minutes so far")
    say(f"cells written to {out}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--counts", action="store_true", help="synthetic checks, then counts on the real data, no grade")
    g.add_argument("--full", action="store_true", help="grade every cell (needs the three variables)")
    g.add_argument("--verdict", type=Path, help="the verdict with the strict season bar")
    a = ap.parse_args(argv)
    if a.counts:
        say(json.dumps(synthetic_checks()))
        c = counts(prepare(H.CACHE))
        print(json.dumps(c, indent=1, default=str))
    elif a.full:
        full(H.CACHE)
    else:
        v = Q.strict_verdict(V.load_cells(a.verdict))
        v.drop(columns=["placebo_rois"], errors="ignore").to_parquet(a.verdict / "verdict_q1anchor.parquet")
        print(f"{len(v)} registered cells; {int(v.house5_passes.sum())} pass the house bars as coded; "
              f"{int(v.passes_strict.sum())} pass with both seasons positive (this search's reading)")
        print(v[["family", "market", "side", "cut", "pool_n", "pool_roi", "pool_ci95_lo", "house5_failed",
                 "h3_both_seasons", "passes_strict"]].to_string(index=False))


if __name__ == "__main__":
    main()
