"""
Posting every released pre-game pick, and the settled recap, to X
(@signalbasepicks).

SCOPE. mike, 2026-08-30, chose the free pick plus the recap, with no links.
mike, 2026-10-18: every released pre-game pick is posted, and every pick
post is the same format. Discord's free pick is not an input to X.

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
from datetime import datetime, timedelta
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
    xp._assert_no_link("⚾ Yankees Over 8.5 -110 at DraftKings. Good to -120.")


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
    t = xp.render_pick(pick)
    assert len(t) <= xp.MAX_TWEET
    xp._assert_no_link(t)

    recap = {"wins": 10, "losses": 5, "units": 3.53,
             "by_sport": [{"sport": "MLB", "wins": 10, "losses": 5}]}
    r = xp.render_results(recap, "2026-08-30")
    assert len(r) <= xp.MAX_TWEET
    xp._assert_no_link(r)


def test_a_very_long_label_is_truncated_not_rejected():
    pick = {"sport": "NCAAF", "label": "X" * 400, "dk_odds": -110}
    assert len(xp.render_pick(pick)) <= xp.MAX_TWEET


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
    assert len(xp.render_pick(pick)) <= xp.MAX_TWEET


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
    assert "notify_x_picks" in src and "notify_x_results" in src
    i = src.index("notify_x_results")
    block = src[i - 400:i + 400]
    assert "except Exception" in block
    assert "unaffected" in block


# ── 4. the two surfaces publish the SAME thing at the SAME time ───────────────
# mike, 2026-09-02: "needs to be the same and fired at the same time."
#
# What went wrong: `--step settle` runs on all ~42 refresh passes and settles
# TODAY. notify_discord_results refuses a date that is not over; notify_x_results
# did not. So the first pass on which anything settled tweeted a mid-slate
# fragment and ledgered it, which then blocked the 6am post of the finished day
# forever. Measured before the fix, from push_sent.sent_at against the same
# settled universe the recap uses:
#
#     2026-08-30   X: 7-3 at 21:15 ET      Discord: 10-8    next 10:38 ET
#     2026-08-31   X: 1-1 at 20:36 ET      Discord: 14-14-1 next 06:04 ET
#     2026-09-01   X: 0-1 at 21:08 ET      Discord: 23-12   next 06:03 ET
#
# 0-1 and 23-12 are the same day (+9.91u). Each test below was watched failing
# with the fix backed out.

def _creds_on(monkeypatch):
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for name in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                 "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(name, "test-value")


def test_x_refuses_a_day_that_is_not_over(monkeypatch):
    """
    The guard must come BEFORE the database is opened, and a return of 0 is not
    enough evidence on its own: without the guard the call still returns 0 in a
    sandbox, because the connection failure is swallowed. So the assertion is
    that the connection was never opened at all.
    """
    _creds_on(monkeypatch)
    import data.db
    opened = []
    monkeypatch.setattr(data.db, "get_connection",
                        lambda *a, **k: opened.append(1))

    from datetime import datetime as _dt
    today = _dt.now(xp.ET).date().isoformat()
    tomorrow = (_dt.now(xp.ET).date() + timedelta(days=1)).isoformat()

    assert xp.notify_x_results(today) == 0
    assert xp.notify_x_results(tomorrow) == 0
    assert not opened, ("notify_x_results opened the database for a day that is "
                        "not over — it will tweet a partial mid-slate record "
                        "and ledger it, blocking the finished day")


def test_x_does_price_a_day_that_is_over(monkeypatch):
    """The guard must not be a blanket refusal: yesterday still goes out."""
    _creds_on(monkeypatch)
    import data.db
    opened = []

    class _Conn:
        def execute(self, *a, **k):
            raise RuntimeError("stop here — the point is that we got this far")

        def close(self):
            pass

    def _open(*a, **k):
        opened.append(1)
        return _Conn()

    monkeypatch.setattr(data.db, "get_connection", _open)
    from datetime import datetime as _dt
    clock = _dt.now(xp.ET)
    morning = clock.replace(hour=8, minute=0, second=0, microsecond=0)
    yesterday = (clock.date() - timedelta(days=1)).isoformat()
    xp.notify_x_results(yesterday, now=morning)
    assert opened, "a settled, finished day must still be published"


def test_x_refuses_a_finished_day_after_noon(monkeypatch):
    """Noon through 6:00am returns before the database, same as a day that
    is not over. A restatement uses this function too."""
    _creds_on(monkeypatch)
    import data.db
    opened = []
    monkeypatch.setattr(data.db, "get_connection",
                        lambda *a, **k: opened.append(1))
    from datetime import datetime as _dt
    clock = _dt.now(xp.ET)
    evening = clock.replace(hour=21, minute=56, second=0, microsecond=0)
    yesterday = (clock.date() - timedelta(days=1)).isoformat()
    assert xp.notify_x_results(yesterday, now=evening) == 0
    assert xp.notify_x_period(
        "week", clock.date(), clock.date(), "Week", now=evening) == 0
    assert not opened


def test_the_tweeted_record_carries_pushes():
    """
    2026-08-31 settled 14-14-1. Discord published 14-14-1; the tweet said 14-14,
    which is a different record for the same day — and the record is the entire
    pitch of the account.
    """
    text = xp.render_results(
        {"wins": 14, "losses": 14, "pushes": 1, "units": -1.341,
         "risked": 31.61, "by_sport": []}, "2026-08-31")
    assert "14-14-1" in text


def test_the_tweeted_record_carries_roi_like_the_embed():
    text = xp.render_results(
        {"wins": 23, "losses": 12, "pushes": 0, "units": 9.9084,
         "risked": 38.02, "by_sport": []}, "2026-09-01")
    assert "23-12" in text
    assert "+9.91u" in text
    assert "+26.1% ROI" in text


def test_a_day_with_nothing_risked_states_units_and_does_not_divide():
    text = xp.render_results(
        {"wins": 0, "losses": 0, "pushes": 2, "units": 0.0, "risked": 0.0,
         "by_sport": []}, "2026-09-01")
    assert "+0.00u" in text
    assert "ROI" not in text


def test_the_date_renders_on_this_machine():
    """
    `%-d` is a glibc extension: fine on the Railway worker, ValueError on
    Windows — which is the machine this repo's only quality gate runs on (§7).
    """
    assert xp.render_results(
        {"wins": 1, "losses": 0, "pushes": 0, "units": 1.0, "risked": 1.1,
         "by_sport": []}, "2026-09-02").startswith("\U0001F4CA Sep 2 results:")


def test_the_tweet_carries_the_days_clv_line_like_the_embed():
    """2026-09-10: the 09-09 recap was re-posted once the missing NFL CLV had
    been captured. Discord's embed changed (it shows CLV); the tweet did not,
    and X refused it: 403 "duplicate content". The tweet now states the
    day's beat-the-close share with its denominator, the embed's exact string."""
    text = xp.render_results(
        {"wins": 5, "losses": 5, "pushes": 0, "units": -0.537, "risked": 11.16,
         "clv": "38% beat close (3/8)",
         "by_sport": [{"sport": "MLB", "wins": 3, "losses": 4, "pushes": 0},
                      {"sport": "NFL", "wins": 2, "losses": 1, "pushes": 0}]},
        "2026-09-09")
    assert "38% beat close (3/8)" in text
    assert text.index("NFL 2-1") < text.index("38% beat close") < text.index("#")
    assert len(text) <= xp.MAX_TWEET


def test_a_day_with_nothing_graded_carries_no_clv_line():
    text = xp.render_results(
        {"wins": 1, "losses": 0, "pushes": 0, "units": 1.0, "risked": 1.1,
         "clv": "", "by_sport": []}, "2026-09-02")
    assert "beat close" not in text
    assert "\n\n" not in text, "an empty CLV must not leave a blank line"


def test_notify_x_results_passes_the_embeds_clv_string():
    import inspect
    src = inspect.getsource(xp.notify_x_results)
    assert '"clv": clv_line(t)' in src


def test_the_per_sport_split_is_not_permanently_empty():
    """`by_sport` was passed [] on every call, so this branch was dead code."""
    import inspect
    src = inspect.getsource(xp.notify_x_results)
    assert '"by_sport": []' not in src, "the per-sport split is still hard-coded empty"
    text = xp.render_results(
        {"wins": 3, "losses": 1, "pushes": 0, "units": 2.0, "risked": 4.4,
         "by_sport": [{"sport": "MLB", "wins": 2, "losses": 1, "pushes": 0},
                      {"sport": "NCAAF", "wins": 1, "losses": 0, "pushes": 1}]},
        "2026-09-01")
    assert "MLB 2-1" in text and "NCAAF 1-0-1" in text


# ── 5. X does not have a free pick ────────────────────────────────────────────
# Discord still chooses one free pick for its own channel. X posts the
# released slate and does not read that choice or wait for it.

def _fake_conn(discord_choice):
    """A connection whose only special row is Discord's free-pick choice."""
    class _Conn:
        _sql = ""

        def execute(self, sql, params=None):
            self._sql = str(sql)
            return self

        def fetchone(self):
            if "pg_try_advisory_lock" in self._sql:
                return (True,)
            if "discord_free_pick" in self._sql:
                return (discord_choice,)
            return None

        def fetchall(self):
            return []

        def commit(self):
            pass

        def close(self):
            pass
    return _Conn()


