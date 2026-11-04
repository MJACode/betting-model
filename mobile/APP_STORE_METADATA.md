# App Store Connect — copy/paste metadata

Drop these into App Store Connect for the launch binary. That binary requires
sign-in and sells Premium as an App Store subscription. Lengths respect
Apple's character limits. Counts under each block are the characters inside
the fence, not counting the newline before the closing fence.

The store name matches the iOS home-screen name in `mobile/app.json`
(`Signalbase`). The product name on signalbase-ai.com is Signal Base. Both
refer to this app.

This copy is for the binary with sign-in and Premium in-app purchase on.
`mobile/eas.json` does not set `EXPO_PUBLIC_AUTH_ENABLED`,
`EXPO_PUBLIC_BILLING_ENABLED`, or `EXPO_PUBLIC_DISCORD_LINK_ENABLED`. Do not
paste this listing onto a build that leaves those off.

Checked against app source on 2026-11-04: product ids and prices in
`mobile/src/lib/billingConfig.ts`, sign-in in `SignInScreen.tsx`, the Discord
invite in `discordHelpers.ts`, the sport list in `useSportFilter.ts`, and the
Picks boards in `PicksHomeScreen.tsx`. Not checked against a live TestFlight
binary.

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
MLB, WNBA, NBA, NFL, NCAAF, NCAAB, UFC, and NHL picks. Sign in for Premium in the App Store. Discord opens after a paid plan, not a trial. No wagers are placed in-app.
```
167 / 170

## Description (4000 char max)
```
Signalbase is a multi-sport picks and signals app (home-screen name Signalbase; Signal Base on signalbase-ai.com). It shows model output for MLB, WNBA, NBA, NFL, NCAAF, NCAAB, UFC, and NHL, a public settled record, player and team stats, and bets you track.

It is not a sportsbook. You cannot place, accept, or settle a wager in the app. A bet button opens that sportsbook's own app or site. Nothing here is betting or financial advice. Past results do not predict future results.

SIGN IN
An account is required. The first screen is Sign in to Signalbase. There is no guest mode and no skip. Continue with Apple, continue with Google, or enter an email and the 6-digit code. Delete account is on the account card in Settings.

PREMIUM
Premium is an auto-renewable subscription bought in the app through the App Store. Weekly is $9.99 with no free trial. Monthly is $24.99 with a 7-day free trial. Annual is $149.99 with a 7-day free trial and is marked Best value. Apple charges, renews, and cancels the plan. The paywall links Terms, the privacy policy, Apple's standard license, and Restore purchases. There is no other way to buy Premium in the app.

A free trial unlocks the app. Closing the paywall without a trial or a paid plan leaves Record available. All, Signals, and Live Signals ask you to subscribe. Scoreboard stays on screen and its games are locked. The parlay builder asks you to subscribe.

DISCORD
Discord is included only after a paid Premium plan is active. A free trial does not include it. The invite is not shown during a trial or on a free account.

PICKS
Four boards. All: every pick scored that day, including paused models marked PAUSED, which are not a bet. Signals: pre-game picks that crossed the bet line and are still standing. Live Signals: in-play picks, priced at DraftKings while a game is running, on every sport. In-play models run on MLB, NCAAF, and NFL. An empty board means nothing is in play, or that sport has no in-play model. Scoreboard: today's games for NFL, NCAAF, MLB, NBA, and NHL, with the score when one is stored and DraftKings' spread, total, and moneyline. Every game is listed. There is no bet button on Scoreboard.

All, Signals, and Live Signals show one sport at a time. An empty board is a real result.

A pick shows the model's probability, the price, and the edge. The published stake is a flat 1-unit play: the amount required to win 1 unit, with risk capped at 3 units. Results are in units. Open a pick to see how the DraftKings line has moved since the pick locked.

RECORD
Record is the published settled record: wins, losses, pushes, and units, with a chart you can share. It stays available without Premium. A paused model's already-settled bets stay on this tab.

PERFORMANCE
Performance is bets you track from a pick, plus bets you log by hand. Mark one won, lost, or a push. An optional bankroll in Settings only turns 1 unit into dollars on this device. It does not change the stake and is not sent off the device.

STATS
Stats is player and team numbers for the sport you select, with a line when a checked sportsbook posts one. Football uses position groups. Baseball uses hitters and pitchers. The line reads "At least" (or the other direction) with the book's number on a short ruler.

MODELS
Models lists built-in models still shown for that sport. Paused and retired models are left off. My models is Build Your Own Model for NFL. Saving uses the signed-in account.

