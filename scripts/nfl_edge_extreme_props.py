"""Extreme edges on the one validated NFL prop rule: fewer bets, more EV per bet?

    python -m scripts.nfl_edge_extreme_props

HYPOTHESIS. models/nfl_prop_market (de-vig a sharp reference at a line, bet a
soft bettable book quoting the SAME line when its price disagrees by an edge
cut) returns MORE per bet at extreme cuts, at low volume.

Everything reads the local cache through scripts/nfl_edge_lib.py. No database,
no Odds API, no network.

=============================================================================
THE CONSTRUCTION -- written before any outcome was looked at
=============================================================================

PART 0. REPRODUCE THE SHIPPED GRADER (scripts/nfl_prop_two_sharps.build).
  Every rule copied: markets = models.nfl_prop_market.SHARP_MARKETS (anytime TD
  is listed but never graded there: its stat column does not exist, so it adds
  nothing); seasons 2023-25; the newest quote with snapshot_at <= kickoff per
  (game, player, market, line, book), of ANY snapshot type; references
  pinnacle and betonlineag, proportional two-way de-vig; soft books as they
  stood on 2026-09-12 (draftkings, fanduel, betmgm, williamhill_us, betrivers,
  fliff, hardrockbet); edge = reference fair probability of a side MINUS the
  soft book's OWN de-vigged probability of that side; "either" = any reference
  clears the cut; one bet per (game, player, market, side) keeping the biggest
  edge; pushes dropped; graded at the selecting book's price. Target numbers
  (docs/nfl_prop_over_lean.md): 1,990 bets / +155.9u / +7.84% at one 5pp floor,
  1,248 / +166.3u / +13.33% at over 6pp / under 5pp.
  WHICH COMMAND PRODUCED THEM (found by bet COUNT before any outcome was
  printed): the grader pinned to `--snapshot open` with the 2026-09-12 soft
  books gives exactly 1,990 bets (1,092 over / 898 under) and 1,248 paired; any
  other variant gives a different count (any type 3,443; today's soft books
  1,740). So the open-pinned grader is THE shipped record, and is the Part-0
  object everywhere below.

  THE DECISION-TIME DEFECT THAT GRADER CARRIES (checked, not assumed, in
  table R2). "Newest quote per KEY" lets the soft quote and the reference quote
  come from DIFFERENT board reads. When the soft quote is the older one, the
  bet uses a reference price that did not exist yet when the soft price was on
  the board, and the soft price was no longer on the board when the reference
  price appeared. That is look-ahead, and it is exactly what a stale "extreme"
  edge would look like. So Part 0 is reproduced as shipped and split by which
  quote was newer, and everything after it uses Part 1.

PART 1. THE CONSTRUCTION GRADED HERE (board-synchronous, shipped ceiling).
  * Decision time: for each (game, market), the LATEST board read stamped
    strictly before kickoff with lead <= 24h (config.NFL_PROP_MAX_LEAD_HOURS).
    All books in one read share one timestamp in this archive (measured on
    player_receptions 2023-25: one stamp per game-hour, 3,189 of 3,189). Only quotes stamped AT that read are
    used -- soft and reference from the same read, nothing after it.
  * Reference: pinnacle and betonlineag, proportional de-vig of a two-way
    quote at the line. Modes: pinnacle / betonlineag / either (the bigger of
    the two edges, any present) / both (the SMALLER of the two edges; both must
    quote the line) -- "both agree and edge >= X" is the precision filter.
  * Candidates: any lib.BETTABLE book with a two-way quote at a line a
    reference also quotes on the same read. edge = ref fair(side) - soft
    de-vig(side), exactly the shipped definition.
  * One bet per proposition = (game, player, market): the candidate (book,
    line, side) with the biggest edge under the mode; at a per-side cut the
    side must clear its own cut first.
  * Price: the BEST price on that side among lib.BETTABLE books at the same
    line on the same read (never worse than the selecting book's price).
    Pushes are bets that return 0 (counted, not dropped).
  * No outcome-derived feature anywhere in selection.
  * Grid: cut 4pp..25pp by 1pp, x side (over / under / pooled), x mode.
    Neighbourhood printed whole. "Strict" = <= 30 bets per season on average.
  * Splits: market, lead (0-3h / 3-12h / 12-24h), season, early (weeks 1-9)
    vs late (10+).
  * Staleness: for the selecting book's quote, how many consecutive board
    reads (ending at the decision read) carried the same line and the same
    price on that side, and the minutes that spans. Reads are 2h-48h apart in
    2023-25 (median 24h), so ">= 2 reads" and ">= 30 minutes" are the same
    population here; both columns are printed so that is visible, not assumed.
    Also: whether a SECOND bettable book clears the same cut at the same line
    (a lone outlier is the stale/erroneous-quote signature).
  * EV axis (secondary): EV = ref fair(side) x decimal(best price) - 1, either
    reference, pooled, 0%..25%. ADDED AFTER THE FIRST FULL RUN (so not
    pre-registered): its by-side grid, season / half / market splits, the same
    EV axis under both placebos, and the Part-2 fit/hold-out rule applied to it.
    That hold-out is not clean -- the pooled 2023-25 EV curve had been seen.
  * Placebo: the same Part-1 machinery with a RETAIL book's own de-vig as the
    reference (fanduel, then draftkings), betting every other bettable book.
    If the mechanism is a sharp reference, these must not work.

PART 1b. SYNCHRONOUS AT EVERY READ, ANY LEAD (declared after the count check
  showed Part 1 has ~no candidates at >= 10pp, and before any outcome).
  Same edge, same modes, same best-price grading, but every pre-kick read is a
  decision opportunity (t72 / t48 / t24 / open / t1, no ceiling) and the bet is
  locked at the FIRST read on which the proposition clears the cut (the
  production lock, CLAUDE.md 1c). This is outside the shipped 24h ceiling: it
  asks only whether extreme SYNCHRONOUS disagreements exist anywhere and pay.
  The same fit/hold-out rule as Part 2 is applied to it separately.

STALENESS ON THE SHIPPED RECORD ITSELF. The persistence measure above is also
  run on the Part-0 (open-pinned, asynchronous) bets, by cut, because that is
  where the extreme edges live.

PART 2. FIT AND HOLD-OUT. Fit seasons 2023-2024; hold-out 2025. The one
  parameter chosen is a strict cell (mode x side x cut): among cells with
  <= 30 bets per fit season on average and >= 15 fit bets, the one with the
  highest 90% CI LOWER bound on the fit seasons (ties -> lower cut). The rule
  is code, run before any 2025 number is printed; 2025 is then read for that
  cell and its +-2pp neighbours. The full-sample grids that follow are
  descriptive and feed no choice.

Intervals: cluster bootstrap on game_id (lib.boot_ci), 90%.
Results in UNITS: 1 unit = one flat bet.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from scripts import nfl_edge_lib as L

SEASONS = (2023, 2024, 2025)
FIT, HOLD = (2023, 2024), (2025,)
REFS = ("pinnacle", "betonlineag")
SHIPPED_MARKETS = (  # models.nfl_prop_market.SHARP_MARKETS
    "player_pass_yds", "player_pass_attempts", "player_pass_completions",
    "player_pass_tds", "player_reception_yds", "player_receptions",
    "player_rush_yds", "player_anytime_td",
)
MARKET_STAT = {  # models.nfl_prop_market.MARKET_STAT (anytime TD -> no column)
    "player_pass_yds": "passing_yards", "player_pass_attempts": "attempts",
    "player_pass_completions": "completions", "player_pass_tds": "passing_tds",
    "player_reception_yds": "receiving_yards", "player_receptions": "receptions",
    "player_rush_yds": "rushing_yards",
}
GRADED = tuple(m for m in SHIPPED_MARKETS if m in MARKET_STAT)
SOFT_0912 = ("draftkings", "fanduel", "betmgm", "williamhill_us",
             "betrivers", "fliff", "hardrockbet")
SOFT_NOW = ("draftkings", "fanduel", "betmgm", "williamhill_us",
            "betrivers", "hardrockbet")
CEILING_H = 24.0
CUTS = [c / 100 for c in range(4, 26)]
STRICT_MAX_PER_SEASON = 30
FIT_MIN_BETS = 15
LEAD_BUCKETS = ((0, 3), (3, 12), (12, 24))
MODES = ("pinnacle", "betonlineag", "either", "both")

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def norm_player_name(name: str) -> str:
    """Byte-for-byte data.ingestors.nfl_props_data_ingestor.norm_player_name
    (copied so this script never imports config / the DB layer)."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = _SUFFIX_RE.sub("", s.lower().strip())
    return re.sub(r"[^a-z]", "", s)


