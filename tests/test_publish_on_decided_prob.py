"""Every publisher and the app filter on the numbers the scorer DECIDED on.

models.scorer._decide decides on the calibrated probability (the promoted map,
DECIDE_ON_CALIBRATED_PROB) and on that number minus the implied probability of
the deciding price, but STORES the raw pair. Discord, push, the health check,
the free pick and the app filtered on the raw pair, so a BET the map lifted
over the cut was written and shown nowhere: 18 NHL underdog BETs between
2026-09-22 and 10-02 (docs/followups.md). config.decided_cut_sql is the one
definition now; these tests pin

  * a row with a raw number under the cut and a calibrated one over it passes
    every publisher and the app;
  * a raw-only row (no calibrated number) and a raw-deciding model behave
    exactly as before;
  * with DECIDE_ON_CALIBRATED_PROB off everything is filtered raw again;
  * the cut agrees with _decide itself on the motivating pick (3094775).
"""
from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

import config
from tracking import discord_notifier as dn
from tracking import push_notifier as pn
from tracking import system_health as sh

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS_TS = (ROOT / "mobile" / "src" / "lib" / "thresholds.ts").read_text(encoding="utf-8")
GENERATED_TS = (ROOT / "mobile" / "src" / "lib" / "thresholds.generated.ts").read_text(encoding="utf-8")

# Pick 3094775, NYR (Regulation) at +180, as stored 2026-10-01.
NYR = dict(model_id="nhl_moneyline_regulation", model_probability=0.3801,
           model_probability_cal=0.443, edge=-0.0045, decision_edge=0.023,
           decision_implied_prob=0.3571, dk_implied_prob=0.3846)
NHL_REG_CUT = dict(min_prob=0.40, min_edge=0.05, prob_only=0)


def _passes(row: dict, cut: dict) -> bool:
    """Evaluate config.decided_cut_sql over one row in SQLite."""
    db = sqlite3.connect(":memory:")
    cols = ["model_id", "model_probability", "model_probability_cal", "edge",
            "decision_edge", "decision_implied_prob", "dk_implied_prob"]
    db.execute(f"CREATE TABLE p ({', '.join(cols)})")
    db.execute("CREATE TABLE t (min_prob, min_edge, prob_only)")
    db.execute(f"INSERT INTO p VALUES ({', '.join('?' for _ in cols)})",
               [row.get(c) for c in cols])
    db.execute("INSERT INTO t VALUES (?, ?, ?)",
               (cut["min_prob"], cut["min_edge"], cut["prob_only"]))
    sql = config.decided_cut_sql("p", "t").replace("prob_only = TRUE", "prob_only = 1")
    return bool(db.execute(f"SELECT {sql} FROM p, t").fetchone()[0])


class _Conn:
    def __init__(self):
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None


def _sql(producer, *args):
    conn = _Conn()
    producer(conn, "2026-10-02", *args)
    return conn.sql


# ── the expression ───────────────────────────────────────────────────────────

def test_the_motivating_pick_fails_raw_and_passes_on_the_decided_numbers():
    raw_ok = (NYR["model_probability"] >= NHL_REG_CUT["min_prob"]
              and NYR["decision_edge"] >= NHL_REG_CUT["min_edge"])
    assert not raw_ok
    assert _passes(NYR, NHL_REG_CUT)


def test_the_cut_agrees_with_the_scorers_own_decision(monkeypatch):
    """_decide on the same inputs: BET. The publishers' cut has to say yes too."""
    from models import scorer
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(scorer, "_calibrated", lambda m, p: 0.443)
    monkeypatch.setattr(scorer, "_paused_signal", lambda m, s: (s, None))
    sig = scorer._decide("nhl_moneyline_regulation", 0.3801, 0.3571,
                         0.3801 - 0.3571, 180.0, is_prop=False)
    assert sig == "BET"
    assert _passes(NYR, NHL_REG_CUT)


def test_a_row_with_no_calibrated_number_is_cut_exactly_as_before():
    row = dict(NYR, model_probability_cal=None)
    assert not _passes(row, NHL_REG_CUT)
    ok = dict(row, model_probability=0.46, decision_edge=0.0864)
    assert _passes(ok, NHL_REG_CUT)


