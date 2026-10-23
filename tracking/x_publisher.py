"""
Post every released pre-game pick, and the settled recaps, to X
(@signalbasepicks).

SCOPE. mike, 2026-08-30, chose "A without links": one free pick plus the
settled recap. mike, 2026-10-18, widened that to every pre-game pick the
system releases, and later the same day took the free-pick concept off X:
every pick post is the same format. No "Free pick" label, no "More in
Discord", no #FreePicks, and X does not read or wait on Discord's free-pick
choice. Discord's own free pick is unchanged and is not an input here.
Live picks stay off X.

X_POST_ALL_PICKS defaults to on, which posts that slate. 0, false, no, or
off posts no pick slate. Off used to mean "the free pick only"; that mode
is gone, because X has no free pick to fall back to. The daily recap is
notify_x_results (yesterday, inside the 6:00am ET pipeline) and is not
affected by this flag. The week and the previous calendar month are
notify_x_period, the same renderer, Monday 7:30am ET. RUN_X_PUBLISHER=0
still stops the slate and every recap.

Pick posts are one tweet per call, at least 10 minutes after the previous
x_pick row, and never between 1:00am and 8:00am ET. A pick whose game has
already started is not tweeted and is not ledgered. The 5-minute social
job and the pipeline refresh both call notify_x_picks; the session lock
plus the ledger timestamp keep those two from sending a pair. Recaps are
not on this clock.

Manual marketing posts are not rendered here. They are rows in
social_post_queue, drained by tracking.social_posts, and they call
deliver_tweet below. That drain can also upload a jpeg, png, or webp
with POST /2/media/upload, signed the same way, and pass the returned
ids as media_ids. Pick and recap posts do not.

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
Slate switch: X_POST_ALL_PICKS=1 (default) posts every released pre-game
    pick, each in the same format. =0 posts no pick slate. It does not
    restore a free-pick-only tweet; X no longer has one.
Reach tags: X_HASHTAG_POOL=GamblingX,SportsBetting,BettingTips
    (comma-separated, with or without the '#'). #FreePicks is dropped if
    it is put in the pool. It is not added on any pick.

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
import re
import secrets
import time
import urllib.parse
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

X_POST_URL = "https://api.x.com/2/tweets"
X_MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
X_PROFILE_URL = "https://api.x.com/1.1/account/update_profile.json"
PROFILE_NAME_MAX = 50
PROFILE_DESCRIPTION_MAX = 160
MAX_TWEET = 280
# One-shot tweet_image on POST /2/media/upload. GIF and video use a different
# category and are not accepted here.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_TWEET_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")

# Anything that would make X charge the link rate, or that reads as a URL to
# their parser. Kept broad on purpose: the cost of a false positive is a
# reworded tweet, the cost of a false negative is 13x on every post.
_LINK_MARKERS = ("http://", "https://", "www.", ".com", ".io", ".co/",
                 ".net", ".org", ".gg", ".ly")


def _enabled() -> bool:
    return os.environ.get("RUN_X_PUBLISHER", "1") == "1"


def post_all_picks() -> bool:
    """True unless X_POST_ALL_PICKS is explicitly off.

    Off ('0', 'false', 'no', 'off') posts no pick slate. The settled recap
    is a different function and still runs. Anything else, including an
    unset variable, posts every released pre-game pick. There is no
    free-pick-only mode on X.
    """
    raw = os.environ.get("X_POST_ALL_PICKS", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _creds() -> tuple | None:
    keys = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    vals = [os.environ.get(k, "") for k in keys]
    return tuple(vals) if all(vals) else None


def results_can_post() -> bool:
    """Whether notify_x_results could tweet here at all: switched on, and all
    four credentials set -- the same two checks it opens with. The recap retry
    (discord_notifier.post_missed_recap) uses it to tell "X has not posted
    this date" from "X is off on this machine", so a worker without X does not
    look like a missed recap on every pass."""
    return _enabled() and _creds() is not None


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
                 nonce: str | None = None, timestamp: str | None = None,
                 extra_params: dict | None = None) -> str:
    api_key, api_secret, token, token_secret = creds
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    # A JSON body is not part of the signature. A form body is: RFC 5849 folds
    # application/x-www-form-urlencoded fields into the same parameter list as
    # the oauth_* fields. extra_params is that form. The Authorization header
    # still lists only oauth_* fields. Tweet posts pass no extra_params.
    signed = dict(oauth)
    for key, value in (extra_params or {}).items():
        if value is None:
            continue
        signed[str(key)] = str(value)
    base = signature_base_string(method, url, signed)
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
    """At most two tags: the sport's own, plus the community one.

    This is the recap's tag line. A pick uses pick_hashtags instead: team
    nicknames plus a short reach pool, capped at MAX_PICK_HASHTAGS.
    """
    tags = []
    tag = _SPORT_TAG.get((sport or "").upper())
    if tag:
        tags.append(tag)
    tags.append(_COMMUNITY_TAG)
    return " ".join(tags[:MAX_HASHTAGS])


# Pick posts. mike, 2026-10-18: every post carries the club nickname(s), then
# a few reach tags, and the whole line stays at or under four. The recap
# keeps the two-tag cap above; three-plus was measured as a spam-filter trip
# for a post that had nothing else to say, and a pick that names its teams
# is a different post. Four is the ceiling, not a target to fill.
MAX_PICK_HASHTAGS = 4
_DEFAULT_REACH_POOL = ("#GamblingX", "#SportsBetting", "#BettingTips")
# Not a reach tag. A pool entry of this name is dropped so it cannot land
# on a pick post.
_BANNED_PICK_TAG = "#FreePicks"
# NCAAB is not a live sport. The tag is here so a later id does not fall
# through to no league tag. NCAAF stays #CFB.
_SPORT_TAG["NCAAB"] = "#CBB"
_SPORT_TAG["CBB"] = "#CBB"


def reach_pool() -> tuple[str, ...]:
    """The configurable reach tags, in priority order.

    X_HASHTAG_POOL is comma-separated. Empty or unset uses the default pool.
    A token may arrive with or without the leading '#'. #FreePicks is
    dropped wherever it appears.
    """
    raw = os.environ.get("X_HASHTAG_POOL", "").strip()
    source = raw.split(",") if raw else _DEFAULT_REACH_POOL
    tags: list[str] = []
    for part in source:
        token = str(part).strip()
        if not token:
            continue
        if not token.startswith("#"):
            token = "#" + token
        if token.lower() == _BANNED_PICK_TAG.lower():
            continue
        if token not in tags:
            tags.append(token)
    return tuple(tags)


def pick_hashtags(pick: dict, *,
                  mascots: dict | None = None) -> tuple[list[str], list[str]]:
    """(team tags, reach tags). Together they never exceed MAX_PICK_HASHTAGS.

    Team tags are kept in full up to the cap. Reach fills whatever slots
    remain: the league tag, then the pool. The caller drops reach tags,
    never team tags, when the character limit bites.
    """
    from tracking.x_teams import team_tags

    teams = team_tags(pick, mascots)[:MAX_PICK_HASHTAGS]
    slots = MAX_PICK_HASHTAGS - len(teams)
    reach: list[str] = []

    def _add(tag: str | None) -> None:
        nonlocal slots
        if tag and slots > 0 and tag not in reach and tag not in teams:
            reach.append(tag)
            slots -= 1

    _add(_SPORT_TAG.get((pick.get("sport") or "").upper()))
    for tag in reach_pool():
        _add(tag)
    return teams, reach


def assemble_text(body: str, team_tags: list[str], reach_tags: list[str],
                  keep: list[str] | None = None) -> str:
    """Body, then pinned text, then team tags, then as many reach tags as fit.

    Reach tags are dropped from the end first. `keep` (the event date and the
    matchup) and the team tags stay. If the body plus those still overflow,
    the body is shortened and the pinned text and team tags are kept whole.
    """
    pinned = [p for p in (keep or []) if p]
    teams = [t for t in team_tags if t]
    reach = [t for t in reach_tags if t]
    protected = pinned + teams

    def _join(text: str, extra: list[str]) -> str:
        parts = [text.strip(), " ".join(extra)]
        return " ".join(p for p in parts if p)

    while reach and len(_join(body, protected + reach)) > MAX_TWEET:
        reach.pop()
    text = _join(body, protected + reach)
    if len(text) <= MAX_TWEET:
        return text
    suffix = " ".join(protected)
    if not suffix:
        return text[:MAX_TWEET]
    room = MAX_TWEET - len(suffix) - 1
    if room < 1:
        return suffix[:MAX_TWEET]
    return body.strip()[:room].rstrip() + " " + suffix


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


def render_pick(pick: dict, mascots: dict | None = None) -> str:
    """One released pick, in one tweet. Every pick uses this format.

    IT LEADS WITH THE BEST BETTABLE PRICE AND THE BOOK THAT HAS IT, the same
    way the Discord card does. mike, 2026-09-03: "it just needs to post the
    best book and price and for bonus, post a good to xx odds."

    An earlier version appended "(+100 at ESPN BET)" after the DraftKings
    price, and a later one prefixed "Free pick —" and closed with "More in
    Discord." The best price is the headline. DraftKings appears only when
    it IS the best. There is no free-pick label and no Discord line.

    Qualification is unchanged and still measured on DraftKings (CLAUDE.md §6).
    This changes where a reader places the bet, not whether the bet exists.

    Every pick names the event date in America/New_York ('Tue 10/20'), from
    the game's start, or from game_date when the start is missing. A prop
    also names the matchup ('NYY @ BOS'). A side or total that does not
    already name both clubs gets that clause when it fits. Over 280
    characters, reach tags drop before the date, the matchup, or a team tag.

    "Good to" is the worst price the model would still have fired at, so it is
    book-agnostic: at or better than that number the bet holds wherever it is
    placed. Dropped rather than truncated when the tweet would overflow — a
    half-written price is worse than none.
    """
    text = _render_pick(pick, mascots=mascots)
    _assert_no_link(text)
    return text


def event_date_label(pick: dict) -> str | None:
    """'Tue 10/20' in America/New_York, from the game's start.

    commence_time wins. A row with no start falls back to game_date, which
    is the event's date. A row with neither has nothing honest to print.
    """
    local = _commence_et(pick.get("commence"))
    if local is None:
        raw = pick.get("game_date")
        if not raw:
            return None
        try:
            day = datetime.fromisoformat(str(raw)[:10]).date()
        except ValueError:
            return None
        return f"{day.strftime('%a')} {day.month}/{day.day}"
    return f"{local.strftime('%a')} {local.month}/{local.day}"


def _commence_et(value) -> datetime | None:
    """The start, in ET. Naive values are UTC, the same rule as Discord."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        try:
            ts = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(ET)