def implied(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, 100.0 / (a + 100.0), np.abs(a) / (np.abs(a) + 100.0))


def devig(o, u):
    qo, qu = implied(o), implied(u)
    s = qo + qu
    return qo / s, qu / s           # NaN wherever either price is missing


def payout(price):
    p = np.asarray(price, dtype=float)
    return np.where(p > 0, p / 100.0, 100.0 / np.abs(p))


# ─── data ──────────────────────────────────────────────────────────────────

def kickoffs() -> pd.DataFrame:
    k = pd.read_parquet(L.CACHE / "local_nfl_team_game_stats.parquet",
                        columns=["game_id", "commence_time"])
    k = k.dropna().drop_duplicates("game_id")
    k["kick"] = pd.to_datetime(k["commence_time"], utc=True)
    return k[["game_id", "kick"]]


def load_props(books: set[str]) -> pd.DataFrame:
    cols = ["game_id", "player_name", "market", "line", "over_price",
            "under_price", "bookmaker", "snapshot_at", "snapshot_type"]
    ko = kickoffs()
    parts = []
    for m in GRADED:
        d = L.props_market(m)[cols]
        d = d[d["game_id"].str.split("_").str[1].astype(int).isin(SEASONS)]
        d["market"] = d["market"].astype(str)
        d["bookmaker"] = d["bookmaker"].astype(str)
        d["snapshot_type"] = d["snapshot_type"].astype(str)
        d = d[d["bookmaker"].isin(books) & ~d["bookmaker"].isin(L.EXCLUDED)]
        d = d[d["line"].notna()]
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d = d.merge(ko, on="game_id", how="inner")
    d["lead_h"] = (d["kick"] - d["snapshot_at"]).dt.total_seconds() / 3600
    d["norm"] = d["player_name"].map(norm_player_name)
    d["season"] = d["game_id"].str.split("_").str[1].astype(int)
    d["week"] = d["game_id"].str.split("_").str[2].astype(int)
    return d


