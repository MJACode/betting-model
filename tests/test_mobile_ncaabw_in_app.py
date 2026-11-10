"""NCAABW (women's college basketball) is a sport the app can show, so the
NCAABW totals model's picks reach it.

Measured on 93b032e3 (2026-11-10), before this change:

- ``useSportFilter.SPORTS`` had no NCAABW chip, so no board could select it,
  and ``pushRoute.asSport`` (which validates against SPORTS) dropped
  ``sport: 'NCAABW'`` from a push.
- **The trap.** ``'ncaabw_total_blend'.startsWith('ncaab')`` is true, so both
  prefix functions (``modelMeta.sportOfModel`` and ``ModelsScreen.sportOf``)
  filed every women's model under the MEN'S sport: the women's totals card
  would have sat on the NCAAB Models tab and in the NCAAB custom-model group.
- ``ncaabw_total_blend`` (``models/ncaabw_total_blend.py`` ``MODEL_ID``) had
  no label, so its card printed the raw id, and no named line in
  ``markets.ts``, so every price, movement and line-shop lookup read the
  moneyline rows.
- ``useTodayPicks`` had no women's look-ahead. DraftKings' first women's total
  came 1 to 6 Eastern dates before the game's date in 155 of 1,772 priced
  games (``scripts/ncaabw_total_card.py`` ``SLATE_DAYS``), so those picks
  would have been invisible until game day.
- The Stats reads fall through to the MLB views for a sport they do not name.
- The women's odds feed stores seven books on top of the usual ones
  (``config.NCAABW_EXTRA_BOOKMAKERS``); none is a book a pick may name. Read
  in production 2026-11-10 (Supabase, read only): ``v_latest_odds_all_books``
  held rows at all seven for the women's games of 2026-11-08 to 11-10. The
  app printed four of them as raw keys (``betonlineag``) and treated two
  (Bally Bet, Fliff) as books a member is sent to.

Women's college basketball has ONE model and nothing else in the app: no
player stats, no Teams board, no in-play model. Where the men's sport has
those, the women's takes the app's existing empty state.

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
from tests.test_mobile_ncaab_in_app import (  # noqa: E402
    DAILY,
    FORMAT,
    MARKETS,
    MODEL_META,
    MODELS_SCREEN,
    PUSH_ROUTE,
    QUERIES,
    ROOT,
    SPORT_FILTER,
    SRC,
    STAT_CATALOG,
    TEAM_FORM,
    TEAM_STAT_CATALOG,
    TODAY,
    _fn,
    _read,
    _sports,
)

STATS_SCREEN = SRC / "screens" / "StatsScreen.tsx"
PLAYER_LOG = SRC / "lib" / "playerLog.ts"
LIVE_SPORTS = SRC / "lib" / "liveSports.ts"
TOTAL_CARD = ROOT / "scripts" / "ncaabw_total_card.py"

# The id the NCAABW totals model writes its picks under
# (models/ncaabw_total_blend.py MODEL_ID).
NCAABW_TOTALS_ID = "ncaabw_total_blend"


# -- the sport exists ---------------------------------------------------------


def test_ncaabw_is_a_sport_chip_right_after_ncaab():
    sports = _sports()
    assert "NCAABW" in sports, "NCAABW has no sport chip, so no board can show its picks"
    assert sports.index("NCAABW") == sports.index("NCAAB") + 1, sports
    union = re.search(r"export type Sport =([^;]*);", _read(SPORT_FILTER))
    assert union and "'NCAABW'" in union.group(1)


def test_a_push_naming_ncaabw_switches_the_board_to_it():
    """asSport validates against SPORTS, so the chip is what lets the push in."""
    body = _fn(_read(PUSH_ROUTE), "routeForPush")
    assert "asSport(d.sport)" in body
    as_sport = re.search(r"function asSport\(.*?\n\}", _read(PUSH_ROUTE), re.S)
    assert as_sport and "SPORTS as string[]).includes(v)" in as_sport.group(0)
    assert "NCAABW" in _sports()


# -- the trap: 'ncaabw_...' starts with 'ncaab' -------------------------------


def _prefix_function(path: Path, name: str) -> tuple[list[tuple[str, str]], str, str]:
    """A sport-from-model-id function: its prefix tests in order, the sport an
    id matching none of them gets, and its body."""
    src = _read(path)
    m = re.search(rf"function {name}\(modelId: string\)[^{{]*\{{(.*?)\n\}}", src, re.S)
    assert m, f"{name} not found in {path.name}"
    body = m.group(1)
    chain = re.findall(r"if \(modelId\.startsWith\('([a-z]+)'\)\) return '([A-Z]+)';", body)
    last = re.search(r"\n  return '([A-Z]+)';\s*$", body)
    assert chain and last, f"{name} is no longer a chain of prefix tests"
    # Every test in the body is one this reads, so running the chain below is
    # running the function.
    assert body.count("startsWith(") == len(chain), f"{name} has a prefix test this check cannot read"
    return chain, last.group(1), body


def _sport_of(chain: list[tuple[str, str]], fallback: str, model_id: str) -> str:
    for prefix, sport in chain:
        if model_id.startswith(prefix):
            return sport
    return fallback


def test_an_ncaabw_model_is_filed_under_ncaabw_and_not_under_the_mens_sport():
    """Run each prefix function's own chain on the ids, in its own order.

    The women's line has to come BEFORE the men's: every women's id starts
    with 'ncaab' too. Asserting that the women's line exists is not enough,
    which is why the chain is run rather than searched.
    """
    for path, name in ((MODEL_META, "sportOfModel"), (MODELS_SCREEN, "sportOf")):
        chain, fallback, body = _prefix_function(path, name)
        where = f"{path.name} {name}"
        assert _sport_of(chain, fallback, NCAABW_TOTALS_ID) == "NCAABW", (
            f"{where} files {NCAABW_TOTALS_ID} under {_sport_of(chain, fallback, NCAABW_TOTALS_ID)}"
        )
        # Any women's id, not only the one model there is today.
        assert _sport_of(chain, fallback, "ncaabw_spread_market") == "NCAABW", where
        # The men's ids stay where they were.
        assert _sport_of(chain, fallback, "ncaab_total_blend") == "NCAAB", where
        assert _sport_of(chain, fallback, "ncaab_live_spread_h1") == "NCAAB", where
        assert _sport_of(chain, fallback, "ncaaf_spread") == "NCAAF", where
        assert "if (modelId.startsWith('ncaabw')) return 'NCAABW';" in body
        assert body.index("'ncaabw'") < body.index("'ncaab')"), (
            f"{where} tests 'ncaab' before 'ncaabw', so a women's id never reaches its own line"
        )
        # Every model config can score is filed under the sport its id names.
        for model_id in config.ACTION_THRESHOLDS:
            want = model_id.split("_")[0].upper()
            assert _sport_of(chain, fallback, model_id) == want, f"{where}: {model_id}"


def test_no_other_prefix_test_can_file_a_womens_id_under_the_mens_sport():
    """A sweep of mobile/src for every way a men's prefix could catch a
    women's id or game.

    Two functions test the model-id prefix today, and each must test the
    women's first. A new one, a regex on the id, or a SQL LIKE on the game id
    ('NCAAB_%' matches 'NCAABW_...': the underscore is LIKE's any-one-character)
    would be the same bug in a new place.
    """
    mens = re.compile(r"startsWith\((['\"])ncaab_?\1\)", re.I)
    womens = re.compile(r"startsWith\((['\"])ncaabw_?\1\)", re.I)
    # A regex anchored on the men's prefix, a substring test, and a LIKE
    # pattern, in either case: each matches the women's ids and game ids too.
    banned = (r"/\^ncaab", r"includes\(['\"]ncaab_?['\"]\)", r"['\"]ncaab_%['\"]")
    found = {}
    for path in sorted(SRC.rglob("*.ts*")):
        # Code only: a comment may name the pattern it warns about.
        src = "\n".join(
            line for line in _read(path).splitlines() if not line.lstrip().startswith(("//", "*", "/*"))
        )
        rel = path.relative_to(SRC).as_posix()
        for pattern in banned:
            assert not re.search(pattern, src, re.I), f"{rel}: {pattern} also matches the women's sport"
        hits = [m.start() for m in mens.finditer(src)]
        if not hits:
            continue
        found[rel] = len(hits)
        firsts = [m.start() for m in womens.finditer(src)]
        assert len(firsts) == len(hits), f"{rel}: a men's prefix test with no women's test beside it"
        for w, m in zip(firsts, hits):
            assert w < m, f"{rel}: 'ncaab' is tested before 'ncaabw'"
    assert found == {"lib/modelMeta.ts": 1, "screens/ModelsScreen.tsx": 1}, found


def test_ncaabw_is_in_the_custom_model_catalog_order():
    src = _read(MODEL_META)
    union = re.search(r"export type BetTypeSport =([^;]*);", src)
    assert union and "'NCAABW'" in union.group(1)
    order = re.search(r"const BET_TYPE_SPORT_ORDER: BetTypeSport\[\] = \[(.*?)\];", src, re.S)
    assert order
    names = re.findall(r"'([A-Z]+)'", order.group(1))
    assert names.index("NCAABW") == names.index("NCAAB") + 1, names


# -- the one model ------------------------------------------------------------


def test_the_totals_model_has_a_label_under_the_id_it_writes():
    src = _read(MODEL_META)
    m = re.search(rf"\n  {NCAABW_TOTALS_ID}: \{{(.*?)\n  \}},", src, re.S)
    assert m, f"{NCAABW_TOTALS_ID} has no MODEL_META entry: its card would print the raw id"
    entry = m.group(1)
    # The record views name the model with exactly this string.
    assert "longLabel: 'NCAABW Totals'" in entry
    assert "shortLabel: 'O/U'" in entry
    assert "type: 'game'" in entry
    # One women's model: a label under any other women's id is a card on the
    # Models tab that never gets a pick.
    labelled = set(re.findall(r"\n  (ncaabw_[a-z0-9_]+): \{", src))
    assert labelled == {NCAABW_TOTALS_ID}, labelled
    scored = {m for m in config.ACTION_THRESHOLDS if m.startswith("ncaabw_")}
    assert scored <= labelled, f"config scores {sorted(scored - labelled)} with no label in the app"


def test_the_totals_model_reads_the_totals_rows():
    """The id has neither 'over_under' nor 'spread' in it (the men's trap).

    Without a named line it falls to 'h2h' (every price, movement and
    line-shop lookup reads the moneyline rows) and to 'other' (a parlay treats
    the total as independent of the same game's other legs).
    """
    markets = _read(MARKETS)
    gm = _fn(markets, "gameMarketForModel")
    assert f"if (modelId === '{NCAABW_TOTALS_ID}') return 'totals';" in gm
    assert gm.index(f"'{NCAABW_TOTALS_ID}'") < gm.rindex("return 'h2h';")
    mc = _fn(markets, "marketClassForModel")
    assert f"if (modelId === '{NCAABW_TOTALS_ID}') return 'game_total';" in mc
    assert mc.index(f"'{NCAABW_TOTALS_ID}'") < mc.index("return 'other';\n}")


def _womens_timing_branch(src: str) -> str:
    body = _fn(src, "modelPageTiming")
    m = re.search(r"if \(GAME_DAY_FIRST_POST_TOTAL_MODELS\.includes\(modelId\)\) \{(.*?)\n  \}\n", body, re.S)
    assert m, "modelPageTiming has no branch for the women's totals model"
    return m.group(1)


def test_the_model_page_says_when_the_womens_total_is_decided():
    """The women's card decides like the men's (once, at DraftKings' first
    posted total, only while it stands) on a different clock, so it cannot
    share the men's sentences.

    DraftKings posted its first women's total 1 to 6 Eastern dates before the
    game in 155 of 1,772 priced games and on the game's own date in the rest
    (scripts/ncaabw_total_card.py SLATE_DAYS), where the men's is "most the
    day before". That first total stood a median 136 minutes in 2024-25 and 85
    in 2025-26 (docs/sports/ncaabw.md), and one in ten changed within 10
    minutes (the card's own header), where about half of the men's change
    within half an hour. The default copy (locks at the first scoring run,
    lines refresh hourly) is wrong for it too.
    """
    src = _read(MODEL_META)
    lst = re.search(r"const GAME_DAY_FIRST_POST_TOTAL_MODELS: readonly string\[\] = \[(.*?)\];", src, re.S)
    assert lst and f"'{NCAABW_TOTALS_ID}'" in lst.group(1)
    mens = re.search(r"const FIRST_POST_TOTAL_MODELS: readonly string\[\] = \[(.*?)\];", src, re.S)
    assert mens and NCAABW_TOTALS_ID not in mens.group(1), "the women's model would print the men's timing"
    body = _fn(src, "modelPageTiming")
    assert body.index("GAME_DAY_FIRST_POST_TOTAL_MODELS.includes(modelId)") < body.index(
        "title: 'Picks lock for the day'"
    )
    branch = _womens_timing_branch(src)
    assert "title: 'Decided when the total opens'" in branch
    flat = "".join(re.findall(r"'([^']*)'", branch))
    assert "at DraftKings’ opening total, usually within minutes of it posting" in flat
    assert "DraftKings opens most totals on the day of the game, some up to six days before" in flat
    assert "only if DraftKings still offers that opening total at the same prices" in flat
    assert "it skips the game" in flat
    assert "An opening total can change within minutes" in flat
    assert "check DraftKings’ total and price before you bet" in flat
    assert "never re-priced" in flat
    # The men's measurements, which are not the women's.
    for mens_only in ("the day before the game", "within half an hour"):
        assert mens_only not in flat, mens_only
    # No Eastern clock time: DraftKings posts at no fixed hour.
    for s in re.findall(r"'([^']*)'", branch):
        assert not re.search(r"\d\s?(?:am|pm)\b|\d:\d\d", s, re.I), s
    for stale in ("first time this model scores it today", "pipeline refresh", "hourly"):
        assert stale not in branch, stale


def test_the_pick_screen_says_posted_once_not_first_scoring_run():
    body = _fn(_read(MARKETS), "pickTimingInfo")
    chain = body[body.index("const nbaPosted ="):body.index("kind: 'posted',")]
    assert f"pick.model_id === '{NCAABW_TOTALS_ID}'" in chain
    m = re.search(rf"pick\.model_id === '{NCAABW_TOTALS_ID}'\s*\n\s*\? '([^']*)'", body)
    assert m, "the women's totals model's Pick Detail note has no sentence of its own"
    assert "An opening total can change within minutes" in m.group(1)
    assert "check DraftKings’ total and price before you bet" in m.group(1)


# -- the board reaches a pick written before game day --------------------------


def test_the_today_board_fetches_ncaabw_ahead():
    src = _read(TODAY)
    days = re.search(r"const NCAABW_AHEAD_DAYS = (\d+);", src)
    assert days, "NCAABW_AHEAD_DAYS missing from useTodayPicks"
    # The card's own slate window: a game is on the card's slate before its
    # first post can land, and the board must reach every date the card can
    # write. Raise the app's number whenever the card's is raised.
    slate = re.search(r"^SLATE_DAYS = (\d+)$", _read(TOTAL_CARD), re.M)
    assert slate, "scripts/ncaabw_total_card.py no longer names SLATE_DAYS"
    assert int(days.group(1)) >= int(slate.group(1)), (
        f"the board reads {days.group(1)} days ahead, the card writes up to {slate.group(1)}"
    )
    assert "fetchUpcomingNcaabwPicks(target, addDays(target, NCAABW_AHEAD_DAYS), (what, e) =>" in src
    assert "swallow('the upcoming NCAABW card')" in src
    start = src.index("const merged = [")
    merged = src[start:src.index("\n", start)]
    assert "...ncaabwRows" in merged, "the NCAABW card is fetched and then dropped"
    assert "...ncaabRows" in merged, "the men's card went missing"


def test_both_college_basketball_look_aheads_are_one_read_of_the_picks_own_games():
    """The women's look-ahead is the men's, with the sport passed in.

    Picks first, then only their games, then lines only for the games with a
    signal, 80 game ids a request. Read in production 2026-11-10 (Supabase,
    read only): 415 NCAABW games stored for 2026-11-10 to 11-17 and 163 on the
    biggest stored day, which a read by date window would pull whole; the
    priced women's games of 2026-11-08 held 162 all-books rows over 12 games,
    30 on the biggest.
    """
    q = _read(QUERIES)
    body = _fn(q, "fetchUpcomingCollegeBasketballPicks")
    assert "sport: 'NCAAB' | 'NCAABW'," in body
    assert ".eq('sport', sport)" in body
    assert ".gt('game_date', afterDate)" in body
    assert ".lte('game_date', throughDate)" in body
    assert "fetchAllPages<Pick>" in body
    assert ".order('signal_type', { ascending: true })" in body
    assert ".order('pick_id'" in body
    # Never by a game-id prefix: LIKE 'NCAAB_%' also matches 'NCAABW_...'.
    assert "like('game_id'" not in body
    for view in ("'games'", "'v_latest_dk_odds'", "'v_latest_odds_all_books'"):
        assert f".from({view})" in body, f"{view} read missing"
    assert body.count(".in('game_id', chunk)") == 3
    assert "if (gameIds.length === 0) return [];" in body
    # A failed line read names the sport it failed for.
    assert "onEnrichmentError?.(`the upcoming ${sport} lines`, e)" in body
    assert "onEnrichmentError?.(`the upcoming ${sport} line shop`, e)" in body
    for name, sport in (("fetchUpcomingNcaabPicks", "NCAAB"), ("fetchUpcomingNcaabwPicks", "NCAABW")):
        wrapper = _fn(q, name)
        assert (
            f"return fetchUpcomingCollegeBasketballPicks('{sport}', afterDate, throughDate, onEnrichmentError);"
            in wrapper
        ), name
        assert "supabase" not in wrapper, f"{name} has a read of its own"


# -- the rest of the app knows the sport --------------------------------------


def test_an_ncaabw_game_leaves_the_board_and_stops_reading_live():
    """Four 10-minute quarters, about two hours on the clock: the men's numbers."""
    src = _read(FORMAT)
    blind = re.search(r"const BLIND_LIVE_WINDOW_MS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert blind
    w = re.search(r"\n  NCAABW: ([\d.]+) \* 3_600_000,", blind.group(1))
    m = re.search(r"\n  NCAAB: ([\d.]+) \* 3_600_000,", blind.group(1))
    assert w and m and w.group(1) == m.group(1), "an NCAABW game would read LIVE for the 6h default"
    dur = re.search(r"const GAME_DURATION_HOURS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert dur
    w = re.search(r"\n  NCAABW: ([\d.]+),", dur.group(1))
    m = re.search(r"\n  NCAAB: ([\d.]+),", dur.group(1))
    assert w and m and w.group(1) == m.group(1), "a started NCAABW game would stay on the board until its score lands"


def test_the_daily_recap_and_form_strip_name_ncaabw():
    order = re.search(r"const SPORT_ORDER: Record<string, number> = \{(.*?)\n\};", _read(DAILY), re.S)
    assert order
    rank = {k: int(v) for k, v in re.findall(r"\n  ([A-Z]+): (\d+),", order.group(1))}
    assert rank.get("NCAABW") == rank["NCAAB"] + 1, rank
    assert len(set(rank.values())) == len(rank), f"two sports share a place in the recap order: {rank}"
    form = _fn(_read(TEAM_FORM), "teamScoreUnit")
    pts = form[form.index("case 'NBA':"):form.index("return 'PTS';")]
    assert "case 'NCAABW':" in pts, "an NCAABW form strip would read R, not PTS"


def test_the_season_label_is_the_ending_year():
    """ESPN labels the women's season by its ending year, as the men's
    (docs/sports/ncaabw.md: 2026-27 is 2027). No women's board reads a season
    today; the helpers answer for every sport on the list."""
    assert "sport === 'NCAABW'" in _fn(_read(FORMAT), "boardSeasonET")
    team = _read(TEAM_STAT_CATALOG)
    for name in ("teamBoardSeason", "teamSeasonLabel"):
        assert "sport === 'NCAABW'" in _fn(team, name), name


def test_ncaabw_has_no_stats_and_asks_the_server_for_none():
    """No women's player stats, Teams board, player page or in-play model.

    Each takes the app's existing empty state, and every Stats read returns
    nothing for NCAABW before it can fall through to another league's view
    (fetchSeasonTotals and fetchWindowTotals end on the MLB read).
    """
    cat = _read(STAT_CATALOG)
    groups = re.search(r"export const GROUP_ORDER: Record<Sport, StatGroup\[\]> = \{(.*?)\n\};", cat, re.S)
    assert groups and "\n  NCAABW: []," in groups.group(1)
    assert "sport: 'NCAABW'" not in cat, "a stat row for a sport with no player data behind it"
    hit = re.search(r"const HIT_RATE_SPORTS = new Set<Sport>\(\[(.*?)\]\);", cat)
    assert hit and "'NCAABW'" not in hit.group(1)
    team = _read(TEAM_STAT_CATALOG)
    ball = re.search(r"const BALL: Sport\[\] = \[(.*?)\];", team)
    assert ball and "'NCAABW'" not in ball.group(1), "an NCAABW Teams board has no rows behind it"
    log = re.search(r"const LOG_SPORTS = new Set<Sport>\(\[(.*?)\]\);", _read(PLAYER_LOG))
    assert log and "'NCAABW'" not in log.group(1), "an NCAABW player page has no log behind it"
    live = re.search(r"export const LIVE_MODEL_SPORTS: ReadonlySet<string> = new Set\(\[(.*?)\]\);", _read(LIVE_SPORTS))
    assert live and "'NCAABW'" not in live.group(1), "NCAABW has no in-play model"

    q = _read(QUERIES)
    season = _fn(q, "fetchSeasonTotals")
    assert season.index("sport === 'NCAABW') return [];") < season.index("'v_player_season_totals_mlb'")
    assert season.index("sport === 'NCAABW') return [];") < season.index("supabase")
    window = _fn(q, "fetchWindowTotals")
    assert window.index("sport === 'NCAABW') return [];") < window.index("'player_window_totals_mlb'")
    teams = _fn(q, "fetchTeamStats")
    assert teams.index("sport === 'NCAABW') return { season: null, rows: [] };") < teams.index("'team_stats_board'")
    for name in ("fetchRecentGames", "fetchSeasonStatValues", "fetchPositionVsOpponent", "fetchPlayerVsDefense"):
        body = _fn(q, name).rstrip()
        assert re.search(r"return \[\];(?: //[^\n]*)?\n\}$", body), f"{name} no longer ends on return []"
        assert "NCAABW" not in body.split("): Promise<")[1], f"{name} has a read for NCAABW"
    # No women's relation is read anywhere: there is none to read.
    assert not re.search(r"['`][a-z_]*ncaabw[a-z_]*['`]", q), "queries.ts names a women's relation"

    # The empty Stats tab names no sportsbook: it has no line to show.
    stats = _read(STATS_SCREEN)
    m = re.search(r"const showHeaderBookLine =(.*?);\n", stats, re.S)
    assert m and "sport !== 'NCAABW'" in m.group(1)


# -- the women's extra books --------------------------------------------------


def _string_list(src: str, declaration: str) -> list[str]:
    start = src.index(declaration)
    return re.findall(r"'([a-z0-9_]+)'", src[start:src.index("];", start)])


def _string_record(src: str, name: str) -> dict[str, str]:
    m = re.search(rf"const {name}: Record<string, string> = \{{(.*?)\n\}};", src, re.S)
    assert m, f"{name} not found"
    return dict(re.findall(r"\n  ([a-z0-9_]+): '([^']*)',", m.group(1)))


def test_the_womens_extra_books_are_named_and_never_a_book_a_member_is_sent_to():
    """config.NCAABW_EXTRA_BOOKMAKERS are stored for women's games as reference
    prices: none is a book a pick may name. In the app that means none is in
    the sportsbook picker or on a line chip (both read the bettable list), and
    the All books table prints each one's name, never its feed key."""
    src = _read(MARKETS)
    assert (
        "export const BETTABLE_BOOKS: BookKey[] = LINE_SHOP_BOOKS.filter(\n"
        "  (b) => !REFERENCE_ONLY_BOOKS.includes(b),\n);"
    ) in src, "the bettable list is derived another way now: re-read this test"
    line_shop = _string_list(src, "export const LINE_SHOP_BOOKS: BookKey[] = [")
    reference = _string_list(src, "export const REFERENCE_ONLY_BOOKS: BookKey[] = [")
    bettable = [b for b in line_shop if b not in reference]
    names = _string_record(src, "BOOK_NAMES")
    labels = _string_record(src, "BOOK_LABELS")
    assert config.NCAABW_EXTRA_BOOKMAKERS, "the list this test walks is empty"
    for book in config.NCAABW_EXTRA_BOOKMAKERS:
        assert book not in bettable, f"{book} is offered as a book to bet at"
        assert names.get(book) and names[book] != book, f"{book} would print as its raw key"
        assert labels.get(book) and len(labels[book]) <= 5, f"{book} has no short label"
    # DraftKings, the only book the women's model names, is still bettable.
    assert "draftkings" in bettable
    # The pill clips a label to three letters: none of the seven may read as
    # another book.
    short = {}
    for book, label in labels.items():
        short.setdefault(label[:3], set()).add(names.get(book, book))
    clashes = {k: v for k, v in short.items() if len(v) > 1}
    assert not clashes, f"two books share a three-letter label: {clashes}"


# -- the UX review's fixes (2026-11-10) ----------------------------------------


def test_voiceover_names_the_womens_chip_in_words():
    """"NCAABW" beside "NCAAB" is the same run of letters until the last one,
    and the chip's spoken label was the code. The chip still shows the code."""
    src = _read(SRC / "lib" / "loadState.ts")
    assert "NCAABW: 'Women’s college basketball'," in src
    body = _fn(src, "sportChipState")
    assert "sportSpokenName(o.sport)," in body
    assert "return SPOKEN_SPORT[sport] ?? sport;" in _fn(src, "sportSpokenName")
    # every control that speaks a sport reads the same name: the Stats tab's
    # sport button and sheet, and the daily recap's chips and section headers
    stats = _read(SRC / "components" / "StatsSportButton.tsx")
    assert "accessibilityLabel={`${sportSpokenName(sport)}, sport`}" in stats
    assert "accessibilityLabel={sportSpokenName(s)}" in stats
    recap = _read(SRC / "components" / "DailyResultsModal.tsx")
    assert "s === 'ALL' ? 'All sports' : sportSpokenName(s)" in recap
    assert "accessibilityLabel={`${sportSpokenName(s.sport)}, ${sub}${" in recap


def test_the_empty_boards_say_where_the_womens_picks_are():
    picks = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    # Today: the women's model posts when DraftKings opens a total, not on the
    # refresh cadence the other sports' copy names.
    assert ("Picks post as DraftKings opens each game’s total, mostly on game day." in picks)
    # Live: no sentence that lists NCAAB and then says NCAABW.
    assert ("'There is no in-play model for women’s college basketball. The All and Signals "
            "boards carry its pre-game picks.'") in picks
    stats = _read(SRC / "screens" / "StatsScreen.tsx")
    assert ("'There are no player or team stats for women’s college basketball. Its totals "
            "picks are on the Picks tab.'") in stats


def test_the_copy_says_a_pick_is_for_the_total_shown_not_a_later_one():
    """A pick at a different number is a different bet (CLAUDE.md 1c), and
    "check the total" alone does not say so."""
    assert "This pick is for the total and price shown, not a later one." in _read(MARKETS)
    meta = " ".join(re.sub(r"'\s*\+\s*'", "", _read(MODEL_META)).split())
    assert "The pick is for the total and price shown, not a later one." in meta
