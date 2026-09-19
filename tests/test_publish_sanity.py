"""Pre-publish sanity gate: refuse/keep cases, and the live path cannot bypass it.

The gate is tracking.publish_sanity.filter_for_publish. It composes
pick_integrity first. Discord and push, pre-game and live, all call it on
the signal *list* immediately before send. Live does not go through
publish_new_signals — that is the bug this file pins.
"""
from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from tracking.pick_integrity import refuse_mismatched
from tracking.publish_sanity import (
    PUBLIC_ONE_WAY_PCT,
    REASON_CONTRADICTION,
    REASON_DEAD_BET,
    REASON_INTEGRITY,
    REASON_LOCK_REPRICE,
    REASON_ONE_SIDED_PUBLIC,
    REASON_STAKEABILITY,
    REASON_STALE_CLOCK,
    filter_for_publish,
    last_refusals,
    pick_sanity_problems,
)
from tracking import discord_notifier, push_notifier


def _sig(**kw):
    # ncaaf_over_under / ncaaf_live_total are LIVE (not in PAUSED/RETIRED).
    base = {
        "lock_key": "NCAAF_2026-09-19_ole-miss_lsu:ncaaf_over_under",
        "label": "Ole Miss @ LSU Under 55.5",
        "sport": "NCAAF",
        "model_id": "ncaaf_over_under",
        "side": "under",
        "line": 55.5,
        "home": "LSU",
        "away": "Ole Miss",
        "prob": 0.58,
        "edge": 0.04,
        "dk_odds": -110,
        "decision_odds": -110,
        "kelly": 0.01,
        "commence": "2099-09-19T23:00:00+00:00",
        "game_date": "2026-09-19",
        "game_id": "NCAAF_2026-09-19_ole-miss_lsu",
    }
    base.update(kw)
    return base


def _live(**kw):
    defaults = {
        "lock_key": "live:NCAAF_2026-09-19_ole-miss_lsu:ncaaf_live_total:under",
        "label": "Ole Miss @ LSU Under 55.5 (live)",
        "model_id": "ncaaf_live_total",
        "live": True,
    }
    defaults.update(kw)
    return _sig(**defaults)


# ── 1. integrity is first and always ────────────────────────────────────────

def test_integrity_still_refuses_a_mismatched_label():
    bad = _sig(label="Ole Miss @ LSU Over 55.5")  # label says Over, side is under
    assert filter_for_publish([bad], "t") == []
    assert any(r["reason"] == REASON_INTEGRITY for r in last_refusals())


def test_kill_switch_disables_sanity_only(monkeypatch):
    monkeypatch.setattr("config.RUN_PUBLISH_SANITY", False)
    # Integrity still runs.
    bad_label = _sig(label="Ole Miss @ LSU Over 55.5")
    assert filter_for_publish([bad_label], "t") == []
    # A paused model would fail sanity; with the switch off it is kept.
    paused = _sig(model_id="mlb_runline",
                  label="NYY @ BOS — NYY +1.5", side="away", line=-1.5)
    kept = filter_for_publish([paused], "t")
    assert [s["lock_key"] for s in kept] == [paused["lock_key"]]


# ── 2. shared base ──────────────────────────────────────────────────────────

def test_paused_and_retired_and_void_never_post():
    paused = _sig(model_id="mlb_runline",
                  label="NYY @ BOS — NYY +1.5", side="away", line=-1.5)
    assert pick_sanity_problems(paused)  # mlb_runline is in PAUSED_MODELS
    assert filter_for_publish([paused], "t") == []
    assert last_refusals()[0]["reason"] == REASON_STAKEABILITY

    void = _sig(condition_status="VOID")
    assert filter_for_publish([void], "t") == []

    from config import RETIRED_MODELS
    retired_id = next(iter(RETIRED_MODELS))
    retired = _sig(model_id=retired_id)
    # Integrity may also refuse if the label doesn't match a non-OU model.
    # Drive the stakeability check directly.
    assert any("retired" in p for p in pick_sanity_problems(retired))


