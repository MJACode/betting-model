# The NFL opener spread model's ceiling: no bet on a gap no real number has shown

**Rule (mike, 2026-11-24):** the opener spread model does not bet a book that is
more than **5.0 points** off Pinnacle's spread. Such a quote is dropped as a feed
error before the game's largest gap is chosen, so a believable second book on
the same game still bets. The declined audit row names the dropped quote.
Code: `MAX_DEV` and `beyond_ceiling` in `nfl/models/opener_spread.py`. Tests:
`tests/test_nfl_opener_dev_ceiling.py`.

## What happened

At 20:56:01 UTC on 2026-11-24 The Odds API served BetMGM's PHI @ DAL spread as
DAL +5.5 (-110 / -108). One poll earlier (20:55:01) it was DAL -8.5 (-108 / -110).
Every other book stayed at DAL -8.5 (Hard Rock -9), and so did Pinnacle (-106 / -106).
The feed kept serving +5.5 for five one-minute polls, 20:56:01 to 21:00:14, the
last the archive held when this was written (`nfl_odds_history`).

The card wrote pick 4757860, "PHI @ DAL — DAL +5.5 · NEW 0m", at BetMGM -110 at
20:56:03. That was a 14-point gap. The model priced it at the clamped top of its
probability table (0.7641, the 8.0-point knot) and claimed a +24pp edge, the
largest it has ever claimed. It posted to Discord and push at 20:56:05. mike: "dal +5.5 that
doesn't exist in any way shape or form".

What the feed served is measured. Why it served it, and whether BetMGM's own
site ever showed DAL +5.5, is not measurable from here; mike's report is that it
did not.

Nothing in the model stopped a gap that size. The age label ("NEW 0m") flagged it
as a possible book error, which is the label's job. Since 2026-09-22, at mike's
direction, a new number is labelled and not blocked.

## Where 5.0 comes from

Bettable books (DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers, Hard
Rock) paired against Pinnacle at the same snapshot, two to ten days before
kickoff. Read from the local parquet mirror of `nfl_odds_history`
(`data/local/research/opener_dev_ceiling2.py`):

| Season | Paired quotes | Largest gap | Quotes ≥ 4 | Quotes ≥ 5 |
|---|---:|---:|---:|---:|
| 2020 | 15,177 | 14.5 | 1,072 | 956 |
| 2021 | 17,078 | 3.0 | 0 | 0 |
| 2022 | 17,294 | 3.5 | 0 | 0 |
| 2023 | 17,161 | 3.0 | 0 | 0 |
| 2024 | 21,612 | 2.5 | 0 | 0 |
| 2025 | 24,792 | 3.5 | 0 | 0 |
| 2026 (minute-level, to the mirror's last copy) | 3,861,082 | 14.0 | 49 | 25 |

The 2026 quotes at 4+ points, by episode:

| Game | Book | Gap | How long | What it was |
|---|---|---:|---|---|
| ARI @ SEA, 2026-11-04 | Caesars, BetRivers, BetMGM, FanDuel, Fanatics | 3.5-4.5 | 10+ min | Real. Pinnacle moved to SEA -13 and five books lagged together |
| CIN @ BAL, 2026-10-21 | FanDuel | 4.0 | 5+ min | Bet by the model (BAL +1.5), lost |
| TEN @ NYG, 2026-09-22 | BetMGM | 4.0 | ~12 min | Feed glitch, the voided 2026-09-22 pick |
| TEN @ NYG, 2026-09-24 | BetMGM | 5.5 | 3 polls | Feed glitch; the game already had its pick |
| HOU @ TEN, 2026-10-07 | BetRivers | 14.0 | 22 polls | An alternate line (+21 at -770) in the main-line slot; the Kelly sizing skipped it |
| PHI @ DAL, 2026-11-24 | BetMGM | 14.0 | 5+ polls | This pick |

**Neighbourhood.** The largest real gap ever stored is 4.5. Nothing real sits
between 4.5 and 14.
- Any ceiling from 5.5 up to 14 removes today's quote and the HOU @ TEN alternate line.
- A ceiling from 4.5 to 5.4 also removes the 2026-09-24 BetMGM glitch. 5.0 sits here.
- Below 4.5 it starts cutting ARI @ SEA-type gaps, where several books really lagged Pinnacle.

**Replay over the model's written bets.** Of the 34 BETs the model has written
this season, every one but pick 4757860 was priced at or below 0.6259, the
4.0-point knot of a table that only rises with the gap. So every one of them had
a gap of at most 4.0. The ceiling would have removed exactly one bet: this one.

## What it does not catch

A phantom inside the ceiling. TEN @ NYG on 2026-09-22 was 4.0 points at its
widest and 2.0 at the tick that fired, and this rule would still bet it.

## Found on the way: the 2020 BetMGM rows are in the backtest

2020 holds about 1,000 BetMGM quotes 3 or more points off Pinnacle. 2021-2025 hold
none, so this is a 2020 feed defect, not real numbers. The backtest behind the
2.0-point cut reads the same rows (`nfl/data/processed/dev_long.parquet`: 939
BetMGM quotes ≥ 5 points across 95 games in 2020, none in any other season). In
the model's own cut sweep (`nfl/scripts/opener_cut_sweep.py`), 18 of the 25
bets at 3+ points are 2020. Those 18 came out about flat (-1.3%). The seven in
2021-2025 all lost. This is tracked as its own issue; the ceiling does not
change the backtest.
