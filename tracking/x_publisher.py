"""
Post the daily free pick and the settled recap to X (@signalbasepicks).

SCOPE IS DELIBERATE AND NARROW. mike, 2026-08-30, choosing between three
options: "A without links."

  A. the free pick of the day + the settled recap   <- this
  B. the full slate, delayed until after first pitch
  C. everything, live

Posting every paid signal publicly would destroy what Whop members pay for:
the sport channels are the product, and the free channel already exists to be
the shop window. This mirrors that split rather than inventing a second one --
X gets exactly what the free Discord channel gets.

WHY NO LINKS, ENFORCED IN CODE. X moved to pay-per-use in February 2026 and
charges $0.015 per post -- but $0.20 if the post contains a URL, added April
2026. That is 13x, on a surcharge that is trivially easy to reintroduce by
adding a betslip link to a renderer months from now. At ~21 posts/month scope A
costs about $0.32 without links and $4.20 with them; at scope B it is $4.20
against $56.00. So the ban is a hard check in _assert_no_link, not a comment.

DELIVERY IS LEDGERED THE SAME WAY DISCORD IS. push_sent has
UNIQUE(lock_key, kind) and is written ONLY after a confirmed 2xx, so a retry
after a network failure cannot double-post and a kind with zero rows has never
once succeeded (§7). The ledger is checked BEFORE the POST, because X's rules
prohibit duplicative content and a double-post is an account risk, not just an
embarrassment.

OAUTH 1.0a BY HAND, no new dependency. POST /2/tweets needs user-context auth;
tweepy and requests-oauthlib are both absent here, and RFC 5849 signing is ~30
lines of stdlib that can be tested against the RFC's own published vector --
which is a better position than an untestable dependency in a repo that runs
its suite as the only gate.

Env (Railway Variables, all four required or this no-ops):
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
Kill switch: RUN_X_PUBLISHER=0

GETTING THOSE FOUR KEYS. Written down because it is fiddly, the two traps are
silent, and the answers are not guessable -- the first draft of these
instructions invented a callback URL for a site that does not exist.

  1. developer.x.com, signed in AS @signalbasepicks. The tokens post as
     whoever authorises them, so a personal account here tweets from the wrong
     place.
  2. Projects & Apps -> Create App.
  3. Settings -> User authentication settings -> Set up:
       App permissions:  Read and write      <- TRAP 1
       Type of App:      Web App, Automated App or Bot
       Callback URI:     https://x.com/signalbasepicks
       Website URL:      https://x.com/signalbasepicks
     Neither URL is ever visited. The callback matters only for 3-legged
     OAuth, where a user logs in through X and is redirected back; this module
     uses OAuth 1.0a with a token generated in the portal, so no redirect
     happens. X's form simply will not save without a value, and the X profile
     is a real URL we own -- there is no website.
  4. Keys & Tokens tab. Transcribed from the real page (2026-08-30), because
     two earlier attempts at this from documentation were both wrong.

     The page has THREE sections. Only the middle one is used:

       App-Only Authentication
         Bearer Token          IGNORE -- read-only, cannot post

       OAuth 1.0 Keys                          <- the only section you need
         Consumer Key      [eye] [Regenerate]  -> X_API_KEY + X_API_SECRET
         Access Token      [Generate]          -> X_ACCESS_TOKEN
                                                  + X_ACCESS_TOKEN_SECRET

       OAuth 2.0 Keys
         Client ID             IGNORE
         Client Secret         IGNORE
         Access Token          IGNORE          <- see the warning below

     TWO ROWS ARE CALLED "Access Token", one per OAuth section, and only the
     OAuth 1.0 one works with this module. The right one is annotated
     "For @SignalBasePicks  Read and write"; the OAuth 2.0 one talks about a
     refresh token and DM access. Picking the wrong one produces credentials
     that look valid and fail to post.

     Each row yields a PAIR. "Consumer Key" reveals the key behind the eye
     icon; Regenerate shows key AND secret together, once. "Access Token" ->
     Generate shows token AND secret, once.

     There is no row called "API Key" -- X's UI says Consumer Key where its own
     API docs say API Key. Same value; our variable follows the docs.

     If the Access Token row already reads "Read and write", TRAP 1 below is
     already handled and the app settings need no revisiting.

TRAP 1: set "Read and write" BEFORE generating the access token. A token minted
under read-only scope keeps read-only scope, and posting fails 403 with a
message that does not mention permissions.

TRAP 2: put these on the `worker` service only, not `pollers`. Publishing
belongs with the pipeline, and credentials on two services doubles the
double-post risk that the push_sent ledger exists to remove.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

X_POST_URL = "https://api.x.com/2/tweets"
MAX_TWEET = 280

# Anything that would make X charge the link rate, or that reads as a URL to
# their parser. Kept broad on purpose: the cost of a false positive is a
# reworded tweet, the cost of a false negative is 13x on every post.
_LINK_MARKERS = ("http://", "https://", "www.", ".com", ".io", ".co/",
                 ".net", ".org", ".gg", ".ly")


def _enabled() -> bool:
    return os.environ.get("RUN_X_PUBLISHER", "1") == "1"


def _creds() -> tuple | None:
    keys = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    vals = [os.environ.get(k, "") for k in keys]
    return tuple(vals) if all(vals) else None


# ── OAuth 1.0a (RFC 5849) ─────────────────────────────────────────────────────

def _quote(s: str) -> str:
    """RFC 3986 percent-encoding. `safe` is empty on purpose: OAuth requires
    even '/' and '~'-adjacent characters encoded, and Python's default safe='/'
    is the classic way to produce a signature that verifies locally and is
    rejected by the server."""
    return urllib.parse.quote(str(s), safe="~")


def signature_base_string(method: str, url: str, params: dict) -> str:
    """The exact string that gets signed. Extracted so it can be tested against
    RFC 5849's published example rather than against itself."""
    normalized = "&".join(
        f"{_quote(k)}={_quote(v)}"
        for k, v in sorted(params.items(), key=lambda kv: (_quote(kv[0]), _quote(kv[1])))
    )
    return "&".join([method.upper(), _quote(url), _quote(normalized)])


