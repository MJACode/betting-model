import React, { useEffect, useRef } from 'react';
import { Modal as RNModal, Platform, type ModalProps } from 'react-native';

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

export function Modal({ trackName, visible = true, onShow, onDismiss, ...rest }: TrackedModalProps) {
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
    />
  );
}