def _label_shows_team(label: str, name: str) -> bool:
    if not name:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(str(name))}(?![A-Za-z0-9])",
        label or "") is not None


def matchup_clause(pick: dict) -> tuple[str | None, bool]:
    """(away @ home, required). None when the label already names both clubs.

    A prop has to name the game. A side or total that does not already show
    both clubs gets the same clause only when it fits.
    """
    home, away = pick.get("home"), pick.get("away")
    if not home or not away:
        return None, False
    if (_label_shows_team(pick.get("label") or "", str(home))
            and _label_shows_team(pick.get("label") or "", str(away))):
        return None, False
    required = bool(pick.get("prop_market")) or (
        "prop" in str(pick.get("model_id") or ""))
    return f"{away} @ {home}", required


def _render_pick(pick: dict, *, mascots: dict | None) -> str:
    emoji = _SPORT_EMOJI.get(pick.get("sport"), "🎯")
    odds, book = _publish_price(pick)
    head = f"{emoji} {pick['label']}"
    price = ""
    if odds is not None:
        price = f"{_american(odds)} at {book}" if book else _american(odds)
    teams, reach = pick_hashtags(pick, mascots=mascots)
    when = event_date_label(pick)
    matchup, matchup_required = matchup_clause(pick)

    def _body(good_to: str | None) -> str:
        parts = [head, price]
        if good_to:
            parts.append(f"Good to {good_to}.")
        return " ".join(p for p in parts if p)

    def _keep(include_matchup: bool) -> list[str]:
        pinned: list[str] = []
        if include_matchup and matchup:
            pinned.append(matchup)
        if when:
            pinned.append(when)
        return pinned

    base = _body(None)
    # A prop matchup stays even when the label has to shorten. Any other
    # matchup is added only when the label, the price, the date and the
    # team tags still fit after every reach tag is dropped.
    include_matchup = bool(matchup) and (
        matchup_required or _fits_whole(base, teams, [], keep=_keep(True)))
    keep = _keep(include_matchup)
    good_to = pick.get("good_to")
    if good_to:
        richer = _body(_american(good_to))
        # The clause is dropped whole. A half-written price is worse than
        # none, and it does not get to push the date, the matchup, or a
        # team tag off the post. Reach tags may go.
        if _fits_whole(richer, teams, reach, keep=keep):
            return assemble_text(richer, teams, reach, keep=keep)
    return assemble_text(base, teams, reach, keep=keep)


