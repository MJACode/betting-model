"""NBA game-line lab: does schedule, availability or the referee crew add anything to the line?

Owner's question (mike, 2026-10-15): "scheduling is critical, just like it is
for NHL -- teams on a lot of road games in a row, back-to-backs, all of these
things need to be taken into consideration." This lab MEASURES that against the
market, on the pre-registered bars of docs/nba_models_2026.md section 1.

THE TEST
--------
A market-anchored logistic model. Target: home win (moneyline), home cover at
Pinnacle's spread, over at Pinnacle's total. Baseline: Pinnacle's no-vig
probability at the decision fetch (offset = its logit). Feature GROUPS are
added as residual predictors and ablated one at a time, walk-forward by season
(fit on seasons before S, grade S). Improvements are then translated into bets
at the best BETTABLE price at Pinnacle's number in the same fetch.

DECISION TIMES (inputs as of that fetch, never later)
  eve  the last evening-before fetch (22Z the day before .. 03Z on the ET game
       date, i.e. 6-11 pm ET) in which Pinnacle quotes the market
  d19  the 19Z fetch on the game date (3 pm ET; referee crews are public from
       ~9 am ET, injury reports from the afternoon)
  pre  the last fetch before tip (this is also Pinnacle's close)

STAGES (each caches to C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/)
  market    per (game, market, fetch) frame             gm_market_frame.parquet
  features  per (game, slot) inputs                     gm_features.parquet
  model     ablation + coefficients + walk-forward p    gm_model_*.parquet
  bets      EV grid, the bars, bet lists                gm_grid.parquet, gm_bets_*.parquet
  rules     the three published schedule spots, blind   gm_rules.parquet
  inline    "is the schedule in the line" diagnostics   gm_inline_*.parquet
  report    results/game_model.md

    PYTHONPATH=. python -m scripts.nba_game_model_lab --stage all
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import config
from features import nba_schedule_features as nsf
from tracking.discord_notifier import stake_for

CACHE = Path(__file__).resolve().parent.parent / "data" / "local" / "nba"
OUT = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/results")
OUT.mkdir(parents=True, exist_ok=True)

BETTABLE = list(config.BEST_LINE_BOOKMAKERS)          # pinnacle, bovada excluded by config
SHARP = "pinnacle"
MAX_AGE_MIN = int(config.PREGAME_PRICE_MAX_AGE_MIN)  # 180: production's stale-quote cut
MIN_ODDS = float(getattr(config, "DEFAULT_MIN_ODDS", -200.0))
COHERENT = (1.00, 1.15)
MARKETS = ("h2h", "spreads", "totals")
SLOTS = ("eve", "eve_soft", "d19", "pre")
GRADED = (2022, 2023, 2024, 2025, 2026)                # 2021-22 .. 2025-26
CONFIRM = 2026                                         # never used to choose anything
CHOOSE = (2022, 2023, 2024, 2025)
EV_STEPS = (0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06)
BOOT_N, BOOT_SEED = 4000, 7
SETTLE_H = 3.0                                         # a game counts as known 3h after tip


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ── prices ────────────────────────────────────────────────────────────────────

def implied(am):
    am = np.asarray(am, float)
    return np.where(am > 0, 100.0 / (am + 100.0), np.abs(am) / (np.abs(am) + 100.0))


def decimal(am):
    am = np.asarray(am, float)
    return np.where(am > 0, 1.0 + am / 100.0, 1.0 + 100.0 / np.abs(am))


def risk_units(dec):
    """Units laid to win one unit, capped at 3 (tracking.discord_notifier.stake_for)."""
    dec = np.asarray(dec, float)
    return np.minimum(1.0 / (dec - 1.0), 3.0)


def _check_stake_parity():
    for am in (-110, -105, 120, -400, 250, -300, -200):
        d = float(decimal([am])[0])
        r = float(risk_units([d])[0])
        assert abs(r - stake_for(1.0, am).risk) < 1e-9, (am, r, stake_for(1.0, am))


# ── data ──────────────────────────────────────────────────────────────────────

def load_games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "nba_games.parquet")
    g = g[(g["season"] <= 2026) & g["home_score"].notna()].copy()
    g["ct"] = pd.to_datetime(g["commence_time"], utc=True)
    g["gd"] = pd.to_datetime(g["game_date"])
    return g[["game_id", "season", "game_date", "gd", "ct", "home_team", "away_team",
              "home_score", "away_score", "went_to_ot"]]


def stage_market() -> pd.DataFrame:
    """Per (game, market, fetch): Pinnacle, soft consensus, best bettable price at Pinnacle's number."""
    _check_stake_parity()
    g = load_games()
    o = pd.read_parquet(CACHE / "nba_odds.parquet",
                        columns=["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at",
                                 "source", "created_at", "home_price", "away_price", "spread_home",
                                 "total_line", "over_price", "under_price"])
    o = o[(o["source"] == "odds_api_historical") & o["market"].isin(MARKETS)]
    o = o.merge(g[["game_id", "season", "gd", "ct"]], on="game_id", how="inner")
    n0 = len(o)
    o["sa"] = pd.to_datetime(o["snapshot_at"], utc=True, format="ISO8601")
    o = o[(o["snapshot_type"] != "in_play") & (o["sa"] <= o["ct"])]
    diag = {"rows_historical": int(n0), "rows_pregame": int(len(o))}

    # A FETCH is one historical request: rows sharing created_at for a game.
    fts = o.groupby(["game_id", "created_at"])["sa"].transform("max")
    o["fetch_ts"] = fts
    o["age_min"] = (o["fetch_ts"] - o["sa"]).dt.total_seconds() / 60.0
    diag["age_min_q"] = o["age_min"].quantile([.5, .9, .99, .999]).round(1).to_dict()
    diag["stale_by_book"] = (o.assign(st=o["age_min"] > MAX_AGE_MIN)
                             .groupby("bookmaker")["st"].mean().round(4).to_dict())
    diag["rows_stale_dropped"] = int((o["age_min"] > MAX_AGE_MIN).sum())
    o = o[o["age_min"] <= MAX_AGE_MIN]

    # Generic two-way: side A = home (h2h, spreads) / over (totals); B = away / under.
    is_tot = o["market"] == "totals"
    o["pa"] = np.where(is_tot, o["over_price"], o["home_price"])
    o["pb"] = np.where(is_tot, o["under_price"], o["away_price"])
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"],
                         np.where(is_tot, o["total_line"], 0.0))
    o = o[o["pa"].notna() & o["pb"].notna() & o["line"].notna()]
    ia, ib = implied(o["pa"]), implied(o["pb"])
    s = ia + ib
    coherent = (s >= COHERENT[0]) & (s <= COHERENT[1])
    diag["incoherent_by_book"] = (o.assign(inc=~coherent).groupby("bookmaker")["inc"].mean()
                                  .round(4).to_dict())
    diag["rows_incoherent_dropped"] = int((~coherent).sum())
    o = o[coherent].copy()
    o["nv_a"] = ia[coherent] / s[coherent]
    # One quote per (fetch, book, market): a duplicate keeps the latest snapshot.
    o = o.sort_values("sa").drop_duplicates(["game_id", "created_at", "market", "bookmaker"], keep="last")

    key = ["game_id", "created_at", "market"]
    pin = o[o["bookmaker"] == SHARP][key + ["line", "nv_a", "pa", "pb"]].rename(
        columns={"line": "pin_line", "nv_a": "pin_p", "pa": "pin_pa", "pb": "pin_pb"})
    soft = o[o["bookmaker"].isin(BETTABLE)].copy()

    # Soft consensus: modal line among bettable books in the fetch, median no-vig at it.
    lc = soft.groupby(key + ["line"]).size().rename("n").reset_index()
    lc["absl"] = lc["line"].abs()
    lc = lc.sort_values(key + ["n", "absl"], ascending=[True] * 3 + [False, True])
    modal = lc.drop_duplicates(key)[key + ["line", "n"]].rename(columns={"line": "cons_line", "n": "cons_n"})
    cons = soft.merge(modal, on=key)
    cons = cons[cons["line"] == cons["cons_line"]]
    cons_p = cons.groupby(key)["nv_a"].median().rename("cons_p").reset_index()

    def best_at(df: pd.DataFrame, ref: pd.DataFrame, ref_line: str, tag: str) -> pd.DataFrame:
        x = df.merge(ref[key + [ref_line]], on=key)
        x = x[x["line"] == x[ref_line]]
        x["da"], x["db"] = decimal(x["pa"]), decimal(x["pb"])
        ba = x.sort_values("da").drop_duplicates(key, keep="last")[key + ["pa", "bookmaker"]]
        bb = x.sort_values("db").drop_duplicates(key, keep="last")[key + ["pb", "bookmaker"]]
        dk = x[x["bookmaker"] == "draftkings"][key + ["pa", "pb"]]
        n = x.groupby(key).size().rename(f"{tag}_nbooks").reset_index()
        r = (ba.rename(columns={"pa": f"{tag}_best_a", "bookmaker": f"{tag}_book_a"})
             .merge(bb.rename(columns={"pb": f"{tag}_best_b", "bookmaker": f"{tag}_book_b"}), on=key, how="outer")
             .merge(dk.rename(columns={"pa": f"{tag}_dk_a", "pb": f"{tag}_dk_b"}), on=key, how="left")
             .merge(n, on=key, how="left"))
        return r

    best_pin = best_at(soft, pin, "pin_line", "bp")
    best_cons = best_at(soft, modal, "cons_line", "bc")
    nsoft = soft.groupby(key).size().rename("n_soft").reset_index()

    fr = (o.groupby(key).agg(fetch_ts=("fetch_ts", "first"), season=("season", "first"),
                             gd=("gd", "first"), ct=("ct", "first")).reset_index())
    fr = (fr.merge(pin, on=key, how="left").merge(modal, on=key, how="left")
          .merge(cons_p, on=key, how="left").merge(best_pin, on=key, how="left")
          .merge(best_cons, on=key, how="left").merge(nsoft, on=key, how="left"))
    fr["fetch_hour"] = fr["fetch_ts"].dt.round("h")
    fr["lead_h"] = (fr["ct"] - fr["fetch_ts"]).dt.total_seconds() / 3600.0
    fr["day_off"] = (fr["fetch_hour"].dt.tz_convert(None).dt.normalize() - fr["gd"]).dt.days
    fr["hour"] = fr["fetch_hour"].dt.hour
    # Two parallel ingest processes may write the same request twice: keep one per hour.
    fr = fr.sort_values("fetch_ts").drop_duplicates(["game_id", "market", "fetch_hour"], keep="last")
    fr.to_parquet(OUT / "gm_market_frame.parquet")
    diag["frame_rows"] = int(len(fr))
    diag["games_by_season"] = fr.groupby("season")["game_id"].nunique().to_dict()
    (OUT / "gm_market_diag.json").write_text(json.dumps(diag, indent=1, default=str))
    log("market frame", len(fr), json.dumps(diag, default=str)[:1500])
    return fr


def select_slots(fr: pd.DataFrame) -> pd.DataFrame:
    """Pick the decision fetch per (game, market, slot); attach Pinnacle's close."""
    fr = fr.copy()
    evening = (((fr["day_off"] == -1) & (fr["hour"] >= 22)) | ((fr["day_off"] == 0) & (fr["hour"] <= 3)))
    has_pin = fr["pin_p"].notna()
    out = []
    e = fr[evening & has_pin].sort_values("fetch_ts").drop_duplicates(["game_id", "market"], keep="last")
    out.append(e.assign(slot="eve"))
    d = fr[(fr["day_off"] == 0) & (fr["hour"] == 19) & has_pin]
    out.append(d.drop_duplicates(["game_id", "market"], keep="last").assign(slot="d19"))
    p = fr[has_pin].sort_values("fetch_ts").drop_duplicates(["game_id", "market"], keep="last")
    out.append(p.assign(slot="pre"))
    # eve_soft: the same evening window, baseline = the soft-book consensus (Pinnacle optional),
    # because Pinnacle quotes few games the evening before -- and fewer back-to-backs.
    es = fr[evening & (fr["cons_n"] >= 2)].sort_values("fetch_ts").drop_duplicates(["game_id", "market"], keep="last")
    out.append(es.assign(slot="eve_soft"))
    sel = pd.concat(out, ignore_index=True)
    soft_slot = sel["slot"] == "eve_soft"
    # Normalised decision columns: the reference line/probability and the prices AT that line.
    sel["mkt_line"] = np.where(soft_slot, sel["cons_line"], sel["pin_line"])
    sel["mkt_p"] = np.where(soft_slot, sel["cons_p"], sel["pin_p"])
    for c in ("best_a", "book_a", "best_b", "book_b", "dk_a", "dk_b", "nbooks"):
        sel[c] = np.where(soft_slot, sel[f"bc_{c}"], sel[f"bp_{c}"])
    close = p[["game_id", "market", "pin_line", "pin_p", "fetch_ts"]].rename(
        columns={"pin_line": "close_line", "pin_p": "close_p", "fetch_ts": "close_ts"})
    # Opener: first fetch for the game within 48h of tip (any book) -- "when the line opened".
    op = fr[fr["lead_h"] <= 48].sort_values("fetch_ts").drop_duplicates(["game_id"], keep="first")
    op = op[["game_id", "fetch_ts"]].rename(columns={"fetch_ts": "open_ts"})
    pin_open = fr[has_pin & (fr["lead_h"] <= 48)].sort_values("fetch_ts").drop_duplicates(["game_id", "market"])
    pin_open = pin_open[["game_id", "market", "pin_line", "pin_p", "fetch_ts"]].rename(
        columns={"pin_line": "pin_open_line", "pin_p": "pin_open_p", "fetch_ts": "pin_open_ts"})
    sel = sel.merge(close, on=["game_id", "market"], how="left").merge(op, on="game_id", how="left")
    sel = sel.merge(pin_open, on=["game_id", "market"], how="left")
    return sel


# ── features as of the decision time ──────────────────────────────────────────

VALID_STATUS = {"Out", "Doubtful", "Questionable", "Probable", "Available", "NOT YET SUBMITTED"}
HL_PLAYER = 8      # EWM half-life in games for player minutes / impact
HL_TEAM = 5        # EWM half-life in games for team form
REF_K = 50.0       # referee shrinkage: prior weight in games


def _schedule_ct() -> pd.DataFrame:
    s = pd.read_parquet(CACHE / "nba_schedule.parquet", columns=["game_id", "commence_time", "game_type", "season",
                                                                 "home_team", "away_team"])
    s["ct"] = pd.to_datetime(s["commence_time"], utc=True)
    return s


