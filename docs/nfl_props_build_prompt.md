# Prompt: build a profitable NFL player-props model

Paste this as the first message of a new chat, from the repo root.

---

I want to build NFL player props in this repo (`MJACode/betting-model`), and I
want them to make money. Treat me as a bettor with real capital at risk, not as
someone who wants a modelling exercise.

**Build from first principles for NFL. Do not carry over any assumptions,
structure, feature sets or thresholds from the existing MLB/NBA/WNBA prop
models.** Those were built for different sports with different scoring
processes, different roster volatility and different market structures. Reuse
the *plumbing* where it genuinely fits (`player_prop_odds`, the prop ingestors,
the trainer, the config gate convention) but derive the *modelling* fresh. If
you find yourself reasoning "the NBA points model does X, so...", stop.

## The first deliverable is a decision, not code

**One model across all prop markets, or a separate model per market?** Answer
this with evidence before building anything, and show your reasoning:

- Which markets plausibly share structure? Passing yards, receptions and
  rushing attempts are all driven by a common latent — team plays, pace, game
  script, target/carry share. That argues for a shared usage core.
- Which plausibly don't? Anytime-TD is a low-rate binary; longest-reception is
  an extreme-value problem; interceptions are rare-event. Those may need
  their own treatment regardless of what the yardage markets want.
- What does the distribution actually look like per market — counts, yards,
  binary, extreme value? A model that assumes the wrong response distribution
  will be miscalibrated in the tails, which is exactly where props are priced.
- Does pooling help the thin markets, or does it contaminate the thick ones?

I want a recommended architecture with the tradeoff stated plainly. A hybrid —
shared usage/volume projection feeding per-market heads — is a legitimate
answer if you can justify it. So is "genuinely separate models". What is not
acceptable is picking one because it is easier to code.

## Markets to cover

Passing: yards, TDs, completions, attempts, interceptions.
Rushing: yards, attempts, TDs, longest.
Receiving: yards, receptions, TDs, longest.
Combined: rush+rec yards, anytime TD, first TD.
Kicking: field goals made, kicking points.
Defence: sacks, tackles+assists, interceptions.

Tell me which of these are worth modelling and which are not. "We can price it"
and "we can beat it" are different claims — I want the second. If a market is
too thin, too juiced, or too efficiently priced to beat, say so and drop it.
A short list of markets you can actually beat is worth more than full coverage.

## Data situation — read this before planning

- `nfl_player_game_log` already exists, fed from nflverse weekly stats by
  `data/ingestors/nfl_player_stats_ingestor.py`. That is your outcome data.
- nflverse play-by-play gives you snap counts, routes, target share, air yards,
  personnel and game script. It is free and it is the real feature source.
- **NFL is NOT in `config.SPORTS`**, so the platform's odds ingestor has never
  pulled NFL. Prop odds for NFL are not currently being collected at all.
  Historical NFL *game-line* odds do exist as ~6,800 JSON snapshots in
  `nfl/data/odds_cache/` (47 books) but they are NOT in Supabase.
- The Odds API historical endpoint starts **2020-06-06**. There is no data
  before that at any price. Player props have their own market keys and their
  own credit cost — price the backfill before proposing it.
- Credits are not a constraint (~4.9M remaining). Sampling density is.

Tell me what you need collected, what it costs, and what the collection
schedule has to be, before you write a model.

## The evidence bar — non-negotiable, learned the hard way here

1. **Price every bet at the juice actually quoted.** Props are heavily juiced;
   a model that looks good at -110 and is quoted -130 is a losing model. This
   has already reversed one finding in this repo.
2. **Your backtest must be able to run exactly what the live path would run.**
   If the backtest is more permissive about books, lines or timing than the
   deployed card, it is measuring fiction. This bit us last week: a backtest
   that did not exclude exchanges inflated a live model's ROI.
3. **Placebo or it did not happen.** Re-run the whole selection with the sharp
   reference swapped for a soft one. If the placebo reproduces your result, you
   have found a selection artifact, not an edge.
4. **Out-of-sample by TIME, walk-forward.** Fit on prior seasons, bet the next.
   In-sample tier boundaries and thresholds are how you fool yourself.
5. **Report the per-season split.** An edge that is 70% one season is one
   season, not an edge.
6. **Beat the right benchmark.** For a prop, that is the price you paid, not
   50%. State what a bet is worth from the number alone before claiming excess.

## Traps specific to props

- **Timestamps.** Prop lines move on injury and inactive news. A backtest that
  uses a line without knowing when it was posted relative to the news is
  leaking. This repo has already shipped a bug where props were scored after
  kickoff against in-play lines for months.
- **Selection on extremes.** Any procedure that picks the best line across
  books will preferentially sample bad data. Screen the books first.
- **Correlated legs.** Multiple props on the same player, or on a QB and his
  WR1, are one bet with extra steps. Sizing must know this.
- **Survivorship in the player pool.** Conditioning on players who played is a
  look-ahead if inactives were not known at bet time.
- **Push-heavy lines.** Whole-number receptions and attempts push often;
  grading must handle it and EV must account for it.

## What I want back

1. The one-model-vs-many decision, with the reasoning and the tradeoff.
2. A shortlist of markets you believe are beatable, and why the others are not.
3. The data collection plan, costed, with a schedule.
4. A validation plan that satisfies the bar above, written down before results
   exist so it cannot be moved afterwards.
5. Only then: the model.

Start by exploring what is already in the repo and telling me what you found,
including anything that contradicts what I have said here. If you think this
whole direction is wrong, say so before building.
