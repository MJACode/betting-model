"""DraftKings' own tennis board: which leagues it lists, saved raw, so the
tennis reader is built from what DraftKings actually serves.

WHY. The odds feed sells only its 53 top-tier tennis tournaments; DraftKings
also lists the men's 250s, Challengers and ITF events and the women's 125s and
ITF events, and a pick below the top tier needs DraftKings' own price
(docs/sports/tennis.md, the market grid). mike, 2026-11-13: yes to reading it.

HOW. The same session the repo's in-play DraftKings reader uses
(data/ingestors/dk_live_board.dk_session: a browser-style session that first
opens the sport's page). It opens the tennis page, collects every league id the
page names, reads each league's board from the sportscontent API, writes each
answer to --out unchanged, and prints one line per league: id, name, events,
markets. It writes nothing to the database. One request at a time, a second
apart; a refusal stops the run.

The permission check refused this read from a Claude session on 2026-11-13,
twice, with mike's yes in chat. It runs from mike's own terminal, or from a
session once his settings allow it:

    python -m scripts.tennis_dk_probe --out C:/Users/micha/tennis_research/dk_probe
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

BOOT_URL = "https://sportsbook.draftkings.com/sports/tennis"
LEAGUE_URL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{league}"
PAUSE_S = 1.0


def session():
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome124")
    return s


def league_ids(page: str) -> list[str]:
    """Every DraftKings league id the tennis page names, in page order:
    `"leagueId":"123"` in its embedded state, and `/leagues/tennis/<slug>`
    links with an id beside them."""
    ids = re.findall(r'"leagueId"\s*:\s*"?(\d{3,7})"?', page)
    ids += re.findall(r'/leagues/tennis/[a-z0-9-]+[^"]*?"?\s*[,:]?\s*"?id"?\s*:\s*"?(\d{3,7})', page)
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def summarise(body: dict) -> dict:
    leagues = body.get("leagues") or []
    name = leagues[0].get("name") if leagues else None
    events = body.get("events") or []
    markets = body.get("markets") or []
    kinds = sorted({str(m.get("marketType", {}).get("name") or m.get("name")) for m in markets})[:12]
    return {"name": name, "events": len(events), "markets": len(markets), "kinds": kinds}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    s = session()
    r = s.get(BOOT_URL, timeout=20)
    (a.out / "tennis_page.html").write_text(r.text, encoding="utf-8")
    print(f"tennis page: HTTP {r.status_code}, {len(r.text):,} characters")
    if r.status_code != 200:
        return 1
    ids = league_ids(r.text)
    print(f"league ids named on the page: {len(ids)}")
    for lid in ids:
        time.sleep(PAUSE_S)
        x = s.get(LEAGUE_URL.format(league=lid), timeout=20)
        if x.status_code != 200:
            print(f"league {lid}: HTTP {x.status_code}; stopping")
            return 1
        body = x.json()
        (a.out / f"league_{lid}.json").write_text(json.dumps(body), encoding="utf-8")
        print(f"league {lid}: {json.dumps(summarise(body))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
