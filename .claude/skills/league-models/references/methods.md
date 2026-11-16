# Methods: what has been tried, and why it worked or did not

Step 5 of `SKILL.md`. Organised by **mechanism** — the reason a book's price
could be wrong — because a new league is searched by asking which mechanisms
could apply to it, not by asking what another sport did. Each entry names the
markets it worked on, where it failed and why, and the doc that holds the
evidence. Numbers are as the docs state them, in units or return at real
prices.

**The most reusable finding in this repo.** In every league searched, models
that predict the game from team or player statistics and compare the result
with the line — classifiers, stat projections, feature-rich trees — mostly
added nothing over the closing line. A model that loses to the market's own
open on log loss has "edges" that are its own error. The edges that held came
from **market structure**: other books' prices, a stale or first-posted
number, a line re-hung mechanically, a regressing quantity priced as
persistent, an input the market under-weights at the moment of decision, the
side the margin sits on, or a stat the book settles differently. Re-mining
features on the same data rarely helps; **a new edge needs new information or
a new mechanism** (`docs/sports/ncaaf.md`, "The model search is CLOSED";
`docs/nfl_prop_method_search.md` §5d; `docs/nhl_market_lab.md`, "Read").

Start every market with the mechanisms below. Use a stat model as an input to
one of them (an anchored adjustment, a gate), and test it with the information
test before trusting it.

---

## 1. Anchor on the market, let the model only move it

The market's no-vig number is the starting point and the model's inputs can
only move it. This keeps a weak model from inventing edges out of its own
error.

- **Market-anchored logit.** The book's no-vig log-odds enters as an
  unpenalised offset; inputs are penalised, the penalty chosen on training
  seasons. *Worked*: the hockey moneyline, +6.28% on 1,326 bets with a -200
  floor, a plateau from EV 0.00 to 0.10, both halves positive, the production
  module reproducing the research grade game by game. An input useless in a
  tree model (rest) helped here: the model design decides whether an input can
  be used. (`docs/nhl_moneyline_rebuild.md`)
