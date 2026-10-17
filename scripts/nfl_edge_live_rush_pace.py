"""
Independent re-derivation of the in-play rushing-attempts UNDER at a high pace ratio
(docs/nfl_live_rush_attempts.md), plus its untested mirrors.

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_live_rush_pace

Reads ONLY the local cache (scripts/nfl_edge_lib.CACHE). No database, no Odds API,
no paid endpoint. Results in UNITS (1 unit = 1 flat bet).

CONSTRUCTION (written before any outcome in this script was looked at)
=====================================================================

DATA. nfl_live_prop_snapshots.parquet is the bought Odds API archive: one gzipped
JSON per API call. Event-odds payloads carry `timestamp` (the API snapshot time),
and per bookmaker per market a `last_update`. Every two-sided quote (over and
under at the same line, same book, same snapshot) is one row. Markets:
player_rush_attempts (the hypothesis), player_receptions and
player_pass_completions (the mirror), player_pass_attempts (reported, not
re-tested). Books: every book in the payload is restored; bets are graded at
draftkings (the published rule) and fanduel, and "best of the bettable books at
the same line" uses BETTABLE_HIST (bovada is a reference, never a venue).

DECISION TIME = the snapshot `timestamp` (ts). Game state is what had HAPPENED by
ts: a play counts only if its END (pbp end_clock_time; else snap time_of_day +
the median play duration; a play with neither is placed by linear interpolation
of the snap clock on play order inside the game) is at or before ts. From the
last such play: game_seconds_remaining (secs), quarter, score. Accrued = the
player's count over those plays only:
    carries      rush_attempt == 1 and not a two-point try, credited to
                 rusher_player_id (this reproduces the official log exactly)
    receptions   complete_pass == 1, not a two-point try, receiver_player_id
    completions  complete_pass == 1, not a two-point try, passer_player_id
Player identity: the quote's name is matched to the player log row for the SAME
game (both teams), on an accent/suffix/punctuation-insensitive full name, then
on first-initial + surname if that is unique in the game. Unmatched quotes are
dropped and counted. pbp is joined by gsis id, never by name.

PACE RATIO (the docs' definition, quoted from scripts/nfl_live_prop_state.py and
nfl/live_model/models/rush_attempt_pace.py):
    elapsed_min  = max((3600 - secs) / 60, 1)
    pace_so_far  = accrued / elapsed_min
    pace_needed  = (line - accrued) / (secs / 60)
    pace_ratio   = pace_needed / pace_so_far
GATES (as published): 240 <= secs <= 3600 (regulation only), accrued >= 1,
line > accrued, both prices present, the bet side's price >= -140.

THE PUBLISHED RULE, GRADED AS STATED FIRST: bet the UNDER when pace_ratio >= 1.25,
at DraftKings, price >= -140, ONE bet per player per game = the first qualifying
quote in time. Graded against the player's official final carries
(player log), at the DK quoted under price; win if final < line, push if equal.

THE ARCHIVE'S DESIGN, MEASURED BEFORE ANY OUTCOME (not "every five minutes"):
the bought pull requested five fixed game-clock points per game (2100, 1800,
1500, 900, 600 s left, floored to the API's 5-minute grid), so 538 games carry
five snapshots and 286 carry one; consecutive snapshots of a game are 5-40 min
apart (median 20). DK carries quotes sit at ~35-38 min left (Q2), halftime
(29% of them), ~28 (early Q3), ~17 and ~13 (Q4). So "game time" is reported
as PHASE: Q2 in play / halftime (last play in Q2, next play in Q3) / Q3 / Q4.

NEIGHBOURHOOD: pace cut {1.0, 1.1, 1.25, 1.4, 1.6, 2.0, 2.5} x phase; by season
(2023/2024/2025), book (DK/FD/best-of-bettable at the same line and ts), player
role, score state, early (weeks 1-9) vs late (10+ incl. postseason). The grid is
DESCRIPTIVE, not a search: 1.25 / -140 / 240 s are fixed by the repo, so nothing
in the published rule is fitted here; it is graded on 2023-25 as stated, and
2023-25 were all read by the repo when the market and the side were chosen (no
hold-out exists for it in this archive). Role is fixed
BEFORE the bet from the market's own view: the lead back is the player with the
highest rush-attempts line on his team in the first archived snapshot of that
game; QB if the log position is QB; else "other". Score state = the player's
team lead at ts: leading 8+, within 7, trailing 8+.

STRICT LOW-VOLUME CELLS: pace >= 1.5 & >= 20 min left; pace >= 2.0 & >= 20 min
left; pace >= 1.5 & team leading 8+; pace >= 2.0 & lead back.

BASELINE (the control the repo never ran): the BLIND under - same gates, same
first-quote-per-player, no pace cut. The live market is documented to lean over,
so the pace rule is judged on its increment over this, not on its absolute ROI.

REPRODUCTION: the repo's two constructions are run separately because they are
different populations: nfl_live_prop_staleness.qualifying() is DK-only (its
"first qualifying quote" row is the 874), nfl_live_prop_rule.report() has no
book filter (DK and FD share a ts, first quote either book; the doc's season
rows sum to 893). Both on log-matched finals only (the original's join had no
2023-24 postseason); postseason recovered from pbp finals is reported apart.
Matching sensitivity: the original counted a play at its SNAP (time_of_day);
this counts it at its END. The count of first-qualifying bets that change is
printed.

PLACEBO: the same rule with each quote's accrued count replaced by the accrued
count of a RANDOM other quote in the same (season, minutes-left bin, line bin)
cell. It keeps the price, line and clock distribution and breaks the link to the
player's own pace. If the mechanism is the player's pace, the placebo returns
roughly minus the vig. 200 permutations; reported as the distribution of ROI.

PLACEABILITY. DK suspends at the snap, and the archive is point-in-time API
snapshots, so a quote may not have been bettable. Measured proxies:
  (a) stoppage vs live drive: the gap from the last play's end before ts to the
      next play's snap after ts. Halftime / quarter break / a gap >= 120 s is a
      stoppage; a gap < 60 s is mid-drive. Halftime is the one state where a
      snap suspension cannot bite.
  (b) FRESHNESS (the primary proxy): market last_update vs ts, and whether any
      play, or any carry by this player, ENDED between last_update and ts. Fresh
      = no play since the book's own update, i.e. the price was hung on the
      state the rule reads. Graded fresh vs stale.
  (c) the price unchanged across >= 2 consecutive archived snapshots of that
      player at that book (same line, same over and under price as the previous
      snapshot), with the gap between them reported. Across 20+ game-minutes an
      unchanged price is as consistent with a frozen board as a stable one.
  (d) quotes hung on a line the player had already passed: was the line
      already passed at the book's own last_update (a frozen board)?

MIRROR (pre-registered on 2023-24, 2025 read ONCE): OVER when pace_ratio <= cut,
cut chosen on 2023-24 from {0.4, 0.5, 0.6, 0.7, 0.8} as the cut with the highest
90% CI lower bound (>= 60 bets); and the UNDER at >= 1.25 / OVER at <= cut on
receptions and completions, same gates. Benjamini-Hochberg over every 2025
read. Caveat known in advance: the doc's bucket table that suggested the over
pooled 2023-25, so 2025 is not fully unseen for that idea.

Intervals: 90% cluster bootstrap on game (scripts.nfl_edge_lib.summarize).
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

import scripts.nfl_edge_lib as L

QUOTES_CACHE = L.CACHE / "nfl_edge_live_quotes.parquet"
STATE_CACHE = L.CACHE / "nfl_edge_live_state.parquet"
MARKETS = {"player_rush_attempts": "carries", "player_receptions": "receptions",
           "player_pass_completions": "completions", "player_pass_attempts": "attempts"}
SEASONS = (2023, 2024, 2025)

TEAM = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def norm(name) -> str:
    if not isinstance(name, str):
        return ""
    s = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name)      # "Lamar Jackson (BAL)"
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace(".", " ").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return re.sub(r"[^a-z]", "", s)


def initial_last(name) -> str:
    if not isinstance(name, str):
        return ""
    s = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", " ", s).replace(".", " ")
    parts = [p for p in re.split(r"\s+", s.strip()) if p]
    if not parts:
        return ""
    return parts[0][0] + "|" + re.sub(r"[^a-z]", "", parts[-1])


# ─── 0. restore the archive ───────────────────────────────────────────────

def restore() -> pd.DataFrame:
    if QUOTES_CACHE.exists():
        return pd.read_parquet(QUOTES_CACHE)
    import hashlib
    blobs = pd.read_parquet(L.CACHE / "nfl_live_prop_snapshots.parquet",
                            columns=["rel_path", "sha256", "content_gz"])
    rows, bad = [], 0
    for rel, sha, gz in blobs.itertuples(index=False):
        raw = gzip.decompress(bytes(gz))
        if hashlib.sha256(raw).hexdigest() != sha:
            bad += 1
            continue
        p = json.loads(raw)
        if not isinstance(p, dict) or "_error" in p or not isinstance(p.get("data"), dict):
            continue
        dat = p["data"]
        for bk in dat.get("bookmakers") or []:
            for mk in bk.get("markets") or []:
                if mk.get("key") not in MARKETS:
                    continue
                for oc in mk.get("outcomes") or []:
                    if oc.get("point") is None or oc.get("price") is None:
                        continue
                    rows.append((rel, p.get("timestamp"), p.get("previous_timestamp"),
                                 dat.get("id"), dat.get("commence_time"),
                                 dat.get("home_team"), dat.get("away_team"),
                                 bk.get("key"), bk.get("last_update"), mk.get("key"),
                                 mk.get("last_update"), oc.get("description"),
                                 str(oc.get("name", "")).lower(), float(oc["point"]),
                                 float(oc["price"])))
    if bad:
        raise SystemExit(f"{bad} archive files fail their checksum")
    cols = ["file", "ts", "prev_ts", "event_id", "commence_time", "home_name", "away_name",
            "book", "book_update", "market", "mkt_update", "player_name", "side", "line",
            "price"]
    d = pd.DataFrame(rows, columns=cols)
    for c in ("ts", "prev_ts", "commence_time", "book_update", "mkt_update"):
        d[c] = pd.to_datetime(d[c], utc=True, errors="coerce")
    key = ["file", "ts", "prev_ts", "event_id", "commence_time", "home_name", "away_name",
           "book", "book_update", "market", "mkt_update", "player_name", "line"]
    d = d.drop_duplicates(key + ["side"], keep="last")
    w = d.pivot_table(index=key, columns="side", values="price", aggfunc="last").reset_index()
    w = w.rename(columns={"over": "over_price", "under": "under_price"})
    w = w.dropna(subset=["over_price", "under_price"]).reset_index(drop=True)
    w.columns.name = None
    w.to_parquet(QUOTES_CACHE, index=False)
    return w


# ─── 1. game state at the quote, no look-ahead ────────────────────────────

PBP_COLS = ["game_id", "play_id", "time_of_day", "end_clock_time", "game_seconds_remaining",
            "qtr", "posteam", "home_team", "away_team", "total_home_score",
            "total_away_score", "rush_attempt", "complete_pass", "two_point_attempt",
            "rusher_player_id", "receiver_player_id", "passer_player_id"]
STAT_SPEC = {"carries": ("rush_attempt", "rusher_player_id"),
             "receptions": ("complete_pass", "receiver_player_id"),
             "completions": ("complete_pass", "passer_player_id")}


def load_pbp() -> pd.DataFrame:
    p = pd.concat([pd.read_parquet(L.CACHE / f"pbp_{s}.parquet", columns=PBP_COLS)
                   for s in SEASONS], ignore_index=True)
    p = p.sort_values(["game_id", "play_id"]).reset_index(drop=True)
    snap = pd.to_datetime(p["time_of_day"], utc=True, errors="coerce", format="mixed")
    end = pd.to_datetime(p["end_clock_time"], utc=True, errors="coerce", format="mixed")
    snap_us = snap.astype("datetime64[us, UTC]").astype("int64").where(snap.notna())
    snap_f = snap_us.astype(float).groupby(p["game_id"]).transform(
        lambda s: s.interpolate(limit_direction="both"))
    p["snap"] = pd.to_datetime(snap_f, unit="us", utc=True)
    dur = (end - snap).dt.total_seconds()
    med = float(dur[(dur > 0) & (dur < 60)].median())
    ok = end.notna() & (dur >= 0) & (dur < 120)
    p["known_at"] = p["snap"] + pd.to_timedelta(med, unit="s")
    p.loc[ok, "known_at"] = end[ok].astype(p["known_at"].dtype)
    span = p.groupby("game_id")["snap"].agg(["min", "max"])
    hrs = (span["max"] - span["min"]).dt.total_seconds() / 3600
    bad = hrs[(hrs < 1.5) | (hrs > 7.0)]
    if len(bad):
        raise SystemExit(f"{len(bad)} games with implausible wall-clock spans: {bad.head()}")
    p.attrs["median_play_s"] = med
    return p.dropna(subset=["known_at"])


def map_games(q: pd.DataFrame) -> pd.DataFrame:
    g = L.games()[["game_id", "season", "week", "game_type", "home_team", "away_team",
                   "gameday"]]
    ev = q[["event_id", "commence_time", "home_name", "away_name"]].drop_duplicates("event_id")
    ev["home_team"] = ev["home_name"].map(TEAM)
    ev["away_team"] = ev["away_name"].map(TEAM)
    loc = ev["commence_time"].dt.tz_convert("America/New_York")
    ev["gameday"] = loc.dt.strftime("%Y-%m-%d")
    m = ev.merge(g, on=["home_team", "away_team", "gameday"], how="left")
    miss = m["game_id"].isna().values
    if miss.any():   # a late UTC kickoff can carry the next calendar day
        alt = ev[miss].copy()
        alt["gameday"] = (alt["commence_time"].dt.tz_convert("America/New_York")
                          - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
        m2 = alt.merge(g, on=["home_team", "away_team", "gameday"], how="left")
        m = pd.concat([m[~miss], m2], ignore_index=True)
    return m[["event_id", "game_id", "season", "week", "game_type"]]


def match_players(q: pd.DataFrame) -> pd.DataFrame:
    log = L.player_log()
    log = log[log["season"].isin(SEASONS)].copy()
    log["gid"] = log["game_id"].str.replace("^NFL_", "", regex=True)
    log["nk"] = log["player_name"].map(norm)
    log["ik"] = log["player_name"].map(initial_last)
    keep = ["gid", "player_id", "pos", "team", "carries", "receptions", "completions",
            "attempts"]
    a = log.drop_duplicates(["gid", "nk"], keep=False)[keep + ["nk"]]
    b = log.drop_duplicates(["gid", "ik"], keep=False)[keep + ["ik"]]
    pl = q[["game_id", "player_name"]].drop_duplicates().copy()
    pl["nk"] = pl["player_name"].map(norm)
    pl["ik"] = pl["player_name"].map(initial_last)
    m1 = pl.merge(a, left_on=["game_id", "nk"], right_on=["gid", "nk"], how="left")
    hit = m1["player_id"].notna().values
    m1 = m1[hit].assign(match="full_name")
    m2 = pl[~pl.set_index(["game_id", "player_name"]).index.isin(
        m1.set_index(["game_id", "player_name"]).index)]
    m2 = m2.merge(b, left_on=["game_id", "ik"], right_on=["gid", "ik"], how="left")
    m2["match"] = np.where(m2["player_id"].notna(), "initial_surname", "unmatched")
    # Third pass, for games the log does not carry (2023-24 postseason): the
    # player's id from his OWN season's log rows, if the name is unique in that
    # season and his team that season is one of the two teams in this game. The
    # final then comes from play-by-play, which reproduces the official log on
    # every player-game where both exist (VERIFY 1).
    m3 = m2[m2["match"] == "unmatched"][["game_id", "player_name", "nk"]].copy()
    m2 = m2[m2["match"] != "unmatched"]
    m3["season"] = m3["game_id"].str.slice(0, 4).astype(int)
    m3["away"] = m3["game_id"].str.split("_").str[2]
    m3["home"] = m3["game_id"].str.split("_").str[3]
    sl = log.sort_values("week").drop_duplicates(["season", "player_id"], keep="last")
    sl = sl.drop_duplicates(["season", "nk"], keep=False)[["season", "nk", "player_id",
                                                           "pos", "team"]]
    m3 = m3.merge(sl, on=["season", "nk"], how="left")
    ok = m3["player_id"].notna() & ((m3["team"] == m3["home"]) | (m3["team"] == m3["away"]))
    m3["match"] = np.where(ok, "season_name_pbp_final", "unmatched")
    m3.loc[~ok, ["player_id", "pos", "team"]] = np.nan
    out = pd.concat([m1, m2, m3], ignore_index=True)
    return out[["game_id", "player_name", "player_id", "pos", "team", "carries",
                "receptions", "completions", "attempts", "match"]]


def _asof(left: pd.DataFrame, col: str, right: pd.DataFrame, rcol: str, by: str,
          take: list, direction: str = "backward") -> pd.DataFrame:
    """merge_asof that returns `take` aligned to left's index."""
    ll = left[[col, by]].reset_index().dropna(subset=[col])
    ll[col] = ll[col].astype("datetime64[us, UTC]")
    ll = ll.sort_values(col)
    rr = right[[rcol, by] + [t for t in take if t != rcol]].dropna(subset=[rcol]).copy()
    rr[rcol] = rr[rcol].astype("datetime64[us, UTC]")
    rr = rr.sort_values(rcol)
    j = pd.merge_asof(ll, rr, left_on=col, right_on=rcol, by=by, direction=direction,
                      allow_exact_matches=True, suffixes=("", "_r"))
    return j.set_index("index")[take].reindex(left.index)


