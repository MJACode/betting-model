# Odds sources: what exists, what it costs, and what it actually adds

*Researched and measured 2026-09-08, at mike's question: "what other odds
sources are there? how are these better/different than the odds api we already
have."*

**The short answer is uncomfortable: the most valuable unused odds source is the
one we already buy and already store.** Details in §1. Everything else is graded
against that.

---

## 1. The finding: we already have ladders, and nothing reads them

`docs/prop_market_research.md` established that a ladder of strikes is an implied
distribution, and that it fixes the biggest data loss in the prop programme --
63,676 propositions discarded because a sharp and a soft book hang different
lines. Kalshi was the answer to that, for free.

**The Odds API serves the same thing, on every book, and we are already paying
for it and storing it.**

| what | value |
|---|---|
| `PROP_ALT_MARKETS['NFL']` | **11 alternate markets**, requested by the live pull since 2026-09-05 |
| rows already in `player_prop_odds` | **1,480,000+** across **14 books** |
| markets that read them | **none** -- `nfl_prop_market.SHARP_MARKETS` lists only standard keys |
| history | **none** -- the pull has them, the BACKFILL does not (`want = list(markets or PROP_MARKETS_NFL)`) |

Ladder depth on one event, measured:

| market | betonlineag | rebet | draftkings | fanduel | williamhill_us |
|---|---|---|---|---|---|
| `player_reception_yds_alternate` | **88** | 88 | 29 | 17 | -- |
| `player_rush_yds_alternate` | **48** | 48 | 20 | 15 | -- |
| `player_pass_yds_alternate` | **34** | 34 | 27 | -- | 16 |
| `player_receptions_alternate` | 11 | -- | 12 | 12 | -- |

**betonlineag -- one of our two sharp de-vig references -- posts an 88-rung
ladder**, against Kalshi's median of 9. And the alternates cover
`player_receptions`, `player_pass_attempts` and `player_pass_completions`, none
of which Kalshi runs at all and which are ~40% of our soft board.

### The cost, measured on a live event

| pull | credits | outcomes |
|---|---|---|
| 4 standard markets | 8 | 611 |
| **4 alternate markets** | **8** | **2,493** |
| both | 16 | 3,104 |

**Same credit cost, four times the data.** Balance at the time of writing:
**3,566,250 credits**. Adding alternates to the whole NFL board is ~128 credits a
pull, ~21.5k a week -- 0.6% of the balance.

### Why this beats the Kalshi route on three counts

1. **It covers the markets Kalshi does not** -- receptions, attempts,
   completions.
2. **It gives a ladder for the SOFT side too**, not just the reference. Kalshi
   can only ever tell us what fair value is; a DraftKings ladder tells us what
   we can actually bet at every rung.
3. **No new integration** -- the rows are already in the table.

Kalshi remains genuinely complementary and is not superseded: it is *independent
price formation* (an exchange, not a book copying a book), it has no vig to
remove, and it cannot limit a winning account. But it is no longer the only way
to get a distribution.

### The two gaps to close

- **`nfl_prop_market` must read the alternates.** Today `SHARP_MARKETS` is
  standard-only, so 1.48M rows sit unused.
- **The backfill must request them.** Without history there is nothing to grade
  a ladder-based construction on, which is the same "record it now or lose it"
  problem the Kalshi recorder was built for -- except here the API sells the
  history and we have the credits.

---

## 2. Every provider, priced

| provider | price | books | props | what it uniquely adds |
|---|---|---|---|---|
| **The Odds API** *(ours)* | $25+/mo, credit-based | 60 on NFL h2h | yes, **+ alternates** | already integrated; historical endpoint at 10x credits |
| **Kalshi** | **free** | n/a (exchange) | yes, ladders | no vig, no limiting, independent price formation |
| **SportsGameOdds** | $99-149 Rookie, $299-499 Pro | 85+ incl Pinnacle, Betfair Exchange | all tiers | **Circa -- Pro tier only** |
| **SportsData.io** | contact | incl Circa | yes | Circa; enterprise support |
| **OddsJam** | $499-5,000+, sales-gated | 100+ | not specified | breadth |
| **Unabated** | $3,000+/mo | major US/intl | yes | WebSocket streaming, no rate limits |
| **OpticOdds** | $5,000+/mo **per sport** | 200+ | yes | sub-800ms, 200+ operators |
| **Polymarket** | free | n/a (exchange) | limited | crypto/on-chain; out of scope for a US consumer app |

### What a new provider would actually buy us

