"""Build the NCAAB totals model's frozen numbers (models/ncaab_total_blend.py).

Writes models/saved/ncaab_total_blend_<season>.json: the ratings settings, the
last finished season's end-of-season ratings (the next season's prior), that
season's league shooting and style rates (the next season's reference), the
stage-2 residual coefficients (fit on 2012 through the last finished season)
and the blend's c / beta / sigma per phase (fit on the paid seasons 2021
through the last finished season, at DraftKings' first posted total). It also
replays the model, walk-forward, on 2022 through the last finished season and
prints the bets at the 0.04 cut by season, so the port can be checked against
the evidence; then replays THE CARD'S OWN DECISION (models.ncaab_total_blend.
decide: the hold, the refit at one cutoff, the inputs, the price, and the
card's price and EV floors) on every quoted game of each season, with that
season's numbers built walk-forward exactly as the artifact is, and matches
its bets to the replay's game by game.

    python -m scripts.ncaab_total_blend_build --cache DIR [--out PATH] [--last-season 2026]
                                              [--card-path-seasons 2022-2026]

DIR is a read-only copy of four Supabase reads, as parquet:
  games.parquet                  SELECT game_id, season, game_date, commence_time, home_score,
                                 away_score, neutral_site FROM games WHERE sport = 'NCAAB'
  ncaab_events.parquet           SELECT * FROM ncaab_events
  ncaab_team_game_stats.parquet  SELECT contest_id, team, game_date, espn_game_id, team_espn_id,
                                 is_home, season, home_espn_id, away_espn_id, pts, d_pts, fga,
                                 fgm, tpa, tpm, fta, ftm, orb, drb, tov, source
                                 FROM ncaab_team_game_stats            (season by season)
  odds_reduced.parquet           per game, DraftKings' FIRST POSTED total: its earliest
                                 pre-game totals row by its own time (o_ts = snapshot_at,
                                 o_total_line, o_over_price, o_under_price), from every
                                 stored row (the opener grid's half-hourly purchase
                                 included) of SELECT game_id, market, bookmaker,
                                 snapshot_at, total_line, over_price, under_price, created_at
                                 FROM odds WHERE market = 'totals' AND snapshot_type IS
                                 DISTINCT FROM 'in_play'; rows stamped after ESPN's tip, rows
                                 missing a price, and totals outside
                                 models.ncaab_total_blend.TOTAL_RANGE dropped FIRST; two rows
                                 with one stamp keep the one stored last. The live card reads
                                 the same first post (scripts/ncaab_total_card.
                                 load_first_posts).
Every row is in Supabase; the copy only saves re-reading 7.3M odds rows. The
2026-11-03 build read research round 5's copy of that day ("truefix": the
2026-10-30 games, events and box reads, and the odds re-read after the opener
grid was stored, with the one feed typo, 1465.0 on
NCAAB_2023-03-17_providence_kentucky, dropped).

Reads nothing else and writes only the JSON. The artifact takes about ten
minutes (the ratings are refit as of every quote, sixteen seasons over); the
card-path replay adds a refit per first-post hour per season.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.ncaab_quote_bounds as qb  # noqa: E402
import models.ncaab_total_blend as nb  # noqa: E402

FIRST_SEASON = 2011          # burn-in season (no prior)
STAGE2_FIRST = 2012          # stage 2 trains from here
STAGE2_SCORED = 2014         # and is scored walk-forward from here
PAID_FIRST = 2021            # the first season with bought DraftKings totals
CUT = 0.04
SETTINGS = {"K": 9.0, "KT": 3.0, "half_life": 45.0, "a": 0.72, "b": 0.0, "r_tempo": 0.9,
            "K_h": 300.0, "htp_K": 300.0}


# ── loading ──────────────────────────────────────────────────────────────────

def load(cache: Path, last: int):
    g = pd.read_parquet(cache / "games.parquet",
                        columns=["game_id", "season", "game_date", "commence_time", "home_score",
                                 "away_score", "neutral_site"])
    ev = pd.read_parquet(cache / "ncaab_events.parquet")
    g = g.merge(ev[["game_id", "espn_event_id", "home_espn_id", "away_espn_id", "status"]],
                on="game_id", how="left")
    g = g[g["home_score"].notna() & (g["season"] <= last)].copy()
    g["home_score"] = g["home_score"].astype(float); g["away_score"] = g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["neutral_site"] = pd.to_numeric(g["neutral_site"], errors="coerce").fillna(0).astype(int)
    box = pd.read_parquet(cache / "ncaab_team_game_stats.parquet")
    box = box[box["season"] <= last].copy()
    red = pd.read_parquet(cache / "odds_reduced.parquet",
                          columns=["game_id", "market", "bookmaker", "o_ts", "o_total_line",
                                   "o_over_price", "o_under_price"])
    dk = red[(red["market"] == "totals") & (red["bookmaker"] == nb.BOOK)]
    dk = dk.dropna(subset=["o_ts", "o_total_line", "o_over_price", "o_under_price"])
    dk = dk.rename(columns={"o_total_line": "line", "o_over_price": "over_price",
                            "o_under_price": "under_price"})
    # The card never prices a feed typo (models/ncaab_quote_bounds.py), so
    # neither does the replay nor the blend fit. The reduction should already
    # have dropped a typo BEFORE taking the first row (so the next row is the
    # first post, as the card reads it); one that slipped through is dropped
    # here and counted, and that game has no quote.
    dk, bad = qb.split(dk, nb.MARKET, "line", ("over_price", "under_price"))
    print(f"DraftKings first totals dropped as data errors: {len(bad)}"
          + "".join(f"\n  {x}" for x in qb.describe(bad, "line", ("over_price", "under_price"))))
    dk["quote_ns"] = pd.to_datetime(dk["o_ts"], utc=True).dt.as_unit("ns").astype("int64")
    return g, box, dk[["game_id", "line", "over_price", "under_price", "quote_ns"]]


def match_contests(box: pd.DataFrame, g: pd.DataFrame) -> dict:
    """contest_id -> game_id for box rows with no ESPN game id (2011-2022):
    the date and both ESPN ids as ESPN orients them, then reversed, then the
    date +-1 day with one id and the exact score (scripts/prep_games.py of the
    research)."""
    h = box[box["is_home"] == True][["contest_id", "game_date", "home_espn_id", "away_espn_id",  # noqa: E712
                                     "pts", "d_pts"]].drop_duplicates("contest_id")
    h = h[h["pts"].notna() & h["d_pts"].notna()]
    h["game_date"] = h["game_date"].astype(str).str[:10]

    def key(df, a, b):
        return (df["game_date"].astype(str) + "|" + df[a].fillna(-1).astype(int).astype(str)
                + "|" + df[b].fillna(-1).astype(int).astype(str))
    hh = h[h["home_espn_id"].notna() & h["away_espn_id"].notna()].copy()
    hh["k"] = key(hh, "home_espn_id", "away_espn_id")
    hh = hh.drop_duplicates("k", keep=False).set_index("k")
    cid = key(g, "home_espn_id", "away_espn_id").map(hh["contest_id"])
    cid = cid.where(cid.notna(), key(g, "away_espn_id", "home_espn_id").map(hh["contest_id"]))
    parts = []
    for off in (0, -1, 1):
        d = (pd.to_datetime(h["game_date"]) + pd.Timedelta(days=off)).dt.strftime("%Y-%m-%d")
        for idc, s1, s2 in (("home_espn_id", "pts", "d_pts"), ("away_espn_id", "d_pts", "pts")):
            k = (d + "|" + h[idc].fillna(-9).astype(int).astype(str) + "|"
                 + h[s1].astype(int).astype(str) + "|" + h[s2].astype(int).astype(str))
            parts.append(pd.Series(h["contest_id"].values, index=k.values))
    s = pd.concat(parts)
    s = s[~s.index.duplicated(keep=False)]
    for idc, sa, sb in (("home_espn_id", "home_score", "away_score"),
                        ("away_espn_id", "away_score", "home_score")):
        k = (g["game_date"] + "|" + g[idc].fillna(-8).astype(int).astype(str) + "|"
             + g[sa].astype(int).astype(str) + "|" + g[sb].astype(int).astype(str))
        cid = cid.where(cid.notna(), k.map(s))
    m = pd.DataFrame({"contest_id": cid.values, "game_id": g["game_id"].values}).dropna()
    m = m.drop_duplicates("contest_id", keep="first")
    return dict(zip(m["contest_id"], m["game_id"]))


def prepare(g: pd.DataFrame, box: pd.DataFrame):
    """Games with possessions and end times; deduped box rows with game_id,
    season and end_ns."""
    b = nb.dedupe_box(box)
    ev_map = dict(zip(pd.to_numeric(g["espn_event_id"], errors="coerce"), g["game_id"]))
    eg = pd.to_numeric(b["espn_game_id"], errors="coerce")
    b["game_id"] = eg.map(ev_map)
    cmap = match_contests(b[b["game_id"].isna()], g)
    b.loc[b["game_id"].isna(), "game_id"] = b.loc[b["game_id"].isna(), "contest_id"].map(cmap)
    poss = nb.game_possessions(b)
    g = g.copy()
    g["poss"] = g["game_id"].map(poss)
    cnt = pd.concat([g[["season", "home_espn_id"]].rename(columns={"home_espn_id": "t"}),
                     g[["season", "away_espn_id"]].rename(columns={"away_espn_id": "t"})]).dropna()
    n = cnt.groupby(["season", "t"]).size()
    g["n_sched_home"] = [n.get((s, t), 0) if pd.notna(t) else 0 for s, t in zip(g["season"], g["home_espn_id"])]
    g["n_sched_away"] = [n.get((s, t), 0) if pd.notna(t) else 0 for s, t in zip(g["season"], g["away_espn_id"])]
    g = nb.season_games(g)
    end = dict(zip(g["game_id"], g["end_ns"]))
    fallback = ((pd.to_datetime(b["game_date"].astype(str).str[:10]) + pd.Timedelta(days=2, hours=6))
                .dt.tz_localize("UTC").dt.as_unit("ns").astype("int64"))
    b["end_ns"] = b["game_id"].map(end)
    b["end_ns"] = b["end_ns"].where(b["end_ns"].notna(), fallback).astype("int64")
    return g, b


# ── the chain ────────────────────────────────────────────────────────────────

def ratings_chain(g: pd.DataFrame, cut: dict, params: nb.Params, log=print):
    preds, ends = [], {}
    prior = None
    for s in sorted(g["season"].unique()):
        t = time.time()
        sg = g[g["season"] == s]
        p, end = nb.season_pass(sg, prior, params, cut)
        preds.append(p)
        ends[int(s)] = end
        prior = end
        log(f"  ratings {s}: {len(sg)} games, {int(p['strict'].sum())} at a DraftKings quote, "
            f"mu {end.mu:.1f} tmu {end.tmu:.1f} htp {end.htp:.2f} ({time.time() - t:.0f}s)")
    return pd.concat(preds, ignore_index=True), ends


def features_all(g: pd.DataFrame, b: pd.DataFrame, dk: pd.DataFrame):
    pairs = nb.box_pairs(b)
    lg = {int(s): nb.league_rates(x) for s, x in pairs.groupby("season")}
    seasons = sorted(lg)
    ref = {s: lg.get(s - 1, lg[seasons[0]]) for s in seasons}
    qc = dict(zip(dk["game_id"], (dk["quote_ns"] // nb._HOUR_NS) * nb._HOUR_NS))
    date_cut = ((pd.to_datetime(g["game_date"]) + pd.Timedelta(hours=6)).dt.tz_localize("America/New_York")
                .dt.tz_convert("UTC").dt.as_unit("ns").astype("int64"))
    q = g[["game_id", "season", "home_espn_id", "away_espn_id"]].copy()
    q["cut_ns"] = [qc.get(x, c) for x, c in zip(g["game_id"], date_cut)]
    return nb.style_features(pairs, q, ref), lg


def stage2_walk(d: pd.DataFrame, last: int):
    rh = pd.Series(np.nan, index=d.index)
    for S in range(STAGE2_SCORED, last + 1):
        tr = d[(d["season"] >= STAGE2_FIRST) & (d["season"] < S)]
        coef = nb.fit_stage2(tr)
        te = d[d["season"] == S]
        rh.loc[te.index] = nb.residual(te, coef)
    final = nb.fit_stage2(d[(d["season"] >= STAGE2_FIRST) & (d["season"] <= last)])
    return rh, final


def stage2_coefs(d: pd.DataFrame, last: int) -> dict:
    """Season S -> the stage-2 coefficients fit on STAGE2_FIRST..S-1, the ones
    stage2_walk scores S with (and, for S = last + 1, the artifact's)."""
    return {S: nb.fit_stage2(d[(d["season"] >= STAGE2_FIRST) & (d["season"] < S)])
            for S in range(STAGE2_SCORED, last + 2)}


def grade(x: pd.DataFrame) -> dict:
    if not len(x):
        return {"bets": 0}
    dd = np.array([nb.dec(p) for p in x["price"]])
    risk = np.minimum(1.0 / (dd - 1.0), 3.0)
    res = np.where(x["side"] == "over", x["total"] - x["line"], x["line"] - x["total"])
    units = np.where(res > 0, risk * (dd - 1.0), np.where(res < 0, -risk, 0.0))
    return {"bets": int(len(x)), "wins": int((res > 0).sum()), "losses": int((res < 0).sum()),
            "pushes": int((res == 0).sum()), "units": round(float(units.sum()), 2),
            "roi_pct": round(float(units.sum() / risk.sum() * 100), 2),
            "overs": int((x["side"] == "over").sum()),
            "price_min": float(x["price"].min()), "price_max": float(x["price"].max())}


def replay(d: pd.DataFrame, dk: pd.DataFrame, last: int):
    """Walk-forward blend (paid seasons 2021..S-1) for S = 2022..last, priced
    at DraftKings' first stored total; the bets at CUT, as the card places them
    (no games-played wait)."""
    x = d.merge(dk, on="game_id")
    x["phase"] = [nb.phase_of(v) for v in x["game_date"]]
    rows = []
    for S in range(PAID_FIRST + 1, last + 1):
        tr = x[(x["season"] >= PAID_FIRST) & (x["season"] < S)]
        te = x[x["season"] == S]
        for ph in nb.PHASES:
            b = nb.fit_blend(tr[tr["phase"] == ph])
            if b is None:
                continue
            for r in te[te["phase"] == ph].itertuples(index=False):
                pz = nb.price(r.pt, r.line, r.over_price, r.under_price, b)
                rows.append({"game_id": r.game_id, "season": S, "game_date": r.game_date,
                             "total": r.total, "line": r.line, "side": pz.side, "price": pz.price,
                             "edge": pz.edge, "prob": pz.prob,
                             "min_gp": min(r.ng_h, r.ng_a)})
    sc = pd.DataFrame(rows)
    bets = sc[sc["edge"] > CUT]
    return sc, bets


def by_season(bets: pd.DataFrame) -> dict:
    return {str(int(S)): grade(x) for S, x in bets.groupby("season")}


def season_artifact(S: int, ends: dict, lg: dict, coefs: dict, x: pd.DataFrame) -> dict:
    """The numbers the card would read for season S, built walk-forward as the
    artifact is: last season's end state and league rates, stage 2 fit
    through S-1, the blend fit on the paid seasons 2021..S-1."""
    tr = x[(x["season"] >= PAID_FIRST) & (x["season"] < S)]
    return {"kind": nb.ARTIFACT_KIND, "season": S, "params": SETTINGS,
            "end_state": ends[S - 1].to_json(), "league_rates": lg[S - 1],
            "stage2": {"coef": coefs[S]},
            "blend": {ph: nb.fit_blend(tr[tr["phase"] == ph]) for ph in nb.PHASES}}


def card_path(g: pd.DataFrame, b: pd.DataFrame, dk: pd.DataFrame, ends: dict, lg: dict,
              coefs: dict, x: pd.DataFrame, seasons, log=print) -> pd.DataFrame:
    """The card's decision on every quoted game of each season in `seasons`:
    nb.decide at the game's first post (the hold, the refit at one cutoff,
    the inputs, the price), with season_artifact()'s numbers, then the card's
    price floor and EV floor (scripts/ncaab_total_card.pick_rows). One row per
    quoted game: status, side, price, edge, prob, and why a bet was refused."""
    import config
    from models.honest_ev import gate
    floor = config.min_odds_for(nb.MODEL_ID)
    cut = config.MODEL_EDGE_THRESHOLDS[nb.MODEL_ID]
    q = dk.set_index("game_id")
    out = []
    for S in seasons:
        t = time.time()
        art = season_artifact(S, ends, lg, coefs, x)
        sg = g[g["season"] == S]
        box = b[b["season"] == S]
        gids = [gid for gid in sg["game_id"] if gid in q.index]
        quotes = {}
        for gid in gids:
            r = q.loc[gid]
            at = pd.Timestamp(int(r["quote_ns"]), tz="UTC").to_pydatetime()
            quotes[gid] = nb.Quote(game_id=gid, line=float(r["line"]), over_price=float(r["over_price"]),
                                   under_price=float(r["under_price"]), quote_at=at, fetched_at=at)
        got = nb.decide(sg[sg["game_id"].isin(gids)], quotes, sg, box, art, cut)
        for dcn in got:
            pz = dcn.priced
            row = {"game_id": dcn.game_id, "season": S, "status": dcn.status,
                   "side": pz.side if pz else None, "price": pz.price if pz else None,
                   "edge": pz.edge if pz else None, "prob": pz.prob if pz else None,
                   "line": dcn.quote.line if dcn.quote else None, "refused": None}
            if dcn.status == "bets":
                if floor is not None and pz.price < floor:
                    row["refused"] = "below_price_floor"
                elif not gate(nb.MODEL_ID, pz.prob, pz.price).clears:
                    row["refused"] = "below_ev_floor"
            out.append(row)
        st = pd.Series([r["status"] for r in out if r["season"] == S]).value_counts().to_dict()
        log(f"  card path {S}: {len(gids)} quoted games, {st} ({time.time() - t:.0f}s)")
    return pd.DataFrame(out)


def match_card_path(cp: pd.DataFrame, sc: pd.DataFrame, bets: pd.DataFrame) -> dict:
    """The card path's written bets against the replay's, game by game."""
    cb = cp[(cp["status"] == "bets") & cp["refused"].isna()]
    seasons = sorted(set(cp["season"]))
    rb = bets[bets["season"].isin(seasons)]
    both = rb.merge(cb, on="game_id", suffixes=("", "_card"))
    allg = sc[sc["season"].isin(seasons)].merge(cp[cp["edge"].notna()], on="game_id", suffixes=("", "_card"))
    return {"replay_bets": int(len(rb)), "card_bets": int(len(cb)), "same_game": int(len(both)),
            "same_side": int((both["side"] == both["side_card"]).sum()),
            "replay_only": sorted(set(rb["game_id"]) - set(cb["game_id"]))[:20],
            "card_only": sorted(set(cb["game_id"]) - set(rb["game_id"]))[:20],
            "refused": cp["refused"].value_counts().to_dict(),
            "held": cp[cp["status"].isin(["box_pending", "box_missing"])].groupby("season").size()
            .rename(index=str).to_dict(),
            "max_abs_edge_diff_all_scored": (round(float((allg["edge"] - allg["edge_card"]).abs().max()), 10)
                                             if len(allg) else None)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--bets-out", type=Path, default=None,
                    help="optional parquet of the replayed bets, for checking against the evidence")
    ap.add_argument("--card-path-seasons", default=None,
                    help="seasons for the card-path replay, e.g. 2022-2026 (default: 2022 to "
                         "--last-season); 'none' skips it")
    a = ap.parse_args(argv)
    t0 = time.time()
    last = a.last_season
    params = nb.Params.from_dict(SETTINGS)
    g, box, dk = load(a.cache, last)
    g, b = prepare(g, box)
    print(f"games {len(g)}, with possessions {int(g['poss'].notna().sum())}; box rows {len(b)}, "
          f"placed on a game {int(b['game_id'].notna().sum())}; DraftKings first totals {len(dk)}")
    cut = dict(zip(dk["game_id"], dk["quote_ns"]))
    preds, ends = ratings_chain(g, cut, params)
    feats, lg = features_all(g, b, dk)
    d = preds.merge(g[["game_id", "home_score", "away_score"]], on="game_id")
    d["total"] = d["home_score"] + d["away_score"]
    d = d.merge(feats, on="game_id", how="left")
    d = d[d["pt_s1"].notna() & d["total"].notna()].copy()
    rh, coef = stage2_walk(d, last)
    coefs = stage2_coefs(d, last)
    d["rhat"] = rh
    d["pt"] = d["pt_s1"] + d["rhat"].fillna(0.0)
    x = d.merge(dk, on="game_id")
    x["phase"] = [nb.phase_of(v) for v in x["game_date"]]
    paid = x[(x["season"] >= PAID_FIRST) & (x["season"] <= last)]
    blend = {ph: nb.fit_blend(paid[paid["phase"] == ph]) for ph in nb.PHASES}
    sc, bets = replay(d, dk, last)
    dev = bets[bets["season"] <= last - 1]
    newest = bets[bets["season"] == last]
    summary = {"cut": CUT, "rule": "every quoted game, no games-played wait",
               "quote": "DraftKings' first posted total (earliest pre-game row by its own time, "
                        f"totals outside {list(nb.TOTAL_RANGE)} dropped first)",
               f"{PAID_FIRST + 1}-{last - 1}": grade(dev), str(last): grade(newest),
               "by_season": by_season(bets),
               # the population the 2026-10-30 evidence graded, to check against it
               "both_teams_10_games": {f"{PAID_FIRST + 1}-{last - 1}": grade(dev[dev["min_gp"] >= 10]),
                                       str(last): grade(newest[newest["min_gp"] >= 10])},
               "min_prob": round(float(bets["prob"].min()), 4) if len(bets) else None,
               "min_ev": round(float(min(p * nb.dec(pr) - 1 for p, pr in zip(bets["prob"], bets["price"]))), 4)
               if len(bets) else None}
    print("replay (walk-forward blend on paid seasons):", json.dumps(summary, indent=1))
    if a.bets_out:
        bets.to_parquet(a.bets_out, index=False)
    spec = a.card_path_seasons or f"{PAID_FIRST + 1}-{last}"
    if spec.lower() != "none":
        lo, _, hi = spec.partition("-")
        seasons = list(range(int(lo), int(hi or lo) + 1))
        cp = card_path(g, b, dk, ends, lg, coefs, x, seasons)
        cbets = cp[(cp["status"] == "bets") & cp["refused"].isna()].merge(
            d[["game_id", "total"]], on="game_id")
        summary["card_path"] = {"seasons": [seasons[0], seasons[-1]],
                                "match": match_card_path(cp, sc, bets),
                                "by_season": by_season(cbets)}
        print("card path (models.ncaab_total_blend.decide, walk-forward numbers):",
              json.dumps(summary["card_path"], indent=1, default=str))
        if a.bets_out:
            cp.to_parquet(a.bets_out.with_name(a.bets_out.stem + "_card_path.parquet"), index=False)
    out = a.out or (nb.ROOT / f"models/saved/ncaab_total_blend_{last + 1}.json")
    art = {
        "kind": nb.ARTIFACT_KIND, "model_id": nb.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": f"python -m scripts.ncaab_total_blend_build --cache <copy of the four reads> --last-season {last}",
        "quote_rule": ("DraftKings' first posted full-game total: the earliest pre-game row by its own "
                       f"time, totals outside {list(nb.TOTAL_RANGE)} dropped first (research round 5, "
                       "2026-11-03; mike)"),
        "params": SETTINGS,
        "possessions": "fga - orb + tov + 0.475 fta, the two teams averaged, every season",
        "end_state": ends[last].to_json(),
        "league_rates": lg[last],
        "stage2": {"cols": list(nb.STAGE2_COLS), "coef": [round(c, 8) for c in coef],
                   "train_seasons": [STAGE2_FIRST, last]},
        "blend": {ph: (None if v is None else {k: (round(w, 8) if isinstance(w, float) else w)
                                               for k, w in v.items()})
                  for ph, v in blend.items()},
        "blend_train_seasons": [PAID_FIRST, last],
        "replay": summary,
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
