"""AI assistant (MCP): the member's saved preferences, and what each assistant advertises.

Matt, 2026-11-23/24. Two members asked their assistants for three prop picks on
a one-game NFL slate and got the same three, because the tools rank the same for
everyone. "Do both of these": a saved preferences profile per member (sports and
teams, price and risk, stats and books, research style; FREE -- not one of the
10 questions), and measure which assistants support MCP elicitation by logging
what each one advertises on initialize.

Run on a scratch cluster through the worker's own apply path, on top of every
earlier connector migration (the foundation fixture), twice.
"""
from __future__ import annotations

import json
import re

import pytest

from data.view_migrations import ACTIVE_MIGRATIONS
from tests.test_anon_lockdown import MIGRATIONS, _can, _psql
from tests.test_mcp_foundation import (  # noqa: F401  (dsn is a fixture)
    CHATGPT, CLAUDE_1, GROK, MATT, NOBODY, ROOT, TRIAL, _apply, _call, _member, dsn)

NAME = "mcp_preferences_2026_11_24.sql"
SERVER = ROOT / "supabase" / "functions" / "mcp" / "index.ts"
T0 = "2026-11-24 15:00:00+00"


@pytest.fixture(scope="module")
def pdsn(dsn):  # noqa: F811
    _apply(dsn, NAME)
    _apply(dsn, NAME)  # second pass: the marker makes it a no-op
    return dsn


def _profile(dsn: str, user: str, action: str, prefs: dict | None = None,
             at: str = T0, client: str = CLAUDE_1, session: str | None = None) -> dict:
    p = "NULL" if prefs is None else "'" + json.dumps(prefs).replace("'", "''") + "'"
    s = "NULL" if session is None else f"'{session}'"
    out = _psql(dsn, f"""
      BEGIN;
      SET LOCAL ROLE mcp_meter_role;
      SELECT mcp_meter.profile_call('{user}'::uuid, '{client}', {s}, '{action}',
                                    {p}::jsonb, '{at}'::timestamptz)::text;
      COMMIT;""")
    return json.loads([ln for ln in out.splitlines() if ln.startswith("{")][-1])


def test_listed_after_the_multi_assistant_migration():
    i = ACTIVE_MIGRATIONS.index
    assert NAME in ACTIVE_MIGRATIONS
    assert i("mcp_multi_assistant_2026_11_22.sql") < i(NAME)
    assert i("mcp_assistant_family_2026_11_22.sql") < i(NAME)


def test_a_new_member_has_no_profile_then_saves_one(pdsn):
    who = "77777777-7777-7777-7777-777777777701"
    _member(pdsn, who)
    r = _profile(pdsn, who, "get")
    assert r["allowed"] is True and r["has_profile"] is False and r["preferences"] == {}
    r = _profile(pdsn, who, "save", {"sports": ["NFL", "NBA"], "min_price": -200, "max_price": 150,
                                      "sides": "both", "books": ["FanDuel"]}, at="2026-11-24 15:01:00+00")
    assert r["has_profile"] is True and r["saved_from"] == "claude"
    assert r["preferences"]["books"] == ["FanDuel"]
    assert _profile(pdsn, who, "get", at="2026-11-24 15:02:00+00")["preferences"]["max_price"] == 150


def test_a_save_merges_and_null_clears_and_nothing_is_overwritten(pdsn):
    who = "77777777-7777-7777-7777-777777777702"
    _member(pdsn, who)
    _profile(pdsn, who, "save", {"sports": ["NHL"], "notes": "no parlays", "sides": "under"})
    r = _profile(pdsn, who, "save", {"sides": "over", "notes": None}, at="2026-11-24 15:01:00+00",
                 client=GROK)
    assert r["preferences"] == {"sports": ["NHL"], "sides": "over"}
    assert r["saved_from"] == "grok"
    # Append-only: both saves are still stored.
    n = _psql(pdsn, f"SELECT count(*) FROM mcp_meter.preference_saves WHERE user_id = '{who}';")
    assert n.strip() == "2"