def test_stale_clock_refuses_a_started_pregame_and_keeps_an_unstarted():
    started = _sig(commence="2020-01-01T00:00:00+00:00")
    assert filter_for_publish([started], "t") == []
    assert last_refusals()[0]["reason"] == REASON_STALE_CLOCK

    future = _sig(commence="2099-01-01T00:00:00+00:00")
    assert filter_for_publish([future], "t") == [future]


def test_stale_clock_missing_commence_fails_open():
    s = _sig()
    s.pop("commence")
    assert pick_sanity_problems(s) == []


def test_absurd_null_zero_and_impossible_numbers():
    assert filter_for_publish([_sig(dk_odds=None, decision_odds=None)], "t") == []
    assert filter_for_publish([_sig(dk_odds=0, decision_odds=0)], "t") == []
    assert filter_for_publish([_sig(dk_odds=-50, decision_odds=-50)], "t") == []
    # NFL total of 200 is not a board.
    nfl = _sig(sport="NFL", model_id="nfl_wind_totals", label="KC Under 43.5",
               side="under", line=200.0, lock_key="NFL_x:nfl_wind_totals")
    assert any("total" in p for p in pick_sanity_problems(nfl))
    # A real MLB total stays.
    assert pick_sanity_problems(_sig()) == []


def test_missing_odds_keys_fail_open_so_push_live_is_not_emptied():
    """Push live dicts do not carry odds. That must not refuse every live push."""
    slim = {"lock_key": "live:G:ncaaf_live_total:under",
            "label": "Under 55.5", "sport": "NCAAF",
            "model_id": "ncaaf_live_total",
            "side": "under", "line": 55.5}
    assert pick_sanity_problems(slim, live=True) == []


def test_same_game_contradiction_refuses_both_sides_in_one_pass():
    over = _sig(lock_key="G:ncaaf_over_under:o", label="Over 55.5",
                side="over", line=55.5, game_id="G")
    under = _sig(lock_key="G:ncaaf_over_under:u", label="Under 55.5",
                 side="under", line=55.5, game_id="G")
    assert filter_for_publish([over, under], "t") == []
    reasons = {r["reason"] for r in last_refusals()}
    assert REASON_CONTRADICTION in reasons

    # Different games, same model, both unders — not a contradiction.
    a = _sig(lock_key="G1:ncaaf_over_under", game_id="G1")
    b = _sig(lock_key="G2:ncaaf_over_under", game_id="G2")
    assert filter_for_publish([a, b], "t") == [a, b]


def test_one_sided_public_refuses_with_the_tickets_and_fails_open_when_missing():
    with_public = _sig(public_bet_pct=82.0, public_n=12)
    assert filter_for_publish([with_public], "t") == []
    assert last_refusals()[0]["reason"] == REASON_ONE_SIDED_PUBLIC

    # Against the public (fade) is not this check.
    fade = _sig(public_bet_pct=28.0, public_n=12)
    assert pick_sanity_problems(fade) == []

    # n too small → fail open.
    thin = _sig(public_bet_pct=82.0, public_n=2)
    assert pick_sanity_problems(thin) == []

    # No public fields → fail open.
    assert pick_sanity_problems(_sig()) == []
    assert PUBLIC_ONE_WAY_PCT == 70.0


# ── 3. live-only ────────────────────────────────────────────────────────────

def test_dead_under_is_refused_when_the_score_already_cleared():
    dead = _live(home_score=40, away_score=30, line=55.5, side="under")
    assert filter_for_publish([dead], "t", live=True) == []
    assert last_refusals()[0]["reason"] == REASON_DEAD_BET


def test_live_under_still_alive_is_kept():
    alive = _live(home_score=7, away_score=3, line=55.5, side="under")
    assert filter_for_publish([alive], "t", live=True) == [alive]


def test_missing_live_state_fails_open():
    assert pick_sanity_problems(_live(), live=True) == []


def test_live_stale_clock_uses_the_slate_window(monkeypatch):
    monkeypatch.setattr("config.live_slate_dates",
                        lambda now=None: ["2026-09-19"])
    ok = _live(game_date="2026-09-19")
    assert pick_sanity_problems(ok, live=True) == []
    old = _live(game_date="2026-09-01")
    assert any("live slate" in p for p in pick_sanity_problems(old, live=True))


