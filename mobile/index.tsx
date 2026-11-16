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
} from './src/lib/appearance';

const BOOT_TIMEOUT_MS = 1500;
// The splash ground (app.json splash.backgroundColor), so the hand-off from
// the native splash is seamless whichever theme follows.
const SPLASH_GROUND = '#0B1220';

function Boot() {
  const [App, setApp] = useState<React.ComponentType | null>(null);

  useEffect(() => {
    let started = false;
    const start = (raw: string | null) => {
      if (started) return;
      started = true;
      const pref = parseAppearancePref(raw);
      const scheme = resolveScheme(pref, Appearance.getColorScheme());
      setBootAppearance(pref, scheme);
      // Native pieces (alerts, pickers, the keyboard) follow an explicit
      // choice; System leaves them to the phone.
      if (pref !== 'system') Appearance.setColorScheme(scheme);
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
