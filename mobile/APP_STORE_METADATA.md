# App Store Connect — copy/paste metadata

Drop these into App Store Connect when prompted. Lengths respect Apple's
character limits.

---

## App name (30 char max)
```
Signalbase
```

## Subtitle (30 char max)
```
Sports model picks & analytics
```

## Promotional Text (170 char max — editable without a new build)
```
Daily MLB model output: projected win probability, calibration error, and edge vs. market for every game and major player prop. Research-only, no wagers placed in-app.
```

## Description (4000 char max)
```
Signalbase is a personal sports analytics app built on top of an XGBoost
machine-learning pipeline. It surfaces the daily output of the same models
the developer uses to study MLB game and player-prop markets.

WHAT YOU SEE
- Today's picks across all eleven supported MLB markets (moneyline,
  totals, runline, first-five-innings moneyline, plus seven player-prop
  models: pitcher strikeouts, hits allowed, earned runs, outs, walks,
  and batter hits, total bases, home runs, RBIs, runs scored, stolen
  bases, walks).
- For every pick: model probability, DraftKings implied probability, the
  raw "edge" between them, and a tenth-Kelly position-size suggestion
  scaled to a bankroll you enter once in Settings.
- Signals tab: the subset of picks that clear per-model probability and
  edge thresholds.
- Performance tab: a calendar heat-map of historical settled picks plus
  rolling ROI, win-rate, and calibration metrics.
- Pick detail screens: rolling team and player trends (last 3, 5, 10, 20,
  season), weather (wind, temperature, dome status), and a plain-language
  breakdown of why the model leans the way it does.

WHAT IT IS NOT
- Not a sportsbook. You cannot place a wager from inside Signalbase.
- Not investment or gambling advice. Model output is presented for research
  and educational use only.
- Not a tipster service. Every probability shown comes from a published,
  reproducible statistical model.

HOW IT WORKS
The model is trained on roughly fifteen years of MLB game and player-game
data (MLB Stats API, Baseball Savant, historical weather, umpire
assignments). Predictions are calibrated post-training via Platt scaling so
that a "65% pick" wins close to 65% of the time over a large sample.
Calibration error is shown live in the Performance tab so you can audit the
model honestly.
```

## Keywords (100 char max, comma-separated, no spaces)
```
mlb,baseball,model,analytics,sabermetrics,picks,projections,stats,xgboost,sports
```

## Support URL
```
https://signalbase-ai.com/support
```
*(If you don't have a support page yet, point it at the same `/privacy` URL
temporarily — Apple just needs the URL to resolve.)*

## Marketing URL (optional)
```
https://signalbase-ai.com
```

## Privacy Policy URL
```
https://signalbase-ai.com/privacy
```

---

## TestFlight — Beta App Description (4000 char max)
```
Signalbase is a personal sports analytics app that displays the output of
an MLB statistical model. The app is read-only — it reads pre-computed
model picks from a Supabase backend and does not place bets, accept
payments, or collect personal information. There is no login.

This TestFlight build is for internal testing of the daily picks UI and
performance dashboard. All picks reflect model output only and are not
investment or gambling advice.
```

## TestFlight — What to Test
```
1. Open the app. The Picks tab should load today's model output within ~2
   seconds. Empty list with "No picks today" is a valid result on off-days.

2. Tap any pick to open the detail screen. Verify the rolling stat strip
   (L3 / L5 / L10 / L20 / Season) renders for team-level picks and the
   sparkline renders for player-prop picks.

3. Open the Performance tab. Verify the calendar shows red/green cells for
   past dates that have settled picks. Tap a green or red cell to drill in.

4. Open Settings. Enter a bankroll (e.g. 1000). Return to Signals. Verify
   each pick now shows a dollar bet size (tenth-Kelly, capped at 5%).

5. Toggle "Placed" on any pick in the detail screen. Re-open the app.
   The toggle should persist across launches.

Known limitations in this build:
- No push notifications.
- No login — anyone with the TestFlight invite sees the same picks.
- iPad layout is not optimized (iPhone only).
```

## TestFlight — Test Information
- **First Name / Last Name:** Matt Alksninis
- **Email:** matt.alksninis@gmail.com
- **Phone:** (your number)
- **Sign-in required:** No

---

## App Review Notes (Inside App Information → App Review Information)
```
Signalbase is a sports analytics / model-output viewer for personal use.

- No real-money wagering or in-app purchase of any kind.
- No account creation, no login. Read-only.
- The Supabase URL/anon key shipped in the bundle is intended public
  read-only access. Row-level security on the backend restricts the anon
  role to SELECT on a small set of model-output tables.
- The "Bet Size ($)" field shown in Settings is a position-size suggestion
  driven by a fractional-Kelly formula applied to a number the user enters
  locally. The app does not transmit this value anywhere.

No special review steps required. Open the app, browse the tabs, optionally
enter a bankroll in Settings.
```

## Age rating
- Frequent/Intense Simulated Gambling: **Yes** → results in 17+
- All other categories: No

## App Privacy (the questionnaire under App Privacy in App Store Connect)
- Do you collect data? **No**
- (All sub-questions disappear once "No" is selected.)

If Apple pushes back on "No data collected" because of the AsyncStorage
bankroll: that's on-device storage, not data collection per Apple's own
definition (https://developer.apple.com/app-store/app-privacy-details/).
