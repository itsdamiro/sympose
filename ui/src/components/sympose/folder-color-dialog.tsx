import * as React from "react"
import { Folder01Icon } from "@hugeicons/core-free-icons"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { FolderColorField } from "@/components/sympose/folder-color-field"
import { IconPicker } from "@/components/sympose/icon-picker"
import { saveFolderColor } from "@/lib/folder-color-api"
import { notify } from "@/lib/notify"

export interface FolderLookStart {
  accent: string | null
  accentDark: string | null
  icon: string | null
}

function ColorForm({
  path,
  start,
  persona,
  onClose,
  onSaved,
}: {
  path: string
  start: FolderLookStart
  persona: string
  onClose: () => void
  onSaved: () => void
}) {
  const [colors, setColors] = React.useState({ accent: start.accent, accentDark: start.accentDark })
  const [icon, setIcon] = React.useState(start.icon)
  const [busy, setBusy] = React.useState(false)
  const top = path.split("/")[0]
  const name = path.split("/").slice(1).join("/")
  const changed = colors.accent !== start.accent || colors.accentDark !== start.accentDark || icon !== start.icon

  const save = async () => {
    if (busy) return
    setBusy(true)
    const res = await saveFolderColor(path, { ...colors, icon }, persona)
    setBusy(false)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    onSaved()
    onClose()
    notify.success(
      colors.accent === null && colors.accentDark === null && icon === null ? `Cleared the look of ${name}` : `Saved the look of ${name}`
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Look of {name}</DialogTitle>
        <DialogDescription>
          The icon is drawn beside this folder in the list. Notes in it are drawn in the colour in the Knowledge Nebula,
          unless a folder inside it has its own. Both are saved in the properties of {top}/{top}.md. No colour means the
          folder above it decides.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-4">
        <div className="grid gap-1.5 text-sm">
          <span className="font-medium">Icon</span>
          <IconPicker label="Icon" value={icon} fallback={Folder01Icon} onChange={setIcon} disabled={busy} />
        </div>
        <div className="grid gap-1.5 text-sm">
          <span className="font-medium">Colour</span>
          <FolderColorField {...colors} onChange={setColors} disabled={busy} />
        </div>
      </div>
      <DialogFooter>
        <DialogClose render={<Button variant="outline" disabled={busy} />}>Cancel</DialogClose>
        <Button disabled={busy || !changed} onClick={() => void save()}>
          Save
        </Button>
      </DialogFooter>
    </>
  )
}

/**
 * The Folder look dialog (docs/decisions/090), opened from the right-click menu of a folder below a top-level one:
 * an icon and a colour for the folder, to tell one project from another in the list and the Knowledge Nebula. It opens filled from the
 * folder's own entry (`setup.start`, already fetched). Cancel writes nothing; only Save does.
 */
export function FolderColorDialog({
  setup,
  persona,
  onClose,
  onSaved,
}: {
  setup: { path: string; start: FolderLookStart } | null
  persona: string
  onClose: () => void
  /** Called after the look was written, so the tree and the nebula can refresh. */
  onSaved: () => void
}) {
  return (
    <Dialog open={setup !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {setup !== null && (
          <ColorForm key={setup.path} path={setup.path} start={setup.start} persona={persona} onClose={onClose} onSaved={onSaved} />
        )}
      </DialogContent>
    </Dialog>
  )
}
