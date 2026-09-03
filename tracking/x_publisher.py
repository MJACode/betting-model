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

TRAP 2: put these on the `worker` service only, not `pollers` (see below). Publishing
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


# ── Reach ─────────────────────────────────────────────────────────────────────
# Two hashtags, never three, and both chosen rather than generic.
#
# Measured behaviour of the 2026 algorithm, not folklore: 1-2 hashtags carry
# about +21% engagement, and 3 or more actively TRIP SPAM FILTERS and cut reach.
# So the cap is a hard slice, not a style guide -- a third tag makes a post
# perform worse than no tags at all.
#
# One sport tag (the niche the post belongs to) plus one community tag. Generic
# tags like #betting or #sports are explicitly avoided: they are the ones the
# ranker treats as noise, and they compete with the entire platform rather than
# putting the post in front of people who follow this subject.
_SPORT_TAG = {"MLB": "#MLB", "WNBA": "#WNBA", "NBA": "#NBA", "NHL": "#NHL",
              "NFL": "#NFL", "NCAAF": "#CFB", "UFC": "#UFC", "GOLF": "#PGA"}
_COMMUNITY_TAG = "#GamblingTwitter"
MAX_HASHTAGS = 2


def hashtags_for(sport: str | None) -> str:
    """At most two tags: the sport's own, plus the community one."""
    tags = []
    tag = _SPORT_TAG.get((sport or "").upper())
    if tag:
        tags.append(tag)
    tags.append(_COMMUNITY_TAG)
    return " ".join(tags[:MAX_HASHTAGS])


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
    """The daily free pick, in one tweet. No link, by design.

    IT NAMES THE CHEAPER BOOK WHEN THERE IS ONE. mike, 2026-09-03: "Yes @ book
    line." This tweet and the free Discord card published the DraftKings price
    with no alternative while the paid channels named one, so the same pick
    reached three surfaces carrying three different amounts of information —
    and the two public ones carried the least. A shop window showing a worse
    number than the shop is a strange thing to have built.

    The book NAME is not a link and does not trip the link rate: `_assert_no_link`
    still runs over the finished text, and "BetMGM" contains no marker it looks
    for. The clause is DROPPED rather than truncated when the tweet would
    overflow — a half-written price is worse than none, and the pick itself is
    the post.
    """
    emoji = _SPORT_EMOJI.get(pick.get("sport"), "\U0001F3AF")
    price = _american(pick.get("dk_odds"))
    parts = [f"{emoji} Free pick — {pick['label']}"]
    if price:
        parts.append(f"{price} at DraftKings")
    good_to = pick.get("good_to")
    if good_to:
        parts.append(f"Good to {_american(good_to)}.")
    parts.append("More in Discord.")
    parts.append(hashtags_for(pick.get("sport")))

    better = _better_price_clause(pick)
    if better:
        # After the DK price, so a reader sees the decision price first and the
        # shopping tip second — the same order the Discord card uses.
        at = 2 if price else 1
        candidate = parts[:at] + [better] + parts[at:]
        if len(" ".join(p for p in candidate if p)) <= MAX_TWEET:
            parts = candidate

    text = " ".join(p for p in parts if p)
    _assert_no_link(text)
    return text[:MAX_TWEET]


_BOOK_DISPLAY = {
    "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars",
    "espnbet": "ESPN BET", "fanatics": "Fanatics", "betrivers": "BetRivers",
    "hardrockbet": "Hard Rock Bet", "ballybet": "Bally Bet",
    "betparx": "betPARX", "rebet": "ReBet",
}


