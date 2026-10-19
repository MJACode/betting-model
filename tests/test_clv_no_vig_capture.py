"""Capture-path guards for no-vig CLV (docs/clv.md).

The arithmetic lives in tracking/clv_math.py and is pinned by test_clv_math.py.
These check the worker actually *calls* it, prefers a sharp close, refuses an
in-play fallback, and does not mix legacy raw_one_sided into the pedigree view.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "tracking" / "paper_tracker.py"


def _fn(name: str) -> str:
    text = SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


def test_capture_grades_raw_same_book_and_a_separate_pinnacle_edge():
    src = _fn("_capture_clv")
    assert "same_book_clv(" in src
    assert "market_edge_clv(" in src
    assert "price_clv_pct(" not in src
    assert "american_to_implied_prob" not in src
    assert "and not line_moved:" in src
    assert "_locked_other_prices(" not in src
    assert "bet_other_prices=" not in src
    assert "pick_book=bookmaker" in src
    assert "pick_book=sharp" in src


def test_a_missing_bet_book_close_is_not_filled_from_another_book():
    game = _fn("_first_game_close")
    prop = _fn("_first_prop_close")
    assert "close_book_candidates" not in game
    assert "close_book_candidates" not in prop
    assert "No other book is tried" in game
    assert "No other book" in prop


def test_game_close_never_falls_back_past_first_pitch():
    """The §106 leak: post-pitch rows labelled 'open'. An unbounded latest
    would record an in-play number as the close."""
    src = _fn("_closing_odds")
    assert "snapshot_at::timestamptz <= %s::timestamptz" in src
    assert src.count("ORDER BY snapshot_at") == 1
    assert "if not commence_time:" in src
    assert "return None" in src


def test_prop_close_stays_bounded_at_first_pitch():
    src = _fn("_closing_prop_odds")
    assert "snapshot_at::timestamptz <= %s::timestamptz" in src


def test_pinnacle_is_a_second_lookup_not_the_headline_close():
    cap = _fn("_capture_clv")
    assert "_sharp_close_book()" in cap
    assert "_first_prop_close(" in cap
    assert "_first_game_close(" in cap
    sharp = _fn("_sharp_close_book")
    assert "close_book_candidates(" in sharp


def test_capture_stamps_method_and_close_book():
    src = _fn("_capture_clv")
    assert "clv_method          = %s" in src
    assert "clv_close_book      = %s" in src


def test_backfill_revisits_anything_that_is_not_standard_v2():
    src = _fn("_backfill_clv")
    assert "p.clv_method IS DISTINCT FROM %s" in src
    cap = _fn("_capture_clv")
    assert "p.clv_method IS DISTINCT FROM %s" in cap


def test_pedigree_view_excludes_legacy_raw():
    sql = (ROOT / "data" / "migrations" /
           "track_record_clv_no_vig_2026_09_14.sql").read_text(encoding="utf-8")
    assert "clv_method IN ('no_vig','zero_vig')" in sql
    assert "raw_one_sided" not in sql.split("EXECUTE")[-1]


def test_column_migration_stamps_existing_rows_legacy():
    sql = (ROOT / "data" / "migrations" /
           "add_clv_method_2026_09_14.sql").read_text(encoding="utf-8")
    assert "clv_method = 'raw_one_sided'" in sql
    assert "ADD COLUMN IF NOT EXISTS clv_method" in sql
    assert "ADD COLUMN IF NOT EXISTS clv_close_book" in sql
    # ALTER and COMMENT take locks even when the column is already there.
    # Both sit behind the catalog check, and the stamp UPDATE sits behind
    # its own "a NULL remains" check. A pass that finds the columns and no
    # NULL does not run either.
    guard = sql.index("IF NOT has_cols")
    assert guard < sql.index("ADD COLUMN IF NOT EXISTS clv_method")
    assert guard < sql.index("COMMENT ON COLUMN")
    assert sql.index("INTO needs_stamp") < sql.index("IF needs_stamp")
    assert sql.index("IF needs_stamp") < sql.index("clv_method = 'raw_one_sided'")


def test_opening_signals_store_same_book_raw_pp_and_the_same_line_guard():
    src = (ROOT / "tracking" / "opening_signals.py").read_text(encoding="utf-8")
    assert "from tracking.clv_math import same_book_clv" in src
    assert "price_clv_pct(" not in src
    assert "if close_price is not None and not line_moved:" in src
    assert "same_book_clv(" in src
    assert "_first_game_close(" in src


def test_both_migrations_are_on_the_worker_list():
    from data.view_migrations import ACTIVE_MIGRATIONS
    cols = "add_clv_method_2026_09_14.sql"
    view = "track_record_clv_no_vig_2026_09_14.sql"
    assert cols in ACTIVE_MIGRATIONS
    assert view in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(cols) < ACTIVE_MIGRATIONS.index(view)
    assert (ACTIVE_MIGRATIONS.index("settled_record_survives_a_pause_2026_09_12.sql")
            < ACTIVE_MIGRATIONS.index(view))
