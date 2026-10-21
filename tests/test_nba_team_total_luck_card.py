"""The NBA home team-total card (scripts/nba_team_total_luck_card.py), end to
end on stored rows: the live feed stores a fetch, the card decides on what is
stored, writes the pick row, and never decides the game again.

The database is tests/test_nba_team_total_odds.FakeDB and the Odds API its
FakeFeed (no paid call, no production write). The ratings are forced (the home
team's part of the gap set directly, as tests/test_nba_team_total_luck.py
does); everything after them -- quotes, fair line, offer, floors, label, row,
ledger, lock -- is the code that runs live.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import data.ingestors.nba_team_total_odds as feed  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import scripts.nba_team_total_luck_card as card  # noqa: E402
from tests.test_nba_team_total_odds import (FANDUEL_LADDER, GID, TIP, book,  # noqa: E402
                                            world)
from tests.test_nba_team_total_luck import _no_missing, _proj  # noqa: E402

GAMES = {GID: {"home": "MIL", "away": "BOS", "game_date": "2026-11-05", "season": 2027,
               "tip": TIP}}
EMPTY_FINAL = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team",
                                    "away_team", "home_score", "away_score"])
EMPTY_BOX = pd.DataFrame(columns=["game_id", "team", *tt.BOX_COLS])


def card_world(monkeypatch, part=-3.0, **kw):
    """The feed and the card on one FakeDB; the home part forced to `part`."""
    clock, db, f = world(monkeypatch, **kw)
    seen = {}

    def fake_slate(conn, now, skipped=None, horizon_min=None):
        seen["horizon"] = horizon_min
        return {g: dict(v) for g, v in GAMES.items()
                if now < v["tip"] <= now + timedelta(minutes=horizon_min)}
    monkeypatch.setattr(card, "get_connection", lambda: db)
    monkeypatch.setattr(card.tlcard, "slate", fake_slate)
    monkeypatch.setattr(card.tlcard, "load_season",
                        lambda conn, season, before: (EMPTY_FINAL, EMPTY_BOX, EMPTY_FINAL))
    monkeypatch.setattr(tt, "f4_projections", lambda targets, tb: _proj(targets, part))
    _no_missing(monkeypatch)
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    return clock, db, f, seen


def _run(clock, after_s=30):
    return card.run_card(do_publish=True, now=clock() + timedelta(seconds=after_s))


def test_a_game_with_no_draftkings_team_total_is_stored_decided_and_bet(monkeypatch):
    """RULE: DraftKings hung no team total; FanDuel's under is the best price
    at Pinnacle's fair line, so the bet is written there, with no DraftKings
    price and line_book naming the book. The label is the platform's, the line
    exactly the stored one, the probability the market's plus the uplift."""
    clock, db, f, seen = card_world(monkeypatch)
    feed.fetch_team_totals([GID], "open", conn=db)
    out = _run(clock)
    assert seen["horizon"] == tt.DECISION_LEAD_MIN[1] + 5
    assert out["published"] == 1 and out["decided"] == 1
    [p] = db.rows["picks"]
    assert p["pick_label"] == "BOS @ MIL — MIL Team Total Under 113.5"
    assert (p["pick_side"], p["scored_line"]) == ("under", 113.5)
    assert (p["decision_book"], p["decision_odds"]) == ("fanduel", -105.0)
    assert p["dk_odds"] is None and p["line_book"] == "fanduel"
    assert (p["dk_implied_prob"], p["edge"]) == (0.0, 0.0)
    assert (p["best_book"], p["best_bet_link"]) == ("fanduel", "https://fanduel/under/113.5")
    assert p["model_probability"] == p["model_probability_cal"]
    [d] = db.rows["nba_team_total_luck_decisions"]
    assert d["n_bets"] == 1 and d["home_part"] == -3.0 and d["book"] == "fanduel"
    assert p["model_probability"] == pytest.approx(
        d["p_fair"] + tt.uplift(card.artifact(), 2027), abs=1e-4)
    assert set(json.loads(d["book_ages"])) == {"fanduel", "pinnacle"}
    assert 55.0 < d["lead_min"] < 56.0


def test_draftkings_own_under_at_the_number_is_the_reference(monkeypatch):
    bodies = {"ev-mil": [book("fanduel", FANDUEL_LADDER),
                         book("draftkings", [(113.5, -112, -108)]),
                         book("pinnacle", [(113.5, -108, -108)])]}
    clock, db, f, _ = card_world(monkeypatch, bodies=bodies)
    feed.fetch_team_totals([GID], "open", conn=db)
    _run(clock)
    [p] = db.rows["picks"]
    assert p["decision_book"] == "fanduel" and p["dk_odds"] == -108.0 and p["line_book"] is None
    assert p["dk_bet_link"] == "https://draftkings/under/113.5"


