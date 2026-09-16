"""Object dtypes on d_starter_era_last3 / d_starter_k9_last3 break XGBoost.

Worker job 114289 (`mlb_runline_retrain_sweep`, register=false) failed after
the train set was built:

    ValueError: DataFrame.dtypes for data must be int, float, bool or category.
    Invalid columns:d_starter_era_last3: object, d_starter_k9_last3: object

Postgres NUMERIC arrives as Decimal; empty / missing last3 starts arrive as
'' or None. pandas leaves those columns object. This file is the test that
would have caught that before the worker ate the job.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from features.feature_engine import (
    FEATURE_MAP,
    SPARSE_OK_FEATURES,
    coerce_numeric_features,
    feature_matrix,
    numeric_feature_value,
)

ROOT = Path(__file__).resolve().parents[1]
LAST3 = ("d_starter_era_last3", "d_starter_k9_last3")
RUNLINE_COLS = FEATURE_MAP["mlb_runline"]


def _runline_row(**overrides) -> dict:
    row = {c: 1.0 for c in RUNLINE_COLS}
    row.update(overrides)
    return row


def test_raw_pandas_frame_leaves_last3_non_numeric():
    """Pin the bug: empty/None last3 is not numeric, which XGBoost then refuses.

    pandas 2 infers `object`; pandas 3 may infer StringDtype for ''. Either
    way the column is not int/float/bool/category — the XGBoost check.
    """
    feats = _runline_row(d_starter_era_last3="", d_starter_k9_last3=None)
    raw = pd.DataFrame([{c: feats.get(c) for c in RUNLINE_COLS}])[RUNLINE_COLS]
    assert not pd.api.types.is_numeric_dtype(raw["d_starter_era_last3"])
    assert not pd.api.types.is_numeric_dtype(raw["d_starter_k9_last3"])


def test_feature_matrix_coerces_last3_empty_and_none_to_numeric_nan():
    feats = _runline_row(d_starter_era_last3="", d_starter_k9_last3=None)
    X = feature_matrix(feats, RUNLINE_COLS)
    for col in LAST3:
        assert pd.api.types.is_numeric_dtype(X[col]), (
            f"{col} stayed {X[col].dtype}; XGBoost will refuse object columns")
        assert X[col].dtype != object
        assert pd.isna(X[col].iloc[0])


def test_feature_matrix_coerces_decimal_last3_to_float():
    feats = _runline_row(
        d_starter_era_last3=Decimal("3.50"),
        d_starter_k9_last3=Decimal("9.10"),
    )
    raw = pd.DataFrame([{c: feats.get(c) for c in RUNLINE_COLS}])[RUNLINE_COLS]
    assert not pd.api.types.is_numeric_dtype(raw["d_starter_era_last3"])
    X = feature_matrix(feats, RUNLINE_COLS)
    assert pd.api.types.is_numeric_dtype(X["d_starter_era_last3"])
    assert pd.api.types.is_numeric_dtype(X["d_starter_k9_last3"])
    assert float(X["d_starter_era_last3"].iloc[0]) == pytest.approx(3.50)
    assert float(X["d_starter_k9_last3"].iloc[0]) == pytest.approx(9.10)


def test_training_frame_empty_last3_becomes_nan_then_numeric():
    """The train-set assembly pandas infers: mixed Decimal / '' / None."""
    rows = [
        _runline_row(d_starter_era_last3=Decimal("3.21"),
                     d_starter_k9_last3=Decimal("8.80")),
        _runline_row(d_starter_era_last3="", d_starter_k9_last3=""),
        _runline_row(d_starter_era_last3=None, d_starter_k9_last3=None),
        _runline_row(d_starter_era_last3="4.10", d_starter_k9_last3="11.2"),
    ]
    df = pd.DataFrame(rows)
    assert not pd.api.types.is_numeric_dtype(df["d_starter_era_last3"])
    assert not pd.api.types.is_numeric_dtype(df["d_starter_k9_last3"])

    out = coerce_numeric_features(df, RUNLINE_COLS)
    for col in LAST3:
        assert pd.api.types.is_numeric_dtype(out[col]), (
            f"{col} stayed {out[col].dtype}")
        assert out[col].dtype != object
    assert pd.isna(out.loc[1, "d_starter_era_last3"])
    assert pd.isna(out.loc[1, "d_starter_k9_last3"])
    assert pd.isna(out.loc[2, "d_starter_era_last3"])
    assert float(out.loc[0, "d_starter_era_last3"]) == pytest.approx(3.21)
    assert float(out.loc[3, "d_starter_k9_last3"]) == pytest.approx(11.2)


def test_empty_last3_is_missing_so_strict_dropna_drops_the_row():
    """'' is not NA. Without coerce, dropna keeps a junk object row in train."""
    df = coerce_numeric_features(
        pd.DataFrame([_runline_row(d_starter_era_last3="", d_starter_k9_last3="")]),
        RUNLINE_COLS,
    )
    strict = [c for c in RUNLINE_COLS if c not in SPARSE_OK_FEATURES]
    assert df.dropna(subset=strict).empty


def test_xgboost_predict_refuses_object_last3_and_accepts_coerced_matrix():
    """The exact failure: pandas object last3 → _transform_pandas_df."""
    rng = np.random.default_rng(0)
    train = pd.DataFrame(rng.normal(size=(8, len(RUNLINE_COLS))), columns=RUNLINE_COLS)
    y = np.array([0, 1, 0, 1, 1, 0, 1, 0])
    clf = XGBClassifier(
        n_estimators=2, max_depth=1, eval_metric="logloss", verbosity=0)
    clf.fit(train, y)

    feats = _runline_row(d_starter_era_last3="", d_starter_k9_last3=None)
    raw = pd.DataFrame([{c: feats.get(c) for c in RUNLINE_COLS}])[RUNLINE_COLS]
    with pytest.raises(ValueError, match="object"):
        clf.predict_proba(raw)

    X = feature_matrix(feats, RUNLINE_COLS)
    proba = clf.predict_proba(X)
    assert proba.shape == (1, 2)
    assert np.isfinite(proba).all()


def test_numeric_feature_value_empty_missing_decimal():
    assert numeric_feature_value("") is None
    assert numeric_feature_value("  ") is None
    assert numeric_feature_value(None) is None
    assert numeric_feature_value(Decimal("2.75")) == pytest.approx(2.75)
    assert numeric_feature_value(0) == 0.0
    assert numeric_feature_value("not-a-number") is None


def test_train_and_runline_sweep_use_the_shared_coerce():
    """Not a one-off in the job wrapper — train + score share the helper."""
    engine = (ROOT / "features" / "feature_engine.py").read_text(encoding="utf-8")
    trainer = (ROOT / "models" / "trainer.py").read_text(encoding="utf-8")
    sweep = (ROOT / "scripts" / "mlb_runline_sweep.py").read_text(encoding="utf-8")
    assert "def coerce_numeric_features(" in engine
    assert "def feature_matrix(" in engine
    assert "df = coerce_numeric_features(df, present_features)" in engine
    assert "coerce_numeric_features" in trainer
    assert "feature_matrix" in sweep
    assert "pd.DataFrame([{c: feats.get(c) for c in feature_cols}])" not in sweep
