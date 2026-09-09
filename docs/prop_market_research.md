# Who has actually beaten player props, how, and with what data

*Researched 2026-09-08 at mike's instruction: "scour the internet, look at open
github repos, message boards, websites, articles, posts — who has beaten this
market, how did they do it, what data did they use."*

Findings are graded by evidence quality, because most of what the search returns
is marketing. The grades:

- **A — verifiable**: a published record, a falsifiable claim, or a price we
  measured ourselves.
- **B — credible but self-reported**: a named professional describing method,
  with reputation attached but no audit.
- **C — assertion**: a tout, a content site, or a repo with no out-of-sample test.

---

## 1. The single best lead, and it is free: Kalshi

**Grade A — measured directly, 2026-09-08.** Not a claim from an article; these
are numbers pulled from the public API in this session.

| series | open markets | two-sided | volume | typical spread |
|---|---|---|---|---|
| `KXNFLRECYDS` | 956 | **956** | 186,476 | **1–2¢** |
| `KXNFLPASSYDS` | 259 | **259** | 136,083 | 3–6¢ |
| `KXNFLPASSTDS` | 118 | 78 | 61,859 | 4–10¢ |

Coverage: **16 games (a full slate), 149 player-games, median 9 strikes per
player.** No API key needed for market data; `config.KALSHI_API_BASE` and
`scripts/verify_kalshi.py` already exist.

### Why this matters more than the spread

Kalshi does not post a single over/under. It posts a **ladder of strikes**, and
a ladder is an implied distribution. Dak Prescott, passing yards, mid-price:

| line | 174.5 | 199.5 | 224.5 | 249.5 | 274.5 | 299.5 | 324.5 | 349.5 |
|---|---|---|---|---|---|---|---|---|
| P(≥) | .835 | .785 | .650 | **.510** | .365 | .225 | .140 | .095 |

Three things follow, in increasing order of value:

1. **A fair value with no vig to remove.** A 1–2¢ two-sided spread is ~2%
   round-trip against a sportsbook's ~7% prop hold. The mid is a cleaner truth
   estimate than a de-vigged Pinnacle price, and de-vigging is an assumption
   (proportional normalisation) we currently have to make.
2. **It answers the LINE MISMATCH problem, which is our single biggest source of
   discarded data.** `docs/nfl_prop_offset_evidence.md` records 63,676 NFL
   propositions thrown away because the sharp and soft books quote different
   numbers — 65% of the comparable board on NCAAF. With a ladder you interpolate
   P at *any* line, so nothing is discarded for a half-point disagreement. The
   model-free monotone bound was tried and yielded 12 bets from 63,676; this is
   the construction that actually recovers them.
3. **It cannot limit you.** A CFTC-regulated exchange has no sharp-account
   problem. `docs/prediction_markets_eval.md` flagged this in 2025 as the #1
   existential pain and never acted on it; the coverage question it left open is
   answered above.

**Caveat worth stating**: the same 2026 study that names Kalshi sharpest for MLB
props also notes prediction markets can be *more* volatile on thin markets. The
liquid NFL ladders are tight; the tail strikes (bid 0.00) are not. Any use must
bound on spread, not just presence.

---

## 2. Establish The Run (ETR) — the strongest "beaten it" claim

**Grade A/B.** ETR publishes a record: **228-158 straight bets, +14.09% ROI,
2024-25 NFL in-season.** The stronger claim, and the one that matters, is that
their projections have shown **higher accuracy than the market's closing lines
over three seasons** — beating the close is the professional standard, not ROI.

Corroborated independently: an industry piece describes ETR releasing prop
projections publicly and *"within 10 minutes… the markets basically steam hard
toward their fair value."* A projection set the market chases is, by definition,
better than the market.

- Releases first projections **~11pm ET Wednesday**.
- Sells a cheaper **"NFL Full Stat Projections"** tier separate from the pricier
  Props product.
- No public API pricing found.

