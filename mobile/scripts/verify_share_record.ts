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
  profitFlat: 1120, stakedFlat: 25900, roi: 0.043, winRate: 0.579,
  clvSettled: 200, clvBeat: 116, clvBeatRate: 0.58,
};
// Set after the literal so the pre-existing missing-field error stays the
// same text. The happy path is a stake the view has already reported.
base.risked = 260;
base.units = 11.2;

const msg = buildShareMessage(base, { endUnits: 11.2, since: '2026-04-14' });
check('includes signed ROI', msg.includes('+4.3%'), msg.split('\n')[2]);
check('includes record', msg.includes('150-109'));
check('includes win rate', msg.includes('57.9% win rate'));
check('includes units', msg.includes('+11.20 units'));
check('includes beat-the-close', msg.includes('58% of the time'));
check('includes settled count + since', msg.includes('259 settled picks since 2026-04-14'));
check('includes app link', msg.includes(APP_URL));
check('transparency line present', msg.includes('Nothing cherry-picked'));

// Negative ROI signs correctly; null clv/units lines drop out.
const neg = buildShareMessage(
  { ...base, roi: -0.052, clvBeatRate: null },
  {},
);
check('negative ROI signed with U+2212', neg.includes('\u22125.2%') && !neg.includes('-5.2%'));
check('null CLV → no beat-the-close line', !neg.includes('beat the close') && !neg.includes('Beat the closing'));
check('no units when omitted', !neg.includes('units, 1 to win'));
const loss = buildShareMessage(base, { endUnits: -33.14 });
check('negative units signed with U+2212', loss.includes('\u221233.14 units') && !loss.includes('-33.14'));
check('zero units unsigned', buildShareMessage(base, { endUnits: 0.004 }).includes('\n0.00 units'));

// The OTA can ship before the view has units. roi is then 0 and a caller
// can still hand endUnits 0. The public text must not say either.
const beforeColumns = buildShareMessage(
  { ...base, units: undefined, risked: undefined, roi: 0 },
  { endUnits: 0, since: '2026-04-14' },
);
check('missing stake drops the ROI line', !beforeColumns.includes('ROI') && !beforeColumns.includes('0.0%'), beforeColumns);
check('missing stake drops the units line', !beforeColumns.includes('units'), beforeColumns);
check('missing stake keeps the record', beforeColumns.includes('150-109'), beforeColumns);
check('missing stake keeps the win rate', beforeColumns.includes('57.9% win rate'), beforeColumns);
check('missing stake still names the app', beforeColumns.includes(APP_URL));

// risked 0 is a real total: every pick voided. The cards dash. Sharing it
// would say 0.0% ROI for a selection that risked nothing.
const allVoid = buildShareMessage(
  { ...base, units: 0, risked: 0, roi: 0 },
  { endUnits: 0, since: '2026-04-14' },
);
check('all-void drops the ROI line', !allVoid.includes('ROI') && !allVoid.includes('0.0%'), allVoid);
check('all-void drops the units line', !allVoid.includes('units'), allVoid);
check('all-void keeps the record', allVoid.includes('150-109'), allVoid);
check('all-void keeps the win rate', allVoid.includes('57.9% win rate'), allVoid);

console.log(failures === 0 ? '\nAll share-record checks passed.' : `\n${failures} FAILED.`);
process.exit(failures === 0 ? 0 : 1);
