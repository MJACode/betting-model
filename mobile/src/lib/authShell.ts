/**
 * What the shell does once AUTH is on. Pure: no React, no react-native.
 * verify_auth.ts imports this. The flags stay off in source; EAS sets them.
 *
 * A signed-out session may sit on SignIn and nowhere else. Signals and Live
 * Signals, for a free member, open the same paywall as a locked pick. All
 * stays the teaser. Scoreboard keeps its own lock sheet.
 */

export function signedOutRouteIsShell(routeName: string | undefined): boolean {
  return routeName != null && routeName !== 'SignIn';
}

export function freeSegmentOpensPaywall(view: string): boolean {
  return view === 'signals' || view === 'live';
}
