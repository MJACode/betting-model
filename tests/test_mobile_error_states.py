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


def _run_node(script: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=cwd, capture_output=True, text=True,
    )


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_aborts_are_silent_and_offline_slow_are_narrow():
    """Reviewer #845 MEDIUM 2: an intentional cancel never shows "You're offline"."""
    script = """
import { errorKind, isAbortError } from './mobile/src/lib/errors.ts';
const abort = Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' });
const aborts = [abort, { name: 'AbortError' }, 'AbortError: The user aborted a request.',
  'The operation was aborted.', 'signal is aborted without reason', 'Aborted', { code: 20 }];
for (const e of aborts) {
  if (!isAbortError(e)) throw new Error(`not treated as abort: ${JSON.stringify(e)}`);
  if (['offline', 'slow'].includes(errorKind(e))) throw new Error(`abort reads as ${errorKind(e)}`);
}
for (const e of [new TypeError('Network request failed'), 'TypeError: Failed to fetch', null, '',
                 'Season aborted early for the franchise'])
  if (isAbortError(e)) throw new Error(`false abort: ${JSON.stringify(e)}`);
const kinds = [
  ['Load failed', 'offline'], ['TypeError: Load failed', 'offline'], ['ENOTFOUND host', 'offline'],
  ['Gateway Timeout', 'slow'], ['connect ETIMEDOUT', 'slow'],
  [{ message: 'canceling statement due to statement timeout', code: '57014' }, 'slow'],
  ['Image load failed for logo', 'server'], ['timeout_ms must be positive', 'server'],
  ['offline_mode column missing', 'server'], ['internet_explorer flag', 'server'],
];
for (const [e, want] of kinds) if (errorKind(e) !== want) throw new Error(`${JSON.stringify(e)}: ${errorKind(e)} !== ${want}`);
"""
    proc = _run_node(script, ROOT)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_load_state_behaviour(tmp_path):
    """Reviewer #845: ErrorBanner vs ErrorState, "—" on failure, the Models
    Custom-tab failure and pricesUnavailable — run, not scanned."""
    lib = SRC / "lib"
    (tmp_path / "errors.ts").write_text(_read(lib / "errors.ts"), encoding="utf-8")
    load_state = _read(lib / "loadState.ts").replace("from './errors';", "from './errors.ts';")
    (tmp_path / "loadState.ts").write_text(load_state, encoding="utf-8")
    script = """
import { countLabel, enrichmentTracker, errorSurface, knownCount, loadPresentation, showLivePricesBanner } from './loadState.ts';
import { errorAnnouncement, friendlyError } from './errors.ts';
const eq = (got, want, what) => { if (JSON.stringify(got) !== JSON.stringify(want)) throw new Error(`${what}: ${JSON.stringify(got)}`); };
const abort = { name: 'AbortError' };
eq(loadPresentation({ loading: true, error: null, hasData: false }), { body: 'skeleton', banner: false }, 'first load');
eq(loadPresentation({ loading: false, error: 'x', hasData: false }), { body: 'error', banner: false }, 'failed first load');
eq(loadPresentation({ loading: false, error: 'x', hasData: true }), { body: 'content', banner: true }, 'failed refresh');
eq(loadPresentation({ loading: false, error: null, hasData: false }), { body: 'content', banner: false }, 'loaded empty');
eq(loadPresentation({ loading: false, error: abort, hasData: true }), { body: 'content', banner: false }, 'abort');
const cold = { loading: false, error: 'Failed to fetch', hasData: false };
eq(errorSurface(cold, true), 'state', 'Built-in cold failure');
eq(errorSurface(cold, false), 'banner', 'Custom cold failure');
eq(errorSurface({ ...cold, hasData: true }, false), 'banner', 'Custom refresh failure');
eq(errorSurface({ ...cold, error: null }, false), 'none', 'Custom no error');
eq(errorSurface({ ...cold, error: abort }, false), 'none', 'Custom abort');
eq(countLabel(knownCount(0, { error: 'x', hasData: false })), '—', 'dash on failure');
eq(countLabel(knownCount(0, { error: null, hasData: false })), '0', 'real zero');
eq(countLabel(knownCount(7, { error: 'x', hasData: true })), '7', 'kept count');
const live = { view: 'live', liveError: null, pricesUnavailable: true, liveCount: 3 };
eq(showLivePricesBanner(live), true, 'M2 banner');
eq(showLivePricesBanner({ ...live, view: 'today' }), false, 'M2 other view');
eq(showLivePricesBanner({ ...live, liveCount: 0 }), false, 'M2 empty');
eq(showLivePricesBanner({ ...live, liveError: 'x' }), false, 'M2 over failure');
const t = enrichmentTracker(); eq(t.missed, false, 'clean fetch');
t.onError('odds', new Error('boom')); eq(t.missed, true, 'missed read');
const t2 = enrichmentTracker(); t2.onError('odds', abort); eq(t2.missed, false, 'aborted read');
const c = friendlyError('Failed to fetch', 'today’s MLB picks');
eq(errorAnnouncement(c, 'Nothing is wrong with your picks.'),
   'Couldn’t load today’s MLB picks. You’re offline. Check your connection and try again. Nothing is wrong with your picks.',
   'announcement');
"""
    proc = _run_node(script, tmp_path)
    assert proc.returncode == 0, proc.stderr


