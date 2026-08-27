"""
_adapt_sql: SQLite-dialect SQL -> psycopg2 format.

The load-bearing rule is that a QUOTED STRING LITERAL is data and must survive
untouched. Rewriting one produces a named placeholder alongside the query's real
%s, and psycopg2 refuses the whole statement with "argument formats can't be
mixed" — which is exactly how PR #226 silently killed opening-signal capture,
the Discord signal query and both push-notifier queries for three days. The same
regex had already been patched once before, for ``::TEXT`` casts.
"""

import re

from data.db import _adapt_sql


def _named(sql: str) -> list[str]:
    return re.findall(r"%\([^)]*\)s", sql)


# ── The regression that motivated this ───────────────────────────────────────

def test_colon_word_inside_a_literal_is_not_a_placeholder():
    """':early' is a value the query concatenates, not a bind param."""
    out = _adapt_sql(
        "SELECT a || CASE WHEN d > %s THEN ':early' ELSE '' END, %s FROM t"
    )
    assert "':early'" in out
    assert _named(out) == [], "a literal must not become a named placeholder"


def test_the_four_queries_pr226_broke_now_adapt_cleanly():
    """opening_signals capture, discord_notifier._new_signals, and both
    push_notifier opening-signal queries all carry a ':early' literal."""
    for sql in (
        "SELECT x FROM picks p WHERE p.model_id NOT LIKE 'mlb_live_%%' "
        "AND lock_key NOT LIKE '%%:early' AND game_date = %s",
        "SELECT a || ':' || b || CASE WHEN d > %s THEN ':early' ELSE '' END, %s FROM t",
    ):
        out = _adapt_sql(sql)
        assert _named(out) == [], f"mixed formats reintroduced: {out}"
        assert ":early" in out


def test_mixing_the_two_styles_is_what_psycopg2_rejects():
    """Guards the invariant directly: no adapted query may contain both."""
    out = _adapt_sql("SELECT ':early', ? FROM t WHERE a = ?")
    assert "%s" in out and _named(out) == []


# ── Conversions that must still happen ───────────────────────────────────────

def test_named_params_outside_literals_still_convert():
    assert _adapt_sql("SELECT * FROM t WHERE a = :foo") == \
        "SELECT * FROM t WHERE a = %(foo)s"


def test_positional_params_outside_literals_still_convert():
    assert _adapt_sql("SELECT * FROM t WHERE a = ?") == \
        "SELECT * FROM t WHERE a = %s"


def test_a_real_param_after_a_literal_still_converts():
    out = _adapt_sql("SELECT ':lit', :real FROM t")
    assert "':lit'" in out and "%(real)s" in out


# ── Things that must not be disturbed ────────────────────────────────────────

def test_postgres_cast_is_untouched():
    """The session-27 fix: ``::TEXT`` must not become %(TEXT)s."""
    assert _adapt_sql("SELECT NOW()::TEXT") == "SELECT NOW()::TEXT"
    assert _named(_adapt_sql("SELECT created_at::TEXT FROM t")) == []


def test_question_mark_inside_a_literal_is_untouched():
    assert "'a?b'" in _adapt_sql("SELECT 'a?b' FROM t")


def test_percent_escape_survives():
    """%% is psycopg2's literal-percent escape and must reach the driver."""
    assert "'mlb_live_%%'" in _adapt_sql(
        "SELECT 1 FROM t WHERE model_id NOT LIKE 'mlb_live_%%'"
    )


def test_embedded_doubled_quote_does_not_end_the_literal():
    out = _adapt_sql("SELECT 'it''s :x', :y FROM t")
    assert "'it''s :x'" in out, "the escaped quote must not split the literal"
    assert "%(y)s" in out, "the real param after it must still convert"


def test_pragma_is_skipped():
    assert _adapt_sql("PRAGMA journal_mode=WAL") is None


def test_sqlite_helpers_still_rewrite():
    assert "NOW()::TEXT" in _adapt_sql("INSERT INTO t VALUES (datetime('now'))")
    assert _adapt_sql("INSERT OR IGNORE INTO t VALUES (1)").startswith("INSERT INTO")
