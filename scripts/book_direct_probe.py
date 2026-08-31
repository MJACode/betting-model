"""Which sportsbooks will answer us DIRECTLY, from the worker, right now.

WHY THIS EXISTS. DraftKings' own feed turned out to be reachable and materially
fresher than the aggregator: on 2026-08-30 a 16-hour collection captured 1,890
distinct in-play quotes across 11 MLB games where The Odds API gave us 654, and
we only ever saw 29.7% of DK's line changes. mike's follow-up is the obvious
one -- if DK direct is that much better, what about the other five or six books
we already price against, and can we build a best line out of MULTIPLE direct
sources rather than one aggregator's cached snapshot?

That question has three parts and this script answers only the FIRST:

  1. does the host answer a request from the Railway worker at all?   <- here
  2. is its payload parseable into (line, over, under) per market?
  3. is it fresh enough to matter?

Steps 2 and 3 cost real work per book, so they are worth spending only on the
books that clear step 1. This script is deliberately a REPORT, not a feed: it
writes nothing, decides nothing, and its output is a table.

WHAT MAKES THIS DIFFERENT FROM RUNNING IT ON A LAPTOP. #293 concluded DK's
refusal was a TLS-fingerprint problem rather than an IP block, and the fix was
browser impersonation. But that was established from mike's home connection.
Datacentre IPs are a separate axis, and they are exactly what got ufcstats,
stats.nba.com and site.api.espn.com blocked on this project before. A book can
be perfectly reachable from a laptop and refuse the worker. So this is built to
run ON THE WORKER, prints its egress IP first, and every verdict below should
be read as "from a datacentre", not "in general".

ENDPOINTS ARE REVERSE-ENGINEERED GUESSES AND ARE TREATED AS SUCH. None of these
books publishes a public odds API. The URL shapes below come from what their
own web front-ends call, they are region-sharded, and they change -- DK's alone
has changed shape at least once (the older /sites/US-SB/api/v5/eventgroups form
vs the newer /api/sportscontent one). So the script TRIES a list per book and
reports what responded, which is the DataGolf convention this repo already
uses: document the assumption, isolate it, and let the run correct it. A 404
here means "this guess is stale", NOT "this book is unreachable" -- the two are
distinguished in the verdict column.

STATUS: SPIKE. Read-only, one request per URL, ~1 req/sec, unauthenticated
pages only. Nothing here writes to the database or to a feed.

    python scripts/book_direct_probe.py                 # every book, MLB
    python scripts/book_direct_probe.py --book bovada
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dk_direct_probe import HEADERS, _session, egress_ip  # noqa: E402

# Per book, the candidate URLs its own front-end is known to call, most likely
# first. `note` says what we already believe about the book, so a surprising
# result is visible AS a surprise rather than being quietly absorbed.
BOOKS: dict[str, dict] = {
    "draftkings": {
        "note": "proven parseable from a RESIDENTIAL ip (6,214 quotes/16h); "
                "403s the datacentre in 10-40ms even with cookie bootstrap",
        "urls": [
            "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/84240",
            "https://sportsbook-nash-usnj.draftkings.com/api/sportscontent/dkusnj/v1/leagues/84240",
        ],
    },
    "espn_dk_live": {
        # NOT a book -- ESPN's own public core API, which republishes DK's line
        # under two providers: 100 "DraftKings" (pre-game) and 200 "DraftKings
        # - Live Odds" (in-play). Verified 2026-08-31 returning a live total of
        # 11.5 on CIN@CHC while DK direct 403'd the same worker.
        #
        # If it is FRESH ENOUGH it is a route to DK's live number from a
        # datacentre, which is the exact blocker. Freshness is unmeasured and
        # this endpoint is an aggregator of DK, so it may be as coarse as The
        # Odds API -- that is the next measurement, not an assumption.
        "note": "ESPN's public core API republishes DK live odds (provider 200)",
        "urls": [
            "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/events?limit=5",
        ],
    },
    "bovada": {
        "note": "the only book that answered the worker: 200, ~800 KB, no key",
        "urls": [
            "https://www.bovada.lv/services/sports/event/coupon/events/A/description/baseball/mlb?marketFilterId=def&preMatchOnly=false&lang=en",
            "https://www.bovada.lv/services/sports/event/v2/events/A/description/baseball/mlb?lang=en",
        ],
    },
    "pinnacle": {
        "note": "has a real API; the public guest key rotates and 401'd",
        "urls": [
            "https://guest.api.arcadia.pinnacle.com/0.1/sports/3/leagues?all=false",
            "https://guest.api.arcadia.pinnacle.com/0.1/leagues/246/matchups",
        ],
    },
    "fanduel": {
        # Round 1 used the region-sharded sbapi.nj/pa hosts and got HTTP 500 --
        # a stale guess, not a refusal. The current shape is the UNSHARDED host
        # (sbapi.fanduel.com) behind Cloudflare with aggressive IP detection.
        "note": "unsharded host + Cloudflare; expect the residential ip to matter",
        "urls": [
            "https://sbapi.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=mlb",
            "https://sbapi.fanduel.com/api/content-managed-page?page=SPORT_HOME&eventTypeId=7511",
            "https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=mlb",
        ],
    },
    "betmgm": {
        "note": "no public API; internal CDS endpoints move without notice",
        "urls": [
            "https://sports.nj.betmgm.com/cds-api/bettingoffer/fixtures?x-bwin-accessid=NTQ3MjY2ZjMtYjRlNi00YTU5LWEwZTMtZTMyZTQ2YTgyMjBl&lang=en-us&country=US&offerMapping=All&sportIds=23&state=Latest",
            "https://sports.betmgm.com/cds-api/bettingoffer/fixtures?lang=en-us&country=US&offerMapping=All&sportIds=23&state=Latest",
        ],
    },
    "williamhill_us": {
        "note": "Caesars; americanwagering API, region-sharded, 403'd the worker",
        "urls": [
            "https://api.americanwagering.com/regions/us/locations/nj/brands/czr/sb/v3/sports/baseball/events/schedule",
        ],
    },
    "espnbet": {
        # api.espnbet.com does not resolve -- the round-1 result was a bad
        # hostname, not a refusal. ESPN BET runs on Penn's platform, so the
        # candidates below are the shapes that platform is known to use.
        "note": "Penn platform; api.espnbet.com does not resolve at all",
        "urls": [
            "https://espnbet.com/api/sports/baseball/mlb/events",
            "https://api.pa.espnbet.com/v2/sportsbook/sports/baseball/leagues/mlb/events",
        ],
    },
    "betrivers": {
        "note": "Rush Street; their /service/ api has historically been open",
        "urls": [
            "https://nj.betrivers.com/api/service/sportsbook/offering/listview/events?cageCode=849&type=live&groupId=1000093616",
        ],
    },
    "fanatics": {
        "note": "took over PointsBet's US ops; endpoint shape unverified",
        "urls": [
            "https://sportsbook.fanatics.com/api/sportsbook/v1/leagues/baseball/mlb",
        ],
    },
    "hardrock": {
        "note": "Hard Rock Bet, Seminole platform",
        "urls": [
            "https://app.hardrock.bet/api/sportsbook/v1/leagues/mlb/events",
        ],
    },
    # WYNNBET IS DELIBERATELY ABSENT. mike asked for it, and the answer is that
    # there is nothing left to probe: WynnBET closed its sportsbook in eight or
    # nine of twelve US markets in August 2023 and exited its last major market,
    # New York, in August 2024, citing customer-acquisition cost. It is not a
    # book we can shop a live line at, so an endpoint guess here would be
    # measuring a brand that no longer takes the bet.
}


def verdict(status: int | None, body_bytes: int, error: str | None) -> str:
    """Separate 'this book refuses us' from 'this guess is stale'.

    The distinction is the whole point of the report: a 403 is a decision the
    book made about us and no URL fix changes it, while a 404 only means the
    front-end moved and someone has to re-read it. Reporting both as 'failed'
    would throw away the only actionable half.
    """
    if error:
        return f"UNREACHABLE ({error[:40]})"
    if status is None:
        return "UNREACHABLE"
    if status in (401, 403):
        return "REFUSED — auth/bot wall, a URL fix will not help"
    if status == 404:
        return "STALE GUESS — endpoint moved, re-read the front-end"
    if status == 429:
        return "RATE LIMITED — reachable, needs backoff"
    if status == 400:
        # A 400 is the most ACTIONABLE failure on this list and the easiest to
        # throw away: the host answered, applied its own logic, and told us the
        # request was wrong. BetRivers returned
        #   {"code":"BAD_REQUEST","message":"No cage configuration found for
        #    cageCode='849'"}
        # which is a reachable book with one wrong parameter, not a closed door.
        return "ANSWERED, BAD PARAMS — reachable; fix the request"
    if 200 <= status < 300:
        return f"OK — {body_bytes:,}b, worth a parser" if body_bytes > 2000 \
            else f"OK BUT THIN — {body_bytes}b, probably not the odds payload"
    return f"HTTP {status}"


def probe_book(name: str, spec: dict, sess, out_dir: str) -> list[dict]:
    print(f"\n=== {name} ===  ({spec['note']})", flush=True)
    results = []
    for url in spec["urls"]:
        status = err = None
        body_bytes = 0
        detail = ""
        top_keys: list[str] = []
        try:
            r = sess.get(url, headers=HEADERS, timeout=20)
            status = r.status_code
            body_bytes = len(r.content or b"")
            body = (r.text or "").strip()
            if body.startswith(("{", "[")):
                detail = " ".join(body.split())
            if 200 <= status < 300:
                try:
                    payload = r.json()
                    top_keys = sorted(payload)[:8] if isinstance(payload, dict) \
                        else [f"<list len={len(payload)}>"]
                    dest = Path(out_dir) / f"book_{name}_sample.json"
                    dest.write_text(json.dumps(payload, indent=2)[:2_000_000],
                                    encoding="utf-8")
                except Exception as exc:                  # noqa: BLE001
                    top_keys = [f"<not json: {type(exc).__name__}>"]
        except Exception as exc:                          # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"

        v = verdict(status, body_bytes, err)
        print(f"  {str(status or 'ERR'):<5} {body_bytes:>9,}b  {v}", flush=True)
        print(f"        {url[:110]}", flush=True)
        if status and 400 <= status < 500 and detail:
            # Only for JSON-ish bodies: an HTML bot-wall page says nothing and
            # would bury the one line that does.
            print(f"        says: {detail[:150]}", flush=True)
        if top_keys:
            print(f"        keys: {top_keys}", flush=True)
        results.append({"book": name, "url": url, "status": status,
                        "bytes": body_bytes, "verdict": v, "keys": top_keys})
        time.sleep(1.0)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", nargs="*", default=sorted(BOOKS))
    ap.add_argument("--impersonate", nargs="?", const="chrome124",
                    default="chrome124")
    ap.add_argument("--out-dir", default=".")
    # Cookie bootstrap: load the book's own site HTML first and reuse its jar.
    # ON by default, because the 16-hour DK collection that worked from mike's
    # machine used it -- and a probe run in a DIFFERENT configuration from the
    # thing it is meant to predict proves nothing. Round 1 ran without it and
    # reported DK 403 from the worker: true, but unable to separate "this
    # datacentre IP is blocked" from "we never picked up a session".
    ap.add_argument("--no-bootstrap", action="store_true")
    a = ap.parse_args()

    print(f"book-direct spike @ {datetime.now(timezone.utc).isoformat()}",
          flush=True)
    sess = _session(a.impersonate, bootstrap=not a.no_bootstrap)
    # Printed FIRST and always: every verdict below is "from this address".
    # A datacentre IP is a different question from a home connection, and #293's
    # TLS-fingerprint finding was established from the latter.
    print(f"egress: {egress_ip(sess)}", flush=True)
    print(f"impersonate: {a.impersonate}   bootstrap: {not a.no_bootstrap}", flush=True)

    all_results = []
    for name in a.book:
        if name not in BOOKS:
            print(f"(unknown book: {name})", flush=True)
            continue
        all_results += probe_book(name, BOOKS[name], sess, a.out_dir)

    print("\n=== SUMMARY ===", flush=True)
    by_book: dict[str, str] = {}
    for r in all_results:
        # Best outcome per book wins: one stale guess does not condemn a book
        # that answered on another URL.
        rank = {"OK": 0}.get(r["verdict"].split(" ")[0], 1)
        if r["book"] not in by_book or rank == 0:
            by_book.setdefault(r["book"], r["verdict"])
            if rank == 0:
                by_book[r["book"]] = r["verdict"]
    for book, v in sorted(by_book.items()):
        print(f"  {book:<16} {v}", flush=True)


if __name__ == "__main__":
    main()
