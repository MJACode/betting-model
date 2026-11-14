"""BestFightOdds as a price-history source for UFC props (method of victory,
goes the distance, round betting, inside the distance). Read-only and polite:
a 3-second pause before every request. robots.txt allows everything but
/cnadm/ (read 2026-11-13).

Three things it measures:

    python bfo_probe.py event ufc-334-4433 ...       # an event page: per book,
        how many fight-winner and prop cells carry a price (the page shows the
        book's LAST price; a book's column is keyed by its data-b id)
    python bfo_probe.py chart "b=22&m=36053&p=1&pt=8&tn=1" ...   # one price
        history: b = book id (omit for the mean of all books), m = fight id,
        pt = prop type (8 = wins by TKO/KO), tn = fighter (1 or 2), p = side.
        The answer is base64, then ROT47, then JSON, as the site's own notIn()
        decodes it. A point is written only when the price changes.
    python bfo_probe.py sitemap                       # UFC event pages listed

Add --offline to re-read what an earlier run saved in ./bfo/. Run from the
study folder (README.md)."""
import base64
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SITE = "https://www.bestfightodds.com"
OUT = Path("bfo")
OUT.mkdir(exist_ok=True)
ROT = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
offline = "--offline" in sys.argv
argv = [a for a in sys.argv[1:] if a != "--offline"]


def get(path: str, save: Path, xhr: bool = False) -> str:
    if offline:
        return save.read_text(encoding="utf-8")
    time.sleep(3)
    headers = {"User-Agent": "Mozilla/5.0"}
    if xhr:
        headers.update({"Referer": SITE + "/", "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(urllib.request.Request(SITE + path, headers=headers), timeout=30) as r:
        body = r.read().decode("utf-8")
        print(f"  HTTP {r.status}, {len(body)} chars  {path}")
    save.write_text(body, encoding="utf-8")
    return body


def event(slug: str):
    t = get(f"/events/{slug}", OUT / f"event_{slug}.html")
    print("\n", re.findall(r"<title>(.*?)</title>", t))
    body = t[[m.start() for m in re.finditer("<table", t)][1]:]
    th = re.search(r"<thead>(.*?)</thead>", body, re.S).group(1)
    books = {int(b): re.split(r"\$|&nbsp;", re.sub("<[^>]+>", "", n))[0].strip()
             for b, n in re.findall(r'data-b="(\d+)">(.*?)</th>', th, re.S)}
    fw, pr, rows = Counter(), Counter(), set()
    for attrs, head, cells in re.findall(r'<tr([^>]*)><th scope="row">(.*?)</th>(.*?)</tr>', body, re.S):
        prop = 'class="pr"' in attrs
        if prop:
            rows.add(re.sub(r"^\S+ wins", "X wins", re.sub("<[^>]+>", "", head).strip()))
        for b, inner in re.findall(r'data-li="\[(\d+),[^"]*\]"[^>]*>(.*?)</td>', cells, re.S):
            if re.search(r"[+−-]\d{3,}", re.sub("<[^>]+>", " ", inner)):
                (pr if prop else fw)[books.get(int(b), b)] += 1
    print("  fight-winner prices per book:", dict(fw))
    print("  prop prices per book:", dict(pr))
    print("  distinct prop rows:", len(rows))


def chart(query: str):
    raw = get(f"/api/ggd?{query}", OUT / f"chart_{re.sub(r'[&=]', '_', query)}.txt", xhr=True)
    print("\n", query)
    if len(raw.strip()) < 8:
        print("  no history")
        return
    text = base64.b64decode(raw.strip()).decode("utf-8")
    for series in json.loads("".join(ROT[(ROT.index(c) + 47) % 94] if c in ROT else c for c in text)):
        pts = series.get("data", [])
        print(f"  {series.get('name')}: {len(pts)} prices")
        for p in pts:
            x, y = (p["x"], p["y"]) if isinstance(p, dict) else p[:2]
            print("   ", dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc).isoformat()[:16], "decimal", y)


def sitemap():
    t = get("/sitemap-events.xml", OUT / "sitemap-events.xml")
    locs = re.findall(r"<loc>([^<]*)</loc>", t)
    ufc = [u for u in locs if "/events/ufc" in u and "bjj" not in u]
    ids = sorted(int(u.rsplit("-", 1)[1]) for u in ufc if u.rsplit("-", 1)[1].isdigit())
    print(f"{len(locs)} event pages, {len(ufc)} UFC (ids {ids[0]}-{ids[-1]}); "
          f"lowest ids: {[u.rsplit('/', 1)[1] for u in ufc if u.endswith(('-1', '-2', '-3'))]}")


{"event": lambda: [event(s) for s in argv[1:]],
 "chart": lambda: [chart(q) for q in argv[1:]],
 "sitemap": sitemap}[argv[0]]()
