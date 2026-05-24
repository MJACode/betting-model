import React from 'react';
import { StyleSheet, Switch, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';

interface Props {
  value: boolean;
  onChange: () => void;
}

export function PlacedToggle({ value, onChange }: Props) {
  return (
    <View style={styles.row}>
      <View style={styles.textCol}>
        <Text style={styles.title}>I'm betting this</Text>
        <Text style={styles.sub}>
          Only picks you turn on here count toward Performance ROI and the calendar.
        </Text>
      </View>
      <Switch value={value} onValueChange={onChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  textCol: {
    flex: 1,
    marginRight: spacing.md,
  },
  title: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: 2,
  },
  sub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
