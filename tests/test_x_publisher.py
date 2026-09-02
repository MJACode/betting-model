"""
Posting the daily free pick and the settled recap to X (@signalbasepicks).

SCOPE. mike, 2026-08-30, choosing between three options: "A without links."
A is the free pick + the recap — exactly what the free Discord channel gets.
Posting every paid signal publicly would destroy what Whop members pay for.

THE THREE THINGS THAT COULD GO WRONG, and all three are cheap to get wrong:

  1. A LINK SNEAKS IN. X charges $0.015 per post but $0.20 if it contains a
     URL — 13x, added April 2026. Adding a betslip link to a renderer months
     from now would look like an improvement and quietly multiply the bill.
     So the ban is a hard check, and it is tested against the ways a URL
     actually appears rather than just "http".

  2. THE SIGNATURE IS WRONG. OAuth 1.0a is easy to implement in a way that
     verifies against your own code and is rejected by the server. So the
     signing is tested against RFC 5849's OWN published example, not against
     itself — the one form of this test that can catch a shared misreading.

  3. IT DOUBLE-POSTS. X's rules prohibit duplicative content, so a retry that
     tweets twice is an account risk, not an embarrassment. Nothing here may
     post without the ledger check, and nothing may raise into the caller.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import x_publisher as xp  # noqa: E402


# ── 1. no links, ever ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "Take the Over https://sportsbook.dk/bet/123",
    "More at www.signalbase.com",
    "Join us at signalbase.io today",
    "discord.gg/abcdef",
    "http://x.com/foo",
])
def test_anything_that_reads_as_a_url_is_refused(bad):
    """13x per post. The check is deliberately broad — a false positive costs a
    reword, a false negative costs money on every post forever."""
    with pytest.raises(ValueError, match="link rate"):
        xp._assert_no_link(bad)


def test_ordinary_pick_text_passes():
    xp._assert_no_link("⚾ Free pick — Yankees Over 8.5. -110 at DraftKings. "
                       "Good to -120. More in Discord.")


def test_post_tweet_refuses_a_link_instead_of_raising(monkeypatch):
    """
    A publishing surface must not be able to break the pass that produced the
    pick — so the refusal is a None, not an exception, and nothing is sent.
    """
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")
    sent = []
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: sent.append(a))
    assert xp.post_tweet("see https://example.com") is None
    assert not sent, "a link reached the wire"


def test_both_renderers_are_link_free_and_fit_one_tweet():
    pick = {"sport": "MLB", "label": "Yankees Over 8.5", "dk_odds": -110,
            "good_to": -120}
    t = xp.render_free_pick(pick, "2026-08-30")
    assert len(t) <= xp.MAX_TWEET
    xp._assert_no_link(t)

    recap = {"wins": 10, "losses": 5, "units": 3.53,
             "by_sport": [{"sport": "MLB", "wins": 10, "losses": 5}]}
    r = xp.render_results(recap, "2026-08-30")
    assert len(r) <= xp.MAX_TWEET
    xp._assert_no_link(r)


def test_a_very_long_label_is_truncated_not_rejected():
    pick = {"sport": "NCAAF", "label": "X" * 400, "dk_odds": -110}
    assert len(xp.render_free_pick(pick, "2026-08-30")) <= xp.MAX_TWEET


# ── 2. the signature, against the RFC's own vector ────────────────────────────

def test_signature_base_string_matches_rfc5849():
    """
    RFC 5849 §3.4.1.1's worked example. Testing against the spec rather than
    against our own output is the only version of this that can catch a
    misreading we would otherwise reproduce in both the code and the test.
    """
    params = {
        "b5": "=%3D", "a3": "a", "c@": "", "a2": "r b",
        "oauth_consumer_key": "9djdj82h48djs9d2",
        "oauth_token": "kkk9d7dh3k39sjv7",
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": "137131201",
        "oauth_nonce": "7d8f3e4a",
    }
    base = xp.signature_base_string("POST", "http://example.com/request", params)
    assert base.startswith("POST&http%3A%2F%2Fexample.com%2Frequest&")
    # the normalized parameter string, percent-encoded once more
    assert "a2%3Dr%2520b" in base
    assert "oauth_consumer_key%3D9djdj82h48djs9d2" in base


def test_the_percent_encoder_leaves_only_the_unreserved_set():
    """
    Python's urllib default is safe='/', which is the classic way to produce a
    signature that verifies locally and is rejected by the server.
    """
    assert xp._quote("a/b") == "a%2Fb"
    assert xp._quote("r b") == "r%20b"
    assert xp._quote("~") == "~"
    assert xp._quote("=%3D") == "%3D%253D"


def test_the_header_is_deterministic_for_a_fixed_nonce_and_clock():
    creds = ("ck", "cs", "tok", "toksec")
    a = xp._auth_header("POST", xp.X_POST_URL, creds, nonce="n", timestamp="1")
    b = xp._auth_header("POST", xp.X_POST_URL, creds, nonce="n", timestamp="1")
    assert a == b
    assert 'oauth_signature_method="HMAC-SHA1"' in a
    assert "oauth_signature=" in a


def test_a_different_secret_changes_the_signature():
    """Guards against a signing key that silently ignores the token secret."""
    h1 = xp._auth_header("POST", xp.X_POST_URL, ("ck", "cs", "tok", "A"),
                         nonce="n", timestamp="1")
    h2 = xp._auth_header("POST", xp.X_POST_URL, ("ck", "cs", "tok", "B"),
                         nonce="n", timestamp="1")
    assert h1 != h2


# ── 3. it cannot post when it should not ──────────────────────────────────────

def test_the_kill_switch_stops_it(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "0")
    sent = []
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: sent.append(a))
    assert xp.post_tweet("hello") is None
    assert not sent


def test_missing_credentials_are_a_no_op_not_a_crash(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.delenv(k, raising=False)
    sent = []
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: sent.append(a))
    assert xp.post_tweet("hello") is None
    assert not sent


def test_partial_credentials_do_not_post(monkeypatch):
    """Three of four keys set is a misconfiguration, not permission to try."""
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    monkeypatch.setenv("X_API_KEY", "a")
    monkeypatch.setenv("X_API_SECRET", "b")
    monkeypatch.setenv("X_ACCESS_TOKEN", "c")
    monkeypatch.delenv("X_ACCESS_TOKEN_SECRET", raising=False)
    sent = []
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: sent.append(a))
    assert xp.post_tweet("hello") is None
    assert not sent


def test_a_transport_failure_returns_none_rather_than_raising(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")

    def _boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(xp.requests, "post", _boom)
    assert xp.post_tweet("hello") is None


def test_a_non_2xx_is_not_reported_as_posted(monkeypatch):
    """
    Reporting a failure as a success would ledger it, and the ledger is what
    stops a retry — so a 403 recorded as posted means the tweet never goes out
    and nothing ever tries again.
    """
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")

    class _R:
        status_code = 403
        text = "forbidden"
        # A json() that WORKS is the point. The first version of this fixture
        # had none, so resp.json() raised and the outer except returned None --
        # the test passed for the wrong reason, and a mutation replacing the
        # status check with `if True:` sailed through it. A test that would
        # pass with the guard removed is not testing the guard.
        def json(self): return {"data": {"id": "should-not-be-used"}}
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    assert xp.post_tweet("hello") is None


def test_a_429_rate_limit_is_not_reported_as_posted(monkeypatch):
    """X rate-limits posting; a 429 recorded as success loses the tweet."""
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")

    class _R:
        status_code = 429
        text = "Too Many Requests"
        def json(self): return {"data": {"id": "nope"}}
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    assert xp.post_tweet("hello") is None


def test_a_success_returns_the_tweet_id(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")

    class _R:
        status_code = 201
        def json(self): return {"data": {"id": "1234567890"}}
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    assert xp.post_tweet("hello") == "1234567890"


def test_dry_run_never_touches_the_network(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")
    sent = []
    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: sent.append(a))
    assert xp.post_tweet("hello", dry_run=True) == "dry-run"
    assert not sent


def test_the_setup_steps_use_a_url_we_actually_own():
    """
    The first draft of these instructions invented `https://signalbase.app/callback`
    for a site that does not exist, and told mike to enter "your website" when he
    has none. X's form requires both fields and will not save without them, so a
    made-up answer is not harmless — it is a step someone cannot complete.

    The repo has exactly two real external URLs (the X profile and the Discord
    invite). Pinned so a future edit cannot reintroduce a plausible-looking
    domain nobody controls.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    setup = src[src.index("GETTING THOSE FOUR KEYS"):src.index("TRAP 1:")]
    assert "https://x.com/signalbasepicks" in setup
    for invented in ("signalbase.app", "signalbase.com", "your site", "your website"):
        assert invented not in setup, f"invented URL back in the setup steps: {invented}"


