"""Which sportsbook betslip links does each book's iPhone app claim?

Matt, 2026-11-12: "The bet with a Sportsbook works, but it should pull up the
app not the website ... MGM link took me to the website." The app opens the
betslip link the odds feed stores (`picks.best_bet_link`). That https link
opens the book's app only if the app claims it in the host's
apple-app-site-association (AASA) file. Otherwise iOS opens Safari.

The sandbox cannot reach any book's host (proxy refusal / ENOTFOUND, measured
2026-11-12), so the worker runs this. For every host a stored link uses, it
fetches the AASA file from the host and from Apple's CDN (the copy iOS
actually installs). It prints the app ids and whether the stored link's
path and query match the file's rules. It writes nothing and makes no Odds
API call. The result is kept in `worker_jobs.result`.

    python -m scripts.book_app_links_probe
"""
from __future__ import annotations

import fnmatch
import json
import sys
from urllib.parse import parse_qsl, urlsplit

import requests

SUMMARY_MARK = "== SUMMARY =="
TIMEOUT = 20
_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
APPLE_CDN = "https://app-site-association.cdn-apple.com/a/v1/{host}"

# One stored link per book, copied from production `picks.best_bet_link`
# (query 2026-11-12, last 30 days). `{state}` is filled with each state below,
# because the host itself changes with the state.
STORED_LINKS: dict[str, str] = {
    "betmgm": "https://sports.{state}.betmgm.com/en/sports?options=19976337-1562536174-2307719716&type=Single",
    "betrivers": "https://{state}.betrivers.com/?page=sportsbook#event/1027397927?coupon=single|4372845443|",
    "draftkings": "https://sportsbook.draftkings.com/?outcomes=0HC84998421N1950_1",
    "fanduel": "https://sportsbook.fanduel.com/addToBetslip?marketId=42.579972737&selectionId=484735",
    "hardrockbet": "https://app.hardrock.bet/?deep_link_value=betslip/1006158484898709903",
    "williamhill_us": "https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=00089d98-6c2a-3493-920d-b8fdd3b7c660",
}
# Each book's fallback site (mobile/src/lib/sportsbookLinks.ts BOOK_APPS.web),
# which the app opens when it holds no link.
WEB_ROOTS: dict[str, str] = {
    "betmgm": "https://sports.betmgm.com/",
    "fanatics": "https://sportsbook.fanatics.com/",
    "betrivers": "https://www.betrivers.com/",
    "hardrockbet": "https://www.hardrock.bet/",
    "ballybet": "https://www.ballybet.com/",
    "betparx": "https://www.betparx.com/",
    "rebet": "https://play.rebet.app/",
}
STATES = ("nj", "pa", "mi", "az", "co", "il", "va", "ny")


def _install() -> None:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("book-app-links-probe")
    except Exception:  # noqa: BLE001
        pass


def _get(url: str):
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                            headers={"User-Agent": _UA, "Accept": "application/json"})
        return resp.status_code, resp.text, None
    except requests.RequestException as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def _pattern_match(pattern: str, value: str) -> bool:
    """AASA wildcards: `*` any run, `?` one character. Case-sensitive, as iOS."""
    return fnmatch.fnmatchcase(value, pattern)


def _component_matches(comp: dict, path: str, query: dict[str, str], fragment: str) -> bool:
    if "/" in comp and not _pattern_match(comp["/"], path):
        return False
    if "#" in comp and not _pattern_match(comp["#"], fragment):
        return False
    q = comp.get("?")
    if isinstance(q, str):
        raw = "&".join(f"{k}={v}" for k, v in query.items())
        if not _pattern_match(q, raw):
            return False
    elif isinstance(q, dict):
        for k, pat in q.items():
            if k not in query or not _pattern_match(pat, query[k]):
                return False
    return True


def link_verdict(aasa: dict, url: str) -> list[dict]:
    """For each app in the file: does it claim `url`? Pure.

    iOS reads the rules in order and the first match decides: a match on an
    `exclude` / `NOT ` rule means not claimed.
    """
    parts = urlsplit(url)
    path = parts.path or "/"
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    fragment = parts.fragment
    out: list[dict] = []
    for d in (aasa.get("applinks") or {}).get("details") or []:
        ids = d.get("appIDs") or ([d["appID"]] if d.get("appID") else [])
        claimed: bool | None = None
        rule = None
        if "components" in d:
            for comp in d["components"]:
                if _component_matches(comp, path, query, fragment):
                    claimed = not comp.get("exclude", False)
                    rule = comp
                    break
        elif "paths" in d:
            full = path + (f"?{parts.query}" if parts.query else "")
            for p in d["paths"]:
                neg = p.startswith("NOT ")
                pat = p[4:] if neg else p
                if _pattern_match(pat, path) or _pattern_match(pat, full):
                    claimed = not neg
                    rule = p
                    break
        out.append({"app_ids": ids, "claimed": bool(claimed), "rule": rule})
    return out


def _fetch_aasa(get, host: str) -> tuple[str, dict | None, str]:
    """Apple's CDN first (what the phone installs), then the host itself."""
    tried = []
    for url in (APPLE_CDN.format(host=host),
                f"https://{host}/.well-known/apple-app-site-association",
                f"https://{host}/apple-app-site-association"):
        status, body, err = get(url)
        if err or status != 200:
            tried.append(f"{url} -> {err or f'HTTP {status}'}")
            continue
        try:
            return url, json.loads(body), ""
        except ValueError:
            tried.append(f"{url} -> HTTP 200, not JSON: {body[:120]!r}")
    return "", None, " | ".join(tried)


def _targets() -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for book, link in STORED_LINKS.items():
        for state in (STATES if "{state}" in link else ("",)):
            seen.append((book, link.replace("{state}", state)))
    for book, root in WEB_ROOTS.items():
        seen.append((f"{book} (site)", root))
    return seen


def probe(get=_get) -> int:
    summary: list[str] = []
    cache: dict[str, tuple[str, dict | None, str]] = {}
    any_fetched = False
    for book, url in _targets():
        host = urlsplit(url).hostname or ""
        if host not in cache:
            cache[host] = _fetch_aasa(get, host)
            src, aasa, why = cache[host]
            print(f"--- {host}")
            if aasa is None:
                print(f"no AASA: {why}")
            else:
                any_fetched = True
                print(f"from {src}")
                print(json.dumps(aasa.get("applinks"), indent=1)[:6000])
        src, aasa, why = cache[host]
        if aasa is None:
            line = f"{book} {host}: NO AASA ({why[:160]})"
        else:
            verdicts = link_verdict(aasa, url)
            claimed = [v for v in verdicts if v["claimed"]]
            if claimed:
                line = (f"{book} {host}: CLAIMED by {claimed[0]['app_ids']} "
                        f"rule={json.dumps(claimed[0]['rule'])[:120]}")
            else:
                ids = [i for v in verdicts for i in v["app_ids"]]
                line = f"{book} {host}: NOT claimed (apps in file: {ids[:6]})"
        print(f"{line}  <- {url}")
        summary.append(line)

    print(SUMMARY_MARK)
    for line in summary:
        print(line)
    return 0 if any_fetched else 1


def main(argv: list[str] | None = None) -> int:
    _install()
    return probe()


if __name__ == "__main__":
    sys.exit(main())
