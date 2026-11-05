"""The open picks, as one view any Claude chat with the Supabase connector reads.

mike, 2026-11-04: no pasting anywhere, ever. docs/mobile_picks_prompt.md used to
hold a prompt and a query for a person to paste into a claude.ai project. The
query now lives in the database as `public.open_picks`, so a chat asks for the
open picks and reads one view, and the logic changes in a reviewed migration
instead of in someone's project settings.

The rows are the open BETs the app, Discord and push show (CLAUDE.md §1b):
the same `model_action_thresholds` cut the producers apply, the same posted
rule as the app's passesActionFilter (a bet Discord already posted keeps the
cuts it was written under), and the same exclusions.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

MIG = ROOT / "data" / "migrations" / "open_picks_view_2026_11_04.sql"
SQL = MIG.read_text(encoding="utf-8") if MIG.exists() else ""

COLUMNS = [
    "sport",
    "game_date",
    "start_time_et",
    "matchup",
    "pick",
    "price",
    "book",
    "stake",
    "risk_units",
    "to_win_units",
    "model",
    "decided_at_et",
    "pick_id",
    "model_id",
]


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def _view_body() -> str:
    m = re.search(r"\$view\$(.*?)\$view\$", SQL, re.S)
    assert m, "no $view$ body in the migration"
    return m.group(1)


def _select_list(body: str) -> str:
    code = _code(body)
    i = code.index("SELECT")
    j = code.index("\n    FROM public.picks p", i)
    return code[i + len("SELECT"):j]


def _top_level_aliases(select_list: str) -> list[str]:
    """`expr AS name` at paren depth 0, in order."""
    out, depth, buf = [], 0, []
    for ch in select_list:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    names = []
    for item in out:
        m = re.search(r"\bAS\s+([a-z_]+)\s*$", item.strip(), re.S)
        assert m, f"a column with no alias: {item.strip()[:80]!r}"
        names.append(m.group(1))
    return names


def _model_meta() -> list[tuple[str, str]]:
    src = (ROOT / "mobile" / "src" / "lib" / "modelMeta.ts").read_text(encoding="utf-8")
    start = src.index("export const MODEL_META")
    body = src[start:src.index("\n};", start)]
    pairs = []
    for m in re.finditer(r"^  ([a-z0-9_]+): \{\n(.*?)^  \},", body, re.M | re.S):
        label = re.search(r"longLabel: '([^']*)'", m.group(2))
        assert label, m.group(1)
        pairs.append((m.group(1), label.group(1)))
    return pairs


# ── Registered, one statement, and a no-op once applied ──────────────────────

def test_the_migration_is_registered_before_the_posted_stake_pair():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.exists(), MIG
    assert MIG.name in ACTIVE_MIGRATIONS
    # It reads v_discord_published as the void-notice file leaves it.
    assert (ACTIVE_MIGRATIONS.index("discord_void_notice_2026_10_09.sql")
            < ACTIVE_MIGRATIONS.index(MIG.name))
    # The posted-stake pair stays last and adjacent.
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS[-2] == "published_pick_units_2026_10_17.sql"
    assert (ACTIVE_MIGRATIONS.index(MIG.name)
            < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql"))


def test_it_is_one_statement_that_returns_on_a_catalog_read_once_applied():
    code = _code(SQL)
    assert code.count("$mig$") == 2 and SQL.strip().endswith(";")
    # Nothing outside the DO block.
    assert code.strip().startswith("DO $mig$")
    first_ddl = code.index("CREATE OR REPLACE VIEW")
    guard = code.index("= 'open_picks ")
    assert guard < code.index("RETURN;", guard) < first_ddl
    assert "has_table_privilege('anon', 'public.open_picks', 'SELECT')" in code
    assert "has_table_privilege('authenticated', 'public.open_picks', 'SELECT')" in code


def test_it_waits_for_what_it_reads_instead_of_failing_the_pass():
    """On a fresh database this file runs before the posted-stake functions.
    It must skip, not raise, or the view-migrations step reds every pass."""
    code = _code(SQL)
    first_ddl = code.index("CREATE OR REPLACE VIEW")
    for prereq in ("to_regprocedure('public.published_pick_stake(numeric)') IS NULL",
                   "to_regclass('public.v_discord_published') IS NULL",
                   "to_regclass('public.model_action_thresholds') IS NULL"):
        assert prereq in code, prereq
        assert code.index(prereq) < first_ddl


def test_the_marker_is_the_hash_of_the_view_body():
    """The skip compares the view's comment to a marker. The marker is the
    body's own hash, so editing the view without changing the marker is a red
    test here rather than a change that never reaches production."""
    body = _view_body().replace("\r\n", "\n")
    want = "open_picks " + hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    code = _code(SQL)
    assert code.count(f"'{want}'") == 2, (
        f"set the marker to '{want}' in both the skip and the COMMENT")
    assert f"COMMENT ON VIEW public.open_picks IS '{want}'" in code


def test_it_writes_nothing_but_the_view_and_its_grants():
    code = _code(SQL).upper()
    for verb in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE", "ALTER TABLE",
                 "DROP ", "CREATE TABLE", "CREATE FUNCTION", "POLICY"):
        assert verb not in code, verb


# ── Who can read it ──────────────────────────────────────────────────────────

def test_it_is_read_with_the_callers_rights_and_granted_select_only():
    code = _code(SQL)
    assert "CREATE OR REPLACE VIEW public.open_picks\n    WITH (security_invoker = on) AS" in code
    assert "REVOKE ALL ON public.open_picks FROM anon, authenticated" in code
    assert "GRANT SELECT ON public.open_picks TO anon, authenticated" in code
    assert code.index("REVOKE ALL ON public.open_picks") < code.index("GRANT SELECT ON public.open_picks")


def test_it_is_declared_readable():
    from data.anon_readable import ANON_READABLE

    from tests.test_anon_readable import AHEAD_OF_THE_APP

    assert "open_picks" in ANON_READABLE
    # Read by Claude chats, not by a mobile `.from()`.
    assert "open_picks" in AHEAD_OF_THE_APP


# ── The columns ──────────────────────────────────────────────────────────────

def test_the_column_list_is_pinned():
    """CREATE OR REPLACE VIEW cannot rename, drop or reorder a column, so the
    list is fixed here. A new column goes on the end."""
    assert _top_level_aliases(_select_list(_view_body())) == COLUMNS


def test_the_pick_is_its_label_word_for_word():
    """CLAUDE.md §00: quote a pick from its label, never rebuild its line.

    One token comes off: the old NFL sizing figure ("· 0.87u") that wind and
    opener labels carry, which is not the stake (the
    stake column is). The pattern is pick_integrity's, so the view, Discord
    and the app drop the same text (tests/test_nfl_label_units.py).
    """
    from tracking.pick_integrity import _STAKE_TOKEN
    cols = _select_list(_view_body())
    want = (f"regexp_replace(p.pick_label, '{_STAKE_TOKEN.pattern}', '', 'g') "
            "AS pick")
    assert want in cols
    assert cols.count("p.pick_label") == 1
    assert "scored_line" not in _code(_view_body())


def test_times_are_eastern():
    cols = _select_list(_view_body())
    assert cols.count("AT TIME ZONE 'America/New_York'") >= 3
    assert "g.commence_time::timestamptz" in cols
    assert "p.created_at::timestamptz" in cols


def test_the_price_and_stake_are_the_published_ones():
    """The price the pick was decided at, and the stake every published
    surface books: 1u to win at that price, risk capped at 3, a bare 1u with
    no price (published_pick_stake, pinned to stake_for by
    tests/test_record_units_agree.py)."""
    body = _code(_view_body())
    assert "published_pick_stake(COALESCE(p.decision_odds, p.dk_odds)) s" in body
    assert "ROUND(COALESCE(p.decision_odds, p.dk_odds))::integer AS price" in body
    assert "ROUND(s.risk, 2) AS risk_units" in body
    assert "ROUND(s.win, 2) AS to_win_units" in body
    # The stake text is fmt_stake's: two decimals, half up, zeros trimmed.
    assert "trim_scale(ROUND(s.risk, 2))::text || 'u to win '" in body
    assert "trim_scale(ROUND(s.win, 2))::text || 'u'" in body
    assert "THEN '1u'" in body
    assert "$" not in body.replace("$view$", ""), "no dollar amounts"
    assert "bankroll" not in body.lower()


def test_every_model_has_its_app_name():
    body = _code(_view_body())
    case = body[body.index("CASE p.model_id"):]
    case = case[:case.index("END AS model")]
    found = re.findall(r"WHEN '([a-z0-9_]+)' THEN '([^']*)'", case)
    assert found == _model_meta()
    assert "ELSE p.model_id" in case
    for _mid, label in found:
        assert "lane" not in label.lower()


def test_every_book_has_its_channel_name():
    from tracking.discord_notifier import _BOOK_NAMES

    body = _code(_view_body())
    case = body[body.index("CASE lower(b.book_key)"):]
    case = case[:case.index("END AS book")]
    found = dict(re.findall(r"WHEN '([a-z0-9_]+)' THEN '([^']*)'", case))
    assert found == _BOOK_NAMES
    assert "ELSE b.book_key" in case


# ── Which rows ───────────────────────────────────────────────────────────────

def test_the_lock_key_is_the_publishers():
    """The view joins the Discord ledger on the pre-game key
    tracking/publish_keys mints. A component added there must be added here."""
    from tracking.publish_keys import KEY_PARTS

    body = _code(_view_body())
    want = "p.game_id || ':' || p.model_id" + "".join(
        f"\n                 || COALESCE(':' || p.{c}, '')" for c in KEY_PARTS)
    assert f"pub.lock_key = {want}" in body
    assert "FROM public.v_discord_published pub" in body


def test_only_open_pre_game_bets():
    body = _code(_view_body())
    for clause in (
        "p.signal_type = 'BET'",
        "p.result IS NULL",
        "(p.is_live IS NULL OR p.is_live = FALSE)",
        r"p.model_id NOT LIKE '%\_live\_%'",
        "(g.commence_time IS NULL\n           OR g.commence_time::timestamptz > now())",
        "(g.commence_time IS NOT NULL\n           OR p.game_date >= to_char(now() AT TIME ZONE 'America/New_York', 'YYYY-MM-DD'))",
    ):
        assert clause in body, clause


def test_void_duplicate_and_paused_rows_are_out():
    body = _code(_view_body())
    for clause in (
        "(p.condition_status IS NULL OR p.condition_status <> 'VOID')",
        "p.condition_status IS DISTINCT FROM 'DUPLICATE'",
        "p.downgrade_reason IS DISTINCT FROM 'model paused'",
    ):
        assert clause in body, clause
    # NFL health states on standing picks ('OK', 'GONE') stay in.
    assert "p.condition_status IS NULL\n" not in body


def test_only_bets_discord_posted_and_a_pause_still_removes_them():
    """The app, Discord and push show the same picks (CLAUDE.md 1b), and the
    app shows a bet once the channel has it. So a row needs the Discord lock.
    passesActionFilter's order: a paused model is out whatever was posted,
    and a posted bet keeps the cuts it was written under, so the view
    re-applies no cut."""
    body = _code(_view_body())
    assert "JOIN public.model_action_thresholds t ON t.model_id = p.model_id" in body
    where = body[body.index("WHERE p.signal_type"):]
    assert "AND t.paused = FALSE" in where
    assert "AND EXISTS (\n        SELECT 1 FROM public.v_discord_published pub" in where
    # Not an OR, not an optional column: the lock is required.
    assert "on_discord" not in body
    assert " OR EXISTS" not in where
    for cut in ("t.min_prob", "t.min_edge", "t.min_odds", "t.prob_only"):
        assert cut not in body, f"a posted bet keeps its cuts; {cut} re-cuts it"


def test_the_producer_posts_only_what_clears_the_cut():
    """The view leans on the producer for the cut: Discord posts a bet only
    after it clears its model's row in model_action_thresholds, at the
    decided price. If that stops being true, the view stops matching it."""
    src = (ROOT / "tracking" / "discord_notifier.py").read_text(encoding="utf-8")
    body = src[src.index("def _new_signals("):src.index("def _locked_signals(")]
    for gate in ("JOIN model_action_thresholds t ON t.model_id = p.model_id",
                 "AND t.paused = FALSE",
                 "AND p.model_probability >= t.min_prob",
                 "COALESCE(p.decision_edge, p.edge) >= COALESCE(t.min_edge, 0)",
                 "COALESCE(p.decision_odds, p.dk_odds) >= t.min_odds"):
        assert gate in body, gate


def test_rows_are_ordered_by_start_time():
    body = _code(_view_body())
    assert "ORDER BY g.commence_time::timestamptz NULLS LAST, p.created_at, p.pick_id" in body


# ── The doc no longer asks anyone to paste ───────────────────────────────────

def test_the_doc_points_at_the_view_and_asks_for_no_paste():
    doc = (ROOT / "docs" / "mobile_picks_prompt.md").read_text(encoding="utf-8")
    assert "open_picks" in doc
    assert "Project Instructions" not in doc
    assert "WITH latest_odds AS" not in doc
    assert not re.search(r"\bpaste (it|this|the)\b", doc, re.I)
    assert "lane" not in doc.lower()
