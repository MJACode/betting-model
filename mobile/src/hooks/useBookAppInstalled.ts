import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { isBookAppInstalled } from '@/lib/sportsbookLinks';

/**
 * Is the book's app on this phone? `true` / `false` when the build can ask
 * (a scheme declared in app.json's LSApplicationQueriesSchemes, iOS), `null`
 * while the answer is loading or when it cannot be known — see
 * `isBookAppInstalled`. A surface that offers the App Store should hide the
 * offer on `true` and keep it on `false` and `null`: an unknown is not a no.
 */
export function useBookAppInstalled(book: string): boolean | null {
  const [installed, setInstalled] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    const ask = () => {
      void isBookAppInstalled(book).then((v) => {
        if (alive) setInstalled(v);
      });
    };
    setInstalled(null);
    ask();
    // The flow this exists for: tap "Get {book} on the App Store", install,
    // come back. The sheet is mounted with its screen, so without this the
    // store row would still be showing (UX review). Same pattern as useNow.
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') ask();
    });
    return () => {
      alive = false;
      sub.remove();
    };
  }, [book]);
  return installed;
}
