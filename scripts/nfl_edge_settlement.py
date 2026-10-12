"""Settlement-definition mismatches in NFL player props: four tests.

    python -m scripts.nfl_edge_settlement

HYPOTHESIS. Where a book settles a prop on a different definition from the
obvious stat (or from other books), a line set from the obvious stat is wrong
by a predictable amount, and that creates low-volume +EV bets.

Everything reads the local cache through scripts/nfl_edge_lib.py. No database,
no Odds API, no paid endpoint. The only network use was downloading six house
rule PDFs (public, Massachusetts Gaming Commission filings) into
<cache>/house_rules/; this script re-reads them and prints the clauses.

=============================================================================
SETTLEMENT RULES AS FILED (checked 2026-10-11, quoted verbatim by Part 0)
=============================================================================
  tackles + assists
    FanDuel 8.29.24      "Includes those recorded on both Defense and Special Teams."
    DraftKings 8.1.24    "Only defensive plays count. Any plays on special teams do not count."
    Caesars 3.6.24       "Special teams tackles do not count."           (williamhill_us)
    ESPN BET 5.23.25     "will only consider tackles made on defensive plays."
    Fanatics 3.27.25     "Special teams tackles will not be counted."     (no tackles rows)
    BetMGM 8.29.24       silent.  betrivers, fliff, hardrockbet, ballybet, betparx,
                         bovada, betonlineag: not checked -> UNKNOWN rule.
  sacks
    FanDuel              "Player to Record a Sack ... Half sacks count as 'Yes'."
    BetMGM               yes needs at least one total sack (1.0)            (no sack rows)
    Fanatics             'which player will make a sack' needs 1+; over/under pushes on
                         an exact half                                      (no sack rows)
    DraftKings           quotes 0.25 / 0.75 / 1.25 two-way lines in this archive, so a
                         half sack settles OVER 0.25 -- the same event as FanDuel's yes.
    0.5-line two-way books (hardrockbet, fliff, espnbet, betonlineag, ballybet,
                         betrivers): an exact 0.5 equals the line -> push (Fanatics'
                         stated convention; the others are assumed to follow it).
  anytime TD             DK / FD / ESPN BET: scorer = player in possession in the end
                         zone, so kick and punt RETURN touchdowns count everywhere.

=============================================================================
THE CONSTRUCTION -- written before any bet outcome was looked at
=============================================================================
Common to all parts
  * Seasons 2023-2025 (sacks: 2024-2025, the only seasons with sack quotes).
  * Decision time: per (game, market) the LATEST board read stamped strictly
    before kickoff at which the part's anchor book quotes the market. Only
    quotes stamped AT that read are used (every book on one read shares one
    timestamp in this archive), so no quote is compared with a later one.
  * Pre-game information only: as-of player rates use games strictly before
    this one; the spread is the consensus of quotes at or before the decision
    read (odds_hist), never the close.
  * One bet per proposition (game, player, market, side). A player who did not
    play (no snap row / no log row) is void and dropped, as at every book.
  * Price: the best price on that side, at the SAME line, on the SAME read,
    among the bettable books that settle on the SAME rule as the book the rule
    names. Pushes are bets returning 0.
  * Intervals: 90% cluster bootstrap on game_id (several players per game);
    one-sided p = share of bootstrap draws with ROI <= 0. "Strict" (marked *)
    = 30 or fewer bets per season on average.
  * Every grid is printed whole (every cell: bets, bets per season, units,
    ROI, 90% CI). Early = weeks 1-9, late = weeks 10+ (playoffs are late).
  * Benjamini-Hochberg (q = 0.10) over every test listed in the final table.

As-of player history (Parts 1, 2, 4): the snap-count universe (every game a
player took a snap), keyed on (normalised name, team), last 17 games, from 2022
on. Play-by-play stats are mapped to that universe through the player log's
gsis id -> name map. Special-teams plays = special_teams_play flag, or
play_type kickoff / punt / field_goal / extra_point, or a no_play whose text is
a kick or a punt.

PART 1. SPECIAL-TEAMS TACKLES (tackles + assists)
  Stat: total = solo + with-assist + assists on all plays (the repo's corrected
  stat, docs/nfl_prop_profitability_search.md section 4); defense-only = total
  minus the same three on special-teams plays. FanDuel settles on total;
  DraftKings / Caesars / ESPN BET settle on defense-only.
  E[ST] = player's special-teams tackles per game over his prior <= 17 games,
  at least 4 prior games.
  1a (as briefed). FanDuel OVER when E[ST] >= x and FanDuel's line equals
     DraftKings' line on the same read, graded on total. FanDuel has 16
     tackles rows in the whole archive (all 2024), so this is printed as a
     count and a row list, not graded for inference.
  1b (the mirror, the testable rule). DraftKings UNDER at DraftKings' line when
     E[ST] >= x, graded on defense-only, at the best under among the
     defense-only books (draftkings, williamhill_us, espnbet) at that line.
     Grid x in {0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00}.
     Fit 2023-2024: among cells with >= 15 fit bets, the highest fit 90% CI
     lower bound (ties -> more bets). Hold-out 2025 read once for that cell.
  Placebo 1b: the same DraftKings under on players with ZERO special-teams
     involvement (no ST tackles and zero ST snap share in every prior game,
     >= 4 prior games).
  Pricing diagnostics (no outcomes): OLS of DraftKings' line on as-of
     defense-only and as-of ST tackles per game (if DK priced ST tackles into a
     line that excludes them, the ST coefficient would be near the defensive
     one); mean line difference of every other book vs DraftKings by E[ST]
     bucket (a book that counts ST tackles should sit higher for high-E[ST]
     players); realised ST tackles by E[ST] bucket (does the as-of rate predict).

PART 2. HALF SACKS
  Anchor FanDuel (yes-only 'to record a sack', line 0.5, half counts).
  Stat: sacks from the play-by-play (1 per sack_player_id, 0.5 per half-sack id),
  checked against the game log's def_sacks.
  2a (same definition). EV_dk = DK fair P(over 0.25) (proportional de-vig) x
     decimal(FD yes) - 1. Bet FD yes when EV_dk >= c, c in {-0.05, 0, 0.02,
     0.05, 0.08, 0.10, 0.15, 0.20, 0.30}. Fit 2024 (same selection rule), hold-out 2025.
  2b (the mismatch as briefed, no parameter). Bet FD yes when FD's yes price is
     at least the best OVER 0.5 price among the 0.5-line two-way books on the
     same read: FD then pays at least as much for a strictly larger event
     (a half sack wins at FD, pushes there). All seasons and hold-out shown.
  2c (as-of rates). p = shrunk as-of share of games with >= 0.5 sacks (prior
     <= 17 games, >= 4, shrunk with weight 8 toward the fit-season mean of
     FD-listed players); bet FD yes when p x decimal(FD) - 1 >= c, same grid,
     fit 2024, hold 2025.
  Placebo 2: rules 2a/2b on players with ZERO half sacks in every prior game
     (>= 8 prior games): the half-sack component of their price is ~0.
  Also: how often a FD-listed player ends on exactly 0.5 sacks, and FD yes
     graded as if half sacks did NOT count (the mechanism's size).

PART 3. QB RUSHING-YARDS UNDERS FOR BIG FAVOURITES (kneel-downs)
  Universe: player_rush_yds main lines, QBs (game-log position QB, that game).
  Line: DraftKings' line if DK quotes the QB on the read, else the modal
  bettable line. Price: best bettable under at that line. Team spread: median
  home point across books' latest spread quote at or before the read
  (odds_hist), turned into the QB's team number.
  3a/3b AS STATED (graded on all seasons first): under on every QB whose team
     is favoured by >= 7 / >= 10.
  Placebo 3: underdog QBs (team point > 0), same construction.
  3c refinement: grid favourite margin {0, 3, 5, 7, 10, 14} x {all, line >=
     as-of baseline} (baseline = QB's mean rushing yards, prior <= 17 games,
     >= 3). Fit 2023-2024 (same selection rule), hold-out 2025.
  Mechanism / pricing (descriptive): kneel yards per QB-game by closing spread
  bucket (pbp, closing spread is fine for a description); line minus as-of
  baseline and actual minus line by bucket; Pinnacle's fair under vs realised.

PART 4. ANYTIME TD FOR PRIMARY KICK / PUNT RETURNERS
  Returns per game = kickoff + punt return plays with the player as returner,
  prior <= 8 games (>= 3). Primary returner: >= 2 returns per game.
  As-of return-TD probability per game = 1 - (1 - r)^(returns/game), r = the
  player's return TDs per return shrunk (weight 200 returns) to the 2016-2022
  league rate.
  Price: best bettable yes; fair yes = Pinnacle's two-way de-vig when quoted.
  Grade: yes wins on ANY touchdown the player scores (pbp td_player_id).
  4a AS STATED: yes on every primary returner, all seasons.
  Placebo 4: players with zero returns in every prior game (>= 3), same price
     bands.
  4b refinement: grid returns/game {1, 2, 3, 4} x best-price band
     {<= +250, +251..+600, > +600}. Fit 2023-2024, hold-out 2025.
  Descriptive: realised TD rate minus Pinnacle fair, returners vs non-returners,
  against the as-of return-TD probability; share of returners' TDs that were
  return TDs.

GRADING FIX AFTER THE FIRST RUN (not a selection change). The first run
mapped play-by-play stats to players through the game log's names, which
differ from the snap-count / prop names for some players ("Kam Curl" vs
"Kamren Curl"). 3.05% of DraftKings-listed tackles player-games had no stat
and were graded on zero tackles (a free under). id_map() now aliases those
names within a team-season; the residual 1.97% were checked by hand on four
starters and carry no tackle credit in the play-by-play at all (genuine
zeros). Every number printed is from the corrected grading; the construction
above is unchanged.

Results in UNITS: 1 unit = one flat bet.
"""
from __future__ import annotations

