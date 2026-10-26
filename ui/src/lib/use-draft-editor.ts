import * as React from "react"

import { notify } from "@/lib/notify"
import { acceptDraft, fetchChanges, resolveChanges, saveDraftText } from "@/lib/persona-changes-api"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { announceDraftsChanged } from "@/lib/use-drafts"
import { useOnWindowFocus } from "@/lib/use-on-window-focus"
import type { PanelFile } from "@/lib/use-note-document"

/**
 * The draft of a new note open in the editor (docs/decisions/071): a note the persona proposed that has no file yet.
 * It is shown through the editor's `file` seam, like a persona's own file, with its text from the proposal. Saving
 * (the button, `⌘/Ctrl-S`, autosave, leaving the draft) keeps the user's edits in the proposal in the persona's folder
 * (never the vault; amended 2026-10-05): the file is made by `accept`, the one deliberate act (the server makes it, as for
 * Slack's Accept, docs/decisions/093), and `decline` forgets the proposal. `path` is the key the editor is
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

  // The drafts whose text has been typed in once this page: a draft opened again is shown at once, as is one the user has edited.
  const revealed = React.useRef(new Set<string>())

  const open = React.useCallback((path: string) => setOpened({ handle, path }), [handle])
  const close = React.useCallback(() => setOpened(null), [])

  const notePath = current?.path
  const file: Omit<PanelFile, "banner"> | undefined = React.useMemo(
    () =>
      notePath
        ? {
            title: `${personaName} · draft`,
            properties: true, // a note's draft opens with its properties card, as the note will
            reveal: () => {
              const key = `${handle}:${notePath}`
              if (revealed.current.has(key) || texts.current.has(key)) return false
              revealed.current.add(key)
              return true
            },
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
    // What is in the editor right now reaches the draft the server holds; if it cannot be kept, the note is not made from older words.
    if ((await getUnsavedGuard()?.save()) === false) return notify.error("Your latest words could not be kept, so the note was not made. Try again.")
    const made = await acceptDraft(notePath, handle)
    if (!made.ok) return notify.error(made.error)
    texts.current.delete(`${handle}:${notePath}`)
    announceDraftsChanged()
    close()
    notify.success("Draft accepted")
    onAccepted(made.path)
  }, [notePath, handle, close, onAccepted])

  // A new-note draft decided in another program (Slack's Accept or Decline, docs/decisions/093) is not waiting any more: when the
  // window comes back into focus the editor asks, and closes if the draft is gone (the notes list reads again on focus, so an accepted
  // note is there). Never polled, no notice.
  const shown = `${handle}:${notePath}`
  const looking = React.useRef(shown)
  React.useEffect(() => {
    looking.current = shown
  })
  useOnWindowFocus(() => {
    if (!notePath?.startsWith("new/")) return
    void fetchChanges(notePath, handle).then((found) => {
      if (looking.current !== shown || !found || found.proposals.some((p) => p.kind === "create")) return // another draft is open now, or this one still waits
      close()
      announceDraftsChanged()
    })
  })

  const decline = React.useCallback(async () => {
    if (!notePath) return
    await forget(notePath)
    notify.success("Draft declined")
  }, [notePath, forget])

  return { current, path: current ? `draft:${handle}/${current.path}` : undefined, open, close, file, accept, decline }
}
