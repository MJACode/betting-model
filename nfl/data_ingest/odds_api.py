"""
The Odds API historical snapshot fetcher.

Design notes:
  * Every snapshot is cached to disk keyed by (date, regions, markets). A cache hit
    costs zero credits. Re-running the backfill is therefore free.
  * A credit ledger is persisted so we always know spend vs. the 20k quota.
  * Cost model (confirmed empirically): 10 credits x n_markets x n_regions per call.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests

API_ROOT = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "odds_cache"
LEDGER = Path(__file__).resolve().parents[1] / "data" / "credit_ledger.json"


def _key(date: str, regions: str, markets: str) -> str:
    raw = f"{date}|{regions}|{markets}"
    return hashlib.md5(raw.encode()).hexdigest()


_LEDGER_LOCK = threading.Lock()


def _ledger_read() -> dict:
    """Tolerant read: a torn write must never crash a backfill mid-run."""
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text())
        except (json.JSONDecodeError, OSError):
            return {"spent": 0, "calls": 0, "remaining": None}
    return {"spent": 0, "calls": 0, "remaining": None}


def _ledger_write(d: dict) -> None:
    """
    Atomic write via temp file + rename.

    On Windows `os.replace` raises PermissionError if anything else holds a
    handle on either file for an instant - an indexer or a virus scanner is
    enough. That killed a 55,000-credit scan on its last call, after every
    payload was already safely cached, purely because bookkeeping failed. The
    ledger is bookkeeping: retry briefly, then give up and keep going rather
    than take the caller down with it.
    """
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2))
    for attempt in range(8):
        try:
            os.replace(tmp, LEDGER)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    print(f"WARNING: could not update {LEDGER.name}; spend is still on the API side",
          file=sys.stderr)


def _ledger_bump(cost: int, remaining) -> None:
    with _LEDGER_LOCK:
        led = _ledger_read()
        led["spent"] = led.get("spent", 0) + cost
        led["calls"] = led.get("calls", 0) + 1
        if remaining is not None:
            led["remaining"] = int(float(remaining))
        _ledger_write(led)


@dataclass
class SnapshotResult:
    date: str
    regions: str
    markets: str
    payload: dict
    from_cache: bool
    cost: int


class OddsAPIClient:
    def __init__(self, api_key: str, quota_guard: int = 300):
        """quota_guard: refuse to spend below this many remaining credits."""
        self.api_key = api_key
        self.quota_guard = quota_guard
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def cost_of(self, regions: str, markets: str) -> int:
        return 10 * len(markets.split(",")) * len(regions.split(","))

    def historical_odds(
        self,
        date: str,
        regions: str = "us",
        markets: str = "spreads",
        odds_format: str = "american",
        max_retries: int = 4,
    ) -> SnapshotResult:
        k = _key(date, regions, markets)
        cache_path = CACHE_DIR / f"{k}.json"

        if cache_path.exists():
            return SnapshotResult(
                date, regions, markets, json.loads(cache_path.read_text()), True, 0
            )

        led = _ledger_read()
        if led.get("remaining") is not None and led["remaining"] < self.quota_guard:
            raise RuntimeError(
                f"Quota guard tripped: {led['remaining']} credits remaining, "
                f"guard set at {self.quota_guard}. Aborting before spend."
            )

        url = f"{API_ROOT}/historical/sports/{SPORT}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "date": date,
        }

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params, timeout=45)
                if r.status_code == 200:
                    payload = r.json()
                    cache_path.write_text(json.dumps(payload))
                    cost = self.cost_of(regions, markets)
                    _ledger_bump(cost, r.headers.get("x-requests-remaining"))
                    return SnapshotResult(date, regions, markets, payload, False, cost)

                if r.status_code == 422:
                    # Out of historical range or malformed date. Cache an empty
                    # payload so we never re-spend on it.
                    payload = {"timestamp": None, "data": [], "_error": r.text[:300]}
                    cache_path.write_text(json.dumps(payload))
                    return SnapshotResult(date, regions, markets, payload, False, 0)

                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    last_err = f"{r.status_code}: {r.text[:200]}"
                    continue

                raise RuntimeError(f"Odds API {r.status_code}: {r.text[:300]}")

            except requests.RequestException as e:  # network flake
                last_err = str(e)
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed after {max_retries} retries: {last_err}")

    def live_odds(
        self,
        regions: str = "us",
        markets: str = "totals",
        odds_format: str = "american",
        max_retries: int = 4,
    ) -> SnapshotResult:
        """
        Current odds for upcoming games. Used by the weekly bet pipeline.

        NEVER cached. A cached live line is a wrong line, and the whole point
        of betting late is acting on the number that is actually up.

        Cost is 1 credit per market per region, not 10 as for historical, so a
        weekly run at regions=us,markets=totals costs 1 credit.
        """
        led = _ledger_read()
        if led.get("remaining") is not None and led["remaining"] < self.quota_guard:
            raise RuntimeError(
                f"Quota guard tripped: {led['remaining']} credits remaining, "
                f"guard set at {self.quota_guard}. Aborting before spend."
            )

        url = f"{API_ROOT}/sports/{SPORT}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params, timeout=45)
                if r.status_code == 200:
                    # live endpoint returns a bare list; wrap it to match the
                    # historical payload shape so parse.py handles both.
                    payload = {"timestamp": None, "data": r.json()}
                    cost = len(markets.split(",")) * len(regions.split(","))
                    _ledger_bump(cost, r.headers.get("x-requests-remaining"))
                    return SnapshotResult("live", regions, markets, payload, False, cost)

                if r.status_code in (429, 500, 502, 503, 504):
                    last_err = f"{r.status_code}: {r.text[:200]}"
                    time.sleep(2 ** attempt)
                    continue

                raise RuntimeError(f"Odds API {r.status_code}: {r.text[:300]}")

            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed after {max_retries} retries: {last_err}")


def ledger_status() -> dict:
    return _ledger_read()
