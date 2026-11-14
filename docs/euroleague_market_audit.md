# EuroLeague market audit — the scout, and the research to come

> Started 2026-11-12 with the league-models skill (`docs/sports/euroleague.md`
> holds the sources, the identity, the grid and the purchase). This file is the
> study doc: the leads table from the scout (step 2b), then the baselines and
> the method search per market as they run. **Nothing below has been tested on
> our prices yet**: every lead is a hypothesis until it passes the kill tests.
>
> The scout ran 2026-11-12 as a read-only subagent (no paid call, no sign-up, no
> write). Its report follows unchanged. Two corrections from what was measured
> in the main session: the odds feed does carry a regulation 3-way market for
> EuroLeague (`h2h_3_way`, two books on that day's board), which lead 9 left
> open; and the "measured attendance" figures are the scout's own reads of
> EuroLeague's API, not stored rows.

Scope: published methods, open data and price history for beating EuroLeague (and EuroCup) betting markets.
Things already known were not searched again: The Odds API's `basketball_euroleague` coverage, and the official API's existence.
No paid calls, no sign-ups. The only API calls were free, keyless GETs to the official EuroLeague API, done to measure fields (timestamp 2026-11-12 23:46 UTC).

Evidence grades: **Strong** = out-of-sample, real prices, bet count, interval or CLV, nothing to sell. **Weak** = win rate only, flat -110, in-sample, one season, or undated. **Noise** = pick sellers, tipsters.

## Halftime (2026-11-13)

**Shipped 2026-11-13** (mike: "yes", knowing it misses the bar): the
Pinnacle-anchored halftime spread is live as `euroleague_live_spread_ht`
(`docs/sports/euroleague.md`, "Halftime spread"). Its build replays this
section's 364 bets one for one.

Run by a read-only research agent on the local cache, with the decision time,
inputs and cut grid written down before any result: every table in
`docs/euroleague_halftime.md`; the scripts are
`scripts/euroleague_research/r4_*.py` (`r4_report.py`, then `r4_verdict.py`).
Halftime is placed by the shot chart: the break between the last
second-quarter shot and the first third-quarter shot is a median 15.9
minutes (games with a break outside 10-25 minutes are left out). A quote
counts only if its snapshot falls inside the break and it was re-hung after
the half's last shot. **Verdict: nothing clears the bar.** The numbers are
the agent's.

| Market | Rule | Bets | Units | Return [90%] | Verdict |
|---|---|---|---|---|---|
| Total | the women's halftime method, unchanged | 574 | -12.61 | -1.93% [-8.44, +4.23] | null (99% overs; the blind over loses -10.04%) |
| Moneyline | the same margin model, priced as a moneyline | 164 | -0.51 | -0.24% [-13.25, +12.85] | null |
| Spread | the women's method, unchanged | 312 | +29.80 | +8.37% [-0.06, +16.33] | lead, misses the bar |
| Spread | the same, Pinnacle's close as the pre-game number | 364 | +45.34 | +10.93% [+3.40, +18.48] | **lead, misses the bar** |
| Total | chosen after seeing results: against the book's departure from half-time points + half the pre-game total | 212 | +33.91 | +13.67% [+3.00, +24.57] | fails (2025-26 carries 85% of its units) |

- **The mechanism, measured in the books' own lines.** At DraftKings the books
  hand back the first half's surprise at about the right rate (27.5% against
  25.7% in the games), but carry 50% of the pre-game margin into the second
  half, where the games carried 40%. So the pre-game favourite covered only
  42-48% of halftime spreads (51% when leading by 10+). Halftime totals sit on
  the formula, with no miss after a high- or low-scoring half.
- **The Pinnacle-anchored spread passed:** the placebo (0 of 200 shuffles of
  the half-time state reached it), every cut from 0.02 to 0.12 positive, the
  blind bets on the same sides losing (-2.0% to -8.6%), the other read, and
  normal prices (median -115, -135 to +105). **It failed:** the
  false-discovery correction across all 183 cells (best p 0.0096 against a
  first-rank threshold of 0.00055); one season negative in each version
  (2023-24); the 2021-22 second look negative; 72-78% of bets are halftime
  underdogs; and 2026-27's 26-31 bets carry a large share of the units.
- **What a live loop would need.** DraftKings posted a fresh halftime line in
  92-100% of games every season; FanDuel, BetMGM, BetRivers and Fanatics from
  2025-26 in 73-100%. The break is about 14 minutes and the first fresh line
  comes a median 3.1 minutes after the half's last shot, so about 12 minutes
  to decide; the 5-minute history gives about 3 reads a break. There is no
  live EuroLeague score source and no live in-play price pull yet.

## Round 2: the home lean, market-anchored models, totals, and three mechanisms per period market (2026-11-13)