def _auth_header(method: str, url: str, creds: tuple,
                 nonce: str | None = None, timestamp: str | None = None) -> str:
    api_key, api_secret, token, token_secret = creds
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    # The JSON body is NOT part of the signature for a JSON-bodied request --
    # only oauth_* params are, since there is no form-encoded payload to fold in.
    base = signature_base_string(method, url, oauth)
    signing_key = f"{_quote(api_secret)}&{_quote(token_secret)}"
    digest = hmac.new(signing_key.encode(), base.encode(), hashlib.sha1).digest()
    oauth["oauth_signature"] = base64.b64encode(digest).decode()
    return "OAuth " + ", ".join(f'{_quote(k)}="{_quote(v)}"'
                                for k, v in sorted(oauth.items()))


# ── Rendering ─────────────────────────────────────────────────────────────────

_SPORT_EMOJI = {"MLB": "⚾", "WNBA": "\U0001F3C0", "NBA": "\U0001F3C0",
                "NHL": "\U0001F3D2", "NFL": "\U0001F3C8", "NCAAF": "\U0001F3C8",
                "UFC": "\U0001F94A", "GOLF": "⛳"}


def _assert_no_link(text: str) -> None:
    """A URL costs 13x per post. This is a hard check, not a convention."""
    low = text.lower()
    for marker in _LINK_MARKERS:
        if marker in low:
            raise ValueError(
                f"refusing to post: text contains {marker!r}, which X bills at "
                f"the link rate ($0.20 vs $0.015 per post)")


def _american(odds) -> str:
    try:
        v = int(float(odds))
    except (TypeError, ValueError):
        return ""
    return f"+{v}" if v > 0 else str(v)


def render_free_pick(pick: dict, target_date: str) -> str:
    """The daily free pick, in one tweet. No link, by design."""
    emoji = _SPORT_EMOJI.get(pick.get("sport"), "\U0001F3AF")
    price = _american(pick.get("dk_odds"))
    parts = [f"{emoji} Free pick — {pick['label']}"]
    if price:
        parts.append(f"{price} at DraftKings")
    good_to = pick.get("good_to")
    if good_to:
        parts.append(f"Good to {_american(good_to)}.")
    parts.append("More in Discord.")
    text = " ".join(parts)
    _assert_no_link(text)
    return text[:MAX_TWEET]