def build_state() -> pd.DataFrame:
    if STATE_CACHE.exists():
        return pd.read_parquet(STATE_CACHE)
    q = restore()
    q = q[q["book"].isin(L.BETTABLE_HIST)].copy()
    q["stat"] = q["market"].map(MARKETS)
    q = q.merge(map_games(q), on="event_id", how="left")
    print(f"bettable-book quotes {len(q):,}; events with no nflverse game: "
          f"{q.loc[q.game_id.isna(), 'event_id'].nunique()}")
    q = q.dropna(subset=["game_id"])
    q["season"] = q["season"].astype(int)
    pm = match_players(q)
    q = q.merge(pm, on=["game_id", "player_name"], how="left")
    print("player-game name match:", pm["match"].value_counts().to_dict())
    q = q[q["match"] != "unmatched"].copy()
    q["final"] = np.select([q.stat == "carries", q.stat == "receptions",
                            q.stat == "completions"],
                           [q.carries, q.receptions, q.completions], q.attempts).astype(float)
    q = q.reset_index(drop=True)

    p = load_pbp()
    print(f"pbp plays {len(p):,}; median play duration {p.attrs['median_play_s']:.2f}s; "
          f"plays with no end clock {p['end_clock_time'].isna().mean():.1%}")
    take = ["known_at", "game_seconds_remaining", "qtr", "total_home_score",
            "total_away_score", "home_team", "away_team"]
    st = p[["game_id"] + take].copy()
    j = _asof(q, "ts", st, "known_at", "game_id", take)
    for c in take:
        q[c] = j[c]
    q = q.rename(columns={"known_at": "last_play_end", "home_team": "home",
                          "away_team": "away"})
    # the next play's SNAP after ts: used only to classify stoppage vs drive
    nx = p[["game_id", "snap", "qtr"]].rename(columns={"qtr": "next_qtr"})
    jn = _asof(q, "ts", nx, "snap", "game_id", ["snap", "next_qtr"], direction="forward")
    q["next_snap"] = jn["snap"]
    q["next_qtr"] = jn["next_qtr"]
    # plays that had ENDED by ts and by the market's own last_update
    p = p.sort_values(["game_id", "known_at"])
    p["n_play"] = p.groupby("game_id").cumcount() + 1
    for col, out in (("ts", "plays_at_ts"), ("mkt_update", "plays_at_upd")):
        q[out] = _asof(q, col, p, "known_at", "game_id", ["n_play"])["n_play"].fillna(0).values

    evs = []
    for stat, (flag, pid) in STAT_SPEC.items():
        e = p.loc[(p[flag] == 1) & (p["two_point_attempt"].fillna(0) != 1) & p[pid].notna(),
                  ["game_id", "known_at", "snap", pid]].rename(columns={pid: "player_id"})
        e["stat"] = stat
        evs.append(e)
    ev = pd.concat(evs, ignore_index=True).sort_values("known_at")
    ev["k"] = ev["game_id"] + "|" + ev["stat"] + "|" + ev["player_id"]
    ev["acc"] = ev.groupby("k").cumcount() + 1
    tot = ev.groupby("k")["acc"].max()
    q["k"] = q["game_id"] + "|" + q["stat"] + "|" + q["player_id"].astype(str)
    for col, out in (("ts", "accrued"), ("mkt_update", "accrued_at_upd")):
        q[out] = _asof(q, col, ev, "known_at", "k", ["acc"])["acc"].fillna(0).values
    q["pbp_total"] = q["k"].map(tot).fillna(0)
    # SENSITIVITY ONLY: the original's timing, a play counted at its snap
    ev2 = ev.sort_values("snap").copy()
    ev2["acc_s"] = ev2.groupby("k").cumcount() + 1
    q["accrued_snap"] = _asof(q, "ts", ev2, "snap", "k", ["acc_s"])["acc_s"].fillna(0).values
    q["secs_snap"] = _asof(q, "ts", p[["game_id", "snap", "game_seconds_remaining"]],
                           "snap", "game_id",
                           ["game_seconds_remaining"])["game_seconds_remaining"].values

    team_home = (q["team"] == q["home"]).values
    own = np.where(team_home, q["total_home_score"], q["total_away_score"])
    opp = np.where(team_home, q["total_away_score"], q["total_home_score"])
    q["lead"] = own - opp
    q["secs"] = q["game_seconds_remaining"].astype(float)
    q["min_left"] = q["secs"] / 60
    q["elapsed_min"] = ((3600 - q["secs"]) / 60).clip(lower=1.0)
    q["pace_so_far"] = q["accrued"] / q["elapsed_min"]
    q["pace_needed"] = (q["line"] - q["accrued"]) / q["min_left"].clip(lower=1e-9)
    q["pace_ratio"] = q["pace_needed"] / q["pace_so_far"].replace(0, np.nan)
    q["went_over"] = (q["final"] > q["line"]).astype(int)
    q["push"] = (q["final"] == q["line"]).astype(int)
    pf = (q["match"] == "season_name_pbp_final") & (q["stat"] != "attempts")
    q.loc[pf, "final"] = q.loc[pf, "pbp_total"]
    q["final_src"] = np.where(q["match"] == "season_name_pbp_final", "pbp", "log")
    q = q[q["final"].notna()].copy()
    q["went_over"] = (q["final"] > q["line"]).astype(int)
    q["push"] = (q["final"] == q["line"]).astype(int)
    q = q.drop(columns=["carries", "receptions", "completions", "attempts"])
    q.to_parquet(STATE_CACHE, index=False)
    return q


