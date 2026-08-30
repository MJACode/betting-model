# Test suite

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> There is no CI on pull requests. Run `python -m pytest -q tests/` by hand
> before merging.

## 14. Tests
A pytest test suite lives in `tests/`. Run after models are trained (earlier tests are
less useful since pure function tests don't need data, but integration is more meaningful
with a populated DB).

```bash
# Install once
python -m pip install "pytest>=8.0.0"

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

---
