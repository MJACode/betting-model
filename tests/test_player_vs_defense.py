"""Player page defense-toughness filter (Matt, 2026-11-07).

player_vs_defense_<sport> ranks each defense with the SAME role cut and stat
CASE as position_vs_opponent_<sport>, or the rank under a bar describes a
different population than the "same position vs opponent" card prints. The
rank runs the other way (1 = toughest) on purpose.

Not applied here. The worker applies ACTIVE_MIGRATIONS; this test reads the
files. The SQL was run read-only against production on 2026-11-07 (Kyrie
Irving points: Tough 38 games, 37 of 38 at 15+, 24.8 avg; BKN #7 of 30 after
8 games; 116 rows in 385 ms).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data/migrations/add_player_vs_defense_rpcs_2026_11_07.sql"
NFL_SIBLING = ROOT / "data/migrations/add_position_vs_opponent_nfl.sql"
BB_SIBLING = ROOT / "data/migrations/add_position_vs_opponent_bball_ncaaf.sql"
QUERIES = ROOT / "mobile/src/lib/queries.ts"
HOOK = ROOT / "mobile/src/hooks/usePlayerDetail.ts"
SCREEN = ROOT / "mobile/src/screens/PlayerStatsScreen.tsx"
CHART = ROOT / "mobile/src/components/HitRateChart.tsx"
MOBILE = ROOT / "mobile"

from tests._node import tsx_cmd  # noqa: E402

FUNCS = ("nba", "wnba", "nfl")
ARGS = "(text, text, text, integer[], integer, text)"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fn(text: str, name: str) -> str:
    """The body of one CREATE FUNCTION, from its name to its closing $fn$."""
    start = text.index(f"FUNCTION public.{name}(")
    body = text.index("AS $fn$", start)
    return text[start:text.index("$fn$", body + len("AS $fn$"))]


def _whens(text: str, needle: str) -> list[str]:
    start = text.find(needle)
    assert start != -1, needle
    body = text[start:text.find("END", start)]
    return [re.sub(r"\s+", " ", a).strip() for a in re.findall(r"WHEN\b.*", body)]


def _norm(arms: list[str]) -> list[str]:
    # The siblings alias the row `g`/`n`; ours aliases the player's own rows
    # `l`/`n` and the league rows `g`. Compare the arms with the alias removed.
    return [re.sub(r"\b[lgn]\.", "x.", a) for a in arms]


def test_registered_for_the_worker_and_the_app():
    vm = _read(ROOT / "data/view_migrations.py")
    start = vm.find("ACTIVE_MIGRATIONS: list[str] = [")
    names = re.findall(r'"([^"]+\.sql)"', vm[start:vm.find("\n]\n", start)])
    assert MIG.name in names
    # Reads player_positions, so after the file that creates it.
    assert names.index("add_player_positions.sql") < names.index(MIG.name)
    assert names[-1] == "published_record_units_2026_10_16.sql"
    anon = _read(ROOT / "data/anon_readable.py")
    code = _read(MIG)
    assert "v_public_track_record" not in code
    for s in FUNCS:
        assert f'"player_vs_defense_{s}"' in anon
        assert f"REVOKE ALL ON FUNCTION public.player_vs_defense_{s}{ARGS} FROM PUBLIC" in code
        assert f"GRANT EXECUTE ON FUNCTION public.player_vs_defense_{s}{ARGS} TO anon, authenticated" in code


def test_one_guarded_statement():
    lines = [ln for ln in _read(MIG).splitlines() if not ln.lstrip().startswith("--")]
    sql = "\n".join(lines).strip()
    assert sql.startswith("DO $mig$") and sql.endswith("$mig$;")
    assert sql.count("DO $mig$") == 1
    assert "player_vs_defense_nba/wnba/nfl already present — skipping" in sql
    assert sql.count("SECURITY INVOKER SET search_path = public, pg_temp") == 3


def test_rank_one_is_the_toughest_defense():
    code = _read(MIG)
    for s in FUNCS:
        body = _fn(code, f"player_vs_defense_{s}")
        assert "rank() OVER (PARTITION BY d.season ORDER BY d.avg_allowed ASC)" in body
        assert "DESC)::int AS def_rank" not in body
        # Ranked per season, and each game joins its OWN season's rank.
        assert "r.season = m.season AND r.defense = m.opp" in body
        # The last three seasons PLAYED, not the last three labels.
        assert "LIMIT GREATEST(p_season_count, 1)" in body


def test_basketball_cut_and_stats_match_the_card():
    new = _read(MIG)
    old = _read(BB_SIBLING)
    for s in ("nba", "wnba"):
        ours = _fn(new, f"player_vs_defense_{s}")
        theirs = _fn(old, f"position_vs_opponent_{s}")
        assert "COALESCE(g.minutes, 0) >= 15 AS has_role" in ours
        assert "COALESCE(g.minutes, 0) >= 15 AS has_role" in theirs
        league = ours[ours.index("q AS ("):]
        assert _norm(_whens(league, "WHEN 'points'")) == _norm(_whens(theirs, "WHEN 'points'"))
        mine = ours[:ours.index("played AS (")]
        assert _norm(_whens(mine, "WHEN 'points'")) == _norm(_whens(theirs, "WHEN 'points'"))
        assert f"pp.sport = '{s.upper()}'" in ours


def test_nfl_cut_and_stats_match_the_card():
    ours = _fn(_read(MIG), "player_vs_defense_nfl")
    theirs = _fn(_read(NFL_SIBLING), "position_vs_opponent_nfl")
    assert _norm(_whens(ours, "WHEN n.pos = 'QB'")) == _norm(_whens(theirs, "WHEN n.pos = 'QB'"))
    assert _norm(_whens(ours, "WHEN 'QB' THEN COALESCE(g.attempts,0)")) == _norm(
        _whens(theirs, "WHEN 'QB' THEN COALESCE(g.attempts,0)")
    )
    league = ours[ours.index("role AS ("):]
    assert _norm(_whens(league, "WHEN 'passing_yards'")) == _norm(_whens(theirs, "WHEN 'passing_yards'"))
    mine = ours[:ours.index("played AS (")]
    assert _norm(_whens(mine, "WHEN 'passing_yards'")) == _norm(_whens(theirs, "WHEN 'passing_yards'"))
    assert ours.count("COALESCE(n.season_type, 'REG') <> 'PRE'") == 2


def test_the_app_reads_and_draws_it():
    q = _read(QUERIES)
    for s in FUNCS:
        assert f"supabase.rpc('player_vs_defense_{s}'" in q
    hook = _read(HOOK)
    assert "fetchPlayerVsDefense(" in hook
    # Tagged with the query that produced it (stale rows must not be tiered).
    assert "defense.data.key === defenseKey" in hook
    screen = _read(SCREEN)
    assert "tierChartGames(defenseGames.games, defenseFilter, range)" in screen
    assert "openingDefenseFilter(defenseGames)" in screen
    # Never applied to H2H: one opponent is one tier.
    assert "!isH2H && defenseCounts != null" in screen
    # The chart holds its spinner while the read is in flight, so it never
    # draws the last-N games and then swaps tiers (UX review, 2026-11-07).
    assert "(!isH2H && defensePicked == null && detail.defensePending)" in screen
    assert "defensePending: defenseKey !== '' && !defenseFresh && defense.error == null" in hook
    # Amber only on navy (UX_REVIEW §2).
    tag = screen.split("nextTag: {", 1)[1].split("},", 1)[0]
    assert "colors.brandNavy" in tag
    chart = _read(CHART)
    assert "games!.every((g) => g.rank != null)" in chart


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_tier_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_defense_tier.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
