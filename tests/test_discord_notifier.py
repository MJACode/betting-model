"""
Pure-function tests for tracking/discord_notifier.py.

No DB and no network: the detection SQL is validated against production
separately, and everything here is the formatting / routing / delivery logic
that decides what a channel actually shows and — critically — what gets
ledgered as sent.
"""

import json
from datetime import datetime, timedelta

import pytest

from tracking import discord_notifier as dn


# ── Formatting ───────────────────────────────────────────────────────────────

def test_american_odds_formatting():
    assert dn._american(-166) == "-166"
    assert dn._american(125) == "+125"
    assert dn._american(-119.0) == "-119"
    # Prob-only picks (F5 O/U, UFC method, WNBA ML) carry no price.
    assert dn._american(None) == "N/A"


def test_matchup_is_sport_aware():
    # Standard team sports read away @ home.
    assert dn._matchup("MLB", "TEX", "LAA") == "LAA @ TEX"
    # UFC has no home team — "@" would be wrong.
    assert dn._matchup("UFC", "Fighter B", "Fighter A") == "Fighter A vs Fighter B"
    # A GOLF games row is a whole tournament; away_team is the literal 'FIELD'.
    assert dn._matchup("GOLF", "The Open Championship", "FIELD") == "The Open Championship"
    assert dn._matchup("MLB", None, None) == ""


def test_game_time_renders_in_eastern():
    # 23:17 UTC on 2026-08-23 is 7:17 PM ET (EDT, UTC-4).
    assert dn._game_time_et("2026-08-23T23:17:00+00:00") == "7:17 PM ET"
    # A Z suffix is the other shape stored in games.commence_time.
    assert dn._game_time_et("2026-08-23T18:36:00Z") == "2:36 PM ET"
    assert dn._game_time_et(None) == ""
    assert dn._game_time_et("not-a-timestamp") == ""


# ── Recap tallying ───────────────────────────────────────────────────────────

# The ACTUAL settled rows the production query returns for game_date 2026-08-21,
# copied verbatim so this test pins the tally against real data rather than
# numbers invented to match. Shape: (sport, model_id, result, profit_flat, bet).
_PROD_ROWS = [
    # (sport, model_id, result, kelly_fraction, dk_odds, clv_pct) - the exact
    # rows the recap query returns for 2026-08-21 under the CURRENT thresholds,
    # pulled from the live DB rather than invented. clv_pct is None on these:
    # CLV is captured only for game-level picks that have a closing DK price,
    # which is exactly why the published percentage carries its denominator.
    ("MLB",  "mlb_f5_moneyline",         "LOSS", 0.031240, -115.0, None),
    ("MLB",  "mlb_f5_moneyline",         "LOSS", 0.023579, -154.0, None),
    ("MLB",  "mlb_f5_moneyline",         "WIN",  0.032729, -140.0, None),
    ("MLB",  "mlb_f5_moneyline",         "WIN",  0.020339, -145.0, None),
    ("MLB",  "mlb_prop_batter_runs",     "WIN",  0.030984,  113.0, None),
    ("WNBA", "wnba_moneyline",           "WIN",  0.044999, -166.0, None),
    ("WNBA", "wnba_prop_player_assists", "WIN",  0.043752, -128.0, None),
]


def test_units_convention_matches_the_stated_rule():
    """Matt, 2026-08-27: "bet 1.1 Units to win 1 unit at -110 odds." The wager is
    what you RISK; what you win depends on the price."""
    assert dn.units_won(1.1, -110) == pytest.approx(1.0, abs=1e-9)
    assert dn.units_won(2.0, 150) == pytest.approx(3.0)
    assert dn._decimal_odds(-110) == pytest.approx(1.9090909, abs=1e-6)
    assert dn._decimal_odds(150) == pytest.approx(2.5)


def test_prob_only_picks_fall_back_to_the_settlement_price():
    """UFC method and some F5 picks carry no DK price. Settlement grades those at
    -110, so the recap must use the same fallback rather than dropping them."""
    assert dn.units_won(1.1, None) == pytest.approx(1.0, abs=1e-9)
    assert dn.units_won(1.1, 0) == pytest.approx(1.0, abs=1e-9)


def test_tally_reproduces_production_numbers_in_units():
    """Recomputed from the real 2026-08-21 rows above.

    These moved when the stake convention changed (2026-08-28): the wager is no
    longer kelly/1%, it is the price-aware risk behind a 1u-3u conviction. Fewer
    units are risked (23.0 -> 16.6) because conviction now tops out at 3u, and
    the units WON on a winner equal that conviction exactly."""
    by_sport = {}
    for r in _PROD_ROWS:
        by_sport.setdefault(r[0], []).append(r)

    mlb = dn._tally(by_sport["MLB"])
    assert (mlb["w"], mlb["l"], mlb["p"]) == (3, 2, 0)
    assert mlb["units"] == pytest.approx(0.3100, abs=0.001)   # flat 1u sizing
    assert mlb["risked"] == pytest.approx(6.4250, abs=0.001)

    wnba = dn._tally(by_sport["WNBA"])
    assert (wnba["w"], wnba["l"]) == (2, 0)
    assert wnba["units"] == pytest.approx(2.0000, abs=0.001)
    assert wnba["risked"] == pytest.approx(2.94, abs=0.001)   # flat 1u

    overall = dn._tally(_PROD_ROWS)
    assert (overall["w"], overall["l"]) == (5, 2)
    assert overall["units"] == pytest.approx(2.3100, abs=0.001)   # flat 1u
    assert overall["risked"] == pytest.approx(9.3650, abs=0.001)   # flat 1u


def test_a_loss_costs_the_full_stake_and_a_push_costs_nothing():
    """The asymmetry is the whole point of the risk/win convention."""
    # kelly 2.2% -> 1.5u conviction; at -110 that lays 1.65u.
    loss = dn._tally([("MLB", "mlb_moneyline", "LOSS", 0.022, -110, None)])
    assert loss["units"] == pytest.approx(-1.10, abs=0.001)   # flat 1u at -110
    assert loss["risked"] == pytest.approx(1.10, abs=0.001)

    push = dn._tally([("MLB", "mlb_moneyline", "PUSH", 0.022, -110, None)])
    assert push["units"] == 0.0
    assert push["risked"] == 0.0, "a push returns the stake, so nothing was risked"


