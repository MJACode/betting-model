# Discord — picks to your server

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> **This file is about PUBLISHING picks to Discord (webhooks, no bot).**
> Discord as a paid MEMBERSHIP — account linking, the subscriber role, and the
> rule that one membership covers both the app and the server — is a separate
> system with its own bot and its own runbook:
> **`mobile/docs/DISCORD_LINKING.md`**. The two share nothing but the server:
> the notifier posts through incoming webhooks and holds no bot token, while
> linking needs a bot with Manage Roles. Adding a bot did NOT change how picks
> are published.

## 30. Discord — picks to your server (webhooks)
Added 2026-08-24. Picks post to a Discord server over **incoming webhooks** — no
bot, no gateway connection, nothing extra to host. Full setup runbook (creating
the webhooks, the variable table, testing, turning it off) is in
**`docs/cloud_worker.md` → "Discord — picks to your server"**. This section is
the engineering summary.

### Routing — one channel per sport

`config.DISCORD_WEBHOOKS` is built from `DISCORD_WEBHOOK_{SPORT}` env vars over
`config.DISCORD_SPORTS` (listed literally because `SPORTS` is defined ~600 lines
further down config.py, and a webhook variable name is user-facing and should be
stable). `DISCORD_WEBHOOK_DEFAULT` is the catch-all; unset means an unmapped
sport posts **nowhere** rather than everything landing in one room.
`DISCORD_WEBHOOK_LIVE` and `_RESULTS` get their own channels (in-play churns;
the recap is cross-sport), each falling back sensibly.

### Producers (`tracking/discord_notifier.py`)

| Function | Source of truth | Called from |
|---|---|---|
| `notify_discord_signals` | **`picks` ⋈ `model_action_thresholds`** — the same table the app reads, at the same cut as its `passesActionFilter` and the `docs/mobile_picks_prompt.md` query. Was `opening_signals` until 2026-09-05; see "One board" below | `step_push_notifier`'s step, i.e. `--step push-notifications` (6am + every refresh pass) |
| `notify_discord_live` | `picks WHERE is_live` BET rows | end of `models/live_scorer.run_live_scorer` |
| `notify_discord_results` | settled BET picks for the date, at current thresholds | inside `step_settle`, after grading |
| `notify_discord_free_pick` | ONE random qualifying signal per day (NFL preferred once the season produces signals) | same step as the signals producer |

### One board — the app, Discord and push publish the same set (2026-09-05)

**The rule is CLAUDE.md §1b; the measurements are `docs/rules_evidence.md`.**

`notify_discord_signals` and `push_notifier._new_bet_signals` read **`picks`**,
not `opening_signals`. Reading the capture table put a gate in front of the
channel that the app does not have, and capture can only ever LOSE rows relative
to `picks` — it can never add one. Measured over every eligible BET from the
first Discord signal to 2026-09-05: 125 eligible, 119 published, **6 missed, all
6 uncaptured and none captured-then-unpublished.** Delivery was never the
problem.

Consequences worth knowing before touching either producer:

- **There is no date horizon.** A pick publishes when its game has not started,
  however far ahead it was written. `_lookahead_horizon` is retired. The two
  Week 1 wind picks were 9 days out against a 7-day window and reached the app
  and nothing else.
- **The first BET wins.** `DISTINCT ON (game_id, model_id, player_id)` ordered
  by `created_at` — deliberately coarser than the `picks` unique key added in
  #487, which includes `pick_side`, so a pre-#311 side flip still collapses to
  the one bet of record (§1c).
- **The ledger key is unchanged.** Both producers synthesise
  `game_id:model_id[:player_id]`, the key `capture_opening_signals` minted, so
  `push_sent` history carries over and nothing already published republishes.
  The two `kind`s stay independent, so neither surface suppresses the other.
- **`opening_signals` is untouched** and still the opening-signal / CLV shadow
  track (`docs/opening_signals.md`). It keeps its own horizon. Never publish
  from it.
- **The started-game guard stays** — on both surfaces. It is the one bound that
  should exist.

### What a pick post shows (2026-08-24)

**Game, start time, odds, unit stake — and nothing else.** No model probability,
no edge, no book name: those are the model's IP and are not published to a
channel. `tests/test_discord_notifier.py::test_field_never_leaks_model_edge_or_book`
asserts the rendered payload contains none of them, so a future field can't
quietly add one back.

A slate posts as ONE embed with a field per pick (chunked at Discord's 25-field
cap), not a stack of one-pick embeds — much tidier in-channel:

