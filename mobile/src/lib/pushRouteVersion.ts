/**
 * The push payload's contract version — in its own module because it has to be
 * importable by code that must not pull in a React Native dependency.
 *
 * `pushRoute.ts` owns the routing and reaches `useSportFilter` (and through it
 * AsyncStorage) to validate a sport, which is fine in the app and fatal under
 * tsx. `pushTest.ts` needs only this number, and scripts/verify_push.ts runs
 * it outside React Native — so the constant lives here and pushRoute.ts
 * re-exports it. One definition, no drift.
 *
 * Mirrors PUSH_ROUTE_VERSION in tracking/push_notifier.py. Only a BREAKING
 * payload change bumps it; a new optional key is not breaking.
 */
export const PUSH_ROUTE_VERSION = 1;
