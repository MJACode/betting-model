"""ATP (men's tennis) and WTA (women's tennis) are sports the app can show, so
the two tennis match-winner models' picks reach every board that shows picks.

The app, Discord and push show the same picks (CLAUDE.md 1b). The models
``atp_moneyline_shop`` and ``wta_moneyline_shop`` went live on cf193c1e
(2026-11-14) with their own Discord channels. Measured on cf193c1e, before
this change (mobile/scripts/verify_tennis_ui.ts ran against it):

- ``useSportFilter.SPORTS`` had no ATP or WTA chip. Every board shows one
  selected sport at a time, so no board could draw a tennis pick, and
  ``pushRoute.asSport`` (which validates against SPORTS) dropped
  ``sport: 'ATP'`` from a push: the route came back with ``sport: null``.
- ``modelMeta.sportOfModel`` and ``ModelsScreen.sportOf`` end on
  ``return 'MLB'``, so both tennis models were filed under MLB: the custom
  model builder's MLB moneyline row carried ``atp_moneyline_shop`` and
  ``wta_moneyline_shop`` beside ``mlb_moneyline``, and a tennis model's page
  was titled MLB.
- A match read "Carlos Alcaraz @ Jannik Sinner" (the signals card, the
  betslip, the daily recap): a tennis match has two players, not a home side.
- The Pick Detail note said "Game picks lock at the first scoring run of the
  day"; the card decides each match once, 25 to 35 minutes before its listed
  start (scripts/tennis_moneyline_card.py DECISION_LEAD).

Tennis has no player or team stats in the app and no in-play model. Where
another sport has those, tennis takes the app's existing empty state. Tennis
prices are stored in tennis_odds_quotes, which the app does not read, so a
tennis card carries the deciding book's price and nothing else.

These are text checks, like the rest of the mobile tests: the behaviour is
in mobile/scripts/verify_tennis_ui.ts, run below through tsx when node is
installed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from tests._node import tsx_cmd  # noqa: E402
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
    TODAY,
    _fn,
    _read,
    _sports,
)
from tests.test_mobile_ncaabw_in_app import _prefix_function, _sport_of  # noqa: E402

MOBILE = ROOT / "mobile"
STATS_SCREEN = SRC / "screens" / "StatsScreen.tsx"
PICKS_HOME = SRC / "screens" / "PicksHomeScreen.tsx"
PICK_DETAIL = SRC / "screens" / "PickDetailScreen.tsx"
PICK_CARD = SRC / "components" / "PickCard.tsx"
PARLAY = SRC / "lib" / "parlay.ts"
SIGNALS_CARD = SRC / "lib" / "signalsCard.ts"
GAME_FILTER = SRC / "lib" / "gameFilter.ts"
STATS_BOARD = SRC / "lib" / "statsBoard.ts"
LOAD_STATE = SRC / "lib" / "loadState.ts"
CARD = ROOT / "scripts" / "tennis_moneyline_card.py"
SETTLE = ROOT / "tracking" / "paper_tracker.py"

# The ids the card writes its picks under (models/tennis_moneyline_shop.py
# MODEL_IDS), and the sport each writes in picks.sport.
TENNIS = {"ATP": "atp_moneyline_shop", "WTA": "wta_moneyline_shop"}

# The two stats reads in queries.ts that fall to the MLB views for a sport
# they do not name (their golf line says so). Each must answer for tennis
# before that read.
STATS_READS = ("fetchSeasonTotals", "fetchWindowTotals")
# The stats reads that name each sport they read and end on `return [];`, so
# a sport they do not name gets nothing and no request.
NAMED_READS = ("fetchRecentGames", "fetchSeasonStatValues", "fetchH2HStatValues")


def _set(src: str, name: str) -> list[str]:
    m = re.search(rf"const {name}(?:: ReadonlySet<string>)? = new Set(?:<string>)?\(\[(.*?)\]\);", src)
    assert m, f"{name} not found"
    return re.findall(r"'([A-Z]+)'", m.group(1))


# -- the sports exist ---------------------------------------------------------


def test_atp_and_wta_are_sport_chips_right_after_ufc():
    sports = _sports()
    for s in TENNIS:
        assert s in sports, f"{s} has no sport chip, so no board can show its picks"
    assert sports.index("ATP") == sports.index("UFC") + 1, sports
    assert sports.index("WTA") == sports.index("ATP") + 1, sports
    union = re.search(r"export type Sport =([^;]*);", _read(SPORT_FILTER))
    assert union and "'ATP'" in union.group(1) and "'WTA'" in union.group(1)


def test_the_card_writes_the_sports_the_chips_name():
    """The chip matches picks on `picks.sport`. The card writes the tour there
    (pick_row: "sport": d["tour"]) and the tour is MODEL_IDS' key."""
    from models import tennis_moneyline_shop as ms
    assert ms.MODEL_IDS == TENNIS
    assert '"sport": d["tour"]' in _read(CARD)
    assert set(TENNIS) <= set(config.DISCORD_SPORTS), "Discord posts a sport the app has no chip for"


