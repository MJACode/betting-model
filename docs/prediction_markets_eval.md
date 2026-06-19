# Prediction markets (Kalshi / Polymarket) — evaluation memo

Roadmap item P3 from the competitor-analysis strategy. This is a **decision memo
+ spike plan**, not a build. Goal: decide whether Signalbase should treat
CFTC-regulated prediction markets as (a) an alternative odds/edge source, (b) a
place we route users to bet without getting limited, or (c) a competitive threat
to monitor.

## Why it's on the radar (2025-26)

- Kalshi went ~600k → 5.1M MAU in 2025; ~$23.8B notional (+~1,100% YoY); >$1B/day
  at the Super Bowl; Robinhood integration; ~$1.3B annualized sports revenue.
- They're **CFTC-regulated event contracts**, not sportsbooks — which is exactly
  why the #1 existential pain in our research (sportsbooks limiting/banning
  winners) **may not apply**. A consistent winner can't be "limited" on an
  exchange the way DraftKings limits sharp accounts.
- Pricing is a live, two-sided order book — often close to fair, sometimes
  laggy/inefficient on less-liquid markets. That's a potential edge surface.

## The three angles

1. **Alternative odds source.** Pull Kalshi market prices for games we already
   model (MLB ML/totals, etc.) and compute edge vs our calibrated probability —
   same math as DK, different venue. If their book is less efficient on certain
   markets, the edge is larger. Adds a non-correlated line to "line shopping."
2. **Limit-resistant routing.** For users who win and get limited at DK/FD, a
   "also available on Kalshi" hand-off keeps them able to act on our picks. Fits
   the disruptor/discipline brand (help users actually keep winning).
3. **Threat to monitor.** If prediction markets keep eating sportsbook share,
   our DK-centric scoring + betslip hand-off may need to follow the volume.

## Open questions to resolve before any build

- **API access & terms.** Does Kalshi's API allow read-only market-data pulls
  for our use? Rate limits? Cost? (Polymarket is crypto/on-chain and likely out
  of scope for a US consumer app.)
- **Market coverage & mapping.** Do their sports contracts map cleanly to our
  `games`/markets (team naming, totals lines, settlement rules)? Settlement and
  contract structure differ from −110 straight bets.
- **Pricing semantics.** Contract price (¢, 0–100) ≈ implied probability. Convert
  to an edge vs our model prob; account for the exchange's fee structure (it's
  not vig, it's a trading fee) when computing true EV.
- **Legal/RG posture.** Routing users to an exchange has its own compliance
  surface; confirm it's defensible state-by-state.

## Recommended spike (small, read-only, no commitment)

Run `python -m scripts.verify_kalshi` (committed). It's read-only and needs no
key for public market-data browsing — it prints the `/events` and `/markets`
shapes, flags any sports-looking contracts, and shows the cents→implied-prob
conversion. Then:

1. From its output, confirm Kalshi exposes game-level sports contracts that map
   to games we model, and that the API terms allow read-only market-data pulls.
2. Join those prices to our `picks` for the same games; compute edge vs our model
   prob (`edge = model_prob − price/100`) and compare to the DK edge we already
   store. Look for: (a) systematic price gaps, (b) markets where their price lags
   the close.
3. Write up: is there a real, recurring edge vs Kalshi, and is the API/terms
   workable? If yes → scope an ingestor (`kalshi_odds_ingestor.py`) mirroring
   `odds_ingestor.py` and a "also on Kalshi" hand-off. If no → keep monitoring.

## Status

Deferred. No code. Revisit after the track-record / line-shopping work proves
out on paper and there's appetite for a non-DK venue.