def test_profile_calls_count_no_question(pdsn):
    """Matt chose free: the profile never spends one of the 10."""
    who = "77777777-7777-7777-7777-777777777703"
    _member(pdsn, who)
    assert _call(pdsn, who, "2026-11-24 15:00:00+00")["questions_used"] == 1
    for i in range(5):
        assert _profile(pdsn, who, "get", at=f"2026-11-24 15:0{i + 1}:00+00")["allowed"] is True
        assert _profile(pdsn, who, "save", {"stats": ["points"]}, at=f"2026-11-24 15:0{i + 1}:30+00")["allowed"]
    # The next real lookup, 9+ minutes on, is question 2 -- not 7 or 12.
    r = _call(pdsn, who, "2026-11-24 15:09:00+00")
    assert r["questions_used"] == 2 and r["questions_left"] == 8
    # Ten profile calls in under a minute did not trip the 5-a-minute cap either.
    rows = _psql(pdsn, f"""SELECT outcome, count(*) FROM mcp_meter.calls
                          WHERE user_id = '{who}' GROUP BY 1 ORDER BY 1;""")
    assert rows.split() == ["ok|2", "profile|10"]


def test_a_burst_continues_across_a_profile_call(pdsn):
    """A profile row must not reset the burst (begin_call reads 'ok' rows only)."""
    who = "77777777-7777-7777-7777-777777777704"
    _member(pdsn, who)
    assert _call(pdsn, who, "2026-11-24 15:00:00+00")["questions_used"] == 1
    _profile(pdsn, who, "get", at="2026-11-24 15:00:10+00")
    assert _call(pdsn, who, "2026-11-24 15:00:20+00")["questions_used"] == 1


def test_the_same_refusals_as_the_gate(pdsn):
    assert _profile(pdsn, TRIAL, "get")["reason"] == "not_entitled"
    assert _profile(pdsn, NOBODY, "save", {"sports": ["NFL"]})["reason"] == "not_entitled"
    who = "77777777-7777-7777-7777-777777777705"
    _psql(pdsn, f"""
      INSERT INTO auth.users (id) VALUES ('{who}');
      INSERT INTO public.access_grants (user_id, access_source) VALUES ('{who}', 'comped');""")
    assert _profile(pdsn, who, "get")["reason"] == "terms_required"
    _psql(pdsn, f"""
      INSERT INTO mcp_meter.terms_acceptances (user_id, terms_version) VALUES ('{who}', '2026-11-22');
      INSERT INTO mcp_meter.suspensions (user_id, reason) VALUES ('{who}', 'test');""")
    assert _profile(pdsn, who, "save", {"sports": ["NFL"]})["reason"] == "suspended"
    n = _psql(pdsn, f"SELECT count(*) FROM mcp_meter.preference_saves WHERE user_id = '{who}';")
    assert n.strip() == "0"


def test_a_disconnected_session_is_refused(pdsn):
    who = "77777777-7777-7777-7777-777777777706"
    _member(pdsn, who)
    assert _profile(pdsn, who, "get", session="sess-1")["allowed"] is True
    _psql(pdsn, f"UPDATE mcp_meter.connections SET revoked_at = now(), revoked_by = 'member' "
                f"WHERE user_id = '{who}';")
    assert _profile(pdsn, who, "get", session="sess-1", at="2026-11-24 15:05:00+00")["reason"] == "disconnected"


def test_a_fourth_assistant_is_refused(pdsn):
    who = "77777777-7777-7777-7777-777777777707"
    _member(pdsn, who)
    for c in (CLAUDE_1, CHATGPT, GROK):
        assert _profile(pdsn, who, "get", client=c)["allowed"] is True
    other = "c1a0de00-0000-4000-8000-000000000005"  # registered to evil.example
    assert _profile(pdsn, who, "get", client=other)["reason"] == "app_limit"


