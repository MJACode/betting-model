import React, { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AppSwitch } from '@/components/AppSwitch';
import { readAuthUserId } from '@/hooks/useAuth';
import { refreshNotificationInbox, useNotificationInbox } from '@/hooks/useNotificationInbox';
import { SPORTS } from '@/hooks/useSportFilter';
import { colors, font, opacity, radii, sectionHeaderText, spacing } from '@/lib/theme';

/**
 * One switch per sport, in the app's sport order. Gold when on. Off sports
 * are not pushed and do not appear in the inbox or the badge. The master
 * Notifications switch stays the global opt-out; while it is off these are
 * disabled, not cleared.
 */
export function SportNotificationSwitches({ masterOn }: { masterOn: boolean }) {
  const { muted, setSportEnabled, userId, loaded } = useNotificationInbox();

  useEffect(() => {
    void refreshNotificationInbox(readAuthUserId());
  }, []);

  const signedIn = userId != null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.heading}>Sports</Text>
      <Text style={styles.sub}>
        Off sports will not notify you or appear in the inbox.
      </Text>
      <Text style={styles.sub}>
        Feedback replies and test alerts are not tied to a sport.
      </Text>
      {!signedIn ? (
        <Text style={styles.sub}>Sign in to choose which sports notify you.</Text>
      ) : null}
      {signedIn && !loaded ? null : signedIn ? (
      <View style={styles.card}>
        {SPORTS.map((sport, index) => {
          const on = !muted.has(sport);
          const disabled = !masterOn || !signedIn;
          return (
            <View key={sport} style={[styles.row, index > 0 && styles.rule, disabled && styles.disabled]}>
              <Text style={styles.sport}>{sport}</Text>
              <AppSwitch
                value={on}
                disabled={disabled}
                onValueChange={(next) => void setSportEnabled(sport, next)}
                trackColor={{ true: colors.tint }}
                accessibilityLabel={`${sport} notifications`}
                accessibilityState={{ disabled }}
              />
            </View>
          );
        })}
      </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: spacing.xl },
  heading: {
    ...sectionHeaderText,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  card: {
    marginTop: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    overflow: 'hidden',
  },
  row: {
    minHeight: 52,
    paddingHorizontal: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rule: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  disabled: { opacity: opacity.disabled },
  sport: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
});
