"""Which link puts a bet on the BetMGM app's slip? Read BetMGM's own sources.

Matt, 2026-11-15: the hand-off now opens the BetMGM app, by its URL scheme
`betmgmsports://` (measured: app_errors `handoff: betmgm -> scheme`, his
phone, build 14301), but the bet is not on the slip. iOS refused the
universal link `https://sports.ma.betmgm.com/en/sportsapp/sports?options=...`
although the host's apple-app-site-association file claims `/*/sportsapp/*`
for one app id, `CB3Y69STL7.com.playmgm.nj.sports2` (worker job 1342184).

Three things decide the fix, and the sandbox can reach none of them (proxy
refusal / ENOTFOUND for every betmgm.com host, 2026-11-12 and 2026-11-15), so
the worker runs this:

1. The App Store record for the BetMGM app (id1430875409) and every app
   named BetMGM: their bundle ids. If the app a member installs is not the
   one the AASA file names, iOS will never route a universal link to it.
2. BetMGM's deep-link documentation (sportsapi.<state>.betmgm.com/restapi),
   as text, with every example link.
3. BetMGM's own website as an iPhone sees it: the smart-banner and App Links
   meta tags and every custom-scheme or `sportsapp` reference in the page and
   its scripts. That is the link BetMGM itself uses to hand a web visitor's
   slip to the app.

Read only. Writes nothing, no Odds API call. Result kept in
`worker_jobs.result`.

    python -m scripts.betmgm_app_link_probe
"""
from __future__ import annotations

import html as _html
import json
import re
from urllib.parse import urljoin, urlsplit

import requests

SUMMARY_MARK = "== SUMMARY =="
TIMEOUT = 20
_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")

AASA_APP_ID = "CB3Y69STL7.com.playmgm.nj.sports2"
APP_STORE_IDS = ("1430875409",)  # mobile/src/lib/sportsbookLinks.ts BOOK_APPS.betmgm.store
ITUNES_LOOKUP = "https://itunes.apple.com/lookup?id={id}&country=us"
ITUNES_SEARCH = "https://itunes.apple.com/search?term=betmgm&entity=software&country=us&limit=25"

DOC_PAGES = (
    "https://sportsapi.nj.betmgm.com/restapi/deeplinking.html",
    "https://sportsapi.nj.betmgm.com/restapi/elementsdeeplink.html",
    "https://sportsapi.nj.betmgm.com/restapi/generatedeeplink.html",
    "https://sportsapi.nj.betmgm.com/restapi/affiliatehelper.html",
)
# A live selection (Ohio State ML, 2026-11-21, picks.best_bet_link) on the
# state Matt bets from, as stored and as the hand-off rewrites it.
SITE_PAGES = (
    "https://sports.ma.betmgm.com/en/sports?options=6:49561-4449666-7262097&type=Single",
    "https://sports.ma.betmgm.com/en/sportsapp/sports?options=6:49561-4449666-7262097&type=Single",
)
NEEDLES = ("betmgmsports", "sportsapp", "app-argument", "universal", "deeplink",
           "deep_link", "openApp", "open-app", "itms-apps", "apple-itunes-app")
MAX_SCRIPTS = 12
SNIPPET = 140


def _install() -> None:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("betmgm-app-link-probe")
    except Exception:  # noqa: BLE001
        pass


def _get(url: str):
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                            headers={"User-Agent": _UA})
        return resp.status_code, resp.text, None, resp.url
    except requests.RequestException as exc:
        return None, "", f"{type(exc).__name__}: {exc}", url


def app_store_apps(payload: dict) -> list[dict]:
    """bundleId, name and store id for each app in an iTunes lookup/search. Pure."""
    out = []
    for r in payload.get("results") or []:
        if r.get("bundleId"):
            out.append({"track_id": r.get("trackId"), "name": r.get("trackName"),
                        "bundle_id": r.get("bundleId"), "seller": r.get("sellerName")})
    return out


def meta_tags(page: str) -> dict[str, str]:
    """App-handoff meta tags: smart banner, App Links, Twitter app cards. Pure."""
    out: dict[str, str] = {}
    for tag in re.findall(r"<meta\b[^>]*>", page, flags=re.I):
        name = re.search(r"\b(?:name|property)\s*=\s*[\"']([^\"']+)[\"']", tag, flags=re.I)
        content = re.search(r"\bcontent\s*=\s*[\"']([^\"']*)[\"']", tag, flags=re.I)
        if not name or not content:
            continue
        key = name.group(1).lower()
        if key == "apple-itunes-app" or key.startswith("al:") or key.startswith("twitter:app"):
            out[key] = _html.unescape(content.group(1))
    return out


def custom_schemes(text: str) -> list[str]:
    """Distinct non-web URL schemes written out in the text (`x://...`). Pure."""
    found = re.findall(r"\b([a-z][a-z0-9+.-]{2,40})://[^\s\"'<>)]{0,160}", text, flags=re.I)
    full = re.findall(r"\b[a-z][a-z0-9+.-]{2,40}://[^\s\"'<>)]{0,160}", text, flags=re.I)
    keep = []
    for scheme, url in zip(found, full):
        if scheme.lower() in ("http", "https", "ws", "wss", "data", "blob", "file"):
            continue
        if url not in keep:
            keep.append(url)
    return keep[:40]