def test_the_two_silent_traps_are_written_down():
    """
    Both fail in ways that do not name their own cause: a read-only token 403s
    without mentioning permissions, and credentials on both services would
    double-post without anything reporting it.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    assert "Read and write" in src and "read-only scope" in src
    assert "not `pollers`" in src


def test_the_setup_steps_name_the_credentials_to_IGNORE():
    """
    The Keys and tokens page shows six credentials, not four, and three of them
    are plausible-looking dead ends — a Bearer Token posts nothing (app-only,
    read-only) and the OAuth 2.0 Client ID/Secret are a different auth flow
    entirely.

    Listing only what to copy left mike unable to match the page against the
    variable names. The exclusions are part of the instruction, not trivia.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    setup = src[src.index("GETTING THOSE FOUR KEYS"):src.index("TRAP 1:")]
    assert "IGNORE" in setup
    for skip in ("Bearer Token", "Client ID", "Client Secret"):
        assert skip in setup, f"the page shows {skip} and the steps do not mention it"
    # X's UI says Consumer Key where its own API docs say API Key
    assert "Consumer Key" in setup


def test_the_duplicate_access_token_row_is_called_out():
    """
    The trap that actually breaks the integration, and the reason two earlier
    versions of these instructions were wrong.

    The Keys & Tokens page has TWO rows named "Access Token" — one under
    OAuth 1.0 Keys and one under OAuth 2.0 Keys. Only the OAuth 1.0 one works
    with this module's signing. The wrong one produces credentials that look
    entirely valid and fail to post.

    Written from the real page rather than from documentation, after two
    attempts from memory got the page's shape wrong.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    setup = src[src.index("GETTING THOSE FOUR KEYS"):src.index("TRAP 1:")]
    assert "OAuth 1.0 Keys" in setup and "OAuth 2.0 Keys" in setup
    assert 'TWO ROWS ARE CALLED "Access Token"' in setup, (
        "the duplicate row is the trap — it must be stated, not implied")


def test_the_smoke_test_defaults_to_dry_run():
    """
    Posting to a public account is not something a stray invocation should be
    able to do. The dangerous direction gets the flag: `--post` publishes,
    bare invocation renders only.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    main = src[src.index("def _main("):]
    assert '"--post", action="store_true"' in main
    assert "dry_run=not args.post" in main, (
        "the smoke test must default to dry run, not to publishing")


