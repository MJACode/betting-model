/**
 * Paused models' picks on the All board (Matt, 2026-09-28; Designer mockups in
 * the paused-on-All PR):
 *
 *   npx tsx scripts/verify_paused_on_all.ts
 *
 * A paused model's pick works like any other pick on All — BET / NONE / AVOID
 * badge, stake, Sharp Score, timing, best book, Slip and Track — with a
 * neutral "Paused" tag, because it is never SENT as a signal. So:
 *   - the strict passesActionFilter (Signals, sport badges) still refuses it,
 *     and Live Signals still drops a paused model;
 *   - the lenient passesActionFilterIgnoringPause (All's "N bets", the card's
 *     green edge, the Edge tint) ignores the pause and the Discord check, but
 *     never counts a VOID, and IS the strict filter for every other model;
 *   - paused rows sort like any other, on every key including Time;
 *   - the betslip resolves paused keys instead of pruning them;
 *   - the tag's VoiceOver text is part of PickCard's one label (#848's rule).
 *
 * Behaviour on the pure libs, then the wiring in the screens (source reads:
 * rendering React Native needs the device). The pytest twin is
 * tests/test_mobile_paused_on_all.py.
 */
import { readFileSync } from 'fs';
import { join } from 'path';
import {
  isModelPaused,
  isPausedForDisplay,
  passesActionFilter,
  passesActionFilterIgnoringPause,
  setServerThresholds,
} from '../src/lib/thresholds';
import { pickTimingInfo } from '../src/lib/markets';
import { signalCountsBySport } from '../src/lib/lineMovementBoard';
import { rowsByDay } from '../src/lib/dateFilter';
import { PAUSED_DETAIL_NOTE, PAUSED_SPOKEN, PAUSED_TAG_TEXT } from '../src/lib/pausedPick';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}
const read = (rel: string) => readFileSync(join(__dirname, '..', rel), 'utf8');

// ── The two filters ─────────────────────────────────────────────────────────
// ncaaf_moneyline is paused in the bundle (min_prob 0.62, min_edge 0.08,
// min_odds −250). The mockups' Alabama ML: model 76.2% at −142, edge +17.5%.
setServerThresholds(null);
const PAUSED_ID = 'ncaaf_moneyline';
const base = {
  model_id: PAUSED_ID, signal_type: 'BET' as const, model_probability: 0.762,
  dk_odds: -142, edge: 0.175, condition_status: null as string | null,
  result: null as string | null, discordPublish: 'unpublished' as const,
};
check('fixture: the model is paused (bundled fallback)', isModelPaused(PAUSED_ID));
check('fixture: an unposted, unsettled pick is drawn as paused', isPausedForDisplay(base));
check('STRICT: a paused model\'s BET is never a signal', passesActionFilter(base) === false);
check('LENIENT: a paused model\'s BET that clears its bar passes', passesActionFilterIgnoringPause(base) === true);
check('LENIENT: ...even with no Discord ledger read (unknown)',
  passesActionFilterIgnoringPause({ ...base, discordPublish: 'unknown' as never }) === true);
check('LENIENT: a paused VOID never counts',
  passesActionFilterIgnoringPause({ ...base, condition_status: 'VOID' }) === false);
check('LENIENT: a paused NONE / AVOID is not a bet',
  !passesActionFilterIgnoringPause({ ...base, signal_type: 'NONE' as never })
  && !passesActionFilterIgnoringPause({ ...base, signal_type: 'AVOID' as never }));
check('LENIENT: the model\'s bar still applies (edge under 8%)',
  passesActionFilterIgnoringPause({ ...base, edge: 0.05 }) === false);
check('LENIENT: the model\'s bar still applies (prob under 62%)',
  passesActionFilterIgnoringPause({ ...base, model_probability: 0.6 }) === false);
check('LENIENT: a retired model is still refused',
  passesActionFilterIgnoringPause({ ...base, model_id: 'mlb_prop_batter_rbi' }) === false);

// For an ACTIVE model the lenient filter IS the strict one, on every VOID /
// Discord combination (a published VOID stays a bet; an unposted VOID doesn't).
{
  const active = { ...base, model_id: 'nhl_moneyline', model_probability: 0.6, dk_odds: 120, edge: 0.15, discordPublish: 'published' as never };
  const combos: Array<[string | null, 'published' | 'unpublished' | undefined]> = [
    [null, 'published'], [null, 'unpublished'], [null, undefined],
    ['VOID', 'published'], ['VOID', 'unpublished'], ['VOID', undefined], ['OK', 'unpublished'],
  ];
  const same = combos.every(([cs, dp]) => {
    const p = { ...active, condition_status: cs, discordPublish: dp as never };
    return passesActionFilter(p) === passesActionFilterIgnoringPause(p);
  });
  check('LENIENT = STRICT for an active model, every VOID / Discord case', same);
  check('fixture: the active BET passes both', passesActionFilter(active) && passesActionFilterIgnoringPause(active));
}

