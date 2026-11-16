/**
 * App entry. Reads the saved Appearance choice BEFORE App is loaded, because
 * every StyleSheet in the app reads `colors` once, at import (lib/appearance.ts
 * says why a theme change waits for the next open).
 *
 * Nothing here may import App, theme.ts or any screen at the top: `require`
 * below is the first time they load. A store that never answers falls back to
 * the default after BOOT_TIMEOUT_MS, so the app always opens.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { registerRootComponent } from 'expo';
import React, { useEffect, useState } from 'react';
import { Appearance, View } from 'react-native';

import {
  APPEARANCE_STORAGE_KEY,
  parseAppearancePref,
  resolveScheme,
  setBootAppearance,
  shouldOverrideNative,
} from './src/lib/appearance';
import appJson from './app.json';

// The splash ground, from its one home, so the hand-off from the native splash
// is seamless whichever theme follows (theme.ts cannot load this early).
const SPLASH_GROUND = appJson.expo.splash.backgroundColor;

const BOOT_TIMEOUT_MS = 1500;

function Boot() {
  const [App, setApp] = useState<React.ComponentType | null>(null);

  useEffect(() => {
    let started = false;
    const start = (raw: string | null) => {
      if (started) return;
      started = true;
      const pref = parseAppearancePref(raw);
      // Read the phone BEFORE any override: afterwards RN reports the override.
      const system = Appearance.getColorScheme() ?? null;
      const scheme = resolveScheme(pref, system);
      const overridden = shouldOverrideNative(raw, pref);
      setBootAppearance(pref, scheme, system, overridden);
      // Native pieces (alerts, pickers, the keyboard) follow a SAVED choice;
      // System and the untouched default leave them to the phone.
      if (overridden) Appearance.setColorScheme(scheme);
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const mod = require('./App') as { default: React.ComponentType };
      setApp(() => mod.default);
    };
    AsyncStorage.getItem(APPEARANCE_STORAGE_KEY).then(start, () => start(null));
    const timer = setTimeout(() => start(null), BOOT_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, []);

  if (!App) return <View style={{ flex: 1, backgroundColor: SPLASH_GROUND }} />;
  return <App />;
}

registerRootComponent(Boot);
