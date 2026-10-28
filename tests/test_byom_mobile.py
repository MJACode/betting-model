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
  assertByomSide, byomRoi, byomWinRate, currentNflSeason, draftFromFilters,
  filtersForDraft, formatByomRecord, isWholeSeason, marketLabel, nflSeasonList,
  otherModelWithName, propSideAfterMarketChange, rankByUnits, recordFromRows,
  saveBlockReason, showsUnits, sideForMarket, suggestedName,
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
if (showsUnits({})) throw new Error('empty shows units');
if (!showsUnits({ markets: ['player_pass_yds'] })) throw new Error('prop hides units');
if (!showsUnits({ markets: ['h2h', 'player_pass_yds'] })) throw new Error('mix hides units');
if (showsUnits({ markets: ['not_a_market'] })) throw new Error('unknown shows units');
if (!showsUnits({ markets: ['h2h', 'spreads'] })) throw new Error('game markets hide units');
if (marketLabel({}) !== '\u2014') throw new Error('empty label');
if (marketLabel({ markets: ['h2h', 'player_pass_yds'] }) !== 'Moneyline \u00b7 Passing yards') {
  throw new Error('label ' + marketLabel({ markets: ['h2h', 'player_pass_yds'] }));
}
if (marketLabel({ markets: ['player_anytime_td'] }) !== 'Anytime TD') throw new Error('atd label');
if (marketLabel({ markets: ['player_sacks'] }) !== 'Sacks') throw new Error('sacks label');
if (marketLabel({ markets: ['player_sacks'], prop_side: 'under' }) !== 'Sacks \u00b7 Under') {
  throw new Error('sacks side ' + marketLabel({ markets: ['player_sacks'], prop_side: 'under' }));
}
if (marketLabel({ markets: ['player_anytime_td'], prop_side: 'over' }) !== 'Anytime TD') {
  throw new Error('atd side label');
}
if (marketLabel({ markets: ['mystery_market'] }) !== 'Props') throw new Error('unknown label');

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
const bareProp = draftFromFilters({ markets: ['player_pass_yds'] });
if (!bareProp || bareProp.market !== 'player_pass_yds' || bareProp.propSide || bareProp.side) {
  throw new Error('bare prop ' + JSON.stringify(bareProp));
}
if (suggestedName({ market: 'spreads', side: 'home', role: 'underdog', primetime: null }) !== 'Home underdogs') {
  throw new Error('name');
}
if (suggestedName({ market: 'h2h', side: null, role: null, primetime: null }) !== 'Moneyline') {
  throw new Error('ml name');
}
if (suggestedName({ market: 'totals', side: null, role: null, primetime: true }) !== 'Primetime over/under') {
  throw new Error('total name');
}
if (suggestedName({ market: 'totals', side: 'over', role: null, primetime: null }) !== 'Over') {
  throw new Error('over name');
}
if (suggestedName({ market: 'totals', side: 'under', role: null, primetime: true }) !== 'Primetime under') {
  throw new Error('under name');
}
if (suggestedName({ market: 'player_pass_yds', side: null, role: null, primetime: null, propSide: 'over' }) !== 'Passing yards over') {
  throw new Error('prop name');
}
if (suggestedName({ market: 'player_rush_yds', side: 'home', role: null, primetime: true, propSide: 'under' }) !== 'Primetime home rushing yards under') {
  throw new Error('prop home name');
}
if (suggestedName({ market: 'player_anytime_td', side: null, role: null, primetime: null, propSide: 'over' }) !== 'Anytime TD') {
  throw new Error('atd name');
}
if (suggestedName({ market: 'player_anytime_td', side: 'away', role: null, primetime: null, propSide: 'over' }) !== 'Away anytime TD') {
  throw new Error('atd away name');
}
const propKept = filtersForDraft(
  { market: 'player_pass_yds', side: 'away', role: 'favorite', primetime: true, propSide: 'over' },
  { weeks: [4], prop_side: 'under', role: 'underdog' },
);
if (propKept.prop_side !== 'over' || propKept.side !== 'away' || propKept.role || propKept.primetime !== true) {
  throw new Error('prop kept ' + JSON.stringify(propKept));
}
if (JSON.stringify(propKept.weeks) !== '[4]' || JSON.stringify(propKept.markets) !== '["player_pass_yds"]') {
  throw new Error('prop weeks ' + JSON.stringify(propKept));
}
const atdUnder = filtersForDraft(
  { market: 'player_anytime_td', side: 'home', role: null, primetime: null, propSide: 'under' },
);
if (atdUnder.prop_side !== 'over' || atdUnder.side !== 'home') throw new Error('atd under ' + JSON.stringify(atdUnder));
const atdYes = filtersForDraft(
  { market: 'player_anytime_td', side: null, role: 'favorite', primetime: false, propSide: 'over' },
);
if (atdYes.prop_side !== 'over' || atdYes.side || atdYes.role || atdYes.primetime !== false) {
  throw new Error('atd yes ' + JSON.stringify(atdYes));
}
const gameDropsProp = filtersForDraft(
  { market: 'h2h', side: 'home', role: 'favorite', primetime: null, propSide: 'over' },
  { prop_side: 'under' },
);
if (gameDropsProp.prop_side || gameDropsProp.side !== 'home' || gameDropsProp.role !== 'favorite') {
  throw new Error('game drop ' + JSON.stringify(gameDropsProp));
}
const over = filtersForDraft(
  { market: 'totals', side: 'over', role: 'favorite', primetime: null },
);
if (over.side !== 'over' || over.role) throw new Error('over kept ' + JSON.stringify(over));
const under = filtersForDraft(
  { market: 'totals', side: 'under', role: null, primetime: false },
);
if (under.side !== 'under' || under.primetime !== false) throw new Error('under kept');
const backOver = draftFromFilters(over);
if (!backOver || backOver.market !== 'totals' || backOver.side !== 'over' || backOver.role) {
  throw new Error('back over ' + JSON.stringify(backOver));
}
if (sideForMarket('totals', 'home') !== null || sideForMarket('spreads', 'over') !== null) {
  throw new Error('side for market');
}
if (sideForMarket('h2h', 'away') !== 'away' || sideForMarket('totals', 'under') !== 'under') {
  throw new Error('side kept');
}
if (sideForMarket('player_pass_yds', 'over') !== null || sideForMarket('player_pass_yds', 'home') !== 'home') {
  throw new Error('prop team side');
}
if (propSideAfterMarketChange('player_anytime_td', 'player_pass_yds', 'over') !== null) {
  throw new Error('leaving anytime should clear over');
}
if (propSideAfterMarketChange('player_pass_yds', 'player_sacks', 'under') !== 'under') {
  throw new Error('other props should keep under');
}
if (propSideAfterMarketChange('player_pass_yds', 'player_anytime_td', 'under') !== 'over') {
  throw new Error('anytime is yes');
}
if (propSideAfterMarketChange('player_anytime_td', 'h2h', 'over') !== null) {
  throw new Error('game clears prop side');
}
const block = (market, side, role) => saveBlockReason({ market, side, role, primetime: null });
if (!block('h2h', null, null) || !block('h2h', null, null).includes('team')) throw new Error('ml any');
if (!block('spreads', null, null) || !block('spreads', null, null).includes('team')) {
  throw new Error('spread any');
}
if (!block('totals', null, null) || !block('totals', null, null).includes('over or under')) {
  throw new Error('total none');
}
if (block('totals', 'home', 'favorite') == null) throw new Error('total home is not a side');
if (block('h2h', 'over', null) == null) throw new Error('ml over is not a team');
if (block('h2h', null, 'favorite') != null) throw new Error('fav should save');
if (block('spreads', null, 'underdog') != null) throw new Error('dog should save');
if (block('h2h', null, 'pickem') != null) throw new Error('pickem should save');
if (block('spreads', 'away', null) != null) throw new Error('away should save');
if (block('h2h', 'home', null) != null) throw new Error('home should save');
if (block('totals', 'over', null) != null) throw new Error('over should save');
if (block('totals', 'under', null) != null) throw new Error('under should save');
const mustThrow = (filters, needle) => {
  let message = '';
  try { assertByomSide(filters); }
  catch (e) { message = String(e); }
  if (!message.includes(needle)) throw new Error(JSON.stringify(filters) + ' -> ' + message);
};
mustThrow({ markets: ['h2h'] }, 'team');
mustThrow({ markets: ['spreads'] }, 'team');
mustThrow({ markets: ['totals'] }, 'over or under');
mustThrow({ markets: ['totals'], side: 'home' }, 'over or under');
mustThrow({ markets: ['h2h'], side: 'over' }, 'team');
assertByomSide({ markets: ['h2h'], role: 'favorite' });
assertByomSide({ markets: ['spreads'], side: 'away' });
assertByomSide({ markets: ['h2h'], side: 'home', role: 'underdog' });
assertByomSide({ markets: ['totals'], side: 'over' });
assertByomSide({ markets: ['totals'], side: 'under' });
assertByomSide({});
mustThrow({ markets: ['player_pass_yds'] }, 'over or under');
mustThrow({ markets: ['player_anytime_td'] }, 'yes');
mustThrow({ markets: ['player_anytime_td'], prop_side: 'under' }, 'yes');
assertByomSide({ markets: ['player_pass_yds'], prop_side: 'over' });
assertByomSide({ markets: ['player_pass_yds'], prop_side: 'under', side: 'away' });
assertByomSide({ markets: ['player_anytime_td'], prop_side: 'over', side: 'home' });
assertByomSide({ markets: ['h2h', 'spreads'] });
const propBlock = saveBlockReason({
  market: 'player_receptions', side: null, role: null, primetime: null, propSide: null,
});
if (!propBlock || !propBlock.includes('over or under')) throw new Error('prop block ' + propBlock);
const anyBlock = saveBlockReason({
  market: 'player_pass_yds', side: null, role: 'favorite', primetime: null, propSide: 'over',
});
if (anyBlock != null) throw new Error('any team should save ' + anyBlock);

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