def test_record_only_model_counts_in_record_but_never_in_money():
    """mlb_prop_batter_hr is tracked for its W-L but its P&L is not counted —
    most HR picks have no real DK price, so counting them fabricates P&L."""
    rows = [
        ("MLB", "mlb_moneyline", "WIN", 0.022, -110, None),
        ("MLB", "mlb_prop_batter_hr", "LOSS", 0.01, 400, None),
        ("MLB", "mlb_prop_batter_hr", "WIN", 0.01, 400, None),
    ]
    t = dn._tally(rows)
    assert (t["w"], t["l"]) == (2, 1), "record must include the HR picks"
    # The winner pays exactly its conviction back: 1.65u risked at -110 wins 1.5u.
    # That identity is what makes the to-win convention readable in the recap.
    assert t["units"] == pytest.approx(1.0, abs=0.001), "HR units must be excluded"
    assert t["risked"] == pytest.approx(1.10, abs=0.001), "HR stake must be excluded"
    assert t["record_only"] == 2


def test_tally_line_reports_units_and_degrades_to_record_only():
    line = dn._tally_line({"w": 3, "l": 2, "p": 0, "units": 1.7693,
                           "risked": 14.0, "record_only": 0})
    assert line.startswith("3-2 ")
    assert "+1.77u" in line and "+12.6% ROI" in line
    # Pushes surface only when they exist.
    assert dn._tally_line({"w": 1, "l": 1, "p": 2, "units": 0.0,
                           "risked": 2.0, "record_only": 0}).startswith("1-1-2 ")
    # An all-record-only day must not print a fabricated 0% ROI.
    assert dn._tally_line({"w": 1, "l": 5, "p": 0, "units": 0.0,
                           "risked": 0.0, "record_only": 6}) == "1-5 · record only"
    # A losing day reads as negative units, not negative dollars.
    assert "-3.00u" in dn._tally_line({"w": 0, "l": 2, "p": 0, "units": -3.0,
                                       "risked": 3.0, "record_only": 0})


# ── Embeds ───────────────────────────────────────────────────────────────────

def _signal(**over):
    base = dict(lock_key="k", label="TEX ML F5", sport="MLB", model_id="mlb_f5_moneyline",
                prob=0.6979, edge=0.0916, dk_odds=-154.0, kelly=0.02192, tier="HIGH",
                home="TEX", away="LAA", commence="2026-08-23T18:36:00+00:00",
                bet_link="https://sportsbook.draftkings.com/?outcomes=abc")
    base.update(over)
    return base


# ── Units ────────────────────────────────────────────────────────────────────

def test_conviction_is_flat_regardless_of_kelly():
    """The Kelly-derived 1..3u scale is retired (Matt, 2026-08-29).

    It sized UP into the only losing bucket: over 387 settled picks the
    highest-edge third won 50.4% for -7.2% ROI, against +16.8% for the lowest,
    and the same decline shows on raw edge, on Kelly and on price. Inverting
    was rejected too -- on a time split the top tier is +8.1% then -32.3%, so
    it is unstable rather than reliably backwards.
    """
    for k in (0.001, 0.025, 0.0328, 0.039, 0.05, 0.06, 0.5, 1.0):
        assert dn.conviction_for(k) == 1.0, k


def test_conviction_floors_at_one_not_a_half():
    """Matt: "1 being the lowest" — the old 0.5u floor is gone."""
    assert dn.conviction_for(0.002) == 1.0
    assert dn.conviction_for(0) == 1.0
    assert dn.conviction_for(None) == 1.0
    assert dn.conviction_for("") == 1.0


def test_the_minus_110_example_matt_gave():
    """"on a -110, the bet should be 1.1U to win 1U"."""
    s = dn.stake_for(0.0167, -110)               # kelly -> exactly 1u conviction
    assert s.conviction == 1.0
    assert round(s.risk, 2) == 1.1
    assert s.win == 1.0
    assert s.capped is False
    assert dn.fmt_stake(s) == "1.1u to win 1u"


def test_underdogs_risk_less_than_their_conviction():
    s = dn.stake_for(0.05, 150)                  # flat 1u to win, at +150
    assert s.conviction == 1.0
    assert round(s.risk, 2) == 0.67              # lay 0.67u to win 1u
    assert s.win == 1.0


def test_favourites_risk_more_until_the_cap_binds():
    s = dn.stake_for(0.0333, -135)               # median price, under the cap
    assert round(s.risk, 2) == 1.35              # lay 1.35u to win 1u
    assert s.win == 1.0
    assert s.capped is False


def test_risk_is_capped_at_three_units_and_the_payout_is_recomputed():
    """The cap is what reconciles "1-3 units to win" with "never more than 3
    units on 1 event". A capped bet must NOT still advertise a 3u win."""
    # At a flat 1u to win, the 3u cap needs a price below about -300; -147 no
    # longer binds. -400 does: it would lay 4u to win 1u.
    assert dn.stake_for(0.05, -147).capped is False
    s = dn.stake_for(0.05, -400)                 # uncapped this would lay 4u
    assert s.conviction == 1.0
    assert s.risk == 3.0
    assert s.capped is True
    assert round(s.win, 2) == 0.75               # recomputed, not left at 1
    assert s.win < s.conviction


def test_risk_and_win_always_agree_with_the_price():
    """The invariant that keeps a capped stake honest: risk x (dec-1) == win."""
    for odds in (-100, -110, -135, -147, -200, -325, -1000, 100, 150, 600):
        for k in (0.001, 0.0167, 0.025, 0.0333, 0.05, 0.2):
            s = dn.stake_for(k, odds)
            assert s.risk <= dn.MAX_RISK_UNITS + 1e-9, (odds, k, s.risk)
            dec = dn._decimal_or_none(odds)
            assert abs(s.risk * (dec - 1) - s.win) < 1e-9, (odds, k)


def test_unpriced_picks_publish_conviction_and_claim_no_payout():
    """Prob-only markets have no price to gross up against. Inventing one would
    assert a payout that does not exist."""
    s = dn.stake_for(0.05, None)
    assert s.priced is False
    assert s.conviction == 1.0
    assert dn.fmt_stake(s) == "1u"


def test_units_for_returns_the_risk_so_exposure_sums_are_money():
    assert round(dn.units_for(0.0167, -110), 2) == 1.1
    assert round(dn.units_for(0.05, 150), 2) == 0.67
    assert dn.units_for(0.05, None) == 1.0


def test_units_format_drops_the_trailing_zero():
    assert dn.fmt_units(2.0) == "2u"
    assert dn.fmt_units(3.5) == "3.5u"
    assert dn.fmt_units(0.5) == "0.5u"


# ── Embed shape ──────────────────────────────────────────────────────────────

def test_field_shows_only_game_time_odds_and_units():
    """The stake is now a PAIR, grossed up by the price: this 1.5u-conviction
    pick at -154 lays 2.3u to win 1.5u. It used to publish a bare "2u", which
    said nothing about what was actually at risk."""
    f = dn._signal_field(_signal())
    assert f["name"] == "TEX ML F5"
    assert f["value"] == (
        "LAA @ TEX \u00b7 2:36 PM ET\n"
        "`-154 @ DraftKings`\u2003\u00b7\u2003**1.5u to win 1u**")