def verify_state(q: pd.DataFrame) -> None:
    """Checks that must hold if the join is right. None reads a bet's outcome;
    each compares the reconstruction with the official final."""
    pg = q[q["final_src"] == "log"].drop_duplicates(["game_id", "stat", "player_id"])
    print("\nVERIFY 1: full-game pbp count vs official final (log-matched player-games)")
    for stat, g in pg.groupby("stat"):
        if stat == "attempts":
            continue
        print(f"   {stat:12s} player-games {len(g):5,d}  exact "
              f"{100*(g.pbp_total == g.final).mean():6.2f}%  mean err "
              f"{(g.pbp_total - g.final).mean():+.3f}")
    live = q[q["secs"].notna() & (q["stat"] != "attempts")]
    ahead = live[live["accrued"] > live["final"]]
    print(f"VERIFY 2: accrued at ts exceeds the final on {len(ahead):,} of {len(live):,} "
          f"quotes ({100*len(ahead)/max(len(live),1):.3f}%)")
    passed = live[live["accrued"] >= live["line"]]
    print(f"VERIFY 3: quotes hung on a line the player had already passed at ts: "
          f"{len(passed):,} ({100*len(passed)/max(len(live),1):.2f}%) -- a late state "
          f"join inflates this, an early one hides it")
    upd_after = (q["mkt_update"] > q["ts"]).mean()
    print(f"VERIFY 4: market last_update later than the snapshot ts on {100*upd_after:.2f}% "
          f"of quotes")




