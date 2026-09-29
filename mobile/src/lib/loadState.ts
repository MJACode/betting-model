/**
 * Load-state decisions, kept pure (no react-native) so the verify script and
 * the pytest can RUN them rather than scan for them (Reviewer, #845):
 *
 *   - what the list body shows: a skeleton, the ErrorState, or the content;
 *   - whether an ErrorBanner sits over content that is still on screen;
 *   - whether a count is known or reads "—" (PATTERNS §F5);
 *   - whether the "Live prices unavailable" banner shows (M2);
 *   - what a detail screen shows: spinner, ErrorState, not-found or content;
 *   - whether the sport chips may say "no picks today" (only once known);
 *   - whether a repeat, identical failure after Retry is read out again.
 *
 * An intentional cancel (isAbortError) is never a failure here.
 */
import { isAbortError, isNotFoundError } from './errors';

export type LoadBody = 'skeleton' | 'error' | 'content';

export interface LoadInput {
  loading: boolean;
  /** The raw error the hook kept, or null. */
  error: unknown;
  /** Something is on screen to keep (rows from an earlier load). */
  hasData: boolean;
}

function failure(error: unknown): boolean {
  return Boolean(error) && !isAbortError(error);
}

/**
 * ErrorState vs ErrorBanner (PATTERNS §E3): a failure with nothing to show
 * REPLACES the body (ErrorState); a failure over rows still on screen keeps
 * them and says so (ErrorBanner). The two never stack. Nothing loaded yet and
 * still loading is the skeleton, never a zero.
 */
export function loadPresentation({ loading, error, hasData }: LoadInput): { body: LoadBody; banner: boolean } {
  const failed = failure(error);
  if (hasData) return { body: 'content', banner: failed };
  if (loading) return { body: 'skeleton', banner: false };
  if (failed) return { body: 'error', banner: false };
  return { body: 'content', banner: false };
}

/**
 * Where a failure surfaces on a screen whose list may not own it. The Models
 * Custom tab lists local models, so a failed settled-records load is never its
 * ErrorState — it must still be SAID, as a banner, or the failure reads as "no
 * models" (Reviewer, #845 MEDIUM 1).
 */
export function errorSurface(input: LoadInput, listOwnsFailure: boolean): 'none' | 'banner' | 'state' {
  if (!failure(input.error)) return 'none';
  if (!listOwnsFailure) return 'banner';
  const p = loadPresentation(input);
  return p.body === 'error' ? 'state' : p.banner ? 'banner' : 'none';
}

export interface CountInput {
  /** At least one load has SUCCEEDED (the hook's `loaded`). */
  loaded: boolean;
  error: unknown;
  hasData: boolean;
}

/**
 * Are the counts real? Rows on screen are; a failed load with nothing on
 * screen is not; and before the first successful load — still loading, a slow
 * load, an aborted one — nothing is known yet, so a count reads "—" and never
 * a fake "0" (Designer #845: "0 bets · 0 scored" and "(0)" before first load).
 * A load that succeeded and came back empty IS a real zero.
 */
export function countsKnown({ loaded, error, hasData }: CountInput): boolean {
  if (hasData) return true;
  if (failure(error)) return false;
  return loaded;
}

/** A count that never loaded is unknown ("—"), not zero. */
export function knownCount(n: number, input: CountInput): number | null {
  return countsKnown(input) ? n : null;
}

export function countLabel(n: number | null): string {
  return n == null ? '—' : String(n);
}

/** PicksHome's All header: "Sep 28 · 3 bets · 12 scored", or dashes until known. */
export function todayHeaderCounts(o: { date: string; known: boolean; bet: number; total: number; paused: number }): string {
  if (!o.known) return `${o.date} · — bets · — scored`;
  return `${o.date} · ${o.bet} bets · ${o.total} scored${o.paused > 0 ? ` · ${o.paused} paused` : ''}`;
}

/**
 * The set SportToggle mutes against, or undefined (every chip neutral) while
 * the board is unknown. Built from empty data, every chip went muted and
 * VoiceOver read "NFL, no picks today" after a failure (Designer #845).
 */
export function sportChipsAvailable(available: Set<string>, known: boolean): Set<string> | undefined {
  return known ? available : undefined;
}

/** One sport chip's muted state and VoiceOver label (SportToggle). */
export function sportChipState(o: {
  sport: string;
  active: boolean;
  /** undefined = unknown: neutral, and never "no picks today". */
  available?: Set<string>;
  count: number;
  live: boolean;
}): { muted: boolean; label: string } {
  const muted = o.available != null && !o.available.has(o.sport) && !o.active;
  const label = [
    o.sport,
    o.count > 0 ? `${o.count} signal${o.count === 1 ? '' : 's'}` : null,
    o.live ? 'in play now' : null,
    o.count === 0 && !o.live && muted ? 'no picks today' : null,
  ]
    .filter(Boolean)
    .join(', ');
  return { muted, label };
}

export type DetailBody = 'loading' | 'error' | 'notFound' | 'content';

/**
 * A detail screen (PickDetail): a row that does not exist is NOT FOUND — its
 * own state with a way out ("Open Picks") — never an ErrorState whose Retry
 * can't succeed (L11). A PGRST116 that still reaches here is not-found too.
 */
export function detailPresentation({ loading, error, found }: { loading: boolean; error: unknown; found: boolean }): DetailBody {
  if (loading) return 'loading';
  if (failure(error) && !isNotFoundError(error)) return 'error';
  return found ? 'content' : 'notFound';
}

/**
 * Re-announce a failure that comes back IDENTICAL after a Retry the user
 * pressed (Designer #845 nice-to-have a). The title/kind effect cannot see it —
 * nothing it keys on changed — so the settled retry attempt is the key: the
 * user pressed Retry, the retry was in flight, it has settled, and the copy is
 * the one already read out. Background polls (never pressed) stay quiet.
 */
export function repeatFailureAnnounce(o: {
  pressed: boolean;
  wasRetrying: boolean;
  retrying: boolean;
  key: string;
  lastKey: string | null;
}): boolean {
  return o.pressed && o.wasRetrying && !o.retrying && o.lastKey != null && o.key === o.lastKey;
}

/**
 * M2: the picks loaded but their live prices did not. Only on the live view,
 * only over rows (an empty board is the empty/error state's job), and never on
 * top of a whole-load failure.
 */
export function showLivePricesBanner(o: {
  view: string;
  liveError: unknown;
  pricesUnavailable: boolean;
  liveCount: number;
}): boolean {
  return o.view === 'live' && !failure(o.liveError) && o.pricesUnavailable && o.liveCount > 0;
}

/**
 * Collects enrichment misses during one fetch (fetchLivePicks'
 * onEnrichmentError), so `pricesUnavailable` is "any live-price read failed
 * THIS fetch" and clears on the next clean one. An abort is not a miss.
 */
export function enrichmentTracker(log?: (what: string, e: unknown) => void) {
  let missed = false;
  return {
    onError: (what: string, e: unknown) => {
      if (isAbortError(e)) return;
      missed = true;
      log?.(what, e);
    },
    get missed() {
      return missed;
    },
  };
}
