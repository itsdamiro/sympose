import * as React from "react"

import { notify } from "@/lib/notify"
import { fetchChanges, resolveChanges, saveDraftText } from "@/lib/persona-changes-api"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { announceDraftsChanged } from "@/lib/use-drafts"
import { createVaultNote, saveVaultNote } from "@/lib/vault-note-api"
import type { PanelFile } from "@/lib/use-note-document"

/**
 * The draft of a new note open in the editor (docs/decisions/071): a note the persona proposed that has no file yet.
 * It is shown through the editor's `file` seam, like a persona's own file, with its text from the proposal. Saving
 * (the button, `⌘/Ctrl-S`, autosave, leaving the draft) keeps the user's edits in the proposal in the persona's folder
 * (never the vault; amended 2026-10-05): the file is made by `accept`, the one deliberate act, and `decline` forgets
 * the proposal. `path` is the key the editor is
 * given, `draft:<handle>/<note path>`, never a vault path.
 */
export function useDraftEditor({
  handle,
  personaName,
  onAccepted,
}: {
  handle: string
  personaName: string
  /** The note was created: its vault path, for the caller to open it and refresh the vault. */
  onAccepted: (path: string) => void
}) {
  const [opened, setOpened] = React.useState<{ handle: string; path: string } | null>(null)
  const current = opened?.handle === handle ? opened : null
  // The text of each draft as the user has it: the proposal's own until the editor saves an edit.
  const texts = React.useRef(new Map<string, string>())

  const open = React.useCallback((path: string) => setOpened({ handle, path }), [handle])
  const close = React.useCallback(() => setOpened(null), [])

  const notePath = current?.path
  const file: Omit<PanelFile, "banner"> | undefined = React.useMemo(
    () =>
      notePath
        ? {
            title: `${personaName} · draft`,
            load: async () => {
              const kept = texts.current.get(`${handle}:${notePath}`)
              if (kept !== undefined) return { content: kept }
              const found = await fetchChanges(notePath, handle)
              const text = found?.proposals.find((p) => p.kind === "create")?.text
              return text === undefined ? null : { content: text }
            },
            save: async (_path, text) => {
              const kept = await saveDraftText(notePath, handle, text) // in her folder, so a reload or a restart keeps it
              if (!kept.ok) return kept
              texts.current.set(`${handle}:${notePath}`, text)
              return { ok: true }
            },
          }
        : undefined,
    [handle, notePath, personaName]
  )

  const forget = React.useCallback(
    async (path: string) => {
      await getUnsavedGuard()?.save() // edits not yet kept would otherwise be flushed to a path that is not a note
      texts.current.delete(`${handle}:${path}`)
      const result = await resolveChanges(path, handle, "all")
      announceDraftsChanged()
      if (!result.ok) notify.error(result.error)
      close()
    },
    [handle, close]
  )

  const accept = React.useCallback(async () => {
    if (!notePath) return
    await getUnsavedGuard()?.save() // what is in the editor right now reaches `texts`
    const text = texts.current.get(`${handle}:${notePath}`) ?? (await fetchChanges(notePath, handle))?.proposals.find((p) => p.kind === "create")?.text
    if (text === undefined) return notify.error("The draft is gone; nothing was created.")
    const created = await createVaultNote(notePath.replace(/\.md$/, ""), handle)
    if (!created.ok) return notify.error(created.error) // a note of that name exists: the draft stays
    const written = await saveVaultNote(notePath, text, handle)
    if (!written.ok) return notify.error(`The note was created but its text was not saved: ${written.error}`)
    await forget(notePath)
    notify.success("Draft accepted")
    onAccepted(notePath)
  }, [notePath, handle, forget, onAccepted])

  const decline = React.useCallback(async () => {
    if (!notePath) return
    await forget(notePath)
    notify.success("Draft declined")
  }, [notePath, forget])

  return { current, path: current ? `draft:${handle}/${current.path}` : undefined, open, close, file, accept, decline }
}
