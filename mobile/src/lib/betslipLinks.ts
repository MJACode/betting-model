/**
 * Betslip link templates — pure, so verify scripts can run it without
 * react-native. The opener lives in sportsbookLinks.ts.
 */

//
// Three books' betslip links arrive from the odds feed as TEMPLATES, measured
// against today's rows (2026-09-04):
//
//   betmgm          https://sports.{state}.betmgm.com/en/sports?options=…&type=Single
//   betrivers       https://{state}.betrivers.com/?page=sportsbook#event/…?coupon={pickType}|…|{wagerAmount}
//   williamhill_us  https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=…
//
// while DraftKings, FanDuel, ESPN BET and Hard Rock carry complete URLs. The
// app opened the templates verbatim: `{state}` is not a host, the open failed,
// and the fallback sent the member to the book's web root with no bet on the
// slip — "it didn't open my mgm app like it does for DK" (Matt). Filled, each
// is the book's own universal link, which iOS routes to the installed app the
// same way it routes DraftKings'.
//
// The state comes from the member (hooks/useBettingState.ts) — it cannot be
// inferred: a New Jersey account opened from a Pennsylvania IP is still a New
// Jersey account. BetRivers' two other placeholders take the values its
// coupon format documents for a single selection: `single` and an empty
// stake, which the book's slip then asks for. NOT yet exercised on a device —
// the sandbox cannot open an app — so verify_book_links.ts pins the shapes
// and the device pass is listed in the session log.

const STATE_PLACEHOLDER = '{state}';

/** Does this link need the member's state before it can be opened? */
export function linkNeedsState(link: string | null | undefined): boolean {
  return !!link && link.includes(STATE_PLACEHOLDER);
}

/**
 * Fill a betslip link's placeholders. Returns null when a placeholder cannot
 * be filled (no state set), so the caller never opens a template.
 */
export function fillBetslipLink(link: string, state: string | null): string | null {
  let out = link.trim();
  if (out.includes(STATE_PLACEHOLDER)) {
    if (!state) return null;
    out = out.split(STATE_PLACEHOLDER).join(state.toLowerCase());
  }
  out = out.split('{pickType}').join('single').split('{wagerAmount}').join('');
  // Anything still templated is a shape we have not seen; do not open it.
  return /\{[a-zA-Z]+\}/.test(out) ? null : out;
}
