"""The player page's "WRs vs ATL" card (Matt, 2026-10-05).

"When you click into a user stat. We should show how other players at the same
position have done against that team." Phase 1 is NFL: the migration
add_position_vs_opponent_nfl.sql adds one RPC, the app maps the player's `pos`
to a group and asks for that group against his next opponent.

What these pin, in order of how quietly each one breaks:

  1. THE GROUP MAP IS WRITTEN TWICE — the SQL CASE that buckets `pos`, and
     NFL_GROUP_OF in lib/positionVsOpponent.ts that picks the group to ask
     for. If they disagree, the card asks for a group the server never fills
     and renders "No games" for every player at that position.
  2. THE ROLE CUT IS WRITTEN TWICE — the SQL that applies it and the footnote
     that tells the reader what it is. A footnote that names the wrong cut is a
     wrong number printed under a right one.
  3. EVERY NFL STAT CHIP HAS A BRANCH in the SQL CASE; a missing one returns
     NULL for every row and the card says "No games" for that stat.
  4. Applied by the worker, one statement, DDL once, granted to anon.

Exercised against a real Postgres 16 on 2026-10-05 (fixture schema, migration
applied twice, function called): a 2-target WR, a NULL stat value and a TE are
excluded from a WR read; a defence that allows more ranks above ATL; an unknown
stat returns zero rows; anon can execute and PUBLIC cannot.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data/migrations/add_position_vs_opponent_nfl.sql"
LIB = ROOT / "mobile/src/lib/positionVsOpponent.ts"
QUERIES = ROOT / "mobile/src/lib/queries.ts"
HOOK = ROOT / "mobile/src/hooks/usePlayerDetail.ts"
SCREEN = ROOT / "mobile/src/screens/PlayerStatsScreen.tsx"
CARD = ROOT / "mobile/src/components/PositionVsOpponentCard.tsx"
CATALOG = ROOT / "mobile/src/lib/statCatalog.ts"

# encoding pinned: box-drawing characters, and cp1252 on the suite's machine.
CODE = MIG.read_text(encoding="utf-8")
SQL_ONLY = "\n".join(ln for ln in CODE.splitlines() if not ln.lstrip().startswith("--"))
TS = LIB.read_text(encoding="utf-8")


def _sql_groups() -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"WHEN n\.pos (?:= '(\w+)'|IN \(([^)]*)\)) THEN '(\w+)'", SQL_ONLY):
        single, many, grp = m.groups()
        for p in [single] if single else re.findall(r"'(\w+)'", many):
            out[p] = grp
    return out


def _ts_groups() -> dict[str, str]:
    body = re.search(r"const NFL_GROUP_OF[^{]*\{(.*?)\n\};", TS, re.S)
    assert body, "NFL_GROUP_OF is missing"
    return dict(re.findall(r"(\w+): '(\w+)'", body.group(1)))


def test_the_worker_applies_it_and_anon_can_call_it():
    from data.anon_readable import RPC_ANON_CALLABLE
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name in ACTIVE_MIGRATIONS
    assert "position_vs_opponent_nfl" in RPC_ANON_CALLABLE
    assert "REVOKE ALL ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) FROM PUBLIC" in CODE
    assert "TO anon, authenticated" in CODE


def test_it_is_one_statement_and_does_its_ddl_once():
    assert SQL_ONLY.strip().startswith("DO $mig$")
    assert SQL_ONLY.strip().endswith("$mig$;")
    assert SQL_ONLY.count("$mig$") == 2
    assert "AS $$" not in SQL_ONLY
    assert "p.proname = 'position_vs_opponent_nfl') THEN" in CODE
    assert "RETURN;" in CODE


def test_the_app_and_the_server_bucket_positions_the_same_way():
    sql, ts = _sql_groups(), _ts_groups()
    assert sql, "could not parse the SQL position CASE"
    assert sql == ts


def test_the_footnote_names_the_cut_the_server_applies():
    cuts = {
        "QB": (r"WHEN 'QB' THEN COALESCE\(g\.attempts,0\) >= (\d+)", "QB: '{n}+ pass attempts'"),
        "RB": (r"WHEN 'RB' THEN COALESCE\(g\.carries,0\) \+ COALESCE\(g\.targets,0\) >= (\d+)", "RB: '{n}+ carries and targets'"),
        "WR": (r"WHEN 'WR' THEN COALESCE\(g\.targets,0\) >= (\d+)", "WR: '{n}+ targets'"),
        "TE": (r"WHEN 'TE' THEN COALESCE\(g\.targets,0\) >= (\d+)", "TE: '{n}+ targets'"),
        "DEF": (r"COALESCE\(g\.def_qb_hits,0\) >= (\d+)", "DL: '{n}+ tackles, sacks or QB hits'"),
    }
    for grp, (pat, ts_line) in cuts.items():
        m = re.search(pat, SQL_ONLY)
        assert m, f"role cut for {grp} not found in the SQL"
        assert ts_line.format(n=m.group(1)) in TS, f"{grp} footnote disagrees with the SQL cut"


def test_every_nfl_stat_chip_has_a_branch():
    catalog = CATALOG.read_text(encoding="utf-8")
    keys = set(re.findall(r"\{ key: '(\w+)', label: '[^']*', sport: 'NFL'", catalog))
    assert keys, "could not parse the NFL stat chips"
    for k in keys:
        assert f"WHEN '{k}'" in SQL_ONLY, f"NFL chip {k} has no branch in position_vs_opponent_nfl"


def test_the_client_reads_the_rpc_by_name_and_only_for_the_nfl():
    q = QUERIES.read_text(encoding="utf-8")
    m = re.search(r"export async function fetchPositionVsOpponent\(.*?\n\}\n", q, re.S)
    assert m
    body = m.group(0)
    assert ".rpc('position_vs_opponent_nfl'" in body
    assert "if (sport !== 'NFL') return [];" in body
    assert "fetchAllPages" in body and ".range(from, to)" in body


def test_the_card_is_about_other_players_and_is_mounted():
    assert "excludePlayerId && r.player_id === opts.excludePlayerId" in TS
    hook = HOOK.read_text(encoding="utf-8")
    assert "fetchPositionVsOpponent(sport, [pvoSeason, pvoSeason - 1]" in hook
    screen = SCREEN.read_text(encoding="utf-8")
    assert "<PositionVsOpponentCard" in screen
    card = CARD.read_text(encoding="utf-8")
    # The rank is described in words; a bare "#9" reads either way round.
    assert "most of ${card.teamsRanked}" in card


def test_a_failed_read_is_not_held_on_the_spinner():
    """useSection's catch replaces the payload with the untagged initial
    `{ statKey: '' }`. The card spins while `loading` is true and the rows
    are empty, and the error line sits behind that. A stat-key mismatch
    during a refetch is still loading; the same mismatch after a failure is
    the failure. Counting it as loading leaves the spinner up forever."""
    hook = HOOK.read_text(encoding="utf-8")
    m = re.search(
        r"rows: pvo\.data\.statKey === String\(stat\?\.key \?\? ''\) \? pvo\.data\.rows : \[\],\n"
        r"\s*loading: pvo\.loading \|\| \(pvo\.error == null && "
        r"pvo\.data\.statKey !== String\(stat\?\.key \?\? ''\)\),",
        hook,
    )
    assert m, "a failed position-vs-opponent read must not stay loading"
    card = CARD.read_text(encoding="utf-8")
    # The error line is reachable once loading is false: spinner, then error.
    assert "{loading && rows.length === 0 ? (" in card
    assert "Couldn't load" in card
