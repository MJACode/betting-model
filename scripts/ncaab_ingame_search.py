"""NCAAB in-play search: the game-state model graded on every decision moment.

Reads Supabase only (ncaab_pbp, games, ncaab_events, odds, ncaab_inplay_fetches)
and decides through models/ncaab_live_ig, the code the live loop runs.

STEPS
  states   every 30 s game state of each season's games, with the pre-game
           prior and the final score (the training set)
  fit      walk-forward: season S's margin and total models fit on seasons < S;
           calibration on S printed (mean error, sd ratio, coverage by f)
  grade    the in-play quotes of the purchase (source
           ncaab_inplay_history.SOURCE), each joined to its fetch's served
           time; the decision per game and rule at the FIRST eligible fetch;
           units at the taken price, one unit to win, risk capped at 3; the
           house standard of docs/nba_models_2026.md 9.1 per cell.

Caches (a cache of Supabase, regenerable: NCAAB_RESEARCH_CACHE, default the
temp dir) hold the reads so a re-run does not re-read 14M plays.

    PYTHONPATH=. python -m scripts.ncaab_ingame_search --fit
    PYTHONPATH=. python -m scripts.ncaab_ingame_search --grade --step 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from models import ncaab_live_ig as M  # noqa: E402

CACHE = Path(os.environ.get("NCAAB_RESEARCH_CACHE")
             or Path(tempfile.gettempdir()) / "ncaab_ingame_cache")
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
GRADED = (2022, 2023, 2024, 2025, 2026)
CUTS = (0.02, 0.05, 0.08)
INPLAY_SOURCE = "odds_api_ncaab_inplay_history"
BOOKS = tuple(config.BEST_LINE_BOOKMAKERS)
N_BOOT = 4000
N_PLACEBO = 200


def _conn():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parents[2] / ".env") if (ROOT.parents[2] / ".env").exists() else None
    from data.db import get_connection
    c = get_connection()
    c.execute("SET statement_timeout = '900s'")
    return c


def _read(conn, sql: str, params=()) -> pd.DataFrame:
    cur = conn._conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    cur.close()
    conn.commit()
    return df


def _cached(name: str, build):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    df = build()
    df.to_parquet(p, index=False)
    return df


# ── reads ────────────────────────────────────────────────────────────────────

def load_plays(conn, season: int) -> pd.DataFrame:
    def build():
        df = _read(conn, """
            SELECT game_id, season, play_no, period, clock_s, game_s, wallclock, type_text,
                   home_score AS h_pts, away_score AS a_pts, team_side
              FROM ncaab_pbp
             WHERE season = %s AND type_text IS DISTINCT FROM 'Substitution'
        """, (season,))
        for c in ("period", "play_no", "h_pts", "a_pts"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        for c in ("clock_s", "game_s"):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
        df["wallclock"] = pd.to_datetime(df["wallclock"], utc=True)
        return df
    return _cached(f"plays_{season}", build)


def load_games(conn) -> pd.DataFrame:
    def build():
        df = _read(conn, """
            SELECT g.game_id, g.season, g.commence_time, g.home_score, g.away_score,
                   e.season_type, e.espn_event_id, pg.score_matches, pg.n_plays
              FROM games g
              JOIN ncaab_events e USING (game_id)
              LEFT JOIN ncaab_pbp_games pg ON pg.espn_game_id = e.espn_event_id
             WHERE g.sport = 'NCAAB' AND g.home_score IS NOT NULL
        """)
        df["tip"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
        df["home_score"] = pd.to_numeric(df["home_score"]).astype(float)
        df["away_score"] = pd.to_numeric(df["away_score"]).astype(float)
        return df.drop(columns="commence_time")
    return _cached("games", build)


def load_priors(conn, season: int) -> pd.DataFrame:
    """(game_id, mu_pre, T_pre, prior_src): Pinnacle's last pre-tip spread and
    total, else the median of the deciding books' last pre-tip quotes."""
    def build():
        q = _read(conn, M.PRIOR_CLOSE_SQL.format(where="g.season = %s"), (season,))
        return M.priors_from_closes(q, BOOKS)
    return _cached(f"priors_{season}", build)


# ── states ───────────────────────────────────────────────────────────────────

