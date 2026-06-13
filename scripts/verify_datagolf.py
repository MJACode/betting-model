"""
scripts/verify_datagolf.py — Phase 0 DataGolf verification spike.

Run this ONCE after subscribing to DataGolf Scratch Plus and setting
DATAGOLF_API_KEY in your .env. It is read-only (no DB writes) — it hits each
endpoint the golf pipeline depends on and prints the JSON shape so we can confirm
the field names the parsers in data/ingestors/datagolf_ingestor.py assume.

It also probes the historical-odds archive endpoints to determine whether your
tier can back-fill closing DK prices (real-odds backtests) or whether the
backtester must fall back to synthetic odds.

Usage:
    python -m scripts.verify_datagolf

Paste the output back into the chat so the parsers/fixtures can be corrected if
DataGolf's shapes differ from the documented assumptions.
"""
import json
import sys

import requests

import config


def _get(path: str, **params):
    params.setdefault("file_format", "json")
    params["key"] = config.DATAGOLF_API_KEY
    url = f"{config.DATAGOLF_BASE_URL}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=30)
    return resp


def _preview(label: str, path: str, **params):
    print("\n" + "=" * 78)
    print(f"# {label}  →  GET /{path}  {params}")
    print("=" * 78)
    try:
        resp = _get(path, **params)
        print(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:500])
            return
        data = resp.json()
        if isinstance(data, list):
            print(f"(list of {len(data)}) first element keys:")
            if data:
                print(json.dumps(data[0], indent=2)[:1500])
        elif isinstance(data, dict):
            print("top-level keys:", list(data.keys()))
            # print the first element of the largest list value
            for k, v in data.items():
                if isinstance(v, list) and v:
                    print(f"\nfirst element of '{k}' (list of {len(v)}):")
                    print(json.dumps(v[0], indent=2)[:1500])
                    break
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")


def main():
    if not config.DATAGOLF_API_KEY:
        print("DATAGOLF_API_KEY is not set. Add it to your .env first.")
        sys.exit(1)

    _preview("Player list", "get-player-list")
    _preview("Event list (history)", "historical-raw-data/event-list")
    _preview("Current schedule", "get-schedule", tour="pga")
    _preview("Field updates", "field-updates", tour="pga")
    _preview("Rankings", "preds/get-dg-rankings")
    # a known recent event — adjust event_id/year if needed after seeing event-list
    _preview("Historical rounds (sample)", "historical-raw-data/rounds",
             tour="pga", event_id=26, year=2024)
    for mkt in ("win", "top_10", "top_20", "make_cut"):
        _preview(f"Live outrights ({mkt})", "betting-tools/outrights",
                 tour="pga", market=mkt, odds_format="american")
    _preview("Live matchups", "betting-tools/matchups",
             tour="pga", market="tournament_matchups", odds_format="american")
    # archive probes — determine whether real-odds backtests are possible
    _preview("ARCHIVE: historical outright odds", "historical-odds/outrights",
             tour="pga", event_id=26, year=2024, market="win", odds_format="american")
    _preview("ARCHIVE: historical matchup odds", "historical-odds/matchups",
             tour="pga", event_id=26, year=2024, odds_format="american")

    print("\n" + "=" * 78)
    print("Done. Paste this output back so parser field names can be confirmed.")
    print("=" * 78)


if __name__ == "__main__":
    main()
