"""The Picks Lines segment: NHL and NBA game cards, best bettable price.

Matt approved the board. The behavioural pins live in
`mobile/scripts/verify_lines_board.ts`; this file runs that script when the
mobile toolchain is installed and pins the source shape either way.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
PICKS = MOBILE / "src" / "screens" / "PicksHomeScreen.tsx"
TYPES = MOBILE / "src" / "types" / "index.ts"
QUERIES = MOBILE / "src" / "lib" / "queries.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_lines_is_a_picks_view():
    m = re.search(r"export type PicksView = ([^;]+);", _read(TYPES))
    assert m, "PicksView is not declared in types/index.ts"
    assert "'lines'" in m.group(1)


def test_the_lines_segment_is_unconditional_and_after_live():
    src = _read(PICKS)
    live = src.find('label="Live Signals"')
    lines = src.find('label="Lines"')
    assert live != -1 and lines != -1
    assert lines > live, "Lines is not after Live Signals"
    preceding = src[max(0, lines - 180) : lines]
    assert "length > 0 ?" not in preceding
    assert "view === 'lines' ?" not in preceding


def test_the_lines_read_names_the_view_and_pages():
    src = _read(QUERIES)
    fn = src[src.index("export async function fetchLinesBoardOdds") : src.index("export async function fetchPropLineRows")]
    assert ".from('v_latest_odds_all_books')" in fn
    assert "fetchAllPages" in fn
    assert "LINES_ODDS_MARKETS" in fn
    games = src[src.index("export async function fetchGamesForLinesBoard") : src.index("export async function fetchLinesBoardOdds")]
    assert ".from('games')" in games
    assert "LINES_SPORTS" in games


def test_lines_board_pins_are_on_the_pr_ci_subset():
    yml = _read(ROOT / ".github" / "workflows" / "pr-ci.yml")
    assert "tests/test_mobile_lines_board.py" in yml


def test_a_missing_draw_price_is_remembered():
    src = _read(QUERIES)
    assert re.search(r"^let linesDrawPriceMissing = false;", src, re.M)
    fn = src[src.index("export async function fetchLinesBoardOdds") : src.index("export async function fetchPropLineRows")]
    assert "if (linesDrawPriceMissing)" in fn
    assert "linesDrawPriceMissing = true" in fn


def test_the_board_reloads_when_the_et_date_changes():
    src = _read(MOBILE / "src" / "hooks" / "useLinesBoard.ts")
    assert "AppState" in src
    assert "todayET()" in src
    roll = src[src.index("const roll = () =>") : src.index("const id = setInterval")]
    assert "day === dateRef.current" in roll
    assert "void load()" in roll
    assert "setDate" not in roll
    fn = src[src.index("const load = useCallback") : src.index("\n  useEffect(")]
    assert fn.index("setDate(day)") > fn.index("fetchLinesBoardOdds")
    assert "if (gen !== loadGen.current) return;" in fn


def test_try_again_is_not_spoken_as_try_again_loading():
    a11y = _read(MOBILE / "src" / "lib" / "a11y.ts")
    err = _read(MOBILE / "src" / "components" / "ErrorState.tsx")
    assert "export function retryAccessibilityLabel" in a11y
    assert "Try loading ${what} again" in a11y
    assert "retryAccessibilityLabel(retryLabel, what)" in err
    assert "${retryLabel} loading ${what}" not in err


def test_lines_is_in_the_anon_manifest():
    from data.anon_readable import ANON_READABLE

    assert "v_latest_odds_all_books" in ANON_READABLE
    assert "games" in ANON_READABLE


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_lines_board.ts"],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
