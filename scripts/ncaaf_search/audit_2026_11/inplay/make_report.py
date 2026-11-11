"""Builds REPORT.md from the JSON the scripts wrote, so every number in a table
is the number a script printed."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import json
from pathlib import Path

OUT = WORK / "inplay"
res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
var = json.loads((OUT / "variants.json").read_text(encoding="utf-8"))
night = json.loads((OUT / "night.json").read_text(encoding="utf-8"))
diag = json.loads((OUT / "diag.json").read_text(encoding="utf-8"))
num = json.loads((OUT / "numbers.json").read_text(encoding="utf-8"))

RULES = ("totals_H1", "totals_H2", "h2h_H1", "h2h_H2")
NAME = {"totals_H1": "Total, first half", "totals_H2": "Total, second half",
        "h2h_H1": "Moneyline, first half", "h2h_H2": "Moneyline, second half"}
CUTS = (0.02, 0.05, 0.08, 0.12, 0.2)
TEST = {"A": "A: fit 2025, test 2026", "B1": "B1: fit 2025 weeks 1-7, test weeks 8+",
        "B2": "B2: fit 2025 weeks 8+, test weeks 1-7"}
VAR = {"V1": "as asked", "V2": "wait and confirm", "V3": "no look-ahead"}


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:+.{d}f}%"


def cells(src, test, v):
    return {(c["rule"], round(c["cut"], 2)): c for c in src[test][v]["cells"]}


def grid_table(src, test, v):
    cs = cells(src, test, v)
    out = ["| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | "
           "Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in RULES:
        for c in CUTS:
            x = cs[(r, c)]
            if not x["bets"]:
                out.append(f"| {NAME[r]} | {c:.2f} | 0 | | | | | | | | | | | | | |")
                continue
            out.append(
                f"| {NAME[r]} | {c:.2f} | {x['bets']} | {x['w']}-{x['l']}-{x['p']} | {x['units']:+.2f} | {x['risked']:.2f} | "
                f"{pct(x['roi'])} | {pct(x['ci_lo'])} .. {pct(x['ci_hi'])} | {pct(x['early_roi'])} on {x['early_n']} | "
                f"{pct(x['late_roi'])} on {x['late_n']} | {x['price_min']:+.0f} / {x['price_med']:+.0f} / {x['price_max']:+.0f} | "
                f"{x['dominant']} ({x['sides'][x['dominant']]} of {x['bets']}) | {pct(x.get('blind_same_side'))} | "
                f"{pct(x.get('placebo_mean'))} | {pct(x.get('placebo_p95'))} | {x.get('placebo_runs_above')} of 200 |")
    return "\n".join(out)


def bars_table(src, v):
    a, b1, b2 = cells(src, "A", v), cells(src, "B1", v), cells(src, "B2", v)
    out = ["| Rule | EV cut | A bets | A return | A interval | A placebo 95th | B1 return (bets) | B2 return (bets) | "
           ">= 100 bets in A | A > 0 | B1 > 0 | B2 > 0 | Interval above 0, or above placebo 95th | Clears all |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    passed = []
    for r in RULES:
        for c in CUTS:
            x, y, z = a[(r, c)], b1[(r, c)], b2[(r, c)]
            k1 = x["bets"] >= 100
            k2 = x["roi"] > 0
            k3 = y["roi"] > 0
            k4 = z["roi"] > 0
            k5 = (x["ci_lo"] > 0) or (x["roi"] > x["placebo_p95"])
            ok = k1 and k2 and k3 and k4 and k5
            if ok:
                passed.append((r, c))
            yn = lambda k: "yes" if k else "no"
            out.append(f"| {NAME[r]} | {c:.2f} | {x['bets']} | {pct(x['roi'])} | {pct(x['ci_lo'])} .. {pct(x['ci_hi'])} | "
                       f"{pct(x['placebo_p95'])} | {pct(y['roi'])} ({y['bets']}) | {pct(z['roi'])} ({z['bets']}) | "
                       f"{yn(k1)} | {yn(k2)} | {yn(k3)} | {yn(k4)} | {yn(k5)} | {'YES' if ok else 'no'} |")
    return "\n".join(out), passed


def cal_table(d):
    out = ["| Target | Share of regulation left | States | Mean error (final - model), points | Realised sd | Model sd | Spread ratio | Within 1 sd |",
           "|---|---|---|---|---|---|---|---|"]
    for r in d:
        out.append(f"| {r['target']} | {r['share_left']} | {r['states']:,} | {r['mean_err']:+.3f} | {r['realised_sd']:.2f} | "
                   f"{r['model_sd']:.2f} | {r['spread_ratio']:.3f} | {r.get('cover_68', '')} |")
    return "\n".join(out)


def cal_table_fb(d):
    out = ["| Target | Share of regulation left | States | Mean error, points | Spread ratio | Share of finals above the model's mean |",
           "|---|---|---|---|---|---|"]
    for r in d:
        out.append(f"| {r['target']} | {r['share_left']} | {r['states']:,} | {r['mean_err']:+.3f} | {r['spread_ratio']:.3f} | "
                   f"{r['final_above_mean']:.3f} |")
    return "\n".join(out)


def elig_table():
    keys = list(res["eligibility"]["2026 live"].keys())
    label = {"quotes": "quotes kept (section above)", "games": "games those quotes are on",
             "no final or no prior (games)": "games with no final or no pre-game line",
             "no final or no prior": "dropped: no final or no pre-game line",
             "state not known at the stamp": "dropped: no state known on both sides of the stamp",
             "of which on games with no state source at all": "... of which on games with no state source at all",
             "ELIGIBLE V1": "**eligible, as asked**",
             "V2: a score becomes known within 240 s after (or its bracket is open)":
                 "wait and confirm drops: a score becomes known within 240 s after the stamp (or its bracket is open)",
             "V2: older than 90 s at the fetch, not halftime": "wait and confirm drops: older than 90 s when received, not halftime",
             "ELIGIBLE V2": "**eligible, wait and confirm**"}
    out = ["| Step | 2025 replay | 2026 live |", "|---|---|---|"]
    for k in keys:
        a, b = res["eligibility"]["2025 replay"][k], res["eligibility"]["2026 live"][k]
        name = label.get(k.strip(), "dropped: " + k.strip())
        out.append(f"| {name} | {a:,} | {b:,} |")
    return "\n".join(out)


def per_rule_eligible():
    out = ["| Test | Eligibility | " + " | ".join(NAME[r] for r in RULES) + " |", "|---|---|---|---|---|---|"]
    for t in ("A", "B1", "B2"):
        for v in ("V1", "V2"):
            e = res[t][v]["eligible"]
            out.append(f"| {TEST[t]} | {VAR[v]} | " + " | ".join(f"{e[r]['quotes']:,} quotes, {e[r]['games']} games" for r in RULES) + " |")
    e = var["plain"]["A"]["V3"]["eligible"]
    out.append(f"| {TEST['A']} | {VAR['V3']} | " + " | ".join(f"{e[r]['quotes']:,} quotes, {e[r]['games']} games" for r in RULES) + " |")
    return "\n".join(out)


def blind_table():
    out = ["| Test | Eligibility | Rule | Over / home: bets, return | Under / away: bets, return |", "|---|---|---|---|---|"]
    for t, src, vs in (("A", res, ("V1", "V2")), ("B1", res, ("V1", "V2")), ("B2", res, ("V1", "V2"))):
        for v in vs:
            b = src[t][v]["blind"]
            for r in RULES:
                a_, b_ = ("over", "under") if r.startswith("totals") else ("home", "away")
                x, y = b[f"{r}|{a_}"], b[f"{r}|{b_}"]
                out.append(f"| {t} | {VAR[v]} | {NAME[r]} | {x['bets']}, {pct(x['roi'])} | {y['bets']}, {pct(y['roi'])} |")
    return "\n".join(out)


def info_table():
    out = ["| Test | Eligibility | Rule | Quotes | Games | Weight on the market price | Weight on the model | 95% interval of the model's weight | Slope on the model alone |",
           "|---|---|---|---|---|---|---|---|---|"]
    for t in ("A", "B1", "B2"):
        for v in ("V1", "V2"):
            for r in RULES:
                i = diag[t][v]["info"][r]
                out.append(f"| {t} | {VAR[v]} | {NAME[r]} | {i['quotes']:,} | {i['games']} | {i['w_market']:.3f} | {i['w_model']:.3f} | "
                           f"{i['w_model_lo']:.3f} .. {i['w_model_hi']:.3f} | {i['slope_model_alone']:.3f} |")
    return "\n".join(out)


def ev_band_table(t, v):
    rows = diag[t][v]["ev_bands"]
    out = ["| Rule | EV at the first eligible quote | Bets | Wins | Units | Return |", "|---|---|---|---|---|---|"]
    for r in RULES:
        for x in rows:
            if x["rule"] == r:
                out.append(f"| {NAME[r]} | {x['ev_band'].replace('-inf', 'below').replace('inf', 'up')} | {x['bets']} | {x['win']} | "
                           f"{x['units']:+.2f} | {pct(x['roi'])} |")
    return "\n".join(out)


def night_table():
    out = ["| Test | Eligibility | Bets | W-L | Units | Risked | Return | 95% interval | Early half | Late half | Slate dates | Bets a slate | "
           "Slates with none | Night cut min / median / max | Prices min / median / max | Placebo mean | Placebo 95th | Placebo best | Placebo runs at or above |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in night:
        out.append(f"| {s['test']} | {VAR[s['variant']]} | {s['bets']} | {s['w']}-{s['l']} | {s['units']:+.2f} | {s['risked']:.2f} | {pct(s['roi'])} | "
                   f"{pct(s['ci_lo'])} .. {pct(s['ci_hi'])} | {pct(s['early_roi'])} on {s['early_n']} | {pct(s['late_roi'])} on {s['late_n']} | "
                   f"{s['slates']} | {s['per_slate']} | {s['slates_without_a_bet']} | {s['night_cut_min']:.3f} / {s['night_cut_median']:.3f} / {s['night_cut_max']:.3f} | "
                   f"{s['price_min']:+.0f} / {s['price_med']:+.0f} / {s['price_max']:+.0f} | {pct(s['placebo_mean'])} | {pct(s['placebo_p95'])} | "
                   f"{pct(s['placebo_max'])} | {s['placebo_runs_above']} of 200 |")
    return "\n".join(out)


def night_rules():
    out = ["| Test | Eligibility | " + " | ".join(NAME[r] for r in RULES) + " |", "|---|---|---|---|---|---|"]
    for s in night:
        br = s["by_rule"]
        out.append(f"| {s['test']} | {VAR[s['variant']]} | " + " | ".join(
            (f"{br[r]['bets']} bets, {br[r]['units']:+.2f}u, {pct(br[r]['roi'])}" if r in br else "0 bets") for r in RULES) + " |")
    return "\n".join(out)


def compare_a():
    """Test A, the three eligibility rules side by side (plain model)."""
    a1, a2, a3 = cells(res, "A", "V1"), cells(res, "A", "V2"), cells(var["plain"], "A", "V3")
    out = ["| Rule | EV cut | As asked: bets, return | Wait and confirm: bets, return | No look-ahead: bets, return, interval, placebo 95th |",
           "|---|---|---|---|---|"]
    for r in RULES:
        for c in CUTS:
            x, y, z = a1[(r, c)], a2[(r, c)], a3[(r, c)]
            out.append(f"| {NAME[r]} | {c:.2f} | {x['bets']}, {pct(x['roi'])} | {y['bets']}, {pct(y['roi'])} | "
                       f"{z['bets']}, {pct(z['roi'])}, {pct(z['ci_lo'])} .. {pct(z['ci_hi'])}, {pct(z['placebo_p95'])} |")
    return "\n".join(out)


def fb_summary():
    out = ["| Rule | EV cut | A as asked | A wait and confirm | A no look-ahead | B1 as asked | B1 wait and confirm | B2 as asked | B2 wait and confirm |",
           "|---|---|---|---|---|---|---|---|---|"]
    f = var["fb"]
    cs = {(t, v): cells(f, t, v) for t, v in (("A", "V1"), ("A", "V2"), ("A", "V3"), ("B1", "V1"), ("B1", "V2"), ("B2", "V1"), ("B2", "V2"))}
    for r in RULES:
        for c in CUTS:
            row = [f"{cs[k][(r, c)]['bets']}, {pct(cs[k][(r, c)]['roi'])}" for k in cs]
            out.append(f"| {NAME[r]} | {c:.2f} | " + " | ".join(row) + " |")
    return "\n".join(out)


bars_v1, pass_v1 = bars_table(res, "V1")
bars_v2, pass_v2 = bars_table(res, "V2")
a1, a2, a3 = cells(res, "A", "V1"), cells(res, "A", "V2"), cells(var["plain"], "A", "V3")
b1v2, b2v2 = cells(res, "B1", "V2"), cells(res, "B2", "V2")
e25, e26 = res["eligibility"]["2025 replay"], res["eligibility"]["2026 live"]
fit = res["fits"]["A"]
sk = var["plain_skew"]
gapA = {r["fb"]: r for r in diag["A"]["V1"]["totals_gap"]}
nA = {s["variant"]: s for s in night if s["test"] == "A"}
nB1 = {s["variant"]: s for s in night if s["test"] == "B1"}
nB2 = {s["variant"]: s for s in night if s["test"] == "B2"}
info = diag["A"]["V1"]["info"]
info2 = diag["A"]["V2"]["info"]


def band(rule, start):
    x = [b for b in diag["A"]["V1"]["ev_bands"] if b["rule"] == rule and b["ev_band"].startswith(start)][0]
    return f"{pct(x['roi'])} on {x['bets']} bets"


def rng(cs, rule, key="roi"):
    v = [cs[(rule, c)][key] for c in CUTS]
    return f"{pct(min(v))} to {pct(max(v))}"


def passed_txt(p):
    return "none" if not p else "; ".join(f"{NAME[r]} at {c:.2f}" for r, c in p)


def one(cs, r, c):
    x = cs[(r, c)]
    return f"{pct(x['roi'])} on {x['bets']} bets (interval {pct(x['ci_lo'])} .. {pct(x['ci_hi'])}, placebo 95th {pct(x['placebo_p95'])})"


md = f"""# NCAAF in play: the NCAAB game-state model ported to football, measured at DraftKings' in-play prices

