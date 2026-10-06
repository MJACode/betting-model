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


def test_the_client_reads_each_rpc_by_name_for_its_own_sport():
    q = QUERIES.read_text(encoding="utf-8")
    m = re.search(r"export async function fetchPositionVsOpponent\(.*?\n\}\n", q, re.S)
    assert m
    body = m.group(0)
    # Literal names, each behind its own sport check, so the read-surface
    # tripwire sees both and neither sport can reach the other's function.
    nfl = body.index("if (sport === 'NFL')")
    mlb = body.index("if (sport === 'MLB')")
    assert body.index(".rpc('position_vs_opponent_nfl'") > nfl
    assert mlb > body.index(".rpc('position_vs_opponent_nfl'")
    assert body.index(".rpc('position_vs_opponent_mlb'") > mlb
    assert body.rstrip().endswith("return [];\n}") or "  return [];\n}" in body
    assert body.count("fetchAllPages") == 2 and body.count(".range(from, to)") == 2


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
    assert (
        "const pvoFresh = pvo.data.statKey === String(stat?.key ?? '') && pvo.data.group === (posGroup ?? '');"
        in hook
    ), "rows must be tagged with BOTH the stat and the group they were read for"
    assert "rows: pvoFresh ? pvo.data.rows : []," in hook
    assert "loading: pvo.loading || (pvo.error == null && !pvoFresh)," in hook, (
        "a failed position-vs-opponent read must not stay loading"
    )
    card = CARD.read_text(encoding="utf-8")
    # The error line is reachable once loading is false: spinner, then error.
    assert "{loading && rows.length === 0 ? (" in card
    assert "Couldn't load" in card


# ── MLB (phase 2, 2026-10-06) ──────────────────────────────────────────────
MLB_MIG = ROOT / "data/migrations/add_position_vs_opponent_mlb.sql"
MLB_CODE = MLB_MIG.read_text(encoding="utf-8")
MLB_SQL = "\n".join(ln for ln in MLB_CODE.splitlines() if not ln.lstrip().startswith("--"))


def test_mlb_is_applied_guarded_and_granted():
    from data.anon_readable import RPC_ANON_CALLABLE
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MLB_MIG.name in ACTIVE_MIGRATIONS
    assert "position_vs_opponent_mlb" in RPC_ANON_CALLABLE
    assert MLB_SQL.strip().startswith("DO $mig$") and MLB_SQL.strip().endswith("$mig$;")
    assert MLB_SQL.count("$mig$") == 2
    assert "p.proname = 'position_vs_opponent_mlb') THEN" in MLB_CODE
    assert "REVOKE ALL ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) FROM PUBLIC" in MLB_CODE


def test_mlb_lineup_buckets_agree_between_app_and_server():
    """The SQL buckets batting_order 1-3/4-6/7-9 into TOP/MID/BOT; the app
    picks the bucket to ask for with the same edges."""
    for lo, hi, grp in re.findall(r"batting_order BETWEEN (\d) AND (\d) THEN '(\w+)'", MLB_SQL):
        assert (lo, hi, grp) in {("1", "3", "TOP"), ("4", "6", "MID"), ("7", "9", "BOT")}
    assert len(re.findall(r"batting_order BETWEEN", MLB_SQL)) == 3
    assert "return slot <= 3 ? 'TOP' : slot <= 6 ? 'MID' : 'BOT';" in TS
    assert "pgl.player_type = 'pitcher' AND pgl.is_starter THEN 'SP'" in MLB_SQL
    # The app can only tell a starter if the log read carries the column.
    log = (ROOT / "mobile/src/lib/playerLog.ts").read_text(encoding="utf-8")
    assert "batting_order, is_starter';" in log


def test_every_mlb_stat_chip_has_a_branch():
    catalog = CATALOG.read_text(encoding="utf-8")
    keys = set(re.findall(r"\{ key: '(\w+)', label: '[^']*', sport: 'MLB'", catalog))
    assert keys, "could not parse the MLB stat chips"
    # The player page swaps Innings for its own Outs chip (playerLog.OUTS_STAT),
    # which is not in the catalog — the key the page actually sends.
    log = (ROOT / "mobile/src/lib/playerLog.ts").read_text(encoding="utf-8")
    m = re.search(r"const OUTS_STAT: StatDef = \{\s*key: '(\w+)'", log)
    assert m, "could not parse OUTS_STAT"
    keys.add(m.group(1))
    for k in keys:
        assert f"WHEN '{k}'" in MLB_SQL, f"MLB chip {k} has no branch in position_vs_opponent_mlb"


def test_mlb_opponent_comes_from_games():
    """player_game_log has no opponent column; the opponent is the other side
    of the row's own MLB game."""
    assert "JOIN games g ON g.game_id = pgl.game_id AND g.sport = 'MLB'" in MLB_SQL
    assert "CASE WHEN g.home_team = pgl.team THEN g.away_team ELSE g.home_team END AS opp" in MLB_SQL


def test_mlb_shows_a_per_player_summary_and_the_nfl_keeps_its_game_list():
    """Matt, 2026-10-06: "Sure in summary" — MLB is ~440 player-games a
    season against one team, so it is summarised per player; the NFL list
    (~45 a season) stays game by game."""
    assert "export function isMlbGroup(g: PositionGroup): g is MlbGroup {" in TS
    assert "return g === 'TOP' || g === 'MID' || g === 'BOT' || g === 'SP';" in TS
    card = CARD.read_text(encoding="utf-8")
    assert "isMlbGroup(group) ? playerSummaries(card.entries) : null" in card
    # The summary counts hits with the SAME isHit the rows use, never its own.
    m = re.search(r"export function playerSummaries\(.*?\n\}\n", TS, re.S)
    assert m and "e.hit ? 1 : 0" in m.group(0) and "isHit(" not in m.group(0)


def test_the_pure_layer_behaves():
    """Runs mobile/scripts/verify_position_vs_opponent.ts: the MLB summary's
    grouping, averaging, latest-team, sort order and side; own-player
    exclusion; doubleheader numbering.

    Local-only. pr-ci.yml installs Python and Node 22, not mobile/node_modules,
    and tsx has to resolve the app's @/ aliases from that install. CI skips
    this test. Run it locally after `npm ci` in mobile/.
    """
    import shutil
    import subprocess

    import pytest

    tsx = ROOT / "mobile" / "node_modules" / ".bin" / "tsx"
    if shutil.which("node") is None or not tsx.exists():
        pytest.skip(
            "local-only: pr-ci does not install mobile/node_modules, so "
            "scripts/verify_position_vs_opponent.ts is not run in CI. "
            "Install deps with npm ci in mobile/ and re-run this test locally."
        )
    proc = subprocess.run(
        [str(tsx), "scripts/verify_position_vs_opponent.ts"],
        cwd=ROOT / "mobile", capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert "ALL PASS" in proc.stdout
