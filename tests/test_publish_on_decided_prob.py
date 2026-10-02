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
        assert (m in own) == (config.scoring_method(m) != config.SCORING_ARTIFACT
                              or m in config.MODELS_ON_OWN_PROBABILITY), m
    assert "nhl_moneyline" not in own and "nhl_moneyline_regulation" not in own


def test_flag_off_falls_back_to_raw(monkeypatch):
    monkeypatch.setattr(config, "DECIDE_ON_CALIBRATED_PROB", False)
    assert config.decided_prob_sql("p") == "p.model_probability"
    assert config.decided_edge_sql("p") == "COALESCE(p.decision_edge, p.edge)"
    assert not _passes(NYR, NHL_REG_CUT)
    assert not config.decides_on_calibrated("nhl_moneyline_regulation")
    assert config.decided_numbers(NYR) == (0.3801, 0.023)
    # And every publisher's SQL is the raw cut again.
    for sql in (_sql(dn._new_signals), _sql(pn._new_bet_signals)):
        assert "p.model_probability >= t.min_prob" in sql
        assert "model_probability_cal" not in sql


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

CUT = config.decided_cut_sql("p", "t")


@pytest.mark.parametrize("producer", [dn._new_signals, dn._locked_signals,
                                      pn._new_bet_signals])
def test_every_pre_game_publisher_applies_the_decided_cut(producer):
    sql = _sql(producer)
    assert CUT in sql
    assert "AND p.model_probability >= t.min_prob" not in sql


def test_the_stale_pause_probe_applies_the_decided_cut():
    src = inspect.getsource(dn._log_stale_pause_hiding_bets)
    assert 'config.decided_cut_sql("p", "t")' in src
    assert "p.model_probability >= t.min_prob" not in src


def test_signal_delivery_applies_the_decided_cut():
    """Else the health check alarms on rows Discord correctly withholds, or
    stays green while Discord withholds a BET."""
    src = inspect.getsource(sh.run_system_health)
    assert 'config.decided_cut_sql("p", "t")' in src
    assert "AND p.model_probability >= t.min_prob" not in src


def test_the_free_pick_cuts_on_the_pick_of_records_decided_numbers():
    sql = _sql(dn._free_pick_candidates)
    assert config.decided_prob_sql("p") + " AS decided_prob" in sql
    assert config.decided_edge_sql("p") + " AS decided_edge" in sql
    assert "COALESCE(pk.decided_prob, os.model_probability) >= t.min_prob" in sql
    assert "COALESCE(pk.decided_edge, os.edge) >= COALESCE(t.min_edge, 0)" in sql
    assert "AND os.model_probability >= t.min_prob" not in sql


def test_the_prompt_sql_emitter_uses_the_decided_numbers():
    from scripts.emit_threshold_sql import emit
    out = emit(prefix="p.")
    reg = [ln for ln in out.splitlines() if "'nhl_moneyline_regulation'" in ln][0]
    assert "COALESCE(p.model_probability_cal, p.model_probability) >= 0.4" in reg
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
    assert "!decidesOnCalibrated(p.model_id) || cal == null" in helper
    assert "p.decision_implied_prob ?? p.dk_implied_prob" in helper
    assert "edge: prob - Number(implied)" in helper
    assert "DECIDE_ON_CALIBRATED_PROB && !DECIDES_ON_RAW_MODELS.has(modelId)" in THRESHOLDS_TS


def test_the_generated_raw_decider_list_is_configs():
    block = GENERATED_TS[GENERATED_TS.index("export const DECIDES_ON_RAW_MODELS"):]
    block = block[:block.index("]);")]
    listed = {ln.strip().strip("',") for ln in block.splitlines()[1:] if ln.strip()}
    assert listed == set(config.decides_on_raw_models())
    flag = "true" if config.DECIDE_ON_CALIBRATED_PROB else "false"
    assert f"export const DECIDE_ON_CALIBRATED_PROB = {flag};" in GENERATED_TS


def test_the_app_query_fetches_the_columns_the_helper_reads():
    q = (ROOT / "mobile" / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    cols = q[q.index("const PICK_COLUMNS"):q.index("const SETTLED_PICK_COLUMNS")]
    for c in ("model_probability_cal", "decision_implied_prob", "dk_implied_prob",
              "decision_edge"):
        assert c in cols, c