def clean_games(plays: pd.DataFrame, games: pd.DataFrame) -> set[str]:
    """Games fit for training and grading: the play-by-play's last score is the
    final, and no 45-minute wallclock gap (a feed restart)."""
    ok = games[games["score_matches"].fillna(False).astype(bool)]["game_id"]
    p = plays[plays["game_id"].isin(ok)].sort_values(["game_id", "play_no"])
    gap = p.groupby("game_id")["wallclock"].diff().dt.total_seconds()
    jumped = set(p.loc[gap > 45 * 60, "game_id"])
    return set(ok) - jumped


def grid_states(plays: pd.DataFrame, step: int = M.GRID_STEP_S) -> pd.DataFrame:
    """Each game's state every `step` s of regulation game time (TRAIN_SECS)."""
    s = plays.dropna(subset=["game_s"]).sort_values(["game_s", "play_no"], kind="stable")
    g = np.arange(M.TRAIN_SECS[0], M.TRAIN_SECS[1] + 1, step, dtype=float)
    ids = s["game_id"].unique()
    left = pd.DataFrame({"game_id": np.repeat(ids, len(g)), "g": np.tile(g, len(ids))})
    left = left.sort_values("g", kind="stable")
    x = pd.merge_asof(left, s, left_on="g", right_on="game_s", by="game_id", direction="backward")
    x = x.dropna(subset=["period"])
    return x[x["period"] <= 2].reset_index(drop=True)


def training_states(conn, season: int, games: pd.DataFrame) -> pd.DataFrame:
    def build():
        plays = M.with_team_fouls(load_plays(conn, season))
        keep = clean_games(plays, games)
        plays = plays[plays["game_id"].isin(keep)]
        st = M.state_columns(grid_states(plays))
        pri = load_priors(conn, season)
        gm = games[["game_id", "home_score", "away_score", "season_type"]]
        st = st.merge(pri, on="game_id").merge(gm, on="game_id")
        st["final_margin"] = st["home_score"] - st["away_score"]
        st["final_total"] = st["home_score"] + st["away_score"]
        st["season"] = season
        cols = ["game_id", "season", "season_type", "g", "period", "clock_s", "game_s",
                "type_text", "h_pts", "a_pts", "h_tf", "a_tf", "secs_left", "f", "half_left",
                "m", "t", "is_break", "mu_pre", "T_pre", "prior_src", "final_margin",
                "final_total"]
        return st[cols]
    return _cached(f"states_{season}", build)


# ── fit and calibration ──────────────────────────────────────────────────────

def fit_models(states: dict[int, pd.DataFrame], S: int) -> dict[str, M.StateModel]:
    train = pd.concat([M.features(states[s]) for s in states if s < S], ignore_index=True)
    return {t: M.StateModel(t).fit(train, S) for t in ("margin", "total")}


