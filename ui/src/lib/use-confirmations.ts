import * as React from "react"

import {
  answerConfirmation,
  fetchConfirmations,
  type ConfirmationRequest,
} from "@/lib/confirmations-api"
import type { ChatTurn } from "@/lib/chat-types"

/** The ids of the requests a conversation's replies refer to (a reply's record lists the `propose_persona` call that filed one). */
export function requestIdsOf(turns: ChatTurn[]): string[] {
  return turns.flatMap((t) => (t.sent?.lookups ?? []).flatMap((l) => (l.tool === "propose_persona" && l.request ? [l.request] : [])))
}

/**
 * The requests behind the cards of the conversation on screen (docs/decisions/078), loaded when the replies refer to a
 * new one, and the answer to one. `onAccepted` runs after the backend has made the persona, so the roster can be read again.
 */
export function useConfirmations(persona: string, sessionId: string | undefined, turns: ChatTurn[], onAccepted?: () => void) {
  const [byId, setById] = React.useState<Record<string, ConfirmationRequest>>({})
  const ids = requestIdsOf(turns)
  const key = ids.join(",")
  React.useEffect(() => {
    if (!sessionId || !key) return // the cards read only the requests the replies refer to, so an old map is never shown
    let alive = true
    fetchConfirmations(persona, sessionId).then((list) => {
      if (alive) setById(Object.fromEntries(list.map((r) => [r.id, r])))
    })
    return () => {
      alive = false
    }
  }, [persona, sessionId, key])

  const answer = React.useCallback(
    async (id: string, accept: boolean, folders: string[] | null, editMode: string | null = null): Promise<string | null> => {
      const result = await answerConfirmation(persona, id, accept, folders, editMode)
      if (!result.ok) return result.error
      setById((prev) => ({ ...prev, [id]: result.request }))
      if (accept && result.request.state === "accepted") onAccepted?.()
      return null
    },
    [persona, onAccepted]
  )
  return { byId, answer }
}