```
⚾ MLB Picks · Sun Aug 23
  TEX ML F5
    LAA @ TEX · 2:36 PM ET
    `-154 @ DraftKings` · **1.5u to win 1u** · posted 4:07 PM ET
```

**When we got it (2026-08-30)**: every post carries `posted <time ET>` — Matt:
*"the time it writes to the database, to know the first minute we get it."*
That is **`picks.created_at`**, read through a LATERAL join on the pick row, and
deliberately NOT `opening_signals.locked_at`: the capture step runs later in the
pass, and over August it lagged the pick's own write by **28 minutes on average
and up to 6.4 hours** (the 2026-08-29 F5 picks wrote at 3:18pm and were captured
at 4:31pm), so stamping locked_at would make a stale signal look newly posted.
A missing pick row publishes no stamp rather than a wrong one. Seconds only
in-play (`posted 2:30:05 PM ET`), where a total moves a full run on one play;
the date is prefixed when it isn't today's, because an NFL opener posts days
before kickoff. Same stamp on the free pick of the day, and the same word the
app's card chip uses.

**Recap units (2026-08-27)**: the recap reports **units, not dollars**. The
wager is the units RISKED; what you win depends on the price — *risk 1.1u at
−110 to win 1u*. WIN `+stake × (decimal − 1)`, LOSS `−stake`, PUSH `0` (and
nothing counted as risked). Prob-only picks with no DK price grade at −110, the
same fallback settlement uses. `mlb_prop_batter_hr` stays record-only.

**Free pick of the day (2026-08-27)**: `DISCORD_WEBHOOK_FREE` gets ONE random
qualifying signal per day, ledgered per date so only the first pass with a
signal posts. `DISCORD_FREE_PICK_PRIORITY` (`("NFL",)`) makes it an NFL pick the
moment the season produces signals, with no date logic; until then it falls
through to whatever qualified. **No `DEFAULT` fallback on purpose** — a more
public audience than the full feed, so an unset variable posts nothing rather
than leaking the free pick into the catch-all channel.

**Unit sizing** (`units_for`): `kelly_fraction ÷ UNIT_KELLY_FRACTION` (1%),
rounded to the nearest 0.5u, so 1u ≡ 1% of roll and Kelly's 5% cap puts the
ceiling at 5u. Reads `kelly_fraction` straight off the pick — deliberately NOT
`recommended_bet`, which is dollars off the compounded bankroll (a decaying
number nobody should read a stake from). Kelly 0 or NULL (prob-only picks)
publishes the default **1u**, never 0u; a real but tiny kelly floors at 0.5u.

### Conventions (load-bearing — don't break)

- **Dedupe reuses `push_sent`** (`UNIQUE(lock_key, kind)`) with `discord_signal`
  / `discord_live` / `discord_results` kinds. Independent of the mobile push for
  the same signal, so neither can suppress the other across the ~42 passes/day.
