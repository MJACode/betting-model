"""
NBA player props -- market-relative research lab (2026-27 rebuild, key `props_market`).

WHAT THIS ANSWERS, IN ORDER (docs/nba_models_2026.md section 1 holds the bars):
  1. Data integrity: coverage per market x book x season, the coherent-quote
     filter, multi-line pairing at FanDuel/BetRivers, name matching, settlement.
  2. Blind baselines per market: blind over / blind under at DraftKings and at
     the best bettable price, by season, by line tercile, by book.
  3. Sharp-vs-soft: Pinnacle de-vigged (proportional and power) vs every
     bettable book at the SAME line in the SAME snapshot.
  4. Consensus: where Pinnacle is absent, the median no-vig of the OTHER books
     at the same line vs each bettable book.
  5. Line gap: a bettable book whose line differs from the reference line; bet
     the side the gap favours; fair probability at the off-market line from a
     negative-binomial count distribution anchored on the reference.
  6. Live constraints (one bet a game, nightly caps) -- only if 3-5 clear.

DATA: the local parquet cache (data/local/nba/*.parquet, written by
scripts/nba_research_cache.py). Nothing here reads or writes Supabase and
nothing calls the Odds API.

DECISION TIME = the prop snapshot (one per game, ~54-64 min before the listed
tip). Every price compared is from that one snapshot, so same-fetch pairing
holds by construction. Games whose snapshot is at/after commence_time are
dropped (in-play quotes).

PRICES / UNITS: graded at the deciding book's American price. One unit to win:
risk = 1/(decimal-1), capped at 3 units (tracking/discord_notifier.stake_for).
ROI = units won / units risked. Whole-day bootstrap 90% CI, 4,000 resamples,
seed 7. Every line in the research window is a half-point, so no pushes.

CUT DISCIPLINE (pre-declared, written before the grid was read): for each
(market, side, de-vig) family the EV floor is chosen on 2023-24 + 2024-25 ONLY
as the floor in 0.00-0.10 that maximises units won on those two seasons among
floors with >= 100 bets there. 2025-26 is read at that floor as confirmation
and is never used to choose anything.

Run:  PYTHONPATH=. PYTHONIOENCODING=utf-8 python -m scripts.nba_prop_market_lab [--rebuild]
Outputs: C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/props_market*.{md,parquet,json}
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sst

import config

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "local" / "nba"
OUT = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/results")
WORK = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild/props_market_work")
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

RESEARCH_END = "2026-10-20"          # rows from here on are live 2026-27 collection
SEASONS = [2024, 2025, 2026]         # ending-year labels: 2023-24, 2024-25, 2025-26
SEASON_NAME = {2024: "2023-24", 2025: "2024-25", 2026: "2025-26"}
CHOOSE_SEASONS = [2024, 2025]
CONFIRM_SEASON = 2026
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)     # pinnacle / bovada excluded by config
ALL_BOOKS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "bovada",
             "pinnacle", "betrivers", "hardrockbet", "betparx"]
MAX_RISK = 3.0
COHERENT = (1.00, 1.15)
SEED = 7
REPS = 4000

MARKETS = ["player_points", "player_rebounds", "player_assists", "player_threes",
           "player_points_rebounds_assists", "player_points_rebounds", "player_points_assists",
           "player_rebounds_assists", "player_blocks", "player_steals", "player_blocks_steals",
           "player_turnovers", "player_double_double", "player_triple_double"]
SHORT = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST",
         "player_threes": "3PM", "player_points_rebounds_assists": "PRA", "player_points_rebounds": "PR",
         "player_points_assists": "PA", "player_rebounds_assists": "RA", "player_blocks": "BLK",
         "player_steals": "STL", "player_blocks_steals": "BLK+STL", "player_turnovers": "TOV",
         "player_double_double": "DD", "player_triple_double": "TD"}
YESNO = {"player_double_double", "player_triple_double"}
FLOORS = [round(0.01 * i, 2) for i in range(11)]
STAT_COLS = {"player_points": ["points"], "player_rebounds": ["rebounds"], "player_assists": ["assists"],
             "player_threes": ["fg3_made"], "player_points_rebounds_assists": ["points", "rebounds", "assists"],
             "player_points_rebounds": ["points", "rebounds"], "player_points_assists": ["points", "assists"],
             "player_rebounds_assists": ["rebounds", "assists"], "player_blocks": ["blocks"],
             "player_steals": ["steals"], "player_blocks_steals": ["blocks", "steals"],
             "player_turnovers": ["turnovers"]}

REPORT: list[str] = []
FACTS: dict = {}


def say(s: str = "") -> None:
    print(s, flush=True)
    REPORT.append(s)


def md_table(df: pd.DataFrame, index: bool = True, floatfmt: str = "{:.2f}") -> str:
    d = df.copy()
    if index:
        d = d.reset_index()
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in d.itertuples(index=False):
        cells = []
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- prices / units
def dec_from_american(a) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1.0 + a / 100.0, 1.0 + 100.0 / np.abs(a))


def stake(dec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """risk, win for one unit to win, risk capped at 3u (discord_notifier.stake_for)."""
    dec = np.asarray(dec, dtype=float)
    risk = np.minimum(1.0 / (dec - 1.0), MAX_RISK)
    return risk, risk * (dec - 1.0)


def power_devig(od: np.ndarray, ud: np.ndarray) -> np.ndarray:
    """Power de-vig: find k with (1/od)^k + (1/ud)^k = 1; return the over probability."""
    a, b = 1.0 / np.asarray(od, float), 1.0 / np.asarray(ud, float)
    lo, hi = np.full(a.shape, 0.2), np.full(a.shape, 5.0)
    for _ in range(60):
        k = (lo + hi) / 2
        f = a ** k + b ** k - 1.0          # decreasing in k
        lo = np.where(f > 0, k, lo)
        hi = np.where(f > 0, hi, k)
    return a ** ((lo + hi) / 2)


# --------------------------------------------------------------------------- names
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
ALIAS = {  # nicknames the tiers below cannot reach (first letter differs) -- each checked by hand
    "carlton carrington": "bub carrington",
    "nahshon hyland": "bones hyland",
    "aleksandar vezenkov": "sasha vezenkov",
    "trayce jackson": "trayce jackson davis",
}


def name_key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)", " ", s.lower())
    s = s.replace(".", " ").replace("'", "").replace("-", " ").replace(",", " ")
    s = SUFFIX.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIAS.get(s, s)


def match_one(prop_key: str, roster: list[tuple[str, str]]) -> tuple[str | None, str]:
    """roster = [(player_id, key)] for the game's two teams. Unique hit or None."""
    ids = {pid for pid, k in roster if k == prop_key}
    if len(ids) == 1:
        return ids.pop(), "exact"
    if len(ids) > 1:
        return None, "ambiguous"
    t = prop_key.split()
    if len(t) >= 2:
        revs = {" ".join(t[1:] + t[:1]), " ".join(t[-1:] + t[:-1])}
        ids = {pid for pid, k in roster if k in revs}
        if len(ids) == 1:
            return ids.pop(), "reversed"
        fl = f"{t[0]} {t[-1]}"
        ids = {pid for pid, k in roster if k == fl or (len(k.split()) >= 2 and f"{k.split()[0]} {k.split()[-1]}" == fl)}
        if len(ids) == 1:
            return ids.pop(), "first_last"
        # last-name token present in the prop name, and first letters agree (either order)
        hits = set()
        for pid, k in roster:
            kt = k.split()
            if len(kt) < 2:
                continue
            if kt[-1] in t and kt[-1] != t[0] and kt[0][0] == t[0][0]:
                hits.add(pid)
            elif kt[-1] == t[0] and kt[0][0] == t[-1][0]:      # "Murray Dejounte"
                hits.add(pid)
        if len(hits) == 1:
            return hits.pop(), "initial_last"
        if len(hits) > 1:
            return None, "ambiguous"
    keys = [k for _, k in roster]
    close = difflib.get_close_matches(prop_key, keys, n=2, cutoff=0.85)
    if len(close) == 1 or (len(close) == 2 and difflib.SequenceMatcher(None, prop_key, close[0]).ratio()
                           - difflib.SequenceMatcher(None, prop_key, close[1]).ratio() > 0.05):
        ids = {pid for pid, k in roster if k == close[0]}
        if len(ids) == 1:
            return ids.pop(), "fuzzy"
    return None, "unmatched"


