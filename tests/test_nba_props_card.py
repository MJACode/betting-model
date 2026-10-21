"""The NBA prop door (scripts/nba_props_card.py): one bet a game across both NBA prop models,
MAX_NBA_PROP_BETS_PER_NIGHT a night, ranked by each bet's EV percentile within its own model
(models/nba_prop_rank.py).

mike, 2026-10-20, after opening night wrote 36 NBA prop bets on one game: "Only the strongest
picks need to be sent, like NHL." Each test pins one property of the door: one a game across
both models; the highest percentile within its own model wins, whichever model's list comes
first; the night cap counts the bets
already written (a VOIDed one excepted); a game already bet gets nothing; a dropped candidate
leaves no picks row; each card's ledger still records its decision; and neither card writes alone.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

import models.nba_prop_market as mk
import models.nba_prop_projection as pj
import models.nba_prop_rank as rank
import scripts.nba_prop_market_card as rule_card
import scripts.nba_prop_projection_card as projection_card
import scripts.nba_props_card as door

TIP = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)
FETCH = (TIP - timedelta(minutes=55)).isoformat()
NIGHT = "2026-10-21"
RULE, PROJ = "nba_prop_market", "nba_prop_projection"


def _rule_bet(gid, ev, player="Stephen Curry", pid="201939", market="player_points", line=24.5,
              game_date=NIGHT):
    return mk.NbaPropBet(
        game_id=gid, game_date=game_date, tip=TIP.isoformat(), player=player, player_id=pid,
        market=market, line=line, book="fanduel", price=105.0, fair=0.5, ev=ev, link="fd-u",
        sharp_over=-110, sharp_under=-110, fetch=FETCH, soft_last_update=FETCH,
        sharp_last_update=FETCH, dk_price=None, dk_link=None, dk_player=None)


def _proj_bet(gid, ev, player="LeBron James", pid="2544", market="player_steals", line=1.5,
              side="over", game_date=NIGHT):
    return pj.ProjectionBet(
        game_id=gid, game_date=game_date, tip=TIP.isoformat(), player=player, player_id=pid,
        market=market, side=side, line=line, book="fanduel", price=110.0, prob=0.55, ev=ev, mu=1.4,
        link="fd-o", fetch=FETCH, book_last_update=FETCH, dk_price=None, dk_link=None)


def _rule_rows(*bets):
    return rule_card.pick_rows(list(bets), bankroll=1000.0)


def _proj_rows(*bets):
    return projection_card.pick_rows(list(bets), bankroll=1000.0)


def _rule_dec(gid):
    return mk.NbaPropDecision(game_id=gid, fetch_at=FETCH, n_quotes=10, n_bets=0, detail="in_window=1")


def _proj_dec(gid):
    return {"game_id": gid, "fetch_at": FETCH, "n_quotes": 10, "n_bets": 0, "detail": "in_window=1",
            "projected_at": FETCH}


class _Conn:
    """picks and the two ledgers, enough for the door's reads and writes."""

    def __init__(self, taken=(), night=None, rule_decided=(), proj_decided=(), rule_bet=(),
                 picks_conflict=False):
        self.picks_conflict = picks_conflict
        self.taken, self.night = set(taken), dict(night or {})
        self.rule_decided, self.proj_decided = set(rule_decided), set(proj_decided)
        self.rule_bet = set(rule_bet)
        self.sql, self.picks, self.ledger, self.commits = [], [], [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.sql.append(s)
        self._one, self._all = None, []
        if s.startswith("SELECT game_id FROM nba_prop_market_decisions"):
            self._all = [(g,) for g in params[0] if g in self.rule_decided]
        elif s.startswith("SELECT game_id FROM nba_prop_projection_decisions"):
            self._all = [(g,) for g in params[0] if g in self.proj_decided]
        elif s.startswith("SELECT DISTINCT game_id FROM picks WHERE model_id = %s"):
            self._all = [(g,) for g in params[1] if g in self.rule_bet]
        elif s.startswith("SELECT DISTINCT game_id FROM picks WHERE model_id = ANY"):
            assert tuple(params[0]) == door.PROP_MODEL_IDS
            self._all = [(g,) for g in params[1] if g in self.taken]
        elif s.startswith("SELECT game_date, count(*) FROM picks"):
            self._all = [(d, n) for d, n in self.night.items() if d in params[1]]
        elif s.startswith("INSERT INTO nba_prop_market_decisions"):
            self._insert_decision(RULE, self.rule_decided, params)
        elif s.startswith("INSERT INTO nba_prop_projection_decisions"):
            self._insert_decision(PROJ, self.proj_decided, params)
        elif s.startswith("INSERT INTO picks"):
            if self.picks_conflict:
                return self
            self.picks.append(params)
            self._one = (len(self.picks),)
        elif s.startswith("UPDATE nba_prop_") and "SET n_bets" in s:
            model = RULE if s.startswith("UPDATE nba_prop_market_decisions") else PROJ
            n, gid = params
            self.ledger = [(m, g, n if (m, g) == (model, gid) else k, d) for m, g, k, d in self.ledger]
        return self

    def _insert_decision(self, model, decided, params):
        if params["game_id"] not in decided:
            decided.add(params["game_id"])
            self.ledger.append((model, params["game_id"], params["n_bets"], params["detail"]))
            self._one = (params["game_id"],)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def commit(self):
        self.sql.append("COMMIT")
        self.commits += 1


def _written(conn):
    return sorted((p["model_id"], p["game_id"], p["pick_label"]) for p in conn.picks)


# ── one bet a game, across both models ───────────────────────────────────────

def test_one_bet_a_game_across_both_models():
    """Opening night: 36 bets on one game. Now the two models' candidates in a game make ONE bet,
    the one highest in its own model's EVs: the rule's 0.05 (about its 89th percentile) beats the
    projection's 0.06 (about its 32nd), although 0.06 is the larger EV."""
    rows = (_rule_rows(_rule_bet("G1", 0.05), _rule_bet("G1", 0.04, market="player_rebounds", line=7.5),
                       _rule_bet("G1", 0.03, market="player_assists", line=6.5))
            + _proj_rows(_proj_bet("G1", 0.06), _proj_bet("G1", 0.02, market="player_blocks", line=0.5)))
    conn = _Conn()
    out = door.publish_across_models(conn, rows, [_rule_dec("G1")], [_proj_dec("G1")])
    assert out["written"] == 1 and len(conn.picks) == 1
    assert conn.picks[0]["model_id"] == RULE and conn.picks[0]["prop_market"] == "player_points"
    assert door.MAX_NBA_PROP_BETS_PER_GAME == 1


def test_the_best_percentile_wins_whichever_models_list_comes_first():
    """The order the cards run in must not decide which model's bet a game gets."""
    rule = _rule_rows(_rule_bet("G1", 0.08), _rule_bet("G2", 0.01))
    proj = _proj_rows(_proj_bet("G1", 0.03), _proj_bet("G2", 0.09))
    a, b = _Conn(), _Conn()
    door.publish_across_models(a, rule + proj, [_rule_dec("G1"), _rule_dec("G2")],
                               [_proj_dec("G1"), _proj_dec("G2")])
    door.publish_across_models(b, proj + rule, [_rule_dec("G1"), _rule_dec("G2")],
                               [_proj_dec("G1"), _proj_dec("G2")])
    assert _written(a) == _written(b)
    assert {(m, g) for m, g, _ in _written(a)} == {(RULE, "G1"), (PROJ, "G2")}
    # a tie on EV goes the same way too
    t1, t2 = _rule_rows(_rule_bet("G3", 0.05)), _proj_rows(_proj_bet("G3", 0.05))
    assert door.one_per_game(t1 + t2) == door.one_per_game(t2 + t1)


def test_run_cards_gathers_both_models_before_it_chooses(monkeypatch):
    """Both cards look first (the projection card told which games the rule decides in this look),
    then ONE door call sees every candidate of both."""
    calls = []

    class _C:
        def close(self):
            pass

    monkeypatch.setattr(door, "get_connection", lambda: _C())
    monkeypatch.setattr(rule_card, "look", lambda conn, now: calls.append("rule") or {
        "games": {"G1": {}}, "bets": [_rule_bet("G1", 0.02)], "diag": {}, "decisions": [_rule_dec("G1")]})

    def _proj_look(conn, now, art=None, rule_deciding=frozenset()):
        calls.append(("proj", set(rule_deciding)))
        return {"games": {"G1": {}}, "bets": [_proj_bet("G1", 0.07)], "diag": {},
                "decisions": [_proj_dec("G1")], "names": {}}

    monkeypatch.setattr(projection_card, "look", _proj_look)
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    seen = {}

    def _door(conn, rows, rule_decisions, projection_decisions):
        calls.append("door")
        seen["models"] = sorted(r["model_id"] for r in rows)
        return {"written": 1, "decided": {RULE: 1, PROJ: 1}, "dropped": {}}

    monkeypatch.setattr(door, "publish_across_models", _door)
    out = door.run_cards(do_publish=True, now=TIP - timedelta(minutes=55))
    assert calls == ["rule", ("proj", {"G1"}), "door"]
    assert seen["models"] == [RULE, PROJ] and out["published"] == 1


# ── the night ────────────────────────────────────────────────────────────────

def test_the_night_cap_counts_the_bets_already_written():
    """Three bets already written tonight and a cap of four: one more, the highest percentile,
    whatever game."""
    rows = (_rule_rows(*[_rule_bet(f"G{i}", 0.01 * (i + 1)) for i in range(4)])
            + _proj_rows(_proj_bet("G9", 0.035)))
    decs = [_rule_dec(f"G{i}") for i in range(4)]
    conn = _Conn(night={NIGHT: door.MAX_NBA_PROP_BETS_PER_NIGHT - 1})
    out = door.publish_across_models(conn, rows, decs, [_proj_dec("G9")])
    assert out["written"] == 1 and [p["game_id"] for p in conn.picks] == ["G3"]      # rule EV 0.04
    full = _Conn(night={NIGHT: door.MAX_NBA_PROP_BETS_PER_NIGHT})
    assert door.publish_across_models(full, rows, decs, [_proj_dec("G9")])["written"] == 0
    assert full.picks == []
    # a fresh night takes the best four, one a game: the projection's 0.035 is about its 10th
    # percentile, below the rule's 0.01 (about its 29th)
    fresh = _Conn()
    door.publish_across_models(fresh, rows, decs, [_proj_dec("G9")])
    assert sorted(p["game_id"] for p in fresh.picks) == ["G0", "G1", "G2", "G3"]
    assert len(fresh.picks) == door.MAX_NBA_PROP_BETS_PER_NIGHT


def test_a_voided_bet_does_not_use_a_nights_slot():
    """2026-10-20: 36 VOIDed opening-night bets would fill that night nine times over. The night's
    count reads BET rows of both models and leaves VOID out; the read is by game_date."""
    conn = _Conn()
    door.prop_bets_by_night(conn, [NIGHT])
    (sql,) = [s for s in conn.sql if "count(*)" in s]
    assert "condition_status IS DISTINCT FROM 'VOID'" in sql
    assert "signal_type = 'BET'" in sql and "model_id = ANY(%s)" in sql and "game_date = ANY(%s)" in sql
    # the one-a-game read keeps a VOIDed game bet (it was decided), so it does not filter VOID
    door.games_with_a_prop_bet(conn, ["G1"])
    assert "VOID" not in conn.sql[-1]


def test_the_nba_night_cap_is_four():
    """NBA's own number, set by the NBA grade (4 a night in tip order); not tied to NHL's."""
    assert door.MAX_NBA_PROP_BETS_PER_NIGHT == 4
    assert door.PROP_MODEL_IDS == (RULE, PROJ)
    for name in ("one_per_game", "per_night", "games_with_a_prop_bet", "prop_bets_by_night",
                 "publish_across_models"):
        assert callable(getattr(door, name)), name


# ── a game already bet, and what a dropped candidate leaves ──────────────────

def test_a_game_already_bet_gets_nothing():
    """A later look never adds a second bet to a game either model has bet. The model deciding it
    now still records its decision, with no bet and the reason."""
    rows = _proj_rows(_proj_bet("G1", 0.20))
    conn = _Conn(taken={"G1"})
    out = door.publish_across_models(conn, rows, [], [_proj_dec("G1")])
    assert out["written"] == 0 and conn.picks == []
    assert conn.ledger == [(PROJ, "G1", 0, "in_window=1 cap_game_already_bet=1")]


def test_a_dropped_candidate_leaves_no_pick_row_and_the_ledger_says_why():
    rows = (_rule_rows(_rule_bet("G1", 0.05), _rule_bet("G1", 0.04, market="player_rebounds", line=7.5))
            + _proj_rows(_proj_bet("G1", 0.02)))
    conn = _Conn()
    door.publish_across_models(conn, rows, [_rule_dec("G1")], [_proj_dec("G1")])
    assert [p["prop_market"] for p in conn.picks] == ["player_points"]
    assert sorted(conn.ledger) == [(RULE, "G1", 1, "in_window=1 cap_one_a_game=1"),
                                   (PROJ, "G1", 0, "in_window=1 cap_one_a_game=1")]
    night = _Conn(night={NIGHT: door.MAX_NBA_PROP_BETS_PER_NIGHT})
    door.publish_across_models(night, _rule_rows(_rule_bet("G1", 0.05)), [_rule_dec("G1")], [])
    assert night.picks == [] and night.ledger == [(RULE, "G1", 0, "in_window=1 cap_night_full=1")]


def test_each_card_still_decides_a_game_once():
    """A game a card has already decided is written nowhere again, and the rule never decides a
    game it already bet; the other model may still decide it (with nothing to bet)."""
    rows = _rule_rows(_rule_bet("G1", 0.09)) + _proj_rows(_proj_bet("G1", 0.01))
    conn = _Conn(rule_decided={"G1"})
    door.publish_across_models(conn, rows, [_rule_dec("G1")], [_proj_dec("G1")])
    assert [(p["model_id"], p["game_id"]) for p in conn.picks] == [(PROJ, "G1")]
    assert conn.ledger == [(PROJ, "G1", 1, "in_window=1")]
    conn = _Conn(rule_bet={"G1"}, taken={"G1"})
    door.publish_across_models(conn, rows, [_rule_dec("G1")], [])
    assert conn.picks == [] and conn.ledger == []


def test_the_door_reads_under_both_locks_and_writes_in_one_transaction(monkeypatch):
    import scripts.nfl_wind_publisher as wp
    locks = []
    monkeypatch.setattr(wp, "_lock_model", lambda conn, mid: (locks.append(mid), conn.sql.append("LOCK")))
    conn = _Conn()
    door.publish_across_models(conn, _rule_rows(_rule_bet("G1", 0.05)), [_rule_dec("G1")], [_proj_dec("G1")])
    assert locks == [RULE, PROJ]                    # the rule's first: the order every writer takes
    last_lock = max(i for i, s in enumerate(conn.sql) if s == "LOCK")
    reads = [i for i, s in enumerate(conn.sql) if s.startswith("SELECT")]
    assert reads and last_lock < min(reads)
    assert conn.commits == 1 and conn.sql[-1] == "COMMIT"


# ── no other door ────────────────────────────────────────────────────────────

def test_neither_card_writes_on_its_own(monkeypatch):
    """One model's card publishing alone would hand the game's one bet to whichever ran first."""
    for card in (rule_card, projection_card):
        assert not hasattr(card, "publish"), card.__name__
        assert "INSERT INTO picks" not in inspect.getsource(card.run_card)
    seen = []
    monkeypatch.setattr(door, "run_cards", lambda **kw: seen.append(kw) or {"published": 0})
    rule_card.run_card(do_publish=True, now=TIP)
    projection_card.run_card(do_publish=True, now=TIP)
    assert [kw["do_publish"] for kw in seen] == [True, True]


@pytest.mark.parametrize("step", ["nba-props", "nba-prop-market", "nba-prop-projection"])
def test_every_nba_prop_step_name_runs_both_cards_through_the_door(monkeypatch, step):
    import run_pipeline as rp
    seen = []
    monkeypatch.setattr(door, "run_cards", lambda do_publish=False, **kw: seen.append(do_publish) or {})
    fn = {"nba-props": rp.step_nba_props, "nba-prop-market": rp.step_nba_prop_market,
          "nba-prop-projection": rp.step_nba_prop_projection}[step]
    assert fn(dry_run=False) is True and seen == [True]
    text = inspect.getsource(rp)
    assert f'"{step}"' in text.split("choices=[", 1)[1].split("]", 1)[0]


def test_the_refresh_pass_runs_the_nba_prop_cards_as_one_step():
    from pathlib import Path
    sh = (Path(door.__file__).parent / "refresh_pass.sh").read_text(encoding="utf-8")
    steps = [ln.split()[1] for ln in sh.splitlines() if ln.startswith("step nba-prop")]
    assert "step nba-props" in sh
    assert "nba-prop-market" not in steps and "nba-prop-projection" not in steps


# ── the ranking: each bet's EV percentile within its own model ───────────────

@pytest.mark.parametrize("model", [RULE, PROJ])
def test_a_models_median_ev_ranks_one_half(model):
    q = rank.BREAKPOINTS[model]
    assert len(q) == 101 and list(q) == sorted(q)
    assert rank.ev_percentile(model, q[50]) == pytest.approx(0.5)
    assert rank.ev_percentile(model, q[0]) == 0.0 and rank.ev_percentile(model, q[-1]) == 1.0


@pytest.mark.parametrize("model", [RULE, PROJ])
def test_the_percentile_is_monotone_in_ev_within_a_model(model):
    evs = [i / 2000 - 0.05 for i in range(2200)]               # -0.05 .. 1.05
    pct = [rank.ev_percentile(model, e) for e in evs]
    assert all(b >= a for a, b in zip(pct, pct[1:]))
    q = rank.BREAKPOINTS[model]
    inside = [p for e, p in zip(evs, pct) if q[0] < e < q[-1]]
    assert all(b > a for a, b in zip(inside, inside[1:]))      # strictly, between its breakpoints
    assert min(pct) == 0.0 and max(pct) == 1.0
    with pytest.raises(KeyError):
        rank.ev_percentile("nba_prop_unknown", 0.05)


def test_a_market_bet_at_its_95th_percentile_beats_a_projection_bet_at_its_60th():
    """The two EVs are on different scales: raw EV gave the projection model 99.7% of the pooled
    top tenth. A bet is compared on where its EV sits among its own model's graded EVs."""
    ev_rule, ev_proj = rank.BREAKPOINTS[RULE][95], rank.BREAKPOINTS[PROJ][60]
    assert ev_proj > ev_rule                                   # the projection's raw EV is larger
    rows = _rule_rows(_rule_bet("G1", ev_rule)) + _proj_rows(_proj_bet("G1", ev_proj))
    for pool in (rows, rows[::-1]):
        (kept,) = door.one_per_game(pool)
        assert kept["model_id"] == RULE
    conn = _Conn()
    door.publish_across_models(conn, rows, [_rule_dec("G1")], [_proj_dec("G1")])
    assert [(p["model_id"], p["prop_market"]) for p in conn.picks] == [(RULE, "player_points")]


def test_a_tie_on_percentile_goes_to_the_higher_raw_ev():
    """Both above their model's highest graded EV: both rank 1.0, so the larger EV wins."""
    rows = _rule_rows(_rule_bet("G1", 0.40)) + _proj_rows(_proj_bet("G1", 1.20))
    assert rank.ev_percentile(RULE, 0.40) == rank.ev_percentile(PROJ, 1.20) == 1.0
    for pool in (rows, rows[::-1]):
        (kept,) = door.one_per_game(pool)
        assert kept["model_id"] == PROJ


def test_the_night_is_filled_by_percentile_too():
    """Five games deciding in one look: the lowest percentile is the one left out, even where its
    raw EV is the largest."""
    q_r, q_p = rank.BREAKPOINTS[RULE], rank.BREAKPOINTS[PROJ]
    rows = (_rule_rows(*[_rule_bet(f"G{i}", q_r[90 + i]) for i in range(4)])
            + _proj_rows(_proj_bet("G9", q_p[50])))
    assert q_p[50] > max(q_r[90:94])
    chosen = door.per_night(door.one_per_game(rows))
    assert sorted(r["game_id"] for r in chosen) == ["G0", "G1", "G2", "G3"]


# ── one model's look failing does not stop the other ─────────────────────────

def _patch_looks(monkeypatch, rule_look, proj_look):
    class _C:
        def close(self):
            pass

    monkeypatch.setattr(door, "get_connection", lambda: _C())
    monkeypatch.setattr(rule_card, "look", rule_look)
    monkeypatch.setattr(projection_card, "look", proj_look)
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    seen = {}

    def _door(conn, rows, rule_decisions, projection_decisions):
        seen["rows"] = sorted((r["model_id"], r["game_id"]) for r in rows)
        seen["decisions"] = ([d.game_id for d in rule_decisions],
                             [d["game_id"] for d in projection_decisions])
        return {"written": len(rows), "decided": {RULE: len(rule_decisions),
                                                  PROJ: len(projection_decisions)}, "dropped": {}}

    monkeypatch.setattr(door, "publish_across_models", _door)
    return seen


def test_the_projection_look_raising_does_not_stop_the_rule(monkeypatch):
    """Review item 2. Before the door, each card ran as its own process. Now one look's error is
    logged, the other model still decides and writes, and the step reports the failure."""
    def _boom(conn, now, art=None, rule_deciding=frozenset()):
        raise RuntimeError("projection artifact missing")

    seen = _patch_looks(monkeypatch, lambda conn, now: {
        "games": {"G1": {}}, "bets": [_rule_bet("G1", 0.05)], "diag": {}, "decisions": [_rule_dec("G1")]},
        _boom)
    out = door.run_cards(do_publish=True, now=TIP - timedelta(minutes=55))
    assert seen["rows"] == [(RULE, "G1")] and seen["decisions"] == (["G1"], [])
    assert out["published"] == 1 and "projection artifact missing" in out["errors"][PROJ]
    assert RULE not in out["errors"]
    import run_pipeline as rp
    monkeypatch.setattr(door, "run_cards", lambda do_publish=False, **kw: out)
    assert rp.step_nba_props(dry_run=False) is False          # the step exits 1


def test_the_rule_look_raising_does_not_stop_the_projection(monkeypatch):
    calls = []

    def _boom(conn, now):
        raise RuntimeError("no Pinnacle")

    def _proj_look(conn, now, art=None, rule_deciding=frozenset()):
        calls.append(set(rule_deciding))
        return {"games": {"G1": {}}, "bets": [_proj_bet("G1", 0.10)], "diag": {},
                "decisions": [_proj_dec("G1")], "names": {}}

    seen = _patch_looks(monkeypatch, _boom, _proj_look)
    out = door.run_cards(do_publish=True, now=TIP - timedelta(minutes=55))
    assert calls == [set()]
    assert seen["rows"] == [(PROJ, "G1")] and seen["decisions"] == ([], ["G1"])
    assert "no Pinnacle" in out["errors"][RULE] and PROJ not in out["errors"]


def test_a_clean_look_reports_no_errors(monkeypatch):
    _patch_looks(monkeypatch, lambda conn, now: {
        "games": {}, "bets": [], "diag": {}, "decisions": []},
        lambda conn, now, art=None, rule_deciding=frozenset(): {
            "games": {}, "bets": [], "diag": {}, "decisions": [], "names": {}})
    out = door.run_cards(do_publish=True, now=TIP)
    assert out["errors"] == {}
    import run_pipeline as rp
    monkeypatch.setattr(door, "run_cards", lambda do_publish=False, **kw: out)
    assert rp.step_nba_props(dry_run=False) is True


# ── the ledger counts what was written ───────────────────────────────────────

def test_the_ledger_counts_the_bets_that_were_written():
    """Review item 5. A picks insert that returns no row (ON CONFLICT DO NOTHING) wrote nothing,
    so the game's ledger row says 0, not 1."""
    conn = _Conn(picks_conflict=True)
    out = door.publish_across_models(conn, _rule_rows(_rule_bet("G1", 0.05)), [_rule_dec("G1")], [])
    assert out["written"] == 0 and conn.picks == []
    assert conn.ledger == [(RULE, "G1", 0, "in_window=1")]
    ok = _Conn()
    door.publish_across_models(ok, _proj_rows(_proj_bet("G1", 0.10)), [], [_proj_dec("G1")])
    assert ok.ledger == [(PROJ, "G1", 1, "in_window=1")]
    assert not any(s.startswith("UPDATE") for s in ok.sql)    # no correction when all were written


# ── the 6am run ──────────────────────────────────────────────────────────────

def test_the_6am_run_calls_the_combined_step_once():
    """Review item 4: both old step names point at the combined step, so calling both ran it twice."""
    import run_pipeline as rp
    src = inspect.getsource(rp.run_daily_pipeline)
    assert src.count("step_nba_props(") == 1
    assert "step_nba_prop_market(" not in src and "step_nba_prop_projection(" not in src