def test_a_push_naming_a_tour_switches_the_board_to_it():
    """asSport validates against SPORTS, so the chip is what lets the push in."""
    body = _fn(_read(PUSH_ROUTE), "routeForPush")
    assert "asSport(d.sport)" in body
    as_sport = re.search(r"function asSport\(.*?\n\}", _read(PUSH_ROUTE), re.S)
    assert as_sport and "SPORTS as string[]).includes(v)" in as_sport.group(0)
    for s in TENNIS:
        assert s in _sports(), f"a push naming {s} is dropped: asSport finds no {s} chip"


# -- each model is filed under its own tour -----------------------------------


def test_tennis_models_are_filed_under_their_tour_and_not_under_mlb():
    """Run each prefix function's own chain, in its own order, as the NCAABW
    test does. Without a tennis line both fell to the final `return 'MLB'`."""
    for path, name in ((MODEL_META, "sportOfModel"), (MODELS_SCREEN, "sportOf")):
        chain, fallback, body = _prefix_function(path, name)
        where = f"{path.name} {name}"
        for sport, model_id in TENNIS.items():
            assert _sport_of(chain, fallback, model_id) == sport, (
                f"{where} files {model_id} under {_sport_of(chain, fallback, model_id)}"
            )
            assert f"if (modelId.startsWith('{sport.lower()}')) return '{sport}';" in body, where
        # 'wta' and 'wnba' share a first letter and nothing else.
        assert _sport_of(chain, fallback, "wnba_moneyline") == "WNBA", where
        assert _sport_of(chain, fallback, "ufc_open_moneyline") == "UFC", where
        assert _sport_of(chain, fallback, "mlb_moneyline") == "MLB", where
    union = re.search(r"function sportOf\(modelId: string\):\s*([^{]*)\{", _read(MODELS_SCREEN))
    assert union and "'ATP'" in union.group(1) and "'WTA'" in union.group(1)


def test_tennis_is_in_the_custom_model_catalog_order_after_ufc():
    src = _read(MODEL_META)
    union = re.search(r"export type BetTypeSport =([^;]*);", src)
    assert union and "'ATP'" in union.group(1) and "'WTA'" in union.group(1)
    order = re.search(r"const BET_TYPE_SPORT_ORDER: BetTypeSport\[\] = \[(.*?)\];", src, re.S)
    assert order
    names = re.findall(r"'([A-Z]+)'", order.group(1))
    assert names.index("ATP") == names.index("UFC") + 1, names
    assert names.index("WTA") == names.index("ATP") + 1, names


def test_the_app_labels_exactly_the_two_tennis_models():
    src = _read(MODEL_META)
    labelled = set(re.findall(r"\n  ((?:atp|wta)_[a-z0-9_]+): \{", src))
    assert labelled == set(TENNIS.values()), labelled
    scored = {m for m in config.ACTION_THRESHOLDS if m.startswith(("atp_", "wta_"))}
    assert scored <= labelled, f"config scores {sorted(scored - labelled)} with no label in the app"
    for sport, model_id in TENNIS.items():
        entry = re.search(rf"\n  {model_id}: \{{(.*?)\n  \}},", src, re.S).group(1)
        assert f"longLabel: '{sport} Match Winner'" in entry and "type: 'game'" in entry


