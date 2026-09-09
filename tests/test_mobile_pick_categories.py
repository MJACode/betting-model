"""The Picks filter's MARKET cut is scoped to the sport on screen, and every
model the server can score has a label in the app.

Two defects, both visible in one screenshot of the NFL board (Matt, 2026-09-09:
*"This filter that is on shows baseball and it's under nfl"*):

  1. `PickFilters` offered all four market categories on every board, because
     `PicksHomeScreen` passed `availableModelIds` only on the signal views and
     the component read `undefined` as "offer everything". So NFL carried MLB's
     "Pitcher" and "Batter" chips, the Props quick chip wrote all three prop
     categories into the state, and the active pill read
     "Pitcher, Batter, Player" over a board of football props.

  2. Twelve NFL prop models were unpaused server-side
     (`model_action_thresholds.paused = false` for all thirteen NFL prop ids on
     2026-09-09) while none had a `MODEL_META` entry. Their cards rendered the
     RAW model id as the market chip -- "nfl_prop_rush_rec_yards" -- and
     `MODEL_META[id]?.type` was undefined everywhere it is read, which let them
     survive EVERY category cut including "Game", which they are not.

WHAT THIS FILE PINS is the second one, in the cross-file form that made it
possible: **config.py is where a model is born, and the app must be able to name
it.** A regex over the source, not an import, so it runs on the pytest gate with
no node and no dotenv. The behavioural half -- the category maths, the filter
predicate, the id fallback -- is executed by
`mobile/scripts/verify_pick_categories.ts`, which this file runs when node
modules are installed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
MODEL_META = MOBILE / "src" / "lib" / "modelMeta.ts"
FILTER_STATE = MOBILE / "src" / "lib" / "pickFilterState.ts"
PICKS_SCREEN = MOBILE / "src" / "screens" / "PicksHomeScreen.tsx"
CONFIG = ROOT / "config.py"


def _read(path: Path) -> str:
    # encoding is explicit: this repo runs on Windows, where read_text() with no
    # encoding uses cp1252 and dies on the box-drawing characters in our source
    # at COLLECTION time, taking the whole suite with it (CLAUDE.md §7).
    return path.read_text(encoding="utf-8")


def _block(src: str, opener: str, closer: str) -> str:
    """The source from `opener` to the next `closer`.

    `opener` must be a DECLARATION, not a bare name: "RETIRED_MODELS" first
    occurs in a comment 300 lines above the real assignment, and anchoring
    there made this file's own guard pass on the broken code -- it read 9KB of
    ACTION_THRESHOLDS as the retired set and subtracted every model from
    itself. That is CLAUDE.md §7's blind-spot rule biting the test written to
    prove it.
    """
    start = src.index(opener)
    end = src.index(closer, start)
    return src[start:end]


def _meta_ids() -> set[str]:
    """Every model_id with a MODEL_META entry."""
    block = _block(_read(MODEL_META), "export const MODEL_META", "\n};")
    return set(re.findall(r"^  ([a-z0-9_]+): \{", block, re.M))


def _meta_types() -> dict[str, str]:
    block = _block(_read(MODEL_META), "export const MODEL_META", "\n};")
    return {
        m.group(1): m.group(2)
        for m in re.finditer(
            r"^  ([a-z0-9_]+): \{.*?\n    type: '([a-z_]+)',", block, re.M | re.S
        )
    }


def _config_scorable_ids() -> set[str]:
    """Every model config.py holds a threshold for, minus the retired ones.

    ACTION_THRESHOLDS is the registry of models that can produce a pick, so it
    is the set the app has to be able to NAME. Retired models keep their labels
    (a pick that existed is the bet of record, CLAUDE.md §1c) but are not
    required to be here.
    """
    src = _read(CONFIG)
    thresholds = _block(src, "\nACTION_THRESHOLDS: dict = {", "\n}")
    ids = set(re.findall(r'^\s+"([a-z0-9_]+)":\s*\{', thresholds, re.M))
    retired = set(
        re.findall(
            r'"([a-z0-9_]+)"',
            _block(src, "\nRETIRED_MODELS: frozenset = frozenset({", "\n})"),
        )
    )
    assert ids, "no model ids parsed out of config.ACTION_THRESHOLDS"
    assert retired, "no model ids parsed out of config.RETIRED_MODELS"
    # The retired set is a handful of models, never most of the registry. A
    # regex that drifts onto the wrong block swallows everything and turns this
    # whole file green against broken code -- which is exactly what it did.
    assert len(retired) < len(ids) / 2, (
        f"parsed {len(retired)} retired ids out of {len(ids)} scorable ones -- "
        "the RETIRED_MODELS block regex has drifted"
    )
    return ids - retired


def test_every_scorable_model_has_a_label_in_the_app():
    """A model with no MODEL_META entry shows the user its own model_id.

    This is the cross-file half: config.py is where a model becomes scorable,
    and nothing on the server side knows the app has to name it. The twelve NFL
    prop models sat in ACTION_THRESHOLDS for seventeen days before anyone saw
    "nfl_prop_rush_rec_yards" on a card.
    """
    missing = sorted(_config_scorable_ids() - _meta_ids())
    assert not missing, (
        "these models can score a pick but have no MODEL_META entry, so the app "
        f"renders their raw model_id as the market chip: {missing}"
    )


def test_every_model_id_derives_its_own_declared_category():
    """`modelCategory`'s id fallback stays true to the registry.

    The fallback is what stops an unlabelled model escaping the Market cut, and
    it only works while ids are named `<sport>_prop_<market>` / `<sport>_<game
    market>`. A model that breaks the convention must fail HERE, loudly, rather
    than be silently misfiled the day someone forgets its MODEL_META entry.
    """

    def derived(model_id: str) -> str:
        if "_prop_pitcher_" in model_id:
            return "pitcher_prop"
        if "_prop_batter_" in model_id:
            return "batter_prop"
        if "_prop_" in model_id or model_id.endswith("_prop"):
            return "player_prop"
        return "game"

    wrong = {
        mid: (declared, derived(mid))
        for mid, declared in _meta_types().items()
        if derived(mid) != declared
    }
    assert not wrong, f"id-derived category disagrees with MODEL_META: {wrong}"


def test_the_market_cut_reads_the_category_of_every_model():
    """applyFilter has no "unknown model" escape hatch.

    It was `if (meta && !state.categories.has(meta.type)) return false;` -- the
    `meta &&` meaning a model with no metadata skipped the cut entirely. A
    missing label is a labelling bug; it must not also be a filtering bug.
    """
    src = _read(FILTER_STATE)
    body = _block(src, "export function applyFilter", "\n}")
    assert "modelCategory(p.model_id)" in body, "applyFilter must categorise via modelCategory"
    # Comments stripped: the body EXPLAINS the lookup it must not perform.
    code = "\n".join(
        line for line in body.splitlines() if not line.strip().startswith("//")
    )
    assert "MODEL_META[" not in code, (
        "applyFilter must not index MODEL_META directly -- that is the lookup "
        "that returns undefined for an unregistered model and waves it through"
    )


def test_the_picks_screen_always_says_what_is_on_the_board():
    """`availableModelIds` is unconditional, and the prop is required.

    The bug was the ternary: `view === 'today' ? undefined : [...]`, with
    PickFilters treating undefined as "offer all four categories".
    """
    screen = _read(PICKS_SCREEN)
    decl = _block(screen, "const availableModelIds", "\n  );")
    assert "undefined" not in decl, (
        "availableModelIds must be computed for every view -- passing undefined "
        "is what offered MLB's Pitcher and Batter markets on the NFL board"
    )
    filters = _read(MOBILE / "src" / "components" / "filters" / "PickFilters.tsx")
    assert "availableModelIds: string[];" in filters, (
        "availableModelIds must be a REQUIRED prop, so a future caller cannot "
        "reintroduce the permissive default"
    )


def test_the_market_categories_are_never_the_hardcoded_four():
    """The offered set comes from the board, not from the universe."""
    filters = _read(MOBILE / "src" / "components" / "filters" / "PickFilters.tsx")
    assert "presentCategoriesFor(availableModelIds)" in filters
    # Every category comparison is relative to what is present. `size <
    # ALL_CATEGORIES.length` was the four-category test that made "Player" on an
    # NFL board look like the same cut as "Player" on an MLB one.
    assert "ALL_CATEGORIES.length" not in filters
    assert "ALL_CATEGORIES.length" not in _read(FILTER_STATE)


def test_the_quick_chip_row_never_changes_shape():
    """Game/Props are disabled in the bar, never removed from it.

    That row is positional and shared with SORT, so dropping ~150pt of leading
    content slides every sort chip left under a thumb already on the row and a
    tap meaning "Game" silently re-sorts the board. The sheet is a vertical
    list and hides its Market section instead -- a faceted filter dropping an
    empty facet moves nothing anyone is aiming at (UX review, 2026-09-09).
    """
    src = _read(MOBILE / "src" / "components" / "filters" / "PickFilters.tsx")
    bar = _block(src, "<ScrollView", "</ScrollView>")
    assert 'label="Game"' in bar and 'label="Props"' in bar, "the quick chips left the bar"
    assert "disabled={!marketCutBites" in bar, (
        "the quick chips must go disabled, not disappear -- removing them "
        "reflows the shared SORT row under the user's thumb"
    )
    sheet = _block(src, "<FilterSheet", "</FilterSheet>")
    assert "{marketCutBites ? (" in sheet, "the sheet's Market section is hidden, not disabled"


def test_the_props_chip_never_writes_a_market_the_board_cannot_hold():
    """One tap used to put pitcher_prop and batter_prop into the state on an
    NFL board. Invisible today because every read intersects with
    presentCategories -- which is the bug masked, not absent."""
    src = _read(MOBILE / "src" / "components" / "filters" / "PickFilters.tsx")
    assert "setCategories(propsOnly ? ALL_CATEGORIES : presentProps)" in src
    assert "PROP_CATEGORIES" not in src, (
        "PickFilters must not reach for the all-sports prop list at all"
    )


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    """Run the executable half -- the maths, on the real boards."""
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_pick_categories.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
