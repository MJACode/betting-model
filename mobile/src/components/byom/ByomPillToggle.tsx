import React from 'react';
import { StyleSheet, View } from 'react-native';

import { SegmentTabs } from '@/components/GroupTabs';
import { spacing } from '@/lib/theme';

/**
 * The BYOM two-way switch (season, official/closing line). One control, so
 * the season toggle and the official/closing toggle cannot drift apart (UX
 * review, 2026-11-04).
 *
 * It renders the app's segmented control, `SegmentTabs` in its compact
 * form. Until 2026-11-14 it drew its own capsule pill on a tinted wash: a
 * third segmented style beside SegmentTabs and the Stats position row (UI
 * consistency pass, Matt approved). The name and props stay so its callers
 * did not change.
 */
export function ByomPillToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (next: T) => void;
}) {
  const labels = new Map(options.map((o) => [o.value, o.label]));
  return (
    <View style={styles.wrap}>
      <SegmentTabs
        items={options.map((o) => o.value)}
        active={value}
        onChange={onChange}
        labelFor={(v) => labels.get(v) ?? v}
        compact
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
});