def _better_price_clause(pick: dict) -> str | None:
    """"(-120 at BetMGM)" when another BETTABLE book beats the decision price.

    Deliberately the same three conditions the Discord card applies
    (tracking/discord_notifier.better_price_note): a book must be recorded, it
    must not be DraftKings, and it must be STRICTLY better. Publishing "also
    -110 at DraftKings" beside "-110" is noise, and publishing a worse price as
    an alternative is actively misleading.

    The book set is already filtered upstream — config.BEST_LINE_BOOKMAKERS
    excludes books that cannot be bet from the US — so this never names Pinnacle
    to a public audience that could not act on it.
    """
    best = pick.get("best_odds")
    book = (pick.get("best_book") or "").strip().lower()
    if best is None or not book or book == "draftkings":
        return None
    try:
        dk = float(pick.get("dk_odds"))
        alt = float(best)
    except (TypeError, ValueError):
        return None

    def _decimal(a: float) -> float:
        return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))

    if _decimal(alt) <= _decimal(dk) + 1e-9:
        return None
    return f"({_american(alt)} at {_BOOK_DISPLAY.get(book, book)})"


def render_results(recap: dict, game_date: str) -> str:
    """The settled day, in one tweet. Numbers only — the record is the pitch.

    THE HEADLINE MUST MATCH THE DISCORD RECAP EXACTLY. mike, 2026-09-02:
    "needs to be the same and fired at the same time." Two surfaces publishing
    two different records for one day is worse than one publishing none —
    whichever is read second makes the first a lie. So the record here carries
    PUSHES (2026-08-31 settled 14-14-1 and this printed 14-14), ROI is stated
    because the embed states it, and the per-sport split is populated from the
    same rows the embed groups rather than being passed an empty list forever.

    The all-time block stays Discord-only: it does not fit inside a tweet, and
    omitting a section is not the same as contradicting one.

    `%-d` is a glibc extension — valid on the Railway worker, a ValueError on
    Windows, which is the machine this repo's only quality gate runs on (§7).
    Same zero-strip the Discord embed uses.
    """
    pretty = datetime.fromisoformat(game_date).strftime("%b %d").replace(" 0", " ")
    w, l = int(recap.get("wins", 0)), int(recap.get("losses", 0))
    pushes = int(recap.get("pushes", 0))
    rec = f"{w}-{l}" + (f"-{pushes}" if pushes else "")
    units = float(recap.get("units", 0.0))
    risked = float(recap.get("risked", 0.0))
    if risked > 0:
        tally = f"{rec}, {units:+.2f}u, {units / risked * 100:+.1f}% ROI"
    else:
        tally = f"{rec}, record only"
    lines = [f"\U0001F4CA {pretty} results: {tally}"]
    by_sport = recap.get("by_sport") or []
    if by_sport:
        parts = [f"{s['sport']} {s['wins']}-{s['losses']}"
                 + (f"-{s['pushes']}" if s.get("pushes") else "")
                 for s in by_sport]
        # Alphabetical and COMPLETE, both to match the embed. This used to take
        # the first four and say nothing, which on an eight-sport day is the
        # same class of bug as the one this module was just fixed for: a
        # silently partial number. Sports are dropped only when the 280
        # characters genuinely run out, and then it says how many (mike,
        # 2026-09-02, choosing the embed's ordering over most-bets-first).
        tags = hashtags_for(None)
        room = MAX_TWEET - len(lines[0]) - len(tags) - 2      # two newlines
        split = ""
        for k in range(len(parts), 0, -1):
            dropped = len(parts) - k
            split = " · ".join(parts[:k]) + (f" · +{dropped} more" if dropped else "")
            if len(split) <= room:
                break
        lines.append(split)
    lines.append(hashtags_for(None))
    text = "\n".join(x for x in lines if x)
    _assert_no_link(text)
    return text[:MAX_TWEET]


# ── Posting ───────────────────────────────────────────────────────────────────

