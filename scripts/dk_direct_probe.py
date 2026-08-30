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
import os
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

# The header set a real Chrome tab sends to this host. Round 1 sent only a UA
# and an Accept, which is the shape of a script wearing a browser's name -- the
# sec-ch-* set and the ordering are themselves part of what gets matched.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://sportsbook.draftkings.com/",
    "Origin": "https://sportsbook.draftkings.com",
    "sec-ch-ua": '"Chromium";v="126", "Not:A-Brand";v="24", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# A real browser reaches the JSON having already loaded the site, so it carries
# whatever cookies the edge set on that first page view.
BOOTSTRAP_URL = "https://sportsbook.draftkings.com/leagues/baseball/mlb"


def _proxies() -> dict | None:
    """Egress the operator supplies, as a plain proxy URL, so nothing here is
    tied to one provider. MEASURED 2026-08-30: a residential IP returned the
    IDENTICAL 403/449b as the Railway datacenter IP, so the source address is
    not what is being matched and a proxy is not expected to help. Kept as a
    switch only so that conclusion stays falsifiable."""
    url = os.environ.get("DK_PROXY_URL")
    return {"http": url, "https": url} if url else None


def _session(impersonate: str | None, bootstrap: bool):
    """A client, plus whatever the edge handed out on the way in.

    With --impersonate this is curl_cffi, which replays a real Chrome TLS and
    HTTP/2 fingerprint. That is the substantive difference from the header work
    above: a header can CLAIM Chrome, a JA3 either is or is not, and after the
    residential test the fingerprint is the only hypothesis left standing."""
    if impersonate:
        from curl_cffi import requests as cr
        sess = cr.Session(impersonate=impersonate)
    else:
        sess = requests.Session()
    sess.headers.update(HEADERS)
    px = _proxies()
    if px:
        sess.proxies = px
    if bootstrap:
        try:
            sess.get(BOOTSTRAP_URL, timeout=20)
        except Exception as exc:                          # noqa: BLE001
            print(f"  (bootstrap failed, continuing: {exc})", flush=True)
    return sess


def _probe_once(url: str, timeout: float = 15.0, sess=None) -> dict:
    started = time.time()
    out = {"url": url, "ok": False, "status": None, "ms": None,
           "bytes": None, "top_keys": None, "error": None}
    client = sess or requests
    try:
        r = client.get(url, headers=HEADERS, timeout=timeout)
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


def egress_ip(sess) -> str:
    """Which address DraftKings actually saw.

    Load-bearing when this runs anywhere but a laptop: the residential-vs-
    datacenter question was settled by comparing two runs, and a run that does
    not record WHICH address it left from cannot be compared to anything. Uses
    the same session, so it reports the egress the probe itself will use rather
    than the machine's idea of its own address."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            r = sess.get(url, timeout=8)
            if r.status_code == 200 and r.text.strip():
                return r.text.strip()[:64]
        except Exception:                                     # noqa: BLE001
            continue
    return "unknown"


def reachability(sports: list[str], impersonate: str | None = None,
                 bootstrap: bool = False, out_dir: str = ".") -> None:
    """Which host and URL shape answers, if any. Answers question 1 and 2.

    The mode line matters as much as the result: every hypothesis here is
    eliminated by a MATCHED PAIR of runs that differ in one switch, so a run
    whose settings are not recorded proves nothing."""
    mode = f"impersonate={impersonate}" if impersonate else "plain-requests"
    mode += " + cookie-bootstrap" if bootstrap else ""
    mode += " + proxy" if _proxies() else " + direct-egress"
    print(f"mode: {mode}", flush=True)
    sess = _session(impersonate, bootstrap)
    print(f"egress: {egress_ip(sess)}", flush=True)
    for sport in sports:
        print(f"\n=== {sport} ===", flush=True)
        for url in CANDIDATES[sport]:
            r = _probe_once(url, sess=sess)
            head = f"{r['status']} {r['ms']}ms {r['bytes']}b" if r["status"] \
                else f"ERR {r['error']}"
            print(f"  {head:<28} {url}", flush=True)
            if r["ok"]:
                print(f"    top-level keys: {r['top_keys']}", flush=True)
                # The whole payload, so a parser is written from a real one
                # rather than from a blog post about one. Local, not /tmp:
                # this runs on Windows as often as on the worker.
                dest = Path(out_dir) / f"dk_{sport.lower()}_sample.json"
                try:
                    body = sess.get(url, headers=HEADERS, timeout=20).json()
                    dest.write_text(json.dumps(body, indent=2)[:2_000_000])
                    print(f"    sample written: {dest}", flush=True)
                except Exception as exc:                  # noqa: BLE001
                    print(f"    (sample not saved: {exc})", flush=True)
            time.sleep(1.0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="*", default=["MLB", "NCAAF"])
    ap.add_argument("--impersonate", nargs="?", const="chrome124", default=None,
                    help="replay a real browser TLS/HTTP2 fingerprint via "
                         "curl_cffi (chrome124, chrome120, safari17_0, ...)")
    ap.add_argument("--bootstrap", action="store_true",
                    help="load the site HTML first and reuse its cookie jar")
    ap.add_argument("--out-dir", default=".",
                    help="where to write a sample payload on success")
    a = ap.parse_args()
    print(f"dk-direct spike @ {datetime.now(timezone.utc).isoformat()}",
          flush=True)
    reachability([s for s in a.sports if s in CANDIDATES],
                 impersonate=a.impersonate, bootstrap=a.bootstrap,
                 out_dir=a.out_dir)
