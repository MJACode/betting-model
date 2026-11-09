"""The NBA in-play rules' registration (config.py, scheduler.py, the
migration list) and their settlement.

Pinned here:
  * the live model carries its own thresholds, its own EV floor (0.05, the
    graded cut, which the rule itself reads) and the graded -200 floor (CLAUDE.md
    section 1b; the floor pinned so a DEFAULT_MIN_ODDS override cannot move it);
  * it is in LIVE_MODELS with the market it settles on, decides on its own
    probability (no borrowed calibration map), and is classified as an
    artifact-backed model;
  * only the quarters 1-2 spread is live (mike, 2026-11-04: the backtest is the
    gate): the two quarter-3 rules, which fail the house standard on the loop's
    own fetch times, and the quarter-4 spread, which failed the placebo bar, are
    in no registry and the loop never decides them;
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
    from tracking.paper_tracker import _market_for_pick
    assert [_market_for_pick(m) for m in M.MODEL_IDS] == ["spreads"]


def test_each_rule_decides_on_its_own_probability_and_is_artifact_backed():
    for mid in M.MODEL_IDS:
        assert mid in config.MODELS_ON_OWN_PROBABILITY
        assert config.scoring_method(mid) == config.SCORING_ARTIFACT
        assert mid not in config.PAUSED_MODELS


def _registered_names() -> set:
    names = set(config.ACTION_THRESHOLDS) | set(config.LIVE_MODELS) | set(config.MODEL_MIN_ODDS)
    names |= set(config.MODEL_OWN_EV_FLOOR) | set(config.MODELS_ON_OWN_PROBABILITY)
    names |= set(config.MODEL_EDGE_THRESHOLDS) | set(config.MODEL_PROB_THRESHOLDS)
    names |= set(config.SCORING_METHODS)
    return names


def test_only_the_quarters_1_2_spread_is_live():
    """mike, 2026-11-04: the backtest is the gate. On the loop's own fetch times
    only the quarters 1-2 spread passes the house standard, so it is the only
    rule the loop runs."""
    assert M.MODEL_IDS == (M.SPREAD_Q12,)
    assert {(r.phase, r.market) for r in M.RULES} == {("Q1-Q2", "spreads")}


def test_the_held_out_rules_are_in_no_registry_and_never_decided():
    """The quarter-3 moneyline and spread fail the house standard on the hourly
    fetches; the quarter-4 spread failed the placebo bar (docs/nba_models_2026.md
    7.3). Their code stays (HELD_OUT_RULES) so they are re-graded, and each is
    added the day it passes, not before."""
    names = _registered_names()
    assert not any(n.startswith("nba_live_") and "q4" in n for n in names)
    held = {r.model_id for r in M.HELD_OUT_RULES}
    assert held == {M.ML_Q3, M.SPREAD_Q3}
    assert not held & names
    assert not held & set(M.MODEL_IDS)
    assert {(r.phase, r.market) for r in M.GRADED_RULES} == {("Q1-Q2", "spreads"), ("Q3", "h2h"), ("Q3", "spreads")}
    art = M.load_artifact()
    assert [r["model_id"] for r in art.raw["rules"]] == [M.SPREAD_Q12]       # --register reads this list
    assert sorted(r["model_id"] for r in art.raw["held_out_rules"]) == sorted(held)


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
    assert "WHERE outcome IN ('bet', 'no_bet', 'declined');" in sql
    assert "CHECK (outcome IN ('bet', 'no_bet', 'declined', 'skipped', 'carried'))" in sql
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


def test_nba_live_picks_never_fall_back_to_another_channel(monkeypatch):
    """With no NBA live webhook or channel, an NBA live pick goes nowhere (and
    is not ledgered), never to the shared live channel or the pre-game #nba.
    Other sports keep their fallback."""
    from tracking import discord_notifier as dn
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_CHANNELS_LIVE", {})
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_LIVE", "https://example.invalid/shared-live")
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {"NBA": "https://example.invalid/nba",
                                                     "MLB": "https://example.invalid/mlb"})
    assert dn._live_webhook_for_sport("NBA") is None
    assert dn._live_webhook_for_sport("MLB") == "https://example.invalid/shared-live"
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS_LIVE", {"NBA": "https://example.invalid/nba-live"})
    assert dn._live_webhook_for_sport("NBA") == "https://example.invalid/nba-live"


def test_an_nba_live_pick_is_announced_only_while_its_game_is_in_progress():
    """live_publishable_sql, run: the NBA pick of a game with a final score is
    not announced; an unfinished one is; another sport is unchanged."""
    import sqlite3
    from tracking.publish_filters import live_publishable_sql
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE picks (game_id TEXT, model_id TEXT, sport TEXT, condition_status TEXT,
                            downgrade_reason TEXT);
        CREATE TABLE games (game_id TEXT, home_score REAL);
        CREATE TABLE model_action_thresholds (model_id TEXT, paused BOOLEAN);
        INSERT INTO model_action_thresholds VALUES ('nba_live_spread_q12', 0), ('mlb_live_total_runs', 0);
        INSERT INTO games VALUES ('NBA_done', 110), ('NBA_live', NULL), ('MLB_done', 5);
        INSERT INTO picks VALUES ('NBA_done', 'nba_live_spread_q12', 'NBA', NULL, NULL),
                                 ('NBA_live', 'nba_live_spread_q12', 'NBA', NULL, NULL),
                                 ('MLB_done', 'mlb_live_total_runs', 'MLB', NULL, NULL);
    """)
    sql = "SELECT p.game_id FROM picks p WHERE 1 = 1 " + live_publishable_sql("p").replace(
        "mat_pub.paused = FALSE", "mat_pub.paused = 0")
    got = {r[0] for r in c.execute(sql).fetchall()}
    assert got == {"NBA_live", "MLB_done"}
    # NBA, and NCAAB since 2026-11-07 (its final is written only at the final)
    assert "NBA" in config.LIVE_ANNOUNCE_WHILE_IN_PROGRESS


