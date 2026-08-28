"""
Pure-function tests for tracking/discord_notifier.py.

No DB and no network: the detection SQL is validated against production
separately, and everything here is the formatting / routing / delivery logic
that decides what a channel actually shows and — critically — what gets
ledgered as sent.
"""

import json

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
    # (sport, model_id, result, kelly_fraction, dk_odds) - the exact rows the
    # recap query returns for 2026-08-21 under the CURRENT thresholds, pulled
    # from the live DB rather than invented.
    ("MLB",  "mlb_f5_moneyline",         "LOSS", 0.031240, -115.0),
    ("MLB",  "mlb_f5_moneyline",         "LOSS", 0.023579, -154.0),
    ("MLB",  "mlb_f5_moneyline",         "WIN",  0.032729, -140.0),
    ("MLB",  "mlb_f5_moneyline",         "WIN",  0.020339, -145.0),
    ("MLB",  "mlb_prop_batter_runs",     "WIN",  0.030984,  113.0),
    ("WNBA", "wnba_moneyline",           "WIN",  0.044999, -166.0),
    ("WNBA", "wnba_prop_player_assists", "WIN",  0.043752, -128.0),
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
    assert mlb["units"] == pytest.approx(0.3900, abs=0.001)
    assert mlb["risked"] == pytest.approx(10.6299, abs=0.001)

    wnba = dn._tally(by_sport["WNBA"])
    assert (wnba["w"], wnba["l"]) == (2, 0)
    assert wnba["units"] == pytest.approx(4.1510, abs=0.001)
    assert wnba["risked"] == pytest.approx(6.0, abs=0.001)

    overall = dn._tally(_PROD_ROWS)
    assert (overall["w"], overall["l"]) == (5, 2)
    assert overall["units"] == pytest.approx(4.5410, abs=0.001)
    assert overall["risked"] == pytest.approx(16.6299, abs=0.001)


def test_a_loss_costs_the_full_stake_and_a_push_costs_nothing():
    """The asymmetry is the whole point of the risk/win convention."""
    # kelly 2.2% -> 1.5u conviction; at -110 that lays 1.65u.
    loss = dn._tally([("MLB", "mlb_moneyline", "LOSS", 0.022, -110)])
    assert loss["units"] == pytest.approx(-1.65, abs=0.001)
    assert loss["risked"] == pytest.approx(1.65, abs=0.001)

    push = dn._tally([("MLB", "mlb_moneyline", "PUSH", 0.022, -110)])
    assert push["units"] == 0.0
    assert push["risked"] == 0.0, "a push returns the stake, so nothing was risked"


def test_record_only_model_counts_in_record_but_never_in_money():
    """mlb_prop_batter_hr is tracked for its W-L but its P&L is not counted —
    most HR picks have no real DK price, so counting them fabricates P&L."""
    rows = [
        ("MLB", "mlb_moneyline", "WIN", 0.022, -110),
        ("MLB", "mlb_prop_batter_hr", "LOSS", 0.01, 400),
        ("MLB", "mlb_prop_batter_hr", "WIN", 0.01, 400),
    ]
    t = dn._tally(rows)
    assert (t["w"], t["l"]) == (2, 1), "record must include the HR picks"
    # The winner pays exactly its conviction back: 1.65u risked at -110 wins 1.5u.
    # That identity is what makes the to-win convention readable in the recap.
    assert t["units"] == pytest.approx(1.5, abs=0.001), "HR units must be excluded"
    assert t["risked"] == pytest.approx(1.65, abs=0.001), "HR stake must be excluded"
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

def test_conviction_scales_kelly_onto_a_1_to_3_scale():
    """Kelly rescaled so the server's 5% cap lands exactly on 3u (Matt,
    2026-08-28: "1-3 unit spreads with 3 being the highest conviction")."""
    assert dn.conviction_for(0.05) == 3.0        # the MAX_KELLY_FRACTION cap
    assert dn.conviction_for(0.025) == 1.5
    assert dn.conviction_for(0.0328) == 2.0      # median live kelly
    assert dn.conviction_for(0.039) == 2.5       # p75 live kelly


def test_conviction_never_exceeds_three():
    """52% of qualifying picks used to publish above 3u. None can now."""
    for k in (0.05, 0.06, 0.09, 0.5, 1.0):
        assert dn.conviction_for(k) == 3.0


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
    s = dn.stake_for(0.05, 150)                  # 3u conviction at +150
    assert s.conviction == 3.0
    assert round(s.risk, 2) == 2.0               # lay 2u to win 3u
    assert s.win == 3.0


def test_favourites_risk_more_until_the_cap_binds():
    s = dn.stake_for(0.0333, -135)               # median price, under the cap
    assert round(s.risk, 2) == 2.7
    assert s.win == 2.0
    assert s.capped is False


def test_risk_is_capped_at_three_units_and_the_payout_is_recomputed():
    """The cap is what reconciles "1-3 units to win" with "never more than 3
    units on 1 event". A capped bet must NOT still advertise a 3u win."""
    s = dn.stake_for(0.05, -147)                 # uncapped this would lay 4.42u
    assert s.conviction == 3.0
    assert s.risk == 3.0
    assert s.capped is True
    assert round(s.win, 2) == 2.04               # recomputed, not left at 3
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
    assert s.conviction == 3.0
    assert dn.fmt_stake(s) == "3u"


def test_units_for_returns_the_risk_so_exposure_sums_are_money():
    assert round(dn.units_for(0.0167, -110), 2) == 1.1
    assert round(dn.units_for(0.05, 150), 2) == 2.0
    assert dn.units_for(0.05, None) == 3.0


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
        "LAA @ TEX \u00b7 2:36 PM ET\n`-154`\u2003\u00b7\u2003**2.3u to win 1.5u**")


def test_field_never_leaks_model_edge_or_book():
    """The whole point of the format change: the channel gets the bet, not the
    model's reasoning. Guards against a future field being added back."""
    blob = json.dumps(dn._picks_embed("MLB", [_signal()], "2026-08-23")).lower()
    for banned in ("model", "edge", "draftkings", "prob", "%", "stake", "$", "high"):
        assert banned not in blob, f"{banned!r} leaked into the Discord payload"


def test_field_degrades_when_context_is_missing():
    f = dn._signal_field(_signal(dk_odds=None, commence=None, home=None, away=None))
    # No price to gross up against -> the bare conviction, claiming no payout.
    assert f["value"] == "`N/A`\u2003\u00b7\u2003**1.5u**", "no dangling separator"


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


def _row(lock_key, sport="MLB"):
    # Column order must match _new_signals' SELECT list.
    return (lock_key, f"label {lock_key}", sport, "mlb_moneyline", 0.72, 0.11,
            -150.0, 0.02, "HIGH", "TEX", "LAA", "2026-08-23T18:36:00+00:00", None)


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
    for leak in ("edge", "model_prob", "probability", "draftkings", "fanduel", "kelly"):
        assert leak not in blob, f"free pick must not expose {leak}"
    # kelly 3.1% -> 2u conviction; at -118 that lays 2.4u to win 2u.
    assert "-118" in blob and "2.4u to win 2u" in blob


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
    assert "2.5u to win 2.5u" in blob          # +100
    assert "2.7u to win 2u" in blob            # -135
    assert "2.6u to win 2u" in blob            # -132
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

