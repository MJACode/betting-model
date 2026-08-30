"""
Reachability + freshness spike: DraftKings' own feed vs The Odds API.

WHY. The complaint that started this was "I opened the DraftKings app two
seconds after your post and it was on 51, you said 46.5". We have since proved
it was not our pipeline (1.3s end to end, Discord's own clock) and not the
per-event endpoint (36/36 paired reads returned the identical cache): The Odds
API serves ONE cached in-play snapshot for ~44-46 seconds. That is a floor we
cannot buy past on that vendor.

Which leaves one question we have never actually measured: HOW FAR BEHIND THE
APP IS THAT FLOOR? The DraftKings app reads DraftKings' own feed, so reading
that feed is the only way to compare like for like -- and if it turns out to be
both reachable and materially fresher, it is also the fix, at zero vendor spend.

STATUS: SPIKE, NOT PRODUCTION. Three things are unknown and this script exists
to answer them rather than assume:
  1. Is the host reachable from the worker at all? Datacenter IPs are exactly
     what got ufcstats, stats.nba.com and site.api.espn.com blocked on us.
  2. Which URL shape answers? DraftKings has no documented API; the endpoints
     are reverse-engineered and have changed shape at least once (the older
     /sites/US-SB/api/v5/eventgroups form vs the newer /api/sportscontent one).
     So it TRIES a list and reports what responds instead of hard-coding a
     guess -- the DataGolf convention: document the assumption, isolate it.
  3. Is it actually fresher than the aggregator, and by how much?

BEFORE ANY OF THIS BECOMES PRODUCTION, the terms-of-service question is the
user's call to make, not this script's. It is read-only, low-rate, and reads
pages DraftKings serves unauthenticated -- the same posture as the ESPN hidden
API this platform already depends on daily -- but that is a reason it is worth
asking about, not a reason to skip asking.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

# Candidate endpoints, newest shape first. leagueId 84240 is MLB and 87637 is
# NCAAF in DraftKings' own numbering as reported publicly; both are UNVERIFIED
# from here, which is the point of trying several.
CANDIDATES = {
    "MLB": [
        "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/84240",
        "https://sportsbook-nash-usnj.draftkings.com/api/sportscontent/dkusnj/v1/leagues/84240",
        "https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/84240?format=json",
    ],
    "NCAAF": [
        "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/87637",
        "https://sportsbook-nash-usnj.draftkings.com/api/sportscontent/dkusnj/v1/leagues/87637",
        "https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/87637?format=json",
    ],
}

# A browser UA. Not evasion -- these hosts return an error page to a bare
# python-requests UA, and a spike that cannot tell "blocked" from "wrong
# header" answers nothing.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "application/json",
}


def _probe_once(url: str, timeout: float = 15.0) -> dict:
    started = time.time()
    out = {"url": url, "ok": False, "status": None, "ms": None,
           "bytes": None, "top_keys": None, "error": None}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        out["status"] = r.status_code
        out["ms"] = round((time.time() - started) * 1000)
        out["bytes"] = len(r.content)
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            body = r.json()
            out["ok"] = True
            out["top_keys"] = sorted(body)[:12] if isinstance(body, dict) else \
                f"list[{len(body)}]"
    except Exception as exc:                              # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def reachability(sports: list[str]) -> None:
    """Which host and URL shape answers, if any. Answers question 1 and 2."""
    for sport in sports:
        print(f"\n=== {sport} ===", flush=True)
        for url in CANDIDATES[sport]:
            r = _probe_once(url)
            head = f"{r['status']} {r['ms']}ms {r['bytes']}b" if r["status"] \
                else f"ERR {r['error']}"
            print(f"  {head:<28} {url}", flush=True)
            if r["ok"]:
                print(f"    top-level keys: {r['top_keys']}", flush=True)
                # One sample so the next session can write a parser from a real
                # payload rather than from a blog post about one.
                Path(f"/tmp/dk_{sport.lower()}_sample.json").write_text(
                    json.dumps(_probe_once(url) | {"note": "keys only"}, indent=2))
            time.sleep(1.0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="*", default=["MLB", "NCAAF"])
    a = ap.parse_args()
    print(f"dk-direct spike @ {datetime.now(timezone.utc).isoformat()}",
          flush=True)
    reachability([s for s in a.sports if s in CANDIDATES])