def test_a_pickem_spread_is_labelled_pk():
    from tracking.pick_integrity import pick_problems
    rule = M.RULE_BY_ID[M.SPREAD_Q3]
    for side in ("home", "away"):
        label = M.pick_label(rule, side, 0.0, "BOS", "NYK")
        assert label == f"{'BOS' if side == 'home' else 'NYK'} PK (live)"
        assert pick_problems(label, side, 0.0, rule.model_id, "BOS", "NYK") == []


def test_the_output_check_reads_a_game_never_looked_at_and_a_silent_window():
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 5, 0, 10, tzinfo=timezone.utc)
    # windows inside tip..tip+100 min: 00:55:36 and 01:55:36 (the 1:50 end stops before 01:55:36)
    assert NH.windows_between(tip, tip + timedelta(minutes=100)) == [
        datetime(2026, 11, 5, 0, 55, 36, tzinfo=timezone.utc)]
    assert NH.games_without_rows(["a", "b"], {"a"}) == ["b"]
    w = datetime(2026, 11, 5, 0, 55, 36, tzinfo=timezone.utc)
    assert NH.windows_without_calls({"a": tip}, {}, []) == [w]
    assert NH.windows_without_calls({"a": tip}, {}, [w + timedelta(seconds=30)]) == []
    # The same window opened before the loop's first tick, so the cutoff drops it.
    # A window after that tick is still missing when nobody called.
    assert NH.windows_without_calls({"a": tip}, {}, [], go_live=NH.GO_LIVE) == []
    later = datetime(2026, 11, 6, 0, 10, tzinfo=timezone.utc)
    later_w = datetime(2026, 11, 6, 0, 55, 36, tzinfo=timezone.utc)
    assert NH.windows_without_calls({"a": later}, {}, [], go_live=NH.GO_LIVE) == [later_w]
    # every live rule (one: the quarters 1-2 spread) decided before the window:
    # no call was needed. Held-out rules are never decided, so they never count.
    done = {"a": [tip + timedelta(minutes=20)] * len(M.RULES)}
    assert len(M.RULES) == 1
    assert NH.windows_without_calls({"a": tip}, done, []) == []


