/**
 * Send this device a push, from this device, and report what actually
 * happened.
 *
 * WHY THE APP SENDS ITS OWN TEST. Expo's push service is KEYLESS — the worker
 * posts to the same URL with no credential (`tracking/push_notifier.py`), so
 * the app can post to it too. That makes a one-tap end-to-end check possible
 * with no backend endpoint, no deploy, and no waiting for a slate: it
 * exercises the APNs entitlement, the token Apple issued, Expo's delivery, the
 * OS presenting it, and — because the payload is a real routed one — the deep
 * link in `pushRoute.ts`.
 *
 * The one link it does NOT cover is the worker reading `device_push_tokens`
 * and choosing what to say. That half is already checkable from a terminal
 * (`python -m tracking.push_notifier --dry-run`), and the registration status
 * in Settings shows whether the row exists at all.
 *
 * `interpretExpoResponse` is pure and exported so scripts/verify_push.ts can
 * run every branch without a device or a network.
 */

import { diagnosePushError, type PushDiagnosis } from '@/lib/pushDiagnosis';
import { PUSH_ROUTE_VERSION } from '@/lib/pushRouteVersion';

export const EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send';

export interface TestPushResult {
  ok: boolean;
  /** Expo's receipt id on success — proof it accepted the message, not that Apple showed it. */
  receiptId?: string;
  /** Present whenever `ok` is false. */
  diagnosis?: PushDiagnosis;
}

/**
 * The message. `data` is a REAL route (Picks → Signals) rather than a bespoke
 * test payload, so a tap proves the deep link works too — a test that avoided
 * the contract would pass while the contract was broken.
 */
export function buildTestMessage(token: string): Record<string, unknown> {
  return {
    to: token,
    title: 'Signalbase test',
    body: 'Notifications are working. Tap to open your signals.',
    data: { v: PUSH_ROUTE_VERSION, type: 'new_bets' },
    sound: 'default',
    priority: 'high',
  };
}

/**
 * Read Expo's reply.
 *
 * Three shapes, and only the first is success:
 *   { "data": [ { "status": "ok", "id": "<receipt>" } ] }
 *   { "data": [ { "status": "error", "message": "...",
 *                 "details": { "error": "DeviceNotRegistered" } } ] }
 *   { "errors": [ { "code": "...", "message": "..." } ] }
 *
 * A 200 is NOT a delivery. `_expo_send` in the worker treated it as one until
 * 2026-09-12 and would have reported "sent" for a message Apple refused.
 */
export function interpretExpoResponse(body: unknown): TestPushResult {
  if (body == null || typeof body !== 'object') {
    return { ok: false, diagnosis: diagnosePushError('Expo returned an empty response.') };
  }
  const b = body as { data?: unknown; errors?: unknown };

  if (Array.isArray(b.errors) && b.errors.length > 0) {
    const first = b.errors[0] as { message?: unknown; code?: unknown };
    const text = [first?.message, first?.code].filter((v) => typeof v === 'string').join(' ');
    return { ok: false, diagnosis: diagnosePushError(text || 'Expo rejected the request.') };
  }

  // A single message in, so a single ticket out. Expo also accepts a bare
  // object for a one-message send, so tolerate both rather than failing a
  // successful push on its envelope.
  const tickets = Array.isArray(b.data) ? b.data : b.data != null ? [b.data] : [];
  if (tickets.length === 0) {
    return { ok: false, diagnosis: diagnosePushError('Expo returned no ticket for the message.') };
  }

  const ticket = tickets[0] as {
    status?: unknown;
    id?: unknown;
    message?: unknown;
    details?: { error?: unknown };
  };

  if (ticket?.status === 'ok') {
    return { ok: true, receiptId: typeof ticket.id === 'string' ? ticket.id : undefined };
  }

  // Expo's machine-readable code first, its prose second — the code is what
  // the rules in pushDiagnosis match on, and the prose is what the reader
  // understands. Both are kept: `detail` carries whichever we had.
  const code = typeof ticket?.details?.error === 'string' ? ticket.details.error : '';
  const message = typeof ticket?.message === 'string' ? ticket.message : '';
  const text = [code, message].filter(Boolean).join(': ') || 'Expo refused the message.';
  return { ok: false, diagnosis: diagnosePushError(text) };
}

/** POST the test message. Never throws — a thrown error comes back diagnosed. */
export async function sendTestPush(token: string): Promise<TestPushResult> {
  try {
    const resp = await fetch(EXPO_PUSH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(buildTestMessage(token)),
    });
    // A non-2xx still carries a JSON body worth reading; fall back to the
    // status line only when it does not parse.
    const body = await resp.json().catch(() => null);
    if (body == null) {
      return {
        ok: false,
        diagnosis: diagnosePushError(`Expo replied ${resp.status} with no readable body.`),
      };
    }
    return interpretExpoResponse(body);
  } catch (err) {
    return { ok: false, diagnosis: diagnosePushError(err, 'network') };
  }
}
