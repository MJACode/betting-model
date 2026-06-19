# Public Track Record — website page spec (Lovable)

The mobile app already ships an in-app Track Record screen. This doc is the
build spec for the **public website** version (the marketing/trust front door at
signalbase-ai.com), which the mobile app can't render. The Supabase views are
already live and anon-readable — this is a front-end-only task.

## Why this page matters

It's the counter-positioning wedge: incumbents (touts, affiliate-funded picks
apps) can't show an honest, complete, loss-included record without undercutting
their hype. We can. This page is the proof.

## Data source (already built, anon-readable)

Two `security_invoker` views, granted to `anon`:

- `v_public_track_record` — one row per `(sport, model_id)`. Every settled BET
  pick meeting **current** action criteria since 2026-04-14. Columns:
  `sport, model_id, picks, wins, losses, pushes, profit_flat, staked_flat,
  clv_settled, clv_beat, avg_clv_pct, first_date, last_date`.
- `v_public_track_record_daily` — one row per `(game_date, sport)` with
  `picks, wins, losses, pushes, profit_flat, staked_flat`. Use for an equity
  curve (cumulate `profit_flat` over `game_date`).

Both apply the same prob/edge cuts as the app, via the `model_action_thresholds`
table, and **exclude paused models** (`paused = true`, e.g. the HR model). Flat
ROI = `profit_flat / staked_flat`; staked = `100 × picks`.

Connect with the anon publishable key (read-only). No auth needed.

```sql
-- Overall headline
select sum(picks) picks, sum(wins) wins, sum(losses) losses, sum(pushes) pushes,
       round(100*sum(profit_flat)/nullif(sum(staked_flat),0),1) roi_pct,
       sum(clv_beat) clv_beat, sum(clv_settled) clv_settled
from v_public_track_record;

-- Per sport
select sport, sum(picks) picks, sum(wins) wins, sum(losses) losses,
       round(100*sum(profit_flat)/nullif(sum(staked_flat),0),1) roi_pct
from v_public_track_record group by sport order by picks desc;

-- Per model (within a sport)
select model_id, picks, wins, losses,
       round(100*profit_flat/nullif(staked_flat,0),1) roi_pct
from v_public_track_record order by profit_flat desc;

-- Equity curve (cumulate client-side over game_date)
select game_date, sum(profit_flat) profit_flat
from v_public_track_record_daily group by game_date order by game_date;
```

## Page layout

1. **Hero** — overall flat-bet ROI (signed, color-coded), W–L–P record, total
   settled picks, and the **"beat the close X%"** CLV stat with a one-line
   explainer. Honest framing: this is paper-trading since 2026-04-14.
2. **Equity curve** — cumulative flat-bet units over time (from the daily view).
3. **By sport** — cards with record + ROI.
4. **By model** — table, sorted by profit; winners and losers both shown.
5. **Methodology footer** — flat $100 bets at the DK price we scored; current
   criteria applied to every settled pick; paused models excluded ("we stopped
   offering them"); a model isn't cleared for real money until 50+ picks,
   positive ROI, and calibration error ≤5%.

## Honesty guardrails (do not violate)

- Never hide a losing model or sport. The credibility comes from showing them.
- Don't quote a hero win-rate or annualized ROI that implies more certainty than
  the sample supports — show sample size next to every number.
- Keep the numbers reconciled with the app: both read the same views.

## Sync note

`model_action_thresholds` mirrors `config.py` / `mobile/src/lib/thresholds.ts`.
When thresholds change, update all three so the website, app, and pipeline agree.
