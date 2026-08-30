"""
_adapt_sql: SQLite-dialect SQL -> psycopg2 format.

The load-bearing rule is that a QUOTED STRING LITERAL is data and must survive
untouched. Rewriting one produces a named placeholder alongside the query's real
%s, and psycopg2 refuses the whole statement with "argument formats can't be
mixed" — which is exactly how PR #226 silently killed opening-signal capture,
the Discord signal query and both push-notifier queries for three days. The same
regex had already been patched once before, for ``::TEXT`` casts.

It then happened a THIRD time, 2026-08-30, through a doorway the literal rule
could not see: an apostrophe in a CODE COMMENT.

    -- os.locked_at is the capture step's clock, which runs later

The apostrophe in "step's" reads as an opening quote, which mis-pairs every
quote after it, which pushes a real literal further down ('%%:early') outside
the boundaries — and its :early becomes a named placeholder. Discord signal
delivery was dead for every sport until the signal_delivery health check
flagged it.

So the rule is wider than "literals are data": a comment is not string context
either, and both have to be skipped in ONE left-to-right pass. Two passes would
reintroduce the mis-pairing — a `--` inside a string is text, and a quote
inside a comment is text, and only whichever opens FIRST can decide.
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


# ── A comment is not string context (2026-08-30) ─────────────────────────────

def test_the_exact_statement_an_apostrophe_in_a_comment_broke():
    sql = """
        SELECT os.lock_key
        FROM opening_signals os
        -- os.locked_at is the capture step's clock, which runs later
        WHERE os.game_date = ?
          AND os.lock_key NOT LIKE '%%:early'
    """
    out = _adapt_sql(sql)
    assert out.count("%s") == 1
    assert not _named(out), "the comment's apostrophe mis-paired the quotes again"
    assert "'%%:early'" in out, "the literal must survive verbatim"


def test_an_apostrophe_in_a_comment_does_not_swallow_a_later_literal():
    out = _adapt_sql("SELECT 1 -- the book's number\nWHERE a = 'x' AND b = ?")
    assert out.count("%s") == 1 and "'x'" in out


def test_a_colon_word_inside_a_comment_is_not_a_placeholder():
    out = _adapt_sql("SELECT 1 -- see :ticket_id for context\nWHERE a = ?")
    assert not _named(out)
    assert out.count("%s") == 1


def test_a_block_comment_is_skipped_too():
    out = _adapt_sql("SELECT 1 /* the model's edge, see :note */ WHERE a = ?")
    assert not _named(out)
    assert out.count("%s") == 1


def test_a_dash_dash_inside_a_literal_is_data_not_a_comment():
    """Whichever region opens first wins. The string opens before the `--`, so
    the parameter after the string must still convert -- if the comment rule
    won here it would swallow the rest of the line."""
    out = _adapt_sql("SELECT * FROM t WHERE label = 'a -- b' AND id = ?")
    assert out.count("%s") == 1 and "'a -- b'" in out


def test_a_line_comment_ends_at_the_newline():
    out = _adapt_sql("SELECT 'x' -- it's fine\nWHERE a = ? AND b = :beta")
    assert out.count("%s") == 1
    assert "%(beta)s" in out


def test_no_sql_statement_in_the_repo_mixes_placeholder_styles():
    """The generic guard, because this is now the third instance of one bug
    class. psycopg2's refusal surfaces wherever the caller happens to swallow
    it, so the check has to be static and repo-wide rather than per-query."""
    import pathlib
    root = pathlib.Path(__file__).parent.parent
    stmt = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b", re.I)
    offenders = []
    for f in root.rglob("*.py"):
        if any(p in str(f) for p in (".venv", "node_modules", "/tests/")):
            continue
        for m in re.finditer(r'"""(.*?)"""', f.read_text(errors="ignore"), re.S):
            q = m.group(1)
            if not stmt.match(q):        # prose that mentions SQL is not SQL
                continue
            try:
                out = _adapt_sql(q)
            except Exception:
                continue
            if out and "%s" in out and _named(out):
                offenders.append(f"{f.relative_to(root)}: {_named(out)[:3]}")
    assert not offenders, "mixed placeholder formats:\n  " + "\n  ".join(offenders)