# ─── 2. the rule, graded ──────────────────────────────────────────────────

CUTS = (1.0, 1.1, 1.25, 1.4, 1.6, 2.0, 2.5)
PHASES = ("Q2 in play", "halftime", "Q3", "Q4")
MIN_PRICE = -140.0


def prep(q: pd.DataFrame) -> pd.DataFrame:
    d = q[q["secs"].notna()].copy()
    half = (d["qtr"] == 2) & (d["next_qtr"] == 3)
    d["phase"] = np.select([half, d["qtr"] <= 2, d["qtr"] == 3, d["qtr"] == 4],
                           ["halftime", "Q2 in play", "Q3", "Q4"], "OT")
    d["gate"] = (d["secs"].between(240, 3600) & (d["qtr"] <= 4) & (d["accrued"] >= 1)
                 & (d["line"] > d["accrued"]) & d["over_price"].notna()
                 & d["under_price"].notna())
    d["score_state"] = np.select([d["lead"] >= 8, d["lead"] <= -8],
                                 ["team leading 8+", "team trailing 8+"], "within 7")
    d["part"] = np.where(d["week"] <= 9, "weeks 1-9", "weeks 10+ / post")
    gap = (d["next_snap"] - d["last_play_end"]).dt.total_seconds()
    d["stop"] = np.select(
        [half, d["next_qtr"] > d["qtr"], gap >= 120, gap < 60],
        ["halftime", "quarter break", "stoppage >= 120s", "mid-drive < 60s"], "gap 60-120s")
    d["plays_since_upd"] = d["plays_at_ts"] - d["plays_at_upd"]
    d["carries_since_upd"] = d["accrued"] - d["accrued_at_upd"]
    d["fresh"] = np.where((d["plays_since_upd"] <= 0) & (d["carries_since_upd"] == 0),
                          "fresh: no play since book update", "stale: play(s) since update")
    # role, fixed from the market's own view at the game's first archived snapshot
    c = d[(d["stat"] == "carries") & (d["book"] == "draftkings")]
    first_ts = c.groupby("game_id")["ts"].transform("min")
    f = c[c["ts"] == first_ts]
    top = f.loc[f.groupby(["game_id", "team"])["line"].idxmax(), ["game_id", "player_id"]]
    lead = set(zip(top["game_id"], top["player_id"]))
    is_lead = pd.Series([(g, p) in lead for g, p in zip(d["game_id"], d["player_id"])],
                        index=d.index)
    d["role"] = np.where(d["pos"] == "QB", "QB",
                         np.where(is_lead, "lead back (top line on team)", "other"))
    # previous archived snapshot, same player, same book, same market
    d = d.sort_values("ts")
    k = ["game_id", "stat", "book", "player_id"]
    for c_ in ("line", "over_price", "under_price", "ts"):
        d["prev_" + c_ if c_ != "ts" else "prev_snap_ts"] = d.groupby(k)[c_].shift(1)
    d["unchanged"] = ((d["prev_line"] == d["line"]) & (d["prev_over_price"] == d["over_price"])
                      & (d["prev_under_price"] == d["under_price"]))
    d["prev_gap_min"] = (d["ts"] - d["prev_snap_ts"]).dt.total_seconds() / 60
    return d