def test_x_posts_without_reading_discords_free_pick(monkeypatch):
    """Discord's recorded choice is not a tweet, and the free-pick pool is
    not consulted. The released slate is what posts."""
    _creds_on(monkeypatch)
    import config
    import data.db
    from tracking import discord_notifier as dn

    monkeypatch.setattr(config, "DISCORD_WEBHOOK_FREE",
                        "https://discord.example/webhook", raising=False)

    def _boom(*_a, **_k):
        raise AssertionError("X consulted the free-pick pool")

    monkeypatch.setattr(dn, "_free_pick_candidates", _boom)
    monkeypatch.setattr(dn, "_pick_free", _boom)
    monkeypatch.setattr(
        dn, "_new_signals",
        lambda conn, d, include_already_posted=False: [
            {"lock_key": "k-slate", "label": "NYY ML", "sport": "MLB",
             "dk_odds": -115, "home": "NYY", "away": "BOS", "side": "home"}])
    monkeypatch.setattr(data.db, "get_connection",
                        lambda *a, **k: _fake_conn("k17"))
    monkeypatch.setattr(xp, "_already_sent", lambda *a, **k: False)
    monkeypatch.setattr(xp, "_ledger", lambda *a, **k: None)

    posted = []

    def _deliver(text, dry_run=False, reply_to=None, allow_link=False):
        posted.append(text)
        return "id1", False

    monkeypatch.setattr(xp, "_deliver_tweet", _deliver)
    afternoon = datetime(2026, 9, 2, 16, 23, tzinfo=xp.ET)
    assert xp.notify_x_picks("2026-09-02", now=afternoon) == 1
    assert len(posted) == 1
    assert "NYY ML" in posted[0]
    assert "Free pick" not in posted[0]
    assert "More in Discord" not in posted[0]
    assert "#FreePicks" not in posted[0]
    assert "Pick 17" not in posted[0]


