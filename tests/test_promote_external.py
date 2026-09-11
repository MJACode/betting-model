"""A map fitted outside the nightly path lands in the promoted_* columns only,
carries its provenance, and is refused unless it helps AND transfers."""
import pytest

from models import probability_calibration as pc


class _Conn:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def rollback(self):
        pass


def test_external_promotion_writes_only_the_promoted_columns(monkeypatch):
    monkeypatch.setattr(pc, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(pc, "schema_is_current", lambda *a, **k: True)
    conn = _Conn()
    pc.promote_external(conn, "mlb_live_total_runs", 0.8578, -0.0787, n=73854,
                        source="inplay_history_2025", helps=True, transfers=True)
    ins = [s for s, _ in conn.sql if s.startswith("INSERT INTO model_calibration")]
    assert len(ins) == 1
    sql, params = next((s, p) for s, p in conn.sql if s.startswith("INSERT INTO model_calibration"))
    assert "promoted_source" in sql and "promoted_method = 'platt'" in sql
    # the candidate columns the nightly fit owns are left to it
    assert "SET promoted = TRUE" in sql and "a = EXCLUDED.a" not in sql.split("ON CONFLICT")[1]
    assert params["a"] == 0.8578 and params["b"] == -0.0787
    assert params["src"].startswith("inplay_history_2025 n=73854 a=0.857800 b=-0.078700")


def test_external_promotion_refuses_a_map_that_does_not_transfer(monkeypatch):
    monkeypatch.setattr(pc, "ensure_schema", lambda conn: None)
    with pytest.raises(ValueError):
        pc.promote_external(_Conn(), "mlb_live_total_runs", 0.9, 0.0, n=10,
                            source="x", helps=True, transfers=False)


def test_the_scorer_reads_the_external_map_like_any_promoted_one():
    """load_calibrations reads promoted_method/promoted_a/promoted_b -- the
    columns promote_external writes -- so nothing else needs to know."""
    class _C(_Conn):
        def fetchall(self):
            return [("mlb_live_total_runs", "platt", 0.8578, -0.0787)]
    maps = pc.load_calibrations(_C())
    assert maps == {"mlb_live_total_runs": {"method": "platt", "a": 0.8578, "b": -0.0787}}
    assert round(pc.apply_calibration(0.72, maps["mlb_live_total_runs"]), 3) == 0.675