def test_a_rerun_and_a_later_better_price_write_nothing(monkeypatch):
    """RULE (CLAUDE.md 1c): each game is decided once. The same run again, and
    a later fetch at a better price, write no decision and no pick."""
    clock, db, f, _ = card_world(monkeypatch)
    feed.fetch_team_totals([GID], "open", conn=db)
    assert _run(clock)["published"] == 1
    again = _run(clock, after_s=40)
    assert (again["published"], again["decided"]) == (0, 0)
    assert again["timing"]["already_decided"] == 1
    clock.tick(60)
    f.bodies["ev-mil"] = [book("fanduel", [(113.5, -130, +115)]),
                          book("pinnacle", [(113.5, -108, -108)])]
    feed.fetch_team_totals([GID], "open", conn=db)
    later = _run(clock)
    assert (later["published"], later["decided"]) == (0, 0)
    assert len(db.rows["picks"]) == 1 and db.rows["picks"][0]["decision_odds"] == -105.0
    assert len(db.rows["nba_team_total_luck_decisions"]) == 1


def test_a_fetch_that_offered_nothing_decides_the_game_with_no_bet(monkeypatch):
    """RULE: a call that came back with no team total is a fetch: the game is
    decided, with the reason, and a later fetch that offers one bets nothing."""
    clock, db, f, _ = card_world(monkeypatch, bodies={"ev-mil": []})
    feed.fetch_team_totals([GID], "open", conn=db)
    out = _run(clock)
    assert out["decided"] == 1 and out["published"] == 0 and db.rows["picks"] == []
    [d] = db.rows["nba_team_total_luck_decisions"]
    assert d["detail"] == "no_fair_line" and d["n_bets"] == 0 and d["home_part"] == -3.0
    clock.tick(60)
    f.bodies["ev-mil"] = [book("fanduel", FANDUEL_LADDER), book("pinnacle", [(113.5, -108, -108)])]
    feed.fetch_team_totals([GID], "open", conn=db)
    assert _run(clock)["published"] == 0 and db.rows["picks"] == []


def test_a_failed_call_is_not_a_fetch(monkeypatch):
    """A failed call decides nothing; the next tick's fetch does."""
    clock, db, f, _ = card_world(monkeypatch, fail={"ev-mil"})
    feed.fetch_team_totals([GID], "open", conn=db)
    out = _run(clock)
    assert out["decided"] == 0 and out["timing"]["no_fetch"] == 1
    f.fail.clear()
    clock.tick(60)
    feed.fetch_team_totals([GID], "open", conn=db)
    assert _run(clock)["published"] == 1


def test_the_closing_snapshot_never_decides(monkeypatch):
    clock, db, f, _ = card_world(monkeypatch)
    feed.fetch_team_totals([GID], "close", conn=db)
    out = _run(clock)
    assert out["decided"] == 0 and out["timing"]["no_fetch"] == 1 and db.rows["picks"] == []


def test_only_this_feed_s_main_numbers_are_read(monkeypatch):
    """The card reads the decision fetch's own rows: an alternate rung, a
    'close' row and another writer's row at a better price are not quotes."""
    clock, db, f, _ = card_world(monkeypatch)
    feed.fetch_team_totals([GID], "open", conn=db)
    stray = dict(next(r for r in db.rows["odds"] if r["bookmaker"] == "fanduel"
                      and r["market"] == "team_totals_home"))
    db.rows["odds"] += [
        {**stray, "bookmaker": "betmgm", "under_price": 150, "over_price": -190, "source": None},
        {**stray, "bookmaker": "betmgm", "under_price": 150, "over_price": -190,
         "snapshot_type": "close"},
        {**stray, "bookmaker": "betmgm", "under_price": 150, "over_price": -190,
         "market": "team_totals_home_alternate"}]
    _run(clock)
    assert db.rows["picks"][0]["decision_book"] == "fanduel"


def test_a_bet_under_the_model_s_ev_floor_is_refused_and_the_game_still_decided(monkeypatch):
    clock, db, f, _ = card_world(monkeypatch)
    monkeypatch.setattr(tt, "uplift", lambda art, season: -0.30)
    feed.fetch_team_totals([GID], "open", conn=db)
    out = _run(clock)
    assert out["published"] == 0 and out["decided"] == 1 and db.rows["picks"] == []
    [d] = db.rows["nba_team_total_luck_decisions"]
    assert d["n_bets"] == 0 and "refused ev_below_floor" in d["detail"]


def test_a_dry_run_creates_no_table_and_writes_nothing(monkeypatch):
    clock, db, f, _ = card_world(monkeypatch)
    feed.fetch_team_totals([GID], "open", conn=db)
    n = len(db.log)
    card.run_card(do_publish=False, now=clock() + timedelta(seconds=30))
    after = [e for e in db.log[n:] if e[0] == "sql"]
    assert not any(s.startswith(("CREATE", "INSERT")) for _, s in after), after
    assert db.rows["picks"] == [] and db.rows["nba_team_total_luck_decisions"] == []