def test_discord_records_which_pick_it_posted():
    """Discord stores the chosen lock key on its own free-pick row. X does
    not read that row; the write is still what the free channel posted."""
    src = (Path(__file__).parent.parent / "tracking" / "discord_notifier.py"
           ).read_text(encoding="utf-8")
    i = src.index("INSERT INTO push_sent",
                  src.index("def notify_discord_free_pick"))
    block = src[i:i + 400]
    assert "discord_free_pick" in block
    assert "message_id" in block
    assert 'pick["lock_key"]' in block


def _split(n):
    """n sports, alphabetical, each with a realistically long record."""
    names = ["GOLF", "MLB", "NBA", "NCAAF", "NFL", "NHL", "UFC", "WNBA"][:n]
    return [{"sport": s, "wins": 14, "losses": 14, "pushes": 1} for s in names]


def test_the_per_sport_split_lists_every_sport_when_it_fits():
    """
    It used to take the first four and say nothing about the rest, which on an
    eight-sport day is the same class of bug this module was just fixed for: a
    silently partial number. Eight sports fit inside 280 characters.
    """
    text = xp.render_results(
        {"wins": 112, "losses": 112, "pushes": 8, "units": -3.0,
         "risked": 240.0, "by_sport": _split(8)}, "2026-09-01")
    assert len(text) <= xp.MAX_TWEET
    for sport in ("GOLF", "MLB", "NBA", "NCAAF", "NFL", "NHL", "UFC", "WNBA"):
        assert f"{sport} 14-14-1" in text, f"{sport} was dropped from the split"
    assert "more" not in text


