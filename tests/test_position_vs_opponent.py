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
    # tripwire sees every one and no sport can reach another's function.
    order = ["NFL", "MLB", "NBA", "WNBA", "NCAAF"]
    checks = [body.index(f"if (sport === '{sp}')") for sp in order] + [len(body)]
    for i, sp in enumerate(order):
        rpc = body.index(f".rpc('position_vs_opponent_{sp.lower()}'")
        assert checks[i] < rpc < checks[i + 1], sp
    assert "  return [];\n}" in body
    assert body.count("fetchAllPages") == len(order)
    assert body.count(".range(from, to)") == len(order)


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
        "const pvoFresh = pvo.data.statKey === String(stat?.key ?? '') && pvo.data.group === (posGroup ?? '')\n"
        "    && pvo.data.opponent === opponent;"
        in hook
    ), "rows must be tagged with the stat, the group and the opponent they were read for"
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
    exclusion; doubleheader numbering. Needs the mobile deps (tsx resolves the
    app's @/ aliases); skipped where they are not installed."""
    import shutil
    import subprocess

    import pytest

    tsx = ROOT / "mobile" / "node_modules" / ".bin" / "tsx"
    if shutil.which("node") is None or not tsx.exists():
        pytest.skip("mobile node_modules not installed")
    proc = subprocess.run(
        [str(tsx), "scripts/verify_position_vs_opponent.ts"],
        cwd=ROOT / "mobile", capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    assert "ALL PASS" in proc.stdout


# ── NBA / WNBA / NCAAF (phase 3, 2026-10-06) ─────────────────────────────────
BN_MIG = ROOT / "data/migrations/add_position_vs_opponent_bball_ncaaf.sql"
BN_CODE = BN_MIG.read_text(encoding="utf-8")
BN_SQL = "\n".join(ln for ln in BN_CODE.splitlines() if not ln.lstrip().startswith("--"))


def _bn_body(sport: str) -> str:
    start = BN_SQL.index(f"FUNCTION public.position_vs_opponent_{sport}(")
    nxt = BN_SQL.find("CREATE OR REPLACE FUNCTION", start + 10)
    return BN_SQL[start:] if nxt == -1 else BN_SQL[start:nxt]


def test_roster_sports_are_applied_after_their_table_guarded_and_granted():
    from data.anon_readable import ANON_READABLE, RPC_ANON_CALLABLE
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert ACTIVE_MIGRATIONS.index(BN_MIG.name) > ACTIVE_MIGRATIONS.index("add_player_positions.sql")
    assert "player_positions" in ANON_READABLE
    for s in ("nba", "wnba", "ncaaf"):
        assert f"position_vs_opponent_{s}" in RPC_ANON_CALLABLE
        assert (f"REVOKE ALL ON FUNCTION public.position_vs_opponent_{s}"
                "(integer[], text, text, text) FROM PUBLIC") in BN_CODE
    assert BN_SQL.strip().startswith("DO $mig$") and BN_SQL.strip().endswith("$mig$;")
    assert ") >= 3 THEN" in BN_CODE and "RETURN;" in BN_CODE


def test_roster_functions_join_positions_and_the_right_opponent():
    for s, sport in (("nba", "NBA"), ("wnba", "WNBA")):
        b = _bn_body(s)
        assert f"pp.sport = '{sport}' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group" in b
        assert f"JOIN games gm ON gm.game_id = l.game_id AND gm.sport = '{sport}'" in b
        assert "COALESCE(g.minutes, 0) >= 15 AS has_role" in b
    b = _bn_body("ncaaf")
    assert "pp.sport = 'NCAAF' AND pp.player_id = l.player_id AND pp.pos_group = p_pos_group" in b
    assert "l.opponent AS opp" in b


def test_the_app_names_the_role_cut_each_roster_function_applies():
    assert "G: '15+ minutes'" in TS and "F: '15+ minutes'" in TS and "C: '15+ minutes'" in TS
    b = _bn_body("ncaaf")
    assert "WHEN 'RB' THEN COALESCE(g.carries,0) + COALESCE(g.receptions,0) >= 6" in b
    assert "RB: '6+ carries and catches'" in TS
    assert "WHEN 'WR' THEN COALESCE(g.receptions,0) >= 1" in b and "WR: '1+ catch'" in TS
    assert "WHEN 'TE' THEN COALESCE(g.receptions,0) >= 1" in b and "TE: '1+ catch'" in TS
    assert "ELSE COALESCE(g.def_tackles,0) + COALESCE(g.def_sacks,0) >= 2" in b
    assert "DL: '2+ tackles or sacks'" in TS
    # QB is the same cut as the NFL's, so it reads the shared map.
    assert "WHEN 'QB' THEN COALESCE(g.attempts,0) >= 10" in b and "QB: '10+ pass attempts'" in TS


def test_every_roster_sport_chip_has_a_branch():
    catalog = CATALOG.read_text(encoding="utf-8")
    for sport, fn in (("NBA", "nba"), ("WNBA", "wnba"), ("NCAAF", "ncaaf")):
        keys = set(re.findall(rf"\{{ key: '(\w+)', label: '[^']*', sport: '{sport}'", catalog))
        assert keys, sport
        body = _bn_body(fn)
        for k in keys:
            assert f"WHEN '{k}'" in body, f"{sport} chip {k} has no branch"


def test_the_player_page_reads_its_own_position_by_key():
    q = QUERIES.read_text(encoding="utf-8")
    m = re.search(r"export async function fetchPlayerPositionGroup\(.*?\n\}\n", q, re.S)
    assert m
    body = m.group(0)
    assert ".from('player_positions')" in body
    assert ".eq('sport', sport)" in body and ".eq('player_id', playerId)" in body
    assert ".maybeSingle()" in body
    for s in ("nba", "wnba", "ncaaf"):
        assert f".rpc('position_vs_opponent_{s}'" in q


def test_ncaaf_ranks_only_opponents_with_three_games():
    """Measured 2026-10-06: 245 opponents in the 2026 college log, 74 with one
    game. A one-game sample keeps its average and gets no rank."""
    b = _bn_body("ncaaf")
    assert "count(DISTINCT ok.game_id)::int AS games" in b
    assert "CASE WHEN d.games >= 3 THEN" in b
    assert "PARTITION BY d.season, d.games >= 3" in b
    for s in ("nba", "wnba"):
        assert "d.games >= 3" not in _bn_body(s)


def test_a_failed_position_read_is_said_not_hidden():
    """No row = no card (the roster pull has not placed him). A failed read
    renders the section with an error line instead (UX_REVIEW §3)."""
    hook = HOOK.read_text(encoding="utf-8")
    assert ("isRosterSport && opponent && stat && !posGroup && (rosterPos.loading || rosterPos.error)"
            in hook)
    screen = SCREEN.read_text(encoding="utf-8")
    assert "<PositionVsOpponentPending" in screen
    card = CARD.read_text(encoding="utf-8")
    assert "Couldn't load this player's position. Pull down to retry." in card


def test_the_card_opens_on_last_season_only_when_the_season_has_not_started():
    """No games against THIS opponent is not 'the season has not started'.
    The auto-open requires seasonStarted === false (no final game for the
    sport). A first meeting stays on this season."""
    card = CARD.read_text(encoding="utf-8")
    ts = TS
    assert "if (state.seasonStarted === false && !hasThis && hasLast) choice = 'last';" in ts
    assert "if (!hasThis && hasLast) choice = 'last';" not in ts
    hook = HOOK.read_text(encoding="utf-8")
    queries = QUERIES.read_text(encoding="utf-8")
    assert "fetchSeasonStarted(" in hook
    assert ".not('home_win', 'is', null)" in queries
    assert ".limit(1)" in queries.split("export async function fetchSeasonStarted")[1].split("export async function")[0]
    # The screen reuses this card for the next player. The once-only flag
    # lives in nextSeasonChoice, keyed on player + opponent, and a tap sets
    # readerPicked so that choice is not overwritten for the same player.
    assert "nextSeasonChoice(" in card
    assert "seasonSubjectKey(playerId, opponent)" in card
    assert "seasonStarted," in card
    assert "readerPicked.current = true;" in card
    assert "picked.current" not in card
    assert "toLowerCase()" not in card
    assert "emptySeasonMessage(" in card
    assert "choice === 'this' && hasAnySeason" in card
    assert "No ${opts.short} games vs ${opts.opponent} in our data, this season or last." in ts