# ── 4. pregame richer ───────────────────────────────────────────────────────

def test_money_ticket_skew_refuses_the_trap_side_and_fails_open_when_missing():
    trap = _sig(public_bet_pct=80.0, public_money_pct=40.0)
    assert filter_for_publish([trap], "t") == []
    # Money and tickets agree — not a trap.
    steam = _sig(public_bet_pct=80.0, public_money_pct=78.0)
    # one-sided public still refuses the 80% ticket side
    assert pick_sanity_problems(steam)  # one_sided_public
    # Missing money → that check opens; tickets 55% is not one-sided.
    no_money = _sig(public_bet_pct=55.0)
    assert pick_sanity_problems(no_money) == []


def test_prop_lineup_refuses_confirmed_out_and_fails_open_when_unknown():
    out = _sig(model_id="nfl_prop_market", sport="NFL",
               label="Mahomes Over 1.5", side="over", line=1.5,
               player_id="mahomes", player_status="out",
               lock_key="G:nfl_prop_market:mahomes")
    assert filter_for_publish([out], "t") == []
    unconfirmed = _sig(model_id="nfl_prop_market", sport="NFL",
                       label="Mahomes Over 1.5", side="over", line=1.5,
                       player_id="mahomes", lineup_confirmed=False,
                       lock_key="G:nfl_prop_market:mahomes")
    assert filter_for_publish([unconfirmed], "t") == []
    unknown = _sig(model_id="nfl_prop_market", sport="NFL",
                   label="Mahomes Over 1.5", side="over", line=1.5,
                   player_id="mahomes",
                   lock_key="G:nfl_prop_market:mahomes")
    assert pick_sanity_problems(unknown) == []


def test_outdoor_total_refuses_an_over_that_ignores_extreme_wind():
    over = _sig(sport="NFL", model_id="ncaaf_over_under",
                label="KC Under 43.5".replace("Under", "Over"),
                side="over", line=43.5, wind_mph=28.0, is_dome=False,
                lock_key="NFL_x:other_total")
    # Label must match side for integrity.
    over = _sig(sport="NFL", model_id="ncaaf_over_under",
                label="KC Over 43.5", side="over", line=43.5,
                wind_mph=28.0, is_dome=False, lock_key="NFL_x:other_total")
    assert filter_for_publish([over], "t") == []
    wind_model = _sig(sport="NFL", model_id="nfl_wind_totals",
                      label="KC Under 43.5", side="under", line=43.5,
                      wind_mph=28.0, is_dome=False,
                      lock_key="NFL_x:nfl_wind_totals")
    assert pick_sanity_problems(wind_model) == []
    no_wind = _sig(sport="NFL", model_id="ncaaf_over_under",
                   label="KC Over 43.5", side="over", line=43.5,
                   lock_key="NFL_x:other_total")
    assert pick_sanity_problems(no_wind) == []


def test_too_good_edge_refuses_above_the_cap():
    wild = _sig(edge=0.55)
    assert filter_for_publish([wild], "t") == []
    assert "edge" in last_refusals()[0]["detail"]
    # Missing edge key (push live) fails open.
    slim = _sig()
    slim.pop("edge")
    assert pick_sanity_problems(slim) == []


def test_first_signal_lock_keeps_the_locked_row_and_refuses_the_reprice():
    locked = _sig(line=55.5, dk_odds=-110, posted_at="2026-09-19T12:00:00+00:00",
                  lock_key="G:ncaaf_over_under", game_id="G")
    reprice = _sig(line=58.5, dk_odds=-120, posted_at="2026-09-19T16:00:00+00:00",
                   label="Ole Miss @ LSU Under 58.5",
                   lock_key="G:ncaaf_over_under", game_id="G")
    kept = filter_for_publish([reprice, locked], "t")
    assert [s["line"] for s in kept] == [55.5]
    assert any(r["reason"] == REASON_LOCK_REPRICE for r in last_refusals())


# ── 5. live path cannot bypass the gate ─────────────────────────────────────

class _Conn:
    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))

        class _R:
            def fetchall(self):
                return []

            def fetchone(self):
                return None
        return _R()

    def commit(self):
        pass

    def close(self):
        pass

    def ledgered(self) -> set:
        return {p[0] for sql, p in self.calls if "INSERT INTO push_sent" in sql}