def test_the_card_refuses_a_season_the_artifact_does_not_end_just_before(monkeypatch):
    """RULE: a season the artifact cannot price decides nothing, and the run
    fails loudly: the step exits non-zero, so the job's heartbeat records an
    error and the alerter reports it, instead of a healthy-looking job that
    decides nothing all season. Watched failing when it only logged."""
    clock, db, f, _ = card_world(monkeypatch)
    monkeypatch.setitem(GAMES[GID], "season", 2028)
    feed.fetch_team_totals([GID], "open", conn=db)
    due = card.newest_fetch(db, card.slate(db, clock()), clock() + timedelta(seconds=30))
    assert tt.timing(TIP, due[GID], clock() + timedelta(seconds=30)) == "decide", \
        "the game must be due, or this proves nothing"
    with pytest.raises(RuntimeError, match="Refit it"):
        _run(clock)
    assert db.rows["picks"] == [] and db.rows["nba_team_total_luck_decisions"] == []
    # The pipeline step, as the window job runs it, at the same instant.
    import run_pipeline
    real = card.run_card
    monkeypatch.setattr(card, "run_card", lambda do_publish=False: real(
        do_publish, now=clock() + timedelta(seconds=30)))
    assert run_pipeline.step_nba_team_total_luck() is False


# ── the row: what every surface shows ────────────────────────────────────────

def _bet(**kw) -> tt.TeamTotalBet:
    """A bet as decide() returns it: FanDuel's under 113.5 at -105."""
    base = dict(game_id=GID, season=2027, line=113.5, price=-105.0, book="fanduel",
                home_part=-3.0, gap_total=-3.5, p_fair=0.52, p_push=0.0, ev_fair=0.0,
                uplift=0.1022, p_model=0.6222, fair_ref="pinnacle", fair_mu=113.5,
                fetch_at=TIP - timedelta(minutes=55), dk_price=None,
                link="https://fanduel/under/113.5", dk_link=None)
    base.update(kw)
    return tt.TeamTotalBet(**base)


def test_a_label_that_disagrees_with_its_team_is_refused(monkeypatch):
    """RULE (CLAUDE.md 00, tracking/pick_integrity): a label that names the
    wrong team's total is never written. Discord and push refuse such a row
    and the app would show it, so the card refuses it first. Watched failing
    with the pick_problems check removed."""
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    assert refused == {} and rows[0]["pick_label"] == "BOS @ MIL — MIL Team Total Under 113.5"
    monkeypatch.setattr(card, "pick_label",
                        lambda b, home, away: f"{away} @ {home} — {away} Team Total Under 113.5")
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    assert rows == [] and refused == {GID: "label_mismatch"}


def test_the_card_writes_only_what_every_publisher_shows():
    """RULE (CLAUDE.md 1b: the app, Discord and push show the same picks):
    every publisher keeps a row whose decision_edge clears the model's
    min_edge. A whole-number team total whose EV is just under 0 with the
    push scored as a loss is refused, even with a chance of a push; every row
    written carries decision_edge >= min_edge. Watched failing with the EV
    floor removed."""
    import config
    dec = 1 + 100 / 110
    whole = _bet(line=113.0, price=-110.0, p_push=0.03, p_model=0.99 / dec)   # EV -0.010
    rows, refused = card.pick_rows([whole], GAMES, 1000.0)
    assert rows == [] and refused[GID].startswith("ev_below_floor")
    rows, refused = card.pick_rows([_bet(), _bet(game_id="G2", price=+110.0, p_model=0.49)],
                                   {**GAMES, "G2": GAMES[GID]}, 1000.0)
    assert refused == {} and len(rows) == 2
    floor = config.ACTION_THRESHOLDS[tt.MODEL_ID]["min_edge"]
    assert all(r["decision_edge"] >= floor for r in rows)


@pytest.mark.parametrize("paused", [False, True])
def test_a_paused_model_s_rows_carry_the_paused_marker(monkeypatch, paused):
    """RULE (config.PAUSED_NOTE): a row written while the model is paused says
    so itself, which is what keeps it off every surface; a live row carries no
    marker. The marker reaches the database: publish() writes it. Watched
    failing with the marker dropped from the row."""
    import config
    from models import scorer
    from tests.test_nba_team_total_odds import Clock, FakeDB
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {tt.MODEL_ID} if paused else set())
    rows, _ = card.pick_rows([_bet()], GAMES, 1000.0)
    want = config.PAUSED_NOTE if paused else None
    assert rows[0]["downgrade_reason"] == want
    db = FakeDB(Clock(TIP - timedelta(minutes=54)), tables=(card.DECISIONS_TABLE,))
    d = tt.TeamTotalDecision(GID, _bet().fetch_at, -3.0, -3.5, 1, "bet")
    assert card.publish(db, rows, [d], {GID: 55.0}, {}) == (1, 1)
    assert db.rows["picks"][0]["downgrade_reason"] == want