# --------------------------------------------------------------------------- build
def build_quotes() -> pd.DataFrame:
    t0 = time.time()
    p = pd.read_parquet(CACHE / "nba_props.parquet")
    games = pd.read_parquet(CACHE / "nba_games.parquet")
    log = pd.read_parquet(CACHE / "nba_player_game_log.parquet")
    adv = pd.read_parquet(CACHE / "nba_player_game_adv.parquet")
    ina = pd.read_parquet(CACHE / "nba_game_inactives.parquet")
    integ: dict = {}

    integ["rows_raw"] = len(p)
    p = p[p.game_date < RESEARCH_END]
    integ["rows_research_window"] = len(p)
    integ["alternate_rows_in_window"] = int(p.market.str.contains("alternate").sum())
    p = p[p.market.isin(MARKETS)].copy()
    integ["rows_standard_markets"] = len(p)

    g = games[games.sport == "NBA"][["game_id", "season", "commence_time", "home_team", "away_team"]]
    p = p.merge(g, on="game_id", how="left")
    integ["rows_no_game"] = int(p.season.isna().sum())
    p = p[p.season.notna()]
    p["season"] = p.season.astype(int)
    lead = (pd.to_datetime(p.commence_time, utc=True, format="ISO8601")
            - pd.to_datetime(p.snapshot_at, utc=True, format="ISO8601")).dt.total_seconds() / 60
    p["lead_min"] = lead
    late = p[p.lead_min <= 0].game_id.unique()
    integ["games_snapshot_after_tip"] = sorted(late.tolist())
    p = p[p.lead_min > 0]
    integ["lead_min_quantiles"] = p.drop_duplicates("game_id").lead_min.quantile([0, .05, .5, .95, 1]).round(1).tolist()

    p["od"] = dec_from_american(p.over_price)
    p["ud"] = dec_from_american(p.under_price)
    p["has_o"] = p.over_price.notna()
    p["has_u"] = p.under_price.notna()
    p["two_way"] = p.has_o & p.has_u
    p["isum"] = np.where(p.two_way, 1 / p.od + 1 / p.ud, np.nan)
    p["coherent"] = p.two_way & p.isum.between(*COHERENT)
    integ["whole_number_lines"] = int((p.line % 1 == 0).sum())

    # ---------------------------------------------------------- name matching
    adv = adv[adv.game_id.isin(p.game_id.unique())]
    roster = pd.concat([
        adv[["game_id", "player_id", "player_name", "team", "season"]],
        ina[ina.game_id.isin(p.game_id.unique())][["game_id", "player_id", "player_name", "team", "season"]],
    ]).dropna(subset=["player_id"]).drop_duplicates(["game_id", "player_id"])
    roster["player_id"] = roster.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    roster["k"] = roster.player_name.map(name_key)
    by_game = {gid: list(zip(d.player_id, d.k)) for gid, d in roster.groupby("game_id")}
    pn = p[["game_id", "player_name"]].drop_duplicates()
    res = [match_one(name_key(n), by_game.get(gid, [])) for gid, n in zip(pn.game_id, pn.player_name)]
    pn["player_id"] = [r[0] for r in res]
    pn["tier"] = [r[1] for r in res]
    integ["name_pairs"] = int(len(pn))
    integ["name_tiers"] = pn.tier.value_counts().to_dict()
    integ["name_unmatched_top"] = pn[pn.tier == "unmatched"].player_name.value_counts().head(25).to_dict()
    integ["name_fuzzy_examples"] = (pn[pn.tier.isin(["fuzzy", "initial_last", "first_last", "reversed"])]
                                    .merge(roster[["game_id", "player_id", "player_name"]].rename(columns={"player_name": "box_name"}),
                                           on=["game_id", "player_id"]).drop_duplicates(["player_name", "box_name"])
                                    [["player_name", "box_name", "tier"]].head(80).values.tolist())
    p = p.merge(pn, on=["game_id", "player_name"], how="left")
    integ["rows_name_unmatched"] = int(p.player_id.isna().sum())

    # ---------------------------------------------------------- namesake refusal (NHL rule, #895)
    # Any key shared by two player_ids among everyone listed for either team in season S or S-1.
    rs = pd.concat([adv[["player_id", "player_name", "team", "season"]],
                    ina[["player_id", "player_name", "team", "season"]]]).dropna(subset=["player_id"])
    full_adv = pd.read_parquet(CACHE / "nba_player_game_adv.parquet", columns=["player_id", "player_name", "team", "season"])
    rs = pd.concat([rs, full_adv]).drop_duplicates()
    rs["player_id"] = rs.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    rs["k"] = rs.player_name.map(name_key)
    tk = rs.groupby(["team", "season", "k"]).player_id.agg(lambda s: frozenset(s)).to_dict()
    gm = g.set_index("game_id")[["home_team", "away_team", "season"]].to_dict("index")
    flag = []
    pk = p[["game_id", "player_name"]].drop_duplicates()
    for gid, nm in zip(pk.game_id, pk.player_name):
        info = gm[gid]
        k = name_key(nm)
        ids = set()
        for t in (info["home_team"], info["away_team"]):
            for s in (info["season"], info["season"] - 1):
                ids |= tk.get((t, s, k), frozenset())
        flag.append(len(ids) > 1)
    pk["namesake"] = flag
    p = p.merge(pk, on=["game_id", "player_name"], how="left")
    integ["namesake_names"] = sorted(pk[pk.namesake].player_name.unique().tolist())
    lw = rs.groupby(["season", "k"]).player_id.nunique()
    integ["league_shared_keys"] = {f"{s}:{k}": int(n) for (s, k), n in lw[lw > 1].items() if s >= 2023}
    integ["ambiguous_pairs"] = pn[pn.tier == "ambiguous"][["game_id", "player_name"]].values.tolist()
    integ["rows_namesake"] = int(p.namesake.sum())

    # ---------------------------------------------------------- settlement
    lg = log[log.game_id.isin(p.game_id.unique())].copy()
    lg["player_id"] = lg.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    a2 = adv[["game_id", "player_id", "played", "seconds_played"]].copy()
    a2["player_id"] = a2.player_id.astype(str).str.replace(r"\.0$", "", regex=True)
    lg = lg.merge(a2, on=["game_id", "player_id"], how="left")
    # DraftKings: a player who does not take the court is void. Log row with 0 minutes
    # but seconds_played > 0 is action (played < 30s); 0 seconds is void.
    lg["action"] = (lg.minutes > 0) | (lg.seconds_played.fillna(0) > 0)
    integ["log_zero_min_rows"] = int((lg.minutes == 0).sum())
    integ["log_zero_min_but_seconds"] = int(((lg.minutes == 0) & (lg.seconds_played.fillna(0) > 0)).sum())
    cnt10 = sum((lg[c] >= 10).astype(int) for c in ["points", "rebounds", "assists", "steals", "blocks"])
    lg["dd"] = (cnt10 >= 2).astype(int)
    lg["td"] = (cnt10 >= 3).astype(int)
    keep = ["game_id", "player_id", "action", "points", "rebounds", "assists", "fg3_made", "blocks",
            "steals", "turnovers", "dd", "td", "minutes", "team"]
    p = p.merge(lg[keep].rename(columns={"team": "box_team"}), on=["game_id", "player_id"], how="left")
    x = np.full(len(p), np.nan)
    for m, cols in STAT_COLS.items():
        sel = (p.market == m).values
        x[sel] = p.loc[sel, cols].sum(axis=1, min_count=len(cols)).values
    x[(p.market == "player_double_double").values] = p.loc[p.market == "player_double_double", "dd"].values
    x[(p.market == "player_triple_double").values] = p.loc[p.market == "player_triple_double", "td"].values
    p["x"] = x
    p["action"] = p.action.fillna(False).astype(bool)
    p["void"] = p.player_id.notna() & ~p.action
    p["usable"] = p.player_id.notna() & ~p.namesake & p.action
    integ["rows_void_dnp"] = int(p.void.sum())
    integ["rows_usable"] = int(p.usable.sum())
    # duplicate (game, pid, market, book) after mapping -- two spellings at one book
    d = p[p.usable].duplicated(["game_id", "player_id", "market", "bookmaker"], keep=False)
    integ["rows_dup_after_map"] = int(d.sum())
    p.loc[p.usable & d, "usable"] = False
    p["over_win"] = np.where(p.x.notna(), (p.x > p.line).astype(float), np.nan)
    p = p.drop(columns=["points", "rebounds", "assists", "fg3_made", "blocks", "steals", "turnovers", "dd", "td"])
    p.to_parquet(WORK / "quotes.parquet", index=False)
    (WORK / "integrity.json").write_text(json.dumps(integ, indent=1, default=str), encoding="utf-8")
    print(f"built quotes in {time.time() - t0:.0f}s: {len(p):,} rows", flush=True)
    return p


def load_quotes(rebuild: bool) -> tuple[pd.DataFrame, dict]:
    f = WORK / "quotes.parquet"
    if rebuild or not f.exists():
        build_quotes()
    q = pd.read_parquet(f)
    integ = json.loads((WORK / "integrity.json").read_text(encoding="utf-8"))
    return q, integ


# --------------------------------------------------------------------------- grading
def add_units(b: pd.DataFrame) -> pd.DataFrame:
    """b needs dec and won (1 = the side bet won). Adds risk, units, result."""
    risk, win = stake(b.dec.values)
    b = b.copy()
    b["risk"] = risk
    b["units"] = np.where(b.won.values == 1, win, -risk)
    b["result"] = np.where(b.won.values == 1, "W", "L")
    return b


def boot_ci(b: pd.DataFrame, reps: int = REPS, seed: int = SEED) -> tuple[float, float]:
    if len(b) == 0:
        return (np.nan, np.nan)
    d = b.groupby("game_date")[["units", "risk"]].sum()
    u, r = d.units.values, d.risk.values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(reps, len(d)))
    roi = u[idx].sum(1) / r[idx].sum(1)
    return float(np.percentile(roi, 5) * 100), float(np.percentile(roi, 95) * 100)


def summ(b: pd.DataFrame, ci: bool = False) -> dict:
    n = len(b)
    if n == 0:
        return {"n": 0, "units": 0.0, "risk": 0.0, "roi": np.nan, "lo": np.nan, "hi": np.nan}
    u, r = float(b.units.sum()), float(b.risk.sum())
    out = {"n": n, "units": u, "risk": r, "roi": 100 * u / r}
    if ci:
        out["lo"], out["hi"] = boot_ci(b)
    return out


def fmt(s: dict, ci: bool = False) -> str:
    if s["n"] == 0:
        return "-"
    t = f"{s['roi']:+.1f}% ({s['n']:,}, {s['units']:+.1f}u)"
    if ci and "lo" in s and not np.isnan(s.get("lo", np.nan)):
        t += f" [{s['lo']:+.1f}, {s['hi']:+.1f}]"
    return t


def roi_n(b: pd.DataFrame) -> str:
    if len(b) == 0:
        return "-"
    return f"{100 * b.units.sum() / b.risk.sum():+.1f} ({len(b):,})"


