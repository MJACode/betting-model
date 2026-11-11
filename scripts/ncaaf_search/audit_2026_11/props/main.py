"""NCAAF player props: does the market-relative rule make money at real stored prices?

DEFINITIONS -- written before any result was looked at. Nothing below is tuned.
===========================================================================
DATA      the audit cache (paths.CACHE): ncaaf_prop_odds.parquet (quotes), ncaaf_games.parquet
          (commence_time), local mirror public.ncaaf_player_game_log (results).
SEASON    football season: year of game_date if month >= 7, else year - 1
          (four January-2026 bowl games carry a "2026" game_id and are 2025).
PRE-GAME  snapshot_at (parsed to UTC) < the game's commence_time AND
          snapshot_type != 'in_play'.
MARKETS   the eight over/under markets: pass yds, pass tds, completions,
          attempts, interceptions, rush yds, reception yds, receptions.
          player_anytime_td skipped (no book posts a No price -- measured in
          inspect3.py). *_alternate ladders are not in the main test.
TWO-WAY   a quote = one book, one snapshot, one line, BOTH prices present.
WINDOW    per game, stamps within 10 minutes of each other are one window
          (measured: every pull carries one stamp, min gap 134.9 minutes, so a
          window is exactly one pull).
DE-VIG    multiplicative: fair_over = imp(over) / (imp(over) + imp(under)).
          Sensitivity S1: power method.
BETTABLE  draftkings, fanduel, betmgm, williamhill_us, fanatics, betrivers,
          hardrockbet. Only two-way quotes are bettable in the primary test.
REFERENCE each run separately:
            pinnacle | bovada | betonlineag  (single book, two-way, de-vigged)
            consensus = median de-vigged probability of all OTHER books (any
              book in the feed except the one being bet) quoting the same
              player/market/line two-way in the same window; needs >= 2 others.
          PLACEBO references: every retail book in the feed, same code:
            draftkings, fanduel, betmgm, williamhill_us, betrivers,
            hardrockbet, espnbet, fliff, rebet, fanatics. A bettable book used
            as the reference is removed from the bettable set for that run.
EQUAL LINE the soft quote and the reference must be at the same line, same
          window. Mismatches are counted, never compared.
EDGE      reference no-vig probability of the side MINUS the soft book's
          implied probability of its own price (vig included).
CUTS      0.02, 0.03, 0.04, 0.05, 0.06, 0.08  (edge >= cut). No edge cap.
LOCK      one bet per proposition (game, player, market): the FIRST window in
          which any bettable book's side has edge >= cut. If several
          (book, side) qualify in that window: the largest edge; ties by
          bettable-book order above, then over before under. The bet is that
          book's side at that book's price and line. Never re-priced.
GRADING   stat = ncaaf_player_game_log column for the market (same map as
          scripts/ncaaf_prop_market_sweep.py / the app's FOOTBALL_STAT_TO_MARKET).
          over wins if actual > line, under if actual < line, equal = push (0).
          Log row present but the stat column is NULL -> the player played and
          recorded none of that stat -> actual = 0 (PRIMARY). Sensitivity S2:
          NULL stat = no action (the repo's NFL settle convention).
          No log row in a game the log holds, and the name IS known in that
          season's log for one of the two teams -> did not play -> NO ACTION.
          Name never in the season log for either team -> one conservative
          fallback (unique same-surname player in that game whose first name
          is a >=3-letter prefix of the other's, or whose whole normalised
          name is a >=8-char prefix of the other's); still nothing -> DROPPED
          UNMATCHED and counted. Two log players with one normalised name in a
          game -> DROPPED AMBIGUOUS.
STAKE     1 unit to win, risk capped at 3: risk = min(1/(dec-1), 3),
          win = risk*(dec-1). ROI = units / units risked (W, L and P stakes).
INTERVAL  95% by resampling game dates with replacement, 2000 draws, seed 42.
HALVES    per season, split at the median distinct game date of that season's
          pre-game main-market prop games (first half = on or before it).
          Pooled rows (pinnacle, consensus): the two halves are the two seasons.
CLOSE     the reference's LAST pre-kick window for that proposition; if it
          still quotes the bet's line, close value = its de-vigged probability
          of the bet's side minus the implied probability of the price taken.
          Reported only on bets where that window is LATER than the bet's own
          (otherwise it is the entry edge again). 2025 has one snapshot per
          game, so 2025 has no close value at all.
CLEARS    a (season, named reference, cut) cell clears only if ALL of:
            >= 150 graded bets; ROI > 0 in both halves;
            interval lower bound > 0 OR mean close value > 0;
            its ROI is above every retail placebo reference that has >= 50
            graded bets at the same season and cut.
VARIANTS  PRIMARY (two-way soft quotes, multiplicative, NULL stat = 0):
            2 seasons x (4 named + 10 placebo references) x 6 cuts, plus
            pooled rows for pinnacle and consensus.
          S1 power de-vig              -- named references only
          S2 NULL stat = no action     -- named references only
          S3 one-way soft quotes allowed (lets BetRivers' over-only quotes in;
             the edge formula needs only the soft price) -- named refs only
          Nothing else is run. The count of cells is printed at the end.

ADDED AFTER THE PRIMARY GRID WAS SEEN (kept apart, labelled POST-HOC everywhere):
          The first run (main_v1_as_first_run.py, grid_v1_first_run.csv) showed
          the primary edge definition leaves at most 42 bets a season against
          Pinnacle and 107 against the consensus -- too few to test anything.
          That definition (edge after the soft book's vig) is stricter than the
          rule the repo actually runs on the NFL and ran on NCAAF 2025:
          models/market_relative.find_bets takes edge = reference fair
          probability MINUS THE SOFT BOOK'S OWN DE-VIGGED probability. So one
          more variant, with nothing else changed (same cuts, lock, grading):
          S4 repo edge definition (soft side de-vigged, multiplicative) -- all
             named AND placebo references, so it has its own placebo table.
          Also added in the same pass: pooled 2025+2026 rows for every
          reference (the first run pooled only pinnacle and consensus), so a
          pooled named row can be set beside pooled placebo rows.
          No cut, book list, lock rule or grading rule was changed.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import glob
import sys
import unicodedata

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 600)

SP = str(WORK)
D = SP + r"\data"
OUT = SP + r"\props"
LOG = str(MIRROR / "public.ncaaf_player_game_log")

CUTS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
BETTABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet"]
NAMED_REFS = ["pinnacle", "bovada", "betonlineag", "consensus"]
PLACEBO_REFS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet",
                "espnbet", "fliff", "rebet", "fanatics"]
MARKET_STAT = {
    "player_pass_yds": "passing_yards",
    "player_pass_tds": "passing_tds",
    "player_pass_completions": "completions",
    "player_pass_attempts": "attempts",
    "player_pass_interceptions": "interceptions",
    "player_rush_yds": "rushing_yards",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
}
PRIO = {b: i for i, b in enumerate(BETTABLE)}
KEY3 = ["game_id", "nn", "market"]
KEY5 = ["game_id", "nn", "market", "win", "line"]
SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
N_BOOT = 2000
SEED = 42


# ───────────────────────────── helpers ─────────────────────────────
def strip_acc(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def tokens(name: str) -> list[str]:
    s = strip_acc(name).replace(".", "").replace(",", " ").replace("'", "").replace("’", "")
    t = ["".join(c for c in w if c.isalnum()) for w in s.split()]
    t = [w for w in t if w]
    while len(t) > 1 and t[-1] in SUFFIX:
        t = t[:-1]
    return t


def norm(name: str) -> str:
    return "".join(tokens(name))


def tnorm(n: str) -> str:
    return "".join(c for c in strip_acc(n) if c.isalnum())


def imp(x):
    x = np.asarray(x, dtype=float)
    return np.where(x > 0, 100.0 / (x + 100.0), -x / (-x + 100.0))


def devig_power(io, iu):
    io = np.asarray(io, float)
    iu = np.asarray(iu, float)
    lo = np.full_like(io, 0.2)
    hi = np.full_like(io, 8.0)
    for _ in range(70):
        mid = (lo + hi) / 2
        f = io ** mid + iu ** mid - 1.0          # decreasing in the exponent
        hi = np.where(f < 0, mid, hi)
        lo = np.where(f >= 0, mid, lo)
    k = (lo + hi) / 2
    return io ** k, iu ** k


def median_american(price):
    """Median price, taken in decimal odds (monotone in the price) and converted back to American."""
    pr = np.asarray(price, float)
    dec = np.where(pr > 0, 1.0 + pr / 100.0, 1.0 + 100.0 / np.abs(pr))
    m = float(np.median(dec))
    return (m - 1.0) * 100.0 if m >= 2.0 else -100.0 / (m - 1.0)


def stake(price):
    price = np.asarray(price, float)
    b = np.where(price > 0, price / 100.0, 100.0 / np.abs(price))   # decimal - 1
    risk = np.minimum(1.0 / b, 3.0)
    return risk, risk * b


# ───────────────────────────── load ─────────────────────────────
def load():
    p = pd.read_parquet(D + r"\ncaaf_prop_odds.parquet")
    g = pd.read_parquet(D + r"\ncaaf_games.parquet")
    lt = pd.concat([pq.read_table(f).to_pandas() for f in sorted(glob.glob(LOG + r"\*.parquet"))],
                   ignore_index=True)
    g["ct"] = pd.to_datetime(g.commence_time, utc=True, format="ISO8601")
    p["ts"] = pd.to_datetime(p.snapshot_at, utc=True, format="ISO8601")
    for c in ("line", "over_price", "under_price"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    gd = pd.to_datetime(p.game_date)
    p["season"] = np.where(gd.dt.month >= 7, gd.dt.year, gd.dt.year - 1)
    p = p.merge(g[["game_id", "ct", "home_team", "away_team"]], on="game_id", how="left")
    assert p.ct.notna().all()
    p["pre"] = (p.ts < p.ct) & (p.snapshot_type != "in_play")
    return p, g, lt


def add_windows(df):
    st = df[["game_id", "ts"]].drop_duplicates().sort_values(["game_id", "ts"]).reset_index(drop=True)
    gap = st.groupby("game_id").ts.diff()
    new = (gap.isna() | (gap > pd.Timedelta(minutes=10))).astype(int)
    st["win"] = new.groupby(st.game_id).cumsum() - 1
    st["win_ts"] = st.groupby(["game_id", "win"]).ts.transform("min")
    return df.merge(st, on=["game_id", "ts"], how="left")


def build_quotes(p, markets):
    q = p[p.pre & p.market.isin(markets) & p.line.notna()
          & (p.over_price.notna() | p.under_price.notna())].copy()
    q = add_windows(q)
    q["nn"] = q.player_name.map(norm)
    q = q.rename(columns={"bookmaker": "book", "over_price": "op", "under_price": "up"})
    q = (q.sort_values("ts").drop_duplicates(["game_id", "nn", "market", "book", "win", "line"], keep="last"))
    q["two"] = q.op.notna() & q.up.notna()
    io, iu = imp(q.op), imp(q.up)
    q["fo_m"] = io / (io + iu)
    q["fu_m"] = iu / (io + iu)
    po, pu = devig_power(np.where(q.two, io, 0.5), np.where(q.two, iu, 0.5))
    q["fo_p"] = np.where(q.two, po, np.nan)
    q["fu_p"] = np.where(q.two, pu, np.nan)
    cols = ["season", "game_id", "game_date", "player_name", "nn", "market", "book", "win", "win_ts",
            "line", "op", "up", "two", "fo_m", "fu_m", "fo_p", "fu_p", "home_team", "away_team"]
    return q[cols].reset_index(drop=True)


# ───────────────────────────── actuals ─────────────────────────────
def build_actuals(q, g, lt):
    """One row per proposition (game_id, nn, market): status, actual, nan0."""
    lt = lt.copy()
    lt["nn"] = lt.player_name.map(norm)
    lt["tn"] = lt.team.map(tnorm)
    lt["tok"] = lt.player_name.map(tokens)
    lg = lt.groupby("game_id").agg(teams=("tn", lambda s: frozenset(s.unique())),
                                   gdate=("game_date", "first")).reset_index()
    lg["gdate"] = pd.to_datetime(lg.gdate)
    by_teams = {}
    for r in lg.itertuples():
        by_teams.setdefault(r.teams, []).append((r.gdate, r.game_id))
    logids = set(lg.game_id)

    pg = q[["game_id", "season", "game_date", "home_team", "away_team"]].drop_duplicates("game_id").copy()
    pg["gdate"] = pd.to_datetime(pg.game_date)
    gmap, ghow = {}, {}
    for r in pg.itertuples():
        teams = frozenset((tnorm(r.home_team), tnorm(r.away_team)))
        if r.game_id in logids:
            gmap[r.game_id], ghow[r.game_id] = r.game_id, "direct"
            continue
        c = [i for d, i in by_teams.get(teams, []) if abs((d - r.gdate).days) <= 1]
        if len(c) == 1:
            gmap[r.game_id], ghow[r.game_id] = c[0], "teams_within_1_day"
        else:
            gmap[r.game_id], ghow[r.game_id] = None, ("ambiguous" if c else "none")

    cnt = lt.groupby(["game_id", "nn"]).size()
    amb = set(cnt[cnt > 1].index)
    rows = {k: v for k, v in zip(zip(lt.game_id, lt.nn), lt.to_dict("records"))}
    by_game = {}
    for rec in lt.to_dict("records"):
        by_game.setdefault(rec["game_id"], []).append(rec)
    season_team_names = set(zip(lt.season, lt.tn, lt.nn))

    props = q[["season", "game_id", "nn", "market", "player_name", "home_team", "away_team"]].drop_duplicates(KEY3)
    out = []
    for r in props.itertuples():
        lgid = gmap.get(r.game_id)
        rec, status = None, None
        if lgid is None:
            status = "game_not_in_log"
        elif (lgid, r.nn) in amb:
            status = "ambiguous"
        elif (lgid, r.nn) in rows:
            rec, status = rows[(lgid, r.nn)], "matched"
        else:
            teams = (tnorm(r.home_team), tnorm(r.away_team))
            if any((r.season, t, r.nn) in season_team_names for t in teams):
                status = "dnp"
            else:
                tk = tokens(r.player_name)
                hits = []
                if len(tk) >= 2:
                    for c in by_game.get(lgid, []):
                        ct = c["tok"]
                        if len(ct) < 2:
                            continue
                        a, b = sorted((tk[0], ct[0]), key=len)
                        f1 = ct[-1] == tk[-1] and len(a) >= 3 and b.startswith(a)
                        s_, l_ = sorted((r.nn, c["nn"]), key=len)
                        f2 = len(s_) >= 8 and l_.startswith(s_)
                        if f1 or f2:
                            hits.append(c)
                if len(hits) == 1 and (lgid, hits[0]["nn"]) not in amb:
                    rec, status = hits[0], "matched_fallback"
                else:
                    status = "unmatched"
        actual, nan0, logname = np.nan, False, None
        if rec is not None:
            v = rec[MARKET_STAT[r.market]]
            logname = rec["player_name"]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                actual, nan0 = 0.0, True
            else:
                actual = float(v)
        out.append((r.game_id, r.nn, r.market, status, actual, nan0, logname, ghow.get(r.game_id)))
    a = pd.DataFrame(out, columns=KEY3 + ["status", "actual", "nan0", "log_name", "game_how"])
    return a, ghow


# ───────────────────────────── candidates / lock / grade ─────────────────────────────
def build_candidates(q, ref, devig="m", soft_one_way=False, edge_def="vig"):
    fo, fu = f"fo_{devig}", f"fu_{devig}"
    two = q[q.two]
    softbooks = [b for b in BETTABLE if b != ref]
    soft = q[q.book.isin(softbooks)]
    if not soft_one_way:
        soft = soft[soft.two]
    base = ["season", "game_date"] + KEY5 + ["book", "win_ts"]
    so = soft[soft.op.notna()][base + ["op", "fo_m"]].rename(columns={"op": "price", "fo_m": "soft_fair"}).assign(side="over")
    su = soft[soft.up.notna()][base + ["up", "fu_m"]].rename(columns={"up": "price", "fu_m": "soft_fair"}).assign(side="under")
    sl = pd.concat([so, su], ignore_index=True)
    sl["imp"] = imp(sl.price)
    diag = {"soft_quotes": int(len(soft))}
    if ref == "consensus":
        oth = two[KEY5 + ["book", fo, fu]].rename(columns={"book": "obook", fo: "fo", fu: "fu"})
        softq = soft[KEY5 + ["book"]].drop_duplicates()
        mm = softq.merge(oth, on=KEY5)
        mm = mm[mm.obook != mm.book]
        agg = mm.groupby(KEY5 + ["book"]).agg(fo=("fo", "median"), fu=("fu", "median"),
                                              n_oth=("fo", "size")).reset_index()
        agg = agg[agg.n_oth >= 2]
        c = sl.merge(agg, on=KEY5 + ["book"])
        diag["compared_quotes"] = int(len(agg))
        diag["ref_any_line"] = np.nan
    else:
        r = two[two.book == ref][KEY5 + [fo, fu]].rename(columns={fo: "fo", fu: "fu"})
        c = sl.merge(r, on=KEY5)
        k4 = ["game_id", "nn", "market", "win"]
        anyl = soft[k4 + ["book", "line"]].merge(r[k4].drop_duplicates(), on=k4)
        diag["ref_any_line"] = int(len(anyl))
        diag["compared_quotes"] = int(len(soft[KEY5 + ["book"]].merge(r[KEY5], on=KEY5)))
        diag["ref_two_way_quotes"] = int(len(r))
    c["fair"] = np.where(c.side == "over", c.fo, c.fu)
    c["edge_vs_price"] = c.fair - c.imp                 # the PRIMARY definition, always kept
    if edge_def == "vig":
        c["edge"] = c.edge_vs_price
    else:                                               # S4, POST-HOC: the repo's find_bets definition
        c["edge"] = c.fair - c.soft_fair
        c = c[c.edge.notna()]
    return c, diag


def lock(c, cut):
    x = c[c.edge >= cut - 1e-12].copy()
    x["prio"] = x.book.map(PRIO)
    x["s"] = (x.side != "over").astype(int)
    x = x.sort_values(KEY3 + ["win", "edge", "prio", "s"], ascending=[True, True, True, True, False, True, True])
    return x.drop_duplicates(KEY3, keep="first").drop(columns=["prio", "s"])


def grade(b, actuals, null_is_no_action=False):
    b = b.merge(actuals, on=KEY3, how="left")
    st = b.status.copy()
    if null_is_no_action:
        st = st.where(~(b.nan0.fillna(False) & st.isin(["matched", "matched_fallback"])), "null_stat")
    b["gstatus"] = st
    graded = st.isin(["matched", "matched_fallback"])
    over = b.actual > b.line
    under = b.actual < b.line
    won = np.where(b.side == "over", over, under)
    push = b.actual == b.line
    risk, win = stake(b.price)
    b["result"] = np.where(~graded, "NA", np.where(push, "P", np.where(won, "W", "L")))
    b["risk"] = np.where(graded, risk, 0.0)
    b["units"] = np.where(b.result == "W", win, np.where(b.result == "L", -risk, 0.0))
    return b


def close_value(b, q, ref, devig="m"):
    fo, fu = f"fo_{devig}", f"fu_{devig}"
    two = q[q.two]
    b = b.reset_index(drop=True).copy()
    b["bet_id"] = np.arange(len(b))
    if ref != "consensus":
        r = two[two.book == ref]
        last = r.groupby(KEY3).win.max().rename("w_last").reset_index()
        b = b.merge(last, on=KEY3, how="left")
        rl = r[KEY3 + ["win", "line", fo, fu]].rename(
            columns={"win": "w_last", "line": "cl_line", fo: "cfo", fu: "cfu"})
        b = b.merge(rl, on=KEY3 + ["w_last"], how="left")
        assert b.bet_id.is_unique
        same = b.cl_line == b.line
        b["cl_fair"] = np.where(same, np.where(b.side == "over", b.cfo, b.cfu), np.nan)
        mv = b.cl_line - b.line
        b["moved_fav"] = (~same) & b.cl_line.notna() & np.where(b.side == "over", mv > 0, mv < 0)
        b["moved_unfav"] = (~same) & b.cl_line.notna() & np.where(b.side == "over", mv < 0, mv > 0)
    else:
        last = two.groupby(KEY3).win.max().rename("w_last").reset_index()
        b = b.merge(last, on=KEY3, how="left")
        oth = two[KEY3 + ["win", "line", "book", fo, fu]].rename(
            columns={"win": "w_last", "book": "obook", fo: "cfo", fu: "cfu"})
        mm = b[KEY3 + ["w_last", "line", "book", "bet_id"]].merge(oth, on=KEY3 + ["w_last", "line"])
        mm = mm[mm.obook != mm.book]
        agg = mm.groupby("bet_id").agg(cfo=("cfo", "median"), cfu=("cfu", "median"), n=("cfo", "size"))
        agg = agg[agg.n >= 2]
        b = b.merge(agg[["cfo", "cfu"]], left_on="bet_id", right_index=True, how="left")
        b["cl_fair"] = np.where(b.side == "over", b.cfo, b.cfu)
        b["moved_fav"] = False
        b["moved_unfav"] = False
    b["later"] = b.w_last > b.win
    b["close_edge"] = b.cl_fair - b.imp
    return b


def boot_ci(g):
    """g: graded bets. Resample game dates."""
    if len(g) == 0:
        return np.nan, np.nan
    d = g.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    n = len(d)
    if n < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, (N_BOOT, n))
    u = d.u.values[idx].sum(axis=1)
    r = d.r.values[idx].sum(axis=1)
    roi = u / r
    return float(np.percentile(roi, 2.5)), float(np.percentile(roi, 97.5))


def summarise(b, mid_by_season, halves="date"):
    g = b[b.result != "NA"]
    out = {
        "locked": len(b),
        "no_action_dnp": int((b.gstatus == "dnp").sum()),
        "dropped_unmatched": int(b.gstatus.isin(["unmatched", "ambiguous", "game_not_in_log"]).sum()),
        "null_stat_no_action": int((b.gstatus == "null_stat").sum()),
        "bets": len(g),
        "W": int((g.result == "W").sum()), "L": int((g.result == "L").sum()), "P": int((g.result == "P").sum()),
        "units": float(g.units.sum()), "risked": float(g.risk.sum()),
        "roi": float(g.units.sum() / g.risk.sum()) if len(g) else np.nan,
    }
    out["ci_lo"], out["ci_hi"] = boot_ci(g)
    if halves == "date":
        h1 = g[g.game_date <= g.season.map(mid_by_season)]
        h2 = g[g.game_date > g.season.map(mid_by_season)]
    else:
        h1, h2 = g[g.season == 2025], g[g.season == 2026]
    for nm, h in (("h1", h1), ("h2", h2)):
        out[f"{nm}_bets"] = len(h)
        out[f"{nm}_units"] = float(h.units.sum())
        out[f"{nm}_roi"] = float(h.units.sum() / h.risk.sum()) if len(h) else np.nan
    if len(g):
        out.update(price_min=float(g.price.min()), price_med=median_american(g.price),
                   price_max=float(g.price.max()), share_shorter_200=float((g.price < -200).mean()),
                   mean_edge=float(g.edge.mean()), max_edge=float(g.edge.max()),
                   mean_edge_vs_price=float(g.edge_vs_price.mean()),
                   over_share=float((g.side == "over").mean()), n_null_as_zero=int(g.nan0.sum()),
                   game_dates=int(g.game_date.nunique()), games=int(g.game_id.nunique()))
        lt_ = g[g.later & g.close_edge.notna()]
        out.update(clv_n=len(lt_),
                   clv_mean=float(lt_.close_edge.mean()) if len(lt_) else np.nan,
                   clv_entry_edge_same_bets=float(lt_.edge_vs_price.mean()) if len(lt_) else np.nan,
                   clv_share_pos=float((lt_.close_edge > 0).mean()) if len(lt_) else np.nan,
                   no_later_window=int((~g.later.fillna(False)).sum()),
                   later_line_gone=int((g.later.fillna(False) & g.close_edge.isna()).sum()),
                   moved_fav=int((g.later.fillna(False) & g.moved_fav).sum()),
                   moved_unfav=int((g.later.fillna(False) & g.moved_unfav).sum()))
    return out


def breakdown(b, col):
    g = b[b.result != "NA"]
    if not len(g):
        return []
    t = g.groupby(col).agg(bets=("units", "size"), W=("result", lambda s: (s == "W").sum()),
                           L=("result", lambda s: (s == "L").sum()), units=("units", "sum"),
                           risked=("risk", "sum")).reset_index()
    t["roi"] = t.units / t.risked
    return t.rename(columns={col: "level"}).to_dict("records")


# ───────────────────────────── main ─────────────────────────────
def main():
    np.seterr(divide="ignore")      # np.where evaluates both branches of imp(); the unused one divides by 0 at -100
    p, g, lt = load()
    q = build_quotes(p, list(MARKET_STAT))
    actuals, ghow = build_actuals(q, g, lt)

    # season midpoints
    mid = {}
    for s, d in q.groupby("season"):
        dates = np.sort(d.game_date.unique())
        mid[int(s)] = dates[(len(dates) - 1) // 2]
        print(f"season {s}: {len(dates)} game dates {dates[0]} .. {dates[-1]}, first half = on or before {mid[int(s)]}")

    # ── inventory (no results) ──
    inv = q.groupby(["season", "book"]).agg(quotes=("two", "size"), two_way=("two", "sum"),
                                            games=("game_id", "nunique")).reset_index()
    inv2 = q[q.two].groupby(["season", "book"]).agg(games_two_way=("game_id", "nunique"),
                                                    props_two_way=("nn", lambda s: 0)).reset_index()
    pt = q[q.two].drop_duplicates(["season", "book"] + KEY3).groupby(["season", "book"]).size().rename("props_two_way")
    inv = inv.merge(inv2[["season", "book", "games_two_way"]], on=["season", "book"], how="left") \
             .merge(pt.reset_index(), on=["season", "book"], how="left").fillna(0)
    inv["bettable"] = inv.book.isin(BETTABLE)
    inv.to_csv(OUT + r"\inv_two_way.csv", index=False)
    print("\nINVENTORY: pre-game main-market quotes per season/book (a quote = book x window x line)\n", inv.to_string())
    w = q.drop_duplicates(["game_id", "win"]).groupby(["season", "game_id"]).size().groupby("season").value_counts().unstack(fill_value=0)
    print("\nwindows per game (pre-kick):\n", w.to_string())
    w.to_csv(OUT + r"\inv_windows_per_game.csv")
    lead = q.drop_duplicates(["game_id", "win"]).merge(g[["game_id", "ct"]], on="game_id")
    lead["lead_h"] = (lead.ct - lead.win_ts).dt.total_seconds() / 3600
    print("\nlead hours of each (game, window):\n", lead.groupby("season").lead_h.describe().round(2).to_string())
    lead.groupby("season").lead_h.describe().round(2).to_csv(OUT + r"\inv_lead_hours.csv")
    et = lead.win_ts.dt.tz_convert("America/New_York")
    lead["et_hm"] = et.dt.strftime("%H:%M")
    print("\n(game, window) count by ET pull time, 2026:\n", lead[lead.season == 2026].et_hm.value_counts().sort_index().to_string())
    lead[lead.season == 2026].et_hm.value_counts().sort_index().to_csv(OUT + r"\inv_pull_times_2026.csv")

    a2 = actuals.merge(q[["game_id", "season"]].drop_duplicates(), on="game_id")
    ms = a2.groupby(["season", "status"]).size().unstack(fill_value=0)
    ms["total"] = ms.sum(axis=1)
    print("\nPROPOSITIONS by match status:\n", ms.to_string())
    ms.to_csv(OUT + r"\inv_match_status.csv")
    gh = pd.Series(ghow).rename("how").reset_index().rename(columns={"index": "game_id"}) \
        .merge(q[["game_id", "season"]].drop_duplicates(), on="game_id")
    ghs = gh.groupby(["season", "how"]).size().unstack(fill_value=0)
    print("\nprop game -> log game:\n", ghs.to_string())
    ghs.to_csv(OUT + r"\inv_game_match.csv")
    fb = actuals[actuals.status == "matched_fallback"].merge(
        q[KEY3 + ["player_name"]].drop_duplicates(KEY3), on=KEY3)[["player_name", "log_name"]].drop_duplicates()
    print("\nfallback name matches (odds name -> log name):\n", fb.to_string())
    fb.to_csv(OUT + r"\inv_fallback_names.csv", index=False)
    nz = a2[a2.status.isin(["matched", "matched_fallback"])].groupby(["season", "market"]).nan0.agg(n="size", null_as_zero="sum")
    print("\nmatched propositions whose stat column is NULL (graded as 0 in PRIMARY):\n", nz.to_string())
    nz.to_csv(OUT + r"\inv_null_stat.csv")

    # grading sanity: reference fair probability vs realised over rate
    san = []
    for ref in ("pinnacle", "bovada", "betonlineag", "fanduel", "hardrockbet"):
        r = q[(q.book == ref) & q.two].sort_values("win").drop_duplicates(KEY3, keep="first") \
            .merge(actuals, on=KEY3)
        r = r[r.status.isin(["matched", "matched_fallback"]) & (r.actual != r.line)]
        r["over"] = (r.actual > r.line).astype(int)
        r["bin"] = pd.cut(r.fo_m, [0, 0.4, 0.47, 0.53, 0.6, 1.0])
        t = r.groupby(["season", "bin"], observed=True).agg(n=("over", "size"), fair_over=("fo_m", "mean"),
                                                            realised_over=("over", "mean")).reset_index()
        t.insert(0, "ref", ref)
        san.append(t)
    san = pd.concat(san)
    print("\nGRADING SANITY: de-vigged over probability (first quote per proposition) vs realised over rate\n", san.round(3).to_string())
    san.to_csv(OUT + r"\sanity_calibration.csv", index=False)

    # blind baseline: first window with a bettable two-way quote, first book in bettable order
    sb = q[q.book.isin(BETTABLE) & q.two].copy()
    sb["prio"] = sb.book.map(PRIO)
    sb = sb.sort_values(KEY3 + ["win", "prio"]).drop_duplicates(KEY3, keep="first")
    base_rows = []
    for side, pc in (("over", "op"), ("under", "up")):
        x = sb.assign(side=side, price=sb[pc], edge=0.0)
        x["imp"] = imp(x.price)
        gb = grade(x, actuals)
        gg = gb[gb.result != "NA"]
        for s, h in gg.groupby("season"):
            lo, hi = boot_ci(h)
            base_rows.append(dict(season=s, side=side, bets=len(h), W=int((h.result == "W").sum()),
                                  L=int((h.result == "L").sum()), P=int((h.result == "P").sum()),
                                  units=h.units.sum(), risked=h.risk.sum(), roi=h.units.sum() / h.risk.sum(),
                                  ci_lo=lo, ci_hi=hi))
    base = pd.DataFrame(base_rows)
    print("\nBLIND BASELINE (every proposition, first bettable two-way quote):\n", base.round(4).to_string())
    base.to_csv(OUT + r"\baseline_blind.csv", index=False)

    # ── the grid ──
    rows, brk, diags, allbets = [], [], [], []
    n_cells = 0

    def run(variant, ref, devig="m", soft_one_way=False, null_na=False, seasons=(2025, 2026), pooled=False,
            edge_def="vig"):
        nonlocal n_cells
        c_all, _ = build_candidates(q, ref, devig, soft_one_way, edge_def)
        for s in seasons:
            qs = q[q.season == s]
            c, diag = build_candidates(qs, ref, devig, soft_one_way, edge_def)
            diag.update(variant=variant, season=s, ref=ref, candidate_sides=len(c),
                        props_compared=int(c.drop_duplicates(KEY3).shape[0]),
                        games_compared=int(c.game_id.nunique()))
            diags.append(diag)
            for cut in CUTS:
                b = lock(c, cut)
                b = grade(b, actuals, null_na)
                b = close_value(b, qs, ref, devig)
                r = summarise(b, mid)
                r.update(variant=variant, season=str(s), ref=ref, cut=cut)
                rows.append(r)
                n_cells += 1
                for col in ("market", "book", "side"):
                    for d in breakdown(b, col):
                        d.update(variant=variant, season=str(s), ref=ref, cut=cut, by=col)
                        brk.append(d)
                allbets.append(b.assign(variant=variant, ref=ref, cut=cut))
        if pooled:
            for cut in CUTS:
                b = lock(c_all, cut)
                b = grade(b, actuals, null_na)
                b = close_value(b, q, ref, devig)
                r = summarise(b, mid, halves="season")
                r.update(variant=variant, season="2025+2026", ref=ref, cut=cut)
                rows.append(r)
                n_cells += 1

    for ref in NAMED_REFS:
        run("PRIMARY", ref, pooled=True)
    for ref in PLACEBO_REFS:
        run("PRIMARY", ref, pooled=True)
    for ref in NAMED_REFS:
        run("S1_power_devig", ref, devig="p")
    for ref in NAMED_REFS:
        run("S2_null_stat_no_action", ref, null_na=True)
    for ref in NAMED_REFS:
        run("S3_one_way_soft_allowed", ref, soft_one_way=True)
    # POST-HOC (see the docstring): the repo's own edge definition
    for ref in NAMED_REFS + PLACEBO_REFS:
        run("S4_POSTHOC_repo_edge_def", ref, pooled=True, edge_def="devig")

    res = pd.DataFrame(rows)
    front = ["variant", "season", "ref", "cut"]
    res = res[front + [c for c in res.columns if c not in front]]
    res.to_csv(OUT + r"\grid.csv", index=False)
    pd.DataFrame(brk).to_csv(OUT + r"\breakdowns.csv", index=False)
    pd.DataFrame(diags).to_csv(OUT + r"\diagnostics.csv", index=False)
    ab = pd.concat(allbets, ignore_index=True)
    keep = ["variant", "ref", "cut", "season", "game_date", "game_id", "nn", "market", "book", "side", "line",
            "price", "fair", "edge", "edge_vs_price", "win", "win_ts", "status", "gstatus", "actual", "nan0",
            "result", "risk", "units", "later", "close_edge", "moved_fav", "moved_unfav"]
    ab[keep].to_parquet(OUT + r"\bets.parquet", index=False)

    show = ["season", "ref", "cut", "bets", "W", "L", "P", "units", "risked", "roi", "ci_lo", "ci_hi",
            "h1_bets", "h1_roi", "h2_bets", "h2_roi", "clv_n", "clv_mean", "price_min", "price_med",
            "price_max", "share_shorter_200"]
    for v in res.variant.unique():
        print(f"\n===== {v} =====")
        print(res[res.variant == v][show].round(4).to_string(index=False))
    print("\nDIAGNOSTICS\n", pd.DataFrame(diags).to_string(index=False))
    print(f"\ncells run (season x reference x cut, all variants, incl. pooled): {n_cells}")
    print("cells by variant:", res.groupby("variant").size().to_dict())
    print("cells with at least one graded bet, by variant:", res[res.bets > 0].groupby("variant").size().to_dict())
    print("variants: PRIMARY, S1_power_devig, S2_null_stat_no_action, S3_one_way_soft_allowed (pre-declared) "
          "+ S4_POSTHOC_repo_edge_def (added after the primary grid was seen) = 5")


if __name__ == "__main__":
    main()
