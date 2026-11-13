/**
 * What Back does when the system button cannot be trusted.
 *
 * On iOS 27 the navigation-bar Back pill stops popping after a modal has
 * been presented on the screen (Player Stats, after Compare odds). The tap
 * never reaches JavaScript. This decision is the handler on the replacement
 * pill: pop when there is a screen underneath, otherwise replace so a deep
 * link or a reset still leaves.
 */

export type StackBackDecision = 'pop' | 'replace';

export function stackBackDecision(canGoBack: boolean): StackBackDecision {
  return canGoBack ? 'pop' : 'replace';
}

/**
 * Where the player / prop detail screen goes when it is the root.
 * The Stats tab is the player list it is pushed from.
 */
export const PLAYER_DETAIL_PARENT = {
  name: 'Tabs' as const,
  screen: 'Stats' as const,
};

/**
 * How wide the centered player name may be before it reaches the Back pill.
 *
 * The native stack centers the title. zIndex on the pill does not lift it
 * over UIKit's title label, so the title has to stop short of the pill on
 * both sides. The pill is a 22pt chevron plus the word "Back" at 17pt.
 * Font scale is capped at 2, the same cap the segmented controls use.
 */
export function playerTitleMaxWidth(windowWidth: number, fontScale: number): number {
  const scale = Math.min(Math.max(fontScale, 1), 2);
  const pill = 22 * scale + 17 * scale * 4;
  const side = 16 + pill + 8;
  return Math.max(80, Math.floor(windowWidth - side * 2));
}

/**
 * How wide a Settings section title may be before it reaches the same Back pill.
 *
 * The player name reserves 4em for "Back", which is wider than the word, so
 * "Legal & support" ellipsizes. This reserves the chevron plus about 2.6em.
 */
export function settingsTitleMaxWidth(windowWidth: number, fontScale: number): number {
  const scale = Math.min(Math.max(fontScale, 1), 2);
  const pill = 22 * scale + 17 * scale * 2.6;
  const side = 16 + pill + 8;
  return Math.max(120, Math.floor(windowWidth - side * 2));
}
