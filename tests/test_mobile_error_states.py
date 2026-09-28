"""Error, empty and loading states — usability audit PR 2 (2026-09-25).

H3: a failed or unfinished load no longer looks like "zero". M1: failures
say what failed, one plain cause and Retry, never the raw Supabase text.
M2: a prices-unavailable banner. M12: "No picks match" when only the search
emptied the list. L11: a vanished pick offers "Open Picks". Skeletons hold
still under Reduce Motion.

The behavioural checks live in `mobile/scripts/verify_error_states.ts`. This
file pins the wiring from source (CI has no node modules), runs the pure
error classifier under node's type stripping, and runs the tsx script when
node modules are installed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"

RAW_IN_TEXT = re.compile(
    r"\{\s*(?:\w+\.)*(?:error|err|e|\w+Error)(?:\.message)?\s*\}|errorText\(|\.message\b|Connection error"
)
TEXT_ELEMENT = re.compile(r"<Text\b[^>]*>(.*?)</Text>", re.S)
# The sign-in form: the auth message IS the instruction ("Invalid login credentials").
ALLOW = {"src/screens/SignInScreen.tsx"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _raw_error_lines(src: str) -> list[int]:
    return [
        src[: m.start()].count("\n") + 1
        for m in TEXT_ELEMENT.finditer(src)
        if RAW_IN_TEXT.search(m.group(1))
    ]


def test_scanner_probe():
    assert _raw_error_lines("<Text style={s.e}>Couldn’t load: {error}</Text>") == [1]
    assert _raw_error_lines("<Text>\n  {errorText(e)}\n</Text>") == [1]
    assert _raw_error_lines("<Text>{`Couldn’t load — ${d.recent.error}`}</Text>") == [1]
    assert _raw_error_lines("<Text>{friendlyCause(error)}</Text>") == []


def test_no_raw_error_text_rendered():
    hits = []
    for path in SRC.rglob("*.tsx"):
        rel = str(path.relative_to(MOBILE))
        if rel in ALLOW:
            continue
        hits += [f"{rel}:{n}" for n in _raw_error_lines(_read(path))]
    assert hits == []


def test_error_state_component():
    src = _read(SRC / "components" / "ErrorState.tsx")
    assert src.count("color={colors.avoidInk}") == 2
    assert not re.search(r"colors\.avoid\b(?!Ink|Soft)", src)
    assert src.count('accessibilityRole="alert"') == 2
    assert src.count("minHeight: 44") >= 2
    assert "announceForAccessibility" in src
    assert "friendlyError(error, what)" in src


def test_skeleton_respects_reduce_motion():
    assert "useReduceMotion()" in _read(SRC / "components" / "Skeleton.tsx")
    assert "useState(true)" in _read(SRC / "hooks" / "useReduceMotion.ts")


@pytest.mark.parametrize(
    "rel, tag",
    [
        ("screens/PicksHomeScreen.tsx", "<ErrorState"),
        ("screens/PicksHomeScreen.tsx", "<ErrorBanner"),
        ("screens/TrackRecordScreen.tsx", "<ErrorState"),
        ("screens/ModelsScreen.tsx", "<ErrorState"),
        ("screens/ModelsScreen.tsx", "<Skeleton"),
        ("screens/PickDetailScreen.tsx", "<ErrorState"),
        ("screens/ParlayScreen.tsx", "<ErrorBanner"),
        ("screens/TeamStatsScreen.tsx", "<ErrorBanner"),
        ("screens/PlayerStatsScreen.tsx", "<ErrorBanner"),
        ("screens/ModelDetailScreen.tsx", "<ErrorBanner"),
        ("screens/BuiltInModelDetailScreen.tsx", "<ErrorBanner"),
        ("screens/OpeningComparisonScreen.tsx", "<ErrorBanner"),
        ("components/TeamsBoard.tsx", "<ErrorBanner"),
    ],
)
def test_screens_use_the_shared_error_state(rel, tag):
    assert tag in _read(SRC / rel)


def test_search_empty_prices_banner_and_vanished_pick():
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    assert "No picks match" in home and "emptiedBySearch" in home and "Clear search" in home
    assert "pricesUnavailable" in home
    assert "Open Picks" in _read(SRC / "screens" / "PickDetailScreen.tsx")


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_friendly_error_behaviour():
    script = """
import { errorKind, friendlyCause, friendlyError } from './mobile/src/lib/errors.ts';
const cases = [
  [errorKind(new TypeError('Network request failed')), 'offline'],
  [errorKind('TypeError: Failed to fetch'), 'offline'],
  [errorKind({ message: 'canceling statement due to statement timeout', code: '57014' }), 'slow'],
  [errorKind({ message: 'JWT expired', code: 'PGRST301' }), 'auth'],
  [errorKind({ message: 'schema cache', code: 'PGRST002' }), 'server'],
  [errorKind({}), 'server'], [errorKind(null), 'server'],
  [friendlyError({ message: 'relation "picks" does not exist', code: '42P01' }, 'today’s MLB picks').title,
   'Couldn’t load today’s MLB picks'],
];
for (const [got, want] of cases) if (got !== want) throw new Error(`${got} !== ${want}`);
const f = friendlyError({ message: 'relation "picks" does not exist', code: '42P01' }, 'x');
if (/relation|42P01/.test(f.title + f.cause)) throw new Error('raw text leaked');
if (/object Object/.test(friendlyCause({}))) throw new Error('[object Object]');
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_error_state_pins_are_on_the_pr_ci_subset():
    yml = _read(ROOT / ".github" / "workflows" / "pr-ci.yml")
    assert "tests/test_mobile_error_states.py" in yml


@pytest.mark.skipif(
    not (MOBILE / "node_modules" / ".bin").exists() or shutil.which("node") is None,
    reason="mobile node modules not installed",
)
def test_the_behavioural_checks_pass():
    tsx = MOBILE / "node_modules" / ".bin" / "tsx"
    proc = subprocess.run(
        [str(tsx), "scripts/verify_error_states.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