def actuals() -> pd.DataFrame:
    """The shipped grader's settlement source (local_store nfl_player_game_log),
    keyed on norm_player_name(player_name) -- last row wins, as in _actuals()."""
    a = pd.read_parquet(L.CACHE / "local_nfl_player_game_log.parquet",
                        columns=["player_name", "game_id"] + sorted(set(MARKET_STAT.values())))
    a = a[a["game_id"].str.split("_").str[1].astype(int).isin(SEASONS)].copy()
    a["norm"] = a["player_name"].map(norm_player_name)
    a = a.drop_duplicates(["norm", "game_id"], keep="last")
    long = []
    for m, stat in MARKET_STAT.items():
        x = a[["norm", "game_id", stat]].rename(columns={stat: "actual"})
        x["market"] = m
        long.append(x)
    return pd.concat(long, ignore_index=True)


# ─── reporting helpers ─────────────────────────────────────────────────────

def cell(df: pd.DataFrame, n_seasons: int | None = None) -> dict:
    if len(df) == 0:
        return {"n": 0}
    roi, (lo, hi) = L.boot_ci(df["profit"].values, df["game_id"].values)
    per = df.groupby("season").size().reindex(SEASONS, fill_value=0)
    return {"n": len(df), "units": df["profit"].sum(), "roi": 100 * roi,
            "lo": 100 * lo, "hi": 100 * hi, "per": per,
            "win": 100 * (df["profit"] > 0).mean()}


def fmt(c: dict, per_season=True, wide=True) -> str:
    if c["n"] == 0:
        return f"{0:>5} {'':>11} {'':>8} {'':>7} {'':>15}" if wide else f"{0:>5}"
    ps = "/".join(str(int(v)) for v in c["per"].values) if per_season else ""
    return (f"{c['n']:>5} {ps:>11} {c['units']:>+8.1f} {c['roi']:>+6.1f}% "
            f"({c['lo']:>+6.1f},{c['hi']:>+6.1f})")


HDR = f"{'bets':>5} {'23/24/25':>11} {'units':>8} {'ROI':>7} {'90% CI':>15}"


# ─── PART 0: the shipped grader, reproduced ────────────────────────────────

def shipped_grader(props: pd.DataFrame, act: pd.DataFrame, soft: tuple[str, ...]):
    """Vectorised scripts.nfl_prop_two_sharps.build, 'either' selection.
    Returns one row per (game, player, market, side) with best edge."""
    x = props[props["snapshot_at"] <= props["kick"]]
    x = x[x["bookmaker"].isin(set(soft) | set(REFS))]
    x = x.sort_values("snapshot_at").groupby(
        ["game_id", "norm", "market", "line", "bookmaker"], as_index=False).tail(1)
    keys = ["game_id", "norm", "market", "line"]
    refs = []
    for r in REFS:
        q = x[x["bookmaker"] == r][keys + ["over_price", "under_price", "snapshot_at"]].copy()
        q["fo_" + r], q["fu_" + r] = devig(q["over_price"], q["under_price"])
        q = q.rename(columns={"snapshot_at": "ts_" + r})[keys + ["fo_" + r, "fu_" + r, "ts_" + r]]
        refs.append(q)
    ref = refs[0].merge(refs[1], on=keys, how="outer")
    s = x[x["bookmaker"].isin(soft)].copy()
    s["so"], s["su"] = devig(s["over_price"], s["under_price"])
    s = s[s["so"].notna()]
    s = s.merge(ref, on=keys, how="inner")
    s = s[s[["fo_pinnacle", "fo_betonlineag"]].notna().any(axis=1)]
    s = s.merge(act, on=["norm", "game_id", "market"], how="inner")
    n_nan = int(s["actual"].isna().sum())
    if n_nan:
        print(f"  [shipped grader] {n_nan} candidate rows have a NaN actual (dropped here)")
    s = s[s["actual"].notna() & (s["actual"] != s["line"])]
    out = []
    for side, sp, price in (("over", "so", "over_price"), ("under", "su", "under_price")):
        f = "fo_" if side == "over" else "fu_"
        e = s[[f + r for r in REFS]].sub(s[sp], axis=0)
        y = s.assign(side=side, price=s[price], e_pin=e[f + "pinnacle"],
                     e_bol=e[f + "betonlineag"], edge=e.max(axis=1))
        y["ref_ts"] = np.where(y["e_pin"].fillna(-9) >= y["e_bol"].fillna(-9),
                               y["ts_pinnacle"], y["ts_betonlineag"])
        y["won"] = (y["actual"] > y["line"]) if side == "over" else (y["actual"] < y["line"])
        out.append(y)
    y = pd.concat(out, ignore_index=True)
    y = y[y["price"].notna()]
    y["profit"] = np.where(y["won"], payout(y["price"]), -1.0)
    y["ref_ts"] = pd.to_datetime(y["ref_ts"], utc=True)
    y = y.sort_values("edge", ascending=False).drop_duplicates(
        ["game_id", "norm", "market", "side"])
    return y


