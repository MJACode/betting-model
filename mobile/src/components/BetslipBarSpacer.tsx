import React from 'react';
import { View } from 'react-native';

import { useBetslipBarInset } from '@/hooks/useBetslipBarInset';

/**
 * Bottom content inset equal to the betslip bar's height, rendered as the last
 * child of a vertical ScrollView (or a FlatList's ListFooterComponent) so the
 * final row can scroll clear of the bar (usability audit M7). Renders nothing
 * while the bar is hidden, so an empty slip costs no extra space.
 */
export function BetslipBarSpacer() {
  const inset = useBetslipBarInset();
  if (inset <= 0) return null;
  return <View style={{ height: inset }} accessible={false} importantForAccessibility="no" />;
}
