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
 * The open note's pending changes and comments from the persona (docs/decisions/070): fetched when a note is opened,
 * and again when the window comes back into focus (she may have proposed something in the chat meanwhile) or when
 * `refresh` is called. `resolve` forgets accepted or declined proposals at once on screen and then on the server; if
 * the server cannot, the real state is read back and the reason shown.
 */
export function usePersonaChanges({ path, persona, enabled = true }: { path?: string; persona: string; enabled?: boolean }) {
  const want = path ? `${persona}:${path}` : ""
  const [state, setState] = React.useState<{ key: string; data: NoteChanges | null }>({ key: "", data: null })
  const [reloadKey, setReloadKey] = React.useState(0)
  // A read that lands while a resolve of its note is in flight, or after one has ended since the read began, may carry
  // what the server held before the decline: it is dropped and the note is read again, once the resolve is over.
  const resolves = React.useRef(new Map<string, { active: number; dropped: boolean }>())
  const resolvesEnded = React.useRef(0)

  React.useEffect(() => {
    if (!path || !enabled) return
    let cancelled = false
    const key = `${persona}:${path}`
    const endedBefore = resolvesEnded.current
    void fetchChanges(path, persona).then((data) => {
      if (cancelled) return
      const resolving = resolves.current.get(key)
      if (resolving) resolving.dropped = true // read again when that resolve ends
      else if (resolvesEnded.current !== endedBefore) setReloadKey((k) => k + 1) // one ended while this read was out
      else setState({ key, data })
    })
    return () => {
      cancelled = true
    }
  }, [path, persona, enabled, reloadKey])

  useOnWindowFocus(() => setReloadKey((k) => k + 1))
  React.useEffect(() => {
    const again = () => setReloadKey((k) => k + 1)
    window.addEventListener(ACTED, again)
    return () => window.removeEventListener(ACTED, again)
  }, [])

  // Another note's changes are never shown while this one's are on their way.
  const changes = enabled && state.key === want ? state.data : null

  const resolve = React.useCallback(
    async (which: string[] | "all", accepted = false) => {
      if (!path) return
      setState((s) =>
        s.data && s.key === `${persona}:${path}`
          ? { ...s, data: { ...s.data, proposals: which === "all" ? [] : s.data.proposals.filter((p) => !which.includes(p.id)) } }
          : s
      )
      const key = `${persona}:${path}`
      const resolving = resolves.current.get(key) ?? { active: 0, dropped: false }
      resolving.active += 1
      resolves.current.set(key, resolving)
      let result
      try {
        result = await (accepted ? resolveChanges(path, persona, which, true) : resolveChanges(path, persona, which))
      } finally {
        resolving.active -= 1
        resolvesEnded.current += 1
        if (resolving.active === 0) {
          resolves.current.delete(key)
          if (resolving.dropped) setReloadKey((k) => k + 1)
        }
      }
      announceDraftsChanged() // the note may no longer be a draft
      if (!result.ok) {
        notify.error(result.error)
        setReloadKey((k) => k + 1)
      } else if (accepted) {
        setReloadKey((k) => k + 1) // accepting settles the comments on those words on the server: read them again
      }
    },
    [path, persona]
  )

  const refresh = React.useCallback(() => setReloadKey((k) => k + 1), [])

  return { changes, resolve, refresh }
}
