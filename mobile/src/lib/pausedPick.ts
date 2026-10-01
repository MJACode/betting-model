/**
 * The words for a paused model's pick on the All board (Matt, 2026-09-28,
 * Designer mockups in the paused-on-All PR). A paused model's pick works like
 * any other pick — stake, Sharp Score, book, Slip, Track — it is just never
 * sent as a signal. One place for the copy, so the card, the detail screen,
 * the betslip leg and the checks that pin them cannot drift apart.
 *
 * Whether a pick is drawn this way is `isPausedForDisplay` (lib/thresholds).
 */

/** The visible tag, next to the model on the card, detail header and slip leg. */
export const PAUSED_TAG_TEXT = 'Paused';

/** What VoiceOver says for the tag. On PickCard it is part of the card's one
 *  label (the card is the accessible element); nested, it would be read twice. */
export const PAUSED_SPOKEN = 'Model paused, not sent as a signal';

/** Pick Detail, textSecondary under the header's tag. */
export const PAUSED_DETAIL_NOTE =
  'This model is paused, so this pick isn’t sent as a signal (no Discord or push alerts). Everything else works as usual.';