def snippets(text: str, needles=NEEDLES, width: int = SNIPPET, cap: int = 30) -> list[str]:
    """Each needle's surrounding text, deduplicated, capped. Pure."""
    out: list[str] = []
    low = text.lower()
    for n in needles:
        start = 0
        hits = 0
        while hits < 6:
            i = low.find(n.lower(), start)
            if i < 0:
                break
            s = " ".join(text[max(0, i - width): i + len(n) + width].split())
            if s not in out:
                out.append(s)
            start = i + len(n)
            hits += 1
        if len(out) >= cap:
            break
    return out[:cap]


def visible_text(page: str) -> str:
    """Tags stripped, scripts and styles dropped, whitespace collapsed. Pure."""
    page = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", page, flags=re.I | re.S)
    page = re.sub(r"<br\s*/?>|</p>|</li>|</tr>|</h\d>", "\n", page, flags=re.I)
    page = re.sub(r"<[^>]+>", " ", page)
    page = _html.unescape(page)
    return "\n".join(" ".join(line.split()) for line in page.splitlines() if line.strip())


def script_srcs(page: str, base: str) -> list[str]:
    srcs = re.findall(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", page, flags=re.I)
    return [urljoin(base, s) for s in srcs][:MAX_SCRIPTS]


def probe(get=_get) -> int:
    summary: list[str] = []
    reached = False

    print("=== 1. App Store: which app is BetMGM's, by bundle id")
    store_ids: list[str] = []
    for sid in APP_STORE_IDS:
        status, body, err, _ = get(ITUNES_LOOKUP.format(id=sid))
        if err or status != 200:
            print(f"lookup id{sid}: {err or f'HTTP {status}'}")
            summary.append(f"app store id{sid}: not read ({err or status})")
            continue
        reached = True
        apps = app_store_apps(json.loads(body))
        print(f"lookup id{sid}: {json.dumps(apps)}")
        for a in apps:
            store_ids.append(a["bundle_id"])
            named = AASA_APP_ID.split(".", 1)[1] == a["bundle_id"]
            summary.append(f"app store id{sid} = {a['bundle_id']} ({a['name']}); "
                           f"AASA names {AASA_APP_ID}: {'SAME app' if named else 'DIFFERENT app'}")
    status, body, err, _ = get(ITUNES_SEARCH)
    if not err and status == 200:
        reached = True
        apps = [a for a in app_store_apps(json.loads(body))
                if "mgm" in (a["name"] or "").lower() or "mgm" in (a["bundle_id"] or "").lower()]
        print(f"search 'betmgm': {json.dumps(apps, indent=1)}")
        summary.append("betmgm apps on the store: " + "; ".join(
            f"{a['name']} = {a['bundle_id']}" for a in apps)[:600])
    else:
        print(f"search: {err or f'HTTP {status}'}")

    print("\n=== 2. BetMGM deep-link documentation")
    for url in DOC_PAGES:
        status, body, err, final = get(url)
        print(f"--- {url}")
        if err or status != 200:
            print(f"not read: {err or f'HTTP {status}'}")
            summary.append(f"doc {urlsplit(url).path}: not read ({err or status})")
            continue
        reached = True
        text = visible_text(body)
        print(text[:6000])
        links = sorted(set(re.findall(r"[a-z][a-z0-9+.-]*://[^\s\"'<>)]+", body, flags=re.I)))
        print("links on page:", json.dumps([l for l in links if "betmgm" in l or "options=" in l][:40], indent=1))
        print("custom schemes:", custom_schemes(body))
        summary.append(f"doc {urlsplit(url).path}: read, {len(text)} chars; schemes={custom_schemes(body)[:5]}")

    print("\n=== 3. BetMGM's website as an iPhone sees it")
    for url in SITE_PAGES:
        status, body, err, final = get(url)
        print(f"--- {url}")
        if err or status is None:
            print(f"not read: {err}")
            summary.append(f"site {urlsplit(url).path}: not read ({err})")
            continue
        reached = True
        metas = meta_tags(body)
        print(f"HTTP {status}, final url {final}, {len(body)} bytes")
        print("meta:", json.dumps(metas, indent=1))
        print("custom schemes in page:", custom_schemes(body))
        for s in snippets(body):
            print("  page:", s)
        summary.append(f"site {urlsplit(url).path}: HTTP {status} final={final[:120]} meta={json.dumps(metas)[:300]}")
        for src in script_srcs(body, final):
            s_status, s_body, s_err, _ = get(src)
            if s_err or s_status != 200:
                print(f"  script {src}: {s_err or s_status}")
                continue
            hits = snippets(s_body)
            schemes = custom_schemes(s_body)
            if hits or schemes:
                print(f"  script {src} ({len(s_body)} bytes)")
                print("    schemes:", schemes)
                for h in hits:
                    print("    ", h)
                for sch in schemes:
                    if "betmgm" in sch.lower():
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