def post_tweet(text: str, dry_run: bool = False,
               reply_to: str | None = None) -> str | None:
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
        # A reply, when we are threading a result under the pick it grades.
        # Replies are the algorithm's heaviest signal -- weighted about 27x a
        # like, and an author's reply on their own thread far more again -- so
        # threading is both the honest presentation (outcome attached to the
        # call) and the one that travels.
        payload: dict = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
        resp = requests.post(
            X_POST_URL,
            json=payload,
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


# ── Ledgered publishing ───────────────────────────────────────────────────────
# Reuses push_sent, exactly as Discord does: UNIQUE(lock_key, kind), and a row
# written ONLY after a confirmed post. Two consequences that matter here more
# than they do for Discord.
#
# The ledger is checked BEFORE the request, not after. X's rules prohibit
# duplicative content, so a retry that tweets twice is an account risk rather
# than an embarrassment -- and the ~42 refresh passes a day each call this.
#
# The returned tweet id is stored in push_sent.message_id (the column already
# exists for Discord's message ids). Nothing reads it yet; it is what makes a
# future "reply the result under the pick that called it" possible without a
# migration, and it costs nothing to record now.


def _already_sent(conn, lock_key: str, kind: str) -> bool:
    try:
        return conn.execute(
            "SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
            (lock_key, kind)).fetchone() is not None
    except Exception as exc:                                  # noqa: BLE001
        # Unknown means DO NOT POST. An unreadable ledger cannot rule out a
        # duplicate, and a missed post is recoverable where a duplicate is not.
        logger.warning(f"X publisher: ledger read failed ({exc}) — skipping")
        return True


def _ledger(conn, lock_key: str, kind: str, tweet_id: str | None) -> None:
    try:
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (lock_key, kind, datetime.now(ET).isoformat(), tweet_id))
        conn.commit()
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X publisher: ledger write failed ({exc})")


def _discord_free_pick_key(conn, target_date: str) -> str | None:
    """The lock_key Discord published as the free pick of the day, or None.

    Written by notify_discord_free_pick into push_sent.message_id at the moment
    it posts. None means Discord has not posted yet (or the row pre-dates this
    column being used), which is a reason to WAIT rather than to choose again.
    """
    try:
        row = conn.execute(
            "SELECT message_id FROM push_sent "
            "WHERE lock_key = %s AND kind = 'discord_free_pick'",
            (f"discord_free:{target_date}",)).fetchone()
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"X publisher: free-pick ledger read failed ({exc})")
        return None
    return (row[0] or None) if row else None


def notify_x_free_pick(target_date: str | None = None,
                       dry_run: bool = False) -> int:
    """Tweet the day's free pick. Ledgered per date; every later pass no-ops.

    IT IS THE SAME PICK DISCORD POSTED, not another draw from the same pool.
    _pick_free ends in random.choice, and this used to call it a second time:
    over the 22-candidate MLB pools of early September the two surfaces agreed
    about 4% of the time, so the pick tweeted publicly was almost never the one
    the free channel was given — while the module's whole charter is that X gets
    exactly what the free Discord channel gets. mike, 2026-09-02, on the recap:
    "needs to be the same and fired at the same time"; the same answer applies
    to the pick, and a seeded RNG would NOT have fixed it (2026-08-30's two
    posts went out twelve hours apart, over pools that had changed underneath).

    So Discord chooses, records its choice, and X mirrors it. If Discord has not
    posted yet this returns 0 and the next pass retries — both surfaces publish
    the same pick or neither does. The one exception is a deployment with no
    free Discord channel configured at all, where there is no choice to mirror
    and X falls back to choosing its own.
    """
    if not _enabled() or not _creds():
        return 0
    if target_date is None:
        target_date = datetime.now(ET).date().isoformat()
    import config
    from data.db import get_connection
    from tracking.discord_notifier import _free_pick_candidates, _pick_free

    lock = f"x_free:{target_date}"
    conn = get_connection()
    try:
        if _already_sent(conn, lock, "x_free_pick"):
            return 0
        candidates = _free_pick_candidates(conn, target_date)
        if not candidates:
            return 0
        chosen_key = _discord_free_pick_key(conn, target_date)
        if chosen_key:
            pick = next((c for c in candidates
                         if c["lock_key"] == chosen_key), None)
            if pick is None:
                # Discord published something this pool no longer contains (a
                # model paused, a threshold moved). Posting a DIFFERENT pick is
                # the bug this branch exists to prevent, so post nothing.
                logger.warning(
                    f"X free pick: Discord's pick {chosen_key} is no longer a "
                    f"candidate for {target_date} — not substituting another")
                return 0
        elif config.DISCORD_WEBHOOK_FREE:
            logger.info(f"X free pick: waiting for Discord to choose "
                        f"for {target_date}")
            return 0
        else:
            pick = _pick_free(candidates)
            if not pick:
                return 0
        tweet_id = post_tweet(render_free_pick(pick, target_date), dry_run=dry_run)
        if not tweet_id:
            return 0
        if not dry_run:
            _ledger(conn, lock, "x_free_pick", tweet_id)
        logger.info(f"X: free pick tweeted ({tweet_id})")
        return 1
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X free pick failed: {exc}")
        return 0
    finally:
        conn.close()


