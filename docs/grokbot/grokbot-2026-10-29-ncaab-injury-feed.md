# Grokbot hand-off: college basketball data

One task for grokbot from mike, for his picks service Signalbase: get a pre-tip injury feed for men's college basketball. Every account, form and email uses **signalbaseskinny@gmail.com** and the name **Signalbase**. No credential ever goes in this document, a chat log or an email.

## The task: a pre-tip injury feed

Prepared 2026-10-28, revised 2026-10-29. All facts below were read on 2026-10-28. Anything marked **unverified** was read once and not confirmed by a second source. Anything marked **unconfirmed** failed a check and must not be repeated as fact. "Day 1" is the day you start work on this brief; every clock below counts from then.

**The name on every vendor form, account, email, contract and invoice is Signalbase** (mike, 2026-10-29). Optional, in the message that hands this over: a phone number, a postal address and a website if you want them on the forms (the brief says what happens if they are blank), and a private route for credentials (section 6 says what happens if there is none).

Everything else is ready to run. The contact address for every account, form and email is **signalbaseskinny@gmail.com**, the same address as mike's cbbdata and KenPom accounts.

**What you need before starting:**

- A web browser. The SportsDataIO sign-up form renders only in a browser; a plain fetch of that page shows unrendered template placeholders.
- A way to make plain HTTP GET requests (a browser address bar or curl), and a folder in which to save every response, each file named with the endpoint and the time it was pulled.
- Access to the mailbox signalbaseskinny@gmail.com is useful but not required; section 5 says what to do either way.


### 1. Objective

Get mike a machine-readable feed of player availability (injuries, suspensions, transfers, "out" / "questionable" status) for every men's Division I college basketball game, delivered before tip-off, that his engineer can poll from a server and store in a database with a timestamp. The 2026-27 season opens 2026-11-01. The feed will be used inside a real-money betting model whose picks are sold to subscribers in an app and a Discord.

Your job this week is not to sign a contract. It is to open two sales conversations on Day 1 and come back, for each vendor, with: a written quote; the contract terms as a file; the vendor's written answers to the numbered questions in section 5; and sample files from whatever key the vendor issues. What counts as done differs by vendor:

- **SportsDataIO:** the quote, the contract text, the written answers, and the sample pulls from the free trial (which returns scrambled data). Email A asks for a key with real, current-season data, but the vendor's own trial page says production access "is only available as part of a commercial licensing discussion with our Sales team and is not granted upon immediate request", so a "no" is a complete answer. The real-data checks in section 7 run once mike signs, or once sales grant an evaluation key.
- **RotoWire:** the quote, the contract text, the written answers, and an evaluation key if they issue one. Whether RotoWire issues evaluation keys at all is **unverified** (no page on their docs site says either way). Ask; a "no" is a complete answer.

Report daily until all of that is in hand or a vendor has said no in writing.

### 2. What mike's operation needs from this source

**Fields, for every listed player:** a stable player ID; first and last name; the team (an ID or a name that can be matched to that day's schedule); status (out, doubtful, questionable, probable, game-time decision, or the vendor's equivalent); the kind of absence (injury body part, suspension, transfer portal, personal); a short note; an expected return date if known; and the vendor's own date or time for when the status was set or last edited.

**Timestamp:** no official source found carries a status-change time. mike's server will poll the feed and store every response with the time it was received, so the feed must be pollable often and must change promptly when a status changes. Where a vendor does carry a per-update time (see RotoWire's Injury News feed in section 3), that field is wanted as well.

**Cadence:** polling every 3 to 5 minutes on game days, every 30 to 60 minutes otherwise. Round the clock at 3 minutes is 480 calls a day per endpoint (24 × 60 ÷ 3); at 5 minutes it is 288. Any request limit must allow that.

**Latency:** the status must appear in the feed before the game tips. Conference reports post between about 90 minutes and 3 hours before tip (section 3.3), so the feed has to take those up inside that window. By reasoning from the conference-only scope of those reports (an inference, not a read fact): from the opening date to late December most games are non-conference, and most of those have no official report, so in that stretch the vendor's own reporters are the only source.

**Coverage:** all Division I men's teams, including the conferences for which no official report was found (WCC, Sun Belt, MAC, Big West, Ivy).

