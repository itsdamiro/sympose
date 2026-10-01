import * as React from "react"

import {
  cancelChatTurn,
  fetchChatStatus,
  fetchChatSession,
  sendChatTurn,
  startChatSession,
  type ChatPhase,
  type SessionPage,
} from "@/lib/chat-api"
import type { ChatTurn, SystemKind } from "@/lib/chat-types"

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
  /** The search index build in progress while a reply waits (whole percent), else `null`. */
  indexing: number | null
  sessionId?: string
  /** The last reply's token count and the model that made it, for the context meter (ADR 018, 044). */
  context?: { used: number; limit: number; model: string }
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
  indexing: null,
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
 * is in flight shows at once and waits; when the reply lands, everything that waited is sent as one turn.
 * `stop` stops the reply in flight (ADR 054): nothing of it is saved, the message that asked for it goes back
 * into the message box (in front of whatever is typed there), and what waited is still sent.
 */
export function useChat(persona: string) {
  const [all, setAll] = React.useState<Record<string, Conversation>>({})
  const inFlight = React.useRef(new Set<string>())
  /** Messages sent while a persona's reply is in flight; they go out together as one turn when it lands. */
  const waiting = React.useRef(new Map<string, { id: string; text: string }[]>())
  /** The wait of each persona's reply in flight, which `stop` aborts once the backend accepted the stop. */
  const aborts = React.useRef(new Map<string, AbortController>())
  const resuming = React.useRef(new Set<string>())
  const nextId = React.useRef(0)
  const convo = all[persona] ?? EMPTY

  const update = React.useCallback((handle: string, change: (c: Conversation) => Conversation) => {
    setAll((prev) => ({ ...prev, [handle]: change(prev[handle] ?? EMPTY) }))
  }, [])

  const newId = React.useCallback(() => `chat-${nextId.current++}`, [])
  const addTo = React.useCallback(
    (c: Conversation, turn: Omit<ChatTurn, "id">, id = newId()): Conversation => ({
      ...c,
      turns: [...c.turns, { ...turn, id }],
    }),
    [newId]
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
      void fetchChatStatus(persona).then(({ phase, indexing }) => {
        if (alive) update(persona, (c) => ({ ...c, phase, indexing }))
      })
    }, PHASE_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [convo.sending, persona, update])

  const send = React.useCallback(async () => {
    const message = convo.draft.trim()
    if (!message) return
    const shown = { role: "user" as const, body: message, timestamp: time(new Date()) }
    const shownId = newId()
    // A message sent while this persona's reply is in flight shows at once and waits; everything that waited
    // goes out as one turn when the reply lands (ADR 008, 044: amendments of 2026-10-01).
    if (inFlight.current.has(persona)) {
      waiting.current.set(persona, [...(waiting.current.get(persona) ?? []), { id: shownId, text: message }])
      update(persona, (c) => ({ ...addTo(c, shown, shownId), draft: "" }))
      return
    }
    inFlight.current.add(persona)
    update(persona, (c) => ({ ...addTo(c, shown, shownId), draft: "", sending: true, phase: null, indexing: null }))
    let batch = [{ id: shownId, text: message }]
    let sessionId = convo.sessionId
    for (;;) {
      const text = batch.map((b) => b.text).join("\n\n")
      const controller = new AbortController()
      aborts.current.set(persona, controller)
      const result = await sendChatTurn(text, persona, sessionId, controller.signal)
      aborts.current.delete(persona)
      const next = waiting.current.get(persona) ?? []
      waiting.current.delete(persona)
      const more = next.length > 0 // decided with no await before `inFlight` is released below
      if (!more) inFlight.current.delete(persona)
      if (result.ok) sessionId = result.reply.session_id
      const asked = new Set(batch.map((b) => b.id)) // read now: `batch` moves on below, before React runs the update
      update(persona, (c) => {
        const done = { ...c, sending: more, phase: null, indexing: null }
        if (!result.ok && result.cancelled) {
          // Stopped (ADR 054): the message that asked is not part of the conversation, so it leaves the
          // transcript and comes back to the writer, in front of anything typed since.
          return addTo(
            {
              ...done,
              turns: done.turns.filter((t) => !asked.has(t.id)),
              draft: done.draft ? `${text}\n\n${done.draft}` : text,
            },
            { role: "system", kind: "notice", body: `Stopped. @${persona} did not reply.` }
          )
        }
        if (!result.ok) {
          return addTo(done, { role: "system", kind: "error", body: `@${persona} couldn't reply: ${result.error}` })
        }
        const { reply, session_id, ttft_ms, sent, model, context_used, context_limit } = result.reply
        const context = model && context_used != null && context_limit != null ? { used: context_used, limit: context_limit, model } : undefined
        return addTo(
          { ...done, sessionId: session_id, context },
          { role: "persona", handle: persona, body: reply, timestamp: time(new Date()), latency: latency(ttft_ms), sent }
        )
      })
      if (!more) return
      batch = next
    }
  }, [convo.draft, convo.sessionId, persona, update, addTo, newId])

  /** Stop this persona's reply in flight. The wait is freed only once the backend accepted the stop: a reply
   *  that is already complete is not thrown away, it arrives. */
  const stop = React.useCallback(async () => {
    const controller = aborts.current.get(persona)
    if (!controller) return
    if (await cancelChatTurn(persona)) controller.abort()
  }, [persona])

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

  /** A system line in this persona's conversation (a confirmation of something the user did outside it). */
  const notice = React.useCallback(
    (kind: SystemKind, body: string) => update(persona, (c) => addTo(c, { role: "system", kind, body })),
    [persona, update, addTo]
  )

  return {
    notice,
    sessionId: convo.sessionId,
    context: convo.context,
    turns: convo.turns,
    draft: convo.draft,
    setDraft,
    send,
    stop,
    sending: convo.sending,
    phase: convo.phase,
    indexing: convo.indexing,
    hasMore: convo.hasMore,
    loadingOlder: convo.loadingOlder,
    loadOlder,
    newConversation,
  }
}