def test_the_split_is_ordered_like_the_embed():
    """
    The embed lists its per-sport fields alphabetically (`sorted(by_sport...)`).
    Ordering the tweet by volume instead read better and made the two surfaces
    disagree on sequence for no reason — mike, 2026-09-02.
    """
    text = xp.render_results(
        {"wins": 3, "losses": 1, "pushes": 0, "units": 2.0, "risked": 4.4,
         "by_sport": _split(4)}, "2026-09-01")
    line = [x for x in text.split("\n") if "MLB" in x][0]
    assert line.index("GOLF") < line.index("MLB") < line.index("NBA") < line.index("NCAAF")

    import inspect
    src = inspect.getsource(xp.notify_x_results)
    assert "sorted(by_sport.items())" in src, (
        "notify_x_results must hand the renderer the same order the embed uses")


def test_a_split_that_cannot_fit_says_how_many_it_dropped():
    """Truncation is allowed; silent truncation is not."""
    long_ones = [{"sport": "NCAAF" + "X" * 30, "wins": 14, "losses": 14,
                  "pushes": 1} for _ in range(8)]
    text = xp.render_results(
        {"wins": 112, "losses": 112, "pushes": 8, "units": -3.0,
         "risked": 240.0, "by_sport": long_ones}, "2026-09-01")
    assert len(text) <= xp.MAX_TWEET
    assert "more" in text, "sports were dropped without saying so"
    assert text.endswith(xp.hashtags_for(None)), "the tags were truncated away"


# ── 6. every released pick, one format, posted once ──────────────────────────
# mike, 2026-10-18: the slate is the X post. X_POST_ALL_PICKS=0 posts no
# pick slate. There is no free-pick tweet.

def _slate():
    return [
        {"lock_key": "k-free", "label": "NYY ML", "sport": "MLB",
         "dk_odds": -115, "home": "NYY", "away": "BOS", "side": "home",
         "good_to": None},
        {"lock_key": "k-total", "label": "NYY vs BOS Over 8.5", "sport": "MLB",
         "dk_odds": -110, "home": "NYY", "away": "BOS", "side": "over",
         "good_to": None},
        {"lock_key": "k-nfl", "label": "SF -3.5", "sport": "NFL",
         "dk_odds": -110, "home": "SF", "away": "SEA", "side": "home",
         "good_to": None},
    ]


def _wire_slate(monkeypatch, slate, already=None):
    """Creds on, Discord chose k-free, ledger and network replaced."""
    _creds_on(monkeypatch)
    import data.db
    from tracking import discord_notifier as dn

    monkeypatch.setattr(dn, "_free_pick_candidates",
                        lambda conn, d: [slate[0]])
    monkeypatch.setattr(
        dn, "_new_signals",
        lambda conn, d, include_already_posted=False: list(slate))
    monkeypatch.setattr(data.db, "get_connection",
                        lambda *a, **k: _fake_conn("k-free"))
    sent = already or set()

    def _sent(conn, key, kind):
        return (key, kind) in sent

    monkeypatch.setattr(xp, "_already_sent", _sent)
    ledgered = []
    pace = {"last": None, "now": None}

    def _last(conn):
        if pace["last"] == "unreadable":
            raise RuntimeError("ledger unreadable")
        return pace["last"]

    monkeypatch.setattr(xp, "_latest_x_pick_sent", _last)

    def _remember(conn, key, kind, tweet_id):
        ledgered.append((key, kind, tweet_id))
        sent.add((key, kind))
        if kind == xp.X_PICK_KIND:
            pace["last"] = pace["now"]

    monkeypatch.setattr(xp, "_ledger", _remember)
    posted = []

    def _deliver(text, dry_run=False, reply_to=None, allow_link=False):
        posted.append(text)
        return f"id{len(posted)}", False

    monkeypatch.setattr(xp, "_deliver_tweet", _deliver)

    def post_at(when, dry_run=False):
        pace["now"] = when
        return xp.notify_x_picks("2026-10-18", dry_run=dry_run, now=when)

    return posted, ledgered, post_at, pace


def test_team_hashtags_use_the_nickname():
    from tracking.x_teams import team_hashtag, team_tags
    assert team_hashtag("MLB", "NYY") == "Yankees"
    assert team_hashtag("MLB", "BOS") == "RedSox"
    assert team_hashtag("NFL", "SF") == "49ers"
    assert team_hashtag("NFL", "WAS") == "Commanders"
    assert team_hashtag("NHL", "TOR") == "MapleLeafs"
    assert team_hashtag("NBA", "PHI") == "76ers"
    side = team_tags({"sport": "MLB", "home": "NYY", "away": "BOS", "side": "home"})
    assert side == ["#Yankees"]
    total = team_tags({"sport": "MLB", "home": "NYY", "away": "BOS", "side": "over"})
    assert total == ["#Yankees", "#RedSox"]


