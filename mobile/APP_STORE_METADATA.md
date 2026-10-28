# App Store Connect — copy/paste metadata

Drop these into App Store Connect when prompted. Lengths respect Apple's
character limits. Counts under each block are the characters inside the fence,
including line breaks.

The store name matches the iOS home-screen name in `mobile/app.json`
(`Signalbase`). The product name on signalbase-ai.com is Signal Base. Both
refer to this app.

Checked against the app source on 2026-10-27, not against a live TestFlight
binary or the EAS dashboard. Sport chips, tab names, and the auth flags below
are what that source does. `EXPO_PUBLIC_*` values set only in the EAS
dashboard would not show up here.

---

## App name (30 char max)
```
Signalbase
```
10 / 30

## Subtitle (30 char max)
```
Model signals for major sports
```
30 / 30

## Promotional Text (170 char max — editable without a new build)
```
Model output for NFL, MLB, NHL, NBA, NCAAF, WNBA, and UFC. Probability, edge versus the market, and a public record in units. Research only. No wagers are placed in-app.
```
169 / 170

## Description (4000 char max)
```
Signal Base is a personal sports analytics app (the home-screen name is Signalbase). It shows statistical model output for the sports in the app — NFL, MLB, NHL, NBA, NCAAF, WNBA, and UFC — plus a public settled record, player and team stats, and bets you choose to track.

It is not a sportsbook. You cannot place, accept, or settle a wager in the app. A bet button hands you to that sportsbook's own app or site. Nothing here is betting or financial advice. Past results do not predict future results.

PICKS
Picks has four boards:
- All: every pick scored for that day, including paused models, which are marked PAUSED and are not a bet.
- Signals: pre-game picks that crossed the bet line and are still standing. In-play picks are not on this board.
- Live Signals: in-play picks, priced at DraftKings while a game is running. The board is on every sport. In-play models run on MLB, NCAAF, and NFL. An empty board means nothing is in play, or that sport has no in-play model.
- Lines: today's NHL and NBA games, with the best price a bettable book is offering on the spread or puck line, the moneyline, and the total. Every game is listed, not only games with a pick.

All, Signals, and Live Signals show one sport at a time. Lines has its own NHL, NBA, and All control. An empty board is a real result. Some days nothing clears the bar.

A pick shows the model's probability, the price, and the edge between them. The published stake is a flat 1-unit play: the amount required to win 1 unit, with risk capped at 3 units. Results in the app are in units. Open a pick to see how the DraftKings line has moved since the pick locked.

RECORD
Record is the published settled record: wins, losses, pushes, and units, with a chart of the running total. You can share it. A paused model's already-settled bets stay on this tab.

PERFORMANCE
Performance is bets you track from a pick, plus bets you log by hand. You can mark one won, lost, or a push. Settings has an optional bankroll that only converts one unit into dollars on this device. It does not change the stake, and it is not sent off the device.

STATS
Stats is player and team numbers for the sport you select, with a line when one of the sportsbooks you checked posts it. Football uses position groups. Baseball uses hitters and pitchers. The line control is compact: the direction reads as a word, such as "At least," and the book's number sits on a short ruler.

MODELS
Models lists the built-in models still shown for the selected sport — paused and retired models are left off this list — and their settled records. My models is Build Your Own Model for NFL games: choose a market and a side, and see how that filter would have done on past games. Saving a model needs a signed-in account.

YOUR SPORTSBOOKS
The first launch asks which sportsbooks you can use. That list changes which prices you see. It does not change the published record. You can change it in Settings, and you can set your state so BetMGM, BetRivers, and Caesars links open in the right app. That state stays on the device.

Settings → Connected books opens a link screen for DraftKings and FanDuel. A banner on that screen says automatic, read-only bet sync is not switched on yet. BetMGM and Caesars are listed there as not available yet. The app does not take a sportsbook password.

ACCOUNT
The current source does not require an account. Sign-in (email code, Apple, or Google), delete account, subscriptions, and Discord account linking are in the app and stay off unless that build turns them on. Notifications are off until you opt in. Feedback is in the app.

If gambling is a problem, Settings links to 1-800-GAMBLER.
```
3660 / 4000

