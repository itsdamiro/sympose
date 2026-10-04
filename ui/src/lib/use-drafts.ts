import * as React from "react"

import { fetchDrafts, type Draft } from "@/lib/persona-changes-api"

const CHANGED = "sympose:drafts-changed"

/** Something that changes what the Drafts section lists happened (a change accepted or declined, a draft created):
 *  every list reads the drafts again. */
export function announceDraftsChanged() {
  window.dispatchEvent(new Event(CHANGED))
}

/**
 * The active persona's drafts for the Drafts section (docs/decisions/071): read when the panel mounts, when the
 * persona changes, when `refreshKey` changes (the vault was refreshed: a note saved, created or deleted), when the
 * window comes back into focus, and when something announces a change. Never polled.
 */
export function useDrafts(persona: string, refreshKey: number) {
  const [state, setState] = React.useState<{ persona: string; drafts: Draft[] }>({ persona, drafts: [] })
  const [again, setAgain] = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    void fetchDrafts(persona).then((drafts) => {
      if (!cancelled) setState({ persona, drafts })
    })
    return () => {
      cancelled = true
    }
  }, [persona, refreshKey, again])

  React.useEffect(() => {
    const read = () => setAgain((n) => n + 1)
    window.addEventListener("focus", read)
    window.addEventListener(CHANGED, read)
    return () => {
      window.removeEventListener("focus", read)
      window.removeEventListener(CHANGED, read)
    }
  }, [])

  // Another persona's drafts are never shown while this one's are on their way.
  return state.persona === persona ? state.drafts : []
}
