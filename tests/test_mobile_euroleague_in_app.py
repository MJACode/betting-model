"""EUROLEAGUE in the app (2026-11-13): the sport its one model, the halftime
spread, needs to reach a board. Read from the source, so it runs with no node;
mobile/scripts/verify_euroleague_ui.ts runs the same wiring as code.

Pinned here: the chip (last), the push route (derived from SPORTS), the
in-play sports list and its empty copy, the model's name and sport (its prefix,
not the MLB default), its price lookups, its timing line, a Stats tab that
promises nothing (no stats stored), and Picks boards that say there is no
pre-game model instead of naming refresh times.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"
MODEL = "euroleague_live_spread_ht"


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    i = re.search(r"export (?:async )?function " + name + r"\(", src).start()
    j = src.find("\nexport ", i + 10)
    return src[i:j if j > 0 else len(src)]


def test_euroleague_is_the_last_chip_and_a_sport():
    src = _read("hooks/useSportFilter.ts")
    union = re.search(r"export type Sport =(.*?);", src, re.S).group(1)
    assert "'EUROLEAGUE'" in union
    sports = re.search(r"export const SPORTS: Sport\[\] = \[(.*?)\];", src, re.S).group(1)
    assert sports.strip().endswith("'EUROLEAGUE'")
    # the push router validates against SPORTS itself, so a EuroLeague push is not dropped
    assert "import { SPORTS, type Sport } from '@/hooks/useSportFilter';" in _read("lib/pushRoute.ts")


def test_the_in_play_sports_name_euroleague_and_its_empty_board_says_when_it_bets():
    src = _read("lib/liveSports.ts")
    live = re.search(r"export const LIVE_MODEL_SPORTS: ReadonlySet<string> = new Set\(\[(.*?)\]\);", src).group(1)
    assert "'EUROLEAGUE'" in live and live.endswith("'NCAAB', 'NCAABW'")
    assert ("'The EuroLeague in-play model checks each game during its halftime break and bets it at most once, ' +"
            in src)
    load = _read("lib/loadState.ts")
    assert load.count("EUROLEAGUE: 'EuroLeague',") == 2           # spoken, and in a sentence
    assert "export function sportDisplayName(sport: string): string {" in load
    assert "name: (sport: string) => string = sportDisplayName" in src


def test_the_model_has_its_name_and_its_sport():
    meta = _read("lib/modelMeta.ts")
    entry = re.search(r"^  " + MODEL + r": \{\n(.*?)^  \},", meta, re.M | re.S).group(1)
    assert "longLabel: 'EuroLeague Halftime Spread'" in entry and "type: 'game'" in entry
    assert "shortLabel: 'LIVE Spread'" in entry
    body = _fn(meta, "sportOfModel")
    assert "if (modelId.startsWith('euroleague')) return 'EUROLEAGUE';" in body
    assert "| 'EUROLEAGUE'" in re.search(r"export type BetTypeSport =(.*?);", meta, re.S).group(1)
    assert "if (modelId === EUROLEAGUE_HALFTIME_MODEL) {" in meta
    models = _read("screens/ModelsScreen.tsx")
    assert "if (modelId.startsWith('euroleague')) return 'EUROLEAGUE';" in models


def test_its_prices_and_its_timing_line():
    m = _read("lib/markets.ts")
    assert "spread" in MODEL                        # gameMarketForModel and marketClassForModel read 'spreads'
    slot = re.search(r"export const LIVE_PRICE_SLOT_ONLY: ReadonlySet<string> = new Set\(\[(.*?)\]\);", m, re.S)
    assert f"'{MODEL}'" in slot.group(1)
    timing = _fn(m, "pickTimingInfo")
    assert "pick.model_id === NCAABW_HALFTIME_MODEL || pick.model_id === EUROLEAGUE_HALFTIME_MODEL" in timing
    assert "'Decided once, during the halftime break, on the full-game spread: it settles on the ' +" in timing


def test_the_stats_tab_promises_nothing_for_a_sport_with_no_stats():
    cat = _read("lib/statCatalog.ts")
    assert "  EUROLEAGUE: [],\n};" in cat
    q = _read("lib/queries.ts")
    for name in ("fetchRecentGames", "fetchSeasonStatValues", "fetchH2HStatValues"):
        assert "if (sport === 'EUROLEAGUE'" in _fn(q, name), name
    assert "if (sport === 'GOLF' || sport === 'EUROLEAGUE') return [];" in _fn(q, "fetchWindowTotals")
    assert "if (sport === 'EUROLEAGUE') return { season: null, rows: [] };" in _fn(q, "fetchTeamStats")


def test_the_pre_game_boards_say_there_is_no_pre_game_model():
    src = _read("screens/PicksHomeScreen.tsx")
    copy = ("'EuroLeague has no pre-game model. Its one model bets during the halftime break, and those bets "
            "post on Live Signals.'")
    assert src.count(copy) == 2                      # the All board and the Signals board
    assert "sport === 'EUROLEAGUE' ? 'No pre-game EuroLeague picks' : `No ${sport} picks today`" in src
    assert "title={sport === 'EUROLEAGUE' ? 'No pre-game EuroLeague signals' : 'No signal bets right now'}" in src
    assert "title={`No ${sportDisplayName(sport)} live signals right now`}" in src
    stats = (SRC / "screens" / "StatsScreen.tsx").read_text(encoding="utf-8")
    assert 'title="No EuroLeague stats"' in stats
    assert "The app has no EuroLeague player or team stats." in stats


def test_the_recap_and_the_board_clock_know_the_sport():
    assert "EUROLEAGUE: 9," in _read("lib/dailyResults.ts")
    fmt = _read("lib/format.ts")
    assert "EUROLEAGUE: 4 * 3_600_000," in fmt and "EUROLEAGUE: 3,\n" in fmt
    assert f"  {MODEL}: {{ min_prob: 0, min_edge: 0, min_odds: -200 }}," in _read("lib/thresholds.generated.ts")
