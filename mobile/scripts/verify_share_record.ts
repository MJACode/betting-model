/**
 * Verifies the Track Record share text (src/lib/shareRecord.ts).
 *   npx tsx scripts/verify_share_record.ts
 */

import { APP_URL, buildShareMessage } from '../src/lib/shareRecord';
import type { TrackRecordSummary } from '../src/lib/trackRecord';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const base: TrackRecordSummary = {
  picks: 259, wins: 150, losses: 109, pushes: 0,
  profitFlat: 1120, stakedFlat: 25900, roiFlat: 0.043, winRate: 0.579,
  clvSettled: 200, clvBeat: 116, clvBeatRate: 0.58,
};

const msg = buildShareMessage(base, { endUnits: 11.2, since: '2026-04-14' });
check('includes signed ROI', msg.includes('+4.3%'), msg.split('\n')[2]);
check('includes record', msg.includes('150-109'));
check('includes win rate', msg.includes('58% win rate'));
check('includes units', msg.includes('+11.2 units'));
check('includes beat-the-close', msg.includes('58% of the time'));
check('includes settled count + since', msg.includes('259 settled picks since 2026-04-14'));
check('includes app link', msg.includes(APP_URL));
check('transparency line present', msg.includes('Nothing cherry-picked'));

// Negative ROI signs correctly; null clv/units lines drop out.
const neg = buildShareMessage(
  { ...base, roiFlat: -0.052, clvBeatRate: null },
  {},
);
check('negative ROI signed with U+2212', neg.includes('\u22125.2%') && !neg.includes('-5.2%'));
check('null CLV → no beat-the-close line', !neg.includes('beat the close') && !neg.includes('Beat the closing'));
check('no units when omitted', !neg.includes('units on flat'));
const loss = buildShareMessage(base, { endUnits: -33.14 });
check('negative units signed with U+2212', loss.includes('\u221233.1 units') && !loss.includes('-33.1'));
check('zero units unsigned', buildShareMessage(base, { endUnits: 0.04 }).includes('\n0.0 units'));

console.log(failures === 0 ? '\nAll share-record checks passed.' : `\n${failures} FAILED.`);
process.exit(failures === 0 ? 0 : 1);