def test_college_nicknames_and_a_shared_mascot_falls_back_to_the_school():
    from tracking.x_teams import team_tags
    both = team_tags(
        {"sport": "NCAAF", "home": "Ohio State", "away": "Michigan", "side": "under"},
        {"Ohio State": "Buckeyes", "Michigan": "Wolverines"})
    assert both == ["#Buckeyes", "#Wolverines"]
    shared = team_tags(
        {"sport": "NCAAF", "home": "USC", "away": "Troy", "side": "under"},
        {"USC": "Trojans", "Troy": "Trojans"})
    assert shared == ["#USC", "#Troy"]


def test_every_pick_post_uses_the_same_format():
    side = xp.render_pick(
        {"sport": "MLB", "label": "NYY ML", "dk_odds": -115,
         "home": "NYY", "away": "BOS", "side": "home"})
    total = xp.render_pick(
        {"sport": "MLB", "label": "NYY vs BOS Over 8.5", "dk_odds": -110,
         "home": "NYY", "away": "BOS", "side": "over"})
    for text in (side, total):
        assert "Free pick" not in text
        assert "More in Discord" not in text
        assert "#FreePicks" not in text
        assert text.count("#") <= xp.MAX_PICK_HASHTAGS
        assert len(text) <= xp.MAX_TWEET
        xp._assert_no_link(text)
    assert "#Yankees" in side and "#MLB" in side and "#GamblingX" in side
    assert "#RedSox" not in side
    assert "#Yankees" in total and "#RedSox" in total and "#MLB" in total
    assert "#GamblingX" in total


def test_a_pick_shows_the_event_date_in_et_and_a_prop_shows_the_matchup():
    """A start after midnight UTC is still the previous evening in New York."""
    prop = xp.render_pick({
        "sport": "MLB", "label": "Aaron Judge Over 1.5 Hits", "dk_odds": -110,
        "home": "BOS", "away": "NYY", "side": "over",
        "prop_market": "player_hits",
        "commence": "2026-10-21T02:10:00+00:00",
    })
    assert "Tue 10/20" in prop
    assert "NYY @ BOS" in prop
    assert prop.index("NYY @ BOS") < prop.index("Tue 10/20")
    assert "#Yankees" in prop and "#RedSox" in prop
    assert len(prop) <= xp.MAX_TWEET


def test_a_side_that_omits_the_opponent_gains_the_matchup_when_it_fits():
    text = xp.render_pick({
        "sport": "MLB", "label": "NYY ML", "dk_odds": -115,
        "best_book": "draftkings", "best_odds": -115,
        "home": "BOS", "away": "NYY", "side": "away",
        "commence": "2026-10-20T23:10:00+00:00",
    })
    assert "NYY ML" in text
    assert "NYY @ BOS" in text
    assert "Tue 10/20" in text
    assert "#Yankees" in text and "#RedSox" not in text
    assert text.index("Tue 10/20") < text.index("#Yankees")


def test_a_total_that_already_names_both_clubs_does_not_repeat_the_matchup():
    text = xp.render_pick({
        "sport": "MLB", "label": "NYY vs BOS Over 8.5", "dk_odds": -105,
        "best_book": "fanduel", "best_odds": -105,
        "home": "BOS", "away": "NYY", "side": "over",
        "commence": "2026-10-20T23:10:00+00:00",
    })
    assert text.count("NYY") == 1 or "NYY vs BOS" in text
    assert "NYY @ BOS" not in text
    assert "Tue 10/20" in text


def test_a_long_post_drops_reach_tags_before_the_date_and_the_matchup():
    body = "X" * 250
    text = xp.assemble_text(
        body, ["#Yankees", "#RedSox"],
        ["#MLB", "#GamblingX", "#BettingTips"],
        keep=["NYY @ BOS", "Tue 10/20"])
    assert len(text) <= xp.MAX_TWEET
    assert "NYY @ BOS" in text and "Tue 10/20" in text
    assert text.index("Tue 10/20") < text.index("#Yankees")
    for dropped in ("#MLB", "#GamblingX", "#BettingTips"):
        assert dropped not in text