def test_field_never_leaks_the_model_s_reasoning():
    """The channel gets the bet, not the model's reasoning. Guards against a
    future field being added back.

    The BOOK is deliberately no longer on this list (Matt, 2026-08-29: post the
    sportsbook the line was found at). A price with no book attached is not
    checkable -- "-115" invites "-115 where?" -- and the book is a fact about
    the market, not about how the model reasons. Probability and edge, which
    ARE the reasoning, stay banned.
    """
    blob = json.dumps(dn._picks_embed("MLB", [_signal()], "2026-08-23")).lower()
    for banned in ("model", "edge", "prob", "%", "stake", "$", "high"):
        assert banned not in blob, f"{banned!r} leaked into the Discord payload"


def test_the_book_is_published_with_the_price():
    """A quoted price must name where it was quoted."""
    blob = json.dumps(dn._picks_embed("MLB", [_signal()], "2026-08-23"))
    assert "-154 @ DraftKings" in blob


def test_a_prob_only_pick_names_no_book():
    """No price means no quote, so naming a book would assert one that never
    existed."""
    f = dn._signal_field(_signal(dk_odds=None))
    # "@" alone is not the check -- the matchup line is "LAA @ TEX". The price
    # segment is what must carry no book.
    price_seg = f["value"].split("\n")[-1]
    assert "@" not in price_seg, price_seg
    assert "N/A" in price_seg


def test_field_degrades_when_context_is_missing():
    f = dn._signal_field(_signal(dk_odds=None, commence=None, home=None, away=None))
    # No price to gross up against -> the bare conviction, claiming no payout.
    assert f["value"] == "`N/A`\u2003\u00b7\u2003**1u**", "no dangling separator"


# ── When we got it (Matt, 2026-08-30) ────────────────────────────────────────
#
# "It should be the time it writes to the database to know the first minute we
# get it." That is picks.created_at, and these pin both halves of it: the value
# rendered, and the column it is read from.

class _StampConn:
    """execute(...).fetchall() -> canned rows, remembering the SQL."""

    def __init__(self, rows):
        self._rows, self.sql = rows, ""

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return self._rows


def _et_now_iso(minutes_ago=0):
    return (datetime.now(dn.ET) - timedelta(minutes=minutes_ago)).isoformat()


def _freeze_now(monkeypatch, instant):
    """Pin dn's clock to `instant`.

    _posted_et decides whether to prefix the ET date by comparing the stamp
    against datetime.now(ET), so a test that builds its fixture from the real
    clock passes all day and fails after midnight ET -- which is exactly what
    this test used to do. Only _posted_et reads the clock on this path
    (_new_signals takes an explicit target_date), so freezing the module's
    datetime pins the seam under test and nothing else.
    """
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant

    monkeypatch.setattr(dn, "datetime", _Frozen)


# One stamp, read at two moments either side of ET midnight. Both are literals
# rather than re-derived with strftime: an expectation computed the same way as
# the code under test cannot catch a formatting change.
_WRITTEN = datetime(2026, 8, 29, 22, 32, tzinfo=dn.ET)


def test_a_signal_says_when_it_was_written(monkeypatch):
    """Real producer -> real renderer, the pattern that caught the live KeyError:
    a hand-written dict would drift from the query in exactly the way the
    renderer once did."""
    _freeze_now(monkeypatch, _WRITTEN.replace(hour=23, minute=59))
    conn = _StampConn([_row("k1", created_at=_WRITTEN.isoformat())])
    sig = dn._new_signals(conn, "2026-08-23")[0]
    value = dn._signal_field(sig)["value"]
    assert "posted 10:32 PM ET" in value, value
    # Same ET day -> no date prefix. Asserted so a regression that ALWAYS
    # prefixes cannot pass on the substring alone.
    assert "8/29" not in value, value


def test_the_same_stamp_read_after_et_midnight_carries_its_date(monkeypatch):
    """The branch that only fires some of the time, pinned so it always does.

    This is the flake in reverse: the stamp is unchanged, only the reader's
    clock moved past midnight, and the date prefix has to appear -- otherwise a
    signal written last night reads as tonight's.
    """
    _freeze_now(monkeypatch, datetime(2026, 8, 30, 0, 2, tzinfo=dn.ET))
    conn = _StampConn([_row("k1", created_at=_WRITTEN.isoformat())])
    sig = dn._new_signals(conn, "2026-08-23")[0]
    assert "posted Sat 8/29, 10:32 PM ET" in dn._signal_field(sig)["value"]


def test_a_pre_game_stamp_is_to_the_minute_not_the_second(monkeypatch):
    """Seconds are the live board's resolution -- a pre-game price is stable for
    hours, so second-level precision there is false precision."""
    _freeze_now(monkeypatch, _WRITTEN.replace(hour=23, minute=59))
    sig = dn._new_signals(_StampConn([_row("k1", created_at=_WRITTEN.isoformat())]),
                          "2026-08-23")[0]
    stamp = dn._signal_field(sig)["value"].split("posted ")[-1]
    assert stamp == "10:32 PM ET", stamp


def test_a_signal_posted_on_an_earlier_day_carries_its_date(monkeypatch):
    """An NFL opener locks days before kickoff. A bare "9:31 AM ET" on a
    Saturday board would read as this morning.

    This one could not flake -- three days back is never today -- but it built
    its expectation with the same strftime call as the code under test, which
    is a mirror rather than a check. Pinned instant, literal expectation.
    """
    _freeze_now(monkeypatch, datetime(2026, 8, 30, 12, 0, tzinfo=dn.ET))
    old = datetime(2026, 8, 27, 9, 31, tzinfo=dn.ET)          # three days back
    sig = dn._new_signals(_StampConn([_row("k1", created_at=old.isoformat())]),
                          "2026-08-23")[0]
    value = dn._signal_field(sig)["value"]
    assert "posted Thu 8/27, 9:31 AM ET" in value, value


def test_a_signal_with_no_pick_row_publishes_no_stamp():
    """The LATERAL misses -> no stamp, rather than falling back to
    opening_signals.locked_at, which is the CAPTURE clock and would make an old
    signal look newly posted."""
    sig = dn._new_signals(_StampConn([_row("k1", created_at=None)]), "2026-08-23")[0]
    assert "posted" not in dn._signal_field(sig)["value"]


@pytest.mark.parametrize("producer", ["_new_signals", "_locked_signals"])
def test_the_stamp_is_read_from_the_pick_row_not_the_capture_step(producer):
    """The column is the requirement, not an implementation detail: locked_at is
    when capture ran (3:18pm picks were captured at 4:31pm on 2026-08-29), so it
    would overstate how fresh a signal is."""
    conn = _StampConn([_row("k1")])
    getattr(dn, producer)(conn, "2026-08-23")
    assert "p.created_at" in conn.sql
    assert "pk.created_at" in conn.sql


