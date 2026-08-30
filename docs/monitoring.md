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