import glob
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from scripts import nfl_edge_lib as L

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

SEASONS = (2023, 2024, 2025)
FIT, HOLD = (2023, 2024), (2025,)
SACK_SEASONS, SACK_FIT, SACK_HOLD = (2024, 2025), (2024,), (2025,)
HIST_FROM = 2022
STRICT = 30
FIT_MIN = 15

TK_INCL_ST = {"fanduel"}
TK_EXCL_ST = ("draftkings", "williamhill_us", "espnbet")       # filed rules
TK_UNKNOWN = ("betmgm", "betrivers", "fliff", "hardrockbet", "ballybet",
              "betparx", "bovada", "betonlineag")
HALF_LINE_BOOKS = ("hardrockbet", "fliff", "espnbet", "betonlineag", "ballybet", "betrivers")

TK_X = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00]
SACK_C = [-0.05, 0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]
QB_FAV = [0, 3, 5, 7, 10, 14]
RET_RPG = [1, 2, 3, 4]
PRICE_BANDS = (("<=+250", -1e9, 250), ("+251..+600", 250, 600), (">+600", 600, 1e9))

TESTS: list[dict] = []          # for Benjamini-Hochberg

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def norm(name) -> str:
    """data.ingestors.nfl_props_data_ingestor.norm_player_name, copied."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = _SUFFIX_RE.sub("", s.lower().strip())
    return re.sub(r"[^a-z]", "", s)


def norm_series(s: pd.Series) -> pd.Series:
    u = pd.Series(s.astype(str).unique())
    m = dict(zip(u, u.map(norm)))
    return s.astype(str).map(m)


def dec(a):
    return L.am_to_dec(a)


# ─── inference / printing ──────────────────────────────────────────────────

def boot_draws(profit, cluster, n=4000, seed=7):
    profit = np.asarray(profit, float)
    uniq, inv = np.unique(np.asarray(cluster), return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n, len(uniq)))
    return sums[idx].sum(1) / cnts[idx].sum(1)


def cell(df: pd.DataFrame, seasons=SEASONS) -> dict:
    if len(df) == 0:
        return {"n": 0, "per": pd.Series(0, index=list(seasons))}
    dr = boot_draws(df["profit"].values, df["game_id"].values)
    per = df.groupby("season").size().reindex(list(seasons), fill_value=0)
    return {"n": len(df), "units": df["profit"].sum(), "roi": 100 * df["profit"].mean(),
            "lo": 100 * np.quantile(dr, 0.05), "hi": 100 * np.quantile(dr, 0.95),
            "p": float((dr <= 0).mean()), "per": per,
            "win": 100 * (df["profit"] > 0).mean(), "strict": per.mean() <= STRICT}


def fmt(c: dict) -> str:
    ps = "/".join(str(int(v)) for v in c["per"].values)
    if c["n"] == 0:
        return f"{0:>5} {ps:>12} {'':>8} {'':>7} {'':>15} {'':>5}"
    star = "*" if c["strict"] else " "
    return (f"{c['n']:>5}{star}{ps:>12} {c['units']:>+8.2f} {c['roi']:>+6.1f}% "
            f"({c['lo']:>+6.1f},{c['hi']:>+6.1f}) {c['win']:>5.1f}")


def hdr(seasons=SEASONS) -> str:
    lab = "/".join(str(s)[2:] for s in seasons)
    return f"{'bets':>5} {lab:>12} {'units':>8} {'ROI':>7} {'90% CI':>15} {'win%':>5}"


def banner(t: str):
    print("\n" + "=" * 110)
    print(t)
    print("=" * 110)


def splits(df: pd.DataFrame, label: str, seasons=SEASONS):
    print(f"  {label}")
    print(f"    {'split':16s} {hdr(seasons)}")
    for s in seasons:
        print(f"    {str(s):16s} {fmt(cell(df[df.season == s], seasons))}")
    print(f"    {'early wk 1-9':16s} {fmt(cell(df[df.week <= 9], seasons))}")
    print(f"    {'late wk 10+':16s} {fmt(cell(df[df.week >= 10], seasons))}")
    print(f"    {'ALL':16s} {fmt(cell(df, seasons))}")


def choose(cells: dict, fit_seasons) -> object:
    """cells: key -> fit-season dataframe. Highest fit CI lower bound among
    cells with >= FIT_MIN bets; ties -> more bets."""
    best, bkey = None, None
    for k, df in cells.items():
        if len(df) < FIT_MIN:
            continue
        c = cell(df, fit_seasons)
        score = (round(c["lo"], 6), c["n"])
        if best is None or score > best:
            best, bkey = score, k
    return bkey


GRID: list[dict] = []      # every grid cell, for the grid-wide BH and the post-hoc look


def gcell(name, df, seasons=SEASONS) -> dict:
    c = cell(df, seasons)
    if c["n"]:
        GRID.append({"cell": name, "bets": c["n"], "per_season": c["per"].mean(), "units": c["units"],
                     "roi": c["roi"], "lo": c["lo"], "hi": c["hi"], "p": c["p"], "df": df, "seasons": seasons})
    return c


def bh(df: pd.DataFrame, q=0.10) -> pd.DataFrame:
    t = df.sort_values("p").reset_index(drop=True)
    m = len(t)
    t["rank"] = np.arange(1, m + 1)
    passed = t["p"] <= q * t["rank"] / m
    kmax = t.loc[passed, "rank"].max() if passed.any() else 0
    t["BH_reject"] = t["rank"] <= kmax
    t["p_adj"] = np.minimum.accumulate((t["p"] * m / t["rank"])[::-1])[::-1].clip(upper=1)
    return t


def add_test(name, df, seasons, kind):
    c = cell(df, seasons)
    TESTS.append({"test": name, "kind": kind, "bets": c["n"],
                  "units": c.get("units", np.nan), "roi": c.get("roi", np.nan),
                  "lo": c.get("lo", np.nan), "hi": c.get("hi", np.nan),
                  "p": c.get("p", np.nan)})


# ─── data ──────────────────────────────────────────────────────────────────

def kicks() -> pd.DataFrame:
    g = L.games()
    g = g[g["season"].between(HIST_FROM - 1, 2025)]
    return g[["game_id", "kick", "season", "week", "game_type", "home_team",
              "away_team", "spread_line"]].rename(columns={"game_id": "gid"})


K = None


def load_props(market: str, books, seasons=SEASONS) -> pd.DataFrame:
    d = L.props_market(market)[["game_id", "player_name", "line", "over_price",
                                "under_price", "bookmaker", "snapshot_at"]]
    d = d.rename(columns={"game_id": "pgid"})
    d["gid"] = d["pgid"].astype(str).str.replace("^NFL_", "", regex=True)
    d["season"] = d["gid"].str[:4].astype(int)
    d = d[d["season"].isin(seasons)]
    d["bookmaker"] = d["bookmaker"].astype(str)
    d = d[d["bookmaker"].isin(set(books)) & ~d["bookmaker"].isin(L.EXCLUDED)]
    d = d[d["line"].notna()]
    d = d.merge(K[["gid", "kick", "week"]], on="gid", how="inner")
    d = d[d["snapshot_at"] < d["kick"]].copy()
    d["lead_h"] = (d["kick"] - d["snapshot_at"]).dt.total_seconds() / 3600
    d["norm"] = norm_series(d["player_name"])
    d = d.drop(columns=["pgid"])
    return d


def board(d: pd.DataFrame, anchor) -> pd.DataFrame:
    a = d[d["bookmaker"].isin(set(anchor))]
    t = a.groupby("gid")["snapshot_at"].max().rename("T").reset_index()
    b = d.merge(t, on="gid")
    b = b[b["snapshot_at"] == b["T"]]
    return b.drop_duplicates(["gid", "norm", "line", "bookmaker"], keep="last")


LOG_NUM = ["rushing_yards", "def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists",
           "def_sacks", "rushing_tds", "receiving_tds"]


def player_log() -> pd.DataFrame:
    """lib.player_log() with numeric columns as float (the 2025-26 file holds
    Decimal objects from a NUMERIC column)."""
    lg = L.player_log()
    for c in LOG_NUM:
        if c in lg.columns:
            lg[c] = pd.to_numeric(lg[c].astype(object).map(lambda v: None if v is None else float(v)),
                                  errors="coerce")
    return lg


_SUFFIX_TOK = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}


def _last(name: str) -> str:
    toks = [t for t in str(name).replace(".", ". ").split() if t.lower() not in _SUFFIX_TOK]
    if not toks:
        return ""
    t = unicodedata.normalize("NFKD", toks[-1]).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", t)


ALIAS_STATS: dict = {}


def id_map() -> pd.DataFrame:
    """gsis id -> the name the snap counts and the prop feeds use.

    The game log (nflverse) and the snap counts / Odds API disagree on some
    first names ("Kam Curl" / "Kamren Curl", "Pat Surtain" / "Patrick
    Surtain"). Found after the first run: such a player kept his snap row but
    lost every play-by-play stat, so he was graded on ZERO tackles / sacks /
    touchdowns -- a free under. Fix: within a team-season, a snap name with no
    log match takes the log player whose surname ends it and whose first
    letter starts it, when exactly one does."""
    lg = player_log()[["player_id", "player_name", "norm_name", "game_date", "team", "season"]]
    lg["n"] = lg["norm_name"].where(lg["norm_name"].notna(), norm_series(lg["player_name"]))
    base = lg.sort_values("game_date").drop_duplicates("player_id", keep="last")[["player_id", "n"]]
    sc = pd.read_parquet(L.CACHE / "local_nfl_snap_counts.parquet", columns=["game_id", "team", "norm_name"])
    sc["season"] = sc["game_id"].str.extract(r"(\d{4})")[0].astype(int)
    sc = sc[sc["season"] >= HIST_FROM - 1].drop_duplicates(["team", "season", "norm_name"])
    lgts = lg[lg["season"] >= HIST_FROM - 1].drop_duplicates(["player_id", "team", "season"]).copy()
    lgts["last"] = lgts["player_name"].map(_last)
    lgts["fi"] = lgts["n"].str[:1]
    snap_by = sc.groupby(["team", "season"])["norm_name"].apply(set).to_dict()
    rows = []
    n_ts = 0
    for (team, season), grp in lgts.groupby(["team", "season"]):
        S = snap_by.get((team, season), set())
        if not S:
            continue
        n_ts += 1
        logn = set(grp["n"])
        cand = grp[~grp["n"].isin(S) & (grp["last"].str.len() >= 3)]
        lasts = cand["last"].astype(object).tolist()
        fis = cand["fi"].astype(object).tolist()
        for sn in S - logn:
            ok = np.array([sn.endswith(l) and f == sn[:1] for l, f in zip(lasts, fis)], dtype=bool)
            m = cand[ok]
            if len(m) == 1:
                rows.append((m["player_id"].iloc[0], sn))
    al = pd.DataFrame(rows, columns=["player_id", "alias"]).drop_duplicates("player_id")
    base = base.merge(al, on="player_id", how="left")
    ALIAS_STATS["aliased ids"] = int(base["alias"].notna().sum())
    ALIAS_STATS["team-seasons matched to snaps"] = n_ts
    base["norm"] = base["alias"].fillna(base["n"])
    return base[["player_id", "norm"]].rename(columns={"player_id": "pid"})


def pbp_stats(seasons) -> pd.DataFrame:
    tk_cols = (["solo_tackle_1_player_id", "solo_tackle_2_player_id",
                "tackle_with_assist_1_player_id", "tackle_with_assist_2_player_id"]
               + [f"assist_tackle_{i}_player_id" for i in range(1, 5)])
    cols = (["game_id", "play_type", "special_teams_play", "desc", "sack_player_id",
             "half_sack_1_player_id", "half_sack_2_player_id",
             "kickoff_returner_player_id", "punt_returner_player_id", "td_player_id",
             "return_touchdown"] + tk_cols)
    p = pd.concat([pd.read_parquet(L.CACHE / f"pbp_{s}.parquet", columns=cols)
                   for s in seasons], ignore_index=True)
    kickpunt = p["desc"].fillna("").str.contains(r"\bpunts\b|\bkicks\b", regex=True)
    p["st"] = ((p["special_teams_play"] == 1)
               | p["play_type"].isin(["kickoff", "punt", "field_goal", "extra_point"])
               | ((p["play_type"] == "no_play") & kickpunt))
    p = p.drop(columns=["desc"])
    parts = []
    for c in tk_cols:
        x = p.loc[p[c].notna(), ["game_id", "st", c]].rename(columns={c: "pid"})
        parts.append(x)
    t = pd.concat(parts)
    tk = t.groupby(["game_id", "pid"]).agg(tot_tk=("st", "size"), st_tk=("st", "sum")).reset_index()
    sk_parts = [p.loc[p["sack_player_id"].notna(), ["game_id", "sack_player_id"]]
                .rename(columns={"sack_player_id": "pid"}).assign(sk=1.0, half=0)]
    for c in ("half_sack_1_player_id", "half_sack_2_player_id"):
        sk_parts.append(p.loc[p[c].notna(), ["game_id", c]].rename(columns={c: "pid"})
                        .assign(sk=0.5, half=1))
    sk = pd.concat(sk_parts).groupby(["game_id", "pid"]).agg(
        sacks=("sk", "sum"), n_half=("half", "sum")).reset_index()
    rp = []
    for c in ("kickoff_returner_player_id", "punt_returner_player_id"):
        x = p.loc[p[c].notna(), ["game_id", c, "td_player_id", "return_touchdown"]].rename(columns={c: "pid"})
        x["rtd"] = ((x["return_touchdown"] == 1) & (x["td_player_id"] == x["pid"])).astype(int)
        rp.append(x)
    rp = pd.concat(rp).groupby(["game_id", "pid"]).agg(returns=("rtd", "size"), ret_td=("rtd", "sum")).reset_index()
    td = (p.loc[p["td_player_id"].notna(), ["game_id", "td_player_id"]]
          .rename(columns={"td_player_id": "pid"}).groupby(["game_id", "pid"]).size()
          .rename("tds").reset_index())
    out = tk.merge(sk, on=["game_id", "pid"], how="outer").merge(
        rp, on=["game_id", "pid"], how="outer").merge(td, on=["game_id", "pid"], how="outer")
    for c in ("tot_tk", "st_tk", "sacks", "n_half", "returns", "ret_td", "tds"):
        out[c] = out[c].fillna(0)
    out["def_tk"] = out["tot_tk"] - out["st_tk"]
    return out.rename(columns={"game_id": "gid"})


def league_return_rate(seasons) -> float:
    """Return touchdowns per return play (kickoff + punt returner set), pbp."""
    n = td = 0
    for s in seasons:
        p = pd.read_parquet(L.CACHE / f"pbp_{s}.parquet",
                            columns=["kickoff_returner_player_id", "punt_returner_player_id",
                                     "td_player_id", "return_touchdown"])
        for c in ("kickoff_returner_player_id", "punt_returner_player_id"):
            x = p[p[c].notna()]
            n += len(x)
            td += int(((x["return_touchdown"] == 1) & (x["td_player_id"] == x[c])).sum())
    return td / max(n, 1)


def universe(stats: pd.DataFrame, idm: pd.DataFrame) -> pd.DataFrame:
    """Every (game, player) with a snap, with that game's pbp stats and as-of
    history over the prior <= 17 games of (norm, team)."""
    sc = pd.read_parquet(L.CACHE / "local_nfl_snap_counts.parquet")
    sc["gid"] = sc["game_id"].str.replace("^NFL_", "", regex=True)
    sc["season"] = sc["gid"].str[:4].astype(int)
    sc = sc[sc["season"].between(HIST_FROM, 2025)]
    sc = sc.rename(columns={"norm_name": "norm"})
    sc = sc[(sc[["offense_pct", "defense_pct", "st_pct"]].fillna(0).sum(axis=1) > 0)]
    sc = sc.drop_duplicates(["gid", "team", "norm"])
    st = stats.merge(idm, on="pid", how="left")
    n_unmapped = st["norm"].isna().sum()
    st = st.dropna(subset=["norm"]).groupby(["gid", "norm"], as_index=False)[
        ["tot_tk", "st_tk", "def_tk", "sacks", "n_half", "returns", "ret_td", "tds"]].sum()
    u = sc.merge(st, on=["gid", "norm"], how="left")
    matched = u["tot_tk"].notna()
    # pbp stat rows that found no snap row (coverage check)
    chk = st[st["gid"].str[:4].astype(int) >= HIST_FROM].merge(
        sc[["gid", "norm"]].drop_duplicates(), on=["gid", "norm"], how="left", indicator=True)
    cov = {
        "pbp ids with no name": int(n_unmapped),
        "ST tackles matched to a snap row": float(chk.loc[chk["_merge"] == "both", "st_tk"].sum()
                                                 / max(chk["st_tk"].sum(), 1)),
        "sacks matched": float(chk.loc[chk["_merge"] == "both", "sacks"].sum() / max(chk["sacks"].sum(), 1)),
        "returns matched": float(chk.loc[chk["_merge"] == "both", "returns"].sum() / max(chk["returns"].sum(), 1)),
    }
    for c in ("tot_tk", "st_tk", "def_tk", "sacks", "n_half", "returns", "ret_td", "tds"):
        u[c] = u[c].fillna(0)
    u["has_stats"] = matched
    u = u.merge(K[["gid", "kick", "week"]], on="gid", how="inner")
    u["sk_any"] = (u["sacks"] >= 0.5).astype(float)
    u["sk_half_only"] = (u["sacks"] == 0.5).astype(float)
    u["st_inv"] = ((u["st_tk"] > 0) | (u["st_pct"].fillna(0) > 0)).astype(float)
    u = u.sort_values(["norm", "team", "kick"]).reset_index(drop=True)
    g = u.groupby(["norm", "team"], sort=False)
    u["pr_n17"] = g.cumcount().clip(upper=17)
    u["pr_n8"] = g.cumcount().clip(upper=8)
    for c in ("st_tk", "def_tk", "tot_tk", "sk_any", "sk_half_only", "n_half", "st_inv", "returns", "ret_td"):
        u["pr17_" + c] = g[c].transform(lambda s: s.shift(1).rolling(17, min_periods=1).sum())
    u["pr8_returns"] = g["returns"].transform(lambda s: s.shift(1).rolling(8, min_periods=1).sum())
    # career-to-date return totals (for the shrunk per-return TD rate)
    u["cum_returns"] = g["returns"].transform(lambda s: s.shift(1).cumsum())
    u["cum_ret_td"] = g["ret_td"].transform(lambda s: s.shift(1).cumsum())
    for c in [c for c in u.columns if c.startswith("pr") or c.startswith("cum_")]:
        u[c] = u[c].fillna(0)
    return u, cov


def attach(b: pd.DataFrame, u: pd.DataFrame, cols) -> pd.DataFrame:
    """Props board rows -> the player's universe row for that game (unique norm
    within the game; a name on both rosters is dropped)."""
    uu = u[["gid", "norm"] + list(cols)]
    dup = uu.duplicated(["gid", "norm"], keep=False)
    uu = uu[~dup]
    return b.merge(uu, on=["gid", "norm"], how="inner")


# ─── PART 0: house rules ───────────────────────────────────────────────────

def part0():
    banner("PART 0. Settlement clauses, re-read from the filed house rules in <cache>/house_rules/")
    try:
        import pypdf
    except ImportError:
        print("  pypdf not installed: clauses not re-read (they are quoted in the docstring)")
        return
    pats = [r"Tackles \+ Assists – Includes[^.]*\.", r"Half sacks count as[^.]*\.",
            r"Tackles, Assists, Tackles and Assists, other Defensive Markets – [^●]*",
            r"Player Defensive Tackles \+ Assists • Special teams tackles do not count\.",
            r"Defensive Tackles and Tackles\+Assists markets will only consider[^.]*\.",
            r"Only tackles made on defense will count[^.]*\.\s*Special teams tackles will not be counted\.",
            r"Includes 0\.5 sacks awarded, however[^.]*\.[^.]*\.",
            r"Individual Sacks can be awarded in increments of 0\.5[^.]*\.",
            r"FO\.6\.8 A touchdown scorer is defined as[^.]*\.",
            r"A touchdown scorer is defined as the player in possession of the ball in the opposing end zone[^.]*\."]
    for f in sorted(glob.glob(str(L.CACHE / "house_rules" / "*.pdf"))):
        r = pypdf.PdfReader(f)
        t = re.sub(r"\s+", " ", "\n".join((pg.extract_text() or "") for pg in r.pages))
        hits = []
        for pt in pats:
            m = re.search(pt, t)
            if m:
                hits.append(m.group(0).strip()[:220])
        print(f"  {os.path.basename(f)}")
        for h in hits:
            print(f"      \"{h}\"")
        if not hits:
            print("      (no tackles / sacks / TD-scorer clause matched)")


# ─── PART 1: special-teams tackles ─────────────────────────────────────────

def part1(u, stats_log_check):
    banner("PART 1. SPECIAL-TEAMS TACKLES")
    print("  grading check: game-log tackles (solo + with-assist + assists) vs play-by-play on ALL plays")
    for k, v in stats_log_check.items():
        print(f"    {k}: {v}")
    books = set(TK_EXCL_ST) | TK_INCL_ST | set(TK_UNKNOWN)
    d = load_props("player_tackles_assists", books)
    print(f"\n  pre-kick tackles quotes 2023-25 by book: "
          + ", ".join(f"{b} {n}" for b, n in d['bookmaker'].value_counts().items()))
    cols = ["team", "def_tk", "st_tk", "tot_tk", "pr_n17", "pr17_st_tk", "pr17_def_tk",
            "pr17_st_inv", "has_stats", "st_pct"]

    # 1a FanDuel, as briefed: count and rows
    fd = d[d["bookmaker"] == "fanduel"]
    print(f"\n  1a. FanDuel tackles rows in the archive, any read: {len(fd)}  "
          f"(player-games {fd[['gid','norm']].drop_duplicates().shape[0]}, seasons "
          f"{sorted(fd['season'].unique().tolist())})")
    if len(fd):
        fb = board(d, ["fanduel"])
        fdb = fb[fb["bookmaker"] == "fanduel"][["gid", "norm", "line", "over_price", "under_price", "T"]]
        dkb = fb[fb["bookmaker"] == "draftkings"][["gid", "norm", "line", "over_price", "under_price"]]
        x = fdb.merge(dkb, on=["gid", "norm"], how="left", suffixes=("_fd", "_dk"))
        x = attach(x.rename(columns={}), u, cols)
        x["E_st"] = np.where(x["pr_n17"] > 0, x["pr17_st_tk"] / x["pr_n17"].clip(lower=1), np.nan)
        print("      FanDuel vs DraftKings on the same read (graded on FD's rule = total incl. ST):")
        show = x[["gid", "norm", "line_fd", "over_price_fd", "under_price_fd", "line_dk",
                  "over_price_dk", "under_price_dk", "E_st", "pr_n17", "tot_tk", "st_tk", "def_tk"]]
        print("      " + show.round(2).to_string(index=False).replace("\n", "\n      "))
        print("      -> too few rows for any inference; rule 1a is UNTESTABLE on this archive.")

    # decision board anchored on DraftKings
    b = board(d, ["draftkings"])
    dk = b[b["bookmaker"] == "draftkings"].copy()
    dk = dk[dk["under_price"].notna() & dk["over_price"].notna()]
    dk = attach(dk, u, cols)
    dk = dk[dk["pr_n17"] >= 4].copy()
    dk["E_st"] = dk["pr17_st_tk"] / dk["pr_n17"]
    dk["E_def"] = dk["pr17_def_tk"] / dk["pr_n17"]
    dk["zero_st"] = (dk["pr17_st_inv"] == 0)
    # best under at DK's line among defense-only books on the read
    ex = b[b["bookmaker"].isin(TK_EXCL_ST) & b["under_price"].notna()][["gid", "norm", "line", "bookmaker", "under_price"]]
    ex = ex.assign(dpay=dec(ex["under_price"]))
    best = ex.sort_values("dpay").groupby(["gid", "norm", "line"]).tail(1)
    dk = dk.merge(best[["gid", "norm", "line", "under_price", "bookmaker"]].rename(
        columns={"under_price": "best_under", "bookmaker": "best_book"}), on=["gid", "norm", "line"], how="left")
    dk["game_id"] = dk["gid"]
    print(f"\n  DraftKings decision board: {len(dk)} player-games with >= 4 prior games "
          f"(per season {dk.groupby('season').size().to_dict()}); lead hours median "
          f"{dk['lead_h'].median():.1f}; best under came from "
          f"{dk['best_book'].value_counts().to_dict()}")
    print("  E[ST] distribution (ST tackles / game, prior <= 17 games): "
          + ", ".join(f"q{int(q*100)} {v:.2f}" for q, v in dk["E_st"].quantile([.25, .5, .75, .9, .95, .99]).items())
          + f"; zero-ST-involvement players {int(dk['zero_st'].sum())}")
    print(f"  listed player-games with NO play-by-play stat at all (graded on 0 tackles): "
          f"{(~dk['has_stats']).sum()} ({100*(~dk['has_stats']).mean():.2f}%)")

    # pricing diagnostics (no outcomes)
    print("\n  PRICING DIAGNOSTIC 1 (no outcomes): OLS  DK line = a + b*E[def tackles] + c*E[ST tackles]")
    X = np.column_stack([np.ones(len(dk)), dk["E_def"], dk["E_st"]])
    y = dk["line"].values
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    gids = dk["gid"].values
    ug, inv = np.unique(gids, return_inverse=True)
    rng = np.random.default_rng(3)
    bs = []
    rows_by_g = [np.where(inv == i)[0] for i in range(len(ug))]
    for _ in range(300):
        pick = rng.integers(0, len(ug), len(ug))
        ii = np.concatenate([rows_by_g[j] for j in pick])
        bs.append(np.linalg.lstsq(X[ii], y[ii], rcond=None)[0])
    bs = np.array(bs)
    for nm, k in (("a (intercept)", 0), ("b E[def]", 1), ("c E[ST]", 2)):
        print(f"    {nm:14s} {coef[k]:+.3f}   90% CI ({np.quantile(bs[:, k], .05):+.3f}, {np.quantile(bs[:, k], .95):+.3f})")
    print("    reading: c near 0 = DK leaves ST tackles out of its line (consistent with its rule);"
          " c near b = DK prices them in although it does not count them.")

    def ebucket(e):
        return pd.cut(e, [-0.01, 0.0, 0.10, 0.25, 0.50, 10], labels=["0", "(0,.10]", "(.10,.25]", "(.25,.50]", ">.50"])

    print("\n  PRICING DIAGNOSTIC 2 (no outcomes): mean (book line - DK line), same player, same read, by E[ST]")
    others = b[~b["bookmaker"].isin(["draftkings"])][["gid", "norm", "bookmaker", "line"]]
    oo = dk[["gid", "norm", "line", "E_st"]].merge(others, on=["gid", "norm"], suffixes=("_dk", ""))
    oo["diff"] = oo["line"] - oo["line_dk"]
    oo["bucket"] = ebucket(oo["E_st"])
    tab = oo.pivot_table(index="bookmaker", columns="bucket", values="diff", aggfunc="mean", observed=False).round(3)
    cnt = oo.pivot_table(index="bookmaker", columns="bucket", values="diff", aggfunc="size", observed=False)
    tab["rule"] = [("incl ST" if bk in TK_INCL_ST else "excl ST" if bk in TK_EXCL_ST else "unknown") for bk in tab.index]
    tab["n"] = cnt.sum(axis=1)
    print("    " + tab.to_string().replace("\n", "\n    "))
    print("    a book that counts ST tackles and prices them should sit ABOVE DK in the right-hand columns.")

    print("\n  PREDICTOR CHECK: realised ST tackles in the game by E[ST] bucket (DK-listed players)")
    dk["bucket"] = ebucket(dk["E_st"])
    pc = dk.groupby("bucket", observed=False).agg(n=("st_tk", "size"), E_st=("E_st", "mean"),
                                                  realised_st=("st_tk", "mean"),
                                                  share_ge1=("st_tk", lambda s: (s >= 1).mean()))
    print("    " + pc.round(3).to_string().replace("\n", "\n    "))

    # outcomes -------------------------------------------------------------
    print("\n  GRADING CHECK: DK over rate (line excluded) by settlement definition, all DK player-games")
    for lab, col in (("defense-only (DK's rule)", "def_tk"), ("total incl. ST", "tot_tk")):
        over = (dk[col] > dk["line"]).mean()
        under = (dk[col] < dk["line"]).mean()
        print(f"    {lab:26s} over {100*over:.1f}%  under {100*under:.1f}%  "
              f"mean (actual - line) {(dk[col]-dk['line']).mean():+.3f}")
    fo, fu = L.devig2(dk["over_price"], dk["under_price"])
    print(f"    DK de-vigged mean P(over) {100*np.nanmean(fo):.1f}%")

    def grade_under(df, price_col):
        df = df[df[price_col].notna()].copy()
        won = (df["def_tk"] < df["line"]).astype(int)
        push = (df["def_tk"] == df["line"]).astype(int)
        df["profit"] = L.profit_units(won, df[price_col], push)
        return df

    g_best = grade_under(dk, "best_under")
    g_dk = grade_under(dk, "under_price")

    banner("1b. DK UNDER (graded defense-only) when E[ST] >= x  -- full neighbourhood, best defense-only price")
    print(f"  {'x':>5} {'cohort':10s} {hdr()}")
    for x in TK_X:
        print(f"  {x:>5.2f} {'best price':10s} {fmt(gcell(f"1b DK under E[ST]>={x}", g_best[g_best.E_st >= x]))}")
        print(f"  {'':>5} {'DK price':10s} {fmt(cell(g_dk[g_dk.E_st >= x]))}")
    print(f"  {'all':>5} {'best price':10s} {fmt(cell(g_best))}   <- every DK under, the base rate")
    print(f"  {'PLAC':>5} {'zero ST':10s} {fmt(cell(g_best[g_best.zero_st]))}   <- placebo: zero ST involvement")
    print("  * = strict (<= 30 bets per season on average)")

    print("\n  same rule graded on TOTAL incl. ST (what it would be if DK counted ST tackles -- it does not):")
    alt = dk[dk["best_under"].notna()].copy()
    alt["profit"] = L.profit_units((alt["tot_tk"] < alt["line"]).astype(int), alt["best_under"],
                                   (alt["tot_tk"] == alt["line"]).astype(int))
    for x in (0.10, 0.20, 0.30, 0.50):
        print(f"  {x:>5.2f} {'total':10s} {fmt(cell(alt[alt.E_st >= x]))}")

    fitc = {x: g_best[(g_best.E_st >= x) & g_best.season.isin(FIT)] for x in TK_X}
    xs = choose(fitc, FIT)
    print(f"\n  FIT 2023-2024 -> chosen x = {xs}")
    if xs is not None:
        ho = g_best[(g_best.E_st >= xs) & g_best.season.isin(HOLD)]
        print(f"  {'fit':10s} {fmt(cell(fitc[xs]))}")
        print(f"  {'HOLD 2025':10s} {fmt(cell(ho))}")
        add_test(f"1b DK under, E[ST]>={xs}, hold-out 2025", ho, SEASONS, "hold-out")
        plac = g_best[g_best.zero_st & g_best.season.isin(HOLD)]
        print(f"  {'placebo 25':10s} {fmt(cell(plac))}")
        splits(g_best[g_best.E_st >= xs], f"chosen cell E[ST] >= {xs}: by season and early/late")
    splits(g_best[g_best.zero_st], "placebo (zero ST involvement): by season and early/late")

    print("\n  descriptive, NOT a test (rule unknown at these books): OVER at each unknown-rule book when"
          " E[ST] >= 0.30 and its line equals DK's, graded both ways")
    oth = b[b["bookmaker"].isin(TK_UNKNOWN) & b["over_price"].notna()][["gid", "norm", "line", "bookmaker", "over_price"]]
    z = dk[["gid", "norm", "line", "E_st", "def_tk", "tot_tk", "season", "week", "game_id"]].merge(
        oth, on=["gid", "norm", "line"])
    z = z[z["E_st"] >= 0.30]
    print(f"  {'book':12s} {'graded':8s} {hdr()}")
    for bk in TK_UNKNOWN:
        zz = z[z["bookmaker"] == bk]
        for lab, col in (("total", "tot_tk"), ("def-only", "def_tk")):
            q = zz.copy()
            q["profit"] = L.profit_units((q[col] > q["line"]).astype(int), q["over_price"], (q[col] == q["line"]).astype(int))
            print(f"  {bk:12s} {lab:8s} {fmt(cell(q))}")
    return dk


# ─── PART 2: half sacks ────────────────────────────────────────────────────

def part2(u, sack_check):
    banner("PART 2. HALF SACKS")
    print("  grading check: play-by-play sacks (1 per sack id + 0.5 per half-sack id) vs game-log def_sacks")
    for k, v in sack_check.items():
        print(f"    {k}: {v}")
    books = {"fanduel", "draftkings"} | set(HALF_LINE_BOOKS)
    d = load_props("player_sacks", books, SACK_SEASONS)
    fdall = d[d["bookmaker"] == "fanduel"]
    print(f"\n  FanDuel sack quotes: {len(fdall)}; lines {fdall['line'].value_counts().to_dict()}; "
          f"under price present on {fdall['under_price'].notna().mean():.3f} -> yes-only 'to record a sack' at 0.5")
    dkall = d[d["bookmaker"] == "draftkings"]
    print(f"  DraftKings sack lines {dkall['line'].value_counts().to_dict()}, two-way share "
          f"{dkall['under_price'].notna().mean():.3f}")
    b = board(d, ["fanduel"])
    fd = b[(b["bookmaker"] == "fanduel") & (b["line"] == 0.5) & b["over_price"].notna()][
        ["gid", "norm", "over_price", "season", "week", "T", "lead_h"]].rename(columns={"over_price": "fd_yes"})
    dk25 = b[(b["bookmaker"] == "draftkings") & (b["line"] == 0.25) & b["under_price"].notna()][
        ["gid", "norm", "over_price", "under_price"]].rename(columns={"over_price": "dk_o", "under_price": "dk_u"})
    hl = b[b["bookmaker"].isin(HALF_LINE_BOOKS) & (b["line"] == 0.5) & b["under_price"].notna() & b["over_price"].notna()]
    hl = hl.assign(dpay=dec(hl["over_price"]))
    hbest = hl.sort_values("dpay").groupby(["gid", "norm"]).tail(1)[["gid", "norm", "over_price", "under_price", "bookmaker"]]
    hbest = hbest.rename(columns={"over_price": "h_o", "under_price": "h_u", "bookmaker": "h_book"})
    bol = hl[hl["bookmaker"] == "betonlineag"][["gid", "norm", "over_price", "under_price"]].rename(
        columns={"over_price": "bol_o", "under_price": "bol_u"})
    x = fd.merge(dk25, on=["gid", "norm"], how="left").merge(hbest, on=["gid", "norm"], how="left").merge(
        bol, on=["gid", "norm"], how="left")
    x = attach(x, u, ["team", "sacks", "n_half", "pr_n17", "pr17_sk_any", "pr17_sk_half_only", "pr17_n_half",
                      "has_stats"])
    x["game_id"] = x["gid"]
    print(f"  listed player-games with NO play-by-play stat at all (graded on 0 sacks): "
          f"{(~x['has_stats']).sum()} ({100*(~x['has_stats']).mean():.2f}%)")
    print(f"\n  FanDuel decision board: {len(x)} player-games ({x.groupby('season').size().to_dict()}); "
          f"with DK 0.25 two-way {x['dk_o'].notna().sum()}; with a 0.5-line two-way book {x['h_o'].notna().sum()} "
          f"({hbest['h_book'].value_counts().to_dict()}); with betonlineag {x['bol_o'].notna().sum()}")

    print("\n  HOW OFTEN A LISTED PLAYER ENDS ON EXACTLY 0.5 SACKS (FanDuel-listed player-games)")
    for s in SACK_SEASONS:
        xs_ = x[x.season == s]
        anyk = (xs_["sacks"] >= 0.5).mean()
        half = (xs_["sacks"] == 0.5).mean()
        print(f"    {s}: n {len(xs_)}  >=0.5 sacks {100*anyk:.1f}%  exactly 0.5 {100*half:.2f}%  "
              f"exactly-0.5 share of FD yes winners {100*half/max(anyk,1e-9):.1f}%  "
              f">=1 sack {100*(xs_['sacks']>=1).mean():.1f}%")

    # pricing comparison (no outcomes)
    print("\n  PRICING (no outcomes): FD yes vs DK over 0.25 (same event) and vs the best 0.5-line over (smaller event)")
    q = x[x["dk_o"].notna()]
    fdi = L.am_to_prob(q["fd_yes"])
    dkf, _ = L.devig2(q["dk_o"], q["dk_u"])
    print(f"    same player-game n {len(q)}: mean FD implied {100*np.mean(fdi):.2f}%  mean DK fair(over .25) {100*np.mean(dkf):.2f}%"
          f"  mean DK raw implied over {100*np.mean(L.am_to_prob(q['dk_o'])):.2f}%")
    q2 = x[x["h_o"].notna()]
    hf, _ = L.devig2(q2["h_o"], q2["h_u"])
    print(f"    same player-game n {len(q2)}: mean FD implied {100*np.mean(L.am_to_prob(q2['fd_yes'])):.2f}%  mean 0.5-book fair(over .5) "
          f"{100*np.mean(hf):.2f}%  share FD yes price >= 0.5-book over price {100*(dec(q2['fd_yes']) >= dec(q2['h_o'])).mean():.1f}%")
    if x["dk_o"].notna().any() and x["h_o"].notna().any():
        q3 = x[x["dk_o"].notna() & x["h_o"].notna()]
        a, _ = L.devig2(q3["dk_o"], q3["dk_u"])
        h3, _ = L.devig2(q3["h_o"], q3["h_u"])
        print(f"    all three quoted n {len(q3)}: DK fair(>=0.5 incl half) {100*np.mean(a):.2f}% vs 0.5-book fair {100*np.mean(h3):.2f}%"
              f" (difference = what the market charges for the half sack; realised exactly-0.5 rate above)")

    # outcomes
    x["won"] = (x["sacks"] >= 0.5).astype(int)
    x["profit"] = L.profit_units(x["won"], x["fd_yes"])
    x["profit_nohalf"] = L.profit_units((x["sacks"] >= 1).astype(int), x["fd_yes"])
    dkf_all, _ = L.devig2(x["dk_o"], x["dk_u"])
    x["ev_dk"] = dkf_all * dec(x["fd_yes"]) - 1
    m_fit = x.loc[x.season.isin(SACK_FIT) & (x["pr_n17"] >= 4)]
    base = (m_fit["pr17_sk_any"].sum() / m_fit["pr_n17"].sum()) if len(m_fit) else 0.2
    x["p_asof"] = (x["pr17_sk_any"] + 8 * base) / (x["pr_n17"] + 8)
    x["ev_asof"] = np.where(x["pr_n17"] >= 4, x["p_asof"] * dec(x["fd_yes"]) - 1, np.nan)
    x["mismatch"] = x["h_o"].notna() & (dec(x["fd_yes"]) >= dec(x["h_o"]))
    x["zero_half"] = (x["pr_n17"] >= 8) & (x["pr17_n_half"] == 0)
    print(f"\n  as-of base rate (fit 2024, >=0.5 sacks per game among FD-listed players): {base:.3f}")

    print(f"\n  every FD yes (base rate):           {fmt(cell(x, SACK_SEASONS))}")
    print(f"  every FD yes, if half sacks LOST:   {fmt(cell(x.assign(profit=x.profit_nohalf), SACK_SEASONS))}")

    banner("2a. FD yes when EV vs DraftKings' over-0.25 fair (same event) >= c -- full neighbourhood")
    print(f"  {'c':>6} {'cohort':12s} {hdr(SACK_SEASONS)}")
    xa = x[x["ev_dk"].notna()]
    for c in SACK_C:
        print(f"  {c:>+6.2f} {'all':12s} {fmt(gcell(f"2a FD yes EV_dk>={c}", xa[xa.ev_dk >= c], SACK_SEASONS))}")
        print(f"  {'':>6} {'zero-half PL':12s} {fmt(cell(xa[(xa.ev_dk >= c) & xa.zero_half], SACK_SEASONS))}")
    fitc = {c: xa[(xa.ev_dk >= c) & xa.season.isin(SACK_FIT)] for c in SACK_C}
    cs = choose(fitc, SACK_FIT)
    print(f"  FIT 2024 -> chosen c = {cs}")
    if cs is not None:
        ho = xa[(xa.ev_dk >= cs) & xa.season.isin(SACK_HOLD)]
        print(f"  {'fit':10s} {fmt(cell(fitc[cs], SACK_SEASONS))}")
        print(f"  {'HOLD 2025':10s} {fmt(cell(ho, SACK_SEASONS))}")
        add_test(f"2a FD yes, EV vs DK>={cs}, hold-out 2025", ho, SACK_SEASONS, "hold-out")
        splits(xa[xa.ev_dk >= cs], f"2a chosen c={cs}: by season and early/late", SACK_SEASONS)

    banner("2b. FD yes when FD's price >= the best 0.5-line OVER price (FD pays as much for a larger event)")
    xb = x[x["h_o"].notna()]
    print(f"  {'cohort':22s} {hdr(SACK_SEASONS)}")
    print(f"  {'mismatch, all':22s} {fmt(cell(xb[xb.mismatch], SACK_SEASONS))}")
    print(f"  {'mismatch, zero-half PL':22s} {fmt(cell(xb[xb.mismatch & xb.zero_half], SACK_SEASONS))}")
    print(f"  {'mismatch, has half hist':22s} {fmt(cell(xb[xb.mismatch & ~xb.zero_half & (xb.pr_n17 >= 8)], SACK_SEASONS))}")
    print(f"  {'no mismatch':22s} {fmt(cell(xb[~xb.mismatch], SACK_SEASONS))}")
    print(f"  {'mismatch, if half LOST':22s} {fmt(cell(xb[xb.mismatch].assign(profit=lambda q: q.profit_nohalf), SACK_SEASONS))}")
    print("  price gap (FD decimal - 0.5-book decimal) as a neighbourhood:")
    gap = dec(xb["fd_yes"]) - dec(xb["h_o"])
    for lo_, hi_ in ((-9, -0.5), (-0.5, -0.2), (-0.2, 0.0), (0.0, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 99)):
        sel = (gap >= lo_) & (gap < hi_)
        print(f"    gap [{lo_:+.1f},{hi_:+.1f})  {fmt(gcell(f"2b FD-0.5book gap [{lo_},{hi_})", xb[sel], SACK_SEASONS))}")
    add_test("2b FD yes >= 0.5-book over price (no parameter), 2024-25", xb[xb.mismatch], SACK_SEASONS, "as-stated")
    splits(xb[xb.mismatch], "2b mismatch: by season and early/late", SACK_SEASONS)

    banner("2c. FD yes when EV vs the as-of player rate P(>=0.5 sacks) >= c -- full neighbourhood")
    xc = x[x["ev_asof"].notna()]
    print(f"  {'c':>6} {hdr(SACK_SEASONS)}")
    for c in SACK_C:
        print(f"  {c:>+6.2f} {fmt(gcell(f"2c FD yes EV_asof>={c}", xc[xc.ev_asof >= c], SACK_SEASONS))}")
    fitc = {c: xc[(xc.ev_asof >= c) & xc.season.isin(SACK_FIT)] for c in SACK_C}
    cs2 = choose(fitc, SACK_FIT)
    print(f"  FIT 2024 -> chosen c = {cs2}")
    if cs2 is not None:
        ho = xc[(xc.ev_asof >= cs2) & xc.season.isin(SACK_HOLD)]
        print(f"  {'fit':10s} {fmt(cell(fitc[cs2], SACK_SEASONS))}")
        print(f"  {'HOLD 2025':10s} {fmt(cell(ho, SACK_SEASONS))}")
        add_test(f"2c FD yes, EV vs as-of rate>={cs2}, hold-out 2025", ho, SACK_SEASONS, "hold-out")
    return x


# ─── PART 3: QB rushing unders ─────────────────────────────────────────────

def spreads_at(T: pd.DataFrame) -> pd.DataFrame:
    oh = L.odds_hist(["spreads"])
    oh = oh[oh["season"].isin(SEASONS)]
    oh = oh[oh["bookmaker"].isin(set(L.BETTABLE_HIST) | set(L.SHARP))]
    oh = oh[["game_id", "bookmaker", "snapshot_at", "point"]].rename(columns={"game_id": "gid"})
    m = oh.merge(T, on="gid")
    m = m[m["snapshot_at"] <= m["T"]]
    m = m.sort_values("snapshot_at").groupby(["gid", "bookmaker"]).tail(1)
    return m.groupby("gid")["point"].median().rename("home_point").reset_index()


def part3():
    banner("PART 3. QB RUSHING-YARDS UNDERS FOR BIG FAVOURITES")
    d = load_props("player_rush_yds", set(L.BETTABLE) | {"pinnacle"})
    log = player_log()
    log = log[log["season"].between(HIST_FROM, 2025)].copy()
    log["gid"] = log["game_id"].str.replace("^NFL_", "", regex=True)
    log["n"] = log["norm_name"].where(log["norm_name"].notna(), norm_series(log["player_name"]))
    log = log.merge(K[["gid", "kick"]], on="gid", how="inner")
    qb = log[log["pos"] == "QB"].sort_values(["player_id", "kick"]).copy()
    g = qb.groupby("player_id")
    qb["pr_n"] = g.cumcount().clip(upper=17)
    qb["pr_ry"] = g["rushing_yards"].transform(lambda s: s.shift(1).rolling(17, min_periods=1).sum()).fillna(0)
    qb["base"] = np.where(qb["pr_n"] >= 3, qb["pr_ry"] / qb["pr_n"].clip(lower=1), np.nan)
    qb = qb.drop_duplicates(["gid", "n"], keep=False)

    b = board(d, L.BETTABLE)
    b = b.merge(qb[["gid", "n", "team", "rushing_yards", "base", "pr_n"]].rename(columns={"n": "norm"}),
                on=["gid", "norm"], how="inner")
    # line: DK's, else the modal bettable line
    bet = b[b["bookmaker"].isin(L.BETTABLE)]
    dkl = bet[bet["bookmaker"] == "draftkings"].groupby(["gid", "norm"])["line"].first().rename("dk_line")
    mode = bet.groupby(["gid", "norm"])["line"].agg(lambda s: s.value_counts().index[0]).rename("mode_line")
    ln = pd.concat([dkl, mode], axis=1).reset_index()
    ln["line"] = ln["dk_line"].fillna(ln["mode_line"])
    ub = bet[bet["under_price"].notna()][["gid", "norm", "line", "under_price", "bookmaker"]]
    ub = ub.assign(dpay=dec(ub["under_price"])).sort_values("dpay").groupby(["gid", "norm", "line"]).tail(1)
    x = ln[["gid", "norm", "line"]].merge(ub[["gid", "norm", "line", "under_price", "bookmaker"]], on=["gid", "norm", "line"])
    pin = b[(b["bookmaker"] == "pinnacle") & b["under_price"].notna() & b["over_price"].notna()][
        ["gid", "norm", "line", "over_price", "under_price"]].rename(columns={"over_price": "pin_o", "under_price": "pin_u"})
    x = x.merge(pin, on=["gid", "norm", "line"], how="left")
    meta = b.drop_duplicates(["gid", "norm"])[["gid", "norm", "team", "rushing_yards", "base", "pr_n",
                                                "season", "week", "T", "lead_h"]]
    x = x.merge(meta, on=["gid", "norm"])
    sp = spreads_at(x[["gid", "T"]].drop_duplicates("gid"))
    x = x.merge(sp, on="gid", how="left").merge(K[["gid", "home_team", "away_team", "spread_line"]], on="gid")
    x["team_point"] = np.where(x["team"] == x["home_team"], x["home_point"], -x["home_point"])
    x["fav"] = -x["team_point"]
    x["game_id"] = x["gid"]
    ok = x["home_point"].notna()
    agree = np.sign(x.loc[ok, "home_point"]) == np.sign(-x.loc[ok, "spread_line"])
    print(f"  QB player-games on the decision read: {len(x)} ({x.groupby('season').size().to_dict()}); "
          f"spread found {ok.mean():.3f}; QB team is the home or away team {((x['team'] == x['home_team']) | (x['team'] == x['away_team'])).mean():.3f}")
    print(f"  spread sanity: corr(consensus home point, -nflverse close) {np.corrcoef(x.loc[ok,'home_point'], -x.loc[ok,'spread_line'])[0,1]:.3f}; "
          f"sign agreement where both non-zero {agree[(x.loc[ok,'home_point']!=0) & (x.loc[ok,'spread_line']!=0)].mean():.3f}")
    print(f"  best under came from {x['bookmaker'].value_counts().to_dict()}; lead hours median {x['lead_h'].median():.1f}")
    x = x[ok].copy()
    won = (x["rushing_yards"] < x["line"]).astype(int)
    push = (x["rushing_yards"] == x["line"]).astype(int)
    x["profit"] = L.profit_units(won, x["under_price"], push)

    # mechanism (descriptive)
    p = pd.concat([pd.read_parquet(L.CACHE / f"pbp_{s}.parquet",
                                   columns=["game_id", "qb_kneel", "rushing_yards", "posteam"])
                   for s in SEASONS], ignore_index=True)
    kn = p[p["qb_kneel"] == 1].groupby(["game_id", "posteam"]).agg(kneels=("qb_kneel", "size"),
                                                                    kneel_yds=("rushing_yards", "sum")).reset_index()
    gg = K[K["season"].isin(SEASONS)][["gid", "home_team", "away_team", "spread_line"]]
    tm = pd.concat([gg.assign(team=gg["home_team"], fav=gg["spread_line"]),
                    gg.assign(team=gg["away_team"], fav=-gg["spread_line"])])
    tm = tm.merge(kn.rename(columns={"game_id": "gid", "posteam": "team"}), on=["gid", "team"], how="left").fillna(
        {"kneels": 0, "kneel_yds": 0})
    tm["b"] = pd.cut(tm["fav"], [-99, -7, -3, 0, 3, 7, 10, 99],
                     labels=["dog 7+", "dog 3-7", "dog 0-3", "fav 0-3", "fav 3-7", "fav 7-10", "fav 10+"], right=False)
    print("\n  MECHANISM (pbp, closing spread, descriptive): kneel-downs per team-game by the team's closing spread")
    print("    " + tm.groupby("b", observed=False).agg(team_games=("kneels", "size"), any_kneel=("kneels", lambda s: (s > 0).mean()),
                                                     kneels=("kneels", "mean"), kneel_yds=("kneel_yds", "mean"))
          .round(3).to_string().replace("\n", "\n    "))

    x["b"] = pd.cut(x["fav"], [-99, -7, -3, 0, 3, 7, 10, 99],
                    labels=["dog 7+", "dog 3-7", "dog 0-3", "fav 0-3", "fav 3-7", "fav 7-10", "fav 10+"], right=False)
    pf, pu = L.devig2(x["pin_o"], x["pin_u"])
    x["pin_fair_u"] = pu
    print("\n  PRICING by the team's spread at the decision read: line vs as-of baseline, actual vs line, Pinnacle fair under vs realised")
    t = x.groupby("b", observed=False).agg(
        n=("line", "size"), line=("line", "mean"), base=("base", "mean"),
        line_minus_base=("line", lambda s: (s - x.loc[s.index, "base"]).mean()),
        actual_minus_line=("line", lambda s: (x.loc[s.index, "rushing_yards"] - s).mean()),
        under_hit=("line", lambda s: (x.loc[s.index, "rushing_yards"] < s).mean()),
        pin_n=("pin_fair_u", lambda s: s.notna().sum()), pin_fair_under=("pin_fair_u", "mean"),
        pin_realised=("pin_fair_u", lambda s: (x.loc[s.dropna().index, "rushing_yards"] < x.loc[s.dropna().index, "line"]).mean()))
    print("    " + t.round(3).to_string().replace("\n", "\n    "))
    print("    by bucket, at the best bettable under:")
    print(f"    {'bucket':10s} {hdr()}")
    for lab in x["b"].cat.categories:
        print(f"    {lab:10s} {fmt(cell(x[x.b == lab]))}")

    banner("3a/3b. AS STATED: under on every QB whose team is favoured by >= 7 / >= 10 (all seasons)")
    print(f"  {'rule':26s} {hdr()}")
    r7 = x[x.fav >= 7]
    r10 = x[x.fav >= 10]
    dog = x[x.fav < 0]
    print(f"  {'3a fav >= 7':26s} {fmt(cell(r7))}")
    print(f"  {'3b fav >= 10':26s} {fmt(cell(r10))}")
    print(f"  {'not fav >= 7':26s} {fmt(cell(x[x.fav < 7]))}")
    print(f"  {'PLACEBO underdog QBs':26s} {fmt(cell(dog))}")
    print(f"  {'all QBs':26s} {fmt(cell(x))}")
    add_test("3a QB under, fav >= 7 (as stated), 2023-25", r7, SEASONS, "as-stated")
    add_test("3b QB under, fav >= 10 (as stated), 2023-25", r10, SEASONS, "as-stated")
    splits(r7, "3a fav >= 7: by season and early/late")
    splits(r10, "3b fav >= 10: by season and early/late")
    splits(dog, "placebo underdogs: by season and early/late")

    banner("3c. REFINEMENT grid: favourite margin x line-vs-baseline (full neighbourhood)")
    x["shade_ok"] = x["base"].notna() & (x["line"] >= x["base"])
    print(f"  {'fav>=':>5} {'filter':16s} {hdr()}")
    fitc = {}
    for f in QB_FAV:
        for lab, msk in (("all", pd.Series(True, index=x.index)), ("line >= baseline", x["shade_ok"])):
            sel = x[(x.fav >= f) & msk]
            print(f"  {f:>5} {lab:16s} {fmt(gcell(f'3c QB under fav>={f} {lab}', sel))}")
            fitc[(f, lab)] = sel[sel.season.isin(FIT)]
    k = choose(fitc, FIT)
    print(f"  FIT 2023-2024 -> chosen cell {k}")
    if k is not None:
        f, lab = k
        msk = x["shade_ok"] if lab != "all" else pd.Series(True, index=x.index)
        ho = x[(x.fav >= f) & msk & x.season.isin(HOLD)]
        print(f"  {'fit':10s} {fmt(cell(fitc[k]))}")
        print(f"  {'HOLD 2025':10s} {fmt(cell(ho))}")
        add_test(f"3c QB under {k}, hold-out 2025", ho, SEASONS, "hold-out")
    return x


# ─── PART 4: returners' anytime TD ─────────────────────────────────────────

def part4(u, league_rate):
    banner("PART 4. ANYTIME TD FOR PRIMARY KICK / PUNT RETURNERS")
    d = load_props("player_anytime_td", set(L.BETTABLE) | {"pinnacle"})
    b = board(d, L.BETTABLE)
    bet = b[b["bookmaker"].isin(L.BETTABLE) & b["over_price"].notna()]
    bet = bet.assign(dpay=dec(bet["over_price"]))
    best = bet.sort_values("dpay").groupby(["gid", "norm"]).tail(1)[["gid", "norm", "over_price", "bookmaker", "season", "week", "lead_h"]]
    pin = b[(b["bookmaker"] == "pinnacle") & b["under_price"].notna() & b["over_price"].notna()][
        ["gid", "norm", "over_price", "under_price"]].rename(columns={"over_price": "pin_o", "under_price": "pin_u"})
    x = best.merge(pin, on=["gid", "norm"], how="left")
    x = attach(x, u, ["team", "tds", "ret_td", "returns", "pr_n8", "pr8_returns", "pr_n17", "pr17_returns",
                      "cum_returns", "cum_ret_td", "has_stats"])
    x = x[x["pr_n8"] >= 3].copy()
    x["rpg"] = x["pr8_returns"] / x["pr_n8"]
    r = (x["cum_ret_td"] + 200 * league_rate) / (x["cum_returns"] + 200)
    x["p_ret"] = 1 - (1 - r) ** x["rpg"]
    x["zero_ret"] = (x["pr17_returns"] == 0)
    x["won"] = (x["tds"] >= 1).astype(int)
    x["profit"] = L.profit_units(x["won"], x["over_price"])
    x["game_id"] = x["gid"]
    pf, _ = L.devig2(x["pin_o"], x["pin_u"])
    x["pin_fair"] = pf
    x["band"] = pd.cut(x["over_price"], [-1e9, 250, 600, 1e9], labels=[p[0] for p in PRICE_BANDS])
    print(f"  league return-TD rate per return, 2016-2022 pbp: {league_rate:.4f}")
    print(f"  anytime-TD decision board: {len(x)} player-games with >= 3 prior games "
          f"({x.groupby('season').size().to_dict()}); best yes came from {x['bookmaker'].value_counts().head(6).to_dict()}")
    print(f"  primary returners (>= 2 returns/game): {int((x.rpg >= 2).sum())}; zero-return players {int(x.zero_ret.sum())}")
    print(f"  listed player-games with NO play-by-play stat at all (graded on 0 TDs): "
          f"{(~x['has_stats']).sum()} ({100*(~x['has_stats']).mean():.2f}%)")
    prim = x[x.rpg >= 2]
    print(f"  primary returners' as-of P(return TD in the game): mean {prim['p_ret'].mean():.4f}; "
          f"realised return-TD games {prim['ret_td'].gt(0).mean():.4f}; "
          f"share of their TD games that included a return TD {prim.loc[prim.tds > 0, 'ret_td'].gt(0).mean():.3f}")

    print("\n  CALIBRATION vs Pinnacle's fair yes (where Pinnacle quotes):")
    print(f"    {'group':22s} {'n':>6} {'pin fair':>9} {'realised':>9} {'gap':>8} {'as-of p_ret':>11}")
    for lab, sel in (("primary returners", x.rpg >= 2), ("some returns (0,2)", (x.rpg > 0) & (x.rpg < 2)),
                     ("zero returns", x.zero_ret)):
        q = x[sel & x["pin_fair"].notna()]
        if len(q):
            print(f"    {lab:22s} {len(q):>6} {100*q.pin_fair.mean():>8.2f}% {100*q.won.mean():>8.2f}% "
                  f"{100*(q.won.mean()-q.pin_fair.mean()):>+7.2f}pp {100*q.p_ret.mean():>10.2f}%")

    banner("4a. AS STATED: anytime TD yes on every primary returner (>= 2 returns/game), best bettable price")
    print(f"  {'cohort':28s} {hdr()}")
    print(f"  {'primary returners':28s} {fmt(cell(prim))}")
    for lab in x["band"].cat.categories:
        print(f"  {'  band ' + lab:28s} {fmt(cell(prim[prim.band == lab]))}")
    print(f"  {'PLACEBO zero-return players':28s} {fmt(cell(x[x.zero_ret]))}")
    for lab in x["band"].cat.categories:
        print(f"  {'  band ' + lab:28s} {fmt(cell(x[x.zero_ret & (x.band == lab)]))}")
    add_test("4a returner anytime TD yes (as stated), 2023-25", prim, SEASONS, "as-stated")
    splits(prim, "4a primary returners: by season and early/late")

    banner("4b. REFINEMENT grid: returns per game x price band (full neighbourhood)")
    print(f"  {'rpg>=':>5} {'band':12s} {hdr()}")
    fitc = {}
    for rr in RET_RPG:
        for lab in ["all"] + list(x["band"].cat.categories):
            sel = x[(x.rpg >= rr) & ((x.band == lab) if lab != "all" else True)]
            print(f"  {rr:>5} {lab:12s} {fmt(gcell(f'4b returner yes rpg>={rr} {lab}', sel))}")
            fitc[(rr, lab)] = sel[sel.season.isin(FIT)]
    k = choose(fitc, FIT)
    print(f"  FIT 2023-2024 -> chosen cell {k}")
    if k is not None:
        rr, lab = k
        ho = x[(x.rpg >= rr) & ((x.band == lab) if lab != "all" else True) & x.season.isin(HOLD)]
        print(f"  {'fit':10s} {fmt(cell(fitc[k]))}")
        print(f"  {'HOLD 2025':10s} {fmt(cell(ho))}")
        add_test(f"4b returner yes {k}, hold-out 2025", ho, SEASONS, "hold-out")
    return x


# ─── main ──────────────────────────────────────────────────────────────────

def main():
    global K
    K = kicks()
    part0()
    idm = id_map()
    stats = pbp_stats(range(HIST_FROM, 2026))
    # grading checks against the game log
    log = player_log()
    log = log[log["season"].between(2023, 2025)].copy()
    log["gid"] = log["game_id"].str.replace("^NFL_", "", regex=True)
    lc = log[["gid", "player_id", "def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists", "def_sacks"]].merge(
        stats.rename(columns={"pid": "player_id"}), on=["gid", "player_id"], how="left")
    for c in ("tot_tk", "sacks", "n_half", "st_tk"):
        lc[c] = lc[c].fillna(0)
    lt = lc["def_tackles_solo"].fillna(0) + lc["def_tackles_with_assist"].fillna(0) + lc["def_tackle_assists"].fillna(0)
    tk_check = {"player-games 2023-25": len(lc),
                "log total == pbp all-play total": round(float((lt == lc["tot_tk"]).mean()), 4),
                "log total == pbp DEFENSE-ONLY total": round(float((lt == lc["tot_tk"] - lc["st_tk"]).mean()), 4),
                "ST tackles per player-game, mean": round(float(lc["st_tk"].mean()), 4),
                "share of all tackles on special teams": round(float(lc["st_tk"].sum() / max(lc["tot_tk"].sum(), 1)), 4)}
    sk_check = {"log def_sacks == pbp sacks": round(float((lc["def_sacks"].fillna(0) == lc["sacks"]).mean()), 4),
                "log def_sacks non-integer share (of sack games)": round(float(((lc["def_sacks"] % 1) != 0).sum()
                                                                          / max((lc["def_sacks"] > 0).sum(), 1)), 4)}
    u, cov = universe(stats, idm)
    print(f"\n  name aliases (log name -> snap/prop name): {ALIAS_STATS}")
    print("  play-by-play -> snap-universe coverage: " + ", ".join(f"{k} {v if isinstance(v, int) else round(v, 4)}"
                                                           for k, v in cov.items()))
    part1(u, tk_check)
    part2(u, sk_check)
    part3()
    # league per-return TD rate from seasons before every graded season
    league_rate = league_return_rate(range(2016, 2023))
    part4(u, league_rate)

    banner("MULTIPLE COMPARISONS: every test above, Benjamini-Hochberg at q = 0.10 (one-sided p, ROI > 0)")
    t = pd.DataFrame(TESTS)
    m = len(t)
    t = t.sort_values("p").reset_index(drop=True)
    t["rank"] = np.arange(1, m + 1)
    t["bh_crit"] = 0.10 * t["rank"] / m
    passed = t["p"] <= t["bh_crit"]
    kmax = t.loc[passed, "rank"].max() if passed.any() else 0
    t["BH_reject"] = t["rank"] <= kmax
    t["p_adj"] = np.minimum.accumulate((t["p"] * m / t["rank"])[::-1])[::-1].clip(upper=1)
    print(f"  tests counted: {m} (FanDuel rule 1a is untestable and not counted)")
    print("  " + t[["test", "kind", "bets", "units", "roi", "lo", "hi", "p", "p_adj", "BH_reject"]].round(3)
          .to_string(index=False).replace("\n", "\n  "))

    banner("GRID-WIDE: every grid cell printed above treated as a comparison, BH at q = 0.10")
    gd = pd.DataFrame([{k: v for k, v in r.items() if k not in ("df", "seasons")} for r in GRID])
    small = gd[gd["bets"] < 20]
    gb = bh(gd[gd["bets"] >= 20])
    print(f"  grid cells: {len(gd)}; {len(small)} have < 20 bets and are left out (a bootstrap p on that few "
          f"bets is meaningless: e.g. {small.sort_values('roi', ascending=False).head(3)['cell'].tolist()})")
    print(f"  cells corrected: {len(gb)}; one-sided p <= 0.05: {int((gb.p <= 0.05).sum())}; "
          f"surviving BH: {int(gb.BH_reject.sum())}")
    print("  the ten smallest p:")
    print("  " + gb.head(10)[["cell", "bets", "per_season", "units", "roi", "lo", "hi", "p", "p_adj", "BH_reject"]]
          .round(3).to_string(index=False).replace("\n", "\n  "))

    banner("POST-HOC (NOT tests): in each grid, the strict cell (<= 30 bets/season) with >= 20 bets and the highest 90% CI lower bound")
    seen = set()
    for r in sorted(GRID, key=lambda r: -r["lo"]):
        fam = r["cell"].split(" ")[0]
        if fam in seen or r["per_season"] > STRICT or r["bets"] < 20:
            continue
        seen.add(fam)
        splits(r["df"], f"{r['cell']}  ({r['bets']} bets, {r['per_season']:.1f} per season)", r["seasons"])


if __name__ == "__main__":
    main()
