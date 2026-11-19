import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './lib/shadcn/tabs'
import { RefreshCw, Moon, Sun, Layers, SlidersHorizontal, Activity, Database, TrendingUp, HeartPulse, Calculator, LayoutDashboard, type LucideIcon } from 'lucide-react'
import ModelsTab from './pages/ModelsTab'
import { TableSkeleton } from './components/PanelUtils'
import { ModelNamesProvider } from './components/models/ModelNamesProvider'
import { ViewerProvider } from './components/ViewerContext'
import { BrandLockup } from './components/brand/SignalMark'
import { useThemeMode } from './hooks/useThemeMode'
import './appTheme.css'

// The Models tab is bundled in; the rest load when opened. Key Metrics opens
// first, so it loads at once (its own code is small; its data is one call).
const KeyMetricsTab = lazy(() => import('./pages/exec/KeyMetricsTab'))
const VolumeTab = lazy(() => import('./pages/VolumeTab'))
const OpsTab = lazy(() => import('./pages/OpsTab'))
const DatabaseTab = lazy(() => import('./pages/DatabaseTab'))
const PicksClvTab = lazy(() => import('./pages/picks/PicksClvTab'))
const HealthTab = lazy(() => import('./pages/HealthTab'))
const SimTab = lazy(() => import('./pages/sim/SimTab'))

function TabFallback() {
  return (
    <div className="px-4 py-6 sm:px-6">
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

const TABS: ReadonlyArray<{ value: string; label: string; icon: LucideIcon }> = [
  { value: 'exec', label: 'Key Metrics', icon: LayoutDashboard },
  { value: 'models', label: 'Models', icon: Layers },
  { value: 'health', label: 'Model Health', icon: HeartPulse },
  { value: 'volume', label: 'Volume', icon: SlidersHorizontal },
  { value: 'ops', label: 'Ops', icon: Activity },
  { value: 'database', label: 'Database', icon: Database },
  { value: 'picks', label: 'Picks & CLV', icon: TrendingUp },
  { value: 'sim', label: 'Profit Simulation', icon: Calculator },
]

const contentClass = 'mt-0 focus-visible:outline-none focus-visible:ring-0'

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const { isDark, toggle } = useThemeMode()
  const navRef = useRef<HTMLDivElement>(null)

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

  // Publish the sticky tab bar's height so pinned content can sit just beneath it.
  useEffect(() => {
    const el = navRef.current
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
          <Tabs defaultValue="exec" className="w-full">
            <header className="sb-header sb-header-top">
              <div className="mx-auto flex h-14 max-w-[1680px] items-center justify-between gap-3 px-4 sm:px-6">
                <BrandLockup product="Ops" />
                <div className="flex items-center gap-2">
                  {lastRefreshed && (
                    <span className="sb-caption hidden text-xs md:inline">
                      Updated <span className="tabular-nums">{formatTimestamp(lastRefreshed)}</span>
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleRefresh()}
                    disabled={refreshing}
                    className="sb-chrome-btn inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium disabled:opacity-60"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} aria-hidden />
                    <span className="hidden sm:inline">Refresh all</span>
                    <span className="sm:hidden">Refresh</span>
                  </button>
                  <button
                    type="button"
                    onClick={toggle}
                    className="sb-chrome-btn inline-flex h-8 w-8 items-center justify-center rounded-lg"
                    aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                    title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                  >
                    {isDark ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
                  </button>
                </div>
              </div>
            </header>

            <div ref={navRef} className="sb-nav sticky top-0 z-30">
              <div className="mx-auto max-w-[1680px] px-4 sm:px-6">
                <TabsList className="sb-scroll-x flex h-auto w-full justify-start gap-6 rounded-none bg-transparent p-0">
                  {TABS.map(t => {
                    const Icon = t.icon
                    return (
                      <TabsTrigger
                        key={t.value}
                        value={t.value}
                        className="sb-tab h-11 rounded-none border-0 bg-transparent px-0.5 py-0 text-[13.5px] font-medium text-[hsl(var(--sb-caption))] shadow-none ring-offset-0 hover:text-[hsl(var(--sb-on-navy))] focus-visible:ring-0 data-[state=active]:bg-transparent data-[state=active]:text-[hsl(var(--sb-on-navy))] data-[state=active]:shadow-none"
                      >
                        <Icon className="h-4 w-4" aria-hidden />
                        {t.label}
                      </TabsTrigger>
                    )
                  })}
                </TabsList>
              </div>
            </div>

            <main className="mx-auto max-w-[1680px] pb-10">
              <TabsContent value="exec" className={contentClass}>
                <Suspense fallback={<TabFallback />}><KeyMetricsTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="models" className={contentClass}>
                <ModelsTab refreshKey={refreshKey} />
              </TabsContent>
              <TabsContent value="health" className={contentClass}>
                <Suspense fallback={<TabFallback />}><HealthTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="volume" className={contentClass}>
                <Suspense fallback={<TabFallback />}><VolumeTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="ops" className={contentClass}>
                <Suspense fallback={<TabFallback />}><OpsTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="database" className={contentClass}>
                <Suspense fallback={<TabFallback />}><DatabaseTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="picks" className={contentClass}>
                <Suspense fallback={<TabFallback />}><PicksClvTab refreshKey={refreshKey} /></Suspense>
              </TabsContent>
              <TabsContent value="sim" className={contentClass}>
                <Suspense fallback={<TabFallback />}><SimTab /></Suspense>
              </TabsContent>
            </main>
          </Tabs>
        </div>
      </ModelNamesProvider>
    </ViewerProvider>
  )
}
