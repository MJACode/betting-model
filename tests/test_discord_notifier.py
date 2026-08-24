"""
Pure-function tests for tracking/discord_notifier.py.

No DB and no network: the detection SQL is validated against production
separately, and everything here is the formatting / routing / delivery logic
that decides what a channel actually shows and — critically — what gets
ledgered as sent.
"""

import types

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


def test_model_label_uses_market_registry_then_falls_back():
    assert dn._model_label("mlb_moneyline") == "Moneyline"
    assert dn._model_label("mlb_f5_moneyline") == "F5 Moneyline"
    assert dn._model_label("nhl_moneyline_regulation") == "Regulation 3-way"
    # Props aren't in config.MODELS — derived from the id.
    assert dn._model_label("wnba_prop_player_assists") == "Player Assists"
    assert dn._model_label("mlb_prop_batter_runs") == "Batter Runs"


# ── Recap tallying ───────────────────────────────────────────────────────────

# The ACTUAL settled rows the production query returns for game_date 2026-08-21,
# copied verbatim so this test pins the tally against real data rather than
# numbers invented to match. Shape: (sport, model_id, result, profit_flat, bet).
_PROD_ROWS = [
    ("MLB",  "mlb_f5_moneyline",          "LOSS", -100.00, 5.0),
    ("MLB",  "mlb_f5_moneyline",          "LOSS", -100.00, 5.0),
    ("MLB",  "mlb_f5_moneyline",          "WIN",    71.43, 5.0),
    ("MLB",  "mlb_prop_batter_rbi",       "WIN",   241.00, 5.0),
    ("MLB",  "mlb_prop_batter_runs",      "WIN",    75.19, 5.0),
    ("MLB",  "mlb_prop_batter_walks",     "WIN",    91.74, 5.0),
    ("MLB",  "mlb_prop_pitcher_k",        "LOSS", -100.00, 5.0),
    ("UFC",  "ufc_method_of_victory",     "LOSS", -100.00, 5.0),
    ("UFC",  "ufc_moneyline",             "LOSS", -100.00, 5.0),
    ("UFC",  "ufc_total_rounds",          "LOSS", -100.00, 5.0),
    ("WNBA", "wnba_moneyline",            "WIN",    58.82, 5.0),
    ("WNBA", "wnba_prop_player_assists",  "LOSS", -100.00, 5.0),
]


def test_tally_reproduces_production_per_sport_numbers():
    """Validated against the live DB for game_date 2026-08-21:
    MLB 4-3 / +179.36 on 700 staked, UFC 0-3 / -300 on 300, WNBA 1-1 / -41.18 on 200."""
    by_sport = {}
    for r in _PROD_ROWS:
        by_sport.setdefault(r[0], []).append(r)

    mlb = dn._tally(by_sport["MLB"])
    assert (mlb["w"], mlb["l"], mlb["p"]) == (4, 3, 0)
    assert mlb["profit"] == pytest.approx(179.36, abs=0.01)
    assert mlb["staked"] == 700.0

    ufc = dn._tally(by_sport["UFC"])
    assert (ufc["w"], ufc["l"]) == (0, 3)
    assert ufc["profit"] == pytest.approx(-300.0)

    wnba = dn._tally(by_sport["WNBA"])
    assert (wnba["w"], wnba["l"]) == (1, 1)
    assert wnba["profit"] == pytest.approx(-41.18, abs=0.01)

    overall = dn._tally(_PROD_ROWS)
    assert (overall["w"], overall["l"]) == (5, 7)
    assert overall["staked"] == 1200.0
    assert overall["profit"] == pytest.approx(-161.82, abs=0.01)


def test_record_only_model_counts_in_record_but_never_in_money():
    """mlb_prop_batter_hr is tracked for its W-L but its P&L is not counted —
    most HR picks have no real DK price, so counting them fabricates P&L."""
    rows = [
        ("MLB", "mlb_moneyline", "WIN", 90.0, 5.0),
        ("MLB", "mlb_prop_batter_hr", "LOSS", -100.0, 5.0),
        ("MLB", "mlb_prop_batter_hr", "WIN", 400.0, 5.0),
    ]
    t = dn._tally(rows)
    assert (t["w"], t["l"]) == (2, 1), "record must include the HR picks"
    assert t["profit"] == pytest.approx(90.0), "HR P&L must be excluded"
    assert t["staked"] == 100.0, "HR stake must be excluded"
    assert t["record_only"] == 2


def test_tally_line_reports_roi_and_degrades_to_record_only():
    line = dn._tally_line({"w": 4, "l": 3, "p": 0, "profit": 179.36,
                           "staked": 700.0, "record_only": 0})
    assert line.startswith("4-3 ")
    assert "+179.36" in line and "+25.6% ROI" in line
    # Pushes surface only when they exist.
    assert dn._tally_line({"w": 1, "l": 1, "p": 2, "profit": 0.0,
                           "staked": 200.0, "record_only": 0}).startswith("1-1-2 ")
    # An all-record-only day must not print a fabricated 0% ROI.
    assert dn._tally_line({"w": 1, "l": 5, "p": 0, "profit": 0.0,
                           "staked": 0.0, "record_only": 6}) == "1-5 · record only"


