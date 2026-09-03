# Live monitor — API traffic and picks, as they happen

`monitoring/` is the operational console for the platform. It has three views:

* **Live** — every outbound API call as it is made, every pick as it is written,
  the credit burn, the last few passes, the health checks. Updates ~1s.
* **Models** — what is registered, what is live vs paused vs untrained, the
  settled record and ROI per model, and picks/signals per model over time.
* **Ops** — audience size (subscribers, app devices, Discord), pipeline runs
  and health in one place.

**Models and Ops are also ported to Retool** (2026-08-31), reading the same
Supabase directly over the `supabase` PostgreSQL resource:
<https://signalbaseskinny--betting-model-models-ops.retool.app>. **Live stays
here and only here** — it streams over SSE at 1-2s latency, and "is the pipeline
running right now" is exactly the question a polling dashboard cannot answer.
The Retool port carries the same three invariants this file documents: it reads
`mv_scored_pick_outcomes` and never `v_model_full_outcome_record`, it computes
ROI over the priced subset with the coverage shown beside it, and it bounds the
picks series on the indexed `game_date`. See the 2026-08-31 session entry for
the three places the port's brief disagreed with production.

A third tab, **Picks & CLV** (2026-09-03), lists every BET pick with the price it
fired at, the closing price, and its CLV, plus a units rollup and charts. It
READS the CLV columns `picks` already carries (`closing_dk_odds`, `closing_line`,
`clv_pct`, `line_clv_pts`, `clv_beat_close`, `clv_captured_at`) — it never
recomputes them, because `tracking/paper_tracker.py::_capture_clv` is where the
same-line, pre-game and DK-only guards live.

**Two rules that tab exists to enforce, and that any future CLV surface inherits:**

* **The CLV split is three-way, never two.** 1,489 of 2,240 measured bets have
  CLV of exactly zero — the line and the price both held. Folding those into
  "did not beat" reports a two-thirds-flat book as a two-thirds-losing one. Show
  BEAT / FLAT / WORSE, and quote both rates with denominators: 22.4% of all
  measured, 66.8% of the 751 that actually moved.
* **`picks.result` has five values, not three.** `NO_ACTION` (a voided bet) and
  NULL (unsettled) sit alongside WIN/LOSS/PUSH. A void never stood, so it belongs
  in neither the record nor the ROI denominator — counting the 57 of them as
  risked stakes moved reported ROI from -5.24% to -5.29%. Units and ROI gate on
  `result IN ('WIN','LOSS','PUSH') AND profit_units IS NOT NULL`.

**Two things that look like gaps and are not, measured 2026-09-03:**

* **"Un-captured CLV" is the wrong denominator.** 1,444 pre-game BET picks have
  no close, but 1,161 of them were stamped AFTER their own first pitch and 276
  never had a `dk_odds` to compare — both permanently unmeasurable by design.
  Only 3 are genuinely eligible and uncaptured, so CLV coverage of *capturable*
  picks is ~99.7% and `_backfill_clv` has converged. Judge it on capturable
  picks, never on the raw un-captured count.
* **`mv_scored_pick_outcomes` excludes live picks twice** — `p.is_live IS NOT
  TRUE` in its base WHERE, and no `*_live_*` model in its allow-list. Since
  `profit_units` exists ONLY in that matview, every surface built on it reports
  zero live units even though 525 live bets are settled. The live record lives in
  `picks` (`profit_flat = profit_units x 100`): **287-238-0, -52.58u, -10.01%** —
  -12.91% for pre-game prop models fired in-play, -1.13% for the dedicated
  `*_live_*` models. Read live P&L from `picks`, not from the matview.
* The matview also has **no `NO_ACTION` concept** — it regrades from box scores,
  so four voided WNBA props are counted as real bets by anything reading its own
  `result` column.

It exists because **an absence is the pipeline's normal failure mode.** The
Odds API quota died on 2026-08-14 and the only symptom for 2.5 days was
"no MLB picks". ESPN 403'd the worker for two weeks and WNBA settlement simply
stopped. A `NameError` killed every hourly pass for three days behind a green
health check. In every case the traffic was gone long before the data was, and
nothing was watching the traffic.

