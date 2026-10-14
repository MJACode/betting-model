"""The in-play leader moneyline loop (nfl_live_leader/gameday.py).

Pinned here:
  * ONE BET PER GAME: the first qualifying evaluation is written and locked,
    and the game is never evaluated (or priced, or billed) again; a game that
    already carries its BET from an earlier process is not re-bet;
  * the 5-minute cadence: first evaluation when the game enters the window,
    then every 300 s; a transitional state does not consume a slot; odds are
    fetched only when a game is due;
  * a DraftKings quote stamped before the last score change we saw is skipped;
  * the pregame spread is DraftKings' LAST PRE-KICKOFF number, a missing one
    is None (never 0), and the fallback keys nfl_odds_history on the nflverse id;
  * game resolution refuses unless exactly one row matches;
  * the pick row: label, side, the DraftKings price used, scored_line NULL,
    quarter and home-minus-away score, tenth-Kelly from config.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from nfl_live_leader import gameday as G
from nfl_live_leader import model as M
from nfl_live_leader.state import EventMeta, LiveState


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


CTX = G.GameContext(game_id="NFL_2026_05_TB_DAL", game_date="2026-10-08", home="DAL",
                    away="TB", commence_time="2026-10-09T00:15:00+00:00", spread_home=-8.5,
                    spread_source="odds draftkings")


def live_state(eid="401872980", secs=300.0, home=16, away=24, poss="home", evaluable=True,
               reason="ok", period=4, state="in", final=False):
    return LiveState(event_id=eid, status_state=state, status_name="STATUS_IN_PROGRESS",
                     period=period, running_clock=secs - 10, final=final, home_score=home,
                     away_score=away, secs=secs, play_period=period, possession=poss,
                     down=1, evaluable=evaluable, reason=reason)


def quote_payload(home_price, away_price, ts="2026-10-09T03:00:00Z",
                  home="Dallas Cowboys", away="Tampa Bay Buccaneers"):
    return [{"home_team": home, "away_team": away, "commence_time": "2026-10-09T00:15:00Z",
             "bookmakers": [{"key": "draftkings", "last_update": ts,
                             "markets": [{"key": "h2h", "last_update": ts, "outcomes": [
                                 {"name": home, "price": home_price},
                                 {"name": away, "price": away_price}]}]}]}]


# ─── cadence ──────────────────────────────────────────────────────────────────

def test_cadence_is_an_epoch_aligned_five_minute_grid():
    """One evaluation per wall-clock slot (:00, :05 ...), like the Odds API
    snapshot grid the evidence was measured on -- not 300 s after first sight."""
    c = G.Cadence(300)
    assert c.due("g", 1000.0)               # slot 3 (900-1199)
    c.mark("g", 1000.0)
    assert not c.due("g", 1199.9)           # same slot
    assert c.due("g", 1200.0)               # slot 4 opens at :20:00, not at 1300
    assert c.due("other", 1000.0)


# ─── quotes ───────────────────────────────────────────────────────────────────

def test_quotes_are_priced_per_team_even_when_home_is_swapped():
    q = G.quotes_by_teams(quote_payload(-300, 240, home="Tampa Bay Buccaneers",
                                        away="Dallas Cowboys"))
    hp, ap, ts = G.side_prices(CTX, G.quote_for_game(q, CTX))
    assert (hp, ap) == (240, -300)          # DAL's price is DAL's, whoever the feed calls home
    assert ts == "2026-10-09T03:00:00Z"


def test_a_later_game_between_the_same_teams_never_prices_this_one():
    """The bulk feed lists every upcoming event. A rematch weeks later, listed
    AFTER the game in progress, must not overwrite its price: the game is
    priced at the event with its own kickoff, and an ambiguous pair is not
    priced at all (review of the build, 2026-10-13)."""
    live = quote_payload(450, -500)
    later = quote_payload(-160, 140)
    later[0]["commence_time"] = "2026-11-29T21:25:00Z"
    q = G.quotes_by_teams(live + later)
    hp, ap, _ = G.side_prices(CTX, G.quote_for_game(q, CTX))
    assert (hp, ap) == (450, -500)
    q = G.quotes_by_teams(later)                      # only the future game is listed
    assert G.quote_for_game(q, CTX) is None


def test_a_quote_older_than_the_last_score_is_skipped(art):
    q = G.quote_for_game(G.quotes_by_teams(quote_payload(450, -500)), CTX)
    st = live_state(poss="away")
    seen = datetime(2026, 10, 9, 3, 0, 30, tzinfo=timezone.utc)      # we saw a score 30 s later
    d, note = G.evaluate(art, st, CTX, q, seen, 0.02)
    assert d is None and "predates the score change" in note
    d, note = G.evaluate(art, st, CTX, q, seen - timedelta(minutes=5), 0.02)
    assert d is not None and d.side == "away" and d.price == -500


def test_no_quote_is_no_decision(art):
    d, note = G.evaluate(art, live_state(), CTX, None, None, 0.02)
    assert d is None and "no DraftKings moneyline" in note


# ─── platform context ─────────────────────────────────────────────────────────

class FakeConn:
    def __init__(self, answers):
        self.answers = list(answers)
        self.sql: list[tuple] = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        rows = self.answers.pop(0) if self.answers else []
        return _Rows(rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_pregame_spread_is_the_last_row_before_kickoff():
    conn = FakeConn([[("-7.5", "2026-10-11T20:25:30Z"),             # after kickoff: out
                      ("-8.5", "2026-10-11T20:24:56Z"),
                      ("-9.5", "2026-10-11T20:24:00.914027+00:00")]])
    sp, src = G.pregame_spread(conn, "NFL_2026_05_DET_ARI", "2026-10-11T20:25:00+00:00")
    assert sp == -8.5 and "draftkings" in src
    sql, params = conn.sql[0]
    assert "snapshot_type <> 'in_play'" in sql and "market = 'spreads'" in sql
    assert params == ("NFL_2026_05_DET_ARI", "2026-10-11T20:26:00")


def test_pregame_spread_falls_back_to_the_history_table_on_the_nflverse_id():
    conn = FakeConn([[], [("3.0", "2026-10-11 20:00:00+00")]])
    sp, src = G.pregame_spread(conn, "NFL_2026_05_DET_ARI", "2026-10-11T20:25:00+00:00")
    assert sp == 3.0 and src.startswith("nfl_odds_history")
    sql, params = conn.sql[1]
    assert "nfl_odds_history" in sql and "snapshot_at <= commence_time" in sql
    assert params == ("2026_05_DET_ARI",)


def test_a_missing_spread_is_none_never_zero():
    assert G.pregame_spread(FakeConn([[], []]), "NFL_X", "2026-10-11T20:25:00Z") is None
    assert G.pregame_spread(FakeConn([]), "NFL_X", None) is None


def test_game_resolution_needs_exactly_one_row():
    k = datetime(2026, 10, 12, 0, 20, tzinfo=timezone.utc)
    one = FakeConn([[("NFL_2026_05_BAL_ATL", "2026-10-11", "2026-10-12T00:20:00+00:00")]])
    assert G.resolve_game(one, "ATL", "BAL", k) == ("NFL_2026_05_BAL_ATL", "2026-10-11",
                                                     "2026-10-12T00:20:00+00:00")
    assert one.sql[0][1] == ("ATL", "BAL", "2026-10-11", "2026-10-13")
    assert G.resolve_game(FakeConn([[], []]), "ATL", "BAL", k) is None
    assert G.resolve_game(FakeConn([[("a", "d", None), ("b", "d", None)], []]), "ATL", "BAL", k) is None
    assert G.resolve_game(FakeConn([]), None, "BAL", k) is None


# ─── the pick row and the gates ───────────────────────────────────────────────

def test_the_pick_row(art):
    import config

    st = live_state(poss="away")
    d = M.decide(art, period=4, secs=300, home_score=16, away_score=24, possession="away",
                 spread_home=-8.5, home_price=450, away_price=-500)
    assert d.bet
    p = G.build_pick(CTX, st, d, 1000.0)
    assert p["model_id"] == "nfl_live_leader_ml" and p["sport"] == "NFL"
    assert p["pick_side"] == "away" and p["pick_label"] == "TB ML (live)"
    assert p["dk_odds"] == -500.0 and p["dk_implied_prob"] == round(1 / d.decimal, 4)
    assert p["model_probability"] == round(d.wp, 4) and p["edge"] == round(d.edge, 4)
    assert p["scored_line"] is None and p["is_live"] is True and p["signal_type"] == "BET"
    assert p["inning_at_pick"] == 4 and p["score_diff_at_pick"] == 16 - 24
    assert p["game_date"] == "2026-10-08" and p["game_time"] == CTX.commence_time
    f = min(config.KELLY_MULTIPLIER * (d.wp - d.implied) / (1 - d.implied),
            config.MAX_KELLY_FRACTION)
    assert p["kelly_fraction"] == pytest.approx(round(f, 6))
    for k in ("bankroll_at_pick", "injury_flag", "injury_detail", "confidence_tier",
              "recommended_bet"):
        assert k in p


def test_the_platform_gates_do_not_bind_on_the_rule(art, monkeypatch):
    """With the LIVE global EV floor restored (conftest holds it at -1.0), the
    smallest-EV kind of bet the rule makes -- edge 0.02 at -4000 -- still clears:
    the model's own floor is 0.02 and its price floor -5000."""
    import os

    import config

    monkeypatch.setattr(config, "GLOBAL_MIN_EV", float(os.environ.get("GLOBAL_MIN_EV", "0.20")))
    imp = 1 / M.am_to_dec(-4000)
    d = M.Decision(True, "BET", side="home", lead=10, secs=100, ball=1, band=0,
                   wp=float(imp) + 0.0201, price=-4000.0, decimal=float(M.am_to_dec(-4000)),
                   implied=float(imp), edge=0.0201)
    assert G.platform_gates(d) is None
    monkeypatch.setattr(config, "PAUSED_MODELS", set(config.PAUSED_MODELS) | {M.MODEL_ID})
    assert "paused" in G.platform_gates(d)