def test_the_free_pick_is_stamped_too():
    """Same question, more public audience: how fresh is this?"""
    pick = {"lock_key": "k", "label": "TEX ML", "sport": "MLB", "dk_odds": -150.0,
            "kelly": 0.02, "home": "TEX", "away": "LAA",
            "commence": "2026-08-23T18:36:00+00:00", "posted_at": _et_now_iso()}
    blob = json.dumps(dn._free_pick_embed(pick, "2026-08-23"))
    assert "posted" in blob


def test_the_stamp_does_not_leak_the_model_s_reasoning():
    """The leak guard must hold with the new field present."""
    sig = _signal(posted_at=_et_now_iso())
    blob = json.dumps(dn._picks_embed("MLB", [sig], "2026-08-23")).lower()
    for banned in ("model", "edge", "prob", "%", "stake", "$", "high"):
        assert banned not in blob, f"{banned!r} leaked into the Discord payload"


def test_a_malformed_timestamp_drops_the_stamp_rather_than_raising():
    """Decoration must never be able to take a post down (the live KeyError)."""
    assert dn._posted_et("not a timestamp") == ""
    assert dn._posted_et(None) == ""


def test_embed_titles_by_sport_and_date():
    e = dn._picks_embed("MLB", [_signal()], "2026-08-23")
    assert e["title"] == "\u26be MLB Picks \u00b7 Sun Aug 23"
    live = dn._picks_embed("MLB", [_signal()], "2026-08-23", live=True)
    assert "LIVE" in live["title"] and live["color"] == dn._COLOR_LIVE


def test_slate_is_one_embed_not_one_per_pick(monkeypatch):
    """A stack of one-pick embeds is what made the channel ugly."""
    posts = []
    monkeypatch.setattr(dn, "_post",
                        lambda url, payload: (posts.append(payload), "m1")[1])
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    chunks = dn._post_picks("http://hook", "MLB", [_signal()] * 8, "2026-08-23")
    assert sum(len(c) for c, _ in chunks) == 8
    assert [mid for _, mid in chunks] == ["m1"], "the message id comes back"
    assert len(posts) == 1, "8 picks must be ONE message"
    assert len(posts[0]["embeds"]) == 1
    assert len(posts[0]["embeds"][0]["fields"]) == 8


def test_slate_chunks_at_discords_field_cap(monkeypatch):
    posts = []
    monkeypatch.setattr(dn, "_post",
                        lambda url, payload: (posts.append(payload), f"m{len(posts)}")[1])
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    chunks = dn._post_picks("http://hook", "MLB", [_signal()] * 30, "2026-08-23")
    assert sum(len(c) for c, _ in chunks) == 30
    assert [mid for _, mid in chunks] == ["m1", "m2"], "one id per chunk"
    assert [len(p["embeds"][0]["fields"]) for p in posts] == [25, 5]


# ── Routing ──────────────────────────────────────────────────────────────────

def test_sport_routes_to_its_own_channel_then_the_default(monkeypatch):
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {"MLB": "http://mlb"})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "http://default")
    assert dn._webhook_for_sport("MLB") == "http://mlb"
    assert dn._webhook_for_sport("NFL") == "http://default"

    # With no default set, an unmapped sport routes nowhere rather than dumping
    # every sport into one channel.
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    assert dn._webhook_for_sport("NFL") is None


def test_configured_is_false_only_when_nothing_is_set(monkeypatch):
    for attr in ("DISCORD_WEBHOOK_DEFAULT", "DISCORD_WEBHOOK_LIVE", "DISCORD_WEBHOOK_RESULTS"):
        monkeypatch.setattr(dn.config, attr, "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {})
    assert dn._configured() is False
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_RESULTS", "http://x")
    assert dn._configured() is True


# ── Delivery / retry ─────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload or {}, text

    def json(self):
        return self._payload


def test_post_succeeds_on_discords_204(monkeypatch):
    """204 has no body, so there is no id — but the post DID land, so the
    return must stay truthy or the caller would refuse to ledger it."""
    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: _Resp(204))
    assert dn._post("http://hook", {}) == dn._POST_OK_NO_ID


def test_post_retries_a_429_then_succeeds(monkeypatch):
    calls = []

    def fake_post(*_a, **_k):
        calls.append(1)
        return _Resp(429, {"retry_after": 0.5}) if len(calls) == 1 else _Resp(204)

    monkeypatch.setattr(dn.requests, "post", fake_post)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    assert dn._post("http://hook", {})
    assert len(calls) == 2


def test_post_gives_up_on_a_bad_webhook_without_raising(monkeypatch):
    """A deleted/invalid webhook is a 404. It must report failure (so nothing is
    ledgered) but never raise into the pipeline."""
    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: _Resp(404, text="Unknown Webhook"))
    assert not dn._post("http://hook", {})


