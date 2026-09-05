"""
Fetch the @signalbasepicks X profile image (and banner) into Supabase.

WHY THIS EXISTS
---------------
matt, 2026-09-03: "Use this logo link to update the logo and color patterns in
the app" — the link being the X profile. The dev sandbox cannot reach x.com,
pbs.twimg.com, or any of the avatar mirrors (every CONNECT is refused by the
egress proxy), and Supabase Storage holds no brand assets. The Railway worker
has open egress, so the image is fetched THERE and parked in Postgres, where
the read-only Supabase MCP can read it back as base64 (CLAUDE.md §1b: the
sandbox's limits are not the system's; extracted data belongs in Supabase).

Run on the worker:   python -m scripts.fetch_brand_avatar
                     (prop-probe: point its start command here, watch this
                     file, connect the branch -- the service skips builds
                     for pushes that touch nothing on its watch list.)
Read it back:        SELECT key, content_type, byte_len, sha256 FROM brand_assets;
                     SELECT bytes_b64 FROM brand_assets WHERE key = 'x_avatar';

Idempotent — re-running overwrites the row for each key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone

import requests

HANDLE = "signalbasepicks"

# The worker already holds the account's own OAuth 1.0a keys (tracking/
# x_publisher.py posts with them), so the first source is X itself rather than
# a third-party mirror. The publisher's header helper signs only oauth_* params
# (correct for its JSON-bodied POST); a GET with a query string must fold the
# query params into the signature base, so the signing is done here.
X_USER_URL = f"https://api.x.com/2/users/by/username/{HANDLE}"
X_USER_FIELDS = {"user.fields": "profile_image_url,profile_banner_url,name,description"}


def _x_api_profile() -> tuple[str | None, str | None] | None:
    from tracking.x_publisher import _creds, _quote, signature_base_string

    creds = _creds()
    if not creds:
        print("x_api: no X_* credentials in the environment")
        return None
    api_key, api_secret, token, token_secret = creds
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    base = signature_base_string("GET", X_USER_URL, {**oauth, **X_USER_FIELDS})
    key = f"{_quote(api_secret)}&{_quote(token_secret)}"
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    header = "OAuth " + ", ".join(f'{_quote(k)}="{_quote(v)}"'
                                  for k, v in sorted(oauth.items()))
    try:
        r = requests.get(X_USER_URL, params=X_USER_FIELDS, timeout=TIMEOUT,
                         headers={"Authorization": header, **UA})
        print(f"x_api: {r.status_code} {r.text[:300]}")
        if r.status_code != 200:
            return None
        data = r.json().get("data", {})
    except (requests.RequestException, ValueError) as exc:
        print(f"x_api: {exc}")
        return None
    return data.get("profile_image_url"), data.get("profile_banner_url")
UA = {"User-Agent": "Mozilla/5.0 (compatible; signalbase-brand-fetch/1.0)"}
TIMEOUT = 30

# Public, unauthenticated profile lookups, in order of preference. Each returns
# JSON with the profile image URL somewhere inside; `pick` pulls it out.
PROFILE_SOURCES = [
    ("fxtwitter",
     f"https://api.fxtwitter.com/{HANDLE}",
     lambda j: (j.get("user", {}).get("avatar_url"),
                j.get("user", {}).get("banner_url"))),
    ("syndication",
     "https://cdn.syndication.twimg.com/widgets/followbutton/info.json"
     f"?screen_names={HANDLE}",
     lambda j: ((j[0] if isinstance(j, list) and j else {}).get("profile_image_url_https"),
                None)),
]

# Direct image mirrors, used only if every profile lookup fails.
IMAGE_FALLBACKS = [
    f"https://unavatar.io/x/{HANDLE}?fallback=false",
    f"https://unavatar.io/twitter/{HANDLE}?fallback=false",
]

_SIZE_SUFFIX = re.compile(r"_(normal|bigger|mini|200x200|400x400|x96)(?=\.[a-z]+$)", re.I)


def _original_size(url: str) -> list[str]:
    """pbs.twimg.com serves `_normal` (48px) by default; the un-suffixed path
    is the original upload, `_400x400` the largest guaranteed variant."""
    if not url:
        return []
    variants = [_SIZE_SUFFIX.sub("", url), _SIZE_SUFFIX.sub("_400x400", url), url]
    seen, out = set(), []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _get_image(url: str) -> tuple[bytes, str] | None:
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  {url} -> {exc}")
        return None
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        print(f"  {url} -> {r.status_code} {ctype}")
        return None
    print(f"  {url} -> {r.status_code} {ctype} {len(r.content)} bytes")
    return r.content, ctype


def discover() -> dict[str, str]:
    """Return {'x_avatar': url, 'x_banner': url} for whatever was found."""
    found: dict[str, str] = {}
    direct = _x_api_profile()
    if direct:
        avatar, banner = direct
        if avatar:
            found["x_avatar"] = avatar
        if banner:
            found["x_banner"] = banner
        if "x_avatar" in found:
            return found
    for name, url, pick in PROFILE_SOURCES:
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            print(f"{name}: {r.status_code}")
            if r.status_code != 200:
                continue
            avatar, banner = pick(r.json())
        except (requests.RequestException, ValueError) as exc:
            print(f"{name}: {exc}")
            continue
        if avatar and "x_avatar" not in found:
            found["x_avatar"] = avatar
        if banner and "x_banner" not in found:
            found["x_banner"] = banner
        if "x_avatar" in found:
            break
    return found


def fetch_all() -> dict[str, tuple[bytes, str, str]]:
    """{key: (bytes, content_type, source_url)}"""
    out: dict[str, tuple[bytes, str, str]] = {}
    urls = discover()
    print("discovered:", json.dumps(urls))

    for key, url in urls.items():
        for candidate in _original_size(url):
            got = _get_image(candidate)
            if got:
                out[key] = (got[0], got[1], candidate)
                break

    if "x_avatar" not in out:
        print("profile lookups failed; trying image mirrors")
        for candidate in IMAGE_FALLBACKS:
            got = _get_image(candidate)
            if got:
                out["x_avatar"] = (got[0], got[1], candidate)
                break
    return out


DDL = """
CREATE TABLE IF NOT EXISTS brand_assets (
    key          TEXT PRIMARY KEY,
    source_url   TEXT NOT NULL,
    content_type TEXT NOT NULL,
    byte_len     INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    bytes_b64    TEXT NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def store(assets: dict[str, tuple[bytes, str, str]]) -> None:
    from data.anon_readable import API_ROLES, lock_down
    from data.db import get_connection
    from data.ddl_guard import schema_is_current

    conn = get_connection()
    try:
        # Gate the DDL (CLAUDE.md §7: every write-time ensure block fires a
        # PostgREST schema reload; IF NOT EXISTS does not make it free).
        # rls=True joined revoked_from= on 2026-09-04: without it this returns
        # True on a database where brand_assets exists but has no RLS, and the
        # lock_down() below never runs.
        if not schema_is_current(conn, "brand_assets", columns=("bytes_b64",),
                                 rls=True, revoked_from=API_ROLES):
            conn.execute(DDL)
            # New object in public: REVOKE from anon/authenticated BY NAME, then
            # RLS as the second lock. lock_down() carries its own catalog gate.
            lock_down(conn, "brand_assets")
            conn.commit()
        for key, (blob, ctype, url) in assets.items():
            conn.execute("""
                INSERT INTO brand_assets
                    (key, source_url, content_type, byte_len, sha256, bytes_b64, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    source_url = EXCLUDED.source_url,
                    content_type = EXCLUDED.content_type,
                    byte_len = EXCLUDED.byte_len,
                    sha256 = EXCLUDED.sha256,
                    bytes_b64 = EXCLUDED.bytes_b64,
                    fetched_at = EXCLUDED.fetched_at
            """, (key, url, ctype, len(blob), hashlib.sha256(blob).hexdigest(),
                  base64.b64encode(blob).decode("ascii"),
                  datetime.now(timezone.utc)))
            print(f"stored {key}: {len(blob)} bytes {ctype} from {url}")
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    assets = fetch_all()
    if not assets:
        print("FAILED: no image reachable from any source")
        return 1
    store(assets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
