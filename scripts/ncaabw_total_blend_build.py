"""Build the NCAABW totals model's frozen numbers (models/ncaabw_total_blend.py).

Writes models/saved/ncaabw_total_blend_<season>.json: the ratings settings, the
last finished season's end-of-season ratings (the next season's prior), that
season's league shooting and style rates (the next season's reference), the
stage-2 residual coefficients (fit on 2016 through the last finished season)
and the blend's c / beta / sigma (fit on the priced seasons, 2024-25 through
the last finished season, at DraftKings' first posted total: every priced
game, and each phase that has 300 of them).

It also replays the model on the priced seasons and prints the bets at the
0.05 cut, so the build can be checked against the evidence
(docs/sports/ncaabw.md "Research"):
  * each priced season after the first, on numbers fitted on the earlier
    seasons only (walk-forward; today that is 2025-26 on 2024-25);
  * the first priced season on the blend of the later ones (a second look,
    not walk-forward);
  * every priced season on the blend the artifact holds (in sample).
Then it replays THE CARD'S OWN DECISION (models.ncaabw_total_blend.decide: the
hold, the refit at one cutoff, the inputs, the price, and the card's price and
EV floors) on every priced game of each walk-forward season, with that
season's numbers built exactly as the artifact is, and matches its bets to the
replay's game by game.

    python -m scripts.ncaabw_total_blend_build [--cache DIR] [--out PATH] [--last-season 2026]
                                               [--card-path-seasons 2026-2026]

DIR (default: the research cache, scripts/ncaabw_research/_paths.py) is a
read-only copy of what Supabase holds, as parquet:
  games.parquet           games joined to ncaabw_events for sport NCAABW
                          (scripts/ncaabw_research/cache.py)
  box.parquet             NCAA's team box rows as ncaabw_team_game_stats
                          stores them (the same script, the importer's own
                          parser)
  pregame_quotes.parquet  every book's change-only pre-game quotes, the rows
                          the purchase stores in `odds` under source
                          odds_api_ncaabw_history, parsed by the production
                          parser from the purchase's spool
                          (scripts/ncaabw_research/quotes.py)
DraftKings' FIRST POSTED total is its earliest pre-game totals row by its own
time on the row; rows missing a price and totals outside
models.ncaabw_total_blend.TOTAL_RANGE are dropped FIRST, so the next row is the
first post. The live card reads the same first post
(scripts/ncaabw_total_card.load_first_posts).

Reads nothing else and writes only the JSON. About four minutes.
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

import models.ncaabw_quote_bounds as qb  # noqa: E402
import models.ncaabw_total_blend as nb  # noqa: E402

FIRST_SEASON = 2016          # the first season ESPN's schedule is stored for (burn-in, no prior)
STAGE2_FIRST = 2016          # stage 2 trains from here
STAGE2_SCORED = 2017         # and is scored walk-forward from here
PAID_FIRST = 2025            # the first season the feed's history prices (from 2024-11-12)
CUT = 0.05
SETTINGS = {"K": 9.0, "KT": 3.0, "half_life": 45.0, "a": 0.72, "b": 0.0, "r_tempo": 0.9,
            "K_h": 300.0, "htp_K": 300.0}
_RNG_SEED = 20261109


# ── loading ──────────────────────────────────────────────────────────────────

def first_posts(quotes: pd.DataFrame) -> pd.DataFrame:
    """DraftKings' first posted total per game from the change-only pre-game
    quotes: data errors dropped FIRST (models/ncaabw_quote_bounds.py), then the
    earliest row by DraftKings' own time."""
    t = quotes[(quotes["market"] == nb.MARKET) & (quotes["bookmaker"] == nb.BOOK)]
    t = t.dropna(subset=["total_line", "over_price", "under_price"])
    t = t.rename(columns={"total_line": "line"})
    t, bad = qb.split(t, nb.MARKET, "line", ("over_price", "under_price"))
    print(f"DraftKings totals rows dropped as data errors: {len(bad)}"
          + "".join(f"\n  {x}" for x in qb.describe(bad, "line", ("over_price", "under_price"))))
    t = t.sort_values(["game_id", "last_update", "snapshot_ts"], kind="stable")
    dk = t.groupby("game_id").head(1).copy()
    dk["quote_ns"] = pd.to_datetime(dk["last_update"], utc=True).dt.as_unit("ns").astype("int64")
    return dk[["game_id", "line", "over_price", "under_price", "quote_ns"]]