def test_post_returns_false_when_the_network_is_down(monkeypatch):
    def boom(*_a, **_k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(dn.requests, "post", boom)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    assert not dn._post("http://hook", {})


def test_partial_delivery_reports_only_what_landed(monkeypatch):
    """The second chunk fails, so only the first chunk's embeds count as sent —
    this is what keeps the undelivered signals un-ledgered and retryable."""
    calls = []

    def fake_post(_url, _payload):
        calls.append(1)
        return "m1" if len(calls) == 1 else None

    monkeypatch.setattr(dn, "_post", fake_post)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    chunks = dn._post_picks("http://hook", "MLB", [_signal()] * 30, "2026-08-23")
    assert sum(len(c) for c, _ in chunks) == 25, \
        "must not claim the failed chunk was delivered"
    assert len(chunks) == 1, "and must not return an id for a chunk that failed"


# ── End-to-end: what gets ledgered ───────────────────────────────────────────

class _FakeResult:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return self._rows
    def fetchone(self): return self._rows[0] if self._rows else None


class _FakeConn:
    """Mimics data.db.DBConnection: execute() returns a result, plus commit/close.
    Records every INSERT so a test can assert exactly what was ledgered."""

    def __init__(self, select_rows):
        self.select_rows, self.inserts, self.commits = select_rows, [], 0

    def execute(self, sql, params=None):
        if sql.strip().upper().startswith("INSERT"):
            self.inserts.append(params)
            return _FakeResult([])
        return _FakeResult(self.select_rows)

    def commit(self): self.commits += 1
    def close(self): pass


def _row(lock_key, sport="MLB", created_at="2026-08-23T14:07:00+00:00"):
    # Column order must match _new_signals' SELECT list. The last two come from
    # the picks LATERAL: the betslip link, and WHEN the pick row was written.
    return (lock_key, f"label {lock_key}", sport, "mlb_moneyline", 0.72, 0.11,
            -150.0, 0.02, "HIGH", "TEX", "LAA", "2026-08-23T18:36:00+00:00",
            None, created_at)


def _setup(monkeypatch, conn, webhooks=None):
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", webhooks if webhooks is not None else {"MLB": "http://mlb"})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_LIVE", "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_RESULTS", "")
    monkeypatch.setattr(dn.config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)


def test_successful_post_ledgers_every_signal(monkeypatch):
    conn = _FakeConn([_row(f"k{i}") for i in range(3)])
    _setup(monkeypatch, conn)
    monkeypatch.setattr(dn, "_post", lambda url, payload: True)

    assert dn.notify_discord_signals(target_date="2026-08-23") == 3
    assert [p[0] for p in conn.inserts] == ["k0", "k1", "k2"]
    assert conn.commits == 1


def test_failed_post_ledgers_nothing_so_the_signal_retries(monkeypatch):
    """The whole point of not ledgering optimistically: a down webhook must leave
    the signals eligible for the next refresh pass."""
    conn = _FakeConn([_row(f"k{i}") for i in range(3)])
    _setup(monkeypatch, conn)
    monkeypatch.setattr(dn, "_post", lambda url, payload: False)

    assert dn.notify_discord_signals(target_date="2026-08-23") == 0
    assert conn.inserts == [], "a failed post must not be recorded as sent"


def test_unmapped_sport_is_skipped_without_being_consumed(monkeypatch):
    """Add the NFL channel at noon and the day's NFL signals still land — they
    were never marked as sent while the channel was missing."""
    conn = _FakeConn([_row("mlb1", "MLB"), _row("nfl1", "NFL")])
    _setup(monkeypatch, conn, webhooks={"MLB": "http://mlb"})
    monkeypatch.setattr(dn, "_post", lambda url, payload: True)

    assert dn.notify_discord_signals(target_date="2026-08-23") == 1
    assert [p[0] for p in conn.inserts] == ["mlb1"], "NFL must not be ledgered"


def test_per_run_cap_holds_the_overflow_for_the_next_pass(monkeypatch):
    conn = _FakeConn([_row(f"k{i}") for i in range(30)])
    _setup(monkeypatch, conn)
    monkeypatch.setattr(dn.config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    monkeypatch.setattr(dn, "_post", lambda url, payload: True)

    assert dn.notify_discord_signals(target_date="2026-08-23") == 20
    assert len(conn.inserts) == 20, "the 10 held back must stay un-ledgered"


def test_dry_run_posts_nothing_and_ledgers_nothing(monkeypatch):
    conn = _FakeConn([_row("k0")])
    _setup(monkeypatch, conn)
    posted = []
    monkeypatch.setattr(dn, "_post", lambda url, payload: posted.append(payload) or True)

    dn.notify_discord_signals(target_date="2026-08-23", dry_run=True)
    assert posted == [] and conn.inserts == [] and conn.commits == 0


def test_signals_are_grouped_into_one_message_per_sport(monkeypatch):
    conn = _FakeConn([_row("m1", "MLB"), _row("m2", "MLB"), _row("n1", "NFL")])
    _setup(monkeypatch, conn, webhooks={"MLB": "http://mlb", "NFL": "http://nfl"})
    seen = []
    monkeypatch.setattr(dn, "_post", lambda url, payload: seen.append((url, payload)) or True)

    assert dn.notify_discord_signals(target_date="2026-08-23") == 3
    by_url = {u: p for u, p in seen}
    assert len(by_url["http://mlb"]["embeds"][0]["fields"]) == 2
    assert len(by_url["http://nfl"]["embeds"][0]["fields"]) == 1
    assert "MLB" in by_url["http://mlb"]["embeds"][0]["title"]
    assert "NFL" in by_url["http://nfl"]["embeds"][0]["title"]


def test_no_webhooks_configured_is_a_clean_no_op(monkeypatch):
    """Nothing configured must not even open a DB connection."""
    _setup(monkeypatch, None, webhooks={})
    monkeypatch.setattr(dn, "get_connection",
                        lambda: (_ for _ in ()).throw(AssertionError("DB opened")))
    assert dn.notify_discord_signals(target_date="2026-08-23") == 0


# ── Free pick of the day ─────────────────────────────────────────────────────

def _cand(sport, label="Some pick", odds=-110, kelly=0.02, lock=None):
    return {"lock_key": lock or f"{sport}:{label}", "label": label, "sport": sport,
            "dk_odds": odds, "kelly": kelly, "home": "HOU", "away": "SEA",
            "commence": "2026-08-27T23:10:00Z"}


def test_free_pick_prefers_nfl_once_the_season_starts():
    """Matt: "should be an NFL pick when the season starts, but MLB and WNBA is
    ok for now." Priority order does this with no date logic — the free pick
    becomes an NFL pick the moment NFL produces signals."""
    pool = [_cand("MLB"), _cand("WNBA"), _cand("NFL", "NFL pick")]
    for _ in range(25):                       # selection is random within a sport
        assert dn._pick_free(pool)["sport"] == "NFL"


def test_free_pick_falls_back_to_any_sport_before_the_nfl_season():
    pool = [_cand("MLB"), _cand("WNBA")]
    picked = {dn._pick_free(pool)["sport"] for _ in range(50)}
    assert picked <= {"MLB", "WNBA"} and picked, "must pick from what exists"


def test_free_pick_is_none_when_nothing_qualifies():
    """Zero picks is a valid day — the channel stays quiet rather than posting
    something that did not clear the cut."""
    assert dn._pick_free([]) is None


def test_free_pick_selection_is_actually_random():
    pool = [_cand("MLB", f"pick {i}", lock=f"k{i}") for i in range(6)]
    seen = {dn._pick_free(pool)["lock_key"] for _ in range(200)}
    assert len(seen) > 1, "a fixed choice would defeat 'one random pick'"


def test_free_pick_never_leaks_model_edge_or_book(monkeypatch):
    """Same rule as the sport channels, and it matters most here: this is the
    most public channel. Game, time, odds, units — nothing else."""
    sent = {}
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_FREE", "https://hook")
    monkeypatch.setattr(dn, "_post", lambda url, payload: sent.update(payload) or True)
    conn = _FakeConn([])
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_free_pick_candidates",
                        lambda c, d: [_cand("MLB", "SEA ML", odds=-118, kelly=0.031)])
    assert dn.notify_discord_free_pick("2026-08-27") == 1
    blob = json.dumps(sent).lower()
    # The BOOK is deliberately absent from this list now (Matt, 2026-08-29):
    # a price must name where it was quoted. Reasoning stays banned.
    for leak in ("edge", "model_prob", "probability", "kelly"):
        assert leak not in blob, f"free pick must not expose {leak}"
    # Flat 1u to win; at -118 that lays 1.2u.
    assert "-118" in blob and "1.2u to win 1u" in blob


def test_free_pick_posts_once_per_day(monkeypatch):
    """~42 passes run per day; only the first with a qualifying signal posts."""
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_FREE", "https://hook")
    monkeypatch.setattr(dn, "_post", lambda url, payload: True)
    conn = _FakeConn([(1,)])          # ledger row already present
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_free_pick_candidates",
                        lambda c, d: [_cand("MLB")])
    assert dn.notify_discord_free_pick("2026-08-27") == 0


