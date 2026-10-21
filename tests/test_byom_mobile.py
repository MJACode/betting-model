"""BYOM mobile data layer. No screen, and sign-in stays off."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _node_strips_types() -> bool:
    if shutil.which("node") is None:
        return False
    out = subprocess.run(
        ["node", "--version"], capture_output=True, text=True,
    ).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", out)
    return bool(match) and (int(match.group(1)), int(match.group(2))) >= (22, 6)


def test_a_stored_unknown_filter_key_does_not_drop_the_model_list():
    """parseFilters skips one unknown key. byomFilters still rejects it on save."""
    byom = (ROOT / "mobile/src/lib/byom.ts").read_text(encoding="utf-8")
    assert "return readStoredFilters(value);" in byom
    filters = (ROOT / "mobile/src/lib/byomFilters.ts").read_text(encoding="utf-8")
    assert "throw new Error(`unknown filter key: ${key}`)" in filters
    assert "delete src[match[1]]" in filters


def test_the_models_hook_drops_a_stale_response():
    src = (ROOT / "mobile/src/hooks/useByomModels.ts").read_text(encoding="utf-8")
    assert "const seq = useRef(0)" in src
    assert "const id = ++seq.current" in src
    assert src.count("if (seq.current !== id) return") >= 2
    assert "if (seq.current === id) setLoading(false)" in src


def test_the_backtest_hook_drops_a_stale_response():
    src = (ROOT / "mobile/src/hooks/useByomBacktest.ts").read_text(encoding="utf-8")
    assert "const seq = useRef(0)" in src
    assert "const id = ++seq.current" in src
    assert src.count("if (seq.current !== id) return") >= 2
    assert "if (seq.current === id) setLoading(false)" in src
    auth = (ROOT / "mobile/src/lib/authConfig.ts").read_text(encoding="utf-8")
    assert "?? 'false'" in auth
    byom = (ROOT / "mobile/src/lib/byom.ts").read_text(encoding="utf-8")
    assert "export const LINE_BASIS = 'DraftKings line at game start'" in byom
    assert "units_uncapped" not in byom
    assert "units_capped" not in byom


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_byom_filters_reject_mixed_case_and_unknown_keys():
    script = """
import { byomFilters, readStoredFilters } from './mobile/src/lib/byomFilters.ts';
const kept = byomFilters({ side: 'home', role: 'favorite' });
if (kept.side !== 'home' || kept.role !== 'favorite') throw new Error('kept');
if (JSON.stringify(byomFilters(null)) !== '{}') throw new Error('null');
if (JSON.stringify(byomFilters(undefined)) !== '{}') throw new Error('undef');
const stored = readStoredFilters({ side: 'away', stake: 1, weeks: [1] });
if (stored.side !== 'away' || JSON.stringify(stored.weeks) !== '[1]' || 'stake' in stored) {
  throw new Error('stored ' + JSON.stringify(stored));
}
const two = readStoredFilters({ side: 'home', stake: 1, minOdds: -200 });
if (two.side !== 'home' || Object.keys(two).join() !== 'side') {
  throw new Error('two ' + JSON.stringify(two));
}
let mixed = '';
try { readStoredFilters({ Side: 'home', side: 'away' }); }
catch (e) { mixed = String(e); }
if (!mixed.includes('lowercase')) throw new Error('mixed ' + mixed);
const cases = [
  [{ Side: 'home' }, 'lowercase'],
  [{ stake: 1 }, 'unknown filter key'],
  [{ minOdds: -200 }, 'unknown filter key'],
  [{ side: 'away', Side: 'home' }, 'lowercase'],
];
for (const [input, needle] of cases) {
  let message = '';
  try { byomFilters(input); }
  catch (e) { message = String(e); }
  if (!message.includes(needle)) throw new Error(`${JSON.stringify(input)} -> ${message}`);
}
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
