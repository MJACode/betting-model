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
- **Fundamentals regression behind a wide gate.** The market number is not a
  feature; the probability comes from an out-of-sample residual distribution;
  bet only when the model is 8+ points from the line; average the fit over
  seeds. *Live*: college football totals, 346 bets +9.35% (interval -2.2 to
  +21.0) in the live shape, positive under all 11 seeds, and 94 real 2026 bets
  +9.76 units. (`docs/ncaaf_market_audit.md` §2, §4)
- *Failed*: the anchored recipe on pro basketball found nothing; the women's
  college sides off the ratings had β near zero ("the line already holds it").

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
- **Line shopping against the books' own median**, priced through an
  empirical final-margin table. "The edge is the off-market number, not a read
  on the game." *Worked*: men's college spreads, 409 bets +9.97% [0.8, 18.4]
  (the doc's own estimate of the true edge: about +2% a bet). *Failed*: college
  football (337 of 338 bets were road teams: a tilt in the fitted table); the
  women's college game (the book standing apart was more often right).
- **A book's moneyline against the same book's spread.** De-vig the spread,
  invert the margin table, take the win probability. *Shipped without
  clearing*: men's college, 838 bets +4.22% [-1.2, 9.3], chosen from 162
  versions after the fact. *Failed*: college football, women's college, pro
  basketball (-25.0% in 2025-26).
- **The first post.** Decide at the moment a book first posts, with enough
  other books up to form a reference. *Worked*: men's college opening
  moneyline, 297 bets +15.15% [7.34, 23.37].
- **A stale opener.** Bet the side the sharp book favours at a soft book's
  stale opening number. *Passed the placebos* (reversed books null, other
  opens null, CLV 0.694, every season positive) and *failed executability*:
  both openers are rarely captured at the same moment on the live feed.
  (`docs/ncaaf_search_findings.md` §11)
- *Failed*: steam lag (about a third of a point of CLV, does not pay at -110);
  predicting the book's next move (correlation +0.66, but the move is smaller
  than the vig).

## 3. The book re-hangs a line mechanically

Derivative and in-play lines are often set from another number by a rule. The
edge is where the rule misses something the state shows.

- **A half priced from the full-game consensus**: a frozen `a + b × consensus`
  map plus a heavily shrunk team half-tendency, priced through a whole-point
  outcome table. *Worked*: men's college first-half total (1,887 bets +5.98%)
  and spread (845 bets +6.13%). *Failed*: hockey team, alternate and period
  totals ("the books price these markets off the main line, correctly"); college
  football first halves and team totals (every quote loses -3.7% to -6.6%).
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
  669 bets +11.84% [+5.1, +18.1], replayed on the loop's own code.
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
