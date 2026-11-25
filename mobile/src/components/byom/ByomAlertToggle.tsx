import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppSwitch } from '@/components/AppSwitch';
import { fetchByomAlertSettings, setByomAlerts } from '@/lib/byomAlerts';
import { friendlyCause, isAbortError } from '@/lib/errors';
import { cardDense, colors, font, opacity, spacing } from '@/lib/theme';

const LABEL = 'Alert me on new bets';

/**
 * "Alert me on new bets" for one saved model (Matt, 2026-11-25: on by
 * default, a switch per model). Hidden only while the server has no such
 * setting (the migration is not applied). A failed read shows the row with
 * Retry, so a member can always reach the switch that turns alerts off.
 */
export function ByomAlertToggle({ modelId, modelName }: { modelId: string; modelName: string }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'absent' | 'failed'>('loading');
  const [saving, setSaving] = useState(false);
  const seq = useRef(0);

  const load = useCallback(() => {
    const id = ++seq.current;
    setState('loading');
    fetchByomAlertSettings()
      .then((settings) => {
        if (seq.current !== id) return;
        if (settings == null) {
          setState('absent');
          return;
        }
        setEnabled(settings.get(modelId) ?? true);
        setState('ready');
      })
      .catch((e: unknown) => {
        if (seq.current !== id || isAbortError(e)) return;
        setState('failed');
      });
  }, [modelId]);

  useEffect(() => {
    load();
    return () => {
      seq.current += 1;
    };
  }, [load]);

  const onToggle = useCallback((next: boolean) => {
    const before = enabled;
    setEnabled(next);
    setSaving(true);
    setByomAlerts(modelId, next)
      .then((saved) => setEnabled(saved))
      .catch((e: unknown) => {
        setEnabled(before);
        if (isAbortError(e)) return;
        Alert.alert('Couldn’t change alerts', friendlyCause(e));
      })
      .finally(() => setSaving(false));
  }, [enabled, modelId]);

  if (state === 'absent' || state === 'loading') return null;

  if (state === 'failed' || enabled == null) {
    return (
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>{LABEL}</Text>
          <Pressable
            onPress={load}
            accessibilityRole="button"
            accessibilityLabel="Retry loading your alert setting"
            style={({ pressed }) => [styles.retry, pressed && styles.pressed]}
          >
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
        <Text style={styles.note}>Couldn’t load your alert setting.</Text>
      </View>
    );
  }

  const note = enabled
    ? 'You get a notification when this model finds a bet. NFL only for now.'
    : 'No notifications from this model. Its bets still show here.';
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.label}>{LABEL}</Text>
        <AppSwitch
          value={enabled}
          onValueChange={onToggle}
          disabled={saving}
          trackColor={{ true: colors.tint }}
          accessibilityLabel={`${LABEL}, ${modelName}`}
        />
      </View>
      <Text style={styles.note}>{note}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { ...cardDense, paddingVertical: spacing.sm, marginBottom: spacing.lg },
  row: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  label: {
    flexShrink: 1,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  retry: { minHeight: 44, minWidth: 44, justifyContent: 'center', alignItems: 'flex-end' },
  pressed: { opacity: opacity.pressed },
  retryText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});
