"""Is ESPN's republished DraftKings line fresh enough to replace DK direct?

mike, 2026-08-31: "measure espn freshness."

WHY THIS MATTERS MORE THAN IT LOOKS. DraftKings refuses the Railway worker with
a 403 in 10-40ms and answers a residential address with a 200 -- so the DK
direct feed can only run on mike's machine, and an always-on live DK line needs
either a residential proxy or a different route. ESPN is a different route:

    provider 100  "DraftKings"             pre-game
    provider 200  "DraftKings - Live Odds"  IN-PLAY

and ESPN answers a datacentre with no impersonation at all. Verified 2026-08-31
on a live CIN@CHC in the bottom of the 9th: provider 200 showed a total of 11.5,
which is what bovada showed for the same game at the same moment.

BUT ESPN IS ITSELF AN AGGREGATOR OF DK, and that is the whole question. The Odds
API is also an honest aggregator of DK, and section 6 measured what it costs us:
we see 29.7% of DK's line changes and are on the wrong line 11.8% of the time,
because it publishes one snapshot per ~67s while DK reprices every 15-25s. ESPN
could easily be the same or worse. So this measures rather than assumes -- the
same mistake would otherwise be made twice.

HOW IT MEASURES. Both sources are polled from the SAME process on the SAME
clock, and each distinct quote is recorded at FIRST SIGHT. The comparison is
then first-seen-here versus first-seen-there, per quote:

  * a quote DK showed that ESPN never shows  -> ESPN's skip rate
  * for quotes both show, ESPN's delay       -> ESPN's lag distribution

That is the identical method section 6 used against The Odds API, deliberately,
so the two answers are comparable numbers rather than two different studies.

RUN IT ON MIKE'S MACHINE, because the DK half needs a residential address:

    python scripts/espn_dk_freshness.py --minutes 60

Writes a JSONL of observations and prints the verdict. Read-only, no database.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from scripts.dk_direct_probe import CANDIDATES, HEADERS, _session
from scripts.dk_freshness_compare import parse_dk_payload

ESPN_SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"
                   "/scoreboard")
ESPN_ODDS = ("https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb"
             "/events/{event}/competitions/{comp}/odds")
ESPN_LIVE_PROVIDER = "200"          # "DraftKings - Live Odds"
UA = {"User-Agent": "Mozilla/5.0"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def espn_live_quotes(sess) -> list[dict]:
    """One read of every live MLB game's DK-live total, via ESPN."""
    out = []
    try:
        sb = sess.get(ESPN_SCOREBOARD, headers=UA, timeout=15).json()
    except Exception:                                     # noqa: BLE001
        return out
    for ev in sb.get("events") or []:
        state = ((ev.get("status") or {}).get("type") or {}).get("state")
        if state != "in":
            continue
        comps = ev.get("competitions") or []
        if not comps:
            continue
        try:
            d = sess.get(ESPN_ODDS.format(event=ev["id"], comp=comps[0]["id"]),
                         headers=UA, timeout=15).json()
        except Exception:                                 # noqa: BLE001
            continue
        for it in d.get("items") or []:
            if str((it.get("provider") or {}).get("id")) != ESPN_LIVE_PROVIDER:
                continue
            cur = it.get("current") or {}
            total = (cur.get("total") or {}).get("american")
            over = (cur.get("over") or {}).get("american")
            under = (cur.get("under") or {}).get("american")
            if total is None or over is None or under is None:
                continue
            out.append({"game": ev.get("shortName"), "line": str(total),
                        "over": str(over), "under": str(under)})
    return out


def dk_live_quotes(sess) -> list[dict]:
    """The same totals, straight from DK. Needs a residential address."""
    out = []
    for url in CANDIDATES["MLB"]:
        try:
            body = sess.get(url, headers=HEADERS, timeout=15).json()
        except Exception:                                 # noqa: BLE001
            continue
        for rec in parse_dk_payload(body, "MLB", live_only=True):
            if rec["market"] != "totals" or rec["line"] is None:
                continue
            out.append({"game": rec["event_name"], "line": str(rec["line"]),
                        "over": str(rec["price_a"]),
                        "under": str(rec["price_b"])})
        return out
    return out


def _key(q: dict) -> str:
    """A quote is the same quote at the same game, line and both prices."""
    return f'{q["game"]}|{q["line"]}|{q["over"]}|{q["under"]}'


def run(minutes: float, interval: float, out_path: Path) -> None:
    dk_sess = _session("chrome124", bootstrap=True)
    espn_sess = requests.Session()
    first: dict[str, dict] = {}
    fh = out_path.open("a", encoding="utf-8")
    deadline = time.time() + minutes * 60
    polls = 0

    print(f"recording to {out_path}", flush=True)
    while time.time() < deadline:
        stamp = _now()
        for src, quotes in (("dk", dk_live_quotes(dk_sess)),
                            ("espn", espn_live_quotes(espn_sess))):
            for q in quotes:
                k = f"{src}:{_key(q)}"
                if k in first:
                    continue
                first[k] = {"src": src, "key": _key(q), "at": stamp, **q}
                fh.write(json.dumps(first[k]) + "\n")
        fh.flush()
        polls += 1
        if polls % 20 == 0:
            print(f"  {polls} polls, {len(first)} distinct first-sightings",
                  flush=True)
        time.sleep(interval)
    fh.close()
    report(first.values(), polls)


def report(rows, polls: int) -> None:
    """The two numbers that decide it, in the same shape section 6 used."""
    dk = {r["key"]: r for r in rows if r["src"] == "dk"}
    espn = {r["key"]: r for r in rows if r["src"] == "espn"}
    if not dk:
        print("\nNO DK QUOTES RECORDED — is this running on a residential "
              "address? DK 403s a datacentre.", flush=True)
        return

    both, lags = 0, []
    for k, d in dk.items():
        e = espn.get(k)
        if not e:
            continue
        both += 1
        lag = (datetime.fromisoformat(e["at"])
               - datetime.fromisoformat(d["at"])).total_seconds()
        lags.append(lag)

    lags.sort()

    def pct(p):
        return lags[min(int(len(lags) * p), len(lags) - 1)] if lags else None

    print(f"\n=== ESPN vs DK direct, {polls} polls ===", flush=True)
    print(f"  DK distinct quotes           {len(dk)}", flush=True)
    print(f"  ESPN distinct quotes         {len(espn)}", flush=True)
    print(f"  DK quotes ESPN also showed   {both} "
          f"({100.0 * both / len(dk):.1f}%)", flush=True)
    if lags:
        print(f"  ESPN lag  median/p90/max     {pct(0.5):.1f}s / "
              f"{pct(0.9):.1f}s / {lags[-1]:.1f}s", flush=True)
    # The Odds API's numbers from section 6, so the verdict is a comparison
    # rather than a bare figure.
    print("  (The Odds API, same method: 29.7% of DK changes seen, "
          "16.1s median lag)", flush=True)
    print("\n  VERDICT: ESPN is worth building on only if it beats BOTH of "
          "those. A better lag on a worse capture rate is not better.",
          flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--out", default="espn_dk_freshness.jsonl")
    a = ap.parse_args()
    run(a.minutes, a.interval, Path(a.out))


if __name__ == "__main__":
    main()