# ── Embeds ───────────────────────────────────────────────────────────────────

def _signal(**over):
    base = dict(lock_key="k", label="TEX ML F5", sport="MLB", model_id="mlb_f5_moneyline",
                prob=0.6979, edge=0.0916, dk_odds=-154.0, stake=2.34, tier="HIGH",
                home="TEX", away="LAA", commence="2026-08-23T18:36:00+00:00",
                bet_link="https://sportsbook.draftkings.com/?outcomes=abc")
    base.update(over)
    return base


def test_signal_embed_carries_the_numbers_and_the_betslip_link():
    e = dn._signal_embed(_signal())
    assert e["title"] == "TEX ML F5"
    assert e["description"] == "LAA @ TEX · 2:36 PM ET"
    assert e["url"].startswith("https://sportsbook.draftkings.com/")
    fields = {f["name"]: f["value"] for f in e["fields"]}
    assert fields["Model"] == "69.8%"
    assert fields["DK"] == "-154"
    assert fields["Edge"] == "+9.2%"
    assert fields["Stake"] == "$2.34"
    assert e["footer"]["text"] == "F5 Moneyline · HIGH"


def test_signal_embed_omits_absent_optional_pieces():
    e = dn._signal_embed(_signal(bet_link=None, edge=None, stake=0, tier=None,
                                 dk_odds=None, commence=None, home=None, away=None))
    assert "url" not in e, "a missing bet link must not produce a dead title link"
    assert "description" not in e
    names = {f["name"] for f in e["fields"]}
    assert "Edge" not in names and "Stake" not in names
    assert {f["value"] for f in e["fields"] if f["name"] == "DK"} == {"N/A"}


def test_embed_never_exceeds_discords_ten_per_message_cap(monkeypatch):
    posts = []
    monkeypatch.setattr(dn, "_post", lambda url, payload: (posts.append(payload), True)[1])
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    delivered = dn._post_embeds("http://hook", [{"title": str(i)} for i in range(23)], "hdr")
    assert delivered == 23
    assert [len(p["embeds"]) for p in posts] == [10, 10, 3]
    # The header rides the first message only, so it isn't repeated per chunk.
    assert posts[0]["content"] == "hdr"
    assert all("content" not in p for p in posts[1:])


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
    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: _Resp(204))
    assert dn._post("http://hook", {}) is True


def test_post_retries_a_429_then_succeeds(monkeypatch):
    calls = []

    def fake_post(*_a, **_k):
        calls.append(1)
        return _Resp(429, {"retry_after": 0.5}) if len(calls) == 1 else _Resp(204)

    monkeypatch.setattr(dn.requests, "post", fake_post)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    assert dn._post("http://hook", {}) is True
    assert len(calls) == 2


def test_post_gives_up_on_a_bad_webhook_without_raising(monkeypatch):
    """A deleted/invalid webhook is a 404. It must report failure (so nothing is
    ledgered) but never raise into the pipeline."""
    monkeypatch.setattr(dn.requests, "post", lambda *a, **k: _Resp(404, text="Unknown Webhook"))
    assert dn._post("http://hook", {}) is False


def test_post_returns_false_when_the_network_is_down(monkeypatch):
    def boom(*_a, **_k):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(dn.requests, "post", boom)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    assert dn._post("http://hook", {}) is False


def test_partial_delivery_reports_only_what_landed(monkeypatch):
    """The second chunk fails, so only the first chunk's embeds count as sent —
    this is what keeps the undelivered signals un-ledgered and retryable."""
    calls = []

    def fake_post(_url, _payload):
        calls.append(1)
        return len(calls) == 1

    monkeypatch.setattr(dn, "_post", fake_post)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    delivered = dn._post_embeds("http://hook", [{"title": str(i)} for i in range(25)])
    assert delivered == 10, "must not claim the failed chunk was delivered"


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
            -150.0, 3.0, "HIGH", "TEX", "LAA", "2026-08-23T18:36:00+00:00", None)


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
    assert len(by_url["http://mlb"]["embeds"]) == 2
    assert len(by_url["http://nfl"]["embeds"]) == 1
    assert by_url["http://mlb"]["content"] == "**2 new MLB signals**"
    assert by_url["http://nfl"]["content"] == "**1 new NFL signal**", "singular"


def test_no_webhooks_configured_is_a_clean_no_op(monkeypatch):
    """Nothing configured must not even open a DB connection."""
    _setup(monkeypatch, None, webhooks={})
    monkeypatch.setattr(dn, "get_connection",
                        lambda: (_ for _ in ()).throw(AssertionError("DB opened")))
    assert dn.notify_discord_signals(target_date="2026-08-23") == 0
