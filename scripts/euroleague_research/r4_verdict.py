"""Round 4 (halftime): append the verdict (section 6) to the results file.
Every number below is quoted from the tables r4_report.py wrote above it.
Run once, after r4_report.py (which rewrites the file and drops this section)."""
from pathlib import Path

F = Path(r"C:\Users\micha\AppData\Local\Temp\euroleague_halftime.md")

V = r"""
## 6. Verdict (written after every table above; each number is quoted from them)

Script: `scripts/euroleague_research/r4_verdict.py` (text only; the numbers are the tables').

### 6.1 What the sample resolves
A blind bet at the best decidable price covers about 1,600 games a market (section 2b, "What the sample resolves").
That resolves its return to about ±3.7 points: a 90% half-width of 3.74 for totals, 3.64 for spreads and 1.99 for moneyline favourites.
A rule with about 300 bets resolves to about ±8 points; rule A's interval has a half-width of 8.2.
So a true +8% edge sits right at the edge of what this sample can show.

### 6.2 Per market, at the pre-registered headline cut of 0.05 (pooled walk-forward, 2022-23 to 2026-27)

| Market | Rule | Bets | Units | Return [90%] | Verdict |
|---|---|---|---|---|---|
| Total | ported unchanged | 574 | -12.61 | -1.93% [-8.44, +4.23] | **null** |
| Moneyline | the margin model priced as a moneyline (an extension) | 164 | -0.51 | -0.24% [-13.25, +12.85] | **null** |
| Spread | **A**: ported unchanged | 312 | +29.80 | +8.37% [-0.06, +16.33] | lead; misses the bar (below) |
| Spread | **B**: variant 2, Pinnacle's close as the prior | 364 | +45.34 | +10.93% [+3.40, +18.48] | lead; misses the bar (below) |
| Total | **P1** (after the fact): fade the book's stray from the mechanical total, D = 2 | 212 | +33.91 | +13.67% [+3.00, +24.57] | after-the-fact lead; fails |

**Why the total fails.** Out of sample, the ported model expects 0.02 to 1.77 more second-half points than EuroLeague games score, in every season (section 3).
It is also too sure: it claims 0.54-0.59 and wins 0.49-0.51. So it leans to the over: 99% of its 574 bets at 0.05 are overs, and the blind over loses 10.04% at the best decidable price.
In the split tables for the total (C and D in section 3b), the row labelled "underdog" is the whole rule, because a total has no favourite.
At the 0.12 cut it reads 120 bets, +6.80%. That passed the placebo. It failed the side split (98% overs), the 10-best-dates test (-6.68%) and the neighbourhood (0.05 reads -1.93%, 0.08 reads +0.75%).

**Why the moneyline fails.** Most games are lost to the price band. In a full season, 142 to 184 games had a fresh decidable quote but none inside -250 to +250, so the rule decides only 117 to 189 games a season.
On the games it does decide, it pays nothing at any cut.

**The spread leads, test by test.** A is the ported rule; B is variant 2.

| Test | A (ported) | B (Pinnacle prior) |
|---|---|---|
| 200+ bets with the 90% interval above zero | **fail**: 312 bets, lower bound -0.06 | pass: 364 bets, lower bound +3.40 |
| Every season with 30+ bets positive | **fail**: 2023-24 -2.53% on 50 (4 of 5 seasons positive) | **fail**: 2023-24 -1.65% on 61 (4 of 5 positive) |
| One part-season carrying the total | **leans on it**: 2026-27 to date, 26 bets, carries 13.30 of 29.80 units | **leans on it**: 2026-27 to date, 31 bets, carries 11.85 of 45.34 units |
| 2021-22 second look (fitted on 2022-23, not walk-forward) | **fail**: -17.01% on 36 | **fail**: -3.55% on 33 |
| Early and late halves of each season both positive | pass, barely: +16.06% / +0.75% | pass: +15.84% / +6.20% |
| Neighbouring cuts (0.02 to 0.12) all positive | pass: +7.23, +9.10, +8.37, +15.03, +3.28 | pass: +4.45, +7.31, +10.93, +11.98, +17.59 |
| Without its 10 best dates | weak: +2.63% (those dates carry 21.05 of 29.80 units) | pass: +6.18% |
| Side split, home/away (70% line) | pass: 62% away | pass: 67% away |
| Side split, favourite/underdog (70% line) | **fail**: 72.4% halftime underdogs | **fail**: 78.0% halftime underdogs |
| Blind control: every decided game on the same kind of side, at the same quotes | pass: underdog -2.01%, ahead of its expected first half -5.86%, behind it -7.28% | pass: -2.20%, -4.58%, -8.59% |
| Placebo (half-time score shuffled across games within each season, 200 times) | pass: real +8.37% against a 95th percentile of -0.45%; 0% of shuffles at or above it | pass: +10.93% against -1.09%; 0% |
| The rule's bets turned round | -21.26% | -23.91% |
| Return rises with the claimed edge | **fail**: 0.05-0.08 band -0.23% on 135; 0.08-0.12 +26.09% on 91; 0.12-0.20 +3.56% | pass, roughly: under 0.05 loses (-4.19, -4.05, -8.07); 0.05 and up pays (+9.19, +6.04, +19.34, +11.75) |
| Fresh quotes only (the fresh rule removed instead) | +9.83%: no difference, because the books re-hang during the break anyway | +11.95%: the same |
| The other read (the last read of the break decides) | pass: +8.67% | pass: +6.96% |
| Price range | median -115, -135 to +105, none shorter than -300 | the same |
| Benjamini-Hochberg at 10% | **fail**: p 0.0506; 0 of 183 cells survive | **fail**: p 0.0096; the first-rank threshold is 0.00055; 0 of 183 survive, and 0 of the 79 method cells |
| Chosen before seeing results | yes (the pre-registered headline) | no: the best of five pre-registered spread rules |

The 25 spread cells of experiment 3 taken alone pass the correction: 17 of 25 survive. That family was chosen after seeing it, and its cells share most of their bets.
That is a secondary read, not a pass.

**P1** (after the fact) passed the donor placebo: 0% of draws reached +13.67%, and the draws' 95th percentile is +3.67%.
It passed the side split (58% unders) and both halves of each season (+17.37% / +10.10%).
It **failed** on four counts. 2025-26 carries 28.97 of its 33.91 units, and 2024-25 reads -17.74% on 25. Without its 10 best dates it reads +3.65%. A stray of 1.0 or 1.5 points reads only +0.64% and +3.39%. And it was chosen with the deviation table in view.

### 6.3 The structural check (experiment 4): are halftime lines re-hung mechanically?
- **Totals: yes, closely, and with no systematic miss.** DraftKings' first fresh halftime total sits within 1 point of the mechanical line in 43-66% of games, depending on the season.
  Its mean distance from that line is 0.90-1.30 points. The mechanical line is half-time points + the pre-game total × 0.50.
  DraftKings carries 0.079 (SE 0.002) of the first half's surprise into the second half. The games carried 0.062 (SE 0.029).
  After a high- or a low-scoring half the book does not miss in one direction: the final minus the book's total runs from -0.57 to +0.64 across the surprise bins at DraftKings, with no pattern.
  Where the book departs from the mechanical line, most of the departure is noise: slope -0.68 (SE 0.23) at DraftKings, and -1.13 at Pinnacle. That is what P1 tried to bet.
- **Spreads: the first-half surprise is handed back at the right rate, and the pre-game margin is over-weighted.**
  DraftKings hands back 27.5% of the first-half surprise (SE 0.3). The games handed back 25.7% (SE 2.4).
  But it carries 50.2% of the pre-game margin into the second half, where the games carried 40.4% (SE 4.1). Home teams also beat the book's second half by 0.67 points (SE 0.26).
  These are in-sample fits over all seasons. The result: the pre-game favourite failed to cover the decidable books' halftime number in every lead bin except "leads by 10+".
  It covered 42-48% in those bins and 51% at 10+. That holds whether the favourite trails or leads.
  This is the mechanism the spread leads trade. The walk-forward margin model carries 0.38-0.48 of the pre-game margin, against the books' 0.50, which is why 72-78% of its bets are halftime underdogs.
  Where the book's spread departs from the mechanical number, most of the departure is information: slope +0.15 (SE 0.08) at DraftKings.

### 6.4 What a live loop would need (no live EuroLeague in-play feed exists yet)
- **Books that post halftime full-game lines.** DraftKings in every season since 2021-22: totals and spreads in 92-100% of games with a read in the break, and the moneyline in 90-97%.
  FanDuel, BetMGM, BetRivers and Fanatics from 2025-26, in 73-100% of games. Before 2025-26, DraftKings was the only book a pick may name.
- **The window.** The break runs a median 15.97 minutes from the last second-quarter shot to the first third-quarter shot (10th-90th percentile 15.38-17.16).
  Inside the one-minute buffers that leaves 13.97 minutes.
  The decidable books' first fresh total is stamped at most a median 3.10 minutes after the last shot. That leaves about 12 minutes to read and bet.
  At the five-minute cadence a break holds a median of 3 reads (2 to 5). In 2021-22, at the ten-minute cadence, it held 1 or 2.
- **Inputs.** A live score source that marks the end of the second quarter and gives the half-time score. EuroLeague's live play-by-play, which the shot chart comes from, is the obvious one.
  The lag between that source and the books cannot be measured until it runs live, so it must be logged from its first day.
  The pre-game prior: the median of the books' last pre-game spread and total, or Pinnacle's last pre-game spread for variant 2. Both are already collected before tip.
  An in-play odds poll of the five decidable books every few minutes during the break, with every read stored as its own price log.
  The decision itself: one per game, at the first read after the half ends that holds a fresh eligible quote.
- **Volume** at 0.05: A made 84, 50, 52, 100 and 26 bets in the five walk-forward seasons, the last over 104 games to date. In 2025-26 that was 100 bets on 376 games with five books, about one game in four.

### 6.5 What would change the verdict
The spread is the one market with a mechanism, a passed placebo, a plateau and blind controls that lose. It still misses the multiplicity bar, one season is negative in each version, and the earliest season reads negative on a second look.
What would move it is games it has never seen. Freeze variant 2 at cut 0.05 as it stands (Pinnacle's close as the prior, the walk-forward fit on every earlier season), and read it unchanged on games after 2026-11-12. That needs halftime prices stored from now on.
The total and the moneyline are null as ported. P1 is a frozen after-the-fact lead, to be read the same way.
"""

if __name__ == "__main__":
    text = F.read_text(encoding="utf-8")
    if "\n## 6. Verdict" in text:
        text = text.split("\n## 6. Verdict")[0]
    F.write_text(text.rstrip("\n") + "\n" + V, encoding="utf-8")
    print(F.stat().st_size, "bytes")
