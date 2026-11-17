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
 * The width the Back button takes in the bar: a 44pt square holding a 22pt
 * chevron, and the chevron grows with font scale (capped at 2, the same cap
 * the segmented controls use). Chevron only since 2026-11-16, so there is no
 * "Back" word to reserve room for.
 */
export function backButtonWidth(fontScale: number): number {
  const scale = Math.min(Math.max(fontScale, 1), 2);
  return Math.max(44, Math.round(22 * scale));
}

/**
 * How wide a centered title may be before it reaches the Back button.
 *
 * The native stack centers the title. zIndex on the button does not lift it
 * over UIKit's title label, so the title has to stop short of the button on
 * both sides: 16pt bar inset, the button, 8pt gap.
 */
function titleMaxWidth(windowWidth: number, fontScale: number, floor: number): number {
  const side = 16 + backButtonWidth(fontScale) + 8;
  return Math.max(floor, Math.floor(windowWidth - side * 2));
}

/** The player name on the player / prop detail screen. */
export function playerTitleMaxWidth(windowWidth: number, fontScale: number): number {
  return titleMaxWidth(windowWidth, fontScale, 80);
}

/** A Settings section title such as "Legal & support". */
export function settingsTitleMaxWidth(windowWidth: number, fontScale: number): number {
  return titleMaxWidth(windowWidth, fontScale, 120);
}