def notify_x_results(game_date: str, dry_run: bool = False) -> int:
    """Tweet the settled day. Ledgered per date, and ONLY for a day that is over.

    THE DAY-IS-OVER GUARD IS THE WHOLE POINT OF THIS FUNCTION'S TIMING, and it
    was missing until 2026-09-02. `--step settle` runs on all ~42 refresh passes
    and settles TODAY, grading games as they finish. notify_discord_results
    refuses that date; this did not — so the first pass of the day on which
    anything settled tweeted a partial mid-slate record, ledgered it, and the
    6am run's call for the completed day then found the ledger row and no-opped
    forever. X therefore never once published a finished day.

    Measured before the fix (push_sent.sent_at against the same settled
    universe the recap uses, reconstructed on picks.settled_at):

        date        X tweeted            Discord posted
        2026-08-30  7-3   at 21:15 ET    10-8    at 08-31 10:38 ET
        2026-08-31  1-1   at 20:36 ET    14-14-1 at 09-01 06:04 ET
        2026-09-01  0-1   at 21:08 ET    23-12   at 09-02 06:03 ET

    0-1 and 23-12 are the same day. The record is the entire pitch of the
    account, so publishing a losing fragment of a +9.91u day is not a cosmetic
    bug. mike, 2026-09-02: "needs to be the same and fired at the same time."

    Same clock, same comparison and same reason as notify_discord_results, so
    both surfaces now decline every refresh pass and both fire in the same
    step_settle call of the 6am run, seconds apart, off the same query.
    """
    if not _enabled() or not _creds():
        return 0
    if game_date >= datetime.now(ET).date().isoformat():
        return 0
    from data.db import get_connection
    from tracking.discord_notifier import _settled_rows, _tally

    lock = f"x_results:{game_date}"
    conn = get_connection()
    try:
        if _already_sent(conn, lock, "x_results"):
            return 0
        rows = _settled_rows(conn, game_date)
        if not rows:
            return 0
        t = _tally(rows)
        if (t["w"] + t["l"] + t["p"]) == 0:
            return 0
        # Grouped the way the embed groups it, off the SAME rows, so the two
        # surfaces cannot report different per-sport splits. row[0] is sport.
        by_sport: dict[str, list] = {}
        for r in rows:
            by_sport.setdefault(r[0], []).append(r)
        # Alphabetical, which is the order the Discord embed lists its
        # per-sport fields in. Ordering by volume read better in a tweet but
        # made the two surfaces disagree on sequence for no reason.
        ordered = sorted(by_sport.items())
        recap = {
            "wins": t["w"], "losses": t["l"], "pushes": t["p"],
            "units": t["units"], "risked": t["risked"],
            "by_sport": [
                {"sport": sport, "wins": g["w"], "losses": g["l"],
                 "pushes": g["p"]}
                for sport, group in ordered
                for g in (_tally(group),)
            ],
        }
        tweet_id = post_tweet(render_results(recap, game_date), dry_run=dry_run)
        if not tweet_id:
            return 0
        if not dry_run:
            _ledger(conn, lock, "x_results", tweet_id)
        logger.info(f"X: results tweeted ({tweet_id})")
        return 1
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X results failed: {exc}")
        return 0
    finally:
        conn.close()


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
