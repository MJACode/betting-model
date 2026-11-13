"""The NCAAB in-play rules' registration (config.py, scheduler.py, the
migration list, the committed artifact) and their settlement.

Pinned here:
  * each live rule carries its own thresholds, its own EV floor (its lowest
    passing cut, which the night's cut never goes under) and the graded -200
    floor; it decides on its own probability; it is a committed-artifact rule;
  * only the three passing rules are live: the first-half total and both
    moneylines are in no registry;
  * settlement on the FULL GAME: a spread against the HOME number, a total
    against the live total at the bet;
  * NCAAB live picks post only to #ncaab-live and only while the game is under way;
  * the scheduler runs the loop on the poller service, on by default, off by
    RUN_NCAAB_LIVE=0; the ledger's migration is applied on every pass;
  * the committed artifact loads and is the one the code expects.
"""
from __future__ import annotations

import config
import models.ncaab_live_ig as M


def test_every_rule_carries_its_own_thresholds_floor_and_ev_floor():
    floors = {M.SPREAD_H1: 0.02, M.SPREAD_H2: 0.05, M.TOTAL_H2: 0.02}
    assert set(M.MODEL_IDS) == set(floors)
    for r in M.RULES:
        mid = r.model_id
        assert mid in config.ACTION_THRESHOLDS
        assert mid in config.MODEL_EDGE_THRESHOLDS and mid in config.MODEL_PROB_THRESHOLDS
        assert config.min_odds_for(mid) == -200
        assert config.MODEL_OWN_EV_FLOOR[mid] == floors[mid] == r.floor
        assert config.min_ev_for(mid) == r.floor
        assert mid in config.MODELS_ON_OWN_PROBABILITY
        assert config.scoring_method(mid) == "rule"
        assert mid not in config.PAUSED_MODELS
        from models.ncaab_quote_bounds import EDGE_CAP
        assert EDGE_CAP[mid] == 0.50


def test_only_the_three_passing_rules_are_registered():
    names = set(config.ACTION_THRESHOLDS) | set(config.LIVE_MODELS) | set(config.MODEL_MIN_ODDS)
    names |= set(config.MODEL_OWN_EV_FLOOR) | set(config.MODEL_EDGE_THRESHOLDS) | set(config.SCORING_METHODS)
    assert {n for n in names if n.startswith("ncaab_live_")} == set(M.MODEL_IDS)


def test_each_rule_settles_on_the_full_game_market():
    assert config.LIVE_MODELS[M.SPREAD_H1][:3] == ("NCAAB", "spreads", "engine")
    assert config.LIVE_MODELS[M.SPREAD_H2][:3] == ("NCAAB", "spreads", "engine")
    assert config.LIVE_MODELS[M.TOTAL_H2][:3] == ("NCAAB", "totals", "engine")
    from tracking.paper_tracker import _market_for_pick
    assert [_market_for_pick(m) for m in M.MODEL_IDS] == ["spreads", "spreads", "totals"]


def test_live_picks_post_only_to_the_ncaab_live_channel_while_the_game_is_on():
    assert "NCAAB" in config.DISCORD_LIVE_CHANNEL_REQUIRED
    assert "NCAAB" in config.LIVE_ANNOUNCE_WHILE_IN_PROGRESS


def test_the_labels_pass_the_publishing_guard():
    from tracking.pick_integrity import pick_problems
    r_sp, r_to = M.RULE_BY_ID[M.SPREAD_H2], M.RULE_BY_ID[M.TOTAL_H2]
    lab = M.pick_label(r_sp, "away", -6.5, "Duke", "North Carolina")
    assert lab == "North Carolina +6.5 (live)"
    assert pick_problems(lab, "away", -6.5, M.SPREAD_H2, "Duke", "North Carolina") == []
    lab = M.pick_label(r_to, "under", 150.5, "Duke", "North Carolina")
    assert lab == "North Carolina @ Duke Under 150.5 (live)"
    assert pick_problems(lab, "under", 150.5, M.TOTAL_H2, "Duke", "North Carolina") == []


def test_the_scheduler_runs_the_loop_on_the_poller_service(monkeypatch):
    import importlib
    import scheduler
    monkeypatch.delenv("RUN_NCAAB_LIVE", raising=False)
    importlib.reload(scheduler)
    assert scheduler.RUN_NCAAB_LIVE is True and "ncaab_live" in scheduler._POLLER_JOBS
    monkeypatch.setenv("RUN_NCAAB_LIVE", "0")
    importlib.reload(scheduler)
    assert scheduler.RUN_NCAAB_LIVE is False
    monkeypatch.delenv("RUN_NCAAB_LIVE", raising=False)
    importlib.reload(scheduler)


def test_the_decision_ledger_migration_runs_on_every_pass():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "ncaab_live_decisions_2026_11_07.sql" in ACTIVE_MIGRATIONS
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / "data" / "migrations"
           / "ncaab_live_decisions_2026_11_07.sql").read_text(encoding="utf-8")
    assert "uq_ncaab_live_decisions_one_decision" in sql and "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.ncaab_live_decisions FROM anon" in sql


def test_the_committed_artifact_is_the_one_the_code_expects():
    art = M.load_artifact()
    assert art.raw["kind"] == M.ARTIFACT_KIND and art.raw["season"] == M.SEASON
    assert art.raw["model_ids"] == list(M.MODEL_IDS)
    assert [r["floor"] for r in art.raw["rules"]] == [r.floor for r in M.RULES]
    assert art.margin.S == M.SEASON and art.total.S == M.SEASON
    assert max(art.raw["train_seasons"]) < M.SEASON          # walk-forward
    assert len(art.ev_quantiles) == 1001 and art.per_game > 0


def test_the_app_copy_names_the_loops_own_cadence_and_cap():
    """The app says "twice an hour" and "five bets a night"; if the loop's
    cadence or cap moves, this fails rather than the copy going stale."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "mobile" / "src" / "lib"
    copy = (root / "liveSports.ts").read_text(encoding="utf-8") + (root / "modelMeta.ts").read_text(encoding="utf-8")
    assert M.CADENCE_MIN == 30 and "twice an hour" in copy
    assert M.NIGHT_CAP == 5 and "five bets a night" in copy
