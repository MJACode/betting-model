import React, { useEffect, useRef } from 'react';
import { Modal as RNModal, Platform, StyleSheet, View, type ModalProps } from 'react-native';

import { noteModalDismissed, noteModalShown, noteModalVisible } from '@/lib/freezeLog';

/**
 * React Native's Modal, with freeze tracking (src/lib/freezeLog.ts). Every
 * pop-up in the app uses this one, never react-native's directly
 * (tests/test_mobile_freeze_log.py), because an iOS pop-up that opens or
 * closes without iOS confirming it leaves an invisible layer over the app that
 * swallows every tap — the "screen won't respond, have to restart" report of
 * 2026-11-06. Behaves exactly like Modal; it only records.
 *
 * `trackName` names the pop-up in the trail and in modal_stuck reports.
 */
export interface TrackedModalProps extends ModalProps {
  trackName: string;
}

export function Modal({ trackName, visible = true, onShow, onDismiss, children, ...rest }: TrackedModalProps) {
  const prev = useRef<boolean | null>(null);

  useEffect(() => {
    // First render: only a pop-up that mounts open is worth recording.
    if (prev.current === null && !visible) {
      prev.current = false;
      return;
    }
    if (prev.current !== visible) noteModalVisible(trackName, visible, Platform.OS === 'ios');
    prev.current = visible;
  }, [visible, trackName]);

  // Unmounting while open removes the pop-up without a visible=false.
  useEffect(
    () => () => {
      if (prev.current) noteModalVisible(trackName, false, false);
    },
    [trackName],
  );

  return (
    <RNModal
      {...rest}
      visible={visible}
      onShow={(e) => {
        noteModalShown(trackName);
        onShow?.(e);
      }}
      onDismiss={() => {
        noteModalDismissed(trackName);
        onDismiss?.();
      }}
    >
      {/* While the pop-up is open, this wrapper does not take taps (the
          sheet's own backdrop does). Once it is told to close, pointerEvents
          none: a modal iOS has not finished tearing down must not keep
          swallowing taps on the screen underneath, including Back. */}
      <View style={styles.fill} pointerEvents={visible ? 'box-none' : 'none'} collapsable={false}>
        {children}
      </View>
    </RNModal>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});
