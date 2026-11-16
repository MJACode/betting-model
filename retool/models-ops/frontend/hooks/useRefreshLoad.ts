import { useEffect } from 'react'

// The last "Refresh all" each data scope has loaded for. Lives for the page
// session so a tab opened after a refresh still skips the cache once.
const seen = new Map<string, number>()

/**
 * Loads a scope's data on mount and on "Refresh all". Normal loads may be
 * answered from the cache (then quietly re-fetched); a load caused by a newer
 * Refresh all always goes to the database.
 */
export function useRefreshLoad(scope: string, refreshKey: number, load: (skipCache: boolean) => void) {
  useEffect(() => {
    const last = seen.get(scope) ?? 0
    seen.set(scope, Math.max(last, refreshKey))
    load(refreshKey > last)
    // Only a new refreshKey (or a remount) should reload; `load` is rebuilt every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, refreshKey])
}