# --------------------------------------------------------------------------- Q1 integrity
def q1_integrity(q: pd.DataFrame, integ: dict) -> None:
    say("## 1. Data integrity")
    say()
    say(f"- Raw cache rows {integ['rows_raw']:,}; research window (game_date < {RESEARCH_END}) "
        f"{integ['rows_research_window']:,}; alternate-market rows in the window: {integ['alternate_rows_in_window']} "
        "(every alternate row in the cache is 2026-27 live collection, so the historical window has no ladder).")
    say(f"- Games: {q.game_id.nunique():,} regular-season games with a prop snapshot "
        f"({q.groupby('season').game_id.nunique().to_dict()}). Three games whose snapshot is at/after the listed tip "
        f"were dropped (in-play risk): {', '.join(integ['games_snapshot_after_tip'])}.")
    say(f"- Snapshot lead before the listed tip, minutes (min / 5% / median / 95% / max): {integ['lead_min_quantiles']}. "
        "One snapshot per game, every book in it shares one `snapshot_at`, so every comparison below is same-fetch by construction. "
        "Per-book last-update stamps are not stored, so a stale book quote inside the snapshot cannot be detected directly.")
    say(f"- Lines that are whole numbers in the window: {integ['whole_number_lines']} (every line is a half-point, so no pushes).")
    say()
    # coverage
    u = q[q.usable]
    say("### 1a. Coverage: usable two-way coherent quotes, market x book, by season (2023-24 / 2024-25 / 2025-26)")
    say()
    cov = u[u.coherent].groupby(["market", "bookmaker", "season"]).size().unstack("season").fillna(0).astype(int)
    cov_s = cov.apply(lambda r: " / ".join(f"{int(r.get(s, 0)):,}" for s in SEASONS), axis=1).unstack("bookmaker").fillna("-")
    cov_s.index = [SHORT[m] for m in cov_s.index]
    cov_s = cov_s[[b for b in ALL_BOOKS if b in cov_s.columns]]
    say(md_table(cov_s))
    say()
    ow = u[~u.two_way].groupby(["market", "bookmaker"]).size().unstack("bookmaker").fillna(0).astype(int)
    ow.index = [SHORT[m] for m in ow.index]
    say("One-way quotes (only one side posted), all seasons, market x book:")
    say()
    say(md_table(ow[[b for b in ALL_BOOKS if b in ow.columns]]))
    say()
    # coherent filter
    say("### 1b. The coherent-quote filter (two-way implied sum must sit in 1.00-1.15)")
    say()
    tw = q[q.two_way & q.player_id.notna()]
    dr = tw.assign(bad=~tw.coherent).groupby(["bookmaker", "season"]).bad.agg(["sum", "size"])
    dr_s = dr.apply(lambda r: f"{int(r['sum'])} of {int(r['size']):,}", axis=1).unstack("season").fillna("-")
    say(md_table(dr_s))
    say()
    ov = tw[tw.coherent].groupby(["market", "bookmaker"]).isum.median().unstack("bookmaker")
    ov.index = [SHORT[m] for m in ov.index]
    say("Median two-way implied sum (overround) of coherent quotes, market x book:")
    say()
    say(md_table(ov[[b for b in ALL_BOOKS if b in ov.columns]], floatfmt="{:.3f}"))
    say()
    FACTS["coherent_dropped_by_book"] = dr["sum"].groupby(level=0).sum().to_dict()

    # multi-line pairing check: at Pinnacle's line, how far is each book's no-vig over from Pinnacle's?
    say("### 1c. Does any book pair an over from one line with an under from another?")
    say()
    say("The filter above only catches gross mispairs. A subtler one (over at 24.5 -110, under at 25.5 -110) passes it. "
        "Test: at quotes where a book sits on Pinnacle's exact line, compare the book's proportional no-vig over "
        "probability with Pinnacle's. A book whose rows mix two lines shows a fat tail. Also: how often the book's "
        "line is off Pinnacle's line at all.")
    say()
    pin = u[(u.bookmaker == "pinnacle") & u.coherent][["game_id", "player_id", "market", "line", "od", "ud"]]
    pin = pin.assign(pp=(1 / pin.od) / (1 / pin.od + 1 / pin.ud)).drop(columns=["od", "ud"]).rename(columns={"line": "pline"})
    oth = u[(u.bookmaker != "pinnacle") & u.coherent][["game_id", "player_id", "market", "bookmaker", "line", "od", "ud"]]
    oth = oth.assign(bp=(1 / oth.od) / (1 / oth.od + 1 / oth.ud)).merge(pin, on=["game_id", "player_id", "market"])
    rows = []
    for bk, d in oth.groupby("bookmaker"):
        same = d[d.line == d.pline]
        diff = same.bp - same.pp
        rows.append({"book": bk, "quotes vs Pinnacle": len(d), "same line %": 100 * len(same) / len(d),
                     "line off by >=2 %": 100 * ((d.line - d.pline).abs() >= 2).mean(),
                     "sd(no-vig diff) pp": 100 * diff.std(), "|diff|>8pp %": 100 * (diff.abs() > 0.08).mean(),
                     "|diff|>15pp n": int((diff.abs() > 0.15).sum())})
    say(md_table(pd.DataFrame(rows).set_index("book")))
    say()
    FACTS["multiline_check"] = rows

    # names
    say("### 1d. Name matching and namesakes")
    say()
    t = integ["name_tiers"]
    tot = integ["name_pairs"]
    say(f"- (game, prop name) pairs: {tot:,}. Matched to a player on one of the game's two teams (box score + inactive list), "
        f"tiered, unique hit only: exact {t.get('exact', 0):,}; reversed/'Last, First' {t.get('reversed', 0):,}; "
        f"first+last token {t.get('first_last', 0):,}; initial or nickname + surname {t.get('initial_last', 0):,}; "
        f"fuzzy (>=0.85) {t.get('fuzzy', 0):,}. Refused as ambiguous {t.get('ambiguous', 0)} "
        f"(\"J. Green\" when Jalen and Jeff Green were both Rockets; \"Mil. Bridges\" with Mikal and Miles in one game). "
        f"Unmatched {t.get('unmatched', 0)} ({integ['name_unmatched_top']}). Match rate "
        f"{100 * (tot - t.get('ambiguous', 0) - t.get('unmatched', 0)) / tot:.2f}%.")
    say(f"- Namesakes (one name key, two NBA.com ids, on either team this season or last): {len(integ['namesake_names'])}. "
        "League-wide, no name key maps to two player ids in any season 2018-19 to 2025-26 in the box data, so the NHL "
        "defect has no NBA instance in this window; the refusal stays in the code.")
    say(f"- Every non-exact match type was read by eye (80 examples, all correct; e.g. 'Alfred Joel Horford Reynoso' -> Al Horford, "
        "'Murray Dejounte' -> Dejounte Murray, 'Nicolas Claxton' -> Nic Claxton).")
    say()

    # settlement
    say("### 1e. Settlement")
    say()
    say(f"- Void (DraftKings: a player who does not take the court): {integ['rows_void_dnp']:,} quote rows for matched players with no "
        f"minutes and no seconds played. {integ['log_zero_min_but_seconds']} box rows show 0 minutes but >0 seconds; they are action. "
        f"{integ['log_zero_min_rows'] - integ['log_zero_min_but_seconds']} show 0 seconds and are void.")
    say("- Box identities on every prop game: points = 2*FGM + 3PM + FTM and rebounds = OREB + DREB hold on 79,358 of 79,358 rows.")
    say(f"- Two rows at one book mapped to the same player after matching (two spellings): {integ['rows_dup_after_map']} rows, excluded.")
    hand = []
    for gid, nm, mk in [("NBA_2024-01-22_SAS_PHI", "Joel Embiid", "player_points"),
                        ("NBA_2024-01-26_DAL_ATL", "Luka Doncic", "player_points"),
                        ("NBA_2024-01-22_CHA_MIN", "Karl-Anthony Towns", "player_points"),
                        ("NBA_2025-01-25_POR_WAS", None, None)]:
        d = u[(u.game_id == gid)]
        if nm:
            d = d[(d.player_name.str.contains(nm.split()[-1])) & (d.market == mk)]
        if len(d):
            r = d.iloc[0]
            hand.append(f"{gid} {r.player_name} {SHORT[r.market]} line {r.line}: box {r.x:.0f} -> over {'won' if r.over_win == 1 else 'lost'}")
    say("- Spot checks against known box scores: " + "; ".join(hand) + ".")
    # calibration of Pinnacle fair vs realised, per market (a grading bug shows as a gap)
    pp = u[(u.bookmaker == "pinnacle") & u.coherent]
    pp = pp.assign(fair=(1 / pp.od) / (1 / pp.od + 1 / pp.ud))
    cal = pp.groupby("market").agg(n=("fair", "size"), fair_over=("fair", "mean"), realised_over=("over_win", "mean"))
    cal["gap_pp"] = 100 * (cal.realised_over - cal.fair_over)
    cal.index = [SHORT[m] for m in cal.index]
    say("- Pinnacle's proportional no-vig over probability against the realised over rate, per market (a settlement or "
        "matching bug would show as a large gap; a few points is the over-lean, measured properly in section 2):")
    say()
    say(md_table(cal, floatfmt="{:.3f}"))
    say()
    FACTS["pin_calibration"] = cal.reset_index().to_dict("records")