def test_free_pick_does_not_fall_back_to_the_default_channel(monkeypatch):
    """A distinct, more public audience: an unset variable must post nothing
    rather than leak the free pick into the catch-all channel."""
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_FREE", "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "https://catch-all")
    monkeypatch.setattr(dn, "_post",
                        lambda *a: pytest.fail("must not post without its own webhook"))
    assert dn.notify_discord_free_pick("2026-08-27") == 0


def test_failed_free_post_ledgers_nothing_so_it_retries(monkeypatch):
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_FREE", "https://hook")
    monkeypatch.setattr(dn, "_post", lambda url, payload: False)
    conn = _FakeConn([])
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    monkeypatch.setattr(dn, "_free_pick_candidates", lambda c, d: [_cand("MLB")])
    assert dn.notify_discord_free_pick("2026-08-27") == 0
    assert conn.inserts == [], "a failed post must ledger nothing so it retries"


# ── Restatement ──────────────────────────────────────────────────────────────

def _restate_env(monkeypatch, ledger: set, signals: list, ok=True):
    """Wire the notifier to a fake webhook + ledger. Returns the posts list."""
    posts = []
    monkeypatch.setattr(dn, "_post", lambda url, payload: (posts.append((url, payload)), ok)[1])
    monkeypatch.setattr(dn.time, "sleep", lambda *_: None)
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS",
                        {"MLB": "http://x/mlb", "WNBA": "http://x/wnba"}, raising=False)
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)

    class _Conn:
        def execute(self, sql, params=None):
            import types as _t
            if "SELECT 1 FROM push_sent" in sql:
                return _t.SimpleNamespace(
                    fetchone=lambda: (1,) if params[0] in ledger else None)
            if "INSERT INTO push_sent" in sql:
                ledger.add(params[0])
            return _t.SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])
        def commit(self): pass
        def close(self): pass

    monkeypatch.setattr(dn, "get_connection", lambda: _Conn())
    monkeypatch.setattr(dn, "_locked_signals", lambda conn, d: signals)
    return posts


def _restate_signals():
    """The real 2026-08-28 slate that triggered this feature."""
    raw = [
        ("MLB", "mlb_f5_moneyline", "LAA ML F5", 100.0, 0.03812),
        ("MLB", "mlb_moneyline", "TB ML", -135.0, 0.03483),
        ("WNBA", "wnba_prop_player_assists", "Erica Wheeler Over 3.5 Ast", -132.0, 0.03509),
    ]
    return [{"lock_key": f"k{i}", "label": lbl, "sport": sp, "model_id": mid,
             "prob": 0.7, "edge": 0.15, "dk_odds": o, "kelly": k, "tier": "HIGH",
             "home": "TB", "away": "LAA",
             "commence": "2026-08-28T22:36:00+00:00", "bet_link": None}
            for i, (sp, mid, lbl, o, k) in enumerate(raw)]


def test_restate_posts_a_labelled_correction_with_the_new_stakes(monkeypatch):
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals())
    n = dn.notify_discord_restate("2026-08-28")

    assert n == 3
    # ONE message per channel: the note rides on the slate embed. Posting them
    # separately meant a 429 in between left a "corrected stakes" header with
    # nothing under it, and the retry added a second header — seen live at
    # 2026-08-28 13:19.
    assert len(posts) == 2, "one atomic message per channel, not note + slate"
    for _, payload in posts:
        embed = payload["embeds"][0]
        assert "units to win" in embed["description"], "the note travels with the picks"
        assert embed["fields"], "and the picks are in the same message"

    blob = json.dumps(posts)
    assert "1u to win 1u" in blob              # +100, flat 1u
    assert "1.4u to win 1u" in blob            # -135, flat 1u
    assert "1.3u to win 1u" in blob            # -132, flat 1u
    # The old convention must be gone.
    assert "**4u**" not in blob and "**3.5u**" not in blob


def test_restate_fires_exactly_once(monkeypatch):
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals())
    assert dn.notify_discord_restate("2026-08-28") == 3
    before = len(posts)
    assert dn.notify_discord_restate("2026-08-28") == 0, "second pass must no-op"
    assert len(posts) == before, "and must post nothing"


def test_restate_never_fires_for_an_unlisted_date(monkeypatch):
    """The date list is the whole safety mechanism: without it, every slate on
    every date would be re-posted."""
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals())
    assert dn.notify_discord_restate("2026-08-29") == 0
    assert posts == []
    assert "2026-08-29" not in dn.DISCORD_RESTATE_DATES


def test_a_failed_restate_ledgers_nothing_so_it_retries(monkeypatch):
    """Same inversion as the rest of this module: only a CONFIRMED delivery is
    consumed. A half-posted correction that could never finish would be worse
    than leaving the stale numbers up."""
    ledger: set = set()
    _restate_env(monkeypatch, ledger, _restate_signals(), ok=False)
    assert dn.notify_discord_restate("2026-08-28") == 0
    assert ledger == set()


def test_restate_reuses_the_normal_rendering_path(monkeypatch):
    """A restated stake must be byte-identical to what the next slate would
    publish — otherwise the correction could itself be wrong."""
    ledger: set = set()
    sigs = _restate_signals()
    posts = _restate_env(monkeypatch, ledger, sigs)
    dn.notify_discord_restate("2026-08-28")
    slate = [p for _, p in posts if p["embeds"][0].get("fields")][0]["embeds"][0]
    assert slate["fields"][0] == dn._signal_field(sigs[0])


# ── Message ids: making a posted message reachable ───────────────────────────

class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b, self.text = code, body or {}, ""
    def json(self):
        return self._b


def test_post_captures_the_message_id(monkeypatch):
    """?wait=true is the whole point: without it Discord answers 204 with no
    body, the id is lost, and the message can never be edited or deleted."""
    seen = {}
    def fake_post(url, json=None, timeout=None):
        seen["url"] = url
        return _Resp(200, {"id": "1234567890"})
    monkeypatch.setattr(dn.requests, "post", fake_post)
    assert dn._post("https://hook/abc", {"embeds": []}) == "1234567890"
    assert "wait=true" in seen["url"]