def test_a_calibration_that_lowers_the_number_now_cuts_on_the_lower_one():
    """Symmetric: a favourite the map pulls under the cut was never a BET
    (the scorer decided on the lower number), so it does not publish."""
    row = dict(model_id="nhl_moneyline", model_probability=0.60,
               model_probability_cal=0.535, edge=0.10, decision_edge=0.10,
               decision_implied_prob=0.50, dk_implied_prob=0.50)
    assert not _passes(row, dict(min_prob=0.55, min_edge=0.05, prob_only=0))


def test_no_price_falls_back_to_the_stored_edge():
    row = dict(NYR, decision_implied_prob=None, dk_implied_prob=None,
               decision_edge=None, edge=0.06)
    assert _passes(row, NHL_REG_CUT)


def test_prob_only_models_skip_the_edge():
    row = dict(NYR, decision_implied_prob=0.60)
    assert _passes(row, dict(NHL_REG_CUT, prob_only=1))


@pytest.mark.parametrize("model_id", sorted(config.decides_on_raw_models()))
def test_raw_deciding_models_keep_the_raw_cut(model_id):
    """Rule cards (selection IS the bet), engines and MODELS_ON_OWN_PROBABILITY
    decide on their own number; their stored calibrated one must not move them."""
    row = dict(NYR, model_id=model_id)
    assert not _passes(row, NHL_REG_CUT)
    assert not config.decides_on_calibrated(model_id)


def test_the_raw_deciders_are_exactly_the_scorers():
    own = config.decides_on_raw_models()
    assert set(config.MODELS_ON_OWN_PROBABILITY) <= own
    for m in config.SCORING_METHODS:
        expect_raw = (m in config.MODELS_ON_OWN_PROBABILITY
                      or (config.scoring_method(m) != config.SCORING_ARTIFACT
                          and m not in config.NON_ARTIFACT_DECISION_SOURCE))
        assert (m in own) == expect_raw, m
    assert "nhl_moneyline" not in own and "nhl_moneyline_regulation" not in own


def test_flag_off_falls_back_to_raw(monkeypatch):
    """Off: every artifact model decides raw again (scorer._decide reads the
    flag). The NCAAF live engine does not read it (decide_honest), so it
    stays calibrated -- see test_ncaaf_live_decides_calibrated_at_dk."""
    monkeypatch.setattr(config, "DECIDE_ON_CALIBRATED_PROB", False)
    assert "ELSE p.model_probability END" in config.decided_prob_sql("p")
    assert config.decided_edge_sql("p").endswith("ELSE COALESCE(p.decision_edge, p.edge) END)")
    assert not _passes(NYR, NHL_REG_CUT)
    assert not config.decides_on_calibrated("nhl_moneyline_regulation")
    assert config.decided_numbers(NYR) == (0.3801, 0.023)
    assert config.decides_on_calibrated("ncaaf_live_win_prob")
    # And every publisher's SQL cuts NHL on the raw number again.
    for sql in (_sql(dn._new_signals), _sql(pn._new_bet_signals)):
        assert config.publishable_cut_sql("p", "t") in sql
        assert "ELSE p.model_probability END" in sql


def test_python_twin_matches_the_sql():
    rows = [NYR, dict(NYR, model_probability_cal=None),
            dict(NYR, decision_implied_prob=None),
            dict(NYR, decision_implied_prob=None, dk_implied_prob=None),
            dict(NYR, model_id="wnba_prop_market")]
    for r in rows:
        p, e = config.decided_numbers(r)
        py = p >= NHL_REG_CUT["min_prob"] and e >= NHL_REG_CUT["min_edge"]
        assert py == _passes(r, NHL_REG_CUT), r


# ── every publisher uses it ──────────────────────────────────────────────────

CUT = config.publishable_cut_sql("p", "t")


@pytest.mark.parametrize("producer", [dn._new_signals, dn._locked_signals,
                                      pn._new_bet_signals])