def first(b: pd.DataFrame, keys=("game_id", "player_id")) -> pd.DataFrame:
    """One bet per player per game: the FIRST qualifying quote in time
    (ties on ts broken by book name, so DK before FD, then by line)."""
    return b.sort_values(["ts", "book", "line"]).drop_duplicates(list(keys), keep="first")


def grade(b: pd.DataFrame, side: str, price: str | None = None) -> pd.DataFrame:
    b = b.copy()
    px = b[price] if price else b[f"{side}_price"]
    won = (b["went_over"] == 1) if side == "over" else ((b["went_over"] == 0) & (b["push"] == 0))
    b["profit"] = L.profit_units(won.astype(int).values, px.values, b["push"].values)
    return b


def rule(d: pd.DataFrame, stat="carries", side="under", cut=1.25, book="draftkings",
         extra=None) -> pd.DataFrame:
    s = d[(d["stat"] == stat) & d["gate"]]
    if book is not None:
        s = s[s["book"] == book] if isinstance(book, str) else s[s["book"].isin(book)]
    if cut is not None:
        s = s[s["pace_ratio"] >= cut] if side == "under" else s[s["pace_ratio"] <= cut]
    s = s[s[f"{side}_price"] >= MIN_PRICE]
    if extra is not None:
        s = s[extra(s)]
    return grade(first(s), side)


def row(b: pd.DataFrame, label: str, **kw) -> dict:
    if len(b) == 0:
        return {"cell": label, **kw, "bets": 0}
    roi, (lo, hi) = L.boot_ci(b["profit"], b["game_id"])
    return {"cell": label, **kw, "bets": len(b), "games": b["game_id"].nunique(),
            "hit%": round(100 * (b["profit"] > 0).mean(), 1),
            "units": round(b["profit"].sum(), 2), "roi%": round(100 * roi, 2),
            "ci90": f"({100*lo:+.1f}, {100*hi:+.1f})"}


def boot_p(b: pd.DataFrame, n=4000, seed=11) -> float:
    """One-sided p: share of game-cluster bootstrap ROI draws <= 0."""
    if len(b) < 5:
        return np.nan
    uniq, inv = np.unique(b["game_id"].values, return_inverse=True)
    sums = np.bincount(inv, weights=b["profit"].values)
    cnt = np.bincount(inv)
    idx = np.random.default_rng(seed).integers(0, len(uniq), size=(n, len(uniq)))
    roi = sums[idx].sum(1) / cnt[idx].sum(1)
    return float((roi <= 0).mean())


def show(rows, title):
    print("\n" + title)
    print(pd.DataFrame(rows).to_string(index=False))


def per_season(b: pd.DataFrame, label: str) -> list:
    out = [row(b[b["season"] == s], label, season=s) for s in SEASONS]
    out.append(row(b, label, season="pooled"))
    return out


# ─── 3. sections ──────────────────────────────────────────────────────────