SPORTSBOOKS
The first launch asks which sportsbooks you can use. That changes which prices you see, not the published record. A state setting, kept on the device, opens BetMGM, BetRivers, and Caesars in the right app. Connected books can link DraftKings or FanDuel. The screen says automatic bet import is coming soon. The app does not take a sportsbook password.

Notifications are off until you opt in. If gambling is a problem, Settings links to 1-800-GAMBLER.
```
3912 / 4000

## Keywords (100 char max, comma-separated, no spaces)
```
ncaab,nfl,mlb,nhl,nba,ncaaf,wnba,ufc,picks,premium,signals,props,stats,odds,record,live,edge,lines
```
98 / 100

Do not repeat the app name or the subtitle words (`model`, `sports`). `signals` is also in the subtitle. It stays in the keywords because it replaced the third-party name `discord` (guideline 2.3.7). `discord` and `signals` are the same length, so the line stays 98.

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

## Terms URL (opened in the app)

Sign-in and the paywall open Terms at path `/terms`. There is no separate
Terms field in App Store Connect. The privacy and support URLs above are the
Connect fields.

```
https://signalbase-ai.com/terms
```

The paywall also links Apple's standard EULA:
`https://www.apple.com/legal/internet-services/itunes/dev/stdeula/`

---

## Subscriptions (App Store Connect)

One auto-renewable subscription group. Premium is bought only in the App Store
sheet (StoreKit). The prices below are the display prices in
`mobile/src/lib/billingConfig.ts`. The price in App Store Connect has to match
them. This repo does not create the products.

| Plan | Product ID | Price | Duration | Introductory offer |
|---|---|---|---|---|
| Weekly | `com.mja.bettingpicks.premium.weekly` | $9.99 | 1 week | none |
| Monthly | `com.mja.bettingpicks.premium.monthly` | $24.99 | 1 month | 7-day free trial |
| Annual | `com.mja.bettingpicks.premium.annual` | $149.99 | 1 year | 7-day free trial |
| Monthly, no trial | `com.mja.bettingpicks.premium.monthly.notrial` | $24.99 | 1 month | none |
| Annual, no trial | `com.mja.bettingpicks.premium.annual.notrial` | $149.99 | 1 year | none |

Put each no-trial product in the same group as its trial sibling, at the same
level or higher. Level 1 is the highest. A lower level waits until renewal, so
the trial would keep running. Weekly has no trial and no no-trial sibling.

Suggested display names, for the subscription localization. App Store Connect
shows its own counter. Apple's subscription reference page does not publish a
length. These are under 30 characters:

- Premium Weekly
- Premium Monthly
- Premium Annual
- Monthly, no trial
- Annual, no trial

---

## TestFlight — Beta App Description (4000 char max)
```
Signalbase (Signal Base) is a multi-sport picks and signals app for MLB, WNBA, NBA, NFL, NCAAF, NCAAB, UFC, and NHL. It shows model output, a public settled record in units, player and team stats, and bets you track or log yourself.

This build requires sign-in. There is no guest mode. Premium is an auto-renewable subscription bought in the app through the App Store (StoreKit): Weekly $9.99 with no trial, Monthly $24.99 with a 7-day trial, Annual $149.99 with a 7-day trial. Discord opens only after a paid plan is active, not during the trial.

This build does not place wagers. A bet button opens a sportsbook's own app or site. It is not betting or financial advice. Settings links to 1-800-GAMBLER.

Use a Sandbox Apple ID for purchases. App Review signs in with the demo email and the fixed code in App Review Information. That code is not emailed. The app has no password. Golf is not in the sport list. The iPhone layout is the one to test. iPad is not supported.
```
974 / 4000

