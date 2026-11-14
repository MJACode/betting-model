"""What DraftKings' own UFC board prices beyond the fight winner: method of
victory, goes the distance, winning round, to win by finish. Read-only, run
from mike's PC (DraftKings refuses the Railway worker: docs/live_odds_freshness.md,
measured 2026-08-31). DraftKings' terms forbid automated access; mike's call on that is
recorded in data/ingestors/dk_direct_feed.py and is not re-argued here.

Same client as data/ingestors/dk_live_board.py: curl_cffi impersonating
Chrome, one boot page, then the sportscontent league answer (UFC is league
9034) and one answer per prop sub-page. Saves every answer to ./dk_probe/ and
prints the fights by date, so a card's prop lead time can be read off it.

    python dk_props_probe.py                      # the four markets below
    python dk_props_probe.py "Round of Finish"    # any sub-page, by its name
    python dk_props_probe.py --offline            # re-read the saved answers

Run from the study folder (README.md). Five requests for the default four
markets after the boot page and the league answer."""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
LEAGUE = "9034"
BOOT = "https://sportsbook.draftkings.com/leagues/mma/ufc"
BASE = f"https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{LEAGUE}"
DEFAULT = ["Method of Victory", "Fight to go the Distance", "Winning Round", "To Win by Finish"]
OUT = Path("dk_probe")
OUT.mkdir(exist_ok=True)

args = [a for a in sys.argv[1:] if a != "--offline"]
offline = "--offline" in sys.argv
wanted = args or DEFAULT
session = None
if not offline:
    from curl_cffi import requests as cr
    session = cr.Session(impersonate="chrome124")
    print("boot page", session.get(BOOT, timeout=20).status_code)


def fetch(url: str, path: Path):
    if offline:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    r = session.get(url, timeout=20)
    print(f"  HTTP {r.status_code}, {len(r.content)} bytes  {url}")
    if r.status_code != 200:
        return None
    path.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()


def by_date(answer) -> dict:
    return dict(sorted(collections.Counter(
        e.get("startEventDate", "")[:10] for e in answer.get("events", [])).items()))


league = fetch(BASE, OUT / f"league_{LEAGUE}.json")
cats = {c["id"]: c.get("name") for c in league.get("categories", [])}
print("categories:", cats)
print("fights on the board, by date:", by_date(league))
subs = {c.get("name", "").strip(): (c.get("categoryId"), c["id"]) for c in league.get("subcategories", [])}
print(len(subs), "sub-pages:", sorted(subs))

for name in wanted:
    if name not in subs:
        print(f"\n{name}: not listed")
        continue
    cat, sub = subs[name]
    d = fetch(f"{BASE}/categories/{cat}/subcategories/{sub}", OUT / f"sub_{sub}.json")
    print(f"\n{name} (category {cat}, sub-page {sub})")
    if not d:
        print("  no answer")
        continue
    ev = {e["id"]: e.get("name") for e in d.get("events", [])}
    mk = {m["id"]: m for m in d.get("markets", [])}
    print(f"  fights {len(ev)}, markets {len(mk)}, prices {len(d.get('selections', []))}; by date {by_date(d)}")
    sels = collections.defaultdict(list)
    for s in d.get("selections", []):
        sels[s.get("marketId")].append(s)
    for mid, ss in list(sels.items())[:3]:
        m = mk.get(mid, {})
        print("  ", ev.get(m.get("eventId")), "|", m.get("name"), "|",
              [(x.get("label"), (x.get("displayOdds") or {}).get("american")) for x in ss][:8])
