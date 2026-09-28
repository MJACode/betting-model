/**
 * Load-state decisions, kept pure (no react-native) so the verify script and
 * the pytest can RUN them rather than scan for them (Reviewer, #845):
 *
 *   - what the list body shows: a skeleton, the ErrorState, or the content;
 *   - whether an ErrorBanner sits over content that is still on screen;
 *   - whether a count is known or reads "—" (PATTERNS §F5);
 *   - whether the "Live prices unavailable" banner shows (M2).
 *
 * An intentional cancel (isAbortError) is never a failure here.
 */
import { isAbortError } from './errors';

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

/** A count that never loaded is unknown ("—"), not zero. */
export function knownCount(n: number, input: Pick<LoadInput, 'error' | 'hasData'>): number | null {
  return failure(input.error) && !input.hasData ? null : n;
}

export function countLabel(n: number | null): string {
  return n == null ? '—' : String(n);
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
