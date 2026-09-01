"""A cloud retrain must outlive its container.

The Railway worker writes a trained .pkl to CONTAINER DISK. The registry row
then points at a path the next deploy destroys — the "uncommitted .pkl is a
silent outage" failure with a new cause: not a person forgetting `git add`, but
a filesystem that does not survive. Training in the cloud is only safe once the
artifact is somewhere that does, which CLAUDE.md §1b already names: Supabase.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import models.trainer as trainer


class _Conn:
    def __init__(self, stored=None, fail=False):
        self.stored = dict(stored or {})
        self.fail = fail
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._last = (sql, params)
        if self.fail:
            raise RuntimeError("relation does not exist")
        if "INSERT INTO model_artifacts" in sql:
            # Faithful to the driver: psycopg2.Binary goes IN, and a memoryview
            # comes back OUT. A fake that stores and returns the same wrapper
            # would pass while production raised.
            blob = params["b"]
            raw = bytes(blob.adapted) if hasattr(blob, "adapted") else bytes(blob)
            self.stored[params["p"]] = memoryview(raw)
        return self

    def fetchone(self):
        sql, params = self._last
        if "SELECT payload FROM model_artifacts" in sql:
            val = self.stored.get(params[0])
            return (val,) if val is not None else None
        return None

    def commit(self):
        pass

    def rollback(self):
        pass


def test_the_artifact_is_stored_before_the_registry_points_at_it():
    """Registering first and uploading second leaves a window where the ACTIVE
    model is a path nothing can produce."""
    src = inspect.getsource(trainer._register_model)
    store_at = src.index("_store_artifact(conn")
    insert_at = src.index("INSERT INTO model_registry")
    assert store_at < insert_at


def test_a_no_register_run_stores_nothing():
    """A baseline run must leave production entirely alone — including the
    artifact table, or a comparison build becomes restorable as if it were real."""
    src = inspect.getsource(trainer._register_model)
    early_return = src.index("        return")
    store_at = src.index("_store_artifact(conn")
    assert early_return < store_at


def test_store_and_restore_round_trip(tmp_path, monkeypatch):
    pkl = tmp_path / "models" / "saved" / "m_v1.pkl"
    pkl.parent.mkdir(parents=True)
    pkl.write_bytes(b"\x80\x04not-really-a-pickle")
    monkeypatch.setattr(trainer, "MODELS_DIR", tmp_path / "models" / "saved")

    conn = _Conn()
    trainer._store_artifact(conn, "mlb_moneyline", "v1", pkl)
    assert conn.stored, "nothing was stored"

    pkl.unlink()                      # the container is gone
    restored = trainer._restore_artifact(conn, "models/saved/m_v1.pkl")
    assert restored is not None and restored.exists()
    assert restored.read_bytes() == b"\x80\x04not-really-a-pickle"


def test_a_failed_upload_does_not_lose_a_model_that_trained():
    """Best-effort by design: the run took an hour, and an upload failure must
    not raise past it. It is logged loudly instead."""
    conn = _Conn(fail=True)
    trainer._store_artifact(conn, "mlb_moneyline", "v1", Path(__file__))  # no raise


def test_a_missing_artifact_table_is_not_an_error_on_restore():
    assert trainer._restore_artifact(_Conn(fail=True), "models/saved/x.pkl") is None


def test_restore_returns_none_when_the_path_was_never_stored():
    assert trainer._restore_artifact(_Conn(), "models/saved/never.pkl") is None


def test_load_model_actually_loads_from_the_store_when_the_file_is_gone(tmp_path, monkeypatch):
    """Functional, not textual. The first version of this test compared string
    positions in the source and passed against a mutation that moved the error
    log but kept the call — which is the "a test that passes without the fix is
    not a test" trap, caught by mutating it.
    """
    import pickle as _pickle

    saved = tmp_path / "models" / "saved"
    saved.mkdir(parents=True)
    artifact = {"model_id": "mlb_moneyline", "feature_cols": ["a", "b"]}
    blob = _pickle.dumps(artifact)
    monkeypatch.setattr(trainer, "MODELS_DIR", saved)

    class _RegistryConn(_Conn):
        def fetchone(self):
            sql, params = self._last
            if "FROM model_registry" in sql:
                return ("models/saved/gone_v1.pkl", "v1")
            return super().fetchone()

        def close(self):
            pass

    conn = _RegistryConn(stored={"models/saved/gone_v1.pkl": memoryview(blob)})
    monkeypatch.setattr(trainer, "get_connection", lambda: conn)

    # The path does NOT exist on disk — this is the first deploy after a cloud
    # retrain, and the container that trained it is gone.
    assert not (saved / "gone_v1.pkl").exists()
    loaded = trainer.load_model("mlb_moneyline")
    assert loaded == artifact


def test_load_model_returns_none_when_the_store_has_nothing_either(tmp_path, monkeypatch):
    """The mutation-guard for the test above: it must not pass by loading
    something that was on disk all along."""
    saved = tmp_path / "models" / "saved"
    saved.mkdir(parents=True)
    monkeypatch.setattr(trainer, "MODELS_DIR", saved)

    class _RegistryConn(_Conn):
        def fetchone(self):
            sql, params = self._last
            if "FROM model_registry" in sql:
                return ("models/saved/gone_v2.pkl", "v2")
            return super().fetchone()

        def close(self):
            pass

    monkeypatch.setattr(trainer, "get_connection", lambda: _RegistryConn())
    assert trainer.load_model("mlb_moneyline") is None