def tag_timing(y: pd.DataFrame) -> pd.DataFrame:
    return y.assign(sync=np.select(
        [y["snapshot_at"] == y["ref_ts"], y["snapshot_at"] < y["ref_ts"]],
        ["same read", "soft OLDER (look-ahead)"], "reference older"))


def part0(props, act):
    print("\n" + "=" * 100)
    print("R1. REPRODUCTION of the shipped grader (scripts/nfl_prop_two_sharps, 'either')")
    print("=" * 100)
    print(f"  {'variant':52s} {HDR}")
    rows = {}
    for label, soft, types in (
            ("SHIPPED: 09-12 soft books, open read", SOFT_0912, {"open"}),
            ("09-12 soft books, any snapshot type", SOFT_0912, None),
            ("today's soft books, open read", SOFT_NOW, {"open"})):
        p = props if types is None else props[props["snapshot_type"].isin(types)]
        y = tag_timing(shipped_grader(p, act, soft))
        rows[label] = y
        one = y[y["edge"] >= 0.05]
        paired = one[(one["side"] == "under") | (one["edge"] >= 0.06)]
        print(f"  {label + ' | 5pp':52s} {fmt(cell(one))}")
        print(f"  {label + ' | over 6 / under 5':52s} {fmt(cell(paired))}")
    print("  target (docs/nfl_prop_over_lean.md): 5pp 1,990 / +155.9u / +7.84% (+4.3,+11.4) "
          "2023 +6.4 / 2024 +8.2 / 2025 +10.1;  paired 1,248 / +166.3u / +13.33%")
    y = rows["SHIPPED: 09-12 soft books, open read"]
    for lab, z in (("5pp", y[y["edge"] >= 0.05]),
                   ("paired", y[(y["edge"] >= 0.05) & ((y["side"] == "under") | (y["edge"] >= 0.06))])):
        print(f"  shipped {lab:6s} per season: " + "  ".join(
            f"{s}: {100*z[z.season==s].profit.mean():+.2f}% ({(z.season==s).sum()})" for s in SEASONS)
            + "   sides: " + "  ".join(
            f"{sd} {(z.side==sd).sum()} {100*z[z.side==sd].profit.mean():+.2f}%" for sd in ("over", "under")))

    for lab in ("SHIPPED: 09-12 soft books, open read", "09-12 soft books, any snapshot type"):
        yy = rows[lab]
        print("\n" + "=" * 100)
        print(f"R2. {lab}: split by WHICH QUOTE WAS NEWER (the soft price vs the reference that set the edge)")
        print("    'soft OLDER' = that soft price was no longer on the board when the reference price was read")
        print("=" * 100)
        print(f"  {'cut':>4} {'timing':26s} {HDR}")
        for c in (0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20):
            z = yy[yy["edge"] >= c]
            for k in ("same read", "reference older", "soft OLDER (look-ahead)"):
                print(f"  {int(round(c*100)):>3}p {k:26s} {fmt(cell(z[z['sync'] == k]))}")
    return rows["SHIPPED: 09-12 soft books, open read"]


# ─── PART 1: board-synchronous construction ────────────────────────────────

def decision_boards(props: pd.DataFrame) -> pd.DataFrame:
    """Rows stamped at the latest pre-kick read with lead <= 24h, per (game, market)."""
    pre = props[(props["snapshot_at"] < props["kick"]) & (props["lead_h"] <= CEILING_H)]
    t = pre.groupby(["game_id", "market"])["snapshot_at"].max().rename("T").reset_index()
    b = pre.merge(t, on=["game_id", "market"])
    b = b[b["snapshot_at"] == b["T"]]
    # the same read is sometimes labelled with two snapshot types: one row each
    b = b.drop_duplicates(["game_id", "market", "norm", "line", "bookmaker"], keep="last")
    return b


