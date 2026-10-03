import * as React from "react"

import { fetchRelated, NO_RELATED, type RelatedState } from "@/lib/vault-related-api"

/** While the server says the vault's first index is still being built, ask again this often. */
const INDEXING_RETRY_MS = 5000

/**
 * The notes close in meaning to the open note (docs/decisions/066), for the notes panel's footer. Asked again each
 * time the open note or the persona changes, and every few seconds while the server says the first index is still
 * being built (an empty list then fills in by itself). An answer for a note that is no longer open is dropped, and
 * until the answer for this note arrives the list is empty, never the last note's neighbours under the new note's name.
 */
export function useRelatedNotes(path: string | undefined, persona: string): RelatedState {
  const [answer, setAnswer] = React.useState<{ key: string; state: RelatedState } | null>(null)
  const [round, setRound] = React.useState(0)
  const key = path ? `${persona}\0${path}` : ""

  React.useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    let retry: ReturnType<typeof setTimeout> | undefined
    fetchRelated(path, persona, controller.signal).then((state) => {
      if (controller.signal.aborted) return
      setAnswer({ key, state })
      if (state.indexing) retry = setTimeout(() => setRound((n) => n + 1), INDEXING_RETRY_MS)
    })
    return () => {
      controller.abort()
      clearTimeout(retry)
    }
  }, [path, persona, key, round])

  return answer && answer.key === key ? answer.state : NO_RELATED
}
