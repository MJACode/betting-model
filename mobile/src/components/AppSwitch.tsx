import { Switch, type SwitchProps } from 'react-native';

import { colors } from '@/lib/theme';

/**
 * The app's only switch. React Native's default OFF state is a near-white
 * track under a white thumb, invisible on a white card — so every toggle
 * goes through here and gets a visible off track. The ON colour is left at
 * the platform default.
 */
export function AppSwitch({ trackColor, ...rest }: Omit<SwitchProps, 'ios_backgroundColor'>) {
  return (
    <Switch
      {...rest}
      trackColor={{ ...trackColor, false: colors.switchTrackOff }}
      ios_backgroundColor={colors.switchTrackOff}
    />
  );
}