Run by a read-only research agent on the local cache; every table, with the
pre-registration written before any result was read:
`docs/euroleague_round2.md`; the scripts are
`scripts/euroleague_research/r3_*.py` (`r3_report.py` reruns them all).
**Verdict: nothing clears the bar.** 109 cells; one survives a
false-discovery correction at 10% (the first-quarter moneyline shrink at cut
0.03), and it has 3 bets. Of the 91 cells with 25+ bets, none survives.

- **No hold-out read yet.** The cache ends 2026-11-12, the same 107 games of
  2026-27 round 1 read, so both frozen leads only reproduced (home underdogs
  against the spread 30 bets -24.06%; first-quarter under 4 bets 3-1).
- **The home lean, within a -200 floor:** the home moneyline at DraftKings'
  close, 972 bets +59.64 units, +4.89% [-0.68, +10.39]; +0.29% without its 10
  best dates, 2026-27 -18.50%. The away side under the same floor loses
  -13.84% on 1,572. First halves, home side: spread -5.15% on 417, moneyline
  -1.91% on 275.
- **Market-anchored models** (the de-vigged close as an unpenalised offset;
  home, home underdog, attendance, relocated venue, rest, double-round week):
  the moneyline's cross-validation picked the largest penalty in 3 of 4
  seasons and its log loss equals the market's (0.6075); the spread at cut
  0.02, 428 bets +0.95%, dies on 2026-27 (-23.92%) and a placebo (27% of
  shuffles matched it). Travel could not be built: no venue coordinates are
  stored.
- **Totals.** A referee crew's earlier residuals predicted the total only in
  2022-23 (pooled slope +0.45, SE 0.47); its bet rule, 466 bets +1.31%, is
  81.5% overs. DraftKings' first-post total: overs -1.38%, unders -7.69%.
  Open-to-close movement predicts nothing (slope +0.020), and a perfect
  predictor of the move would earn only +6.07% at the first post.
- **Three mechanisms each for the first half and quarter** (the invention
  floor): a club-pair first-half share (118 bets +7.77%, -12.44% without its
  10 best dates); a club first-quarter share; a moneyline shrink toward 50%
  (the fitted factor came out above 1 on the offshore-only seasons; the rule
  bet favourites and lost -17.00% on 150). **The club first-quarter share at
  margin 1.0** (the grid's top cell; the pre-registered margin 0.5 lost
  -3.68%): 63 bets, 43-20, +17.71 units, +22.23% [+4.08, +39.66]; passed the
  placebo (1% of shuffles at or above it), a 54/46 side split, both halves
  and both seasons positive, +4.46% without its 10 best dates; failed the
  200-bet bar, the false-discovery correction (p 0.0188) and the plateau.
  Prices -122 median, -145 shortest. **Frozen as a lead.**
- **Not yet null.** Still to run: the frozen leads on games after
  2026-11-12 (the forward cache, below); halftime, now that the shot charts
  place it on the wall clock (`data/ingestors/euroleague_shots.py`); new
  information (domestic schedules, venue coordinates, fouls and free throws);
  a fresh read not anchored on these rounds (the stuck ladder's rung 7).

## Full game, round 1 (2026-11-13)

Moneyline, spread and total, 2021-22 to 2026-27 to date, run by a read-only
research agent on the local cache. Every table, each naming its script:
`docs/euroleague_fullgame_round1.md`; the scripts are
`scripts/euroleague_research/r2_*.py` (`r2_report.py` reruns them all).
**Verdict: nothing clears the bar.** The numbers are the agent's.

- **The data.** 24 of 397,197 pre-game quotes were incoherent and dropped; the
  home spread's sign agrees with the moneyline favourite on 98-100% of pairs
  at every book. `snapshot_at` is the book's own update stamp (the snapshot
  that caught it came a median 46 seconds later). DraftKings priced 292 games
  of 2021-22 and first posts a median 45-73 hours before the tip; Pinnacle
  28-43 hours. Pinnacle priced 240/299, 272/328, 291/331, 330/330, 402/402
  and 107/107 games, 2021-22 to 2026-27.
- **Baselines.** Worst: the away moneyline at DraftKings' close, -14.39%
  [-18.25, -10.05]; underdogs longer than +300 lose about 40%. Best: the home
  moneyline at the best price, about +1.4%, interval through zero. Pinnacle's
  open is as accurate as its close (moneyline log loss 0.6105 against 0.6116
  on 1,642 games). Home teams won 63% against a 60% no-vig price; in 2026-27
  to date 54% against 60%.
- **The four basketball methods, unchanged.** Line shopping against the
  median: +7.78% on 538 spread bets, but 99.6% are home teams, 64% sit on the
  consensus number and closing-line value is negative: a home lean, not line
  shopping (+2.61% [-4.54, +9.48] without its 10 best dates, 2026-27 -25%).
  A book's moneyline against its own spread: -11.00% on 86. The first post
  against Pinnacle could not run: Pinnacle was up at 45, 52 and 6 of
  DraftKings' first posts. Sharp against soft at one snapshot: 13-23 bets,
  null.
