# NFL props — deep dive: two lanes, one of them can't see the slate

> Matt, 2026-09-07: *"the prop models were unpaused from other chats… I was
> searching for nfl_prop_market and it was not flagged… what's going on with NFL
> props, do a deep dive."*
>
> **Analysis only — no code changed.** Everything below is measured today
> against production and the live board, not read off docs.

---

## The short answer

**`nfl_prop_market` is alive and fired for the first time ever at 12:26 UTC
today.** Two picks. It was never flagged in the other chats because until
yesterday it had *never produced a pick in any sport* — there was nothing to
find.

**The eleven projection models mike unpaused yesterday are also working — but
they cannot see the slate.** Their scorer only ever looks at *today's* games,
while the card it shares a tick with looks ten days ahead. Run against a real
Week 1 Sunday they produce **112 bets**. Run against today, **zero**.

So NFL props are not broken. They are two lanes on very different footing, and
one of them is about to fire much harder than anyone has decided it should.

---

## 1. What actually happened, in order

| When | What |
|---|---|
| 2026-08-23 | Twelve projection models paused — "no NFL prop odds exist in `player_prop_odds`" |
| #215 | Twelve artifacts committed **from a replica**. All twelve failed `pickle.load` on the pipeline machine. Nobody noticed for two weeks: the family was paused, so nothing opened them, and the health check asks whether an active registry *row* exists, not whether the file behind it deserialises |
| 2026-09-06 (#532) | Session 246 finds `market_relative` **has never written a pick in any sport**. NFL cause: gated to `NFL_PROP_WINDOW_HOURS = 30`, first kickoff was 70.4h out, so the job returned free *before* its log line. Widened to **240h** |
| 2026-09-06 (#536) | Eleven of twelve models **unpaused by mike**, artifacts retrained on the pipeline machine, `tests/test_model_artifacts_load.py` added so a dead artifact can't hide again. The six go-live gates are **explicitly not met** — recorded as a decision about when to start betting, not as evidence |
| 2026-09-07 12:26 UTC | **`nfl_prop_market` writes its first two picks ever** |

**On "it was not flagged":** it genuinely could not have been. Its whole history
was zero rows. The commit that fixed it is titled *"The prop rule has never
fired, in any sport"* — the flag existed, it just landed in a different chat.

---

## 2. The two lanes

### Lane A — `nfl_prop_market` (the de-vig rule)

Take Pinnacle's price as truth, de-vig it, bet where DraftKings disagrees by
more than the juice. **+10.33% over 954 bets, positive in all three seasons.**
Only compares equal lines. Trades 8 markets; Pinnacle declines four, and a
market maker declining is treated as information.

Today's two picks:

| Pick | Line | DK | Model | Edge |
|---|---|---|---|---|
| Joe Burrow **Over 24.5** completions | 24.5 | +101 | 0.528 | +5.9% |
| Bo Nix **Under 1.5** pass TDs | 1.5 | −178 | 0.656 | +5.1% |

Both for games on 13–14 Sept, both found ten days out. Working as designed.

### Lane B — the eleven projection models

Predict the player's number from scratch, bet where it beats the quote. Live
since yesterday **on placeholder thresholds**, with the go-live gates unmet by
decision, and with `nfl_prop_tackles_assists` held back on a re-measurement.

---

## 3. The finding: the scorer is pinned to today, the card is not

Both lanes run in **one tick** (`scheduler.py:run_nfl_prop_card`), off **one**
board fetch — card first, scorer second, then publish. That design is right, and
the comment explaining it is careful.

But the two halves disagree about *which days exist*:

```
nfl_prop_market_card   --days 10   →  start .. start+10d      (a 10-day range)
run_nfl_prop_scorer    game_date = target_date  →  ONE exact day, and
                       target_date defaults to today_et()
```

`_nfl_kickoff_map` (`models/scorer.py:3842`) is `WHERE game_date = %s`. A single
date. The scheduler passes no date, so it is always today.

**Measured today, both by dry run:**

| Scored for | Result |
|---|---|
| **2026-09-07** (today — no NFL games) | `no scoring rows` × 12 → **0 BETs** |
| **2026-09-13** (a real Week 1 Sunday) | **112 BETs / 551 picks** |

So the eleven models will produce nothing until the morning of a game day, and
then only for that day. Meanwhile the card will have spent ten days of hourly
ticks claiming propositions ahead of them.

There is precedent for the fix: **#532 already did exactly this for MLB** —
*"Score props for tomorrow too, and stop announcing them under today's date."*
NFL did not get the same treatment.

---

## 4. The duplicate risk is already handled — well

I went looking for a collision (both lanes betting the same player, possibly
opposite sides) because the unique index is
`(game_date, model_id, game_id, player_id, pick_side)` — **`model_id` is in the
key**, so nothing at the database level stops it.

It is handled in the scorer instead, and the reasoning is sound
(`models/scorer.py:3908-3926`, mike 2026-09-06 *"no dupes"*):

- claimed at the **proposition** level (game, player, market), not by side —
  "two models taking opposite sides of the same line is the worst version of
  this, not an exception to it";
- **`nfl_prop_market` wins**, because it is the one with a measured record;
- a **write-time skip, not a delete** — §1c, a pick that exists is never removed;
- the card runs first in the tick, so the claim is in place before the scorer
  looks.

Confirmed working: the 13 Sept dry run reports `1 skipped — nfl_prop_market
holds them`.

---

## 5. The thing I would actually worry about: volume

Per-model BETs for **one Sunday** (2026-09-13):

| Model | BETs | scored | BET rate |
|---|---:|---:|---:|
| `nfl_prop_rec_yards` | 35 | 116 | 30% |
| `nfl_prop_receptions` | 25 | 104 | 24% |
| `nfl_prop_rush_yards` | 12 | 29 | **41%** |
| `nfl_prop_rush_attempts` | 12 | 26 | **46%** |
| `nfl_prop_rush_rec_yards` | 8 | 25 | 32% |
| `nfl_prop_pass_tds` | 6 | 32 | 19% |
| `nfl_prop_pass_yards` | 5 | 32 | 16% |
| `nfl_prop_pass_attempts` | 4 | 36 | 11% |
| `nfl_prop_pass_completions` | 4 | 30 | 13% |
| `nfl_prop_anytime_td` | 1 | 121 | 1% |
| `nfl_prop_sacks` | 0 | 0 | — |
| `nfl_prop_tackles_assists` | 0 | 0 | — |
| **Total** | **112** | | |

Three things in that table:

1. **112 bets on one Sunday, from models whose thresholds were never tuned
   against a price.** For scale, the lane with the measured record produced
   **two** picks across a ten-day board. The ratio is 56:1 in favour of the lane
   with no evidence.
2. **A 41–46% BET rate on the rushing models is not a selective model.** A cut
   that fires on nearly half of everything it sees is a placeholder, and
   `docs/nfl_props_model.md` says exactly that.
3. **`sacks` and `tackles_assists` produced 0 BETs and 0 non-BETs** — they
   evaluated 177 and 136 players and wrote *nothing at all*, not even dead-zone
   rows. That is the "publishes nothing looks like switched off" signature
   again, in a third place. Worth a look before Sunday.

---

## 6. What I would do, in order

Nothing here is changed — items 1 and 2 alter what a model does, so they are
mike's or Matt's call and need an `Updated-By:` trailer.

1. **Decide the volume before Sunday.** 112 prop bets in one slate, on
   placeholder cuts, is a position size nobody has actually chosen. Options:
   tighten the placeholder thresholds; cap bets per model per slate; or accept
   it deliberately and record that, the way `nfl_live_prop` going live with its
   gate unmet was recorded.
2. **Give the NFL scorer the same look-ahead the card has** — the MLB fix from
   #532 applied to NFL. Until then the eleven models only fire on game day, and
   only for that day, which also means their picks land at the *worst* offset
   (closest to kickoff, most efficient line) rather than the ten-day spread the
   card enjoys.
3. **Check `sacks` and `tackles_assists`** — zero rows of any kind is not a
   quiet market, it is a missing input.
4. **Watch the first real tick.** The next card runs hourly; the first slate it
   can actually score is Thursday 10 Sept.

---

*Written 2026-09-07. Measured against production (`picks`, `model_registry`),
the live Odds API board, the Railway worker logs, and two dry runs of the
scorer. No code, config or threshold was changed.*