def test_a_long_post_drops_reach_tags_before_team_tags():
    body = "X" * 270
    text = xp.assemble_text(
        body, ["#Yankees", "#RedSox"], ["#MLB", "#GamblingX", "#BettingTips"])
    assert len(text) <= xp.MAX_TWEET
    assert text.endswith("#Yankees #RedSox")
    for dropped in ("#MLB", "#GamblingX", "#BettingTips"):
        assert dropped not in text


def test_freepicks_in_the_pool_is_dropped(monkeypatch):
    monkeypatch.setenv("X_HASHTAG_POOL", "FreePicks,CustomTag")
    pick = {"sport": "MLB", "home": "NYY", "away": "BOS", "side": "home"}
    _teams, reach = xp.pick_hashtags(pick)
    assert "#CustomTag" in reach
    assert "#FreePicks" not in reach
    assert "#GamblingX" not in reach
    text = xp.render_pick(
        {"sport": "MLB", "label": "NYY ML", "dk_odds": -115,
         "home": "NYY", "away": "BOS", "side": "home"})
    assert "#FreePicks" not in text and "#CustomTag" in text


def _afternoon():
    return datetime(2026, 10, 18, 16, 23, tzinfo=xp.ET)


def test_all_released_picks_are_posted_once_in_one_format(monkeypatch):
    """The same three picks still post, one per call, 10 minutes apart."""
    slate = _slate()
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, slate)
    start = _afternoon()
    assert post_at(start) == 1
    assert post_at(start + timedelta(minutes=9, seconds=59)) == 0
    assert post_at(start + timedelta(minutes=10)) == 1
    assert post_at(start + timedelta(minutes=20)) == 1
    assert post_at(start + timedelta(minutes=30)) == 0
    assert len(posted) == 3, posted
    assert all("Free pick" not in t and "More in Discord" not in t
               and "#FreePicks" not in t for t in posted)
    assert sum("NYY ML" in t for t in posted) == 1
    assert any("NYY ML" in t and "#Yankees" in t and "#MLB" in t for t in posted)
    assert any("Over 8.5" in t and "#Yankees" in t and "#RedSox" in t for t in posted)
    assert any("SF -3.5" in t and "#49ers" in t and "#NFL" in t for t in posted)
    assert {row[0] for row in ledgered} == {"k-free", "k-total", "k-nfl"}
    assert [row[0] for row in ledgered] == ["k-free", "k-total", "k-nfl"]
    assert all(kind == "x_pick" for _key, kind, _id in ledgered)
    assert not any(kind == "x_free_pick" for _key, kind, _id in ledgered)


def test_the_flag_off_posts_no_pick_slate(monkeypatch):
    monkeypatch.setenv("X_POST_ALL_PICKS", "0")
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, _slate())
    assert post_at(_afternoon()) == 0
    assert posted == []
    assert ledgered == []


def test_the_kill_switch_posts_no_pick_slate(monkeypatch):
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, _slate())
    monkeypatch.setenv("RUN_X_PUBLISHER", "0")
    assert post_at(_afternoon()) == 0
    assert posted == []
    assert ledgered == []


def test_a_pick_already_tweeted_is_not_posted_again(monkeypatch):
    posted, ledgered, post_at, _pace = _wire_slate(
        monkeypatch, _slate(), already={("k-total", "x_pick")})
    start = _afternoon()
    assert post_at(start) == 1
    assert post_at(start + timedelta(minutes=10)) == 1
    assert post_at(start + timedelta(minutes=20)) == 0
    assert not any("Over 8.5" in t for t in posted)
    assert any("SF -3.5" in t for t in posted)
    assert any("NYY ML" in t for t in posted)
    assert not any(key == "k-total" for key, _kind, _id in ledgered)


