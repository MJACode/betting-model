"""One real event is one bet in the record, however many game ids it was bet under.

mike, 2026-10-09: "Count each fight once." Two UFC fights were each in the
settled record twice: `ufc_total_rounds` scored both games rows of one fight
(fighters swapped; an Eastern and a UTC date) and both copies settled WIN.

    kept 332605  UFC_2026-06-20_kevin-borjas_andre-lima          mark 332615
    kept 524487  UFC_2026-07-18_kamaru-usman_dricus-du-plessis   mark 530849

The extra copy is MARKED (condition_status = config.DUPLICATE_STATUS), never
re-graded, and every record surface skips the marker: the two published views,
the Discord recap, model_quality, the 250-bet review, the monitor dashboard
(both halves), the probability calibration, and the app's record filter, team
record, player record and settled-pick cache. These tests pin each surface,
the marking migration, the view patch, and the rule for which copy stays.
"""
from __future__ import annotations

import inspect
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import config
from tracking import record_duplicates as rd

ROOT = Path(__file__).resolve().parents[1]
MIG_DIR = ROOT / "data" / "migrations"
MARK = MIG_DIR / "record_counts_each_event_once_2026_10_09.sql"
VIEWS = MIG_DIR / "record_views_count_each_event_once_2026_10_09.sql"
LIB = ROOT / "mobile" / "src" / "lib"

CLAUSE = "condition_status IS DISTINCT FROM 'DUPLICATE'"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(sql: str) -> str:
    """SQL minus comment lines, so a comment cannot satisfy a test."""
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


# ── the shared predicate ──────────────────────────────────────────────────────

def test_the_marker_is_one_constant_and_one_predicate():
    assert config.DUPLICATE_STATUS == "DUPLICATE"
    sql = config.duplicate_copy_exclusion_sql("p")
    assert sql.lstrip().startswith("AND")
    assert f"p.{CLAUSE}" in sql


def test_the_predicate_keeps_rows_with_no_marker():
    """`<>` would drop every NULL condition_status, i.e. almost every pick."""
    sql = config.duplicate_copy_exclusion_sql("x")
    assert "IS DISTINCT FROM" in sql and "<>" not in sql
    assert "x.condition_status" in sql


# ── every server-side record surface ──────────────────────────────────────────

def test_the_discord_recap_counts_each_event_once():
    from tracking.discord_notifier import _SETTLED_SQL
    assert config.duplicate_copy_exclusion_sql("p") in _SETTLED_SQL


