/**
 * PII scrubber and the tags set at Sentry.init.
 *
 *   npx tsx scripts/verify_sentry_scrub.ts
 */

import { scrubBreadcrumb, scrubSentryEvent, scrubString } from '../src/lib/sentryScrub';
import { scopeTags } from '../src/lib/sentryScope';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  console.log(`${cond ? '[PASS]' : '[FAIL]'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!cond) failures++;
}

const event = {
  message: 'login failed for pat@example.com bearer next',
  user: { id: 'keep-me', email: 'pat@example.com', ip_address: '203.0.113.8' },
  tags: { device_id: '11111111-1111-4111-8111-111111111111', screen: 'Settings' },
  extra: { password: 'hunter2', note: 'token=abc123 still here' },
  request: {
    url: 'https://api.example.com/v1?token=sekret&ok=1',
    headers: { Authorization: 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturexx' },
  },
  exception: {
    values: [{
      value: 'sk_live_abcDEF123 failed',
      stacktrace: { frames: [{ filename: '@/lib/sentry.ts', function: 'startSentry' }] },
    }],
  },
};

const scrubbed = scrubSentryEvent(event);

check('the event is kept', scrubbed !== null);
check('an email in a message is removed', !JSON.stringify(scrubbed).includes('pat@example.com'));
check('the user email field is removed', scrubbed.user.email === '[redacted]');
check('the user ip is removed', scrubbed.user.ip_address === '[redacted]');
check('a non-email user id is kept', scrubbed.user.id === 'keep-me');
check('the device id tag is kept', scrubbed.tags.device_id === event.tags.device_id);
check('the screen tag is kept', scrubbed.tags.screen === 'Settings');
check('a password field is removed', scrubbed.extra.password === '[redacted]');
check('a token= value in text is removed', !scrubbed.extra.note.includes('abc123'));
check('a query-string token is removed and the other param stays',
  scrubbed.request.url.includes('token=[redacted]') && scrubbed.request.url.includes('ok=1'));
check('a bearer JWT header is removed',
  !scrubbed.request.headers.Authorization.includes('eyJ') &&
  scrubbed.request.headers.Authorization.includes('[redacted]'));
check('an sk_live key in an exception is removed', !scrubbed.exception.values[0].value.includes('sk_live_'));
check('a stack frame filename is kept', scrubbed.exception.values[0].stacktrace.frames[0].filename === '@/lib/sentry.ts');
check('the input event is not mutated', event.user.email === 'pat@example.com');

const crumb = scrubBreadcrumb({
  category: 'navigation',
  message: 'Settings',
  data: { url: 'https://api.example.com/x?api_key=zzzz&x=1', from: 'Home' },
});
check('a screen breadcrumb is kept', crumb.message === 'Settings' && crumb.data.from === 'Home');
check('a breadcrumb query key is removed', crumb.data.url.includes('api_key=[redacted]') && crumb.data.url.includes('x=1'));

check('a basic auth header value is removed', !scrubString('Basic dXNlcjpwYXNz').includes('dXNlcjpwYXNz'));

const tags = scopeTags({
  deviceId: 'dev-1',
  release: '1.3.0',
  updateId: 'upd-1',
});
check('init tags carry the device id', tags.device_id === 'dev-1');
check('init tags carry the app version as release', tags.release === '1.3.0');
check('init tags carry the update id', tags.update_id === 'upd-1');

const cold = scopeTags({ deviceId: null, release: '1.3.0', updateId: null });
check('a missing device id is absent, not an empty tag', !('device_id' in cold) && !('update_id' in cold));
check('the release tag is still set with no device id', cold.release === '1.3.0');

if (failures) {
  console.error(`${failures} failed`);
  process.exit(1);
}
console.log('ALL PASS');