# -- a match is "A vs B" ------------------------------------------------------


def test_a_two_player_match_reads_vs_everywhere():
    """One set names the sports whose games row holds two competitors in
    slots, and every matchup string reads it. Six sites tested
    `sport === 'UFC'` by hand; a seventh copy is the next miss."""
    fmt = _read(FORMAT)
    assert _set(fmt, "VERSUS_SPORTS") == ["UFC", "ATP", "WTA"]
    assert "return VERSUS_SPORTS.has(sport ?? '');" in _fn(fmt, "isVersusSport")
    sites = {
        PICK_CARD: "${isVersusSport(game.sport) ? 'vs' : '@'}",
        PICK_DETAIL: "${isVersusSport(game.sport) ? 'vs' : '@'}",
        PARLAY: "const sep = isVersusSport(game.sport) ? 'vs' : '@';",
        DAILY: "if (isVersusSport(g.sport)) return `${g.away_team} vs ${g.home_team}`;",
        SIGNALS_CARD: "${isVersusSport(sport) ? 'vs' : '@'}",
    }
    for path, line in sites.items():
        assert line in _read(path), f"{path.name} does not read the matchup through isVersusSport"
    assert "${isVersusSport(sport) ? 'versus' : 'at'}" in _read(SIGNALS_CARD)
    # No hand-written UFC test is left on a matchup.
    for path in sorted(SRC.rglob("*.ts*")):
        src = _read(path)
        assert not re.search(r"=== 'UFC' \? '(?:vs|versus)'", src), path.name
        assert "=== 'UFC') return `${" not in src, path.name


def test_a_match_has_no_fixture_row_no_home_side_and_no_team_slate():
    """The gameFilter, slate and neutral-site sets hold tennis, like UFC: the
    two players are slots, so "A @ B" names a home side that does not exist."""
    assert _set(_read(GAME_FILTER), "NO_FIXTURE_SPORTS") == ["UFC", "GOLF", "ATP", "WTA"]
    board = _read(STATS_BOARD)
    assert _set(board, "TEAMLESS_SPORTS") == ["UFC", "GOLF", "ATP", "WTA"]
    assert _set(board, "NEUTRAL_SITE_SPORTS") == ["UFC", "GOLF", "ATP", "WTA"]


def test_tracking_a_tennis_pick_promises_no_line_move_alert():
    """The alert reads DraftKings' line from the shared odds table, where no
    tennis price is ever stored, so the Track copy must not promise one."""
    notifier = _read(ROOT / "tracking" / "push_notifier.py")
    body = notifier[notifier.index("def _line_change_alerts"):]
    body = body[:body.index("\ndef ")]
    assert "_get_dk_odds(conn, game_id, market)" in body, "the alert reads another table now: re-read this"
    m = re.search(r"const trackAlertsEligible =(.*?);\n", _read(PICK_DETAIL), re.S)
    assert m and "pick.sport !== 'ATP' && pick.sport !== 'WTA'" in m.group(1)


def test_pick_detail_draws_no_team_form_for_a_match():
    """useTeamTrends would ask the team-form reads for 'Jannik Sinner'."""
    src = _read(PICK_DETAIL)
    assert "const showTeamTrends = isGameModel && !isVersusSport(teamSport) && !isGolf;" in src
    assert src.index("const teamSport =") < src.index("const showTeamTrends =")


# -- the board keeps a match, and reaches one posted before midnight ------------


