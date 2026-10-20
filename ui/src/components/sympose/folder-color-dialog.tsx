import * as React from "react"

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
import { saveFolderColor } from "@/lib/folder-color-api"
import { notify } from "@/lib/notify"

function ColorForm({
  path,
  start,
  persona,
  onClose,
  onSaved,
}: {
  path: string
  start: { accent: string | null; accentDark: string | null }
  persona: string
  onClose: () => void
  onSaved: () => void
}) {
  const [colors, setColors] = React.useState(start)
  const [busy, setBusy] = React.useState(false)
  const top = path.split("/")[0]
  const name = path.split("/").slice(1).join("/")
  const changed = colors.accent !== start.accent || colors.accentDark !== start.accentDark

  const save = async () => {
    if (busy) return
    setBusy(true)
    const res = await saveFolderColor(path, colors, persona)
    setBusy(false)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    onSaved()
    onClose()
    notify.success(
      colors.accent === null && colors.accentDark === null ? `Cleared the colour of ${name}` : `Saved the colour of ${name}`
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Colour for {name}</DialogTitle>
        <DialogDescription>
          Notes in this folder are drawn in this colour in the Knowledge Nebula, unless a folder inside it has its own. It
          is saved in the properties of {top}/{top}.md. No colour means the folder above it decides.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-1.5 text-sm">
        <span className="font-medium">Colour</span>
        <FolderColorField {...colors} onChange={setColors} disabled={busy} />
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
 * The Folder colour dialog (docs/decisions/090), opened from the right-click menu of a folder below a top-level one:
 * a colour for the folder, to tell one project from another in the Knowledge Nebula. It opens filled from the
 * folder's own entry (`setup.start`, already fetched). Cancel writes nothing; only Save does.
 */
export function FolderColorDialog({
  setup,
  persona,
  onClose,
  onSaved,
}: {
  setup: { path: string; start: { accent: string | null; accentDark: string | null } } | null
  persona: string
  onClose: () => void
  /** Called after the colour was written, so the tree and the nebula can refresh. */
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