// The server flag, not the bundle, when it has loaded.
setServerThresholds({
  [PAUSED_ID]: { min_prob: 0.62, min_edge: 0.08, min_odds: -250, prob_only: false, paused: true },
});
check('server store: strict refuses, lenient passes',
  passesActionFilter(base) === false && passesActionFilterIgnoringPause(base) === true);
setServerThresholds({
  [PAUSED_ID]: { min_prob: 0.62, min_edge: 0.08, min_odds: -250, prob_only: false, paused: false },
});
check('server store unpaused: both are the same filter again',
  passesActionFilter({ ...base, discordPublish: 'published' as never })
  === passesActionFilterIgnoringPause({ ...base, discordPublish: 'published' as never }));
setServerThresholds(null);

// ── Sport badges are signals: paused rows never badge a chip ────────────────
{
  const row = (pick: object) => ({ pick: { sport: 'NCAAF', game_date: '2026-09-28', ...pick }, game: null }) as never;
  const counts = signalCountsBySport([row(base), row({ ...base, model_id: 'nhl_moneyline', sport: 'NHL', model_probability: 0.6, dk_odds: 120, edge: 0.15, discordPublish: 'published' })]);
  check('sport badges count the active BET, never the paused one',
    counts.NCAAF === undefined && counts.NHL === 1, JSON.stringify(counts));
}

// ── Copy ────────────────────────────────────────────────────────────────────
{
  const created = '2026-09-28T21:19:00Z';
  const t = { ...base, created_at: created, player_id: null, is_live: false, sport: 'NCAAF', game_date: '2026-09-28' } as never;
  const paused = pickTimingInfo(t, { paused: true });
  const posted = pickTimingInfo(t);
  check('timing: a paused pick reads "Picked …"', !!paused && paused.label.startsWith('Picked ') && paused.verb === 'Picked', paused?.label);
  check('timing: any other pick still reads "Posted …"', !!posted && posted.label.startsWith('Posted '), posted?.label);
  check('timing: the paused note says it was not sent', !!paused && /wasn’t sent as a signal/.test(paused.note));
}
check('tag text', PAUSED_TAG_TEXT === 'Paused');
check('VoiceOver text', PAUSED_SPOKEN === 'Model paused, not sent as a signal');
check('detail note', PAUSED_DETAIL_NOTE === 'This model is paused, so this pick isn’t sent as a signal (no Discord or push alerts). Everything else works as usual.');

// ── Time sort: no paused-last partition inside a day ────────────────────────
{
  type R = { id: string; date: string };
  const rows = rowsByDay<R>(
    [{ id: 'a', date: '2026-09-28' }, { id: 'pausedEarly', date: '2026-09-28' }, { id: 'b', date: '2026-09-28' }],
    (r) => r.date, (r) => r.id, undefined, '2026-09-28',
  );
  const order = rows.filter((r) => r.kind === 'item').map((r) => r.key).join(',');
  check('rowsByDay with no trailing keeps kickoff order', order === 'a,pausedEarly,b', order);
}

// ── Wiring ──────────────────────────────────────────────────────────────────
const card = read('src/components/PickCard.tsx');
const home = read('src/screens/PicksHomeScreen.tsx');
const detail = read('src/screens/PickDetailScreen.tsx');
const reasoning = read('src/components/ReasoningCard.tsx');
const slipHook = read('src/hooks/useResolvedSlip.ts');
const leg = read('src/components/ParlayLegCard.tsx');
const tag = read('src/components/PausedTag.tsx');

