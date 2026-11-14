/**
 * Settings home (Option B): one short live line per section tile.
 *
 * The drill-ins keep the controls. These strings are only the tile summary,
 * so they stay short enough for a half-width tile. Notification summaries
 * name intent and registration only.
 *
 * Pure. No React, no dollar literals: the bankroll line is assembled from
 * labels `formatDollars` already produced (lib/bankroll.ts).
 */

export const SETTINGS_GRID_SECTIONS = [
  'sportsbooks',
  'bankroll',
  'notifications',
  'explore',
  'community',
  'account',
] as const;

export const SETTINGS_LEGAL_SECTION = 'legal' as const;

/**
 * Which home tiles sit in the 2-up grid, and which are full width.
 *
 * An odd count puts the last tile on its own row. A large font scale, or a
 * narrow phone (width / scale under 360), stacks every tile.
 */
export function settingsHomeLayout<T>(
  tiles: readonly T[],
  fontScale: number,
  windowWidth: number,
): { paired: T[]; fullWidth: T[] } {
  const scale = fontScale > 0 ? fontScale : 1;
  const stack = scale > 1.3 || windowWidth / scale < 360;
  if (stack) return { paired: [], fullWidth: [...tiles] };
  if (tiles.length % 2 === 1) {
    return { paired: tiles.slice(0, -1), fullWidth: tiles.slice(-1) };
  }
  return { paired: [...tiles], fullWidth: [] };
}

export type SettingsSectionId =
  | (typeof SETTINGS_GRID_SECTIONS)[number]
  | typeof SETTINGS_LEGAL_SECTION;

export const SETTINGS_SECTION_TITLE: Record<SettingsSectionId, string> = {
  sportsbooks: 'Sportsbooks',
  bankroll: 'Bankroll',
  notifications: 'Notifications',
  explore: 'Explore',
  community: 'Community',
  account: 'Account',
  legal: 'Legal & support',
};

const SECTION_IDS: readonly string[] = [...SETTINGS_GRID_SECTIONS, SETTINGS_LEGAL_SECTION];

export function isSettingsSectionId(value: string): value is SettingsSectionId {
  return SECTION_IDS.includes(value);
}

/** "DK, FD +2 · New York". Two names, then a count, then the state. */
export function sportsbooksTileSummary(shortLabels: readonly string[], stateName: string | null): string {
  const books =
    shortLabels.length === 0
      ? 'Not set'
      : shortLabels.length <= 2
        ? shortLabels.join(', ')
        : `${shortLabels[0]}, ${shortLabels[1]} +${shortLabels.length - 2}`;
  return `${books} · ${stateName ?? 'Not set'}`;
}

/** "$2,500 · 1u = $25", or "Not set · 1u = 1%" when no amount is saved. */
export function bankrollTileSummary(amountLabel: string | null, unitLabel: string): string {
  return amountLabel == null ? `Not set · ${unitLabel}` : `${amountLabel} · ${unitLabel}`;
}

export type SettingsPushStatus = 'idle' | 'registering' | 'registered' | 'failed';

/**
 * Intent, then reality. "Signals on · registered" is the on-and-registered
 * case. A device that has not answered storage yet does not claim to be off.
 */
export function notificationsTileSummary(
  enabled: boolean,
  status: SettingsPushStatus,
  ready: boolean,
): string {
  if (!ready) return 'Checking this device';
  if (!enabled) return 'Signals off';
  if (status === 'registered') return 'Signals on · registered';
  if (status === 'registering') return 'Signals on · registering';
  if (status === 'failed') return 'Signals on · not registered';
  return 'Signals on';
}

export const EXPLORE_TILE_SUMMARY = 'Record, Live Signals, intro';

export const LEGAL_TILE_SUMMARY = 'Help line · Terms · Privacy';

/**
 * Unread replies are the live part, so they replace the static list.
 * Discord leads the static list, and only when that row is on the drill-in.
 * Flags-off stays "X · Feedback".
 */
export function communityTileSummary(showDiscord: boolean, unread: number): string {
  if (unread > 0) {
    const noun = unread === 1 ? 'reply' : 'replies';
    return `X · ${unread} new ${noun}`;
  }
  return showDiscord ? 'Discord · X · Feedback' : 'X · Feedback';
}

/**
 * Included chip on the Community tile. Paid only, and only when the Discord
 * row is on the drill-in and the summary still names it. An unread reply
 * replaces that summary, so the chip would no longer say what is included.
 * Flags-off has no chip.
 */
export function communityIncludedChip(
  showDiscord: boolean,
  paid: boolean,
  unread = 0,
): boolean {
  return showDiscord && paid && unread <= 0;
}

/** Keep a long address from pushing the plan word off a two-line tile. */
export function shortenAccountEmail(email: string): string {
  if (email.length <= 22) return email;
  const at = email.indexOf('@');
  if (at > 0) {
    const local = email.slice(0, at);
    const domain = email.slice(at);
    const localShort = local.length > 8 ? `${local.slice(0, 8)}…` : local;
    const combined = `${localShort}${domain}`;
    if (combined.length <= 26) return combined;
  }
  return `${email.slice(0, 18)}…`;
}

/**
 * "jamie@icloud.com · Premium". No plan label when billing is off.
 * `shorten` is the tile text. VoiceOver uses the full address.
 */
export function accountTileSummary(
  signedIn: boolean,
  email: string | null,
  planLabel: string | null,
  shorten = false,
): string {
  const full = signedIn ? (email && email.length > 0 ? email : 'Signed in') : 'Not signed in';
  const who = shorten && signedIn && email && email.length > 0 ? shortenAccountEmail(email) : full;
  return planLabel ? `${who} · ${planLabel}` : who;
}
