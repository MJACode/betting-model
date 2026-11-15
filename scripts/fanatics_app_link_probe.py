"""Which link puts a bet on the Fanatics Sportsbook app's slip?

Matt, 2026-11-15: Fanatics now opens its app (`fanaticssportsbook://`, a real
scheme: app_errors `handoff: fanatics -> scheme`, 18:14Z) but with no bet. The
odds feed sends no Fanatics link (0 of 566,588 current lines), only each
outcome's selection id (`odds.home_sid` etc.). A slip link could be built
from those ids if the format were known. No public documentation gives it,
and the sandbox cannot reach Fanatics, so the worker reads:

1. The App Store record (id1616738407): the app's bundle id.
2. The apple-app-site-association file of every host Fanatics might use, as
   Apple's CDN serves it: which paths the app claims.
3. Fanatics' website as an iPhone sees it: smart-banner / App Links meta tags
   and any `fanaticssportsbook://`, betslip or selection-id link in the page
   and its scripts.

Read only. Writes nothing, no Odds API call.

    python -m scripts.fanatics_app_link_probe
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from scripts.betmgm_app_link_probe import (
    ITUNES_LOOKUP, _get, _install, app_store_apps, custom_schemes, meta_tags,
    script_srcs, snippets,
)
from scripts.book_app_links_probe import _fetch_aasa

SUMMARY_MARK = "== SUMMARY =="
APP_STORE_ID = "1616738407"  # mobile/src/lib/sportsbookLinks.ts BOOK_APPS.fanatics.store
AASA_HOSTS = (
    "sportsbook.fanatics.com", "www.sportsbook.fanatics.com", "betfanatics.com",
    "www.betfanatics.com", "sportsbook.betfanatics.com", "fanatics.com",
    "www.fanatics.com", "link.sportsbook.fanatics.com", "links.sportsbook.fanatics.com",
    "app.sportsbook.fanatics.com", "ma.sportsbook.fanatics.com",
    "fanaticssportsbook.app.link", "fanatics-sportsbook.app.link",
    "betfanatics.app.link", "fanaticssportsbook.onelink.me", "betfanatics.onelink.me",
)
SITE_PAGES = (
    "https://sportsbook.fanatics.com/",
    "https://sportsbook.fanatics.com/sports",
    "https://betfanatics.com/",
)
NEEDLES = ("fanaticssportsbook", "betslip", "bet-slip", "selectionid", "selection_id",
           "selectionids", "deeplink", "deep_link", "deep-link", "app.link",
           "onelink", "app-argument", "apple-itunes-app", "universal")
MAX_SCRIPTS = 15


def probe(get=_get) -> int:
    summary: list[str] = []
    reached = False

    print("=== 1. App Store")
    status, body, err, _ = get(ITUNES_LOOKUP.format(id=APP_STORE_ID))
    if err or status != 200:
        print(f"lookup: {err or f'HTTP {status}'}")
        summary.append(f"app store id{APP_STORE_ID}: not read ({err or status})")
    else:
        reached = True
        apps = app_store_apps(json.loads(body))
        print(json.dumps(apps))
        for a in apps:
            summary.append(f"app store id{APP_STORE_ID} = {a['bundle_id']} ({a['name']})")

    print("\n=== 2. apple-app-site-association per host")
    aasa_get = lambda url: get(url)[:3]  # noqa: E731
    for host in AASA_HOSTS:
        src, aasa, why = _fetch_aasa(aasa_get, host)
        print(f"--- {host}")
        if aasa is None:
            print(f"no AASA: {why[:300]}")
            summary.append(f"aasa {host}: none")
            continue
        reached = True
        links = aasa.get("applinks") or {}
        print(f"from {src}")
        print(json.dumps(links, indent=1)[:5000])
        ids = [i for d in links.get("details") or []
               for i in (d.get("appIDs") or ([d["appID"]] if d.get("appID") else []))]
        rules = [json.dumps(d.get("components") or d.get("paths"))[:300]
                 for d in links.get("details") or []]
        summary.append(f"aasa {host}: apps={ids[:4]} rules={rules[:3]}")

    print("\n=== 3. Fanatics' website as an iPhone sees it")
    for url in SITE_PAGES:
        status, body, err, final = get(url)
        print(f"--- {url}")
        if err or status is None:
            print(f"not read: {err}")
            summary.append(f"site {url}: not read ({str(err)[:100]})")
            continue
        reached = True
        metas = meta_tags(body)
        print(f"HTTP {status}, final url {final}, {len(body)} bytes")
        print("meta:", json.dumps(metas, indent=1))
        print("custom schemes in page:", custom_schemes(body))
        for s in snippets(body, needles=NEEDLES):
            print("  page:", s)
        summary.append(f"site {url}: HTTP {status} final={final[:100]} meta={json.dumps(metas)[:300]}")
        for src in script_srcs(body, final)[:MAX_SCRIPTS]:
            s_status, s_body, s_err, _ = get(src)
            if s_err or s_status != 200:
                print(f"  script {src}: {s_err or s_status}")
                continue
            hits = snippets(s_body, needles=NEEDLES)
            schemes = custom_schemes(s_body)
            if hits or schemes:
                print(f"  script {src} ({len(s_body)} bytes)")
                print("    schemes:", schemes)
                for h in hits:
                    print("    ", h)
                for sch in schemes:
                    if "fanatics" in sch.lower():
                        summary.append(f"scheme in {urlsplit(src).path[-60:]}: {sch[:160]}")

    print(SUMMARY_MARK)
    for line in summary:
        print(line)
    return 0 if reached else 1


def main(argv: list[str] | None = None) -> int:
    _install()
    return probe()


if __name__ == "__main__":
    raise SystemExit(main())