- **The scout's leads.** Relocated "home" games show no shortfall (+0.74
  points against +0.48 at normal home games). A club's home edge does not
  persist season to season (slope 0.30, SE 0.31).
- **Home underdogs against the spread:** 454 bets +9.72% [+2.44, +16.89],
  rising to +19.4% at +5 or more. **Fails** three kill tests: 2025-26 carries
  64% of the units, +5.37% without its 10 best dates, +3.16% walk-forward;
  it misses the multiplicity bar and was chosen with the table in view.
  Frozen, to be read unchanged on 2026-27.
- **Moneyline favourites at -500 or shorter:** at DraftKings' close 188 bets,
  175-13, +34.59 units, +6.13% [+2.27, +9.60] (they won 93.1% against an
  84.1% price); +7.74% at its first post; +6.32% at Pinnacle's close; 5 of 6
  seasons positive (2022-23 -1.39%); +4.69% [+0.71, +8.41] without its 10
  best dates; survives the false-discovery correction at the first post and
  the best decidable close. **What it misses:** 188 bets, under the 200 of
  the stricter bar; one season negative; it is a price band read off the
  table, and the band beside it loses (-500 to -200: 793 bets, -151.38 units,
  -7.11%), so the edge sits on a cliff, not a plateau. **The price range:**
  median -675, shortest -4,000, 564 units risked to win 73.6, each loss 3
  units, 96% home favourites. Whether to bet it is mike's call.
- **Multiplicity:** 283 cells, 4 survive at a 10% false-discovery rate.
- **What the sample resolves:** about +/-3.5-3.8 points for one side over
  1,770 games; about +/-7 for a 450-bet rule.
- **Next:** the home lean on moneylines and first halves; a market-anchored
  model with home-underdog and attendance terms; totals by referee crew and
  at the opening total (DraftKings first-post overs lose -1.4% against -7.7%
  for unders).

## First half and first quarter, round 1 (2026-11-13)

Run by a read-only research agent on the local cache (no paid call, no
production read). Every table, each naming the script that printed it:
`docs/euroleague_1h1q_round1.md`; the scripts are
`scripts/euroleague_research/r1_*.py` (`r1_report.py` reruns them all).
**Verdict: nothing clears.** The numbers below are the agent's, from those
scripts.

- **Settlement.** A tied half or quarter pushes the two-way moneyline: no
  two-way quote carries a draw price, and at BetRivers the two-way price with
  the margin removed equals the three-way price with the draw removed (mean
  difference 0.0012 over 2,461 first-half pairs). Fanatics posts only the
  three-way first-half moneyline, where a tie loses. Ties: 6.31% of 2,125 games
  after one quarter, 3.39% at the half.
- **Bettable coverage.** No book a pick may name priced these markets before
  2025-26. 2025-26: FanDuel and BetMGM on about 314 of 402 games (first-half
  spread and total), BetRivers both moneylines on 316. 2026-27 to date: FanDuel
  and BetRivers on 106-107 of 107.
- **Baselines.** 556 cells; of the 103 positive ones with 25+ bets, none
  survives a multiple-comparison correction and none has a 90% interval above
  zero. Best at the best bettable close, 2025-26 and 2026-27: first-half
  moneyline underdog, 465 bets, +19.14 units, +4.22% [-4.64, +12.35]. Worst:
  first-half spread favourite, 423 bets, -50.67 units, -10.65% [-17.21, -3.55].
- **The books price the periods off the full game, and closely.** The
  first-half total sits at 50.05-50.29% of the full-game total and the first
  quarter at 25.07-25.37%, the books' numbers within 0.23-0.55 points of that.
  The moneylines close favourites too short (calibration slope 0.877 first
  half, 0.751 first quarter).
- **The catalogued method, unchanged** (a half priced from the full-game
  consensus): first-half totals on a 2025-26 time split, 51 bets +29.78%
  [+8.56, +49.99], **dead**: refitted on every season it leaves 9 bets, the
  frozen fit loses on the seasons it never saw (2026-27 -15.1% on 38, 2023-24
  -9.6% on 127), and it is +2.9% without its 10 best dates.
- **The one lead:** first-quarter totals, walk-forward, anchored on Pinnacle's
  full-game alternate ladder: 59 bets +14.96% [-5.49, +32.97]. Passed the
  placebo, the market-alone control, the cut neighbourhood, early/late and the
  other reads. **Failed:** 57 of 59 bets are unders, 55 of 59 fall in one
  season, and it is -13.1% without its 10 best dates. Frozen; to be read
  unchanged on 2026-27 as games are played.
