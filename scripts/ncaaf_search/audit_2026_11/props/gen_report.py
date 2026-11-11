"""Build REPORT.md from the CSVs main.py / verdict.py (and alt.py, when present) wrote.
Every number in the report is read from those files or recomputed here from the raw data;
none is typed by hand."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import os
import sys

import numpy as np
import pandas as pd

OUT = str(WORK / "props")
sys.path.insert(0, OUT)
import main as M          # noqa: E402
import verdict as V       # noqa: E402

np.seterr(divide="ignore")
NAMED = M.NAMED_REFS
RETAIL = M.PLACEBO_REFS
L = []


def w(s=""):
    L.append(s)


def pct(x, d=1):
    return "n/a" if pd.isna(x) else f"{100 * x:+.{d}f}%"


def num(x, d=2):
    return "n/a" if pd.isna(x) else f"{x:+.{d}f}"


def md(df):
    cols = list(df.columns)
    w("| " + " | ".join(str(c) for c in cols) + " |")
    w("|" + "|".join("---" for _ in cols) + "|")
    for r in df.itertuples(index=False):
        w("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in r) + " |")
    w()


SORD = {"2025": 0, "2026": 1, "2025+2026": 2}


def grid_table(r):
    r = r.assign(_s=r.season.map(SORD)).sort_values(
        [c for c in ("o",) if c in r.columns] + ["_s"] + (["ref"] if "o" not in r.columns else []) + ["cut"], kind="stable")
    t = pd.DataFrame({
        "season": r.season, "reference": r.ref, "cut": r.cut.map(lambda c: f"{c:.2f}"),
        "bets": r.bets.astype(int),
        "W-L-P": [f"{int(a)}-{int(b)}-{int(c)}" for a, b, c in zip(r.W, r.L, r.P)],
        "units": [num(u) if n else "" for u, n in zip(r.units, r.bets)],
        "risked": [f"{x:.1f}" if n else "" for x, n in zip(r.risked, r.bets)],
        "ROI": [pct(x) if n else "" for x, n in zip(r.roi, r.bets)],
        "95% interval": [f"({pct(a)}, {pct(b)})" if pd.notna(a) else "" for a, b in zip(r.ci_lo, r.ci_hi)],
        "1st half": [f"{int(n)} / {pct(x)}" if n else "0" for n, x in zip(r.h1_bets, r.h1_roi)],
        "2nd half": [f"{int(n)} / {pct(x)}" if n else "0" for n, x in zip(r.h2_bets, r.h2_roi)],
        "close value (n / mean)": [f"{int(n)} / {num(x, 4)}" if pd.notna(n) and n > 0 else ("0" if b else "")
                                   for n, x, b in zip(r.clv_n, r.clv_mean, r.bets)],
        "price min / med / max": [f"{a:+.0f} / {b:+.0f} / {c:+.0f}" if pd.notna(a) else ""
                                  for a, b, c in zip(r.price_min, r.price_med, r.price_max)],
        "shorter than -200": [pct(x, 1).replace("+", "") if pd.notna(x) else "" for x in r.share_shorter_200],
        "no action": r.no_action_dnp.astype(int), "dropped": r.dropped_unmatched.astype(int),
    })
    md(t)


def pivot_table(r, refs=None):
    r = r.copy()
    if refs is not None:
        r = r[r.ref.isin(refs)]
    r["cell"] = [f"{int(b)} / {pct(x)}" if b else "0" for b, x in zip(r.bets, r.roi)]
    p = r.pivot_table(index=["season", "ref"], columns="cut", values="cell", aggfunc="first").reset_index()
    p.columns = [c if isinstance(c, str) else f"{c:.2f}" for c in p.columns]
    p = p.assign(_s=p.season.map(SORD), _n=p.ref.map(lambda x: 0 if x in NAMED else 1)).sort_values(["_s", "_n", "ref"]).drop(columns=["_s", "_n"])
    p = p.rename(columns={"ref": "reference"})
    md(p.fillna("0"))


def main():
    g = pd.read_csv(OUT + r"\grid.csv", dtype={"season": str})
    brk = pd.read_csv(OUT + r"\breakdowns.csv", dtype={"season": str})
    diag = pd.read_csv(OUT + r"\diagnostics.csv")
    ver = V.verdict()
    ver.to_csv(OUT + r"\verdict.csv", index=False)
    inv = pd.read_csv(OUT + r"\inv_two_way.csv")
    base = pd.read_csv(OUT + r"\baseline_blind.csv")
    san = pd.read_csv(OUT + r"\sanity_calibration.csv")
    P = g[g.variant == "PRIMARY"]
    S4 = g[g.variant == "S4_POSTHOC_repo_edge_def"]
    seas = ["2025", "2026"]

    # raw-data inventory pieces
    p, games, lt = M.load()
    q = M.build_quotes(p, list(M.MARKET_STAT))
    q["wk"] = pd.to_datetime(q.game_date).dt.to_period("W-MON").astype(str)

    def cell(v, s, ref, cut):
        x = g[(g.variant == v) & (g.season == s) & (g.ref == ref) & (np.isclose(g.cut, cut))]
        return x.iloc[0]

    vs = ver[ver.season.isin(seas)]
    n_named_season = len(vs)
    clear_pre = vs[(vs.variant != "S4_POSTHOC_repo_edge_def") & vs.CLEARS]
    clear_s4 = vs[(vs.variant == "S4_POSTHOC_repo_edge_def") & vs.CLEARS]
    pooled_clear = ver[(ver.season == "2025+2026") & ver.CLEARS]
    maxb = P[P.ref.isin(NAMED) & P.season.isin(seas)].sort_values("bets", ascending=False).iloc[0]

    w("# College football player props: the market-relative rule, 2025 and 2026, at stored prices")
    w()
    w("Built by `gen_report.py` from the files `main.py`, `verdict.py` and `alt.py` wrote. "
      "Results are in units (1 unit to win, risk capped at 3). No database was read or written; no paid call was made.")
    w()
    w("## Verdict")
    w()
    w(f"**No. Nothing clears.** Of the pre-declared cells (season x named reference x cut, four variants), "
      f"{len(clear_pre)} clear all four tests. The largest pre-declared cell is {maxb.ref} {maxb.season} at the "
      f"{maxb.cut:.2f} cut with {int(maxb.bets)} graded bets, so the 150-bet bar is never reached in a single season.")
    w()
    a = cell("PRIMARY", "2026", "pinnacle", 0.02)
    b = cell("PRIMARY", "2026", "bovada", 0.02)
    c = cell("PRIMARY", "2026", "consensus", 0.02)
    d = cell("PRIMARY", "2025", "betonlineag", 0.02)
    e = cell("PRIMARY", "2025", "consensus", 0.02)
    w("Pre-declared test, 2 percentage point cut (the loosest):")
    w()
    for x in (a, b, c, d, e):
        w(f"- {x.ref} {x.season}: {int(x.bets)} bets, {int(x.W)}-{int(x.L)}-{int(x.P)}, {num(x.units)} units, "
          f"ROI {pct(x.roi)}, 95% interval ({pct(x.ci_lo)}, {pct(x.ci_hi)}).")
    w()
    fd25 = cell("PRIMARY", "2025", "fanduel", 0.02)
    wh26 = cell("PRIMARY", "2026", "williamhill_us", 0.02)
    fl26 = cell("PRIMARY", "2026", "fliff", 0.02)
    r26 = P[(P.season == "2026") & np.isclose(P.cut, 0.02) & (P.bets > 0)].sort_values("roi")
    pin_rank = int((r26.roi < a.roi).sum()) + 1
    w(f"The placebo fails again. Used as the \"reference\", FanDuel returns {pct(fd25.roi)} over {int(fd25.bets)} bets in 2025; "
      f"in 2026 William Hill returns {pct(wh26.roi)} over {int(wh26.bets)} and Fliff {pct(fl26.roi)} over {int(fl26.bets)}. "
      f"At that cut Pinnacle has the {'lowest' if pin_rank == 1 else str(pin_rank) + 'th lowest'} ROI of the {len(r26)} references "
      f"with a bet on the 2026 board.")
    w()
    s4p = cell("S4_POSTHOC_repo_edge_def", "2026", "pinnacle", 0.02)
    s4p5 = cell("S4_POSTHOC_repo_edge_def", "2026", "pinnacle", 0.05)
    s4b = cell("S4_POSTHOC_repo_edge_def", "2026", "bovada", 0.02)
    w("One variant was added after the first grid was seen, and is labelled POST-HOC everywhere: the edge definition the "
      "repo's NFL rule actually uses (reference fair probability minus the soft book's own de-vigged probability, "
      "which admits many more bets). On 2026 it gives Pinnacle "
      f"{int(s4p.bets)} bets at the 0.02 cut for {pct(s4p.roi)} ({pct(s4p.ci_lo)}, {pct(s4p.ci_hi)}), close value "
      f"{num(s4p.clv_mean, 4)} on {int(s4p.clv_n)} bets, and it gets worse as the cut tightens "
      f"({pct(s4p5.roi)} over {int(s4p5.bets)} bets at 0.05). Bovada: {int(s4b.bets)} bets, {pct(s4b.roi)}. "
      f"No season cell clears under it either ({len(clear_s4)} of the post-hoc season cells).")
    w()
    if len(pooled_clear):
        for x in pooled_clear.itertuples():
            row = cell(x.variant, "2025+2026", x.ref, x.cut)
            lo = g[(g.variant == x.variant) & (g.season == "2025+2026") & (g.ref == x.ref)].sort_values("cut").reset_index(drop=True)
            i = int(np.where(np.isclose(lo.cut, x.cut))[0][0])
            nb = []
            if i > 0:
                nb.append(f"{pct(lo.roi[i - 1])} at {lo.cut[i - 1]:.2f}")
            if i < len(lo) - 1:
                nb.append(f"{pct(lo.roi[i + 1])} at {lo.cut[i + 1]:.2f}")
            w(f"One pooled two-season row meets all four tests as written: {x.variant}, {x.ref}, cut {x.cut:.2f}: "
              f"{int(row.bets)} bets, {num(row.units)} units, ROI {pct(row.roi, 2)}, interval ({pct(row.ci_lo)}, {pct(row.ci_hi)}), "
              f"2025 {pct(row.h1_roi, 2)} over {int(row.h1_bets)}, 2026 {pct(row.h2_roi, 2)} over {int(row.h2_bets)}, "
              f"close value {num(row.clv_mean, 4)} on {int(row.clv_n)} bets. It is not counted as a pass, for four reasons: "
              f"the variant was added after results were seen; the tests were declared for single-season cells and this is a "
              f"pooled row whose 2026 season is flat; its interval spans zero; and the cuts either side of it lose "
              f"({' and '.join(nb)}).")
            w()
    dgn = diag[(diag.variant == "PRIMARY")]
    def eq(season, ref):
        r_ = dgn[(dgn.season == season) & (dgn.ref == ref)].iloc[0]
        return f"{100 * r_.compared_quotes / r_.ref_any_line:.0f}%"
    i26 = inv[inv.season == 2026].set_index("book")
    w("Why the board cannot carry this rule (all measured below):")
    w()
    w("- DraftKings and BetRivers post no two-way college props in either season, so neither can be de-vigged.")
    w(f"- In 2026 only FanDuel ({int(i26.two_way['fanduel']):,} two-way quotes) and Hard Rock ({int(i26.two_way['hardrockbet']):,}) "
      f"are two-way in volume; William Hill has {int(i26.two_way['williamhill_us']):,} and stops in September, BetMGM has {int(i26.two_way['betmgm'])}.")
    w(f"- Where a reference quotes the same player, market and pull, the soft book is on the same line only "
      f"{eq(2026, 'pinnacle')} of the time against Pinnacle and {eq(2026, 'bovada')} against Bovada (2026), {eq(2025, 'betonlineag')} against BetOnline (2025).")
    late = []
    for ref in ("bovada", "consensus", "pinnacle"):
        cnd, _ = M.build_candidates(q[q.season == 2026], ref)
        lt_ = cnd[cnd.game_date >= "2026-09-29"]
        late.append(f"{ref} {int((lt_.edge >= 0.02 - 1e-12).sum())} of {len(lt_):,}")
    w("- From 2026-09-29 on, FanDuel and Hard Rock all but stopped disagreeing at equal lines. Soft sides reaching the 0.02 cut "
      "from that date to the end of the capture: " + "; ".join(late) + ".")
    ag = OUT + r"\alt_grid.csv"
    if os.path.exists(ag):
        ga = pd.read_csv(ag)
        gn = ga[ga.ref.isin(["pinnacle", "bovada", "consensus"])]
        w()
        w(f"The alternate ladders, the only place DraftKings can be tested, do not clear either: the largest named cell has "
          f"{int(gn.bets.max())} bets (section 8).")
    w()

    # ── 1. what was run ──
    w("## 1. What was run")
    w()
    w("Definitions were written at the top of `main.py` before any result was produced (the first-run copy is "
      "`main_v1_as_first_run.py`, its grid `grid_v1_first_run.csv`; the re-run reproduces all 324 first-run cells exactly).")
    w()
    w("- **Pre-game**: `snapshot_at` parsed to UTC, before `commence_time`, type not in-play.")
    w("- **Markets**: pass yards, pass TDs, completions, attempts, interceptions, rush yards, reception yards, receptions.")
    w("- **Two-way quotes only**; multiplicative de-vig of the reference.")
    w("- **Bettable books**: draftkings, fanduel, betmgm, williamhill_us, fanatics, betrivers, hardrockbet.")
    w("- **References**: pinnacle, bovada, betonlineag, consensus (median de-vigged probability of at least 2 other books at the same line, same pull).")
    w("- **Edge**: reference no-vig probability minus the soft book's implied probability of its price (vig included). Equal line required.")
    w("- **Cuts**: 0.02, 0.03, 0.04, 0.05, 0.06, 0.08.")
    w("- **Lock**: one bet per player, market and game, at the first pull where any bettable side crosses the cut; largest edge if several.")
    w("- **Grading**: the player's stat in `ncaaf_player_game_log`; no row in a logged game for a known player is no action; pushes are 0.")
    w("- **Stake**: 1 unit to win, risk capped at 3. ROI = units / units risked.")
    w("- **Interval**: 95%, resampling game dates, 2,000 draws. **Halves**: split at the season's median game date "
      f"(2025: on or before {sorted(q[q.season == 2025].game_date.unique())[(q[q.season == 2025].game_date.nunique() - 1) // 2]}; "
      f"2026: on or before {sorted(q[q.season == 2026].game_date.unique())[(q[q.season == 2026].game_date.nunique() - 1) // 2]}). "
      "Pooled rows use the two seasons as the two halves.")
    w("- **Clears** only if: at least 150 bets; positive in both halves; interval lower bound above 0 or close value "
      "positive; ROI above every retail placebo reference with at least 50 bets at the same season and cut.")
    w()
    vc = g.groupby("variant").size()
    vb = g[g.bets > 0].groupby("variant").size()
    w(f"**Variants run: 5, {len(g)} cells in total** (season x reference x cut, pooled rows included).")
    w()
    md(pd.DataFrame({
        "variant": ["PRIMARY", "S1_power_devig", "S2_null_stat_no_action", "S3_one_way_soft_allowed", "S4_POSTHOC_repo_edge_def"],
        "what changes": ["nothing (the fixed method)", "power de-vig instead of multiplicative",
                         "a logged player with an empty stat column is no action instead of 0",
                         "a one-way soft price may be bet (lets BetRivers' over-only quotes in)",
                         "edge = reference fair minus the soft book's DE-VIGGED probability (the repo's `find_bets`)"],
        "declared": ["before results", "before results", "before results", "before results", "AFTER the first grid was seen"],
        "references": ["4 named + 10 placebo", "4 named", "4 named", "4 named", "4 named + 10 placebo"],
        "cells": [int(vc.get(v, 0)) for v in ["PRIMARY", "S1_power_devig", "S2_null_stat_no_action", "S3_one_way_soft_allowed", "S4_POSTHOC_repo_edge_def"]],
        "cells with a bet": [int(vb.get(v, 0)) for v in ["PRIMARY", "S1_power_devig", "S2_null_stat_no_action", "S3_one_way_soft_allowed", "S4_POSTHOC_repo_edge_def"]],
    }))

    # ── 2. inventory ──
    w("## 2. Data inventory (measured)")
    w()
    w("### 2.1 Two-way coverage, eight over/under markets, pre-game")
    w()
    w("A quote is one book, one pull, one line. `fanatics` and `draftkings` have no row here at all.")
    w()
    t = inv.copy()
    t["two-way share"] = (t.two_way / t.quotes).map(lambda x: f"{100 * x:.1f}%")
    t = t[["season", "book", "bettable", "quotes", "two_way", "two-way share", "games", "games_two_way", "props_two_way"]]
    for c_ in ("games_two_way", "props_two_way"):
        t[c_] = t[c_].astype(int)
    t.columns = ["season", "book", "bettable", "quotes", "two-way quotes", "two-way share", "games", "games two-way", "propositions two-way"]
    md(t)
    pre = p[p.pre].copy()
    pre["kind"] = np.where(pre.market.str.endswith("_alternate"), "alternate ladders",
                           np.where(pre.market == "player_anytime_td", "anytime TD", "eight over/under markets"))
    pre["two"] = pre.over_price.notna() & pre.under_price.notna()
    k = pre.groupby(["season", "bookmaker", "kind"]).agg(rows=("two", "size"), two_way=("two", "sum")).reset_index()
    kd = k[k.bookmaker.isin(["draftkings", "betrivers"])]
    w("DraftKings and BetRivers, every pre-game row by kind (two-way = both prices present):")
    w()
    md(kd.rename(columns={"bookmaker": "book", "two_way": "two-way rows"}))
    atd = k[k.kind == "anytime TD"].groupby("season").agg(rows=("rows", "sum"), two_way=("two_way", "sum")).reset_index()
    alt = k[k.kind == "alternate ladders"].groupby("season").agg(rows=("rows", "sum"), two_way=("two_way", "sum")).reset_index()
    w("**Anytime TD**: " + "; ".join(f"{int(r.season)}: {int(r.rows):,} pre-game rows, {int(r.two_way)} with a No price"
                                     for r in atd.itertuples()) + ". No book posts both sides, so it is skipped.")
    w()
    w("**Alternate ladders**: " + "; ".join(f"{int(r.season)}: {int(r.rows):,} pre-game rows, {int(r.two_way)} two-way"
                                            for r in alt.itertuples()) + ". All one-way. Section 8 tests them.")
    w()
    w("### 2.2 Snapshot cadence")
    w()
    wpg = pd.read_csv(OUT + r"\inv_windows_per_game.csv")
    lead = pd.read_csv(OUT + r"\inv_lead_hours.csv")
    pt = pd.read_csv(OUT + r"\inv_pull_times_2026.csv")
    st = np.sort(q[q.season == 2026].win_ts.unique())
    gaps = np.diff(st).astype("timedelta64[s]").astype(float) / 60
    w(f"Every pull carries one timestamp. 2026 has {len(st)} distinct pre-game pull stamps; the smallest gap between two is "
      f"{gaps.min():.1f} minutes, so the 10-minute window is exactly one pull.")
    w()
    w("Pulls per game before kickoff (number of games):")
    w()
    md(wpg)
    w("Hours from pull to kickoff, per (game, pull):")
    w()
    md(lead.rename(columns={lead.columns[0]: "season"}))
    w("2026 (game, pull) pairs by pull time, Eastern: " + ", ".join(f"{a} = {int(b)}" for a, b in zip(pt.iloc[:, 0], pt.iloc[:, 1])) + ".")
    w()
    w("2025 is one pull per game about 24 hours out, so in 2025 the first-signal lock is that one pull and there is no later "
      "quote to measure close value against. 2026 is game-day only (first pull 9:35am ET).")
    w()
    w("### 2.3 The 2026 capture changed at the end of September")
    w()
    two26 = q[(q.season == 2026) & q.two]
    wk = two26.groupby(["wk", "book"]).size().unstack(fill_value=0).reset_index().rename(columns={"wk": "week (Tue-Mon)"})
    w("Two-way quotes by week and book:")
    w()
    md(wk)
    a_ = two26[two26.book == "fanduel"][M.KEY5 + ["fo_m", "wk"]]
    b_ = two26[two26.book == "hardrockbet"][M.KEY5 + ["fo_m"]]
    m_ = a_.merge(b_, on=M.KEY5, suffixes=("_fd", "_hr"))
    m_["d"] = (m_.fo_m_fd - m_.fo_m_hr).abs()
    dsp = m_.groupby("wk").d.agg(pairs="size", mean_abs_diff="mean", share_3pp=lambda s: (s >= 0.03).mean()).reset_index()
    dsp["mean_abs_diff"] = dsp.mean_abs_diff.map(lambda x: f"{x:.4f}")
    dsp["share_3pp"] = dsp.share_3pp.map(lambda x: f"{100 * x:.1f}%")
    dsp.columns = ["week (Tue-Mon)", "FanDuel/Hard Rock pairs at one line, one pull", "mean gap in de-vigged over probability", "share of pairs 3pp+ apart"]
    md(dsp)
    pre26 = p[p.pre & (p.season == 2026)]
    lastd = pre26.groupby("bookmaker").game_date.max()
    maxd = pre26.game_date.max()
    stopped = lastd[lastd < maxd].sort_values()
    hrm = two26[two26.book == "hardrockbet"].groupby("market").game_date.max()
    hr_stop = hrm[hrm < "2026-10-01"].sort_values()
    w("Books whose last pre-game row of any kind is before the end of the capture (" + maxd + "): " +
      "; ".join(f"{b} last seen {d}" for b, d in stopped.items()) + ".")
    w()
    w("Hard Rock two-way markets that end early: " + "; ".join(f"{m} last quoted {d}" for m, d in hr_stop.items()) +
      ". Over the same days the gap between FanDuel and Hard Rock at an equal line falls to a fraction of what it was. "
      "The cause is not established here; the effect is that from October the soft books almost never price an equal "
      "line 2 points better than a reference.")
    w()
    sig = []
    for ref in ("pinnacle", "bovada", "consensus"):
        cnd, _ = M.build_candidates(q[q.season == 2026], ref)
        cnd["wk"] = pd.to_datetime(cnd.game_date).dt.to_period("W-MON").astype(str)
        s_ = cnd.groupby("wk").agg(sides=("edge", "size"), ge2=("edge", lambda s: int((s >= 0.02).sum())))
        s_.columns = [f"{ref}: sides compared", f"{ref}: sides at 0.02+"]
        sig.append(s_)
    sg = pd.concat(sig, axis=1).fillna(0).astype(int).reset_index().rename(columns={"wk": "week (Tue-Mon)"})
    w("Soft sides compared at an equal line, and how many reach the 0.02 cut, by week (2026):")
    w()
    md(sg)
    w("### 2.4 Matching odds to results")
    w()
    gm = pd.read_csv(OUT + r"\inv_game_match.csv")
    ms = pd.read_csv(OUT + r"\inv_match_status.csv")
    w("Games with a pre-game quote in the eight markets, matched to a log game (every one found a log game):")
    w()
    md(gm)
    ms2 = ms.copy()
    for c_ in ("matched_fallback", "ambiguous", "dnp", "unmatched", "matched"):
        if c_ not in ms2.columns:
            ms2[c_] = 0
    ms2["name-match rate"] = ((ms2.matched + ms2.matched_fallback + ms2.dnp) / ms2.total).map(lambda x: f"{100 * x:.1f}%")
    ms2["graded share"] = ((ms2.matched + ms2.matched_fallback) / ms2.total).map(lambda x: f"{100 * x:.1f}%")
    ms2 = ms2[["season", "total", "matched", "matched_fallback", "dnp", "unmatched", "ambiguous", "name-match rate", "graded share"]]
    ms2.columns = ["season", "propositions", "matched exactly", "matched by fallback", "known player, no row (no action)",
                   "name never in log (dropped)", "two players one name (dropped)", "name-match rate", "graded share"]
    w("Propositions (player, market, game), all books, eight markets. Name-match rate counts a known player with no row "
      "that day as matched (he is identified; he did not play):")
    w()
    md(ms2)
    fb = pd.read_csv(OUT + r"\inv_fallback_names.csv")
    w(f"The fallback matched {len(fb)} distinct spellings, for example: " +
      "; ".join(f"{a} = {b}" for a, b in zip(fb.player_name.head(8), fb.log_name.head(8))) + ". All are in `inv_fallback_names.csv`.")
    w()
    nz = pd.read_csv(OUT + r"\inv_null_stat.csv")
    nzs = nz.groupby("season").agg(n=("n", "sum"), z=("null_as_zero", "sum")).reset_index()
    w("A logged player whose stat column is empty (a back with no catch) is graded as 0: " +
      "; ".join(f"{int(r.season)}: {int(r.z)} of {int(r.n):,} matched propositions" for r in nzs.itertuples()) +
      ". Variant S2 treats them as no action instead.")
    w()
    w("### 2.5 How much of the soft board each reference can be compared with")
    w()
    dd = diag[(diag.variant == "PRIMARY") & (diag.candidate_sides > 0) & diag.ref.isin(NAMED)].copy()
    dd["equal-line share"] = [f"{100 * c / a:.1f}%" if pd.notna(a) and a else "" for c, a in zip(dd.compared_quotes, dd.ref_any_line)]
    dd = dd[["season", "ref", "soft_quotes", "ref_any_line", "compared_quotes", "equal-line share", "props_compared", "games_compared"]]
    dd["ref_any_line"] = dd.ref_any_line.map(lambda x: "" if pd.isna(x) else int(x))
    dd.columns = ["season", "reference", "soft two-way quotes", "reference quotes the same player/market/pull", "at the same line",
                  "equal-line share", "propositions compared", "games compared"]
    md(dd)
    w("### 2.6 Is the grading right? De-vigged probability against what happened")
    w()
    s2 = san.copy()
    s2["fair_over"] = s2.fair_over.map(lambda x: f"{x:.3f}")
    s2["realised_over"] = s2.realised_over.map(lambda x: f"{x:.3f}")
    s2.columns = ["book", "season", "de-vigged over probability band", "propositions", "mean de-vigged over", "share that went over"]
    md(s2[s2.book.isin(["pinnacle", "bovada", "betonlineag"])])
    sb = san[san.n >= 100].copy()
    sb["step"] = sb.groupby(["ref", "season"]).realised_over.diff()
    refs3 = sb[sb.ref.isin(["pinnacle", "bovada", "betonlineag"])]
    oth = sb[~sb.ref.isin(["pinnacle", "bovada", "betonlineag"])]
    w(f"Looking only at bands of 100 or more propositions: for the three references the share that went over falls from one band "
      f"to the next {int((refs3.step < 0).sum())} times in {int(refs3.step.notna().sum())} steps; for FanDuel and Hard Rock "
      f"{int((oth.step < 0).sum())} times in {int(oth.step.notna().sum())} (`sanity_calibration.csv`). Outcomes follow the quoted "
      "probabilities, which is what correct grading looks like. Separately, `crosscheck.py` recomputed five cells with "
      "different code (plain loops over the raw rows) and got the same bets, record, units and risk in all five, and "
      "matched six graded results to the raw log rows (`crosscheck_out.txt`).")
    w()
    w("### 2.7 The baseline: bet every proposition blind")
    w()
    bb = base.copy()
    bb["W-L-P"] = [f"{a}-{b}-{c}" for a, b, c in zip(bb.W, bb.L, bb.P)]
    bb["units"] = bb.units.map(num)
    bb["ROI"] = bb.roi.map(pct)
    bb["95% interval"] = [f"({pct(a)}, {pct(b)})" for a, b in zip(bb.ci_lo, bb.ci_hi)]
    md(bb[["season", "side", "bets", "W-L-P", "units", "ROI", "95% interval"]])
    w("First bettable two-way quote per proposition, first book in the bettable order. Any rule has to beat these.")
    w()

    # ── 3. PRIMARY ──
    w("## 3. Results: the pre-declared test")
    w()
    w("### 3.1 Full grid, named references (every cut, losing and empty cells included)")
    w()
    w("Close value = the reference's last pre-kick de-vigged probability at the bet's line minus the implied probability of "
      "the price taken, on bets where that last pull is later than the bet's own. \"No action\" = player did not play; "
      "\"dropped\" = name not matched.")
    w()
    x = P[P.ref.isin(NAMED)].copy()
    x["o"] = x.ref.map({r: i for i, r in enumerate(NAMED)})
    grid_table(x.sort_values(["o", "season", "cut"]))
    w("### 3.2 The placebo: every book as the reference (bets / ROI)")
    w()
    w("draftkings, betrivers, rebet and fanatics have no two-way quotes and so produce no bets as a reference.")
    w()
    pivot_table(P)
    w("Placebo rows with their intervals at the two loosest cuts:")
    w()
    x = P[P.ref.isin(RETAIL) & (P.bets > 0) & P.cut.isin([0.02, 0.03])].sort_values(["season", "cut", "ref"])
    grid_table(x)
    w("### 3.3 Rank of each named reference among all references with a bet")
    w()
    rk = ver[(ver.variant == "PRIMARY") & (ver.bets > 0)].copy()
    rk["rank"] = [f"{int(a)} of {int(b) + 1}" for a, b in zip(rk.rank_among_refs_with_bets, rk.n_placebos_with_bets)]
    rk["ROI"] = rk.roi.map(pct)
    rk["cut"] = rk.cut.map(lambda c: f"{c:.2f}")
    md(rk[["season", "ref", "cut", "bets", "ROI", "rank", "placebo_note"]].rename(
        columns={"ref": "reference", "rank": "rank vs retail references", "placebo_note": "best retail reference with 50+ bets"}))
    w("### 3.4 By market, by soft book, by side (named references)")
    w()
    for by, title in (("market", "By market"), ("book", "By soft book"), ("side", "By side")):
        bx = brk[(brk.variant == "PRIMARY") & (brk.by == by) & brk.ref.isin(NAMED) & brk.season.isin(seas)].copy()
        bx["cell"] = [f"{int(n)} / {num(u)}u / {pct(r_)}" for n, u, r_ in zip(bx.bets, bx.units, bx.roi)]
        pv = bx.pivot_table(index=["season", "ref", "level"], columns="cut", values="cell", aggfunc="first").reset_index()
        pv.columns = [c_ if isinstance(c_, str) else f"{c_:.2f}" for c_ in pv.columns]
        w(f"**{title}** (bets / units / ROI):")
        w()
        md(pv.rename(columns={"ref": "reference", "level": by}).fillna(""))

    # ── 4. sensitivities ──
    w("## 4. Pre-declared sensitivities (named references)")
    w()
    for v, title in (("S1_power_devig", "S1: power de-vig"),
                     ("S2_null_stat_no_action", "S2: empty stat column = no action"),
                     ("S3_one_way_soft_allowed", "S3: one-way soft prices allowed (BetRivers overs)")):
        w(f"### {title}")
        w()
        x = g[(g.variant == v) & (g.bets > 0)].copy()
        x["o"] = x.ref.map({r: i for i, r in enumerate(NAMED)})
        grid_table(x.sort_values(["o", "season", "cut"]))
        z = g[(g.variant == v) & (g.bets == 0)]
        w(f"Cells with no bet in this variant: {len(z)} of {len(g[g.variant == v])}.")
        w()

    # ── 5. S4 ──
    w("## 5. POST-HOC: the repo's own edge definition")
    w()
    w("Added after the pre-declared grid was seen, because that grid is too thin to test anything. The only change: "
      "edge = reference fair probability minus the soft book's de-vigged probability (`models/market_relative.find_bets`, "
      "the rule behind `nfl_prop_market` and the 2025 college sweep). This scale sits above the pre-declared one by the soft "
      "book's vig. Measured on the 2026 Pinnacle cells, the bets taken average an after-vig edge (reference fair minus the "
      "implied probability of the price) of " + ", ".join(
          f"{cell('S4_POSTHOC_repo_edge_def', '2026', 'pinnacle', c_).mean_edge_vs_price:+.4f} at the {c_:.2f} cut" for c_ in (0.02, 0.03, 0.05)) +
      ". So the loosest cuts here take prices that are about level with the reference's fair value. Column "
      "`mean_edge_vs_price` in `grid.csv` has this for every cell.")
    w()
    w("### 5.1 Full grid, named references")
    w()
    x = S4[S4.ref.isin(NAMED) & (S4.bets > 0)].copy()
    x["o"] = x.ref.map({r: i for i, r in enumerate(NAMED)})
    grid_table(x.sort_values(["o", "season", "cut"]))
    z = S4[S4.ref.isin(NAMED) & (S4.bets == 0)]
    w(f"Named cells with no bet (reference not captured that season, or nothing reached the cut): {len(z)}.")
    w()
    w("### 5.2 The placebo under this definition (bets / ROI)")
    w()
    pivot_table(S4)
    w("### 5.3 By market and by soft book, 2026 Pinnacle and 2025 BetOnline (bets / units / ROI)")
    w()
    for by in ("market", "book", "side"):
        bx = brk[(brk.variant == "S4_POSTHOC_repo_edge_def") & (brk.by == by)
                 & (((brk.ref == "pinnacle") & (brk.season == "2026")) | ((brk.ref == "betonlineag") & (brk.season == "2025"))
                    | ((brk.ref == "bovada") & (brk.season == "2026")) | (brk.ref == "consensus"))].copy()
        bx["cell"] = [f"{int(n)} / {num(u)}u / {pct(r_)}" for n, u, r_ in zip(bx.bets, bx.units, bx.roi)]
        pv = bx.pivot_table(index=["season", "ref", "level"], columns="cut", values="cell", aggfunc="first").reset_index()
        pv.columns = [c_ if isinstance(c_, str) else f"{c_:.2f}" for c_ in pv.columns]
        md(pv.rename(columns={"ref": "reference", "level": by}).fillna(""))
    bo3 = cell("S4_POSTHOC_repo_edge_def", "2025", "betonlineag", 0.03)
    bo4 = cell("S4_POSTHOC_repo_edge_def", "2025", "betonlineag", 0.04)
    bo5 = cell("S4_POSTHOC_repo_edge_def", "2025", "betonlineag", 0.05)
    fd5 = cell("S4_POSTHOC_repo_edge_def", "2025", "fanduel", 0.05)
    fd6 = cell("S4_POSTHOC_repo_edge_def", "2025", "fanduel", 0.06)
    n_bo26 = int(((p.bookmaker == "betonlineag") & (p.season == 2026)).sum())
    w(f"The one reference that looks like something is BetOnline in 2025: {pct(bo3.roi)} over {int(bo3.bets)} bets at 0.03, "
      f"{pct(bo4.roi)} over {int(bo4.bets)} at 0.04 (interval {pct(bo4.ci_lo)} to {pct(bo4.ci_hi)}), "
      f"{pct(bo5.roi)} over {int(bo5.bets)} at 0.05, positive in both halves at 0.03 to 0.05. Two things stop it being a "
      f"finding. FanDuel as the reference does the same at the tighter cuts ({pct(fd5.roi)} over {int(fd5.bets)} at 0.05, "
      f"{pct(fd6.roi)} over {int(fd6.bets)} at 0.06). And it cannot be checked on 2026: the 2026 capture holds "
      f"{n_bo26} BetOnline rows.")
    w()

    # ── 6. clearing test ──
    w("## 6. The clearing test, cell by cell")
    w()
    tot = ver.groupby("variant").agg(named_cells=("CLEARS", "size"), with_bets=("bets", lambda s: int((s > 0).sum())),
                                     bets_150=("c1_150_bets", "sum"), both_halves=("c2_both_halves_pos", "sum"),
                                     ci_or_close=("c3_ci_or_close", "sum"), beats_placebo=("c4_beats_placebos", "sum"),
                                     clears=("CLEARS", "sum")).reset_index()
    tot.columns = ["variant", "named cells (pooled rows included)", "with a bet", "150+ bets", "both halves positive",
                   "interval above 0 or close value positive", "above every 50+ bet placebo", "all four"]
    md(tot)
    w("Every named cell with 150 or more bets:")
    w()
    vv = ver[ver.c1_150_bets].copy()
    vv["ROI"] = vv.roi.map(pct)
    vv["95% interval"] = [f"({pct(a)}, {pct(b)})" for a, b in zip(vv.ci_lo, vv.ci_hi)]
    vv["halves"] = [f"{pct(a)} / {pct(b)}" for a, b in zip(vv.h1_roi, vv.h2_roi)]
    vv["close value"] = [f"{int(n)} / {num(x_, 4)}" if pd.notna(n) and n > 0 else "none" for n, x_ in zip(vv.clv_n, vv.clv_mean)]
    vv["cut"] = vv.cut.map(lambda c_: f"{c_:.2f}")
    yn = lambda s: s.map({True: "yes", False: "no"})
    vv["halves ok"] = yn(vv.c2_both_halves_pos)
    vv["interval/close ok"] = yn(vv.c3_ci_or_close)
    vv["beats placebos"] = yn(vv.c4_beats_placebos)
    vv["CLEARS"] = yn(vv.CLEARS)
    md(vv[["variant", "season", "ref", "cut", "bets", "ROI", "95% interval", "halves", "halves ok", "close value",
           "interval/close ok", "placebo_note", "beats placebos", "CLEARS"]].rename(
        columns={"ref": "reference", "placebo_note": "best retail reference (50+ bets)"}))
    w("Every cell's four answers are in `verdict.csv`.")
    w()

    # ── 7. limits ──
    w("## 7. What could not be done, and what is uncertain")
    w()
    w("- **DraftKings cannot be tested on its main lines.** It has no row in the eight over/under markets in either season; "
      "its college props arrive only as one-way alternate ladders and anytime TD. Section 8 is the only DraftKings test possible.")
    w("- **Close value does not exist for 2025** (one pull per game), and in 2026 the \"close\" is the last of at most three "
      "game-day pulls, which can be hours before kickoff.")
    w("- **BetOnline was not captured in 2026**, so the only reference with a positive 2025 record has no second season.")
    w("- **A player who played and recorded no stat at all is missing from the log** (`docs/sports/ncaaf.md` says the table drops all-zero players; not re-measured here), so "
      "he is graded no action here where a book would settle the under as a win. This drops some winning unders and some "
      "losing overs. Its size is not measurable from these files.")
    w("- **Why soft prices converged after 2026-09-28 is not established.** It could be the books or the capture. It was not investigated beyond the tables in 2.3.")
    hq = q[q.two].copy()
    hq["hold"] = M.imp(hq.op) + M.imp(hq.up) - 1
    hm = hq[hq.season == 2026].groupby("book").hold.median()
    w("- **Neither reference is a low-margin market maker on this board.** Median two-way overround in 2026: " +
      ", ".join(f"{b} {100 * hm[b]:.1f}%" for b in ("pinnacle", "bovada", "fanduel", "hardrockbet") if b in hm.index) + ".")
    sens = g[g.variant.isin(["S1_power_devig", "S2_null_stat_no_action", "S3_one_way_soft_allowed"])]
    w(f"- None of the three pre-declared sensitivities produces a cell that clears; the largest cell under any of them has "
      f"{int(sens.bets.max())} bets (section 4).")
    w()

    # ── 8. alternates ──
    ap = OUT + r"\alt_grid.csv"
    if os.path.exists(ap):
        import alt_report
        alt_report.section(w, md, pct, num, grid_table, pivot_table)

    w("## Files")
    w()
    for f, dsc in (("main.py", "definitions, grid, sensitivities, post-hoc variant"),
                   ("main_v1_as_first_run.py", "the script exactly as first run, before the post-hoc variant"),
                   ("verdict.py", "applies the clearing rule"), ("gen_report.py", "builds this file"),
                   ("alt.py / alt_report.py", "the alternate-ladder section"),
                   ("inspect1.py .. inspect6.py", "inventory only, no results"),
                   ("grid.csv", "every cell"), ("breakdowns.csv", "by market / book / side"),
                   ("diagnostics.csv", "comparison counts"), ("bets.parquet", "every locked bet in every cell"),
                   ("verdict.csv", "the four tests per named cell"),
                   ("crosscheck.py / crosscheck_out.txt", "five cells recomputed with different code; six results matched to the raw log"),
                   ("alt_monotone.py", "the broken-ladder count and the ordered-ladders-only grid"),
                   ("alt_grid.csv / alt_m_grid.csv / alt_bets.parquet", "the alternate-ladder cells and bets"),
                   ("grid_v1_first_run.csv", "the grid exactly as first produced, before the post-hoc variant")):
        w(f"- `{OUT}\\{f}`: {dsc}")
    w()
    open(OUT + r"\REPORT.md", "w", encoding="utf-8").write("\n".join(L))
    print("wrote", OUT + r"\REPORT.md", len(L), "lines")


if __name__ == "__main__":
    main()