**History:** mike backtests to about 2011. **Nothing found reaches 2011.** The earliest official availability report found is the Big Ten's weekly PDF for the week of Nov 20–26, 2023; most conference reports started in 2025-26. The nearest vendor leads: SportsDataIO lists per-game injury fields "from 2016" (**unverified**, and whether that is the pre-tip value or a post-game overwrite is not stated anywhere); RotoWire's feeds reach back two weeks, and anything beyond that is "a custom arrangement". Ask each vendor once (the numbered questions in section 5). "No", or "from 2016", is a complete answer; do not keep chasing 2011. History is only useful if the stored status is the one that stood before tip-off, not a value overwritten after the game.

**Delivery:** an API or files that a server can load into a database. Nothing that requires a browser, a dashboard or copying by hand.

### 3. The options

#### 3.1 SportsDataIO (commercial feed)

**What it is.** A College Basketball API with an injured-players endpoint.
Docs: https://sportsdata.io/developers/api-documentation/ncaa-basketball

- `GET https://api.sportsdata.io/v3/cbb/scores/json/InjuredPlayers` — "Returns all injured players with their injury status, injury start date, injury body part, and injury note." The docs label its "Call Interval" as 3 Minutes. That is the vendor's refresh label, not a stated request limit, and no second source confirms it.
- `/v3/cbb/scores/json/Players` (label: 1 Hour) and `/v3/cbb/scores/json/Players/{team}` (1 Hour) also carry injury information. `/v3/cbb/scores/json/PlayersBasic/{team}` (5 Minutes) is listed as including injury information. The three interval labels, and the injury information on `PlayersBasic`, are **unverified**: they rest on the vendor's docs page alone (the public mirror of the vendor's spec names the first two endpoints but carries no intervals and has no `PlayersBasic` path).
- Trap: a second endpoint also titled "Player Details - by Active" at `/v3/cbb/scores/json/PlayersByActive` does not mention injuries. Use the paths above, not the titles.
- Fields on a player record, from the public OpenAPI mirror of the vendor's spec (https://api.apis.guru/v2/specs/sportsdata.io/cbb-v3-scores/1.0/openapi.json): `PlayerID`, `Team`, `InjuryStatus`, `InjuryStartDate`, `InjuryBodyPart`, `InjuryNotes`. No status-change timestamp; `InjuryStartDate` is a date.
- Auth: `?key=` on the query string, or header `Ocp-Apim-Subscription-Key`.
- Host: the docs say `api.sportsdata.io`; the 2023 spec mirror says `azure-api.sportsdata.io`. Ask which the key is issued for.
- **Unverified** (vendor workflow guide, https://sportsdata.io/developers/workflow-guide/ncaa-basketball): they "monitor and provide updates to injuries for all NCAA Division I teams"; official sources preferred, "credible media reports are also used"; statuses Probable, Questionable, Doubtful, Out; `InjuryStartDate` is "the date at which the player's injury was first verified"; off-season only serious injuries are tracked.
- **Unverified** (data dictionary, https://sportsdata.io/developers/data-dictionary/ncaa-basketball): per-game injury fields listed "from 2016" on box scores and player game logs. Whether that is the pre-tip value or a post-game overwrite is not stated anywhere.

**Price.** Page: https://sportsdata.io/developers (no date on the page; footer © 2026).

- Discovery Lab (self-serve, buy at discoverylab.sportsdata.io): Fantasy $99/mo ($599/yr); Odds $99/mo ($599/yr); Fantasy + Odds $149/mo ($899/yr); a free tier with last season's data. "100–1,000 API calls per day depending on tier". "Data is delayed by one day — not suitable for live applications". "Not licensed for commercial redistribution". Covers 8 sports including College Basketball. **This product cannot be the feed**: its data is a day late.
- Leagues API (the real-time product): "Contact sales — requires a commercial agreement"; "Unlimited API calls"; "Pricing based on use case, volume, and sports". **Price on request** — get it by emailing sales@sportsdata.io and using the Contact Sales button on the developers page. The vendor's licensing page (https://sportsdata.io/help/data-rights-and-licensing-questions) adds: "API usage volume is not a factor in pricing"; "Licenses are quoted per client based on leagues and competitions required"; "Commercial terms, including minimum license fees, apply regardless of corporate structure"; "Redistributing or reselling the feed itself as a standalone data product is not permitted."
- Vault / historical data: "Requires sales-enabled access"; "10+ years"; contact sales@sportsdata.io (https://sportsdata.io/help/historical-data-integration-guide). Price on request.
- One third-party marketplace figure exists, not a vendor price: Vendr lists a "Median buyer cost: $16,496" a year, range $15,898 to $20,000 (https://vendr.com/marketplace/sportsdataio). Treat it as a rough signal only.
- Free trial (https://sportsdata.io/free-trial): "scrambled data" for checking response structures and integration code; "Production access is only available as part of a commercial licensing discussion with our Sales team and is not granted upon immediate request." The scrambling note (https://sportsdata.io/help/scrambled-data) says values are shifted 5–20%, schedules, teams and players are not scrambled, and the trial does not expire. One line on the API docs page says the free trial "only provides access to the UEFA Champions League (Competition ID: 3)"; the two pages disagree, so try it and ask sales for a CBB trial key in the same email if CBB is missing.

#### 3.2 RotoWire (commercial feed, direct or through OpticOdds)

**What it is.** RotoWire's B2B API with college basketball injury, injury-news, lineup, depth-chart and player feeds.
Docs: https://rotowire.readme.io/reference/get_basketball-cbb-injuries-php

- `GET https://api.rotowire.com/Basketball/CBB/Injuries.php?key=...&format=json` — "Current injury report for college basketball players." Response: `Players[]` with `FirstName`, `LastName`, `Position`, `Link`, `Injury{Status, Type, Location, Detail, Side, ReturnDate}`, `Id`, `SportDataIOId`. Status examples on the page: OUT, GTD, Q, D, IR. The data dictionary (https://rotowire.readme.io/docs/data-dictionary.md) lists OUT, GTD, Q, D, IR, IR-R, PUP, SUSP, DNP, NA, ACT and says `ReturnDate` is often null. The page's own example has `Type: "Transfer Portal"`, so `Type` is not only body parts. For this endpoint, `Link` and `SportDataIOId` are documented on its own page only (the NBA version of the same endpoint has neither); confirm both on the first pull.
- **Gap:** this response has no team field (the NBA version of the same endpoint does). Mapping a player to a team needs the CBB Players endpoint or the Injury News feed. Ask the vendor (question list in section 5).
- No timestamp in this response. The companion feed `GET https://api.rotowire.com/Basketball/CBB/News/Injuries.php` (https://rotowire.readme.io/reference/get_basketball-cbb-news-injuries-php.md) returns `Updates[]` with `DateTime` (ISO 8601), `LastEdited`, `Priority` 1–5, `Headline`, `Notes`, `Analysis`, the same `Injury{}` block, `Player{..., Id, SportDataIOId}` and `Team{Name, Nickname, Id}`. This is the only per-update timestamp found at any vendor.
- Other CBB feeds listed (https://rotowire.readme.io/llms.txt): News, News Updates, Players, Depth Chart, Lineups ("Confirmed and projected starting lineups for college basketball games", https://rotowire.readme.io/reference/get_basketball-cbb-lineups-php), Daily Projections, Season Projections, Daily Projected Minutes, Team Previews.
- `SportDataIOId` on each player means RotoWire and SportsDataIO records can be joined if mike buys both (confirm the field is populated on the first pull).
- History (https://rotowire.readme.io/docs/historical-data.md): feed endpoints take `hours` (capped at 336, two weeks) and `date` (MMDDYYYY). "Access beyond 2 weeks requires a custom arrangement — contact your RotoWire sales representative."
- Polling guidance (https://rotowire.readme.io/docs/polling-best-practices.md): injuries every 30–60 minutes off-day, every 10–15 minutes pre-game, every 5 minutes in-game; lineups every minute in the 15–30 minutes before lock; use `hours=48` on the first poll of the day; back off on 429 and 5xx. No request limit is stated.
- Two URL styles appear in current docs (`Basketball/CBB/Injuries.php?format=json` in the reference; `get-nba-injuries.php?key=&hours=` in the quick start and OpticOdds examples). Which one a key accepts is unknown until called. Ask.
- Coverage depth (how many men's teams; women's) is stated on no page read. Ask.
- Whether RotoWire issues evaluation keys is **unverified**: no page read says either way. Ask.

**Price.** **Price on request.** No pricing, terms or rate-limit page exists anywhere on the docs site.

- Direct: the partner page https://www.rotowire.com/partner/ offers "Request a Demo" / "Schedule a Call" and a contact form, no prices. The docs' general guide names a contact: "contact us at shannon@rotowire.com" (https://rotowire.readme.io/docs/rotowire-general-guide.md).
- Through OpticOdds: RotoWire is sold as an add-on to an OpticOdds package, with a separate RotoWire key — "Your OpticOdds API Key will not work with RotoWire" (https://developer.opticodds.com/docs/rotowire-news-injury-data). OpticOdds itself is demo-request only (https://opticodds.com/pricing). OpticOdds also has an injuries endpoint of its own that lists NCAAB among its leagues, with no source named and no timestamp field (https://developer.opticodds.com/reference/get_injuries.md). This route only makes sense if mike wants OpticOdds for other reasons.

#### 3.3 Official conference availability reports (free, public, not usable as the feed)

Required in the five major conferences for the last couple of seasons; the NCAA tournament used them in 2026 through a provider called HD Intelligence (ESPN, 2026-03-04: https://www.espn.com/mens-college-basketball/story/_/id/48101693/ncaa-impose-financial-penalties-tourney-availability-report-violations). Conference games only unless stated.

| Conference | Games covered | Initial report | Game-day update | Statuses | Since | Source |
|---|---|---|---|---|---|---|
| SEC | conference games | night before | on game day (hour not stated by AP; one unverified article says two hours before tip) | pre-game available/probable/questionable/doubtful/out; game day available/game-time decision/out | 2024-25 | https://abc17news.com/news/2024/08/29/sec-to-release-player-availability-reports-as-a-sports-betting-safeguard/ |
| ACC | each conference game | night before | two hours before tip | same two sets as SEC | 2025-26 | https://theacc.com/sports/2025/8/28/availability-reporting.aspx |
| Big 12 | games between Big 12 schools | day before by 7:00 pm Central (the hour is from the policy PDF, **unverified**: https://s3.amazonaws.com/big12sports.com/documents/2025/8/19/2025_Big_12_Conference_Player_Availability_Reporting_Policy.pdf) | no later than 90 minutes before tip | game day available/game-time decision/out | 2025-26 | https://www.cbssports.com/college-football/news/big-12-to-mandate-player-availability-reports-for-football-basketball-starting-in-2025-26 |
| Big Ten | all games, non-conference included | weekly PDF | ESPN: "the morning of games" | OUT / QUESTIONABLE | earliest found: Nov 20–26, 2023 | ESPN link above |
| Big East | conference games | three hours before tip | — | questionable / out | 2025-26 | bigeast.com release 2025-12-12 (**unverified** page: https://www.bigeast.com/news/2025/12/12/general-big-east-to-provide-public-availability-reports-for-mens-and-womens-basketball.aspx) |
| MVC | conference games | 9 p.m. local the night before | two hours before tip | questionable / out (**unverified**); provider HD Intelligence | Jan 2026 | mvc-sports.com release 2026-01-02 (**unverified** page: https://mvc-sports.com/news/2026/1/1/mvc-to-implement-public-player-availability-reports-for-mens-and-womens-basketball.aspx) |
| American | intraconference only | about 2 hours before the first game of the day | updated as needed | posted as PNG images | 2025-12-30 | theamerican.org (**unverified** page: https://theamerican.org/sports/2025/12/26/2025-26_mbb_pa.aspx) |
| Atlantic 10 | not stated | about 2 h 45 min before each tip | — | not stated | — | atlantic10.com (**unverified** page: https://atlantic10.com/sports/2025/12/3/availability-reporting-mbb-current.aspx) |
| Conference USA | conference; non-conference only if both teams file | "prior to gametime" | — | Out (0%) / Questionable (~50%) | 2025-26 | conferenceusa.com (**unverified** page: https://conferenceusa.com/news/2025/8/19/general-cusa-expands-game-day-initiatives-with-collaborative-replay-availability-reports.aspx) |
| Mountain West | conference games; 2026-27 adds the conference championships | before game day | on game day before tip | not stated | 2025-26 | themw.com (**unverified** page: https://themw.com/sports/2026/8/21/reports.aspx) |
| WCC, Sun Belt, MAC, Big West, Ivy | no report found | | | | | An AP story from 2024 says the MAC adopted "a similar policy" in August 2024 without naming the sport; worth one direct look at getsomemaction.com |

Why these are not the feed:

- Reports list names and a status only. They carry no reason and no timestamp. The Big Ten PDFs carry none; the ACC and Big 12 policy texts say status only (**unverified**).
- From the opening date to late December almost every game is non-conference. Of the reports above, the Big Ten's weekly PDF covers those games; Conference USA covers a non-conference game only when both teams file; the rest cover conference games only.
- Formats are weekly PDFs (Big Ten), PNG images (American), per-game PDFs (Conference USA, **unverified**), or pages that render in the browser only (SEC, Big 12, ACC, MVC, Atlantic 10).
- Most conference sites run on Sidearm Sports (big12sports.com, mvc-sports.com and theamerican.org confirmed), whose robots.txt files disallow `/documents/` and `/images/` to general crawlers, with a crawl delay of 5. secsports.com runs on a different platform (**unverified**).
- HD Intelligence, the provider behind the MVC and NCAA tournament reports, may sell them as a feed. No contact or website for it was verified, so that is a lead to look up, not a plan.

#### 3.4 Checked and set aside

- Sportradar's college basketball API: **unconfirmed** — our check found no injury feed in its list and the detailed claim about it failed verification. Do not spend time on it unless both commercial routes fail.
- NCAA tournament reports: used in the 2026 tournament through HD Intelligence (ESPN link in 3.3); whether that was a pilot and whether it continues in 2027 is **unconfirmed**. It covers March only in any case.
- Goalserve, BALLDONTLIE, Highlightly, SportsGameOdds, collegebasketballdata.com, Genius Sports, Stats Perform, Don Best: no college basketball injury product was found (**unverified** — single pass, several pages unreadable).
- Free consumer pages (Covers, RotoWire's free news, CBS, ESPN): no timestamps and no feed, and some were empty or unreadable on 2026-10-28. Not a plan.

### 4. Recommended path and why

Run both commercial sales conversations on Day 1, in parallel, and let the first vendor that clears two gates become the feed:

1. **A written quote and contract** for real-time men's Division I coverage.
2. **A key that returns real, current-season college basketball data.** For SportsDataIO that key comes with a signed contract or as an evaluation key granted by sales during the sales discussion; for RotoWire, whether evaluation keys exist is unverified (section 3.2).

These two gates decide which feed mike buys. They are not this week's deliverables; section 1 says what those are.

Why both, not one:

- Both prices are on request, and each contract needs a sales conversation to close. Two conversations halve the chance of going into the season with nothing.
- RotoWire's Injury News feed is the only source found with a per-update timestamp (`DateTime`, `LastEdited`), and RotoWire also sells confirmed and projected starting lineups and depth charts. Its contract terms are unknown; that is its risk.
- SportsDataIO has a documented commercial product, a `Team` field on every injury row, a 3-minute refresh label on the injury endpoint, and a possible history route (per-game injury fields "from 2016", unverified, meaning unknown). Its risk is no per-update timestamp and an unknown price.
- Each RotoWire player carries a `SportDataIOId`, so if mike buys both they join and cross-check each other (confirm the field on the first pull).

What not to buy or do is listed once, in section 5.

### 5. Exact steps

#### Day 1 (the day you start), in this order

1. **SportsDataIO free trial.** In a browser, open https://sportsdata.io/free-trial and sign up with signalbaseskinny@gmail.com and a new long random password. If the sign-up sends a verification link to that mailbox and you cannot read the mailbox, stop here, record it, and go on to steps 2 to 4; mike completes the verification himself, and once he says it is done you log in with the password you set and finish the two pulls below. The password and the trial key are credentials: section 6 says where they go and where they never go. With the key, call `https://api.sportsdata.io/v3/cbb/scores/json/InjuredPlayers?key=TRIALKEY` and `https://api.sportsdata.io/v3/cbb/scores/json/Players?key=TRIALKEY`. Save each response as a file named with the endpoint and the time pulled. If the trial returns nothing for CBB, note that and continue; item 3 of Email A covers it.
2. **Email A to SportsDataIO.** Send the text below to sales@sportsdata.io. From: the mailbox signalbaseskinny@gmail.com if you can send from it. If not, send from your own address, put signalbaseskinny@gmail.com in Cc and as Reply-To, and sign it Signalbase; it is mike's request. Also paste the same text into the Contact Sales form reached from https://sportsdata.io/developers, giving signalbaseskinny@gmail.com as the contact address.
3. **Email B to RotoWire.** Send the text below to shannon@rotowire.com the same way (mike's mailbox if you can; otherwise your own address with signalbaseskinny@gmail.com in Cc and as Reply-To, signed Signalbase). Also submit the contact form at https://www.rotowire.com/partner/ with the same text and the same contact address.
4. **Record** the time each message went out, from which address, and to whom. That record, and the exact text of each email as sent, go in the Day 1 report (section 6).

#### Email A — SportsDataIO

> **Subject:** Price quote — NCAA men's basketball injury and player feeds
>
> Hello,
>
> Signalbase is a one-person subscription service that publishes its own sports betting picks to paying members through a mobile app and a private Discord. We want to buy your College Basketball (CBB) data for the 2026-27 season (opening date 2026-11-01), starting as soon as possible.
>
> Feeds we would use: Player Details - by Injured (/v3/cbb/scores/json/InjuredPlayers), polled about every 3 minutes on game days; Player Details - by Active and by Team (/Players, /Players/{team}); and the schedule and team feeds needed to match players to games.
>
> How we would use it: as an input to our own prediction models, and to show a player's availability status next to a pick inside our app and Discord.
>
> Please send:
> 1. A quote and contract term for the Leagues API covering men's Division I college basketball in real time.
> 2. Historical injury data for college basketball: what you hold, from which season, delivered as API or files, the price, and specifically whether the per-game InjuryStatus in your historical data is the status as it stood before tip-off or a value updated after the game.
> 3. A time-limited evaluation key with real, current-season college basketball data so our engineer can build the loader as early in the season as possible. If that is not possible, a trial key that includes the CBB endpoints.
> 4. The request limits that apply to the injury endpoint, and which host the key is issued for (api.sportsdata.io or azure-api.sportsdata.io).
> 5. Whether your CBB player feeds carry suspensions and transfer-portal departures as well as injuries, and in which field.
> 6. The billing details you need from us.
>
> Contact: signalbaseskinny@gmail.com. Thank you.
>
> Signalbase

#### Email B — RotoWire

> **Subject:** College basketball injury, injury news and lineup feeds — price quote
>
> Hello,
>
> Signalbase is a one-person subscription service that publishes its own sports betting picks to paying members through a mobile app and a private Discord. We would like to buy RotoWire college basketball data directly for the 2026-27 season (opening date 2026-11-01), starting as soon as possible. We are not an OpticOdds customer.
>
> Feeds we would use: CBB Injuries, CBB Injury News, CBB Lineups, CBB Depth Chart and CBB Players, polled on the cadence in your polling guide (injuries every 5 to 15 minutes around games, lineups every minute before lock).
>
> How we would use it: as an input to our own prediction models, and to show a player's status next to a pick in our app and Discord.
>
> Please send:
> 1. A quote and contract term for the feeds above.
> 2. Coverage: how many men's Division I teams the CBB injuries feed covers, and whether your editors update it from the conference availability reports on game days.
> 3. The CBB Injuries endpoint has no team field in the documented response. How should we map a player to a team and to a game — the CBB Players feed, the Team block in Injury News, or another way?
> 4. Historical injury data beyond the two-week window: from which season, in what form (files or API), and the price.
> 5. Which URL form our key will accept (Basketball/CBB/Injuries.php with format=json, or the get-...-injuries.php form), whether the hours and date parameters work on the CBB endpoints, and any request limits.
> 6. An evaluation key, if you issue them, so our engineer can build the loader as early in the season as possible.
>
> Contact: signalbaseskinny@gmail.com. Thank you.
>
> Signalbase

#### Answers to give if a vendor asks (do not improvise beyond these)

- Company size: one person. Name: Signalbase.
- Phone number, postal address, website: not in this brief. If mike put them in the hand-over message, use those. Otherwise leave them blank where the form allows; where a form makes one of them mandatory, stop on that form, use the email route for that vendor instead, and say so in the daily report.
- Use case: internal prediction models plus subscriber content (app and Discord). No raw-feed redistribution.
- Leagues: men's Division I college basketball now. Other sports may follow later; no commitment.
- Volume: up to about 480 calls a day per endpoint (a poll every 3 minutes, round the clock); nearer 288 at 5 minutes.
- Start date: as soon as a key and contract exist; the season's opening date is 2026-11-01.
- Budget: do not name one. Say mike decides on receipt of the quote.
- Anything else: "I will take that back to the owner" and put it in the daily report.

#### What to buy and what not to buy yet

- Buy **nothing**. You have no spending authority. Free trials and quote requests only; mike signs and pays.
- Do **not** buy Discovery Lab in any tier (reasons in section 3.1).
- Do **not** buy or trial OpticOdds as a way to reach RotoWire unless mike says so (section 8).
- Do **not** take out consumer subscriptions (RotoWire's consumer site, Covers, CBS, ESPN) with the intent to automate them.

#### Follow-up cadence

- Vendor replies land in signalbaseskinny@gmail.com (and in your own mailbox as well, if you sent from it with mike's address in Cc). If you cannot read mike's mailbox, mike forwards each vendor reply to you in the hand-over conversation, with any key removed first. The clock below runs from the time you sent.
- No reply one business day after you sent: send one follow-up on the same thread, and use whichever channel you did not use the first time (form or email).
- When a quote arrives: put the quote and the contract text, unchanged, in that day's report as files; a quote and a contract are not secrets. Do not negotiate price; do ask for the evaluation key if it was not included. Invoices stay in mike's mailbox; do not copy them into the conversation.
- When an evaluation key arrives: it is a credential; section 6 says where it goes. If you hold it, pull one sample from each endpoint in section 3, save each as a file with the time pulled, and run the checks in section 7 that you can run without mike's server. If it reached mike's mailbox and you never held it, the sample pulls and the section 7 checks pass to mike's engineer, and your report says only that the key arrived and when.
- Report to mike at the end of every day, in the conversation where he handed you this brief, until section 1's "done" is met for both vendors or a vendor has said no in writing.

### 6. What to hand back to mike

- **Credentials** (passwords, API keys, portal logins): never in a chat transcript, log, report, email body or screenshot, and never in a reply to this brief. Use the private route mike named in the hand-over message. If he named none: every account is opened with signalbaseskinny@gmail.com, so mike resets the password himself (if the site offers a password reset by email), reads the key after logging in, and receives any key a vendor emails in his own mailbox. In that case hand back only the account email and where on the site the key is shown. If the site offers no password reset, if a key is shown once at sign-up and not afterwards, or a key arrives in your own mailbox because you sent with Cc, hold it, say in the report that you are waiting for a private route, and do not send it any other way.
- **Per vendor**, as a short written summary plus files:
  - the quote exactly as the vendor wrote it (number, currency, term, what it covers), and the invoice format;
  - the contract text as a file, verbatim;
  - the vendor's written answers to the numbered questions in the emails;
  - the API documentation link (section 3) and which host and URL form the key accepts;
  - sample responses from each endpoint, saved as files named with endpoint and pull time, including the trial pulls from step 1;
  - the names and email addresses of the people you dealt with, and the dates of each exchange.
- **A daily report** (one message) in the conversation where mike handed you this brief: sent / replied / blocked, with times. Only what is new since the last report. The Day 1 report also carries the exact text of Emails A and B as sent, the address each went from, and the times.

### 7. Acceptance checks — how mike's engineer will know it worked

The feed is accepted when every line below is true for at least one vendor. Checks 1 to 5 need a key that returns real data: a signed contract, or an evaluation key the vendor granted. Until one exists, the only SportsDataIO key is the scrambled trial, and the only check it supports is structural: the two endpoints in step 1 answer HTTP 200 with JSON in the documented shape. Say in each report which checks ran on which key.

1. **Real data.** A GET to the injury endpoint with the production or evaluation key returns HTTP 200 and JSON with real, current-season player names and statuses, not scrambled values and not last season. The vendor has said in writing whether suspensions and transfer-portal departures are included and where (Email A question 5; RotoWire shows them as status SUSP and Type "Transfer Portal").
2. **Coverage.** The response includes players from at least five conferences, including at least one team from a conference that publishes no official report (WCC, Sun Belt, MAC, Big West or Ivy).
3. **Polling.** One hour of polling at the vendor's stated cadence (SportsDataIO every 3 minutes; RotoWire every 5 minutes) completes with no 429 and no block.
4. **Joinable.** Every player row can be linked to a team and to that day's schedule (SportsDataIO: the `Team` field; RotoWire: by whatever mapping the vendor confirms in answer to Email B question 3).
5. **Timestamps.** Every stored row carries the time mike's server received it, plus the vendor's own date or time fields (`InjuryStartDate`; RotoWire `DateTime` and `LastEdited` on Injury News). A change in a player's status between two polls on a game day shows up as two rows with two received times.
6. **Contract.** The signed contract or order form is a file mike holds, and it covers real-time men's Division I data.
7. **History (only if bought).** A sample for one past game date shows per-player status, and the vendor has stated in writing whether that status is as it stood before tip-off or a final value.
8. **Handling.** No credential appeared in the conversation or in any report; every account is under signalbaseskinny@gmail.com; the quote and contract are files mike holds.

### 8. Decisions only mike can make

| Decision | Cost | Recommendation |
|---|---|---|
| Buy SportsDataIO's Leagues API for men's college basketball | Price on request from sales@sportsdata.io (the one third-party signal is in section 3.1) | Get the quote. Buy if the price is acceptable to you; it is the better-documented product of the two. |
| Buy RotoWire direct | Price on request via shannon@rotowire.com or rotowire.com/partner/ | Get the quote. Prefer it at a comparable price, because it is the only feed with a per-update timestamp and it adds lineups and depth charts. |
| Buy both | Sum of the two quotes | If the budget allows, yes: they join on `SportDataIOId` and check each other. |
| Reach RotoWire through OpticOdds instead | OpticOdds price on request (demo form) plus the RotoWire add-on | No, unless you want an OpticOdds odds feed for other reasons. |
| Buy historical injury data (SportsDataIO Vault, or RotoWire's custom arrangement) | Price on request | Only after the vendor states in writing that the stored status is the pre-tip value. If it is a post-game value it is useless for backtests. Nothing found reaches 2011 either way. |
| Buy a feed of the official reports from HD Intelligence or a conference office | Unknown; no contact verified | A lead for later, not for this week. It would still cover conference games only. |
| Which name goes on the accounts, the contract and the invoice | None | Signalbase (mike, 2026-10-29). The email is fixed: signalbaseskinny@gmail.com, the same as the cbbdata and KenPom accounts. |
| Give grokbot the mailbox, or forward vendor replies yourself | None | Either works; section 5 covers both. Forwarding means you read every vendor reply first, which is the safer default. |
| Name a private route for credentials | None | Optional. Without one, section 6's fallback applies: accounts are under your email, you reset passwords and read keys yourself. |

### 9. Constraints

- Do not scrape conference or consumer sites under this brief: they carry no timestamps and mostly cover conference games, and the vendor feed replaces them.
- No data from Discovery Lab (a day late) or the free trial (scrambled values) goes into mike's production database or a published pick. Trial pulls are for building the loader and for the sample files only.
- Every dataset that is bought must arrive as an API or as files that a server can load into a database. No browser-only dashboards, no manual exports.
- You buy nothing and sign nothing. Quotes and contracts go to mike; he decides.
- Credentials never appear in a chat log, a report or any reply to this brief.
- Say only what is in this brief to vendors. Do not describe mike's models, his bankroll, his subscriber count or his other data sources.
- State dates in full (2026-11-01), prices as the vendor wrote them, and "price on request" where no price was given. "Day 1" is the day you start, whatever the calendar date.
