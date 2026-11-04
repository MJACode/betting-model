"""The NBA in-play rules' registration (config.py, scheduler.py, the
migration list) and their settlement.

Pinned here:
  * every model carries its own thresholds, its own EV floor (0.05, the graded
    cut, which the rule itself reads) and the graded -200 floor (CLAUDE.md
    section 1b; the floor pinned so a DEFAULT_MIN_ODDS override cannot move it);
  * each is in LIVE_MODELS with the market it settles on, decides on its own
    probability (no borrowed calibration map), and is classified as an
    artifact-backed model;
  * the quarter-4 spread, which failed the placebo bar, is NOT registered;
  * settlement: a spread against the HOME number (CLAUDE.md section 4), a
    moneyline on home_win with overtime counted;
  * the scheduler runs the loop on the poller service, on by default, off by
    RUN_NBA_LIVE=0, and a loop that dies fails its job;
  * the decision ledger's migration is applied on every pass.
"""

from __future__ import annotations

import config
import models.nba_live_ig2 as M


def test_every_rule_carries_its_own_thresholds_floor_and_ev_floor():
    for mid in M.MODEL_IDS:
        assert mid in config.ACTION_THRESHOLDS
        assert mid in config.MODEL_EDGE_THRESHOLDS and mid in config.MODEL_PROB_THRESHOLDS
        assert config.MODEL_MIN_ODDS[mid] == -200
        assert config.MODEL_OWN_EV_FLOOR[mid] == 0.05
        assert config.min_ev_for(mid) == 0.05 and config.min_odds_for(mid) == -200
        assert mid not in config.MODEL_MIN_EV                    # MODEL_OWN_EV_FLOOR is returned outright
        assert M.rule_cut(mid) == 0.05 and M.rule_floor(mid) == -200


def test_each_rule_settles_on_its_own_market():
    assert config.LIVE_MODELS[M.SPREAD_Q12][:3] == ("NBA", "spreads", "engine")
    assert config.LIVE_MODELS[M.ML_Q3][:3] == ("NBA", "h2h", "engine")
    assert config.LIVE_MODELS[M.SPREAD_Q3][:3] == ("NBA", "spreads", "engine")
    from tracking.paper_tracker import _market_for_pick
    assert [_market_for_pick(m) for m in M.MODEL_IDS] == ["spreads", "h2h", "spreads"]


def test_each_rule_decides_on_its_own_probability_and_is_artifact_backed():
    for mid in M.MODEL_IDS:
        assert mid in config.MODELS_ON_OWN_PROBABILITY
        assert config.scoring_method(mid) == config.SCORING_ARTIFACT
        assert mid not in config.PAUSED_MODELS


def test_the_quarter_4_spread_is_not_registered():
    """It failed the placebo bar (docs/nba_models_2026.md 7.3); it is added the
    day it passes on the live record, not before."""
    names = set(config.ACTION_THRESHOLDS) | set(config.LIVE_MODELS)
    assert not any(n.startswith("nba_live_") and "q4" in n for n in names)
    assert {r.phase for r in M.RULES} == {"Q1-Q2", "Q3"}
    assert {(r.phase, r.market) for r in M.RULES} == {("Q1-Q2", "spreads"), ("Q3", "h2h"), ("Q3", "spreads")}


def test_a_spread_settles_against_the_home_number():
    """scored_line -2.5 is BOS -2.5. BOS by 2: the home side loses, the away
    side (NYK +2.5) wins; BOS by 3: the reverse."""
    from tracking.paper_tracker import _compute_result
    assert _compute_result("away", "spreads", 102, 100, 1, None, 0, 100.0, -2.5, None, 1.0)[0] == "WIN"
    assert _compute_result("home", "spreads", 102, 100, 1, None, 0, 100.0, -2.5, None, 1.0)[0] == "LOSS"
    assert _compute_result("home", "spreads", 103, 100, 1, None, 0, 100.0, -2.5, None, 1.0)[0] == "WIN"
    assert _compute_result("away", "spreads", 103, 100, 1, None, 0, -110.0, -3.0, None, 1.0)[0] == "PUSH"


def test_a_moneyline_counts_overtime():
    """home_win is the full game, overtime included (all five 2026-27 NBA
    overtime games carry it, read 2026-11-04)."""
    from tracking.paper_tracker import _compute_result
    assert _compute_result("away", "h2h", 118, 121, 0, None, 1, 210.0, None, None, 1.0)[0] == "WIN"
    assert _compute_result("home", "h2h", 118, 121, 0, None, 1, -150.0, None, None, 1.0)[0] == "LOSS"