def test_post_stays_truthy_on_a_bare_204_but_is_not_addressable(monkeypatch):
    """A proxy could strip ?wait=. The boolean contract every caller relies on
    must survive that, WITHOUT pretending we can reach the message."""
    monkeypatch.setattr(dn.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(204))
    v = dn._post("https://hook/abc", {})
    assert v and v == dn._POST_OK_NO_ID
    assert dn._delete_message("https://hook/abc", v) is False


def test_post_failure_is_falsy(monkeypatch):
    monkeypatch.setattr(dn.requests, "post",
                        lambda url, json=None, timeout=None: _Resp(400))
    assert not dn._post("https://hook/abc", {})


def test_delete_targets_the_webhook_message_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(dn.requests, "delete",
                        lambda url, timeout=None: (calls.append(url), _Resp(204))[1])
    assert dn._delete_message("https://hook/abc?wait=true", "42")
    assert calls == ["https://hook/abc/messages/42"]


def test_delete_treats_an_already_gone_message_as_done(monkeypatch):
    """The goal is that the message is not in the channel, not that WE removed
    it — so a 404 is success, and a retry never gets stuck."""
    monkeypatch.setattr(dn.requests, "delete",
                        lambda url, timeout=None: _Resp(404))
    assert dn._delete_message("https://hook/abc", "42") is True


def test_delete_never_raises_when_the_network_is_down(monkeypatch):
    def boom(url, timeout=None):
        raise OSError("network down")
    monkeypatch.setattr(dn.requests, "delete", boom)
    assert dn._delete_message("https://hook/abc", "42") is False


def test_restate_deletes_the_stale_post_when_the_id_is_known(monkeypatch):
    """The point of storing ids: a correction clears the stale numbers instead
    of stacking a second slate beneath them."""
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals())
    deleted = []
    monkeypatch.setattr(dn, "_delete_posted",
                        lambda conn, d, sport, kind: (deleted.append((d, sport, kind)), 1)[1])
    assert dn.notify_discord_restate("2026-08-28") == 3
    assert [x[1] for x in deleted] == ["MLB", "WNBA"]
    assert all(x[2] == "discord_signal" for x in deleted)
    assert posts, "the corrected slate still posts after the delete"


def test_restate_still_corrects_when_no_id_was_stored(monkeypatch):
    """2026-08-28's own case: those messages predate id capture, so they cannot
    be removed. The correction must still post rather than silently doing
    nothing."""
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals())
    monkeypatch.setattr(dn, "_delete_posted", lambda *a, **k: 0)
    assert dn.notify_discord_restate("2026-08-28") == 3
    assert len(posts) == 2, "one message per channel"
    assert all(p["embeds"][0].get("description") for _, p in posts)


def test_delete_posted_degrades_when_the_column_is_missing(monkeypatch):
    """The column arrives via a migration on the first pass after merge. A pass
    that runs before it must warn and move on, not red the step."""
    class _Conn:
        def execute(self, sql, params=None):
            raise Exception('column "message_id" does not exist')
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS",
                        {"MLB": "https://hook/mlb"}, raising=False)
    assert dn._delete_posted(_Conn(), "2026-08-28", "MLB", "discord_signal") == 0


def test_a_rate_limited_restate_leaves_nothing_half_posted(monkeypatch):
    """The live failure this design change came from: on 2026-08-28 the note
    posted as its own message and the slate 429'd, which would have left a
    'corrected stakes' header with no corrected picks under it — and the retry
    would have added a second header. One atomic message per channel makes that
    impossible: either the whole correction lands or none of it does."""
    ledger: set = set()
    posts = _restate_env(monkeypatch, ledger, _restate_signals(), ok=False)
    monkeypatch.setattr(dn, "_delete_posted", lambda *a, **k: 0)
    assert dn.notify_discord_restate("2026-08-28") == 0
    assert ledger == set(), "un-ledgered, so the next pass retries"


def test_slate_note_rides_only_on_the_first_chunk(monkeypatch):
    """A 30-pick slate pages at Discord's 25-field cap. Repeating the correction
    header above every page would be noise."""
    posts = []
    monkeypatch.setattr(dn, "_post",
                        lambda url, payload: (posts.append(payload), f"m{len(posts)}")[1])
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    dn._post_picks("http://hook", "MLB", [_signal()] * 30, "2026-08-23", note="HEADS UP")
    assert posts[0]["embeds"][0].get("description") == "HEADS UP"
    assert "description" not in posts[1]["embeds"][0]


def test_a_429_reports_what_discord_asked_for(monkeypatch):
    """'still rate-limited after retries' on its own is undiagnosable — a
    one-second burst limit and a multi-minute ban look identical, and the fix
    differs. The requested delay must reach the log."""
    warned = []
    monkeypatch.setattr(dn.requests, "post",
                        lambda *a, **k: _Resp(429, {"retry_after": 45.0}))
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    monkeypatch.setattr(dn.logger, "warning", lambda m: warned.append(m))
    assert dn._post("http://hook", {}) is None
    assert warned and "45.0s" in warned[0]
    # ...and we never actually sit through it: the next pass is minutes away and
    # nothing was ledgered, so a bounded wait is free.
    assert f"{dn._MAX_429_WAIT:.1f}s" in warned[0]



# ── Flat sizing, and record-only models ──────────────────────────────────────
#
# The Kelly-derived 1..3u scale sized UP into the only losing bucket: over 387
# settled picks the highest-edge third won 50.4% for -7.2% ROI against +16.8%
# for the lowest, and the same decline shows on raw edge, Kelly and price.
# Flat until a tier signal survives a time split (Matt, 2026-08-29).

def test_conviction_is_flat_for_every_kelly():
    for k in (None, 0, 0.001, 0.02, 0.0333, 0.05, 0.2, "junk"):
        assert dn.conviction_for(k) == dn.FLAT_CONVICTION, k


def test_flat_conviction_is_still_price_adjusted():
    """Flat means flat in units TO WIN, not flat in units risked."""
    assert dn.fmt_stake(dn.stake_for(0.02, -110)) == "1.1u to win 1u"
    assert dn.fmt_stake(dn.stake_for(0.02, 250)) == "0.4u to win 1u"
    assert dn.fmt_stake(dn.stake_for(0.02, None)) == "1u"


def test_the_risk_cap_can_no_longer_bind():
    """At 1u to win, the 3u risk cap needs a price below about -300."""
    assert dn.stake_for(0.05, -200).capped is False
    assert dn.stake_for(0.05, -1000).capped is True   # 10u to win 1u -> capped


def test_a_record_only_model_publishes_no_stake():
    f = dn._signal_field(_signal(model_id="mlb_prop_batter_hr", dk_odds=300))
    assert "record only" in f["value"]
    assert "u to win" not in f["value"]


def test_a_normal_model_still_publishes_a_stake():
    f = dn._signal_field(_signal())
    assert "to win" in f["value"]


