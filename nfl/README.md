# NFL Game Lines Model System

Quantitative NFL betting research and the one strategy out of it that is cleared
for live money.

The full write-up, including every negative result, lives in
[`nfl_game_lines_model_system.md`](nfl_game_lines_model_system.md). Start with
the **DOCUMENT STATUS** block at the top and the **Runbook: Wind Totals** at the
bottom.

## What actually works

**Wind-suppressed totals.** The market moves the total about 2.6 points across
the wind range while actual scoring falls about 6.2, so it prices roughly 40% of
the true wind effect. Bet the under on outdoor games with high forecast wind.

| Wind source, 2016-2025 | n | Under rate | ROI @ -110 |
|---|---|---|---|
| nflverse observed wind >= 12 | 408 | 58.09% | +10.90% |
| ERA5 reanalysis >= 12 | 354 | 59.32% | +13.25% |
| Under measured day-3 forecast error | ~385 | 57.09% | +9.00% |

The two wind sources correlate only 0.688 and agree on the `>= 12` flag just
85.8% of the time, yet the rule holds on both, and the games where they disagree
hit at 62.1% and 59.0%. That is the strongest evidence here: the effect is
physical wind, not an artifact of either data source.

This is a **standing closing-line inefficiency**, not a race. It is measured
against the closing total, so it can be bet any time up to kickoff. Roughly 35 to
49 bets a season. Small, and real.

**Live risk:** 2024 and 2025 both lost. At ~35 bets a season that is not
conclusive, but it is not nothing. The flat cap stays binding.

## What does not work

Documented so it is not re-litigated: backup-QB starts (look-ahead artifact),
home dogs, cold-weather unders (the effect reverses), referee tendencies,
divisional rematches, rest, primetime, key numbers, and middling. Fundamentals
and EPA features contribute almost nothing to game-line CLV.

The early-week **Opener** signal survives only on spreads, and only just.
Sharp-vs-soft deviation at threshold 1.0, 2023-2025, at the juice books actually
quote, benchmarked against the number bought rather than against 50%:

| market | n | excess | 95% CI | ROI actual | placebo excess |
|---|---|---|---|---|---|
| spreads | 593 | **+5.11pp** | [+1.1, +8.9] | +6.82% | +0.98pp |
| totals | 700 | +0.66pp | [-3.0, +4.3] | -1.57% | +0.56pp |
| h2h | 781 | +1.52pp | [-1.8, +4.7] | +2.07% | -1.26pp |

Totals and moneyline were scanned densely on 2026-08-17 (55,440 credits, 2,772
snapshots) and **both are null**. A totals result reported earlier that day from
the sparse cache did not survive the denser grid: its DraftKings placebo now
matches it at every threshold, which is the decisive test.

Spreads decays hard by season: +4.75%, +14.31%, +1.05% for 2023/2024/2025. The
Opener rests on one market in one season out of three and is **not cleared for
money**. The next test is 2026 out-of-sample, not another market.

## Quickstart

```bash
pip install -r requirements.txt
export THE_ODDS_API_KEY=...

python scripts/weekly_wind_card.py --days 2     # live card, 1 credit
python scripts/weekly_wind_card.py --dry-run    # weather only, 0 credits
python scripts/wind_poller.py                   # watch the board, alert on the first qualifier
python scripts/wind_poller.py --dry-run         # cadence and watchlist only, 0 credits
```

## Polling and firing

`scripts/wind_poller.py` watches the board instead of being run by hand. It
polls hourly out to a 10-day horizon, switches to every 10 minutes once a
watched game is inside 3 hours of kickoff, and holds fire on a game until
**Pinnacle** is actually quoting a total on it. The first time a game clears the
frozen rule with Pinnacle up, it prints an alert and appends the bet to
`data/cards/fired_bets.csv`. Each game fires at most once, ever, across
restarts.

It alerts. It does not place bets, and nothing in this repo talks to a
sportsbook.

Pinnacle lives in the Odds API `eu` region, so the default is `--regions us,eu`
at 2 credits a tick, roughly 500-700 credits a week. Pinnacle **gates**; it does
not price. Selection and the de-vig still run off the book being bet, exactly as
validated, and the Pinnacle de-vig rides along as a diagnostic.

Firing early is not free. The measured under rate falls about 0.41pp per day of
forecast lead, so a lead-7 fire is worth 0.58 units where a lead-3 fire is 1.00.
Past lead 7 there is no measured forecast error at all and the poller reports
the game as watch-only rather than betting it.

```bash
python scripts/selftest_poller.py    # offline: gate, fire-once, cadence. 0 credits
```

## How much to bet

`scripts/stake_sizing.py` derives it; `models/wind_totals.py` implements it.