Written 2026-11-10. Everything here was computed from the local extracts; nothing was written to a database,
nothing in the repo was edited, and no paid call was made. Results are in units: one unit to win, risk capped
at three. Scripts and their printed output are listed at the end; every table below is built from the files
those scripts wrote.

## 1. The answer

**No. A market-anchored game-state model does not beat DraftKings' in-play NCAAF totals or moneylines on the
stored data. No rule clears the bars under the eligibility rule as asked.**

| Rule | Test A (fit 2025, test 2026), every cut, as asked | Clears every bar? |
|---|---|---|
| Total, first half | {rng(a1, 'totals_H1')} on {a1[('totals_H1', 0.2)]['bets']} to {a1[('totals_H1', 0.02)]['bets']} bets | No: negative in test A at every cut |
| Total, second half | {rng(a1, 'totals_H2')} on {a1[('totals_H2', 0.2)]['bets']} to {a1[('totals_H2', 0.02)]['bets']} bets | No: negative in test A at every cut |
| Moneyline, first half | {rng(a1, 'h2h_H1')} on {a1[('h2h_H1', 0.2)]['bets']} to {a1[('h2h_H1', 0.02)]['bets']} bets | No: no cut is positive in A and in both halves of 2025 |
| Moneyline, second half | {rng(a1, 'h2h_H2')} on {a1[('h2h_H2', 0.2)]['bets']} to {a1[('h2h_H2', 0.02)]['bets']} bets | No: negative in test A at every cut |