def test_the_recap_query_counts_the_kept_copy_and_not_the_marked_one():
    """Behavioural, on SQLite: the recap's own SQL over the June pair, plus a
    VOID and an NCAAF 'GONE' row (a live state on a real pick, which counts)."""
    import sqlite3
    from tracking.discord_notifier import _SETTLED_SQL
    if sqlite3.sqlite_version_info < (3, 39):
        pytest.skip("IS DISTINCT FROM needs SQLite >= 3.39")
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE picks (pick_id, sport, model_id, result,
                  kelly_fraction, dk_odds, clv_pct, is_live, game_date,
                  signal_type, downgrade_reason, condition_status)""")
    rows = [
        (332605, "UFC", "ufc_total_rounds", "WIN", 0.02, -166, None, 0, "2026-06-20", "BET", None, None),
        (332615, "UFC", "ufc_total_rounds", "WIN", 0.02, -130, None, 0, "2026-06-20", "BET", None, "DUPLICATE"),
        (9, "UFC", "ufc_total_rounds", "NO_ACTION", 0.02, -110, None, 0, "2026-06-20", "BET", None, "VOID"),
        (10, "NCAAF", "ncaaf_spread", "LOSS", 0.02, -110, None, 0, "2026-06-20", "BET", None, "GONE"),
    ]
    db.executemany("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    sql = _SETTLED_SQL.format(window="= ?").replace("%%", "%")
    got = sorted((r[1], r[4]) for r in db.execute(sql, ("2026-06-20",)).fetchall())
    assert got == [("ncaaf_spread", -110), ("ufc_total_rounds", -166)]


def test_model_quality_counts_each_event_once():
    from tracking import model_quality
    src = inspect.getsource(model_quality.run_model_quality)
    line = next(l for l in src.splitlines() if l.strip().startswith("excl = "))
    assert 'duplicate_copy_exclusion_sql("p")' in line
    assert 'record_exclusion_sql("p")' in line


class _CaptureConn:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params or ())))
        rows = self.rows

        class _C:
            def fetchall(self_inner):
                return rows

            def fetchone(self_inner):
                return rows[0] if rows else None
        return _C()


def test_the_250_bet_review_counts_each_event_once():
    from tracking import threshold_review
    conn = _CaptureConn()
    threshold_review._slate(conn)
    sql, params = conn.calls[0]
    assert "condition_status IS DISTINCT FROM %s" in _code(sql)
    assert config.DUPLICATE_STATUS in params


def test_the_monitor_dashboard_picks_arm_counts_each_event_once():
    """The arm that grades UFC from picks. It showed ufc_total_rounds at
    14 settled 9-5 on 2026-10-09; once each fight counts once, 12 settled 7-5."""
    from monitoring import store
    from tests.test_monitoring import FakeConn
    conn = FakeConn([])
    store.model_performance(conn)
    sql = conn.queries[0]
    arm = sql[sql.index("FROM picks p"):]
    arm = arm[:arm.index("GROUP BY")]
    assert config.duplicate_copy_exclusion_sql("p").strip() in arm


def test_the_monitor_dashboard_box_score_arm_counts_each_event_once():
    """The arm that reads mv_scored_pick_outcomes (MLB, WNBA). The matview
    re-grades from box scores and carries no pick-level marker, so the copy is
    dropped through a join back to its pick. LEFT JOIN: a graded row whose
    pick is gone stays counted."""
    from monitoring import store
    from tests.test_monitoring import FakeConn
    conn = FakeConn([])
    store.model_performance(conn)
    sql = conn.queries[0]
    arm = sql[sql.index("FROM mv_scored_pick_outcomes o"):]
    arm = arm[:arm.index("GROUP BY")]
    assert "LEFT JOIN picks pk ON pk.pick_id = o.pick_id" in arm
    assert config.duplicate_copy_exclusion_sql("pk").strip() in arm


class _RecordingConn:
    def __init__(self):
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))
        return self

    def fetchall(self):
        return []


@pytest.mark.parametrize("model_id", ["ufc_total_rounds", "mlb_live_total_runs"])
def test_the_probability_calibration_counts_each_event_once(model_id):
    """The calibration sets the betting threshold for every UFC, NCAAF, NFL and
    in-play model from graded picks. Both reads of the picks table skip the
    copy: ufc_total_rounds read the June Borjas-Lima WIN twice (8 graded bets,
    4 won; 7 and 3 once it counts once, measured 2026-10-09)."""
    from models import probability_calibration as pc
    conn = _RecordingConn()
    pc.fetch_graded(conn, model_id, "2026-06-20")
    assert "FROM picks" in conn.sql[0]
    assert "AND picks.condition_status IS DISTINCT FROM 'DUPLICATE'" in conn.sql[0]


# ── the published views ───────────────────────────────────────────────────────

def test_both_migrations_are_registered_after_every_owner_of_the_views():
    """An unregistered migration never runs; one ordered before an owner of
    the views is overwritten by it on the next pass."""
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MARK.exists() and VIEWS.exists()
    strike = ACTIVE_MIGRATIONS.index("record_strikes_nfl_live_prop_2026_10_04.sql")
    assert ACTIVE_MIGRATIONS.index(MARK.name) > strike
    assert ACTIVE_MIGRATIONS.index(VIEWS.name) > strike


def test_the_view_patch_adds_the_clause_to_both_published_views():
    code = _code(_read(VIEWS))
    assert "ARRAY['v_public_track_record', 'v_public_track_record_daily']" in code
    # The clause it splices in front of GROUP BY ('' is an escaped quote).
    assert "AND condition_status IS DISTINCT FROM ''DUPLICATE''::text" in code
    assert "GROUP BY" in code


def test_the_view_patch_is_idempotent_and_keeps_the_grants():
    code = _code(_read(VIEWS))
    assert "IF position('DUPLICATE' in d) > 0 THEN" in code
    assert "CONTINUE" in code
    assert "security_invoker = on" in code
    assert "GRANT SELECT ON public.%I TO anon, authenticated" in code
    assert code.count("DO $mig$") == 1, "view migrations must be ONE statement"


def test_the_view_patch_does_not_touch_the_sweep_views():
    """The sweep universe re-cuts by design (CLAUDE.md 7) and is not a record."""
    code = _code(_read(VIEWS))
    for view in ("mv_scored_pick_outcomes", "v_model_full_outcome_record",
                 "v_model_full_outcome_picks"):
        assert view not in code


# ── the marking migration ─────────────────────────────────────────────────────

def _updates(sql: str) -> list[str]:
    code = _code(sql)
    return re.findall(r"UPDATE public\.picks x(.*?);\s*\n\s*GET DIAGNOSTICS",
                      code, re.S)


def test_the_migration_marks_exactly_the_two_extra_copies():
    updates = _updates(_read(MARK))
    assert len(updates) == 2
    marked = {int(m) for u in updates for m in re.findall(r"x\.pick_id = (\d+)", u)}
    assert marked == {332615, 530849}


def test_the_migration_never_touches_a_result_a_price_or_a_time():
    """mike: count each fight once, leaving the picks themselves untouched."""
    for u in _updates(_read(MARK)):
        set_clause = u[u.index("SET"):u.index("WHERE")]
        assigned = set(re.findall(r"(\w+)\s*=", set_clause))
        assert assigned == {"condition_status", "condition_note"}, assigned
        assert "'DUPLICATE'" in set_clause
        assert "mike, 2026-10-09" in set_clause


def test_the_migration_is_guarded_so_a_second_pass_is_a_no_op():
    for u in _updates(_read(MARK)):
        where = u[u.index("WHERE"):]
        assert "x.condition_status IS NULL" in where
        assert "x.result IN ('WIN', 'LOSS', 'PUSH')" in where
        assert "x.signal_type = 'BET'" in where
        assert "x.model_id = 'ufc_total_rounds'" in where
        # The kept copy must still be there, settled and unmarked.
        assert "EXISTS (SELECT 1 FROM public.picks k" in where
        assert "k.condition_status IS NULL" in where


def test_the_migration_header_quotes_the_measured_numbers():
    """The migration file is the permanent record of this change; its numbers
    must be the ones measured (and quoted in store.py and the session log)."""
    header = "\n".join(l for l in _read(MARK).splitlines() if l.lstrip().startswith("--"))
    header = " ".join(header.replace("--", " ").split())
    assert ("14 settled 9-5 (-1.09u, 8 priced) to 12 settled 7-5 "
            "(-1.86u, 7 priced)") in header
    assert "13 settled 8-5" not in header and "11 settled 6-5" not in header


# ── which copy stays ──────────────────────────────────────────────────────────

# The four rows as read from production, 2026-10-09 (read-only SQL).
JUNE = (
    {"pick_id": 332605, "created_at": "2026-06-20 22:38:42.060968+00", "posted": False},
    {"pick_id": 332615, "created_at": "2026-06-20 22:38:42.060968+00", "posted": False},
)
JULY = (
    {"pick_id": 524487, "created_at": "2026-07-12 20:49:05.91343+00", "posted": False},
    {"pick_id": 530849, "created_at": "2026-07-19 03:50:46.752974+00", "posted": False},
)


@pytest.mark.parametrize("pair,kept_id,extra_id", [(JUNE, 332605, 332615),
                                                   (JULY, 524487, 530849)])
def test_the_rule_keeps_the_copies_the_migration_keeps(pair, kept_id, extra_id):
    for a, b in (pair, pair[::-1]):
        kept, extra = rd.choose_kept(a, b)
        assert (kept["pick_id"], extra["pick_id"]) == (kept_id, extra_id)
    code = _code(_read(MARK))
    assert f"x.pick_id = {extra_id}" in code and f"k.pick_id = {kept_id}" in code


def test_a_posted_copy_stays_even_when_it_was_written_later():
    early = {"pick_id": 1, "created_at": "2026-09-01 10:00:00+00", "posted": False}
    late = {"pick_id": 2, "created_at": "2026-09-01 12:00:00+00", "posted": True}
    assert rd.choose_kept(early, late)[0]["pick_id"] == 2


def test_the_earlier_copy_stays_and_compares_instants_not_text():
    """'+00' and '-04:00' stamps compare as instants: 09:00-04:00 is 13:00Z."""
    utc = {"pick_id": 1, "created_at": "2026-09-01 12:30:00+00", "posted": False}
    et = {"pick_id": 2, "created_at": "2026-09-01T09:00:00-04:00", "posted": False}
    assert rd.choose_kept(et, utc)[0]["pick_id"] == 1


def test_an_unreadable_stamp_never_wins():
    bad = {"pick_id": 1, "created_at": "not a time", "posted": False}
    ok = {"pick_id": 2, "created_at": "2026-09-01 12:00:00+00", "posted": False}
    assert rd.choose_kept(bad, ok)[0]["pick_id"] == 2


def test_the_finder_reports_which_copy_to_mark():
    row = ("UFC", "ufc_total_rounds",
           332605, "UFC_2026-06-20_kevin-borjas_andre-lima",
           "2026-06-20 22:38:42.060968+00", False,
           332615, "UFC_2026-06-20_andre-lima_kevin-borjas",
           "2026-06-20 22:38:42.060968+00", False)
    pairs = rd.find_duplicate_pairs(_CaptureConn([row]))
    assert [(p["kept"]["pick_id"], p["extra"]["pick_id"]) for p in pairs] == [(332605, 332615)]
    assert rd.describe(pairs) == "ufc_total_rounds 332615 (keep 332605)"


# ── when two rows are one event ───────────────────────────────────────────────

def test_the_finder_skips_copies_already_marked():
    assert config.duplicate_copy_exclusion_sql("p") in rd.DUPLICATE_PAIRS_SQL


def test_the_finder_matches_the_same_pick_on_the_same_two_sides_either_way_round():
    sql = rd.DUPLICATE_PAIRS_SQL
    assert "LEAST(g.home_team, g.away_team)" in sql
    assert "GREATEST(g.home_team, g.away_team)" in sql
    assert "a.model_id = b.model_id" in sql
    from tracking.publish_keys import KEY_PARTS
    for part in KEY_PARTS:      # one player's prop is not another's
        assert f"COALESCE(a.{part}, '') = COALESCE(b.{part}, '')" in sql
    assert "ABS(a.game_date::date - b.game_date::date) <= 1" in sql


def test_a_series_sport_needs_the_same_start_and_no_conflicting_final():
    """MLB plays the same opponent on consecutive days and in doubleheaders, so
    the date alone would call two real games one event."""
    assert rd.NO_SERIES_SPORTS == ("UFC", "NCAAF", "NFL")
    sql = rd.DUPLICATE_PAIRS_SQL
    assert "a.sport IN ('UFC', 'NCAAF', 'NFL')" in sql
    assert f"< {rd.SERIES_WINDOW_HOURS} * 3600" in sql
    assert rd.SERIES_WINDOW_HOURS < 16, "an MLB series game can start 16.3h later"
    assert "a.lo <> b.lo OR a.hi <> b.hi" in sql


def test_an_in_play_pick_must_also_be_on_the_same_side():
    sql = rd.DUPLICATE_PAIRS_SQL
    assert "WHEN 'home' THEN g.home_team" in sql and "WHEN 'away' THEN g.away_team" in sql
    assert "(a.is_live IS NOT TRUE OR a.side = b.side)" in sql


def test_the_health_check_reports_and_never_writes():
    src = _read(ROOT / "tracking" / "system_health.py")
    block = src[src.index("# ── One bet per real event"):src.index("# ── One games row per NCAAF")]
    assert '"one_pick_per_event"' in block
    assert "find_duplicate_pairs(conn)" in block
    assert "UPDATE" not in block and "INSERT" not in block


# ── the app ───────────────────────────────────────────────────────────────────

def test_the_app_marker_is_generated_from_config():
    gen = _read(LIB / "thresholds.generated.ts")
    assert f"export const DUPLICATE_STATUS = '{config.DUPLICATE_STATUS}';" in gen


def test_the_app_record_filter_skips_the_extra_copy():
    src = _read(LIB / "thresholds.ts")
    body = src[src.index("export function passesRecordFilter"):]
    body = body[:body.index("\n}")]
    assert "if (isDuplicateCopy(p)) return false;" in body
    helper = src[src.index("export function isDuplicateCopy"):]
    assert "p.condition_status === DUPLICATE_STATUS" in helper[:helper.index("\n}")]


def test_the_player_record_skips_the_extra_copy():
    """playerPickRecord re-implements the record filter inline."""
    src = _read(LIB / "playerDetail.ts")
    body = src[src.index("export function playerPickRecord"):]
    assert "if (isDuplicateCopy(p)) continue;" in body[:body.index("\n}")]


def _fn(src: str, sig: str) -> str:
    m = re.search(re.escape(sig) + r".*?\n\}\n", src, re.S)
    assert m, f"{sig} is missing"
    return m.group(0)


def test_the_team_and_player_records_skip_the_extra_copy():
    """Both re-implement the record filter inline. The team page is where an
    NCAAF copy (an Eastern and a UTC date for one game) would land."""
    team = _fn(_read(LIB / "teamDetail.ts"), "export function teamPickRecords(")
    player = _fn(_read(LIB / "playerDetail.ts"), "export function playerPickRecord(")
    for name, body in (("teamPickRecords", team), ("playerPickRecord", player)):
        assert "if (isDuplicateCopy(p)) continue;" in body, name


def test_the_team_and_player_record_reads_drop_the_extra_copy_on_the_server():
    q = _read(LIB / "queries.ts")
    assert ("export const NOT_DUPLICATE_COPY = "
            "`condition_status.is.null,condition_status.neq.\"${DUPLICATE_STATUS}\"`;"
            in q), "NULL must pass explicitly: neq alone drops every unmarked row"
    for sig in ("export async function fetchSettledGamePicksForGames(",
                "export async function fetchSettledPropPicksForPlayer("):
        body = _fn(q, sig)
        assert ".or(NOT_DUPLICATE_COPY)" in body, sig
        assert ".or(NOT_PAUSED_ROW)" in body, sig
        assert "!isDuplicateCopy(p)" in body, f"{sig}: filter the rows too"


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_the_app_record_filter_behaves(tmp_path: Path):
    """Run the real passesRecordFilter under node's type stripping."""
    for name in ("thresholds.ts", "thresholds.generated.ts", "decisionPrice.ts",
                 "discordPublish.ts", "format.ts"):
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", _read(LIB / name))
        (tmp_path / name).write_text(src, encoding="utf-8")
    script = """
import { passesRecordFilter, isDuplicateCopy } from './thresholds.ts';
const bet = { model_id: 'ufc_total_rounds', signal_type: 'BET', is_live: false,
              downgrade_reason: null, condition_status: null };
const out = {
  plain: passesRecordFilter(bet),
  duplicate: passesRecordFilter({ ...bet, condition_status: 'DUPLICATE' }),
  voided: passesRecordFilter({ ...bet, condition_status: 'VOID' }),
  ncaafGone: passesRecordFilter({ ...bet, condition_status: 'GONE' }),
  helper: isDuplicateCopy({ condition_status: 'DUPLICATE' }),
};
console.log(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    got = proc.stdout.strip().splitlines()[-1]
    assert got == ('{"plain":true,"duplicate":false,"voided":false,'
                   '"ncaafGone":true,"helper":true}'), got


def _copy_for_node(tmp_path: Path, names: tuple[str, ...]) -> None:
    """Copy lib files so node can import them: './x' and '@/lib/x' become
    './x.ts'. Type-only imports (@/types, @/hooks) are erased by node."""
    for name in names:
        src = _read(LIB / name)
        src = re.sub(r"from '\./([\w.]+)';", r"from './\1.ts';", src)
        src = re.sub(r"from '@/lib/([\w.]+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")


def _node(tmp_path: Path, script: str) -> str:
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip().splitlines()[-1]


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_the_team_record_counts_the_kept_copy_once(tmp_path: Path):
    """Run the real teamPickRecords: one NCAAF game under an Eastern and a UTC
    date, the same bet on both, the extra copy marked. One bet counts."""
    _copy_for_node(tmp_path, ("teamDetail.ts", "format.ts", "decisionPrice.ts",
                              "thresholds.ts", "thresholds.generated.ts",
                              "discordPublish.ts", "teamStatCatalog.ts", "teamBoard.ts"))
    script = """
