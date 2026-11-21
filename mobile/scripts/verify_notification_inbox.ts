/**
 * The inbox rules that do not need a device.
 *
 *   npx tsx scripts/verify_notification_inbox.ts
 *
 * Muted sports leave the list and the badge. The 7-day window is rolling.
 * A one-pick alert still routes to that pick. The bell is on every tab.
 * The badge is set from the same count, and a read dismisses that id.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { applyUnreadBadge, dismissInboxNotifications, inboxIdOf } from '../src/lib/notificationBadge';
import {
  inboxRouteCaption,
  inboxSection,
  inboxTimeLabel,
  mutedSports,
  unreadCount,
  visibleInbox,
  type InboxRow,
} from '../src/lib/notificationInbox';

let passed = 0;
const failures: string[] = [];

function check(label: string, cond: boolean) {
  if (cond) passed++;
  else failures.push(label);
}

function row(partial: Partial<InboxRow> & Pick<InboxRow, 'id' | 'kind' | 'sent_at'>): InboxRow {
  return {
    title: partial.title ?? partial.kind,
    body: partial.body ?? '',
    sport: partial.sport ?? null,
    route: partial.route ?? { v: 1, type: partial.kind },
    notification_id: partial.notification_id ?? partial.id,
    read_at: partial.read_at ?? null,
    ...partial,
  };
}

const now = new Date('2026-11-18T19:55:00-05:00');
const minutesAgo = (m: number) => new Date(now.getTime() - m * 60000).toISOString();

const live = row({
  id: '1',
  kind: 'live_signals',
  title: '🔴 1 live pick',
  body: 'First Half Charleston Southern +2.5',
  sport: 'NCAAB',
  sent_at: minutesAgo(8),
  route: { v: 1, type: 'live_signals', pickId: 42, sport: 'NCAAB' },
});
const bets = row({
  id: '2',
  kind: 'new_bets',
  title: '🟢 4 new BET signals',
  sport: null,
  sent_at: minutesAgo(12),
  route: { v: 1, type: 'new_bets' },
});
const moved = row({
  id: '3',
  kind: 'line_change',
  title: '📉 Line moved against you',
  sport: 'NCAAB',
  sent_at: minutesAgo(25),
  route: { v: 1, type: 'line_change', pickId: 7, sport: 'NCAAB' },
});
const ufc = row({
  id: '4',
  kind: 'new_bets',
  title: '🟢 1 new BET signal',
  sport: 'UFC',
  sent_at: minutesAgo(30),
  route: { v: 1, type: 'new_bets', pickId: 3, sport: 'UFC' },
});
const old = row({
  id: '5',
  kind: 'test',
  title: 'Signalbase test',
  sent_at: '2026-11-01T12:00:00',
  route: { v: 1, type: 'dropped' },
});
const feedback = row({
  id: '6',
  kind: 'feedback_reply',
  title: '💬 We replied to your feedback',
  sent_at: '2026-11-17T15:00:00',
  read_at: '2026-11-17T16:00:00',
  route: { v: 1, type: 'feedback_reply', threadId: 9 },
});

const muted = mutedSports([
  { sport: 'UFC', enabled: false },
  { sport: 'NBA', enabled: true },
]);
const visible = visibleInbox([live, bets, moved, ufc, old, feedback], muted, now);

check('a muted sport is hidden', !visible.some((r) => r.id === '4'));
check('an 8-day-old row is hidden', !visible.some((r) => r.id === '5'));
check('feedback with no sport stays', visible.some((r) => r.id === '6'));
check('unread count ignores the muted row and the old row', unreadCount(visible) === 3);
check('a read feedback row is not unread', unreadCount(visible.filter((r) => r.kind === 'feedback_reply')) === 0);

check('today is Today', inboxSection(live.sent_at, now) === 'TODAY');
check('yesterday is Earlier', inboxSection(feedback.sent_at, now) === 'EARLIER');
check('8 minutes reads 8m', inboxTimeLabel(live.sent_at, now) === '8m');
check('the day before reads Yesterday', inboxTimeLabel(feedback.sent_at, now) === 'Yesterday');

check('a live pick says it opens the pick', inboxRouteCaption(live) === 'Live · opens this pick');
check('a summary says it opens Signals', inboxRouteCaption(bets) === 'Signals · opens Picks · Signals');
check('a line move says it opens the pick', inboxRouteCaption(moved) === 'Tracked bet · opens this pick');
check(
  'the test says it opens Today',
  inboxRouteCaption(row({ id: 't', kind: 'test', sent_at: minutesAgo(1), route: { v: 1, type: 'dropped' } })) ===
    'Test · opens Picks · Today',
);

const badgeCalls: number[] = [];
const dismissed: string[] = [];
const fake = {
  async setBadgeCountAsync(count: number) {
    badgeCalls.push(count);
    return true;
  },
  async getPresentedNotificationsAsync() {
    return [
      { request: { identifier: 'os-1', content: { data: { inboxId: 'na' } } } },
      { request: { identifier: 'os-2', content: { data: { inboxId: 'other' } } } },
      { request: { identifier: 'os-3', content: { data: { v: 1 } } } },
    ];
  },
  async dismissNotificationAsync(identifier: string) {
    dismissed.push(identifier);
  },
};
async function checkBadge() {
  await applyUnreadBadge(3, fake);
  await dismissInboxNotifications(['na'], fake);
  check('the badge is the unread count', badgeCalls.join(',') === '3');
  check('only the matching Signalbase notification is dismissed', dismissed.join(',') === 'os-1');
  check('a notification without inboxId is not ours', inboxIdOf(fakeGet('os-3')) === null);
}

function fakeGet(id: string) {
  return { request: { identifier: id, content: { data: id === 'os-3' ? { v: 1 } : { inboxId: 'na' } } } };
}

const src = (rel: string) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');
const bellScreens = [
  'src/screens/PicksHomeScreen.tsx',
  'src/screens/TrackRecordScreen.tsx',
  'src/screens/PerformanceScreen.tsx',
  'src/screens/ModelsScreen.tsx',
  'src/screens/StatsScreen.tsx',
];
for (const rel of bellScreens) {
  check(`${rel} renders the bell`, src(rel).includes('<NotificationBell />'));
}
check('Picks no longer renders an unread banner (Matt, 2026-11-21: the bell is enough)', !src('src/screens/PicksHomeScreen.tsx').includes('UnreadNotificationsPill'));
check('the badge handler is on', /shouldSetBadge:\s*true/.test(src('src/lib/pushPresentation.ts')));
check(
  'sports switches follow SPORTS and use a gold track',
  src('src/components/SportNotificationSwitches.tsx').includes('SPORTS.map') &&
    src('src/components/SportNotificationSwitches.tsx').includes('trackColor={{ true: colors.tint }}'),
);
check(
  'opening a row uses the push route',
  src('src/screens/NotificationsScreen.tsx').includes('routeForPush') &&
    src('src/screens/NotificationsScreen.tsx').includes('openPushRoute'),
);
check(
  'the inbox does not add a started-pick block',
  !/no longer on the board|has started/.test(src('src/screens/NotificationsScreen.tsx')),
);
const sports = src('src/hooks/useSportFilter.ts');
check(
  'all 12 sports are the switch list',
  sports.includes("'EUROLEAGUE'") && sports.includes("'ATP'") && sports.includes("'WTA'") && sports.includes("'NCAABW'"),
);

checkBadge().then(() => {
  if (failures.length) {
    console.error(`\n${failures.length} failed:\n- ${failures.join('\n- ')}`);
    process.exit(1);
  }
  console.log(`verify_notification_inbox: ${passed} checks passed`);
});