def test_saves_have_their_own_daily_cap(pdsn):
    who = "77777777-7777-7777-7777-777777777708"
    _member(pdsn, who)
    out = [_profile(pdsn, who, "save", {"stats": ["points"]},
                    at=f"2026-11-24 15:{i:02d}:00+00")["allowed"] for i in range(21)]
    assert out[:20] == [True] * 20 and out[20] is False
    # Founders are unlimited, as everywhere else.
    for i in range(22):
        assert _profile(pdsn, MATT, "save", {"stats": ["points"]},
                        at=f"2026-11-24 16:{i:02d}:00+00")["allowed"] is True


def test_record_client_counts_each_shape_once(pdsn):
    who = "77777777-7777-7777-7777-777777777709"
    _member(pdsn, who)
    for caps in ('{"elicitation": {}}', '{"elicitation": {}}', '{"roots": {}}'):
        _psql(pdsn, f"""
          BEGIN; SET LOCAL ROLE mcp_meter_role;
          SELECT mcp_meter.record_client('{who}'::uuid, '{CHATGPT}', '2025-06-18',
                 '{{"name": "openai-mcp", "version": "1.0"}}'::jsonb, '{caps}'::jsonb, NULL);
          COMMIT;""")
    rows = _psql(pdsn, f"""SELECT assistant, client_name, elicitation, seen_count
                          FROM mcp_meter.client_capabilities WHERE user_id = '{who}'
                          ORDER BY elicitation DESC;""")
    assert rows.split() == ["chatgpt|openai-mcp|t|2", "chatgpt|openai-mcp|f|1"]


def test_nothing_new_is_readable_outside_the_gate(pdsn):
    for role in ("anon", "authenticated", "mcp_reader", "mcp_meter_role"):
        for t in ("preference_saves", "client_capabilities"):
            ok, err = _can(pdsn, role, f"SELECT 1 FROM mcp_meter.{t};")
            assert not ok and "42501" in err, (role, t)
    for role in ("anon", "authenticated", "mcp_reader"):
        ok, err = _can(pdsn, role, f"SELECT mcp_meter.profile_call('{MATT}', 'x', NULL, 'get', NULL, now());")
        assert not ok and "42501" in err, role


def test_file_shape():
    sql = (MIGRATIONS / NAME).read_text(encoding="utf-8")
    assert "'mcp_preferences v1'" in sql and "-- mcp_preferences v1" in sql
    # Nothing is ever deleted (CLAUDE.md §1b); the FK cascade is auth's, not ours.
    assert not re.search(r"(?<!ON )\bDELETE\b|\bTRUNCATE\b|\bDROP\s+TABLE\b", sql)


def test_server_routes_profile_tools_around_the_question_gate():
    src = SERVER.read_text(encoding="utf-8")
    assert 'name: "get_my_preferences"' in src and 'name: "save_my_preferences"' in src
    assert 'new Set(["get_my_preferences", "save_my_preferences"])' in src
    branch = src.index("if (PROFILE_TOOLS.has(name))")
    assert branch < src.index("gate = await beginCall(who, name, args)")
    assert "mcp_meter.profile_call(" in src and "mcp_meter.record_client(" in src
    # initialize records what the assistant advertises, elicitation included.
    init = src.index('case "initialize"')
    assert "recordClient(who, msg.params)" in src[init:init + 300]
    # The instructions tell the assistant to ask first and apply the profile.
    assert "call get_my_preferences" in src and "has_profile is false, ask the member" in src
    # Every price tool takes the member's books.
    for tool in ("get_best_price", "get_prop_board", "get_game_lines"):
        start = src.index(f'name: "{tool}"')
        assert "books: booksProp" in src[start:start + 1600], tool
    assert src.count("jsonb_array_elements_text(${books}::jsonb)") == 3
