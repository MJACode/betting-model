"""BYOM mobile data layer and the NFL My models screens. Sign-in stays off."""
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


def test_nfl_first_season_matches_the_facts_builder():
    constants = (ROOT / "byom/constants.py").read_text(encoding="utf-8")
    record = (ROOT / "mobile/src/lib/byomRecord.ts").read_text(encoding="utf-8")
    py = re.search(r"DK_HISTORY_START_SEASON = (\d+)", constants)
    ts = re.search(r"BYOM_NFL_FIRST_SEASON = (\d+)", record)
    assert py and ts and py.group(1) == ts.group(1)


def test_backtest_row_reads_units_and_not_the_left_out_count():
    byom = (ROOT / "mobile/src/lib/byom.ts").read_text(encoding="utf-8")
    iface = re.search(r"export interface ByomBacktestRow \{.*?\n\}", byom, re.S)
    assert iface is not None
    assert "units: number | null;" in iface.group(0)
    assert "skipped" not in iface.group(0)
    assert "optionalNum(row, 'units')" in byom
    assert "optionalNum(row, 'risked')" in byom


def test_my_models_screens_do_not_mention_a_left_out_count_or_a_price_estimate():
    # ExplainerScreen keeps its own pre-game unit sentence ("at −110 you lay
    # 1.1u"). That line is not a BYOM price estimate, so it is not scanned here.
    files = [
        ROOT / "mobile/src/screens/ByomBuilderScreen.tsx",
        ROOT / "mobile/src/screens/ByomEditScreen.tsx",
        ROOT / "mobile/src/screens/ByomDetailScreen.tsx",
        ROOT / "mobile/src/screens/ModelsScreen.tsx",
    ]
    files.extend((ROOT / "mobile/src/components/byom").glob("*.tsx"))
    banned = re.compile(
        r"skipped|excluded|left out|left-out|don'?t trust|small sample|[-−]110",
        re.I,
    )
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith(("//", "*", "/*")):
                continue
            if banned.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
    assert hits == []
    note = (ROOT / "mobile/src/components/byom/ByomUnitsNote.tsx").read_text(encoding="utf-8")
    record = (ROOT / "mobile/src/lib/byomRecord.ts").read_text(encoding="utf-8")
    assert "BYOM_UNITS_COPY" in note
    assert "u = units. Each bet is 1u to win at the DraftKings price at game start" in record
    models = (ROOT / "mobile/src/screens/ModelsScreen.tsx").read_text(encoding="utf-8")
    assert "My models" in models
    assert "ByomModelList" in models
    assert "BACKTEST_START_LABEL" not in models