def s_repro(d, q):
    print("\n" + "=" * 100 + "\nA. REPRODUCTION OF THE PUBLISHED RULE (under, pace >= 1.25, "
          "price >= -140, first qualifying quote per player-game)\n" + "=" * 100)
    log = d[d["final_src"] == "log"]
    dk = rule(log)
    rows = per_season(dk, "DK only, log finals (staleness.py construction; doc: 874, +11.2%)")
    either = rule(log, book=["draftkings", "fanduel"])
    rows += per_season(either, "DK or FD first, log finals (rule.py construction; doc rows "
                               "294/321/278)")
    allf = rule(d)
    rows += per_season(allf, "DK only, + 2023-24 postseason from pbp finals")
    show(rows, "A1. as stated, by season")
    roi, (lo, hi) = L.boot_ci(allf["profit"], allf["season"].astype(str) + "-"
                              + allf["week"].astype(str))
    print(f"   the same {len(allf)} bets with the 90% CI clustered on season-week instead of "
          f"game: {100*roi:+.2f}% ({100*lo:+.1f}, {100*hi:+.1f})")
    # the snap-timing sensitivity
    s = d.copy()
    s["accrued"] = s["accrued_snap"]
    s["secs"] = s["secs_snap"].astype(float)
    s["gate"] = (s["secs"].between(240, 3600) & (s["qtr"] <= 4) & (s["accrued"] >= 1)
                 & (s["line"] > s["accrued"]))
    s["pace_ratio"] = (((s["line"] - s["accrued"]) / (s["secs"] / 60))
                       / (s["accrued"] / ((3600 - s["secs"]) / 60).clip(lower=1.0)))
    alt = rule(s[s["final_src"] == "log"])
    a = set(zip(dk.game_id, dk.player_id, dk.ts))
    b = set(zip(alt.game_id, alt.player_id, alt.ts))
    print(f"\nA2. matching sensitivity: snap-timed state (the original's) gives {len(alt)} bets, "
          f"{len(a ^ b)} differ from end-timed; ROI {100*alt.profit.mean():+.2f}% vs "
          f"{100*dk.profit.mean():+.2f}%")
    return dk


def s_baseline(d):
    print("\n" + "=" * 100 + "\nB. THE INCREMENT OVER THE BLIND UNDER, AND THE PLACEBO\n" + "=" * 100)
    rows = []
    blind = rule(d, cut=None)
    rows += per_season(blind, "blind under: same gates, no pace cut")
    pub = rule(d)
    rows += per_season(pub, "published rule (pace >= 1.25)")
    low = rule(d, extra=lambda s: s["pace_ratio"] < 1.25, cut=None)
    rows += per_season(low, "complement: under at pace < 1.25")
    show(rows, "B1. DK, all finals (log + pbp postseason)")
    # placebo: permute accrued within (season, phase, integer line)
    base = d[(d["stat"] == "carries") & (d["book"] == "draftkings")
             & d["secs"].between(240, 3600) & (d["qtr"] <= 4)].copy()
    base["cell"] = (base["season"].astype(str) + "|" + base["phase"] + "|"
                    + np.floor(base["line"]).astype(int).astype(str))
    rng = np.random.default_rng(3)
    base = base.sort_values("cell", kind="mergesort")
    codes = pd.factorize(base["cell"])[0]
    acc = base["accrued"].values
    rois, ns = [], []
    for _ in range(200):
        x = base.copy()
        # positions are in cell order, so a lexsort on (random, cell) is a
        # permutation inside every cell block
        x["accrued"] = acc[np.lexsort((rng.random(len(acc)), codes))]
        x["gate"] = (x["accrued"] >= 1) & (x["line"] > x["accrued"])
        x["pace_ratio"] = (((x["line"] - x["accrued"]) / (x["secs"] / 60))
                           / (x["accrued"] / x["elapsed_min"]))
        g = rule(x)
        rois.append(g["profit"].mean())
        ns.append(len(g))
    rois = np.array(rois)
    print(f"\nB2. PLACEBO (accrued permuted within season x phase x line, 200 draws): "
          f"bets {np.mean(ns):.0f} avg; ROI mean {100*rois.mean():+.2f}%, 5-95% "
          f"({100*np.quantile(rois,.05):+.2f}%, {100*np.quantile(rois,.95):+.2f}%); "
          f"draws >= the real rule's {100*pub.profit.mean():+.2f}%: "
          f"{int((rois >= pub.profit.mean()).sum())}/200")


def s_grid(d):
    print("\n" + "=" * 100 + "\nC. NEIGHBOURHOOD (DK, all finals). Each cell = the rule "
          "restricted to that cell, first qualifying quote per player-game\n" + "=" * 100)
    rows = []
    for cut in CUTS:
        rows.append(row(rule(d, cut=cut), "all phases", cut=cut))
        for ph in PHASES:
            rows.append(row(rule(d, cut=cut, extra=lambda s, ph=ph: s["phase"] == ph), ph, cut=cut))
    show(rows, "C1. pace cut x game phase")
    rows = []
    for cut in CUTS:
        b = rule(d, cut=cut)
        for s in SEASONS:
            rows.append(row(b[b["season"] == s], f"season {s}", cut=cut))
    show(rows, "C2. pace cut x season")
    pub = rule(d)
    rows = []
    for col in ("role", "score_state", "part", "phase"):
        for v, g in pub.groupby(col):
            rows.append(row(g, f"{col} = {v}"))
    show(rows, "C3. the published rule split by role, score state, early/late, phase")
    # books
    rows = [row(pub, "DraftKings quotes, DK price")]
    rows.append(row(rule(d, book="fanduel"), "FanDuel quotes, FD price"))
    rows.append(row(rule(d, book=list(L.BETTABLE_HIST)), "any bettable book, first quote"))
    allq = d[(d["stat"] == "carries")]
    best = allq.groupby(["game_id", "player_id", "ts", "line"])["under_price"].max()
    nb = allq.groupby(["game_id", "player_id", "ts", "line"])["book"].nunique()
    b2 = pub.copy()
    key = list(zip(b2.game_id, b2.player_id, b2.ts, b2.line))
    b2["best_under"] = best.reindex(key).values
    b2["n_books"] = nb.reindex(key).values
    b2 = grade(b2, "under", price="best_under")
    rows.append(row(b2, "DK-qualifying bets at best bettable price, same line + ts"))
    print(f"\n   (best-price column: {int((b2.n_books > 1).sum())} of {len(b2)} DK bets had a "
          f"second bettable book at the same line and ts; "
          f"{int((b2.best_under > pub.under_price.values).sum())} got a better price)")
    show(rows, "C4. by book")


def s_strict(d):
    print("\n" + "=" * 100 + "\nD. STRICT LOW-VOLUME CELLS (DK, all finals), every season\n"
          + "=" * 100)
    cells = {
        "pace >= 1.5 & >= 20 min left": (1.5, lambda s: s["min_left"] >= 20),
        "pace >= 2.0 & >= 20 min left": (2.0, lambda s: s["min_left"] >= 20),
        "pace >= 1.5 & team leading 8+": (1.5, lambda s: s["lead"] >= 8),
        "pace >= 2.0 & lead back": (2.0, lambda s: s["role"].str.startswith("lead")),
        "pace >= 1.5 & halftime": (1.5, lambda s: s["phase"] == "halftime"),
        "pace >= 1.25 & team leading 8+ (the doc's split, already seen)":
            (1.25, lambda s: s["lead"] >= 8),
    }
    rows = []
    for lab, (cut, f) in cells.items():
        rows += per_season(rule(d, cut=cut, extra=f), lab)
    show(rows, "D1.")


