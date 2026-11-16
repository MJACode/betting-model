import { createContext, useContext, type ReactNode } from 'react'
import { useCurrentUser } from '../hooks/useCurrentUser'

/** undefined while loading, null when nobody is signed in, else the email. */
const ViewerContext = createContext<string | null | undefined>(undefined)

export function ViewerProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useCurrentUser()
  return (
    <ViewerContext.Provider value={loading ? undefined : (user?.email ?? null)}>
      {children}
    </ViewerContext.Provider>
  )
}

export function useViewerEmail(): string | null | undefined {
  return useContext(ViewerContext)
}
