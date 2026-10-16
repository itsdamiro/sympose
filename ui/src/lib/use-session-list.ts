import * as React from "react"

import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { announceDraftsChanged } from "@/lib/use-drafts"
import { archiveSession, deleteSession, fetchSessions, updateSession, type SessionRow } from "@/lib/sessions-api"

/** What the chat gives the list: the conversation on screen, what each held conversation is doing, and the means to
 *  open one, start one and drop one (`useChat`). */
interface ChatForList {
  sessionId: string | undefined
  marks: Record<string, { replying: boolean; unread: boolean }>
  listVersion: number
  openConversation: (sessionId: string) => Promise<boolean>
  newConversation: () => Promise<void>
  forgetConversation: (sessionId: string) => Promise<void>
}

export interface ListedSession extends SessionRow {
  unread: boolean
  current: boolean
}

/**
 * The persona's list of conversations (ADR 057): what the backend lists, with what this browser knows added
 * (which one is on screen, which is being replied to, which has a reply nobody has read). Rename, pin and delete go
 * to the backend and the list takes the row it answers with; a delete moves the conversation to the Bin, so it asks
 * first as any delete does, and `binVersion` is bumped for the Bin to list it. It is read again whenever the chat says
 * something it shows changed.
 */
export function useSessionList(persona: string, chat: ChatForList) {
  const [loaded, setLoaded] = React.useState<{ persona: string; rows: SessionRow[] } | null>(null)
  const rows = loaded?.persona === persona ? loaded.rows : null // another persona's list is not this one's while it loads
  const [binVersion, setBinVersion] = React.useState(0)
  const { openConversation, newConversation, forgetConversation, listVersion } = chat

  // Only the answer to the newest read is kept: a slower, earlier one (the persona before, or the list as it was a
  // moment ago) arriving last would put its rows back.
  const newest = React.useRef(0)
  const refresh = React.useCallback(async () => {
    const mine = ++newest.current
    const next = await fetchSessions(persona)
    if (next && mine === newest.current) setLoaded({ persona, rows: next })
  }, [persona])

  React.useEffect(() => {
    void refresh()
  }, [refresh, listVersion])

  const sessions: ListedSession[] = React.useMemo(
    () =>
      (rows ?? []).map((row) => ({
        ...row,
        replying: row.replying || (chat.marks[row.id]?.replying ?? false),
        unread: chat.marks[row.id]?.unread ?? false,
        current: row.id === chat.sessionId,
      })),
    [rows, chat.marks, chat.sessionId]
  )

  const change = React.useCallback(
    async (id: string, what: { title?: string; pinned?: boolean }) => {
      const out = await updateSession(persona, id, what)
      if (!out.ok) {
        notify.error(out.error)
        return false
      }
      await refresh()
      return true
    },
    [persona, refresh]
  )

  const remove = React.useCallback(
    (row: SessionRow) =>
      confirm({
        message: `Move “${row.title || "this conversation"}” to the bin?`,
        description: "You can restore it from the bin later. Until then the persona won't remember it.",
        confirmLabel: "Move to bin",
        onConfirm: async () => {
          const out = await deleteSession(persona, row.id)
          if (!out.ok) {
            notify.error(out.error)
            return
          }
          await forgetConversation(row.id)
          setBinVersion((v) => v + 1)
          await refresh()
          notify.success("Moved the conversation to the bin")
        },
      }),
    [persona, forgetConversation, refresh]
  )

  // A conversation being written up: its menu item does nothing a second time while the first call is out.
  const archiving = React.useRef(new Set<string>())
  const archive = React.useCallback(
    async (row: SessionRow) => {
      if (archiving.current.has(row.id)) return
      archiving.current.add(row.id)
      // One toast for the whole call: it stays up while the model writes (a local one takes many seconds), and the
      // result takes its place.
      const id = `archive-${row.id}`
      const result = { id, duration: undefined } // the result replaces the toast and times out like any other
      notify.info("Writing the note…", { id, duration: Infinity })
      const out = await archiveSession(persona, row.id)
      archiving.current.delete(row.id)
      if (!out.ok) {
        notify.error(out.error, result)
        return
      }
      announceDraftsChanged()
      notify.success(`“${out.value}” is waiting in Drafts`, result)
    },
    [persona]
  )

  const open = React.useCallback(
    async (id: string) => {
      if (!(await openConversation(id))) notify.error("Couldn't open that conversation")
    },
    [openConversation]
  )

  return {
    sessions,
    loaded: rows !== null,
    binVersion,
    refresh,
    open,
    startNew: newConversation,
    rename: (id: string, title: string) => change(id, { title }),
    pin: (id: string, pinned: boolean) => change(id, { pinned }),
    archive,
    remove,
  }
}
