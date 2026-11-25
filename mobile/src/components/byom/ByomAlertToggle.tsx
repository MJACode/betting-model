import React, { useCallback, useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';

import { AppSwitch } from '@/components/AppSwitch';
import { fetchByomAlertSettings, setByomAlerts } from '@/lib/byomAlerts';
import { friendlyCause, isAbortError } from '@/lib/errors';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * "Alert me on new bets" for one saved model (Matt, 2026-11-25: on by
 * default, a switch per model). Hidden until the server has the setting,
 * so a build ahead of the migration shows no switch that does nothing.
 */
export function ByomAlertToggle({ modelId, modelName }: { modelId: string; modelName: string }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    fetchByomAlertSettings()
      .then((settings) => {
        if (!live || settings == null) return;
        setEnabled(settings.get(modelId) ?? true);
      })
      .catch(() => {
        // A failed read leaves the switch hidden; the model page still works.
      });
    return () => {
      live = false;
    };
  }, [modelId]);

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

  if (enabled == null) return null;
  const note = enabled
    ? 'You get a notification when this model finds a bet. NFL only for now.'
    : 'No notifications from this model. Its bets still show here.';
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <Text style={styles.label}>Alert me on new bets</Text>
        <AppSwitch
          value={enabled}
          onValueChange={onToggle}
          disabled={saving}
          trackColor={{ true: colors.tint }}
          accessibilityLabel={`Alerts for ${modelName}`}
          accessibilityHint={note}
        />
      </View>
      <Text style={styles.note}>{note}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.lg,
  },
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
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});
