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

403 in 37–41ms returning 449 bytes is an edge/WAF refusal, not a rate limit —
the datacenter-IP block that already took out `ufcstats`, `stats.nba.com` and
`site.api.espn.com`.

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

### Explicitly rejected

- **Residential proxy networks** (Bright Data, Oxylabs and similar). Purpose-built
  to defeat exactly the block DK has put up. That is circumvention, not access.
- **Browser impersonation** — cookies, `sec-ch-*` headers, headless Chrome. Same
  thing wearing a different hat. A 403 is a refusal; working around it is not a
  technical problem to be solved.
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
