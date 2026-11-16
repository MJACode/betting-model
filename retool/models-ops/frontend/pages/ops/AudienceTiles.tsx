import { Info, Users, Smartphone, MessageSquare, BookOpen, MessageCircle, Send } from 'lucide-react'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../../lib/shadcn/tooltip'
import { PanelError, StatCard, StatsSkeleton } from '../../components/PanelUtils'

type AudienceData = {
  subscribers_active: string
  subscribers_total: string
  push_devices: string
  linked_books: string
  feedback_open: string
  discord_posts_7d: string
  discord_posts_total: string
}

type TileConfig = {
  label: string
  icon: typeof Users
  value: string | null
  subtitle?: string
  darkByDesign?: boolean
  note?: string
  tooltip?: string
}

type Props = {
  data: unknown
  loading: boolean
  error: string | null
}

function NoteWithTooltip({ note, tooltip }: { note: string; tooltip?: string | undefined }) {
  if (!tooltip) return <span className="italic">{note}</span>
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex cursor-help items-center gap-1 italic">
            {note}
            <Info className="h-3 w-3 shrink-0" aria-hidden />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">{tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export default function AudienceTiles({ data, loading, error }: Props) {
  if (loading) return <StatsSkeleton count={6} />
  if (error) return <PanelError message={error} />

  const d = data as AudienceData | undefined | null

  const tiles: TileConfig[] = [
    {
      label: 'Active subscribers',
      icon: Users,
      value: d?.subscribers_active ?? '0',
      subtitle: `${d?.subscribers_total ?? '0'} total`,
      darkByDesign: true,
      note: 'Dark by design',
      tooltip: 'Billing ships dark — BILLING_ENABLED defaults to false. Zero is expected, not a failure.',
    },
    {
      label: 'Push devices',
      icon: Smartphone,
      value: d?.push_devices ?? '0',
      darkByDesign: true,
      note: 'Dark by design',
      tooltip: 'Native push build was never made. Zero is expected.',
    },
    {
      label: 'Discord members',
      icon: MessageSquare,
      value: null,
      note: 'Needs a bot token to read',
      tooltip: 'An incoming webhook is write-only and cannot read membership; needs a bot token that isn\'t set.',
    },
    { label: 'Linked sportsbooks', icon: BookOpen, value: d?.linked_books ?? '0' },
    { label: 'Open feedback', icon: MessageCircle, value: d?.feedback_open ?? '0' },
    {
      label: 'Discord posts (7d)',
      icon: Send,
      value: d?.discord_posts_7d ?? '—',
      subtitle: `${d?.discord_posts_total ?? '—'} total`,
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {tiles.map(t => (
        <StatCard
          key={t.label}
          label={t.label}
          icon={t.icon}
          value={
            t.value === null
              ? <span className="text-muted-foreground">n/a</span>
              : t.darkByDesign
                ? <span className="text-muted-foreground">{t.value}</span>
                : t.value
          }
          caption={
            <span className="flex flex-col gap-0.5">
              {t.subtitle && <span>{t.subtitle}</span>}
              {t.note && <NoteWithTooltip note={t.note} tooltip={t.tooltip} />}
            </span>
          }
        />
      ))}
    </div>
  )
}
