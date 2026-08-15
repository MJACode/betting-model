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

The early-week opener signal is real but marginal once priced honestly: +6.98%
ROI at the juice books actually quote, 95% CI [-0.6, +14.5]. Books charge for a
better number almost exactly what the number is worth.

## Quickstart

```bash
pip install -r requirements.txt
export THE_ODDS_API_KEY=...

python scripts/weekly_wind_card.py --days 2     # live card, 1 credit
python scripts/weekly_wind_card.py --dry-run    # weather only, 0 credits
```

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
scripts/replay_wind_card.py      regression test against a completed week
scripts/validate_wind_forecast.py  every number behind the wind rule
scripts/screen_books.py          per-book integrity screen
scripts/backtest_opener.py       opener strategy, correctly priced
data/odds_cache/           ~45,000 credits of Odds API snapshots
data/weather_cache/        Open-Meteo pulls
```

## Reproduce everything

All of this costs zero Odds API credits; it runs off the committed cache.

```bash
python scripts/screen_books.py --rebuild --write
python scripts/validate_wind_forecast.py
python scripts/backtest_opener.py --placebo draftkings
python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3 --settle
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