- **Nothing is ledgered unless the POST succeeded.** This is the deliberate
  inversion of `push_notifier`, which ledgers regardless (so a signal with zero
  devices online isn't re-detected forever). Here the analogous cases — a
  webhook not configured yet, a 5xx, a rate limit — are ones we WANT to retry:
  add the NFL channel at noon and the day's remaining NFL picks still land.
  `_post_embeds` returns only the CONFIRMED-delivered count and stops at the
  first failed chunk, so a partial send can't over-ledger.
- **The recap only covers a day that is OVER.** `--step settle` runs on every
  refresh pass against **today** (grading games as they finish), while the daily
  6am pipeline settles **yesterday**. `notify_discord_results` therefore refuses
  any `game_date >= today ET` — without that guard a partial mid-slate record
  would post and be ledgered, and the real end-of-day recap could never fire.
- **Record-only models don't contribute money.** `mlb_prop_batter_hr` counts
  toward W-L but never P&L in the recap (mirrors the mobile `RECORD_ONLY_MODELS`
  and the `v_model_full_outcome_record` zeroing) — most HR picks have no real DK
  price, so counting them fabricates P&L.
- **Failures never propagate.** Discord gets its own try block in both the
  pipeline step and the live loop, so a broken webhook can't fail the step or
  mask the mobile push that already succeeded.
- **Volume is capped** per channel per run (`DISCORD_MAX_EMBEDS_PER_RUN`, 20).
  Overflow is left un-ledgered and drips out on the next pass rather than
  dumping a full locked slate into a channel the moment a webhook is added.
- Discord's own limits are respected: 10 embeds/message (`_post_embeds` chunks),
  429 honoured via `retry_after` (clamped so a bad value can't stall a step).

### Tests

`tests/test_discord_notifier.py` — 24 tests, no DB and no network. The recap
tally is pinned against the **real** production rows for 2026-08-21 (MLB 4-3
+179.36 / UFC 0-3 -300 / WNBA 1-1 -41.18), and the ledger-correctness properties
above each have a test (failed post ledgers nothing; unmapped sport isn't
consumed; cap holds overflow; dry-run writes nothing). The two detection SQL
queries were validated directly against production.
## 32. Discord delivery — what actually reaches a channel
`docs/discord.md` documents the design. This section records the delivery faults found on
2026-08-29, because all three had the same shape: **the code looked wired, and
the only symptom was an absence.**

### The three producers do not fail the same way

| Producer | Called from | Failure signature |
|---|---|---|
| `notify_discord_signals` | `--step push-notifications` (6am + every refresh pass) | a sport with no locked signal for `game_date = today` posts nothing — indistinguishable from "no picks today" |
| `notify_discord_live` | end of `models/live_scorer.run_live_scorer` AND `ncaaf_live.gameday.write_picks` | caller swallows and logs; a raise inside the notifier is invisible outside the Railway log |
| `notify_discord_results` | inside `step_settle` | refuses `game_date >= today`, so a mid-slate call is a silent no-op by design |

**`push_sent` is the ground truth for "did anything ever post".** Nothing is
ledgered unless the POST confirmed, so a `kind` with zero rows means that
producer has never once succeeded — not that it had nothing to say:

```sql
SELECT kind, count(*), max(sent_at) FROM push_sent GROUP BY 1 ORDER BY 1;
```

That one query is what turned "NCAAF picks aren't posting" into "no live signal
has EVER posted, for any sport."

### Lesson: a swallowed exception plus an expected-empty channel is invisible

`notify_discord_live` raised `KeyError('commence')` on **every** call from the
day Discord shipped (2026-08-24) until 2026-08-29. `_new_live_signals` built its
dicts from a SELECT that omitted `commence_time`; `_signal_field` subscripted
`s["commence"]`. Both callers wrap the call so a broken webhook cannot stop
pricing — correct — which also meant the fault only ever appeared as a log line
on a worker nobody was tailing, in a channel that is legitimately empty most of
the time.

Two mitigations, both in place:
- context fields (`sport`, `home`, `away`, `commence`) are read with `.get` —
  decoration must not be able to take a post down. Label, price and stake stay
  subscripted, because a pick missing those is a real error.
- `tests/test_discord_live_field.py` runs the **real producer** against a fake
  cursor and feeds its **real output** to the renderer. A hand-written fixture
  cannot catch this class of bug: it drifts from the producer in exactly the way
  the renderer did. (Written first as a hand-written fixture; it caught 1 of 5
  cases. Worth remembering.)

### Lesson: look-ahead sports need capture and posting to move together

`capture_opening_signals` and `_new_signals` both keyed on `game_date = today`.
Four sports write picks with a FUTURE `game_date`, and the correct behaviour
splits on **whether the pick is already locked**:

- **NFL — post immediately.** `nfl_opener_spread` locks T-7..T-2 and
  `nfl_wind_totals` prices Thursday for Sunday; both are INSERT-ONCE, so the
  pick is the bet of record the moment it lands. Waiting for game day would post
  the opener *after* the soft book corrects — i.e. after its only edge is gone.
  Both windows read `config.NFL_LOCK_AHEAD_DAYS` (7, matching the opener's own
  `LEAD_HI_DAYS`); capture reaching forward while the poster did not would just
  lock rows that sit unposted until kickoff.
- **UFC / GOLF / NCAAF — post on game day.** These delete-and-rescore every pass
  until game morning, so they genuinely are not locked yet. Session 126's rule
  ("no signal shows unless it's locked") points the other way for them.

The UFC `:early` shadow key is guarded on **sport**, not date alone — keyed on
date it would have swallowed every NFL look-ahead pick into a measurement row
that never displays.

### The channel is not the only place a signal can be lost

Also confirmed on 2026-08-29: a `KeyError` from ONE model
(`ncaaf_spread_premium`, registered in `config.MODELS` but absent from
`FEATURE_MAP`) propagated out of `run_scorer` and killed game-level scoring for
**every sport, all day** — zero game-level picks for MLB, WNBA, NHL, UFC and
NCAAF, while the only visible symptom was an empty NCAAF board. Fixed in #261
(per-model try/except that still re-raises a summary after committing survivors)
plus a derived test asserting every `config.MODELS` entry has a `FEATURE_MAP`
entry. When a sport looks quiet, check `pipeline_runs.failed_steps` before
looking at thresholds:

```sql
SELECT started_at, steps_failed, failed_steps, ok
FROM pipeline_runs ORDER BY started_at DESC LIMIT 10;
```

### Lesson: a per-game notify is O(games), and a one-game slate hides it

The NCAAF live loop announced from inside `write_picks`, which runs once per
game. Both notifiers scope their query to the slate DATE, so the first call
already covers the whole board and every later one runs the same query to find
nothing. `write_picks` also opened its own DB connection per call, and
`data.db.get_connection()` does not pool.

That is invisible on the one-game Tuesday it was built on. **Peak concurrency
on 2026-09-05 is 60 simultaneous NCAAF games** — at a 10s cadence that was up
to ~100 fresh TCP+TLS+auth handshakes to the session pooler every tick, ~10 a
second sustained for hours. The failure mode there is not latency, it is pool
exhaustion.

Now: `main()` owns ONE connection for the pass, `write_picks` RETURNS the
slate date when a game is worth announcing, and `notify_live()` is called once
after the loop. Three connections a tick instead of a hundred, flat in slate
size. Each game still commits its own transaction, so a failed write is rolled
back and the rest of the board still prices.

`models/live_scorer.py` (MLB) already did it this way — the NCAAF loop was the
outlier. When adding a sport's live loop, copy that shape.

### Live MLB is one model now, and the loop runs at 5s (2026-08-29)

Two changes that only make sense together.

**Selectivity.** Swept every settled live BET at real DK prices, flat $100:

| model | at 0.65/0.10 | verdict |
|---|---|---|
| `mlb_live_total_runs` | 41 bets 24-17, **+8.2%** | LIVE, re-cut to **0.68 / 0.14** = 17 bets 12-5 **+27.9%** |
| `mlb_live_win_prob` | 15 bets 6-9, **-34.1%** | **PAUSED** |
| `mlb_live_runline` | 14 bets 5-9, **-39.9%** | **PAUSED** |

Totals is the only live model whose ROI RISES with both prob and edge, and the
0.68/0.14 cell has all eight neighbours positive — a plateau, not a peak. The
two binary models are negative at EVERY cut and get WORSE as the probability
floor rises (win_prob at 0.65/0.15 is -78.9% on 8 bets): avg model probability
0.73-0.76 against a 36-40% realised win rate. That is overconfidence, not a
threshold problem, and it is what their 5.3%/5.9% holdout CalErr was already
warning about. 17 bets is thin and in-sample — re-sweep at ~50.

A paused live model still SCORES, written as NONE (`classify_live_signal`), so
the forward record accrues for the unpause decision. The usual "no NONE rows in
live" rule is about a live game writing hundreds of dead rows a day; a paused
model's would-be BETs are 1-2.

**Cadence: 15s poll / 60s fetch → 5s / 5s.** Both bounds tracked it
(`LIVE_ODDS_MAX_AGE_SEC` 120→30, `LIVE_STATE_MAX_AGE_SEC` 300→60,
`LIVE_DAILY_CREDIT_CAP` 10k→50k). Two second-order costs had to be paid first,
and neither is optional at 5s:

- **Pre-game features are cached per game** (`_pregame_features`). They cannot
  change during a game — every input is as-of first pitch, and `_get_dk_odds`
  excludes in-play by construction — so rebuilding them was ~10 queries per
  game per pass for a constant row.
- **A lane is rewritten only when the PROPOSITION changed** (`_lane_signature`:
  side, signal, line, price — deliberately not model_probability, which drifts
  every pitch while the bet on offer is unchanged). Delete-and-replace at 5s
  would have been ~52k `picks` rows an hour and twice that in `picks_log`,
  almost all identical. The write is now proportional to line movement rather
  than to poll frequency, which is what a faster loop was for.

On the NCAAF side the state poll went 10s → 5s, which is what actually makes
its odds knob 5s: the fetch runs inside the state loop, so the pass is the hard
bound. That roughly doubles the CFBD live-window bill to ~35k calls/month —
past the $5 / 30k tier. The account is on the **$10 / 75k** tier (confirmed
2026-08-29), so it fits; going below 5s would not.

### Lesson: a trigger set is only as good as the events it does not miss

The MLB in-play line refreshed ONLY when an `inning_change` or `score_change`
trigger fired — `consume_triggers_once` returned immediately when no trigger
was pending. But a live total moves on **every baserunner**, not only on runs
and half-innings, so the trigger set was a strict subset of the events that
move the line.

Measured on 2026-08-29: DraftKings in-play snapshots landed on average every
**269 seconds**, with gaps up to **1,020s** — against a `LIVE_ODDS_MAX_AGE_SEC`
of 300, so the staleness bound was looser than the feed's own refresh and could
never bite. The loop was routinely allowed to price a multi-minute-old total.

The published number was NOT wrong — CWS@MIN Over 9.5 at −124 was DraftKings'
real price at 18:29:36 — it was **stale**: by 18:35 DK was on 10.5, and the 9.5
rung had become an alternate at −140s. "The line is fake" and "the line is six
minutes old" look identical to a user opening the app.

Three changes, and they only work together:
- a **floor fetch** (every `LIVE_FG_DEBOUNCE_SEC` while any game is live, not
  only on a trigger), gated on a game actually being live;
- `LIVE_ODDS_MAX_AGE_SEC` 300 → 120, so a stale line is DECLINED rather than
  bet — meaningless without the floor, which is what makes 120s achievable;
- `LIVE_DAILY_CREDIT_CAP` 1000 → 10000, because 1000 was sized for
  trigger-only fetching and a 60s floor is ~1,800 credits on a 10-hour slate:
  the old cap would have bound by mid-afternoon and silently stopped the
  refresh, which is the exact failure the floor exists to prevent.

Live Discord posts now carry a timestamp (`posted 2:30:05 PM ET` — labelled
`priced` until 2026-08-30, when pre-game posts gained the same stamp and the two
were unified on the app's word; same column, same instant, `picks.created_at`).
An in-play number is only the number it was when we wrote it down, and a post
that reads as "available now" sends someone to a book that has already moved.

**When a live line looks wrong, check its AGE before its VALUE.** The odds
table stores one row per book per snapshot, so several different totals at the
same second are seven books, not a corrupted feed — that misreading cost a
detour here.

### The book's publish clock is the only freshness that matters (2026-08-29)

A live pick read Over 46.5 while DraftKings was on 51. The pipeline was not
slow — it was **1.3 seconds end to end**:

```
23:58:16.31  DK snapshot read      46.5  -120
23:58:16.95  pick written
23:58:17.60  posted to Discord
23:59:06     DK re-hangs           51.5
23:59:51     DK re-hangs           54.5
```

The number was correct when posted and wrong 49 seconds later, because
DraftKings had **held 46.5 unchanged for 4m35s of running clock** and then
re-hung it eight points away. A book that stops moving a live number has taken
the market down; the last price it published is not a price you can take.

**Every freshness guard we had measured OUR latency, and our latency was never
the problem.** At a 5s cadence a fetch-age bound is always ~0 and can only fire
when the loop itself dies. The field that distinguishes "confirming 46.5 every
twenty seconds" from "froze at 46.5 four minutes ago" is the book's own
`last_update`, free in the payload we already pay for — and the NCAAF feed
**discarded it**, even though `nfl/live_model`, the package it was ported from,
reads it and refuses to price without it (`MAX_QUOTE_AGE_SEC = 90`).

Now: `parse_event_odds` carries `ts` **per market** (DK suspends the total and
the moneyline independently), `serve.market_is_takeable` declines past
`LIVE_QUOTE_MAX_AGE_SEC`, and the price log stamps `snapshot_at` with the book's
publish time rather than ours — a log on our clock shows a frozen price
refreshing every five seconds, which is the same illusion, written down.

**A bound tighter than the feed it guards is an outage, not a guard.** MLB
already stored the feed's `last_update` as `snapshot_at`, so its check was
always a publish-age check — and it was then tightened to 30s on the reasoning
that the bound should track the *fetch* cadence. Measured over 1,687 in-play
publishes, the value advances every **47s median, 106s p90**. A 30s bound sat
below that and declined roughly 60% of the time. 90s across all sports accepts
the rhythm and rejects a freeze.

**CORRECTION, same night: that 47s is THE AGGREGATOR'S CACHE, not DraftKings
republishing.** Every event in a bulk response carries the SAME `last_update`,
and ~7 consecutive 5s polls receive the identical payload. `last_update` is The
Odds API's own snapshot stamp for the response, not a per-market publish time
from the book. Do not read it as "the book moved."

### The feed has a ~45s floor, and it cannot be bought past (2026-08-29)

Three things were measured in one night, in this order, and each killed a
cheaper explanation:

1. **Not us.** Discord stamps every message with a snowflake encoding its own
   receive time. The Florida State post reached Discord **0.03s** after the loop
   started the notify; across ten live posts, Railway→Discord was 0.03–0.26s.
   The full path from reading the odds snapshot to Discord holding the message
   was **1.33 seconds**.
2. **Not the endpoint.** `scripts/live_feed_probe.py` read the same live games
   from the bulk and per-event endpoints at the same instant: **36/36 paired
   observations returned an identical `last_update`, line and price**, and both
   flipped to the new snapshot at the same moment. The per-event endpoint costs
   1 credit per event per market and buys **nothing**. Do not re-test this.
3. **It is a cache.** 136 distinct snapshots over 2.5 hours, ~7 of our fetches
   served per snapshot, median refresh **46s** (NCAAF looked closer to 64s).

So every live price we publish can be up to ~45s behind the book's own app, and
polling faster cannot change that — 5s polling buys catching a new snapshot
within 5s of it appearing, against a 46s floor.

**What is still unmeasured:** whether the aggregator is ALSO behind DraftKings
on top of the cache granularity. A 45s-old-but-accurate snapshot and a snapshot
that is itself a minute stale look identical from our side. Answering it needs a
second independent read of DK's line — see `docs/live_odds_freshness.md`.

**DraftKings direct needs BOTH a browser fingerprint and a residential
address — either alone gets 403.** `scripts/dk_direct_probe.py` across the full
matrix (2026-08-30):

| | plain requests | `--impersonate chrome124` |
|---|---|---|
| datacenter (Railway) | 403 | **403** |
| residential (laptop) | 403 | **200, 96KB** |

The first column looked like the datacenter-IP block that took out ufcstats,
stats.nba.com and site.api.espn.com, and the residential 403 looked like proof
it was not an IP block at all. Both readings were too strong: that pair only
shows a residential address is not SUFFICIENT. The fourth cell shows it is
NECESSARY. **So DK-direct is not shippable from the worker at any request
shape** — the legitimate route is the one `nba_api` already uses, a scheduled
job on a residential machine (`docs/sports/wnba.md`).

Meanwhile the SAME first-candidate URL opened in Chrome returns the full payload
**including live in-play markets on started games**. So the endpoint is alive,
the URL shape is right, and what is matched is the REQUEST — TLS/JA3 and HTTP/2,
not the UA string (round 1 already sent Chrome's UA and still 403'd).
`--impersonate` (curl_cffi) tests exactly that, at mike's direction 2026-08-30.

**Two things the real payload settles before anyone writes a parser:** it has
**no `last_update` — no timestamp of any kind**, so DK-direct buys a fresher
line but no publish clock (freshness could only be inferred from when *we* see a
change); and `displayOdds.american` is Unicode (`\u2212131`), so parse
`decimal`. A `subscriptionPartials` block hints at a websocket push channel,
unexplored. Full findings + the ToS boundary: `docs/live_odds_freshness.md`.



Two things this does not fix, both recorded rather than assumed:
- **Volatility is not staleness.** Measured on the same slate, NCAAF live totals
  drifted 2-8 points within ten minutes of a pick; MLB drifted 0-2 runs. Live
  picks lock at first signal and are never re-priced, so a posted NCAAF number
  can be several points off within minutes even when it was current when posted.
- Whether the 4m35s freeze was a halftime suspension is **inferred, not
  measured** — we had no `last_update` to look at. The guard is also the
  instrument: once it is running, a declined market is evidence.

### "Paper trading" is banned from user-facing copy (2026-08-29)

The daily recap posted a "Paper trading" footer under real settled numbers. The
phrase came from `CLAUDE.md` §2, which was written when it was true and never
revisited; every downstream surface inherited it. §2 now states the platform is
live and that the go-live gate is **per model**. Removed from the Discord recap
footer, the email footer, the dashboard, and the Track Record / Settings /
Explainer / Opening Comparison screens. Still correct — and deliberately kept —
where it describes a NEW model that must be paper-traded first
(`scripts/ncaaf_margin_eval.py`, `docs/ncaaf_search_findings.md`,
`nfl/live_model/`).
