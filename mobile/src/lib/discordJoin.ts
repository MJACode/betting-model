/**
 * Discord as a paid perk. Paywall line, onboarding slide, and the once-only
 * Join screen. Pure: no React, no AsyncStorage, no invite URL.
 *
 * The URL stays in discordInviteIfPaid. A screen that wants to open it has
 * to pass a paid flag through that function. Free and trial never get a string.
 *
 * `paid` here is the app's discordPaid: an active (not trialing) App Store
 * row, or a comped grant. A trial is not paid. Whop does not make it paid.
 */

export const DISCORD_JOIN_STORAGE_KEY = 'discord.join.v1';

export type DiscordTier = 'open' | 'free' | 'trial' | 'paid';
export type DiscordJoinVariant = 'firstPaid' | 'converted';
export type DiscordJoinChoice = 'join' | 'later';

export interface DiscordJoinRecord {
  seen: boolean;
  /** This account was observed on a trial before the paid tier. */
  sawTrial: boolean;
}

export interface DiscordJoinStore {
  users: Record<string, DiscordJoinRecord>;
}

export const EMPTY_DISCORD_JOIN_RECORD: DiscordJoinRecord = {
  seen: false,
  sawTrial: false,
};

function recordFrom(value: unknown): DiscordJoinRecord {
  if (!value || typeof value !== 'object') return EMPTY_DISCORD_JOIN_RECORD;
  const row = value as { seen?: unknown; sawTrial?: unknown };
  return {
    seen: row.seen === true,
    sawTrial: row.sawTrial === true,
  };
}

/** Anything that is not the map we wrote reads as empty. A bad blob cannot mark anyone seen. */
export function parseDiscordJoinStore(raw: string | null): DiscordJoinStore {
  if (!raw) return { users: {} };
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return { users: {} };
    const usersIn = (parsed as { users?: unknown }).users;
    if (!usersIn || typeof usersIn !== 'object') return { users: {} };
    const users: Record<string, DiscordJoinRecord> = {};
    for (const [id, value] of Object.entries(usersIn)) {
      if (!id) continue;
      users[id] = recordFrom(value);
    }
    return { users };
  } catch {
    return { users: {} };
  }
}

export function serializeDiscordJoinStore(store: DiscordJoinStore): string {
  return JSON.stringify({ v: 1, users: store.users });
}

export function userDiscordJoinRecord(
  store: DiscordJoinStore,
  userId: string | null,
): DiscordJoinRecord {
  if (!userId) return EMPTY_DISCORD_JOIN_RECORD;
  return store.users[userId] ?? EMPTY_DISCORD_JOIN_RECORD;
}

export function withUserDiscordJoinRecord(
  store: DiscordJoinStore,
  userId: string,
  record: DiscordJoinRecord,
): DiscordJoinStore {
  return { users: { ...store.users, [userId]: record } };
}

/**
 * A trial observation sticks. A later paid tier does not clear it: that is
 * how a conversion is told apart from a Weekly checkout.
 */
export function observeDiscordTier(
  record: DiscordJoinRecord,
  tier: DiscordTier,
): DiscordJoinRecord {
  if (tier !== 'trial' || record.sawTrial) return record;
  return { ...record, sawTrial: true };
}

/**
 * Join and Maybe later are the same flag. The screen does not come back.
 * The choice is recorded so a caller cannot treat the two buttons differently.
 */
export function markDiscordJoinChosen(
  record: DiscordJoinRecord,
  _choice: DiscordJoinChoice,
): DiscordJoinRecord {
  if (record.seen) return record;
  return { ...record, seen: true };
}

/** In-memory trial notes survive a storage read that started earlier. Seen is sticky too. */
export function mergeDiscordJoinStores(
  stored: DiscordJoinStore,
  memory: DiscordJoinStore,
): DiscordJoinStore {
  const ids = new Set([...Object.keys(stored.users), ...Object.keys(memory.users)]);
  const users: Record<string, DiscordJoinRecord> = {};
  for (const id of ids) {
    const a = stored.users[id] ?? EMPTY_DISCORD_JOIN_RECORD;
    const b = memory.users[id] ?? EMPTY_DISCORD_JOIN_RECORD;
    users[id] = { seen: a.seen || b.seen, sawTrial: a.sawTrial || b.sawTrial };
  }
  return { users };
}

export interface DiscordJoinGate {
  /** Active paid plan or a comped grant. Never a trial, never free, never Whop-only. */
  discordPaid: boolean;
  seen: boolean;
  sawTrial: boolean;
  /** Comped copy is the first-paid screen, even if a trial was also observed. */
  comped: boolean;
  /** Slides and the sportsbook step are both done, so the two full screens do not stack. */
  onboardingFinished: boolean;
  /** Signed in, and not on Sign in or the paywall. */
  surfaceClear: boolean;
  /** A signed-in account. The flag is stored per account. */
  hasAccount: boolean;
}

export function discordJoinOffer(gate: DiscordJoinGate): {
  show: boolean;
  variant: DiscordJoinVariant | null;
} {
  if (
    !gate.hasAccount ||
    !gate.discordPaid ||
    gate.seen ||
    !gate.onboardingFinished ||
    !gate.surfaceClear
  ) {
    return { show: false, variant: null };
  }
  // 02b is only the trial-to-paid moment. Weekly, comped, and a member who
  // was already paid before we ever saw a trial get the first-paid screen.
  const variant: DiscordJoinVariant = gate.sawTrial && !gate.comped ? 'converted' : 'firstPaid';
  return { show: true, variant };
}

/** Hold the daily recap while the Join screen might still appear on top of it. */
export function discordJoinBlocksRecap(input: {
  storageReady: boolean;
  membershipHold: boolean;
  show: boolean;
}): boolean {
  return !input.storageReady || input.membershipHold || input.show;
}

export function paywallDiscordBullet(trialDays: number): string {
  return trialDays > 0
    ? 'The subscriber Discord: the community, plus extra bets shared beyond the models (after the trial)'
    : 'The subscriber Discord: the community, plus extra bets shared beyond the models, included with this plan';
}

/** Preview slide. No join button on either variant. */
export function discordOnboardingSlide(discordPaid: boolean): { title: string; body: string } {
  return {
    title: 'The subscriber Discord',
    body: discordPaid
      ? 'Your plan includes a private community, plus extra bets shared beyond the models. You’ll be able to join after this intro — or anytime in Settings.'
      : 'Paid plans include a private community, plus extra bets shared beyond the models. It unlocks when a paid plan is active, after any free trial.',
  };
}

export const DISCORD_CARD_TITLE = 'Discord for members';
export const DISCORD_CARD_BODY = 'The community, plus extra bets shared beyond the models.';

const JOIN_BULLETS = [
  'Talk with other subscribers',
  'Extra bets shared beyond the model board',
  'Room to talk through the models and the day',
] as const;

export function discordJoinCopy(variant: DiscordJoinVariant): {
  headline: string;
  body: string;
  bullets: readonly string[];
  primary: string;
  secondary: string;
  note: string;
} {
  const shared = {
    bullets: JOIN_BULLETS,
    primary: 'Join Discord',
    secondary: 'Maybe later',
    note: 'You can always join later from Settings → Community.',
  };
  if (variant === 'converted') {
    return {
      ...shared,
      headline: 'Your paid plan includes Discord',
      body: 'The trial has ended, and the subscriber Discord is now included — the community, plus extra bets shared beyond the models.',
    };
  }
  return {
    ...shared,
    headline: 'Join the subscriber Discord',
    body: 'Your plan includes a private community, plus extra bets shared beyond the models.',
  };
}