---

## Reaching it

**On the worker (phone-friendly).** The dashboard runs as a daemon thread inside
`scheduler.py`. It needs two things in Railway:

| Variable | Value | Why |
|---|---|---|
| `MONITOR_TOKEN` | a long random string | Required. Without it the server binds loopback only and is unreachable — deliberately, since the dashboard exposes pipeline internals. |
| `PORT` | set by Railway when the service has a domain | The server falls back to 8080. |

Then Railway → the `worker` service → Settings → Networking → **Generate Domain**.
Open `https://<domain>/?token=<MONITOR_TOKEN>` and bookmark it.

**Locally.** Same code, same Supabase, no worker needed:

```bash
python -m monitoring          # opens http://127.0.0.1:8787/
```

Loopback-only and unauthenticated by default — set `MONITOR_TOKEN` locally only
if you want to bind an address other than `127.0.0.1`.

---

## How a call gets on the screen

```
requests.get(...)  ->  probe patch  ->  in-memory queue  ->  writer thread
                                                                 |  every 0.75s
                                                            api_call_log
                                                                 |  polled every 1s
                                                            SSE  ->  dashboard
```

End-to-end latency is ~1–2s.

**The probe is one patch, not 75 call-site edits.** `monitoring/probe.py`
wraps `requests.sessions.Session.request` once, which catches every ingestor
*and* the calls made inside libraries we do not own — MLB-StatsAPI, nba_api,
pybaseball, cloudscraper. `curl_cffi` is patched separately because it is a
different HTTP stack (browser TLS fingerprint) that a requests patch cannot
reach. A new ingestor is covered the day it is written.

**It goes through the database on purpose.** The scheduler shells out for every
pass, so the process making the calls is never the process serving the
dashboard. The database is the only place they meet — and it is also what makes
the local viewer show the worker's traffic, and what makes history survive a
redeploy.

**Three rules the probe lives by**, each with a test:
1. It never changes what a call returns and never raises into a caller.
2. It never makes a call slower — recording is a bounded queue and a daemon
   thread; nothing touches the database on the request path.
3. **It never persists a credential.** The query string is dropped except for an
   allowlist of descriptive params (`markets`, `regions`, `sport`, …), so
   `apiKey` cannot be stored even on a host nobody has thought about yet.
   Error text is scrubbed too — `requests` embeds the full URL, key and all, in
   its exception messages, which is a second and far easier-to-miss path to the
   same secret.

---

## Reading the screen

| Tile | What it means |
|---|---|
| **calls / min** | Outbound calls in the last 60s. Zero during a slate is the alarm. |
| **error rate** | Share of the last 5 minutes that failed. A wall of 403s (ESPN, DK) shows here first. |
| **p95 latency** | Skewed by CFBD (~1.5s) by design; watch the shape, not the number. |
| **odds credits** | `x-requests-remaining` plus day-over-day burn. |
| **signals 24h** | BET picks vs everything scored — the dead-zone rows are the denominator. |
| **last pass** | From `pipeline_runs`. "running" for more than a few minutes is a hang. |
| **health** | Unresolved CRIT/WARN from the latest `system_health_checks` run. |

The **Traffic** chart stacks OK (blue) against errors (red) per bucket; `Table`
swaps it for the same numbers as text. **By API** is the panel that answers "did
this feed stop?" — it carries per-API counts, errors, p95 and time since the
last call. **Picks** streams new rows as the scorer writes them, BET marked
green. Space bar freezes the feed.

---

## Models

**Performance** is the settled BET record per model — W-L-P, units, ROI, and
the date of the last settled pick. Two things about the numbers matter more
than the table:

* It reads **`mv_scored_pick_outcomes`**, not `v_model_full_outcome_record`.
  The view re-grades every pick against the current thresholds and costs
  1,596ms / 568k buffer hits; it cannot sit behind a dashboard at any poll
  rate. The matview is the same grading, materialised, at 285ms. It is
  refreshed by `--step refresh-outcomes` right after settle, so it is at most
  a day stale — which is also how often a settled record changes.
