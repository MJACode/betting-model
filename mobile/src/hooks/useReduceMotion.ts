import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

/**
 * iOS Reduce Motion (Android: Remove animations). Pulses and fades check this
 * and hold still when it is on (HIG Motion; PATTERNS §E2). Starts `true` so a
 * skeleton never pulses for one frame before the setting has been read.
 */
export function useReduceMotion(): boolean {
  const [reduce, setReduce] = useState(true);
  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((on) => {
        if (alive) setReduce(on);
      })
      .catch(() => {
        if (alive) setReduce(false);
      });
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);
  return reduce;
}