The bars: at least 100 bets in test A; positive in test A and in both directions of test B; and an interval
whose lower bound is above zero, or a return above the placebo's 95th percentile. Cells clearing all of them,
as asked: **{passed_txt(pass_v1)}**. Section 5 has every cell.

Three things a reader should know before the tables.

1. **The hypothesis was half right.** Anchoring on the pre-game line does make the model's total more
   informative than the two-stage engine's was (calibration slope 0.135 in `docs/sports/ncaaf.md`): on 2026
   second-half totals the slope of the result on this model's probability is {info['totals_H2']['slope_model_alone']:.3f}
   as asked and {info2['totals_H2']['slope_model_alone']:.3f} under the stricter eligibility, and
   {diag['B1']['V2']['info']['totals_H2']['slope_model_alone']:.3f} and {diag['B2']['V2']['info']['totals_H2']['slope_model_alone']:.3f}
   in the two halves of 2025. A calibrated model reads 1.0. In the first half of 2026 it is
   {info['totals_H1']['slope_model_alone']:.3f}. So most of every edge the model claims on a total is not there,
   and what is left does not cover the price: second-half totals in 2026 return {rng(a1, 'totals_H2')}, which is better than
   betting the same side blind ({pct(res['A']['V1']['blind']['totals_H2|over']['roi'])} on the over) and better than
   the placebo (mean {pct(a1[('totals_H2', 0.02)]['placebo_mean'])}), and still a loss.