def player_value_timeline() -> pd.DataFrame:
    """One row per player game PLAYED: EWM minutes and impact INCLUDING that game, known at tip + 3h."""
    a = pd.read_parquet(CACHE / "nba_player_game_adv.parquet",
                        columns=["game_id", "player_id", "player_name", "team", "played", "minutes_exact", "pie",
                                 "is_starter"])
    s = _schedule_ct()[["game_id", "ct"]].drop_duplicates("game_id")
    a = a.merge(s, on="game_id", how="inner")
    a = a[(a["played"] == True) & (a["minutes_exact"] > 0)].sort_values(["player_id", "ct"])  # noqa: E712
    a["pie_c"] = a["pie"].clip(-0.1, 0.4)
    g = a.groupby("player_id", sort=False)
    a["min_ewm"] = g["minutes_exact"].transform(lambda x: x.ewm(halflife=HL_PLAYER).mean())
    a["pie_ewm"] = g["pie_c"].transform(lambda x: x.ewm(halflife=HL_PLAYER).mean())
    a["n_games"] = g.cumcount() + 1
    a["known_ts"] = a["ct"] + pd.Timedelta(hours=SETTLE_H)
    a = a.rename(columns={"ct": "last_ct"})
    return a[["player_id", "player_name", "team", "known_ts", "last_ct", "min_ewm", "pie_ewm", "n_games"]]


def team_last_game() -> pd.DataFrame:
    s = _schedule_ct()
    s = s[s["game_type"].isin(["regular", "cup_final", "playin", "playoff"])]
    t = pd.concat([s[["home_team", "ct"]].rename(columns={"home_team": "team"}),
                   s[["away_team", "ct"]].rename(columns={"away_team": "team"})])
    t["known_ts"] = t["ct"] + pd.Timedelta(hours=SETTLE_H)
    return t.rename(columns={"ct": "team_last_ct"}).sort_values("known_ts")


def availability(q: pd.DataFrame, pv: pd.DataFrame, tl: pd.DataFrame, inj: pd.DataFrame) -> pd.DataFrame:
    """q: (qid, game_id, team, ts). Returns per qid the as-of availability sums.

    Status = the latest injury report with report_ts <= ts in which the team
    SUBMITTED for that game (a NOT YET SUBMITTED team carries no information,
    so has_report = 0 and the sums are NaN -> filled 0 with the flag kept).
    Player value = EWM minutes / impact from games completed before ts.
    """
    sub = inj[inj["status"] != "NOT YET SUBMITTED"][["game_id", "team", "report_ts"]].drop_duplicates()
    sub = sub.sort_values("report_ts")
    qq = q.sort_values("ts")
    m = pd.merge_asof(qq, sub.rename(columns={"report_ts": "rts"}), left_on="ts", right_on="rts",
                      by=["game_id", "team"], direction="backward")
    m["has_report"] = m["rts"].notna().astype(int)
    m["rgid"] = np.where(m["rts"].notna(), m["game_id"], None)
    # No report for THIS game yet (the first one lands ~35h before tip): carry the team's
    # latest submitted report for ANY game, which is what the book also knew then.
    miss = m["rts"].isna()
    if miss.any():
        anyg = sub.rename(columns={"report_ts": "rts2", "game_id": "rgid2"}).sort_values("rts2")
        fb = pd.merge_asof(m.loc[miss, ["qid", "team", "ts"]].sort_values("ts"), anyg, left_on="ts",
                           right_on="rts2", by="team", direction="backward").set_index("qid")
        mi = m.set_index("qid")
        mi.loc[fb.index, "rts"] = fb["rts2"]
        mi.loc[fb.index, "rgid"] = fb["rgid2"]
        m = mi.reset_index()
    rows = m[m["rts"].notna()].merge(
        inj[["game_id", "team", "report_ts", "player_id", "player_name", "status"]].rename(
            columns={"game_id": "rgid"}),
        left_on=["rgid", "team", "rts"], right_on=["rgid", "team", "report_ts"])
    rows = rows[rows["status"].isin(["Out", "Doubtful", "Questionable"])].copy()
    # Name fallback for the ~1% of report rows without a player_id.
    name_map = pv.drop_duplicates("player_name", keep="last").set_index("player_name")["player_id"]
    rows["pid"] = rows["player_id"].fillna(rows["player_name"].map(name_map))
    rows["unvalued"] = rows["pid"].isna().astype(int)
    rv = rows[rows["pid"].notna()].sort_values("ts")
    pvs = pv.rename(columns={"player_id": "pid"}).sort_values("known_ts")
    rv = pd.merge_asof(rv, pvs[["pid", "known_ts", "last_ct", "min_ewm", "pie_ewm"]], left_on="ts",
                       right_on="known_ts", by="pid", direction="backward")
    tls = tl[["team", "known_ts", "team_last_ct"]].rename(columns={"known_ts": "tk"}).sort_values("tk")
    rv = pd.merge_asof(rv.sort_values("ts"), tls, left_on="ts", right_on="tk", by="team", direction="backward")
    rv["min_ewm"] = rv["min_ewm"].fillna(0.0)
    rv["pie_ewm"] = rv["pie_ewm"].fillna(0.0)
    rv["new"] = (rv["last_ct"].notna() & (rv["last_ct"] == rv["team_last_ct"])).astype(int)
    od = rv["status"].isin(["Out", "Doubtful"])
    rv["o_min"] = np.where(od, rv["min_ewm"], 0.0)
    rv["o_pie"] = np.where(od, rv["pie_ewm"], 0.0)
    rv["q_min"] = np.where(~od, rv["min_ewm"], 0.0)
    rv["o_new_min"] = np.where(od & (rv["new"] == 1), rv["min_ewm"], 0.0)
    agg = rv.groupby("qid")[["o_min", "o_pie", "q_min", "o_new_min"]].sum()
    unv = rows.groupby("qid")["unvalued"].sum().rename("n_unvalued")
    out = m[["qid", "has_report"]].set_index("qid").join(agg).join(unv)
    return out.fillna(0.0).reset_index()


