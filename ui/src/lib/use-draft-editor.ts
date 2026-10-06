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
/** A proposed note's title as a file name: no characters a file name or a link cannot hold, no runs of spaces, not empty. */
function fileNameOf(title: string | null | undefined): string {
  const name = (title ?? "").replace(/[\\/:*?"<>|#^[\]]/g, " ").replace(/\s+/g, " ").trim().slice(0, 80)
  return name || "Untitled"
}

export function useDraftEditor({
  handle,
  personaName,
  folder,
  onAccepted,
}: {
  handle: string
  personaName: string
  /** The folder the user is in, where a new note that has no folder yet is made when accepted (none: the vault's top). */
  folder?: () => string | undefined
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
    const proposed = (await fetchChanges(notePath, handle))?.proposals.find((p) => p.kind === "create")
    const text = texts.current.get(`${handle}:${notePath}`) ?? proposed?.text
    if (text === undefined) return notify.error("That draft no longer exists, so no note was created.")
    // A note she proposed lives under a working path (`new/<id>.md`) that is nothing to keep: it is made in the folder the user
    // is in, named by its title, and under another number when that name is taken. A draft that already has a real path keeps it.
    let target = notePath.replace(/\.md$/, "")
    if (notePath.startsWith("new/")) {
      // The folder she was asked to make it in, else the one the user is in.
      const base = [proposed?.folder || folder?.(), fileNameOf(proposed?.name)].filter(Boolean).join("/")
      let made = false
      for (let n = 1; n <= 20 && !made; n++) {
        const candidate = n === 1 ? base : `${base} (${n})`
        const created = await createVaultNote(candidate, handle)
        if (created.ok) {
          target = candidate
          made = true
        } else if (!/already exists/i.test(created.error)) return notify.error(created.error)
      }
      if (!made) return notify.error("A note with that name already exists, and so do the numbered ones. Rename one and try again.")
    } else {
      const created = await createVaultNote(target, handle)
      if (!created.ok) return notify.error(created.error) // a note of that name exists: the draft stays
    }
    const path = `${target}.md`
    const written = await saveVaultNote(path, text, handle)
    if (!written.ok) return notify.error(`The note was created but its text couldn't be saved. Open it and try again. (${written.error})`)
    await forget(notePath)
    notify.success("Draft accepted")
    onAccepted(path)
  }, [notePath, handle, folder, forget, onAccepted])

  const decline = React.useCallback(async () => {
    if (!notePath) return
    await forget(notePath)
    notify.success("Draft declined")
  }, [notePath, forget])

  return { current, path: current ? `draft:${handle}/${current.path}` : undefined, open, close, file, accept, decline }
}