## TestFlight — What to Test
```
This binary requires sign-in and sells Premium through StoreKit. Purchases use a Sandbox Apple ID. The app has no password. The demo account in App Review Information is filled before submission.

1. Sign in. The first screen is Sign in to Signalbase. There is no Skip. App Review: type the User name into the email field first, then tap Email me a code, Continue with Apple, or Continue with Google, and enter the code from the Password field. No email is sent for that address. Anyone else taps Email me a code and uses the message that arrives. After sign-in the paywall opens.

2. Premium, on the StoreKit sandbox sheet. Weekly is $9.99 and the button says Subscribe (no free trial). Monthly is $24.99 and Annual is $149.99; those buttons say Start 7-day free trial. Annual is selected and marked Best value. Terms, Privacy, and EULA open. Restore purchases is on the screen. There is no checkout outside the App Store sheet. Product ids: com.mja.bettingpicks.premium.weekly, com.mja.bettingpicks.premium.monthly, com.mja.bettingpicks.premium.annual. Ending a trial early uses com.mja.bettingpicks.premium.monthly.notrial or com.mja.bettingpicks.premium.annual.notrial, same group, no introductory offer.

3. Close the paywall with no trial and no paid plan. Record stays available. All, Signals, and Live Signals ask for Premium. Scoreboard stays up and its games are locked. The parlay builder asks for Premium.

4. Picks, once a trial or a paid plan is active. Sports: MLB, WNBA, NBA, NFL, NCAAF, NCAAB, UFC, NHL. Golf is not a chip.
   - All lists scored picks, including paused models marked PAUSED.
   - Signals lists pre-game picks that crossed the bet line. Empty is valid.
   - Live Signals stays on every sport. It can fill for MLB, NCAAF, and NFL. Another sport says "No live model for {sport} yet."
   - Scoreboard lists today's NFL, NCAAF, MLB, NBA, and NHL games, with the score when one is stored and DraftKings' spread, total, and moneyline. Every game, not only games with a pick. No bet button on this board.

5. Open a pick. The label matches the side and the number. Check probability, price, and edge. Track it. It should show on Performance after you leave and come back.

6. Record. Change the sport filter. The chart and the share action use the same rows. This tab is available without Premium.

7. Discord. During a free trial, Settings, Discord for members, does not show Join Discord or an invite. Buy Weekly, or on a trial tap Unlock Discord early. After the plan is paid, not trialing, Join Discord opens https://discord.gg/JWMUzK9Da. A trial alone must not open that link.

8. Performance. Log a bet, then mark it won, lost, or a push. Connected books says automatic import is coming soon. DraftKings and FanDuel have connect buttons. BetMGM and Caesars are listed as not available yet.

9. Models. Built-in lists models that are not paused or retired. My models is NFL only. Saving uses the signed-in account.

10. Stats. Football shows QB, RB, WR/TE, DEF, and Teams. Baseball shows Hitters, Pitchers, and Teams. The line control uses "At least" (or the other direction) and a short ruler.

11. Settings. Sportsbooks change the prices on Picks and Stats, not the record. State is only for BetMGM, BetRivers, and Caesars links, and it stays on the device. Bankroll is optional and display-only. Gambling a problem links to 1-800-GAMBLER (1-800-522-4700). Delete account is on the account card.

12. Hand-off. From a pick, open an installed sportsbook. Signalbase leaves. The wager is not placed inside the app.

Known limits: iPhone only (ios.supportsTablet is false). No in-app age gate. The website terms say 21+. Automatic bet-history sync is labeled not switched on yet.
```
3709 / 4000

## TestFlight — Test Information
- **First Name / Last Name:** Matt Alksninis
- **Email:** matt.alksninis@gmail.com
- **Phone:** (your number)
- **Sign-in required:** Yes

Sign-in required is Yes for this binary. The first screen is sign-in. There
is no skip. Picks, other than the locked Scoreboard shell, wait for a trial
or a paid plan. Record stays available without one.

## Reviewer demo account

App Store Connect, App Review Information. **Sign-in required: Yes.**

User name is ready to paste. Password is a placeholder. Do not submit while
Password or the Sandbox Apple ID line still says TODO.

This repo is public. Do not write the six-digit code here. Matt picks a fresh
code that has never been in git, pastes it only into App Store Connect, and
sets `APP_REVIEW_DEMO_OTP` to that same value. `APP_REVIEW_DEMO_EMAIL` is
`review@signalbase-ai.com`. No mailbox has to exist for this address.

After App Review approves the binary, unset `APP_REVIEW_DEMO_OTP` (or replace
it with a new code that is not the one just used). Leaving the secret set
keeps this address open.

- **User name:** review@signalbase-ai.com
- **Password:** TODO — Matt fills a fresh 6-digit code in App Store Connect and sets APP_REVIEW_DEMO_OTP to the same value. The app has no password field. Type the User name into the email field first, then tap Email me a code, or Continue with Apple, or Continue with Google, and type that code. No email is sent.
- **Sandbox Apple ID for StoreKit:** TODO — Matt fills the Sandbox tester that completes the purchase sheet, if it is different from the sign-in account. Purchases are StoreKit sandbox, not a production charge.

The review notes tell the reviewer to use the Password field. They do not contain the code.

---