def referee_tendencies(games: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Per game: crew means of shrunk tendencies from games on EARLIER dates only.

    tot_resid  actual total - Pinnacle close total
    cov_resid  home margin + Pinnacle close spread (the home cover margin)
    foul_dev   total personal fouls - the league mean of the previous 300 games
    Each official's value = sum(x) / (n + REF_K) over his earlier games
    (shrunk toward 0); the crew value is the mean over the game's officials.
    """
    o = pd.read_parquet(CACHE / "nba_game_officials.parquet", columns=["game_id", "official_id", "game_type"])
    o = o[o["game_type"].isin(["regular", "cup_final"])]
    adv = pd.read_parquet(CACHE / "nba_player_game_adv.parquet", columns=["game_id", "fouls"])
    fouls = adv.groupby("game_id")["fouls"].sum().rename("fouls")
    g = games.merge(close, on="game_id", how="left").set_index("game_id").join(fouls).reset_index()
    g = g.sort_values("ct")
    g["tot_resid"] = g["home_score"] + g["away_score"] - g["close_total"]
    g["cov_resid"] = (g["home_score"] - g["away_score"]) + g["close_spread"]
    g["foul_dev"] = g["fouls"] - g["fouls"].shift(1).rolling(300, min_periods=50).mean()
    x = o.merge(g[["game_id", "gd", "tot_resid", "cov_resid", "foul_dev"]], on="game_id").sort_values("gd")
    # per official, per DATE sums (several games a date never happens for one official, but be safe)
    vals = ["tot_resid", "cov_resid", "foul_dev"]
    d = x.groupby(["official_id", "gd"]).agg(**{f"s_{v}": (v, "sum") for v in vals},
                                             **{f"n_{v}": (v, "count") for v in vals}).reset_index()
    d = d.sort_values(["official_id", "gd"])
    for v in vals:
        d[f"cs_{v}"] = d.groupby("official_id")[f"s_{v}"].cumsum() - d[f"s_{v}"]
        d[f"cn_{v}"] = d.groupby("official_id")[f"n_{v}"].cumsum() - d[f"n_{v}"]
        d[f"ref_{v}"] = d[f"cs_{v}"] / (d[f"cn_{v}"] + REF_K)
    # value as of a game's date = the official's row on that date (cumsum excludes the date itself)
    xo = x[["game_id", "official_id", "gd"]].merge(d[["official_id", "gd"] + [f"ref_{v}" for v in vals]],
                                                    on=["official_id", "gd"], how="left")
    crew = xo.groupby("game_id")[[f"ref_{v}" for v in vals]].mean()
    crew["n_officials"] = xo.groupby("game_id").size()
    return crew.reset_index()


def team_form_timeline(games: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Per team game: EWM ATS residual, O/U residual and pace INCLUDING the game, known at tip + 3h."""
    lg = pd.read_parquet(CACHE / "nba_player_game_log.parquet",
                         columns=["game_id", "team", "fg_att", "offensive_reb", "turnovers", "ft_att"])
    poss = lg.groupby(["game_id", "team"]).sum(numeric_only=True)
    poss = (poss["fg_att"] - poss["offensive_reb"] + poss["turnovers"] + 0.44 * poss["ft_att"]).rename("poss")
    g = games.merge(close, on="game_id", how="left")
    rows = []
    for side, sign in (("home", 1), ("away", -1)):
        t = g[["game_id", "ct", "season"]].copy()
        t["team"] = g[f"{side}_team"]
        margin = sign * (g["home_score"] - g["away_score"])
        t["ats"] = margin + sign * g["close_spread"]
        t["ou"] = g["home_score"] + g["away_score"] - g["close_total"]
        rows.append(t)
    t = pd.concat(rows).merge(poss.reset_index(), on=["game_id", "team"], how="left").sort_values("ct")
    t["poss_dev"] = t["poss"] - t["poss"].shift(1).rolling(600, min_periods=100).mean()
    t = t.sort_values(["team", "ct"])
    grp = t.groupby("team", sort=False)
    for v in ("ats", "ou", "poss_dev"):
        t[f"f_{v}"] = grp[v].transform(lambda x: x.ewm(halflife=HL_TEAM, ignore_na=True).mean())
    t["known_ts"] = t["ct"] + pd.Timedelta(hours=SETTLE_H)
    return t[["team", "known_ts", "f_ats", "f_ou", "f_poss_dev"]].sort_values("known_ts")


def stage_features() -> pd.DataFrame:
    games = load_games()
    fr = pd.read_parquet(OUT / "gm_market_frame.parquet")
    sel = select_slots(fr)
    pre = sel[sel["slot"] == "pre"]
    close = (pre[pre["market"] == "spreads"][["game_id", "pin_line"]].rename(columns={"pin_line": "close_spread"})
             .merge(pre[pre["market"] == "totals"][["game_id", "pin_line"]].rename(columns={"pin_line": "close_total"}),
                    on="game_id", how="outer"))
    sched = pd.read_parquet(CACHE / "nba_schedule.parquet")
    gf = nsf.game_schedule_features(sched)
    tf = nsf.team_schedule_features(sched)

    q = sel[["game_id", "market", "slot", "fetch_ts", "open_ts"]].copy()
    q["qid"] = np.arange(len(q))
    q = q.merge(games[["game_id", "home_team", "away_team", "ct", "went_to_ot"]], on="game_id")

    # Load (result-gated): previous game's overtime, known only once it has finished.
    prev = tf[["game_id", "team", "prev_ct", "season", "game_no"]].copy()
    tf_sorted = tf.sort_values(["season", "team", "game_no"])
    tf_sorted["prev_game_id"] = tf_sorted.groupby(["season", "team"])["game_id"].shift(1)
    prev = tf_sorted[["game_id", "team", "prev_ct", "prev_game_id"]]
    ot = games.set_index("game_id")["went_to_ot"]
    prev = prev.assign(prev_ot_raw=prev["prev_game_id"].map(ot))
    for side in ("home", "away"):
        p = prev.rename(columns={"team": f"{side}_team", "prev_ct": f"{side}_pct",
                                 "prev_ot_raw": f"{side}_pot"})[["game_id", f"{side}_team", f"{side}_pct", f"{side}_pot"]]
        q = q.merge(p, on=["game_id", f"{side}_team"], how="left")
        known = q[f"{side}_pct"].notna() & ((q[f"{side}_pct"] + pd.Timedelta(hours=SETTLE_H)) <= q["fetch_ts"])
        q[f"{side}_prev_known"] = (known | q[f"{side}_pct"].isna()).astype(int)
        q[f"{side}_prev_ot"] = np.where(known, q[f"{side}_pot"].fillna(0), 0.0)

    # Availability at the decision and at the opener.
    log("availability ...")
    inj = pd.read_parquet(CACHE / "nba_injury_report.parquet",
                          columns=["report_ts", "game_id", "team", "player_id", "player_name", "status"])
    inj = inj[inj["status"].isin(VALID_STATUS) & inj["game_id"].notna()]
    pv = player_value_timeline()
    tl = team_last_game()
    av_parts = []
    for side in ("home", "away"):
        for when, col in (("dec", "fetch_ts"), ("open", "open_ts")):
            qq = q[["qid", "game_id", f"{side}_team", col]].rename(columns={f"{side}_team": "team", col: "ts"})
            qq = qq[qq["ts"].notna()]
            av = availability(qq, pv, tl, inj).set_index("qid")
            av.columns = [f"{side}_{when}_{c}" for c in av.columns]
            av_parts.append(av)
    av = pd.concat(av_parts, axis=1)
    q = q.set_index("qid").join(av).reset_index()

    # Referees (posted ~9am ET on game day): usable at d19 / pre, never at eve.
    log("referees ...")
    refs = referee_tendencies(games, close)
    q = q.merge(refs, on="game_id", how="left")
    for c in ("ref_tot_resid", "ref_cov_resid", "ref_foul_dev"):
        q[c] = np.where(q["slot"].isin(["eve", "eve_soft"]), 0.0, q[c].fillna(0.0))

    # Team form / pace as of the decision.
    log("form ...")
    ft = team_form_timeline(games, close)
    for side in ("home", "away"):
        qs = q[["qid", f"{side}_team", "fetch_ts"]].rename(columns={f"{side}_team": "team"}).sort_values("fetch_ts")
        m = pd.merge_asof(qs, ft, left_on="fetch_ts", right_on="known_ts", by="team", direction="backward")
        m = m.set_index("qid")[["f_ats", "f_ou", "f_poss_dev"]]
        m.columns = [f"{side}_{c}" for c in m.columns]
        q = q.set_index("qid").join(m).reset_index()

    q = q.merge(gf.drop(columns=["season", "home_team", "away_team"]), on="game_id", how="left")
    q.to_parquet(OUT / "gm_features.parquet")
    log("features", q.shape)
    return q


# ── the residual model ────────────────────────────────────────────────────────

SIDE_GROUPS = {
    "S": ["home_b2b", "away_b2b", "rest_diff", "home_3in4", "away_3in4", "home_travel_k", "away_travel_k",
          "home_east", "away_east", "home_west", "away_west", "home_g7", "away_g7", "away_road_no",
          "away_trip_len", "home_stand_no", "home_first_after3", "at_altitude", "alt_vs_tired",
          "away_tz_from_home", "early_tip", "season_day_c", "post_all_star", "nba_cup", "neutral"],
    "S_core": ["home_b2b", "away_b2b", "rest_diff", "away_travel_k", "away_east", "alt_vs_tired"],
    "L": ["home_prev_ot", "away_prev_ot"],
    "A": ["d_o_min", "d_o_pie", "d_q_min", "d_o_new"],
    "C": ["dd_o_min", "dd_o_pie"],
    "R": ["ref_cov"],
    "F": ["d_f_ats"],
}
TOT_GROUPS = {
    "S": ["sum_b2b", "both_b2b", "sum_rest", "sum_3in4", "sum_travel_k", "sum_east", "sum_west", "sum_g7",
          "away_road_no", "at_altitude", "early_tip", "season_day_c", "post_all_star", "nba_cup", "neutral"],
    "S_core": ["sum_b2b", "both_b2b", "sum_travel_k", "at_altitude"],
    "L": ["sum_prev_ot"],
    "A": ["s_o_min", "s_o_pie", "s_q_min", "s_o_new"],
    "C": ["sd_o_min", "sd_o_pie"],
    "R": ["ref_tot", "ref_foul"],
    "F": ["s_f_ou", "s_f_pace"],
}
ALL_GROUPS = ("S", "L", "A", "C", "R", "F")
ABLATION = ("M", "M_int", "M_recal", "S_core", "S", "L", "A", "C", "R", "F", "all", "S_r", "all_r")
# Bets use the market alone and the RIDGE fits ("_r"): decided 2026-10-15 after the unpenalised
# ablation on partial data showed 25 inputs on one training season overfit badly, and BEFORE
# any bet grid was run. The ridge penalty (intercept included) is chosen by leave-one-season-out
# inside the training seasons, so at a large penalty the model collapses to the market alone.
BET_VARIANTS = ("M", "S_r", "all_r")
RIDGE_GRID = (0.0, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0)


def groups_for(market: str) -> dict:
    return TOT_GROUPS if market == "totals" else SIDE_GROUPS


def features_for(market: str, variant: str) -> list[str]:
    gs = groups_for(market)
    variant = variant[:-2] if variant.endswith("_r") else variant
    if variant == "all":
        return [c for g in ALL_GROUPS for c in gs[g]]
    return list(gs.get(variant, []))


def design(q: pd.DataFrame) -> pd.DataFrame:
    """Model inputs. Side markets use home and away terms; totals use sums. NaN -> 0."""
    d = pd.DataFrame(index=q.index)
    k = 1000.0
    for s in ("home", "away"):
        d[f"{s}_b2b"] = q[f"{s}_b2b"]
        d[f"{s}_3in4"] = q[f"{s}_is_3in4"]
        d[f"{s}_travel_k"] = q[f"{s}_travel_mi"] / k
        d[f"{s}_east"] = q[f"{s}_east_shift"]
        d[f"{s}_west"] = q[f"{s}_west_shift"]
        d[f"{s}_g7"] = q[f"{s}_g_last7"]
        d[f"{s}_prev_ot"] = q[f"{s}_prev_ot"]
    d["rest_diff"] = q["rest_diff"]
    d["away_road_no"] = q["away_road_game_no"]
    d["away_trip_len"] = q["away_road_trip_len"]
    d["home_stand_no"] = q["home_home_game_no"]
    d["home_first_after3"] = q["home_first_home_after3"]
    for c in ("at_altitude", "alt_vs_tired", "early_tip", "post_all_star", "nba_cup", "neutral", "both_b2b"):
        d[c] = q[c]
    d["away_tz_from_home"] = q["away_tz_from_home"]
    d["season_day_c"] = q["days_since_open"] / 100.0
    d["sum_b2b"] = q["home_b2b"] + q["away_b2b"]
    d["sum_rest"] = q["home_rest_days"] + q["away_rest_days"]
    d["sum_3in4"] = q["home_is_3in4"] + q["away_is_3in4"]
    d["sum_travel_k"] = (q["home_travel_mi"] + q["away_travel_mi"]) / k
    d["sum_east"] = q["home_east_shift"] + q["away_east_shift"]
    d["sum_west"] = q["home_west_shift"] + q["away_west_shift"]
    d["sum_g7"] = q["home_g_last7"] + q["away_g_last7"]
    d["sum_prev_ot"] = q["home_prev_ot"] + q["away_prev_ot"]
    h, a = "home_dec_", "away_dec_"
    d["d_o_min"] = (q[h + "o_min"] - q[a + "o_min"]) / 48
    d["d_o_pie"] = q[h + "o_pie"] - q[a + "o_pie"]
    d["d_q_min"] = (q[h + "q_min"] - q[a + "q_min"]) / 48
    d["d_o_new"] = (q[h + "o_new_min"] - q[a + "o_new_min"]) / 48
    d["s_o_min"] = (q[h + "o_min"] + q[a + "o_min"]) / 48
    d["s_o_pie"] = q[h + "o_pie"] + q[a + "o_pie"]
    d["s_q_min"] = (q[h + "q_min"] + q[a + "q_min"]) / 48
    d["s_o_new"] = (q[h + "o_new_min"] + q[a + "o_new_min"]) / 48
    has_open = q["open_ts"].notna()
    ch_m = {s: np.where(has_open, q[f"{s}_dec_o_min"] - q[f"{s}_open_o_min"], 0.0) for s in ("home", "away")}
    ch_p = {s: np.where(has_open, q[f"{s}_dec_o_pie"] - q[f"{s}_open_o_pie"], 0.0) for s in ("home", "away")}
    d["dd_o_min"] = (ch_m["home"] - ch_m["away"]) / 48
    d["dd_o_pie"] = ch_p["home"] - ch_p["away"]
    d["sd_o_min"] = (ch_m["home"] + ch_m["away"]) / 48
    d["sd_o_pie"] = ch_p["home"] + ch_p["away"]
    d["ref_cov"] = q["ref_cov_resid"]
    d["ref_tot"] = q["ref_tot_resid"]
    d["ref_foul"] = q["ref_foul_dev"]
    d["d_f_ats"] = q["home_f_ats"] - q["away_f_ats"]
    d["s_f_ou"] = q["home_f_ou"] + q["away_f_ou"]
    d["s_f_pace"] = q["home_f_poss_dev"] + q["away_f_poss_dev"]
    return d.astype(float).fillna(0.0)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


def build_panel() -> pd.DataFrame:
    """(game, market, slot) rows: market reference, prices, close, target, design matrix."""
    games = load_games()
    fr = pd.read_parquet(OUT / "gm_market_frame.parquet")
    sel = select_slots(fr)
    q = pd.read_parquet(OUT / "gm_features.parquet")
    keep = ["game_id", "market", "slot", "fetch_ts", "lead_h", "mkt_line", "mkt_p", "best_a", "book_a", "best_b",
            "book_b", "dk_a", "dk_b", "nbooks", "close_line", "close_p", "pin_line", "pin_p", "pin_open_line",
            "pin_open_p", "cons_line", "cons_p"]
    x = sel[keep].merge(q.drop(columns=["fetch_ts", "open_ts"]), on=["game_id", "market", "slot"], how="inner")
    x = x.merge(games[["game_id", "season", "gd", "ct", "home_score", "away_score"]], on="game_id")
    x = x.merge(q[["game_id", "market", "slot", "open_ts"]], on=["game_id", "market", "slot"], how="left")
    hs, as_ = x["home_score"], x["away_score"]
    x["margin_vs_line"] = np.select(
        [x["market"] == "h2h", x["market"] == "spreads"],
        [hs - as_, (hs - as_) + x["mkt_line"]],
        (hs + as_) - x["mkt_line"])
    x["push"] = (x["margin_vs_line"] == 0).astype(int)
    x["y"] = (x["margin_vs_line"] > 0).astype(int)
    x = x[x["mkt_p"].notna()].reset_index(drop=True)
    d = design(x)
    d.columns = ["x_" + c for c in d.columns]
    return pd.concat([x, d], axis=1)


def _ridge_fit(X: np.ndarray, y: np.ndarray, off: np.ndarray, lam: float) -> np.ndarray:
    """Logistic regression with an offset: mean log loss + lam/2 * ||b||^2 (intercept included)."""
    from scipy.optimize import minimize

    def f(b):
        z = off + X @ b
        p = sigmoid(z)
        ll = np.mean(np.logaddexp(0, z) - y * z)
        g = X.T @ (p - y) / len(y) + lam * b
        return ll + 0.5 * lam * b @ b, g

    r = minimize(f, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B")
    return r.x


def _std(X: pd.DataFrame, mu=None, sd=None):
    if mu is None:
        mu, sd = X.mean(), X.std()
        keep = [c for c in X.columns if sd[c] > 1e-9]
        mu, sd = mu[keep], sd[keep]
    Z = ((X[list(mu.index)] - mu) / sd).to_numpy(float)
    return np.column_stack([np.ones(len(X)), Z]), mu, sd


def fit_ridge(df: pd.DataFrame, cols: list[str]):
    """Ridge with the penalty chosen by leave-one-season-out inside the training seasons
    (a date split into halves when only one training season exists)."""
    X = df[["x_" + c for c in cols]]
    y = df["y"].to_numpy(float)
    off = logit(df["mkt_p"])
    seasons = sorted(df["season"].unique())
    if len(seasons) >= 2:
        folds = [df["season"].to_numpy() == s for s in seasons]
    else:
        med = df["gd"].median()
        folds = [(df["gd"] < med).to_numpy(), (df["gd"] >= med).to_numpy()]
    best = (np.inf, None)
    for lam in RIDGE_GRID:
        tot, n = 0.0, 0
        for te in folds:
            tr = ~te
            Xtr, mu, sd = _std(X[tr])
            b = _ridge_fit(Xtr, y[tr], off[tr], lam)
            Xte, _, _ = _std(X[te], mu, sd)
            z = off[te] + Xte @ b
            tot += np.sum(np.logaddexp(0, z) - y[te] * z)
            n += te.sum()
        if tot / n < best[0]:
            best = (tot / n, lam)
    lam = best[1]
    Xa, mu, sd = _std(X)
    return ("ridge", _ridge_fit(Xa, y, off, lam), mu, sd, lam)


def fit_glm(df: pd.DataFrame, cols: list[str], variant: str):
    import statsmodels.api as sm
    off = logit(df["mkt_p"])
    if variant == "M":
        return None
    if variant.endswith("_r"):
        return fit_ridge(df, cols)
    if variant == "M_recal":
        X = sm.add_constant(pd.DataFrame({"mlogit": off}, index=df.index), has_constant="add")
        return sm.GLM(df["y"], X, family=sm.families.Binomial()).fit(), None, None
    X = df[["x_" + c for c in cols]].copy() if cols else pd.DataFrame(index=df.index)
    mu, sd = X.mean(), X.std()
    keepc = [c for c in X.columns if sd[c] > 1e-9]
    X = ((X[keepc] - mu[keepc]) / sd[keepc])
    X = sm.add_constant(X, has_constant="add")
    m = sm.GLM(df["y"], X, family=sm.families.Binomial(), offset=off).fit()
    return m, mu[keepc], sd[keepc]


def predict_glm(fit, df: pd.DataFrame, variant: str) -> np.ndarray:
    import statsmodels.api as sm
    off = logit(df["mkt_p"])
    if variant == "M":
        return np.asarray(df["mkt_p"], float)
    if variant.endswith("_r"):
        _, b, mu, sd, _lam = fit
        Xte, _, _ = _std(df[list(mu.index)], mu, sd)
        return sigmoid(off + Xte @ b)
    m, mu, sd = fit
    if variant == "M_recal":
        X = sm.add_constant(pd.DataFrame({"mlogit": off}, index=df.index), has_constant="add")
        return np.asarray(m.predict(X))
    X = df[list(mu.index)] if len(mu) else pd.DataFrame(index=df.index)
    X = (X - mu) / sd
    X = sm.add_constant(X, has_constant="add")
    return sigmoid(np.asarray(X @ m.params.values) + off)


def stage_model() -> None:
    panel = build_panel()
    panel = panel[panel["season"] >= 2021]
    preds, abl = [], []
    for market in MARKETS:
        for slot in SLOTS:
            sub = panel[(panel["market"] == market) & (panel["slot"] == slot) & (panel["push"] == 0)]
            for S in GRADED:
                tr, te = sub[sub["season"] < S], sub[sub["season"] == S]
                if len(te) == 0 or len(tr) < 100:
                    continue
                base = te[["game_id", "market", "slot", "season"]].copy()
                for v in ABLATION:
                    cols = features_for(market, v) if v not in ("M", "M_int", "M_recal") else []
                    f = fit_glm(tr, cols, v)
                    p = predict_glm(f, te, v)
                    lam = f[4] if (f is not None and v.endswith("_r")) else np.nan
                    pr = np.clip(p, 1e-6, 1 - 1e-6)
                    yy = te["y"].to_numpy()
                    ll = -(yy * np.log(pr) + (1 - yy) * np.log(1 - pr))
                    abl.append({"market": market, "slot": slot, "season": S, "variant": v, "n": len(te),
                                "n_train": len(tr), "logloss": ll.mean(), "brier": ((pr - yy) ** 2).mean(),
                                "ridge_lambda": lam})
                    base[f"p_{v}"] = p
                    base[f"ll_{v}"] = ll
                preds.append(base.assign(gd=te["gd"].values))
            log("model", market, slot)
    pd.concat(preds).to_parquet(OUT / "gm_model_preds.parquet")
    pd.DataFrame(abl).to_parquet(OUT / "gm_model_ablation.parquet")
    coefs = []
    import statsmodels.api as sm  # noqa: F401
    for fit_seasons, tag in (((2021, 2022, 2023, 2024, 2025), "fit_2021_2025"), (tuple(range(2021, 2027)), "fit_all")):
        for market in MARKETS:
            for slot in SLOTS:
                sub = panel[(panel["market"] == market) & (panel["slot"] == slot) & (panel["push"] == 0)
                            & panel["season"].isin(fit_seasons)]
                for v in ("S", "all"):
                    cols = features_for(market, v)
                    X = sub[["x_" + c for c in cols]]
                    keepc = [c for c in X.columns if X[c].std() > 1e-9]
                    Xc = sm.add_constant(X[keepc], has_constant="add")
                    m = sm.GLM(sub["y"], Xc, family=sm.families.Binomial(), offset=logit(sub["mkt_p"])).fit()
                    ci = m.conf_int(0.10)
                    for name in m.params.index:
                        coefs.append({"fit": tag, "market": market, "slot": slot, "variant": v,
                                      "feature": name.replace("x_", ""), "coef": m.params[name],
                                      "lo90": ci.loc[name, 0], "hi90": ci.loc[name, 1], "p": m.pvalues[name],
                                      "mean": X[name].mean() if name in X else np.nan,
                                      "n": len(sub)})
    pd.DataFrame(coefs).to_parquet(OUT / "gm_model_coefs.parquet")
    log("coefs written")


# ── bets ──────────────────────────────────────────────────────────────────────

def units_for(dec: np.ndarray, res: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """res: 1 win, 0 loss, 0.5 push. Returns (units won, units risked)."""
    r = risk_units(dec)
    won = np.where(res == 1, r * (dec - 1.0), np.where(res == 0, -r, 0.0))
    return won, r


def boot_ci(day: np.ndarray, units: np.ndarray, risk: np.ndarray, n=BOOT_N, seed=BOOT_SEED):
    """Whole-day bootstrap 90% CI of ROI (4,000 resamples, seed 7)."""
    if len(units) == 0:
        return (np.nan, np.nan)
    df = pd.DataFrame({"d": day, "u": units, "r": risk}).groupby("d")[["u", "r"]].sum()
    u, r = df["u"].to_numpy(), df["r"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(u), size=(n, len(u)))
    roi = u[idx].sum(1) / r[idx].sum(1)
    return (float(np.percentile(roi, 5)), float(np.percentile(roi, 95)))


SIGMA = {}


def close_fair(side_a: np.ndarray, market: np.ndarray, line: np.ndarray, close_line: np.ndarray,
               close_p: np.ndarray) -> np.ndarray:
    """Pinnacle no-vig close probability for the bet side at the BET line.

    Same number: the close itself. Different number (spreads / totals): a normal
    margin model centred so the close's probability is reproduced at its own line
    (sigma = the measured SD of the result around the close line)."""
    from scipy.stats import norm
    pa = np.full(len(line), np.nan)
    same = (market == "h2h") | (line == close_line)
    pa[same] = close_p[same]
    for mk, sgn in (("spreads", 1), ("totals", -1)):
        idx = (~same) & (market == mk) & ~np.isnan(close_line) & ~np.isnan(close_p)
        if not idx.any():
            continue
        s = SIGMA[mk]
        z = norm.ppf(np.clip(close_p[idx], 1e-6, 1 - 1e-6))
        if mk == "spreads":   # P(margin + L > 0) = Phi((L + mu)/s)
            mu = s * z - close_line[idx]
            pa[idx] = norm.cdf((line[idx] + mu) / s)
        else:                  # P(total > T) = Phi((mu - T)/s)
            mu = close_line[idx] + s * z
            pa[idx] = norm.cdf((mu - line[idx]) / s)
    return np.where(side_a, pa, 1 - pa)


def bet_frame(panel: pd.DataFrame, preds: pd.DataFrame, variant: str, price: str = "best") -> pd.DataFrame:
    """One candidate per (game, market, slot): the side with the larger EV at the chosen price set."""
    x = panel.merge(preds[["game_id", "market", "slot", f"p_{variant}"]], on=["game_id", "market", "slot"])
    p_a = x[f"p_{variant}"].to_numpy(float)
    ca, cb = ("best_a", "best_b") if price == "best" else ("dk_a", "dk_b")
    pa_am, pb_am = x[ca].to_numpy(float), x[cb].to_numpy(float)
    ok_a = ~np.isnan(pa_am) & ((pa_am >= MIN_ODDS) | (pa_am > 0))
    ok_b = ~np.isnan(pb_am) & ((pb_am >= MIN_ODDS) | (pb_am > 0))
    da, db = decimal(np.nan_to_num(pa_am, nan=-110)), decimal(np.nan_to_num(pb_am, nan=-110))
    ev_a = np.where(ok_a, p_a * da - 1, -np.inf)
    ev_b = np.where(ok_b, (1 - p_a) * db - 1, -np.inf)
    side_a = ev_a >= ev_b
    out = pd.DataFrame({
        "game_id": x["game_id"], "game_date": x["gd"].dt.strftime("%Y-%m-%d"), "season": x["season"],
        "market": x["market"], "slot": x["slot"], "variant": variant, "price_set": price,
        "side": np.where(x["market"] == "totals", np.where(side_a, "over", "under"),
                         np.where(side_a, "home", "away")),
        "side_a": side_a,
        "line": x["mkt_line"],
        "book": np.where(side_a, x["book_a"] if price == "best" else "draftkings",
                         x["book_b"] if price == "best" else "draftkings"),
        "price": np.where(side_a, pa_am, pb_am),
        "model_prob": np.where(side_a, p_a, 1 - p_a),
        "market_prob": np.where(side_a, x["mkt_p"], 1 - x["mkt_p"]),
        "ev": np.maximum(ev_a, ev_b),
        "decision_fetch": x["fetch_ts"], "lead_h": x["lead_h"],
        "margin_vs_line": x["margin_vs_line"], "close_line": x["close_line"], "close_p": x["close_p"],
    })
    out = out[np.isfinite(out["ev"])].copy()
    m = out["margin_vs_line"].to_numpy()
    res_a = np.where(m > 0, 1.0, np.where(m < 0, 0.0, 0.5))
    res = np.where(out["side_a"], res_a, np.where(res_a == 0.5, 0.5, 1 - res_a))
    out["result"] = np.select([res == 1, res == 0], ["W", "L"], "P")
    dec = decimal(out["price"].to_numpy(float))
    out["units"], out["risk"] = units_for(dec, res)
    out["close_fair_prob"] = close_fair(out["side_a"].to_numpy(), out["market"].to_numpy(),
                                        out["line"].to_numpy(float), out["close_line"].to_numpy(float),
                                        out["close_p"].to_numpy(float))
    out["clv_ev"] = out["close_fair_prob"] * dec - 1
    out["close_same_number"] = (out["market"] == "h2h") | (out["line"] == out["close_line"])
    return out


def cell_stats(b: pd.DataFrame) -> dict:
    if len(b) == 0:
        return {"bets": 0}
    lo, hi = boot_ci(b["game_date"].to_numpy(), b["units"].to_numpy(), b["risk"].to_numpy())
    r = {"bets": len(b), "units": b["units"].sum(), "risk": b["risk"].sum(),
         "roi": b["units"].sum() / b["risk"].sum(), "ci_lo": lo, "ci_hi": hi,
         "side_a_share": b["side_a"].mean(), "clv_med": b["clv_ev"].median(),
         "clv_mean": b["clv_ev"].mean(), "clv_cov": b["clv_ev"].notna().mean(),
         "clv_same_num": b["close_same_number"].mean()}
    for S in GRADED:
        s = b[b["season"] == S]
        r[f"n_{S}"] = len(s)
        r[f"roi_{S}"] = s["units"].sum() / s["risk"].sum() if len(s) else np.nan
    dmed = np.sort(b["game_date"].unique())[len(b["game_date"].unique()) // 2]
    e, l = b[b["game_date"] < dmed], b[b["game_date"] >= dmed]
    r["roi_h1"] = e["units"].sum() / e["risk"].sum() if len(e) else np.nan
    r["roi_h2"] = l["units"].sum() / l["risk"].sum() if len(l) else np.nan
    return r


def stage_bets() -> None:
    panel = build_panel()
    preds = pd.read_parquet(OUT / "gm_model_preds.parquet")
    graded = panel[panel["season"].isin(GRADED)]
    # sigma of the result around Pinnacle's close line, for CLV at a different number
    cl = graded[(graded["slot"] == "pre")]
    for mk in ("spreads", "totals"):
        SIGMA[mk] = float(cl[cl["market"] == mk]["margin_vs_line"].std())
    log("sigma", SIGMA)
    rows, frames = [], {}
    for v in BET_VARIANTS:
        for price in ("best", "dk"):
            bf = bet_frame(graded, preds, v, price)
            frames[(v, price)] = bf
            for (mk, sl), g in bf.groupby(["market", "slot"]):
                for ev in EV_STEPS:
                    b = g[g["ev"] >= ev]
                    st = cell_stats(b)
                    ch = b[b["season"].isin(CHOOSE)]
                    st.update({"market": mk, "slot": sl, "variant": v, "price_set": price, "ev_cut": ev,
                               "bets_choose": len(ch),
                               "units_choose": ch["units"].sum() if len(ch) else 0.0})
                    rows.append(st)
        log("bets", v)
    grid = pd.DataFrame(rows)
    grid.to_parquet(OUT / "gm_grid.parquet")
    for k, bf in frames.items():
        bf.to_parquet(OUT / f"gm_candidates_{k[0]}_{k[1]}.parquet")
    log("grid", len(grid), "cells (best + dk)")


def blind_baselines(panel: pd.DataFrame) -> pd.DataFrame:
    """Blind side bets on every priced game, at the best bettable price at the reference number."""
    rows = []
    g = panel[panel["season"].isin(GRADED)]
    for (mk, sl), x in g.groupby(["market", "slot"]):
        m = x["margin_vs_line"].to_numpy()
        res_a = np.where(m > 0, 1.0, np.where(m < 0, 0.0, 0.5))
        for side, col, res in (("a", "best_a", res_a), ("b", "best_b", np.where(res_a == 0.5, 0.5, 1 - res_a))):
            pr = x[col].to_numpy(float)
            ok = ~np.isnan(pr) & ((pr >= MIN_ODDS) | (pr > 0))
            u, r = units_for(decimal(pr[ok]), res[ok])
            lo, hi = boot_ci(x["gd"].dt.strftime("%Y-%m-%d").to_numpy()[ok], u, r)
            rows.append({"market": mk, "slot": sl, "side": side, "bets": int(ok.sum()), "units": u.sum(),
                         "roi": u.sum() / r.sum(), "ci_lo": lo, "ci_hi": hi})
        if mk == "h2h":   # favourite / underdog by the market
            fav_a = x["mkt_p"].to_numpy() >= 0.5
            for side in ("fav", "dog"):
                pick_a = fav_a if side == "fav" else ~fav_a
                pr = np.where(pick_a, x["best_a"], x["best_b"]).astype(float)
                res = np.where(pick_a, res_a, 1 - res_a)
                ok = ~np.isnan(pr) & ((pr >= MIN_ODDS) | (pr > 0))
                u, r = units_for(decimal(pr[ok]), res[ok])
                rows.append({"market": mk, "slot": sl, "side": side, "bets": int(ok.sum()), "units": u.sum(),
                             "roi": u.sum() / r.sum()})
    return pd.DataFrame(rows)


# ── the three published schedule spots, as blind rules ────────────────────────

RULES = {
    "R1_home_b2b_vs_rested": "home team on night two of a back-to-back, visitor rested (>=1 day): bet the VISITOR",
    "R1e_plus_east": "R1 and the home team travelled EAST into tonight's game: bet the VISITOR",
    "R2_alt_vs_tired": "Denver or Utah at home, visitor on a back-to-back or 3-in-4: bet the HOME team",
    "R3_long_b2b": "a team on night two after >=750 miles of travel since last night (only one such team): bet AGAINST it",
}


def rule_sides(x: pd.DataFrame) -> dict:
    """Per rule: boolean mask and whether the bet is on side A (home)."""
    r1 = (x["home_b2b"] == 1) & (x["away_rest_days"] >= 1)
    alt = x["venue"].isin(["Denver", "Salt Lake City"]) & (x["neutral"] == 0)
    r2 = alt & ((x["away_b2b"] == 1) | (x["away_is_3in4"] == 1))
    hl = (x["home_b2b"] == 1) & (x["home_travel_mi"] >= 750)
    al = (x["away_b2b"] == 1) & (x["away_travel_mi"] >= 750)
    return {
        "R1_home_b2b_vs_rested": (r1, np.zeros(len(x), bool)),
        "R1e_plus_east": (r1 & (x["home_east_shift"] > 0), np.zeros(len(x), bool)),
        "R2_alt_vs_tired": (r2, np.ones(len(x), bool)),
        "R3_long_b2b": ((hl ^ al), al.to_numpy()),     # bet home when the AWAY team is the tired one
    }


def stage_rules() -> None:
    panel = build_panel()
    panel = panel[panel["season"] >= 2021]
    for mk in ("spreads", "totals"):
        cl = panel[(panel["slot"] == "pre") & (panel["market"] == mk)]
        SIGMA[mk] = float(cl["margin_vs_line"].std())
    rows, lists = [], []
    for (mk, sl), x in panel[panel["market"].isin(["spreads", "h2h"])].groupby(["market", "slot"]):
        x = x.reset_index(drop=True)
        for name, (mask, on_a) in rule_sides(x).items():
            mask = np.asarray(mask, bool)
            for price in ("best", "dk"):
                ca, cb = ("best_a", "best_b") if price == "best" else ("dk_a", "dk_b")
                pr = np.where(on_a, x[ca], x[cb]).astype(float)
                ok = mask & ~np.isnan(pr) & ((pr >= MIN_ODDS) | (pr > 0))
                m = x["margin_vs_line"].to_numpy()
                res_a = np.where(m > 0, 1.0, np.where(m < 0, 0.0, 0.5))
                res = np.where(on_a, res_a, np.where(res_a == 0.5, 0.5, 1 - res_a))
                dec = decimal(np.nan_to_num(pr, nan=-110))
                u, r = units_for(dec, res)
                b = pd.DataFrame({
                    "game_id": x["game_id"], "game_date": x["gd"].dt.strftime("%Y-%m-%d"), "season": x["season"],
                    "market": mk, "slot": sl, "rule": name, "price_set": price,
                    "side": np.where(on_a, "home", "away"), "side_a": on_a, "line": x["mkt_line"],
                    "book": np.where(on_a, x["book_a"], x["book_b"]) if price == "best" else "draftkings",
                    "price": pr, "fair_prob": np.where(on_a, x["mkt_p"], 1 - x["mkt_p"]),
                    "ev": np.where(on_a, x["mkt_p"], 1 - x["mkt_p"]) * dec - 1,
                    "decision_fetch": x["fetch_ts"], "result": np.select([res == 1, res == 0], ["W", "L"], "P"),
                    "units": u, "risk": r, "close_line": x["close_line"], "close_p": x["close_p"]})[ok]
                b["close_fair_prob"] = close_fair(b["side_a"].to_numpy(), b["market"].to_numpy(),
                                                  b["line"].to_numpy(float), b["close_line"].to_numpy(float),
                                                  b["close_p"].to_numpy(float))
                b["clv_ev"] = b["close_fair_prob"] * decimal(b["price"].to_numpy(float)) - 1
                b["close_same_number"] = (b["market"] == "h2h") | (b["line"] == b["close_line"])
                st = cell_stats_all(b)
                st.update({"market": mk, "slot": sl, "rule": name, "price_set": price,
                           "eligible_games": int(mask.sum())})
                rows.append(st)
                if price == "best":
                    lists.append(b)
    pd.DataFrame(rows).to_parquet(OUT / "gm_rules.parquet")
    bl = pd.concat(lists)
    bl.to_parquet(OUT / "gm_rules_bets.parquet")
    log("rules", len(rows))


def cell_stats_all(b: pd.DataFrame) -> dict:
    """cell_stats over every season present (rules are graded 2020-21 .. 2025-26)."""
    r = cell_stats(b)
    if len(b):
        s = b[b["season"] == 2021]
        r["n_2021"] = len(s)
        r["roi_2021"] = s["units"].sum() / s["risk"].sum() if len(s) else np.nan
        w = (b["result"] == "W").sum()
        l_ = (b["result"] == "L").sum()
        r["win_rate"] = w / (w + l_) if (w + l_) else np.nan
    return r


# ── is the schedule already in the line? ──────────────────────────────────────

# at_altitude and away_tz_from_home are left out ON PURPOSE: with home and away team-season fixed
# effects each is (almost) a linear combination of the team dummies -- the venue is the home team's
# -- so its coefficient would be identified by a handful of neutral-site games only.
INLINE_SIDE = ["home_b2b", "away_b2b", "rest_diff", "home_3in4", "away_3in4", "home_travel_k", "away_travel_k",
               "away_east", "away_west", "home_east", "home_west", "alt_vs_tired",
               "away_road_no", "home_first_after3", "early_tip"]
INLINE_TOT = ["sum_b2b", "both_b2b", "sum_3in4", "sum_travel_k", "sum_east", "sum_west", "early_tip"]
# Availability (home minus away): minutes out /48, PIE out, new absences /48, change since the opener /48.
INLINE_AVAIL = ["d_o_min", "d_o_pie", "d_o_new", "dd_o_min"]


def _fe_ols(y: np.ndarray, X: pd.DataFrame, fe: pd.DataFrame):
    import statsmodels.api as sm
    D = pd.get_dummies(fe.astype(str), drop_first=True, dtype=float)
    Z = sm.add_constant(pd.concat([X.reset_index(drop=True), D.reset_index(drop=True)], axis=1), has_constant="add")
    m = sm.OLS(y, Z).fit(cov_type="HC1")
    ci = m.conf_int(0.10)
    return pd.DataFrame({"coef": m.params[X.columns], "lo90": ci.loc[X.columns, 0], "hi90": ci.loc[X.columns, 1],
                         "p": m.pvalues[X.columns]})


def stage_inline() -> None:
    """Points the LINE assigns each schedule feature vs points the RESULT moved, with team-season fixed effects.

    expected  = -Pinnacle close spread (the market's home margin)   | totals: close total
    actual    = home margin                                         | actual total
    residual  = actual - expected (= the cover margin)              | total - close
    If the line prices a feature correctly, expected ~= actual and the residual's CI covers 0.
    Movement  = Pinnacle close spread - Pinnacle opener spread (home number): did the line move
                during the day in the direction the feature predicts (the open under-adjusted)?
    """
    panel = build_panel()
    x = panel[(panel["slot"] == "pre") & panel["season"].between(2021, 2026)].copy()
    out = []
    s = x[x["market"] == "spreads"].reset_index(drop=True)
    fe = pd.DataFrame({"h": s["season"].astype(str) + s["home_team"], "a": s["season"].astype(str) + s["away_team"]})
    X = s[["x_" + c for c in INLINE_SIDE]].rename(columns=lambda c: c[2:])
    hm = (s["home_score"] - s["away_score"]).to_numpy(float)
    exp_ = -s["close_line"].to_numpy(float)
    for tag, y in (("line_expected", exp_), ("actual", hm), ("residual", hm - exp_)):
        r = _fe_ols(y, X, fe)
        r["market"], r["quantity"], r["n"] = "spreads", tag, len(s)
        out.append(r.reset_index().rename(columns={"index": "feature"}))
    mv = (s["close_line"] - s["pin_open_line"]).to_numpy(float)
    okm = ~np.isnan(mv)
    import statsmodels.api as sm
    Xm = sm.add_constant(X[okm], has_constant="add")
    m = sm.OLS(mv[okm], Xm).fit(cov_type="HC1")
    ci = m.conf_int(0.10)
    r = pd.DataFrame({"coef": m.params[X.columns], "lo90": ci.loc[X.columns, 0], "hi90": ci.loc[X.columns, 1],
                      "p": m.pvalues[X.columns]})
    r["market"], r["quantity"], r["n"] = "spreads", "open_to_close_move", int(okm.sum())
    out.append(r.reset_index().rename(columns={"index": "feature"}))
    t = x[x["market"] == "totals"].reset_index(drop=True)
    fe = pd.DataFrame({"h": t["season"].astype(str) + t["home_team"], "a": t["season"].astype(str) + t["away_team"]})
    X = t[["x_" + c for c in INLINE_TOT]].rename(columns=lambda c: c[2:])
    tot = (t["home_score"] + t["away_score"]).to_numpy(float)
    ex = t["close_line"].to_numpy(float)
    for tag, y in (("line_expected", ex), ("actual", tot), ("residual", tot - ex)):
        r = _fe_ols(y, X, fe)
        r["market"], r["quantity"], r["n"] = "totals", tag, len(t)
        out.append(r.reset_index().rename(columns={"index": "feature"}))
    # Availability at 19Z, same construction: does the 19Z line respond to who is out, and by the right amount?
    a19 = panel[(panel["slot"] == "d19") & (panel["market"] == "spreads") & panel["season"].between(2021, 2026)]
    a19 = a19.reset_index(drop=True)
    fe = pd.DataFrame({"h": a19["season"].astype(str) + a19["home_team"],
                       "a": a19["season"].astype(str) + a19["away_team"]})
    X = a19[["x_" + c for c in INLINE_AVAIL]].rename(columns=lambda c: c[2:])
    hm = (a19["home_score"] - a19["away_score"]).to_numpy(float)
    ex19 = -a19["mkt_line"].to_numpy(float)
    for tag, y in (("line_expected", ex19), ("actual", hm), ("residual", hm - ex19)):
        r = _fe_ols(y, X, fe)
        r["market"], r["quantity"], r["n"] = "spreads_avail_d19", tag, len(a19)
        out.append(r.reset_index().rename(columns={"index": "feature"}))
    pd.concat(out).to_parquet(OUT / "gm_inline.parquet")

    # Rest permutations at Pinnacle's close: the one table that answers "is rest priced?"
    s = x[x["market"] == "spreads"].copy()
    s["home_r"] = np.where(s["home_rest_days"] == 0, "0", np.where(s["home_rest_days"] == 1, "1", "2+"))
    s["away_r"] = np.where(s["away_rest_days"] == 0, "0", np.where(s["away_rest_days"] == 1, "1", "2+"))
    s["cover"] = np.where(s["push"] == 1, np.nan, s["y"])
    s["home_win"] = (s["home_score"] > s["away_score"]).astype(float)
    s["exp_margin"] = -s["close_line"]
    s["margin"] = s["home_score"] - s["away_score"]
    perm = s.groupby(["home_r", "away_r"]).agg(
        games=("game_id", "size"), home_cover=("cover", "mean"), home_win=("home_win", "mean"),
        line_home_margin=("exp_margin", "mean"), actual_home_margin=("margin", "mean")).reset_index()
    perm["residual"] = perm["actual_home_margin"] - perm["line_home_margin"]
    s["resid"] = s["margin"] - s["exp_margin"]
    sd = s.groupby(["home_r", "away_r"]).agg(rsd=("resid", "std"), nc=("cover", "count")).reset_index()
    perm = perm.merge(sd, on=["home_r", "away_r"])
    perm["resid_lo90"] = perm["residual"] - 1.645 * perm["rsd"] / np.sqrt(perm["games"])
    perm["resid_hi90"] = perm["residual"] + 1.645 * perm["rsd"] / np.sqrt(perm["games"])
    se = np.sqrt(perm["home_cover"] * (1 - perm["home_cover"]) / perm["nc"])
    perm["cover_lo90"], perm["cover_hi90"] = perm["home_cover"] - 1.645 * se, perm["home_cover"] + 1.645 * se
    perm.to_parquet(OUT / "gm_inline_restperm.parquet")
    log("inline written")


# ── candidates and the pre-registered bars ────────────────────────────────────

PLACEBO_N = 200


def placebo_roi(panel: pd.DataFrame, preds: pd.DataFrame, market: str, slot: str, variant: str, ev_cut: float,
                n: int = PLACEBO_N, seed: int = BOOT_SEED) -> np.ndarray:
    """ROI with the model's probabilities shuffled among games on the SAME date (same market, slot)."""
    x = panel[(panel["market"] == market) & (panel["slot"] == slot) & panel["season"].isin(GRADED)]
    x = x.merge(preds[["game_id", "market", "slot", f"p_{variant}"]], on=["game_id", "market", "slot"])
    x = x.sort_values("gd").reset_index(drop=True)
    pa_am, pb_am = x["best_a"].to_numpy(float), x["best_b"].to_numpy(float)
    ok_a = ~np.isnan(pa_am) & ((pa_am >= MIN_ODDS) | (pa_am > 0))
    ok_b = ~np.isnan(pb_am) & ((pb_am >= MIN_ODDS) | (pb_am > 0))
    da, db = decimal(np.nan_to_num(pa_am, nan=-110)), decimal(np.nan_to_num(pb_am, nan=-110))
    m = x["margin_vs_line"].to_numpy()
    res_a = np.where(m > 0, 1.0, np.where(m < 0, 0.0, 0.5))
    res_b = np.where(res_a == 0.5, 0.5, 1 - res_a)
    ua, ra = units_for(da, res_a)
    ub, rb = units_for(db, res_b)
    p = x[f"p_{variant}"].to_numpy(float)
    day = x["gd"].to_numpy()
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for i in range(n):
        # rows are sorted by date, so sorting by (date, random key) permutes WITHIN each date block
        order = np.lexsort((rng.random(len(p)), day))
        ps = p[order]
        ev_a = np.where(ok_a, ps * da - 1, -np.inf)
        ev_b = np.where(ok_b, (1 - ps) * db - 1, -np.inf)
        side_a = ev_a >= ev_b
        ev = np.maximum(ev_a, ev_b)
        sel = ev >= ev_cut
        u = np.where(side_a, ua, ub)[sel]
        r = np.where(side_a, ra, rb)[sel]
        out[i] = u.sum() / r.sum() if r.sum() > 0 else np.nan
    return out


def evaluate_bars(c: pd.Series, grid: pd.DataFrame, blind: pd.DataFrame, panel, preds,
                  bets: pd.DataFrame | None = None) -> dict:
    g = grid[(grid["market"] == c["market"]) & (grid["slot"] == c["slot"]) & (grid["variant"] == c["variant"])
             & (grid["price_set"] == "best")].sort_values("ev_cut").reset_index(drop=True)
    i = int(np.where(np.isclose(g["ev_cut"], c["ev_cut"]))[0][0])
    nb = [g.loc[j, "roi"] for j in (i - 1, i + 1) if 0 <= j < len(g)]
    seasons = {S: (c.get(f"n_{S}", 0), c.get(f"roi_{S}", np.nan)) for S in GRADED}
    b = {}
    b["4_confirm_2025_26"] = bool(seasons[CONFIRM][0] >= 30 and seasons[CONFIRM][1] > 0)
    b["5_every_season"] = bool(all((r > 0) for n, r in seasons.values() if n >= 30))
    b["6_volume_ci"] = bool(c["bets"] >= 200 and c["ci_lo"] > 0)
    b["7_plateau"] = bool(len(nb) > 0 and all((x > 0) for x in nb if not np.isnan(x)))
    b["8_halves"] = bool(c["roi_h1"] > 0 and c["roi_h2"] > 0)
    share = c["side_a_share"]
    side = "a" if share >= 0.5 else "b"
    bl = blind[(blind["market"] == c["market"]) & (blind["slot"] == c["slot"]) & (blind["side"] == side)]
    blind_roi = float(bl["roi"].iloc[0]) if len(bl) else np.nan
    ok9 = bool(c["roi"] > blind_roi) if (share > 0.7 or share < 0.3) else True
    # A moneyline rule can lean on favourite/underdog without leaning home/away: test that lean too.
    dog_share, blind_dog = np.nan, np.nan
    if c["market"] == "h2h" and bets is not None and len(bets):
        dog_share = float((bets["market_prob"] < 0.5).mean())
        if dog_share > 0.7 or dog_share < 0.3:
            fd = "dog" if dog_share > 0.7 else "fav"
            bd = blind[(blind["market"] == "h2h") & (blind["slot"] == c["slot"]) & (blind["side"] == fd)]
            blind_dog = float(bd["roi"].iloc[0]) if len(bd) else np.nan
            ok9 = ok9 and bool(c["roi"] > blind_dog)
    b["9_beats_blind_side"] = ok9
    pl = placebo_roi(panel, preds, c["market"], c["slot"], c["variant"], c["ev_cut"])
    b["10_placebo"] = bool(np.nanmean(pl >= c["roi"]) < 0.05)
    b["11_clv"] = bool(c["slot"] != "pre" and c["clv_med"] > 0)
    return {"bars": b, "passes_all": all(b.values()), "placebo_mean": float(np.nanmean(pl)),
            "placebo_share_ge": float(np.nanmean(pl >= c["roi"])), "blind_same_side_roi": blind_roi,
            "blind_side": side, "neighbours": nb, "dog_share": dog_share, "blind_fav_dog_roi": blind_dog}


def stage_bars() -> None:
    panel = build_panel()
    preds = pd.read_parquet(OUT / "gm_model_preds.parquet")
    grid = pd.read_parquet(OUT / "gm_grid.parquet")
    blind = blind_baselines(panel)
    blind.to_parquet(OUT / "gm_blind.parquet")
    g = grid[grid["price_set"] == "best"]
    picks = []
    for mk in MARKETS:
        x = g[(g["market"] == mk) & (g["bets_choose"] >= 150)]
        if len(x):
            picks.append(("chosen", x.sort_values("units_choose").iloc[-1]))
        for v in ("S_r", "all_r"):
            y = x[x["variant"] == v]
            if len(y):
                picks.append((f"best_{v}", y.sort_values("units_choose").iloc[-1]))
    res = []
    for tag, c in picks:
        name = f"{c['market']}_{c['slot']}_{c['variant']}_ev{c['ev_cut']:.2f}"
        cand = pd.read_parquet(OUT / f"gm_candidates_{c['variant']}_best.parquet")
        bl = cand[(cand["market"] == c["market"]) & (cand["slot"] == c["slot"]) & (cand["ev"] >= c["ev_cut"])]
        ev = evaluate_bars(c, grid, blind, panel, preds, bl)
        path = OUT / f"game_model_bets_{name}.parquet"
        bl[["game_id", "game_date", "season", "market", "side", "line", "book", "price", "model_prob",
            "market_prob", "ev", "decision_fetch", "result", "units", "risk", "close_fair_prob", "clv_ev",
            "close_same_number", "lead_h"]].to_parquet(path)
        dk = grid[(grid["market"] == c["market"]) & (grid["slot"] == c["slot"]) & (grid["variant"] == c["variant"])
                  & (grid["price_set"] == "dk") & np.isclose(grid["ev_cut"], c["ev_cut"])]
        res.append({"tag": tag, "name": name, **{k: c[k] for k in c.index}, **ev,
                    "dk_bets": int(dk["bets"].iloc[0]) if len(dk) else 0,
                    "dk_roi": float(dk["roi"].iloc[0]) if len(dk) else np.nan, "bet_list": str(path)})
        log("bars", tag, name, ev["passes_all"], ev["bars"])
    pd.to_pickle(res, OUT / "gm_bars.pkl")




# ── POST-HOC: the pre-tip moneyline lead (seen after the grid; reported, never shipped) ──

POSTHOC_CELLS = (("h2h", "pre", "M", 0.02), ("h2h", "pre", "M", 0.03))


def _roi_tab(df: pd.DataFrame, by: str) -> dict:
    out = {}
    for k, x in df.groupby(by, observed=True):
        out[str(k)] = {"bets": int(len(x)), "units": float(x["units"].sum()),
                       "roi": float(x["units"].sum() / x["risk"].sum()) if len(x) else float("nan")}
    return out


def stage_posthoc() -> None:
    """Bars, blind-underdog comparison and timing checks for the pre-tip moneyline market-alone row.

    NOT a candidate: the pre-registered choice rule picked EV 0.00 in this row (it fails). These two cells
    were looked at because the whole row read positive, so every number here is post hoc."""
    panel = build_panel()
    preds = pd.read_parquet(OUT / "gm_model_preds.parquet")
    grid = pd.read_parquet(OUT / "gm_grid.parquet")
    blind = pd.read_parquet(OUT / "gm_blind.parquet")
    cand = pd.read_parquet(OUT / "gm_candidates_M_best.parquet")
    res = []
    for mk, sl, v, ev in POSTHOC_CELLS:
        c = grid[(grid["market"] == mk) & (grid["slot"] == sl) & (grid["variant"] == v)
                 & (grid["price_set"] == "best") & np.isclose(grid["ev_cut"], ev)].iloc[0]
        b = cand[(cand["market"] == mk) & (cand["slot"] == sl) & (cand["ev"] >= ev)]
        r = evaluate_bars(c, grid, blind, panel, preds, b)
        name = f"{mk}_{sl}_{v}_ev{ev:.2f}_POSTHOC"
        path = OUT / f"game_model_bets_{name}.parquet"
        b[["game_id", "game_date", "season", "market", "side", "line", "book", "price", "model_prob", "market_prob",
           "ev", "decision_fetch", "result", "units", "risk", "close_fair_prob", "clv_ev", "close_same_number",
           "lead_h"]].to_parquet(path)
        dog = b["market_prob"] < 0.5
        res.append({"name": name, "bets": int(c["bets"]), "units": float(c["units"]), "roi": float(c["roi"]),
                    "ci": [float(c["ci_lo"]), float(c["ci_hi"])],
                    "by_season": {int(S): [int(c[f"n_{S}"]), float(c[f"roi_{S}"])] for S in GRADED},
                    "halves": [float(c["roi_h1"]), float(c["roi_h2"])],
                    "dog_roi": float(b[dog]["units"].sum() / b[dog]["risk"].sum()),
                    "fav_roi": float(b[~dog]["units"].sum() / b[~dog]["risk"].sum()) if (~dog).any() else None,
                    "within_15min": int((b["lead_h"] <= 0.25).sum()),
                    "bet_list": str(path), **r})
    (OUT / "gm_posthoc.json").write_text(json.dumps(res, indent=1, default=str))

    # Blind underdogs at the pre-tip fetch, bucketed by their EV against Pinnacle's no-vig.
    p = panel[(panel["market"] == "h2h") & (panel["slot"] == "pre") & panel["season"].isin(GRADED)]
    dog_a = (p["mkt_p"] < 0.5).to_numpy()
    pr = np.where(dog_a, p["best_a"], p["best_b"]).astype(float)
    fair = np.where(dog_a, p["mkt_p"], 1 - p["mkt_p"])
    ra = (p["margin_vs_line"].to_numpy() > 0).astype(float)
    res_d = np.where(dog_a, ra, 1 - ra)
    ok = ~np.isnan(pr)
    dec = decimal(np.nan_to_num(pr, nan=100))
    u, rk = units_for(dec, res_d)
    evd = fair * dec - 1
    buckets = []
    for lo, hi in ((-1, -0.03), (-0.03, -0.01), (-0.01, 0), (0, 0.01), (0.01, 0.02), (0.02, 0.03), (0.03, 0.05), (0.05, 9)):
        s = ok & (evd >= lo) & (evd < hi)
        buckets.append({"ev_from": lo, "ev_to": hi, "bets": int(s.sum()),
                        "roi": float(u[s].sum() / rk[s].sum()) if s.any() else None,
                        "median_price": float(np.median(pr[s])) if s.any() else None})

    # Timing: did Pinnacle move into this fetch, which book, how close to tip, and quote-age gaps.
    diag = {"dog_ev_buckets": buckets}
    f = pd.read_parquet(OUT / "gm_market_frame.parquet")
    f = f[(f["market"] == "h2h") & f["pin_p"].notna()].sort_values("fetch_ts")
    f["prev_pin_p"] = f.groupby("game_id")["pin_p"].shift(1)
    for sl in ("pre", "d19"):
        b = cand[(cand["market"] == "h2h") & (cand["slot"] == sl) & (cand["ev"] >= 0.02)]
        b = b.merge(f[["game_id", "fetch_ts", "pin_p", "prev_pin_p"]], left_on=["game_id", "decision_fetch"],
                    right_on=["game_id", "fetch_ts"], how="left")
        mv = np.where(b["side"] == "home", b["pin_p"] - b["prev_pin_p"], b["prev_pin_p"] - b["pin_p"])
        b["moved"] = np.select([mv > 0.005, mv < -0.005], ["toward bet", "away from bet"], "flat (<0.5pp)")
        b["lead_bucket"] = pd.cut(b["lead_h"], [0, 0.25, 0.5, 1, 3, 6, 48]).astype(str)
        diag[sl] = {"by_pin_move": _roi_tab(b, "moved"), "by_book": _roi_tab(b, "book"),
                    "by_lead": _roi_tab(b, "lead_bucket")}
    o = pd.read_parquet(CACHE / "nba_odds.parquet",
                        columns=["game_id", "market", "bookmaker", "snapshot_at", "created_at", "source", "snapshot_type"])
    o = o[(o["source"] == "odds_api_historical") & (o["market"] == "h2h") & (o["snapshot_type"] != "in_play")]
    o["sa"] = pd.to_datetime(o["snapshot_at"], utc=True, format="ISO8601")
    o["fetch_ts"] = o.groupby(["game_id", "created_at"])["sa"].transform("max")
    pin = (o[o["bookmaker"] == SHARP][["game_id", "fetch_ts", "sa"]].rename(columns={"sa": "pin_sa"})
           .drop_duplicates(["game_id", "fetch_ts"]))
    soft = (o[["game_id", "fetch_ts", "bookmaker", "sa"]].rename(columns={"bookmaker": "book", "sa": "book_sa"})
            .drop_duplicates(["game_id", "fetch_ts", "book"]))
    b = cand[(cand["market"] == "h2h") & (cand["slot"] == "pre") & (cand["ev"] >= 0.02)]
    x = (b.merge(pin, left_on=["game_id", "decision_fetch"], right_on=["game_id", "fetch_ts"], how="left")
         .merge(soft, left_on=["game_id", "decision_fetch", "book"], right_on=["game_id", "fetch_ts", "book"], how="left"))
    gap = (x["pin_sa"] - x["book_sa"]).dt.total_seconds() / 60
    x["gap_b"] = pd.cut(gap, [-1e9, -1, 1, 3, 1e9],
                        labels=["book newer >1m", "within 1m", "pin newer 1-3m", "pin newer >3m"]).astype(str)
    diag["pre_gap"] = _roi_tab(x, "gap_b")
    (OUT / "gm_pretip_diag.json").write_text(json.dumps(diag, indent=1, default=str))
    log("posthoc written")


# ── data checks written for the report ────────────────────────────────────────

def stage_checks() -> None:
    ex = {}
    panel = build_panel()
    g = panel[panel["season"].isin((2021,) + GRADED)]
    pre = g[g["slot"] == "pre"]
    ex["sigma_spreads"] = float(pre[pre["market"] == "spreads"]["margin_vs_line"].std())
    ex["sigma_totals"] = float(pre[pre["market"] == "totals"]["margin_vs_line"].std())
    games = load_games()
    games = games[games["season"] >= 2021]
    cov = (g[g["market"] == "spreads"].groupby(["slot", "season"])["game_id"].nunique().unstack()
           .reindex(columns=sorted(games["season"].unique())))
    ex["check_games with a decision quote, spread market, by season (" +
       ", ".join(str(s) for s in cov.columns) + ")"] = "; ".join(
        f"{sl}: " + "/".join(str(int(v)) if not np.isnan(v) else "0" for v in cov.loc[sl]) for sl in cov.index) + \
        "; regular-season games: " + "/".join(str(int(v)) for v in games.groupby("season").size())
    sched = pd.read_parquet(CACHE / "nba_schedule.parquet")
    gf = nsf.game_schedule_features(sched)
    gx = games.merge(gf[["game_id", "home_b2b", "away_b2b"]], on="game_id")
    gx["grp"] = np.select([gx["home_b2b"].eq(1) & gx["away_b2b"].eq(1), gx["home_b2b"].eq(1), gx["away_b2b"].eq(1)],
                          ["both on a back-to-back", "home on a back-to-back", "visitor on a back-to-back"], "neither")
    parts = []
    for sl in SLOTS:
        ids = set(g[(g["slot"] == sl) & (g["market"] == "spreads")]["game_id"])
        r = gx.assign(h=gx["game_id"].isin(ids)).groupby("grp")["h"].mean()
        parts.append(f"{sl}: " + ", ".join(f"{k} {v:.1%}" for k, v in r.items()))
    ex["check_share of games that HAVE a decision quote, by back-to-back status (the evening selection effect)"] = \
        " | ".join(parts) + " | game counts: " + ", ".join(f"{k} {v}" for k, v in gx["grp"].value_counts().items())
    sn = g.assign(s=g["nbooks"].fillna(0) > 0).groupby(["market", "slot"])["s"].mean()
    ex["check_share of decisions where >=1 bettable book posts Pinnacle's exact number (the rest are discarded)"] = \
        "; ".join(f"{m}/{s}: {v:.1%}" for (m, s), v in sn.items())
    q = pd.read_parquet(OUT / "gm_features.parquet")
    q = q[q["market"] == "spreads"]
    hr = q.groupby("slot")[["home_dec_has_report", "away_dec_has_report"]].mean().mean(axis=1)
    ex["check_share of team-decisions with a submitted injury report for THIS game"] = \
        "; ".join(f"{k}: {v:.1%}" for k, v in hr.items())
    ex["check_injury-report Out/Doubtful/Questionable rows with no player match (left unvalued), per team-decision"] = \
        f"{q[['home_dec_n_unvalued', 'away_dec_n_unvalued']].mean().mean():.3f}"
    # Out at 19Z vs who actually sat (inactives / DNP are post-hoc truth, used only here)
    inj = pd.read_parquet(CACHE / "nba_injury_report.parquet",
                          columns=["report_ts", "game_id", "team", "player_id", "status"])
    inj = inj[inj["status"].isin(["Out", "Doubtful", "Questionable", "Probable"]) & inj["player_id"].notna()]
    d19 = g[(g["slot"] == "d19") & (g["market"] == "spreads")][["game_id", "fetch_ts"]]
    x = inj.merge(d19, on="game_id")
    x = x[x["report_ts"] <= x["fetch_ts"]]
    x = x.sort_values("report_ts").drop_duplicates(["game_id", "team", "player_id"], keep="last")
    adv = pd.read_parquet(CACHE / "nba_player_game_adv.parquet", columns=["game_id", "player_id", "played"])
    ina = pd.read_parquet(CACHE / "nba_game_inactives.parquet", columns=["game_id", "player_id"])
    played = adv[adv["played"] == True][["game_id", "player_id"]].assign(pl=1)  # noqa: E712
    x = x.merge(played, on=["game_id", "player_id"], how="left")
    x["sat"] = x["pl"].isna()
    rates = x.groupby("status")["sat"].agg(["mean", "size"])
    ex["check_status on the latest report before 19Z vs whether the player sat (inactive list / box score)"] = \
        "; ".join(f"{k}: {v['mean']:.1%} sat (n={int(v['size']):,})" for k, v in rates.iterrows())
    ex["check_inactive list rows matched to a box-score DNP or absence"] = \
        f"{ina.merge(played, on=['game_id', 'player_id'], how='left')['pl'].isna().mean():.1%} of inactives have no played box row"
    tf = nsf.team_schedule_features(sched)
    t27 = tf[tf["season"] == 2027]
    ex["check_schedule module vs NBA.com 2026-27 schedule notes (14.2 back-to-backs a team; 59 of 750+ miles)"] = \
        f"module: {t27.groupby('team')['b2b'].sum().mean():.1f} a team; {int(((t27['b2b'] == 1) & (t27['travel_mi'] >= 750)).sum())} of 750+ miles"
    ex["check_back-to-back second nights with the previous game already finished at the decision (result-derived load usable)"] = \
        "; ".join(f"{sl}: {v:.1%}" for sl, v in
                  q[q["home_b2b"] == 1].groupby("slot")["home_prev_known"].mean().items())
    rc = q.groupby("slot")["ref_tot_resid"].apply(lambda s: (s != 0).mean())
    ex["check_decisions with a referee input"] = "; ".join(f"{k}: {v:.1%}" for k, v in rc.items())
    ex["check_2020-21 caveat"] = ("the schedule table holds the season as PLAYED; COVID postponements re-slotted "
                                  "games, and the second half was published mid-season. Past-game inputs are "
                                  "exact; road-trip LENGTH may differ from what was known at an early line.")
    (OUT / "gm_extra_checks.json").write_text(json.dumps(ex, indent=1, default=str))
    log("checks written")


# ── report ────────────────────────────────────────────────────────────────────

def _f(x, nd=1, pct=False, sign=True):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if pct:
        return f"{x * 100:+.{nd}f}%" if sign else f"{x * 100:.{nd}f}%"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


SLOT_NAME = {"eve": "evening before, Pinnacle quoting", "eve_soft": "evening before, soft-book consensus",
             "d19": "game day 19Z (3 pm ET)", "pre": "last fetch before tip (= the close)"}
MK_NAME = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
VAR_NAME = {"M": "market alone", "S_r": "market + schedule (ridge)", "all_r": "market + every group (ridge)",
            "S": "market + schedule", "all": "market + every group", "M_int": "market + intercept",
            "M_recal": "market recalibrated", "S_core": "market + 6 core schedule inputs",
            "L": "market + last-game overtime", "A": "market + availability", "C": "market + availability change",
            "R": "market + referees", "F": "market + form/pace"}


def stage_report() -> None:
    diag = json.loads((OUT / "gm_market_diag.json").read_text())
    abl = pd.read_parquet(OUT / "gm_model_ablation.parquet")
    preds = pd.read_parquet(OUT / "gm_model_preds.parquet")
    coefs = pd.read_parquet(OUT / "gm_model_coefs.parquet")
    grid = pd.read_parquet(OUT / "gm_grid.parquet")
    blind = pd.read_parquet(OUT / "gm_blind.parquet")
    rules = pd.read_parquet(OUT / "gm_rules.parquet")
    inline = pd.read_parquet(OUT / "gm_inline.parquet")
    perm = pd.read_parquet(OUT / "gm_inline_restperm.parquet")
    bars = pd.read_pickle(OUT / "gm_bars.pkl")
    extra = json.loads((OUT / "gm_extra_checks.json").read_text()) if (OUT / "gm_extra_checks.json").exists() else {}
    L = []
    w = L.append
    w("# NBA game lines: does schedule, availability or the referee crew add anything to the line?")
    w("")
    w("Key `game_model`. Script `scripts/nba_game_model_lab.py`, schedule features "
      "`features/nba_schedule_features.py`. Every number below is produced by those two files from the parquet "
      "cache (`data/local/nba/`), read after `LINES_READY` was created. No Odds API call was made. "
      f"Generated {time.strftime('%Y-%m-%d %H:%M')} local.")
    w("")

    # ── 0. Verdict (every number computed below from the stage outputs)
    w("## 0. Verdict")
    w("")
    sp0 = inline[(inline["market"] == "spreads")]
    pv0 = sp0.pivot_table(index="feature", columns="quantity", values="coef")
    rs0 = sp0[sp0["quantity"] == "residual"].set_index("feature")
    rt0 = inline[(inline["market"] == "totals") & (inline["quantity"] == "residual")].set_index("feature")
    excl = [f for f in rs0.index if rs0.loc[f, "lo90"] > 0 or rs0.loc[f, "hi90"] < 0]
    exct = [f for f in rt0.index if rt0.loc[f, "lo90"] > 0 or rt0.loc[f, "hi90"] < 0]
    ntest = len(rs0) + len(rt0)
    alt_txt = ""
    if "alt_vs_tired" in excl:
        alt_txt = (f" The Denver/Utah-hosting-a-tired-visitor spot goes the OTHER way from the published edge: the "
                   f"line gives the home side {pv0.loc['alt_vs_tired', 'line_expected']:+.2f} points and the result "
                   f"was {pv0.loc['alt_vs_tired', 'actual']:+.2f}.")
    w(f"- **Schedule is in the line.** Pinnacle's close moves the expected home margin "
      f"{pv0.loc['home_b2b', 'line_expected']:+.2f} points when the home team is on the second night of a "
      f"back-to-back; the actual margin moved {pv0.loc['home_b2b', 'actual']:+.2f} (residual "
      f"{rs0.loc['home_b2b', 'coef']:+.2f}, 90% CI {rs0.loc['home_b2b', 'lo90']:+.2f}..{rs0.loc['home_b2b', 'hi90']:+.2f}). "
      f"For a visitor on a back-to-back: line {pv0.loc['away_b2b', 'line_expected']:+.2f}, result "
      f"{pv0.loc['away_b2b', 'actual']:+.2f}, residual {rs0.loc['away_b2b', 'coef']:+.2f} "
      f"({rs0.loc['away_b2b', 'lo90']:+.2f}..{rs0.loc['away_b2b', 'hi90']:+.2f}). Of {ntest} schedule residuals "
      f"(spread and total), {len(excl) + len(exct)} have a 90% interval clear of zero "
      f"({', '.join(excl + exct) or 'none'}); about {0.1 * ntest:.1f} are expected by chance." + alt_txt)
    a0 = abl.copy()
    a0["lln"] = a0["logloss"] * a0["n"]
    p0 = a0.groupby(["market", "slot", "variant"]).agg(n=("n", "sum"), lln=("lln", "sum"))
    p0["ll"] = p0["lln"] / p0["n"]
    b0 = p0.xs("M", level="variant")["ll"]
    p0["d"] = (p0["ll"] - b0.reindex(p0.index.droplevel(2)).values) * 1000
    d19 = p0.xs("d19", level="slot")["d"].unstack()
    w("- **Adding schedule to the market does not improve the forecast.** At 19Z, change in log loss vs "
      "Pinnacle alone (thousandths; negative = better): ridge schedule model "
      + ", ".join(f"{MK_NAME[m]} {d19.loc[m, 'S_r']:+.2f}" for m in MARKETS)
      + "; unpenalised schedule model " + ", ".join(f"{MK_NAME[m]} {d19.loc[m, 'S']:+.2f}" for m in MARKETS)
      + ". Availability, availability change, referees and form are no better (§2).")
    nsig0 = coefs[(coefs["fit"] == "fit_2021_2025") & (coefs["variant"] == "S") & (coefs["feature"] != "const")]
    w(f"- **Coefficients:** {int((nsig0['p'] < 0.05).sum())} of {len(nsig0)} schedule coefficients have p < 0.05 "
      f"(about {0.05 * len(nsig0):.0f} expected by chance).")
    w(f"- **No candidate passes the bars.** {sum(r['passes_all'] for r in bars)} of {len(bars)} candidate cells "
      "pass; §5 lists each with the bars it fails.")
    r1 = rules[(rules["price_set"] == "best") & (rules["market"] == "spreads") & (rules["slot"] == "d19")].set_index("rule")
    w("- **The published schedule spots do not beat the modern line** (spread, 19Z, best bettable price, 2020-21..2025-26): "
      + "; ".join(f"{k} {int(r1.loc[k, 'bets'])} bets {r1.loc[k, 'roi'] * 100:+.1f}% "
                  f"(CI {r1.loc[k, 'ci_lo'] * 100:+.1f}..{r1.loc[k, 'ci_hi'] * 100:+.1f})" for k in RULES if k in r1.index) + ".")
    sel_key = [k for k in extra if "evening selection effect" in k]
    if sel_key:
        w("- **The evening line cannot test back-to-backs.** Share of games with a decision quote: " + extra[sel_key[0]])
    if (OUT / "gm_posthoc.json").exists():
        ph = json.loads((OUT / "gm_posthoc.json").read_text())
        h = ph[0]
        w(f"- **One lead, outside the schedule question, found AFTER the grid (§5b):** at the last fetch before tip, "
          f"betting the moneyline side whose best soft price beats Pinnacle's no-vig by EV ≥ 0.02 made "
          f"{h['units']:+.1f} units on {h['bets']} bets ({h['roi'] * 100:+.1f}%, CI {h['ci'][0] * 100:+.1f}.."
          f"{h['ci'][1] * 100:+.1f}), positive in all five graded seasons; {h['dog_share'] * 100:.0f}% of its bets are "
          "underdogs. It passes bars 4-10 post hoc and cannot be checked for closing-line value, because the decision "
          "IS the close. It was not chosen by the pre-registered rule and is not a candidate.")
    w("")
    w(f"Search size: {3 * 4 * 3 * len(EV_STEPS)} pre-registered bet cells (3 markets × 4 decision points × 3 variants × "
      f"{len(EV_STEPS)} EV cuts), {len(rules[rules['price_set'] == 'best'])} blind-rule cells (4 rules × 4 decision "
      f"points × 2 markets), {len(ABLATION)} ablation variants × 12 market/decision pairs × 5 graded seasons "
      "(diagnostic, not bet), and 2 post-hoc cells (§5b). DraftKings-only columns are reported beside each cell, "
      "not searched.")
    w("")

    # ── 1. Verdict on the owner's question
    w("## 1. Is the schedule already in the line?")
    w("")
    sp = inline[(inline["market"] == "spreads")]
    piv = sp.pivot_table(index="feature", columns="quantity", values="coef")
    ci = sp[sp["quantity"] == "residual"].set_index("feature")[["lo90", "hi90", "p"]]
    mv = sp[sp["quantity"] == "open_to_close_move"].set_index("feature")[["coef", "lo90", "hi90"]]
    rows = []
    for f in INLINE_SIDE:
        rows.append({"input": f, "points the line gives it": _f(piv.loc[f, "line_expected"], 2),
                     "points the result moved": _f(piv.loc[f, "actual"], 2),
                     "residual (result − line)": _f(piv.loc[f, "residual"], 2),
                     "residual 90% CI": f"{ci.loc[f, 'lo90']:+.2f} .. {ci.loc[f, 'hi90']:+.2f}",
                     "line move open→close": _f(mv.loc[f, "coef"], 2)})
    n_sp = int(sp["n"].iloc[0])
    w(f"Home-margin points per unit of each schedule input, with home and away team-season fixed effects "
      f"(so team strength is held constant), {n_sp:,} regular-season games 2020-21..2025-26 at Pinnacle's close. "
      "\"Points the line gives it\" is the change in Pinnacle's closing expected home margin; \"points the result "
      "moved\" is the change in the actual home margin; the residual is their difference (the cover margin). "
      "A schedule effect the line prices correctly shows a residual whose interval covers zero. The last column is how "
      "far Pinnacle's spread moved between its first quote and its close (home number; + = toward the visitor).")
    w("")
    w(_md(pd.DataFrame(rows)))
    w("")
    tt = inline[inline["market"] == "totals"]
    pt = tt.pivot_table(index="feature", columns="quantity", values="coef")
    ct = tt[tt["quantity"] == "residual"].set_index("feature")[["lo90", "hi90"]]
    rows = [{"input": f, "points the line gives it": _f(pt.loc[f, "line_expected"], 2),
             "points the total moved": _f(pt.loc[f, "actual"], 2), "residual": _f(pt.loc[f, "residual"], 2),
             "residual 90% CI": f"{ct.loc[f, 'lo90']:+.2f} .. {ct.loc[f, 'hi90']:+.2f}"} for f in INLINE_TOT]
    w("Totals, same construction (points of total):")
    w("")
    w(_md(pd.DataFrame(rows)))
    w("")
    av = inline[inline["market"] == "spreads_avail_d19"]
    if len(av):
        pa_ = av.pivot_table(index="feature", columns="quantity", values="coef")
        ca_ = av[av["quantity"] == "residual"].set_index("feature")[["lo90", "hi90"]]
        rows = [{"input (home minus away)": f, "points the 19Z line gives it": _f(pa_.loc[f, "line_expected"], 2),
                 "points the result moved": _f(pa_.loc[f, "actual"], 2), "residual": _f(pa_.loc[f, "residual"], 2),
                 "residual 90% CI": f"{ca_.loc[f, 'lo90']:+.2f} .. {ca_.loc[f, 'hi90']:+.2f}"} for f in INLINE_AVAIL]
        w(f"Availability, same construction at the 19Z line ({int(av['n'].iloc[0]):,} games). Units: per 48 "
          "player-minutes out (d_o_min, d_o_new, dd_o_min) or per unit of PIE share out (d_o_pie). A sign check on the "
          "inputs themselves: the line must move against a team missing players. The four inputs are entered together, "
          "so each is net of the others.")
        w("")
        w(_md(pd.DataFrame(rows)))
        w("")
    w("Rest permutations at Pinnacle's close (home rest days × visitor rest days; 0 = second night of a "
      "back-to-back):")
    w("")
    pr = perm.copy()
    pr["home cover (90% CI)"] = [f"{a:.3f} ({lo:.3f}-{hi:.3f})" for a, lo, hi in
                                 zip(pr["home_cover"], pr["cover_lo90"], pr["cover_hi90"])]
    pr["line home margin"] = pr["line_home_margin"].map(lambda v: f"{v:+.2f}")
    pr["actual home margin"] = pr["actual_home_margin"].map(lambda v: f"{v:+.2f}")
    pr["residual (90% CI)"] = [f"{a:+.2f} ({lo:+.2f}..{hi:+.2f})" for a, lo, hi in
                               zip(pr["residual"], pr["resid_lo90"], pr["resid_hi90"])]
    w(_md(pr[["home_r", "away_r", "games", "home cover (90% CI)", "line home margin", "actual home margin",
              "residual (90% CI)"]].rename(columns={"home_r": "home rest", "away_r": "visitor rest"})))
    w("")

    # ── 2. Ablation
    w("## 2. The test: market-anchored model, feature groups ablated")
    w("")
    w("Logistic regression with Pinnacle's no-vig logit as an offset (the soft-book consensus at the "
      "`eve_soft` decision point). Walk-forward: fit on every season before S, grade S, for S = 2021-22 .. 2025-26. "
      "Each cell is the change in log loss against the market alone, in thousandths, pooled over the graded "
      "seasons (negative = better than the market). Unpenalised fits are diagnostics; the `_r` rows are ridge fits "
      "whose penalty is chosen by leave-one-season-out inside the training seasons — those are the ones bet.")
    w("")
    a = abl.copy()
    a["lln"] = a["logloss"] * a["n"]
    a["brn"] = a["brier"] * a["n"]
    pool = a.groupby(["market", "slot", "variant"]).agg(n=("n", "sum"), lln=("lln", "sum"), brn=("brn", "sum"))
    pool["ll"] = pool["lln"] / pool["n"]
    pool["br"] = pool["brn"] / pool["n"]
    base = pool.xs("M", level="variant")
    pool["dll"] = (pool["ll"] - base["ll"].reindex(pool.index.droplevel(2)).values) * 1000
    pool["dbr"] = (pool["br"] - base["br"].reindex(pool.index.droplevel(2)).values) * 1000
    tab = pool["dll"].unstack("variant")[list(ABLATION)].round(2)
    tab.insert(0, "games", base["n"].reindex(tab.index).astype(int).values)
    tab.insert(1, "market log loss", base["ll"].reindex(tab.index).round(4).values)
    w(_md(tab.reset_index()))
    w("")
    w("Brier change (thousandths), same layout:")
    w("")
    tb = pool["dbr"].unstack("variant")[list(ABLATION)].round(3)
    w(_md(tb.reset_index()))
    w("")
    # whole-day bootstrap CI of the pooled change for the ridge variants
    rows = []
    for (mk, sl), x in preds.groupby(["market", "slot"]):
        for v in ("S_r", "all_r", "S", "all"):
            d = (x[f"ll_{v}"] - x["ll_M"]).to_numpy() * 1000
            day = x["gd"].astype(str).to_numpy()
            df = pd.DataFrame({"d": day, "v": d}).groupby("d")["v"].agg(["sum", "count"])
            rng = np.random.default_rng(BOOT_SEED)
            idx = rng.integers(0, len(df), size=(BOOT_N, len(df)))
            bs = df["sum"].to_numpy()[idx].sum(1) / df["count"].to_numpy()[idx].sum(1)
            per = x.assign(dd=d).groupby("season")["dd"].mean()
            rows.append({"market": mk, "slot": sl, "variant": v, "Δ log loss ×1000": f"{d.mean():+.2f}",
                         "90% CI": f"{np.percentile(bs, 5):+.2f} .. {np.percentile(bs, 95):+.2f}",
                         "by season": " / ".join(f"{s % 100:02d}:{per[s]:+.1f}" for s in per.index)})
    w("Pooled change with a whole-day bootstrap 90% CI (4,000 resamples, seed 7) and the per-season values:")
    w("")
    w(_md(pd.DataFrame(rows)))
    w("")
    lam = abl[abl["variant"].isin(["S_r", "all_r"])].groupby(["variant", "ridge_lambda"]).size().unstack(fill_value=0)
    w("Ridge penalty chosen (count of market × decision point × season fits). The grid tops out at 30; "
      "a penalty of 30 leaves the model within a hair of the market alone:")
    w("")
    w(_md(lam.reset_index()))
    w("")

    # ── 3. Coefficients
    w("## 3. Schedule coefficients (ridge-free logistic, market offset, fit on 2020-21..2024-25)")
    w("")
    w("Size and sign of every schedule input, unpenalised, with 90% CIs. Units: change in the log-odds of a home "
      "cover / home win / over per unit of the input. For the spread at 19Z the last column converts to points with "
      "the measured slope of cover probability per point at the line (about 0.4/σ, σ = the SD of the cover margin).")
    w("")
    sig = extra.get("sigma_spreads", 13.0)
    for mk in MARKETS:
        c = coefs[(coefs["fit"] == "fit_2021_2025") & (coefs["market"] == mk) & (coefs["slot"] == "d19")
                  & (coefs["variant"] == "S")]
        c = c[c["feature"] != "const"].copy()
        c["coef (90% CI)"] = [f"{b:+.3f} ({lo:+.3f}..{hi:+.3f})" for b, lo, hi in zip(c["coef"], c["lo90"], c["hi90"])]
        c["p"] = c["p"].map(lambda v: f"{v:.3f}")
        cols = ["feature", "coef (90% CI)", "p"]
        if mk == "spreads":
            c["≈ points"] = (c["coef"] / 4 / (0.3989 / sig)).map(lambda v: f"{v:+.2f}")
            cols.append("≈ points")
        w(f"**{MK_NAME[mk]}, 19Z, n = {int(c['n'].iloc[0]):,}**")
        w("")
        w(_md(c[cols]))
        w("")
    nsig = coefs[(coefs["fit"] == "fit_2021_2025") & (coefs["variant"] == "S") & (coefs["feature"] != "const")]
    w(f"Across all four decision points and three markets, {int((nsig['p'] < 0.05).sum())} of {len(nsig)} schedule "
      f"coefficients have p < 0.05 (about {0.05 * len(nsig):.0f} expected by chance alone).")
    w("")

    # ── 4. EV grid
    w("## 4. From probabilities to bets: the EV grid")
    w("")
    w("One bet a game per market: the side with the larger EV = model probability × decimal price − 1, at the best "
      "BETTABLE price (`config.BEST_LINE_BOOKMAKERS`: " + ", ".join(BETTABLE) + ") among books quoting Pinnacle's "
      f"exact number in the same fetch; price −200 or better. Units: one unit to win, risk capped at 3. "
      f"Graded 2021-22..2025-26. Pre-registered search: 3 markets × 4 decision points × 3 variants × "
      f"{len(EV_STEPS)} EV cuts = {3 * 4 * 3 * len(EV_STEPS)} cells (the DraftKings-only column is reported beside "
      "each cell, not searched). Each block is a neighbourhood: read the row, not the best cell.")
    w("")
    gb = grid[grid["price_set"] == "best"].copy()
    gd = grid[grid["price_set"] == "dk"].set_index(["market", "slot", "variant", "ev_cut"])
    for mk in MARKETS:
        w(f"### {MK_NAME[mk]}")
        w("")
        rows = []
        for (sl, v), x in gb[gb["market"] == mk].groupby(["slot", "variant"], sort=False):
            for _, r in x.sort_values("ev_cut").iterrows():
                k = (mk, sl, v, r["ev_cut"])
                dk = gd.loc[k] if k in gd.index else None
                rows.append({"decision": sl, "variant": v, "EV ≥": f"{r['ev_cut']:.2f}", "bets": int(r["bets"]),
                             "units": _f(r.get("units", np.nan), 1), "ROI": _f(r.get("roi", np.nan), 1, True),
                             "90% CI": (f"{r['ci_lo'] * 100:+.1f}..{r['ci_hi'] * 100:+.1f}" if r["bets"] else "—"),
                             **{f"{S % 100:02d}": (f"{r[f'roi_{S}'] * 100:+.0f} ({int(r[f'n_{S}'])})"
                                                  if r["bets"] and r.get(f"n_{S}", 0) else "—") for S in GRADED},
                             "halves": (f"{r['roi_h1'] * 100:+.0f}/{r['roi_h2'] * 100:+.0f}" if r["bets"] else "—"),
                             "CLV med": (_f(r["clv_med"], 1, True) if r["bets"] and sl != "pre" else "n/a"),
                             "DK bets / ROI": (f"{int(dk['bets'])} / {_f(dk['roi'], 1, True)}"
                                               if dk is not None and dk["bets"] else "0")})
        w(_md(pd.DataFrame(rows)))
        w("")
    w("Blind baselines on every priced game at the same decision points (best bettable price at Pinnacle's number; "
      "side a = home / over, b = away / under):")
    w("")
    bb = blind.copy()
    bb["ROI"] = bb["roi"].map(lambda v: _f(v, 1, True))
    bb["units"] = bb["units"].map(lambda v: _f(v, 1))
    bb["90% CI"] = [f"{lo * 100:+.1f}..{hi * 100:+.1f}" if not np.isnan(lo) else "—"
                    for lo, hi in zip(bb.get("ci_lo", np.nan), bb.get("ci_hi", np.nan))]
    w(_md(bb[["market", "slot", "side", "bets", "units", "ROI", "90% CI"]]))
    w("")

    # ── 5. Candidates and bars
    w("## 5. Candidates and the pre-registered bars")
    w("")
    w("The chosen cell per market is the pre-registered rule: the most units on 2021-22..2024-25 among cells with "
      "≥150 bets there (2025-26 never chooses). The best schedule-model cell and best every-group cell per market are "
      "also run through the bars, because the owner's question is about those models. Bars 1-3 hold by construction "
      "(best bettable price, units, every priced game scored); 12 is structural (§7); 13 does not apply to team "
      "markets. Bar 11 cannot be met at the `pre` decision point: that decision IS the close, so no later price exists.")
    w("")
    rows = []
    for r in bars:
        b = r["bars"]
        rows.append({"candidate": r["tag"], "cell": r["name"], "bets": int(r["bets"]),
                     "units": _f(r["units"], 1), "ROI": _f(r["roi"], 1, True),
                     "90% CI": f"{r['ci_lo'] * 100:+.1f}..{r['ci_hi'] * 100:+.1f}",
                     "DK only": f"{r['dk_bets']} / {_f(r['dk_roi'], 1, True)}",
                     "placebo mean ROI": _f(r["placebo_mean"], 1, True),
                     "failed bars": ", ".join(k for k, v in b.items() if not v) or "none",
                     "passes all": "YES" if r["passes_all"] else "no"})
    w(_md(pd.DataFrame(rows)))
    w("")
    w("Bet lists (parquet): " + "; ".join(sorted({f"`{Path(r['bet_list']).name}`" for r in bars})))
    w("")
    if (OUT / "gm_posthoc.json").exists():
        ph = json.loads((OUT / "gm_posthoc.json").read_text())
        w("### 5b. POST-HOC lead: the pre-tip moneyline, market alone (not a candidate)")
        w("")
        w("Seen after the grid ran, so it is reported, not shipped. Rule: at the last fetch before tip, take the "
          "moneyline side where the best bettable price beats Pinnacle's proportional no-vig probability by EV >= cut. "
          "Produced by `stage_posthoc` in `scripts/nba_game_model_lab.py` (`gm_posthoc.json`, `gm_pretip_diag.json`). "
          "This is a market-relative rule with no model in it, so it most likely belongs to the key that owns "
          "`scripts/nba_game_market_lab.py`; it is handed over, not claimed.")
        w("")
        rows = []
        for h in ph:
            rows.append({"cell": h["name"], "bets": h["bets"], "units": f"{h['units']:+.1f}",
                         "ROI": f"{h['roi'] * 100:+.1f}%", "90% CI": f"{h['ci'][0] * 100:+.1f}..{h['ci'][1] * 100:+.1f}",
                         "by season": " / ".join(f"{int(s) % 100:02d}:{v[1] * 100:+.0f}({v[0]})"
                                                 for s, v in h["by_season"].items()),
                         "halves": f"{h['halves'][0] * 100:+.0f}/{h['halves'][1] * 100:+.0f}",
                         "underdog share": f"{h['dog_share'] * 100:.0f}%",
                         "blind underdog ROI": f"{h['blind_fav_dog_roi'] * 100:+.1f}%",
                         "placebo mean": f"{h['placebo_mean'] * 100:+.1f}%",
                         "failed bars": ", ".join(k for k, v in h["bars"].items() if not v) or "none"})
        w(_md(pd.DataFrame(rows)))
        w("")
        if (OUT / "gm_pretip_diag.json").exists():
            dg = json.loads((OUT / "gm_pretip_diag.json").read_text())
            w("Timing checks on the EV >= 0.02 bets (is it a soft book lagging Pinnacle?):")
            w("")
            g_ = dg.get("pre_gap", {})
            w("- Pinnacle's last update minus the bet book's, same fetch: " + "; ".join(
                f"{k}: {int(v['bets'])} bets {v['roi'] * 100:+.1f}%" for k, v in g_.items()))
            mv_ = dg["pre"]["by_pin_move"]
            w("- Pinnacle's move since its previous fetch, relative to the bet side: " + "; ".join(
                f"{k}: {v['bets']} bets {v['roi'] * 100:+.1f}%" for k, v in mv_.items()))
            bk = dg["pre"]["by_book"]
            w("- By book: " + "; ".join(f"{k} {v['bets']} bets {v['roi'] * 100:+.1f}%" for k, v in bk.items()))
            ld = dg["pre"]["by_lead"]
            w("- By hours before tip: " + "; ".join(
                f"{k} {int(v['bets'])} bets {v['roi'] * 100:+.1f}%" for k, v in ld.items() if v["bets"]))
            w("- The same rule at 19Z (`d19`, market alone) is in the §4 moneyline grid: it does not hold there.")
            h0 = ph[0]
            w(f"- {h0['within_15min']} of {h0['bets']} bets were decided within 15 minutes of the scheduled tip, so "
              "this exists only for a fetch-and-bet loop running in that window.")
            w("- The §4 `DK bets / ROI` column and the DraftKings row above are different populations: the first is "
              "DraftKings' own price clearing the cut, the second is DraftKings being the best of eight books.")
            bk_ = dg.get("dog_ev_buckets", [])
            if bk_:
                w("- Every underdog at the pre-tip fetch, bucketed by its EV against Pinnacle's no-vig (a rule that is "
                  "mostly underdogs must beat blind underdogs, and the effect should rise with EV): " + "; ".join(
                    f"[{d['ev_from']:+.2f}, {d['ev_to']:+.2f}) {d['bets']} bets "
                    + (f"{d['roi'] * 100:+.1f}% (median price {d['median_price']:+.0f})" if d['bets'] else "")
                    for d in bk_))
            w("")

    # ── 6. Blind schedule rules
    w("## 6. The three published schedule spots, replicated as blind rules (2020-21..2025-26)")
    w("")
    for k, v in RULES.items():
        w(f"- `{k}`: {v}")
    w("")
    rr = rules[rules["price_set"] == "best"].copy()
    rows = []
    for _, r in rr.iterrows():
        rows.append({"rule": r["rule"], "market": MK_NAME[r["market"]], "decision": r["slot"],
                     "games": int(r["eligible_games"]), "bets": int(r["bets"]),
                     "win rate": (f"{r['win_rate']:.3f}" if r["bets"] else "—"),
                     "units": _f(r.get("units", np.nan), 1), "ROI": _f(r.get("roi", np.nan), 1, True),
                     "90% CI": (f"{r['ci_lo'] * 100:+.1f}..{r['ci_hi'] * 100:+.1f}" if r["bets"] else "—"),
                     **{f"{S % 100:02d}": (f"{r[f'roi_{S}'] * 100:+.0f} ({int(r[f'n_{S}'])})"
                                          if r["bets"] and r.get(f"n_{S}", 0) else "—") for S in (2021,) + GRADED},
                     "CLV med": (_f(r["clv_med"], 1, True) if r["bets"] and r["slot"] != "pre" else "n/a")})
    w(_md(pd.DataFrame(rows)))
    w("")
    w("Bet list: `gm_rules_bets.parquet` (every rule × decision point × market at the best bettable price).")
    w("")

    # ── 7. Data checks
    w("## 7. Data checks")
    w("")
    w(f"- Odds rows (historical source): {diag['rows_historical']:,}; pre-game after excluding `in_play` and "
      f"`snapshot_at > commence_time`: {diag['rows_pregame']:,}.")
    w(f"- A FETCH = rows sharing `created_at` for a game; decision time = the newest `snapshot_at` in it. "
      f"Quote age inside a fetch, quantiles 50/90/99/99.9%: {diag['age_min_q']} minutes. Rows dropped as stale "
      f"(> {MAX_AGE_MIN} min, production's cut): {diag['rows_stale_dropped']:,}. Rows dropped as incoherent "
      f"(two-way implied sum outside 1.00-1.15): {diag['rows_incoherent_dropped']:,}.")
    for k, v in extra.items():
        if k.startswith("check_"):
            w(f"- {k[6:]}: {v}")
    w("")
    w("## 8. Definitions")
    w("")
    w("Schedule inputs (verbatim from `features/nba_schedule_features.py`):")
    w("")
    w("```")
    w(nsf.__doc__.split("DEFINITIONS (one place; the lab report copies these)")[1].split("Venue coordinates")[0]
      .strip().lstrip("-").strip())
    w("```")
    w("")
    w("Other groups, all as of the decision fetch:")
    w("")
    w("- **Availability (A)**: the latest official injury report with `report_ts` ≤ decision in which the team "
      "had SUBMITTED for that game (a NOT YET SUBMITTED team carries no information; if no report for this game "
      "exists yet the team's latest submitted report for any game is carried). Out/Doubtful players are valued by "
      f"their exponentially weighted minutes (half-life {HL_PLAYER} games played) and PIE, from box scores of games "
      f"that tipped at least {SETTLE_H:.0f}h before the decision. Inputs: minutes out (home − away, /48), PIE out, "
      "Questionable minutes, and minutes out of players who played the team's previous game (new absences).")
    w("- **Availability change (C)**: the same sums at the decision minus at the first fetch within 48h of tip "
      "(news after the line opened).")
    w(f"- **Referees (R)**: crew mean of each official's shrunk tendency, sum / (n + {REF_K:.0f}) over games on "
      "EARLIER dates: total − Pinnacle close total, home margin + close spread, fouls − league trailing mean. "
      "Crews are posted about 9 am ET, so the input is zero at the evening decision points.")
    w(f"- **Form/pace (F)**: team EWM (half-life {HL_TEAM} games) of cover margin vs the close, total − close "
      "total, and possessions vs the league trailing mean, from games finished before the decision.")
    w("- **Load (L)**: whether the team's previous game went to overtime — a RESULT, so it counts only if that "
      f"game tipped {SETTLE_H:.0f}h before the decision.")
    w("")
    (OUT / "game_model.md").write_text("\n".join(L), encoding="utf-8")
    log("report written", OUT / "game_model.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="market")
    a = ap.parse_args()
    st = a.stage
    if st in ("market", "all"):
        stage_market()
    if st in ("features", "all"):
        stage_features()
    if st in ("model", "all"):
        stage_model()
    if st in ("bets", "all"):
        stage_bets()
    if st in ("rules", "all"):
        stage_rules()
    if st in ("inline", "all"):
        stage_inline()
    if st in ("bars", "all"):
        stage_bars()
    if st in ("posthoc", "all"):
        stage_posthoc()
    if st in ("checks", "all"):
        stage_checks()
    if st in ("report", "all"):
        stage_report()
