/**
 * One push-token write at a time.
 *
 * Registration and opt-out both update the same row. If opt-out is allowed
 * to finish first, a registration that was already in flight writes
 * enabled = true afterwards and the toggle loses. The queue is the order
 * the reader asked for.
 */
export function createQueue(): <T>(job: () => Promise<T>) => Promise<T> {
  let chain: Promise<unknown> = Promise.resolve();
  return function enqueue<T>(job: () => Promise<T>): Promise<T> {
    const run = chain.then(job, job);
    chain = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  };
}

export const enqueuePushWrite = createQueue();
