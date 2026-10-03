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
import type { CreateKind } from "@/lib/use-create-flow"

const FIELD =
  "block w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-brand disabled:opacity-60"

function Form({
  kind,
  onCreate,
  onClose,
}: {
  kind: CreateKind
  /** Creates it; `true` when it was created, so the dialog can close. */
  onCreate: (name: string) => Promise<boolean>
  onClose: () => void
}) {
  const [name, setName] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const submit = async () => {
    if (busy || !name.trim()) return
    setBusy(true)
    const ok = await onCreate(name)
    setBusy(false)
    if (ok) onClose()
  }
  const noun = kind === "note" ? "note" : "folder"
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        void submit()
      }}
    >
      <DialogHeader>
        <DialogTitle>New {noun} in the vault root</DialogTitle>
        <DialogDescription>
          {kind === "note"
            ? "A note at the top level of the vault, outside any folder."
            : "A folder at the top level of the vault. You can say what it is for next."}
        </DialogDescription>
      </DialogHeader>
      <input
        autoFocus
        value={name}
        disabled={busy}
        aria-label={`Name of the new ${noun}`}
        placeholder={kind === "note" ? "Note name" : "Folder name"}
        onChange={(e) => setName(e.target.value)}
        className={`${FIELD} my-4`}
      />
      <DialogFooter>
        <DialogClose render={<Button type="button" variant="outline" disabled={busy} />}>Cancel</DialogClose>
        <Button type="submit" disabled={busy || !name.trim()}>
          Create
        </Button>
      </DialogFooter>
    </form>
  )
}

/**
 * The name prompt for a note or folder made at the vault root from the main menu's right-click or long-press menu
 * (docs/decisions/060). Open while `kind` is set; Enter or Create makes it, Cancel or closing writes nothing.
 */
export function RootCreateDialog({
  kind,
  onCreate,
  onClose,
}: {
  kind: CreateKind | null
  onCreate: (kind: CreateKind, name: string) => Promise<boolean>
  onClose: () => void
}) {
  return (
    <Dialog open={kind !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {kind !== null && <Form key={kind} kind={kind} onCreate={(name) => onCreate(kind, name)} onClose={onClose} />}
      </DialogContent>
    </Dialog>
  )
}