@pytest.mark.skipif(not _node_strips_types(), reason="node >= 22.6 not available")
def test_byom_record_rank_roi_and_filters(tmp_path):
    # Node's type stripper does not resolve extensionless imports. Copy the
    # two modules and add the .ts suffix the way test_mobile_a11y.py does.
    # App sources keep the extensionless form Metro and tsc already resolve.
    for name in ("byomRecord.ts", "byomFilters.ts"):
        src = (ROOT / "mobile/src/lib" / name).read_text(encoding="utf-8")
        src = re.sub(r"from '\./(\w+)';", r"from './\1.ts';", src)
        (tmp_path / name).write_text(src, encoding="utf-8")
    script = r"""
import {
  byomRoi, byomWinRate, currentNflSeason, draftFromFilters, filtersForDraft,
  formatByomRecord, isWholeSeason, marketLabel, nflSeasonList, rankByUnits,
  otherModelWithName, recordFromRows, showsUnits, suggestedName,
} from './byomRecord.ts';

const summed = recordFromRows([
  { bets: 2, wins: 1, losses: 1, pushes: 0, ties: 0, units: 1.5, risked: 4 },
  { bets: 1, wins: 0, losses: 0, pushes: 1, ties: 1, units: 0, risked: 2 },
]);
if (summed.bets !== 3 || summed.wins !== 1 || summed.pushes !== 1 || summed.ties !== 1) {
  throw new Error('sum ' + JSON.stringify(summed));
}
if (summed.units !== 1.5 || summed.risked !== 6) throw new Error('money ' + JSON.stringify(summed));
if (formatByomRecord(summed) !== '1\u20131\u20132') throw new Error('record ' + formatByomRecord(summed));
if (byomWinRate(summed) !== 0.5) throw new Error('rate ' + byomWinRate(summed));
if (byomRoi(summed) !== 0.25) throw new Error('roi ' + byomRoi(summed));

const missing = recordFromRows([
  { bets: 1, wins: 1, losses: 0, pushes: 0, ties: 0, units: 1, risked: null },
]);
if (missing.units !== 1 || missing.risked !== null || byomRoi(missing) !== null) {
  throw new Error('missing risk ' + JSON.stringify(missing));
}
const noUnits = recordFromRows([
  { bets: 1, wins: 1, losses: 0, pushes: 0, ties: 0, units: null, risked: 2 },
]);
if (noUnits.units !== null || byomRoi(noUnits) !== null) throw new Error('no units');
if (byomWinRate({ bets: 2, wins: 0, losses: 0, pushes: 2, ties: 0, units: 0, risked: 0 }) !== null) {
  throw new Error('pushes are not a win rate');
}

const oct = new Date('2026-10-25T16:00:00Z');
const march = new Date('2026-03-15T16:00:00Z');
const before = new Date('2026-09-01T00:30:00Z');
const after = new Date('2026-09-01T04:00:00Z');
if (currentNflSeason(oct) !== 2026) throw new Error('oct ' + currentNflSeason(oct));
if (currentNflSeason(march) !== 2025) throw new Error('march ' + currentNflSeason(march));
if (currentNflSeason(before) !== 2025) throw new Error('before ' + currentNflSeason(before));
if (currentNflSeason(after) !== 2026) throw new Error('after ' + currentNflSeason(after));
const seasons = nflSeasonList(oct);
if (seasons[0] !== 2020 || seasons[seasons.length - 1] !== 2026 || seasons.length !== 7) {
  throw new Error('seasons ' + seasons.join(','));
}

if (!isWholeSeason({})) throw new Error('empty');
if (isWholeSeason({ markets: ['h2h'] })) throw new Error('market is not the whole season');
if (showsUnits({}) || showsUnits({ markets: ['player_pass_yds'] })) throw new Error('props show units');
if (!showsUnits({ markets: ['h2h', 'spreads'] })) throw new Error('game markets hide units');
if (marketLabel({}) !== '\u2014') throw new Error('empty label');
if (marketLabel({ markets: ['h2h', 'player_pass_yds'] }) !== 'Moneyline \u00b7 Props') {
  throw new Error('label ' + marketLabel({ markets: ['h2h', 'player_pass_yds'] }));
}

const kept = filtersForDraft(
  { market: 'totals', side: 'home', role: 'underdog', primetime: true },
  { weeks: [1, 2], side: 'away', markets: ['spreads'] },
);
if (kept.side || kept.role || !kept.primetime || JSON.stringify(kept.weeks) !== '[1,2]') {
  throw new Error('totals ' + JSON.stringify(kept));
}
if (JSON.stringify(kept.markets) !== '["totals"]') throw new Error('markets ' + JSON.stringify(kept.markets));
const spread = filtersForDraft(
  { market: 'spreads', side: 'home', role: 'underdog', primetime: null },
  { weeks: [3] },
);
if (spread.side !== 'home' || spread.role !== 'underdog' || spread.primetime != null) {
  throw new Error('spread ' + JSON.stringify(spread));
}
if (JSON.stringify(spread.weeks) !== '[3]') throw new Error('weeks dropped');
const back = draftFromFilters(spread);
if (!back || back.market !== 'spreads' || back.side !== 'home' || back.role !== 'underdog') {
  throw new Error('draft ' + JSON.stringify(back));
}
if (draftFromFilters({ markets: ['player_pass_yds'] }) !== null) throw new Error('prop draft');
if (suggestedName({ market: 'spreads', side: 'home', role: 'underdog', primetime: null }) !== 'Home underdogs') {
  throw new Error('name');
}
if (suggestedName({ market: 'h2h', side: null, role: null, primetime: null }) !== 'Moneyline') {
  throw new Error('ml name');
}
if (suggestedName({ market: 'totals', side: null, role: null, primetime: true }) !== 'Primetime over/under') {
  throw new Error('total name');
}

const ranked = rankByUnits([
  { id: 'c', name: 'Zero', bets: 0, units: 0, showsUnits: true },
  { id: 'b', name: 'Down', bets: 4, units: -1, showsUnits: true },
  { id: 'a', name: 'Up', bets: 4, units: 5, showsUnits: true },
  { id: 'd', name: 'Props', bets: 10, units: 0, showsUnits: false },
  { id: 'e', name: 'Home', bets: 2, units: 1, showsUnits: true },
  { id: 'f', name: 'Away', bets: 2, units: 1, showsUnits: true },
]);
const order = ranked.map((row) => `${row.name}:${row.rank}`).join(',');
if (order !== 'Up:1,Away:2,Home:3,Down:4,Props:5,Zero:null') throw new Error(order);

const models = [
  { model_id: 'a', name: 'Home underdogs' },
  { model_id: 'b', name: 'Primetime' },
];
const taken = otherModelWithName(models, '  Primetime  ', 'a');
if (!taken || taken.model_id !== 'b') throw new Error('taken ' + JSON.stringify(taken));
if (otherModelWithName(models, 'Primetime', 'b') !== null) throw new Error('self');
if (otherModelWithName(models, 'primetime') !== null) throw new Error('case');
if (otherModelWithName(models, 'Road') !== null) throw new Error('missing');
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_a_rename_saves_the_new_name_before_it_removes_the_old_row():
    """The old row stays until the new name has been saved. A name that
    already belongs to another model is not overwritten without a confirm.
    """
    edit = (ROOT / "mobile/src/screens/ByomEditScreen.tsx").read_text(encoding="utf-8")
    builder = (ROOT / "mobile/src/screens/ByomBuilderScreen.tsx").read_text(encoding="utf-8")
    assert "await deleteByomModel(model.model_id);\n        await saveByomModel" not in edit
    assert edit.index("await saveByomModel") < edit.index("await deleteByomModel")
    assert edit.count("await saveByomModel") == 1
    assert edit.count("await deleteByomModel") == 1
    assert "The old model is still in your list." in edit
    assert "Couldn’t save this model." in edit
    assert "Delete one before renaming." in edit
    assert "savedId !== '' && savedId !== model.model_id" in edit
    assert "BYOM_MODEL_CAP" in edit
    delete_tail = edit.split("await deleteByomModel", 1)[1]
    inner = delete_tail.split("catch (e: unknown)", 1)[1].split("catch (e: unknown)", 1)[0]
    assert "The old model is still in your list." in inner
    assert "Couldn’t save this model." not in inner
    assert "Replace this model?" in edit
    assert "Replace overwrites that model" in edit
    assert "otherModelWithName" in edit
    assert "Replace this model?" in builder
    assert "Replace overwrites that model" in builder
    assert "otherModelWithName" in builder
    assert "deleteByomModel" not in builder
    leaderboard = (ROOT / "mobile/src/hooks/useByomLeaderboard.ts").read_text(encoding="utf-8")
    assert "async function pool" not in leaderboard
    assert "failed: true" in leaderboard
    byom = (ROOT / "mobile/src/lib/byom.ts").read_text(encoding="utf-8")
    assert "export async function pool" in byom
