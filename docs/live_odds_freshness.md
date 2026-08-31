# Live odds freshness: what was measured, what is left, and what to do about it

Investigation of 2026-08-29/30, opened by a live NCAAF pick published at **Over
46.5** while the DraftKings app showed **51**.

---

## 1. What was measured

Each step killed a cheaper explanation than the one before it.

### Our pipeline is 1.33 seconds

| time (UTC) | event | clock |
|---|---|---|
| 23:58:16.31 | DK in-play snapshot read | ours |
| 23:58:16.95 | pick written | ours |
| **23:58:17.64** | **Discord holds the message** | **Discord's** |
| 23:59:06 | feed first shows 51.5 | ours |
| 23:59:51 | feed first shows 54.5 | ours |

The delivery time is not our claim: Discord message IDs are snowflakes encoding
Discord's own receive time. Across ten live posts, Railway→Discord was
**0.03–0.26s**. Delivery was never the problem.

### The per-event endpoint is the same cache — do not re-test this

`scripts/live_feed_probe.py` reads the same live games from the bulk and
per-event endpoints at the same instant.

**36 of 36 paired observations: identical `last_update`, identical line,
identical price, flipping to the new snapshot at the same moment.**

```
00:49:15  bulk 7.5 +104  lu 00:49:14   event 7.5 +104  lu 00:49:14
00:49:25  bulk 7.5 +104  lu 00:49:14   event 7.5 +104  lu 00:49:14
...
00:49:55  bulk 7.5 +104  lu 00:49:14   event 7.5 +104  lu 00:49:14   ← 41s old
00:50:05  bulk 7.5 +102  lu 00:49:58   event 7.5 +102  lu 00:49:58   ← both flip
```

The per-event endpoint bills 1 credit **per event per market** and buys nothing.

### It is a ~45 second cache

Over 2.5 hours of in-play fetching: **136 distinct snapshots, ~7 of our fetches
served per snapshot, median refresh 46s** (NCAAF looked closer to 64s). Every
event in a response shares one `last_update` — it is the API's snapshot stamp
for the response, **not** a per-market publish time from the book.

So a live price we publish can be up to ~45s behind the book, and **polling
faster cannot change that.** A 5s cadence buys catching a new snapshot within 5s
of it appearing, against a 46s floor.

### DraftKings direct is blocked from the worker

`scripts/dk_direct_probe.py`, run on Railway 2026-08-30 01:27 UTC:

```
=== MLB ===
  403  37ms  449b   sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/84240
  ERR  DNS          sportsbook-nash-usnj.draftkings.com   (regional host)
  403  40ms  444b   sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/84240
=== NCAAF ===  identical
```

403 in 37–41ms returning 449 bytes is an edge/WAF refusal, not a rate limit.

**The obvious read of that — a datacenter-IP block, the thing that took out
`ufcstats`, `stats.nba.com` and `site.api.espn.com` — turned out to be WRONG,
and a free test is what proved it.** The same probe from a **residential
connection** (2026-08-30):

```
403  563ms  449b   sportsbook-nash.draftkings.com/.../leagues/84240
403  518ms  444b   sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/84240
```

Two very different source addresses, **one response, byte-identical in size**.
The natural read was "the address is not what is being matched" — and that was
**too strong a conclusion from this pair**, as the fourth run below showed. What
these two actually prove is narrower: *a residential address alone is not enough
to pass.* They say nothing about whether it is NECESSARY, because neither run
carried a browser fingerprint.

### The endpoint is alive — the block is purely the client fingerprint

Opened in Chrome, the FIRST candidate URL
(`sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/84240`)
returns the full payload, **including live in-play markets on STARTED events**
(a 3rd-inning game carrying Total Over 8.5 +101 / Under 8.5 −131). Same URL,
same second, same public internet: Chrome 200, script 403.

So the URL shape is right, the data is there, and what is being matched is the
REQUEST, not the requester. Round 1 already sent a Chrome `User-Agent` and still
got 403, so it is not the UA string either — which leaves the TLS/JA3 and
HTTP/2 fingerprint, the one thing a header cannot fake. That is what
`--impersonate` tests.

**Two gotchas already visible in the real payload, for whoever writes the
parser:**