def test_reassurance_prop_is_picks_home_only():
    es = _read(SRC / "components" / "ErrorState.tsx")
    assert "reassurance?: string" in es
    assert len(re.findall(r"\{copy\.cause\}</Text>\s*\{reassurance \?", es)) == 2
    assert "errorAnnouncement(copy, reassurance)" in es
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    assert "PICKS_REASSURANCE = 'Nothing is wrong with your picks.'" in home
    assert home.count("reassurance={PICKS_REASSURANCE}") == 2
    others = [
        str(p.relative_to(MOBILE)) for p in SRC.rglob("*.tsx")
        if p.name not in {"PicksHomeScreen.tsx", "ErrorState.tsx"} and re.search(r"\breassurance=", _read(p))
    ]
    assert not others, others


def test_aborts_render_nothing_and_every_catch_skips_them():
    es = _read(SRC / "components" / "ErrorState.tsx")
    assert es.count("if (silent) return null;") == 2
    unguarded = []
    for p in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
        rel = str(p.relative_to(MOBILE))
        if "/lib/" in rel or "SignInScreen" in rel:
            continue
        for i, line in enumerate(_read(p).splitlines(), 1):
            if re.search(r"(setError\(|error: )errorText\(", line) and "isAbortError(" not in line:
                unguarded.append(f"{rel}:{i}")
    assert not unguarded, unguarded
    # The catch-site toasts and the linking alert skip an abort too.
    assert re.search(r"if \(cancelled \|\| isAbortError\(e\)\) return;\s*setSlate", _read(SRC / "components" / "TeamsBoard.tsx"))
    assert re.search(r"if \(cancelled \|\| isAbortError\(e\)\) return;\s*setPropLines", _read(SRC / "screens" / "StatsScreen.tsx"))
    assert "if (!isAbortError(e)) Alert.alert('Couldn’t start linking'" in _read(SRC / "screens" / "ConnectSportsbookScreen.tsx")


def test_models_custom_tab_says_a_failed_load():
    models = _read(SRC / "screens" / "ModelsScreen.tsx")
    assert "errorSurface(load, tab === 'builtin')" in models
    assert "surface === 'banner' ?" in models and "surface === 'state' ?" in models
    assert "error && !failedLoad" not in models
    assert re.search(r"firstLoad \|\| failedLoad \? null : \(\s*!loading &&", models), "ternary not parenthesised"


def test_picks_home_and_live_picks_use_load_state():
    home = _read(SRC / "screens" / "PicksHomeScreen.tsx")
    for fn in ("loadPresentation(", "knownCount(", "showLivePricesBanner("):
        assert fn in home, fn
    live = _read(SRC / "hooks" / "useLivePicks.ts")
    assert "enrichmentTracker(" in live and "setPricesUnavailable(enrichment.missed)" in live


def test_retrying_lows():
    assert "retrying={loading}" not in _read(SRC / "screens" / "PickDetailScreen.tsx")
    board = _read(SRC / "components" / "TeamsBoard.tsx")
    banner = re.search(r"<ErrorBanner\b.*?/>", board, re.S)
    assert banner and "retrying={loading}" in banner.group(0)


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
