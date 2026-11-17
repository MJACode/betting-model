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
 * Height of every React view in a header bar slot (headerLeft / headerRight).
 *
 * WHY 36, NOT 44 (2026-11-17, Matt's screenshot: the Back chevron sat 3.8pt
 * below the middle of its glass bubble). On iOS 26+ UIKit sizes a bar
 * button's custom view itself. react-native-screens 4.16 (Expo SDK 54's
 * pin) hands UIKit our header view directly, and leaves our content at that
 * view's top-left corner whatever size UIKit gives it. Upstream fixed this
 * in a centering wrapper (#3449, #3548; present in 4.23.0's
 * RNSScreenStackHeaderSubview.mm, absent from 4.16.0's). Measured on iOS
 * 27.3 (screenshot, 3x pixels): a 44 x 44 view drew its center 3.8pt below
 * the bubble's, and the bubble was 52 x 44. Both fit UIKit giving the view a
 * 36pt-tall slot (top 4pt down) with the bubble 4pt outside it all round, and
 * our 44pt content hanging below from that top. A 36pt-tall view fills that
 * slot exactly. Upstream's fix pins compression resistance and hugging for
 * the same reason; the community workaround on its issue (#2990) is 36pt.
 * The tap target stays at least 44pt through hitSlop.
 */
export const HEADER_ITEM_HEIGHT = 36;

/** The Back chevron: 22pt, and at most 28 so it stays inside the 36pt item at any font scale. */
export function backChevronSize(fontScale: number): number {
  const scale = Math.min(Math.max(fontScale, 1), 2);
  return Math.min(28, Math.round(22 * scale));
}

/**
 * The width the Back button takes in the bar: its 36pt square plus the 4pt
 * the iOS glass bubble pads each side, 44 in all. Chevron only since
 * 2026-11-16, so there is no "Back" word to reserve room for. The chevron is
 * capped (backChevronSize), so font scale does not widen it.
 */
export function backButtonWidth(_fontScale: number): number {
  return HEADER_ITEM_HEIGHT + 2 * 4;
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