def test_the_smoke_test_never_prints_a_secret():
    """
    It runs on the worker and its output lands in Railway logs. Length and
    prefix distinguish a real value from an empty string or a mispasted
    placeholder without putting the credential in a log.
    """
    src = (Path(__file__).parent.parent / "tracking" / "x_publisher.py").read_text(
        encoding="utf-8")
    main = src[src.index("def _main("):]
    assert "len(val)" in main and "val[:4]" in main
    assert "{val}" not in main, "a full credential value would reach the logs"


# ── reach ─────────────────────────────────────────────────────────────────────

def test_never_more_than_two_hashtags():
    """
    Not a style rule. 1-2 tags carry about +21% engagement on the 2026
    algorithm; THREE OR MORE trips spam filters and cuts reach below what the
    post would get with none. So the cap has to be enforced, not advised.
    """
    # Asserted against the LITERAL 2, not against xp.MAX_HASHTAGS. Comparing a
    # constant to itself is not a test: raising the constant to 3 moved the
    # goalposts and this passed cleanly, which is exactly the change that would
    # cost reach.
    assert xp.MAX_HASHTAGS == 2, (
        "1-2 hashtags is the evidenced optimum; 3+ trips spam filters")
    for sport in ("MLB", "WNBA", "NCAAF", "UFC", None, "CRICKET"):
        assert xp.hashtags_for(sport).count("#") <= 2


