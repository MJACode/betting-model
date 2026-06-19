"""
scripts/verify_kalshi.py — P3 prediction-markets verification spike (Kalshi).

Read-only. Hits Kalshi's public market-data endpoints and prints the JSON shape
so we can decide whether their event contracts are an exploitable, limit-resistant
edge source before building any ingestor. See docs/prediction_markets_eval.md for
the decision framing.

What it checks:
  1. /events            — can we browse event contracts without a key?
  2. /markets           — market shape: ticker, yes/no bid/ask (cents), volume
  3. sports coverage    — are there game-level sports markets we already model?
  4. price → probability — Kalshi prices are cents (0–100) ≈ implied probability,
                           so edge = our model_prob − (price/100), same math as DK.

Usage:
    python -m scripts.verify_kalshi            # public market data (no key)
    KALSHI_API_KEY=... python -m scripts.verify_kalshi   # if a key is needed

Paste the output back into the chat. If the shapes look workable AND there's a
recurring price gap vs our model on games we cover, the next step is a
data/ingestors/kalshi_odds_ingestor.py mirroring odds_ingestor.py (edge vs our
calibrated prob, a "also on Kalshi" hand-off). Otherwise we keep monitoring.
"""
import json
import sys

import requests

import config

# Substrings that hint a market/series is a sport we model (best-effort filter).
_SPORT_HINTS = ("MLB", "NBA", "NHL", "NFL", "WNBA", "UFC", "PGA", "GOLF",
                "BASEBALL", "BASKETBALL", "HOCKEY", "FOOTBALL")


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if config.KALSHI_API_KEY:
        # Kalshi v2 uses key-id + RSA request signing for private endpoints; this
        # bearer fallback is only a convenience for deployments that proxy auth.
        h["Authorization"] = f"Bearer {config.KALSHI_API_KEY}"
    return h


def _get(path: str, **params):
    url = f"{config.KALSHI_API_BASE.rstrip('/')}/{path.lstrip('/')}"
    return requests.get(url, params=params, headers=_headers(), timeout=30)


def _preview(label: str, path: str, **params):
    print("\n" + "=" * 78)
    print(f"# {label}  ->  GET /{path}  {params}")
    print("=" * 78)
    try:
        resp = _get(path, **params)
        print(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:400])
            return None
        data = resp.json()
        # Print only the top of the payload + the first record's keys.
        if isinstance(data, dict):
            print("top-level keys:", list(data.keys()))
            for k, v in data.items():
                if isinstance(v, list) and v:
                    print(f"\nfirst '{k}' record:")
                    print(json.dumps(v[0], indent=2)[:1200])
                    break
        return data
    except Exception as e:  # noqa: BLE001 — spike script, surface anything
        print(f"ERROR: {e}")
        return None


def main() -> int:
    print(f"Kalshi base: {config.KALSHI_API_BASE}")
    print(f"API key set: {bool(config.KALSHI_API_KEY)}")

    events = _preview("Events (public browse)", "events", limit=20, status="open")
    markets = _preview("Markets (public browse)", "markets", limit=20, status="open")

    # Best-effort sports scan across the markets sample.
    rows = (markets or {}).get("markets", []) if isinstance(markets, dict) else []
    sporty = [
        m for m in rows
        if any(h in (str(m.get("ticker", "")) + str(m.get("title", "")) + str(m.get("event_ticker", ""))).upper()
               for h in _SPORT_HINTS)
    ]
    print("\n" + "=" * 78)
    print(f"# Sports-looking markets in sample: {len(sporty)} / {len(rows)}")
    print("=" * 78)
    for m in sporty[:10]:
        # yes_bid/yes_ask are cents; midpoint/100 ~= implied probability.
        yb, ya = m.get("yes_bid"), m.get("yes_ask")
        mid = (yb + ya) / 2 if isinstance(yb, (int, float)) and isinstance(ya, (int, float)) else None
        print(f"  {m.get('ticker')!s:28} yes_bid={yb} yes_ask={ya} "
              f"impl_prob={'%.3f' % (mid / 100) if mid is not None else 'n/a'} "
              f"vol={m.get('volume')}  {str(m.get('title'))[:48]}")

    if not rows:
        print("\nNo markets returned — endpoint may require auth, a different base "
              "URL, or be blocked from this network. Confirm Kalshi API access/terms "
              "(docs/prediction_markets_eval.md) and re-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