def load(cache: Path, last: int):
    g = pd.read_parquet(cache / "games.parquet",
                        columns=["game_id", "season", "game_date", "commence_time", "home_score",
                                 "away_score", "neutral_site", "espn_event_id", "home_espn_id",
                                 "away_espn_id", "status"])
    g = g[g["home_score"].notna() & (g["season"] >= FIRST_SEASON) & (g["season"] <= last)].copy()
    g["home_score"] = g["home_score"].astype(float); g["away_score"] = g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["neutral_site"] = pd.to_numeric(g["neutral_site"], errors="coerce").fillna(0).astype(int)
    box = pd.read_parquet(cache / "box.parquet")
    # One season of box rows before the first season of games: its league
    # rates are the first season's reference (features_all), as in the
    # evidence. NCAA's box rows go back to 2009-10; the schedule does not.
    box = box[(box["season"] >= FIRST_SEASON - 1) & (box["season"] <= last)].copy()
    dk = first_posts(pd.read_parquet(cache / "pregame_quotes.parquet"))
    return g, box, dk[dk["game_id"].isin(set(g["game_id"]))]


def prepare(g: pd.DataFrame, box: pd.DataFrame):
    """Games with possessions and end times; the box rows placed on their
    games, one source per game, with season and end_ns."""
    b = nb.place_box(box, g)
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


# ── grading ──────────────────────────────────────────────────────────────────

def grade(x: pd.DataFrame) -> dict:
    """Bets at one unit to win, risk capped at 3; the interval resamples
    dates."""
    if not len(x):
        return {"bets": 0}
    dd = np.array([nb.dec(p) for p in x["price"]])
    risk = np.minimum(1.0 / (dd - 1.0), 3.0)
    res = np.where(x["side"] == "over", x["total"] - x["line"], x["line"] - x["total"])
    units = np.where(res > 0, risk * (dd - 1.0), np.where(res < 0, -risk, 0.0))
    dates = x["game_date"].astype(str).values
    ud = pd.Series(units).groupby(dates).sum().values
    rd = pd.Series(risk).groupby(dates).sum().values
    idx = np.random.default_rng(_RNG_SEED).integers(0, len(ud), size=(3000, len(ud)))
    lo, hi = np.percentile(ud[idx].sum(axis=1) / rd[idx].sum(axis=1) * 100, [2.5, 97.5])
    return {"bets": int(len(x)), "wins": int((res > 0).sum()), "losses": int((res < 0).sum()),
            "pushes": int((res == 0).sum()), "units": round(float(units.sum()), 2),
            "roi_pct": round(float(units.sum() / risk.sum() * 100), 2),
            "roi_95": [round(float(lo), 1), round(float(hi), 1)],
            "overs": int((x["side"] == "over").sum()),
            "price_min": float(x["price"].min()), "price_max": float(x["price"].max())}


def score(te: pd.DataFrame, blends: dict) -> pd.DataFrame:
    """Each game of `te` (the model total, DraftKings' first post, the final)
    priced with its phase's blend, else the all-phase one."""
    rows = []
    for r in te.itertuples(index=False):
        b = nb.blend_for(blends, r.game_date)
        if b is None:
            continue
        pz = nb.price(r.pt, r.line, r.over_price, r.under_price, b)
        rows.append({"game_id": r.game_id, "season": int(r.season), "game_date": r.game_date,
                     "total": r.total, "line": r.line, "side": pz.side, "price": pz.price,
                     "edge": pz.edge, "prob": pz.prob, "min_gp": min(r.ng_h, r.ng_a)})
    return pd.DataFrame(rows)