def test_the_scheduler_runs_the_loop_on_the_poller(monkeypatch):
    import importlib

    import scheduler
    monkeypatch.delenv("RUN_NBA_LIVE", raising=False)
    importlib.reload(scheduler)
    assert scheduler.RUN_NBA_LIVE is True
    assert "nba_live" in scheduler._POLLER_JOBS
    src = (config.ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert '[sys.executable, "-m", "models.nba_live_loop"]' in src
    from tracking.job_heartbeat import MAX_SILENCE
    assert MAX_SILENCE["nba_live"] >= 480            # clears the 3am-11am gap


def test_the_scheduler_flag_turns_it_off(monkeypatch):
    import importlib

    import scheduler
    for off in ("0", "false", " off ", "NO"):
        monkeypatch.setenv("RUN_NBA_LIVE", off)
        importlib.reload(scheduler)
        assert scheduler.RUN_NBA_LIVE is False, off
    monkeypatch.delenv("RUN_NBA_LIVE")
    importlib.reload(scheduler)
    assert scheduler.RUN_NBA_LIVE is True


def test_a_loop_that_dies_fails_its_job(monkeypatch):
    import pytest

    import scheduler
    for outcome in ("fail", "timeout", "error"):
        monkeypatch.setattr(scheduler, "_run", lambda *a, **k: outcome)
        with pytest.raises(RuntimeError):
            scheduler.run_nba_live()
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: "ok")
    scheduler.run_nba_live()


def test_the_job_is_registered_with_its_cron(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh
    for fn in ("seed", "beat", "mark_disabled"):
        monkeypatch.setattr(jh, fn, lambda *a, **k: None)
    sched = scheduler.build_scheduler()
    jobs = {j.id: j for j in sched.get_jobs()}
    job = jobs["nba_live"]
    assert job.max_instances == 1
    trig = str(job.trigger)
    assert "hour='0-2,11-23'" in trig and "minute='*/10'" in trig, trig


def test_the_decision_ledger_is_created_on_every_pass():
    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR
    name = "nba_live_decisions_2026_11_04.sql"
    assert name in ACTIVE_MIGRATIONS
    sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.nba_live_decisions FROM anon" in sql
    assert "REVOKE ALL ON public.nba_live_decisions FROM authenticated" in sql
    assert "PRIMARY KEY (game_id, model_id)" in sql
    assert sql.strip().startswith("--") and sql.count("DO $mig$") == 1      # one statement


def test_the_live_fetch_names_pinnacle_and_stays_inside_one_region():
    from data.ingestors.nba_live_feed import MARKETS, feed_books
    books = feed_books()
    assert "pinnacle" in books and set(config.BEST_LINE_BOOKMAKERS) <= set(books)
    assert len(books) <= 10 and MARKETS == ("h2h", "spreads")


def test_a_live_pull_stores_an_nba_row_stamped_after_the_tip_as_in_play(monkeypatch):
    """The refresh pass and the pre-game poller keep receiving a game once it
    is under way. A row stamped after the listed tip is a live price and is
    stored 'in_play', never 'open'; a row stamped before stays 'open'."""
    from data.ingestors import odds_ingestor as oi
    from tests import _nba_live_synth as S
    from datetime import timedelta
    before = S.book("draftkings", S.TIP - timedelta(minutes=5), h2h=(-150, 130), spread=(-3.5, -110, -110))
    after = S.book("fanduel", S.TIP + timedelta(minutes=20), h2h=(-300, 240), spread=(-7.5, -110, -110))
    monkeypatch.setattr(oi, "_get_odds", lambda key, markets: S.events([before, after]))
    monkeypatch.setattr(oi, "_upsert_games", lambda conn, rows: len(rows))

    class C:
        def commit(self):
            pass

        def close(self):
            pass
    monkeypatch.setattr(oi, "get_connection", lambda: C())
    rows = oi.fetch_pregame_rows(["NBA"])
    labels = {(r["bookmaker"], r["market"]): r["snapshot_type"] for r in rows}
    assert labels[("draftkings", "h2h")] == "open" and labels[("draftkings", "spreads")] == "open"
    assert labels[("fanduel", "h2h")] == "in_play" and labels[("fanduel", "spreads")] == "in_play"
    assert "NBA" in oi.LIVE_PULL_IN_PLAY_SPORTS