def _nba_live_slate():
    """The three tables `nba_live_health.check` reads, empty."""
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE games (
            game_id TEXT, sport TEXT, game_date TEXT, commence_time TEXT, home_score REAL);
        CREATE TABLE nba_live_decisions (
            game_id TEXT, game_date TEXT, outcome TEXT, decided_at TEXT);
        CREATE TABLE api_call_log (api TEXT, ts TEXT, source TEXT);
    """)
    return c


def _final_nba(c, game_id, game_date, tip):
    c.execute("INSERT INTO games VALUES (?, 'NBA', ?, ?, 110)",
              (game_id, game_date, tip.isoformat()))


def test_go_live_is_the_first_supervisor_tick_after_the_deploy():
    """11:00 America/New_York on 2026-11-05. DST had already ended, so 16:00 UTC.
    The cron does not run from 3am to 11am ET, and the deploy landed inside that gap."""
    from datetime import datetime, timezone
    from tracking import nba_live_health as NH
    assert NH.GO_LIVE == datetime(2026, 11, 5, 16, 0, tzinfo=timezone.utc)
    assert NH.GO_LIVE_LABEL == "2026-11-05 11:00 America/New_York"


def test_a_slate_that_finished_before_go_live_is_not_stale():
    """The morning after go-live, yesterday's finals and their overnight
    fetch windows (00:55Z through 04:55Z) had already ended. No ledger rows
    and no Odds API calls is expected. It must not read STALE."""
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    c = _nba_live_slate()
    for hour in range(5):
        tip = datetime(2026, 11, 5, hour, 10, tzinfo=timezone.utc)
        assert tip + timedelta(minutes=100) < NH.GO_LIVE
        windows = NH.windows_between(tip, tip + timedelta(minutes=100))
        assert windows and all(w < NH.GO_LIVE for w in windows)
        _final_nba(c, f"NBA_2026-11-04_{hour}", "2026-11-04", tip)
    status, detail = NH.check(c, "2026-11-04")
    assert status == "skipped"
    assert "go-live" in detail and "not scored" in detail
    assert "nba_live_decisions" not in detail
    assert "00:55:36Z" not in detail and "04:55:36Z" not in detail


def test_a_window_opened_before_go_live_is_not_stale_when_the_game_was_looked_at():
    """A game whose span reaches go-live can have its only fetch window open
    earlier. That window is not a missed call. A row means the game was seen."""
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)
    end = tip + timedelta(minutes=NH.DECISION_SPAN_MIN)
    assert end >= NH.GO_LIVE
    windows = NH.windows_between(tip, end)
    assert windows and all(w < NH.GO_LIVE for w in windows)
    c = _nba_live_slate()
    _final_nba(c, "NBA_2026-11-05_EARLY", "2026-11-05", tip)
    c.execute("INSERT INTO nba_live_decisions VALUES (?, ?, 'skipped', ?)",
              ("NBA_2026-11-05_EARLY", "2026-11-05", tip.isoformat()))
    status, detail = NH.check(c, "2026-11-05")
    assert status == "ok"
    assert "15:55:36Z" not in detail


def test_a_game_still_in_span_at_go_live_with_no_row_is_stale():
    """The span reached the first tick, so a missing row is still an outage.
    The fetch window that opened before that tick is not part of the reason."""
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)
    assert tip + timedelta(minutes=NH.DECISION_SPAN_MIN) >= NH.GO_LIVE
    c = _nba_live_slate()
    _final_nba(c, "NBA_2026-11-05_EARLY", "2026-11-05", tip)
    status, detail = NH.check(c, "2026-11-05")
    assert status == "stale"
    assert "NBA_2026-11-05_EARLY" in detail
    assert "15:55:36Z" not in detail


def test_a_post_go_live_slate_missing_a_row_and_a_call_is_stale():
    """The first live night, and every night after: a final with no ledger row
    and a fetch window with no nba-live call still reads STALE."""
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 6, 0, 10, tzinfo=timezone.utc)  # 19:10 ET, Nov 5
    assert tip + timedelta(minutes=100) > NH.GO_LIVE
    windows = NH.windows_between(tip, tip + timedelta(minutes=100))
    assert len(windows) == 1 and windows[0] >= NH.GO_LIVE
    c = _nba_live_slate()
    _final_nba(c, "NBA_2026-11-05_BOS_NYK", "2026-11-05", tip)
    status, detail = NH.check(c, "2026-11-05")
    assert status == "stale"
    assert "NBA_2026-11-05_BOS_NYK" in detail
    assert "nba_live_decisions" in detail
    assert "nba-live" in detail
    assert windows[0].strftime("%H:%M:%SZ") in detail


def test_a_post_go_live_window_with_no_call_is_stale_even_when_the_row_exists():
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 6, 0, 10, tzinfo=timezone.utc)
    windows = NH.windows_between(tip, tip + timedelta(minutes=100))
    assert windows and windows[0] >= NH.GO_LIVE
    c = _nba_live_slate()
    gid = "NBA_2026-11-05_BOS_NYK"
    _final_nba(c, gid, "2026-11-05", tip)
    c.execute("INSERT INTO nba_live_decisions VALUES (?, ?, 'skipped', ?)",
              (gid, "2026-11-05", tip.isoformat()))
    status, detail = NH.check(c, "2026-11-05")
    assert status == "stale"
    assert "nba-live" in detail
    assert windows[0].strftime("%H:%M:%SZ") in detail
    assert gid not in detail


def test_a_covered_slate_with_its_row_and_its_call_is_ok():
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    tip = datetime(2026, 11, 6, 0, 10, tzinfo=timezone.utc)
    window = NH.windows_between(tip, tip + timedelta(minutes=100))[0]
    c = _nba_live_slate()
    gid = "NBA_2026-11-05_BOS_NYK"
    _final_nba(c, gid, "2026-11-05", tip)
    c.execute("INSERT INTO nba_live_decisions VALUES (?, ?, 'bet', ?)",
              (gid, "2026-11-05", (tip + timedelta(minutes=50)).isoformat()))
    c.execute("INSERT INTO api_call_log VALUES (?, ?, ?)",
              (NH.ODDS_API, window.isoformat(), NH.LOOP_SOURCE))
    status, detail = NH.check(c, "2026-11-05")
    assert status == "ok"
    assert "each with a row" in detail
    assert "not scored" not in detail


def test_an_earlier_final_does_not_hide_or_excuse_a_covered_miss():
    """One game finished before go-live, one did not. Only the later game,
    with no row and no call, is the outage."""
    from datetime import datetime, timedelta, timezone
    from tracking import nba_live_health as NH
    early = datetime(2026, 11, 5, 2, 10, tzinfo=timezone.utc)
    late = datetime(2026, 11, 6, 0, 10, tzinfo=timezone.utc)
    assert early + timedelta(minutes=100) < NH.GO_LIVE
    assert late > NH.GO_LIVE
    c = _nba_live_slate()
    _final_nba(c, "NBA_2026-11-05_EARLY", "2026-11-05", early)
    _final_nba(c, "NBA_2026-11-05_LATE", "2026-11-05", late)
    status, detail = NH.check(c, "2026-11-05")
    assert status == "stale"
    assert "NBA_2026-11-05_LATE" in detail
    assert "NBA_2026-11-05_EARLY" not in detail
    assert "1 of 1" in detail
    assert "1 earlier" in detail


def test_the_output_check_runs_in_system_health():
    src = (config.ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert '"nba_live_outputs"' in src and "nba_live_health import check" in src


def test_the_loop_settings_are_documented_for_the_worker():
    doc = (config.ROOT / "docs" / "cloud_worker.md").read_text(encoding="utf-8")
    for name in ("RUN_NBA_LIVE", "NBA_LIVE_PBP_WAIT_SEC", "NBA_LIVE_PBP_RECHECK_SEC", "NBA_LIVE_FETCH_OFFSET_SEC",
                 "NBA_LIVE_FETCH_WINDOW_SEC", "NBA_LIVE_RETRY_GAP_SEC", "NBA_LIVE_PLAY_LAG_MAX_SEC",
                 "NBA_LIVE_HEADER_RECHECK_SEC", "NBA_LIVE_CALL_CAP", "NBA_LIVE_CREDIT_CAP",
                 "DISCORD_CHANNEL_LIVE_NBA", "DISCORD_WEBHOOK_LIVE_NBA"):
        assert name in doc, name
