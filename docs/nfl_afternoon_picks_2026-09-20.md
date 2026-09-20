# NFL afternoon board, 2026-09-20 — only tackles on the app

Measured 2026-09-20 ~20:16 UTC (4:16 PM ET). Production `picks` /
`model_action_thresholds` / `api_call_log` via Supabase `execute_sql`. No
code change. Do not un-void Saturday's rows unless Michael says so.

## What Matt saw

NFL Picks → **Today**: scored rows that are all `nfl_prop_tackles_assists`
(64 NONE + 1 AVOID). Header should read **0 bets · 65 scored** (or that
count minus any game `isGameOver` has dropped; NFL has no duration fallback,
and `games.home_score` is still NULL, so all 65 stay).

NFL Picks → **Signals**: empty. There is no standing pre-game BET.

NFL Picks → **Live Signals**: 7 `nfl_live_prop` BETs, all pass-attempts,
1pm ET games only. Those rows are `is_live` and are excluded from Today.

## Verdict

**(C) + (D), with (A) as the display consequence of hide-paused.**

| Hypothesis | Result |
|---|---|
| (A) mobile filter stuck on tackles / wrong sport query / leftover deep-link | **No.** Sport change resets the filter. The list query is `picks` where `game_date = todayET` and `is_live` is not true (`fetchPicksForDate`). After `useTodayPicks` drops paused + VOID, the only remaining NFL rows *are* tackles. |
| (B) API / feed returns only tackles | **No.** The same date has 733 non-VOID NONE rows on the eleven paused distributional props. The client hides them. |
| (C) publisher only wrote tackle BETs for the afternoon slate | **Partly.** The publisher wrote **zero** new pre-game BETs today. The four Saturday tackle BETs were VOID'd. Today's tackle scorer wrote NONE/AVOID only. |
| (D) EV floor + Saturday VOID + one-read-per-game + hide-paused | **Yes.** This is the full cause. |

Not #780 (PickCard is display-only). Not a missed #766 publish hour — the
13:xx UTC `nfl-prop-card` tick ran (175 `api_call_log` rows, `ok=true`).

## Mobile list path (what the NFL tab expects)

```
fetchPicksForDate(todayET)
  picks: game_date = today, is_live IS NOT TRUE, limit 5000
  + fetchUpcomingNflPicks(after today … +11d)   # no 2026-09-21..28 BETs exist
useTodayPicks keeps a row only if
  !isGameOver && !retired && !paused && condition_status !== 'VOID'
Today  = those rows (BET / AVOID / NONE)
Signals = those rows that pass passesActionFilter (BET, not paused, not VOID)
```

