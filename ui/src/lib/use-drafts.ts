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

/** A new note she proposed, still under its working path (`new/…`): it belongs to no folder yet. */
const unplaced = (d: Draft) => d.is_new && d.path.startsWith("new/")

/** The drafts that belong to the folder in view, at any depth (`Notes and Pets/` is not in `Notes/`), as Pinned is
 *  scoped to its root folder. With no folder in view (the vault's own root notes) only the drafts of notes outside
 *  every folder are listed. A new note she proposed is in every list. */
export function draftsInFolder(drafts: Draft[], folder: string | undefined): Draft[] {
  // A new note a persona proposed has no folder yet (it is kept under a working path until it is accepted): it is listed
  // wherever the user is, or it could not be found at all.
  if (folder === undefined) return drafts.filter((d) => unplaced(d) || !d.path.includes("/"))
  const prefix = `${folder}/`
  return drafts.filter((d) => unplaced(d) || d.path.startsWith(prefix))
}