## Keywords (100 char max, comma-separated, no spaces)
```
nfl,mlb,nhl,nba,ncaaf,wnba,ufc,picks,props,stats,analytics,record,edge,probability,lines,live,odds
```
98 / 100

Do not repeat the app name or the subtitle words (`model`, `signals`, `sports`).

## Support URL
```
https://signalbase-ai.com/support
```

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
Signalbase (Signal Base) is a sports analytics app. It shows model output for NFL, MLB, NHL, NBA, NCAAF, WNBA, and UFC, a public settled record in units, player and team stats, and bets you track or log yourself.

This build does not place wagers. A bet button opens a sportsbook's own app or site. It is not betting or financial advice.

The source this copy was written from does not require an account. Sign-in, delete account, subscriptions, and Discord account linking appear only if the build sets their flags (EXPO_PUBLIC_AUTH_ENABLED, and the billing or Discord flags). Automatic sportsbook bet-history import is marked coming soon on the Connect Sportsbook screen. Notifications are optional.

Golf is not in the sport list. The iPhone layout is the one to test. iPad is not supported.
```
794 / 4000

## TestFlight — What to Test
```
1. First launch. Read the intro or tap Skip. The sportsbook step still appears ("Where do you bet?"). Leave the books you can use checked, then continue. An empty Picks board is a valid result.

2. Picks. Switch sports (MLB, WNBA, NBA, NFL, NCAAF, UFC, NHL). Golf is not a chip. Open All, Signals, Live Signals, and Lines.
   - All lists scored picks for the selected sport and day, including paused models marked PAUSED.
   - Signals lists pre-game picks that crossed the bet line. Empty is valid. A paused-model pick on All should not be on Signals.
   - Live Signals stays on screen for every sport. It can fill for MLB, NCAAF, and NFL. Other sports should say there is no in-play model, not that a live edge is merely absent.
   - Lines replaces the sport row with NHL, NBA, and All. It lists today's games and prices, not only games with a pick.

3. Open a pick. Confirm the label matches the side and the number. Check probability, price, and edge. Track the pick. It should show on Performance and stay tracked after you leave and come back. This is Track, not a "Placed" toggle.

4. Record. The settled record is not MLB-only. Change the sport filter. The chart and the share action should use the same rows.

5. Performance. Tracked picks and hand-logged bets live here. Log a bet, then mark it won, lost, or a push. Settings → Connected books should say automatic import is coming soon. The connect screen's banner says the same. DraftKings and FanDuel have connect buttons. BetMGM and Caesars are listed as not available yet. Do not expect a synced history while that banner is up.

6. Models. Built-in lists models for the selected sport that are not paused or retired, with their settled records. My models: on NFL, build a filter and read the historical result. Saving says an account is required unless this build has sign-in on. Any other sport should say to switch to NFL. Do not expect a saved model on a build with sign-in off.

7. Stats. Switch sports. Football should show position groups (QB, RB, WR/TE, DEF) and Teams. Baseball should show Hitters, Pitchers, and Teams. The compact line control (Compact B) uses the word "At least" (or the other direction you pick) and a short ruler. The book's number is on that control. A player none of your checked books has priced shows no line.

8. Settings. Change sportsbooks and confirm Picks and Stats follow that set. Set your state. It is only for opening BetMGM, BetRivers, and Caesars links, and it stays on the device. The bankroll field is optional and display-only: it turns 1 unit into dollars and does not change the published stake. Leave it blank and confirm no dollar figure appears that you did not type. Turn notifications on only if you want the prompt. Send a feedback note if you can, and confirm the thread opens.

9. Account, on a default build (no EXPO_PUBLIC_AUTH_ENABLED). Settings should not show Sign in, Delete account, or Subscription. Community should show "Join our Discord" as an invite link. If this build set the auth flag, Sign in should offer email code, Apple, and Google, and Delete account should be on the account card. Signing in is optional. Subscriptions appear only when billing is also on. Discord account linking replaces that invite only when that flag is on and you are signed in.

10. Hand-off. From a pick or the bet slip, open a sportsbook you have installed. The app should leave Signalbase for that book. The wager is not placed inside Signalbase. If the state is unset, BetMGM, BetRivers, and Caesars should not open a broken link.

