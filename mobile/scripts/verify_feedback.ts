/**
 * Standalone verification for the in-app feedback helpers
 * (src/lib/feedbackHelpers.ts). Run with:
 *
 *   npx tsx scripts/verify_feedback.ts
 *
 * The load-bearing case is parseTimestamp: these columns are TEXT written by
 * Postgres' NOW()::TEXT — "2026-08-24 12:34:56.789+00", a space separator and a
 * two-digit offset — which is NOT ISO-8601 and returns Invalid Date on some JS
 * engines if passed straight to new Date(). Everything with a timestamp on the
 * feedback screens flows through it.
 */

import {
  FEEDBACK_CATEGORIES,
  MAX_FEEDBACK_CHARS,
  categoryLabel,
  feedbackErrorMessage,
  parseTimestamp,
  relativeTime,
  sortThreads,
  statusLabel,
  unreadTotal,
  validateFeedback,
  type FeedbackThread,
} from '../src/lib/feedbackHelpers';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function thread(over: Partial<FeedbackThread>): FeedbackThread {
  return {
    thread_id: 1, category: 'bug', subject: 's', status: 'open',
    created_at: '2026-08-20 10:00:00+00', last_message_at: '2026-08-20 10:00:00+00',
    last_read_at: null, message_count: 1, unread_count: 0,
    last_sender: 'user', last_body: 'hi',
    ...over,
  };
}

// ── parseTimestamp: the Postgres NOW()::TEXT shape ──────────────────────────
const pgShape = '2026-08-24 12:34:56.789012+00';
const pgParsed = parseTimestamp(pgShape);
check('parses Postgres NOW()::TEXT', pgParsed != null && !Number.isNaN(pgParsed));
check(
  'Postgres shape parses to the right instant',
  pgParsed === Date.parse('2026-08-24T12:34:56.789Z'),
  `${pgParsed} vs ${Date.parse('2026-08-24T12:34:56.789Z')}`,
);
check(
  'negative offset handled',
  parseTimestamp('2026-08-24 08:34:56.789-04') === Date.parse('2026-08-24T12:34:56.789Z'),
);
check('plain ISO still parses', parseTimestamp('2026-08-24T12:34:56.789Z') === Date.parse('2026-08-24T12:34:56.789Z'));
check('null in, null out', parseTimestamp(null) === null);
check('empty string → null', parseTimestamp('') === null);
check('garbage → null (never NaN)', parseTimestamp('not a date') === null);

// ── relativeTime ────────────────────────────────────────────────────────────
const base = Date.parse('2026-08-24T12:00:00Z');
check('under a minute', relativeTime('2026-08-24 11:59:30+00', base) === 'just now');
check('minutes', relativeTime('2026-08-24 11:20:00+00', base) === '40m ago');
check('hours', relativeTime('2026-08-24 06:00:00+00', base) === '6h ago');
check('days', relativeTime('2026-08-22 12:00:00+00', base) === '2d ago');
check('over a week falls back to a date', /Aug/.test(relativeTime('2026-08-01 12:00:00+00', base)));
check(
  'future timestamp never reads "in 3 hours"',
  relativeTime('2026-08-24 15:00:00+00', base) === 'just now',
);
check('unparseable renders as empty, not "Invalid Date"', relativeTime('nope', base) === '');

// ── validateFeedback mirrors the server rules ───────────────────────────────
check('rejects empty', validateFeedback('').ok === false);
check('rejects whitespace-only (server trims too)', validateFeedback('   \n  ').ok === false);
const trimmed = validateFeedback('  hello  ');
check('trims before sending', trimmed.ok === true && trimmed.body === 'hello');
check('accepts exactly the cap', validateFeedback('x'.repeat(MAX_FEEDBACK_CHARS)).ok === true);
check('rejects one over the cap', validateFeedback('x'.repeat(MAX_FEEDBACK_CHARS + 1)).ok === false);
check('cap matches the server cap in feedback_submit', MAX_FEEDBACK_CHARS === 4000);

// ── categories match the server whitelist ──────────────────────────────────
const serverWhitelist = ['bug', 'idea', 'picks', 'billing', 'other'];
check(
  'every category key is on the server whitelist',
  FEEDBACK_CATEGORIES.every((c) => serverWhitelist.includes(c.key)),
  FEEDBACK_CATEGORIES.map((c) => c.key).join(','),
);
check('unknown category label falls back', categoryLabel('nonsense') === 'Something else');

// ── status + unread ────────────────────────────────────────────────────────
check('unread wins over status', statusLabel(thread({ status: 'answered', unread_count: 2 })) === 'New reply');
check('answered + read', statusLabel(thread({ status: 'answered' })) === 'Replied');
check('open means the ball is with us', statusLabel(thread({ status: 'open' })) === 'Waiting on us');
check('closed', statusLabel(thread({ status: 'closed' })) === 'Closed');
check(
  'unreadTotal sums across threads',
  unreadTotal([thread({ unread_count: 2 }), thread({ thread_id: 2, unread_count: 3 })]) === 5,
);
check('unreadTotal of nothing is 0', unreadTotal([]) === 0);

// ── sort ───────────────────────────────────────────────────────────────────
const input = [
  thread({ thread_id: 1, last_message_at: '2026-08-20 10:00:00+00' }),
  thread({ thread_id: 2, last_message_at: '2026-08-24 10:00:00+00' }),
  thread({ thread_id: 3, last_message_at: null }),
];
const inputOrder = input.map((t) => t.thread_id).join(',');
const sorted = sortThreads(input);
check('newest activity first', sorted.map((t) => t.thread_id).join(',') === '2,1,3', sorted.map((t) => t.thread_id).join(','));
check('sort does not mutate the caller\'s array', input.map((t) => t.thread_id).join(',') === inputOrder);

// ── error mapping ──────────────────────────────────────────────────────────
check(
  'rate limit is explained',
  feedbackErrorMessage({ message: 'too many messages, try again later' }).includes('later'),
);
check(
  'too many threads is explained',
  feedbackErrorMessage({ message: 'too many open conversations' }).includes('open conversations'),
);
check('length error names the cap', feedbackErrorMessage({ message: 'message too long' }).includes('4,000'));
check(
  "someone else's thread reads as unavailable",
  feedbackErrorMessage({ message: 'thread not found' }).includes("isn't available"),
);
const generic = feedbackErrorMessage({ message: 'ERROR: function feedback_submit(x) does not exist' });
check('unknown errors never leak SQL', !generic.toLowerCase().includes('feedback_submit'), generic);
check('undefined error still returns copy', feedbackErrorMessage(undefined).length > 0);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
