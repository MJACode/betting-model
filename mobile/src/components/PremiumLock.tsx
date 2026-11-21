import React from 'react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { EmptyState } from '@/components/EmptyState';
import { SignalLockCard } from '@/components/SignalLockCard';
import { billingReady } from '@/lib/billingConfig';
import { PREMIUM_ACCESS_HINT } from '@/lib/errors';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * The hook's refusal. Children are the screen's normal body and render only
 * when this is not a refusal.
 *
 * Billing on: the same card FeatureGate uses ("Included with Premium",
 * Unlock opens the paywall). Billing off: the paywall is not offered, so
 * the hook's own hint is the empty state. No new sentence.
 */
export function PremiumLock({
  locked,
  children = null,
}: {
  locked: boolean;
  children?: React.ReactNode;
}) {
  const navigation = useNavigation<Nav>();
  if (!locked) return <>{children}</>;
  if (!billingReady()) return <EmptyState title={PREMIUM_ACCESS_HINT} />;
  return (
    <SignalLockCard
      title="Included with Premium"
      onPress={() => navigation.navigate('Paywall')}
    />
  );
}