def test_a_match_leaves_the_board_on_its_final_not_on_the_clock():
    """Settlement writes the sets won to `games` when it grades a bet, so a bet
    leaves the board on its final, as every sport's does. A match with no bet
    never gets a score. A listed start can run up to an hour early
    (docs/sports/tennis.md) and a men's Grand Slam match is best of five, so a
    duration bound could take a pick off the board before its match ends; a
    tennis row with no final stays for its day."""
    src = _read(FORMAT)
    dur = re.search(r"const GAME_DURATION_HOURS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert dur
    for s in TENNIS:
        assert not re.search(rf"\n  {s}: ", dur.group(1)), f"{s} is dropped on the clock"
    settle = _read(SETTLE)
    body = settle[settle.index("def _settle_tennis_picks"):]
    body = body[:body.index("\ndef ")]
    assert "UPDATE games SET home_score = %s, away_score = %s" in body, (
        "a graded tennis bet no longer writes its final: re-read GAME_DURATION_HOURS")
    assert "AND p.signal_type = 'BET'" in body, "settlement grades more than bets now: re-read this"
    blind = re.search(r"const BLIND_LIVE_WINDOW_MS: Record<string, number> = \{(.*?)\n\};", src, re.S)
    assert blind
    for s in TENNIS:
        assert re.search(rf"\n  {s}: 6 \* 3_600_000,", blind.group(1)), f"{s} has no named LIVE window"


def test_the_today_board_reaches_a_match_posted_before_midnight():
    """The card decides 35 minutes or less before the listed start and files
    the pick under the listed start's Eastern date, so a match listed between
    00:00 and 00:35 ET is posted the evening before, under tomorrow's date.
    The same-day read would hide it until midnight while Discord carries it."""
    card = _read(CARD)
    lead = re.search(r"^DECISION_LEAD = timedelta\(minutes=(\d+)\)$", card, re.M)
    assert lead and timedelta(minutes=int(lead.group(1))) < timedelta(days=1)
    assert 'game_date = listed.tz_convert(_ET).date().isoformat()' in card
    src = _read(TODAY)
    days = re.search(r"const TENNIS_AHEAD_DAYS = (\d+);", src)
    assert days and int(days.group(1)) >= 1
    assert "fetchUpcomingTennisPicks(target, addDays(target, TENNIS_AHEAD_DAYS))" in src
    assert ".catch(swallow('the upcoming tennis matches'))" in src
    start = src.index("const merged = [")
    merged = src[start:src.index("\n", start)]
    assert "...tennisRows" in merged, "the tennis read is fetched and then dropped"
    for name in ("rows", "ufcRows", "ncaabRows", "ncaabwRows", "nhlRows"):
        assert f"...{name}" in merged, name


def test_the_tennis_look_ahead_reads_the_two_tours_and_no_odds_view():
    """Tennis prices are in tennis_odds_quotes, which the app does not read
    (data/anon_readable.py), so the shared odds views hold nothing for a
    match: the read is the picks and their games only."""
    body = _fn(_read(QUERIES), "fetchUpcomingTennisPicks")
    assert body.count(".in('sport', ['ATP', 'WTA'])") == 2
    assert body.count(".gt('game_date', afterDate)") == 2
    assert body.count(".lte('game_date', throughDate)") == 2
    assert ".from('picks')" in body and ".from('games')" in body
    for view in ("v_latest_dk_odds", "v_latest_odds_all_books"):
        assert view not in body
    # Matched on the sport column, never a game-id prefix.
    assert "like('game_id'" not in body
    from data.anon_readable import ANON_READABLE, WORKER_ONLY_TABLES
    assert "tennis_odds_quotes" in WORKER_ONLY_TABLES and "tennis_odds_quotes" not in ANON_READABLE


# -- the rest of the app knows the sport ----------------------------------------


def test_the_daily_recap_orders_the_tours_after_ufc():
    order = re.search(r"const SPORT_ORDER: Record<string, number> = \{(.*?)\n\};", _read(DAILY), re.S)
    assert order
    rank = {k: int(v) for k, v in re.findall(r"\n  ([A-Z]+): (\d+),", order.group(1))}
    assert rank.get("ATP") == rank["UFC"] + 1, rank
    assert rank.get("WTA") == rank["ATP"] + 1, rank
    assert len(set(rank.values())) == len(rank), f"two sports share a place in the recap order: {rank}"


def test_no_stats_read_falls_through_to_mlb_for_tennis():
    """Each stats read names the sports it reads and falls to the MLB views
    for any other. Tennis answers empty first, as golf does."""
    q = _read(QUERIES)
    for name in STATS_READS:
        body = _fn(q, name)
        sig = body[:body.index(")")]
        assert "'ATP' | 'WTA'" in sig, f"{name} does not take the tennis sports"
        guard = "if (sport === 'ATP' || sport === 'WTA') return [];"
        assert guard in body, f"{name} reads the MLB views for tennis"
        reads = [i for i in (body.find(x) for x in ("supabase", "pageRpc(", "fetchAllPages", ".rpc("))
                 if i >= 0]
        assert body.index(guard) < min(reads, default=len(body)), f"{name} reads before its tennis guard"
    for name in NAMED_READS:
        body = _fn(q, name)
        sig = body[:body.index(")")]
        assert "'ATP' | 'WTA'" in sig, f"{name} does not take the tennis sports"
        assert re.search(r"return \[\];(?: //[^\n]*)?\n\}$", body.rstrip()), f"{name} no longer ends on return []"
        assert "'ATP'" not in body[len(sig):] and "'WTA'" not in body[len(sig):], f"{name} reads something for tennis"
    teams = _fn(q, "fetchTeamStats")
    guard = "if (sport === 'ATP' || sport === 'WTA') return { season: null, rows: [] };"
    assert guard in teams and teams.index(guard) < teams.index("supabase")
    for name in ("fetchTonightMatchups", "fetchPositionVsOpponent", "fetchPlayerVsDefense"):
        sig = _fn(q, name)
        assert "'ATP' | 'WTA'" in sig[:sig.index(")")], name
    groups = re.search(r"export const GROUP_ORDER: Record<Sport, StatGroup\[\]> = \{(.*?)\n\};",
                       _read(STAT_CATALOG), re.S)
    assert groups and "\n  ATP: []," in groups.group(1) and "\n  WTA: []," in groups.group(1)


def test_the_stats_tab_says_there_are_no_tennis_stats():
    stats = _read(STATS_SCREEN)
    m = re.search(r"const showHeaderBookLine =(.*?);\n", stats, re.S)
    assert m and "sport !== 'ATP' && sport !== 'WTA'" in m.group(1), "the empty tennis board names a sportsbook"
    assert "There are no player stats for ${sport === 'ATP' ? 'men’s' : 'women’s'} tennis." in stats
    assert "Its match-winner picks are on the Picks tab." in stats


def test_the_empty_today_board_says_when_tennis_posts():
    """The default copy names the hourly refresh; the card posts each match
    about 30 minutes before its listed start."""
    picks = _read(PICKS_HOME)
    assert (": sport === 'ATP' || sport === 'WTA'\n"
            "              ? `No ${sport} picks have posted for ${date} yet. Picks post about 30 minutes "
            "before each match the model bets.`") in picks


def test_the_pick_screen_says_posted_once_at_the_price_shown():
    markets = _read(MARKETS)
    lst = re.search(r"const POSTED_MONEYLINE_MODELS: readonly string\[\] = \[(.*?)\];", markets, re.S)
    assert lst
    body = _fn(markets, "pickTimingInfo")
    chain = body[body.index("const nbaPosted ="):body.index("kind: 'posted',")]
    for model_id in TENNIS.values():
        assert f"'{model_id}'" in lst.group(1), model_id
        assert f"pick.model_id === '{model_id}'" in chain, model_id


def test_a_parlay_treats_a_match_as_independent_like_a_fight():
    mc = " ".join(_fn(_read(MARKETS), "marketClassForModel").split())
    assert ("if ( modelId.startsWith('ufc_') || modelId.startsWith('golf_') || "
            "modelId.startsWith('atp_') || modelId.startsWith('wta_') ) { return 'other'; }") in mc
    # Before the moneyline test, which would file a tennis id as 'game_ml'.
    assert mc.index("startsWith('atp_')") < mc.index("modelId.includes('moneyline')")


def test_voiceover_names_each_tour_in_words():
    src = _read(LOAD_STATE)
    assert "ATP: 'ATP men’s tennis'," in src
    assert "WTA: 'WTA women’s tennis'," in src


# -- the behaviour --------------------------------------------------------------


def test_the_behavioural_checks_pass():
    cmd = tsx_cmd(MOBILE)
    if cmd is None:
        pytest.skip("node or mobile/node_modules is not installed")
    proc = subprocess.run([*cmd, "scripts/verify_tennis_ui.ts"], cwd=MOBILE,
                          capture_output=True, text=True, timeout=300, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
