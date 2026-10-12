"""
Kalshi NFL probe + fetch (free, no-login public market-data API).

Every GET goes through `get()`, which caches the raw JSON under
%TEMP%/nfl_edge/kalshi/raw/ keyed on the full URL, so a re-run costs zero
requests, and counts the live requests it made (printed at the end).
Rate limit: unauthenticated limits are not published; we pace at <= 4 req/s
and back off on HTTP 429.

Stages (python -m scripts.nfl_edge_kalshi_fetch --stage <s>):
  probe    cutoff, the NFL game/spread/total series, every settled market in
           those series (historical + live), counts by season/week, volume,
           and a candlestick availability check on a few markets.
  candles  1-minute candles for ONE market per game (the home team's
           KXNFLGAME market: buying the away side = buying NO on it at
           1 - yes_bid), window kickoff-8h .. kickoff+5h.

Nothing here is graded. Grading is scripts/nfl_edge_kalshi.py.
Repo rule: anything fetched here must be stored in Supabase before it is
relied on; this script only records row counts and sizes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from scripts.nfl_edge_lib import CACHE, games

BASE = "https://api.elections.kalshi.com/trade-api/v2"
KDIR = CACHE / "kalshi"
RAW = KDIR / "raw"
RAW.mkdir(parents=True, exist_ok=True)
SERIES = ["KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL"]
LIVE_REQUESTS = 0
_last = [0.0]


def get(path: str, params: dict | None = None, max_live: int = 10_000):
    """Cached GET. Returns parsed JSON (or {'_http_error': code})."""
    global LIVE_REQUESTS
    q = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
    url = f"{BASE}{path}" + (f"?{q}" if q else "")
    key = hashlib.sha1(url.encode()).hexdigest()[:20]
    f = RAW / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["body"]
    if LIVE_REQUESTS >= max_live:
        raise RuntimeError(f"live request cap {max_live} reached")
    for attempt in range(6):
        wait = 0.26 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        LIVE_REQUESTS += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"Accept": "application/json",
                                  "User-Agent": "nfl-edge-research/0.1"}), timeout=60) as r:
                body = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            body = {"_http_error": e.code, "_msg": e.read().decode("utf-8", "replace")[:300]}
            break
    else:
        raise RuntimeError(f"429 x6 on {url}")
    f.write_text(json.dumps({"url": url, "fetched": time.time(), "body": body}), encoding="utf-8")
    return body


def paged(path: str, params: dict, item_key: str = "markets"):
    out, cursor = [], None
    while True:
        p = dict(params, cursor=cursor) if cursor else dict(params)
        b = get(path, p)
        if "_http_error" in b:
            print("  HTTP", b)
            break
        out += b.get(item_key, [])
        cursor = b.get("cursor")
        if not cursor or not b.get(item_key):
            break
    return out


# Kalshi team codes -> nflverse codes (only where they differ).
K2N = {"JAC": "JAX", "WSH": "WAS", "LA": "LA", "LAR": "LA", "LV": "LV", "OAK": "LV"}


def parse_event(ev: str):
    """KXNFLGAME-25SEP07BALBUF -> (date 2025-09-07, letters 'BALBUF')."""
    tail = ev.split("-", 1)[1]
    d = pd.to_datetime(tail[:7], format="%y%b%d", errors="coerce")
    return d, tail[7:]


def map_games(mk: pd.DataFrame) -> pd.DataFrame:
    """Attach nflverse game_id by (date +-1 day, team-letter string) match."""
    g = games()
    g = g[g["season"] >= 2024][["game_id", "season", "week", "game_type", "gameday",
                                "home_team", "away_team", "kick"]].copy()
    g["gameday"] = pd.to_datetime(g["gameday"])
    rows = []
    for ev in mk["event_ticker"].unique():
        d, letters = parse_event(ev)
        if pd.isna(d):
            continue
        cand = g[(g["gameday"] - d).abs() <= pd.Timedelta(days=1)]
        hit = None
        for _, r in cand.iterrows():
            names = {r.home_team, r.away_team}
            for a in names:
                ka = [k for k, v in K2N.items() if v == a] + [a]
                for kk in ka:
                    if letters.startswith(kk):
                        rest = letters[len(kk):]
                        o = (names - {a}).pop()
                        ko = [k for k, v in K2N.items() if v == o] + [o]
                        if rest in ko:
                            hit = r
        if hit is not None:
            rows.append({"event_ticker": ev, "game_id": hit.game_id, "season": hit.season,
                         "week": hit.week, "game_type": hit.game_type,
                         "home_team": hit.home_team, "away_team": hit.away_team,
                         "kick": hit.kick})
    return mk.merge(pd.DataFrame(rows), on="event_ticker", how="left")


def probe():
    print("cutoff:", get("/historical/cutoff"))
    s = get("/series", {"category": "Sports"})
    ser = {x["ticker"]: x for x in s.get("series", [])}
    for t in SERIES:
        x = ser.get(t, {})
        print(f"series {t}: title={x.get('title')!r} fee_type={x.get('fee_type')} "
              f"fee_multiplier={x.get('fee_multiplier')}")
    allm = []
    for t in SERIES:
        h = paged("/historical/markets", {"series_ticker": t, "limit": 1000})
        lv = paged("/markets", {"series_ticker": t, "limit": 1000, "status": "settled"})
        for m in h:
            m["src"] = "historical"
        for m in lv:
            m["src"] = "live"
        print(f"{t}: historical {len(h)} markets, live-settled {len(lv)} markets")
        for m in h + lv:
            m["series"] = t
        allm += h + lv
    mk = pd.DataFrame(allm)
    keep = ["ticker", "event_ticker", "series", "src", "title", "yes_sub_title",
            "open_time", "close_time", "status", "result", "volume_fp", "open_interest_fp",
            "floor_strike", "strike_type", "custom_strike", "rules_primary", "rules_secondary",
            "settlement_value_dollars", "expiration_value"]
    mk = mk[[c for c in keep if c in mk.columns]].drop_duplicates("ticker")
    mk["volume"] = pd.to_numeric(mk["volume_fp"], errors="coerce")
    mk = map_games(mk)
    mk["custom_strike"] = mk["custom_strike"].astype(str) if "custom_strike" in mk else None
    mk.to_parquet(KDIR / "markets_nfl.parquet", index=False)
    print(f"saved {len(mk)} markets -> {KDIR / 'markets_nfl.parquet'} "
          f"({(KDIR / 'markets_nfl.parquet').stat().st_size / 1e6:.2f} MB)")
    un = mk[mk["game_id"].isna()]
    print(f"unmapped markets: {len(un)} (events {un.event_ticker.nunique()}), e.g.",
          un.event_ticker.drop_duplicates().head(8).tolist())
    m = mk.dropna(subset=["game_id"])
    tab = (m.groupby(["series", "season", "game_type"])
             .agg(markets=("ticker", "size"), games=("game_id", "nunique"),
                  games_vol=("game_id", lambda s: m.loc[s.index][m.loc[s.index, "volume"] > 0]
                             .game_id.nunique()),
                  med_vol_per_mkt=("volume", "median"),
                  first=("open_time", "min"), last=("close_time", "max"))
             .reset_index())
    print(tab.to_string(index=False))
    w = m[(m["season"] == 2026) & (m["game_type"] == "REG")]
    print("2026 REG by week (KXNFLGAME games):",
          w[w.series == "KXNFLGAME"].groupby("week").game_id.nunique().to_dict())
    # candlestick availability on 3 KXNFLGAME markets: one early 2025, one late 2025, one 2026
    gm = m[(m.series == "KXNFLGAME") & (m.volume > 0)].sort_values("kick")
    picks = []
    for sea, wk in ((2025, 1), (2025, 17), (2026, 3)):
        x = gm[(gm.season == sea) & (gm.week == wk)]
        if len(x):
            picks.append(x.iloc[0])
    for r in picks:
        k = int(pd.Timestamp(r.kick).timestamp())
        for per in (1, 60):
            path = (f"/historical/markets/{r.ticker}/candlesticks" if r.src == "historical"
                    else f"/series/KXNFLGAME/markets/{r.ticker}/candlesticks")
            b = get(path, {"start_ts": k - 8 * 3600, "end_ts": k + 5 * 3600,
                           "period_interval": per})
            c = b.get("candlesticks", []) if isinstance(b, dict) else []
            print(f"candles {r.ticker} ({r.src}, {r.season} wk{r.week}) period={per}m: "
                  f"{len(c)} candles; err={b.get('_http_error') if isinstance(b, dict) else None}"
                  + (f"; first={c[0]}" if c and per == 60 else ""))


def candles(seasons=(2025, 2026), max_week_2026: int = 5):
    mk = pd.read_parquet(KDIR / "markets_nfl.parquet")
    gm = mk[(mk.series == "KXNFLGAME") & mk.game_id.notna() & (mk.volume > 0)
            & (mk.game_type == "REG") & mk.season.isin(seasons)]
    gm = gm[~((gm.season == 2026) & (gm.week > max_week_2026))]
    # the HOME team's market: its yes_sub_title / ticker suffix is the home code
    gm = gm.assign(suffix=gm.ticker.str.rsplit("-", n=1).str[-1].map(lambda s: K2N.get(s, s)))
    home = gm[gm.suffix == gm.home_team].drop_duplicates("game_id")
    print(f"games with a home-team market: {len(home)} "
          f"(of {gm.game_id.nunique()} games with any traded market)")
    out = []
    for i, r in enumerate(home.itertuples()):
        k = int(pd.Timestamp(r.kick).timestamp())
        path = (f"/historical/markets/{r.ticker}/candlesticks" if r.src == "historical"
                else f"/series/KXNFLGAME/markets/{r.ticker}/candlesticks")
        b = get(path, {"start_ts": k - 8 * 3600, "end_ts": k + 5 * 3600, "period_interval": 1},
                max_live=420)
        for c in (b.get("candlesticks", []) if isinstance(b, dict) else []):
            out.append({"game_id": r.game_id, "ticker": r.ticker, "ts": c["end_period_ts"],
                        "yes_bid_c": c.get("yes_bid", {}).get("close_dollars", c.get("yes_bid", {}).get("close")),
                        "yes_ask_c": c.get("yes_ask", {}).get("close_dollars", c.get("yes_ask", {}).get("close")),
                        "yes_bid_lo": c.get("yes_bid", {}).get("low_dollars", c.get("yes_bid", {}).get("low")),
                        "yes_ask_hi": c.get("yes_ask", {}).get("high_dollars", c.get("yes_ask", {}).get("high")),
                        "price_c": (c.get("price") or {}).get("close_dollars", (c.get("price") or {}).get("close")),
                        "volume": c.get("volume_fp", c.get("volume")),
                        "oi": c.get("open_interest_fp", c.get("open_interest"))})
        if i % 50 == 0:
            print(f"  {i}/{len(home)} live requests so far {LIVE_REQUESTS}")
    cd = pd.DataFrame(out)
    for c in ("yes_bid_c", "yes_ask_c", "yes_bid_lo", "yes_ask_hi", "price_c", "volume", "oi"):
        cd[c] = pd.to_numeric(cd[c], errors="coerce")
    cd["ts"] = pd.to_datetime(cd["ts"], unit="s", utc=True)
    cd.to_parquet(KDIR / "candles_1m_nflgame.parquet", index=False)
    print(f"saved {len(cd)} candles over {cd.game_id.nunique()} games -> "
          f"{(KDIR / 'candles_1m_nflgame.parquet').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["probe", "candles"], required=True)
    a = ap.parse_args()
    {"probe": probe, "candles": candles}[a.stage]()
    print(f"LIVE REQUESTS THIS RUN: {LIVE_REQUESTS}")
