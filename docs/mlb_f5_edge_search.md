# MLB first-five-innings markets: the edge search (2026-09-19)

> **Provenance.** Written 2026-09-19 for PR #762, which was never merged.
> Carried to master 2026-10-10 as a write-up only: the PR's sweep-script
> change, worker job and tests were not kept (the code is on branch
> `cursor/mlb-f5-edge-hunt-7ba7`, commit `b3a4aac`). The 2026-09-19 text is
> below as measured that day, with abbreviations spelled out. The
> **2026-10-10 addendum** at the end re-measures the closest miss through
> September 30 and splits it by side. Read the addendum before acting on
> anything above it.

This pass hunted for a bettable rule in the three first-five-innings
markets (moneyline, total, run line), whose models are `mlb_f5_moneyline`,
`mlb_f5_over_under` and `mlb_f5_runline`. It followed the full-game
searches of the same week: run line (`docs/mlb_runline_edge_hunt.md`),
totals (`docs/mlb_total_public_fade.md` and
`docs/mlb_runline_ou_edge_search.md`) and the Pinnacle run-line rule
(`docs/mlb_spread_market_2026.md`).

Pausing and unpausing is mike's call. Nothing here unpauses a model or
turns on a publish switch.

**Verdict (2026-09-19): no card.** No construction was selective, positive
in every month, at least 40 bets, a few bets a day, and part of a
neighbourhood rather than one lucky setting. The closest misses are below
so the next search does not re-derive them.

---

## Coverage (Supabase, measured 2026-09-19)

| Source | What is actually there |
|---|---|
| First-five scores | 1,749 of 2,257 2026 MLB games; `home_score_f5` from 2026-04-16 to 2026-09-18 |
| First-five moneyline (`h2h_1st_5_innings`), DraftKings | 1,640 games, 2026-05-10 to 2026-09-19. Several books only from **2026-09-02** (~224 games) |
| Pinnacle first-five moneyline | **0 rows** |
| First-five totals and run line (`totals_1st_5_innings`, `spreads_1st_5_innings`), real books | Pinnacle, FanDuel, BetMGM, William Hill, Bovada from **2026-09-02** only (~223-224 games). Rows before May from `sbr_consensus` are synthetic (full-game total × 0.62, or a fixed −0.5) |
| Pinnacle first-five "spreads" | `spread_home = 0` on 4,583 of 4,591 rows: stored as a first-five moneyline, not −0.5. Comparing on an equal line against a soft book's −0.5 finds nothing |
| `public_betting` | Full-game moneyline, run line and totals only. **No first-five splits** |
| Public split taken before first pitch | May 0, Jun 59, Jul 25, **Aug 0**, Sep 54 (moneyline, home, consensus) |

Live `mlb_f5_moneyline` settled bets on 2026-09-19 (not void, priced):
**213, 123-90, −3.29 units, −1.54%**. `mlb_f5_over_under` and
`mlb_f5_runline`: May leftovers from the synthetic-line era (unpriced) and
NONE rows from 2026-09-15. Both stay paused (their artifacts date from
2026-05-08, trained on the leaked tables and synthetic lines).

---

## What was measured

Every cell uses only pre-game quotes (`snapshot_type='open'` and
`snapshot_at <= commence_time`). First-five moneyline and totals are graded
on `home_score_f5` / `away_score_f5`. Pushes (a first-five tie, or a total
landing on the line) are left out of the ROI denominator. "Soft books" are
`BEST_LINE_BOOKMAKERS` minus Pinnacle unless a book is named.

### 1. Pinnacle no-vig against a bettable soft book's no-vig, first-five totals (the closest miss)

Equal `total_line`, both quotes within 300 seconds of each other, one bet a
game (the largest edge). **September only**, because Pinnacle first-five
totals begin 2026-09-02.

| mode | cut | n | units | ROI | notes |
|---|---|---|---|---|---|
| either side | 1.5 points | **69** | **+5.09u** | **+7.37%** | 42 over / 27 under; 16 days; 5.1 a day on average; **max 9** a day |
| either side | 2.0 points | 34 | +5.18u | +15.23% | n under 40 |
| Pinnacle's side only | 1.5 points | 38 | +4.96u | +13.04% | n under 40 |
| against the soft book's raw price (with its margin) | 1.5 points and up | 0 | — | — | the margin swallows the gap |

Split by week at 1.5 points, either side: Sep 2-10 **+11.70% on 31**; Sep
11-18 **+4.90% on 38**. Both halves positive, but this is 16 days of one
month, not month-stable, and 9 bets on one day is not "a few". The
full-game version of this rule (Pinnacle no-vig against soft no-vig on
totals, 2 points) was **−11.13% on 79** (`docs/mlb_runline_ou_edge_search.md`).
No first-five totals card on this cell.

### 2. First-five moneyline, following or fading a DraftKings line move (May 10 to Sep 18; 1,595 games, 11.8 snapshots a game on average)

Following a move of 1 to 5 points: **red every month** at 1 and 2 points
(August −13.0% on 191 at 1 point; −11.7% on 104 at 2 points).

Fading a 2-point move: pooled **+2.07% on 339**; first half +6.23% on 74,
second half +0.91% on 265. **The neighbours flip sign**: 1 point −3.27% on
693; 3 points −4.50% on 167. By month at 2 points: May +39% on 18, Jun
**−4.37% on 56**, Jul +1.32% on 85, Aug +2.55% on 104, Sep **−1.80% on 76**.
One good setting, not a plateau.

### 3. Fading the full-game public on the first-five moneyline (splits taken before first pitch)

Fade the side holding most of the full-game consensus tickets; bet the
other first-five moneyline side at DraftKings' last pre-game price.