- **Ratings blend at the book's first posted total.** Team offence, defence and
  pace refit as of the quote, a fixed luck and style correction, then
  `mean = line + c + β(model − line)`, priced at that book's own two prices,
  decided once at the first post and only while that number still stands.
  *Worked*: men's college totals, 1,432 bets +8.68% [3.51, 13.55], every season
  positive; the same settings, unchanged, are live on the women's game (402
  bets +6.77% [-2.2, +15.1] on its one walk-forward season). The edge is larger at the first post (9.4% of games
  clear against 3.2% later). (`docs/sports/ncaab.md`, `docs/sports/ncaabw.md`)
  *Failed*: the same model at another book's first total, on the games the
  anchor book never prices (women's college, 2026-11-16): 140 bets +5.97%
  [-6.7, +18.4] walk-forward, falling to -4.92% above 0.08, the opposite of
  the anchor-book games (`scripts/ncaabw_research/totals_other_books.py`).
- **Fundamentals regression behind a wide gate.** The market number is not a
  feature; the probability comes from an out-of-sample residual distribution;
  bet only when the model is 8+ points from the line; average the fit over
  seeds. *Live*: college football totals, 346 bets +9.35% (interval -2.2 to
  +21.0) in the live shape, positive under all 11 seeds, and 94 real 2026 bets
  +9.76 units. (`docs/ncaaf_market_audit.md` §2, §4)
- *Failed*: the anchored recipe on pro basketball found nothing; the women's
  college sides off the ratings had β near zero ("the line already holds it").
  UFC props at five US books, 2021-2026: nothing on KO/TKO, submission,
  inside the distance, round betting, fight ends in round N or round totals.
  On a market with many outcomes give the anchor a free slope on the
  market's own logit and one intercept per outcome type, and fit a two-way
  market once per pair, on one side: fitted on both sides, the inputs cancel
  (`docs/ufc_market_audit.md` §5f).
  Horse racing, Hong Kong win pools 1997–2005 (2026-11-15): Benter's blend
  (`softmax(b · log p_model + c · log p_pool)`) on a 25-fact Bolton–Chapman
  conditional logit, walk-forward, 4,581 graded races: `b` between −0.11 and
  +0.04 in every season, and the blend scored worse out of sample than the
  pool calibrated alone. Against a FINAL pool, which already holds the late
  money, this is the harder test; the published Hong Kong successes blended
  against the pool minutes before the off. A leak check (the race's own speed
  figure) lit the same harness up (`b` +2.9 to +9.1), so the null is real
  (`docs/horse_racing_market_audit.md` §3b). Against the pool 5 to 12
  minutes BEFORE the off (2016–2018, the free GitHub snapshots), with stage
  1 fit on ten earlier seasons: `b` +0.14 to +0.21 (1.8 to 2.7 SE), so the
  form model does hold a little the pre-race pool lacks; out of sample
  +0.001 to +0.003 nats a race (within one SE), against the final pool `b`
  ≤ 0, and the bets (longshots) lose. The late money absorbs what the model
  knows, after the last snapshot a bettor can use (§7b).
  UK and Ireland at starting price, 1995–2026 (2026-11-16): the same two
  stages, walk-forward by year, Flat and jumps fitted apart, on form,
  earlier-run figures, official ratings, weight, age, draw, layoff and
  jockey and trainer records. Stage 1 alone is far weaker than SP
  (pseudo-R² 0.127 against 0.177 in Britain). Blended with SP it gains
  +3.60 [+3.25, +3.95] ×1000 log-likelihood a race in Britain, but that
  gain fell from about +8 to +13 a year in 1996–2003 to within ±0.7 every
  year from 2022, and most of it (59% to 94%) is the earlier-run figures.
  SP is the close, so the blend is an information test only. The decidable
  bet (stage 1's top-rated runner at SP) loses in Britain 2011–2026: −4.28%
  on units with no cut (flat −4.73%), −0.92% [−2.21, +0.36] on units in the
  strictest cell (flat −0.11%). Its 1995–2010
  profit is not taken: whether the stored figures are as published on the
  day is unknown, and only one of four model-free figure picks was positive
  then (`docs/horse_racing_market_audit.md` §8b). One subgroup, Irish chases
  where the model gives its top horse over a 50% chance, is positive in
  2011–2026 but was found after looking, among 96 late cells, and is a peak
  whose neighbours and halves span zero (§8b).

## 2. The books disagree — with each other, with themselves, with a sharp book

- **Same line, better price, against a sharp reference.** De-vig the sharp
  book (Pinnacle, or the nearest), bet a soft book quoting the same line at a
  better price. **The two quotes must come from the same snapshot.** *Worked*:
  pro football props, 1,990 bets +7.84% (90% CI +4.3, +11.4), three seasons
  positive, retail placebo negative, then per-side cuts from a measured over
  lean (`docs/nfl_prop_over_lean.md`); pro basketball same-line prop unders,
  25,204 bets +2.85%. *Shipped on mike's call without clearing*: hockey
  full-game totals, 1,276 bets +4.72%, interval -0.6 to +10.1, CLV +1.32%,
  found by the market-structure round after fitted models failed four times.
  *Failed*: college football props (a retail placebo beat the sharp
  reference); baseball props, -4.01% on 6,931 ("the edge is specific to a
  market"); baseball totals once quotes had to be within 300 seconds (no bets
  left).
  *Shipped, missed the stricter bar*: tennis match winner (2026-11-14), the
  best of seven US books against Pinnacle's POWER-de-vigged pair about 30
  minutes before the listed start, EV 0.02 to 0.05 with each book's
  retirement rule, 355 bets +11.0% (+2.5, +19.5); walk-forward cut +1.2%,
  Bovada placebo +5.2% (`docs/sports/tennis.md`, "Research, round 1"). Same
  method, same line, on tennis total games and games spreads: null (the
  three books a median 7% below Pinnacle's fair price).
- **Line shopping against the books' own median**, priced through an
  empirical final-margin table. "The edge is the off-market number, not a read
  on the game." *Worked*: men's college spreads, 409 bets +9.97% [0.8, 18.4]
  (the doc's own estimate of the true edge: about +2% a bet). *Failed*: college
  football (337 of 338 bets were road teams: a tilt in the fitted table); the
  women's college game (the book standing apart was more often right);
  EuroLeague spreads (99.6% of 538 bets were home teams, closing value
  negative: a home lean, not shopping; `docs/euroleague_market_audit.md`).
- **A book's moneyline against the same book's spread.** De-vig the spread,
  invert the margin table, take the win probability. *Shipped without
  clearing*: men's college, 838 bets +4.22% [-1.2, 9.3], chosen from 162
  versions after the fact. *Failed*: college football, women's college, pro
  basketball (-25.0% in 2025-26), EuroLeague (-11.00% on 86).
- **The first post.** Decide at the moment a book first posts, with enough
  other books up to form a reference. *Worked*: men's college opening
  moneyline, 297 bets +15.15% [7.34, 23.37]. *Could not run*: EuroLeague,
  where the sharp book was up at only 103 of DraftKings' first posts in three
  seasons; check that the reference is up at the soft book's first post
  before planning this rule.
- **A rating model anchored on the first posted price.** The open is one
  book's first guess; ratings built before the fight say which way it will
  be corrected. *Worked*: UFC fight winner, anchored on Pinnacle's no-vig
  price at least a week out and bet at the best deciding book, on the
  bought 2020-2026 history: 846 bets +12.85% [+8.0, +17.5], every year
  positive, +2.2% against Pinnacle's close, placebo -1.9%; live as
  `ufc_open_moneyline`. The edge grows with the lead and is negative inside
  a week. On an archive's open (whichever book posted first) it read +7.8%
  on 1,531; on our 2026 store's 104 DraftKings openers it looked dead, which
  the purchase overturned. At the close it finds nothing. *Failed* in the
  same sport: betting the side the line moved toward, at the worst close,
  lost in every band of move size (`docs/ufc_market_audit.md` §3, §8).
  *Failed* on UFC round totals: fighter and bout inputs on top of
  Pinnacle's total made the price worse at 1.5 and 2.5, and their bets
  matched a donor-input placebo (-5.34% against -5.30%). A per-line
  intercept alone corrected the price a little and still lost to
  DraftKings' 6.2% margin as the cut rose (`docs/ufc_market_audit.md` §4d).
  **Give an anchored model a free intercept per line**: without one it
  cannot correct a bias in the anchor, and the UFC version bet the side
  carrying the margin.
- **A stale opener.** Bet the side the sharp book favours at a soft book's
  stale opening number. *Passed the placebos* (reversed books null, other
  opens null, CLV 0.694, every season positive) and *failed executability*:
  both openers are rarely captured at the same moment on the live feed.
  (`docs/ncaaf_search_findings.md` §11)
- *Failed*: steam lag (about a third of a point of CLV, does not pay at -110);
  predicting the book's next move (correlation +0.66, but the move is smaller
  than the vig).
- **A market against its own derivative: the place pool against the win
  pool** (Hausch, Ziemba and Rubinstein's "Dr Z" system, 1981). Harville's
  place chance from the win prices, calibrated, against the place price.
  *Failed* in horse racing (2026-11-15): Hong Kong's final pools, calibrated
  on 1997–2000 and graded on 2001–2004, negative at every EV cut (best
  −7.2% [−18.0, +3.5], 2,590 bets) even though the rule read both final
  pools; the Betfair exchange (Australia and New Zealand), calibrated on
  2020–2022 with a place BSP predicted from the scheduled-start prices,
  negative net of commission in every graded year 2023–2026 (best −1.78%
  [−2.33, −1.24]). **Harville over-rates short horses for a place (said 0.84,
  placed 0.75) in both markets, and both place markets already price that**:
  calibrate the place model before any ROI test, or the "edge" is Harville's
  bias (`docs/horse_racing_market_audit.md` §3a, §4a). On Hong Kong's live
  pools before the off (2016–2018), calibrated on 2016/17 and graded on
  2017/18 at the final place dividend: −7.6% to −36.9% at every lead from
  33 to 5.6 minutes and every EV cut (§7a).
- **Untested in racing, and the shape that has worked elsewhere**: the
  sharp exchange's price on a race against the pool a US outlet sells, both
  at a moment before the off. Needs a price path for both, which nothing
  free holds (`docs/sports/racing.md`, "What would have to change").

- **Late money in a pool, decided before the off.** Back (or fade) the
  runner whose pool share moved most between two snapshots, decided at the
  later one, paid at the final dividend. *Failed* in Hong Kong 2016–2018
  (six lead pairs from 30 to 5.6 minutes out; biggest steamer −12.9% to
  −19.3%, biggest drifter −7.4% to −20.5%, none positive in both seasons).
  The pool's last snapshot a bettor can use is 0.0634 nats a race short of
  the close, 84% of all it learns after 30 minutes out (§7a). A late-money
  rule has to act after the moves it reads, and in a pool the price paid
  includes the moves after it acts.

## 3. The book re-hangs a line mechanically

Derivative and in-play lines are often set from another number by a rule. The
edge is where the rule misses something the state shows.

- **A half priced from the full-game consensus**: a frozen `a + b × consensus`
  map plus a heavily shrunk team half-tendency, priced through a whole-point
  outcome table. *Worked*: men's college first-half total (1,887 bets +5.98%)
  and spread (845 bets +6.13%). *Failed*: hockey team, alternate and period
  totals ("the books price these markets off the main line, correctly"); college
  football first halves and team totals (every quote loses -3.7% to -6.6%);
  EuroLeague first halves and quarters, round 1 (the books set the half at
  50.05-50.29% of the full-game total and stray 0.23-0.55 points from it; the
  one positive version was a slope that held only in 2025-26:
  `docs/euroleague_market_audit.md`).
- **In-play game-state model.** Points still to come from the pre-game prior,
  the current margin, pace and late-game terms; the first fresh eligible quote
  decides. *Worked*: men's college in-play (three markets, the best 5 a night,
  2,533 bets +10.1% [+6.4, +13.8], placebo p95 -1.1%); pro basketball first-half
  in-play spread (1,348 bets +6.4%); baseball live total anchored on the
  pre-game line. *Failed*: college football in-play (-3.4% on fresh quotes:
  "the probabilities are honest; the prices are not beatable"), pro football
  halftime second-half lines, later-quarter basketball.
- **The halftime break as the decision point.** The state is fixed and "a
  bettor has minutes, not seconds". *Worked*: women's college halftime total,
  669 bets +11.84% [+5.1, +18.1], replayed on the loop's own code. In 2026-27
  the books hang halftime totals closer to it: it bets 25% of decided games
  against 60–64% in the stored seasons, under every fit, and this season's 36
  bets went 16-20 (`docs/sports/ncaabw.md`, 2026-11-16).
  *EuroLeague*: the total, ported unchanged, failed (574 bets -1.93%: it
  expected too many second-half points); the spread is a lead that misses the
  bar (364 bets +10.93% [+3.40, +18.48], placebo passed, the false-discovery
  correction failed), with a measured mechanism: the books carry 50% of the
  pre-game margin into the second half where the games carried 40%
  (`docs/euroleague_market_audit.md`, Halftime).
- **Live re-anchoring off the pre-game number and the clock.** The book's live
  prop line is re-hung from the opener and time elapsed; it under-adjusts for
  the game script. *Measured, in sample*: pro football rushing-attempt unders
  +11.2% over 874 bets, every season positive, every threshold positive
  (`docs/nfl_live_rush_attempts.md`); the in-play prop model it fed was retired
  and its record struck. Model it relative to the book's own number, never as
  a fresh projection.
- **Late-game leader moneyline.** One logistic regression per lead size,
  replayed with the state lagged behind the quote. Shipped on mike's call
  (167 bets +9.4%, both seasons in-sample); its first bet laid -980, which is
  why price floors are stated before shipping.

## 4. A regressing quantity priced as if it persists

- **Shooting luck.** Take opponents' three-point and free-throw luck out of the
  projection; bet when the gap is 3+. *Worked*: pro basketball full-game over
  (508 bets +10.1%), home team-total under (349 bets +16.6%), first-half over
  (595 bets +8.0%). Credible because the return rises with the gap, the
  mechanism is published, and every season is positive. *Failed*: the same
  rule on the away team total (so the home figure overstated); a football luck
  rule (-6.36%).
- Other candidates of the same shape to test in a new league: finishing rates,
  save percentage, close-game records, turnover luck.

## 5. An input the market under-weights at the moment of decision

- **Weather forecast.** Use the issued forecast (never the observed weather),
  with its measured forecast error, inside a fixed lead window. *Live*: pro
  football wind unders, validated at 57.09% under [52.4, 61.9] and confirmed on
  independent reanalysis weather; the deployed forecast population for
  2024-25 reads 47.5% under on 101 games against a 46.0% base
  (`docs/nfl_wind_lead_evidence.md`). *Failed* in college football,
  where the market already moves its total with wind. A model that needs a
  forecast must refuse to decide without one.
- **Confirmed starters** (goalie, pitcher, quarterback) are **gates**: no bet
  until confirmed, and the price is fetched after the confirmation. As edges
  on their own they were null.
- **Schedule spots** (rest, back-to-backs, travel) are known weeks ahead and
  usually already in the line; test them, from the stored schedule, never from
  played games.
- **Public splits, reverse line movement, steam**: used as overlays (the
  baseball game-market gate); as fades they failed.

## 6. Where the margin sits

- **A pool's take falls evenly; an exchange's margin is the commission.**
  Horse racing (2026-11-15): Hong Kong's win pool (about 18.7% out, measured
  from the pool's book) loses −15% to −23% in every odds band and about −50%
  over 51; the pool share is calibrated within 0.4 points wherever the
  sample is large. On the Betfair exchange the de-vigged BSP is within 0.2
  points of the win rate in every band of 8,000+ runners, blind bets are
  near zero before commission, and 7–10% commission makes every band and
  every year's favourite lose. No cheap side in either
  (`docs/horse_racing_market_audit.md` §3, §4). A conditional logit on the
  exchange's scheduled-start snapshot (back, spread, book, field; after Sung
  and Johnson 2010) matched the back's own log loss (1.7906 against 1.7907)
  and lost −3.7% to −4.0% net in every graded year (§4b).
  UK and Irish starting prices (2026-11-16, 1988–2026): a bookmaker's
  close that over-prices longshots. Every runner in an SP
  band at SP, Britain 2015–2026: −3.2% under 1/2, −14.1% at 4/1 to 7/1,
  −54.1% at 50/1 to 100/1 (flat stake). Power de-vig removes most of the
  bias at short prices; longshots stay over-bet, though less each decade (A/E at
  50/1 to 100/1: 0.40 in 1988–99 to 0.81 in 2020–26 in Britain, 0.19 to
  0.80 in Ireland). Irish books run higher (median 1.228 against 1.155,
  2015–2026). The place part of an each-way bet clears only when the
  runner is chosen on the SP itself (an upper bound); the two place-part
  rules that do not read the SP are positive only on units, which rely on
  knowing the SP. At each-way terms the place part is sold only inside the
  whole bet, which loses at a flat stake in every family where it was
  graded, pooled over 2005–2026 (`docs/horse_racing_market_audit.md` §8a).
- **Unders on count props.** Books put more of the margin on the over: blind
  hockey prop overs lost 9.0-12.4%, unders 0.3-3.5%. A Poisson count model
  betting selective unders on its own probability *worked*: saves, shots on
  goal, assists, blocked shots (each positive on hundreds of bets). With a
  borrowed probability correction instead of its own probability, the same
  bets lost. (`docs/nhl_market_lab.md`, `docs/nhl_clv_ev_assessment.md`)
- **Measure the lean per market** before choosing sides
  (`docs/nfl_prop_over_lean.md`), and set per-side cuts from it.
- **Structural mismatches between two books** (a sharp book's draw against a
  soft book's) are notes, not models: books close them.

## 7. The book settles a different number

- **Match the target to the book's definition.** Tackles were graded by the
  books as solo + with-assist + assists; the game log held fewer. The fake
  backtest on the undercount was +22%; on the corrected stat the model was 340
  bets +15.6% (`docs/nfl_prop_profitability_search.md` §4). Settlement rules
  (overtime, regulation-only second halves, whole-number pushes) produce
  phantom edges the same way.
- **A settlement rule that hands the bettor an option.** DraftKings voids a
  tennis moneyline bet on a player who retires after the first set, where the
  sharp book grades it a loss (DraftKings house rules, p. 47). Priced off the
  sharp book, every DraftKings tennis price is worth the side's chance of
  retiring more than it says: 1.13% a side on average, 3.0% after a previous
  match over 3½ hours, 1.7% within 30 days of a retirement
  (`scripts/tennis_retirement_rates.py`, 86,797 tour matches 2015-2026). About
  half DraftKings' 2.4-point margin a side on average, so not an edge alone;
  a term to add when a DraftKings price is compared with the sharp no-vig
  number. *Not yet graded against prices* (`docs/sports/tennis.md`). Look for
  the same shape elsewhere: any market where one book voids what another
  settles.

## 8. Stat projections — the default that usually fails

- Pro football: 11 of 11 stat-projection props lost (2,133 bets -1.90%); the
  book prices its main line flat and the information test found nothing the
  line lacked. Pro basketball: a minutes × rate projection is live (66,588 bets
  +3.60% in the backtest; live `nba_prop_projection`, all settled to 2026-11-13: 84 bets 36-48, -0.42 units, -0.6%, too few to overturn the backtest, reviewed 2026-11-13). Hockey: count models on their own probability worked on unders.
- **The architecture is a decision before code**
  (`docs/nfl_props_build_prompt.md`): one model across prop markets, one per
  market, or a shared usage core feeding per-market heads. Decide from the
  response distribution of each market (counts, yards, binary, extreme value,
  rare event), which markets share a latent (volume, pace, game script), and
  whether pooling helps the thin markets or contaminates the thick ones.
- Prop traps: line timestamps against injury news, correlated legs (one
  player, or a passer and his receiver, is one bet), survivorship in the player
  pool, push-heavy whole-number lines, one-way markets that cannot be
  de-vigged.

## 9. Selection and sizing on top of a model

- **The best N a night** (in-play models, props), **one a game**, **a per-game
  cap**: a cap is a plateau, not a gain, so set it from the record, never to
  rescue a cut. Volume after shipping is the volume dial (`set_model_volume`),
  so the cut is set for edge.
- **No two picks on one game that cannot both win** (mike, 2026-10-17), and no
  under beside a big favourite's spread bet (mike, 2026-11-11).
- **Flat stake.** 1 unit to win, risk capped at 3; any sizing tilt needs its
  own evidence (sizing by EV thirds was "not a ranking").
- **Price floors** per model, default -200; graded with the excluded prices
  removed before the best quote is chosen.

---

## The frontier — proposed here and not yet run

Each line is a hypothesis with its doc. Run it, then move it into the
sections above with its result.

- Horse racing, the sharp price against the pool: Betfair's price on a Hong
  Kong (or US) race minutes before the off against the commingled pool's odds
  at the same moment, bet the pool when it pays more than the exchange's fair
  price by more than the take, graded at the final dividend. Needs both price
  paths (`docs/sports/racing.md`, "What would have to change").
- Horse racing, a Betfair back book under 100% at the scheduled start (818
  of 115,296 races, median 0.99): an arbitrage only if the backs fill, and
  the free files carry no sizes.

- Tennis total games and games spreads priced from each player's hold and
  break rates; the scout found no published test of these markets anywhere
  (`docs/sports/tennis.md`, mechanism 3).
- Tennis fatigue (the previous match's length) against the market's own
  number, decided at the next match's first post (mechanism 4).
- Men's Grand Slam games spreads: does the book price best of five like best
  of three (mechanism 5)?

- UFC: a Pinnacle-anchored finish model for round totals on the bought
  history (every blind total loses; Pinnacle's over is near fair).
- UFC: notice length from the feed's first listing of a pairing; a
  DraftKings total left stale when its moneyline moves; the five-round
  favourite at per-book prices (null at the worst close, fails the late
  half); BestFightOdds'
  per-book prop pages as a round-total price route
- UFC round totals, the card-day over: Pinnacle's no-vig total plus a
  per-line intercept fitted on earlier years, decided on fight-day pulls,
  bet at DraftKings when EV >= 0. It fails the bar: 228 bets +6.92%
  [-2.5, +15.9], 2025 (its biggest year) -2.97%, three best dates removed
  +3.2% with a late half of -0.5%, and it was the second decision time
  tried. Even at its full return the interval needs about 400 bets. Nothing
  records it forward; the experiment is to grade it on fights after
  2026-06-13 (`docs/ufc_market_audit.md` §4f).
- UFC: notice length from the feed's first listing of a pairing, for the
  fight winner (dead on totals); the five-round favourite at per-book
  prices (null at the worst close, fails the late half)
  (`docs/ufc_market_audit.md` §8, §9).
- UFC goes the distance, the market-anchored model: +10.0% on 791 bets at
  BestFightOdds' last recorded prices 2022-2026, a plateau over cut and
  penalty, 0 of 50 placebos. **Re-graded at the price an hour before the
  fight it does not hold**: +6.8% on 745 [-0.9, +14.4], 2026 -3.6%, the cut
  neighbourhood a hump; about half of it was the market
  recalibrated (decisions priced too low in 2023-2025), and it loses at
  DraftKings, the only live prop board read. The experiment: grade it
  forward on each card's page at FanDuel and Caesars, at the price an hour
  before each fight (`docs/ufc_market_audit.md` §5f).
- UFC decision by fighter, a decision price that disagrees with the
  fight-winner price (each fighter's no-vig method prices rescaled to the
  fight-winner no-vig chance; no fitted part): 56 bets +49.5% [+12.7,
  +81.7] at the price an hour before, positive at every cut, but 2025 and
  2026 lose (16 bets, none of 2026's 7 won), and its own chance at that
  price (0.259) barely differs from the price's (0.258) while the bets won
  0.375. Too few, and the wins are not its mechanism's. The experiment:
  grade it forward with the goes-the-distance lead
  (`docs/ufc_market_audit.md` §5f).
- A third live book for live props, turning them into the cross-book
  construction (`docs/nfl_live_prop_assessment.md` §7).
- Live rushing overs at a low pace ratio; the rushing under out of sample on
  recorded halftime quotes (`docs/nfl_edge_search.md` §4,
  `docs/nfl_live_rush_attempts.md` §5).
- A Kalshi ladder graded once settled history exists
  (`docs/prop_market_research.md` §6b).
- Stale numbers on the accruing intraday sharp-book history, and one book's
  earlier posting as a lead (`docs/sports/ncaaf.md`).
- In-play selection on a second season with real clock times, possession and
  field position (`docs/ncaaf_market_audit_inplay.md` §8, §10).
- The wind rule at a different threshold, and walked back further on
  reanalysis weather (`docs/nfl_wind_lead_evidence.md`).
- The window between a starter-out announcement and the close; it needs a
  timestamped news feed (`docs/sports/ncaaf.md`).
- The women's college halftime spread on this season's stored halftime prices
  (`docs/sports/ncaabw.md`).
- Sharp-against-soft first-five-innings total overs, +30.1% on 54 bets, a
  lead for next season (`docs/mlb_f5_edge_search.md`).
- The hockey puck line: a peak, not a plateau, never trained
  (`docs/nhl_market_lab.md`); hockey in play: never attempted.
- A margin model that varies with the strike, for any one-sided ladder
  (`docs/odds_sources.md` §4).

## Ideas nobody here has tested

Not evidence of anything; listed so a new league's search has somewhere to
start beyond the frontier. Each needs a mechanism and a kill test first.

- Live team totals and live derivatives re-hung off the live full-game line.
- A prediction market's price moving before the books' (or after), as a lead.
- Correlation the book prices as independence across two markets on one game.
- The first-posted number in markets other than sides and totals (props,
  derivatives).
- Officiating or venue effects with a measurable mechanism and a schedule
  known in advance.