- **What the sample resolves:** about 423 bettable games a market, so a return
  is resolved to roughly +/-7-9 points.
- **A data trap, checked in the main session.** A book's main first-half key
  can hold only an alternate rung: every one of BetMGM's 104 stored 2026-27
  first-half spreads sits 2+ points off FanDuel's, and on
  EUROLEAGUE_E2025_404 BetMGM's answer held one number, -6.5 at +160/-235,
  against FanDuel's -2.5. Fanatics' 58 stored 2025-26 spreads are the same.
  The purchase kept the only number it was given; the research treats a main
  number whose two prices are far from even as a rung.
- **Next round (queued):** read the frozen first-quarter under lead on 2026-27
  as it is played; the first-half home underdog on the offshore seasons; the
  moneylines with probabilities shrunk toward 50% (the calibration slopes
  above); the method on every season once the older full-game lines are
  stored, with the team half-tendency term restored; three mechanisms of our
  own before either market is called null (`SKILL.md`, step 5).

---

## 1. Leads

| # | Lead | Source (link) | Claim | Mechanism | Needs (data, price) | Evidence quality | Experiment that would test it on our prices |
|---|---|---|---|---|---|---|---|
| 1 | **Relocated "home" games are crowd-less games, live right now** | Venues: [Eurohoops 2026-03-04](https://www.eurohoops.net/en/euroleague/1939120/euroleague-confirms-alternative-venues-for-israeli-teams-and-dubai), [Eurohoops 2026-02-27](https://www.eurohoops.net/en/euroleague/1937313/fenerbahce-anadolu-efes-maccabi-tel-aviv-hapoel-tel-aviv-euroleague-basketball-announces-relocated-games), [Maccabi to Belgrade, Oct 2023](https://eurohoops.net/en/euroleague/1571519/maccabi-tel-aviv-to-play-home-games-in-belgrade-amid-israel-hamas-war). Crowd effect: De Angelis & Reade, Annals of OR 325 (2023) [RePEc](https://econpapers.repec.org/RePEc:rdg:emxxdp:em-dp2022-01) | Maccabi has played "home" games in Belgrade since Oct 2023. In 2026-27 it plays in Belgrade and Limassol (Cyprus), and Hapoel Tel Aviv in Sofia and Botevgrad. Dubai played in Sarajevo from March 2026. **Measured attendance (official API):** Maccabi v Milan, 2026-10-08: **254**. Maccabi v Real Madrid, 10-22: **102**. Hapoel v Barcelona in Sofia, 11-05: **3,428**. Across 27,691 games in ten European leagues, crowd-less games cut home win rate by about 5% (≈61% to ≈56%), and bookmakers priced that in at the time. | No crowd means no crowd-driven home edge, but these teams are still listed as home. The API's `isNeutralVenue` flag read **False** on all three games: if a model or a book keys home edge off that flag, it carries a home edge that is not there. | Arena per game (v1 schedule), `audience` (v2 game), our closing spreads and moneylines (DK, Pinnacle). | Mechanism **Strong** (large multi-league sample, published). Whether it is mispriced for these teams **untested**: no study looks at relocated EuroLeague games. Whether EuroLeague is one of De Angelis & Reade's ten leagues is **unconfirmed**: the abstract does not name them. | For every TEL / HTA / Hapoel Jerusalem / DUB "home" game since Oct 2023, compute (actual home margin) − (closing home spread) and the no-vig home win probability against the result, at Pinnacle and at DK. Compare with the same clubs' Tel Aviv / Dubai home games before relocation, and with league-wide home games. Report bet count, mean residual and a CI. Derive "neutral" from the arena name against the club's own arena, never from the flag. |
| 2 | **Home edge depends on crowd size and team, not a flat number** | Jiménez, Valido & Jiménez, *J. Sports Econ.* 26(4) 2025 [record](https://accedacris.ulpgc.es/handle/10553/139738); Pollard & Gómez, *Rev. Psicol. Deporte* 2013 [UAB](https://ddd.uab.cat/record/114170) | EuroLeague, EuroCup and ACB, 2014–2024: without a crowd, the home win probability is **5.76% lower in EuroLeague** (5.6% in ACB). Home teams commit a larger share of fouls without a crowd. The two sources disagree on EuroCup: one passage says home edge exists in EuroLeague and ACB but not EuroCup; another says the point margin falls without a crowd in EuroCup and ACB but not significantly in EuroLeague. Both are recorded. Pollard & Gómez: 17,099 games in 35 domestic leagues, 2009–12. Home win rate averages 60.7% and passes 70% in Bosnia and Croatia. Home edge in the 10 Balkan countries stays significantly higher after controlling for crowd, balance and travel (p<0.001). | Big, hostile arenas (Belgrade Arena, 21,000 capacity per the schedule, home of Crvena Zvezda; Partizan splits between it and the 8,000-seat Aleksandar Nikolic Hall) add points that a league-wide home number misses. Clubs also switch arenas: in 2026-27, Partizan, Olympiacos, Paris, Virtus and ASVEL each list two home arenas. | v2 `audience` per game, arena capacity, our closing lines. | **Weak** for betting: no prices, and these are win-rate studies. The crowd effect itself rests on a large sample. | Fit a home edge per home club (prior-season only, shrunk to the league mean) plus an attendance term. Test whether (actual margin − closing spread) is predicted by "attendance × club home edge" out of sample, season by season, 2021-22 → 2025-26. |
| 3 | **Weaker teams lean on home court more** | Foteinakis et al., *J. Hum. Sport Exerc.* 21(2), 2026-03-18 [JHSE](https://www.jhse.es/index.php/jhse/article/view/quantifying-euroleague-home-advantage) | 2,154 regular-season EuroLeague games, 2016–2025. Home teams won **62.9%**. Lower-quality teams show a larger home edge (B = 10.06, SE 2.15, p<.01). Competitive balance does not predict it (p=.088). Home edge fell in 2020-21 and peaked in 2021-22. | If books apply one home number to every team, weak home teams are under-rated at home and strong teams over-rated. | Team strength (prior ratings), our closing spreads. | **Weak**: descriptive, no prices. | Bucket home games by the home team's prior-season rating (or by closing spread) and plot the mean spread residual per bucket at DK and Pinnacle. If the slope is non-zero out of sample, a team-quality × home term is the model. |
| 4 | **Favourite-longshot and home-favourite pattern on moneylines** | Vėlyvis, *EuroLeague Betting Market and Its Efficiency*, Vilnius Univ. bachelor thesis, 2021 [PDF](https://epublications.vu.lt/object/elaba:193224883/MAIN) | 1,843 regular-season games, 2011-12 → 2018-19. One Lithuanian bookmaker, odds via OddsPortal, flat 1-euro stakes. Return per bet: home favourite **−2.65%**, home underdog −6.50%, away favourite −9.76%, away underdog **−14.80%**. Favourites over 60%: −3.0%. Longshots under 10%: −43.4%. No profitable cell. | The book loads its margin onto underdogs and away teams. At a soft book, the cheap side is the home favourite. | Our moneyline closes by book. | **Weak**: one retail book, in-sample, flat stake, moneyline only, pre-2020. | Rebuild the same four-cell table and implied-probability buckets on DK and Pinnacle closes, 2020-21 → 2025-26, with bet counts and CIs. Then at the best available price: does any cell beat zero once you shop the line? |
| 5 | **Referee crews are public about a day before tip, with history back to 2000-01** | Measured on the official v2 API (see section 2). New AI-based crew assignment from 2026-27: [Eurohoops 2026-09-28](https://www.eurohoops.net/en/euroleague/2013402/euroleague-basketball-introduces-an-innovative-referee-nomination-system/) | At 2026-11-12 23:46 UTC, crews were listed for the Nov 13 games (tip 17:30–19:30 UTC, so ≥17.7 h ahead). They were not yet listed for the Nov 17 game (≈112 h ahead). One observation, so publication falls somewhere between ~18 h and ~4.7 days before tip. Crews are present for game 1 of E2000, E2005, E2007, E2010 and E2016. The 2026-27 system has 14 rules, including nationality mix and how often a crew sees the same team. | Crews differ in foul rate, so free throws and pace differ, so totals differ. No EuroLeague-specific study found; the mechanism comes from NBA work. | v2 `referee1..4` per game, box-score fouls and FTA, our closing totals. | **Untested** for EuroLeague: no study, no prices. The data and its timing are measured. | Rolling prior-only crew foul rate and FTA rate → (actual total − closing total), 2021-22 → 2025-26, out of sample by season. Also test whether the market has moved on the crew by the time it is posted: compare the residual at the snapshot nearest crew publication with the residual at close. |
| 6 | **Travel distance and rest hurt shooting and add fouls** | Sansone et al., *J. Sports Sci.* 42(18) 2024 [record](https://iris.uniroma4.it/handle/20.500.14244/9435), DOI 10.1080/02640414.2024.2409557. Player-level companion: *IJPAS* 2025 | Top 10 teams of 2020-21, 761 games (EuroLeague plus domestic leagues). Longer travel → worse 3-point %, more offensive rebounds, more fouls. Longer rest → fewer made free throws. R² 0.05–0.22. EuroLeague schedules are less congested than the NBA's. | Fatigue lowers shooting efficiency. Long trips: Israel / Cyprus / Sofia, Istanbul, Dubai and Sarajevo. | Arena addresses (v2 `venue.address`) to geocode, kick-off times, **domestic-league schedules** (the EuroLeague API has none; this is the gap), our closing spreads and totals. | **Weak**: one season (COVID year), small effects, no prices. | Compute km travelled and days of rest for both teams before each game, including domestic games. Regress the spread and total residuals on the travel and rest gaps. Dubai's 2025-26 away games and opponents' trips to Dubai give the extreme values. |
| 7 | **Double-round weeks** | BasketNews, 2024-10-15 [article](https://basketnews.com/news-204343-euroleague-double-weeks-are-they-that-bad-and-which-teams-are-the-best.html) | 783 EuroLeague games after double-round weeks, 2016-17 → 2023-24, graded on the OddsPortal consensus spread. Home teams covered **50.39%**, away teams **53.03%**. The team tables are small samples. | The second game of a two-game week leaves less rest. Away teams also travel twice. | Schedule dates (two rounds in one week), our closing spreads. | **Weak**: no prices, consensus line, in-sample. | Tag the second game of each double-round week by its kick-off date. Test the spread residual for the team on fewer rest days, and for away teams on their second trip, at DK and Pinnacle closes. |
| 8 | **Pinnacle firms up toward tip; early lines are the soft ones** | OddsPapi vendor blog, 2026-09-19 [post](https://oddspapi.io/blog/?p=3934); SBR forum threads 2010–11 [thread](https://www.sportsbookreview.com/forum/sportsbooks-industry/591713-severely-limited-by-pinnacle) | On the 2026 EuroLeague final, Pinnacle's margin went from 5.29% at open to 3.84% at close, and its stake limit rose from 864 to a 51,813 peak. 188–192 books quote the winner market; the median two-way margin is 5.95–6.49%. SBR posters: early lines open with low limits, which rise near tip. **No source names who sets the EuroLeague line.** | The opening price is information-poor and its limits are low. Retail books may lag Pinnacle's moves. | Our timestamped snapshots (DK, Pinnacle, Bovada; FanDuel and BetMGM from 2025-26). | **Weak**: vendor blog, a single game; forum posts are 15 years old. | Measure DK's lag behind Pinnacle: when Pinnacle's no-vig price moves by ≥X between snapshots, does DK's price follow, and how fast? Then grade "bet DK when DK no-vig minus Pinnacle no-vig > threshold" against Pinnacle's close (CLV) and results. |
| 9 | **The regulation three-way market (with a draw) has no sharp anchor** | OddsPapi, same post | 69 books quote the 3-way regulation result. No sharp book or exchange quotes it (that check was done on a FIBA women's game). The draw was priced 9.0–21.0 across books on one EuroLeague game. Eurohoops reports 18% of games are decided by one possession (season not stated). | Without a sharp reference, retail draw prices vary widely. A tie probability can be modelled from the closing spread and total. | Quarter scores give the overtime rate (official API). A 3-way price: it is **not known** whether The Odds API carries one for EuroLeague; check before building. | **Noise / untested.** | Model P(regulation tie) from the closing spread and total on 2007→ results (overtime games from quarter scores). Compare with any stored 3-way draw prices, if a feed has them. |
| 10 | **Official per-round injury reports: price moves around their release** | EuroLeague per-round report pages, e.g. [round 26](https://www.euroleaguebasketball.net/euroleague/news/injury-report-round-26); reposts on [Eurohoops 2026-10-15](https://www.eurohoops.net/en/euroleague/2021188/euroleague-releases-round-6-injury-report/) | The league publishes a report per round (statuses: questionable, ruled out, sidelined) and notes clubs that have "not yet sent" one. The round 6 report came out on the day of the round's first games (Eurohoops repost at 12:32 UTC). No submission deadline is stated. | Prices quoted before the report are stale. Clubs that file late leave a window. | Report timestamps (euroleaguebasketball.net refuses automated fetches with 429; Eurohoops reposts are reachable), our snapshots. | **Untested.** | Log the report time each round. Measure line moves in the snapshots straddling it, and whether DK lags Pinnacle on "ruled out" players. |
| 11 | Big-club / public-team bias (Real Madrid, Barcelona, Olympiacos, Panathinaikos, Fenerbahce) | Tipster guides; bettingexpert 2023-24 trends (403 to our fetch; numbers seen only through search snippets) | Real Madrid 17-17 against the spread in 2023-24. Otherwise only opinion. | Fans and the public back famous clubs. | Our closing spreads by club. | **Noise** | Club-by-club spread residuals, 2021-22 → 2025-26, with CIs. Expect a null; it is cheap to rule out. |
| 12 | Market as the accuracy ceiling | Giasemidis 2020, [arXiv 2002.08465](https://arxiv.org/abs/2002.08465) | ML on 2016–19 EuroLeague games reached ≤67% test accuracy, beaten by a crowd of fans. | Benchmark only. | — | **Weak** | Use the Pinnacle-close Brier and log-loss as the bar any EuroLeague model must beat before it bets. |

Not EuroLeague, kept for the mechanism only: Qureshi & Zaman, [arXiv 2109.07581](https://arxiv.org/abs/2109.07581). NBA moneylines during COVID: betting every underdog returned +16.7%, mostly at odds of +233 to +400. Weak (one period, in-sample). Relevant only as "crowd-less games were mispriced once, in one league".

---

## 2. Data sources

| Source | What it holds | Seasons | Access (URL, auth?) | Terms / robots note |
|---|---|---|---|---|
| **Official API v2, game** — `https://api-live.euroleague.net/v2/competitions/{E\|U}/seasons/{E2026}/games/{n}` | Measured fields: `referee1..4` (name, code, country); `venue` (name, code, capacity, address); `audience`, `audienceConfirmed`; `isNeutralVenue`; `utcDate`, `localDate`; scores. **Traps:** `isNeutralVenue` = False on Maccabi's Belgrade games (attendance 254 and 102), so the flag is useless. `audience` = 0 in E2005 and E2007 means missing, not an empty arena. | Referees and venue present for game 1 of E2000, E2005, E2007, E2010, E2016, E2026. EuroCup (`U2026`) has the same shape (referees and audience present). | Open, no key, HTTP 200. | robots.txt 404 (none). No terms page found. |
| **Official API v1, schedule** — `https://api-live.euroleague.net/v1/schedules?seasonCode=E2026` | XML: gameday, arena code / name / capacity, date, start time, `confirmeddate`, `confirmedtime`, `played`. E2026 = 380 regular-season games, 273 unplayed at measurement. | Per season code. | Open, no key, 200. | As above. |
| **live.euroleague.net/api** — `Header`, `PlaybyPlay`, `Points` (shot coordinates), `Boxscore` | Header: stadium, quarter scores, referees. Its `Capacity` field holds **attendance** (7,237 = v2 `audience`, while arena capacity is 8,300). **Header returns 200 with 0 bytes for unplayed games**, so use v2 for anything pre-game. | Play-by-play and shots: **from E2007** (empty for E2000 and E2005). | Open, no key, 200. | robots.txt 404. |
| [giasemidis/euroleague_api](https://github.com/giasemidis/euroleague_api) (PyPI `euroleague-api`) | Python wrapper for EuroLeague and EuroCup: game stats, player and team stats, standings, shot data (`/api/Points`), play-by-play with lineups, box scores, game metadata (stadium, capacity, referees, via `/api/Header`), schedule. | Whatever the API holds (above). | Public GitHub, 101 stars, pushed 2026-11-12. | GitHub license field reads NOASSERTION (a LICENSE.md exists but is not a recognised licence). |
| [egemeny13/euroleague-analytics](https://github.com/egemeny13/euroleague-analytics) | Validated warehouse: possessions, 5-man lineups, shot coordinates, per-referee season stats (fouls/game, home-win rate, pace). | Loaded E2024 (330 games) and E2025 (402); backfill target E2003–E2025, "in progress". | Code public; its hosted endpoint uses OAuth (not used). | MIT. |
| R: [solmos/eurolig](https://github.com/solmos/eurolig), [FlavioLeccese92/euroleaguer](https://github.com/FlavioLeccese92/euroleaguer), [JaseZiv/euroleagueR](https://github.com/JaseZiv/euroleagueR); Python: [bsamot10/EuroleagueDataETL](https://github.com/bsamot10/EuroleagueDataETL), [dimitrisnikolaou10/euroleague_play_by_play](https://github.com/dimitrisnikolaou10/euroleague_play_by_play) | Play-by-play, shots, box scores; EuroCup in euroleaguer; lineup-aware play-by-play database in the last one. | API seasons. | Public. | Licence fields NOASSERTION or none. |
| Injury reports | EuroLeague per-round report pages; Eurohoops reposts; Dunkest fantasy notes (GTD / OUT). | Per round, at least 2024-25 onward (seen in search results). | euroleaguebasketball.net returned **429** (Vercel security checkpoint) to both WebFetch and curl. Eurohoops 200. | euroleaguebasketball.net robots.txt not readable (429). |
| Venue relocations | Eurohoops articles (dates and venues); also visible directly in the v1 schedule's arena names. | Oct 2023 → present. | 200. | — |
| [OddsPortal](https://www.oddsportal.com/basketball/europe/euroleague/results/) | Past results with odds from many bookmakers. Used by the VU thesis and BasketNews, and scraped by [giasemidis/euroleague_odds](https://github.com/giasemidis/euroleague_odds) (Selenium, last pushed 2020-11-16). | Seasons back to at least 2011-12 (VU thesis). | Web pages; no API. | **robots.txt disallows every path containing `-1998` through `-2024`**, i.e. every past-season archive URL (`euroleague-2022-2023`). The current-season `/results/` path is not disallowed. Also disallows `*/match-event/*` and the `ajax-*` paths. |
| BetExplorer | Same family of odds archive. | — | Web. | robots.txt disallows `/*?year=`, `/*?stage=`, `/*?page=`, `/bookmaker/` and others. |
| Flashscore | Results and odds pages. | — | Web. | robots.txt disallows `/live/`, `/finished/`, `/scheduled/`, `/standings/`. |
| OddsPapi (vendor) | Claims 205 books on EuroLeague, Pinnacle snapshots with **stake limits**, and free historical snapshots on its free tier. | Example dates back to the 2026 final; depth not stated. | API key = sign-up → **not tried**. | Vendor claims, not verified. |
| Betfair historic data | Exchange data since 2016 (basketball event type 7522). | 2016→. | Betfair account required → **not tried**. | No EuroLeague liquidity figure found anywhere. |
| Baselight "Ultimate Basketball Dataset" | Listing said NBA + EuroLeague + domestic leagues, with an odds table of 22,605,330 rows. | Unknown. | **Baselight has shut down** (its page, July 2026). | Dead. |

---

## 3. Routes

| Route | Result |
|---|---|
| WebSearch | Answered every query (about 30). |
| export.arxiv.org API | 200. "euroleague" gives 2 papers; "european basketball" 1; basketball + betting 10, none on EuroLeague markets. |
| `gh search repos` / `gh api` | 200. |
| api-live.euroleague.net v1 schedules, v2 games | 200, no auth. |
| live.euroleague.net/api Header / PlaybyPlay / Points | 200 (Header 0 bytes before a game is played). |
| epublications.vu.lt (thesis PDF) | 200; binary saved, text extracted locally with pypdf. |
| jhse.es, eurohoops.net, basketnews.com, oddspapi.io, econpapers.repec.org | 200. |
| centaur.reading.ac.uk (De Angelis & Reade PDF) | Blocked by an Anubis bot-protection page. |
| cris.unibo.it (same paper) | 403. |
| ncbi PMC (same paper) | 301 → pmc.ncbi.nlm.nih.gov → reCAPTCHA page. |
| iris.uniroma4.it (Sansone PDF) | 403 (abstract read via search snippets). |
| bettingexpert.com | 403. |
| dev.rdpc.dspace.uevora.pt ("COVID home advantage in EuroLeague", Évora) | 500. |
| pinnaclesports.freshdesk.com (EuroLeague overtime rules) | 404. |
| euroleaguebasketball.net (pages and robots.txt) | 429, Vercel security checkpoint. |
| baselight.app → baselight.ai | 301, then a "Baselight has shut down" page. |
| robots.txt: oddsportal / betexplorer / flashscore | 200. kaggle.com: 404 (HTML page). live.euroleague.net and api-live: 404. |
| Reddit | Not fetched directly (known 403). Search surfaced only off-topic threads via a mirror. |
| Covers forums | Search returned no Covers EuroLeague threads. |
| SBR forums | Search returned only 2010–11 threads (Pinnacle limits, a Greek book's €40 max). |

---

## 4. Dead ends (do not repeat)

- **Peer-reviewed EuroLeague market-efficiency study**, any market. Only the 2021 Vilnius bachelor thesis exists. "Euroleague betting market efficiency", "point spread / totals / closing line" + EuroLeague (standard and extended search): nothing else.
- **EuroLeague totals / over-under bias**: nothing basketball-Europe-specific. Only soccer (Paul & Weinbach, 22 leagues: overs lose more than twice what unders lose) and NBA literature.
- **First-half / first-quarter EuroLeague research**: nothing.
- **In-play EuroLeague efficiency**: nothing. Closest are a 4-game NBA Finals thesis (ISCTE 2016) and in-play football (Ötting et al., *Econ. Inquiry* 2025).
- **FIBA-rule effects on totals** (40 minutes, no 3-in-the-key, foul rules): no study. The only margin facts are from Eurohoops (18% of games decided by one possession; 34.6% by ≤5 points).
- **EuroLeague overtime rate**: no published figure. Compute it from quarter scores.
- **Who sets the EuroLeague line / Pinnacle limits**: no source. Pinnacle's own site turned up no EuroLeague resource page.
- **Public big-club bias**: tipster opinion only.
- **Kaggle EuroLeague odds dataset**: none found.
- **Betfair EuroLeague liquidity**: no figures anywhere.
- **Israel / Turkey / Dubai travel studies**: none. The only travel study is Sansone 2024 (one season).
- **Štrumbelj basketball-odds paper**: none found (his IJF paper is soccer).
- **Referee publication lead time**: no article states it. Measure it by polling the v2 game endpoint.