| cut | n | ROI | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|---|
| 60% of tickets | 82 | +6.59% | +16.33% on 33 | +23.21% on 20 | **no data** | **−15.96% on 29** |

The pooled plus is June and July. August has no pre-game public data (the
same gap as the totals public fade). September is red. Not month-stable.

Reverse line movement (tickets minus money at least 10 points; fade the
ticket side) on the same join: Jun −6.24% on 28, Jul +14.47% on 6, Sep
+1.92% on 19. Thin and mixed.

### 4. First-five moneyline against the full-game moneyline (DraftKings against DraftKings)

Bet the first-five side priced softer than the full-game price implies.
May at 1 point −3.54% on 168; Jun −11.37% on 208; Jul −5.71% on 179.
Tighter cuts stay red. The opposite (bet the sharper first-five side) is
also red in July. Games where the first-five favourite differs from the
full-game favourite are few (August 18 bets, −19.4%).

### 5. Blind and price-band first-five moneyline

| rule | n | ROI |
|---|---|---|
| Bet every first-five underdog | 1,353 | **−8.81%** (first half −10.4%, second half −7.7%) |
| Bet every first-five favourite | 1,353 | **−3.67%** |
| Underdog by favourite price band (−120 / −140 / −160 / −200) | 81-550 | all **−6% to −17%** |
| Favourite at −119 or shorter | 81 | +3.86% pooled; May to July positive, then Aug **−27% on 18**, Sep **−32% on 11** |

### 6. Full-game public over pile, bet the first-five under (September only; FanDuel first-five total)

Over tickets at 60%, 70% and 80%: **−24.6% on 37** (80%: −26.9% on 33).
Over-rate at Pinnacle's first-five line: 110-90-10 (unders win 45%), so
there is no blind first-five under lean either.

### 7. Pinnacle first-five "spreads" at line 0 against DraftKings' first-five moneyline

210 games join, 145 of them with both quotes inside an hour. Against
DraftKings' raw price (with its margin): **n=0** at 1.5 points and up.
Against DraftKings' no-vig price: 1.5 points 28 bets −6.8%; 2 points 13
bets +16.8% (thin). Not a card.

---

## What this is not

- Not an unpause of `mlb_f5_moneyline`, `mlb_f5_over_under` or
  `mlb_f5_runline`. Live first-five moneyline was −1.54% on 213 on
  2026-09-19. The first-five total and run-line artifacts were trained on
  leaked tables and synthetic lines.
- Not another neighbour of the 1.8-point Pinnacle run-line rule.
- Not a change to the totals public fade or to any publish switch.

---

## Addendum (2026-10-10): through September 30, and by side

Re-measured with read-only SQL against production on 2026-10-10, during the
review of PR #762. The query copies the PR's pick logic: each book's latest
pre-game quote, equal line, both quotes within 300 seconds, one bet a game
at the largest edge, soft books FanDuel, BetMGM, William Hill, Rebet and
the other bettable books, Bovada excluded. Two separate runs agreed on the
totals below.

**Coverage.** Pinnacle first-five totals cover 316 games from Sep 2 to 30
and 16 in October (postseason). Pinnacle still has no first-five
moneyline rows. Its first-five spreads are 6,974 rows at line 0, out of
6,985. The next full month of Pinnacle first-five prices is April 2027.

**The closest miss, extended (1.5 points, either side):**

| Window | Bets | ROI | Note |
|---|---|---|---|
| Sep 2-18 | 68 | +6.12% | PR reported 69 / +7.37% on 09-19 |
| Sep 19-30 (after the PR) | 28 | +19.15% | but 2 points: 16 bets −2.27%; 2.5 points: 6 bets −1.36% |
| Sep 2-30 | 96 | +9.92% | at most 9 bets a day, 4.2 on average |
| Postseason, through Oct 9 | 7 | +15.7% | all 7 were unders |

**By side.** Each pick compared with betting every over (or under) blind
at the same book and the same line:

| Picks | Bets | ROI | Blind, same book and line |
|---|---|---|---|
| Overs, Sep 2-30 | 54 | **+30.1%** | +4.8% |
| Overs, Sep 2-18 | 42 | +25.3% | +4.0% |
| Overs, Sep 19-30 | 12 | +46.9% | +7.7% |
| Unders, Sep 2-30 | 42 | **−16.0%** | −7.6% |

The red 2-point cell after Sep 18 is all unders: 8 bets, −26.8%. The overs
in that cell were 8 bets, +22.3%. Blind September betting: every Pinnacle
first-five over +5.0% (160-136-18), every FanDuel over +2.3%, every
FanDuel under −13.6%.

Per-book under results depend on how ties are broken. Six games tie exactly
between BetMGM and William Hill at the same price; the PR's script keeps
the first book alphabetically (BetMGM). Run that way, BetMGM unders are 7
bets +12.0%, not 6 bets −1.9%. The pooled 96 bets, +9.92%, is the same
under either rule.

**Reading.** Still not a card: one month, about 1.7 standard errors on 54
over bets, found in a search over many cells. But the over side is a lead,
and it held after the PR was written. Overs running hot in September
explain about 5 of its 30 points, not all of it. Under picks lost more
than blind unders. The first review on 2026-10-10 read the plus as "an
over-tilt in one hot month"; the same-book, same-line comparison above
does not support that reading.

**For 2027.** The bettable first-five totals books will be FanDuel, BetMGM
and William Hill: Rebet was dropped from the shopped books on 2026-09-20
(`config.py`, the "TEN BOOKS" comment), and it supplied 4 of the 96 picks.
The re-check is in `docs/followups.md`. If code is wanted, start from the
PR's sweep change (branch `cursor/mlb-f5-edge-hunt-7ba7`, commit `b3a4aac`)
and add a by-side split; that sweep does not report one.
