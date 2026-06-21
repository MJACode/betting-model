import React, { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Minimal global toast — a brief bottom banner for lightweight confirmations
 * ("Saved to your parlays") that don't warrant a blocking Alert. Module-store +
 * listener pattern (same as useParlaySlip); render <ToastHost/> once at the app
 * root and call showToast(msg) from anywhere.
 */

type Listener = (msg: string) => void;
const listeners = new Set<Listener>();

export function showToast(message: string): void {
  listeners.forEach((fn) => fn(message));
}

const VISIBLE_MS = 2200;

export function ToastHost() {
  const insets = useSafeAreaInsets();
  const [msg, setMsg] = useState<string | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const listener: Listener = (m) => {
      setMsg(m);
      if (timer.current) clearTimeout(timer.current);
      Animated.timing(opacity, { toValue: 1, duration: 160, useNativeDriver: true }).start();
      timer.current = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(
          ({ finished }) => {
            if (finished) setMsg(null);
          },
        );
      }, VISIBLE_MS);
    };
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [opacity]);

  if (!msg) return null;
  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.toast, { opacity, bottom: insets.bottom + spacing.xxl }]}
    >
      <Text style={styles.text}>{msg}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  toast: {
    position: 'absolute',
    left: spacing.xl,
    right: spacing.xl,
    alignItems: 'center',
    backgroundColor: colors.textPrimary,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  text: {
    color: colors.bg,
    fontSize: font.size.callout,
    fontWeight: font.weight.medium,
    textAlign: 'center',
  },
});
