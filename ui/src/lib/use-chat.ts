import * as React from "react"

import {
  fetchChatPhase,
  fetchChatSession,
  sendChatTurn,
  startChatSession,
  type ChatPhase,
  type SessionPage,
} from "@/lib/chat-api"
import type { ChatTurn } from "@/lib/chat-types"

/** How often the status of a reply in flight is asked for. */
const PHASE_POLL_MS = 500

/** How many turns one section of a saved conversation holds. */
const PAGE_TURNS = 20

const time = (date: Date) => date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })

const latency = (ttftMs: number | null | undefined) =>
  ttftMs != null ? `${(ttftMs / 1000).toFixed(2)}s` : undefined

interface Conversation {
  turns: ChatTurn[]
  draft: string
  sending: boolean
  phase: ChatPhase | null
  sessionId?: string
  /** The persona's saved conversation was looked for (found or not); it is asked for once. */
  resumed: boolean
  /** The number of the oldest saved turn shown, and whether older ones exist. */
  oldest: number
  hasMore: boolean
  loadingOlder: boolean
}

const EMPTY: Conversation = {
  turns: [],
  draft: "",
  sending: false,
  phase: null,
  resumed: false,
  oldest: 0,
  hasMore: false,
  loadingOlder: false,
}

/** The saved turns of a page as transcript items: each turn is the user's message and the persona's reply. */
function turnsFromPage(handle: string, page: SessionPage): ChatTurn[] {
  return page.turns.flatMap((saved) => {
    const at = saved.timestamp ? time(new Date(saved.timestamp)) : undefined
    return [
      { id: `saved-${page.session_id}-${saved.index}-user`, role: "user" as const, body: saved.user, timestamp: at },
      {
        id: `saved-${page.session_id}-${saved.index}-reply`,
        role: "persona" as const,
        handle,
        body: saved.assistant,
        timestamp: at,
        latency: latency(saved.ttft_ms),
        sent: saved.sent,
      },
    ]
  })
}

/**
 * The web chat's own state, kept out of the app shell (ADR 044): the conversation, the draft, whether a reply
 * is in flight and what it is doing. Each persona has its own conversation, so switching persona shows that
 * persona's and a reply that lands after a switch goes to the persona it was for. A persona's latest saved
 * conversation is picked up the first time it is shown (a refresh resumes it), the last turns first and
 * older ones on `loadOlder`; `newConversation` starts a fresh one, saved as an empty conversation so a refresh shows it blank. A message sent while that persona's reply
 * is in flight is not accepted, since the queue cannot be shown yet.
 */
export function useChat(persona: string) {
  const [all, setAll] = React.useState<Record<string, Conversation>>({})
  const inFlight = React.useRef(new Set<string>())
  const resuming = React.useRef(new Set<string>())
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

  // Pick up the persona's latest saved conversation, once. If the user has already said something by the
  // time it arrives, it is left out rather than put in front of a conversation that is already going.
  React.useEffect(() => {
    if (resuming.current.has(persona)) return
    resuming.current.add(persona)
    void fetchChatSession(persona, { limit: PAGE_TURNS }).then((page) => {
      update(persona, (c) => {
        if (c.resumed || c.turns.length > 0 || !page || !page.session_id) return { ...c, resumed: true }
        return {
          ...c,
          resumed: true,
          sessionId: page.session_id,
          turns: turnsFromPage(persona, page),
          oldest: page.start,
          hasMore: page.has_more,
        }
      })
    })
  }, [persona, update])

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
      ...addTo(c, { role: "user", body: message, timestamp: time(new Date()) }),
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
      const { reply, session_id, ttft_ms, sent } = result.reply
      return addTo(
        { ...done, sessionId: session_id },
        { role: "persona", handle: persona, body: reply, timestamp: time(new Date()), latency: latency(ttft_ms), sent }
      )
    })
  }, [convo.draft, convo.sessionId, persona, update, addTo])

  const loadOlder = React.useCallback(async () => {
    if (!convo.hasMore || convo.loadingOlder || !convo.sessionId) return
    update(persona, (c) => ({ ...c, loadingOlder: true }))
    const page = await fetchChatSession(persona, {
      sessionId: convo.sessionId,
      before: convo.oldest,
      limit: PAGE_TURNS,
    })
    update(persona, (c) => {
      // A conversation started over while this was loading is not the one these turns belong to.
      if (!page || c.sessionId !== page.session_id) return { ...c, loadingOlder: false }
      return {
        ...c,
        turns: [...turnsFromPage(persona, page), ...c.turns],
        oldest: page.start,
        hasMore: page.has_more,
        loadingOlder: false,
      }
    })
  }, [convo.hasMore, convo.loadingOlder, convo.sessionId, convo.oldest, persona, update])

  const newConversation = React.useCallback(async () => {
    if (inFlight.current.has(persona)) return
    update(persona, () => ({ ...EMPTY, resumed: true })) // blank at once; the backend is told just after
    const sessionId = await startChatSession(persona)
    // If the user has already said something, that conversation is the one now; this one is not used.
    update(persona, (c) => (sessionId && !c.sessionId && c.turns.length === 0 ? { ...c, sessionId } : c))
  }, [persona, update])

  return {
    turns: convo.turns,
    draft: convo.draft,
    setDraft,
    send,
    sending: convo.sending,
    phase: convo.phase,
    hasMore: convo.hasMore,
    loadingOlder: convo.loadingOlder,
    loadOlder,
    newConversation,
  }
}