def replay(x: pd.DataFrame, last: int) -> pd.DataFrame:
    """Walk-forward: each priced season after the first, on the blend of the
    priced seasons before it."""
    parts = []
    for S in range(PAID_FIRST + 1, last + 1):
        tr = x[(x["season"] >= PAID_FIRST) & (x["season"] < S)]
        parts.append(score(x[x["season"] == S], nb.fit_blends(tr)))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def by_season(bets: pd.DataFrame) -> dict:
    return {str(int(S)): grade(z) for S, z in bets.groupby("season")}


def by_phase(bets: pd.DataFrame) -> dict:
    ph = np.array([nb.phase_of(v) for v in bets["game_date"]])
    return {name: grade(bets[ph == name]) for name in nb.PHASES}


def season_artifact(S: int, ends: dict, lg: dict, coefs: dict, x: pd.DataFrame) -> dict:
    """The numbers the card would read for season S, built walk-forward as the
    artifact is: last season's end state and league rates, stage 2 fit
    through S-1, the blend fit on the priced seasons before S."""
    tr = x[(x["season"] >= PAID_FIRST) & (x["season"] < S)]
    return {"kind": nb.ARTIFACT_KIND, "season": S, "params": SETTINGS,
            "end_state": ends[S - 1].to_json(), "league_rates": lg[S - 1],
            "stage2": {"coef": coefs[S]}, "blend": nb.fit_blends(tr)}


def card_path(g: pd.DataFrame, b: pd.DataFrame, dk: pd.DataFrame, ends: dict, lg: dict,
              coefs: dict, x: pd.DataFrame, seasons, log=print) -> pd.DataFrame:
    """The card's decision on every priced game of each season in `seasons`:
    nb.decide at the game's first post (the hold, the refit at one cutoff,
    the inputs, the price), with season_artifact()'s numbers, then the card's
    price floor and EV floor (scripts/ncaabw_total_card.pick_rows). One row per
    priced game: status, side, price, edge, prob, and why a bet was refused."""
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
        log(f"  card path {S}: {len(gids)} priced games, {st} ({time.time() - t:.0f}s)")
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


