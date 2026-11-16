import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './lib/shadcn/tabs'
import { Button } from './lib/shadcn/button'
import { RefreshCw, Moon, Sun, Activity } from 'lucide-react'
import ModelsTab from './pages/ModelsTab'
import { TableSkeleton } from './components/PanelUtils'
import { ModelNamesProvider } from './components/models/ModelNamesProvider'
import { ViewerProvider } from './components/ViewerContext'
import { useThemeMode } from './hooks/useThemeMode'
import './appTheme.css'

// Only the Models tab is needed for first paint; the rest load when opened.
const VolumeTab = lazy(() => import('./pages/VolumeTab'))
const OpsTab = lazy(() => import('./pages/OpsTab'))
const PicksClvTab = lazy(() => import('./pages/picks/PicksClvTab'))

function TabFallback() {
  return (
    <div className="px-4 py-5 sm:px-6">
      <TableSkeleton rows={6} />
    </div>
  )
}

function formatTimestamp(d: Date): string {
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

const TABS = [
  { value: 'models', label: 'Models' },
  { value: 'volume', label: 'Volume' },
  { value: 'ops', label: 'Ops' },
  { value: 'picks', label: 'Picks & CLV' },
] as const

const triggerClass =
  'relative h-11 rounded-none border-b-2 border-transparent bg-transparent px-1 text-sm font-medium text-muted-foreground shadow-none transition-colors hover:text-foreground data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none'

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const { isDark, toggle } = useThemeMode()
  const headerRef = useRef<HTMLElement>(null)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    setRefreshKey(k => k + 1)
    // Give a brief visual affordance, then mark complete
    await new Promise(r => setTimeout(r, 600))
    setLastRefreshed(new Date())
    setRefreshing(false)
  }, [])

  useEffect(() => {
    setLastRefreshed(new Date())
  }, [])

  // Publish the header height so pinned content can sit just beneath it.
  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    const publish = () => document.documentElement.style.setProperty('--app-header-h', `${el.offsetHeight}px`)
    publish()
    const ro = new ResizeObserver(publish)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <ViewerProvider>
      <ModelNamesProvider>
        <div className="min-h-screen bg-background text-foreground">
          <Tabs defaultValue="models" className="w-full">
            <header ref={headerRef} className="sticky top-0 z-30 border-b bg-card/90 backdrop-blur">
              <div className="mx-auto max-w-[1680px] px-4 sm:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-primary text-primary-foreground shadow-retool-sm">
                      <Activity className="h-[18px] w-[18px]" aria-hidden />
                    </span>
                    <div>
                      <h1 className="text-xl font-semibold leading-tight tracking-tight">Signalbase Ops</h1>
                      <p className="text-xs text-muted-foreground">Models, volume, ops, picks and CLV</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {lastRefreshed && (
                      <span className="hidden text-xs text-muted-foreground sm:inline">
                        Last refreshed <span className="tabular-nums">{formatTimestamp(lastRefreshed)}</span>
                      </span>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleRefresh()}
                      disabled={refreshing}
                      className="h-8 gap-1.5 text-xs"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                      Refresh all
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={toggle}
                      className="h-8 w-8 p-0"
                      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                    >
                      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <TabsList className="mt-2 h-auto gap-6 rounded-none bg-transparent p-0">
                  {TABS.map(t => (
                    <TabsTrigger key={t.value} value={t.value} className={triggerClass}>{t.label}</TabsTrigger>
                  ))}
                </TabsList>
              </div>
            </header>

            <main className="mx-auto max-w-[1680px]">
              <TabsContent value="models" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
                <ModelsTab refreshKey={refreshKey} />
              </TabsContent>
              <TabsContent value="volume" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
                <Suspense fallback={<TabFallback />}><VolumeTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="ops" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
                <Suspense fallback={<TabFallback />}><OpsTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="picks" className="mt-0 focus-visible:outline-none focus-visible:ring-0">
                <Suspense fallback={<TabFallback />}><PicksClvTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
            </main>
          </Tabs>
        </div>
      </ModelNamesProvider>
    </ViewerProvider>
  )
}