def candidates(board: pd.DataFrame, refs: tuple[str, ...], soft: tuple[str, ...],
               price_books: tuple[str, ...]) -> pd.DataFrame:
    """One row per (soft book quote, side) with the per-reference edges.
    Keys carry the read's timestamp, so a board may hold many reads and a
    soft quote is only ever compared with a reference on the SAME read."""
    keys = ["game_id", "market", "snapshot_at", "norm", "line"]
    ref = None
    for r in refs:
        q = board[board["bookmaker"] == r][keys + ["over_price", "under_price"]].copy()
        q["fo_" + r], q["fu_" + r] = devig(q["over_price"], q["under_price"])
        q = q[q["fo_" + r].notna()][keys + ["fo_" + r, "fu_" + r]]
        ref = q if ref is None else ref.merge(q, on=keys, how="outer")
    s = board[board["bookmaker"].isin(soft) & ~board["bookmaker"].isin(refs)].copy()
    s["so"], s["su"] = devig(s["over_price"], s["under_price"])
    s = s[s["so"].notna()].merge(ref, on=keys, how="inner")
    # best bettable price on each side at the same line on the same read
    pb = board[board["bookmaker"].isin(price_books)]
    best = pb.assign(po=payout(pb["over_price"].fillna(-1e9)),
                     pu=payout(pb["under_price"].fillna(-1e9)))
    best.loc[pb["over_price"].isna(), "po"] = np.nan
    best.loc[pb["under_price"].isna(), "pu"] = np.nan
    best = best.groupby(keys).agg(best_po=("po", "max"), best_pu=("pu", "max")).reset_index()
    s = s.merge(best, on=keys, how="left")
    out = []
    for side in ("over", "under"):
        f, sp = ("fo_", "so") if side == "over" else ("fu_", "su")
        y = s[keys + ["bookmaker", "lead_h", "season", "week",
                      "over_price", "under_price"]].copy()
        y["side"] = side
        y["own_price"] = s["over_price" if side == "over" else "under_price"]
        y["best_pay"] = s["best_po" if side == "over" else "best_pu"]
        for r in refs:
            y["fair_" + r] = s[f + r]
            y["e_" + r] = s[f + r] - s[sp]
        out.append(y)
    return pd.concat(out, ignore_index=True)


def add_modes(c: pd.DataFrame, refs: tuple[str, ...]) -> pd.DataFrame:
    if len(refs) == 2:
        a, b = c["e_" + refs[0]], c["e_" + refs[1]]
        c["m_" + refs[0]] = a
        c["m_" + refs[1]] = b
        c["m_either"] = pd.concat([a, b], axis=1).max(axis=1)
        c["m_both"] = pd.concat([a, b], axis=1).min(axis=1).where(a.notna() & b.notna())
        fa, fb = c["fair_" + refs[0]], c["fair_" + refs[1]]
        ev_a = fa * (1 + c["best_pay"]) - 1
        ev_b = fb * (1 + c["best_pay"]) - 1
        c["ev_either"] = pd.concat([ev_a, ev_b], axis=1).max(axis=1)
    else:
        c["m_either"] = c["e_" + refs[0]]
        c["ev_either"] = c["fair_" + refs[0]] * (1 + c["best_pay"]) - 1
    return c