def _round_blend(blend: dict) -> dict:
    return {ph: (None if v is None else {k: (round(w, 8) if isinstance(w, float) else w)
                                         for k, w in v.items()})
            for ph, v in blend.items()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=None,
                    help="the copy of the three reads (default: the research cache)")
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--bets-out", type=Path, default=None,
                    help="optional parquet of every replayed game, for checking against the evidence")
    ap.add_argument("--card-path-seasons", default=None,
                    help="seasons for the card-path replay, e.g. 2026-2026 (default: the "
                         "walk-forward seasons); 'none' skips it")
    a = ap.parse_args(argv)
    t0 = time.time()
    last = a.last_season
    if a.cache is None:
        from scripts.ncaabw_research._paths import CACHE
        a.cache = CACHE
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
    paid = x[(x["season"] >= PAID_FIRST) & (x["season"] <= last)]
    blend = nb.fit_blends(paid)
    # 1. walk-forward; 2. the first priced season on the later ones; 3. in sample
    sc = replay(x, last)
    bets = sc[sc["edge"] > CUT] if len(sc) else sc
    later = x[(x["season"] > PAID_FIRST) & (x["season"] <= last)]
    second = score(x[x["season"] == PAID_FIRST], nb.fit_blends(later)) if len(later) else pd.DataFrame()
    live = score(paid, blend)
    live_bets = live[live["edge"] > CUT]
    pooled = pd.concat([bets, second[second["edge"] > CUT]]) if len(second) else bets
    summary = {
        "cut": CUT, "rule": "every priced game, no games-played wait",
        "quote": "DraftKings' first posted total (earliest pre-game row by its own time, "
                 f"totals outside {list(nb.TOTAL_RANGE)} dropped first)",
        "priced_games_by_season": {str(int(s)): int(n) for s, n in paid.groupby("season").size().items()},
        "walk_forward": {"what": "each priced season after the first, blend fitted on the priced "
                                 "seasons before it", **grade(bets), "by_season": by_season(bets) if len(bets) else {}},
        "second_look": {"what": f"{PAID_FIRST} on the blend of the later priced seasons (not walk-forward)",
                        **(grade(second[second["edge"] > CUT]) if len(second) else {"bets": 0})},
        "each_season_on_the_others_pooled": grade(pooled) if len(pooled) else {"bets": 0},
        "live_blend_in_sample": {
            "what": "every priced season on the blend the artifact holds",
            **grade(live_bets), "by_season": by_season(live_bets),
            "share_of_priced_games_bet": round(float((live["edge"] > CUT).mean()), 4),
            "min_prob": round(float(live_bets["prob"].min()), 4),
            "min_ev": round(float(min(p * nb.dec(pr) - 1 for p, pr in zip(live_bets["prob"], live_bets["price"]))), 4),
            "max_edge_every_priced_game": round(float(live["edge"].max()), 4),
            "by_phase": by_phase(live_bets)},
        "each_season_on_the_others_by_phase": by_phase(pooled) if len(pooled) else {},
        "neighbours_live_blend": {f"{c:.2f}": {k: v for k, v in grade(live[live["edge"] > c]).items()
                                               if k in ("bets", "units", "roi_pct", "roi_95")}
                                  for c in (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10)},
        "neighbours_each_season_on_the_others": {
            f"{c:.2f}": {k: v for k, v in grade(pd.concat([sc[sc["edge"] > c], second[second["edge"] > c]])).items()
                         if k in ("bets", "units", "roi_pct", "roi_95")}
            for c in (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10)} if len(sc) and len(second) else {},
    }
    print("replay:", json.dumps(summary, indent=1))
    if a.bets_out:
        live.to_parquet(a.bets_out, index=False)
    spec = a.card_path_seasons or (f"{PAID_FIRST + 1}-{last}" if last > PAID_FIRST else "none")
    if spec.lower() != "none":
        lo, _, hi = spec.partition("-")
        seasons = list(range(int(lo), int(hi or lo) + 1))
        cp = card_path(g, b, dk, ends, lg, coefs, x, seasons)
        cbets = cp[(cp["status"] == "bets") & cp["refused"].isna()].merge(
            d[["game_id", "total", "game_date"]], on="game_id")
        summary["card_path"] = {"seasons": [seasons[0], seasons[-1]],
                                "match": match_card_path(cp, sc, bets),
                                "by_season": by_season(cbets)}
        print("card path (models.ncaabw_total_blend.decide, walk-forward numbers):",
              json.dumps(summary["card_path"], indent=1, default=str))
        if a.bets_out:
            cp.to_parquet(a.bets_out.with_name(a.bets_out.stem + "_card_path.parquet"), index=False)
    out = a.out or (nb.ROOT / f"models/saved/ncaabw_total_blend_{last + 1}.json")
    art = {
        "kind": nb.ARTIFACT_KIND, "model_id": nb.MODEL_ID,
        "season": last + 1, "prior_season": last,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": f"python -m scripts.ncaabw_total_blend_build --last-season {last}",
        "quote_rule": ("DraftKings' first posted full-game total: the earliest pre-game row by its own "
                       f"time, totals outside {list(nb.TOTAL_RANGE)} dropped first"),
        "params": SETTINGS,
        "possessions": "fga - orb + tov + 0.475 fta, the two teams averaged, every season",
        "end_state": ends[last].to_json(),
        "league_rates": lg[last],
        "stage2": {"cols": list(nb.STAGE2_COLS), "coef": [round(c, 8) for c in coef],
                   "train_seasons": [STAGE2_FIRST, last]},
        "blend": _round_blend(blend),
        "blend_note": ("a phase with fewer than 300 priced games has no fit of its own (null) and is "
                       "priced with 'all'"),
        "blend_train_seasons": [PAID_FIRST, last],
        "replay": summary,
    }
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
