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
Matt's machine and writes to Supabase (§19, §23). DK's block is the same shape,
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