def test_save_requires_a_side_or_a_favorite():
    """Team Any with no favorite or underdog cannot save. A total with
    no over or under cannot save. Either choice on a side market can.
    """
    record = (ROOT / "mobile/src/lib/byomRecord.ts").read_text(encoding="utf-8")
    assert "Choose a team, or a favorite or underdog." in record
    assert "Choose over or under." in record
    builder = (ROOT / "mobile/src/screens/ByomBuilderScreen.tsx").read_text(encoding="utf-8")
    edit = (ROOT / "mobile/src/screens/ByomEditScreen.tsx").read_text(encoding="utf-8")
    fields = (ROOT / "mobile/src/components/byom/ByomFields.tsx").read_text(encoding="utf-8")
    for src in (builder, edit):
        assert "saveBlockReason" in src
        assert "sideReason != null" in src
        assert "{sideReason}" in src
    assert "Over and under are both" not in fields
    assert "When is kickoff?" not in builder
    assert "{ value: 'over', label: 'Over' }" in fields
    assert "{ value: 'under', label: 'Under' }" in fields
    assert "NFL player props" in fields
    assert "Player\u2019s team" in fields
    assert 'accessibilityLabel="Side, Yes"' in fields
    assert "{ value: 'yes', label: 'Yes' }" not in fields
    assert "Choose yes." in record
    for label in (
        "Passing yards", "Passing TDs", "Pass attempts", "Completions",
        "Rushing yards", "Rush attempts", "Receiving yards", "Receptions",
        "Rush + rec yards", "Anytime TD", "Tackles + assists", "Sacks",
    ):
        assert label in record
    assert "prop_side" in (ROOT / "mobile/src/lib/byomFilters.ts").read_text(encoding="utf-8")
    assert "propSide" in builder
    assert "onPropSide={setPropSide}" in builder
    assert "propSide" in edit
    assert "onPropSide={setPropSide}" in edit
    assert "Position" not in fields
    assert "line range" not in fields.lower()
    byom = (ROOT / "mobile/src/lib/byom.ts").read_text(encoding="utf-8")
    assert byom.index("assertByomSide(checked)") < byom.index("supabase.rpc('byom_save_model'")
    forward = (ROOT / "data/migrations/byom_total_side_2026_10_25.sql").read_text(encoding="utf-8")
    assert "Choose a team, or a favorite or underdog." in forward
    assert "Choose over or under." in forward
    assert "'over'::text" in forward
    assert "'under'::text" in forward
    assert "byom_backtest_v1" in forward
    assert "byom_saved_models_v1" in forward
    assert "20261023225630" in forward
    assert "20261023222927" in forward
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in forward
    historical = (
        "byom_saved_models_2026_10_16.sql",
        "byom_backtest_rpc_2026_10_16.sql",
        "byom_dk_price_fallback_2026_10_23.sql",
        "byom_dk_start_price_2026_10_23.sql",
    )
    for name in historical:
        text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
        assert "Choose a team, or a favorite or underdog." not in text
        assert "Choose over or under." not in text
        assert "'over'::text" not in text
        assert "'under'::text" not in text