1. **There is no `last_update`, or any timestamp, anywhere in it.** DK-direct
   would give a fresher line but **no publish clock** — freshness could only be
   inferred from when *we* first observe a change, which is a weaker guarantee
   than the aggregator's (coarse, but stamped).
2. Odds are Unicode: `displayOdds.american` is `"\u2212131"` (minus sign), not
   ASCII `-131`. Parse `decimal` instead, or normalise.

Shape: `events[]` (`id`, `status`, `liveGameState.period`, live score data),
`markets[]` (`eventId`, `name`, `main`), `selections[]` (`marketId`, `label`,
`points`, `outcomeType`, `displayOdds`). A `subscriptionPartials` block hints at
a websocket push channel — unexplored, and the interesting thing if this route
ever goes past a spike.

### BOTH gates are real: fingerprint AND address (2026-08-30)

The fourth cell of the matrix, run from the Railway worker (egress
`152.55.177.9`) with the **same** `--impersonate chrome124` that gets 200 on a
laptop:

```
403  30ms  449b   sportsbook-nash.draftkings.com/.../leagues/84240
403  14ms  449b   ... /leagues/87637   (NCAAF, same)
```

Completing the matrix:

| | plain requests | browser fingerprint |
|---|---|---|
| **datacenter (Railway)** | 403 | **403** |
| **residential (laptop)** | 403 | **200** |

Neither factor explains it alone — **both are necessary**. That is an ordinary
WAF shape (fingerprint check for everyone, IP reputation on top), and it
CORRECTS the claim above: residential proxies were declared dead on the
strength of a residential run that had no browser fingerprint, i.e. tested in
the one configuration now known not to work. That was my error, and the
conclusion does not survive the fourth run.

**What follows for deployment.** DK-direct is **not shippable from the worker**
and no amount of request shaping changes that. It runs from a residential
machine, which is exactly the situation `nba_api` is already in: stats.nba.com
blocks datacenter IPs, so the Basketball Daily Ingest job runs on a local
machine on a schedule. That precedent is the legitimate route, and it is free.

A residential proxy is now *technically* un-eliminated, but it is a paid
service whose purpose is defeating this kind of block — and the local-machine
precedent gets the same data without buying that. It stays out of scope absent
a separate decision.

---

## 2. What is still unmeasured, and why it matters

**Is the aggregator merely COARSE, or is it also BEHIND?**

A 45s-old-but-accurate snapshot and a snapshot that is itself a minute stale
look identical from our side. The difference decides everything:

| finding | what to do |
|---|---|
| coarse only | nothing to buy. The edge band + disclosure already shipped ARE the fix. |
| also behind | it is a source problem, and the source has to change. |

Answering it requires **a second independent read of DraftKings' line**, which
is the whole reason the DK-direct spike existed.

**The cheapest possible measurement needs no infrastructure at all:** the next
time a live pick posts, screenshot the DraftKings app with the clock visible.
One paired observation — our published number and timestamp against DK's number
at a known second — is most of the answer.

---

## 3. Routes to a fresher live line

Ranked by legitimacy first, then by whether they use a connection we already
have.

### A. A residential IP — the proven precedent

**This repo has already solved this exact problem once.** `stats.nba.com` blocks
datacenter IPs, so the WNBA/NBA ingest runs as a Windows Task Scheduler job on
Matt's machine and writes to Supabase (`docs/sports/wnba.md`, `docs/sports/nba.md`). DK's block is the same shape,
so the same answer applies.

Shape: local poller → Supabase `odds` rows (`snapshot_type='in_play'`,
`bookmaker='draftkings_direct'`) → the Railway live loops prefer the fresher
source when it is present and fall back to The Odds API when it is not.

- **Cost:** $0. No new vendor, no new infra.
- **Risk, and it is real:** the machine has to be awake during game windows, and
  that job has already died silently once (dead from ~2026-07-04, found in
  session 112). Any version of this needs a `system_health` check from day one.
- **First step:** run `python -m scripts.dk_direct_probe` on the local machine.
  The script already tries several URL shapes and prints what answers. If it
  returns JSON there, this route is open.

### B. A different datacenter — cheap to test, probably blocked

Supabase Edge Functions run on Deno Deploy, a different IP space from Railway,
and we already have two functions deployed there. Cloudflare Workers / Vercel /
Fly free tiers are the same idea. All are well-known datacenter ranges and
likely already on the same blocklist, but the test is ten minutes.

