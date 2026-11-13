/**
 * Whether a subscription fetch may still be published.
 *
 * The read is async. Sign-out, or a switch to another account, can land
 * first. A late row for the old account must not be stored, and must not
 * count as the read for the new account.
 */
export interface SubscriptionFetchTicket {
  generation: number;
  userId: string | null;
}

export function subscriptionFetchStillCurrent(
  started: SubscriptionFetchTicket,
  now: SubscriptionFetchTicket,
): boolean {
  return started.generation === now.generation && started.userId === now.userId;
}

export interface SubscriptionSnapshot<Row> {
  subscription: Row | null;
  loading: boolean;
  error: string | null;
}

export interface SubscriptionStore<Row> {
  get(): SubscriptionSnapshot<Row>;
  /** userId null is signed out. force skips the "already loaded" cache. */
  load(userId: string | null, force?: boolean): Promise<void>;
  currentUserId(): string | null;
}

/**
 * A reader that waits on someone else's in-flight fetch starts its own read
 * when that fetch is dropped. Skipping whenever the wait ends leaves the new
 * account with a null row until the next foreground.
 */
export function createSubscriptionStore<Row>(opts: {
  fetchRow: () => Promise<Row | null>;
  billingOn: () => boolean;
  isAbort?: (error: unknown) => boolean;
  errorText?: (error: unknown) => string;
  onChange?: (snapshot: SubscriptionSnapshot<Row>) => void;
}): SubscriptionStore<Row> {
  let snapshot: SubscriptionSnapshot<Row> = {
    subscription: null,
    loading: opts.billingOn(),
    error: null,
  };
  function write(next: SubscriptionSnapshot<Row>) {
    snapshot = next;
    opts.onChange?.(snapshot);
  }
  /** User id of the last successful read. undefined = never read. */
  let loadedFor: string | null | undefined;
  let currentUserId: string | null = null;
  let generation = 0;
  let inFlight: Promise<void> | null = null;

  function ticketNow(): SubscriptionFetchTicket {
    return { generation, userId: currentUserId };
  }

  function noteUser(userId: string | null) {
    if (userId === currentUserId) return;
    generation += 1;
    currentUserId = userId;
    loadedFor = undefined;
  }

  async function load(userId: string | null, force = false): Promise<void> {
    noteUser(userId);
    if (!opts.billingOn() || !userId) {
      loadedFor = null;
      write({ subscription: null, loading: false, error: null });
      return;
    }
    const asked = ticketNow();
    if (inFlight) {
      await inFlight;
      if (!subscriptionFetchStillCurrent(asked, ticketNow())) return;
      // The awaited read may have been for a previous account and dropped.
      // Skip only when it actually stored this user's row.
      if (!force && loadedFor === userId) return;
    }
    if (!force && loadedFor === userId) return;

    let finish!: () => void;
    const run = new Promise<void>((resolve) => {
      finish = resolve;
    });
    inFlight = run;
    const started = ticketNow();
    snapshot = { ...snapshot, loading: true };
    opts.onChange?.(snapshot);
    try {
      const row = await opts.fetchRow();
      if (!subscriptionFetchStillCurrent(started, ticketNow())) {
        write({ ...snapshot, loading: false });
        return;
      }
      loadedFor = userId;
      write({ subscription: row ?? null, error: null, loading: false });
    } catch (error) {
      if (!subscriptionFetchStillCurrent(started, ticketNow())) {
        write({ ...snapshot, loading: false });
        return;
      }
      const aborted = opts.isAbort?.(error) ?? false;
      write({
        ...snapshot,
        loading: false,
        error: aborted ? snapshot.error : (opts.errorText?.(error) ?? 'error'),
      });
    } finally {
      if (inFlight === run) inFlight = null;
      finish();
    }
  }

  return {
    get: () => snapshot,
    load,
    currentUserId: () => currentUserId,
  };
}