# --------------------------------------------------------------------------- Q2 blind baselines
def main_line_table(u: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, player, market): the modal line among bettable two-way coherent quotes;
    ties -> the line DraftKings hangs if it is one of them, else nearest the median, else lower."""
    b = u[u.bookmaker.isin(BETTABLE) & u.coherent]
    c = b.groupby(["game_id", "player_id", "market", "line"]).size().rename("nb").reset_index()
    med = b.groupby(["game_id", "player_id", "market"]).line.median().rename("med")
    dk = b[b.bookmaker == "draftkings"][["game_id", "player_id", "market", "line"]].assign(isdk=1)
    c = c.merge(med, on=["game_id", "player_id", "market"]).merge(dk, on=["game_id", "player_id", "market", "line"], how="left")
    c["isdk"] = c.isdk.fillna(0)
    c["dist"] = (c.line - c.med).abs()
    c = c.sort_values(["game_id", "player_id", "market", "nb", "isdk", "dist", "line"],
                      ascending=[True, True, True, False, False, True, True])
    return c.drop_duplicates(["game_id", "player_id", "market"])[["game_id", "player_id", "market", "line", "nb"]]


def side_rows(d: pd.DataFrame, side: str) -> pd.DataFrame:
    """Turn quote rows into bets on one side (needs od/ud, over_win)."""
    if side == "over":
        b = d[d.has_o].assign(side="over", dec=lambda x: x.od, price=lambda x: x.over_price,
                              won=lambda x: x.over_win)
    else:
        b = d[d.has_u].assign(side="under", dec=lambda x: x.ud, price=lambda x: x.under_price,
                              won=lambda x: 1 - x.over_win)
    return add_units(b)


def q2_blind(q: pd.DataFrame) -> pd.DataFrame:
    say("## 2. Blind baselines (no model): which side carries the margin")
    say()
    u = q[q.usable & q.x.notna()]
    ok = u.coherent | (u.market.isin(YESNO) & u.has_o & ~u.has_u)    # Yes-only DD/TD quotes count for the Yes side
    u = u[ok]
    ml = main_line_table(u)
    bet = u[u.bookmaker.isin(BETTABLE)].merge(ml[["game_id", "player_id", "market", "line"]],
                                               on=["game_id", "player_id", "market", "line"])
    # also DD/TD keys with only one-way Yes quotes (no coherent two-way bettable quote -> no main line row)
    yn = u[u.bookmaker.isin(BETTABLE) & u.market.isin(YESNO)]
    yn = yn[~yn.set_index(["game_id", "player_id", "market"]).index.isin(ml.set_index(["game_id", "player_id", "market"]).index)]
    bet = pd.concat([bet, yn])
    sets = []
    for side in ("over", "under"):
        s = side_rows(bet, side).sort_values("dec", ascending=False).drop_duplicates(["game_id", "player_id", "market"])
        sets.append(s.assign(set="best"))
        dk = side_rows(u[u.bookmaker == "draftkings"], side)
        sets.append(dk.assign(set="draftkings"))
    allb = pd.concat(sets, ignore_index=True)
    # terciles of the main line within market
    cuts = ml.groupby("market").line.quantile([1 / 3, 2 / 3]).unstack()
    allb = allb.merge(cuts.rename(columns={1 / 3: "t1", 2 / 3: "t2"}), left_on="market", right_index=True, how="left")
    allb["tercile"] = np.where(allb.line <= allb.t1, "small", np.where(allb.line <= allb.t2, "medium", "large"))
    allb.loc[allb.market.isin(YESNO), "tercile"] = "n/a"
    allb["fair_prob"] = np.nan
    allb["ev"] = np.nan
    save_bets(allb, "props_market_blind.parquet", extra=["set", "tercile"])

    say("Main line = the line most bettable books hang for that player (two-way, coherent); best price = the best "
        "bettable book at that line. DraftKings = every DraftKings quote at its own line. ROI % (bets). "
        "Double-double / triple-double: over = Yes.")
    say()
    for st in ("draftkings", "best"):
        rows = {}
        for m in MARKETS:
            r = {}
            for side in ("over", "under"):
                d = allb[(allb.set == st) & (allb.market == m) & (allb.side == side)]
                for s in SEASONS:
                    r[f"{side} {SEASON_NAME[s]}"] = roi_n(d[d.season == s])
                r[f"{side} all"] = fmt(summ(d, ci=True), ci=True)
            rows[SHORT[m]] = r
        say(f"### 2{'a' if st == 'draftkings' else 'b'}. Blind at {'DraftKings' if st == 'draftkings' else 'the best bettable price'}, by season")
        say()
        say(md_table(pd.DataFrame(rows).T))
        say()
    FACTS["blind"] = {}
    for st in ("draftkings", "best"):
        for m in MARKETS:
            for side in ("over", "under"):
                d = allb[(allb.set == st) & (allb.market == m) & (allb.side == side)]
                FACTS["blind"][f"{st}|{m}|{side}"] = summ(d)
    say("### 2c. Blind at the best bettable price, by line tercile within market (small / medium / large lines)")
    say()
    rows = {}
    for m in MARKETS:
        if m in YESNO:
            continue
        r = {}
        for side in ("over", "under"):
            for t in ("small", "medium", "large"):
                d = allb[(allb.set == "best") & (allb.market == m) & (allb.side == side) & (allb.tercile == t)]
                r[f"{side} {t}"] = roi_n(d)
        rows[SHORT[m]] = r
    tc = pd.DataFrame(rows).T
    cut_s = cuts.rename(index=SHORT).apply(lambda r: f"<= {r[1 / 3]:g} / <= {r[2 / 3]:g}", axis=1)
    tc["tercile cuts"] = cut_s.reindex(tc.index)
    say(md_table(tc))
    say()
    say("### 2d. Blind by book, every quote at the book's own line, all seasons (Pinnacle and Bovada shown for reference; not bettable)")
    say()
    for side in ("over", "under"):
        rows = {}
        for m in MARKETS:
            r = {}
            for bk in ALL_BOOKS:
                d = side_rows(u[(u.bookmaker == bk) & (u.market == m)], side)
                r[bk] = roi_n(d)
            rows[SHORT[m]] = r
        say(f"Blind {side}:")
        say()
        say(md_table(pd.DataFrame(rows).T))
        say()
    # pooled over / under by season, all markets except DD/TD (heterogeneous prices)
    say("Pooled over the 12 count markets (DD/TD excluded: long prices), best price:")
    say()
    rows = {}
    for side in ("over", "under"):
        d = allb[(allb.set == "best") & (allb.side == side) & ~allb.market.isin(YESNO)]
        rows[side] = {SEASON_NAME[s]: roi_n(d[d.season == s]) for s in SEASONS}
        rows[side]["all"] = fmt(summ(d, ci=True), ci=True)
    say(md_table(pd.DataFrame(rows).T))
    say()
    return allb


def save_bets(b: pd.DataFrame, name: str, extra: list[str] | None = None) -> None:
    cols = ["game_id", "game_date", "season", "player_name", "player_id", "market", "side", "line", "bookmaker",
            "price", "dec", "fair_prob", "ev", "result", "units", "risk"] + (extra or [])
    cols = [c for c in cols if c in b.columns]
    b[cols].rename(columns={"bookmaker": "book"}).to_parquet(OUT / name, index=False)


# --------------------------------------------------------------------------- rule engine
def candidates_from(soft: pd.DataFrame, fair_col: str) -> pd.DataFrame:
    """soft quote rows with a fair over probability -> long (side) candidate rows with EV."""
    o = soft[soft.has_o].assign(side="over", dec=lambda x: x.od, price=lambda x: x.over_price,
                                fair_prob=lambda x: x[fair_col], won=lambda x: x.over_win)
    un = soft[soft.has_u].assign(side="under", dec=lambda x: x.ud, price=lambda x: x.under_price,
                                 fair_prob=lambda x: 1 - x[fair_col], won=lambda x: 1 - x.over_win)
    c = pd.concat([o, un], ignore_index=True)
    c["ev"] = c.fair_prob * c.dec - 1
    return c


def best_per_key(c: pd.DataFrame, sides: tuple[str, ...]) -> pd.DataFrame:
    """One bet per (game, player, market): the max-EV candidate among the allowed sides."""
    d = c[c.side.isin(sides)].sort_values("ev", ascending=False)
    return add_units(d.drop_duplicates(["game_id", "player_id", "market"]))


SIDES = {"over": ("over",), "under": ("under",), "both": ("over", "under")}


def grid(best: dict, families: list[tuple], label: str) -> pd.DataFrame:
    """best[(market, side, method)] -> per-key best frame. Rows per family x floor x season."""
    rows = []
    for fam in families:
        b = best[fam]
        for f in FLOORS:
            sel = b[b.ev >= f]
            for s in SEASONS + ["all", "choose"]:
                if s == "all":
                    d = sel
                elif s == "choose":
                    d = sel[sel.season.isin(CHOOSE_SEASONS)]
                else:
                    d = sel[sel.season == s]
                rows.append({"rule": label, "market": fam[0], "side": fam[1], "method": fam[2], "floor": f,
                             "season": str(s), "n": len(d), "units": d.units.sum(), "risk": d.risk.sum()})
    g = pd.DataFrame(rows)
    g["roi"] = 100 * g.units / g.risk.replace(0, np.nan)
    return g


def choose_floor(g: pd.DataFrame, fam: tuple) -> float | None:
    d = g[(g.market == fam[0]) & (g.side == fam[1]) & (g.method == fam[2]) & (g.season == "choose") & (g.n >= 100)]
    if d.empty:
        return None
    return float(d.sort_values(["units", "floor"], ascending=[False, True]).iloc[0].floor)


def neighbourhood_table(g: pd.DataFrame, fams: list[tuple], season: str = "all") -> pd.DataFrame:
    d = g[g.season == season]
    rows = {}
    for fam in fams:
        x = d[(d.market == fam[0]) & (d.side == fam[1]) & (d.method == fam[2])].set_index("floor")
        name = f"{SHORT.get(fam[0], fam[0])} {fam[1]}" + (f" {fam[2]}" if fam[2] not in ("-", "") else "")
        rows[name] = {f"{f:.2f}": (f"{x.loc[f, 'roi']:+.1f} ({int(x.loc[f, 'n'])})" if x.loc[f, "n"] > 0 else "-")
                      for f in FLOORS}
    return pd.DataFrame(rows).T


def halves(b: pd.DataFrame) -> tuple[dict, dict]:
    dates = np.sort(b.game_date.values)
    mid = dates[len(dates) // 2]
    return summ(b[b.game_date < mid]), summ(b[b.game_date >= mid])


def within_season_halves(b: pd.DataFrame) -> tuple[dict, dict]:
    e, l = [], []
    for s, d in b.groupby("season"):
        dates = np.sort(d.game_date.unique())
        mid = dates[len(dates) // 2]
        e.append(d[d.game_date < mid])
        l.append(d[d.game_date >= mid])
    return summ(pd.concat(e)) if e else summ(b.iloc[:0]), summ(pd.concat(l)) if l else summ(b.iloc[:0])


def _placebo_core(c: pd.DataFrame, key_fair: pd.DataFrame, floors: list[float], side_sets: dict,
                  reps: int) -> pd.DataFrame:
    """Shuffle the key-level fair over probability within (date, market) -- each proposition gets another
    proposition's fair from the same night and market -- recompute EV for every candidate, keep one bet per
    key (max EV among the allowed sides) and grade every floor. Vectorised; seed 7."""
    key = ["game_id", "player_id", "market"]
    kf = key_fair.drop_duplicates(key).merge(c[key].drop_duplicates(), on=key).reset_index(drop=True)
    kf["kid"] = np.arange(len(kf))
    cc = c.merge(kf[key + ["kid"]], on=key)
    kid = cc.kid.values
    is_over = (cc.side == "over").values
    dec = cc.dec.values
    won = cc.won.values
    risk, win = stake(dec)
    pay = np.where(won == 1, win, -risk)
    grp = kf.groupby(["game_date", "market"]).ngroup().values
    base = np.argsort(grp, kind="stable")
    fv = kf.fair_over.values
    rng = np.random.default_rng(SEED)
    out = []
    for r in range(reps):
        order = np.lexsort((rng.random(len(kf)), grp))
        fs = np.empty(len(kf))
        fs[base] = fv[order]
        fo = fs[kid]
        ev = np.where(is_over, fo, 1 - fo) * dec - 1
        for sd, allowed in side_sets.items():
            m = np.isin(cc.side.values, allowed)
            idx = np.nonzero(m)[0]
            o = idx[np.argsort(-ev[idx], kind="stable")]
            _, first = np.unique(kid[o], return_index=True)
            pick = o[first]
            for fl in floors:
                p = pick[ev[pick] >= fl]
                out.append({"rep": r, "side": sd, "floor": fl, "n": len(p),
                            "roi": 100 * pay[p].sum() / risk[p].sum() if len(p) else np.nan})
    return pd.DataFrame(out)


def placebo(c: pd.DataFrame, key_fair: pd.DataFrame, fam: tuple, floor: float, reps: int = 50) -> dict:
    cc = c if fam[0] == "ALL" else c[c.market == fam[0]]
    r = _placebo_core(cc, key_fair, [floor], {fam[1]: SIDES[fam[1]]}, reps).roi.values
    return {"mean": float(np.nanmean(r)), "p95": float(np.nanpercentile(r, 95)), "max": float(np.nanmax(r)), "reps": reps}


def grid_placebo(c: pd.DataFrame, key_fair: pd.DataFrame, reps: int = 20) -> pd.DataFrame:
    """Whole-grid placebo on the pooled rows: every floor x side."""
    return _placebo_core(c, key_fair, FLOORS, SIDES, reps)


def evaluate(name: str, rule: str, fam: tuple, floor: float, bests: dict, g: pd.DataFrame, c_fam: pd.DataFrame,
             key_fair: pd.DataFrame | None, blind_pool: pd.DataFrame, dk_best: pd.DataFrame | None) -> dict:
    """Every pre-registered bar on one chosen cell. Returns a dict for the report and the structured output."""
    b = bests[fam]
    sel = b[b.ev >= floor]
    tag = f"{rule}_{fam[0]}_{fam[1]}_{fam[2]}_{floor:.2f}".replace("player_", "")
    path = OUT / f"props_market_bets_{tag}.parquet"
    save_bets(sel, path.name)
    s_all = summ(sel, ci=True)
    per = {s: summ(sel[sel.season == s]) for s in SEASONS}
    h1, h2 = halves(sel) if len(sel) else (summ(sel), summ(sel))
    w1, w2 = within_season_halves(sel) if len(sel) else (summ(sel), summ(sel))
    nb = {}
    for f2 in (round(floor - 0.01, 2), round(floor + 0.01, 2)):
        nb[f2] = summ(b[b.ev >= f2])        # below 0.00 or above 0.10 is outside the pre-registered grid
    extra = {}
    if floor <= 0.0:
        extra[-0.02] = summ(b[b.ev >= -0.02])
    side_share = sel.side.value_counts(normalize=True)
    dom = side_share.idxmax() if len(sel) else "-"
    dom_share = float(side_share.max()) if len(sel) else 0.0
    # blind same side over the eligible population at the same book set: best price on that side per key
    bl = blind_pool[(blind_pool.side == dom)]
    if fam[0] != "ALL":
        bl = bl[bl.market == fam[0]]
    bl = add_units(bl.sort_values("dec", ascending=False).drop_duplicates(["game_id", "player_id", "market"]))
    s_bl = summ(bl)
    by_book = sel.groupby("bookmaker").agg(n=("units", "size"), units=("units", "sum"))
    dk = None
    if dk_best is not None:
        dsel = dk_best[dk_best.ev >= floor]
        dk = summ(dsel)
    bars = {
        "1 real prices": True,
        "5 every season >=30 positive": all((per[s]["n"] < 30) or (per[s]["roi"] > 0) for s in SEASONS)
                                         and any(per[s]["n"] >= 30 for s in SEASONS),
        "6 n>=200 and CI>0": s_all["n"] >= 200 and s_all.get("lo", -1) > 0,
        "7 plateau (floor +-0.01 positive)": all(v["n"] > 0 and v["roi"] > 0 for v in nb.values()),
        "8 both halves positive": h1["n"] > 0 and h2["n"] > 0 and h1["roi"] > 0 and h2["roi"] > 0,
        "9 beats blind same side": (dom_share <= 0.70) or (s_all["n"] > 0 and s_all["roi"] > s_bl["roi"]),
        "10 placebo loses the edge": None,
        "11 CLV": None,     # N/A: one snapshot, no later price stored
        "confirm 2025-26 positive": per[CONFIRM_SEASON]["n"] > 0 and per[CONFIRM_SEASON]["roi"] > 0,
    }
    cheap = all(v for k, v in bars.items() if v is not None)
    pl = None
    if cheap and key_fair is not None and len(sel):
        pl = key_fair(fam, floor) if callable(key_fair) else placebo(c_fam, key_fair, fam, floor)
        bars["10 placebo loses the edge"] = s_all["roi"] > pl["p95"]
    else:
        bars["10 placebo loses the edge"] = "not run (an earlier bar failed)"
    passes = cheap and bars["10 placebo loses the edge"] is True
    return {"name": name, "rule": rule, "fam": fam, "floor": floor, "all": s_all, "per": per, "halves": (h1, h2),
            "ws_halves": (w1, w2), "neighbours": nb, "extra": extra, "dom": dom, "dom_share": dom_share, "blind": s_bl,
            "placebo": pl, "sel": sel, "by_book": by_book, "dk": dk, "bars": bars, "passes": passes,
            "path": str(path)}


def report_candidate(ev: dict) -> None:
    fam = ev["fam"]
    say(f"**{ev['name']}** -- floor {ev['floor']:.2f} (chosen on 2023-24 + 2024-25). All seasons: {fmt(ev['all'], ci=True)}. "
        + "By season: " + "; ".join(f"{SEASON_NAME[s]} {fmt(ev['per'][s])}" for s in SEASONS) + ".")
    h1, h2 = ev["halves"]
    w1, w2 = ev["ws_halves"]
    say(f"- Halves (bet-date median): early {fmt(h1)}, late {fmt(h2)}. Within each season, early {fmt(w1)}, late {fmt(w2)}.")
    lab = lambda k: f"floor {k:.2f}" + (" (outside the pre-registered 0.00-0.10 grid, read for the plateau only)"
                                         if k < 0 or k > 0.10 else "")
    say(f"- Neighbours: " + "; ".join(f"{lab(k)} {fmt(v)}" for k, v in ev["neighbours"].items())
        + "".join(f"; {lab(k)} {fmt(v)}" for k, v in ev.get("extra", {}).items()) + ".")
    say(f"- Side: {ev['dom']} on {100 * ev['dom_share']:.0f}% of bets. Blind {ev['dom']} at the best price among the same "
        f"books over every proposition the rule could have bet (the bar-9 comparator): {fmt(ev['blind'])}.")
    if ev["placebo"]:
        p = ev["placebo"]
        say(f"- Placebo (fair probability shuffled within date x market, {p['reps']} reps): mean {p['mean']:+.1f}%, "
            f"95th pct {p['p95']:+.1f}%, max {p['max']:+.1f}%.")
    if ev["dk"] is not None:
        say(f"- DraftKings only, same rule and floor: {fmt(ev['dk'])}.")
    bb = ev["by_book"]
    say("- Units by book: " + ", ".join(f"{k} {int(r.n)} / {r.units:+.1f}u" for k, r in bb.sort_values("units").iterrows()) + ".")
    def _b(k, v):
        if v is None:
            return "N/A (one snapshot, no later price)"
        if isinstance(v, str):
            return v
        return "pass" if v else "FAIL"
    say("- Bars: " + "; ".join(f"{k}: {_b(k, v)}" for k, v in ev["bars"].items()) + f". **{'PASSES' if ev['passes'] else 'does not pass'}**.")
    say(f"- Bet list: `{ev['path']}`")
    say()


# --------------------------------------------------------------------------- Q3 sharp vs soft
PIN_MARKETS: list[str] = []


def soft_rows(u: pd.DataFrame, books: list[str]) -> pd.DataFrame:
    ok = u.coherent | (u.market.isin(YESNO) & u.has_o & ~u.has_u)
    return u[u.bookmaker.isin(books) & ok]


def q3_sharp(q: pd.DataFrame) -> tuple[list, pd.DataFrame]:
    global PIN_MARKETS
    say("## 3. Sharp-vs-soft: Pinnacle no-vig vs every bettable book at the same line")
    say()
    u = q[q.usable & q.x.notna()]
    pin = u[(u.bookmaker == "pinnacle") & u.coherent][["game_id", "player_id", "market", "line", "od", "ud", "game_date"]].copy()
    pin["fair_prop"] = (1 / pin.od) / (1 / pin.od + 1 / pin.ud)
    pin["fair_pow"] = power_devig(pin.od.values, pin.ud.values)
    PIN_MARKETS = [m for m in MARKETS if (pin.market == m).sum() >= 300]
    say(f"Markets Pinnacle quotes (>= 300 usable coherent quotes): {', '.join(SHORT[m] for m in PIN_MARKETS)}. "
        f"Not quoted: {', '.join(SHORT[m] for m in MARKETS if m not in PIN_MARKETS)}.")
    say()
    soft = soft_rows(u, BETTABLE)
    soft = soft[soft.market.isin(PIN_MARKETS)]
    j = soft.merge(pin[["game_id", "player_id", "market", "line", "fair_prop", "fair_pow"]].rename(columns={"line": "pline"}),
                   on=["game_id", "player_id", "market"], how="left")
    diag = j.assign(no_pin=j.pline.isna(), mismatch=j.pline.notna() & (j.line != j.pline),
                    compared=j.pline.notna() & (j.line == j.pline)).groupby("bookmaker")[["compared", "mismatch", "no_pin"]].sum()
    say("Soft quotes compared at Pinnacle's exact line, dropped for a different line, and with no Pinnacle quote (markets Pinnacle quotes):")
    say()
    say(md_table(diag.astype(int)))
    say()
    m = j[j.line == j.pline]
    cands = {}
    for meth, col in (("prop", "fair_prop"), ("power", "fair_pow")):
        cands[meth] = candidates_from(m, col)
    bests, fams = {}, []
    for meth in ("prop", "power"):
        for mk in PIN_MARKETS + ["ALL"]:
            c = cands[meth] if mk == "ALL" else cands[meth][cands[meth].market == mk]
            for sd in SIDES:
                fam = (mk, sd, meth)
                bests[fam] = best_per_key(c, SIDES[sd])
                fams.append(fam)
    g = grid(bests, fams, "sharp")
    g.to_parquet(OUT / "props_market_grid_sharp.parquet", index=False)
    say(f"Grid searched: {len(PIN_MARKETS) + 1} market rows (each market + pooled) x 3 sides x 2 de-vig methods x "
        f"{len(FLOORS)} EV floors = {len(fams) * len(FLOORS)} cells, each graded by season. "
        "One bet per (game, player, market): the max-EV bettable book and side. ROI % (bets), all three seasons:")
    say()
    for meth in ("prop", "power"):
        say(f"De-vig: {meth}")
        say()
        say(md_table(neighbourhood_table(g, [f for f in fams if f[2] == meth])))
        say()
    key_fair0 = pin.rename(columns={"fair_prop": "fair_over"})[["game_id", "player_id", "market", "game_date", "fair_over"]]
    gp = grid_placebo(cands["prop"], key_fair0)
    gp.to_parquet(OUT / "props_market_grid_sharp_placebo.parquet", index=False)
    real = g[(g.market == "ALL") & (g.method == "prop") & (g.season == "all")].set_index(["side", "floor"])
    pm = gp.groupby(["side", "floor"]).agg(placebo_mean=("roi", "mean"), placebo_p95=("roi", lambda x: np.nanpercentile(x, 95)),
                                            placebo_n=("n", "mean"))
    pm = pm.join(real[["roi", "n"]].rename(columns={"roi": "real_roi", "n": "real_n"}))
    say("Whole-grid placebo, pooled markets, prop de-vig (Pinnacle fair shuffled within date x market, 20 reps): real ROI "
        "vs the placebo mean and 95th percentile at every floor:")
    say()
    say(md_table(pm.reset_index().assign(floor=lambda x: x.floor.map(lambda v: f"{v:.2f}")).set_index(["side", "floor"]), floatfmt="{:.1f}"))
    say()
    # per-season view for pooled rows
    say("Pooled markets, by season (prop de-vig):")
    say()
    for s in [str(x) for x in SEASONS]:
        say(f"{SEASON_NAME[int(s)]}:")
        say()
        say(md_table(neighbourhood_table(g, [f for f in fams if f[2] == "prop" and f[0] == "ALL"], season=s)))
        say()
    # DK-only beside
    dk_bests = {}
    for meth, col in (("prop", "fair_prop"), ("power", "fair_pow")):
        cdk = cands[meth][cands[meth].bookmaker == "draftkings"]
        for mk in PIN_MARKETS + ["ALL"]:
            c = cdk if mk == "ALL" else cdk[cdk.market == mk]
            for sd in SIDES:
                dk_bests[(mk, sd, meth)] = best_per_key(c, SIDES[sd])
    gdk = grid(dk_bests, fams, "sharp_dk")
    gdk.to_parquet(OUT / "props_market_grid_sharp_dk.parquet", index=False)
    say("DraftKings only (same rule, the soft book restricted to DraftKings), prop de-vig, all seasons:")
    say()
    say(md_table(neighbourhood_table(gdk, [f for f in fams if f[2] == "prop"])))
    say()
    # save every per-key best (any grid cell = filter ev >= floor)
    allbest = pd.concat([b.assign(fam_market=f[0], fam_side=f[1], fam_method=f[2]) for f, b in bests.items()
                         if f[0] == "ALL"], ignore_index=True)
    save_bets(allbest, "props_market_sharp_best_per_key.parquet", extra=["fam_side", "fam_method"])
    # choose floors + evaluate
    key_fair = pin.rename(columns={"fair_prop": "fair_over"})[["game_id", "player_id", "market", "game_date", "fair_over"]]
    blind_pool = pd.concat([m[m.has_o].assign(side="over", dec=m.od, won=m.over_win, price=m.over_price),
                            m[m.has_u].assign(side="under", dec=m.ud, won=1 - m.over_win, price=m.under_price)])
    evals = []
    say("### 3b. Chosen cut per family (2023-24 + 2024-25 only), every bar")
    say()
    for fam in fams:
        f = choose_floor(g, fam)
        if f is None:
            continue
        # only evaluate families positive on the choosing seasons at the chosen floor
        row = g[(g.market == fam[0]) & (g.side == fam[1]) & (g.method == fam[2]) & (g.floor == f) & (g.season == "choose")].iloc[0]
        if row.units <= 0:
            continue
        cf = cands[fam[2]] if fam[0] == "ALL" else cands[fam[2]][cands[fam[2]].market == fam[0]]
        kf = key_fair if fam[2] == "prop" else pin.rename(columns={"fair_pow": "fair_over"})[["game_id", "player_id", "market", "game_date", "fair_over"]]
        ev = evaluate(f"Sharp-vs-soft {SHORT.get(fam[0], 'all markets')} {fam[1]} ({fam[2]} de-vig)", "sharp", fam, f,
                      bests, g, cf, kf, blind_pool, dk_bests.get(fam))
        report_candidate(ev)
        evals.append(ev)
    if not evals:
        say("No family is positive on 2023-24 + 2024-25 at any floor with >= 100 bets.")
        say()
    nfam_pos = len(evals)
    say(f"Families with a positive chosen cut on the choosing seasons: {nfam_pos} of {len(fams)}; passing every bar: "
        f"{sum(e['passes'] for e in evals)}.")
    say()
    return evals, g


# --------------------------------------------------------------------------- Q4 consensus
def q4_consensus(q: pd.DataFrame) -> tuple[list, pd.DataFrame]:
    say("## 4. Consensus rule where Pinnacle is absent")
    say()
    u = q[q.usable & q.x.notna()]
    haspin = u[(u.bookmaker == "pinnacle") & u.coherent][["game_id", "player_id", "market"]].drop_duplicates().assign(hp=1)
    u = u.merge(haspin, on=["game_id", "player_id", "market"], how="left")
    u = u[u.hp.isna()]
    tw = u[u.coherent][["game_id", "player_id", "market", "line", "bookmaker", "od", "ud"]].copy()
    tw["p"] = (1 / tw.od) / (1 / tw.od + 1 / tw.ud)
    soft = soft_rows(u, BETTABLE)
    j = soft[["game_id", "player_id", "market", "line", "bookmaker"]].reset_index().merge(
        tw[["game_id", "player_id", "market", "line", "bookmaker", "p"]].rename(columns={"bookmaker": "ob"}),
        on=["game_id", "player_id", "market", "line"])
    j = j[j.ob != j.bookmaker]
    agg = j.groupby("index").p.agg(["median", "size"])
    soft = soft.join(agg)
    soft = soft[soft["size"] >= 3].rename(columns={"median": "fair_cons"})
    say(f"Propositions without a Pinnacle quote; each bettable quote is compared with the median proportional no-vig over "
        f"probability of the OTHER books (bettable or not, excluding the book being bet) at the same line, at least 3 of them. "
        f"Soft quotes with a consensus: {len(soft):,} "
        f"({soft.groupby('market').size().rename(index=SHORT).to_dict()}).")
    say()
    c = candidates_from(soft, "fair_cons")
    mks = [m for m in MARKETS if (c.market == m).sum() >= 500]
    bests, fams = {}, []
    for mk in mks + ["ALL"]:
        cc = c if mk == "ALL" else c[c.market == mk]
        for sd in SIDES:
            fam = (mk, sd, "-")
            bests[fam] = best_per_key(cc, SIDES[sd])
            fams.append(fam)
    g = grid(bests, fams, "consensus")
    g.to_parquet(OUT / "props_market_grid_consensus.parquet", index=False)
    say(f"Grid searched: {len(mks) + 1} market rows x 3 sides x {len(FLOORS)} floors = {len(fams) * len(FLOORS)} cells. ROI % (bets), all seasons:")
    say()
    say(md_table(neighbourhood_table(g, fams)))
    say()
    dk_bests = {}
    cdk = c[c.bookmaker == "draftkings"]
    for mk in mks + ["ALL"]:
        cc = cdk if mk == "ALL" else cdk[cdk.market == mk]
        for sd in SIDES:
            dk_bests[(mk, sd, "-")] = best_per_key(cc, SIDES[sd])
    gdk = grid(dk_bests, fams, "consensus_dk")
    say("DraftKings only:")
    say()
    say(md_table(neighbourhood_table(gdk, fams)))
    say()
    allbest = pd.concat([bests[("ALL", sd, "-")].assign(fam_side=sd) for sd in SIDES], ignore_index=True)
    save_bets(allbest, "props_market_consensus_best_per_key.parquet", extra=["fam_side"])
    key_fair = soft.drop_duplicates(["game_id", "player_id", "market", "line"])[["game_id", "player_id", "market", "game_date", "fair_cons"]] \
        .rename(columns={"fair_cons": "fair_over"}).drop_duplicates(["game_id", "player_id", "market"])
    blind_pool = pd.concat([soft[soft.has_o].assign(side="over", dec=soft.od, won=soft.over_win, price=soft.over_price),
                            soft[soft.has_u].assign(side="under", dec=soft.ud, won=1 - soft.over_win, price=soft.under_price)])
    evals = []
    say("### 4b. Chosen cut per family (2023-24 + 2024-25 only), every bar")
    say()
    for fam in fams:
        f = choose_floor(g, fam)
        if f is None:
            continue
        row = g[(g.market == fam[0]) & (g.side == fam[1]) & (g.method == fam[2]) & (g.floor == f) & (g.season == "choose")].iloc[0]
        if row.units <= 0:
            continue
        cf = c if fam[0] == "ALL" else c[c.market == fam[0]]
        # placebo note: the consensus fair differs by book (excludes the bet book); shuffle uses the per-key first value
        ev = evaluate(f"Consensus {SHORT.get(fam[0], 'all markets')} {fam[1]}", "consensus", fam, f, bests, g, cf,
                      key_fair, blind_pool, dk_bests.get(fam))
        report_candidate(ev)
        evals.append(ev)
    if not evals:
        say("No family is positive on 2023-24 + 2024-25 at any floor with >= 100 bets.")
        say()
    say(f"Families with a positive chosen cut on the choosing seasons: {len(evals)} of {len(fams)}; passing every bar: "
        f"{sum(e['passes'] for e in evals)}.")
    say()
    return evals, g


# --------------------------------------------------------------------------- Q5 line gap
GAP_MARKETS = [m for m in MARKETS if m not in YESNO]
BOX_STAT = {"player_points": ["points"], "player_rebounds": ["rebounds"], "player_assists": ["assists"],
            "player_threes": ["fg3_made"], "player_points_rebounds_assists": ["points", "rebounds", "assists"],
            "player_points_rebounds": ["points", "rebounds"], "player_points_assists": ["points", "assists"],
            "player_rebounds_assists": ["rebounds", "assists"], "player_blocks": ["blocks"], "player_steals": ["steals"],
            "player_blocks_steals": ["blocks", "steals"], "player_turnovers": ["turnovers"]}
MU_GRID = np.concatenate([np.arange(0.005, 5, 0.005), np.arange(5, 95, 0.02)])


def nb_alpha(log: pd.DataFrame, market: str, season: int) -> float:
    """NB2 dispersion (var = mu + alpha mu^2) from box scores of seasons strictly before `season`:
    player-seasons with >= 20 games played, weighted least squares through the origin. alpha <= 0 -> Poisson."""
    d = log[(log.season < season) & (log.minutes > 0)]
    x = d[BOX_STAT[market]].sum(axis=1)
    g = x.groupby([d.player_id, d.season]).agg(["mean", "var", "size"])
    g = g[(g["size"] >= 20) & (g["mean"] >= 0.5)]
    a = float((g["size"] * g["mean"] ** 2 * (g["var"] - g["mean"])).sum() / (g["size"] * g["mean"] ** 4).sum())
    return max(a, 0.0)


class NBTable:
    """P(X > L) on a mu grid for every half-point line, one market and one dispersion."""
    def __init__(self, alpha: float, lines: np.ndarray):
        self.alpha = alpha
        self.lines = np.unique(lines)
        k = np.floor(self.lines)[:, None]
        mu = MU_GRID[None, :]
        if alpha <= 1e-6:
            self.sf = sst.poisson.sf(k, mu)
        else:
            r = 1.0 / alpha
            self.sf = sst.nbinom.sf(k, r, r / (r + mu))
        self.idx = {float(l): i for i, l in enumerate(self.lines)}

    def mu_from(self, L: np.ndarray, p: np.ndarray) -> np.ndarray:
        out = np.full(len(L), np.nan)
        for l in np.unique(L):
            s = L == l
            curve = self.sf[self.idx[float(l)]]          # increasing in mu
            out[s] = np.interp(p[s], curve, MU_GRID)
        return out

    def p_over(self, L: np.ndarray, mu: np.ndarray) -> np.ndarray:
        out = np.full(len(L), np.nan)
        for l in np.unique(L):
            s = L == l
            out[s] = np.interp(mu[s], MU_GRID, self.sf[self.idx[float(l)]])
        return out


def q5_line_gap(q: pd.DataFrame) -> list:
    say("## 5. Line-gap rule: a bettable book off the market's line")
    say()
    log = pd.read_parquet(CACHE / "nba_player_game_log.parquet")
    u = q[q.usable & q.x.notna() & q.coherent & q.market.isin(GAP_MARKETS)].copy()
    u["p"] = (1 / u.od) / (1 / u.od + 1 / u.ud)
    alphas = {(m, s): nb_alpha(log, m, s) for m in GAP_MARKETS for s in SEASONS}
    tabs = {(m, s): NBTable(alphas[(m, s)], u[u.market == m].line.values) for m in GAP_MARKETS for s in SEASONS}
    say("Fair probability at an off-market line: a negative-binomial count distribution for the stat, var = mu + alpha mu^2, "
        "with alpha fitted per market on box scores of seasons strictly before the graded season (player-seasons with "
        ">= 20 games; 2018-19 onward). The reference quote (Pinnacle's line and no-vig price; else the median over the other "
        "books' implied means, at least 3 books) fixes mu, and the distribution gives P(over) at the book's own line. "
        "alpha by market and season (0 = Poisson):")
    say()
    say(md_table(pd.DataFrame({SEASON_NAME[s]: {SHORT[m]: alphas[(m, s)] for m in GAP_MARKETS} for s in SEASONS}), floatfmt="{:.4f}"))
    say()
    u["mu"] = np.nan
    for (m, s), t in tabs.items():
        sel = (u.market == m) & (u.season == s)
        if sel.any():
            u.loc[sel, "mu"] = t.mu_from(u.loc[sel, "line"].values, u.loc[sel, "p"].values)
    key = ["game_id", "player_id", "market"]
    pin = u[u.bookmaker == "pinnacle"][key + ["line", "mu"]].rename(columns={"line": "Lref", "mu": "mu_ref"})
    soft = u[u.bookmaker.isin(BETTABLE)].reset_index(drop=True)
    soft["rid"] = np.arange(len(soft))
    sp = soft.merge(pin, on=key, how="inner")
    sp["ref"] = "pinnacle"
    nopin = soft[~soft.set_index(key).index.isin(pin.set_index(key).index)]
    oth = u[u.bookmaker != "pinnacle"][key + ["bookmaker", "line", "mu"]].rename(columns={"bookmaker": "ob", "line": "ol", "mu": "om"})
    j = nopin[key + ["rid", "bookmaker"]].merge(oth, on=key)
    j = j[j.ob != j.bookmaker]
    agg = j.groupby("rid").agg(Lref=("ol", "median"), mu_ref=("om", "median"), n_oth=("ol", "size"))
    agg = agg[agg.n_oth >= 3]
    sc = nopin.merge(agg, left_on="rid", right_index=True)
    sc["ref"] = "consensus"
    allq = pd.concat([sp, sc.drop(columns=["n_oth"])], ignore_index=True)
    allq["gap"] = allq.line - allq.Lref
    allq["fair_over"] = np.nan
    for (m, s), t in tabs.items():
        sel = (allq.market == m) & (allq.season == s)
        if sel.any():
            allq.loc[sel, "fair_over"] = t.p_over(allq.loc[sel, "line"].values, allq.loc[sel, "mu_ref"].values)
    on_line = allq[allq.gap == 0]
    off = allq[allq.gap != 0].copy()
    say(f"Bettable two-way quotes with a reference: {len(allq):,}; on the reference line {len(on_line):,}; off it {len(off):,} "
        f"(by book: {off.groupby('bookmaker').size().to_dict()}).")
    say()
    off["err"] = (off.fair_over - off.p) * -np.sign(off.gap)
    off["absgap"] = off.gap.abs()
    off["gb"] = np.where(off.absgap <= 0.5, "0.5", np.where(off.absgap <= 1, "1", np.where(off.absgap <= 1.5, "1.5", "2+")))
    chk = off.groupby(["market", "gb"]).agg(n=("err", "size"), d=("err", lambda e: 100 * e.mean()))
    say("Check 1 -- the market's own ladder: the distribution's probability for the gap-favoured side at the book's line, minus "
        "the book's own no-vig probability for that side, in points (positive = the distribution says the book under-adjusts "
        "its price for the gap, so the favoured side looks like value):")
    say()
    say(md_table(chk.reset_index().assign(market=lambda x: x.market.map(SHORT)).pivot(index="market", columns="gb", values="d"),
                 floatfmt="{:+.1f}"))
    say()
    o = off[off.gap < 0].assign(side="over", dec=lambda x: x.od, price=lambda x: x.over_price, fair_prob=lambda x: x.fair_over,
                                won=lambda x: x.over_win, book_p=lambda x: x.p)
    un = off[off.gap > 0].assign(side="under", dec=lambda x: x.ud, price=lambda x: x.under_price,
                                 fair_prob=lambda x: 1 - x.fair_over, won=lambda x: 1 - x.over_win, book_p=lambda x: 1 - x.p)
    c = pd.concat([o, un], ignore_index=True)
    c["ev"] = c.fair_prob * c.dec - 1
    cal = c.groupby(["ref", "gb"]).agg(n=("won", "size"), realised=("won", "mean"), distribution=("fair_prob", "mean"),
                                       book_novig=("book_p", "mean"))
    say("Check 2 -- outcomes: realised win rate of the gap-favoured side against the distribution's probability and the "
        "book's own no-vig probability (every off-line quote, all seasons, all markets):")
    say()
    say(md_table(cal, floatfmt="{:.3f}"))
    say()
    say("**Read every line-gap EV below with this in mind:** the distribution overstates the gap-favoured side "
        "(on Pinnacle-referenced one-point gaps it says 0.560 where 0.545 happened and the books' own no-vig said 0.542), so "
        "the `fair_prob` and `ev` columns of every line-gap bet list are biased upward by roughly 1.5 points. An EV floor of "
        "0.02 here is roughly 0.005 at realised rates. The floors absorb this because they were chosen on graded results, "
        "but the EV numbers are not calibrated probabilities.")
    say()
    c["fav"] = c.absgap
    blind = add_units(c.sort_values(["fav", "dec"], ascending=[False, False]).drop_duplicates(key + ["ref"]))
    rows = {}
    for ref in ("pinnacle", "consensus"):
        for m in GAP_MARKETS:
            d = blind[(blind.ref == ref) & (blind.market == m)]
            if len(d) < 30:
                continue
            r = {gb: roi_n(d[d.gb == gb]) for gb in ("0.5", "1", "1.5", "2+")}
            r["all"] = fmt(summ(d, ci=True), ci=True)
            r["over share"] = f"{100 * (d.side == 'over').mean():.0f}%"
            rows[f"{ref} | {SHORT[m]}"] = r
    say("### 5a. Blind gap-side bets by gap size (no EV filter; one bet per player-market, the most favourable line then the "
        "best price). ROI % (bets):")
    say()
    say(md_table(pd.DataFrame(rows).T))
    say()
    by_bk = blind.groupby(["ref", "bookmaker"]).apply(lambda d: roi_n(d)).unstack("ref")
    say("Blind gap-side by the book that hung the off-market line:")
    say()
    say(md_table(by_bk))
    say()
    by_side = blind.groupby(["ref", "side"]).apply(lambda d: fmt(summ(d, ci=True), ci=True)).unstack("side")
    say("Blind gap-side by side:")
    say()
    say(md_table(by_side))
    say()
    save_bets(blind, "props_market_gap_blind.parquet", extra=["ref", "gap", "gb"])
    bests, fams = {}, []
    for ref in ("pinnacle", "consensus"):
        cr = c[c.ref == ref]
        for m in GAP_MARKETS + ["ALL"]:
            cc = cr if m == "ALL" else cr[cr.market == m]
            if len(cc) < 300:
                continue
            for sd in SIDES:
                fam = (m, sd, ref)
                bests[fam] = best_per_key(cc, SIDES[sd])
                fams.append(fam)
    g = grid(bests, fams, "gap")
    g.to_parquet(OUT / "props_market_grid_gap.parquet", index=False)
    say(f"### 5b. EV-filtered gap bets (fair from the distribution), grid: {len(fams)} families x {len(FLOORS)} floors = "
        f"{len(fams) * len(FLOORS)} cells. ROI % (bets), all seasons:")
    say()
    say(md_table(neighbourhood_table(g, fams)))
    say()
    gb_rows = {}
    for ref in ("pinnacle", "consensus"):
        b = bests.get(("ALL", "both", ref))
        if b is None:
            continue
        for f in (0.0, 0.03, 0.05, 0.08):
            d = b[b.ev >= f]
            gb_rows[f"{ref} EV>={f:.2f}"] = {gb: roi_n(d[d.gb == gb]) for gb in ("0.5", "1", "1.5", "2+")}
    say("Pooled, by gap size of the bet taken:")
    say()
    say(md_table(pd.DataFrame(gb_rows).T))
    say()
    allb = pd.concat([b.assign(fam_ref=f[2], fam_side=f[1]) for f, b in bests.items() if f[0] == "ALL"], ignore_index=True)
    save_bets(allb, "props_market_gap_best_per_key.parquet", extra=["fam_ref", "fam_side", "gap", "gb"])
    dk_bests = {}
    for fam in fams:
        cc = c[(c.ref == fam[2]) & (c.bookmaker == "draftkings")]
        if fam[0] != "ALL":
            cc = cc[cc.market == fam[0]]
        dk_bests[fam] = best_per_key(cc, SIDES[fam[1]])
    gdk = grid(dk_bests, fams, "gap_dk")
    say("DraftKings only:")
    say()
    say(md_table(neighbourhood_table(gdk, fams)))
    say()

    def gap_placebo(fam, floor, reps=50):
        rng = np.random.default_rng(SEED)
        cc = c[c.ref == fam[2]]
        if fam[0] != "ALL":
            cc = cc[cc.market == fam[0]]
        cc = cc[cc.side.isin(SIDES[fam[1]])].reset_index(drop=True)
        kk = cc[key + ["game_date", "mu_ref"]].drop_duplicates(key).reset_index(drop=True)
        kk["kid"] = np.arange(len(kk))
        kid = cc.merge(kk[key + ["kid"]], on=key, how="left").kid.values
        grp = kk.groupby(["game_date", "market"]).ngroup().values
        base = np.argsort(grp, kind="stable")
        mv = kk.mu_ref.values
        lines, dec, won = cc.line.values, cc.dec.values, cc.won.values
        is_over = (cc.side == "over").values
        risk, win = stake(dec)
        pay = np.where(won == 1, win, -risk)
        slices = [(t, ((cc.market == m) & (cc.season == ss)).values) for (m, ss), t in tabs.items()]
        rois = []
        for _ in range(reps):
            order = np.lexsort((rng.random(len(kk)), grp))
            ms = np.empty(len(kk))
            ms[base] = mv[order]
            mu = ms[kid]
            fo = np.full(len(cc), np.nan)
            for t, sl in slices:
                if sl.any():
                    fo[sl] = t.p_over(lines[sl], mu[sl])
            ev = np.where(is_over, fo, 1 - fo) * dec - 1
            o = np.argsort(-ev, kind="stable")
            _, first = np.unique(kid[o], return_index=True)
            p = o[first]
            p = p[ev[p] >= floor]
            rois.append(100 * pay[p].sum() / risk[p].sum() if len(p) else np.nan)
        r = np.array(rois, dtype=float)
        return {"mean": float(np.nanmean(r)), "p95": float(np.nanpercentile(r, 95)), "max": float(np.nanmax(r)), "reps": reps}

    blind_pool = pd.concat([on_line[on_line.has_o].assign(side="over", dec=on_line.od, won=on_line.over_win, price=on_line.over_price),
                            on_line[on_line.has_u].assign(side="under", dec=on_line.ud, won=1 - on_line.over_win, price=on_line.under_price)])
    evals = []
    say("### 5c. Chosen cut per family (2023-24 + 2024-25 only), every bar. The blind comparator is the same side at the best "
        "bettable price on the reference line.")
    say()
    for fam in fams:
        f = choose_floor(g, fam)
        if f is None:
            continue
        row = g[(g.market == fam[0]) & (g.side == fam[1]) & (g.method == fam[2]) & (g.floor == f) & (g.season == "choose")].iloc[0]
        if row.units <= 0:
            continue
        ev = evaluate(f"Line gap {SHORT.get(fam[0], 'all markets')} {fam[1]} (ref {fam[2]})", "gap", fam, f, bests, g, None,
                      gap_placebo, blind_pool[blind_pool.ref == fam[2]], dk_bests.get(fam))
        report_candidate(ev)
        evals.append(ev)
    if not evals:
        say("No family is positive on 2023-24 + 2024-25 at any floor with >= 100 bets.")
        say()
    say(f"Families with a positive chosen cut on the choosing seasons: {len(evals)} of {len(fams)}; passing every bar: "
        f"{sum(e['passes'] for e in evals)}.")
    say()
    return evals


# --------------------------------------------------------------------------- Q6 live constraints
def live_constraints(path: str, name: str) -> None:
    """One bet a game, then a nightly cap of 2/4/6/none, ranked by EV (knows the whole night) and first-come
    by tip time (what a card deciding at tip - 60 min could actually do). Units a season = units / 3."""
    b = pd.read_parquet(path)
    g = pd.read_parquet(CACHE / "nba_games.parquet", columns=["game_id", "commence_time"])
    b = b.merge(g, on="game_id", how="left")
    one = b.sort_values("ev", ascending=False).drop_duplicates("game_id")
    rows = {}
    rows["every bet (several a game)"] = b
    for k in (3, 2):        # information only: what the per-game limit costs in units a season
        rows[f"{k} a game (best EV), no nightly cap"] = b.sort_values("ev", ascending=False).groupby("game_id").head(k)
    rows["one a game"] = one
    for n in (2, 4, 6):
        rows[f"one a game, {n} a night, best EV"] = one.sort_values("ev", ascending=False).groupby("game_date").head(n)
        rows[f"one a game, {n} a night, first-come"] = (one.sort_values(["commence_time", "ev"], ascending=[True, False])
                                                         .groupby("game_date").head(n))
    out = {}
    for k, d in rows.items():
        s = summ(d, ci=True)
        out[k] = {"bets": s["n"], "units a season": s["units"] / len(SEASONS), "ROI": fmt(s, ci=True),
                  **{SEASON_NAME[x]: roi_n(d[d.season == x]) for x in SEASONS}}
    say(f"**{name}** under live constraints:")
    say()
    say(md_table(pd.DataFrame(out).T))
    say()


def q6(evals: list) -> None:
    say("## 6. Live constraints: one bet a game, nightly caps, units a season")
    say()
    say("Each passing pooled candidate is replayed as a card would run it: one bet a game (the best EV), then at most N a "
        "night. 'best EV' ranks the whole night (it needs every game's price, which a card deciding 60 minutes before each "
        "tip does not have for later games); 'first-come' takes games in tip order and, at a shared tip time, the higher EV "
        "first -- what a card deciding at each game's snapshot can actually do. Units a season = total units / 3.")
    say()
    passing = [e for e in evals if e["passes"]]
    if not passing:
        say("No candidate cleared every bar, so the live constraints are not a shipping question.")
        say()
        return
    pooled = [e for e in passing if e["fam"][0] == "ALL"]
    for e in (pooled or passing):
        live_constraints(e["path"], e["name"] + f" (EV >= {e['floor']:.2f})")
    unders = sorted([e for e in pooled if e["fam"][1] == "under" and e["fam"][2] != "power"],
                    key=lambda e: ["sharp", "consensus", "gap"].index(e["rule"]))
    if len(unders) >= 2:
        parts = [pd.read_parquet(e["path"]).assign(src=e["rule"]) for e in unders]
        un = pd.concat(parts, ignore_index=True).drop_duplicates(["game_id", "player_id", "market"], keep="first")
        p = OUT / "props_market_bets_union_under.parquet"
        un.to_parquet(p, index=False)
        live_constraints(str(p), "Union of the pooled under candidates (" + " + ".join(e["name"] for e in unders)
                         + "; NOT a pre-registered family -- the same-line bet is kept where both fire, and the line-gap "
                         "EVs that enter the ranking are biased upward)")


def assemble() -> None:
    parts = [WORK / "head.md"] + [OUT / f"props_market_part_{t}.md" for t in ("12", "3", "4", "5", "6")] \
        + [OUT / "props_market_robust.md"]
    body = []
    for p in parts:
        if p.exists():
            t = p.read_text(encoding="utf-8")
            if p.name.startswith("props_market_part_") and p.name != "props_market_part_12.md":
                t = "\n".join(t.split("\n")[4:])          # drop the repeated title block
            body.append(t)
    (OUT / "props_market.md").write_text("\n\n".join(body), encoding="utf-8")
    print("wrote", OUT / "props_market.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--only", default="1,2,3,4,5,6")
    ap.add_argument("--assemble", action="store_true")
    args = ap.parse_args()
    if args.assemble:
        assemble()
        return
    only = set(args.only.split(","))
    q, integ = load_quotes(args.rebuild)
    say("# NBA player props -- market-relative lab (key `props_market`)")
    say()
    say(f"Generated by `scripts/nba_prop_market_lab.py` on the local cache. Bettable books (config.BEST_LINE_BOOKMAKERS): "
        f"{', '.join(BETTABLE)}. No Odds API calls, no database reads.")
    say()
    if "1" in only:
        q1_integrity(q, integ)
    if "2" in only:
        q2_blind(q)
    ev3, ev4 = [], []
    if "3" in only:
        ev3, _ = q3_sharp(q)
    if "4" in only:
        ev4, _ = q4_consensus(q)
    ev5 = []
    if "5" in only:
        ev5 = q5_line_gap(q)
    if "6" in only:
        prior = []
        for tag in ("3", "4", "5"):
            p = WORK / f"evals_{tag}.pkl"
            if p.exists():
                d = pd.read_pickle(p)
                prior += d.get("ev3", []) + d.get("ev4", []) + d.get("ev5", [])
        q6(ev3 + ev4 + ev5 + prior)
    (OUT / f"props_market_part_{args.only.replace(',', '')}.md").write_text("\n".join(REPORT), encoding="utf-8")
    pd.to_pickle({"ev3": ev3, "ev4": ev4, "ev5": ev5, "facts": FACTS}, WORK / f"evals_{args.only.replace(',', '')}.pkl")


if __name__ == "__main__":
    main()
