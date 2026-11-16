/**
 * Appearance: System / Light / Dark (Matt, 2026-11-16).
 *
 * WHY A THEME CHANGE WAITS FOR THE NEXT OPEN. Every StyleSheet in the app
 * reads `colors` once, when its module loads. Switching live would mean
 * rewriting ~126 of them to read the theme on each render; reloading the JS
 * runtime would mean `Updates.reloadAsync()`, which is banned (lib/otaUpdate.ts,
 * the 2026-10-19 TestFlight crash). So the choice is saved at once and applied
 * when the app next starts: `index.tsx` reads it BEFORE it loads App, and
 * theme.ts picks its palette from `bootScheme()` at import.
 *
 * The default is Light (Matt, 2026-11-16, "opt in"), so nobody's app changes
 * until they pick something.
 *
 * Pure — no React, no react-native, no AsyncStorage import — so
 * scripts/verify_appearance.ts can pin every rule, and theme.ts can import it
 * without pulling anything into the boot path.
 */

export type AppearancePref = 'system' | 'light' | 'dark';
export type ColorScheme = 'light' | 'dark';

export const APPEARANCE_STORAGE_KEY = 'appearance.v1';

export const APPEARANCE_DEFAULT: AppearancePref = 'light';

export const APPEARANCE_OPTIONS: readonly { value: AppearancePref; label: string; detail: string | null }[] = [
  { value: 'system', label: 'System', detail: "Matches your iPhone's setting" },
  { value: 'light', label: 'Light', detail: null },
  { value: 'dark', label: 'Dark', detail: null },
];

/** A stored value, or the default for anything missing or unrecognised. */
export function parseAppearancePref(raw: string | null | undefined): AppearancePref {
  return raw === 'system' || raw === 'light' || raw === 'dark' ? raw : APPEARANCE_DEFAULT;
}

/** The scheme a preference draws. System follows the phone; an unknown phone answer is light. */
export function resolveScheme(pref: AppearancePref, system: string | null | undefined): ColorScheme {
  if (pref === 'system') return system === 'dark' ? 'dark' : 'light';
  return pref;
}

// ── The scheme this run of the app was started in ──────────────────────────
// Set once, by index.tsx, before App (and so theme.ts) is loaded. Anything
// that reads it without a boot (a verify script) gets the default.
let boot: {
  pref: AppearancePref;
  scheme: ColorScheme;
  /** The PHONE's scheme, read before any override was set. */
  system: string | null;
  /** Whether index.tsx forced native UI to `scheme` (an explicit pick). */
  overridden: boolean;
} | null = null;

export function setBootAppearance(
  pref: AppearancePref,
  scheme: ColorScheme,
  system: string | null = null,
  overridden = false,
): void {
  boot = { pref, scheme, system, overridden };
}

/**
 * Only a choice the user SAVED forces native UI (alerts, sheets, keyboard).
 * The default Light leaves the phone in charge, as before this feature, so a
 * member who never opens Appearance sees no change at all.
 */
export function shouldOverrideNative(raw: string | null | undefined, pref: AppearancePref): boolean {
  return raw != null && parseAppearancePref(raw) === raw && pref !== 'system';
}

/**
 * The phone's scheme for "is a switch pending?". While an override is set,
 * React Native reports the OVERRIDE, not the phone (RCTAppearance returns
 * sColorSchemeOverride first), so the value read at boot stands in for it.
 */
export function phoneScheme(live: string | null | undefined): string | null {
  if (boot?.overridden) return boot.system;
  return live ?? null;
}

export function bootScheme(): ColorScheme {
  return boot?.scheme ?? 'light';
}

export function bootPref(): AppearancePref {
  return boot?.pref ?? APPEARANCE_DEFAULT;
}

/**
 * The line under the three options. When the saved choice would draw a
 * different scheme than the one on screen, say what reopening does; otherwise
 * say only when a change applies.
 */
export function appearanceFootnote(
  chosen: AppearancePref,
  running: ColorScheme,
  system: string | null | undefined,
): string {
  const next = resolveScheme(chosen, system);
  if (next !== running) {
    return `Swipe Signalbase away in the app switcher, then reopen it to switch to ${next === 'dark' ? 'Dark' : 'Light'}.`;
  }
  return 'A change applies after Signalbase is fully closed and reopened.';
}

/** The Settings home tile line: the saved choice, and "reopen to apply" while it is pending. */
export function appearanceTileSummary(
  chosen: AppearancePref,
  running: ColorScheme,
  system: string | null | undefined,
): string {
  const label = APPEARANCE_OPTIONS.find((o) => o.value === chosen)?.label ?? 'Light';
  return resolveScheme(chosen, system) !== running ? `${label} · reopen to apply` : label;
}