def test_every_pre_game_publisher_applies_the_decided_cut(producer):
    sql = _sql(producer)
    assert CUT in sql
    assert config.decided_cut_sql("p", "t") in sql
    assert "AND p.model_probability >= t.min_prob" not in sql


def test_the_stale_pause_probe_applies_the_decided_cut():
    src = inspect.getsource(dn._log_stale_pause_hiding_bets)
    assert 'config.publishable_cut_sql("p", "t")' in src
    assert "p.model_probability >= t.min_prob" not in src


def test_signal_delivery_applies_the_decided_cut():
    """Else the health check alarms on rows Discord correctly withholds, or
    stays green while Discord withholds a BET."""
    src = inspect.getsource(sh.run_system_health)
    assert 'AND {config.decided_cut_sql("p", "t")}' in src
    assert 'AND {config.price_gap_ok_sql("p")}' in src
    # The 24h window in Python: commence_time is TEXT in mixed shapes there.
    assert "config.decided_only_window_open(" in src
    assert 'CASE WHEN {config.raw_cut_sql("p", "t")} THEN 1 ELSE 0 END AS raw_ok' in src
    assert "AND p.model_probability >= t.min_prob" not in src


def test_the_python_window_twin_matches_the_sql_window():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 2, 20, 5, tzinfo=timezone.utc)      # 4:05 PM ET
    at = lambda s: datetime.fromisoformat(s)
    fresh = at("2026-10-02T20:00:00+00:00")
    assert config.decided_only_window_open(at("2026-10-02T22:40:00+00:00"), None, fresh, now)
    assert config.decided_only_window_open(at("2026-10-03T08:00:00+00:00"), None, fresh, now)
    assert not config.decided_only_window_open(at("2026-10-03T23:10:00+00:00"), None, fresh, now)
    assert config.decided_only_window_open(None, "2026-10-03", fresh, now)
    assert not config.decided_only_window_open(None, "2026-10-04", fresh, now)
    assert not config.decided_only_window_open(None, None, fresh, now)
    # The price-age half (PUBLISH_MAX_PRICE_AGE_HOURS against the start).
    tonight = at("2026-10-02T22:40:00+00:00")
    assert not config.decided_only_window_open(
        tonight, None, at("2026-10-01T11:24:56+00:00"), now)          # 3094775 as stored
    assert config.decided_only_window_open(tonight, None, at("2026-10-02T11:00:00+00:00"), now)
    assert not config.decided_only_window_open(tonight, None, at("2026-10-02T10:30:00+00:00"), now)
    assert not config.decided_only_window_open(tonight, None, None, now)
    assert not config.decided_only_window_open(None, "2026-10-02", at("2026-10-02T07:00:00+00:00"), now)


def test_the_free_pick_cuts_on_the_pick_of_records_decided_numbers():
    sql = _sql(dn._free_pick_candidates)
    assert config.decided_prob_sql("p") + " AS decided_prob" in sql
    assert config.decided_edge_sql("p") + " AS decided_edge" in sql
    assert "COALESCE(pk.decided_prob, os.model_probability) >= t.min_prob" in sql
    assert "COALESCE(pk.decided_edge, os.edge) >= COALESCE(t.min_edge, 0)" in sql
    assert "AND os.model_probability >= t.min_prob" not in sql
    # ...and the same two publish-time guards, off the same pick.
    assert config.price_gap_ok_sql("p") in sql
    assert config.decided_only_window_sql("p", "t", "g.commence_time") in sql
    assert "AND COALESCE(pk.publish_ok, TRUE)" in sql


def test_the_prompt_sql_emitter_uses_the_decided_numbers():
    from scripts.emit_threshold_sql import emit
    out = emit(prefix="p.")
    reg = [ln for ln in out.splitlines() if "'nhl_moneyline_regulation'" in ln][0]
    assert "COALESCE(p.model_probability_cal, p.model_probability) >= 0.4" in reg
    assert "NULLIF(p.decision_implied_prob, 0)" in reg
    wind = [ln for ln in out.splitlines() if "'nfl_wind_totals'" in ln][0]
    assert "model_probability_cal" not in wind


# ── the app ──────────────────────────────────────────────────────────────────