Known limits of the source this copy describes:
- iPhone only (ios.supportsTablet is false).
- Sign-in, delete account, subscriptions, and Discord linking are off unless the build flags say otherwise. eas.json does not set those flags.
- Automatic bet-history sync is labeled not switched on yet.
- No in-app age gate. The website terms say 21+.
```
3896 / 4000

## TestFlight — Test Information
- **First Name / Last Name:** Matt Alksninis
- **Email:** matt.alksninis@gmail.com
- **Phone:** (your number)
- **Sign-in required:** No

Sign-in required stays No while `AUTH_ENABLED` is off. If a TestFlight build is made with `EXPO_PUBLIC_AUTH_ENABLED=true`, change this to Yes only if you want testers to sign in before they start. The app still treats sign-in as optional: Picks, Record, and Stats do not require it. Saving an NFL model does.

---

## App Review Notes (Inside App Information → App Review Information)
```
Signalbase (product name Signal Base) is a sports analytics app. It shows model output, a public record in units, stats, and bets the user tracks or logs. It is not a sportsbook.

- No wager is placed, accepted, or settled in the app. A bet button opens a third-party sportsbook app or site. The user places any wager there.
- No account is required in the source configuration. Sign-in, delete account, subscriptions, and Discord account linking are compiled in and hidden unless the build sets EXPO_PUBLIC_AUTH_ENABLED (and, for payments or Discord linking, those flags). eas.json does not set them. If the binary you are reviewing has them on, Settings shows Sign in. Email is a 6-digit code. Apple and Google are also offered. Delete account is on that same card.
- The anon Supabase key in the app reads model output. Row-level security limits that role. Crash reports, in-app feedback, and the user's sportsbook checklist are written under an app-generated device id. The optional bankroll and the state picker stay on the device.
- Notifications are off until the user opts in. Opting in stores a push token for that device.
- Settings → Connected books can start a SharpSports link for DraftKings or FanDuel. The screen says automatic read-only bet sync is not switched on yet. The app does not receive a sportsbook password.
- The optional bankroll only converts the flat 1-unit stake into dollars for display. It does not size the bet.

To review: open the app, finish or skip the intro, confirm the sportsbook step, then browse Picks, Record, Performance, Models, and Stats. No demo account is required on a build with auth off.
```
1639 / 4000

## Age rating
- Frequent/Intense Simulated Gambling: **Yes** → results in 17+
- All other categories: No

The in-app copy does not contain an age gate. The website terms describe the service as for people 21 and older. That is a terms statement, not a control in the app. Do not answer the age-rating questions as if the app verifies age.

## App Privacy (the questionnaire under App Privacy in App Store Connect)

Answer **Yes, we collect data.** "No" was true of the old read-only build. It is not true of this one.

Not used for tracking. The app does not use the data below for advertising or to track the user across other companies' apps.

Collect these for the default source configuration, linked to the user through the app-generated device id, purpose App Functionality:

- **Identifiers — Device ID.** An install UUID. It is sent with crash reports, feedback, and the sportsbook checklist, and with push registration if notifications are on.
- **Diagnostics — Crash Data.** Error text, the screen, and the app version, sent to fix crashes.
- **User Content — Customer Support.** Only if the user sends feedback.
- **User Content — Other User Content.** The sportsbooks the user checks, stored with the device id.
- **Identifiers.** If the user turns notifications on, the Expo push token is stored so those notifications can be sent. Leave this off the label if you ship a build with notifications removed.

Do not declare these for a build that leaves the flags off:

- Contact info (email, name). Declare it only if `EXPO_PUBLIC_AUTH_ENABLED` is on for the binary you submit. Sign-in can collect an email and the name Apple or Google sends.
- Purchases. Declare them only if billing is on for that binary.
- Precise location. The state picker is a choice the user types, and it stays on the device. It is not GPS.
- Financial info from a sportsbook. Declare the read-only bet history only if the SharpSports sync is actually on for that binary. The screen currently says it is not switched on yet.

The optional bankroll is on-device storage, not a collection, under Apple's definition (https://developer.apple.com/app-store/app-privacy-details/). The state picker is the same.
