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
import { IconPicker } from "@/components/sympose/icon-picker"
import { saveFolderSettings, type FolderSettings } from "@/lib/folder-settings-api"
import { notify } from "@/lib/notify"
import { folderIconFor } from "@/lib/vault-folders"

const FIELD =
  "block w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-brand disabled:opacity-60"

function SettingsForm({
  folder,
  start,
  manual,
  persona,
  onClose,
  onSaved,
}: {
  folder: string
  start: FolderSettings
  /** Opened from "Folder settings" on a folder that already exists, not as the step after creating one. */
  manual: boolean
  persona: string
  onClose: () => void
  onSaved: () => void
}) {
  const [purpose, setPurpose] = React.useState(start.purpose)
  const [template, setTemplate] = React.useState(start.template.join("\n"))
  const [icon, setIcon] = React.useState(start.icon)
  const [colors, setColors] = React.useState({ accent: start.accent, accentDark: start.accentDark })
  const [busy, setBusy] = React.useState(false)

  // A folder with a definition is saved when something changed; one without, when there is anything to write.
  const changed =
    purpose.trim() !== start.purpose.trim() ||
    template !== start.template.join("\n") ||
    icon !== start.icon ||
    colors.accent !== start.accent ||
    colors.accentDark !== start.accentDark
  const somethingToWrite =
    purpose.trim() !== "" || template.trim() !== "" || icon !== null || colors.accent !== null || colors.accentDark !== null

  // The button is disabled while there is nothing to save; this only stops a second click while the first is in
  // flight.
  const save = async () => {
    if (busy) return
    setBusy(true)
    const res = await saveFolderSettings(
      folder,
      { purpose: purpose.trim(), template: template.split("\n"), icon, ...colors },
      persona
    )
    setBusy(false)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    onSaved()
    onClose()
    notify.success(
      res.created ? `Created the folder description for ${folder}` : `Saved the settings for ${folder}`
    )
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{manual ? `Settings for ${folder}` : `Set up ${folder}`}</DialogTitle>
        <DialogDescription>
          {manual ? "Choose" : "Optional. Choose"} how this folder looks, what it is for and which properties its notes
          start with; all of it is saved in {folder}/{folder}.md.{" "}
          {manual ? "Cancel" : "Skip"} writes nothing.
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-4">
        <div className="grid gap-1.5 text-sm">
          <span className="font-medium">Icon</span>
          <IconPicker
            label="Icon"
            value={icon}
            fallback={folderIconFor(folder)}
            onChange={setIcon}
            disabled={busy}
          />
        </div>
        <div className="grid gap-1.5 text-sm">
          <span className="font-medium">Colour</span>
          <FolderColorField {...colors} onChange={setColors} disabled={busy} />
        </div>
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">What is this folder for?</span>
          <textarea
            rows={2}
            value={purpose}
            disabled={busy}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="A sentence or two about what goes in this folder"
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
            placeholder="Fields each note should have, one per line"
            spellCheck={false}
            className={`${FIELD} font-mono text-xs`}
          />
          <span className="text-xs text-muted-foreground">
            {start.templateSource === "vault"
              ? "Started from your Templates/Note template.md. "
              : start.templateSource === "settings"
                ? "Started from the default keys. "
                : ""}
            {"{{title}}"} and {"{{date}}"} are filled in when a note is created.
          </span>
        </label>
      </div>
      <DialogFooter>
        <DialogClose render={<Button variant="outline" disabled={busy} />}>
          {manual ? "Cancel" : "Skip"}
        </DialogClose>
        <Button
          disabled={busy || (start.defined ? !changed : !somethingToWrite)}
          onClick={() => void save()}
        >
          {start.defined || manual ? "Save" : "Create the description"}
        </Button>
      </DialogFooter>
    </>
  )
}

/**
 * The Folder settings dialog (docs/decisions/087), opened from a top-level folder's right-click menu and, as a
 * skippable step, after a root folder is created (docs/decisions/038): the folder's icon and colour, what it is
 * for, and the properties its notes start with. It opens filled from the folder's definition note when it has one
 * (`setup.settings`, already fetched; the app shell only sets it for a folder the server says it can edit).
 * Closing it, or Skip, writes nothing; only what the user set is written, and only on Save.
 */
export function FolderSettingsDialog({
  setup,
  persona,
  onClose,
  onSaved,
}: {
  setup: { folder: string; settings: FolderSettings; manual?: boolean } | null
  persona: string
  onClose: () => void
  /** Called after the definition note was written, so the tree can refresh. */
  onSaved: () => void
}) {
  return (
    <Dialog open={setup !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {setup !== null && (
          <SettingsForm
            key={setup.folder}
            folder={setup.folder}
            start={setup.settings}
            manual={setup.manual === true}
            persona={persona}
            onClose={onClose}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