# ── CLV, all-time, and the audit trail (2026-08-29, mike) ───────────────────

def test_clv_counts_only_picks_that_have_a_closing_price():
    """CLV is captured for game-level picks with a closing DK price. A pick
    without one is not a miss, it is not measured -- counting it as a miss
    would understate the rate."""
    rows = [
        ("MLB", "mlb_moneyline", "WIN",  0.022, -110, 2.4),    # beat close
        ("MLB", "mlb_moneyline", "LOSS", 0.022, -110, -1.1),   # closed worse
        ("MLB", "mlb_moneyline", "WIN",  0.022, -110, None),   # not measured
    ]
    t = dn._tally(rows)
    assert (t["clv_n"], t["clv_beat"]) == (2, 1)
    assert "50% beat close (1/2)" == dn.clv_line(t)


def test_clv_line_is_empty_when_nothing_was_measured():
    """No denominator, no claim."""
    t = dn._tally([("MLB", "mlb_moneyline", "WIN", 0.022, -110, None)])
    assert dn.clv_line(t) == ""
    assert "beat close" not in dn._tally_line(t, with_clv=True)


def test_exactly_flat_clv_is_not_a_beat():
    """Matching the close is not beating it."""
    t = dn._tally([("MLB", "mlb_moneyline", "WIN", 0.022, -110, 0.0)])
    assert (t["clv_n"], t["clv_beat"]) == (1, 0)


def test_tally_line_omits_clv_unless_asked():
    """The signal cards do not carry CLV; only results messages do."""
    t = dn._tally([("MLB", "mlb_moneyline", "WIN", 0.022, -110, 3.0)])
    assert "beat close" not in dn._tally_line(t)
    assert "beat close" in dn._tally_line(t, with_clv=True)


def test_the_recap_carries_no_methodology_footer():
    """Matt/mike, 2026-08-29: the numbers, not an explanation of them."""
    import ast
    import inspect
    src = inspect.getsource(dn.notify_discord_results)
    assert '"footer"' not in src, "the results recap must not carry a footer"


def test_snapshot_rows_capture_every_published_figure():
    """Whatever the recap says must be reproducible from Supabase afterwards:
    live tables move (late settlements, a threshold sweep, a pause), so the
    published number has to be stored, not recomputed."""
    daily = [("MLB", "mlb_moneyline", "WIN", 0.022, -110, 2.0),
             ("WNBA", "wnba_moneyline", "LOSS", 0.022, -110, -3.0)]
    by_sport = {"MLB": daily[:1], "WNBA": daily[1:]}
    rows = dn.snapshot_rows(
        "2026-08-28", "2026-08-29T06:00:00-04:00",
        dn._tally(daily), by_sport, dn._tally(daily), by_sport, 2, 2)

    scopes = {(r[1], r[2]) for r in rows}
    assert scopes == {("daily", None), ("daily", "MLB"), ("daily", "WNBA"),
                      ("all_time", None), ("all_time", "MLB"),
                      ("all_time", "WNBA")}
    overall = next(r for r in rows if r[1] == "daily" and r[2] is None)
    # game_date, scope, sport, w, l, p, settled, record_only, ...
    assert overall[0] == "2026-08-28"
    assert (overall[3], overall[4], overall[5]) == (1, 1, 0)
    assert overall[11] == 2 and overall[12] == 1        # clv graded / beat
    assert overall[13] == pytest.approx(50.0)           # clv pct
    assert overall[14] == "2026-08-29T06:00:00-04:00"


def test_a_snapshot_with_no_clv_stores_null_not_zero():
    """0% beat-close and 'not measured' are different facts."""
    rows_in = [("MLB", "mlb_moneyline", "WIN", 0.022, -110, None)]
    rows = dn.snapshot_rows("2026-08-28", "ts", dn._tally(rows_in),
                            {"MLB": rows_in}, dn._tally(rows_in),
                            {"MLB": rows_in}, 1, 1)
    assert all(r[13] is None for r in rows)


def test_a_started_game_is_never_delivered():
    """2026-08-29: three F5 picks locked at 3:18pm ET; the 3:17pm refresh pass
    ABORTED before the capture step, the 4:17pm pass captured them at 4:31pm,
    and Discord posted all three -- 20 minutes after two of those games had
    first pitch. The pick was legitimate; announcing a bet the reader cannot
    take is not. Guarded at DELIVERY so the pick still locks and still settles."""
    import inspect
    src = inspect.getsource(dn._new_signals)
    assert "g.commence_time::timestamptz > NOW()" in src
    assert "g.commence_time IS NULL" in src, (
        "an unknown start time must not silently suppress a signal (golf)")


def test_the_mobile_push_carries_the_same_guard():
    """If it is wrong to post a bet the reader cannot take, it is wrong to buzz
    their phone about it."""
    import inspect
    from tracking import push_notifier as pn
    src = inspect.getsource(pn._new_bet_signals)
    assert "g.commence_time::timestamptz > NOW()" in src
    assert "g.commence_time IS NULL" in src


# ── the live staleness disclosure ────────────────────────────────────────────

def test_every_live_post_carries_the_staleness_note(monkeypatch):
    """The feed's floor is a measured property, not a disclaimer: The Odds API
    serves one cached in-play snapshot for ~45s and its bulk and per-event
    endpoints return that SAME cache. A reader who opens DraftKings and sees a
    different total is seeing the floor, so the post has to say so."""
    posts = []
    monkeypatch.setattr(dn, "_post", lambda url, p: posts.append((url, p)) or "1")
    dn._post_picks("http://x", "MLB", [_signal()], "2026-08-23", live=True,
                   note=dn.LIVE_STALENESS_NOTE)
    desc = posts[0][1]["embeds"][0]["description"]
    assert "45s" in desc, "the note must name the measured number, not hand-wave"
    assert "DraftKings" in desc


def test_the_note_tells_the_reader_what_to_do():
    """A warning that does not resolve to an action is noise on a betting card.

    The action used to be "if it has moved past your edge, skip it" -- which
    asks the reader to check a number that is deliberately never published.
    Matt, 2026-08-30: "people wont know what the edge is." It now points at the
    per-pick "good to" price, which is on the card in front of them."""
    n = dn.LIVE_STALENESS_NOTE.lower()
    assert "good to" in n and "pass" in n
    assert "edge" not in n, "the note must not ask about a number we never show"


def test_pregame_posts_do_not_carry_it(monkeypatch):
    """Pre-game prices are stable for hours. Attaching the live warning there
    would train readers to ignore it on the picks where it is true."""
    posts = []
    monkeypatch.setattr(dn, "_post", lambda url, p: posts.append((url, p)) or "1")
    dn._post_picks("http://x", "MLB", [_signal()], "2026-08-23")
    assert "description" not in posts[0][1]["embeds"][0]
