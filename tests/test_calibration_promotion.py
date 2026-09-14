"""
A promoted calibration map is promoted until someone demotes it.

WHY THIS EXISTS
---------------
`load_calibrations` read `promoted_a` / `promoted_b` — the deliberate,
person-named copy — while filtering on `method`, which is the CANDIDATE's, and
the nightly fit rewrites it. So a refit that could not fit a model wrote
`method = NULL` and the promoted map disappeared on the next read, silently.

Measured in production 2026-09-07: `mlb_prop_pitcher_k` and
`mlb_prop_pitcher_hits` picks carried a distinct `model_probability_cal` on 166
of 166 rows from 2026-08-31 to 09-03, on 11 of 43 on 09-04, and on 0 of 95 from
09-05 — three days with no calibration at all, decided by a cron. That is the
exact failure the candidate/promoted split exists to prevent, arriving through
the one column the split forgot to duplicate.

The second half is the bar. Promotion used to require `applied`, which is
`helps` alone. `helps` says the map beats the raw number on unseen picks;
`transfers` says it actually closes the gap. `mlb_prop_pitcher_er` helps
(11.9pp -> 6.8pp) and does not close, and its own fit says "publish it; do not
build a threshold on it yet" — so it may move a display number and must not
move a decision.

Pure-function tests against a fake connection — no DB.
"""

from __future__ import annotations

import json

from models import probability_calibration as pc


class FakeConn:
    """Rows in, statements recorded. Column order follows the real queries."""

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        self._last = sql
        return self

    def fetchall(self):
        sql = " ".join(self._last.split())
        if "SELECT model_id, promoted_method, promoted_a, promoted_b" in sql:
            return [(r["model_id"], r.get("promoted_method"),
                     r.get("promoted_a"), r.get("promoted_b"))
                    for r in self.rows if r.get("promoted")]
        if "SELECT model_id, method, a, b" in sql:
            return [(r["model_id"], r.get("method"), r.get("a"), r.get("b"))
                    for r in self.rows if r.get("applied")]
        if "SELECT model_id, a, b, method, payload" in sql:
            return [(r["model_id"], r.get("a"), r.get("b"), r.get("method"),
                     r.get("payload")) for r in self.rows if r.get("applied")]
        raise AssertionError(f"unexpected query: {sql[:80]}")

    def commit(self):
        pass


def _row(model_id, **kw):
    base = {"model_id": model_id, "method": "platt", "a": 0.8, "b": -0.2,
            "applied": True, "promoted": False}
    base.update(kw)
    return base


def _payload(helps=True, transfers=True):
    return json.dumps({"helps": helps, "transfers": transfers})


# ── the inert-map defect ─────────────────────────────────────────────────────

def test_a_promoted_map_survives_a_refit_that_could_not_fit(monkeypatch):
    """THE REGRESSION. The nightly fit nulls `method` when it has too few
    graded picks; that must not reach into the promoted slot."""
    conn = FakeConn([_row("mlb_prop_pitcher_k", method=None, a=None, b=None,
                          promoted=True, promoted_method="platt",
                          promoted_a=0.76, promoted_b=-0.22)])
    maps = pc.load_calibrations(conn)
    assert "mlb_prop_pitcher_k" in maps
    assert maps["mlb_prop_pitcher_k"]["a"] == 0.76


def test_the_promoted_map_is_read_entirely_out_of_the_promoted_columns():
    """A candidate refit that moved a/b must not move the live decision."""
    conn = FakeConn([_row("m", a=0.11, b=0.11, promoted=True,
                          promoted_method="platt", promoted_a=0.9,
                          promoted_b=-0.3)])
    assert pc.load_calibrations(conn)["m"] == {
        "method": "platt", "a": 0.9, "b": -0.3}


def test_a_row_promoted_before_the_method_column_existed_is_inert():
    """Fail closed. A NULL promoted_method means nobody recorded what the map
    was, and an unknown map must not decide a bet."""
    conn = FakeConn([_row("m", promoted=True, promoted_method=None,
                          promoted_a=0.9, promoted_b=-0.3)])
    assert pc.load_calibrations(conn) == {}


def test_the_candidate_view_still_reads_the_candidate_columns():
    """The dashboard's drift view asks a different question and keeps its
    answer."""
    conn = FakeConn([_row("m", a=0.11, b=0.22, applied=True)])
    assert pc.load_calibrations(conn, promoted_only=False)["m"]["a"] == 0.11


def test_a_broken_table_is_identity_maps_not_an_exception():
    class Boom(FakeConn):
        def execute(self, sql, params=None):
            raise RuntimeError("no such column")

        def rollback(self):
            self.rolled_back = True

    assert pc.load_calibrations(Boom([])) == {}


# ── the promotion bar ────────────────────────────────────────────────────────

