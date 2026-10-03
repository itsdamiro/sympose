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
import { notify } from "@/lib/notify"
import {
  createFolderDefinition,
  type NoteTemplate,
} from "@/lib/vault-definition-api"

const FIELD =
  "block w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-brand disabled:opacity-60"

function SetupForm({
  folder,
  template: start,
  manual,
  persona,
  onClose,
  onCreated,
}: {
  folder: string
  template: NoteTemplate
  /** Opened from "Define folder" on a folder that already exists, not as the step after creating one. */
  manual: boolean
  persona: string
  onClose: () => void
  onCreated: () => void
}) {
  const [purpose, setPurpose] = React.useState("")
  const [template, setTemplate] = React.useState(start.lines.join("\n"))
  const [busy, setBusy] = React.useState(false)

  const nothingToWrite = !purpose.trim() && !template.trim()

  // The button is disabled while there is nothing to write; this only stops a
  // second click while the first is in flight.
  const create = async () => {
    if (busy) return
    setBusy(true)
    const res = await createFolderDefinition(
      folder,
      purpose.trim(),
      template.split("\n"),
      persona
    )
    setBusy(false)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    onCreated()
    onClose()
    notify.success(`Created ${folder}/${folder}.md`)
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{manual ? `Define ${folder}` : `Set up ${folder}`}</DialogTitle>
        <DialogDescription>
          {manual ? "Say" : "Optional. Say"} what this folder is for and which properties its notes
          start with; both are saved in {folder}/{folder}.md.{" "}
          {manual ? "Cancel" : "Skip"} writes nothing.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-4">
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">What is this folder for?</span>
          <textarea
            rows={2}
            value={purpose}
            maxLength={500}
            disabled={busy}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="One or two sentences."
            className={FIELD}
          />
        </label>
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">Properties new notes start with</span>
          <textarea
            rows={5}
            value={template}
            disabled={busy}
            onChange={(e) => setTemplate(e.target.value)}
            placeholder="One property per line."
            spellCheck={false}
            className={`${FIELD} font-mono text-xs`}
          />
          <span className="text-xs text-muted-foreground">
            {start.source === "vault"
              ? "Started from your Templates/Note template.md."
              : "Started from the default keys."}{" "}
            {"{{title}}"} and {"{{date}}"} are filled in when a note is created.
          </span>
        </label>
      </div>
      <DialogFooter>
        <DialogClose render={<Button variant="outline" disabled={busy} />}>
          {manual ? "Cancel" : "Skip"}
        </DialogClose>
        <Button
          disabled={busy || nothingToWrite}
          onClick={() => void create()}
        >
          {manual ? "Save" : "Create the definition"}
        </Button>
      </DialogFooter>
    </>
  )
}

/**
 * The setup step after a root folder is created (docs/decisions/038): what
 * the folder is for and the properties its notes start with, both optional.
 * Open while `setup` is set, with the generic template already fetched (the
 * app shell only sets it for a folder the server says can have a definition).
 * Closing it, or Skip, writes nothing; only the user's own words are written,
 * and only on Create the definition.
 */
export function FolderSetupDialog({
  setup,
  persona,
  onClose,
  onCreated,
}: {
  setup: { folder: string; template: NoteTemplate; manual?: boolean } | null
  persona: string
  onClose: () => void
  /** Called after the definition note was written, so the tree can refresh. */
  onCreated: () => void
}) {
  return (
    <Dialog open={setup !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {setup !== null && (
          <SetupForm
            key={setup.folder}
            folder={setup.folder}
            template={setup.template}
            manual={setup.manual === true}
            persona={persona}
            onClose={onClose}
            onCreated={onCreated}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