def test_the_app_filter_reads_the_decided_numbers():
    body = THRESHOLDS_TS[THRESHOLDS_TS.index("export function passesActionFilter"):]
    body = body[:body.index("\n}\n")]
    assert "const { prob, edge } = decidedNumbers(p);" in body
    assert "if (prob < sv.min_prob) return false;" in body
    assert "if (prob < t.min_prob) return false;" in body
    assert "p.model_probability <" not in body


def test_the_app_helper_mirrors_the_sql():
    helper = THRESHOLDS_TS[THRESHOLDS_TS.index("export function decidedNumbers"):]
    helper = helper[:helper.index("\n}\n")]
    assert "src === 'raw' || cal == null" in helper
    assert "src === 'calibrated_at_dk' ? dk : (impliedOrNull(p.decision_implied_prob) ?? dk)" in helper
    assert "edge: prob - implied" in helper
    assert "n === 0 || Number.isNaN(n) ? null : n" in THRESHOLDS_TS
    src = THRESHOLDS_TS[THRESHOLDS_TS.index("export function decisionSource"):]
    src = src[:src.index("\n}\n")]
    assert "DECIDES_CALIBRATED_AT_DK_MODELS.has(modelId)" in src
    assert "!DECIDE_ON_CALIBRATED_PROB || DECIDES_ON_RAW_MODELS.has(modelId)" in src


def test_the_app_applies_both_publish_guards():
    body = THRESHOLDS_TS[THRESHOLDS_TS.index("export function passesActionFilter"):]
    body = body[:body.index("\n}\n")]
    assert body.count("return publishGuardsPass(p, {") == 2
    g = THRESHOLDS_TS[THRESHOLDS_TS.index("export function publishGuardsPass"):]
    g = g[:g.index("\n}\n")]
    assert "if (p.is_live || isLiveModel(p.model_id)) return true;" in g
    assert "Math.abs(dec - dk) > PUBLISH_MAX_PRICE_GAP" in g
    assert "DECIDED_ONLY_PUBLISH_WITHIN_HOURS * 3600_000" in g
    assert "PUBLISH_MAX_PRICE_AGE_HOURS * 3600_000" in g
    assert "priced >= start - maxAgeMs" in g and "priced >= nowMs - maxAgeMs" in g
    assert "if (Number.isNaN(priced)) return false;" in g


def test_custom_models_compare_the_decided_numbers():
    src = (ROOT / "mobile" / "src" / "lib" / "customModelFilters.ts").read_text(encoding="utf-8")
    body = src[src.index("export function pickMatchesModel"):]
    body = body[:body.index("\n}\n")]
    assert "const { prob, edge } = decidedNumbers(pick);" in body
    assert "prob < r.min_prob" in body and "edge < r.min_edge" in body
    assert "pick.model_probability <" not in body


def _generated_set(name: str) -> set:
    block = GENERATED_TS[GENERATED_TS.index(f"export const {name}"):]
    block = block[:block.index("]);")]
    return {ln.strip().strip("',") for ln in block.splitlines()[1:] if ln.strip()}


def test_the_generated_raw_decider_list_is_configs():
    assert _generated_set("DECIDES_ON_RAW_MODELS") == set(config.decides_on_raw_models())
    assert (_generated_set("DECIDES_CALIBRATED_AT_DK_MODELS")
            == set(config.decides_calibrated_at_dk_models()))
    flag = "true" if config.DECIDE_ON_CALIBRATED_PROB else "false"
    assert f"export const DECIDE_ON_CALIBRATED_PROB = {flag};" in GENERATED_TS
    assert f"export const PUBLISH_MAX_PRICE_GAP = {config.PUBLISH_MAX_PRICE_GAP:g};" in GENERATED_TS
    assert (f"export const DECIDED_ONLY_PUBLISH_WITHIN_HOURS = "
            f"{int(config.DECIDED_ONLY_PUBLISH_WITHIN_HOURS)};") in GENERATED_TS
    assert (f"export const PUBLISH_MAX_PRICE_AGE_HOURS = "
            f"{int(config.PUBLISH_MAX_PRICE_AGE_HOURS)};") in GENERATED_TS