def s_place(d):
    print("\n" + "=" * 100 + "\nE. PLACEABILITY (DK, all finals, published rule unless "
          "stated)\n" + "=" * 100)
    pub = rule(d)
    rows = []
    for col in ("stop", "fresh"):
        for v, g in pub.groupby(col):
            rows.append(row(g, f"{col}: {v}"))
    rows.append(row(pub[pub["unchanged"]], "price unchanged vs previous archived snapshot"))
    rows.append(row(pub[~pub["unchanged"] & pub["prev_line"].notna()],
                    "price changed vs previous archived snapshot"))
    rows.append(row(pub[pub["prev_line"].isna()], "no previous archived snapshot"))
    show(rows, "E1. the published rule's bets split by placeability proxy")
    u = pub[pub["unchanged"]]
    print(f"   gap to the previous snapshot on the 'unchanged' bets: median "
          f"{u.prev_gap_min.median():.1f} min, range {u.prev_gap_min.min():.1f}-"
          f"{u.prev_gap_min.max():.1f}")
    rows = []
    rows += per_season(rule(d, extra=lambda s: s["fresh"].str.startswith("fresh")),
                       "rule applied to FRESH quotes only")
    rows += per_season(rule(d, extra=lambda s: s["unchanged"]),
                       "rule applied to quotes unchanged across 2 snapshots only")
    rows += per_season(rule(d, extra=lambda s: s["phase"] == "halftime"),
                       "rule applied at HALFTIME only")
    rows += per_season(rule(d, extra=lambda s: s["stop"] != "mid-drive < 60s"),
                       "rule excluding mid-drive quotes")
    show(rows, "E2. the rule re-run on each placeable subset (first qualifying within it)")
    # the n-th qualifying quote, with its real gap
    s = d[(d["stat"] == "carries") & d["gate"] & (d["book"] == "draftkings")
          & (d["pace_ratio"] >= 1.25) & (d["under_price"] >= MIN_PRICE)].sort_values("ts")
    s = s.copy()
    s["n"] = s.groupby(["game_id", "player_id"]).cumcount()
    t0 = s[s["n"] == 0].set_index(["game_id", "player_id"])["ts"]
    rows = []
    for n in range(4):
        g = grade(s[s["n"] == n], "under")
        wait = (g["ts"].values - t0.reindex(list(zip(g.game_id, g.player_id))).values)
        wait = pd.to_timedelta(wait).total_seconds() / 60
        rows.append(row(g, f"qualifying quote #{n+1}",
                        wait_min_median=round(float(np.median(wait)), 1) if len(g) else None))
    show(rows, "E3. the n-th qualifying quote (the doc called #2 '~5 min later')")
    c = d[(d["stat"] == "carries") & (d["book"] == "draftkings") & d["secs"].between(240, 3600)]
    passed = c[c["accrued"] >= c["line"]]
    print(f"\nE4. DK carries quotes hung on a line already passed at ts: {len(passed)}; "
          f"already passed at the book's own last_update: "
          f"{int((passed.accrued_at_upd >= passed.line).sum())} (a frozen board); "
          f"DK carries quotes with >= 1 play since the book's update: "
          f"{100*(c.plays_since_upd > 0).mean():.1f}%, >= 1 carry by the player: "
          f"{100*(c.carries_since_upd > 0).mean():.1f}%")


def s_mirror(d):
    print("\n" + "=" * 100 + "\nF. THE MIRROR - pre-registered on 2023-24, 2025 read once "
          "(DK, all finals)\n" + "=" * 100)
    fit = d[d["season"].isin([2023, 2024])]
    hold = d[d["season"] == 2025]
    rows, chosen = [], {}
    for stat in ("carries", "receptions", "completions"):
        best = None
        for cut in (0.4, 0.5, 0.6, 0.7, 0.8):
            b = rule(fit, stat=stat, side="over", cut=cut)
            r = row(b, f"{stat} OVER pace <= {cut}", fit="2023-24")
            rows.append(r)
            if r["bets"] >= 60:
                lo = float(r["ci90"].strip("()").split(",")[0])
                if best is None or lo > best[1]:
                    best = (cut, lo)
        chosen[stat] = best[0] if best else 0.6
        rows.append(row(rule(fit, stat=stat, side="over", cut=None),
                        f"{stat} blind OVER", fit="2023-24"))
        if stat != "carries":
            rows.append(row(rule(fit, stat=stat, side="under", cut=1.25),
                            f"{stat} UNDER pace >= 1.25", fit="2023-24"))
            rows.append(row(rule(fit, stat=stat, side="under", cut=None),
                            f"{stat} blind UNDER", fit="2023-24"))
    show(rows, "F1. fit seasons 2023-24, every cell")
    print(f"   chosen over cuts (highest 90% CI lower bound, >= 60 bets): {chosen}")
    reads = [("carries UNDER pace >= 1.25 (published; 2025 NOT unseen)", "carries", "under", 1.25)]
    for stat in ("carries", "receptions", "completions"):
        reads.append((f"{stat} OVER pace <= {chosen[stat]}", stat, "over", chosen[stat]))
        if stat != "carries":
            reads.append((f"{stat} UNDER pace >= 1.25", stat, "under", 1.25))
    rows, ps = [], []
    for lab, stat, side, cut in reads:
        b = rule(hold, stat=stat, side=side, cut=cut)
        r = row(b, lab, fit="2025 read")
        r["p_one_sided"] = round(boot_p(b), 4)
        ps.append(r["p_one_sided"])
        rows.append(r)
        bl = rule(hold, stat=stat, side=side, cut=None)
        rows.append(row(bl, f"   its blind {side} baseline", fit="2025 read"))
    m = len(ps)
    order = np.argsort(ps)
    adj = np.empty(m)
    run = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        run = min(run, ps[i] * m / (rank + 1))
        adj[i] = run
    k = 0
    for r in rows:
        if "p_one_sided" in r:
            r["p_BH"] = round(float(adj[k]), 4)
            k += 1
    show(rows, f"F2. 2025, read once ({m} tests, Benjamini-Hochberg across them)")