def test_write_bet_never_writes_over_a_bet_of_record(monkeypatch):
    import models.scorer as sc

    inserted = []
    monkeypatch.setattr(sc, "_insert_picks", lambda conn, picks: inserted.extend(picks))
    monkeypatch.setattr(sc, "_locked_live_lanes", lambda conn, gid, mids: {"nfl_live_leader_ml"})
    conn = FakeConn([])
    assert G.write_bet(conn, {"game_id": "g", "pick_label": "TB ML (live)"}) is False
    assert inserted == [] and conn.commits == 0
    monkeypatch.setattr(sc, "_locked_live_lanes", lambda conn, gid, mids: set())
    assert G.write_bet(conn, {"game_id": "g", "pick_label": "TB ML (live)"}) is True
    assert len(inserted) == 1 and conn.commits == 1


# ─── the loop ─────────────────────────────────────────────────────────────────

class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def time(self):                         # wall clock: slot 0 opens at t=0
        return self.t

    def sleep(self, s):
        self.t += 20.0


class FakeClient:
    """Scripted ESPN states, one list per tick, for two games."""

    def __init__(self, script, clock, season_types=None):
        self.script = script
        self.clock = clock
        self.season_types = season_types or {}

    def list_event_refs(self, now=None):
        return ["r1", "r2"]

    def event_meta(self, ref):
        eid = {"r1": "E1", "r2": "E2"}[ref]
        return EventMeta(event_id=eid, date="2026-10-09T00:15Z", home_id="6", away_id="27",
                         home_abbr="DAL", away_abbr="TB", status_ref=None, situation_ref=None,
                         plays_ref=None, season_type=self.season_types.get(eid, 2))

    def poll(self, meta, detail=True):
        rows = self.script[min(int(self.clock.t // 20), len(self.script) - 1)]
        return rows[meta.event_id]


class FakeFeed:
    def __init__(self, payload):
        self.payload = payload
        self.fetches = 0
        self.credits_used = 0

    def fetch(self):
        self.fetches += 1
        return self.payload


def _run_loop(monkeypatch, script, payload, locked=False, season_types=None):
    clock = FakeClock()
    client = FakeClient(script, clock, season_types)
    feed = FakeFeed(payload)
    writes, notes, evals = [], [], []
    ctx2 = G.GameContext(game_id="NFL_E2", game_date="2026-10-08", home="NYG", away="WAS",
                         commence_time="2026-10-09T00:15:00+00:00", spread_home=-1.0,
                         spread_source="x")
    monkeypatch.setattr(G, "time", clock)
    monkeypatch.setattr(G, "CoreClient", lambda: client)
    monkeypatch.setattr(G, "LiveOddsFeed", lambda: feed)
    monkeypatch.setattr(G, "load_context",
                        lambda conn, meta: CTX if meta.event_id == "E1" else ctx2)
    monkeypatch.setattr(G, "is_locked", lambda conn, gid: locked and gid == CTX.game_id)
    monkeypatch.setattr(G, "write_bet", lambda conn, pick: writes.append(pick) or True)
    monkeypatch.setattr(G, "notify_live", lambda d: notes.append(d))
    real_eval = G.evaluate
    monkeypatch.setattr(G, "evaluate",
                        lambda *a, **k: evals.append((a[1].event_id, clock.t)) or real_eval(*a, **k))
    import data.db
    import data.ingestors.live_price_log as lpl
    import models.scorer as sc
    monkeypatch.setattr(data.db, "get_connection", lambda: FakeConn([]))
    monkeypatch.setattr(sc, "_get_current_bankroll", lambda conn: 1000.0)
    prices = []
    monkeypatch.setattr(lpl, "record_live_prices",
                        lambda conn, rows, known_game_ids=None: prices.extend(rows) or len(rows))
    rc = G.main([])
    _run_loop.prices = prices
    return rc, writes, notes, evals, feed


def test_one_bet_per_game_and_the_five_minute_cadence(monkeypatch):
    """E1 qualifies on its first evaluation; E2 (a game the cut never clears)
    is in the window throughout. E1 is written ONCE and never re-evaluated;
    E2 is evaluated once per 5-minute wall-clock slot; a transitional E2 state
    at the first tick of the t=300 slot SPENDS that slot (it is not carried to
    t=320) -- the fixed grid the evidence sampled."""
    e1 = live_state(eid="E1", poss="away")                       # TB up 8, BET at -500
    e2 = live_state(eid="E2", home=20, away=14, poss="home")     # NYG up 6
    e2_trans = live_state(eid="E2", home=20, away=14, poss=None, evaluable=False,
                          reason="no scrimmage down (down=0): transitional")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    final2 = live_state(eid="E2", state="post", final=True, evaluable=False)
    ticks = []
    for i in range(46):                                  # 0 .. 900 s in 20 s ticks
        t = i * 20
        ticks.append({"E1": e1, "E2": e2_trans if t == 300 else e2})
    ticks += [{"E1": final, "E2": final2}] * 4
    payload = quote_payload(450, -500) + quote_payload(-100000, 99999, home="New York Giants",
                                                        away="Washington Commanders")
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, payload)
    assert rc == 0
    assert len(writes) == 1 and writes[0]["pick_label"] == "TB ML (live)"
    # Announced on the pass that wrote it, then re-asked at most every 300 s
    # so a failed post is retried (the notifiers' ledgers make repeats no-ops).
    assert set(notes) == {"2026-10-08"} and 2 <= len(notes) <= 4
    e1_evals = [t for e, t in evals if e == "E1"]
    e2_evals = [t for e, t in evals if e == "E2"]
    assert e1_evals == [0.0]
    assert e2_evals == [0.0, 600.0, 900.0]
    assert feed.fetches == len(set(t for _, t in evals))      # one bulk call per due pass
    # every DraftKings quote decided on is logged to `odds` as in_play
    rows = _run_loop.prices
    assert rows and {r["snapshot_type"] for r in rows} == {"in_play"}
    assert {r["bookmaker"] for r in rows} == {"draftkings"} and {r["market"] for r in rows} == {"h2h"}
    tb = [r for r in rows if r["game_id"] == CTX.game_id]
    assert len(tb) == 1 and (tb[0]["home_price"], tb[0]["away_price"]) == (450, -500)
    assert tb[0]["snapshot_at"] == "2026-10-09T03:00:00Z"     # the BOOK's publish time


def test_a_game_with_a_bet_from_an_earlier_process_is_not_rebet(monkeypatch):
    e1 = live_state(eid="E1", poss="away")
    e2 = live_state(eid="E2", home=20, away=14, poss="home", evaluable=False, reason="x")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    ticks = [{"E1": e1, "E2": e2}] * 5 + [{"E1": final, "E2": final}] * 4
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, quote_payload(450, -500),
                                               locked=True)
    assert writes == [] and evals == [] and feed.fetches == 0


def test_an_unanswered_status_feed_is_not_an_empty_slate(monkeypatch):
    """Five ticks where every ESPN status read failed, then a live game that
    qualifies: the loop must still be running to bet it (three idle ticks
    would have ended it)."""
    down = LiveState(event_id="E1", status_state=None, status_name=None, period=None,
                     running_clock=None, reason="status unavailable")
    down2 = LiveState(event_id="E2", status_state=None, status_name=None, period=None,
                      running_clock=None, reason="status unavailable")
    e1 = live_state(eid="E1", poss="away")
    e2 = live_state(eid="E2", home=20, away=14, poss="home", evaluable=False, reason="x")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    ticks = [{"E1": down, "E2": down2}] * 5 + [{"E1": e1, "E2": e2}] + \
        [{"E1": final, "E2": final}] * 4
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, quote_payload(450, -500))
    assert rc == 0 and len(writes) == 1