## App Review Notes (Inside App Information → App Review Information)
```
Signalbase (product name Signal Base) is a multi-sport picks and signals app for MLB, WNBA, NBA, NFL, NCAAF, NCAAB, UFC, and NHL. It shows model output, a public record in units, stats, and bets the user tracks or logs. It is not a sportsbook and it does not take real-money wagers.

No wager is placed, accepted, or settled in the app. A bet button opens a third-party sportsbook app or site. The user places any wager there. Settings links to 1-800-GAMBLER (1-800-522-4700), 24/7.

Sign-in is required. There is no guest mode and no skip. The first screen is Sign in to Signalbase. The app has no password field.

Demo account: review@signalbase-ai.com. The Password field above this note is the 6-digit code. This note does not contain that code.
Type review@signalbase-ai.com into the email field first. Then tap Email me a code, or Continue with Apple, or Continue with Google. Any of those opens the code step for this address. Type the code from the Password field. Do not wait for an email. No email is sent. Apple or Google with an empty email field starts that provider instead of this account.

Premium is an auto-renewable subscription sold only through StoreKit. Review purchases in the sandbox. Use a Sandbox Apple ID (Settings, App Store, Sandbox Account). Do not use a production card. The paywall has no external checkout.
- Weekly, $9.99, no free trial, button Subscribe. Product id com.mja.bettingpicks.premium.weekly.
- Monthly, $24.99, 7-day free trial, button Start 7-day free trial. Product id com.mja.bettingpicks.premium.monthly.
- Annual, $149.99, 7-day free trial, selected by default, marked Best value. Product id com.mja.bettingpicks.premium.annual.
All five products are in one subscription group. The other two have no introductory offer and exist so a trial can be ended early: com.mja.bettingpicks.premium.monthly.notrial and com.mja.bettingpicks.premium.annual.notrial. Rank each no-trial product at the same level as its trial sibling, or higher (level 1 is the highest). The paywall links Terms (https://signalbase-ai.com/terms), Privacy (https://signalbase-ai.com/privacy), Apple's standard EULA, and Restore purchases.

A free trial unlocks the app and does not unlock Discord. Closing the paywall with no trial and no paid plan leaves Record available. All, Signals, and Live Signals ask for Premium. Scoreboard stays visible and its games are locked.

Discord: Settings, Discord for members. During a trial the screen does not show an invite and does not show Join Discord. It says the invite waits until the paid plan starts. After Weekly (charged immediately) or after Unlock Discord early on a trial, and only once the subscription status is active, Join Discord opens https://discord.gg/JWMUzK9Da. A trial must not be given that link. Settings can show "Already in Discord via Whop?" That card only links an existing Discord account. It does not sell a subscription. Premium is purchased only in the App Store sheet.

To review: sign in, subscribe or start a trial in the sandbox, then browse Picks (All, Signals, Live Signals, Scoreboard), Record, Performance, Models, and Stats. Confirm a trial does not reveal the Discord invite, and that a paid plan does.
```
3204 / 4000

## Age rating
- Frequent/Intense Simulated Gambling: **Yes** → results in 17+
- All other categories: No

The in-app copy does not contain an age gate. The website terms describe the service as for people 21 and older. That is a terms statement, not a control in the app. Do not answer the age-rating questions as if the app verifies age.

## App Privacy (the questionnaire under App Privacy in App Store Connect)

Answer **Yes, we collect data.** Not used for tracking. The app does not use
the data below for advertising or to track the user across other companies'
apps.

This binary has sign-in and subscriptions on. Declare contact and account
data. Linked to the user. Purpose: App Functionality.

- **Contact Info — Email Address.** The address used for the email code.
- **Contact Info — Name.** The name Apple or Google sends with that sign-in.
- **Identifiers — User ID.** The account id the subscription and Discord link are stored against.
- **Purchases — Purchase History.** The App Store subscription (Weekly, Monthly, or Annual).

Also collect these, linked to the user through the app-generated device id,
purpose App Functionality:

- **Identifiers — Device ID.** An install UUID. It is sent with crash reports, load timings, feedback, and the sportsbook checklist, and with push registration if notifications are on.
- **Diagnostics — Crash Data.** Error text, the screen, and the app version, sent to fix crashes.
- **Diagnostics — Performance Data.** How long screens and requests take to load, with the screen name and app version, sent to make the app faster (`app_timings`).
- **User Content — Customer Support.** Only if the user sends feedback.
- **User Content — Other User Content.** The sportsbooks the user checks, stored with the device id.
- **Identifiers.** If the user turns notifications on, the Expo push token is stored so those notifications can be sent. Leave this off the label if you ship a build with notifications removed.

Do not declare these:

- Precise location. The state picker is a choice the user types, and it stays on the device. It is not GPS.
- Financial info from a sportsbook. The Connected books screen says automatic read-only bet sync is not switched on yet.

The optional bankroll is on-device storage, not a collection, under Apple's definition (https://developer.apple.com/app-store/app-privacy-details/). The state picker is the same.
