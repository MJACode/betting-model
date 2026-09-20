# NFL 2026 paper-track — opener and wind, no unit bump

> Policy encoded 2026-09-14. Not a threshold change and not a unit increase.
> Re-score: `python -m scripts.nfl_rule_2026_track` (add `--settle` to run the
> existing `paper_tracker` grader on any still-unsettled dates first).

## The policy

1. **`nfl_opener_spread`** — paper-track through 2026 with **no unit bump**.
   Retire if 2026 finishes **≤ flat** on standing settled BETs (`signal_type='BET'`,
   result in WIN/LOSS/PUSH; VOID is not the record). The six-season restatement
   already spans zero: 2024 carried, 2020–22 lost (`nfl/models/opener_spread.py`).
   **Do not unpause** the paused distributional / XGB NFL props
   (`config.PAUSED_MODELS`: pass/rush/rec yards and attempts, TDs, sacks, …)
   as a response to this track.
2. **`nfl_wind_totals`** — keep the physical residual. **`MAX_FIRE_LEAD` stays 4.** Do not widen the fire window.
   Measure the deployed Open-Meteo *issued-forecast* population (not observed
   wind). 2024 and 2025 lost on observed wind; the first measurement of the
   deployed population is `docs/nfl_wind_lead_evidence.md` (lead-3 issued
   forecast, 2024–2025: 47.5% under on n=101 vs 46.0% outdoor base). Do not
   widen the fire window.
3. **Do not change live pick emission thresholds** unless a bug is clearly
   sending bets past `MAX_FIRE_LEAD=4`. The tracker flags any standing wind
   BET locked outside that window; it does not loosen the gate.

Units stay `UNIT_PCT = 0.01` on both cards. Wind `MAX_UNITS = 2`. Opener
`MAX_UNITS = 4`. A good month does not raise them.

## 2026-09-20 — the two rules carry their own EV floor (mike)

The platform's global EV floor (0.30 on 2026-09-19, 0.20 from 2026-09-20)
switched both rules off: across every bet either has written, the EV on the
rule's own probability is 0.058-0.100 for wind (5 bets) and 0.011-0.053 for
opener (9 bets), and the pooled calibration offset took wind's 0.574 to 0.510.
A rule that never bets cannot be tracked. mike: *"give wind and opener their
own floors"*. `config.MODEL_OWN_EV_FLOOR` (wind 0.05, opener 0.01 -- set just
under the smallest bet each has written, NOT swept) and
`config.MODELS_ON_OWN_PROBABILITY` (both decide on the rule's own lookup until
they have 50 graded bets). This restores how they bet before 2026-09-19; it is
not a new threshold and not a unit change, and everything above still holds --
including that the wind rule's measured issued-forecast under rate is 47.5% on
n=101, which is under break-even at -110.

## How to re-score in October (or at season end)

```bash
python -m scripts.nfl_rule_2026_track                  # read the 2026 record
python -m scripts.nfl_rule_2026_track --settle         # settle then read
python -m scripts.nfl_rule_2026_track --season 2026
```

The production grader is unchanged: `python -m tracking.paper_tracker --date YYYY-MM-DD`
already settles these two models through the generic totals/spreads path
(`paper_tracker._NFL_MODEL_MARKETS`). `--settle` on the tracker is that grader
pointed at the dates that still hold an unsettled opener or wind BET, so October
does not have to hunt.

Historical / issued-forecast population (zero Odds API credits, needs the
gitignored weather cache):

```bash
cd nfl
python scripts/forecast_persistence.py                 # deployed Open-Meteo flag
python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3 --settle
python scripts/replay_opener_card.py --season 2025 --week 1 --settle
```

`replay_wind_card.py` opts out of `MAX_FIRE_LEAD` on purpose (a backtest that
inherits the live firing gate reports a lie). The live card does not.

## 2026 record as of 2026-09-14

Queried production `picks` on the Betting Model Supabase project
(`model_id IN ('nfl_opener_spread','nfl_wind_totals')`, `signal_type='BET'`).
Units = `profit_flat / 100` on priced rows.

### `nfl_opener_spread`

| bucket | n | notes |
|---|---|---|
| Standing settled BETs | **2-0, +1.74u, ROI +87.0%** on 2 priced | too thin to retire or hold on |
| VOID | 7 | re-cut 2026-09-11 below \|dev\| ≥ 2.0; not the record |
| Unsettled | 0 | |

Quoted from their labels:

- `SF @ LA — SF +4.5 (Opener -1 vs Pinnacle, DK) · 0.57u` — WIN, +0.87u.
  Locked under the old 1.0-pt rule; already settled when the 2.0 cut landed, so
  it stands (§1c). `condition_status='GONE'` is the monitor (soft book caught
  up), not a retraction.
- `BUF @ HOU — BUF +1 (Opener -2 vs Pinnacle, fanatics) · 0.98u` — WIN, +0.87u.
  The deployed \|dev\| ≥ 2.0 pick. Monitor later marked GONE (`deviation +0.50
  below the 2.0 pt threshold`) — line movement after lock.

On the **deployed 2.0 cut alone** the 2026 settled sample is one pick (BUF @
HOU). The retire-if-flat rule grades the standing BET record, which includes
SF @ LA because it was written as a BET. VOID rows stay out.

**Verdict today:** HOLD. Season is not over. Retire at the end of 2026 if that
record is ≤ flat.

### `nfl_wind_totals`

| bucket | n | notes |
|---|---|---|
| Standing settled BETs | **0** | nothing to ROI |
| Unsettled | 1 | `DEN @ KC Under 43.5 (Wind 12 mph, DK) · 1.15u` (pick_id 1969489). `games.home_score` / `away_score` still NULL on 2026-09-14. Created 2026-09-11 for a 2026-09-14 kick — inside MAX_FIRE_LEAD=4. |
| VOID / deleted Week-1 long-lead | 6 | fired at 7.2–8.7 days; VOID 09-07, DELETE 09-11. Not the record. |

**Verdict today:** HOLD. Physical residual, `MAX_FIRE_LEAD` stays 4, no unit
bump. 2024/2025 observed-wind losses stand as the live-risk caveat in
`nfl/models/wind_totals.py`; 2026 is the first season graded on the deployed
Open-Meteo + T-4 population.

## What this is not

- Not a unit increase, a cut move, a pause, or an unpause.
- Not a reason to unpause `nfl_prop_pass_yards` and the other ten distributional
  props. Their pause is `docs/nfl_props_model.md` §5b, independent of these two
  rules.
- Not a reason to fire wind past 4 days because 2024–2025 “need more volume”.
  Volume at a lead with no measured forecast error is the Week-1 failure mode.