def test_promotion_requires_helps_AND_transfers():
    conn = FakeConn([_row("good", payload=_payload(True, True)),
                     _row("helps_only", payload=_payload(True, False))])
    assert pc.promote(conn) == ["good"]


def test_promotion_records_the_method_and_the_verdicts_it_promoted_on():
    """So the decision path reads an endorsement frozen at promotion, rather
    than one a nightly fit can rewrite underneath it."""
    conn = FakeConn([_row("good", payload=_payload(True, True))])
    pc.promote(conn)
    params = [p for sql, p in conn.statements if p and "helps" in p][-1]
    assert params["method"] == "platt"
    assert params["helps"] is True and params["transfers"] is True


def test_an_unfitted_candidate_is_never_promoted():
    conn = FakeConn([_row("m", method=None, a=None, b=None,
                          payload=_payload(True, True))])
    assert pc.promote(conn) == []


def test_a_missing_payload_is_not_an_endorsement():
    conn = FakeConn([_row("m", payload=None)])
    assert pc.promote(conn) == []


def test_promote_can_be_restricted_to_named_models():
    conn = FakeConn([_row("a", payload=_payload()),
                     _row("b", payload=_payload())])
    assert pc.promote(conn, ["b"]) == ["b"]


def test_demote_clears_every_promoted_column():
    """A half-cleared row would read as promoted with an unknown map."""
    conn = FakeConn([])
    pc.demote(conn, ["m"])
    sql = conn.statements[-1][0]
    for col in ("promoted = FALSE", "promoted_a = NULL", "promoted_b = NULL",
                "promoted_method = NULL", "promoted_helps = NULL",
                "promoted_transfers = NULL"):
        assert col in sql


def test_the_promoted_columns_are_in_the_schema_guard():
    """ensure_schema ALTERs exactly the columns named here, so a column that
    only the CREATE TABLE knows about goes missing on every existing database."""
    assert {"promoted_method", "promoted_helps",
            "promoted_transfers"} <= set(pc._COLUMNS)


# ── candidate vs promoted, the 2026-09-14 health-check pair ──────────────────
#
# batter_runs was CRIT +11.1pp with a PROMOTED map. The map was the error: raw
# on the same window is +1.0pp. pitcher_er was CRIT on RAW because it has no
# promoted map, and its candidate still fails transfer (6.28pp > 6.0pp).


def test_a_missing_parameter_is_a_different_map():
    assert pc.maps_materially_differ(1.0, 0.0, None, 0.0)


def test_fit_noise_is_not_a_different_map():
    assert not pc.maps_materially_differ(1.10, 0.01, 1.11, 0.02)


def test_batter_runs_2026_09_14_is_a_re_promote():
    """The 09-07 promoted (a=1.138, b=0.377) vs the 09-14 candidate
    (a=1.106, b=0.012). Helps and transfers; params moved."""
    note = pc.eligibility_clause(
        "mlb_prop_batter_runs",
        helps=True, transfers=True, transfer_gap_pp=0.42,
        promoted=True,
        cand_a=1.105872, cand_b=0.011578,
        prom_a=1.138253, prom_b=0.376525,
    )
    assert note is not None and "re-promote" in note


def test_pitcher_er_2026_09_14_is_not_eligible():
    """helps 12.33 -> 6.28, which is still above MAX_TRANSFER_GAP_PP. Not a
    bug in the gate — the monthly gap is unstable (May +6.9, June +19.8,
    Aug +8.8, Sep +16.1)."""
    note = pc.eligibility_clause(
        "mlb_prop_pitcher_er",
        helps=True, transfers=False, transfer_gap_pp=6.28,
        promoted=False,
        cand_a=0.632661, cand_b=-0.195753,
        prom_a=None, prom_b=None,
    )
    assert note is not None
    assert "not eligible" in note
    assert "6.3pp" in note


def test_a_map_that_does_not_help_is_silent():
    assert pc.eligibility_clause(
        "m", helps=False, transfers=True, transfer_gap_pp=1.0,
        promoted=False, cand_a=1.0, cand_b=0.0, prom_a=None, prom_b=None,
    ) is None


def test_an_unpromoted_transferring_candidate_is_named():
    note = pc.eligibility_clause(
        "mlb_prop_batter_tb",
        helps=True, transfers=True, transfer_gap_pp=0.34,
        promoted=False,
        cand_a=0.55, cand_b=0.09, prom_a=None, prom_b=None,
    )
    assert note is not None and "not promoted" in note


def test_the_nightly_fit_does_not_promote():
    """A refit that promoted itself would re-cut every mapped model overnight
    with nobody deciding. Re-promotion is the worker job / --promote CLI."""
    import inspect
    src = inspect.getsource(pc.run_calibration_fit)
    assert "promote(" not in src
    persist_src = inspect.getsource(pc.persist)
    assert "DELIBERATELY not updated" in persist_src
    assert "promoted / promoted_a / promoted_b are DELIBERATELY not updated" in persist_src
