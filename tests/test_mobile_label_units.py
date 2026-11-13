"""The app shows one unit number per pick.

Older NFL wind and opener labels end in the model's own
sizing ("DAL @ IND — IND +7.5 · 0.79u · NEW 0m"), while the row beside them
shows the posted stake or the posted units. The stored label is never
rewritten (CLAUDE.md §1c), so the app drops that one token on screen
(`labelWithoutStake`, mobile/src/lib/format.ts) wherever it prints a
stored label, and VoiceOver reads the same text. The bet, the age tag and
every parenthetical stay word for word (CLAUDE.md §00).

tests/test_nfl_label_units.py pins the writer and the server-side surfaces.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MOBILE = ROOT / "mobile"
SRC = MOBILE / "src"
LIB = SRC / "lib"

from tests._node import NODE, node_strips_types  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.skipif(not node_strips_types(), reason="node >= 22.6 not available")
def test_only_the_unit_figure_leaves_an_old_label(tmp_path):
    (tmp_path / "format.ts").write_text(_read(LIB / "format.ts"), encoding="utf-8")
    script = r"""
import { labelWithoutStake } from './format.ts';
const eq = (got, want, what) => {
  if (got !== want) throw new Error(`${what}: ${JSON.stringify(got)} !== ${JSON.stringify(want)}`);
};
eq(labelWithoutStake('DAL @ IND — IND +7.5 · 0.79u · NEW 0m'), 'DAL @ IND — IND +7.5 · NEW 0m', 'opener');
eq(labelWithoutStake('LA @ WAS Under 47.5 · 0.87u'), 'LA @ WAS Under 47.5', 'wind');
eq(labelWithoutStake('TEN @ CIN — CIN -11 · 1.27u · up 12h'), 'TEN @ CIN — CIN -11 · up 12h', 'age after');
eq(labelWithoutStake('CHI @ ATL — CHI +0.5 · NEW 0m · 0.98u'), 'CHI @ ATL — CHI +0.5 · NEW 0m', 'age before');
eq(labelWithoutStake('TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · 1.96u · NEW 0m'),
   'TEN @ NYG — NYG -1 (Opener +2 vs Pinnacle, MGM) · NEW 0m', 'annotated opener');
eq(labelWithoutStake('NYJ @ MIA Under 43.5 (Wind 14 mph, FD) · 1.00u'),
   'NYJ @ MIA Under 43.5 (Wind 14 mph, FD)', 'annotated wind');
for (const kept of ['TEN @ NYG — NYG -1 · NEW 0m', 'NYJ @ MIA Under 43.5',
    'Boston Bruins (Regulation)', 'NYY ML (F5)', 'Aaron Judge Over 0.5 HR',
    'BOS @ MIL — MIL Team Total Under 115.5', 'Islam Makhachev Under 2.5 Rounds',
    'Jadarian Price Over 1.5 Rec (FD)']) {
  eq(labelWithoutStake(kept), kept, kept);
}
eq(labelWithoutStake(null), '', 'null');
eq(labelWithoutStake(undefined), '', 'undefined');
"""
    out = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr


def test_the_helper_and_the_server_strip_the_same_token():
    from tracking.pick_integrity import _STAKE_TOKEN
    src = _read(LIB / "format.ts")
    m = re.search(r"const LABEL_STAKE_TOKEN = /(.+)/gu;", src)
    assert m, "format.ts defines LABEL_STAKE_TOKEN as a /…/gu literal"
    assert m.group(1) == _STAKE_TOKEN.pattern
    # The Signals card peels the same token through the helper, not a copy.
    signals = _read(LIB / "signalsCard.ts")
    assert "labelWithoutStake(text)" in signals
    assert r"\d+(?:\.\d+)?u" not in signals, "a second stake pattern"


# Every place the app prints a stored pick_label beside a stake, units or a
# price, and every VoiceOver label that reads one.
SITES = {
    "lib/markets.ts": 3,                       # pickRowTitle, pickRowMatchup, splitPickTitle
    "components/DailyResultsModal.tsx": 2,     # graded and open rows
    "components/PickCard.tsx": 1,              # the board card's spoken label
    "screens/ModelDetailScreen.tsx": 4,        # upcoming + graded, shown and spoken
    "screens/BuiltInModelDetailScreen.tsx": 2,  # two spoken row labels
    "screens/PerformanceScreen.tsx": 3,        # untrack alert, spoken row, stake editor
    "screens/PickDetailScreen.tsx": 2,         # title and the news sheet subtitle
    "lib/parlay.ts": 2,                        # a betslip leg, and a saved slip reopened
    "screens/SavedParlaysScreen.tsx": 2,       # a saved slip's leg row and its hand-off
}


@pytest.mark.parametrize("rel,count", sorted(SITES.items()))
def test_every_label_shown_beside_a_stake_drops_the_old_figure(rel, count):
    src = _read(SRC / rel)
    assert src.count("labelWithoutStake(") >= count, rel
    # No bare label left in a Text child or a spoken label at those sites.
    code = "\n".join(line.split("//", 1)[0] for line in src.splitlines())
    assert not re.search(r"\{\s*(?:\w+\.)*pick\.pick_label\s*\}", code), rel
    assert not re.search(r"\{\s*item\.pick_label\s*\}", code), rel
    assert not re.search(r"accessibilityLabel=\{\[\s*(?:\w+\.)*pick_label\b", code), rel