import { teamPickRecords } from './teamDetail.ts';
const games = [
  { game_id: 'NCAAF_2026-10-03_ohio-state_michigan', home_team: 'Ohio State', away_team: 'Michigan' },
  { game_id: 'NCAAF_2026-10-04_ohio-state_michigan', home_team: 'Ohio State', away_team: 'Michigan' },
];
const bet = { model_id: 'ncaaf_spread', signal_type: 'BET', result: 'WIN', pick_side: 'home',
              player_id: null, dk_odds: -110, decision_odds: -110, profit_flat: 90.91,
              downgrade_reason: null, condition_status: null };
const picks = [
  { ...bet, pick_id: 1, game_id: games[0].game_id },
  { ...bet, pick_id: 2, game_id: games[1].game_id, condition_status: 'DUPLICATE' },
  { ...bet, pick_id: 3, game_id: games[1].game_id, pick_side: 'over', result: 'LOSS',
    profit_flat: -100, condition_status: 'GONE' },
];
const r = teamPickRecords(picks, games, 'Ohio State');
console.log(JSON.stringify({ settled: r.settled, onWins: r.on.wins, overLosses: r.over.losses }));
"""
    got = _node(tmp_path, script)
    # The marked copy is out; a live state on a real pick ('GONE') still counts.
    assert got == '{"settled":2,"onWins":1,"overLosses":1}', got


# ── the app's on-device cache ─────────────────────────────────────────────────

def test_every_load_reads_the_markers_and_applies_them_before_the_merge():
    """The cache re-downloads only the last 21 days and keeps older rows as
    first fetched. A copy is marked only after both copies settle and a
    migration merges, which can be weeks later, so every load reads the
    markers and copies them onto the cached rows."""
    hook = _read(ROOT / "mobile" / "src" / "hooks" / "useCustomModelStats.ts")
    body = _fn(hook, "export function useSettledPicksSincePaperStart(")
    assert "fetchSettledPickMarkers(PAPER_START).catch(() => null)" in body
    assert "mergeSettled(applySettledMarkers(cached, markers, PAPER_START), fresh, from)" in body
    q = _fn(_read(LIB / "queries.ts"), "export async function fetchSettledPickMarkers(")
    assert "fetchAllPages<SettledPickMarker>(" in q, "the server caps a response at 1,000 rows"
    assert ".not('condition_status', 'is', null)" in q
    assert ".gte('game_date', since)" in q
    assert ".order('pick_id'" in q
    # Settled or not: a result filter would make the list incomplete for the
    # range, and a cached row missing from it is set back to null.
    assert "result" not in q.split("supabase", 1)[1]


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_marker_set_after_caching_reaches_the_cached_row(tmp_path: Path):
    """Run the real settledPickCache and settledPickMarkers the way the hook
    does. A copy cached unmarked on 09-05, more than 21 days before the newest
    cached day, is marked on the server later. Without the marker read the
    merge keeps it unmarked and the record counts it; with it, it is out."""
    _copy_for_node(tmp_path, ("settledPickCache.ts", "settledPickMarkers.ts", "recordStart.ts",
                              "format.ts", "decisionPrice.ts", "thresholds.ts",
                              "thresholds.generated.ts", "discordPublish.ts"))
    cache = tmp_path / "settledPickCache.ts"
    cache.write_text(_read(cache).replace(
        "from '@react-native-async-storage/async-storage';", "from './asyncStorage.ts';"),
        encoding="utf-8")
    (tmp_path / "asyncStorage.ts").write_text(
        "export default { getItem: async () => null, setItem: async () => {}, "
        "removeItem: async () => {} };\n", encoding="utf-8")
    script = """
