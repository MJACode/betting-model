import { useCallback, useEffect, useState } from 'react'
import { readStorage, writeStorage } from '../utils/safeStorage'

export type ThemeChoice = 'light' | 'dark'

const STORAGE_KEY = 'signalbase-ops:theme'

function storedChoice(): ThemeChoice | null {
  const v = readStorage(STORAGE_KEY)
  return v === 'light' || v === 'dark' ? v : null
}

function isDarkNow(): boolean {
  return document.documentElement.classList.contains('dark')
}

/**
 * Light/dark toggle for the header. With no stored choice the page follows the
 * system setting (handled by darkMode.ts); once the viewer picks a mode it is
 * remembered and re-applied whenever something else flips the class.
 */
export function useThemeMode() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    const c = storedChoice()
    return c ? c === 'dark' : isDarkNow()
  })

  useEffect(() => {
    const apply = () => {
      const c = storedChoice()
      if (c) {
        const want = c === 'dark'
        if (isDarkNow() !== want) document.documentElement.classList.toggle('dark', want)
      }
      setIsDark(isDarkNow())
    }
    apply()
    const observer = new MutationObserver(apply)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  const toggle = useCallback(() => {
    const next: ThemeChoice = isDarkNow() ? 'light' : 'dark'
    writeStorage(STORAGE_KEY, next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }, [])

  return { isDark, toggle }
}
