"""What Dunks & Threes shows without an account (mike, 2026-11-27: "I don't want to buy
without testing"). Read-only: a handful of GETs, one per page, logged; writes nothing.

Runs on the worker (the sandbox cannot resolve dunksandthrees.com):
    python -m scripts.research_probe_dnt_free
Every line starts "DNT|" so the Railway log filter finds it.
"""
from __future__ import annotations

import json
import re
import time

import requests

BASE = "https://dunksandthrees.com"
UA = {"User-Agent": "Mozilla/5.0 (research probe)", "Accept": "text/html,application/json"}

PAGES = [
    "/", "/epm", "/epm?date=2025-01-15", "/predictions", "/predictions?date=2025-01-15",
    "/teams", "/stats",
    # SvelteKit serves a page's data at <path>/__data.json: shows what the free payload holds
    "/epm/__data.json", "/predictions/__data.json", "/__data.json",
]
API = ["/api/v2/epm?date=2025-12-02", "/api/v2/game-predictions?date=2025-12-02",
       "/api/v2/game-predictions-box?date=2025-12-02"]
WORDS = ("subscribe", "premium", "login", "locked", "upgrade", "trial", "refund", "free",
         "box score", "boxscore", "projection", "minutes", "pts")


def text_of(html: str) -> str:
    html = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def log(*parts) -> None:
    print("DNT|" + "|".join(str(p) for p in parts), flush=True)


def page(path: str, s: requests.Session) -> str:
    try:
        r = s.get(BASE + path, headers=UA, timeout=30)
    except Exception as exc:  # noqa: BLE001
        log(path, "ERROR", repr(exc))
        return ""
    body = r.text
    log(path, "HTTP", r.status_code, "type", r.headers.get("content-type"), "len", len(body))
    if "json" in (r.headers.get("content-type") or ""):
        log(path, "json head", body[:1500])
        keys = sorted(set(re.findall(r'"([a-z_]{3,30})"\s*:', body)))[:120]
        log(path, "json keys", json.dumps(keys))
        return body
    t = text_of(body)
    cut = t.find("Next slide")
    main = t[cut + 10:] if cut >= 0 else t
    log(path, "text", main[:1800])
    log(path, "words", json.dumps({w: t.lower().count(w) for w in WORDS}))
    log(path, "numbers", len(re.findall(r"[-+]?\d+\.\d", main)))
    links = sorted(set(re.findall(r'href="(/[^"#]{1,120})"', body)))
    log(path, "links", json.dumps([u for u in links if not u.startswith("/_app")][:80]))
    return body


def main() -> None:
    s = requests.Session()
    game_links: list[str] = []
    for p in PAGES:
        body = page(p, s)
        game_links += re.findall(r'href="(/(?:game|games|predictions)/[^"#]{3,120})"', body)
        time.sleep(1.5)
    for g in sorted(set(game_links))[:3]:       # one game page: are its box-score predictions free?
        page(g, s)
        page(g.rstrip("/") + "/__data.json", s)
        time.sleep(1.5)
    for a in API:                                # no key: confirm 401, read the error
        try:
            r = s.get(BASE + a, headers={"Accept": "application/json"}, timeout=30)
            log(a, "HTTP", r.status_code, "body", r.text[:300])
        except Exception as exc:  # noqa: BLE001
            log(a, "ERROR", repr(exc))
        time.sleep(1.5)
    log("done")


if __name__ == "__main__":
    main()