**1 unit = 1% of bankroll.** A bet is sized Kelly-proportionally: its own full
Kelly over the reference bet's (lead 3, threshold 11, -110), capped at 2 units,
then shaded by `1/sqrt(1+(k-1)rho)` on a k-game slate because same-day wind
games share a weather system. The 3% minimum edge against the de-vigged market
is unchanged; it gates, it does not size.

Full Kelly on the measured edge is 9.1% of bankroll, so anywhere below about 2%
the growth curve is still linear: median three-season return is 8.3 to 8.9 times
the stake at every size in that range. Nothing in the mathematics picks a number
there. Only a drawdown budget does, which is why the unit is stated as a policy
and not dressed up as an optimum.

| 3-season sim, flat stake | median | 5th pct | P(down) | P(DD > 35%) |
|---|---|---|---|---|
| 0.50% | +4.4% | -7.4% | 28% | 0% |
| **1.00%** | **+8.6%** | **-14.6%** | **29%** | **0%** |
| 2.00% | +16.2% | -27.8% | 30% | 7% |
| half Kelly (4.6%) | +29.1% | -56.9% | 35% | 58% |
| full Kelly (9.1%) | +17.8% | -88.0% | 45% | 96% |

The true rate is drawn once per simulated world and held, because you do not get
a fresh one each week; 25% of worlds assume the market has already priced wind.
That asymmetry is the argument for a small stake: at a true rate of 52%, inside
the confidence interval, a 1% stake loses 1.2bp a bet while full Kelly loses
45bp — 38 times the damage for 4.8 times the upside.

Needs egress to `api.open-meteo.com`. Some sandboxes block that host with a proxy
403 while allowing the archive and historical hosts; run the live card from a
machine with open egress.

## Layout

```
data_ingest/weather.py     Open-Meteo: ERA5, issued forecasts, live forecasts
data_ingest/odds_api.py    The Odds API, historical (cached) and live
data_ingest/parse.py       snapshot payloads -> tidy frames
models/wind_totals.py      the frozen rule, calibrated probabilities, staking
models/ev_engine.py        general EV / de-vig helpers
features/build.py          feature matrix
scripts/weekly_wind_card.py      LIVE: the weekly bet card
scripts/wind_poller.py           LIVE: poll, wait for Pinnacle, fire once
scripts/selftest_poller.py       offline test of the poller's gating
scripts/replay_wind_card.py      regression test against a completed week
scripts/stake_sizing.py          where the unit size comes from
scripts/calibrate_lead.py        under rate by forecast lead, 1 to 7 days
scripts/validate_wind_forecast.py  every number behind the wind rule
scripts/screen_books.py          per-book integrity screen
scripts/backtest_opener.py       Opener: spreads, totals and h2h
scripts/scan_opener_window.py    Opener: fetch the T-7..T-2 window, any market
data/odds_cache/           ~45,000 credits of Odds API snapshots
data/weather_cache/        Open-Meteo pulls
```

## Reproduce everything

All of this costs zero Odds API credits; it runs off the committed cache.

```bash
python scripts/screen_books.py --rebuild --write
python scripts/validate_wind_forecast.py
python scripts/backtest_opener.py --market all --placebo draftkings --by-season
python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3 --settle
python scripts/calibrate_lead.py
python scripts/stake_sizing.py
python scripts/selftest_poller.py
```

## Two traps that cost real analysis time

**Four books transpose home and away** on a subset of spread records:
`betanysports` (16.2% of quotes), `betsson`, `nordicbet`, `tipico_de`. Any
procedure selecting on extreme values over-samples them enormously, and a defect
in 0.4% of rows supplied 15% of selected bets. Run `scripts/screen_books.py`
whenever a new book appears. Three separate findings in this project were
reversed by data quality rather than by modelling.

**Forecast debiasing has a sign trap.** `E[forecast - truth | truth]` says
forecasts under-call high wind. `E[truth | forecast]`, the only one you can apply
live, has the opposite sign: conditioning on a high forecast, true wind regresses
down, because an extreme forecast is partly extreme noise. At lead 3 a 12-14 mph
forecast means 10.7 mph actual. Both tables are in `data_ingest/weather.py`; only
the second is used, and only as a diagnostic. Selection thresholds the raw
forecast, because that is how the rule was validated.

## Data sources

nflverse (schedules, play-by-play, results), The Odds API (historical and live
book quotes), Open-Meteo (ERA5 reanalysis, archived issued forecasts, live
forecasts). No API keys are committed; everything reads from the environment.

Note that `wind_speed_10m_previous_dayN`, the only leakage-free historical
forecast, is null before **2024-01-18**. The plain series on the historical
endpoint is near-analysis and leaks if used as a forecast.