def test_the_app_query_fetches_the_columns_the_helper_reads():
    q = (ROOT / "mobile" / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    cols = q[q.index("const PICK_COLUMNS"):q.index("const SETTLED_PICK_COLUMNS")]
    for c in ("model_probability_cal", "decision_implied_prob", "dk_implied_prob",
              "decision_edge", "game_time", "game_date", "is_live", "created_at"):
        assert c in cols, c


# ── the publish-time guards (reviewer, 2026-10-02) ───────────────────────────

FRESH = "2026-10-02T20:00:00+00:00"          # priced 5 minutes before NOW below


def _publishable(row: dict, cut: dict, *, start: str | None, horizon: str,
                 tomorrow: str = "2026-10-03",
                 now: str = "2026-10-02T20:05:00+00:00") -> bool:
    """Evaluate config.publishable_cut_sql over one row in SQLite.

    NOW()/INTERVAL/to_char/::timestamptz are Postgres; they are swapped for the
    literal horizon (now + 24h, ISO), tomorrow's ET date the clause computes,
    and julianday() arithmetic for the price-age bound. A row with no
    created_at given is priced at FRESH."""
    db = sqlite3.connect(":memory:")
    cols = ["model_id", "model_probability", "model_probability_cal", "edge",
            "decision_edge", "decision_implied_prob", "dk_implied_prob",
            "is_live", "game_date", "created_at"]
    db.execute(f"CREATE TABLE p ({', '.join(cols)})")
    db.execute("CREATE TABLE t (min_prob, min_edge, prob_only)")
    db.execute("CREATE TABLE g (commence_time)")
    row = {"is_live": 0, "game_date": "2026-10-03", "created_at": FRESH, **row}
    db.execute(f"INSERT INTO p VALUES ({', '.join('?' for _ in cols)})",
               [row.get(c) for c in cols])
    db.execute("INSERT INTO t VALUES (?, ?, ?)",
               (cut["min_prob"], cut["min_edge"], cut["prob_only"]))
    db.execute("INSERT INTO g VALUES (?)", (start,))
    h = int(config.DECIDED_ONLY_PUBLISH_WITHIN_HOURS)
    a = int(config.PUBLISH_MAX_PRICE_AGE_HOURS)
    sql = (config.publishable_cut_sql("p", "t")
           .replace("prob_only = TRUE", "prob_only = 1")
           .replace("p.is_live = FALSE", "p.is_live = 0")
           .replace(f"g.commence_time::timestamptz <= NOW() + INTERVAL '{h} hours'",
                    f"g.commence_time <= '{horizon}'")
           .replace("to_char((NOW() AT TIME ZONE 'America/New_York')::date + 1, 'YYYY-MM-DD')",
                    f"'{tomorrow}'")
           .replace(f"p.created_at::timestamptz >= g.commence_time::timestamptz - INTERVAL '{a} hours'",
                    f"julianday(p.created_at) >= julianday(g.commence_time) - {a}/24.0")
           .replace(f"p.created_at::timestamptz >= NOW() - INTERVAL '{a} hours'",
                    f"julianday(p.created_at) >= julianday('{now}') - {a}/24.0"))
    assert "NOW()" not in sql and "::timestamptz" not in sql
    return bool(db.execute(f"SELECT {sql} FROM p, t, g").fetchone()[0])


NOW_PLUS_24 = "2026-10-03T20:05:00+00:00"   # 2026-10-02 4:05 PM ET + 24h


def test_a_decided_only_pick_waits_until_its_game_is_within_24h():
    tonight = "2026-10-02T22:40:00+00:00"    # 3094775, 6:40 PM ET
    assert _publishable(NYR, NHL_REG_CUT, start=tonight, horizon=NOW_PLUS_24)
    in_three_days = "2026-10-05T00:10:00+00:00"
    assert not _publishable(NYR, NHL_REG_CUT, start=in_three_days, horizon=NOW_PLUS_24)
    # Unknown start: held to game_date <= tomorrow (ET).
    assert _publishable(dict(NYR, game_date="2026-10-03"), NHL_REG_CUT, start=None,
                        horizon=NOW_PLUS_24)
    assert not _publishable(dict(NYR, game_date="2026-10-05"), NHL_REG_CUT, start=None,
                            horizon=NOW_PLUS_24)


def test_a_pick_that_passes_raw_keeps_todays_behaviour():
    raw_ok = dict(NYR, model_probability=0.46, decision_edge=0.0864)
    assert _publishable(raw_ok, NHL_REG_CUT, start="2026-10-07T23:40:00+00:00",
                        horizon=NOW_PLUS_24)


def test_the_price_gap_guard_refuses_a_stale_or_wrong_side_quote():
    """3101240 FLA ML: decided at BetMGM +154 against DK -125, 16.2pp apart."""
    fla = dict(model_id="nhl_moneyline", model_probability=0.4998,
               model_probability_cal=0.5644, edge=-0.0558, decision_edge=0.1061,
               decision_implied_prob=0.3937, dk_implied_prob=0.5556)
    ml_cut = dict(min_prob=0.55, min_edge=0.05, prob_only=0)
    soon = "2026-10-03T00:00:00+00:00"
    assert _passes(fla, ml_cut)                               # the cut alone says yes
    assert not _publishable(fla, ml_cut, start=soon, horizon=NOW_PLUS_24)
    # A real best-price gap (7.56pp, above every posted BET's 6.72pp max) passes.
    assert _publishable(dict(fla, decision_implied_prob=0.48), ml_cut,
                        start=soon, horizon=NOW_PLUS_24)
    assert not _publishable(dict(fla, decision_implied_prob=0.4700), ml_cut,
                            start=soon, horizon=NOW_PLUS_24)
    # No DraftKings price (NULL or 0.0): nothing to compare, the guard passes.
    for dk in (None, 0.0):
        assert _publishable(dict(fla, dk_implied_prob=dk, decision_edge=0.2), ml_cut,
                            start=soon, horizon=NOW_PLUS_24)


def test_the_guards_are_pre_game_only():
    """In-play quotes move in seconds; ncaaf_live_win_prob decides a mean 6.2pp
    off DK by design. Live rows skip both guards."""
    live = dict(NYR, model_id="ncaaf_live_win_prob", is_live=1,
                decision_implied_prob=0.20, dk_implied_prob=0.40,
                model_probability_cal=0.47)
    assert _publishable(live, dict(min_prob=0.40, min_edge=0.05, prob_only=0),
                        start="2026-10-09T00:00:00+00:00", horizon=NOW_PLUS_24)


# ── the price-age bound (review round 2) ─────────────────────────────────────

TONIGHT = "2026-10-02T22:40:00+00:00"        # 3094775, 6:40 PM ET


def test_a_decided_only_pick_priced_too_long_before_its_start_never_publishes():
    """3094775 as stored: priced 2026-10-01 11:24Z, 35.3h before the puck drop.
    No re-pricing exists, so the window alone would post that price."""
    stored = dict(NYR, created_at="2026-10-01T11:24:56+00:00")
    assert not _publishable(stored, NHL_REG_CUT, start=TONIGHT, horizon=NOW_PLUS_24)
    # 11h40m before the start passes; 12h10m does not.
    assert _publishable(dict(NYR, created_at="2026-10-02T11:00:00+00:00"), NHL_REG_CUT,
                        start=TONIGHT, horizon=NOW_PLUS_24)
    assert not _publishable(dict(NYR, created_at="2026-10-02T10:30:00+00:00"), NHL_REG_CUT,
                            start=TONIGHT, horizon=NOW_PLUS_24)
    # An unknown price time is never fresh.
    assert not _publishable(dict(NYR, created_at=None), NHL_REG_CUT,
                            start=TONIGHT, horizon=NOW_PLUS_24)


def test_the_age_verdict_is_fixed_against_the_start_not_now():
    """Measured against the START, so a decided-only pick the app shows and
    Discord posted does not drop off the board as the clock runs."""
    row = dict(NYR, created_at="2026-10-02T11:00:00+00:00")
    for now in ("2026-10-02T12:00:00+00:00", "2026-10-02T20:05:00+00:00",
                "2026-10-02T22:39:00+00:00"):
        assert _publishable(row, NHL_REG_CUT, start=TONIGHT, horizon=NOW_PLUS_24, now=now)


def test_with_no_start_the_age_is_measured_against_now():
    nodate = dict(NYR, game_date="2026-10-02")
    assert _publishable(dict(nodate, created_at="2026-10-02T09:00:00+00:00"), NHL_REG_CUT,
                        start=None, horizon=NOW_PLUS_24)
    assert not _publishable(dict(nodate, created_at="2026-10-02T07:00:00+00:00"), NHL_REG_CUT,
                            start=None, horizon=NOW_PLUS_24)


def test_the_price_age_bound_leaves_raw_passes_and_live_rows_alone():
    old = "2026-09-28T00:00:00+00:00"
    raw_ok = dict(NYR, model_probability=0.46, decision_edge=0.0864, created_at=old)
    assert _publishable(raw_ok, NHL_REG_CUT, start=TONIGHT, horizon=NOW_PLUS_24)
    live = dict(NYR, model_id="ncaaf_live_win_prob", is_live=1, created_at=old,
                model_probability_cal=0.47, dk_implied_prob=0.40)
    assert _publishable(live, dict(min_prob=0.40, min_edge=0.05, prob_only=0),
                        start=TONIGHT, horizon=NOW_PLUS_24)


def test_signal_delivery_applies_the_price_age_bound():
    """The health check's Python window gets the row's created_at, so a
    decided-only pick the publishers refuse for its age is not an undelivered
    signal (CRIT)."""
    src = inspect.getsource(sh)
    assert "config.decided_only_window_open(\n                        _parse_ts(commence), game_date, _parse_ts(created_at))" in src


def test_the_price_age_bound_is_the_measured_one():
    """Measured 2026-10-02 over 621 posted pre-game BETs, post time minus the bet
    of record's created_at: p99 10.4h, max 22.7h, 2 over 12h, 0 over 24h."""
    assert config.PUBLISH_MAX_PRICE_AGE_HOURS == 12


def test_the_gap_threshold_is_the_measured_one():
    """Measured 2026-10-02 over 621 posted pre-game BETs: max off-DK gap 6.72pp."""
    assert config.PUBLISH_MAX_PRICE_GAP == 0.08
    assert config.DECIDED_ONLY_PUBLISH_WITHIN_HOURS == 24


# ── who decides on what (reviewer MEDIUM: ncaaf_live) ────────────────────────

def test_ncaaf_live_decides_calibrated_at_dk(monkeypatch):
    """ncaaf_live/serve.py decide_honest: honest_probability, minus DK's implied,
    regardless of DECIDE_ON_CALIBRATED_PROB. The cut must agree with it."""
    from ncaaf_live.serve import LiveEngine
    import models.honest_ev as he
    monkeypatch.setattr(he, "honest_probability", lambda m, p: 0.47)
    src = inspect.getsource(LiveEngine)
    assert "self.decide_honest(c[\"model_id\"], p, implied" in src
    for m in ("ncaaf_live_win_prob", "ncaaf_live_total"):
        assert f'"{m}"' in src
        assert config.decision_source(m) == "calibrated_at_dk"
    row = dict(model_id="ncaaf_live_win_prob", model_probability=0.42,
               model_probability_cal=0.47, edge=0.02, decision_edge=0.09,
               decision_implied_prob=0.33, dk_implied_prob=0.40, is_live=1)
    cut = dict(min_prob=0.45, min_edge=0.06, prob_only=0)
    sig = LiveEngine.decide_honest("ncaaf_live_win_prob", 0.42, 0.40, 0.45, 0.06)
    # 0.47 - 0.40 = 0.07 >= 0.06 at DK: BET; the decision book's 0.33 is not read.
    assert sig == "BET"
    assert _passes(row, cut)
    assert config.decided_numbers(row) == (0.47, pytest.approx(0.07))
    assert not _passes(dict(row, dk_implied_prob=0.42), cut)
    monkeypatch.setattr(config, "DECIDE_ON_CALIBRATED_PROB", False)
    assert config.decides_on_calibrated("ncaaf_live_win_prob")
    assert _passes(row, cut)


def test_every_non_artifact_model_is_classified_against_its_decision_code():
    """A non-artifact model decides raw unless its engine decides on the
    honest number; the only such engine is ncaaf_live (decide_honest)."""
    serve = (ROOT / "ncaaf_live" / "serve.py").read_text(encoding="utf-8")
    assert "honest_probability(model_id, p)" in serve
    for m, how in config.SCORING_METHODS.items():
        if how == config.SCORING_ARTIFACT:
            continue
        expected = "calibrated_at_dk" if m.startswith("ncaaf_live_") else "raw"
        assert config.decision_source(m) == expected, m


# ── boundary handling (reviewer LOWs) ────────────────────────────────────────

def test_a_zero_implied_probability_is_a_missing_price():
    """Pre-09-09 rows with no DK quote carry dk_implied_prob = 0.0; cal - 0
    would publish the whole probability as edge."""
    row = dict(model_id="mlb_prop_batter_hr", model_probability=0.30,
               model_probability_cal=0.31, edge=0.0, decision_edge=None,
               decision_implied_prob=None, dk_implied_prob=0.0)
    cut = dict(min_prob=0.25, min_edge=0.05, prob_only=0)
    assert not _passes(row, cut)
    assert config.decided_numbers(row) == (0.31, 0.0)
    assert "NULLIF(p.dk_implied_prob, 0)" in config.decided_edge_sql("p")
    assert "NULLIF(p.decision_implied_prob, 0)" in config.decided_edge_sql("p")


def test_the_probability_cut_compares_the_scorers_own_rounding(monkeypatch):
    """scorer._calibrated returns round(.., 4) -- the same number stored in
    model_probability_cal -- so a calibrated prob exactly on the cut agrees."""
    from models import scorer
    src = inspect.getsource(scorer._calibrated)
    assert "round(apply_calibration(float(prob), _CAL_CACHE.get(model_id)), 4)" in src
    row = dict(NYR, model_probability_cal=0.4, decision_implied_prob=0.3)
    assert _passes(row, NHL_REG_CUT)
    assert not _passes(dict(row, model_probability_cal=0.3999), NHL_REG_CUT)


# ── record views and reports (reviewer MEDIUMs) ──────────────────────────────

def test_the_record_view_migration_is_generated_from_config_and_registered():
    from scripts.emit_record_views_decided_cut import OUT, render
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert OUT.read_text(encoding="utf-8") == render(), "regenerate the migration"
    body = OUT.read_text(encoding="utf-8")
    assert config.decided_prob_sql("p") + " AS prob" in body
    assert config.decided_edge_sql("p") + " AS edge" in body
    assert body.count(config.decided_cut_sql("pp", "m")) == 2
    for v in ("v_model_full_record", "v_model_full_outcome_record",
              "v_model_full_outcome_picks"):
        assert f"CREATE OR REPLACE VIEW public.{v} WITH (security_invoker = on)" in body
        assert f"pg_get_viewdef('public.{v}'::regclass, true)" in body
    assert body.count("IF position('model_probability_cal' in d) > 0 THEN") == 3
    assert ACTIVE_MIGRATIONS[-1] == "record_views_decided_cut_2026_10_02.sql"
    assert ACTIVE_MIGRATIONS.index("record_views_decided_cut_2026_10_02.sql") > \
        ACTIVE_MIGRATIONS.index("record_excludes_paused_rows_2026_09_28.sql")


def test_the_reports_cut_on_the_decided_numbers():
    import scripts.model_roi_report as roi
    import scripts.mlb_bet_record_audit as audit
    assert config.decided_cut_sql("p", "m") in roi.SQL
    assert config.decided_cut_sql("p", "t") in audit.PICKS_SQL
    dash = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "_prob = decided_prob_col(_mid)" in dash
    assert "{decided_edge_col(_mid)} >= {_t['min_edge']}" in dash
    assert "AND model_probability >= {_t['min_prob']}" not in dash
