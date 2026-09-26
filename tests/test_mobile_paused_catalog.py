"""Paused models are hidden from the mobile catalog, not from the record.

Matt, 2026-09-19: users should not see paused models on follow-lists, filters,
the bet-type picker, Stats add-pick, or today's board. The pause source is
`isModelPaused` (server `model_action_thresholds.paused`, bundled
`PAUSED_MODELS` fallback) — the same helper `passesActionFilter` and the Live
board already use. A hand-copied set on any of those surfaces would drift.

The settled record is a different question (CLAUDE.md §1c). `trackRecord.ts`
and graded daily-results rows must NOT start filtering on `isModelPaused`:
a pause does not unsay a bet already made. This file pins both halves so a
future session cannot "complete" the hide by dropping the record too.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on the box-drawing characters in our source
    # at COLLECTION time, taking the whole suite with it (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def _block(src: str, opener: str, closer: str) -> str:
    start = src.index(opener)
    return src[start : src.index(closer, start)]


def test_the_models_list_filters_paused_models():
    """ModelsScreen's built-in list is a catalog, not a record."""
    src = _read(MOBILE / "src" / "screens" / "ModelsScreen.tsx")
    body = _block(src, "const builtInWithStats", "\n  );")
    assert "isModelPaused(modelId)" in body
    assert "isModelRetired(modelId)" in body
    # The 2026-09-12 "listed, not hidden" sort (paused rows below live ones)
    # is the thing this hide replaces. A sort that still keys on paused means
    # the list still contains them.
    assert "Number(isModelPaused" not in src
    # Empty copy names the pause, not "this sport was never built" (UX review).
    assert "Paused models are hidden here" in src
    assert "withdrawnRulesEmpty" in src


def test_the_bet_type_picker_filters_paused_models():
    src = _read(MOBILE / "src" / "lib" / "modelMeta.ts")
    body = _block(src, "export function betTypeGroups", "\n}")
    assert "isModelPaused(id)" in body
    assert "isModelRetired(id)" in body


def test_the_custom_model_picker_is_three_bet_types():
    """The picker collapses model_ids into ML / line / player props.
    betTypeGroups stays the per-model catalog so a pause still drops an id
    before the collapse. The screen must not go back to one row per longLabel.
    """
    meta = _read(MOBILE / "src" / "lib" / "modelMeta.ts")
    assert "{ label: 'ML', subtitle: 'Moneyline' }" in meta
    assert "{ label: 'Run line', subtitle: '±1.5' }" in meta
    assert "{ label: 'Puck line', subtitle: '±1.5' }" in meta
    assert "{ label: 'Spread', subtitle: 'Spread line' }" in meta
    assert "{ label: 'Player props', subtitle: 'All player markets' }" in meta
    collapse = _block(meta, "export function betTypePickerGroups", "\n}")
    assert "betTypeGroups()" in collapse
    # Rule chrome (editor, detail, Models list) all call betTypeLabel. A slot
    # must title itself with the picker's short name, not longLabel.
    titled = _block(meta, "export function betTypeLabel", "\n}")
    assert "betSlotForModel" in titled
    assert "choiceCopy" in titled
    # NCAAF Spread writes ncaaf_spread only. Premium stays out of the slot
    # so the row cannot add a second rule with the same title.
    slot = _block(meta, "export function betSlotForModel", "\n}")
    assert "id === 'ncaaf_spread_premium'" in slot

    screen = _read(MOBILE / "src" / "screens" / "ModelEditScreen.tsx")
    assert "betTypePickerGroups" in screen
    assert "betTypeGroups(" not in screen
    assert "function NumberField" not in screen
    assert "function PickerField" not in screen
    assert "RangeSlider" in screen
    assert "onPick(choice.modelIds)" in screen
    # One thumb moving must not snap the other end. The screen commits
    # through commitSliderBounds; indexToBound on both indices was the bug.
    assert "commitSliderBounds" in screen
    assert "onChange(indexToBound(stops, lo), indexToBound(stops, hi))" not in screen
    assert "onChange(indexToBound(stops, pair.low), indexToBound(stops, pair.high))" not in screen