* **ROI is over the PRICED subset**, and the count is shown beside it. A
  prob-only pick with no real DK price has `profit_units` NULL, so
  `mlb_prop_batter_hr` reads "20 of 252 priced" in amber: its 42-210 record is
  real and its ROI describes a twentieth of it. Fabricating −110 for the rest
  is exactly how a record-only model grows invented P&L.

**Roster** is every row in `model_action_thresholds` — the authority on whether
a model FIRES, since it is what the app's action filter reads and what the
daily pipeline syncs from `config.py`. Each row is joined to its active
`model_registry` artifact, so a model that is registered but has **no trained
artifact** (the NHL totals/puckline pair, the golf models) shows up as a state
rather than being discovered at score time. The header counts live / paused /
no-artifact.

**Picks per model over time** charts the last 14 days from `picks`, one series
per model as a sparkline plus a slate-level total. It excludes live picks —
they churn every pass and would swamp the pre-game board they sit beside.

## Ops

Audience counters, all from tables the pipeline already writes:

| Tile | Source | Note |
|---|---|---|
| Subscribers | `subscriptions` | **0 today by design** — billing ships dark (`BILLING_ENABLED` defaults false, §122). Lights up on its own when it turns on. |
| Discord members / online | Discord API | Needs a bot token — see below. |
| Discord posts | `push_sent` where kind starts `discord` | Delivered posts, i.e. reach. This one works today. |
| Push devices | `device_push_tokens` | 0 until the native push build is made (§26). |
| Linked books | `linked_sportsbook_accounts` | SharpSports links. |
| Open feedback | `feedback_threads` | Threads not closed (§126c). |

### Discord member counts need a bot, not a webhook

An **incoming webhook is write-only.** It can post to a channel; it cannot see
who is in the server. There is no way around this — the only endpoint that
returns a member count is `GET /guilds/{id}?with_counts=true`, and that needs a
bot token. Until one is set the tile says so instead of showing a number.

To turn it on:

1. https://discord.com/developers/applications → **New Application** → Bot →
   **Reset Token** → copy it.
2. OAuth2 → URL Generator → scope `bot` (no permissions needed, and **no
   privileged intents** — this call only requires membership) → open the URL and
   add it to the server.
3. Discord → User Settings → Advanced → **Developer Mode** on, then right-click
   the server → **Copy Server ID**.
4. Railway → `worker` → Variables: `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`.

The response gives `approximate_member_count` and `approximate_presence_count`
(online now). Failures are reported distinctly — 401 bad token, 403 bot not in
the guild, 404 wrong id, 429 rate-limited — because "no number" has four very
different fixes.

---

## Why the operational panels are cached

The live panels tail an index and are cheap. These are not: the performance
query reads a 132k-row matview and the time series scans two weeks of `picks`.
Both sit behind `monitoring/cache.py`, a module-level TTL cache, which makes
their cost independent of two things at once:

* **viewer count** — five people watching share one entry;
* **poll rate** — the meta tick stays at 10s while a 300s panel actually hits
  the database twelve times an hour.

TTLs: roster 60s, time series 120s, performance 300s, community 300s, Discord
600s. Every cached panel ships its own `age_s` and the UI renders it, so a
five-minute-old ROI says it is five minutes old rather than implying "now". On
a refresh failure the **stale value is served**: a slightly old number beats an
empty panel because the pooler dropped a connection.

---

## Cost and retention

`api_call_log` grows by roughly 25k rows/day (the 5s live loops dominate). The
writer prunes rows older than `API_LOG_RETENTION_DAYS` (default 7) at most once
an hour, which holds the working set near 175k rows. It is internal-only: RLS
on, no policy, `anon`/`authenticated` revoked by name.

## Database cost

Every query the dashboard runs is index-served, which matters because they run
on a 1s (stream) / 10s (meta) loop per viewer. `pick_counts` is the one that
needed care: `picks.created_at` is TEXT, so the timestamptz cast cannot use an
index and the filter alone was a 679ms parallel seq scan. It carries a
`game_date` lower bound (indexed; a pick written today never belongs to a slate
older than yesterday, and there is deliberately no upper bound because NFL and
golf picks are written days ahead) — 13ms, zero disk reads, identical rows.

