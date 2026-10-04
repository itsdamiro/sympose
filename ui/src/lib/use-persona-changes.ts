import * as React from "react"

import { notify } from "@/lib/notify"
import { fetchChanges, resolveChanges, type NoteChanges } from "@/lib/persona-changes-api"

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

  React.useEffect(() => {
    if (!path || !enabled) return
    let cancelled = false
    void fetchChanges(path, persona).then((data) => {
      if (!cancelled) setState({ key: `${persona}:${path}`, data })
    })
    return () => {
      cancelled = true
    }
  }, [path, persona, enabled, reloadKey])

  React.useEffect(() => {
    const again = () => setReloadKey((k) => k + 1)
    window.addEventListener("focus", again)
    return () => window.removeEventListener("focus", again)
  }, [])

  // Another note's changes are never shown while this one's are on their way.
  const changes = enabled && state.key === want ? state.data : null

  const resolve = React.useCallback(
    async (which: string[] | "all") => {
      if (!path) return
      setState((s) =>
        s.data && s.key === `${persona}:${path}`
          ? { ...s, data: { ...s.data, proposals: which === "all" ? [] : s.data.proposals.filter((p) => !which.includes(p.id)) } }
          : s
      )
      const result = await resolveChanges(path, persona, which)
      if (!result.ok) {
        notify.error(result.error)
        setReloadKey((k) => k + 1)
      }
    },
    [path, persona]
  )

  const refresh = React.useCallback(() => setReloadKey((k) => k + 1), [])

  return { changes, resolve, refresh }
}
