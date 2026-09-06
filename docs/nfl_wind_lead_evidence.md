# NFL wind totals — how far out the rule may fire, and what the evidence says

> Measured 2026-09-06 after mike asked why `nfl_wind_totals` was firing on
> nearly half the Week 1 slate. Produced by
> `nfl/scripts/forecast_persistence.py` (free — Open-Meteo, zero Odds API
> credits). Rerun it before changing `MAX_FIRE_LEAD` or `DEPLOY_THRESHOLD`.

## The question

Two different questions were tangled together, and they have different answers:

1. **Is the NUMBER on a long-lead bet trustworthy?** No, and this was never in
   doubt. `CALIBRATED_UNDER_RATE` stops at lead 7 because Open-Meteo's
   `previous_dayN` stops there, so a lead-8 probability is a clip. All five
   Week 1 picks locked at leads 7.2–8.7 days carrying `model_probability`
   0.5489 — the `(7, 11)` row exactly.
2. **How MANY bets does a long-lead card produce, and are the extra ones real?**
   That is what mike actually asked, and it needed a measurement.

## What was measured

Every outdoor 2024–2025 game with a **known** roof state and issued forecasts at
both leads (n=380). Graded on nflverse `total_line` vs `total` — the same source
as the frozen rule's published 58.09% / n=408 — so it is comparable to the
validation and needs neither the odds cache nor a credit. Pushes excluded.

```
WIND FLAG PERSISTENCE  lead 7d -> lead 3d, threshold 11.0 mph

flagged at lead 7: 83     flagged at lead 3: 102
P(still flagged at lead 3 | flagged at lead 7) = 56.6%  (47/83)

HOW EACH GROUP ACTUALLY SETTLED (nflverse closing total):
  flagged at 7d - what a long-lead card bets      46.9% under  n=81   [36.0, 57.8]
  flagged at 3d - what the 3-day gate bets        47.5% under  n=101  [37.8, 57.3]
    survived 7d -> 3d                             39.1% under  n=46   [25.0, 53.2]
    DROPPED 7d -> 3d (the gate skips these)       57.1% under  n=35   [40.7, 73.5]
    ADDED at 3d (the gate gains these)            54.5% under  n=55   [41.4, 67.7]
  every outdoor game (base rate)                  46.0% under  n=378  [41.0, 51.1]

PER SEASON:
  2024:  flagged 7d 33.3% (n=39) | flagged 3d 41.2% (n=51) | DROPPED 38.5% (n=13)
  2025:  flagged 7d 59.5% (n=42) | flagged 3d 54.0% (n=50) | DROPPED 68.2% (n=22)
```

**Lead 7 is the longest measurable lead in existence for us.** The picks that
prompted this locked at 7.2–8.7 days, which no source we have can reach. Skill
only degrades with lead, so persistence at 8.7 days is **worse** than 56.6%.

## What it supports

**The volume finding is solid and it is the answer to mike's question.** Only
**56.6%** of games flagged at lead 7 are still flagged at lead 3. A long-lead
card is not finding more edge; it is betting a set that is **~43% transient
forecast noise**, and locking it insert-once. That is the mechanism behind "way
too many picks", and it gets worse the further out you go.

`MAX_FIRE_LEAD = 4` (mike, 2026-09-06) rests on this plus the calibration
argument, which stands on its own.

## What it does NOT support, and must not be quoted as

**The settlement columns cannot adjudicate whether skipping the dropped games is
+EV, and they lean the other way.** The DROPPED set hit 57.1% under and the
SURVIVORS hit 39.1% — the opposite of what the gate's rationale would predict.
Do not read that as evidence against the gate:

- **n=35, CI [40.7, 73.5].** It straddles the base rate, breakeven, and the
  model's claimed rate simultaneously.
- **The time split destroys it** (`.claude/rules/analysis-and-thresholds.md`:
  "a pooled edge that vanishes on a time split is noise"). DROPPED is 38.5% in
  2024 (n=13) and 68.2% in 2025 (n=22). Two adjacent seasons, opposite signs,
  single-digit-to-low-double-digit counts. There is no plateau anywhere here.
- **The gate was never argued on this basis.** It is a calibration and lock
  argument: a lead-8 probability is an assumption, and insert-once makes the
  assumption permanent.

## The finding that deserves its own decision

**On the only two seasons that can be measured this way, the wind flag shows
essentially no edge over the base rate.** Flagged at lead 3: **47.5% under**
(n=101). Every outdoor game: **46.0% under** (n=378). Breakeven at −110 is
52.38%; the model claims 56.71% at that lead.

Context before anyone acts on it:

- **This is the known-losing slice, independently confirmed.** `wind_totals.py`
  already says so in its LIVE RISK block: *"2024 and 2025 both lost on observed
  wind (−8.09u and +1.73u at −110 in ERA5 terms; −3.64u and −3.55u in the
  published nflverse terms)."* 2024–2025 are the only seasons with
  issued-forecast coverage, so they are the only seasons this method can reach.
  This is not a new contradiction — it is the same two seasons, reached by a
  different route, agreeing.
- **It is 2 seasons of a 10-season validation** (2016–2025, 58.09%, n=408).
  n=101 at a CI of [37.8, 57.3] cannot overturn that, and cannot confirm it.
- The two readings `wind_totals.py` names are still the live ones and still
  cannot be separated: ordinary variance at ~35 bets a season, or **the market
  has learned to price wind**.

**Nothing was changed on the strength of this** — a threshold move is Matt's or
mike's call and carries an `Updated-By` stamp. What it does is put a number on
how long "we cannot separate them yet" can keep being the answer. The natural
next check is the same script run at `--threshold 12` (the published rule's
threshold, versus the deployed 11) and a season-by-season walk back through
2016 on ERA5 rather than issued forecasts, which `validate_wind_forecast.py`
can already produce.

## Reproducing

```bash
cd nfl
python scripts/forecast_persistence.py                              # the table above
python scripts/forecast_persistence.py --threshold 12               # published rule
python scripts/forecast_persistence.py --from-lead 7 --to-lead 1    # to game day
```

Blank-roof games are excluded from this measurement on purpose — see
`RETRACTABLE_STADIUMS` in `nfl/data_ingest/weather.py`; counting a closed roof
as open air is a separate bug fixed the same day, and it must not leak into a
measurement of the rule.