- **Circa** -- the one book external consensus names sharpest for props, and the
  only genuine coverage gap. Cheapest confirmed route is **SportsGameOdds Pro,
  $299/mo annual**. But their own page says Circa coverage is "deepest on sides,
  totals and moneylines" and **does not confirm player props**, which were the
  entire reason to want it. Trial before spending.
- **Latency** (OpticOdds, Unabated) -- irrelevant here. Our measured edge sits
  ~7h before kickoff (`docs/nfl_prop_offset_evidence.md`); sub-second delivery
  buys nothing at that horizon.
- **More books** -- marginal. `scripts/nfl_prop_book_sweep` already rejects the
  books we have on volume and coverage grounds; adding twenty more thin ones
  adds rejections, not edge.
- **Betfair Exchange** (SGO) -- interesting in principle as a second vig-free
  reference, but measured 2026-09-08 against our own feed: **no exchange posts
  NFL player props at all.**

---

## 3. Recommendation

**Spend nothing yet.** In order:

1. **Read the alternates we already store** -- 1.48M rows, zero new cost, and it
   supersedes most of what a new provider would sell us.
2. **Backfill alternates** so a ladder construction can be graded. The historical
   endpoint costs 10x, and the balance is 3.57M credits.
3. **Keep recording Kalshi** (shipped) -- independent, free, and the only
   limit-proof venue.
4. **Trial SportsGameOdds Pro** only if Circa player props are confirmed to
   exist. $299/mo is cheap; buying a Circa feed that turns out to be sides and
   totals is not.
5. **Ignore** OpticOdds and Unabated at $3-5k/mo. They sell latency and breadth,
   and neither is our binding constraint. Our constraint is that the eleven
   distributional models measure -1.90% and the one working rule had never been
   run in the regime it was measured in.

---

## 4. GRADED, AND IT DOES NOT WORK (2026-09-08)

The alternates were backfilled across three seasons and the anchored-ladder
construction was graded against them. **It fails the bar on every clause.**

`scripts/nfl_prop_ladder_grade`, reference betonlineag, one bet per proposition:

| cut | bets | win% | units | ROI | 90% CI | by season |
|---|---|---|---|---|---|---|
| 3% | 849 | 48.6% | -7.05 | -0.83% | (-7.0, +5.4) | 2024 -2.2%, 2025 +0.5% |
| 4% | 545 | 49.5% | -9.51 | -1.74% | (-9.2, +6.0) | 2024 -2.1%, 2025 -1.3% |
| 5% | 365 | 50.4% | -0.68 | -0.19% | (-9.6, +9.2) | 2024 +3.2%, 2025 -3.5% |
| **6%** | 237 | 45.1% | **-36.72** | **-15.49%** | **(-26.1, -4.8)** | 2024 -22.2%, 2025 -9.3% |

- **No plateau.** The shipped rule rises monotonically with the cut
  (2.46 -> 4.31 -> 9.83 -> 12.15%). This does the opposite.
- **Every usable interval spans zero.**
- **The placebo fails outright.** Standing a retail book in as the ladder
  reference: fanduel **+5.00%** (311 bets), espnbet +0.38%, hardrockbet -1.80%,
  draftkings -12.98%. A retail book beats the sharp reference, which is the
  same failure that killed the NCAAF attempt.

### The informative part: the biggest edges are the worst bets

The 6pp cell is not merely negative, it is SIGNIFICANTLY negative -- the only
interval in the table excluding zero, and on the wrong side. A fair value that
is right on average but wrong where it deviates most is the signature of a
miscalibrated tail, and that points straight at this module's one stated
assumption: `Ladder.anchored` shifts by a CONSTANT in logit space, i.e. it
assumes the book's margin is uniform across its own ladder. It is not. Books
charge far more at the extremes, so the correction under-removes vig exactly
where the large apparent edges live, and the rule then bets hardest on its own
worst estimates.

That is worth knowing beyond this construction: any future use of a one-sided
ladder needs a margin model that varies with the strike, not a single shift.

### And the history is shallower than the spend assumed

**Alternate coverage effectively begins in 2024.** For 2023 only draftkings
(5,308 rows), fanduel (26,469) and hardrockbet (2,710) carry any at all, and
**betonlineag carries none** -- so 2023 contributed no bets to the sweep and the
72,094 credits spent on it bought nothing usable for this. Total backfill spend
was ~514k credits against a ~291k estimate; the per-event cost was 583, not the
341 measured from a single cheap event.

**Verdict: do not wire the anchored ladder into scoring.** The 19.3% coverage
gain is real and the bets it unlocks are not profitable. What survives is the
machinery (`models/prop_ladder`), the Kalshi recorder, and a now-graded reason
not to spend more on this idea.