def test_a_rate_limit_does_not_ledger_and_the_same_pick_retries(monkeypatch):
    slate = _slate()
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, slate)
    calls = {"n": 0}

    def _deliver(text, dry_run=False, reply_to=None, allow_link=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return None, True
        posted.append(text)
        return f"id{calls['n']}", False

    monkeypatch.setattr(xp, "_deliver_tweet", _deliver)
    start = _afternoon()
    assert post_at(start) == 0
    assert posted == []
    assert ledgered == []
    assert calls["n"] == 1
    # Nothing was confirmed, so the gap does not start. The next call retries
    # the same pick.
    assert post_at(start) == 1
    assert len(posted) == 1
    assert "NYY ML" in posted[0]
    assert "Free pick" not in posted[0]
    assert ledgered[0][0] == "k-free"
    assert calls["n"] == 2


def test_quiet_hours_hold_the_pick_until_8am(monkeypatch):
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, _slate())
    assert xp._in_pick_quiet_hours(datetime(2026, 10, 19, 0, 59, tzinfo=xp.ET)) is False
    assert xp._in_pick_quiet_hours(datetime(2026, 10, 19, 1, 0, tzinfo=xp.ET)) is True
    assert xp._in_pick_quiet_hours(datetime(2026, 10, 19, 7, 59, tzinfo=xp.ET)) is True
    assert xp._in_pick_quiet_hours(datetime(2026, 10, 19, 8, 0, tzinfo=xp.ET)) is False
    assert post_at(datetime(2026, 10, 19, 1, 0, tzinfo=xp.ET)) == 0
    assert post_at(datetime(2026, 10, 19, 7, 59, tzinfo=xp.ET)) == 0
    assert posted == [] and ledgered == []
    assert post_at(datetime(2026, 10, 19, 8, 0, tzinfo=xp.ET)) == 1
    assert len(posted) == 1 and ledgered[0][0] == "k-free"


def test_a_pick_whose_game_has_started_is_dropped_and_not_ledgered(monkeypatch):
    slate = _slate()
    slate[0]["commence"] = "2026-10-18T16:00:00-04:00"
    slate[1]["commence"] = "2026-10-18T21:00:00-04:00"
    slate[2]["commence"] = "2026-10-19T07:00:00-04:00"
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, slate)
    eight = datetime(2026, 10, 19, 8, 0, tzinfo=xp.ET)
    assert post_at(datetime(2026, 10, 18, 16, 23, tzinfo=xp.ET)) == 1
    assert "Over 8.5" in posted[0]
    assert not any(key == "k-free" for key, _kind, _id in ledgered)
    assert post_at(eight) == 0
    assert not any(key == "k-nfl" for key, _kind, _id in ledgered)
    assert len(posted) == 1


def test_a_missing_commence_is_still_posted(monkeypatch):
    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, _slate())
    assert post_at(_afternoon()) == 1
    assert ledgered[0][0] == "k-free"


def test_an_unreadable_pick_clock_posts_nothing(monkeypatch):
    posted, ledgered, post_at, pace = _wire_slate(monkeypatch, _slate())
    pace["last"] = "unreadable"
    assert post_at(_afternoon()) == 0
    assert posted == [] and ledgered == []


def test_a_held_lock_posts_nothing(monkeypatch):
    from contextlib import contextmanager

    posted, ledgered, post_at, _pace = _wire_slate(monkeypatch, _slate())

    @contextmanager
    def _held(*_a, **_k):
        yield False

    monkeypatch.setattr("tracking.publish_lock.publish_lock", _held)
    assert post_at(_afternoon()) == 0
    assert posted == [] and ledgered == []


def test_the_pick_clock_uses_the_later_instant_across_the_dst_overlap():
    class _Conn:
        def execute(self, sql, params=None):
            return self

        def fetchall(self):
            # 01:30 EDT is 05:30 UTC. 01:00 EST is 06:00 UTC and is later,
            # even though the clock face looks earlier.
            return [
                ("2026-11-01T01:30:00-04:00",),
                ("2026-11-01T01:00:00-05:00",),
            ]

    got = xp._latest_x_pick_sent(_Conn())
    assert got == datetime.fromisoformat("2026-11-01T06:00:00+00:00")


def test_recaps_are_not_on_the_pick_clock():
    import inspect
    for fn in (xp.notify_x_results, xp.notify_x_period):
        src = inspect.getsource(fn)
        assert "PICK_MIN_GAP" not in src
        assert "_in_pick_quiet_hours" not in src
        assert "X_PICKS_LOCK" not in src


def test_pick_posts_use_a_session_connection_and_the_five_minute_job():
    import inspect
    src = inspect.getsource(xp.notify_x_picks)
    assert "session_mode=True" in src
    body = inspect.getsource(xp._post_released_picks)
    assert "X_PICKS_LOCK" in body
    assert "publish_lock(" in body
    sched = (Path(__file__).parent.parent / "scheduler.py").read_text(encoding="utf-8")
    job = sched[sched.index("def run_social_post_queue"):sched.index("def run_job_queue")]
    assert "notify_x_picks" in job
    assert "notify_x_results" not in job
    assert "notify_x_period" not in job


