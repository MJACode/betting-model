import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { AccessibilityInfo, useColorScheme } from 'react-native';

import {
  APPEARANCE_STORAGE_KEY,
  appearanceFootnote,
  appearanceTileSummary,
  bootPref,
  bootScheme,
  parseAppearancePref,
  phoneScheme,
  type AppearancePref,
} from '@/lib/appearance';

/**
 * The saved Appearance choice (lib/appearance.ts). It starts at what this run
 * booted with, and a pick is written at once; the theme on screen changes at
 * the next open. One module-level value so the Settings tile and the drill-in
 * agree without a second read.
 */
let current: AppearancePref | null = null;
const listeners = new Set<(p: AppearancePref) => void>();

export function useAppearance() {
  const [pref, setPref] = useState<AppearancePref>(current ?? bootPref());
  const system = phoneScheme(useColorScheme());

  useEffect(() => {
    const onChange = (p: AppearancePref) => setPref(p);
    listeners.add(onChange);
    if (current == null) {
      AsyncStorage.getItem(APPEARANCE_STORAGE_KEY)
        .then((raw) => {
          if (current != null) return;
          current = parseAppearancePref(raw);
          listeners.forEach((l) => l(current as AppearancePref));
        })
        .catch(() => {});
    }
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  const choose = useCallback(
    (next: AppearancePref) => {
      current = next;
      listeners.forEach((l) => l(next));
      AsyncStorage.setItem(APPEARANCE_STORAGE_KEY, next).catch(() => {});
      // accessibilityLiveRegion is Android-only; VoiceOver needs the footnote said.
      AccessibilityInfo.announceForAccessibility(appearanceFootnote(next, bootScheme(), system));
    },
    [system],
  );

  const running = bootScheme();
  return {
    pref,
    choose,
    footnote: appearanceFootnote(pref, running, system),
    tileSummary: appearanceTileSummary(pref, running, system),
  };
}

