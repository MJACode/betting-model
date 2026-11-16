import { useState } from 'react'
import {
  LayoutGrid, Save, CopyPlus, Trash2, RotateCcw, Eye, Move, AlertCircle, CheckCircle2, Loader2,
} from 'lucide-react'
import { Button } from '../../lib/shadcn/button'
import { Switch } from '../../lib/shadcn/switch'
import { Input } from '../../lib/shadcn/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectSeparator } from '../../lib/shadcn/select'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger,
} from '../../lib/shadcn/dropdown-menu'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../lib/shadcn/dialog'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../../lib/shadcn/alert-dialog'
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

export function TabToolbar({ layouts }: { layouts: TabLayouts }) {
  const [saveAsOpen, setSaveAsOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const desktop = useMediaQuery(DESKTOP_QUERY)
  const isDefault = layouts.selected === DEFAULT_LAYOUT
  const canSave = layouts.available === true && !layouts.busy
  const hidden = layouts.working.filter(t => t.hidden)
  const metaById = new Map(layouts.metas.map(m => [m.id, m]))

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card px-3 py-2 shadow-retool-sm">
        <div className="flex items-center gap-2">
          <LayoutGrid className="h-4 w-4 text-muted-foreground" aria-hidden />
          <span className="text-xs font-medium text-muted-foreground">Layout</span>
          <Select value={layouts.selected} onValueChange={layouts.selectLayout}>
            <SelectTrigger className="h-8 w-48 text-sm" aria-label="Layout">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DEFAULT_LAYOUT} className="text-sm">Default</SelectItem>
              {layouts.saved.length > 0 && <SelectSeparator />}
              {layouts.saved.map(s => (
                <SelectItem key={s.name} value={s.name} className="text-sm">{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {layouts.dirty && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-secondary-fg">Unsaved changes</span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <Button
            size="sm" variant="outline" className="h-8 gap-1.5 text-xs"
            onClick={() => void layouts.saveCurrent()}
            disabled={!canSave || isDefault}
            title={isDefault ? 'The built-in Default cannot be overwritten; use Save as…' : undefined}
          >
            <Save className="h-3.5 w-3.5" /> Save
          </Button>
          <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs" onClick={() => setSaveAsOpen(true)} disabled={!canSave}>
            <CopyPlus className="h-3.5 w-3.5" /> Save as…
          </Button>
          <Button size="sm" variant="ghost" className="h-8 gap-1.5 text-xs" onClick={() => setConfirmDelete(true)} disabled={!canSave || isDefault}>
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </Button>
          <Button size="sm" variant="ghost" className="h-8 gap-1.5 text-xs" onClick={layouts.resetToDefault}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset to default
          </Button>
          {layouts.busy && <Loader2 className="ml-1 h-4 w-4 animate-spin text-muted-foreground" aria-label="Working" />}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
                <Eye className="h-3.5 w-3.5" />
                Tiles{hidden.length > 0 ? ` (${hidden.length} hidden)` : ''}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
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
          <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-secondary-fg">
            <Move className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
            Arrange
            <Switch checked={layouts.arrange} onCheckedChange={layouts.setArrange} aria-label="Arrange tiles" />
          </label>
        </div>
      </div>

      <div className="flex min-h-[18px] flex-wrap items-center gap-x-4 gap-y-1 px-1 text-xs">
        {layouts.available === false && !layouts.loadError && (
          <span className="text-muted-foreground">Saving layouts turns on after a database update.</span>
        )}
        {layouts.loadError && (
          <span className="flex items-center gap-1.5 text-crit"><AlertCircle className="h-3.5 w-3.5" />Saved layouts could not be read: {layouts.loadError}</span>
        )}
        {layouts.actionError && !saveAsOpen && (
          <span className="flex items-center gap-1.5 text-crit"><AlertCircle className="h-3.5 w-3.5" />{layouts.actionError}</span>
        )}
        {layouts.notice && (
          <span className="flex items-center gap-1.5 text-good"><CheckCircle2 className="h-3.5 w-3.5" />{layouts.notice}</span>
        )}
        {layouts.arrange && (
          <span className="text-muted-foreground">
            {desktop
              ? 'Drag a tile by its header; resize from the bottom-right corner or pick a size from its menu.'
              : 'On a narrow screen tiles stack in layout order; you can still hide and show them.'}
          </span>
        )}
      </div>

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
