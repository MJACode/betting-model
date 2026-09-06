import { SPORTS, type Sport } from '@/hooks/useSportFilter';
import type { PicksView } from '@/screens/PicksHomeScreen';

/**
 * Where a tapped notification should land.
 *
 * Until 2026-09-06 nothing here existed: `tracking/push_notifier.py` sent no
 * `data` at all and the app installed no response listener, so tapping a push
 * opened whatever screen the user happened to have left the app on. For a live
 * pick — a number the board itself says is up to ~45s stale — that is the whole
 * value of the notification thrown away at the last step.
 *
 * This module is the PURE half: payload in, navigation intent out, no
 * navigation and no side effects, so every branch is testable without a device.
 * `usePushDeepLink` performs the intent.
 *
 * THE PAYLOAD IS A CONTRACT WITH A SENDER THAT SHIPS SEPARATELY. The worker
 * deploys on merge; this app reaches phones by OTA, and an old build can sit on
 * someone's phone for months. So a payload this build does not understand
 * RESOLVES TO NULL and the tap merely opens the app — never a guess, never a
 * throw. `v` is pinned to PUSH_ROUTE_VERSION in push_notifier.py and only a
 * BREAKING change bumps it; a new optional key is not breaking, and a new
 * `type` this build has never heard of simply falls through.
 */

/** Mirrors PUSH_ROUTE_VERSION in tracking/push_notifier.py. */
export const PUSH_ROUTE_VERSION = 1;

export type PushRoute =
  /** Open one pick's detail screen. */
  | { kind: 'pick'; pickId: number }
  /** Open the Picks board on a view, optionally switching sport first. */
  | { kind: 'board'; view: PicksView; sport: Sport | null }
  /** Open one support conversation. */
  | { kind: 'feedbackThread'; threadId: number };

/** Which board view each summary push belongs on. */
const VIEW_FOR_TYPE: Record<string, PicksView> = {
  // In-play picks live on the Live segment, which only renders while that sport
  // has one standing — which is exactly when this push is sent.
  live_signals: 'live',
  // A fresh BET is a signal, so Signals is the shortest path to it.
  new_bets: 'signals',
  // A pick that flipped to AVOID is no longer a signal: Signals is the one
  // board it is guaranteed NOT to be on. Today shows everything scored.
  dropped: 'today',
};

function asPositiveInt(v: unknown): number | null {
  // Expo round-trips `data` through JSON, and some transports stringify
  // numbers, so accept both rather than dropping a valid route on a type.
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN;
  return Number.isInteger(n) && n > 0 ? n : null;
}

function asSport(v: unknown): Sport | null {
  return typeof v === 'string' && (SPORTS as string[]).includes(v) ? (v as Sport) : null;
}

/**
 * Map a notification's `data` to a route, or null when there is nothing
 * trustworthy to act on.
 */
export function routeForPush(data: unknown): PushRoute | null {
  if (data == null || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;

  // An unknown version means a sender newer than this build. Opening the app is
  // the correct outcome; inventing a destination is not.
  if (d.v !== PUSH_ROUTE_VERSION) return null;

  const type = typeof d.type === 'string' ? d.type : null;
  if (!type) return null;

  if (type === 'feedback_reply') {
    const threadId = asPositiveInt(d.threadId);
    return threadId == null ? null : { kind: 'feedbackThread', threadId };
  }

  // A line change is always about one tracked bet, so it always opens that bet.
  if (type === 'line_change') {
    const pickId = asPositiveInt(d.pickId);
    return pickId == null ? null : { kind: 'pick', pickId };
  }

  const view = VIEW_FOR_TYPE[type];
  if (!view) return null;

  // A summary push naming exactly one pick opens that pick — one tap to the
  // bet instead of one tap to a list you then have to search. The sender only
  // sets pickId when the batch is a single pick.
  const pickId = asPositiveInt(d.pickId);
  if (pickId != null) return { kind: 'pick', pickId };

  // Otherwise the board. `sport` is absent when the batch spanned several, and
  // then the sport must NOT change: the board shows one sport at a time, so
  // picking one of them would hide the rest with no way to know it happened.
  return { kind: 'board', view, sport: asSport(d.sport) };
}