def _fits_whole(body: str, team_tags: list[str], reach_tags: list[str],
                keep: list[str] | None = None) -> bool:
    """True when body + pinned text + tags fit without shortening the body."""
    pinned = [p for p in (keep or []) if p]
    teams = [t for t in team_tags if t]
    protected = " ".join(pinned + teams)

    def _text(extra: list[str]) -> str:
        parts = [body.strip(), protected, " ".join(extra)]
        return " ".join(p for p in parts if p)

    reach = [t for t in reach_tags if t]
    if len(_text(reach)) <= MAX_TWEET:
        return True
    # Reach tags may be dropped. The body, the date, the matchup and the
    # team tags may not.
    while reach:
        reach.pop()
        if len(_text(reach)) <= MAX_TWEET:
            return True
    return False


_BOOK_DISPLAY = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel", "betmgm": "BetMGM", "williamhill_us": "Caesars",
    "espnbet": "ESPN BET", "fanatics": "Fanatics", "betrivers": "BetRivers",
    "hardrockbet": "Hard Rock Bet", "ballybet": "Bally Bet",
    "betparx": "betPARX", "rebet": "ReBet",
    # fliff joined the bettable set on 2026-09-07 with the nfl_prop_market
    # widening. Both surfaces are pinned together by
    # test_every_offerable_book_has_a_human_name_on_both_surfaces.
    "fliff": "Fliff",
}


def _publish_price(pick: dict) -> tuple[float | None, str | None]:
    """The price to publish and the book to publish it at.

    Deliberately the same rule as tracking/discord_notifier.publish_price: the
    best BETTABLE price wins, and the row's own book is the fallback whenever
    the alternative is absent, equal or worse. That book is decision_book when
    it was taken at dk_odds, else the old label, else DraftKings. Publishing a
    worse price as though it were an upgrade is the one failure mode worse
    than publishing the price the row already stores.

    The book set is filtered upstream — config.BEST_LINE_BOOKMAKERS excludes
    books that cannot be bet from the US — so this never sends a public audience
    to Pinnacle.
    """
    dk = pick.get("dk_odds")
    best = pick.get("best_odds")
    book = (pick.get("best_book") or "").strip().lower()

    def _decimal(a):
        try:
            a = float(a)
        except (TypeError, ValueError):
            return None
        return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))

    # The same book Discord names for this price. A line-shopped card stores
    # it on decision_book; a row written before that still names it in the
    # label. Hardcoding DraftKings here published FanDuel's number as
    # DraftKings once the label stopped carrying the book.
    from tracking.discord_notifier import book_for_pick

    if best is None or not book:
        return dk, book_for_pick(pick)
    b, d = _decimal(best), _decimal(dk)
    if b is None or (d is not None and b <= d + 1e-9):
        return dk, book_for_pick(pick)
    return best, _BOOK_DISPLAY.get(book, book)


