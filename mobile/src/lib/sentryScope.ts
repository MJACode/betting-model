/**
 * Tags placed on the Sentry scope at init (lib/sentry.ts initialScope).
 *
 * device_id has to be here, not in a promise that resolves after init, or a
 * crash in the first moment goes out without the id app_errors joins on.
 * release is the app version (app.json), the value docs/sentry.md filters on.
 * The native SDK keeps its own release string (bundle id, version, build) so
 * the dSYM uploaded with the binary still matches.
 */

export function scopeTags(input: {
  deviceId: string | null;
  release: string;
  updateId: string | null;
}): Record<string, string> {
  const tags: Record<string, string> = {};
  if (input.deviceId) tags.device_id = input.deviceId;
  if (input.release) tags.release = input.release;
  if (input.updateId) tags.update_id = input.updateId;
  return tags;
}
