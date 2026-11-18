# Test suite

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> Pull requests run a **non-integration** pytest subset via
> `.github/workflows/pr-ci.yml` (smoke + lock/settle/freshness/leakage +
> threshold-parity). No live Odds API, no prod DB. Full suite:
> `python -m pytest -q tests/` by hand before merging risky changes.

## 14. Tests
A pytest test suite lives in `tests/`. Run after models are trained (earlier tests are
less useful since pure function tests don't need data, but integration is more meaningful
with a populated DB).

```bash
# Install once: pytest, a pip-packaged node for the tests that run the app's
# TypeScript (tests/_node.py), and a pip-packaged Postgres for the two files
# that drive real triggers on a throwaway cluster (tests/_pg.py). System
# installs are used first when present.
python -m pip install -r requirements-test.txt

# Once more, for the app's own verify scripts (they need mobile/node_modules):
# scripts/npm.py runs npm through the pip node when there is no system npm.
cd mobile && python ../scripts/npm.py ci --no-audit --no-fund && cd ..

# Run all tests
python -m pytest tests/ -v

# Run a single file
python -m pytest tests/test_scorer.py -v
```

**Coverage:**

| File | What it tests |
|------|--------------|
| `test_config.py` | Model registry, SPORTS config, threshold constants |
| `test_db_setup.py` | Schema creates all 11 tables, idempotency, column presence |
| `test_sbr_loader.py` | Team name normalization, odds parsing, date parsing, DB insert |
| `test_feature_engine.py` | Injury adjustment, starter-out detection, target computation |
| `test_scorer.py` | Implied prob conversion, Tenth-Kelly sizing, signal classification |
| `test_backtester.py` | Calibration error, P&L evaluation, go-live gate logic |

Tests are pure function tests — no external APIs, no SBR files needed. DB tests use
in-memory SQLite (via `conftest.py` fixture).

**What `tests/conftest.py` refuses or stubs, so no test reaches a real service.**
`data/db.py` loads the checkout's `.env`, which in the main checkout names the
production database, so a test that reaches a real connection would be talking
to production.

- **The Odds API**: a real request fails, so no test can bill credits.
- **A database not on this machine** (`tests/_db_guard.py`, 2026-11-18, #1396):
  `psycopg2.connect` to any host but `localhost`, a loopback address or a local
  socket fails at once without dialling. The end of every run prints how many
  were refused and from which tests; that count should be 0. The scratch
  Postgres in `tests/_pg.py` is on 127.0.0.1 and gets through. A child process
  a test starts is not guarded.
- **Heartbeats** (#1455, #1456): `tracking.job_heartbeat.beat` is stubbed for
  every test. Building the scheduler calls it 32 times, and each call opened a
  connection: a heartbeat row in production from the main checkout, or a 4.1 s
  refused connect to localhost with no `.env`. A test of the heartbeat itself
  is marked `@pytest.mark.real_heartbeat`.
- **The scorer's leftover auto-pause list** (#1396): held empty for every test.
  The scorer reads it once per process, so the first test in a run to score a
  pick opened a connection for it, whichever test that was.
- `tests/test_no_test_reaches_a_database.py` fails if building the scheduler
  or the pause check opens a connection, or if the guard lets a remote host
  through.

---
