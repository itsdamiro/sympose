import * as React from "react"

import {
  cancelChatTurn,
  compactChatSession,
  fetchChatStatus,
  fetchChatSession,
  sendChatTurn,
  startChatSession,
  type ChatPhase,
  type SessionPage,
} from "@/lib/chat-api"
import { takeAttached, type Passage } from "@/lib/attachments"
import { getOpenNote } from "@/lib/open-note-source"
import { announcePersonaActed } from "@/lib/use-persona-changes"
import type { ChatTurn, SystemKind } from "@/lib/chat-types"

/** How often the status of a reply in flight is asked for. */
const PHASE_POLL_MS = 500

/** How many turns one section of a saved conversation holds. */
const PAGE_TURNS = 20

const time = (date: Date) => date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })

const latency = (ttftMs: number | null | undefined) =>
  ttftMs != null ? `${(ttftMs / 1000).toFixed(2)}s` : undefined

interface Conversation {
  persona: string
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
  /** The turns the notes of a compaction stand for in this conversation (ADR 055), and whether notes are being written. */
  condensed: number
  compacting: boolean
  /** A reply landed in it while the user was in another conversation, and it has not been opened since (ADR 057). */
  unread: boolean
}

const blank = (persona: string): Conversation => ({
  persona,
  turns: [],
  draft: "",
  sending: false,
  phase: null,
  indexing: null,
  resumed: false,
  oldest: 0,
  hasMore: false,
  loadingOlder: false,
  condensed: 0,
  compacting: false,
  unread: false,
})

/** A conversation's key in the browser: its persona and a number. The key is not the session's id, which a new
 *  conversation has only once the backend has been told (and which two keys never share). */
const personaOf = (key: string) => key.slice(0, key.lastIndexOf("#"))
const firstKey = (persona: string) => `${persona}#0`

/** The saved turns of a page as transcript items: each turn is the user's message and the persona's reply. */
function turnsFromPage(handle: string, page: SessionPage): ChatTurn[] {
  const notes = page.compaction
  return page.turns.flatMap((saved) => {
    const at = saved.timestamp ? time(new Date(saved.timestamp)) : undefined
    // Where the notes of a compaction (ADR 055) take over from the turns above, so they can be read there.
    const marker: ChatTurn[] =
      notes && saved.index === notes.through
        ? [{ id: `saved-${page.session_id}-notes`, role: "system", kind: "output", title: "Earlier messages are summarised here", body: notes.text }]
        : []
    return [
      ...marker,
      { id: `saved-${page.session_id}-${saved.index}-user`, role: "user" as const, body: saved.user, timestamp: at, attached: saved.sent?.attached },
      {
        id: `saved-${page.session_id}-${saved.index}-reply`,
        role: "persona" as const,
        handle,
        body: saved.assistant,
        timestamp: at,
        model: saved.model ?? undefined,
        latency: latency(saved.ttft_ms),
        sent: saved.sent,
      },
    ]
  })
}

/**
 * The web chat's own state, kept out of the app shell (ADR 044, 057): the conversations, their drafts, whether a
 * reply is in flight and what it is doing. The state is one per conversation, not one per persona: the user can
 * leave a conversation while its reply is being written (a new one, or an older one from the persona's list) and
 * come back to it, and a reply that lands goes to the conversation it was sent from, marked unread when the user is
 * elsewhere. Each persona shows the conversation it was last on; its latest saved one is picked up the first time
 * it is shown (a refresh resumes it), the last turns first and older ones on `loadOlder`. `newConversation`
 * starts a fresh one (saved as an empty conversation so a refresh shows it blank), `openConversation` shows an
 * earlier one. A message sent while that conversation's reply is in flight shows at once and waits; when the reply
 * lands, everything that waited is sent as one turn. A message in another conversation of the same persona goes
 * at once: the backend runs it side by side or after the first, as `parallel_replies` says, and the status line
 * says `queued` while it waits. `stop` stops the active conversation's reply (ADR 054): nothing of it is saved,
 * the message that asked for it goes back into the message box (in front of whatever is typed there), and what
 * waited is still sent.
 */