import { mergeSettled, refreshFrom } from './settledPickCache.ts';
import { applySettledMarkers } from './settledPickMarkers.ts';
import { passesRecordFilter } from './thresholds.ts';
const bet = (id, date, cs = null) => ({ pick_id: id, game_date: date, result: 'WIN',
  model_id: 'ufc_total_rounds', signal_type: 'BET', is_live: false,
  downgrade_reason: null, condition_status: cs });
// Cached on an earlier load: the kept copy, the extra copy (not yet marked),
// a copy marked once and since rolled back, and the newest row.
const cached = [bet(1, '2026-09-05'), bet(2, '2026-09-05'), bet(3, '2026-09-06', 'DUPLICATE'),
                bet(4, '2026-09-07', 'VOID'), bet(9, '2026-10-08')];
const from = refreshFrom(cached, '2026-09-01');
const fresh = [bet(9, '2026-10-08'), bet(10, '2026-10-09')];
const markers = [{ pick_id: 2, condition_status: 'DUPLICATE' }, { pick_id: 4, condition_status: 'VOID' }];
const counted = (rows) => rows.filter(passesRecordFilter).map((r) => r.pick_id).sort((a, b) => a - b);
const status = (rows, id) => rows.find((r) => r.pick_id === id).condition_status;
const withMarkers = mergeSettled(applySettledMarkers(cached, markers, '2026-09-01'), fresh, from);
const without = mergeSettled(cached, fresh, from);
const failed = mergeSettled(applySettledMarkers(cached, null, '2026-09-01'), fresh, from);
console.log(JSON.stringify({
  from,
  withMarkers: counted(withMarkers), extra: status(withMarkers, 2), rolledBack: status(withMarkers, 3),
  without: counted(without),
  failed: counted(failed), failedKept: status(failed, 3),
}));
"""
    got = _node(tmp_path, script)
    assert got == ('{"from":"2026-09-17",'
                   '"withMarkers":[1,3,9,10],"extra":"DUPLICATE","rolledBack":null,'
                   '"without":[1,2,9,10],'
                   '"failed":[1,2,9,10],"failedKept":"DUPLICATE"}'), got


# ── the rule is where a session doing SQL will see it ─────────────────────────

def test_the_rule_is_in_claude_md():
    text = _read(ROOT / "CLAUDE.md")
    start = text.index("A SETTLED PICK LEAVES THE RECORD ONLY TWO WAYS")
    block = text[start:start + 2000]
    assert "condition_status='DUPLICATE'" in block


# ── custom models ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_a_custom_model_counts_the_kept_copy_once(tmp_path: Path):
    """The labelled copy keeps its real WIN, so a custom model's own W/L/P
    tally counted it until it learned the label (UX review, 2026-10-09)."""
    _copy_for_node(tmp_path, ("customModelBacktest.ts", "customModelFilters.ts",
                              "modelMeta.ts", "thresholds.ts", "thresholds.generated.ts",
                              "decisionPrice.ts", "discordPublish.ts", "format.ts"))
    script = """