def render_results(recap: dict, game_date: str, restate: bool = False,
                   heading: str | None = None) -> str:
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
    # A week or a month passes its own heading. The daily title stays here so
    # the settled-day tweet cannot drift from the one already posted.
    w, l = int(recap.get("wins", 0)), int(recap.get("losses", 0))
    pushes = int(recap.get("pushes", 0))
    rec = f"{w}-{l}" + (f"-{pushes}" if pushes else "")
    units = float(recap.get("units", 0.0))
    risked = float(recap.get("risked", 0.0))
    if risked > 0:
        tally = f"{rec}, {units:+.2f}u, {units / risked * 100:+.1f}% ROI"
    else:
        tally = f"{rec}, {units:+.2f}u"
    # "(restated)" when a late settlement invalidated the tweet before it --
    # the embed says "restated" in its title; the two must agree.
    if heading:
        head = heading
    else:
        head = f"{pretty} results (restated)" if restate else f"{pretty} results"
    lines = [f"\U0001F4CA {head}: {tally}"]
    # The day's closing-line figure, exactly as the embed states it -- share
    # of graded bets that beat the close, WITH its denominator (discord_notifier
    # .clv_line renders both surfaces). Added 2026-09-10: the tweet carried no
    # CLV, so when the 09-09 recap was re-posted with the NFL CLV that had
    # been missing, X refused the tweet as duplicate content -- byte-identical
    # to the one before it. An empty string when nothing was graded.
    clv = (recap.get("clv") or "").strip()
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
        room = (MAX_TWEET - len(lines[0]) - len(tags) - 2      # two newlines
                - (len(clv) + 1 if clv else 0))                 # its newline
        split = ""
        for k in range(len(parts), 0, -1):
            dropped = len(parts) - k
            split = " · ".join(parts[:k]) + (f" · +{dropped} more" if dropped else "")
            if len(split) <= room:
                break
        lines.append(split)
    if clv:
        lines.append(clv)
    lines.append(hashtags_for(None))
    text = "\n".join(x for x in lines if x)
    _assert_no_link(text)
    return text[:MAX_TWEET]


# ── Posting ───────────────────────────────────────────────────────────────────

class TweetDelivery:
    """One attempt to POST /2/tweets.

    outcome is posted, posted_without_id, dry_run, skipped, refused,
    rate_limited, rejected, or transport. rate_limited is True only for a
    429, which is what the slate loop already stops on.
    """

    def __init__(self, tweet_id: str | None, rate_limited: bool, outcome: str,
                 detail: str = ""):
        self.tweet_id = tweet_id
        self.rate_limited = rate_limited
        self.outcome = outcome
        self.detail = detail


def post_tweet(text: str, dry_run: bool = False,
               reply_to: str | None = None,
               allow_link: bool = False,
               media_ids: list[str] | None = None) -> str | None:
    """POST one tweet. Returns its id, or None when it did not post.

    Never raises into a caller: a publishing surface must not be able to break
    the pass that produced the pick. A 429 is None here; callers that post a
    slate use _deliver_tweet so they can stop instead of hammering the limit.

    allow_link defaults off. Pick and recap posts leave it off, so a URL is
    still refused before the request. A manual row passes True only when that
    row's allow_link column is set — X bills a URL at $0.20 instead of $0.015.

    media_ids defaults off. Pick and recap posts leave it unset, so the JSON
    body has no media key. A manual row passes ids only after each image has
    already been uploaded.
    """
    extra = {"media_ids": media_ids} if media_ids else {}
    tweet_id, _limited = _deliver_tweet(
        text, dry_run=dry_run, reply_to=reply_to, allow_link=allow_link,
        **extra)
    return tweet_id


def _deliver_tweet(text: str, dry_run: bool = False,
                   reply_to: str | None = None,
                   allow_link: bool = False,
                   media_ids: list[str] | None = None) -> tuple[str | None, bool]:
    """(tweet id or None, rate_limited).

    POST /2/tweets allows 100 posts per user per 15 minutes. A 429 is not a
    success and must not be ledgered; the second value tells a slate loop to
    stop and leave the rest for the next pass. A 2xx with no id still returns
    the old "posted" sentinel so existing callers do not treat it as a miss.
    """
    delivered = deliver_tweet(
        text, dry_run=dry_run, reply_to=reply_to, allow_link=allow_link,
        media_ids=media_ids)
    if delivered.outcome == "posted_without_id":
        return "posted", False
    return delivered.tweet_id, delivered.rate_limited


