# Live monitor — API traffic and picks, as they happen

`monitoring/` is a real-time console for the pipeline: every outbound API call
as it is made, every pick as it is written, the credit burn, the last few
passes, and the health checks — on one screen that updates about once a second.

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

If you add a panel, `EXPLAIN (ANALYZE, BUFFERS)` it first. A seq scan here is
multiplied by the poll rate.

## Switches

| Variable | Effect |
|---|---|
| `MONITOR_TOKEN` | Required to bind anything but loopback. |
| `RUN_MONITOR=0` | Worker starts without the dashboard thread. |
| `PIPELINE_TELEMETRY=0` | Stops recording everywhere (the probe never installs). |
| `API_LOG_RETENTION_DAYS` | Prune horizon, default 7. |
| `API_LOG_FLUSH_SEC` | Writer flush interval, default 0.75. |
| `MONITOR_POLL_SEC` | Stream poll interval, default 1.0. |

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

A real-time console for the pipeline: every outbound API call as it happens,
every pick as it is written, credit burn, recent passes, health. Full runbook in
**`docs/monitoring.md`**; ops entries in `docs/cloud_worker.md` and
`docs/local_ops.md`.

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

**Switches:** `MONITOR_TOKEN` (required to bind publicly), `RUN_MONITOR=0` (no
dashboard), `PIPELINE_TELEMETRY=0` (no recording anywhere).

**Chart colors** are the dataviz reference instance: series blue `#3987e5` and
the reserved status palette only, validated all-pairs against the dark surface
(worst CVD ΔE 25.7, normal-vision 31.9, both ≥3:1).

---
