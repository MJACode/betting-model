# NHL derivative totals — team, alternate, first period

Michael, 2026-10-02: buy `team_totals`, `alternate_totals` and `totals_p1` and
build the models. The full-game total had already failed (every over −4.0%,
every under −4.4% on six seasons; `docs/nhl_market_lab.md`, "Read, total
goals").

**Nothing cleared. Not publishing.** `models/nhl_derivative_totals.py` keeps
`PUBLISHED = ()`. The three ids (`nhl_team_total`, `nhl_alternate_total`,
`nhl_p1_total`) are not in `config.ACTION_THRESHOLDS` and not in
`config.PAUSED_MODELS`. `scripts/nhl_derivative_totals_card.py` writes nothing
and is not a pipeline step.

## What was graded

`python -m scripts.nhl_derivative_totals_backtest --cache <extract>`. The
extract is the stored pre-game rows with `odds.source =
odds_api_nhl_totals_history`: **264,043 quotes, 4,192 games**, ending seasons
2024 / 2025 / 2026 (1,400 / 1,398 / 1,394 scored games, every one of them with
an alternate total and a first-period total). The same extract's games file
has **16 scored 2027 games and zero derivative rows** for them. Books in the
rows: betmgm, betrivers, bovada, draftkings, fanatics, fanduel, hardrockbet,
pinnacle, williamhill_us. DraftKings posted **no team total** in the extract
(FanDuel team totals: 1,306 / 1,384 / 1,377 games by season).

Walk-forward: 8,384 team-games, both means on all 4,192 games. Goal
dispersion on the training rows: **0.000**, so the probability is Poisson.
One bet per game (per team, for team totals): the best-EV line on that side.
Price floor −200 is `config.DEFAULT_MIN_ODDS`. Returns are flat-bet **units**.
The interval is a day bootstrap, 4,000 resamples, seed 7. A side is
publishable only with ≥200 bets, ≥2 seasons of ≥30 bets all with a positive
mean, both date-halves positive, and the interval entirely above zero. The
0.10 cut is a rule only when 0.08 and 0.12 clear the same way.

Removing the price floor did not change which cuts cleared. Those tables are
in the backtest output and are omitted here.

## Blind, the line whose over is closest to −110

DraftKings alternate totals. Both sides lose in every season.

| side | bets | units | roi | 95% by day | clears |
|---|---:|---:|---:|---|---|
| over | 3,751 | −255.7 | −6.82% | −9.5 .. −4.0 | no |
| under | 3,750 | −237.6 | −6.33% | −9.8 .. −3.0 | no |

DraftKings 1st-period total. Both sides lose in every season.

| side | bets | units | roi | 95% by day | clears |
|---|---:|---:|---:|---|---|
| over | 3,989 | −278.9 | −6.99% | −9.7 .. −4.4 | no |
| under | 3,989 | −190.6 | −4.78% | −7.9 .. −1.7 | no |

FanDuel team total, **regulation** (three periods). The under is the only
blind row that passes `publishable`.

| side | bets | units | roi | 95% by day | clears | early | late | 2023-24 | 2024-25 | 2025-26 |
|---|---:|---:|---:|---|---|---:|---:|---|---|---|
| over | 8,134 | −1,095.7 | −13.47% | −15.3 .. −11.6 | no | −14.8 | −12.2 | −15.5% (2,612) | −11.7% (2,768) | −13.3% (2,754) |
| under | 8,101 | +186.5 | +2.30% | +0.3 .. +4.3 | yes | +3.8 | +0.8 | +4.2% (2,612) | +0.7% (2,766) | +2.1% (2,723) |

Same quotes, **full-game** goals (overtime included). The under flips sign.

| side | bets | units | roi | 95% by day | clears |
|---|---:|---:|---:|---|---|
| over | 8,134 | −550.0 | −6.76% | −8.6 .. −4.9 | no |
| under | 8,101 | −358.3 | −4.42% | −6.4 .. −2.4 | no |

DraftKings' 2024 house rules said a pre-game team total excludes overtime.
The current rule is unverified (`docs/nhl_market_research.md`). A side that
wins on only one of the two settlements is not publishable, and this one is
a blind fade rather than the model. Not published.

## Model, price floor −200

Alternate total at DraftKings: overs about −18% to −23%, unders about −8% to
−12%, every season negative, plateau no. At the best bettable price the
under at EV ≥ 0.10 is −13.27% on 3,765 bets (−499.7 units, −21.0 .. −5.2).

1st-period total at DraftKings: no cut clears. The under at EV ≥ 0 is −3.78%
on 763 (interval through zero). At the best bettable price the under at
EV ≥ 0.10 is −2.30% on 748 (interval through zero); 2025-26 is negative.

Team total, best bettable price, **regulation** settlement. Overs −16% to
−23%. Unders:

| EV ≥ | bets | units | roi | 95% by day | clears | early | late |
|---:|---:|---:|---:|---|---|---:|---:|
| 0.00 | 3,277 | +79.2 | +2.42% | −0.9 .. +5.8 | no | +4.1 | +0.8 |
| 0.03 | 2,496 | +81.0 | +3.24% | −0.5 .. +7.1 | no | +3.5 | +3.0 |
| 0.06 | 1,847 | +78.2 | +4.23% | −0.5 .. +8.9 | no | +3.4 | +5.0 |
| 0.08 | 1,465 | +90.9 | +6.21% | +1.2 .. +11.6 | yes | +3.4 | +9.0 |
| 0.10 | 1,132 | +56.4 | +4.98% | −1.0 .. +10.8 | no | +2.8 | +7.1 |
| 0.12 | 843 | +62.6 | +7.42% | +0.1 .. +14.9 | yes | +5.8 | +9.1 |
| 0.15 | 528 | +64.7 | +12.26% | +3.1 .. +21.5 | yes | +12.9 | +11.6 |

The 0.10 cut's interval includes zero, so there is no plateau. The same
unders on the **full-game** score are −1.78% at EV ≥ 0.10 (1,132 bets,
−20.2 units, −8.0 .. +4.1). Not published.

Ablation of the alternate total, best bettable, EV ≥ 0.10, floor −200.
Dropping shots or rest does not turn the loss into a win.

| features | side | bets | units | roi | 95% by day |
|---|---|---:|---:|---:|---|
| no shots | under | 3,879 | −518.1 | −13.36% | −20.8 .. −5.4 |
| no shots | over | 1,729 | −406.8 | −23.53% | −38.0 .. −7.8 |
| no rest | under | 3,786 | −468.3 | −12.37% | −20.0 .. −4.1 |
| no rest | over | 1,764 | −463.0 | −26.25% | −40.4 .. −10.4 |

## The buyer

`python -m data.ingestors.nhl_derivative_odds_history` prints the plan and,
when `ODDS_API_KEY` is set, the credits a three-game probe actually billed.
`--apply` buys every scored game in ending seasons 2024–2027 that does not
already have `odds.source = odds_api_nhl_totals_history` or a row in
`nhl_derivative_odds_pulls`. One pre-game snapshot, an hour before that
day's first puck, ten books (the same list as
`scripts/nhl_odds_history_backfill.py`).

Michael, 2026-10-03: there is no credit cap. The script does not take
`--max-credits`, does not keep a reserve, and does not stop because a quota
plan refused. A re-run buys nothing already stored.

This session did not call the Odds API. `ODDS_API_KEY` was not in the
environment, and the Railway account visible from here (created 2026-10-02)
has no projects, so the worker's key was not readable. Nothing was spent.
