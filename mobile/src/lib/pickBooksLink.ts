/**
 * The Discord landing page opens the app here: `signalbase://pick/<id>`.
 * The id is the picks.pick_id. Anything else is not this route.
 *
 * Pure. The hook that navigates lives in hooks/usePickBooksLink.ts.
 */

const PICK_PATH = /^signalbase:\/\/pick\/([1-9][0-9]{0,14})\/?(?:\?[^#]*)?$/i;

/** The pick id in a `signalbase://pick/<id>` URL, or null. */
export function parsePickBooksUrl(url: string | null | undefined): number | null {
  if (!url) return null;
  const match = PICK_PATH.exec(url.trim());
  if (!match) return null;
  const id = Number(match[1]);
  if (!Number.isSafeInteger(id) || id <= 0) return null;
  return id;
}

export function pickBooksUrl(pickId: number): string {
  return `signalbase://pick/${pickId}`;
}