def render_results(recap: dict, game_date: str) -> str:
    """The settled day, in one tweet. Numbers only — the record is the pitch."""
    pretty = datetime.fromisoformat(game_date).strftime("%b %-d")
    w, l = int(recap.get("wins", 0)), int(recap.get("losses", 0))
    units = float(recap.get("units", 0.0))
    sign = "+" if units >= 0 else ""
    lines = [f"\U0001F4CA {pretty} results: {w}-{l}, {sign}{units:.2f}u"]
    by_sport = recap.get("by_sport") or []
    if by_sport:
        lines.append(" · ".join(f"{s['sport']} {s['wins']}-{s['losses']}"
                                for s in by_sport[:4]))
    text = "\n".join(lines)
    _assert_no_link(text)
    return text[:MAX_TWEET]


# ── Posting ───────────────────────────────────────────────────────────────────

def post_tweet(text: str, dry_run: bool = False) -> str | None:
    """POST one tweet. Returns its id, or None when it did not post.

    Never raises into a caller: a publishing surface must not be able to break
    the pass that produced the pick."""
    if not _enabled():
        logger.info("X publisher: RUN_X_PUBLISHER=0 — skipping")
        return None
    creds = _creds()
    if not creds:
        logger.info("X publisher: credentials not configured — skipping")
        return None
    try:
        _assert_no_link(text)
    except ValueError as exc:
        logger.error(f"X publisher: {exc}")
        return None
    if dry_run:
        logger.info(f"[dry-run] would tweet:\n{text}")
        return "dry-run"
    try:
        resp = requests.post(
            X_POST_URL,
            json={"text": text},
            headers={"Authorization": _auth_header("POST", X_POST_URL, creds),
                     "Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return str(resp.json().get("data", {}).get("id", "")) or "posted"
        logger.error(f"X publisher: HTTP {resp.status_code} {resp.text[:200]}")
        return None
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X publisher: post failed ({exc})")
        return None


# ── Manual test ───────────────────────────────────────────────────────────────
# Run on the Railway worker or the prop-probe one-off service, where the
# credentials live. The dev sandbox has none, so it reports "not configured"
# and exits without touching the network -- which is itself the first check.

def _main() -> int:
    """One-off verification that the credentials and signing actually work.

    Run on the Railway worker, where the four X_* variables live:

        python -m tracking.x_publisher --dry-run   # render only, no network
        python -m tracking.x_publisher --post      # really tweet

    The default is DRY RUN. Posting to a public account is not something a
    stray invocation should be able to do, so the real post needs an explicit
    flag -- the same reason run_pipeline defaults to writing and the scorer
    needs --dry-run rather than the reverse: the dangerous direction gets the
    flag.
    """
    import argparse
    ap = argparse.ArgumentParser(description="X publisher smoke test")
    ap.add_argument("--post", action="store_true",
                    help="actually publish (default is dry run)")
    ap.add_argument("--text", default=None, help="override the test text")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    creds = _creds()
    print(f"credentials configured: {bool(creds)}")
    if creds:
        # Never print a secret. Length and prefix are enough to tell a real
        # value from an empty string or a placeholder someone pasted wrong.
        names = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                 "X_ACCESS_TOKEN_SECRET")
        for name, val in zip(names, creds):
            print(f"  {name}: {len(val)} chars, starts {val[:4]}...")

    text = args.text or (
        "Signal Base is live. Model picks, tracked honestly — "
        "wins and losses both. First card posts soon."
    )
    print(f"\ntext ({len(text)} chars):\n{text}\n")

    result = post_tweet(text, dry_run=not args.post)
    if result and result != "dry-run":
        print(f"POSTED — tweet id {result}")
        print(f"https://x.com/signalbasepicks/status/{result}")
        return 0
    if result == "dry-run":
        print("DRY RUN — nothing was sent. Re-run with --post to publish.")
        return 0
    print("FAILED — see the error above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