import { computeCustomModelStats } from './customModelBacktest.ts';
const bet = { model_id: 'ufc_total_rounds', sport: 'UFC', signal_type: 'BET', result: 'WIN',
              pick_side: 'over', model_probability: 0.6, edge: 0.05, dk_odds: -130,
              decision_odds: -130, profit_flat: 76.92, is_live: false, downgrade_reason: null,
              condition_status: null, game_date: '2026-06-20' };
const settled = [
  { ...bet, pick_id: 332605, game_id: 'UFC_2026-06-20_kevin-borjas_andre-lima' },
  { ...bet, pick_id: 332615, game_id: 'UFC_2026-06-20_andre-lima_kevin-borjas',
    condition_status: 'DUPLICATE' },
];
const model = { id: 'm', name: 'm', rules: [{ model_id: 'ufc_total_rounds' }], filters: {} };
const s = computeCustomModelStats(model, settled);
console.log(JSON.stringify({ picks: s.picks, wins: s.wins }));
"""
    got = _node(tmp_path, script)
    assert got == '{"picks":1,"wins":1}', got


def test_the_custom_model_pick_list_skips_the_labelled_copy():
    hook = _read(ROOT / "mobile" / "src" / "hooks" / "useCustomModelStats.ts")
    assert "&& !isDuplicateCopy(p))" in hook
    assert "import { isDuplicateCopy } from '@/lib/thresholds';" in hook

