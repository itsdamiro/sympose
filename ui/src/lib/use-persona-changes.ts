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
  // A read that began while a resolve was in flight, or that one began or ended during, may carry what the server held
  // before the decline: it is dropped, and the read is made again when the resolve is over.
  const resolving = React.useRef(0)
  const resolveEpoch = React.useRef(0)
  const dropped = React.useRef(false)

  React.useEffect(() => {
    if (!path || !enabled) return
    let cancelled = false
    const epoch = resolveEpoch.current
    const inFlight = resolving.current > 0
    void fetchChanges(path, persona).then((data) => {
      if (cancelled) return
      if (inFlight || epoch !== resolveEpoch.current) dropped.current = true
      else setState({ key: `${persona}:${path}`, data })
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
      resolving.current += 1
      resolveEpoch.current += 1
      const result = await (accepted ? resolveChanges(path, persona, which, true) : resolveChanges(path, persona, which))
      resolving.current -= 1
      resolveEpoch.current += 1
      if (dropped.current && resolving.current === 0) {
        dropped.current = false
        setReloadKey((k) => k + 1)
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
