import { useEffect, useState } from 'react';

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
    setInstalled(null);
    void isBookAppInstalled(book).then((v) => {
      if (alive) setInstalled(v);
    });
    return () => {
      alive = false;
    };
  }, [book]);
  return installed;
}