def deliver_tweet(text: str, dry_run: bool = False,
                  reply_to: str | None = None,
                  allow_link: bool = False,
                  media_ids: list[str] | None = None) -> TweetDelivery:
    """POST one tweet and say why it did or did not.

    rejected is an HTTP 4xx other than 429: X refused, so the tweet was not
    created. transport is a network error or a 5xx: the tweet may already
    exist, and a retry can double-post. Callers that must not double-post
    treat transport as uncertain rather than as a miss.

    media_ids, when passed, is sent as media.media_ids. When it is None or
    empty the key is omitted, which is the pick and recap body.
    """
    if not _enabled():
        logger.info("X publisher: RUN_X_PUBLISHER=0 — skipping")
        return TweetDelivery(None, False, "skipped", "RUN_X_PUBLISHER=0")
    creds = _creds()
    if not creds:
        logger.info("X publisher: credentials not configured — skipping")
        return TweetDelivery(None, False, "skipped", "credentials not configured")
    if not allow_link:
        try:
            _assert_no_link(text)
        except ValueError as exc:
            logger.error(f"X publisher: {exc}")
            return TweetDelivery(None, False, "refused", str(exc))
    if dry_run:
        logger.info(f"[dry-run] would tweet:\n{text}")
        return TweetDelivery("dry-run", False, "dry_run", "")
    try:
        # A reply, when we are threading a result under the pick it grades.
        # Replies are the algorithm's heaviest signal -- weighted about 27x a
        # like, and an author's reply on their own thread far more again -- so
        # threading is both the honest presentation (outcome attached to the
        # call) and the one that travels.
        payload: dict = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
        if media_ids:
            cleaned = [str(item) for item in media_ids]
            if (len(cleaned) > 4
                    or any(not re.fullmatch(r"[0-9]{1,19}", item) for item in cleaned)):
                return TweetDelivery(
                    None, False, "refused",
                    "media_ids must be 1 to 4 numeric ids")
            payload["media"] = {"media_ids": cleaned}
        resp = requests.post(
            X_POST_URL,
            json=payload,
            headers={"Authorization": _auth_header("POST", X_POST_URL, creds),
                     "Content-Type": "application/json"},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            tweet_id = str((resp.json().get("data") or {}).get("id") or "")
            if tweet_id:
                return TweetDelivery(tweet_id, False, "posted", "")
            return TweetDelivery(None, False, "posted_without_id", "2xx with no id")
        detail = f"HTTP {resp.status_code} {resp.text[:200]}"
        if resp.status_code == 429:
            logger.error(f"X publisher: rate limited (429) {resp.text[:200]}")
            return TweetDelivery(None, True, "rate_limited", detail)
        if 400 <= resp.status_code < 500:
            logger.error(f"X publisher: {detail}")
            return TweetDelivery(None, False, "rejected", detail)
        logger.error(f"X publisher: {detail}")
        return TweetDelivery(None, False, "transport", detail)
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X publisher: post failed ({exc})")
        return TweetDelivery(None, False, "transport", str(exc)[:200])


class ImageFetch:
    """Bytes downloaded for one manual-post image. outcome is fetched,
    failed, or rate_limited. Pick and recap posts never construct one."""

    def __init__(self, content: bytes | None, media_type: str | None,
                 outcome: str, detail: str = ""):
        self.content = content
        self.media_type = media_type
        self.outcome = outcome
        self.detail = detail


class MediaUpload:
    """One POST /2/media/upload. outcome is uploaded, rejected, transport,
    rate_limited, or skipped. A missing media_id is not uploaded."""

    def __init__(self, media_id: str | None, outcome: str, detail: str = ""):
        self.media_id = media_id
        self.outcome = outcome
        self.detail = detail


def _sniff_tweet_image(content: bytes) -> str | None:
    """The type X's one-shot tweet_image call accepts, from the file bytes."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def fetch_https_image(url: str) -> ImageFetch:
    """GET one https image. Does not tweet and does not upload.

    The final URL after redirects must stay https. The type is taken from
    the bytes, not the response header. GIF is refused: the one-shot
    tweet_image category does not list it.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ImageFetch(None, None, "failed", "image URL must be https")
    try:
        resp = requests.get(url, timeout=30, stream=True)
    except Exception as exc:  # noqa: BLE001 — the caller marks the row failed
        return ImageFetch(None, None, "failed", f"image fetch failed: {exc}"[:200])
    try:
        final = urllib.parse.urlparse(resp.url)
        if final.scheme != "https":
            return ImageFetch(None, None, "failed", "image URL redirected off https")
        if resp.status_code == 429:
            return ImageFetch(None, None, "rate_limited", "image host HTTP 429")
        if resp.status_code != 200:
            return ImageFetch(None, None, "failed", f"image fetch HTTP {resp.status_code}")
        buf = bytearray()
        for chunk in resp.iter_content(65536):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > MAX_IMAGE_BYTES:
                return ImageFetch(None, None, "failed", "image is over 5MB")
        content = bytes(buf)
    except Exception as exc:  # noqa: BLE001
        return ImageFetch(None, None, "failed", f"image fetch failed: {exc}"[:200])
    finally:
        resp.close()
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return ImageFetch(
            None, None, "failed",
            "gif is not a one-shot tweet_image; use jpeg, png, or webp")
    media_type = _sniff_tweet_image(content)
    if media_type not in _TWEET_IMAGE_TYPES:
        return ImageFetch(None, None, "failed", "image is not jpeg, png, or webp")
    if not content:
        return ImageFetch(None, None, "failed", "image is empty")
    return ImageFetch(content, media_type, "fetched", "")


def upload_tweet_image(content: bytes, media_type: str) -> MediaUpload:
    """POST /2/media/upload with the same OAuth 1.0a header as a tweet.

    The JSON body is not part of the signature. Does not create a tweet.
    A 2xx whose data.id is missing, or whose processing state is not ready,
    returns no media id so the caller does not attach one.
    """
    if media_type not in _TWEET_IMAGE_TYPES:
        return MediaUpload(None, "rejected", f"unsupported media_type {media_type}")
    if not content or len(content) > MAX_IMAGE_BYTES:
        return MediaUpload(None, "rejected", "image is empty or over 5MB")
    if not _enabled():
        return MediaUpload(None, "skipped", "RUN_X_PUBLISHER=0")
    creds = _creds()
    if not creds:
        return MediaUpload(None, "skipped", "credentials not configured")
    payload = {
        "media": base64.b64encode(content).decode("ascii"),
        "media_category": "tweet_image",
        "media_type": media_type,
    }
    try:
        resp = requests.post(
            X_MEDIA_UPLOAD_URL,
            json=payload,
            headers={"Authorization": _auth_header("POST", X_MEDIA_UPLOAD_URL, creds),
                     "Content-Type": "application/json"},
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        return MediaUpload(None, "transport", str(exc)[:200])
    if resp.status_code not in (200, 201):
        detail = f"HTTP {resp.status_code} {resp.text[:200]}"
        if resp.status_code == 429:
            return MediaUpload(None, "rate_limited", detail)
        if 400 <= resp.status_code < 500:
            return MediaUpload(None, "rejected", detail)
        return MediaUpload(None, "transport", detail)
    try:
        data = (resp.json() or {}).get("data") or {}
    except Exception as exc:  # noqa: BLE001
        return MediaUpload(None, "rejected", f"upload 2xx was not json: {exc}"[:200])
    media_id = str(data.get("id") or "")
    if not re.fullmatch(r"[0-9]{1,19}", media_id):
        return MediaUpload(None, "rejected", "upload 2xx with no media id")
    state = str((data.get("processing_info") or {}).get("state") or "")
    if state in ("pending", "in_progress", "failed"):
        return MediaUpload(None, "rejected", f"image not ready ({state})")
    return MediaUpload(media_id, "uploaded", "")


class ProfileUpdate:
    """One POST /1.1/account/update_profile.json.

    outcome is updated, skipped, rejected, or transport. rejected is an HTTP
    4xx, including 429: the profile drain does not retry those. skipped means
    the call was not made. Pick and recap posts never construct one.
    """

    def __init__(self, outcome: str, detail: str = "", body: str = ""):
        self.outcome = outcome
        self.detail = detail
        self.body = body


def update_profile(*, name: str | None = None, description: str | None = None,
                   url: str | None = None) -> ProfileUpdate:
    """Set the account name, description, and url. Does not create a tweet.

    Omitted fields (None) are left off the form, so X leaves them as they are.
    A name over 50 characters or a description over 160 is refused here, before
    the request. RUN_X_PUBLISHER=0 returns skipped and does not call X.
    """
    if not _enabled():
        return ProfileUpdate("skipped", "RUN_X_PUBLISHER=0")
    creds = _creds()
    if not creds:
        return ProfileUpdate("skipped", "credentials not configured")
    fields: dict[str, str] = {}
    if name is not None:
        fields["name"] = str(name)
    if description is not None:
        fields["description"] = str(description)
    if url is not None:
        fields["url"] = str(url)
    if not fields:
        return ProfileUpdate("rejected", "nothing to update")
    if "name" in fields and len(fields["name"]) > PROFILE_NAME_MAX:
        return ProfileUpdate(
            "rejected",
            f"name is {len(fields['name'])} characters; the limit is {PROFILE_NAME_MAX}")
    if "description" in fields and len(fields["description"]) > PROFILE_DESCRIPTION_MAX:
        return ProfileUpdate(
            "rejected",
            f"description is {len(fields['description'])} characters; "
            f"the limit is {PROFILE_DESCRIPTION_MAX}")
    try:
        resp = requests.post(
            X_PROFILE_URL,
            data=fields,
            headers={
                "Authorization": _auth_header(
                    "POST", X_PROFILE_URL, creds, extra_params=fields),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        return ProfileUpdate("transport", str(exc)[:500])
    body = (resp.text or "")[:4000]
    if resp.status_code in (200, 201):
        return ProfileUpdate("updated", "", body)
    detail = f"HTTP {resp.status_code} {body[:500]}"
    if 400 <= resp.status_code < 500:
        return ProfileUpdate("rejected", detail, body)
    return ProfileUpdate("transport", detail, body)


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


# One row per pick, on the pick's own lock key. A later pass sees the row
# and does not tweet that pick again. The row is still written only after
# a confirmed post. Pacing reads sent_at; it does not insert a claim row.
X_PICK_KIND = "x_pick"
# Minimum gap between two confirmed pick tweets. The 5-minute job is what
# makes the gap about 10 minutes instead of the hourly refresh.
PICK_MIN_GAP = timedelta(minutes=10)
# 1:00am inclusive through 8:00am exclusive, America/New_York. 12:35am is
# before this window. A held pick posts on the first eligible call at or
# after 8:00am whose game has not started.
_QUIET_START = dt_time(1, 0)
_QUIET_END = dt_time(8, 0)


def _as_et(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _in_pick_quiet_hours(now: datetime) -> bool:
    local = _as_et(now)
    return _QUIET_START <= local.time().replace(microsecond=0) < _QUIET_END


def _parse_sent_at(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ET)
    # UTC, not ET. Two ET stamps in the November overlap share a tzinfo, and
    # Python then compares the clock face and ignores fold, so 1:30am EDT
    # sorts after 1:00am EST even though EST is later.
    return ts.astimezone(ZoneInfo("UTC"))


def _latest_x_pick_sent(conn) -> datetime | None:
    """Newest x_pick sent_at, or None when no pick has been confirmed.

    Raises when the read fails or a returned stamp cannot be parsed. The
    caller treats that as "do not post": an unreadable clock cannot prove
    the gap. String order of the offset is wrong across the DST overlap,
    so the newest of the last few rows is taken by parsed time.
    """
    rows = conn.execute(
        "SELECT sent_at FROM push_sent WHERE kind = %s "
        "ORDER BY sent_at DESC LIMIT 8",
        (X_PICK_KIND,)).fetchall()
    latest = None
    saw = False
    for row in rows:
        saw = True
        parsed = _parse_sent_at(row[0])
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    if saw and latest is None:
        raise ValueError("x_pick sent_at unreadable")
    return latest


def _x_pick_gap_open(conn, now: datetime) -> bool:
    try:
        last = _latest_x_pick_sent(conn)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"X publisher: pick clock unreadable ({exc}) — skipping")
        return False
    if last is None:
        return True
    return now - last >= PICK_MIN_GAP


def _game_already_started(pick: dict, now: datetime) -> bool:
    """True when this pick's commence is at or before now.

    A missing or unparseable commence is not treated as started. That is
    the same rule as the slate query: an unknown start must not drop a pick.
    """
    raw = pick.get("commence")
    if raw is None or raw == "":
        return False
    if isinstance(raw, datetime):
        ts = raw
    else:
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    # Instants, not the ET clock face. The November overlap makes 1:30am EDT
    # compare greater than 1:00am EST when both carry the same tzinfo.
    return ts.astimezone(ZoneInfo("UTC")) <= _as_et(now).astimezone(ZoneInfo("UTC"))


def _college_mascots(conn, picks: list[dict]) -> dict[str, str]:
    """school -> mascot for the NCAAF clubs in this batch. Empty on any failure.

    The nickname lives in ncaaf_teams, not in the games row (that row is the
    school name). A miss falls back to the school name inside team_hashtag.
    """
    schools: list[str] = []
    for pick in picks:
        if (pick.get("sport") or "").upper() != "NCAAF":
            continue
        for key in ("home", "away"):
            name = pick.get(key)
            if name:
                schools.append(str(name))
    if not schools:
        return {}
    try:
        rows = conn.execute(
            "SELECT school, mascot FROM ncaaf_teams WHERE school = ANY(%s)",
            (sorted(set(schools)),)).fetchall()
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"X publisher: college nicknames unavailable ({exc})")
        return {}
    return {row[0]: row[1] for row in rows if row[0] and row[1]}


def _post_released_picks(conn, target_date: str, dry_run: bool = False,
                         now: datetime | None = None) -> int:
    """Tweet at most one released pre-game pick that has no X row yet.

    The set is _new_signals with the Discord ledger ignored: the same picks
    Discord's sport channels release, including a game dated ahead of today,
    excluding live and started games. Discord's free-pick choice is not
    consulted. Order is that query's order. This posts the first one that
    is not already ledgered and whose game has not started.

    One confirmed tweet per call. The previous x_pick sent_at must be at
    least PICK_MIN_GAP old. From 1:00am through 8:00am ET the call posts
    nothing and writes nothing; the pick stays eligible. A game that has
    started by send time is skipped and not ledgered, and the call moves
    to the next pick. Each posted pick is ledgered as x_pick on its own
    lock_key after a confirmed post. A 429 stops the call; nothing unsent
    is ledgered, so the next eligible call retries that same pick.

    The session advisory lock is held across the read, the send, and the
    ledger so a pipeline pass and the 5-minute job cannot each send one.
    """
    if not post_all_picks():
        return 0
    clock = _as_et(now)
    if _in_pick_quiet_hours(clock):
        logger.info("X picks: quiet hours (1:00am–8:00am ET) — holding")
        return 0
    from tracking.publish_lock import X_PICKS_LOCK, publish_lock
    with publish_lock(conn, X_PICKS_LOCK, "X picks") as owned:
        if not owned:
            return 0
        if not _x_pick_gap_open(conn, clock):
            return 0
        try:
            from tracking.discord_notifier import _new_signals
            picks = _new_signals(conn, target_date, include_already_posted=True)
        except Exception as exc:                              # noqa: BLE001
            logger.error(f"X slate failed: {exc}")
            return 0
        try:
            mascots = _college_mascots(conn, picks)
        except Exception as exc:                              # noqa: BLE001
            logger.warning(f"X publisher: mascot load failed ({exc})")
            mascots = {}
        posted = 0
        for pick in picks:
            key = pick.get("lock_key")
            if not key:
                continue
            if _already_sent(conn, key, X_PICK_KIND):
                continue
            if _game_already_started(pick, clock):
                logger.info(f"X picks: {key} game has started — not posting")
                continue
            try:
                text = render_pick(pick, mascots=mascots)
            except ValueError as exc:
                logger.error(f"X publisher: {exc}")
                continue
            tweet_id, limited = _deliver_tweet(text, dry_run=dry_run)
            if limited:
                logger.warning(
                    "X publisher: rate limited — this pick waits for the next pass")
                break
            if not tweet_id:
                continue
            if not dry_run:
                _ledger(conn, key, X_PICK_KIND, tweet_id)
            posted += 1
            break
        if posted:
            logger.info(f"X: {posted} pick(s) tweeted")
        return posted


def notify_x_picks(target_date: str | None = None,
                   dry_run: bool = False,
                   now: datetime | None = None) -> int:
    """Tweet the next released pre-game pick that is not already on X.

    One format for every pick. This does not read Discord's free-pick row,
    does not wait for that choice, and does not label one tweet differently.
    Each pick is ledgered on its own lock key, so a later pass posts only
    picks that were not confirmed. One call confirms at most one tweet, and
    only when the last x_pick is at least 10 minutes old and the ET clock
    is outside 1:00am–8:00am.

    The connection is session mode so the advisory lock is held across the
    HTTP call. The transaction pooler would release it after the lock
    statement, and the pipeline pass and the 5-minute job would both send.

    X_POST_ALL_PICKS=0 returns 0 and posts nothing. Returns the number of
    tweets confirmed on this call.
    """
    if not _enabled() or not _creds() or not post_all_picks():
        return 0
    if target_date is None:
        target_date = datetime.now(ET).date().isoformat()
    from data.db import get_connection

    conn = get_connection(session_mode=True)
    try:
        return _post_released_picks(conn, target_date, dry_run=dry_run, now=now)
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X picks failed: {exc}")
        return 0
    finally:
        conn.close()


def notify_x_results(game_date: str, dry_run: bool = False,
                     restate: dict | None = None,
                     now: datetime | None = None) -> int:
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
    from tracking.discord_notifier import (_as_et, _settled_rows, _tally,
                                           clv_line, in_daily_recap_window,
                                           restate_lock_key, sport_in_progress,
                                           window_still_live)
    clock = _as_et(now)
    # Same clock as notify_discord_results: a day that is not over, and any
    # hour from noon through 6:00am, returns before the database is opened.
    if game_date >= clock.date().isoformat():
        return 0
    if not in_daily_recap_window(clock):
        return 0
    from data.db import get_connection

    # A restatement (recaps_needing_restatement's dict) rides its own ledger
    # kind, keyed on the published_at of the recap it corrects -- the same
    # key shape Discord uses, so the two surfaces fire on the same batch.
    kind = "x_results_restate" if restate else "x_results"
    lock = (restate_lock_key(kind, game_date, restate["published_at"])
            if restate else f"x_results:{game_date}")
    conn = get_connection()
    try:
        if _already_sent(conn, lock, kind):
            return 0
        rows = _settled_rows(conn, game_date)
        if not rows:
            return 0
        sports = tuple({r[0] for r in rows if r[0]})
        if window_still_live(conn, game_date, game_date, sports):
            logger.info(f"X results: {game_date} still has a game "
                        f"without a final score")
            return 0
        if sport_in_progress(conn, sports, now):
            logger.info(f"X results: {game_date} waits, a game of "
                        f"that sport is in progress")
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
            # The same string the embed's headline carries.
            "clv": clv_line(t),
            "by_sport": [
                {"sport": sport, "wins": g["w"], "losses": g["l"],
                 "pushes": g["p"]}
                for sport, group in ordered
                for g in (_tally(group),)
            ],
        }
        tweet_id = post_tweet(render_results(recap, game_date,
                                             restate=bool(restate)),
                              dry_run=dry_run)
        if not tweet_id:
            return 0
        if not dry_run:
            _ledger(conn, lock, kind, tweet_id)
        logger.info(f"X: results tweeted ({tweet_id})")
        return 1
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X results failed: {exc}")
        return 0
    finally:
        conn.close()


def notify_x_period(span: str, start, end, heading: str,
                    dry_run: bool = False,
                    now: datetime | None = None) -> int:
    """Tweet one week or one month. Same settled picks as the daily recap.

    The heading is the one Discord uses, plus 'results', so the two surfaces
    name the window the same way. Ledgered on the window's start, only after
    a confirmed post.
    """
    if not _enabled() or not _creds():
        return 0
    from tracking.discord_notifier import (_settled_rows_since, _tally, clv_line,
                                           in_period_recap_window,
                                           sport_in_progress, window_still_live)
    if not in_period_recap_window(now):
        return 0
    from data.db import get_connection

    kind = f"x_results_{span}"
    lock = f"{kind}:{start.isoformat()}"
    conn = get_connection()
    try:
        if _already_sent(conn, lock, kind):
            return 0
        rows = _settled_rows_since(conn, start.isoformat(), end.isoformat())
        if not rows:
            return 0
        sports = tuple({r[0] for r in rows if r[0]})
        if window_still_live(conn, start.isoformat(), end.isoformat(), sports):
            logger.info(f"X {span}: {heading} still has a game "
                        f"without a final score")
            return 0
        if sport_in_progress(conn, sports, now):
            logger.info(f"X {span}: {heading} waits, a game of "
                        f"that sport is in progress")
            return 0
        t = _tally(rows)
        if (t["w"] + t["l"] + t["p"]) == 0:
            return 0
        by_sport: dict[str, list] = {}
        for r in rows:
            by_sport.setdefault(r[0], []).append(r)
        ordered = sorted(by_sport.items())
        recap = {
            "wins": t["w"], "losses": t["l"], "pushes": t["p"],
            "units": t["units"], "risked": t["risked"],
            "clv": clv_line(t),
            "by_sport": [
                {"sport": sport, "wins": g["w"], "losses": g["l"],
                 "pushes": g["p"]}
                for sport, group in ordered
                for g in (_tally(group),)
            ],
        }
        tweet_id = post_tweet(
            render_results(recap, start.isoformat(),
                           heading=f"{heading} results"),
            dry_run=dry_run)
        if not tweet_id:
            return 0
        if not dry_run:
            _ledger(conn, lock, kind, tweet_id)
        logger.info(f"X: {span} results tweeted ({tweet_id})")
        return 1
    except Exception as exc:                                  # noqa: BLE001
        logger.error(f"X {span} results failed: {exc}")
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
