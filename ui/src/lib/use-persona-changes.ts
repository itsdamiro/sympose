import * as React from "react"

import { notify } from "@/lib/notify"
import { fetchChanges, resolveChanges, type NoteChanges } from "@/lib/persona-changes-api"
import { announceDraftsChanged } from "@/lib/use-drafts"
import { useOnWindowFocus } from "@/lib/use-on-window-focus"

const ACTED = "sympose:persona-acted"

/** A chat turn ended: she may have proposed a change, left a comment or made a draft, so the open note's changes and
 *  the Drafts list are read again. */
export function announcePersonaActed() {
  window.dispatchEvent(new Event(ACTED))
  announceDraftsChanged()
}

/**
 * A decline answers the server after a read of the same note may have begun, and that read can land after it carrying
 * what the server held before. So a read that lands while a resolve of its note is in flight, or after one has ended
 * since the read began, is not shown: the note is read again (by `reload`) once the resolve is over.
 */
function useResolveGuard(reload: () => void) {
  const notes = React.useRef(new Map<string, { active: number; dropped: boolean }>())
  const ended = React.useRef(0)
  return React.useMemo(
    () => ({
      /** A resolve of `key` begins; call the result when it ends, however it ends. */
      begin(key: string) {
        const note = notes.current.get(key) ?? { active: 0, dropped: false }
        note.active += 1
        notes.current.set(key, note)
        return () => {
          note.active -= 1
          ended.current += 1
          if (note.active > 0) return
          notes.current.delete(key)
          if (note.dropped) reload()
        }
      },
      /** A read of `key` begins; call the result when it lands: true if its answer may be shown. */
      watch(key: string) {
        const before = ended.current
        return () => {
          const note = notes.current.get(key)
          if (note) {
            note.dropped = true
            return false
          }
          if (ended.current !== before) {
            reload()
            return false
          }
          return true
        }
      },
    }),
    [reload]
  )
}

/**
 * The open note's pending changes and comments from the persona (docs/decisions/070): fetched when a note is opened,
 * and again when the window comes back into focus (she may have proposed something in the chat meanwhile) or when
 * `refresh` is called. `resolve` forgets accepted or declined proposals at once on screen and then on the server; if
 * the server cannot, the real state is read back and the reason shown.
 */
export function usePersonaChanges({ path, persona, enabled = true }: { path?: string; persona: string; enabled?: boolean }) {
  const want = path ? `${persona}:${path}` : ""
  const [state, setState] = React.useState<{ key: string; data: NoteChanges | null }>({ key: "", data: null })
  const [reloadKey, setReloadKey] = React.useState(0)
  const refresh = React.useCallback(() => setReloadKey((k) => k + 1), [])
  const guard = useResolveGuard(refresh)

  React.useEffect(() => {
    if (!path || !enabled) return
    let cancelled = false
    const landed = guard.watch(want)
    void fetchChanges(path, persona).then((data) => {
      if (!cancelled && landed()) setState({ key: want, data })
    })
    return () => {
      cancelled = true
    }
  }, [path, persona, want, enabled, reloadKey, guard])

  useOnWindowFocus(refresh)
  React.useEffect(() => {
    window.addEventListener(ACTED, refresh)
    return () => window.removeEventListener(ACTED, refresh)
  }, [refresh])

  // Another note's changes are never shown while this one's are on their way.
  const changes = enabled && state.key === want ? state.data : null

  const resolve = React.useCallback(
    async (which: string[] | "all", accepted = false) => {
      if (!path) return
      setState((s) =>
        s.data && s.key === want
          ? { ...s, data: { ...s.data, proposals: which === "all" ? [] : s.data.proposals.filter((p) => !which.includes(p.id)) } }
          : s
      )
      const end = guard.begin(want)
      let result
      try {
        result = await (accepted ? resolveChanges(path, persona, which, true) : resolveChanges(path, persona, which))
      } finally {
        end()
      }
      announceDraftsChanged() // the note may no longer be a draft
      if (!result.ok) {
        notify.error(result.error)
        refresh()
      } else if (accepted) {
        refresh() // accepting settles the comments on those words on the server: read them again
      }
    },
    [path, persona, want, guard, refresh]
  )

  return { changes, resolve, refresh }
}