def calibration(models: dict, st: pd.DataFrame) -> pd.DataFrame:
    x = M.features(st)
    rows = []
    for t, mdl in models.items():
        mean, sd = mdl.predict(x)
        y = x["final_margin" if t == "margin" else "final_total"].to_numpy(float)
        z = (y - mean) / sd
        fb = pd.cut(x["f"], [0, 0.1, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
        d = pd.DataFrame({"fb": fb, "err": y - mean, "z": z})
        for b, g in d.groupby("fb", observed=True):
            rows.append({"target": t, "f_bucket": str(b), "n": len(g),
                         "mean_err": round(g["err"].mean(), 3),
                         "sd_ratio": round(g["z"].std(), 3),
                         "cover_68": round((g["z"].abs() <= 1).mean(), 3)})
    return pd.DataFrame(rows)


def run_fit(conn) -> dict:
    games = load_games(conn)
    states = {s: training_states(conn, s, games) for s in SEASONS}
    out = {}
    for S in GRADED:
        mdl = fit_models(states, S)
        cal = calibration(mdl, states[S])
        print(f"\n== season {S}: margin beta {np.round(mdl['margin'].beta, 3)} "
              f"s1 {mdl['margin'].s1:.1f} s0 {mdl['margin'].s0:.2f} | total beta "
              f"{np.round(mdl['total'].beta, 3)} s1 {mdl['total'].s1:.1f} s0 {mdl['total'].s0:.2f}")
        print(cal.to_string(index=False))
        out[S] = {k: v.to_dict() for k, v in mdl.items()}
    return out


# ── quotes, decisions, grade ─────────────────────────────────────────────────

def load_fetches(conn) -> pd.DataFrame:
    """Every bought snapshot: what was asked for, what the feed served, and the
    commit time its rows carry (odds.created_at defaults to the transaction's
    now(), the same instant as the ledger row's pulled_at)."""
    df = _read(conn, "SELECT requested_at, snapshot_ts, pulled_at FROM ncaab_inplay_fetches")
    df["requested_at"] = pd.to_datetime(df["requested_at"], utc=True)
    df["served"] = pd.to_datetime(df["snapshot_ts"], utc=True)
    df["pulled_at"] = pd.to_datetime(df["pulled_at"], utc=True)
    return df[["requested_at", "served", "pulled_at"]].sort_values("served").reset_index(drop=True)


def load_quotes(conn, season: int) -> pd.DataFrame:
    def build():
        q = _read(conn, """
            SELECT o.game_id, o.market, o.bookmaker AS book, o.snapshot_at, o.created_at,
                   o.home_price, o.away_price, o.spread_home, o.total_line, o.over_price,
                   o.under_price
              FROM odds o JOIN games g ON g.game_id = o.game_id
             WHERE o.sport = 'NCAAB' AND g.season = %s AND o.source = %s
               AND o.snapshot_type = 'in_play'          -- idx_odds_source_inplay
        """, (season, INPLAY_SOURCE))
        q["stamp"] = pd.to_datetime(q["snapshot_at"], utc=True)
        q["stored_at"] = pd.to_datetime(q["created_at"], utc=True)
        for c in ("home_price", "away_price", "spread_home", "total_line", "over_price",
                  "under_price"):
            q[c] = pd.to_numeric(q[c], errors="coerce").astype(float)
        return q.drop(columns=["snapshot_at", "created_at"])
    return _cached(f"quotes2_{season}", build)


def assign_fetch(q: pd.DataFrame, fetches: pd.DataFrame) -> pd.DataFrame:
    """Each quote to the snapshot that SERVED it: its row was written in that
    snapshot's transaction (stored_at == pulled_at). `fetches` is the cadence's
    set, so a quote another cadence's snapshot served is not in it. An unchanged
    quote served by two snapshots was stored by each and is in each."""
    f = fetches.rename(columns={"served": "fetch_at"})
    x = q.merge(f[["pulled_at", "fetch_at", "requested_at"]], left_on="stored_at",
                right_on="pulled_at", how="inner")
    return x.drop(columns=["pulled_at"]).reset_index(drop=True)


# The decision path lives in models/ncaab_live_ig, the code the live loop runs.
state_at = M.state_at
quote_states = M.quote_states
price = M.price_offers


def priced_offers(qs: pd.DataFrame, models: dict, games_prior: pd.DataFrame) -> pd.DataFrame:
    """Every offer of every eligible decision quote, priced by the model
    (M.eligible_quotes, then M.decision_offers: the first eligible fetch per
    game and rule)."""
    return M.decision_offers(M.eligible_quotes(qs, games_prior, BOOKS), models)


def best(off: pd.DataFrame) -> pd.DataFrame:
    """The decision per (game, rule): its best-EV allowed offer (cut applied later)."""
    return M.choose(off, -np.inf, BOOKS)


def grade(d: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    b = d.merge(games[["game_id", "home_score", "away_score", "tip"]], on="game_id")
    b["result"] = M.settle(b["market"], b["side"], b["line"], b["home_score"], b["away_score"])
    b["units"], b["risk"] = M.units(b["result"], b["price"])
    b["day"] = (b["tip"] - pd.Timedelta(hours=5)).dt.date
    return b


def roi(b: pd.DataFrame) -> float:
    r = b["risk"].sum()
    return float(b["units"].sum() / r) if r else float("nan")


def boot_ci(b: pd.DataFrame, seed: int = 7, n: int = N_BOOT) -> tuple[float, float]:
    """Whole-day bootstrap 95% interval of the return (units / risk)."""
    if not len(b):
        return (np.nan, np.nan)
    by = b.groupby("day")[["units", "risk"]].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(by), size=(n, len(by)))
    u, r = by["units"].to_numpy()[idx].sum(1), by["risk"].to_numpy()[idx].sum(1)
    return float(np.percentile(u / r, 2.5)), float(np.percentile(u / r, 97.5))


def blind(off: pd.DataFrame, side: str, games: pd.DataFrame) -> float:
    """Every decision's best-priced offer on one real side, graded (bar 4)."""
    o = off[(off["side"] == side) & off["book"].isin(BOOKS) & (off["price"] >= M.PRICE_FLOOR)]
    o = o.sort_values("price", ascending=False).drop_duplicates(["game_id", "rule"])
    return roi(grade(o, games)) if len(o) else float("nan")


def placebo_all(off: pd.DataFrame, rule: str, cuts, games: pd.DataFrame,
                runs: int = N_PLACEBO) -> dict[float, np.ndarray]:
    """{cut: the rule's return in each of `runs` shuffles} (bar 6). Each run
    gives every decision game another game's model (mean, sd), drawn within
    the same fetch, re-prices every offer and takes the best-EV offer per game
    exactly as best() does (EV rounded to 12 decimals, ties to the earlier
    book). Seeds 1..runs. Every offer is settled once, outside the runs."""
    o = off[(off["rule"] == rule) & off["book"].isin(BOOKS) & (off["price"] >= M.PRICE_FLOOR)]
    o = o.merge(games[["game_id", "home_score", "away_score"]], on="game_id").reset_index(drop=True)
    res = M.settle(o["market"], o["side"], o["line"], o["home_score"], o["away_score"])
    units, risk = M.units(res, o["price"])
    gcode, gids = pd.factorize(o["game_id"])
    first = pd.Series(np.arange(len(o))).groupby(gcode).first().to_numpy()
    fcode = pd.factorize(o["fetch_at"].to_numpy()[first])[0]
    is_tot = (o["market"] == "totals").to_numpy()
    mu_g = np.where(is_tot[first], o["mu_t"].to_numpy()[first], o["mu_m"].to_numpy()[first])
    sd_g = np.where(is_tot[first], o["sd_t"].to_numpy()[first], o["sd_m"].to_numpy()[first])
    rank = o["book"].map({b: i for i, b in enumerate(BOOKS)}).to_numpy()
    market, side, line, price_ = o["market"].to_numpy(), o["side"].to_numpy(), o["line"].to_numpy(),         o["price"].to_numpy(float)
    n = len(gids)
    idx_a = np.lexsort((np.arange(n), fcode))
    out = {c: [] for c in cuts}
    for seed in range(1, runs + 1):
        rng = np.random.default_rng(seed)
        idx_b = np.lexsort((rng.random(n), fcode))
        donor = np.empty(n, dtype=int)
        donor[idx_a] = idx_b
        mu, sd = mu_g[donor][gcode], sd_g[donor][gcode]
        pw, pp = M.side_probs(market, side, line, mu, sd)
        ev = np.round(M.ev_of(price_, pw, pp), 12)
        order = np.lexsort((rank, -ev, gcode))
        g_sorted = gcode[order]
        pick = order[np.r_[True, g_sorted[1:] != g_sorted[:-1]]]
        for c in cuts:
            m = pick[ev[pick] >= c]
            r = risk[m].sum()
            out[c].append(float(units[m].sum() / r) if r else 0.0)
    return {c: np.asarray(v) for c, v in out.items()}


def pin_split(b: pd.DataFrame) -> dict:
    """Where Pinnacle quoted the same game and market in the same fetch: the
    bet's number against Pinnacle's, in the bet's favour (points; no-vig
    probability for a moneyline), and whether Pinnacle sits nearer the model or
    the soft book. ROI concentrated where the soft book is well off Pinnacle in
    the bet's favour is a stale soft book, which a live bet would not get."""
    if not len(b) or "pin_num" not in b:
        return {}
    sp, to = b["market"] == "spreads", b["market"] == "totals"
    a_side = b["side"].isin(["home", "over"])
    p_soft = 1.0 / M.dec(b["price"])
    p_pin_side = np.where(b["side"] == "home", b["pin_num"], 1.0 - b["pin_num"])
    fav = np.where(sp, np.where(a_side, b["line"] - b["pin_num"], b["pin_num"] - b["line"]),
                   np.where(to, np.where(a_side, b["pin_num"] - b["line"], b["line"] - b["pin_num"]),
                            p_pin_side - p_soft))
    tol = np.where(sp | to, 1.0, 0.03)
    has = b["pin_num"].notna()
    bucket = np.select([~has, np.abs(fav) <= tol, fav > tol], ["no pinnacle", "within", "soft better"],
                       "soft worse")
    model = np.where(sp, -b["mu_m"], np.where(to, b["mu_t"], np.nan))
    nearer = np.where(sp | to, np.where(np.abs(b["pin_num"] - model) < np.abs(b["line"] - model),
                                        "pin nearer model", "soft nearer model"), "")
    out = {}
    for k in ("no pinnacle", "within", "soft better", "soft worse"):
        g = b[bucket == k]
        if len(g):
            row = {"n": len(g), "roi": round(roi(g), 4)}
            if k == "soft better":
                nn = pd.Series(nearer[bucket == k]).value_counts().to_dict()
                row["pin_nearer_model"] = int(nn.get("pin nearer model", 0))
            out[k] = row
    return out


def cell_verdict(off: pd.DataFrame, dec: pd.DataFrame, rule: str, cut: float,
                 games: pd.DataFrame, pl: np.ndarray | None = None) -> dict:
    """The house standard (docs/nba_models_2026.md 9.1) on one cell."""
    d = dec[dec["rule"] == rule]
    b = grade(d[d["ev"] >= cut], games)
    out = {"rule": rule, "cut": cut, "bets": len(b)}
    if not len(b):
        return out
    lo, hi = boot_ci(b)
    by_s = {int(s): (len(g), roi(g)) for s, g in b.groupby("season")}
    judged = [v for v in by_s.values() if v[0] >= 30]
    dom = b["side"].value_counts().idxmax()
    bl = blind(off[off["rule"] == rule], dom, games)
    edges = [0.0, *CUTS, np.inf]
    i = edges.index(cut)
    bands = {}
    for a, z in zip(edges[i - 1:-1], edges[i:]):
        bb = grade(d[(d["ev"] >= a) & (d["ev"] < z)], games)
        bands[f"{a:.2f}-{z:.2f}"] = (len(bb), roi(bb) if len(bb) else float("nan"))
    bands_ok = all(r > 0 for n, r in bands.values() if n >= 30) and roi(b) > 0
    p95 = float(np.nanpercentile(pl, 95)) if pl is not None else float("nan")
    half = b["tip"] <= b["tip"].quantile(0.5)
    dk = b[b["book"] == "draftkings"]
    out.update({
        "units": round(float(b["units"].sum()), 1), "roi": round(roi(b), 4),
        "ci": (round(lo, 4), round(hi, 4)),
        "seasons": {s: (n, round(r, 3)) for s, (n, r) in by_s.items()},
        "early": round(roi(b[half]), 4), "late": round(roi(b[~half]), 4),
        "dominant": dom, "blind": round(bl, 4),
        "bands": {k: (n, round(r, 3)) for k, (n, r) in bands.items()},
        "placebo_p95": round(p95, 4),
        "dk_only": (len(dk), round(roi(dk), 4) if len(dk) else None),
        "prices": (float(b["price"].min()), float(b["price"].median()), float(b["price"].max())),
        "pinnacle": pin_split(b),
        "bar1_n": len(b) >= 200, "bar2_ci": lo > 0,
        "bar3_seasons": len(judged) >= 2 and sum(r <= 0 for _, r in judged) <= 1,
        "bar4_blind": roi(b) > bl, "bar5_bands": bands_ok,
        "bar6_placebo": (roi(b) > p95) if pl is not None else None,
    })
    out["passes"] = all(bool(out[k]) for k in ("bar1_n", "bar2_ci", "bar3_seasons",
                                               "bar4_blind", "bar5_bands", "bar6_placebo"))
    return out


def season_offers(conn, S: int, states: dict, games: pd.DataFrame,
                  fetches: pd.DataFrame) -> pd.DataFrame | None:
    models = fit_models(states, S)
    plays = M.with_team_fouls(load_plays(conn, S))
    keep = clean_games(plays, games)
    q = load_quotes(conn, S)
    q = q[q["game_id"].isin(keep)]
    if not len(q):
        print(f"season {S}: no in-play quotes stored")
        return None
    aq = assign_fetch(q, fetches)
    qs = quote_states(aq, plays[plays["game_id"].isin(keep)])
    off = priced_offers(qs, models, load_priors(conn, S))
    off["season"] = S
    pin = qs[qs["book"] == "pinnacle"]
    pin = pin.assign(pin_num=np.where(pin["market"] == "spreads", pin["spread_home"],
                     np.where(pin["market"] == "totals", pin["total_line"],
                              M.novig_home(pin["home_price"].fillna(-110), pin["away_price"].fillna(-110)))),
                     pin_age=(pin["fetch_at"] - pin["stamp"]).dt.total_seconds(),
                     pin_fresh=pin["pts_since"] == 0)
    off = off.merge(pin[["game_id", "market", "fetch_at", "pin_num", "pin_age", "pin_fresh"]]
                    .drop_duplicates(["game_id", "market", "fetch_at"]),
                    on=["game_id", "market", "fetch_at"], how="left")
    print(f"season {S}: {len(q):,} quotes, {len(aq):,} served at this cadence, "
          f"{off['game_id'].nunique():,} games decided")
    return off


def run_grade(conn, step: int, n_placebo: int = N_PLACEBO, seasons=GRADED) -> pd.DataFrame:
    games = load_games(conn)
    states = {s: training_states(conn, s, games) for s in SEASONS}
    fetches = load_fetches(conn)
    if step == 60:
        fetches = fetches[fetches["requested_at"].dt.minute == 0]
    offs = [o for S in seasons if (o := season_offers(conn, S, states, games, fetches)) is not None]
    off = pd.concat(offs, ignore_index=True)
    dec = best(off)
    off.to_parquet(CACHE / f"offers_step{step}.parquet", index=False)
    rows = []
    for mk in M.MARKETS:
        for ph in M.PHASES:
            rule = f"{mk}_{ph}"
            pls = placebo_all(off, rule, CUTS, games, n_placebo) if n_placebo else {}
            rows += [cell_verdict(off, dec, rule, c, games, pls.get(c)) for c in CUTS]
            print(f"{rule} judged", flush=True)
    return pd.DataFrame(rows)


# ── the shipped selection: the best few a night (mike, 2026-11-07: "3-5 best per night") ─

N_QUANTILES = 1001


def night_table(dec: pd.DataFrame, slates: pd.DataFrame) -> tuple[np.ndarray, float]:
    """(EV at q = 0, 1/1000, ..., 1, decisions per slate game) of `dec`, the
    live rules' decisions of the seasons an artifact is built from."""
    q = np.quantile(dec["ev"].to_numpy(float), np.linspace(0.0, 1.0, N_QUANTILES))
    nights = dec[["season", "night"]].drop_duplicates().merge(slates, on=["season", "night"])
    per_game = len(dec) / nights["slate_games"].sum()
    return q, float(per_game)


def live_decisions(off: pd.DataFrame, games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(every decision of the live rules, graded, with its night; the slates)."""
    o = off[off["rule"].isin(list(M.RULE_BY_KEY))]
    d = grade(best(o), games)
    d["night"] = d["day"]
    slates = games.assign(night=(games["tip"] - pd.Timedelta(hours=5)).dt.date) \
        .groupby(["season", "night"]).size().rename("slate_games").reset_index()
    return d.merge(slates, on=["season", "night"], how="left"), slates


def select_nights(dec: pd.DataFrame, arts: dict) -> pd.DataFrame:
    """The bets the loop makes: per night, decisions in decision order (fetch,
    then the higher EV first), each at or above M.night_cut for its rule on
    that night's slate, the first M.NIGHT_CAP of them. `arts`: {season:
    M.Artifact} built from earlier seasons only."""
    out = []
    for (season, night), x in dec.groupby(["season", "night"]):
        art = arts.get(int(season))
        if art is None:
            continue
        n = int(x["slate_games"].iloc[0])
        cut = x["rule"].map({k: M.night_cut(art, n, r) for k, r in M.RULE_BY_KEY.items()}).to_numpy(float)
        keep = x["ev"].to_numpy(float) >= cut
        out.append(x[keep].assign(night_cut=cut[keep])
                   .sort_values(["fetch_at", "ev"], ascending=[True, False]).head(M.NIGHT_CAP))
    return pd.concat(out) if out else dec.iloc[:0]


def season_arts(dec: pd.DataFrame, slates: pd.DataFrame, models_by_season: dict | None = None) -> dict:
    """{S: an artifact whose night table is built from the decisions of seasons < S}."""
    arts = {}
    for S_ in sorted(dec["season"].unique()):
        prior = dec[dec["season"] < S_]
        if not len(prior):
            continue
        q, per_game = night_table(prior, slates)
        m = (models_by_season or {}).get(int(S_))
        arts[int(S_)] = M.Artifact(m["margin"] if m else None, m["total"] if m else None, q, per_game)
    return arts


def night_placebo(off: pd.DataFrame, games: pd.DataFrame, arts: dict, runs: int) -> np.ndarray:
    """The selection's return with each decision game given another game's
    model (mean, sd) drawn within its fetch, seeds 1..runs."""
    o = off[off["rule"].isin(list(M.RULE_BY_KEY)) & off["book"].isin(BOOKS)
            & (off["price"] >= M.PRICE_FLOOR)].reset_index(drop=True)
    key = pd.factorize(o["game_id"])[0]
    first = pd.Series(np.arange(len(o))).groupby(key).first().to_numpy()
    fcode = pd.factorize(o["fetch_at"].to_numpy()[first])[0]
    cols = ("mu_m", "sd_m", "mu_t", "sd_t")
    per_game = {c: o[c].to_numpy()[first] for c in cols}
    n = len(first)
    idx_a = np.lexsort((np.arange(n), fcode))
    out = []
    for seed in range(1, runs + 1):
        rng = np.random.default_rng(seed)
        idx_b = np.lexsort((rng.random(n), fcode))
        donor = np.empty(n, dtype=int)
        donor[idx_a] = idx_b
        sh = o.assign(**{c: per_game[c][donor][key] for c in cols})
        d, _sl = live_decisions(price(sh), games)
        b = select_nights(d, arts)
        out.append(roi(b) if len(b) else 0.0)
    return np.asarray(out)


def run_best_per_night(conn, n_placebo: int = N_PLACEBO) -> dict:
    off = pd.read_parquet(CACHE / "offers_step30.parquet")
    games = load_games(conn)
    dec, slates = live_decisions(off, games)
    arts = season_arts(dec, slates)
    b = select_nights(dec, arts)
    graded_nights = slates[slates["season"].isin(list(arts))]
    per = b.groupby("night").size()
    lo, hi = boot_ci(b)
    half = b["tip"] <= b["tip"].quantile(0.5)
    pl = night_placebo(off, games, arts, n_placebo) if n_placebo else np.array([np.nan])
    dk = b[b["book"] == "draftkings"]
    res = {"bets": len(b), "slate_nights": len(graded_nights),
           "per_night": round(len(b) / len(graded_nights), 2),
           "nights_without_a_bet": int(len(graded_nights) - len(per)), "most_in_a_night": int(per.max()),
           "units": round(float(b["units"].sum()), 1), "roi": round(roi(b), 4),
           "ci": (round(lo, 4), round(hi, 4)), "early": round(roi(b[half]), 4),
           "late": round(roi(b[~half]), 4),
           "seasons": {int(s): (len(x), round(roi(x), 4), round(float(x["units"].sum()), 1))
                       for s, x in b.groupby("season")},
           "by_model": {M.RULE_BY_KEY[r].model_id: (len(x), round(roi(x), 4), round(float(x["units"].sum()), 1))
                        for r, x in b.groupby("rule")},
           "prices": (float(b["price"].min()), float(b["price"].median()), float(b["price"].max())),
           "dk_only": (len(dk), round(roi(dk), 4)), "pinnacle": pin_split(b),
           "placebo": {"runs": int(n_placebo), "mean": round(float(np.nanmean(pl)), 4),
                       "p95": round(float(np.nanpercentile(pl, 95)), 4), "max": round(float(np.nanmax(pl)), 4)}}
    b.drop(columns=[c for c in b.columns if str(b[c].dtype) == "category"]).to_parquet(
        CACHE / "best_per_night.parquet", index=False)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--grade", action="store_true")
    ap.add_argument("--step", type=int, choices=(60, 30), default=60)
    ap.add_argument("--placebo", type=int, default=N_PLACEBO)
    ap.add_argument("--best-per-night", action="store_true",
                    help="grade the shipped selection (needs the --grade --step 30 offers)")
    a = ap.parse_args(argv)
    conn = _conn()
    try:
        if a.fit:
            out = run_fit(conn)
            (CACHE / "fit.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        if a.grade:
            res = run_grade(conn, a.step, a.placebo)
            pd.set_option("display.width", 250)
            print(res.to_string(index=False))
            res.to_json(CACHE / f"grade_step{a.step}.json", orient="records", indent=1)
        if a.best_per_night:
            res = run_best_per_night(conn, a.placebo)
            print(json.dumps(res, indent=1, default=str))
            (CACHE / "best_per_night.json").write_text(json.dumps(res, indent=1, default=str),
                                                       encoding="utf-8")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