**The catch**: if the market converges within ten minutes of a *public* drop, the
edge for a subscriber is small and fast. The value to us is less "bet their
picks" than "use their projection as the fair value, in place of our own model
that measures −1.90%."

---

## 3. Rufus Peabody — the method, described concretely

**Grade B.** Co-founder of Massey-Peabody (Wall Street Journal weekly since
2010, 56%+ ATS lifetime), betting group reported at **$1M+/year**, now
"basically just does props."

His stated approach is hierarchical, and it is *not* what our models do:

1. **Project game-level quantities first** — pass attempts, and how they depend
   on game state (ahead/behind, pace, script).
2. **Then player-level** — **routes run** and **target percentage**.
3. **Then build the distribution** for the stat.
4. **Compare against the MEDIAN, not the mean.**

### The mean/median trap — the most actionable idea found

Receiving and rushing yards are right-skewed: explosive plays inflate the
average. The sportsbook's line sits at the **median**, because that is where
over/under prices equalise. A projection model naturally produces a **mean**,
and mean > median for a right-skewed stat.

*"The average projection for yards is larger than the market value. Peabody
accounts for this discrepancy."*

Compare a mean projection to the line and you will systematically bet OVER. This
is confirmed independently by Unabated, which tells readers to use **median**
projections for exactly this reason.

**Our models show the OPPOSITE bias, which is its own finding.** From the
2023-25 backtest: `pass_yards` 19 over / 126 under; `pass_completions` 12 over /
187 under; `tackles_assists` 9 over / 784 under. We are ~87% unders. So either
the distributional heads are fitted too pessimistically, or the P(over)
calculation is not doing what the mean/median analysis assumes. **Worth an audit
either way** — a model that is 87% one-sided is making one bet, repeatedly.

---

## 4. What the academic literature does and does not say

**Grade A, but not about props.** The peer-reviewed work on betting-market
inefficiency is almost entirely about **game lines**, not player props:

- Favourite-longshot bias: large literature, mixed direction by sport, and the
  reviews conclude returns are small and pre-tax where positive at all.
- One concrete NFL inefficiency: teams that made the prior season's playoffs are
  over-favoured in **week 1**, reported at >25% return per game over 2004-2011.
  Situational, opening-week, game-line — not a prop result.
- Weak-form efficiency studies generally find minor inefficiencies and conclude
  beating these markets is hard.

**There is no peer-reviewed, out-of-sample demonstration of a profitable NFL
player-prop model that this search could find.** That absence is itself
information: it is consistent with the edge living in data and execution
(routes, target share, timing, book selection) rather than in a published method
anyone can copy.

---

## 5. Open-source repos — nothing to take

**Grade C across the board.** Repos found: `gmalbert/nfl-predictions` (XGBoost on
L3/L5/L10 rolling averages for DK Pick 6), `mattleonard16/nflalgorithm`
(backtesting + dashboards), `throwawayhub25/Sports-Betting-Model` (moneyline),
plus the `sports-betting` / `betting-models` GitHub topics.

All share the shape our own eleven distributional models already have — rolling
averages and a gradient-boosted head — and **none carries an out-of-sample
record, a CLV measurement, or a placebo test.** Our own version of this approach
measures **−1.90% over 2,133 bets**. There is no reason to expect a hobbyist
repo with a weaker validation story to do better, and nothing in them we do not
already have.

---

## 6. What the sharp-book consensus actually says

**Grade B.** Multiple independent sources agree on a point that contradicts our
current setup: **Pinnacle is the reference for mainlines, not for props.**

- Circa is repeatedly named the sharpest US book for props and NFL specifically,
  and the book others follow.
- A 2026 study of 600M+ line movements names **Kalshi and ProphetX** sharpest
  for MLB player props.
- Pinnacle is described as smartest on moneylines/spreads.

**Measured against our feed, 2026-09-08**: Circa, ProphetX and Novig are **not
served by The Odds API at all** (60 books returned; none of the three). Of 14
candidate sharp and exchange books probed for NFL props, only **bovada,
betonlineag and pinnacle** post two-way prop quotes. No exchange — Betfair,
Smarkets, Matchbook — posts props.

