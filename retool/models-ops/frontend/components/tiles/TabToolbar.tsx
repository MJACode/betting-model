import { useState, type ReactNode } from 'react'
import {
  Save, CopyPlus, Trash2, RotateCcw, Eye, Move, AlertCircle, CheckCircle2, Loader2, MoreHorizontal, Check, Info,
} from 'lucide-react'
import { Button } from '../../lib/shadcn/button'
import { Input } from '../../lib/shadcn/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectSeparator } from '../../lib/shadcn/select'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../lib/shadcn/dropdown-menu'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../lib/shadcn/dialog'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../../lib/shadcn/alert-dialog'
import { cn } from '../../lib/shadcn/utils'
import { DEFAULT_LAYOUT } from './layoutTypes'
import type { TabLayouts } from './useTabLayouts'
import { useMediaQuery, DESKTOP_QUERY } from '../../hooks/useMediaQuery'

function SaveAsDialog({
  open, onOpenChange, layouts,
}: { open: boolean; onOpenChange: (o: boolean) => void; layouts: TabLayouts }) {
  const [name, setName] = useState('')
  const trimmed = name.trim()
  const valid = trimmed.length >= 1 && trimmed.length <= 60
  const exists = layouts.saved.some(s => s.name === trimmed)

  async function submit() {
    if (!valid || layouts.busy) return
    const ok = await layouts.saveAs(trimmed)
    if (ok) {
      setName('')
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={o => { if (!o) setName(''); onOpenChange(o) }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Save layout as…</DialogTitle>
          <DialogDescription>Saves the current tile arrangement for this tab under a name only you see.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={e => { e.preventDefault(); void submit() }}
          className="space-y-2"
        >
          <Input
            autoFocus
            value={name}
            maxLength={60}
            placeholder="e.g. Morning check"
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
            aria-label="Layout name"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{exists ? 'A layout with this name exists; saving replaces it.' : '1 to 60 characters.'}</span>
            <span className="tabular-nums">{trimmed.length}/60</span>
          </div>
          {layouts.actionError && (
            <p className="flex items-start gap-1.5 text-xs text-crit"><AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{layouts.actionError}</p>
          )}
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => void submit()} disabled={!valid || layouts.busy}>
            {layouts.busy && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * The layout controls beside a tab's heading: which layout, Customize (drag
 * and resize tiles), and a menu with save, save as, delete, reset and the
 * hidden tiles. Every action of the earlier toolbar is here.
 */
export function TabToolbar({ layouts }: { layouts: TabLayouts }) {
  const [saveAsOpen, setSaveAsOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const isDefault = layouts.selected === DEFAULT_LAYOUT
  const canSave = layouts.available === true && !layouts.busy
  const hidden = layouts.working.filter(t => t.hidden)
  const metaById = new Map(layouts.metas.map(m => [m.id, m]))

  return (
    <div className="flex flex-wrap items-center gap-2">
      {layouts.savable && (
        <Select value={layouts.selected} onValueChange={layouts.selectLayout}>
          <SelectTrigger className="h-8 w-44 bg-card text-[13px]" aria-label="Layout">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={DEFAULT_LAYOUT} className="text-sm">Default layout</SelectItem>
            {layouts.saved.length > 0 && <SelectSeparator />}
            {layouts.saved.map(s => (
              <SelectItem key={s.name} value={s.name} className="text-sm">{s.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      <Button
        size="sm"
        variant={layouts.arrange ? 'default' : 'outline'}
        className={cn('h-8 gap-1.5 text-xs', !layouts.arrange && 'bg-card')}
        onClick={() => layouts.setArrange(!layouts.arrange)}
        aria-pressed={layouts.arrange}
      >
        {layouts.arrange ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Move className="h-3.5 w-3.5" aria-hidden />}
        {layouts.arrange ? 'Done' : 'Customize'}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline" className="relative h-8 w-8 bg-card p-0" aria-label="Layout options">
            <MoreHorizontal className="h-4 w-4" aria-hidden />
            {hidden.length > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] font-semibold leading-none text-white">
                {hidden.length}
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          {layouts.savable ? (
            <>
              <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Layout</DropdownMenuLabel>
              <DropdownMenuItem
                onSelect={() => void layouts.saveCurrent()}
                disabled={!canSave || isDefault}
                className="gap-2 text-sm"
                title={isDefault ? 'The built-in Default cannot be overwritten; use Save as…' : undefined}
              >
                <Save className="h-3.5 w-3.5" /> Save
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setSaveAsOpen(true)} disabled={!canSave} className="gap-2 text-sm">
                <CopyPlus className="h-3.5 w-3.5" /> Save as…
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setConfirmDelete(true)} disabled={!canSave || isDefault} className="gap-2 text-sm">
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </DropdownMenuItem>
            </>
          ) : (
            <div className="flex items-start gap-2 px-2 py-1.5 text-xs text-muted-foreground">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              Layouts on this tab last for this visit; they are not saved.
            </div>
          )}
          <DropdownMenuItem onSelect={layouts.resetToDefault} className="gap-2 text-sm">
            <RotateCcw className="h-3.5 w-3.5" /> Reset to default
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Hidden tiles</DropdownMenuLabel>
          {hidden.length === 0 ? (
            <div className="px-2 py-1.5 text-xs text-muted-foreground">Every tile is showing. Hide one from its own menu.</div>
          ) : (
            hidden.map(t => (
              <DropdownMenuItem key={t.id} onSelect={() => layouts.showTile(t.id)} className="gap-2 text-sm">
                <Eye className="h-3.5 w-3.5" />
                Show {metaById.get(t.id)?.title ?? t.id}
              </DropdownMenuItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {layouts.busy && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-label="Working" />}

      <SaveAsDialog open={saveAsOpen} onOpenChange={setSaveAsOpen} layouts={layouts} />

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{layouts.selected}"?</AlertDialogTitle>
            <AlertDialogDescription>This removes the saved layout. The tab switches back to Default.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void layouts.deleteSelected()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

/** One line under the heading: unsaved changes, notices, errors, and how to arrange. */
export function TabToolbarStatus({ layouts }: { layouts: TabLayouts }) {
  const desktop = useMediaQuery(DESKTOP_QUERY)
  const items: ReactNode[] = []
  if (layouts.dirty && layouts.savable) {
    items.push(
      <span key="dirty" className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-secondary-fg">Unsaved changes</span>,
    )
  }
  if (layouts.savable && layouts.available === false && !layouts.loadError) {
    items.push(<span key="off" className="text-muted-foreground">Saving layouts turns on after a database update.</span>)
  }
  if (layouts.loadError) {
    items.push(
      <span key="load" className="flex items-center gap-1.5 text-crit"><AlertCircle className="h-3.5 w-3.5" />Saved layouts could not be read: {layouts.loadError}</span>,
    )
  }
  if (layouts.actionError) {
    items.push(<span key="act" className="flex items-center gap-1.5 text-crit"><AlertCircle className="h-3.5 w-3.5" />{layouts.actionError}</span>)
  }
  if (layouts.notice) {
    items.push(<span key="note" className="flex items-center gap-1.5 text-good"><CheckCircle2 className="h-3.5 w-3.5" />{layouts.notice}</span>)
  }
  if (layouts.arrange) {
    items.push(
      <span key="how" className="text-muted-foreground">
        {desktop
          ? 'Drag a tile by its header; resize from the bottom-right corner or pick a size from its menu. Press Done when finished.'
          : 'On a narrow screen tiles stack in layout order; you can still hide and show them.'}
      </span>,
    )
  }
  if (items.length === 0) return null
  return <div className="-mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">{items}</div>
}
