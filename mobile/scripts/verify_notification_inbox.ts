/**
 * Standalone verification for the notifications inbox helpers
 * (src/lib/notificationInboxHelpers.ts). Run by tests/test_notification_inbox.py
 * under `node --experimental-strip-types`.
 */

import {
  badgeText,
  dayBucket,
  inboxIdFromPush,
  inboxSections,
  inboxTimeLabel,
  parseInboxTime,
  unreadOf,
  withAllRead,
  withRead,
  type InboxItem,
} from '../src/lib/notificationInboxHelpers';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function item(over: Partial<InboxItem>): InboxItem {
  return {
    id: 1, kind: 'new_bets', title: '🟢 2 new BET signals', body: 'a · b',
    data: { v: 1, type: 'new_bets' }, created_at: '2026-11-14T20:30:00+00:00',
    is_read: false, ...over,
  };
}

// 2026-11-14 22:00 ET = 2026-11-15 03:00Z. A UTC calendar would call 20:30Z
// on the 14th "yesterday" from here; ET says today.
const NOW = Date.parse('2026-11-15T03:00:00Z');

check('a Postgres-style timestamp parses',
  parseInboxTime('2026-11-14 18:30:19.92+00') === Date.parse('2026-11-14T18:30:19.92+00:00'));
check('an unreadable timestamp is null', parseInboxTime('nope') === null);

check('today is the ET day, not the UTC one',
  dayBucket('2026-11-14T20:30:00+00:00', NOW) === 'Today');
check('yesterday by ET', dayBucket('2026-11-13T23:00:00+00:00', NOW) === 'Yesterday');
check('older is Earlier', dayBucket('2026-11-10T15:00:00+00:00', NOW) === 'Earlier');

check('a time today reads as the ET clock',
  inboxTimeLabel('2026-11-14T20:30:00+00:00', NOW) === '3:30 PM ET',
  inboxTimeLabel('2026-11-14T20:30:00+00:00', NOW));
check('an older time carries its date',
  inboxTimeLabel('2026-11-10T15:00:00+00:00', NOW) === 'Nov 10 · 10:00 AM ET',
  inboxTimeLabel('2026-11-10T15:00:00+00:00', NOW));

const list = [
  item({ id: 1, created_at: '2026-11-10T15:00:00+00:00', is_read: true }),
  item({ id: 3, created_at: '2026-11-14T22:00:00+00:00' }),
  item({ id: 2, created_at: '2026-11-13T23:00:00+00:00' }),
];
const sections = inboxSections(list, NOW);
check('sections run Today, Yesterday, Earlier',
  sections.map((s) => s.title).join(',') === 'Today,Yesterday,Earlier');
check('newest first within the list', sections[0].data[0].id === 3);

check('unread counts only unopened', unreadOf(list) === 2);
check('opening one clears that one only', unreadOf(withRead(list, 3)) === 1
  && withRead(list, 3).find((i) => i.id === 2)!.is_read === false);
check('opening an unknown id changes nothing', unreadOf(withRead(list, 99)) === 2);
check('read all clears every one', unreadOf(withAllRead(list)) === 0);

check('no badge at zero', badgeText(0) === null);
check('badge shows the count', badgeText(7) === '7');
check('badge caps at 99+', badgeText(140) === '99+');

check('the inbox id is read off the push', inboxIdFromPush({ v: 1, inboxId: 42 }) === 42);
check('a stringified inbox id still reads', inboxIdFromPush({ inboxId: '42' }) === 42);
check('a push from before the inbox marks nothing', inboxIdFromPush({ v: 1, type: 'new_bets' }) === null);
check('a bad inbox id marks nothing', inboxIdFromPush({ inboxId: -3 }) === null);

console.log(failures === 0 ? 'ALL PASS' : `${failures} FAILED`);
if (failures) process.exit(1);
