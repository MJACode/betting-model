"""Adversarial verification of the NBA prop projection card on WORKER-ONLY inputs.

The question: can the projection-model card (pooled unders, one a game) run on
the 2026-27 Railway worker? On the worker the only inputs are:

  * nba_player_game_log written from ESPN box scores -- whole minutes,
    is_starter, counting stats. No usage, possessions, plus/minus, fouls or
    position (stats.nba.com is unreachable from the worker; parse_nba_box
    never writes PF).
  * the schedule (nba_schedule / games), game odds, prop odds;
  * the ESPN injuries table: statuses 'Out' and 'Day-To-Day' only (measured
    2026-10-16: those two are the only NBA statuses stored). The official
    league report is not wired on the worker.

So this script feeds the UNCHANGED models.nba_props.build_frame a synthetic
`data` dict built from those inputs, and drives the researcher's own lab stages
(scripts/nba_prop_model_lab) with every path redirected to the verifier's
folder. Nothing in the researcher's work folder is read for inputs or written.

  * nba_player_game_adv  <- the game log: minutes_exact = the whole-number
    minutes, played = True, is_starter from the log; usage, fouls and
    position are blank (position falls to the rate guess in _positions).
  * nba_game_inactives   <- an AS-OF roster: for each team-game, a player
    whose latest log appearance strictly before the game was for this team in
    this season within ROSTER_DAYS days, or who is listed Out / Day-To-Day on
    the team's injury report at the decision, and who has no log row tonight.
  * nba_injury_report    <- the official report collapsed to what ESPN holds:
    Out -> Out; Doubtful / Questionable / Probable -> Questionable (the
    Day-To-Day stand-in); Available -> unlisted. ESPN 'Out' ~ official 'Out'
    is an approximation the task grants; it cannot be measured (the ESPN NBA
    rows start 2026-06-17, the official report ends 2026-04).
  * feature lists: usg_l, usg_s, r_fouls_l, own_p and the four *_usg
    teammate columns removed (mutated in place, so the module's own
    minutes_features() reads them).

    python -m scripts.nba_prop_model_verify frame [--lines] [--lag 60]
    python -m scripts.nba_prop_model_verify prices [--lag 60]
    python -m scripts.nba_prop_model_verify fit --variant wk --methods all --folds 2023,2026
    python -m scripts.nba_prop_model_verify gate|grid|judge --variant wk
    python -m scripts.nba_prop_model_verify card | variants | pinnacle | audit | rescore --lag 60

No Odds API call, no database read or write.
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
import scripts.nba_prop_model_lab as lab  # noqa: E402

TEMP = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild")
OUT = TEMP / "verify_model"
BETS = OUT / "bets"
ORIG_WORK = TEMP / "results" / "props_model_work"
PIN_RULE = TEMP / "results" / "props_market_bets_sharp_ALL_under_prop_0.00.parquet"
ROSTER_DAYS = 30
DTD_FROM = ("Doubtful", "Questionable", "Probable")
UNLISTED = "ESPN_UNLISTED"
NON_PIN_MARKETS = ("player_points_rebounds", "player_points_assists", "player_rebounds_assists",
                   "player_blocks", "player_steals", "player_blocks_steals", "player_turnovers")
VARIANT_RUNS = ("wk", "wk_no_avail", "wk_no_sched", "lines_wk", "wk_seed")

_ORIG_LOAD = nb.load_cache
_RAW: dict | None = None
_WK: dict = {}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── the worker's inputs ──────────────────────────────────────────────────────

def raw_cache() -> dict:
    global _RAW
    if _RAW is None:
        _RAW = _ORIG_LOAD(with_props=True, with_lines=True)
    return _RAW


def collapse_report(inj: pd.DataFrame, lag_min: int = 0) -> pd.DataFrame:
    """The official report read as the ESPN table would carry it, visible `lag_min` minutes late."""
    r = inj.copy()
    s = r.status.astype(object)
    s = s.where(~s.isin(DTD_FROM), "Questionable")
    s = s.where(s != "Available", UNLISTED)
    r["status"] = s
    if lag_min:
        r["report_ts"] = r.report_ts + pd.Timedelta(minutes=lag_min)
    return r


def adv_from_log(raw: dict) -> pd.DataFrame:
    games = raw["nba_games"].set_index("game_id")
    sch = raw["nba_schedule"]
    reg = set(sch[sch.game_type == "regular"].game_id)
    lg = raw["nba_player_game_log"]
    lg = lg[lg.game_id.isin(reg) & lg.game_id.isin(games.index)].copy()
    home, away = lg.game_id.map(games.home_team), lg.game_id.map(games.away_team)
    bad = ~((lg.team == home) | (lg.team == away))
    if bad.any():
        log(f"log rows whose team is neither side of the game: {int(bad.sum())} (dropped)")
        lg, home, away = lg[~bad], home[~bad], away[~bad]
    is_home = (lg.team == home)
    return pd.DataFrame({
        "game_id": lg.game_id.values, "player_id": lg.player_id.astype(str).values, "nba_game_id": None,
        "season": lg.season.values, "game_type": "regular", "game_date": lg.game_date.values,
        "team": lg.team.values, "opponent": np.where(is_home, away, home), "is_home": is_home.values,
        "player_name": lg.player_name.values, "position": None, "is_starter": lg.is_starter.values,
        "played": True, "minutes_exact": lg.minutes.astype(float).values,
        "usage_pct": np.nan, "fouls": np.nan})


def asof_roster(adv: pd.DataFrame, raw: dict, inj: pd.DataFrame, dec: pd.DataFrame,
                days: int = ROSTER_DAYS) -> pd.DataFrame:
    """Every (game, team, player) a worker could know is on the roster at the decision, from the log
    history and the injury table alone. Returns the pre-game roster INCLUDING players who then played
    (column in_log), so the audit can see who is on it for a reason other than having played."""
    g = raw["nba_games"]
    ids = set(adv.game_id)
    g = g[g.game_id.isin(ids)][["game_id", "season", "game_date", "home_team", "away_team"]]
    tg = pd.concat([g.rename(columns={"home_team": "team"})[["game_id", "season", "game_date", "team"]],
                    g.rename(columns={"away_team": "team"})[["game_id", "season", "game_date", "team"]]])
    tg["d"] = pd.to_datetime(tg.game_date)
    ap = adv[["player_id", "player_name", "team", "season", "game_date"]].copy()
    ap["d"] = pd.to_datetime(ap.game_date)
    # candidates: players who appeared for this team this season (any date); the as-of filter follows
    tsp = ap[["team", "season", "player_id"]].drop_duplicates()
    pairs = tg.merge(tsp, on=["team", "season"])
    last = ap.rename(columns={"team": "last_team", "season": "last_season", "d": "last_d"})[
        ["player_id", "last_team", "last_season", "last_d"]].sort_values("last_d")
    pairs = pairs.sort_values("d")
    m = pd.merge_asof(pairs, last, left_on="d", right_on="last_d", by="player_id",
                      allow_exact_matches=False)
    hist = m[(m.last_team == m.team) & (m.last_season == m.season)
             & ((m.d - m.last_d).dt.days <= days)][["game_id", "team", "player_id"]].assign(why="history")
    # the injury table at the decision: Out and Day-To-Day players
    rep = nb.injury_asof(inj, dec[dec.game_id.isin(ids)])
    rep = rep[rep.status.isin(["Out", "Questionable"])]
    b = adv[["team", "season", "player_id", "player_name"]]
    rep = nb._attach_report_ids(rep, b)
    rep = rep[["game_id", "team", "player_id"]].assign(player_id=lambda x: x.player_id.astype(str), why="report")
    ros = pd.concat([hist, rep], ignore_index=True)
    ros = ros.groupby(["game_id", "team", "player_id"], as_index=False).why.agg(lambda s: "+".join(sorted(set(s))))
    inlog = set(zip(adv.game_id, adv.player_id))
    ros["in_log"] = [k in inlog for k in zip(ros.game_id, ros.player_id)]
    return ros


def worker_cache(path=None, with_props: bool = False, with_lines: bool = True, lag_min: int = 0) -> dict:
    key = (lag_min,)
    if key not in _WK:
        raw = raw_cache()
        adv = adv_from_log(raw)
        inj = collapse_report(raw["nba_injury_report"], lag_min)
        props = raw["nba_props"]
        dec = nb.decisions_for(raw, props[props.game_date < lab.LAST_RESEARCH_DATE])
        ros = asof_roster(adv, raw, inj, dec)
        names = adv.drop_duplicates("player_id").set_index("player_id").player_name
        gm = raw["nba_games"].set_index("game_id")
        ina = ros[~ros.in_log][["game_id", "team", "player_id"]].copy()
        ina["player_name"] = ina.player_id.map(names)
        ina["season"] = ina.game_id.map(gm.season)
        ina["game_date"] = ina.game_id.map(gm.game_date)
        ina["game_type"] = "regular"
        ina["reason"] = "inferred"
        _WK[key] = {"nba_games": raw["nba_games"], "nba_schedule": raw["nba_schedule"],
                    "nba_player_game_log": raw["nba_player_game_log"], "nba_player_game_adv": adv,
                    "nba_game_inactives": ina, "nba_injury_report": inj,
                    "player_positions": raw["player_positions"].iloc[0:0], "_roster": ros}
        log(f"worker inputs (lag {lag_min}): box rows {len(adv):,}, inferred absences {len(ina):,} "
            f"(history {int(ros[~ros.in_log].why.str.contains('history').sum()):,}, "
            f"report {int(ros[~ros.in_log].why.str.contains('report').sum()):,})")
    out = dict(_WK[key])
    out.pop("_roster")
    if with_props:
        out["nba_props"] = raw_cache()["nba_props"]
    if with_lines:
        out["nba_odds"] = raw_cache()["nba_odds"]
    return out


def setup(work: Path, lag_min: int = 0) -> None:
    """Redirect every lab path, swap the cache loader, and drop what the worker cannot compute."""
    work.mkdir(parents=True, exist_ok=True)
    BETS.mkdir(parents=True, exist_ok=True)
    lab.WORK = work
    lab.RESULTS = BETS
    nb.OWN[:] = [c for c in nb.OWN if c not in ("usg_l", "usg_s", "r_fouls_l", "own_p")]
    nb.AVAIL[:] = [c for c in nb.AVAIL if c not in ("tm_o_usg", "ctx_o_usg", "d_o_usg", "opp_o_usg")]
    lab.VARIANTS.update({"wk": (), "wk_no_avail": ("avail",), "wk_no_sched": ("sched",), "lines_wk": (),
                         "wk_seed": ()})
    nb.load_cache = lambda path=None, with_props=False, with_lines=True: worker_cache(
        path, with_props, with_lines, lag_min)


# ── stages that are the lab's own, redirected ────────────────────────────────

def stage_frame(lines: bool, lag_min: int) -> None:
    lab.stage_frame(with_lines=lines)
    if not lines:
        ros = _WK[(lag_min,)]["_roster"]
        ros.to_parquet(lab.WORK / "asof_roster.parquet")


def stage_fit(variant: str, methods: str, folds: tuple) -> None:
    if variant == "wk_seed":
        for d in (nb.XGB_COUNT, nb.XGB_MIN, nb.XGB_BIN):
            d["random_state"] = 7
    lab.stage_fit(variant, methods, folds)


def stage_rescore(src: Path, variant: str = "wk") -> None:
    """Score this WORK's frame with the models fitted in `src` (the live situation: a model trained on
    history, fed tonight's late-read injury table). Writes pred_<variant>_<S> here, and copies the
    widths and the per-market choices."""
    fr = lab.load_frame()
    use = nb.usable(fr)
    for S in lab.FOLDS:
        fitted = pd.read_pickle(src / f"models_{variant}_{S}.pkl")
        te = fr[use & (fr.season == S)]
        P = te[lab.KEY_COLS].copy()
        P["min_hat"] = nb.predict_minutes(fitted["minutes"], te)
        for s in nb.BASE_STATS:
            P[f"mu2_{s}"] = nb.predict_rate_mean(fitted[f"rate_{s}"], te, P.min_hat.values)
        for spec in nb.COUNT_SPECS:
            k = f"direct_{spec.market}"
            if k in fitted:
                P[f"mud_{spec.market}"] = nb.predict_direct(fitted[k], te)
        for spec in nb.SPECS:
            k = f"binary_{spec.market}"
            if k in fitted:
                P[f"pb_{spec.market}"] = nb.predict_binary(fitted[k], te)
        for s in nb.BASE_STATS:
            for b in ("sa", "l10", "ew"):
                P[f"{b}_{s}"] = te[f"{b}_{s}"].values
        P.to_parquet(lab.WORK / f"pred_{variant}_{S}.parquet")
        log(f"rescored {S}: {len(P):,} rows")
    for f in (f"alphas_{variant}.json", f"gate_decide_{variant}.json"):
        (lab.WORK / f).write_text((src / f).read_text(encoding="utf-8"), encoding="utf-8")


# ── the card ─────────────────────────────────────────────────────────────────

def tips() -> pd.Series:
    g = raw_cache()["nba_games"].set_index("game_id")
    return nb._utc(g.commence_time)


def select(C: pd.DataFrame, cut: float, rule: str, tip: pd.Series | None = None) -> pd.DataFrame:
    """C sorted by EV descending. One bet a game (best EV); 'fc4' then keeps each night's first four
    games in tip order (ties by game id) -- the first-come cap a live card can actually run."""
    b = C[C.ev >= cut].drop_duplicates(["game_id", "player_id", "market"]).drop_duplicates("game_id")
    if rule == "game":
        return b
    if rule == "fc4":
        t = tip if tip is not None else tips()
        b = b.assign(_tip=b.game_id.map(t)).sort_values(["game_date", "_tip", "game_id"], kind="mergesort")
        return b.groupby("game_date", sort=False).head(4).drop(columns="_tip")
    return lab.apply_rule(C, cut, rule)


def sort_ev(C: pd.DataFrame) -> pd.DataFrame:
    return C.sort_values(["ev", "market", "player_id", "line"], ascending=[False, True, True, True],
                         kind="mergesort")


def stats(b: pd.DataFrame, ci: bool = True) -> dict:
    c = lab.cell_stats(b, with_ci=ci)
    keep = ["bets", "voids", "units", "roi", "n_2024", "roi_2024", "u_2024", "n_2025", "roi_2025", "u_2025",
            "n_2026", "roi_2026", "u_2026", "u_early", "u_late", "claimed", "won", "ci_lo", "ci_hi"]
    out = {k: c.get(k) for k in keep}
    out["seasons_pos"] = int(sum(1 for S in lab.SEASONS if (c.get(f"u_{S}") or 0) > 0))
    return out


def placebo_rule(P: pd.DataFrame, mks: tuple, cut: float, rule: str, n: int, tip: pd.Series) -> list[float]:
    """lab.placebo with the card's own selection: each player's model mean over his middle line handed to
    another player priced in the same market that night, every line re-priced, then the card rule."""
    rng = np.random.default_rng(7)
    C = P[P.market.isin(mks)]
    C = C.merge(lab.main_lines_from(C), on=["game_id", "player_id", "market"], how="left")
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
    under = C.side.values == "under"
    rois = []
    for _ in range(n):
        order = np.lexsort((rng.random(len(pl)), mcode, dcode))
        v = val[order]
        mu_p = np.where(cnt_pl, v * pl.main_line.values, v)[idx]
        po = np.where(cnt, lab._p_over_vec(mu_p, C.line.values, np.nan_to_num(C.alpha.values)), mu_p)
        mp = np.where(C.side.values == "over", po, 1 - po)
        Y = C.assign(model_prob=mp, ev=nb.expected_value(mp, C.price.values))[under]
        b = select(sort_ev(Y), cut, rule, tip)
        s = b[b.result.isin(["W", "L", "P"])]
        rois.append(100 * float(s.units.sum() / s.risk.sum()) if len(s) else np.nan)
    return rois


def blind_structured(P: pd.DataFrame, mks: tuple, rule: str, tip: pd.Series) -> dict:
    """The card's own structure on unders, ordered by something that is not the model: the highest price
    on offer, and at random (mean of 10)."""
    U = P[P.market.isin(mks) & (P.side == "under")]
    hp = stats(select(U.assign(ev=U.price).sort_values(["ev", "market", "player_id", "line"],
                                                        ascending=[False, True, True, True], kind="mergesort"),
                      -1e9, rule, tip), ci=False)
    rr = []
    for k in range(10):
        Cr = U.assign(ev=np.random.default_rng(k).random(len(U))).sort_values("ev", ascending=False)
        rr.append(stats(select(Cr, -1.0, rule, tip), ci=False)["roi"])
    return {"highest_price_roi": hp["roi"], "highest_price_bets": hp["bets"],
            "highest_price_by_season": [hp[f"roi_{S}"] for S in lab.SEASONS],
            "random_roi_mean": round(float(np.mean(rr)), 2), "random_roi_max": round(float(np.max(rr)), 2)}


def card_block(P: pd.DataFrame, PD: pd.DataFrame, PL: pd.DataFrame | None, mks: tuple, tip: pd.Series,
               tag: str, save: bool = True, n_placebo: int = 0, lean_checks: bool = True) -> dict:
    """The shippable card on one set of scored propositions: unders, one a game, with and without the
    first-come four a night, at the best of eight, the five live-feed books, and DraftKings alone."""
    out = {}
    U = sort_ev(P[P.market.isin(mks) & (P.side == "under")])
    UD = sort_ev(PD[PD.market.isin(mks) & (PD.side == "under")])
    UL = sort_ev(PL[PL.market.isin(mks) & (PL.side == "under")]) if PL is not None else None
    for rule in ("game", "fc4"):
        b = select(U, 0.0, rule, tip)
        out[f"{rule}|best"] = stats(b)
        out[f"{rule}|dk"] = stats(select(UD, 0.0, rule, tip))
        if UL is not None:
            out[f"{rule}|live5"] = stats(select(UL, 0.0, rule, tip))
        if save:
            cols = [c for c in lab.BET_COLS + ["ev_pin", "half", "mu", "status"] if c in b.columns]
            b[cols].to_parquet(BETS / f"card_{tag}_{rule}_best.parquet")
            bd = select(UD, 0.0, rule, tip)
            bd[cols].to_parquet(BETS / f"card_{tag}_{rule}_dk.parquet")
        # EV-floor neighbourhood (the floor barely binds one-a-game)
        out[f"{rule}|floors"] = {f"{cut:.2f}": {k: v for k, v in stats(select(U, cut, rule, tip), ci=False).items()
                                               if k in ("bets", "roi", "u_2024", "u_2025", "u_2026", "seasons_pos")}
                                 for cut in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)}
        # price-floor neighbourhood: -150 is a post-filter of the -200 set (the best price is the max)
        out[f"{rule}|price_floor_-150"] = stats(select(U[U.price >= -150], 0.0, rule, tip), ci=False)
        if lean_checks:
            out[f"{rule}|blind_structured"] = blind_structured(P, mks, rule, tip)
        if n_placebo:
            pl = placebo_rule(P, mks, 0.0, rule, n_placebo, tip)
            out[f"{rule}|placebo"] = {"n": n_placebo, "mean": round(float(np.nanmean(pl)), 2),
                                      "p95": round(float(np.nanpercentile(pl, 95)), 2),
                                      "max": round(float(np.nanmax(pl)), 2),
                                      "share_ge_real": round(float(np.mean(np.array(pl) >= out[f"{rule}|best"]["roi"])), 3)}
    if lean_checks:
        out["blind_under_same_props"] = lab.blind_same(P, mks, "under")
        # the blind under on the SAME population the card draws from: every player-market's main-line under
        out["blind_under_by_season"] = {}
        q = lab.load_quotes()
        q = q[q.usable & ~q.status.isin(["Out", "Doubtful"]) & q.market.isin(mks)]
        L = lab.main_lines(q)
        bl = P[P.market.isin(mks) & (P.side == "under")].merge(L, on=["game_id", "player_id", "market", "line"])
        for S in lab.SEASONS:
            out["blind_under_by_season"][S] = lab.summary(bl[bl.season == S])
    return out


def scored(variant: str, price: str) -> pd.DataFrame:
    p = lab.WORK / f"scored_{variant}_{price}.parquet"
    if not p.exists():
        import config
        P = lab.scored_propositions(variant, dk_only=(price == "DK"),
                                    book_set=tuple(config.LIVE_FEED_BOOKMAKERS) if price == "live5" else None)
        P.to_parquet(p)
        return P
    return pd.read_parquet(p)


def pooled_markets(work: Path, variant: str) -> tuple:
    decide = json.loads((work / f"gate_decide_{variant}.json").read_text(encoding="utf-8"))
    return tuple(mk for mk, d in decide.items() if d["pass"]), decide


def stage_card(n_placebo: int = 100) -> None:
    tip = tips()
    res = {}
    # 1. the worker re-fit
    mks, decide = pooled_markets(lab.WORK, "wk")
    P, PD, PL = scored("wk", "best"), scored("wk", "DK"), scored("wk", "live5")
    res["worker"] = {"markets": mks, "methods": {k: [v["method"], v["dist"], v["pass"]] for k, v in decide.items()},
                     **card_block(P, PD, PL, mks, tip, "worker", n_placebo=n_placebo)}
    # price floor -250 (needs the propositions rebuilt with the lower floor)
    lab.PRICE_FLOOR = -250.0
    P250 = lab.scored_propositions("wk")
    lab.PRICE_FLOOR = -200.0
    U = sort_ev(P250[P250.market.isin(mks) & (P250.side == "under")])
    for rule in ("game", "fc4"):
        res["worker"][f"{rule}|price_floor_-250"] = stats(select(U, 0.0, rule, tip), ci=False)
    # 2. the researcher's original model, the SAME card rules, read from his saved scores (not refit)
    omks, _ = pooled_markets(ORIG_WORK, "full")
    OP = pd.read_parquet(ORIG_WORK / "scored_full_best.parquet")
    OD = pd.read_parquet(ORIG_WORK / "scored_full_DK.parquet")
    res["original"] = {"markets": omks, **card_block(OP, OD, None, omks, tip, "original", n_placebo=0,
                                                     lean_checks=False)}
    # 3. overlap of the two cards
    w = select(sort_ev(P[P.market.isin(mks) & (P.side == "under")]), 0.0, "game", tip)
    o = select(sort_ev(OP[OP.market.isin(omks) & (OP.side == "under")]), 0.0, "game", tip)
    kw = set(zip(w.game_id, w.player_id.astype(str), w.market))
    ko = set(zip(o.game_id, o.player_id.astype(str), o.market))
    res["overlap_worker_vs_original_one_a_game"] = {"worker": len(kw), "original": len(ko), "shared": len(kw & ko),
                                                    "share_of_worker": round(len(kw & ko) / max(len(kw), 1), 3)}
    # 4. the card's bets by market, by his OFFICIAL status at the decision (what the worker cannot see)
    oq = pd.read_parquet(ORIG_WORK / "quotes.parquet", columns=["game_id", "player_id", "status"]).drop_duplicates(
        ["game_id", "player_id"]).rename(columns={"status": "official_status"})
    oq["pid"] = oq.player_id.astype(str)
    wb = w.assign(pid=w.player_id.astype(str)).merge(oq[["game_id", "pid", "official_status"]],
                                                     on=["game_id", "pid"], how="left")
    res["worker_by_official_status"] = wb.groupby(wb.official_status.fillna("none")).apply(
        lambda y: lab._agg(y)).reset_index().to_dict("records")
    res["worker_by_market"] = w.groupby("market").apply(lambda y: lab._agg(y)).reset_index().to_dict("records")
    (OUT / "card.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log("card written")
    print(json.dumps(res, indent=1, default=str)[:20000])


def stage_variants() -> None:
    """The model-specification spread on the worker inputs: the same card, the 12 count markets, the
    two-stage model throughout (rows comparable), refit with one change each."""
    tip = tips()
    P0 = scored("wk", "best")
    P0 = P0[P0.market.isin([s.market for s in nb.COUNT_SPECS])]
    rows, base = [], {}
    for v in VARIANT_RUNS:
        if not (lab.WORK / f"pred_{v}_2026.parquet").exists():
            log(f"{v}: no predictions, skipped")
            continue
        X, _ = lab._two_stage_props(v, P0)
        X = lab.grade(X) if "result" not in X.columns else X
        for rule in ("game", "fc4"):
            b = select(sort_ev(X[X.side == "under"]), 0.0, rule, tip)
            keys = set(zip(b.game_id, b.player_id.astype(str), b.market))
            if v == "wk":
                base[rule] = keys
            ov = len(keys & base.get(rule, set())) / max(len(keys), 1)
            rows.append({"variant": v, "rule": rule, "overlap_with_wk": round(ov, 3), **stats(b)})
            b.to_parquet(BETS / f"variant_{v}_{rule}.parquet")
        log(f"variant {v} done")
    A = pd.DataFrame(rows)
    A.to_parquet(OUT / "variants.parquet")
    print(A.to_string())


def stage_pinnacle() -> None:
    """How much of the card is the shipped Pinnacle rule, and what the model does where Pinnacle is silent."""
    tip = tips()
    mks, decide = pooled_markets(lab.WORK, "wk")
    P, PD = scored("wk", "best"), scored("wk", "DK")
    S = pd.read_parquet(PIN_RULE)
    S["player_id"] = S.player_id.astype(str)
    sk = set(zip(S.game_id, S.player_id, S.market))
    skl = set(zip(S.game_id, S.player_id, S.market, S.line))
    res = {}
    for rule in ("game", "fc4"):
        b = select(sort_ev(P[P.market.isin(mks) & (P.side == "under")]), 0.0, rule, tip)
        b = b.assign(pid=b.player_id.astype(str))
        k = list(zip(b.game_id, b.pid, b.market))
        b["in_pin_rule"] = [x in sk for x in k]
        b["in_pin_rule_same_line"] = [x in skl for x in zip(b.game_id, b.pid, b.market, b.line)]
        b["pin_market"] = ~b.market.isin(NON_PIN_MARKETS)
        b["pin_quote_same_line"] = b.ev_pin.notna()
        r = {"bets": int(b.result.isin(["W", "L", "P"]).sum()),
             "also_pin_rule_bets": int(b.in_pin_rule.sum()),
             "also_pin_rule_same_line": int(b.in_pin_rule_same_line.sum())}
        for lab_, sel in (("in_pin_rule", b.in_pin_rule), ("not_in_pin_rule", ~b.in_pin_rule),
                          ("pin_markets", b.pin_market), ("non_pin_markets", ~b.pin_market),
                          ("pin_quotes_line", b.pin_quote_same_line), ("no_pin_quote_at_line", ~b.pin_quote_same_line)):
            r[lab_] = stats(b[sel], ci=True)
        res[rule] = r
    # a card run ONLY over the markets Pinnacle does not price (new cell, chosen after seeing results)
    nm = tuple(m for m in mks if m in NON_PIN_MARKETS)
    res["non_pin_card"] = {"markets": nm, **card_block(P, PD, None, nm, tip, "worker_nonpin", n_placebo=100)}
    # each non-Pinnacle market's under rule, every player above the floor (no game limit): the cut
    # chosen on 2023-24 + 2024-25 from the worker grid, 2025-26 as found
    G = pd.read_parquet(lab.WORK / "grid_wk.parquet")
    ch = lab.choose_cut(G)
    per = []
    for m in NON_PIN_MARKETS:
        for st in ("player", "game"):
            r = ch[(ch.scope == m) & (ch.side == "under") & (ch.structure == st)]
            if r.empty:
                per.append({"market": m, "structure": st, "chosen": None})
                continue
            r = r.iloc[0]
            U = sort_ev(P[(P.market == m) & (P.side == "under")])
            UD = sort_ev(PD[(PD.market == m) & (PD.side == "under")])
            b = select(U, r.cut, st)
            b.to_parquet(BETS / f"nonpin_{m}_under_{st}_ev{r.cut:.2f}.parquet")
            g = G[(G.price == "best") & (G.scope == m) & (G.side == "under") & (G.structure == st)]
            nbr = g[g.cut.isin([c for c in lab.EV_CUTS if abs(c - r.cut) < 0.025 and c != r.cut])]
            per.append({"market": m, "structure": st, "cut": r.cut, **stats(b),
                        "dk": stats(select(UD, r.cut, st), ci=False),
                        "neighbour_roi": nbr.roi.round(2).tolist(),
                        "blind": lab.blind_same(P, (m,), "under")})
    res["non_pin_market_rules"] = per
    (OUT / "pinnacle.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str)[:20000])


# ── audit ────────────────────────────────────────────────────────────────────

FEATS = sorted(set(nb.OWN + nb.AVAIL + nb.SCHED + nb.TEAM + nb.LINES + nb.all_rates()
                   + [f"{b}_{s}" for b in ("sa", "l10", "ew") for s in nb.BASE_STATS] + ["status", "pos"]))


def _perturb(data: dict, cut: str, worker: bool, seed: int = 11) -> dict:
    """Outcomes of every game on or after `cut` scrambled: minutes and stats re-drawn, and 10% of the
    players who played turned into did-not-play. Rows strictly before `cut` and the decision inputs
    (schedule, report, odds) are untouched, so any feature on a row dated `cut` that moves is a leak."""
    rng = np.random.default_rng(seed)
    d = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in data.items()}
    stats_ = ["points", "rebounds", "offensive_reb", "defensive_reb", "assists", "steals", "blocks", "turnovers",
              "fg_made", "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att"]
    lg = d["nba_player_game_log"]
    late = pd.to_datetime(lg.game_date) >= pd.Timestamp(cut)
    for c in stats_ + ["minutes"]:
        lg.loc[late, c] = rng.permutation(lg.loc[late, c].values)
    adv = d["nba_player_game_adv"]
    alate = pd.to_datetime(adv.game_date) >= pd.Timestamp(cut)
    for c in ("minutes_exact", "usage_pct", "fouls"):
        if c in adv:
            adv.loc[alate, c] = rng.permutation(adv.loc[alate, c].values)
    drop = late & (rng.random(len(lg)) < 0.10)
    if worker:
        d["nba_player_game_log"] = lg[~drop]
        d["nba_player_game_adv"] = adv[~adv.set_index(["game_id", "player_id"]).index.isin(
            lg[drop].set_index(["game_id", "player_id"]).index)]
    else:
        flip = adv.set_index(["game_id", "player_id"]).index.isin(lg[drop].set_index(["game_id", "player_id"]).index)
        adv.loc[flip, "played"] = False
        adv.loc[flip, "minutes_exact"] = 0.0
        d["nba_player_game_log"] = lg[~drop]
        d["nba_player_game_adv"] = adv
    return d


def _restrict(data: dict, seasons: tuple) -> dict:
    d = dict(data)
    for k in ("nba_player_game_log", "nba_player_game_adv", "nba_game_inactives"):
        d[k] = d[k][d[k].season.isin(seasons)]
    d["nba_games"] = d["nba_games"][d["nba_games"].season.isin(seasons)]
    return d


def _compare(a: pd.DataFrame, b: pd.DataFrame, day: str) -> dict:
    k = ["game_id", "player_id"]
    x = a[pd.to_datetime(a.game_date) == pd.Timestamp(day)].set_index(k)
    y = b[pd.to_datetime(b.game_date) == pd.Timestamp(day)].set_index(k)
    common = x.index.intersection(y.index)
    out = {"rows_day": len(x), "rows_day_perturbed": len(y), "rows_compared": len(common), "moved": {}}
    for c in FEATS:
        if c not in x.columns or c not in y.columns:
            continue
        u, v = x.loc[common, c], y.loc[common, c]
        if u.dtype.kind in "fi" and v.dtype.kind in "fi":
            diff = ~(np.isclose(u.astype(float), v.astype(float), equal_nan=True))
        else:
            diff = ~((u.astype(str) == v.astype(str)))
        if diff.any():
            out["moved"][c] = int(diff.sum())
    return out


def stage_audit() -> None:
    res = {}
    seasons = (2025, 2026)
    day = "2026-01-15"
    raw = raw_cache()
    props = raw["nba_props"]
    dec = nb.decisions_for(raw, props[props.game_date < lab.LAST_RESEARCH_DATE])
    # A. the ORIGINAL frame builder on the ORIGINAL inputs
    base = _restrict({k: raw[k] for k in nb.TABLES}, seasons)
    f0 = nb.build_frame(base, dec, with_lines=False)
    f1 = nb.build_frame(_perturb(base, day, worker=False), dec, with_lines=False)
    res["original_builder_outcomes_scrambled_from_" + day] = _compare(f0, f1, day)
    log("audit A done")
    # B. the worker frame on worker inputs (the roster is inferred, so a removed box row also leaves the roster
    #    unless the history or the injury table holds him)
    wk = _restrict(worker_cache(), seasons)
    g0 = nb.build_frame(wk, dec, with_lines=False)
    pw = _perturb(wk, day, worker=True)
    # the inferred roster must be rebuilt from the perturbed log, as the worker would
    adv_p = pw["nba_player_game_adv"]
    ros = asof_roster(adv_p, {"nba_games": pw["nba_games"]}, pw["nba_injury_report"], dec)
    names = adv_p.drop_duplicates("player_id").set_index("player_id").player_name
    gm = pw["nba_games"].set_index("game_id")
    ina = ros[~ros.in_log][["game_id", "team", "player_id"]].copy()
    ina["player_name"], ina["season"] = ina.player_id.map(names), ina.game_id.map(gm.season)
    ina["game_date"], ina["game_type"] = ina.game_id.map(gm.game_date), "regular"
    pw["nba_game_inactives"] = ina
    g1 = nb.build_frame(pw, dec, with_lines=False)
    res["worker_builder_outcomes_scrambled_from_" + day] = _compare(g0, g1, day)
    log("audit B done")
    # C. the roster: who is on it only because he played tonight (the one outcome a box-built roster carries)
    ros_all = pd.read_parquet(lab.WORK / "asof_roster.parquet")
    fr = lab.load_frame()
    fr["player_id"] = fr.player_id.astype(str)
    key = set(zip(ros_all.game_id, ros_all.player_id))
    played = fr[fr.played & ~fr.upcoming]
    off = played[[k not in key for k in zip(played.game_id, played.player_id)]]
    ret_off = off[(off.miss_streak >= 1) & (off.tm_n > 0)]
    res["roster"] = {"played_rows": len(played), "played_rows_not_on_pregame_roster": len(off),
                     "of_which_counted_as_returning": len(ret_off),
                     "share_of_rows_with_tm_r_min_gt0": round(float((fr.tm_r_min > 0).mean()), 4)}
    # D. original vs worker frame on the priced rows: how far the availability inputs moved
    of = pd.read_parquet(ORIG_WORK / "frame.parquet", columns=["game_id", "player_id", "tm_o_min", "tm_r_min",
                                                               "tm_q_min", "min_l", "tm_min", "pos", "status"])
    of["player_id"] = of.player_id.astype(str)
    q = pd.read_parquet(lab.WORK / "quotes.parquet", columns=["game_id", "player_id"]).drop_duplicates()
    q["player_id"] = q.player_id.astype(str)
    m = q.merge(of, on=["game_id", "player_id"]).merge(
        fr[["game_id", "player_id", "tm_o_min", "tm_r_min", "tm_q_min", "min_l", "tm_min", "pos", "status"]],
        on=["game_id", "player_id"], suffixes=("_off", "_wk"))
    d = {}
    for c in ("tm_o_min", "tm_r_min", "tm_q_min", "min_l", "tm_min"):
        a_, b_ = m[f"{c}_off"], m[f"{c}_wk"]
        d[c] = {"corr": round(float(a_.corr(b_)), 4), "mean_off": round(float(a_.mean()), 3),
                "mean_wk": round(float(b_.mean()), 3), "mae": round(float((a_ - b_).abs().mean()), 3)}
    d["pos_agree"] = round(float((m.pos_off == m.pos_wk).mean()), 4)
    d["status_crosstab"] = pd.crosstab(m.status_off.fillna("none"), m.status_wk.fillna("none")).to_dict()
    res["official_vs_worker_frame_priced_rows"] = d
    # E. hand recompute of the 'latest played game strictly before' semantics on one player
    pid = fr[fr.played].player_id.value_counts().index[0]
    x = fr[fr.player_id == pid].sort_values("tip")
    pl_ = x[x.played & ~x.upcoming]
    e = pl_.minutes_exact.ewm(halflife=10.0).mean()
    manual = e.reindex(x.index).shift(1).ffill()
    res["hand_recompute_min_l"] = {"player_id": pid, "rows": len(x),
                                   "max_abs_diff": float(np.nanmax(np.abs(manual.values - x.min_l.values)))}
    (OUT / "audit.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


def stage_leakcheck() -> None:
    """The one outcome the inferred roster carries: a player who returns after more than ROSTER_DAYS days
    and is on no injury list enters his team's roster only by playing, and then counts in his teammates'
    'returning' minutes. Grade the card without every bet on a team-game where that happened."""
    tip = tips()
    ros = pd.read_parquet(lab.WORK / "asof_roster.parquet")
    fr = lab.load_frame()[["game_id", "player_id", "team", "played", "upcoming", "miss_streak", "tm_n",
                           "min_l", "tm_min", "status"]]
    fr["player_id"] = fr.player_id.astype(str)
    key = set(zip(ros.game_id, ros.player_id))
    pl = fr[fr.played & ~fr.upcoming]
    off = pl[[k not in key for k in zip(pl.game_id, pl.player_id)]]
    off = off[(off.miss_streak >= 1) & (off.tm_n > 0) & ((off.min_l - off.tm_min).clip(lower=0) > 0)]
    bad = off[["game_id", "team", "player_id"]].rename(columns={"player_id": "leaker"})
    mks, _ = pooled_markets(lab.WORK, "wk")
    P = scored("wk", "best")
    res = {"leak_rows": len(off), "leak_team_games": int(bad[["game_id", "team"]].drop_duplicates().shape[0])}
    for rule in ("game", "fc4"):
        b = select(sort_ev(P[P.market.isin(mks) & (P.side == "under")]), 0.0, rule, tip)
        b = b.drop(columns=[c for c in ("team",) if c in b.columns]).assign(pid=b.player_id.astype(str)).merge(
            fr[["game_id", "player_id", "team"]].rename(columns={"player_id": "pid"}), on=["game_id", "pid"], how="left")
        hit = b.merge(bad, on=["game_id", "team"], how="left")
        hit = hit[hit.leaker.notna() & (hit.leaker != hit.pid)][["game_id", "pid"]].drop_duplicates()
        hk = set(zip(hit.game_id, hit.pid))
        mask = np.array([k in hk for k in zip(b.game_id, b.pid)])
        res[rule] = {"bets_touched": int(mask.sum()), "touched": stats(b[mask], ci=False),
                     "untouched": stats(b[~mask])}
    (OUT / "leakcheck.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


def stage_settle_check() -> None:
    """Settlement must not depend on the worker inputs: the regenerated quotes against the researcher's."""
    a = pd.read_parquet(lab.WORK / "quotes.parquet", columns=["game_id", "player_id", "market", "bookmaker", "line",
                                                               "played", "actual", "usable", "status"])
    b = pd.read_parquet(ORIG_WORK / "quotes.parquet", columns=["game_id", "player_id", "market", "bookmaker", "line",
                                                                "played", "actual", "usable", "status"])
    for d in (a, b):
        d["player_id"] = d.player_id.astype(str)
    k = ["game_id", "player_id", "market", "bookmaker", "line"]
    m = a.merge(b, on=k, how="outer", suffixes=("_wk", "_off"), indicator=True)
    both = m[m._merge == "both"]
    res = {"rows_wk": len(a), "rows_off": len(b), "only_wk": int((m._merge == "left_only").sum()),
           "only_off": int((m._merge == "right_only").sum()),
           "played_disagree": int((both.played_wk != both.played_off).sum()),
           "actual_disagree": int((~np.isclose(both.actual_wk.astype(float), both.actual_off.astype(float),
                                               equal_nan=True)).sum()),
           "usable_wk_not_off": int((both.usable_wk & ~both.usable_off).sum()),
           "usable_off_not_wk": int((~both.usable_wk & both.usable_off).sum()),
           "status_crosstab": pd.crosstab(both.status_off.fillna("none"), both.status_wk.fillna("none")).to_dict()}
    (OUT / "settle_check.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, default=str))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["frame", "prices", "fit", "gate", "grid", "judge", "card", "variants",
                                      "pinnacle", "audit", "rescore", "checks", "settle", "lagcard", "leakcheck"])
    ap.add_argument("--variant", default="wk")
    ap.add_argument("--methods", default="all")
    ap.add_argument("--folds", default=",".join(map(str, lab.FOLDS)))
    ap.add_argument("--lines", action="store_true")
    ap.add_argument("--lag", type=int, default=0)
    ap.add_argument("--placebo", type=int, default=100)
    a = ap.parse_args()
    work = OUT / ("work" if a.lag == 0 else f"work_lag{a.lag}")
    setup(work, a.lag)
    t0 = time.time()
    if a.stage == "frame":
        stage_frame(a.lines, a.lag)
    elif a.stage == "prices":
        lab.stage_prices()
    elif a.stage == "fit":
        stage_fit(a.variant, a.methods, tuple(int(x) for x in a.folds.split(",")))
    elif a.stage == "gate":
        lab.stage_gate(a.variant)
    elif a.stage == "grid":
        lab.stage_grid(a.variant)
    elif a.stage == "judge":
        lab.stage_judge(a.variant, "pooled")
    elif a.stage == "card":
        stage_card(a.placebo)
    elif a.stage == "variants":
        stage_variants()
    elif a.stage == "pinnacle":
        stage_pinnacle()
    elif a.stage == "audit":
        stage_audit()
    elif a.stage == "rescore":
        stage_rescore(OUT / "work", a.variant)
    elif a.stage == "checks":
        lab.stage_checks()
    elif a.stage == "settle":
        stage_settle_check()
    elif a.stage == "leakcheck":
        stage_leakcheck()
    elif a.stage == "lagcard":
        tip = tips()
        mks, _ = pooled_markets(lab.WORK, "wk")
        P, PD = scored("wk", "best"), scored("wk", "DK")
        res = card_block(P, PD, None, mks, tip, f"worker_lag{a.lag}", n_placebo=0, lean_checks=False)
        (OUT / f"card_lag{a.lag}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(json.dumps(res, indent=1, default=str)[:6000])
    log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