Getting Circa means a second provider: **OddsJam API $499–$5,000+/mo
(sales-gated), Unabated API from $3,000/mo.** Kalshi delivers the
"sharper-than-Pinnacle-for-props" thesis for **$0**, which is why it is first in
this document and Circa is last.

---

## 6b. BUILT: the ladder interpolator, and what it actually recovers

Recommendations 1 and 2 are implemented (`models/prop_ladder.py`,
`data/ingestors/kalshi_prop_ingestor.py`, `scripts/kalshi_ladder_probe.py`).
**Measured against the live NFL board, 2026-09-08:**

| | quotes | share |
|---|---|---|
| soft-book quotes | 2,707 | |
| priced now (a sharp reference on the SAME line) | 1,825 | 67.4% |
| a Kalshi ladder can price | 791 | 29.2% |
| **RECOVERED - priceable only via the ladder** | **301** | **11.1%** |

That is **+16.5% more priceable propositions**, and it is concentrated:

| market | soft | priced now | via ladder | recovered |
|---|---|---|---|---|
| `player_reception_yds` | 779 | 483 | 366 | **+123** |
| `player_rush_yds` | 362 | 223 | 227 | **+87** |
| `player_pass_yds` | 159 | 64 | 144 | **+87** |
| `player_rush_reception_yds` | 139 | 0 | 4 | +4 |
| `player_receptions` | 641 | 558 | **0** | 0 |
| `player_rush_attempts` | 175 | 120 | **0** | 0 |
| `player_pass_completions` | 96 | 91 | **0** | 0 |

`player_pass_yds` more than doubles (64 to 151 priceable). But **Kalshi runs no
receptions, attempts or completions market at all**, and those are ~40% of our
soft board, so this is a real and bounded gain rather than a transformation.

**It is deliberately NOT wired into scoring.** Kalshi's NFL prop settled history
reaches back only to 2026 preseason, so there is no record to validate a
reference against, and Pinnacle only became one after a placebo on three
seasons. The immediate next step is a recording job so that history starts
accumulating; grading follows it, and production wiring follows the grade.

## 7. Ranked recommendations

| # | Action | Cost | Why |
|---|---|---|---|
| 1 | **Kalshi ladder as the fair-value reference** for NFL props | **$0** | Tight two-sided prices, no de-vig assumption, already-existing config |
| 2 | **Interpolate the ladder to price ANY line** | $0 | Recovers the 63,676 propositions the equal-line rule discards |
| 3 | **Audit the 87% under-bias** in the eleven models | $0 | Mean/median is the known trap; ours points the other way, so something else is wrong |
| 4 | **Kalshi as a betting venue** | $0 | ~2% round-trip vs ~7% book hold, and no limiting |
| 5 | ETR Full Stat Projections as an alternative fair value | sub | Only source claiming to beat the close, 3 seasons |
| 6 | Circa via OddsJam/Unabated | $3–5k/mo | Strong external consensus, but the cheapest test of the same thesis is #1 |

**The one-line version**: the outside world says the sharpest prop price is not
Pinnacle, we cannot buy the book they name, and an exchange that is plausibly
better than both is sitting behind a free API we already have a config entry
for.

---

## 8. What was searched

GitHub (`sports-betting`, `betting-models` topics and NFL prop repos), academic
literature via ScienceDirect / NBER / MDPI / arXiv, Unabated's own methodology
articles, The Power Rank's interview series, ingame.com on prediction markets,
Pikkit and SmartStake book-sharpness studies, odds-API provider pricing
comparisons, and direct probes of The Odds API (60 books, prop coverage for 14
candidates) and the Kalshi Trade API (1,333 open NFL prop markets).

**Not found, despite looking**: any audited, out-of-sample, publicly reproducible
NFL player-prop model. The credible operators sell projections or trade their
own money; none publishes a method you can lift.