export function useChat(persona: string) {
  const [all, setAll] = React.useState<Record<string, Conversation>>({})
  const [activeKeys, setActiveKeys] = React.useState<Record<string, string>>({})
  /** Bumped when something the backend lists about the persona's conversations may have changed. */
  const [listVersion, setListVersion] = React.useState(0)
  const allRef = React.useRef(all)
  const activeRef = React.useRef(activeKeys)
  React.useEffect(() => {
    allRef.current = all
    activeRef.current = activeKeys
  })
  /** A note she opened for the user (ADR 072 amendment); `n` makes the same note opened twice two requests. */
  const [shownNote, setShownNote] = React.useState<{ path: string; n: number } | null>(null)
  const inFlight = React.useRef(new Set<string>())
  /** Messages sent while a conversation's reply is in flight; they go out together as one turn when it lands. */
  const waiting = React.useRef(new Map<string, { id: string; text: string; passages: Passage[] }[]>())
  /** The wait of each conversation's reply in flight, which `stop` aborts once the backend accepted the stop. */
  const aborts = React.useRef(new Map<string, AbortController>())
  const resuming = React.useRef(new Set<string>())
  const nextId = React.useRef(0)
  const nextKey = React.useRef(1)
  const activeKey = activeKeys[persona] ?? firstKey(persona)
  const convo = all[activeKey] ?? blank(persona)

  const update = React.useCallback((key: string, change: (c: Conversation) => Conversation) => {
    setAll((prev) => ({ ...prev, [key]: change(prev[key] ?? blank(personaOf(key))) }))
  }, [])

  const newId = React.useCallback(() => `chat-${nextId.current++}`, [])
  const addTo = React.useCallback(
    (c: Conversation, turn: Omit<ChatTurn, "id">, id = newId()): Conversation => ({
      ...c,
      turns: [...c.turns, { ...turn, id }],
    }),
    [newId]
  )

  /** Show the conversation `key` for its persona; opening a conversation clears its unread mark. */
  const show = React.useCallback((handle: string, key: string) => {
    activeRef.current = { ...activeRef.current, [handle]: key }
    setActiveKeys((prev) => ({ ...prev, [handle]: key }))
    setAll((prev) => (prev[key]?.unread ? { ...prev, [key]: { ...prev[key], unread: false } } : prev))
  }, [])

  const keyOfSession = React.useCallback(
    (handle: string, sessionId: string) =>
      Object.keys(allRef.current).find((k) => allRef.current[k].persona === handle && allRef.current[k].sessionId === sessionId),
    []
  )

  const setDraft = React.useCallback(
    (draft: string) => update(activeKey, (c) => ({ ...c, draft })),
    [activeKey, update]
  )

  // Pick up the persona's latest saved conversation, once. If the user has already said something by the
  // time it arrives, it is left out rather than put in front of a conversation that is already going.
  React.useEffect(() => {
    if (resuming.current.has(persona)) return
    resuming.current.add(persona)
    void fetchChatSession(persona, { limit: PAGE_TURNS }).then((page) => {
      update(firstKey(persona), (c) => {
        if (c.resumed || c.turns.length > 0 || !page || !page.session_id) return { ...c, resumed: true }
        return {
          ...c,
          resumed: true,
          sessionId: page.session_id,
          turns: turnsFromPage(persona, page),
          oldest: page.start,
          hasMore: page.has_more,
          condensed: page.compaction?.through ?? 0,
        }
      })
    })
  }, [persona, update])

  React.useEffect(() => {
    if (!convo.sending) return
    let alive = true
    const id = window.setInterval(() => {
      void fetchChatStatus(persona, convo.sessionId).then(({ phase, indexing }) => {
        if (alive) update(activeKey, (c) => ({ ...c, phase, indexing }))
      })
    }, PHASE_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [convo.sending, convo.sessionId, activeKey, persona, update])

  const send = React.useCallback(async () => {
    const message = convo.draft.trim()
    if (!message) return
    const key = activeKey
    const passages = takeAttached() // what the user attached goes with this message and is shown on it
    const shown = { role: "user" as const, body: message, timestamp: time(new Date()), ...(passages.length > 0 ? { attached: passages.length } : {}) }
    const shownId = newId()
    // A message sent while this conversation's reply is in flight shows at once and waits; everything that waited
    // goes out as one turn when the reply lands (ADR 008, 044: amendments of 2026-10-01).
    if (inFlight.current.has(key)) {
      waiting.current.set(key, [...(waiting.current.get(key) ?? []), { id: shownId, text: message, passages }])
      update(key, (c) => ({ ...addTo(c, shown, shownId), draft: "" }))
      return
    }
    inFlight.current.add(key)
    update(key, (c) => ({ ...addTo(c, shown, shownId), draft: "", sending: true, phase: null, indexing: null }))
    let batch = [{ id: shownId, text: message, passages }]
    let sessionId = convo.sessionId
    for (;;) {
      const text = batch.map((b) => b.text).join("\n\n")
      const controller = new AbortController()
      aborts.current.set(key, controller)
      const result = await sendChatTurn(text, persona, sessionId, controller.signal, getOpenNote(), batch.flatMap((b) => b.passages))
      aborts.current.delete(key)
      const next = waiting.current.get(key) ?? []
      waiting.current.delete(key)
      const more = next.length > 0 // decided with no await before `inFlight` is released below
      if (!more) inFlight.current.delete(key)
      if (result.ok) {
        sessionId = result.reply.session_id
        announcePersonaActed() // she may have proposed or commented on the note, or made a draft, during the turn
        // She may have opened a note for the user (ADR 072 amendment): the last one, only from the conversation in view.
        const inView = (activeRef.current[persona] ?? firstKey(persona)) === key
        const shown = (result.reply.sent?.lookups ?? []).filter((l) => l.tool === "show_note" && l.saved && l.path).pop()
        if (shown?.path && inView) setShownNote((c) => ({ path: shown.path!, n: (c?.n ?? 0) + 1 }))
      }
      const asked = new Set(batch.map((b) => b.id)) // read now: `batch` moves on below, before React runs the update
      const elsewhere = activeRef.current[persona] !== undefined ? activeRef.current[persona] !== key : key !== firstKey(persona)
      update(key, (c) => {
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
            { role: "system", kind: "notice", body: "Stopped. No reply was sent." }
          )
        }
        if (!result.ok) {
          return addTo({ ...done, unread: elsewhere || done.unread }, { role: "system", kind: "error", body: `Couldn't get a reply: ${result.error}` })
        }
        const { reply, session_id, ttft_ms, sent, model, context_used, context_limit } = result.reply
        const condensed = result.reply.condensed ?? 0
        const context = model && context_used != null && context_limit != null ? { used: context_used, limit: context_limit, model } : undefined
        const answered = addTo(
          { ...done, sessionId: session_id, context, condensed, unread: elsewhere || done.unread },
          { role: "persona", handle: persona, body: reply, timestamp: time(new Date()), model: model ?? undefined, latency: latency(ttft_ms), sent }
        )
        // The notes of a compaction (ADR 055) are said once, when they first reach a prompt or grow: not on every reply.
        return condensed > c.condensed
          ? addTo(answered, { role: "system", kind: "notice", body: "Earlier messages were summarised to make room." })
          : answered
      })
      setListVersion((v) => v + 1) // its turn count, time and (first reply) title changed
      if (!more) return
      batch = next
    }
  }, [convo.draft, convo.sessionId, activeKey, persona, update, addTo, newId])

  /** Stop the active conversation's reply in flight. The wait is freed only once the backend accepted the stop: a
   *  reply that is already complete is not thrown away, it arrives. */
  const stop = React.useCallback(async () => {
    const controller = aborts.current.get(activeKey)
    if (!controller) return
    if (await cancelChatTurn(persona, convo.sessionId)) controller.abort()
  }, [activeKey, persona, convo.sessionId])

  const loadOlder = React.useCallback(async () => {
    if (!convo.hasMore || convo.loadingOlder || !convo.sessionId) return
    const key = activeKey
    update(key, (c) => ({ ...c, loadingOlder: true }))
    const page = await fetchChatSession(persona, {
      sessionId: convo.sessionId,
      before: convo.oldest,
      limit: PAGE_TURNS,
    })
    update(key, (c) => {
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
  }, [convo.hasMore, convo.loadingOlder, convo.sessionId, convo.oldest, activeKey, persona, update])

  /** Condense the earlier part of this conversation into notes now (ADR 055), and say what happened. The notes
   *  are shown as a line of their own so they can be read; the meter's figure was of the longer conversation,
   *  so it is dropped and the backend's estimate takes its place. */
  const compact = React.useCallback(async () => {
    const sessionId = convo.sessionId
    const key = activeKey
    if (convo.compacting) return
    if (!sessionId) {
      update(key, (c) => addTo(c, { role: "system", kind: "notice", body: "Nothing to condense yet. This chat is too short." }))
      return
    }
    update(key, (c) => ({ ...c, compacting: true }))
    const out = await compactChatSession(persona, sessionId)
    update(key, (c) => {
      const done = { ...c, compacting: false }
      if (c.sessionId !== sessionId) return done // a conversation started over while the notes were being written
      if (!out.ok) return addTo(done, { role: "system", kind: "error", body: `Couldn't condense the conversation: ${out.error}` })
      const { status, covered, text } = out.result
      if (status === "done") {
        const said = addTo(done, { role: "system", kind: "confirmation", body: `Summarised the first ${covered} messages to free up room:` })
        return { ...addTo(said, { role: "system", kind: "output", title: "The notes", body: text }), condensed: covered, context: undefined }
      }
      const reason = {
        nothing: "Nothing to condense yet: the latest messages always stay as they are.",
        too_small: "Nothing to gain: a summary would not be shorter.",
        failed: "The notes could not be written: the model could not be reached or gave nothing.",
        busy: "Already condensing this conversation: try again in a moment.",
      }[status]
      const said = addTo(done, { role: "system", kind: status === "failed" ? "error" : "notice", body: reason })
      return status === "nothing" && text ? addTo(said, { role: "system", kind: "output", title: "The notes now", body: text }) : said
    })
  }, [convo.sessionId, convo.compacting, activeKey, persona, update, addTo])

  /** A fresh conversation, blank at once and shown; the backend is told just after. Its reply, if one is still
   *  being written in the conversation left, lands there. When the user is already on a blank one it does nothing,
   *  and when the backend answers with the blank conversation this browser already holds, that one is shown. */
  const startBlank = React.useCallback(async () => {
    const key = `${persona}#${nextKey.current++}`
    update(key, () => ({ ...blank(persona), resumed: true }))
    show(persona, key)
    const sessionId = await startChatSession(persona)
    if (!sessionId) return
    const held = keyOfSession(persona, sessionId)
    if (held && held !== key && activeRef.current[persona] === key && (allRef.current[key]?.turns.length ?? 0) === 0) {
      setAll((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => k !== key)))
      show(persona, held)
      return
    }
    // If the user has already said something, that conversation is the one now; this one is not used.
    update(key, (c) => (!c.sessionId && c.turns.length === 0 ? { ...c, sessionId } : c))
    setListVersion((v) => v + 1)
  }, [persona, update, show, keyOfSession])

  const newConversation = React.useCallback(async () => {
    if (convo.turns.length === 0 && !convo.sending) return
    await startBlank()
  }, [convo.turns.length, convo.sending, startBlank])

  /** Show the persona's earlier conversation `sessionId`: the one this browser already holds (with its draft,
   *  waiting messages and reply in flight) or, if not held, its saved turns. `false` when it cannot be read. */
  const openConversation = React.useCallback(
    async (sessionId: string): Promise<boolean> => {
      const held = keyOfSession(persona, sessionId)
      if (held) {
        show(persona, held)
        return true
      }
      const page = await fetchChatSession(persona, { sessionId, limit: PAGE_TURNS })
      if (!page || page.session_id !== sessionId) return false
      const meanwhile = keyOfSession(persona, sessionId)
      if (meanwhile) {
        show(persona, meanwhile)
        return true
      }
      const key = `${persona}#${nextKey.current++}`
      update(key, () => ({
        ...blank(persona),
        resumed: true,
        sessionId,
        turns: turnsFromPage(persona, page),
        oldest: page.start,
        hasMore: page.has_more,
        condensed: page.compaction?.through ?? 0,
      }))
      show(persona, key)
      return true
    },
    [persona, show, update, keyOfSession]
  )

  /** The conversation `sessionId` was deleted or must otherwise leave this browser's state. When it is the one
   *  on screen, a fresh one takes its place. */
  const forgetConversation = React.useCallback(
    async (sessionId: string) => {
      const key = keyOfSession(persona, sessionId)
      if (!key) return
      const wasShown = (activeRef.current[persona] ?? firstKey(persona)) === key
      setAll((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => k !== key)))
      if (wasShown) await startBlank()
    },
    [persona, keyOfSession, startBlank]
  )

  /** A system line in the conversation on screen (a confirmation of something the user did outside it). */
  const notice = React.useCallback(
    (kind: SystemKind, body: string) => update(activeKey, (c) => addTo(c, { role: "system", kind, body })),
    [activeKey, update, addTo]
  )

  /** Which of this persona's conversations (by session id) are being replied to or have an unread reply. */
  const marks = React.useMemo(() => {
    const out: Record<string, { replying: boolean; unread: boolean }> = {}
    for (const c of Object.values(all)) {
      if (c.persona === persona && c.sessionId) out[c.sessionId] = { replying: c.sending, unread: c.unread }
    }
    return out
  }, [all, persona])

  return {
    notice,
    sessionId: convo.sessionId,
    context: convo.context,
    turns: convo.turns,
    shownNote,
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
    openConversation,
    forgetConversation,
    marks,
    listVersion,
    compact,
    compacting: convo.compacting,
    condensed: convo.condensed,
  }
}