def test_preseason_and_unknown_season_types_are_never_priced(monkeypatch):
    e1 = live_state(eid="E1", poss="away")
    e2 = live_state(eid="E2", home=20, away=14, poss="home")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    ticks = [{"E1": e1, "E2": e2}] * 3 + [{"E1": final, "E2": final}] * 4
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, quote_payload(450, -500),
                                               season_types={"E1": 1, "E2": None})
    assert rc == 0 and writes == [] and evals == [] and feed.fetches == 0


def test_a_standing_bet_from_an_earlier_process_is_still_announced(monkeypatch):
    e1 = live_state(eid="E1", poss="away")
    e2 = live_state(eid="E2", home=20, away=14, poss="home", evaluable=False, reason="x")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    ticks = [{"E1": e1, "E2": e2}] * 3 + [{"E1": final, "E2": final}] * 4
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, quote_payload(450, -500),
                                               locked=True)
    assert writes == [] and notes and set(notes) == {"2026-10-08"}


def test_the_pick_row_binds_every_parameter_of_the_real_insert(art):
    """_insert_picks binds ~40 named parameters; a key the loop forgot would
    raise on the first live BET, inside a non-fatal try that only logs. Run the
    REAL insert against a recording connection."""
    import re

    from models.scorer import _insert_picks

    class Rec:
        def __init__(self):
            self.calls = []

        def executemany(self, sql, rows):
            self.calls.append((sql, list(rows)))

    d = M.decide(art, period=4, secs=300, home_score=16, away_score=24, possession="away",
                 spread_home=-8.5, home_price=450, away_price=-500)
    pick = G.build_pick(CTX, live_state(poss="away"), d, 1000.0)
    conn = Rec()
    _insert_picks(conn, [dict(pick)])
    sql, rows = conn.calls[0]
    names = set(re.findall(r"%\((\w+)\)s", sql))
    assert len(names) >= 35
    missing = names - set(rows[0])
    assert not missing, f"the pick row lacks {sorted(missing)}"
    r = rows[0]
    assert r["decision_book"] == "draftkings" and r["decision_odds"] == -500.0
    assert r["model_probability_cal"] == r["model_probability"]   # its own probability
    assert r["is_live"] is True and r["best_book"] is None


