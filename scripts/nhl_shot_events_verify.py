"""Check nhl_shot_events against things outside it.

    python -m scripts.nhl_shot_events_verify --stored        # the stored table (read once)
    python -m scripts.nhl_shot_events_verify --strength 20   # goal strength vs the league's label
    python -m scripts.nhl_shot_events_verify --source        # re-parse the cached feeds

--stored    rows and games per season against nhl_team_game_log; per team-game
            (shots on goal + goals, shootouts excluded) against shots_for, and
            goals against goals_for; the geometry (an unblocked shot on the
            wrong half of the ice, a goal from beyond the far blue line); which
            end each period was decided by and how often the feed's side
            disagreed; blocked-shot ownership; miss and block reasons by season.
--strength  for N games a season, every goal's strength and modifier as the
            league labels it (gamecenter/<id>/landing) against the decoded
            situationCode stored for the same eventId.
--source    every cached feed through the same parser: sortOrder against the
            clock, duplicate event ids, roster misses, scores, the derived end
            against the feed's, and the feed's own shot totals.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import requests
from loguru import logger

from data.db import get_connection
from data.ingestors.nhl_shot_events import (CACHE_DIR, NHL_API_BASE, NHL_HEADERS,
                                            GameMeta, game_list, parse_game)
from data.nhl_xg import _obj, load_shot_frame

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)


def _team_log() -> pd.DataFrame:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT nhl_game_id, team, season, game_type, is_home, shots_for, goals_for "
            "FROM nhl_team_game_log WHERE season >= 2019").fetchall()
        conn.commit()
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=["nhl_game_id", "team", "season", "game_type",
                                       "is_home", "shots_for", "goals_for"])


def stored_checks() -> None:
    df = load_shot_frame()
    log = _team_log()
    kind = _obj(df["event_type"])
    so = _obj(df["period_type"]) == "SO"

    print("\n== rows per season by event type (shootout attempts included)")
    print(pd.crosstab(df["season"], kind, margins=True).to_string())
    print(f"\nshootout attempts stored: {int(so.sum()):,}")

    print("\n== games stored vs games in nhl_team_game_log")
    exp = log.groupby("season")["nhl_game_id"].nunique()
    got = df.groupby("season")["nhl_game_id"].nunique()
    g = pd.DataFrame({"expected": exp, "stored": got}).fillna(0).astype(int)
    g["missing"] = g["expected"] - g["stored"]
    print(g.to_string())
    missing = sorted(set(log["nhl_game_id"]) - set(df["nhl_game_id"]))
    print(f"missing game ids ({len(missing)}): {missing[:40]}")

    print("\n== shots on goal + goals per team-game vs nhl_team_game_log.shots_for")
    sh = df[kind.isin(("shot-on-goal", "goal")) & ~so]
    cnt = sh.groupby(["nhl_game_id", "is_home"]).size().rename("pbp_shots")
    gl = df[(kind == "goal") & ~so].groupby(["nhl_game_id", "is_home"]).size().rename("pbp_goals")
    m = (log.set_index(["nhl_game_id", "is_home"])
         .join(cnt, how="left").join(gl, how="left").fillna({"pbp_shots": 0, "pbp_goals": 0})
         .reset_index())
    m = m[m["nhl_game_id"].isin(df["nhl_game_id"].unique())]
    m["diff"] = m["pbp_shots"] - m["shots_for"]
    m["gdiff"] = m["pbp_goals"] - m["goals_for"]
    by = m.groupby("season").agg(
        team_games=("diff", "size"),
        exact=("diff", lambda d: round(float((d == 0).mean()), 4)),
        within_1=("diff", lambda d: round(float((d.abs() <= 1).mean()), 4)),
        mean_diff=("diff", lambda d: round(float(d.mean()), 3)),
        pbp_total=("pbp_shots", "sum"), log_total=("shots_for", "sum"),
        goals_exact=("gdiff", lambda d: round(float((d == 0).mean()), 4)))
    print(by.to_string())
    print(f"all seasons: exact {float((m['diff'] == 0).mean()):.4f} over {len(m):,} team-games; "
          f"goals exact {float((m['gdiff'] == 0).mean()):.4f}")
    worst = m.reindex(m["diff"].abs().sort_values(ascending=False).index).head(15)
    print("worst shot mismatches:\n" + worst[["nhl_game_id", "season", "team", "is_home",
                                             "shots_for", "pbp_shots", "diff",
                                             "goals_for", "pbp_goals"]].to_string(index=False))
    gw = m[m["gdiff"] != 0]
    print(f"team-games whose goals differ: {len(gw)}\n"
          + gw.head(15)[["nhl_game_id", "season", "team", "goals_for", "pbp_goals"]].to_string(index=False))

    print("\n== geometry: unblocked, non-shootout attempts")
    ub = df[kind.isin(("shot-on-goal", "missed-shot", "goal")) & ~so]
    dist = np.hypot(89 - ub["x_norm"].astype(float), ub["y_norm"].astype(float))
    geo = pd.DataFrame({
        "season": ub["season"], "goal": _obj(ub["event_type"]) == "goal",
        "no_xy": ub["x"].isna() | ub["y"].isna(),
        "no_side": ub["attacking_net_x"].isna(),
        "wrong_half": ub["x_norm"] <= 0, "dist": dist})
    gs = geo.groupby("season").agg(
        attempts=("goal", "size"), goals=("goal", "sum"), no_xy=("no_xy", "sum"),
        no_side=("no_side", "sum"),
        share_x_norm_le_0=("wrong_half", lambda s: round(float(s.mean()), 4)),
        median_dist=("dist", lambda s: round(float(s.median()), 1)))
    gs["goals_beyond_89ft"] = geo[geo["goal"] & (geo["dist"] > 89)].groupby("season").size()
    gs["goals_beyond_89ft_share"] = (gs["goals_beyond_89ft"].fillna(0) / gs["goals"]).round(4)
    print(gs.fillna(0).to_string())

    print("\n== which end: how each event's side was decided, and the feed's agreement")
    print(pd.crosstab(df["season"], _obj(df["side_source"]).fillna("none")).to_string())
    has_feed = df["home_defending_side"].notna() & ~so & df["attacking_net_x"].notna()
    f = df[has_feed]
    feed_home_sign = np.where(_obj(f["home_defending_side"]) == "left", 1, -1)
    chosen_home_sign = np.sign(f["attacking_net_x"].astype(float)) * np.where(f["is_home"] == 1, 1, -1)
    agree = pd.Series(feed_home_sign == chosen_home_sign, index=f.index)
    per = f.assign(agree=agree).groupby("season")["agree"].agg(["size", "mean"])
    print("events where the feed names a side; share where the stored end agrees:")
    print(per.round(5).to_string())
    bad = f[~agree].groupby(["nhl_game_id", "period"]).size()
    print(f"game-periods where they disagree: {len(bad)} {list(bad.index[:20])}")

    print("\n== blocked shots")
    blk = df[kind == "blocked-shot"]
    bo = blk.assign(owner_not_shooter=_obj(blk["event_owner_team"]) != _obj(blk["shooting_team"]),
                    teammate=_obj(blk["reason"]) == "teammate-blocked")
    print(bo.groupby("season").agg(blocked=("owner_not_shooter", "size"),
                                   owner_not_shooter=("owner_not_shooter", "sum"),
                                   teammate_blocked=("teammate", "sum")).to_string())

    print("\n== reasons per game, by season")
    games = df.groupby("season")["nhl_game_id"].nunique()
    for k in ("missed-shot", "blocked-shot"):
        r = df[kind == k]
        t = pd.crosstab(r["season"], _obj(r["reason"]).fillna("(none)"))
        print(f"\n{k} per game:\n" + t.div(games, axis=0).round(2).to_string())
    per_game = pd.crosstab(df["season"], kind).div(games, axis=0).round(2)
    print("\nevents per game by type:\n" + per_game.to_string())

    print("\n== the defending goalie vs the empty-net digit (unblocked, non-shootout)")
    u = ub[ub["situation_code"].notna()]
    mis = (u["goalie_id"].isna()) != (u["empty_net"] == 1)
    print(u.assign(mis=mis).groupby("season")["mis"].agg(["size", "sum"]).to_string())
    print(f"missing situation codes (all events): {int(df['situation_code'].isna().sum())}")


def strength_check(per_season: int, seed: int = 7) -> None:
    """Every goal in a sample of games: the league's strength label and
    modifier (landing endpoint) vs the decoded situationCode stored."""
    df = load_shot_frame()
    rng = random.Random(seed)
    goals = df[_obj(df["event_type"]) == "goal"]
    sample = []
    for s, ids in df.groupby("season")["nhl_game_id"].unique().items():
        ids = sorted(ids)
        sample += rng.sample(ids, min(per_season, len(ids)))
    stored = goals[goals["nhl_game_id"].isin(sample)].set_index(["nhl_game_id", "event_id"])
    res = defaultdict(Counter)
    bad = []
    sess = requests.Session()
    sess.headers.update(NHL_HEADERS)
    for gid in sample:
        r = sess.get(f"{NHL_API_BASE}/gamecenter/{gid}/landing", timeout=30)
        r.raise_for_status()
        body = r.json()
        season = int(str(body.get("season"))[4:])
        for per in (body.get("summary") or {}).get("scoring") or []:
            if (per.get("periodDescriptor") or {}).get("periodType") == "SO":
                continue
            for g in per.get("goals") or []:
                key = (gid, g.get("eventId"))
                if key not in stored.index:
                    res[season]["not_stored"] += 1
                    bad.append((gid, g.get("eventId"), "not stored", g.get("strength")))
                    continue
                row = stored.loc[key]
                mod = g.get("goalModifier")
                official = "PS" if mod == "penalty-shot" else (g.get("strength") or "").upper()
                res[season]["goals"] += 1
                ok_strength = official == row["strength"]
                res[season]["strength_agree"] += int(ok_strength)
                official_en = int(mod == "empty-net")
                ok_en = official_en == int(row["empty_net"] or 0)
                res[season]["empty_net_agree"] += int(ok_en)
                res[season]["official_empty_net"] += official_en
                res[season]["official_pp"] += int(official == "PP")
                res[season]["official_sh"] += int(official == "SH")
                res[season]["official_ps"] += int(official == "PS")
                if not (ok_strength and ok_en):
                    bad.append((gid, g.get("eventId"), f"league {official}/{mod}",
                                f"stored {row['strength']} {row['situation_code']} "
                                f"en={row['empty_net']} {row['strength_state']}"))
    t = pd.DataFrame(res).T.fillna(0).astype(int).sort_index()
    t["strength_agree_rate"] = (t["strength_agree"] / t["goals"]).round(4)
    t["empty_net_agree_rate"] = (t["empty_net_agree"] / t["goals"]).round(4)
    print(f"\n== goal strength vs the league's label, {per_season} games a season "
          f"({len(sample)} games)\n" + t.to_string())
    tot = t.sum()
    print(f"all: {tot['strength_agree']}/{tot['goals']} strength, "
          f"{tot['empty_net_agree']}/{tot['goals']} empty net")
    print("disagreements:\n" + "\n".join(map(str, bad[:40])))


def source_checks() -> None:
    """Every cached feed through the stored parser, totals by season."""
    conn = get_connection()
    try:
        games, _ = game_list(conn, 2019, 2027)
    finally:
        conn.close()
    tot: dict[int, Counter] = defaultdict(Counter)
    side: dict[int, Counter] = defaultdict(Counter)
    sog_off, shares = [], []
    for meta in games:
        path = CACHE_DIR / f"{meta.nhl_game_id}.json.gz"
        if not path.exists():
            tot[meta.season]["not_cached"] += 1
            continue
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            pbp = json.load(fh)
        rows, diag = parse_game(pbp, meta)
        tot[meta.season].update(diag["counts"])
        tot[meta.season]["games"] += 1
        if diag["sog_feed"] != diag["sog_counted"]:
            sog_off.append((meta.nhl_game_id, diag["sog_feed"], diag["sog_counted"]))
            tot[meta.season]["feed_sog_differs"] += 1
        for per, ev in diag["sides"].items():
            side[meta.season][ev.get("how") or "undecided"] += 1
            if ev["feed"] is not None and ev["derived"] is not None:
                side[meta.season]["both"] += 1
                side[meta.season]["both_agree"] += int(ev["feed"] == ev["derived"])
            if ev.get("how") == "derived":
                shares.append((meta.season, ev["share"], ev["votes"]))
    print("\n== parser diagnostics by season\n"
          + pd.DataFrame(tot).T.fillna(0).astype(int).sort_index().to_string())
    print("\n== period ends: decided by, and derived vs feed where both exist\n"
          + pd.DataFrame(side).T.fillna(0).astype(int).sort_index().to_string())
    sh = pd.DataFrame(shares, columns=["season", "share", "votes"])
    print("\nderived-end vote share (periods decided by votes):\n"
          + sh.groupby("season")["share"].describe(percentiles=[.01, .05, .5]).round(3).to_string())
    print(f"\nfeed sog != counted (non-shootout): {len(sog_off)} games {sog_off[:20]}")


MONEYPUCK_TEAMS = ("https://moneypuck.com/moneypuck/playerData/seasonSummary/"
                   "{start}/regular/teams.csv")


def moneypuck_check(start_year: int) -> None:
    """All-situations team xGF% for one regular season, from nhl_team_game_xg,
    against MoneyPuck's public team summary for the same season (their xG,
    their model; a check that ours ranks and scales teams the same way, not
    that it is the same number). Natural Stat Trick, the other public source,
    answers HTTP 403 (a Cloudflare challenge) to scripted requests."""
    import io

    from data.ingestors.nhl_stats_ingestor import _norm_nhl
    r = requests.get(MONEYPUCK_TEAMS.format(start=start_year), timeout=30,
                     headers=NHL_HEADERS)
    r.raise_for_status()
    mp = pd.read_csv(io.StringIO(r.text))
    mp = mp[mp["situation"] == "all"].assign(team=lambda d: d["team"].map(_norm_nhl))
    mp = mp.set_index("team")[["games_played", "xGoalsFor", "xGoalsAgainst",
                               "goalsFor", "goalsAgainst"]]
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT team, count(*), sum(xgf), sum(xga), sum(gf), sum(ga) "
            "FROM nhl_team_game_xg WHERE season = ? AND game_type = 2 GROUP BY team",
            (start_year + 1,)).fetchall()
        conn.commit()
    finally:
        conn.close()
    ours = pd.DataFrame(rows, columns=["team", "gp", "xgf", "xga", "gf", "ga"]).set_index("team")
    j = ours.join(mp, how="outer")
    j["xgf_pct"] = 100 * j["xgf"] / (j["xgf"] + j["xga"])
    j["mp_xgf_pct"] = 100 * j["xGoalsFor"] / (j["xGoalsFor"] + j["xGoalsAgainst"])
    j["diff_pp"] = j["xgf_pct"] - j["mp_xgf_pct"]
    j = j.sort_values("mp_xgf_pct")
    print(f"\n== {start_year}-{str(start_year + 1)[2:]} regular season, all situations: "
          f"ours vs MoneyPuck\n" + j.round(2).to_string())
    print(f"teams {j['diff_pp'].notna().sum()}; xGF% correlation "
          f"{j['xgf_pct'].corr(j['mp_xgf_pct']):.4f}; mean |diff| "
          f"{j['diff_pp'].abs().mean():.2f} pp; max |diff| {j['diff_pp'].abs().max():.2f} pp")
    print(f"league totals: ours xG {j['xgf'].sum():.1f} vs goals {j['gf'].sum():.0f} "
          f"(ratio {j['xgf'].sum() / j['gf'].sum():.4f}); MoneyPuck xG "
          f"{j['xGoalsFor'].sum():.1f} vs goals {j['goalsFor'].sum():.0f} "
          f"(ratio {j['xGoalsFor'].sum() / j['goalsFor'].sum():.4f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stored", action="store_true")
    ap.add_argument("--strength", type=int, metavar="GAMES_PER_SEASON")
    ap.add_argument("--source", action="store_true")
    ap.add_argument("--moneypuck", type=int, nargs="+", metavar="START_YEAR",
                    help="e.g. 2023 for 2023-24")
    a = ap.parse_args()
    if a.stored:
        stored_checks()
    if a.strength:
        strength_check(a.strength)
    if a.source:
        source_checks()
    for y in a.moneypuck or ():
        moneypuck_check(y)