The operational queries were measured the same way: roster 0.6ms, performance
285ms, time series ~60ms. The two expensive ones are cached (above) rather than
optimised further — a settled record genuinely only changes once a day.

If you add a panel, `EXPLAIN (ANALYZE, BUFFERS)` it first. A seq scan here is
multiplied by the poll rate — and if it costs more than ~50ms, put it behind a
TTL rather than behind the meta tick.

## Switches

| Variable | Effect |
|---|---|
| `MONITOR_TOKEN` | Required to bind anything but loopback. |
| `RUN_MONITOR=0` | Worker starts without the dashboard thread. |
| `PIPELINE_TELEMETRY=0` | Stops recording everywhere (the probe never installs). |
| `API_LOG_RETENTION_DAYS` | Prune horizon, default 7. |
| `API_LOG_FLUSH_SEC` | Writer flush interval, default 0.75. |
| `MONITOR_POLL_SEC` | Stream poll interval, default 1.0. |
| `DISCORD_BOT_TOKEN` | Enables the Discord member/online tiles (with the guild id). |
| `DISCORD_GUILD_ID` | The server id. Both are needed; neither is used for posting. |

Nothing here can break the pipeline: the probe swallows its own exceptions, the
writer drops a batch rather than retrying into a backlog, and the server is
started inside a `try` that logs and moves on.

## Known gap

A call made by a process that never imports `monitoring` is invisible. The four
entrypoints are wired (`scheduler.py`, `run_pipeline.py`, the live orchestrator,
both live gameday loops); a one-off script run by hand is not, unless it goes
through `run_pipeline.py`.


---

## Design notes and invariants

> Moved from CLAUDE.md `docs/monitoring.md` on 2026-08-30. Overlaps the sections above in
> places; kept because it states the invariants and the reasoning behind them.

Three views on one page. **Live**: every outbound API call as it happens, every
pick as it is written, credit burn, recent passes, health. **Models**: registry
state (live / paused / registered-but-untrained), settled record + ROI per
model, picks and signals per model over 14 days. **Ops**: subscribers, Discord,
push devices, linked books, open feedback. Ops entries in `docs/cloud_worker.md`
and `docs/local_ops.md`.

**Why it exists.** Every incident in this repo's history announced itself as an
ABSENCE — no MLB picks (Odds API quota, 2026-08-14), no WNBA settlement (ESPN
403, two weeks), no signals at all (a `NameError` behind a green health check,
three days). The traffic stopped long before the data did, and nothing watched
the traffic.

**Coverage is one patch, not 75 call-site edits.** `monitoring/probe.install()`
wraps `requests.sessions.Session.request` once, which catches every ingestor
*and* the libraries we do not own (MLB-StatsAPI, nba_api, pybaseball,
cloudscraper — the last is a Session subclass whose `request` calls `super()`,
so it counts once). `curl_cffi` is patched separately: it is a different HTTP
stack (browser TLS fingerprint) that a requests patch cannot reach, and the DK
freshness collector uses it. Installed at four entrypoints — `scheduler.py`,
`run_pipeline.py`, `live_trigger_orchestrator.py`, both live gameday loops. A
script run by hand outside those is invisible.

**It rendezvouses through the database on purpose.** The scheduler shells out
for every pass, so the process making the calls is never the process serving the
dashboard. That is also what makes the local viewer show the worker's traffic
and history survive a redeploy. Probe flush 0.75s + stream poll 1s ≈ 1–2s
end-to-end.

**Load-bearing rules (each has a test):**
- The probe never changes a response, never raises into a caller, and never
  touches the DB on the request path (bounded queue + daemon thread; on overflow
  it drops the OLDEST record, because during an incident the recent calls are
  the ones worth having).
