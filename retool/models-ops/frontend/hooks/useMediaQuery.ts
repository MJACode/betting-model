import { useEffect, useState } from 'react'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    try {
      return window.matchMedia(query).matches
    } catch {
      return true
    }
  })

  useEffect(() => {
    let mq: MediaQueryList
    try {
      mq = window.matchMedia(query)
    } catch {
      return
    }
    const onChange = () => setMatches(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [query])

  return matches
}

/** Tiles are arranged on a 12-column grid at this width and above; below it they stack. */
export const DESKTOP_QUERY = '(min-width: 1024px)'