`model_action_thresholds.paused` (synced 2026-09-20 20:16 UTC) matches
`config.PAUSED_MODELS`. Live NFL models: `nfl_prop_tackles_assists`,
`nfl_prop_market`, `nfl_wind_totals`, `nfl_opener_spread`, `nfl_live_prop`.
The eleven other `nfl_prop_*` ids are paused (#774 hides them from Today).

## What is in `picks` for game_date 2026-09-20

Pre-game BETs, all written **Saturday 2026-09-19** (or earlier), all VOID:

| model | n | voided | why (`condition_note`) |
|---|---|---|---|
| `nfl_prop_market` | 25 | 2026-09-19 18:48 UTC | Kalshi ladder, no sharp book (#771) |
| `nfl_prop_market` | 23 | 2026-09-19 22:08 UTC | under the 2026-09-19 global EV floor; mike |
| `nfl_prop_tackles_assists` | 4 | 2026-09-19 22:08 UTC | same EV-floor void |
| `nfl_wind_totals` | 4 | 2026-09-19 22:08 UTC | same EV-floor void |

Today's scorer output, still standing:

| model | signal | n |
|---|---|---|
| `nfl_prop_tackles_assists` | NONE | 64 |
| `nfl_prop_tackles_assists` | AVOID | 1 |
| eleven paused `nfl_prop_*` | NONE | 733 |
| `nfl_live_prop` | BET | 7 (`is_live`, Live Signals only) |
| `nfl_live_prop` | AVOID | 19 |

`nfl_prop_market` / `nfl_wind_totals` / `nfl_opener_spread` wrote **no**
non-VOID row today.

Tackles NONE/AVOID: 0 of 65 clear the live cut (`min_prob` 0.70 and
`min_edge` 0.15 together). Max edge 0.181; max prob 0.708; no row has both.

## Why today's 13:xx pass wrote nothing

Morning worker log (already in `docs/sessions/2026-09.md`, 13:25 UTC pass,
floor still 0.30): 3,494 quotes, 4 cleared the market edge cut, all 4 dropped
`ev_below_floor`. Best EV **0.209** (Jonathan Taylor Under 2.5 Rec +120) —
that is IND @ KC, kickoff **2026-09-21 00:20 UTC / 8:20 PM ET**.

Then, same day, in this order:

1. #793 `GLOBAL_MIN_EV` 0.30 → 0.20 (those 4 would now clear).
2. #794 / #796 own floors. `nfl_prop_market` **stays 0.20** (mike, on its
   19-20 −2.49u record). Wind 0.05 / opener 0.01.
3. #766 one-read-per-game: `publishable_games()` is empty after 13:xx UTC
   unless that hour never ran. It ran. Later hourly ticks fetch the board
   and **do not publish**.

So the four market bets that would have posted at 0.20 were left on the
floor because the only legal publish hour had already fired under 0.30.

VOID + first-signal lock: `models/scorer.py` locks any `signal_type='BET'`
including VOID. `scripts/nfl_prop_market_card.publish` skips a proposition
that already has a row, including VOID. Saturday's voids therefore occupy
those games / propositions. That is existing lock behaviour (and the
2026-09-19 first-signal-repair guard: do not re-announce a voided lane).
Not changed here.

## Still-open kickoffs (as of 20:16 UTC)

| game | kickoff UTC | notes |
|---|---|---|
| afternoon window 20:05 / 20:25 | already started | too late for a new pre-game lock |
| `NFL_2026_02_IND_KC` | 2026-09-21T00:20Z | SNF. Wind VOID occupies the lock. Taylor 0.209 was the best 13:xx drop. |
| `NFL_2026_02_NYG_LA` | 2026-09-22T00:15Z | Monday. No BET row of any model. |

## Ops checklist (Matt / Michael)

Do **not** invent a mobile fix. The board is showing the rows the filters
are supposed to keep.

1. **Confirm the segment.** Today = tackle NONE/AVOID. Signals = empty.
   Live Signals = 7 pass-attempt overs. If Signals is empty and Today is
   only tackles, the app matches production.
2. **Do not un-void** the 56 Saturday BETs unless Michael explicitly
   reverses the 2026-09-19 Kalshi / EV-floor voids. §1c: a VOID is an exit.
3. **SNF market bet (Michael gate).** The 13:25 UTC pass found 4 edges;
   best 0.209 on IND @ KC. A one-off `nfl-prop-card --publish` after 13:xx
   is an exception to #766. Only if Michael wants that hour replayed under
   the 0.20 floor. Afternoon games are already underway; this is SNF/Monday
   only.
4. **Do not lower `nfl_prop_market`'s 0.20 floor** from this incident.
   #796 left it there on the written record. Largest EV across its 90
   historical BETs is 0.227; most Sundays at 0.20 will look like this.
5. **Wind / opener** already have own floors (#794). Re-firing a VOID'd
   game needs a lock-policy call, not a silent scorer change. IND @ KC
   wind is the occupied case.
6. **Tackles** is live and scored today; it did not clear its own 0.70 /
   0.15 cut. Adding it to `MODEL_OWN_EV_FLOOR` would not have created a
   BET on this slate. Michael gate if anyone wants a floor anyway.
7. **Paused props** (pass yards, rec, sacks, …) still score NONE so the
   record accrues. Unpausing is a model-policy call (`Updated-By:`), not
   an app bug. #774 hiding them from Today is why the board is tackles-only
   instead of 733 dead-zone cards plus tackles.

## Queries (re-run, do not guess)

```sql
-- standing NFL rows the Today board can keep
SELECT model_id, signal_type, condition_status, COUNT(*)
FROM picks
WHERE sport = 'NFL' AND game_date = '2026-09-20' AND COALESCE(is_live, false) = false
GROUP BY 1, 2, 3
ORDER BY 1, 2;

-- 13:xx publish tick
SELECT date_trunc('hour', ts), COUNT(*), BOOL_OR(ok)
FROM api_call_log
WHERE source = 'nfl-prop-card' AND ts >= '2026-09-20'
GROUP BY 1
ORDER BY 1;
```