def test_today_picks_drop_paused_models_at_the_source():
    """useTodayPicks feeds Today, Signals counts, Models cards, Market chips
    and Stats odds pills. A filter only on passesActionFilter left Today and
    the pills showing a paused model's leftover BET (the retired-model bug
    one row down)."""
    src = _read(MOBILE / "src" / "hooks" / "useTodayPicks.ts")
    assert "!isModelPaused(d.pick.model_id)" in src
    assert "!isModelRetired(d.pick.model_id)" in src


def test_stats_add_pick_refuses_a_paused_model():
    src = _read(MOBILE / "src" / "lib" / "statCatalog.ts")
    body = _block(src, "export function propModelForStat", "\n}")
    assert "isModelPaused(id)" in body
    assert "isModelRetired(id)" in body


def test_the_record_surfaces_do_not_drop_paused_models():
    """A pause does not unsay a settled bet. These files may label a paused
    model; they must not filter it out of the published record."""
    track = _read(MOBILE / "src" / "lib" / "trackRecord.ts")
    assert "isModelPaused" not in track
    assert "isModelRetired" in track

    daily = _read(MOBILE / "src" / "lib" / "dailyResults.ts")
    # Graded rows go through passesRecordFilter (pause-blind). Ungraded
    # "placed" rows go through passesActionFilter (pause-aware). A new
    # isModelPaused on the graded path is the 2026-09-12 record wipe.
    assert "graded ? passesRecordFilter(p) : passesActionFilter(p)" in daily


def test_the_pause_source_is_isModelPaused_not_a_hand_copied_set():
    """Every catalog surface must ask isModelPaused, not PAUSED_MODELS.has.
    The server store can pause a model the bundle still thinks is live."""
    surfaces = [
        MOBILE / "src" / "screens" / "ModelsScreen.tsx",
        MOBILE / "src" / "lib" / "modelMeta.ts",
        MOBILE / "src" / "hooks" / "useTodayPicks.ts",
        MOBILE / "src" / "lib" / "statCatalog.ts",
    ]
    for path in surfaces:
        src = _read(path)
        # Comments may name the fallback set; the predicate must not.
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("//")
        )
        assert "isModelPaused" in src, f"{path.name} never calls isModelPaused"
        assert not re.search(r"PAUSED_MODELS\.has", code), (
            f"{path.name} reads PAUSED_MODELS directly — that skips the "
            "server flag isModelPaused exists to prefer"
        )


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_paused_catalog.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_paused_picks_reach_the_all_board_only_and_labelled():
    """Matt, 2026-09-26: "NFL is only showing tackle bets. It should be all
    bets" -- 11 of 12 NFL prop models were paused and hidden. A paused model's
    rows now appear on the All segment, labelled PAUSED, and nowhere else.

    Three halves, each one a way to get this wrong:
    - the hook keeps paused rows OUT of `data` (every other consumer: Signals,
      sport badges, Models cards, Stats pills, the betslip);
    - the Picks screen merges `pausedData` into the All list only;
    - the card drops everything that reads as a bet (badge, stake, Sharp
      Score, book hand-off, betslip) when `paused`.
    """
    hook = _read(MOBILE / "src" / "hooks" / "useTodayPicks.ts")
    assert "setData(all.filter((d) => !isModelPaused(d.pick.model_id)))" in hook
    assert "setPausedData(all.filter((d) => isModelPaused(d.pick.model_id)))" in hook

    screen = _read(MOBILE / "src" / "screens" / "PicksHomeScreen.tsx")
    assert "[...allData, ...pausedData].filter((d) => d.pick.sport === sport)" in screen
    assert "paused={view === 'today' && isModelPaused(item.pick.model_id)}" in screen
    # Signals is derived through passesActionFilter, which refuses a paused
    # model -- the guard that keeps a paused row off the paid board.
    assert "todayData.filter((d) => passesActionFilter(d.pick) && !isUnlockedPreview(d.pick))" in screen
    thresholds = _read(MOBILE / "src" / "lib" / "thresholds.ts")
    body = _block(thresholds, "export function passesActionFilter", "\n}")
    assert "if (sv.paused) return false;" in body
    assert "if (PAUSED_MODELS.has(p.model_id)) return false;" in body

    card = _read(MOBILE / "src" / "components" / "PickCard.tsx")
    assert ">PAUSED<" in card
    assert "const sharp = preview || paused ? null" in card
    assert "!preview && !paused && pick.signal_type === 'BET'" in card
    assert "&& !preview && !paused;" in card
    assert "pick.signal_type !== 'BET' || preview || paused" in card
