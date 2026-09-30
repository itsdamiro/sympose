import * as React from "react"

import { fetchChatPhase, sendChatTurn, type ChatPhase } from "@/lib/chat-api"
import type { ChatTurn } from "@/lib/chat-types"

/** How often the status of a reply in flight is asked for. */
const PHASE_POLL_MS = 500

const clock = () => new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })

interface Conversation {
  turns: ChatTurn[]
  draft: string
  sending: boolean
  phase: ChatPhase | null
  sessionId?: string
}

const EMPTY: Conversation = { turns: [], draft: "", sending: false, phase: null }

/**
 * The web chat's own state, kept out of the app shell (ADR 044): the conversation, the draft, whether a reply
 * is in flight and what it is doing. Each persona has its own conversation, so switching persona shows that
 * persona's and a reply that lands after a switch goes to the persona it was for (resuming a persona's saved
 * session after a refresh is its own piece). A message sent while that persona's reply is in flight is not
 * accepted, since the queue cannot be shown yet.
 */
export function useChat(persona: string) {
  const [all, setAll] = React.useState<Record<string, Conversation>>({})
  const inFlight = React.useRef(new Set<string>())
  const nextId = React.useRef(0)
  const convo = all[persona] ?? EMPTY

  const update = React.useCallback((handle: string, change: (c: Conversation) => Conversation) => {
    setAll((prev) => ({ ...prev, [handle]: change(prev[handle] ?? EMPTY) }))
  }, [])

  const addTo = React.useCallback(
    (c: Conversation, turn: Omit<ChatTurn, "id">): Conversation => ({
      ...c,
      turns: [...c.turns, { ...turn, id: `chat-${nextId.current++}` }],
    }),
    []
  )

  const setDraft = React.useCallback(
    (draft: string) => update(persona, (c) => ({ ...c, draft })),
    [persona, update]
  )

  React.useEffect(() => {
    if (!convo.sending) return
    let alive = true
    const id = window.setInterval(() => {
      void fetchChatPhase(persona).then((phase) => {
        if (alive) update(persona, (c) => ({ ...c, phase }))
      })
    }, PHASE_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [convo.sending, persona, update])

  const send = React.useCallback(async () => {
    const message = convo.draft.trim()
    if (!message || inFlight.current.has(persona)) return
    inFlight.current.add(persona)
    update(persona, (c) => ({
      ...addTo(c, { role: "user", body: message, timestamp: clock() }),
      draft: "",
      sending: true,
      phase: null,
    }))
    const result = await sendChatTurn(message, persona, convo.sessionId)
    inFlight.current.delete(persona)
    update(persona, (c) => {
      const done = { ...c, sending: false, phase: null }
      if (!result.ok) {
        return addTo(done, { role: "system", kind: "error", body: `@${persona} couldn't reply: ${result.error}` })
      }
      const { reply, session_id, ttft_ms } = result.reply
      return addTo(
        { ...done, sessionId: session_id },
        {
          role: "persona",
          handle: persona,
          body: reply,
          timestamp: clock(),
          latency: ttft_ms != null ? `${(ttft_ms / 1000).toFixed(2)}s` : undefined,
        }
      )
    })
  }, [convo.draft, convo.sessionId, persona, update, addTo])

  return { turns: convo.turns, draft: convo.draft, setDraft, send, sending: convo.sending, phase: convo.phase }
}