def test_the_sport_tag_is_specific_not_generic():
    """
    Generic tags are the ones the ranker treats as noise, and they compete with
    the whole platform instead of reaching people who follow the subject.
    """
    assert "#MLB" in xp.hashtags_for("MLB")
    assert "#CFB" in xp.hashtags_for("NCAAF")
    for generic in ("#betting", "#sports", "#gambling ", "#picks"):
        assert generic not in xp.hashtags_for("MLB").lower()


def test_an_unknown_sport_still_gets_the_community_tag():
    assert xp.hashtags_for("KABADDI") == xp._COMMUNITY_TAG
    assert xp.hashtags_for(None) == xp._COMMUNITY_TAG


def test_tags_are_inside_the_character_budget():
    pick = {"sport": "MLB", "label": "X" * 300, "dk_odds": -110}
    assert len(xp.render_free_pick(pick, "2026-08-30")) <= xp.MAX_TWEET


def test_a_reply_carries_the_parent_id(monkeypatch):
    """
    Replies are the algorithm's heaviest signal, and threading a result under
    the pick that called it is also the honest presentation.
    """
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(k, "x")
    sent = {}

    class _R:
        status_code = 201
        def json(self): return {"data": {"id": "999"}}

    def _post(url, json=None, headers=None, timeout=None):
        sent.update(json or {})
        return _R()

    monkeypatch.setattr(xp.requests, "post", _post)
    xp.post_tweet("hello", reply_to="12345")
    assert sent["reply"] == {"in_reply_to_tweet_id": "12345"}

    sent.clear()
    xp.post_tweet("standalone")
    assert "reply" not in sent, "a normal post must not carry a reply block"


# ── the ledger ────────────────────────────────────────────────────────────────

def test_an_unreadable_ledger_blocks_the_post(monkeypatch):
    """
    The asymmetry that decides this: a missed post is recoverable, a duplicate
    is not — X prohibits duplicative content and ~42 passes a day call this.
    So "I cannot tell whether this was already sent" must mean DO NOT SEND.
    """
    class _Conn:
        def execute(self, *a, **k):
            raise RuntimeError("db down")
    assert xp._already_sent(_Conn(), "k", "x_free_pick") is True


def test_a_clean_ledger_allows_the_post():
    class _Conn:
        def execute(self, *a, **k): return self
        def fetchone(self): return None
    assert xp._already_sent(_Conn(), "k", "x_free_pick") is False


def test_the_tweet_id_is_stored_for_future_threading():
    """
    push_sent.message_id already exists for Discord. Recording the tweet id
    now is what makes "reply the result under the pick that called it" possible
    later without a migration.
    """
    captured = []

    class _Conn:
        def execute(self, sql, params=None):
            captured.append((sql, params))
            return self
        def commit(self): pass

    xp._ledger(_Conn(), "x_free:2026-08-30", "x_free_pick", "555")
    sql, params = captured[0]
    assert "message_id" in sql
    assert params[3] == "555"


def test_the_pipeline_wires_both_surfaces_independently():
    """
    One surface failing must never suppress the other. X is wrapped in its own
    try so a bad tweet cannot cost a Discord recap, and vice versa.
    """
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "notify_x_free_pick" in src and "notify_x_results" in src
    i = src.index("notify_x_results")
    block = src[i - 400:i + 400]
    assert "except Exception" in block
    assert "unaffected" in block