// Tag renders, badge stays.
check('PickCard: the tag renders on a paused card', /caption && paused \? \([\s\S]*?<PausedTag \/>/.test(card));
check('PickCard: the BET / NONE / AVOID badge is not replaced (no PAUSED pill)',
  !/>PAUSED</.test(card) && /\) : showSignalBadge \? \(\s*<View style=\{styles\.labelChip\}>\s*<SignalBadge/.test(card));
check('PickCard: the VoiceOver text is in cardLabel', /pick\.signal_type,\s*\/\/[^\n]*\n\s*paused \? PAUSED_SPOKEN : null,/.test(card));
check('PausedTag: hidden from VoiceOver unless asked to speak',
  /speak = false/.test(tag) && /accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants'/.test(tag));
check('PausedTag: neutral — hairline separatorOpaque outline, textSecondary, pause glyph, no fill',
  /borderWidth: StyleSheet\.hairlineWidth/.test(tag) && /borderColor: colors\.separatorOpaque/.test(tag)
  && /color: colors\.textSecondary/.test(tag) && /name="pause"/.test(tag) && !/backgroundColor/.test(tag));
check('PausedTag: 11pt on cards, 12pt on detail', /large \? font\.size\.caption : font\.size\.micro/.test(tag));
check('PickDetail: the tag sits beside the model, the badge stays',
  /<Text style=\{styles\.modelName\}>\{modelLong\(pick\.model_id\)\}<\/Text>[\s\S]{0,200}\{paused \? <PausedTag large \/> : null\}/.test(detail)
  && /<SignalBadge signal=\{voided \? 'NONE' : pick\.signal_type\} \/>/.test(detail) && !/'PAUSED'/.test(detail));
check('PickDetail: the textSecondary note replaces "for reference only"',
  /\{paused \? <Text style=\{styles\.pausedNote\}>\{PAUSED_DETAIL_NOTE\}<\/Text> : null\}/.test(detail)
  && /pausedNote: \{[\s\S]*?color: colors\.textSecondary/.test(detail) && !/for reference/.test(detail));
check('ParlayLegCard: a paused leg shows the tag, and it speaks there',
  /leg\.pick && isPausedForDisplay\(leg\.pick\) \? <PausedTag speak \/> : null/.test(leg));

// Normal sort.
check('PicksHome: no paused-last partition', !/all\.filter\(\(d\) => !?isPausedForDisplay/.test(home));
check('PicksHome: Time sort passes no paused trailing key',
  /rowsByDay\(\s*sortPicks\(filtered, 'time'\),\s*\(d\) => d\.pick\.game_date,\s*\(d\) => String\(d\.pick\.pick_id\),\s*\)/.test(home));

// Count.
check('PicksHome: All\'s "N bets" is the lenient filter',
  /const bet = todayData\.filter\(\s*\(d\) => passesActionFilterIgnoringPause\(d\.pick\) && !isUnlockedPreview\(d\.pick\),?\s*\)\.length;/.test(home));
check('PicksHome: " · N paused" is still counted',
  /const paused = todayData\.filter\(\(d\) => isPausedForDisplay\(d\.pick\)\)\.length;/.test(home));
check('PicksHome: Signals stays strict',
  /const live = useMemo\(\s*\(\) => todayData\.filter\(\(d\) => passesActionFilter\(d\.pick\) && !isUnlockedPreview\(d\.pick\)\)/.test(home));
check('PicksHome: sport badges read allData (no paused rows), strict',
  /signalCountsBySport\(allData\)/.test(home) && /if \(!passesActionFilter\(d\.pick\)\) continue;/.test(read('src/lib/lineMovementBoard.ts')));
check('PicksHome: Live Signals still drops a paused model', /!isModelPaused\(d\.pick\.model_id\) &&\s*!isModelRetired/.test(home));
check('PicksHome: a Signal filter keeps paused rows (BET only includes a paused BET)',
  !/displayFilter\.signals\.size === ALL_SIGNALS\.length \|\| !isPausedForDisplay/.test(home));
check('PicksHome: tooltip copy', /tagged Paused\. They work like any other pick, but aren’t sent as signals \(no Discord or push alerts\) and never appear on Signals\./.test(home)
  && !/marked PAUSED/.test(home));

// Chips, stake, Slip, Track, best book.
check('PickCard: Sharp Score and the contrarian chip show on a paused card',
  /const sharp = preview \? null : sharpScore\(pick\);/.test(card) && /const contra = contrarianTag\(pick\);/.test(card));
check('PickCard: stake caption, best book and Slip have no paused gate',
  /pick\.signal_type !== 'BET' \|\| preview\n/.test(card)
  && /const offersBook = !preview && pick\.signal_type === 'BET';/.test(card)
  && /const canSlip =\s*Boolean\(onToggleSlip\) && hasPricedLine\(pick\) && open && !preview && cta\.slip;/.test(card));
check('PickCard: timing shows, as "Picked"', /const timing = openForAction\(pick\) \? pickTimingInfo\(pick, \{ paused \}\) : null;/.test(card));
check('PickCard: green edge from the lenient filter', /const qualifies = passesActionFilterIgnoringPause\(pick\);/.test(card));
check('PickCard: the reference-only line is gone', !/shown for reference/.test(card) && !/pausedLabel/.test(card));
check('PickDetail: timing, Sharp, bet-at and betslip have no paused gate',
  /<PickTimingCard pick=\{pick\} paused=\{paused\} \/>/.test(detail) && /\n\s*<SharpScoreCard pick=\{pick\} \/>/.test(detail)
  && /\{pick\.signal_type === 'BET' && !preview && !retired && !voided \? \(\s*cta\.handoff/.test(detail)
  && /hasPricedLine\(pick\) && openHere && !preview && !retired\s*&& !voided && cta\.slip/.test(detail));
check('ReasoningCard: stake row shown, "the stake the model would publish", lenient tint, no paused heading',
  /pick\.signal_type === 'BET' && !isUnlockedPreview\(pick\) \? \(/.test(reasoning)
  && /the stake the model would publish/.test(reasoning)
  && /tint=\{passesActionFilterIgnoringPause\(pick\)/.test(reasoning)
  && /reasoningHeading\(pick\.signal_type, \{ preview: isUnlockedPreview\(pick\) \}\)/.test(reasoning));

// Betslip keeps paused keys.
check('useResolvedSlip: the board includes pausedData',
  /const \{ data, pausedData, loading, error \} = picks;/.test(slipHook)
  && /\[\.\.\.data, \.\.\.pausedData, \.\.\.livePicks\.data\]/.test(slipHook));

// The mock switch must never ship.
check('no __fix mock switch anywhere it could ship',
  ![card, home, detail, reasoning, slipHook, leg, tag].some((s) => /__fix|fix\('PAUSED'\)/.test(s)));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