2. **The moneyline looks better only under a rule that peeks.** I added a stricter eligibility ("wait and
   confirm", section 3) before grading anything, because our 2026 score log trails DraftKings by a median 75
   seconds. Under it the 2026 moneylines are positive at every cut ({rng(a2, 'h2h_H1')} first half,
   {rng(a2, 'h2h_H2')} second half) and two single cells meet every bar ({passed_txt(pass_v2)}). That rule
   conditions each bet on nothing being scored in the next four minutes. Re-run with no look-ahead at all
   ("no look-ahead", section 3, 2026 only) the same two cells are {one(a3, 'h2h_H1', 0.08)} and
   {one(a3, 'h2h_H2', 0.2)}: inside what the placebo produces. In all 30 moneyline cells of test A (three
   eligibility rules) the early half of the window returns less than the late half, and it loses in 26 of them.
3. **The cut barely selects under a first-crossing rule.** With a new DraftKings quote about once a minute
   ({num['q_by_season_market']['2026|totals']:,} total quotes on {num['qgames_by_season_market']['2026|totals']} games in 2026), "the first quote
   that clears the cut" is found in almost every game: in test A {100 * num['A_V1_share_of_games_betting']['totals_H2@0.2']:.1f}% of
   games bet a second-half total at EV 0.20 and {100 * num['A_V1_share_of_games_betting']['h2h_H1@0.2']:.1f}% bet a first-half
   moneyline. The 2026 feed holds {num['quotes_per_game_rule']['2026']} eligible quotes per game and rule against
   {num['quotes_per_game_rule']['2025']} in the 2025 replay, so the same cut is a different rule in tests A and B.

The "best few a night" variant (section 8) returns {pct(nA['V1']['roi'])} on {nA['V1']['bets']} bets in test A
(interval {pct(nA['V1']['ci_lo'])} .. {pct(nA['V1']['ci_hi'])}) and {pct(nB1['V1']['roi'])} and {pct(nB2['V1']['roi'])}
in the two halves of 2025. Positive in A, flat in B, interval across zero: not a pass.

## 2. The data actually used

| What | Count | Source |
|---|---|---|
| 2025 play-by-play | 293,383 plays, 1,659 games | `ncaaf_plays.parquet` |
| dropped: a negative drive id, so play order cannot be known | 14 games | |
| matched to a row of the games table (two team names, within two days) | {num['g2025_matched']} of {num['g2025_pbp_games']:,} | the rest are games the games table does not hold |
| play-by-play ends on the stored final | {num['g2025_final_ok']} | |
| clean: ends on the final and every score step is 1, 2, 3, 6, 7 or 8 | {num['g2025_clean']} | a step of any other size is a hole in the plays |
| clean with a pre-game spread and total: the training games | {num['g2025_train']} ({num['g2025_train_by_block']['early']} weeks 1-7, {num['g2025_train_by_block']['late']} weeks 8+ and postseason) | |
| training states, one per 30 seconds of regulation clock | {num['train_states']:,} ({num['train_states_by_block']['early']:,} and {num['train_states_by_block']['late']:,}) | 117 a game |
| prior of the training games | DraftKings' last pre-kick row {num['g2025_train_prior']['draftkings']}, CFBD's DraftKings close {num['g2025_train_prior']['cfbd_draftkings']}, CFBD's Bovada close {num['g2025_train_prior']['cfbd_bovada']} | |
| 2026 logged game states | 23,535 on 496 games, 2026-09-19 16:50 UTC to 2026-11-08 07:04 UTC | `ncaaf_live_states.parquet` |
| 2026 logged score changes | 6,470, of which 147 are a score going down (120 games) | a correction or a feed error; not separated |
| DraftKings in-play quotes kept, 2025 replay | {num['q2025']:,} ({num['q_by_season_market']['2025|totals']:,} totals on {num['qgames_by_season_market']['2025|totals']} games, {num['q_by_season_market']['2025|h2h']:,} moneylines on {num['qgames_by_season_market']['2025|h2h']}) | 57,979 rows less 8,929 exact duplicates |
| DraftKings in-play quotes kept, 2026 live | {num['q2026']:,} ({num['q_by_season_market']['2026|totals']:,} totals on {num['qgames_by_season_market']['2026|totals']} games, {num['q_by_season_market']['2026|h2h']:,} moneylines on {num['qgames_by_season_market']['2026|h2h']}) | 211,472 rows less the 10,809 of 2026-08-29 that carry our clock, not the book's |
| 2026 games with a quote but before the state log starts (2026-09-19) | {num['g2026_quote_games_before_0919']} games, {num['g2026_quotes_before_0919']:,} quotes: unusable | {num['g2026_quote_games_from_0919']} games remain, all with logged states |
| 2025 replay games with a clean play-by-play game | {num['g2025_quote_games_clean_pbp']} of {num['g2025_quote_games']} | |
| games graded | test A {num['A_games']} on {num['A_slates']} slate dates; B1 {num['B1_games']} on {num['B1_slates']}; B2 {num['B2_games']} on {num['B2_slates']} | |

Finals: a 2025 odds row with no score of its own takes its twin's (the same two teams within a day): 561 own,
167 from a twin, 8 with none. All 2026 rows carry their own. The prior of the graded games is DraftKings' last
pre-kick row on all 473 games of 2026 and on 468 of the 597 of 2025 (CFBD's DraftKings close on 68, CFBD's
Bovada close on 61). Pinnacle's pre-kick close is stored for 1,222 of the 1,377 games with a quote or a state;
where both exist DraftKings and Pinnacle differ by a mean 0.625 points on the spread and 0.727 on the total, and
are within a point on both on 76.6% of games. The model uses DraftKings' number.

There are no in-play spreads in the store, so the market that carried most of the NCAAB result cannot be tested.

**What was dropped, and why.** Counts are quotes unless the row says games, and each drop is taken from what
the rows above it left. The feed-error rules found no bad price and no impossible total; the only quotes they
removed are a total at or below the points already on the board and totals priced beyond +/-250 on a side.

{elig_table()}

Eligible quotes and games by rule:

{per_rule_eligible()}

Two measurements made on the data before any grade, both of which shape the rules in section 3:

- **DraftKings is ahead of our 2026 score log.** For each logged score change I took DraftKings' nearest total
  move of 2.5 points or more within five minutes either side (3,995 matched). The log shows the score a median
  75 seconds AFTER the book moved; 75th percentile 120 s, 90th 182 s, 95th 221 s.
- **The 2025 play wallclocks are not the time of the play.** They are a last-edited stamp: 1.8% are a whole
  day off and 7.9% are missing or out of play order. A score's true time is only known to lie between the previous in-order
  wallclock and the wallclock the score is first seen at: median 44 seconds apart, 75th percentile 81 s, 90th
  217 s, 95th 290 s.

## 3. Method, as fixed before grading

The definitions are the docstring at the top of `grid.py`. In short:

- **Model.** What is still to come, the home margin and the total, is Normal with mean X b and standard
  deviation sqrt(s0 + s1 f + s2 f^2), f the share of the 3,600 seconds of regulation left. Weighted least
  squares, three passes, weight 1 / variance, on **one state per 30 seconds of regulation game clock**.
  Margin on: f x prior margin, f, current margin x f. Total on: f x prior total, f^2 x prior total, f, f^2,
  (points so far minus (1 - f) x prior total) x f, |margin| x f, and a late-and-close term. NCAAB's two bonus
  terms are dropped. No possession, down, distance or field position: the 2026 log carries possession on 58%
  of rows and field position on 41%.
- **Rules.** Total first half; total second half (halftime to 5:00 left); moneyline first half; moneyline second
  half. DraftKings only. One decision per game and rule: the first eligible quote, in the order received,
  whose better side has EV >= the cut. Cuts 0.02, 0.05, 0.08, 0.12, 0.20. No moneyline side shorter than -200.
- **State at a quote.** The quote's stamp is the book's own (2025 the `lu=` value; 2026 the stored
  last-update). 2025: the last play, in order, whose wallclock is in order and at or before the stamp. 2026: the
  last logged state at or before the stamp, the clock read between it and the next logged state.
- **Eligible, as asked.** A state before and after the stamp no more than 30 minutes apart; not a feed error;
  no score became known in the 60 seconds before the stamp; none between the stamp and when we received the
  quote. The 30-minute bound and the last condition (the repo's own freshness rule in `docs/live_betting.md`)
  are mine; the rest is the rule as it was given to me.
- **Eligible, wait and confirm** (added before grading, because of the 75-second lead above). As asked, plus:
  no score becomes known in the 240 seconds after the stamp; in 2025 no score whose time bracket is open at the
  stamp; and the quote no older than 90 seconds when received unless at halftime. Graded at the quote's own
  price, which a loop that waited four minutes would no longer get.
- **Eligible, no look-ahead** (added AFTER the first grid, test A only, in `variants.py`). As asked, plus: no
  score known in the 240 seconds before the stamp, and no jump by DraftKings in those 240 seconds (its total
  up 2.0 or more, or its no-vig moneyline probability moving 0.08 or more, between consecutive quotes). It
  asks the wait-and-confirm question using only the past. The 2025 replay has one snapshot every five minutes,
  so it cannot be run there.
- **Tests.** A: fit on all of 2025, test on 2026. B1: fit on 2025 weeks 1-7, test on weeks 8+ and the
  postseason. B2: the reverse. No test state was in its fit.
- **Grade.** Risk = min(1 / (decimal - 1), 3) to win risk x (decimal - 1); return = units / units risked; 95%
  interval from 2,000 resamples of slate dates; early and late half of each window split at the median slate
  date of its games; blind = each side at every game's first eligible quote.
- **Placebo, 200 runs.** Each game takes another game's model opinion at the same share of the game left
  (bands of 0.02, nearest within 0.04): the donor's model probability minus the donor's own no-vig market
  probability, added to this game's no-vig probability; then the same rule and cuts. A raw swap of probabilities
  would be meaningless on a moneyline, where the favourite differs by game; on a total the two are the same.

## 4. Model fit

Fit on all of 2025 (test A): margin b = {fit['margin']['beta']} on (f x prior margin, f, margin x f), variance
{fit['margin']['s0']} + {fit['margin']['s1']} f + {fit['margin']['s2']} f^2. Total b = {fit['total']['beta']} on
(f x prior total, f^2 x prior total, f, f^2, pace x f, |margin| x f, late-and-close), variance
{fit['total']['s0']} + {fit['total']['s1']} f + {fit['total']['s2']} f^2. {fit['total']['n_train']:,} states.

Out of sample, by share of regulation left. Mean error is the final minus the model's mean; the spread ratio is
the standard deviation of the standardised error (1.0 = the model's width is right).

**B1, fit on weeks 1-7, read on weeks 8+ and the postseason ({num['g2025_train_by_block']['late']} games):**

{cal_table(res['calibration']['B1 (fit weeks 1-7, read on weeks 8+)'])}

**B2, fit on weeks 8+, read on weeks 1-7 ({num['g2025_train_by_block']['early']} games):**

{cal_table(res['calibration']['B2 (fit weeks 8+, read on weeks 1-7)'])}

**A, fit on 2025, read on every logged 2026 state in regulation:**

{cal_table(res['calibration']['A (fit 2025, read on the 2026 logged states)'])}

The widths are right (spread ratio 0.883 to 1.142) and the largest mean error is 1.045 points. Two shapes in it
matter for a total. The model's total runs high with a quarter to a half of the game left in all three reads
(mean error -0.462, -0.567, -0.849) and low with a half to three quarters left (+0.328, +1.045, +0.567):
football scores more late in each half and a clock-linear model cannot bend there. And the total's distribution is right-skewed: on the training states the
final lands above the model's own mean {100 * sk[0]['mean']:.1f}% of the time with a quarter of the game or less left and
{100 * sk[1]['mean']:.1f}% between a quarter and a half, so a Normal around an unbiased mean leans over against a line set at
the median. In test A the model's mean sits above DraftKings' total by {gapA['(0.25, 0.5]']['model_minus_line']:+.2f} points
on average between a quarter and a half left, and the model's bets there are mostly overs
({a1[('totals_H2', 0.02)]['sides'].get('over', 0)} of {a1[('totals_H2', 0.02)]['bets']} at EV 0.02). Section 7 removes both
shapes and re-grades.

## 5. The grid: every cell

Returns are units won per unit risked. "Blind, that side" is the cell's most-bet side taken at every game's first
eligible quote. "Placebo runs at or above" counts the 200 placebo runs that returned at least what the model did.

### Against the bars, eligibility as asked

{bars_v1}

Cells clearing every bar: **{passed_txt(pass_v1)}**.

### Against the bars, wait and confirm

{bars_v2}

Cells clearing every bar: **{passed_txt(pass_v2)}**. Each is one cut wide: the first-half moneyline at 0.05 and
0.12 is {pct(b2v2[('h2h_H1', 0.05)]['roi'])} and {pct(b2v2[('h2h_H1', 0.12)]['roi'])} in B2, and the second-half moneyline at
0.12 is {pct(b2v2[('h2h_H2', 0.12)]['roi'])} in B2 on {b2v2[('h2h_H2', 0.12)]['bets']} bets (its passing cell, 0.20, has
{b2v2[('h2h_H2', 0.2)]['bets']}). And this eligibility conditions on the future; the next table is the same season without that.

### Test A, the three eligibility rules side by side

{compare_a()}

### Test A, as asked: {res['A']['games']} games, slate dates {res['A']['first_slate']} to {res['A']['last_slate']}, halves split after {res['A']['split_date']}

{grid_table(res, 'A', 'V1')}

### Test A, wait and confirm

{grid_table(res, 'A', 'V2')}

### Test A, no look-ahead

{grid_table(var['plain'], 'A', 'V3')}

### Test B1, as asked: {res['B1']['games']} games, slate dates {res['B1']['first_slate']} to {res['B1']['last_slate']}, halves split after {res['B1']['split_date']}

{grid_table(res, 'B1', 'V1')}

### Test B1, wait and confirm

{grid_table(res, 'B1', 'V2')}

### Test B2, as asked: {res['B2']['games']} games, slate dates {res['B2']['first_slate']} to {res['B2']['last_slate']}, halves split after {res['B2']['split_date']}

{grid_table(res, 'B2', 'V1')}

### Test B2, wait and confirm

{grid_table(res, 'B2', 'V2')}

### The blind sides

{blind_table()}

**Prices laid** (the 140 cells above). Totals: -160 at the shortest, a median of -116 to -110 by cell, +185 at
the longest. Moneylines: never shorter than -200 by rule; the median bet of every cell is an underdog, +180 to
+420, and the longest is +4400. A moneyline return therefore rests on few units risked
({a1[('h2h_H1', 0.2)]['risked']:.2f} units over {a1[('h2h_H1', 0.2)]['bets']} bets in test A's first-half cell at 0.20), and the
moneyline intervals are 22 to 72 points wide.

**Across the 140 cells:** all 30 total cells of test A are negative (-13.0% to -0.5%), and the first-half
total's interval is entirely below zero in 12 of its 15. One cell has an interval whose lower bound is above
zero: the second-half moneyline in B1 under wait and confirm at 0.02 ({pct(b1v2[('h2h_H2', 0.02)]['roi'])},
lower bound {pct(b1v2[('h2h_H2', 0.02)]['ci_lo'])}); the same cell is {pct(b2v2[('h2h_H2', 0.02)]['roi'])} in B2.

## 6. Why it does not pay: two reads that do not depend on a cut

**Does the model's probability add anything to the price?** The result of the over (or the home side)
regressed on the market's no-vig probability and the model's, both as log-odds, every eligible quote, games
resampled for the interval. A model that only repeats the price has weight 0. "Slope on the model alone" is
the calibration slope: 1.0 means a claimed edge is all there.

{info_table()}

On totals the slope on the model alone is 0.119 to 0.414 in ten of the twelve reads and -0.068 and -0.021 in
the other two, the first half of 2026; the interval of the model's weight is above zero in six of the twelve.
On moneylines the interval of the model's weight is above zero in seven of the eight reads of tests A and B1
and in none of the four of B2. Part of a moneyline weight can be the no-vig arithmetic itself (a proportional
no-vig understates favourites), so it is not evidence of a price that can be beaten; the grid is.

**Does a higher EV pay more?** Test A, as asked, one decision per game and rule at its first eligible quote
(no first-crossing selection):

{ev_band_table('A', 'V1')}

No rule's return rises steadily with the EV band. The second-half total returns {band('totals_H2', '0.08')}
at 0.08 to 0.12, {band('totals_H2', '0.12')} at 0.12 to 0.20 and {band('totals_H2', '0.20')} above. The top band
of the first-half moneyline is {band('h2h_H1', '0.20')} and of the second-half moneyline {band('h2h_H2', '0.20')}.
The NCAAB selection lives in a tail that climbs with EV (`docs/sports/ncaab.md`); nothing here shows one.

## 7. A football-shaped version (defined after the first grid; `variants.py`)

To see whether the totals result is only the two shapes of section 4, I refit with time measured as the share
of SCORING left (the training games' mean points still to come at each 30 seconds, over their mean final:
0.779 with three quarters of the clock left, 0.476 at the half, 0.261 with a quarter left) and read a total's
probability off the training states' own standardised errors instead of the Normal. Both come from training
states only. It was designed after the plain grid had been read, so it is a check on the conclusion, not a
candidate.

It does what it was built to do: in test A the model's mean now sits +0.26 to +0.66 points from DraftKings'
total in every band and its mean probability of the over is 0.497. Out of sample:

**A, fit on 2025, read on the 2026 logged states:**

{cal_table_fb(var['fb_calibration']['A (fit 2025, read on the 2026 logged states)'])}

And it does not change the answer (bets, return):

{fb_summary()}

Totals stay negative in test A in 29 of the 30 cells (the exception: the second-half total under wait and
confirm at 0.20). The moneyline returns are close to the plain model's.

## 8. The best few a night (run after the grid was written up; `night.py`)

The NCAAB selection on the four rules together: each game and rule decides at its FIRST eligible quote; a
decision bets only at or over the night's EV cut and only while the slate date holds fewer than five bets, in
the order received; a decision under the cut, or over it with the night full, spends the rule for that game. The
night's cut is the EV that the fit-side decisions exceeded four times per expected decision on a slate that
size, never under 0.02 (fit side: the 2025 replay under the all-2025 model for test A; the other half of 2025
for B1 and B2).

{night_table()}

By rule:

{night_rules()}

Test A is positive under all three eligibility rules and beats the placebo's 95th percentile, on
{nA['V2']['bets']} to {nA['V1']['bets']} bets, with intervals of {pct(nA['V1']['ci_lo'])} .. {pct(nA['V1']['ci_hi'])},
{pct(nA['V2']['ci_lo'])} .. {pct(nA['V2']['ci_hi'])} and {pct(nA['V3']['ci_lo'])} .. {pct(nA['V3']['ci_hi'])}, and an early half
that loses each time. Neither half of 2025 repeats it ({pct(nB1['V1']['roi'])} and {pct(nB1['V2']['roi'])} in B1,
{pct(nB2['V1']['roi'])} and {pct(nB2['V2']['roi'])} in B2).
In test A as asked, the first-half moneyline supplies {nA['V1']['by_rule']['h2h_H1']['units']:+.2f} of the
{nA['V1']['units']:+.2f} units on {nA['V1']['by_rule']['h2h_H1']['bets']} bets, and the selection's longest price is
{nA['V1']['price_max']:+.0f}. The night's cut sits at the 0.02 floor on small slates (the median cut is
{nA['V1']['night_cut_median']:.3f} in A and {nB1['V1']['night_cut_median']:.3f} in B1), so on a weekday this bets nearly every
decision.

## 9. For context: the two live models' 2026 record (`picks_record.py`)

From `ncaaf_picks.parquet`, signal_type BET, VOID and DUPLICATE excluded (one row of each, both on the
win-probability model), one unit to win with risk capped at three at COALESCE(decision_odds, dk_odds):

| Model | Record | Units | Risked | Return | Settled bets | Game dates | Prices min / median / max |
|---|---|---|---|---|---|---|---|
| ncaaf_live_total | 51-47-0 | -5.20 | 117.90 | -4.4% | 98 | 2026-08-29 to 2026-09-17 | -176 / -120 / +105 |
| ncaaf_live_win_prob | 25-24-0 | +6.73 | 47.97 | +14.0% | 49 | 2026-08-29 to 2026-11-07 | -238 / +110 / +300 |

The win-probability model is 16-9, +4.70 units to 2026-09-18 and 9-15, +2.03 units from 2026-09-19 (the window
test A covers). No settled bet was missing a price and none carries a stake of its own.

## 10. What I could not do, and what I am unsure of

Could not do:

- **In-play spreads.** None are stored for NCAAF.
- **2026 before 2026-09-19.** 145 games and 38,446 quotes have no logged state, so test A is 32 slate dates.
- **The no-look-ahead rule on 2025.** One snapshot every five minutes does not show the book's last four minutes.
- **A second out-of-sample season, or a walk-forward.** Play-by-play is stored for 2025 only.

Unsure of:

- **The 2025 clock.** Play wallclocks are edit stamps (section 2). Test B's states are softer than test A's, in a
  direction I cannot sign.
- **The 2026 clock.** Between two logged states the clock is read off a straight line, which uses the next
  state's clock (not its score).
- **Wait and confirm flatters.** It bets only when nothing is scored in the next four minutes and grades at a
  price that would be gone. The no-look-ahead rule is the honest read of the same idea, and it was written after
  the first grid.
- **The moneyline tail.** The median moneyline bet of every cell is an underdog at +180 to +420. I did not
  measure how much of the model's disagreement with those prices is the Normal's tail and how much is the game
  state, and I did not test a different tail.
- **The placebo's form.** It moves a game's model-minus-market opinion, not its raw probability. On totals the
  two are the same; on moneylines the choice matters and I chose the harder one.
- **No possession or field position.** DraftKings prices them and this model cannot. That is a handicap of the
  stored 2026 log, not of the idea.
- **Cut meaning differs by season.** 78 eligible quotes per game and rule in 2026 against 15 in 2025.

## 11. Files

All in `scripts/ncaaf_search/audit_2026_11/inplay/`:

| File | What it is |
|---|---|
| `prep.py`, `prep_out.txt` | the extracts turned into games, training states, state timelines and quotes; every count and drop |
| `grid.py`, `grid_out.txt`, `results.json` | the definitions (docstring), the fits, calibration, eligibility and the plain grid for tests A, B1, B2 |
| `diag.py`, `diag_out.txt`, `diag.json` | orientation checks, the information test, the EV bands |
| `variants.py`, `variants_out.txt`, `variants.json` | the no-look-ahead rule and the football-shaped model |
| `night.py`, `night_out.txt`, `night.json` | the best few a night |
| `picks_record.py` | the two live models' 2026 record |
| `verify.py`, `numbers.json` | bets re-graded from the raw finals (the stored units match to the cent on four cells), the counts quoted above |
| `make_report.py` | builds this file from the JSON |
| `bets_*.parquet`, `night_*.parquet`, `priced_*.parquet` | every bet of every cell, and every eligible quote with the model's numbers |
"""
(OUT / "REPORT.md").write_text(md, encoding="utf-8")
print("written", len(md), "chars;", "V1 passes:", pass_v1, "V2 passes:", pass_v2)
