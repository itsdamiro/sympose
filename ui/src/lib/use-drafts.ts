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

/** A new note she proposed, still under its working path (`new/…`): it has no file yet, so it is placed by the folder it
 *  was proposed for, not by its path. */
const unplaced = (d: Draft) => d.is_new && d.path.startsWith("new/")

/** The drafts that belong to the folder in view, at any depth (`Notes and Pets/` is not in `Notes/`), as Pinned is
 *  scoped to its root folder. With no folder in view (the vault's own root notes) only the drafts of notes outside
 *  every folder are listed. A new note she proposed is listed where it will be made: the folder it was proposed for (the
 *  persona's Inbox when nobody named one, docs/decisions/094), at any depth like the rest. A new note with no folder
 *  (one that was already waiting before ADR 094) is in every list, or it could not be found at all. */
export function draftsInFolder(drafts: Draft[], folder: string | undefined): Draft[] {
  const prefix = folder === undefined ? undefined : `${folder}/`
  return drafts.filter((d) => {
    if (unplaced(d) && !d.folder) return true
    const where = unplaced(d) ? `${d.folder}/x` : d.path
    return prefix === undefined ? !where.includes("/") : where.startsWith(prefix)
  })
}
