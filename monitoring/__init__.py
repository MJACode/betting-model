"""Real-time monitoring for the betting pipeline.

Three pieces, deliberately decoupled so a failure in any of them can never
touch the pipeline:

  probe.py     a single global patch of requests.Session.request that records
               EVERY outbound HTTP call the process makes (including calls made
               inside third-party libs: statsapi, nba_api, cloudscraper, ...).
  store.py     the api_call_log table + the read queries the dashboard runs.
  server.py    a stdlib HTTP server exposing the dashboard, a JSON snapshot and
               an SSE event stream that tails the database.

Run the viewer locally:      python -m monitoring
It also runs inside the Railway worker as a daemon thread (see scheduler.py).
"""
