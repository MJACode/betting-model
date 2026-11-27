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


def hydrate(data: list, i: int, seen=None):
    """SvelteKit's __data.json is `devalue`-encoded: values are indices into one flat array."""
    if i < 0:
        return None                                  # -1 undefined, -3 NaN, ... : none matter here
    v = data[i]
    if isinstance(v, dict):
        return {k: hydrate(data, j) for k, j in v.items()}
    if isinstance(v, list):
        if v and isinstance(v[0], str) and v[0] in ("Date", "Set", "Map", "BigInt", "RegExp"):
            return v[1] if len(v) > 1 else None
        return [hydrate(data, j) for j in v]
    return v


def decoded(body: str) -> list:
    out = []
    for node in json.loads(body).get("nodes") or []:
        if isinstance(node, dict) and node.get("type") == "data" and node.get("data"):
            out.append(hydrate(node["data"], 0))
    return out


def walk(x, path="", found=None):
    """Every dict that has a p_* key: where it sits, and one example."""
    found = {} if found is None else found
    if isinstance(x, dict):
        pk = sorted(k for k in x if k.startswith("p_"))
        if pk and path not in found:
            found[path] = {k: x[k] for k in list(x)[:60]}
        for k, v in x.items():
            walk(v, f"{path}.{k}", found)
    elif isinstance(x, list):
        for v in x[:3]:
            walk(v, f"{path}[]", found)
    return found


def decode_games() -> None:
    s = requests.Session()
    for gid in ("22301000", "22401168", "22501115"):
        r = s.get(f"{BASE}/games/{gid}/__data.json", headers=UA, timeout=30)
        log("decode", gid, "HTTP", r.status_code, "len", len(r.text))
        try:
            nodes = decoded(r.text)
        except Exception as exc:  # noqa: BLE001
            log("decode", gid, "ERROR", repr(exc), r.text[:300])
            continue
        for n, node in enumerate(nodes):
            if isinstance(node, dict):
                log("decode", gid, "node", n, "keys", json.dumps(sorted(node)[:80]))
                for k in ("has_access", "has_custom", "game_info"):
                    if k in node:
                        log("decode", gid, "node", n, k, json.dumps(node[k], default=str)[:1500])
        for path, ex in walk(nodes).items():
            log("decode", gid, "p_dict", path, json.dumps(ex, default=str)[:2500])
        time.sleep(1.5)
    log("done")


def main() -> None:
    import sys
    if "--decode" in sys.argv:
        decode_games()
        return
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