def grade(c: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    c = c.merge(act, on=["norm", "game_id", "market"], how="inner")
    c = c[c["actual"].notna() & c["best_pay"].notna()]
    won = np.where(c["side"] == "over", c["actual"] > c["line"], c["actual"] < c["line"])
    push = c["actual"] == c["line"]
    c["push"] = push
    c["profit"] = np.where(push, 0.0, np.where(won, c["best_pay"], -1.0))
    c["profit_own"] = np.where(push, 0.0, np.where(won, payout(c["own_price"]), -1.0))
    return c


def one_per_prop(c: pd.DataFrame, col: str, side_cut: dict | None = None,
                 cut: float | None = None, side: str | None = None,
                 first: bool = False) -> pd.DataFrame:
    """Qualify on the cut(s), then keep ONE candidate per proposition: the
    biggest edge (one read per game), or with first=True the FIRST read on
    which it qualifies and the biggest edge on that read (the 1c lock)."""
    z = c[c[col].notna()]
    if side is not None:
        z = z[z["side"] == side]
    if side_cut is not None:
        z = z[z[col] >= z["side"].map(side_cut)]
    elif cut is not None:
        z = z[z[col] >= cut]
    if first:
        z = z.sort_values(["snapshot_at", col], ascending=[True, False])
    else:
        z = z.sort_values(col, ascending=False)
    return z.drop_duplicates(["game_id", "norm", "market"])


def persistence(sel: pd.DataFrame, props: pd.DataFrame) -> pd.DataFrame:
    """For each selected quote: consecutive pre-kick reads (ending at the
    decision read) on which the SAME book quoted the SAME line at the SAME price
    on the bet's side."""
    pre = props[props["snapshot_at"] < props["kick"]]
    stamps = (pre[["game_id", "market", "snapshot_at"]].drop_duplicates()
              .sort_values("snapshot_at").groupby(["game_id", "market"])["snapshot_at"]
              .apply(list).to_dict())
    k4 = ["game_id", "market", "norm", "bookmaker"]
    need = sel[k4].drop_duplicates()
    hist = pre.merge(need, on=k4)
    q = {}
    listed = set()
    for r in hist.itertuples(index=False):
        q[(r.game_id, r.market, r.norm, r.bookmaker, r.line, r.snapshot_at)] = (r.over_price, r.under_price)
        listed.add((r.game_id, r.market, r.norm, r.bookmaker, r.snapshot_at))
    n_stood, minutes, status = [], [], []
    for r in sel.itertuples(index=False):
        st = stamps.get((r.game_id, r.market), [])
        i = st.index(r.snapshot_at)
        own = r.over_price if r.side == "over" else r.under_price
        n, first, stat = 1, r.snapshot_at, None
        j = i - 1
        while j >= 0:
            v = q.get((r.game_id, r.market, r.norm, r.bookmaker, r.line, st[j]))
            p = None if v is None else (v[0] if r.side == "over" else v[1])
            if p is not None and p == own:
                n += 1
                first = st[j]
                j -= 1
                continue
            if stat is None:
                if (r.game_id, r.market, r.norm, r.bookmaker, st[j]) not in listed:
                    stat = "book not quoting player on prior read"
                else:
                    stat = "book had another line/price on prior read"
            break
        if stat is None:
            stat = "first read of the game" if i == 0 else "stood"
        if n >= 2:
            stat = "stood >= 2 reads"
        n_stood.append(n)
        minutes.append((r.snapshot_at - first).total_seconds() / 60)
        status.append(stat)
    return sel.assign(n_stood=n_stood, stood_min=minutes, stand=status)


# ─── printing ──────────────────────────────────────────────────────────────

def bar(title: str, ch: str = "=") -> None:
    print("\n" + ch * 100)
    print(title)
    if ch == "=":
        print(ch * 100)


def grid(c: pd.DataFrame, col: str, title: str, cuts=CUTS, first=False, mark_strict=True):
    bar(title, "-")
    print(f"  {'cut':>4} | OVER {HDR} | UNDER {HDR} | POOLED {HDR}")
    for x in cuts:
        cells = [cell(one_per_prop(c, col, cut=x, side=s, first=first)) for s in ("over", "under")]
        cells.append(cell(one_per_prop(c, col, cut=x, first=first)))
        tag = ""
        if mark_strict and cells[2]["n"] and cells[2]["n"] / len(SEASONS) <= STRICT_MAX_PER_SEASON:
            tag = " *"
        print(f"  {int(round(x*100)):>3}p | " + " | ".join(fmt(k) for k in cells) + tag)


def split_table(sel_by_cut: dict, labels, title: str):
    bar(title, "-")
    print(f"  {'cut':>4} {'group':24s} {HDR}")
    for x, z in sel_by_cut.items():
        for lab, mask_fn in labels:
            print(f"  {int(round(x*100)):>3}p {lab:24s} {fmt(cell(z[mask_fn(z)]))}")


def splits(c: pd.DataFrame, first: bool, leads, label: str):
    cuts = (0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
    sel = {x: one_per_prop(c, "m_either", cut=x, first=first) for x in cuts}
    split_table(sel, [(m.replace("player_", ""), (lambda z, m=m: z["market"] == m)) for m in GRADED],
                f"{label}: BY MARKET (either, pooled sides)")
    split_table(sel, [(f"lead {a}-{b}h", (lambda z, a=a, b=b: (z.lead_h >= a) & (z.lead_h < b)))
                      for a, b in leads], f"{label}: BY LEAD of the decision read (either, pooled)")
    split_table(sel, [(str(s), (lambda z, s=s: z["season"] == s)) for s in SEASONS],
                f"{label}: BY SEASON (either, pooled)")
    split_table(sel, [("early (weeks 1-9)", lambda z: z["week"] <= 9),
                      ("late (weeks 10+)", lambda z: z["week"] >= 10)],
                f"{label}: EARLY vs LATE season (either, pooled)")
    for side in ("over", "under"):
        sel_s = {x: one_per_prop(c, "m_either", cut=x, side=side, first=first) for x in cuts}
        split_table(sel_s, [(f"{side} {s}", (lambda z, s=s: z["season"] == s)) for s in SEASONS]
                    + [(f"{side} early", lambda z: z["week"] <= 9),
                       (f"{side} late", lambda z: z["week"] >= 10)],
                    f"{label}: BY SEASON and HALF, {side.upper()} only (either)")


def fit_holdout(c: pd.DataFrame, first: bool, label: str, cols: dict | None = None,
                cuts=CUTS, floor: float = 0.04):
    bar(f"{label}: strict-cell choice on FIT seasons 2023-2024 only, then HOLD-OUT 2025 read once")
    cols = cols or {m: "m_" + m for m in MODES}
    fit = c[c["season"].isin(FIT)]
    best, n_cells = None, 0
    for mode, col in cols.items():
        for side in ("over", "under", None):
            for x in cuts:
                z = one_per_prop(fit, col, cut=x, side=side, first=first)
                if len(z) < FIT_MIN_BETS or len(z) / len(FIT) > STRICT_MAX_PER_SEASON:
                    continue
                n_cells += 1
                roi, (lo, hi) = L.boot_ci(z["profit"].values, z["game_id"].values)
                key = (lo, -x)
                if best is None or key > best[0]:
                    best = (key, mode, side, x, len(z), roi, lo, hi)
    print(f"  eligible strict cells (<= {STRICT_MAX_PER_SEASON}/fit season, >= {FIT_MIN_BETS} fit bets): "
          f"{n_cells}")
    if best is None:
        print("  no eligible cell: the hypothesis has no strict cell to hold out")
        return None
    _, mode, side, x, n, roi, lo, hi = best
    print(f"  CHOSEN: reference={mode} side={side or 'pooled'} cut={int(round(x*100))}pp  "
          f"fit {n} bets, ROI {100*roi:+.1f}% (90% CI {100*lo:+.1f}, {100*hi:+.1f})")
    print(f"  {'cut':>4}   FIT 2023-24 {HDR}   ||  HOLD-OUT 2025 {HDR}")
    hold = c[c["season"].isin(HOLD)]
    for d in (-2, -1, 0, 1, 2):
        xx = round(x + d / 100, 2)
        if xx < floor:
            continue
        a = cell(one_per_prop(fit, cols[mode], cut=xx, side=side, first=first))
        b = cell(one_per_prop(hold, cols[mode], cut=xx, side=side, first=first))
        print(f"  {int(round(xx*100)):>3}p   {fmt(a)}   ||  {fmt(b)}" + ("  <- chosen" if d == 0 else ""))
    return mode, side, x


def staleness(sel: pd.DataFrame, props: pd.DataFrame, col: str, title: str, c_all=None):
    bar(title)
    s = persistence(sel, props)
    if c_all is not None:
        k5 = ["game_id", "market", "snapshot_at", "norm", "line", "side"]
        cs = c_all[c_all["m_either"].notna()].sort_values("m_either", ascending=False)
        cs = cs.assign(rk=cs.groupby(k5).cumcount())
        e2 = cs[cs["rk"] == 1][k5 + ["m_either"]].rename(columns={"m_either": "e2"})
        s = s.merge(e2, on=k5, how="left")
    gaps = s.loc[s["n_stood"] >= 2, "stood_min"]
    if len(gaps):
        print(f"  minutes the price had stood, where it stood >= 2 reads: min {gaps.min():.0f}, "
              f"median {gaps.median():.0f}, max {gaps.max():.0f}")
    print(f"  {'cut':>4} {'the soft price on the read(s) before':42s} {HDR}")
    for x in (0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20):
        z = s[s[col] >= x]
        for lab in ("stood >= 2 reads", "book had another line/price on prior read",
                    "book not quoting player on prior read", "first read of the game"):
            print(f"  {int(round(x*100)):>3}p {lab:42s} {fmt(cell(z[z['stand'] == lab]))}")
        print(f"  {int(round(x*100)):>3}p {'stood >= 30 minutes':42s} {fmt(cell(z[z['stood_min'] >= 30]))}")
        if c_all is not None:
            print(f"  {int(round(x*100)):>3}p {'a 2nd bettable book also clears the cut':42s} "
                  f"{fmt(cell(z[z['e2'] >= x]))}")
            print(f"  {int(round(x*100)):>3}p {'lone outlier (no 2nd book clears)':42s} "
                  f"{fmt(cell(z[~(z['e2'] >= x)]))}")
    print("\n  every cut, only prices that STOOD >= 2 reads (>= 30 min):")
    print(f"  {'cut':>4} {HDR}")
    for x in CUTS:
        z = s[(s[col] >= x) & (s["n_stood"] >= 2)]
        print(f"  {int(round(x*100)):>3}p {fmt(cell(z))}")


def main() -> None:
    books = set(L.BETTABLE) | set(REFS) | set(SOFT_0912)
    props = load_props(books)
    act = actuals()
    print(f"prop rows loaded 2023-25 (7 graded markets, needed books): {len(props):,}")
    nm = pd.read_parquet(L.CACHE / "local_nfl_player_game_log.parquet",
                         columns=["player_name", "norm_name"]).drop_duplicates()
    print(f"name normaliser vs the log's own norm_name column: "
          f"{(nm.player_name.map(norm_player_name) == nm.norm_name).mean():.4%} identical")
    print(f"quotes stamped exactly AT kickoff (kept by the shipped grader, dropped in Part 1): "
          f"{int((props.snapshot_at == props.kick).sum())}")

    # ── Part 0 ────────────────────────────────────────────────────────────
    y0 = part0(props, act)
    bar("R3. The SHIPPED grader (open read, asynchronous) on the full cut grid, pooled one per proposition",
        "-")
    print(f"  {'cut':>4} | ALL {HDR} | SAME-READ ONLY {HDR} | SOFT OLDER {HDR}")
    y0p = y0.sort_values("edge", ascending=False).drop_duplicates(["game_id", "norm", "market"])
    for x in CUTS:
        z = y0p[y0p["edge"] >= x]
        print(f"  {int(round(x*100)):>3}p | {fmt(cell(z))} | {fmt(cell(z[z['sync'] == 'same read']))} | "
              f"{fmt(cell(z[z['sync'] == 'soft OLDER (look-ahead)']))}")
    staleness(y0p[y0p["edge"] >= 0.04], props, "edge",
              "STALENESS on the SHIPPED record (open read): did the bet's soft price stand on earlier reads?")

    # ── Part 1 ────────────────────────────────────────────────────────────
    board = decision_boards(props)
    c = grade(add_modes(candidates(board, REFS, tuple(L.BETTABLE), tuple(L.BETTABLE)), REFS), act)
    bar("PART 1. Board-synchronous, latest read with lead <= 24h, BETTABLE books, best price at the line")
    dg = board.drop_duplicates(["game_id", "market"])
    print(f"decision reads: {dg.game_id.nunique()} games; lead of the decision read (game x market): "
          + ", ".join(f"{a}-{b}h {((dg.lead_h >= a) & (dg.lead_h < b)).sum()}" for a, b in LEAD_BUCKETS))
    print(f"graded candidate rows (quote x side): {len(c):,}; pushes among them: {int(c.push.sum())}")
    print("\n  bridge -- the shipped cuts on the Part-1 construction:")
    print(f"  {'':44s} {HDR}")
    for lab, sc in (("either, one 5pp floor", {"over": .05, "under": .05}),
                    ("either, over 6 / under 5 (shipped)", {"over": .06, "under": .05})):
        z = one_per_prop(c, "m_either", side_cut=sc)
        print(f"  {lab:44s} {fmt(cell(z))}")
        print(f"  {lab + ' @ selecting book':44s} {fmt(cell(z.assign(profit=z['profit_own'])))}")
    fit_holdout(c, False, "PART 2 (on Part 1)")
    bar("PART 1 GRIDS, all seasons (descriptive). '*' = strict: <= 30 pooled bets per season")
    for mode in MODES:
        grid(c, "m_" + mode, f"PART 1, reference = {mode}  (edge = ref fair - soft de-vig)")
    splits(c, False, LEAD_BUCKETS, "PART 1")
    staleness(one_per_prop(c, "m_either", cut=0.04), props, "m_either",
              "PART 1 STALENESS (either, pooled)", c_all=c)
    bar("PART 1 EV AXIS: EV = ref fair x decimal(best price) - 1 (either), pooled", "-")
    print(f"  {'EV>=':>5} {HDR}")
    ev_cuts = [v / 100 for v in range(0, 26)]
    for x in ev_cuts:
        print(f"  {int(round(x*100)):>4}% {fmt(cell(one_per_prop(c, 'ev_either', cut=x)))}")
    # ADDED AFTER the pooled EV table above was printed (it pools 2023-25, so
    # the hold-out below is NOT clean: the rule is the same mechanical one as
    # Part 2, but the decision to run it on this axis was taken after seeing
    # the pooled EV curve). Reported as such.
    grid(c, "ev_either", "PART 1 EV AXIS by side (cut = EV, not edge)", cuts=ev_cuts)
    sel_ev = {x: one_per_prop(c, "ev_either", cut=x) for x in (0.03, 0.05, 0.07, 0.08, 0.09, 0.10, 0.12)}
    split_table(sel_ev, [(str(s), (lambda z, s=s: z["season"] == s)) for s in SEASONS]
                + [("early (weeks 1-9)", lambda z: z["week"] <= 9),
                   ("late (weeks 10+)", lambda z: z["week"] >= 10)]
                + [(m.replace("player_", ""), (lambda z, m=m: z["market"] == m)) for m in GRADED],
                "PART 1 EV AXIS: by season, half and market (cut = EV)")
    fit_holdout(c, False, "PART 2 on the EV AXIS (NOT a clean hold-out, see code comment)",
                cols={"either (EV)": "ev_either"}, cuts=ev_cuts, floor=0.0)
    for pref in ("fanduel", "draftkings"):
        soft = tuple(b for b in L.BETTABLE if b != pref)
        pc = grade(add_modes(candidates(board, (pref,), soft, soft), (pref,)), act)
        grid(pc, "m_either", f"PLACEBO (Part 1): reference = {pref}'s own de-vig, betting the other "
                              f"bettable books -- must NOT work", mark_strict=False)
        grid(pc, "ev_either", f"PLACEBO (Part 1) on the EV AXIS: reference = {pref} (cut = EV)",
             cuts=ev_cuts, mark_strict=False)
    del c

    # ── Part 1b ───────────────────────────────────────────────────────────
    allb = props[props["snapshot_at"] < props["kick"]].drop_duplicates(
        ["game_id", "market", "snapshot_at", "norm", "line", "bookmaker"], keep="last")
    cb = grade(add_modes(candidates(allb, REFS, tuple(L.BETTABLE), tuple(L.BETTABLE)), REFS), act)
    leads_b = ((0, 3), (3, 12), (12, 24), (24, 48), (48, 200))
    bar("PART 1b. Synchronous at EVERY read, any lead, locked at the first qualifying read (exploratory)")
    print(f"graded candidate rows: {len(cb):,}")
    fit_holdout(cb, True, "PART 2 (on Part 1b)")
    for mode in MODES:
        grid(cb, "m_" + mode, f"PART 1b, reference = {mode}", first=True)
    splits(cb, True, leads_b, "PART 1b")
    staleness(one_per_prop(cb, "m_either", cut=0.04, first=True), props, "m_either",
              "PART 1b STALENESS (either, pooled)", c_all=cb)
    for pref in ("fanduel", "draftkings"):
        soft = tuple(b for b in L.BETTABLE if b != pref)
        pc = grade(add_modes(candidates(allb, (pref,), soft, soft), (pref,)), act)
        grid(pc, "m_either", f"PLACEBO (Part 1b): reference = {pref}'s own de-vig -- must NOT work",
             first=True, mark_strict=False)


if __name__ == "__main__":
    main()