def test_a_failed_odds_fetch_backs_off_instead_of_calling_every_tick(monkeypatch):
    """A 401/429/5xx returns None. The loop must not call again on the next
    20-second tick: 60 s, then 120 s, then 300 s."""
    e1 = live_state(eid="E1", poss="away")
    e2 = live_state(eid="E2", home=20, away=14, poss="home", evaluable=False, reason="x")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    ticks = [{"E1": e1, "E2": e2}] * 15 + [{"E1": final, "E2": final}] * 4   # 0..280 s
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, ticks, None)
    # without the backoff this is one call per tick: 15
    assert 1 <= feed.fetches <= 3 and writes == []


def test_the_session_call_cap_stops_calling(monkeypatch):
    """A call that fails before any header is read moves no credit meter --
    a connection error raises, a 5xx carries no x-requests-last -- so the
    number of calls is capped on its own."""
    import nfl_live_leader.odds as O

    class R:
        status_code = 500
        headers = {}

        def raise_for_status(self):
            raise RuntimeError("500")

    class S:
        n = 0

        def get(self, *a, **k):
            S.n += 1
            if S.n % 2:
                raise ConnectionError("reset")
            return R()

    monkeypatch.setenv("ODDS_API_KEY", "x")
    feed = O.LiveOddsFeed(cap=10, session=S())
    for _ in range(O.SESSION_CALL_CAP + 5):
        assert feed.fetch() is None
    assert S.n == O.SESSION_CALL_CAP