def test_a_tweet_without_media_omits_the_media_key(monkeypatch):
    _creds_on(monkeypatch)
    sent = {}

    class _R:
        status_code = 201
        text = ""

        def json(self):
            return {"data": {"id": "55"}}

    def _post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return _R()

    monkeypatch.setattr(xp.requests, "post", _post)
    assert xp.deliver_tweet("hello").tweet_id == "55"
    assert sent["url"] == xp.X_POST_URL
    assert sent["json"] == {"text": "hello"}


def test_media_ids_are_attached_and_a_bad_id_is_not_sent(monkeypatch):
    _creds_on(monkeypatch)
    sent = []

    class _R:
        status_code = 201
        text = ""

        def json(self):
            return {"data": {"id": "56"}}

    def _post(url, json=None, headers=None, timeout=None):
        sent.append(json)
        return _R()

    monkeypatch.setattr(xp.requests, "post", _post)
    delivered = xp.deliver_tweet("hello", media_ids=["11", "22"])
    assert delivered.outcome == "posted"
    assert sent == [{"text": "hello", "media": {"media_ids": ["11", "22"]}}]
    refused = xp.deliver_tweet("hello", media_ids=["nope"])
    assert refused.outcome == "refused"
    assert len(sent) == 1


def test_upload_tweet_image_uses_the_oauth_header_and_does_not_tweet(monkeypatch):
    import base64
    _creds_on(monkeypatch)
    png = b"\x89PNG\r\n\x1a\n" + b"pixels"
    sent = {}

    class _R:
        status_code = 200
        text = ""

        def json(self):
            return {"data": {"id": "1146654567674912769", "media_key": "3_1"}}

    def _post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        sent["auth"] = headers["Authorization"]
        sent["timeout"] = timeout
        return _R()

    monkeypatch.setattr(xp.requests, "post", _post)
    uploaded = xp.upload_tweet_image(png, "image/png")
    assert uploaded.outcome == "uploaded"
    assert uploaded.media_id == "1146654567674912769"
    assert sent["url"] == xp.X_MEDIA_UPLOAD_URL
    assert sent["url"] != xp.X_POST_URL
    assert sent["json"]["media_category"] == "tweet_image"
    assert sent["json"]["media_type"] == "image/png"
    assert sent["json"]["media"] == base64.b64encode(png).decode("ascii")
    assert sent["auth"].startswith("OAuth ")
    assert "oauth_signature" in sent["auth"]
    assert sent["timeout"] == 60


def test_a_refused_upload_returns_no_media_id(monkeypatch):
    _creds_on(monkeypatch)

    class _R:
        status_code = 403
        text = "forbidden"

        def json(self):
            return {}

    monkeypatch.setattr(xp.requests, "post", lambda *a, **k: _R())
    uploaded = xp.upload_tweet_image(b"\x89PNG\r\n\x1a\n", "image/png")
    assert uploaded.outcome == "rejected"
    assert uploaded.media_id is None
    assert "403" in uploaded.detail


def test_fetch_https_image_sniffs_bytes_and_refuses_gif(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"pixels"
    gif = b"GIF89a" + b"pixels"

    class _Resp:
        def __init__(self, body, status=200, url="https://cdn.example/a.png"):
            self._body = body
            self.status_code = status
            self.url = url
            self.closed = False

        def iter_content(self, _n):
            yield self._body

        def close(self):
            self.closed = True

    monkeypatch.setattr(xp.requests, "get", lambda url, timeout=None, stream=None: _Resp(png))
    fetched = xp.fetch_https_image("https://cdn.example/a.png")
    assert fetched.outcome == "fetched"
    assert fetched.media_type == "image/png"
    assert fetched.content == png

    monkeypatch.setattr(xp.requests, "get", lambda url, timeout=None, stream=None: _Resp(gif))
    refused = xp.fetch_https_image("https://cdn.example/a.gif")
    assert refused.outcome == "failed"
    assert refused.content is None
    assert "gif" in refused.detail

    monkeypatch.setattr(
        xp.requests, "get",
        lambda url, timeout=None, stream=None: _Resp(b"\xff\xd8\xff" + b"x" * (xp.MAX_IMAGE_BYTES + 1)))
    huge = xp.fetch_https_image("https://cdn.example/huge.jpg")
    assert huge.outcome == "failed"
    assert "5MB" in huge.detail

    assert xp.fetch_https_image("http://cdn.example/a.png").outcome == "failed"
