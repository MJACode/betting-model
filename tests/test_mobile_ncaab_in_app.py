"""NCAAB is a sport the app can show, so the NCAAB totals model's picks reach it.

Measured on origin/master b6c2af63 (2026-10-30), before this change:

- ``useSportFilter.SPORTS`` had no NCAAB chip, so no board could select it,
  and ``pushRoute.asSport`` (which validates against SPORTS) dropped
  ``sport: 'NCAAB'`` from a push.
- ``modelMeta.sportOfModel`` had no ``ncaab`` prefix, so an ``ncaab_*`` model
  fell through to its last line and was filed under MLB. ``ModelsScreen``
  keeps a second copy of that function with the same gap.
- ``useTodayPicks`` read today's date plus look-ahead cards for UFC, the NFL,
  NCAAF and the NHL only. The NCAAB totals card is planned to decide the
  evening before the game, so its picks would have been invisible until game
  day.
- The Stats reads fall through to the MLB views for a sport they do not name,
  so an NCAAB board would have asked for MLB rows.

The NCAAB model is planned as ``ncaab_over_under`` (the build plan's id). The
model's own pull request must use the same id: ``test_mobile_pick_categories``
fails the day config scores a model the app has no label for.

These are text checks, like the rest of the mobile tests: node is not on the
machine that runs this suite (CLAUDE.md section 1b), so the TypeScript is read,
not imported.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"
SPORT_FILTER = SRC / "hooks" / "useSportFilter.ts"
TODAY = SRC / "hooks" / "useTodayPicks.ts"
QUERIES = SRC / "lib" / "queries.ts"
MODEL_META = SRC / "lib" / "modelMeta.ts"
MODELS_SCREEN = SRC / "screens" / "ModelsScreen.tsx"
PUSH_ROUTE = SRC / "lib" / "pushRoute.ts"
FORMAT = SRC / "lib" / "format.ts"
DAILY = SRC / "lib" / "dailyResults.ts"
TEAM_FORM = SRC / "lib" / "teamForm.ts"
STAT_CATALOG = SRC / "lib" / "statCatalog.ts"
TEAM_STAT_CATALOG = SRC / "lib" / "teamStatCatalog.ts"
MARKETS = SRC / "lib" / "markets.ts"


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with
    # no encoding uses cp1252 and dies on box-drawing characters at collection
    # time (CLAUDE.md section 7).
    return path.read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    """The body of an exported function, up to the next top-level declaration."""
    m = re.search(rf"export (?:async )?function {name}\b", src)
    assert m, f"{name} not found"
    nxt = re.search(r"\n(?:export |const |function |async function |/\*\*|// )", src[m.end():])
    end = m.end() + nxt.start() if nxt else len(src)
    return src[m.start():end]


def _sports() -> list[str]:
    m = re.search(r"export const SPORTS:\s*Sport\[\]\s*=\s*\[(.*?)\]", _read(SPORT_FILTER), re.S)
    assert m, "SPORTS not found"
    return re.findall(r"'([A-Z]+)'", m.group(1))


# -- the sport exists ---------------------------------------------------------


def test_ncaab_is_a_sport_chip_beside_ncaaf():
    sports = _sports()
    assert "NCAAB" in sports, "NCAAB has no sport chip, so no board can show its picks"
    assert sports.index("NCAAB") == sports.index("NCAAF") + 1, sports
    union = re.search(r"export type Sport =([^;]*);", _read(SPORT_FILTER))
    assert union and "'NCAAB'" in union.group(1)


def test_a_push_naming_ncaab_switches_the_board_to_it():
    """asSport validates against SPORTS, so the chip is what lets the push in."""
    body = _fn(_read(PUSH_ROUTE), "routeForPush")
    assert "asSport(d.sport)" in body
    as_sport = re.search(r"function asSport\(.*?\n\}", _read(PUSH_ROUTE), re.S)
    assert as_sport and "SPORTS as string[]).includes(v)" in as_sport.group(0)
    assert "NCAAB" in _sports()


def test_an_ncaab_model_is_filed_under_ncaab_not_mlb():
    for path, name in ((MODEL_META, "sportOfModel"), (MODELS_SCREEN, "sportOf")):
        src = _read(path)
        m = re.search(rf"function {name}\(modelId: string\)[^{{]*\{{(.*?)\n\}}", src, re.S)
        assert m, f"{name} not found in {path.name}"
        body = m.group(1)
        assert "if (modelId.startsWith('ncaab')) return 'NCAAB';" in body, (
            f"{path.name} {name} has no ncaab prefix, so ncaab_* falls through to MLB"
        )
        # 'ncaab' must be tested before the line every unknown id falls to.
        assert body.index("'ncaab'") < body.index("return 'MLB'")


def test_ncaab_is_in_the_custom_model_catalog_order():
    src = _read(MODEL_META)
    union = re.search(r"export type BetTypeSport =([^;]*);", src)
    assert union and "'NCAAB'" in union.group(1)
    order = re.search(r"const BET_TYPE_SPORT_ORDER: BetTypeSport\[\] = \[(.*?)\];", src, re.S)
    assert order
    names = re.findall(r"'([A-Z]+)'", order.group(1))
    assert names.index("NCAAB") == names.index("NCAAF") + 1, names


def test_the_planned_totals_model_has_a_label_and_prices_totals():
    src = _read(MODEL_META)
    m = re.search(r"\n  ncaab_over_under: \{(.*?)\n  \},", src, re.S)
    assert m, "ncaab_over_under has no MODEL_META entry: its card would print the raw id"
    entry = m.group(1)
    assert "longLabel: 'NCAAB Totals'" in entry
    assert "shortLabel: 'O/U'" in entry
    assert "type: 'game'" in entry
    # gameMarketForModel reads the id: 'over_under' maps to the totals rows.
    # An id without it (ncaab_total_*) would fall to 'h2h' and every price,
    # movement and line-shop lookup would read moneyline rows.
    gm = _fn(_read(MARKETS), "gameMarketForModel")
    assert "if (modelId.includes('over_under')) return 'totals';" in gm


# -- the board reaches the evening-before pick --------------------------------


def test_the_today_board_fetches_ncaab_ahead():
    src = _read(TODAY)
    days = re.search(r"const NCAAB_AHEAD_DAYS = (\d+);", src)
    assert days, "NCAAB_AHEAD_DAYS missing from useTodayPicks"
    # The scorer's outer bound for the basketball sports. The planned card
    # writes the evening before, so 7 covers it with room for an earlier one.
    assert int(days.group(1)) == config.GAME_SCORE_AHEAD_DAYS
    assert "fetchUpcomingNcaabPicks(target, addDays(target, NCAAB_AHEAD_DAYS))" in src
    assert "swallow('the upcoming NCAAB card')" in src
    start = src.index("const merged = [")
    merged = src[start:src.index("\n", start)]
    assert "...ncaabRows" in merged, "the NCAAB card is fetched and then dropped"


def test_the_ncaab_look_ahead_reads_only_the_picks_games():
    """A full NCAAB week is too big to read by date window.

    Measured 2026-10-30 (Supabase, read only): 182 games on 2026-11-02; over
    2025-26 the biggest day had 4,417 main-market rows across all books and
    the biggest 7 days 10,424. The NCAAF and NHL look-aheads read every game
    in their window; for NCAAB that is up to eleven 1,000-row pages per mount.
    So the picks are read first and every other read asks only for the games
    those picks are on.
    """
    body = _fn(_read(QUERIES), "fetchUpcomingNcaabPicks")
    assert ".eq('sport', 'NCAAB')" in body
    assert ".gt('game_date', afterDate)" in body
    assert ".lte('game_date', throughDate)" in body
    assert ".gte('game_date', afterDate)" not in body
    # The picks read is drained, with a deterministic order: signals first so
    # a row cap could never cost a BET, then a unique key.
    assert "fetchAllPages<Pick>" in body
    assert ".order('signal_type', { ascending: true })" in body
    assert ".order('pick_id'" in body
    # No read is scoped by a date window over every NCAAB game.
    assert "like('game_id', 'NCAAB_%')" not in body
    for view in ("'games'", "'v_latest_dk_odds'", "'v_latest_odds_all_books'"):
        assert f".from({view})" in body, f"{view} read missing"
    assert body.count(".in('game_id', chunk)") == 3
    # No picks, no reads.
    assert "if (gameIds.length === 0) return [];" in body


def test_the_same_day_dk_read_is_drained():
    """The same-day DraftKings read was one unordered request.

    Measured 2026-10-30: 1,132 DraftKings rows in v_latest_dk_odds for
    game_date 2026-01-10, 1,103 for 2026-02-07, most of them NCAAB. PostgREST
    returns an arbitrary 1,000 of those and says nothing, so a line pill on any
    sport's card could go blank on a full college basketball day. The markets a
    pick reads (MAIN_GAME_ODDS_MARKETS) were 743 of the 1,132, so the read is
    narrowed to them as well as drained.
    """
    body = _fn(_read(QUERIES), "fetchPicksForDate")
    m = re.search(r"fetchAllPages<LatestDkOddsRow>\((.*?)\),\s*\n", body, re.S)
    assert m, "the same-day v_latest_dk_odds read is not paged"
    read = m.group(1)
    assert ".from('v_latest_dk_odds')" in read
    assert ".eq('game_date', date)" in read
    assert ".in('market', [...MAIN_GAME_ODDS_MARKETS])" in read
    assert ".order('game_id')" in read and ".order('market')" in read
    assert "supabase.from('v_latest_dk_odds').select(LATEST_ODDS_COLUMNS).eq('game_date', date)," not in body


# -- the rest of the app knows the sport --------------------------------------


def test_an_ncaab_game_leaves_the_board_and_stops_reading_live():
    src = _read(FORMAT)
    blind = re.search(r"const BLIND_LIVE_WINDOW_MS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert blind and re.search(r"\n  NCAAB: \d+ \* 3_600_000,", blind.group(1))
    dur = re.search(r"const GAME_DURATION_HOURS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert dur and re.search(r"\n  NCAAB: [\d.]+,", dur.group(1))


def test_the_daily_recap_and_form_strip_name_ncaab():
    order = re.search(r"const SPORT_ORDER: Record<string, number> = \{(.*?)\n\};", _read(DAILY), re.S)
    assert order and re.search(r"\n  NCAAB: \d+,", order.group(1))
    form = _fn(_read(TEAM_FORM), "teamScoreUnit")
    pts = form[form.index("case 'NBA':"):form.index("return 'PTS';")]
    assert "case 'NCAAB':" in pts, "an NCAAB form strip would read R, not PTS"


def test_the_stats_board_has_nothing_to_show_for_ncaab_and_asks_for_nothing():
    """No NCAAB player or team stats are in the app yet.

    The leaderboard catalog is empty for NCAAB (the Stats screen's "No player
    leaderboard" state), it has no team board, and every Stats read returns
    [] for it before a request: each of them otherwise falls through to a
    different sport's view.
    """
    cat = _read(STAT_CATALOG)
    groups = re.search(r"export const GROUP_ORDER: Record<Sport, StatGroup\[\]> = \{(.*?)\n\};", cat, re.S)
    assert groups and "\n  NCAAB: []," in groups.group(1)
    assert not re.search(r"sport: 'NCAAB'", cat), "a stat catalog entry for NCAAB has no data behind it"
    team = _read(TEAM_STAT_CATALOG)
    # The Teams board is the BALL list (TEAM_SPORTS = new Set(BALL)).
    assert "const TEAM_SPORTS = new Set<Sport>(BALL);" in team
    ball = re.search(r"const BALL: Sport\[\] = \[(.*?)\];", team)
    assert ball and "'NCAAB'" not in ball.group(1), "an NCAAB Teams board has no rows behind it"
    q = _read(QUERIES)
    # These three fall through to another sport's read (the MLB views, the
    # team board RPC) for a sport they do not name, so NCAAB returns first.
    for name in ("fetchSeasonTotals", "fetchWindowTotals"):
        assert re.search(r"if \(sport === 'GOLF' \|\| sport === 'NCAAB'\) return \[\];", _fn(q, name)), (
            f"{name} has no early return for NCAAB, so it reads the MLB view"
        )
    assert re.search(
        r"if \(sport === 'UFC' \|\| sport === 'GOLF' \|\| sport === 'NCAAB'\) return \{ season: null, rows: \[\] \};",
        _fn(q, "fetchTeamStats"),
    )
    # The Stats screen does not read a week of games for a sport it can only
    # show the empty state for.
    stats = _read(SRC / "screens" / "StatsScreen.tsx")
    slate = stats[stats.index("const slateKey = slateReadKey(sport, etDay);"):]
    slate = slate[:slate.index("fetchSlateGames(sport")]
    assert "if (!defaultStatFor(sport) && !supportsTeamBoard(sport)) {" in slate
    # These end on `return []` for every sport they do not name.
    for name in ("fetchRecentGames", "fetchSeasonStatValues", "fetchPositionVsOpponent"):
        body = _fn(q, name).rstrip()
        assert re.search(r"return \[\];(?: //[^\n]*)?\n\}$", body), f"{name} no longer ends on return []"