Needs `supabase functions deploy` — the MCP is read-only for functions.

### C. Ask DraftKings

DK runs media and affiliate programs and has partner data arrangements. Slow,
probably needs a commercial relationship, and the only route with zero ToS
question. Worth an email precisely because it is the one that cannot be revoked
by a WAF rule.

### D. Buy it from someone who has already solved it

The entire value proposition of OpticOdds / OddsPapi / TheRundown is maintaining
book connections we cannot. See §4.

### Ruled out by measurement, not by argument

- **Residential proxy networks** (Bright Data, Oxylabs and similar). I expected
  this to be the answer and it is not: a residential IP gets the **identical
  403**. Nothing to buy. This is the strongest result in the whole
  investigation, because it is the one that saved money.

### Being tested at the user's direction

- **Browser impersonation** (`--impersonate`, curl_cffi TLS/JA3 replay). I
  raised the concern that working around a 403 is a refusal rather than a
  technical problem; **mike's call, 2026-08-30, was to test it** — "there is
  nothing illegal here" — and that is recorded as the decision it is. The
  narrow case for it: this is an unauthenticated public page a browser fetches
  freely, read-only and low-rate, which is the same posture as the ESPN hidden
  API this platform already depends on daily.

  What would make it a genuinely different thing, and would need a fresh
  decision rather than this one: authenticating, defeating a challenge, rate
  that resembles scraping, or redistributing the data. **None of that is in
  scope**, and DK's ToS forbids automated access regardless of how the request
  is shaped — which is why this stays a spike and does not enter the pipeline
  on its own.
- **Using the mobile app's users as collectors.** It would technically work —
  phones are on residential and cellular IPs — and it is unambiguously wrong. It
  conscripts users' devices and addresses for our data collection, and would
  rightly get the app removed.

---

## 4. Vendor comparison

Latency claims below are **vendor-stated and unverified**. Note also that most
of the public comparison pages are written by these vendors about each other,
and that **OddsJam's API is powered by OpticOdds** — the same infrastructure,
not a second opinion.

| vendor | live delivery | cost | note |
|---|---|---|---|
| The Odds API (current) | **~45s cache, measured** | current plan | the floor we are on |
| OddsPapi | WebSocket push on Pro | free tier: 250 req/mo, no card | free tier is enough for ONE comparison run |
| TheRundown | WebSocket, "sub-second on sharp books" | $49/mo Starter | cheapest paid trial |
| OpticOdds / OddsJam | sub-second, enterprise | reported ~$5,000/mo | out of scope |

**Every "sub-second" claim describes the vendor's delivery once a book moves,
not how often they poll DraftKings.** The only number worth acting on is one we
measure ourselves — which is exactly how the current floor was found.

### Runbook: trialling a vendor

1. Create the account and put the key in Railway → Variables.
2. Point `scripts/live_feed_probe.py` at it (add an adapter; the table
   `live_feed_probe` already keys rows by `source`, so the comparison against
   The Odds API is automatic).
3. Run 20 minutes on a live slate and compare `last_update` advance intervals
   and the line itself, the same way the bulk-vs-per-event question was settled.
4. Decide on the measurement, not the marketing.

---

## 5. What shipped in the meantime

Because the floor is real whatever the source turns out to be:

- **NCAAF live edge is a band** (#283): floor 0.08 → 0.12, cap 0.25 → 0.18. On
  the slate that produced the bad pick, the two largest edges were the two worst
  immediate line moves.
- **A live-specific edge cap** (#286): `LIVE_MAX_EDGE_CAP`, separate from the
  pre-game one, because a pre-game price is stable for hours while a live price
  is ≤45s old by construction. Left at 0.20 for MLB — measured, not skipped: its
  worst edge bucket is at the BOTTOM (0.10–0.12 = −63.5%), 0.16–0.18 = +17.3%.
- **Disclosure** (#286): every live Discord post and the Live tab name the
  measured number and resolve to an action.
- **Audit trail** (#282): live prices for every sport are written to `odds` with
  the feed's own publish clock, so this question is answerable with a query
  instead of an argument.

---

## 6. ANSWERED, 2026-08-30: it is COARSE, not behind

The question §1–§4 exist to ask — *is the aggregator's in-play cache merely
coarse, or is it also stale?* — has an answer, from the first slate where DK's
own line was recorded independently (`scripts/dk_freshness_compare.py`, run on
mike's machine, 6,214 distinct quotes across 14 MLB games over 16 hours).

**The usable overlap is 2026-08-30 13:55–15:50 ET, 11 games, both feeds live.**
The overnight session has no aggregator counterpart at all (§6.4).

### The verdict, and the three numbers that agree on it

| measured | value |
|---|---|
| DK reprices a live total every | **15–25 s** |
| Aggregator publishes a distinct snapshot every | **~67 s** (108 in 2 h) |
| Aggregator polls per distinct snapshot | **147** |
| DK line changes that ever reached us | **29.7%** (559 of 1,885) |
| Lag, for a change that did reach us — median / p90 | **16.1 s / 64.3 s** |
| Aggregator's self-reported age (`created_at − snapshot_at`) — median / p90 | **28.6 s / 50.8 s** |

Those are three independent measurements telling one story. A quote that lives
~20 s, sampled on a ~67 s cadence, should be captured about 20/67 ≈ **30%** of
the time — we measured **29.7%**. A captured quote should be found about half
its lifetime in, ≈ 10–15 s — we measured **16.1 s**. A poll landing at random
inside a ~67 s bucket should sit ~33 s deep — we measured **28.6 s**.

**Nothing is left over for "behind."** The aggregator is not serving us a stale
snapshot; it is serving us an honest snapshot too rarely. Per §1's own framing
that means **the edge band and the disclosure already shipped ARE the fix**, and
there is no source problem to buy our way out of.

### The join key is sound — this is the check that makes the above trustworthy

A strict equality join on `(game, total_line, over_price, under_price)` will
manufacture a skip rate if the two sides represent prices differently. They do
not: both are American integers, and **96.8% of the aggregator's 654 distinct
quotes are found in DK's set** (633 of 654). What we hold is a faithful subset of
DK's book — 654 of the 1,890 distinct quotes DK actually showed. The misses are
real skips, not a matching artifact.

### What coarseness actually costs at the moment of a bet

Row-weighted over every in-play row we wrote (so a cached snapshot re-read 147
times counts 147 times — which is the right weighting, because it is what "the
price at a random action moment" means), against DK's concurrent quote:

- **11.8% of the time the line itself differs.** Under §1c that is not a stale
  price, it is **a different bet**: 7.5 and 8.5 are not the same proposition.
- Of the 88.2% on the same line, **25.1% match on price exactly**, the median
  gap is **3 cents**, and **20.7% are ≥10 cents off** (~2pp of implied
  probability).
- Combined: at a random action moment, roughly **30%** of the time the price we
  would decide on is materially not DK's price.

Against a 0.32 EV / 0.70 probability live cut, a 3-cent median is noise and a
10-cent tail is tolerable. **The wrong-line 11.8% is the part that is not.**

### One hypothesis, explicitly not yet a finding

The discrepancy is **not symmetric**: mean signed gap is **−10.1 cents on the
over** and **+14.9 on the under** (the aggregator's over price skews worse, its
under price better), with 90% of over gaps within +5 cents and a long negative
tail.

There is a mechanical candidate. Between scoring events an in-play total drifts
one way — outs pass scoreless, P(over) falls, DK's current over price improves
continuously — so a stale snapshot systematically shows a worse over and a
better under. A run scoring flips it violently, which would be the tail. If that
is right, **stale prices inflate under edges and deflate over edges, and the
phantom-edge moments cluster in the seconds after a run scores** — a selection
effect, not noise.

**This is one afternoon, and the means are tail-driven. It is a hypothesis.**
Conditioning the signed gap on whether a run scored in the prior ~60 s would
settle it, and that is the next query to run, not a conclusion to act on.

### 6.4 Found in passing: the loop went dark again overnight

Not what this collector was built to measure, and not fixed here.

- Last in-play row written: **2026-08-29 23:50:35 ET**.
- DK was still quoting **three live games until 01:07 ET** — recorded, so this
  is not inference.
- The aggregator wrote **nothing in-play for ~77 minutes of live baseball**, and
  nothing again until 12:00 ET the next day.

**RESOLVED 2026-08-30, and it was not a recurrence of #296.** It is the half of
that bug #296 did not fix.

A game carries the `game_date` of its FIRST PITCH. The three games were all West
Coast: PHI@LAA and ARI@SF started 22:06-22:08 ET, and their `game_date` is
`2026-08-29`. Both live loops resolved "which games do I poll?" as
`statsapi.schedule(date=today_et())` / `WHERE game_date = today_et()` — so at
00:00 ET the answer became `2026-08-30`, the in-progress games were no longer in
it, and the loop reported "no active games" and idled.

#296 moved the blind spot from 8pm ET to midnight ET. It did not remove it, and
it failed the same silent way: **"no active games" is also exactly what an empty
slate looks like**, which is why it ran ten nights the first time and at least
one more after the fix.

Fixed by `config.live_slate_dates()` — the ET dates whose games could still be
in progress, which is today plus yesterday in the early-morning window. Wired
into the MLB poller, the MLB live scorer and the NCAAF live loop, which had the
identical gap and plays more games across midnight ET than MLB does. The live
scorer also now announces every date it scored: both notifiers filter picks on
`game_date`, so scoring yesterday's late game while notifying only today would
have written a BET and never announced it.

### Standing position on DK direct

Unchanged, and the collector's own header says it: **DraftKings' terms forbid
automated access however the request is shaped.** This stays a measurement. Its
result argues we do not need it to become a feed — the coarseness is real but
its cost is bounded, and the mitigations already shipped.

---

## 7. Direct book feeds — what answers us, and from where (2026-08-31)

mike: *"build the dk direct live feed. explore if live feeds from other sports
books can work as well. multiple sources. how else would we get a live best
line, so lets get more sources."*

### The result that decides the architecture

`scripts/book_direct_probe.py`, run **on the Railway worker** (egress
`152.55.177.9`) with a Chrome 124 TLS fingerprint:

| book | from the worker | note |
|---|---|---|
| **bovada** | **200 OK — 756 KB** | public JSON coupon, no key. Parseable. |
| draftkings | **403 REFUSED** | works from a residential IP; see below |
| betmgm | 403 REFUSED | CDS API bot wall |
| pinnacle | 401 REFUSED | guest key rotated |
| williamhill_us | 403 REFUSED | americanwagering bot wall |
| espnbet | DNS failure | endpoint guess is wrong, not a refusal |
| fanduel | HTTP 500 | endpoint guess is wrong, not a refusal |

**#293's conclusion does not survive contact with a datacentre.** It found DK's
refusal was a TLS-fingerprint problem rather than an IP block — and that was
true, *from mike's home connection*, where the same code collected 6,214 quotes
over 16 hours without a single block. From Railway the identical request with
the identical fingerprint gets a 403.

So the axis is **residential vs datacentre**, not browser vs script. This is the
same thing that got `ufcstats`, `stats.nba.com` and `site.api.espn.com` blocked
on this project before, and it is why the probe prints its egress IP first: a
verdict here means "from this address".

### Confirmed with the exact configuration that works locally

The first probe ran WITHOUT the cookie bootstrap that mike's 16-hour collection
used, so it could not separate "this datacentre IP is blocked" from "we never
picked up a session". Re-run 2026-08-31 02:07 UTC with
`impersonate=chrome124 + cookie-bootstrap`, the identical configuration:

```
egress: 152.55.177.9
403  40ms  sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/84240
403  10ms  sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/84240
```

**10-40ms is an edge refusal, not a rate limit and not a session problem** — the
request never reached an application that could have asked for a cookie. The
same code, same fingerprint, same bootstrap, from a residential address, ran 16
hours and 6,214 quotes without a block. **The variable is the address.**

### What that means for the feed

`data/ingestors/dk_direct_feed.py` is built and tested, and it **cannot run on
the worker**. Its options, in the order they should be considered:

1. **Run it on mike's machine** — proven, free, and already how the 16-hour
   collection happened. The cost is that it is not always-on.
2. **A residential proxy** — makes the worker look residential. Real monthly
   cost, and it is the option that most obviously buys around a block.
3. **Bovada instead** — reachable from the worker today, no proxy, no
   impersonation. It is a different book from the one we decide on, so it does
   not replace DK; it is a second live source for the BEST LINE.

### The honest read on "more sources"

Four of the six non-DK books refuse the worker outright, and the two that did
not (`espnbet`, `fanduel`) failed on a stale URL guess rather than a refusal —
they are unknown, not open. **The multi-source live best line is one book wide
today: bovada.** That is worth having and is not what was hoped for.

The aggregator remains the only source that covers all seven books in play, and
§6 established what it costs: we see 29.7% of DK's line changes and are on the
wrong line 11.8% of the time. Direct feeds narrow that where they are reachable
and change nothing where they are not.

### The feed, when it runs

Rows land in `odds` as `bookmaker='draftkings'`, `snapshot_type='in_play'`,
`source='dk_direct'`. Same book, same vocabulary, so `_get_live_dk_odds` and
`_best_live_price` pick them up with no code change and §6's decide-on-DK
invariant is preserved rather than bent. `source` keeps the two feeds
distinguishable — without it the lag measurement that justified the work becomes
circular — and `DELETE FROM odds WHERE source='dk_direct'` is a complete undo.

`snapshot_at` means something different for these rows and that is deliberate:
DK's league feed carries no per-market publish stamp, so it is OUR clock at read
time. At 5s polling it clears the 30s gate by observation rather than by the
book's assertion.

**`RUN_DK_DIRECT_FEED` defaults to 0.** Turning it on changes what every live
MLB model prices against, which is a decision rather than a deploy.

---

## 8. Every book, from both addresses (2026-08-31)

mike: *"chase down espn bet, fanduel, mgm, wynn any others."*

The probe now runs from both places, because **the address is the variable** —
that is the whole finding of §7, proved end to end here: the identical request
gets **200 / 76 KB from a residential IP (67.189.160.146)** and **403 from the
Railway worker (152.55.177.9)**.

| book | from mike's machine | from the worker | verdict |
|---|---|---|---|
| **draftkings** | **200, 76 KB** | 403 | parseable; **residential only** |
| **bovada** | **200, 795 KB** | **200, 802 KB** | parseable **anywhere** — shipped |
| **betmgm** | 400 *"Access id is invalid"* | 403 | **reachable, needs a valid access id** |
| **betrivers** | 400 *"No cage configuration found for cageCode='849'"* | — | **reachable, needs a valid cage code** |
| pinnacle | 401 | 401 | refused; guest key rotated |
| williamhill_us | 403 | 403 | refused (Caesars bot wall) |
| espnbet | cert / DNS failure | DNS failure | endpoint unknown, not refused |
| fanduel | SSL failure / 500 | 500 | endpoint unknown, not refused |
| fanatics | 404 | — | stale guess |
| hardrock | 404 | — | stale guess |

### Reading a 400 as a lead, not a failure

**This is the change that produced the two new leads.** A 400 means the host
answered, applied its own logic, and told us *why* — which is the most
actionable outcome on the list and the easiest to file under "failed". So the
probe now prints the JSON error body, and the moment it did:

- BetMGM stopped looking like a bot wall and started looking like an **expired
  `x-bwin-accessid`**.
- BetRivers named the exact parameter it wanted.

Both are a correct parameter away from a 200, and neither was visible when the
column just said `HTTP 400`.

### WynnBET: nothing to probe

Asked for, and the honest answer is that the brand is gone from US sports
betting. It closed its sportsbook in eight or nine of twelve markets in August
2023 and exited its last major market, New York, in August 2024, citing
customer-acquisition cost. There is no live line to shop there, so no endpoint
was guessed for it.

### The lead worth measuring next: DK's live line via ESPN

ESPN's own public core API republishes DraftKings under **two** providers:

```
id=100  DraftKings              (pre-game)   CHC -150   ou 9.5
id=200  DraftKings - Live Odds  (in-play)    CIN -2900  ou 11.5
```

Verified 2026-08-31 on a live CIN@CHC in the bottom of the 9th, and the live
total of 11.5 matches what bovada was showing for the same game at the same
moment. ESPN answers a datacentre without impersonation.

**If it is fresh enough, it is a route to DK's live number from Railway** —
which is the exact blocker §7 ran into. It is NOT yet that, because ESPN is
itself an aggregator of DK and may be as coarse as The Odds API. That is a
measurement, not an assumption, and it is the same one §6 already has a method
for: record ESPN's provider-200 line beside DK direct's for one slate and
compare first-seen times.

Note also that ESPN has IP-blocked this worker twice before (sessions 112, 115),
so anything built on it needs a cadence chosen with that in mind.