def test_discord_and_push_pregame_and_live_call_the_shared_filter():
    """THE choke-point pin. Live must not only wrap publish_new_signals."""
    d_pre = inspect.getsource(discord_notifier._post_new_signals)
    d_live = inspect.getsource(discord_notifier._post_new_live_signals)
    p_pre = inspect.getsource(push_notifier._send_signal_changes)
    p_live = inspect.getsource(push_notifier.notify_live_signals)
    for src, name in ((d_pre, "Discord pregame"), (d_live, "Discord live"),
                      (p_pre, "Push pregame"), (p_live, "Push live")):
        assert "filter_for_publish(" in src, f"{name} does not call the shared gate"
    # Live does not go through publish_new_signals.
    pub = inspect.getsource(
        __import__("tracking.signal_publisher", fromlist=["publish_new_signals"])
        .publish_new_signals)
    assert "notify_discord_live" not in pub
    assert "notify_live_signals" not in pub


def test_live_writers_call_the_gated_notifiers_not_a_private_post():
    for rel in ("models/live_scorer.py", "ncaaf_live/gameday.py",
                "nfl/live_model/pick_writer.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "notify_discord_live" in src, f"{rel} does not post live Discord"
        assert "notify_live_signals" in src, f"{rel} does not push live"
        assert "_post_new_live_signals" not in src, (
            f"{rel} reaches around the gate")


def test_discord_live_refuses_a_dead_bet_and_does_not_ledger(monkeypatch):
    dead = _live(home_score=40, away_score=30, line=55.5, side="under")
    alive = _live(home_score=7, away_score=3, line=55.5, side="under",
                  lock_key="live:G2:ncaaf_live_total:under",
                  game_id="G2")
    sent: list[str] = []

    def fake_post(url, sport, group, target_date, **kw):
        sent.extend(s["label"] for s in group)
        return [(group, "m1")]

    monkeypatch.setattr(discord_notifier, "_new_live_signals",
                        lambda c, d: [dead, alive])
    monkeypatch.setattr(discord_notifier, "_post_picks", fake_post)
    monkeypatch.setattr(discord_notifier, "_live_webhook_for_sport",
                        lambda s: "https://x")
    conn = _Conn()
    assert discord_notifier._post_new_live_signals(conn, "2026-09-19", False) == 1
    assert sent == [alive["label"]]
    assert conn.ledgered() == {alive["lock_key"]}


def test_push_live_refuses_a_dead_bet_and_does_not_ledger(monkeypatch):
    dead = _live(home_score=40, away_score=30, line=55.5, side="under")
    alive = _live(home_score=7, away_score=3, line=55.5, side="under",
                  lock_key="live:G2:ncaaf_live_total:under",
                  game_id="G2")
    monkeypatch.setattr(push_notifier, "_new_live_signals",
                        lambda c, d: [dead, alive])
    conn = _Conn()
    monkeypatch.setattr(push_notifier, "get_connection", lambda: conn)
    push_notifier.notify_live_signals("2026-09-19")
    assert conn.ledgered() == {alive["lock_key"]}


# ── 6. no auto-pause / unit bump ────────────────────────────────────────────

def test_the_gate_never_pauses_or_bumps_units():
    src = (ROOT / "tracking" / "publish_sanity.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" in src  # it READs the set
    assert "PAUSED_MODELS.add" not in src
    assert "PAUSED_MODELS =" not in src.split("def ", 1)[-1]
    assert "model_auto_pauses" not in src
    assert "KELLY_MULTIPLIER" not in src
    assert "recommended_bet" not in src
    # Mentions the quality table only as something it does NOT write.
    assert "INSERT INTO model_quality_checks" not in src
    assert "execute(" not in src


def test_filter_composes_integrity_not_a_copy():
    src = inspect.getsource(filter_for_publish)
    assert "refuse_mismatched(" in src


def test_a_clean_pick_is_kept():
    s = _sig()
    assert refuse_mismatched([s], "t") == [s]
    assert filter_for_publish([s], "t") == [s]
    assert last_refusals() == []