- **No credential is ever persisted.** The query string is dropped except for an
  allowlist of descriptive params, so `apiKey` cannot land in `path` even on a
  host nobody has thought about. Error text is scrubbed too — `requests` embeds
  the full URL, key and all, in its exception messages. That second path was
  found by a test asserting no key appears anywhere in a recorded row, not by
  reading the code.
- **`server.build_server` refuses any non-loopback bind without `MONITOR_TOKEN`.**
  The dashboard exposes pipeline internals and a Railway domain is public.
- `api_call_log` is created at runtime by its own module (`store.ensure_table`),
  like `pipeline_runs` — the Supabase MCP is read-only and `setup_database()`
  only runs at first-time setup. RLS on, no policy, anon/authenticated REVOKEd
  BY NAME (a PUBLIC-only revoke is a no-op under Supabase's default privileges).
- Retention is not optional: ~25k rows/day, pruned to `API_LOG_RETENTION_DAYS`
  (7) by the writer, at most hourly.
- **Every dashboard query is index-served**, because they run on a 1s/10s loop
  per viewer. The one that wasn't — `pick_counts`, filtering on `picks.created_at`
  (TEXT, so the timestamptz cast is unindexable) — was a 679ms parallel seq scan
  with ~3.5k disk reads, the same pattern #291 had just fixed. A `game_date`
  lower bound (indexed, and a pick written today never belongs to a slate older
  than yesterday) takes it to **13ms and zero reads**, identical rows.

**The operational panels are cached, and that is a cost decision.** Performance
reads a 132k-row matview (285ms) and the time series scans two weeks of `picks`;
both sit behind a module-level TTL cache (`monitoring/cache.py`) so their cost is
independent of BOTH viewer count and poll rate — the meta tick stays at 10s while
a 300s panel hits the DB twelve times an hour. Stale is served on a refresh
failure, and every cached panel ships its `age_s` so the UI states its age rather
than implying "now".

**Two model-record conventions that must not drift:**
- Performance reads **`mv_scored_pick_outcomes`, never `v_model_full_outcome_record`**
  (the view re-grades against current thresholds at 1,596ms / 568k buffer hits —
  unservable behind a poll loop; the matview is the same grading, materialised,
  refreshed by `--step refresh-outcomes` after settle).
- **ROI is over the PRICED subset only**, with the count shown beside it. A
  prob-only pick with no DK price has NULL `profit_units`, so `mlb_prop_batter_hr`
  reads "20 of 252 priced" — the record-only rule (`docs/thresholds.md`), enforced
  in the UI rather than by inventing −110.

**Discord member counts need a BOT TOKEN, not a webhook.** An incoming webhook is
write-only and cannot read membership; only `GET /guilds/{id}?with_counts=true`
returns a count. Two tiles read 0 by design rather than by fault: subscribers
(billing ships dark) and push devices (the native push build was never made).

**Switches:** `MONITOR_TOKEN` (required to bind publicly), `RUN_MONITOR=0` (no
dashboard), `PIPELINE_TELEMETRY=0` (no recording anywhere).

**Chart colors** are the dataviz reference instance: series blue `#3987e5` and
the reserved status palette only, validated all-pairs against the dark surface
(worst CVD ΔE 25.7, normal-vision 31.9, both ≥3:1).

---


---

## Live tuning (Models view)

One row per live model: the cutoff in force, what it is projected to cost per
week against its ceiling, the record it has actually produced, and the
calibration gap between what the model claims and what it delivers. Under each
row, the verdict from `tracking/live_calibration.py` — including the refusals
("not enough data", "no profitable cut", "nothing fits the ceiling").

Colour is deliberate and narrow:

- **bets/week goes red when it is over the model's `LIVE_MAX_BETS_PER_WEEK`** —
  volume over the ceiling is the thing this panel exists to surface.
- **ROI is grey below 12 settled bets**, whatever its sign. A 3-bet sample is a
  number, not a result, and colouring it green invites acting on it.
- **The calibration gap is red past 8pp**, amber past 4. A model claiming 70%
  and winning 56% cannot be fixed by moving a threshold.

The panel reads the `live_calibration` table, which the pipeline step writes; it
never recomputes on a dashboard tick. Empty state until the first run.