def s_diagnostics(d):
    print("\n" + "=" * 100 + "\nH. DIAGNOSTICS (no new rule is chosen here)\n" + "=" * 100)
    c = d[(d["stat"] == "carries") & (d["book"] == "draftkings")]
    snaps = c.groupby(["season", "game_id"])["ts"].nunique().reset_index()
    print("H1. archive composition, DK carries: snapshots per game, and quotes by phase")
    print(pd.crosstab(snaps["season"], snaps["ts"]).to_string())
    print(pd.crosstab(c["season"], c["phase"]).to_string())
    pub = rule(d)
    p_u, _ = L.devig2(pub["under_price"].values, pub["over_price"].values)
    print(f"\nH2. the published rule's bets: median DK under price {pub.under_price.median():+.0f}, "
          f"share plus-money {100*(pub.under_price > 0).mean():.1f}%, mean de-vigged under prob "
          f"{p_u.mean():.3f}, actual under hit {(pub.profit > 0).mean():.3f}, mean hold "
          f"{100*(L.am_to_prob(pub.under_price) + L.am_to_prob(pub.over_price) - 1).mean():.1f}%")
    # pre-bet idleness: game minutes since the player's last carry or target, at ts
    p = pd.concat([pd.read_parquet(L.CACHE / f"pbp_{s}.parquet",
                                   columns=["game_id", "play_id", "time_of_day", "end_clock_time",
                                            "game_seconds_remaining", "rusher_player_id",
                                            "receiver_player_id", "rush_attempt", "pass_attempt",
                                            "posteam"])
                   for s in SEASONS], ignore_index=True)
    t = pd.to_datetime(p["end_clock_time"], utc=True, errors="coerce", format="mixed")
    t = t.fillna(pd.to_datetime(p["time_of_day"], utc=True, errors="coerce", format="mixed")
                 + pd.Timedelta(seconds=5))
    p["t"] = t.astype("datetime64[us, UTC]")
    inv = pd.concat([
        p.loc[p["rush_attempt"] == 1, ["game_id", "t", "game_seconds_remaining",
                                       "rusher_player_id"]].rename(columns={"rusher_player_id": "pid"}),
        p.loc[p["pass_attempt"] == 1, ["game_id", "t", "game_seconds_remaining",
                                       "receiver_player_id"]].rename(columns={"receiver_player_id": "pid"}),
    ]).dropna(subset=["pid", "t"])
    inv["k"] = inv["game_id"] + "|" + inv["pid"]
    b = pub.copy()
    b["k2"] = b["game_id"] + "|" + b["player_id"].astype(str)
    last = _asof(b.rename(columns={"k2": "kk"}), "ts", inv.rename(columns={"k": "kk"}),
                 "t", "kk", ["game_seconds_remaining"])
    b["idle_min"] = (last["game_seconds_remaining"].values - b["secs"].values) / 60
    b["after"] = b["final"] - b["accrued"]
    rows = []
    for lab, m in (("last carry/target < 5 game-min before ts", b["idle_min"] < 5),
                   ("5-10 game-min", b["idle_min"].between(5, 10)),
                   ("> 10 game-min idle before ts (possible exit)", b["idle_min"] > 10)):
        rows.append(row(b[m], lab, zero_carries_after=f"{100*(b[m]['after'] == 0).mean():.0f}%"))
    show(rows, "H3. the published rule's bets by pre-bet idleness (known at ts); the share "
               "with ZERO carries after ts is an outcome, shown only to size exits")
    print(f"   all rule bets: {100*(b['after'] == 0).mean():.1f}% had zero carries after ts")
    rows = per_season(rule(d, extra=lambda s: s["phase"] == "halftime"), "halftime rule, all")
    hb = grade(first(d[(d.stat == "carries") & d.gate & (d.book == "draftkings")
                       & (d.pace_ratio >= 1.25) & (d.under_price >= MIN_PRICE)
                       & (d.phase == "halftime")]), "under")
    hb["k2"] = hb["game_id"] + "|" + hb["player_id"].astype(str)
    lh = _asof(hb.rename(columns={"k2": "kk"}), "ts", inv.rename(columns={"k": "kk"}), "t", "kk",
               ["game_seconds_remaining"])
    hb["idle_min"] = (lh["game_seconds_remaining"].values - hb["secs"].values) / 60
    rows += per_season(hb[hb["idle_min"] <= 10], "halftime rule, player used <= 10 min before")
    show(rows, "H4. the halftime rule with possible exits removed (a pre-bet filter)")
    x = pub.copy()
    rows = [row(g, f"phase {ph} / {st}") for (ph, st), g in x.groupby(["phase", "stop"])
            if len(g) >= 20]
    show(rows, "H5. the published rule's bets, phase x stoppage (cells >= 20 bets)")


def s_production():
    p = pd.read_parquet(L.CACHE / "picks_nfl.parquet",
                        columns=["model_id", "prop_market", "signal_type", "result",
                                 "pick_label", "created_at", "profit_flat", "dk_odds"])
    x = p[(p["model_id"] == "nfl_live_prop") & (p["prop_market"] == "player_rush_attempts")
          & (p["signal_type"] == "BET")]
    print("\nG. PRODUCTION: every nfl_live_prop rushing-attempts BET in picks_nfl.parquet")
    print(x[["created_at", "pick_label", "dk_odds", "result"]].to_string(index=False))
    u = pd.to_numeric(x["profit_flat"], errors="coerce") / 100.0    # stored per $100 stake
    print(f"   {len(x)} bets, {int((x.result == 'WIN').sum())}-{int((x.result == 'LOSS').sum())}, "
          f"{u.sum():+.2f} units")


def main() -> None:
    q = build_state()
    verify_state(q)
    d = prep(q)
    c = d[(d.stat == "carries") & (d.book == "draftkings")]
    print(f"\nDK carries quotes with a live state: {len(c):,} in {c.game_id.nunique()} games; "
          f"by season {c.season.value_counts().sort_index().to_dict()}; by phase "
          f"{c.phase.value_counts().to_dict()}")
    s_repro(d, q)
    s_baseline(d)
    s_grid(d)
    s_strict(d)
    s_place(d)
    s_mirror(d)
    if "--skip-diag" not in sys.argv:
        s_diagnostics(d)
    s_production()


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    main()
