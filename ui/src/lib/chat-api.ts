import type { SentRecord } from "@/lib/chat-types"
import { detailOf } from "@/lib/vault-note-api"

/** What the persona's reply in flight is doing right now (the engine's own phases, ADR 043). */
export type ChatPhase = "searching" | "reading" | "asking"

/** The parts of `POST /api/chat/turn`'s answer the web chat uses. */
export interface ChatReply {
  reply: string
  session_id: string
  model: string | null
  ttft_ms: number | null
  truncated: boolean
  saved: boolean
  /** Categories of the vault that went to a non-local model, and those held back (ADR 031). */
  cloud: string[]
  withheld: string[]
  /** What reached the model besides the messages; the grounded view reads its notes. */
  sent: SentRecord | null
  /** The conversation's tokens and the prompt budget they were counted against, for the context meter (ADR
   *  018); `null` when the model's window is unknown. */
  context_used: number | null
  context_limit: number | null
  /** The turns the notes of a compaction stood for in this reply's prompt (ADR 055); 0 when there were none. */
  condensed?: number
}

const BACKEND_DOWN = "the Sympose backend is not reachable. Is it running (`sympose web`, or `python -m sympose.main` beside `npm run dev`)?"

export type SendChatTurnResult =
  | { ok: true; reply: ChatReply }
  | { ok: false; error: string; cancelled?: false }
  /** The reply was stopped (ADR 054): nothing was saved. */
  | { ok: false; cancelled: true; error?: undefined }

/**
 * Client for `POST /api/chat/turn` — one message to a persona, answered whole. `sessionId` continues a
 * conversation; omitted, a new one starts and its id comes back. Returns a discriminated result rather than
 * throwing so the chat can show the reason as a system line (a model that is not running, a cloud model the
 * web chat does not use yet). A reply that was stopped (`cancelChatTurn`, or `signal` aborted once the stop
 * was accepted) comes back as `{ ok: false, cancelled: true }`.
 */
export async function sendChatTurn(
  message: string,
  persona: string,
  sessionId?: string,
  signal?: AbortSignal
): Promise<SendChatTurnResult> {
  try {
    const res = await fetch("/api/chat/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, persona, session_id: sessionId }),
      signal,
    })
    if (res.ok) {
      const body = (await res.json()) as ChatReply & { cancelled?: boolean }
      return body.cancelled ? { ok: false, cancelled: true } : { ok: true, reply: body }
    }
    const detail = await detailOf(res)
    if (detail) return { ok: false, error: detail }
    // A gateway error with no reason of ours in it is the dev server's proxy saying nothing is behind it.
    if ([502, 503, 504].includes(res.status)) return { ok: false, error: BACKEND_DOWN }
    return { ok: false, error: `HTTP ${res.status}` }
  } catch (err) {
    if (signal?.aborted) return { ok: false, cancelled: true }
    return { ok: false, error: `${BACKEND_DOWN} (${err})` }
  }
}

/**
 * Client for `POST /api/chat/cancel` (ADR 054): ask the engine to stop the persona's reply in flight. `true`
 * means the stop was accepted and nothing of that turn will be saved; `false` means there was nothing to stop
 * (no reply running, or it is already complete and will arrive), or the backend could not be reached.
 */
export async function cancelChatTurn(persona: string): Promise<boolean> {
  try {
    const res = await fetch("/api/chat/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona }),
    })
    return res.ok && ((await res.json()) as { stopping?: boolean }).stopping === true
  } catch {
    return false
  }
}

/** What the reply in flight is doing, and the search index build still running (whole percent) or `null`. */
export interface ChatStatus {
  phase: ChatPhase | null
  indexing: number | null
}

/** Client for `GET /api/chat/status` — the phase of the persona's reply in flight and any index build. */
export async function fetchChatStatus(persona: string): Promise<ChatStatus> {
  const none = { phase: null, indexing: null }
  try {
    const res = await fetch(`/api/chat/status?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) return none
    const body = (await res.json()) as Partial<ChatStatus>
    return { phase: body.phase ?? null, indexing: typeof body.indexing === "number" ? body.indexing : null }
  } catch {
    return none
  }
}

/**
 * Client for `GET /api/chat/context` — the context meter's estimate for a conversation on the persona's current
 * model (docs/decisions/044): its tokens in use and the prompt budget, worked out without a model call, or `null`
 * when there is nothing to count (no reply yet, the model's window unknown) or the backend cannot say.
 */
export async function fetchContextEstimate(
  persona: string,
  sessionId: string
): Promise<{ used: number; limit: number } | null> {
  try {
    const res = await fetch(
      `/api/chat/context?persona=${encodeURIComponent(persona)}&session_id=${encodeURIComponent(sessionId)}`
    )
    if (!res.ok) return null
    const body = (await res.json()) as { used: number | null; limit: number | null }
    return body.used != null && body.limit != null ? { used: body.used, limit: body.limit } : null
  } catch {
    return null
  }
}

/** One saved turn of a conversation, as `GET /api/chat/session` returns it. */
export interface SessionTurn {
  /** The turn's number in the whole conversation, from 0. */
  index: number
  user: string
  assistant: string
  timestamp: string | null
  model: string | null
  ttft_ms: number | null
  truncated: boolean
  /** What reached the model besides the messages (ADR 025); the grounded view reads it. */
  sent: SentRecord | null
}

export interface SessionPage {
  /** `null` when the persona has no conversation yet. */
  session_id: string | null
  /** The notes that stand for the first `through` turns of the conversation (ADR 055), or `null`. */
  compaction?: { through: number; text: string } | null
  turns: SessionTurn[]
  /** The number of the first turn on this page, and how many turns the conversation has in all. */
  start: number
  total: number
  has_more: boolean
}

/**
 * Client for `GET /api/chat/session` — one section of a persona's conversation: the latest turns, or the
 * turns before number `before` in the conversation `sessionId` (given so older pages stay in the one the
 * first page came from). `null` when the backend cannot be reached or refuses, so the chat starts empty
 * instead of failing.
 */
export async function fetchChatSession(
  persona: string,
  options: { sessionId?: string; before?: number; limit?: number } = {}
): Promise<SessionPage | null> {
  const params = new URLSearchParams({ persona })
  if (options.sessionId) params.set("session_id", options.sessionId)
  if (options.before !== undefined) params.set("before", String(options.before))
  if (options.limit !== undefined) params.set("limit", String(options.limit))
  try {
    const res = await fetch(`/api/chat/session?${params}`)
    if (!res.ok) return null
    return (await res.json()) as SessionPage
  } catch {
    return null
  }
}

/**
 * Client for `POST /api/chat/session` — start a fresh, empty conversation with a persona and get its id, so a
 * refresh before the first message shows it blank instead of bringing the previous one back. `null` when the
 * backend cannot be reached or refuses; the chat is then blank in the browser only.
 */
export async function startChatSession(persona: string): Promise<string | null> {
  try {
    const res = await fetch("/api/chat/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona }),
    })
    if (!res.ok) return null
    return ((await res.json()) as { session_id: string }).session_id
  } catch {
    return null
  }
}

/** What happened when the earlier part of a conversation was condensed into notes (ADR 055). */
export type CompactStatus = "done" | "nothing" | "too_small" | "failed" | "busy"

export interface CompactResult {
  status: CompactStatus
  /** The turns the notes now stand for. */
  covered: number
  /** The notes in force afterwards (the new ones on `done`), or an empty string when there are none. */
  text: string
  /** Tokens the notes replaced and tokens the notes take, on `done`. */
  before: number
  after: number
}

/**
 * Client for `POST /api/chat/compact` — condense the earlier part of a conversation into notes now, with the
 * persona's model, and wait for it (ADR 055). A model that could not write the notes is `status: "failed"`, not
 * an error; `ok: false` is for the backend refusing (no such conversation) or not being reachable.
 */
export async function compactChatSession(
  persona: string,
  sessionId: string
): Promise<{ ok: true; result: CompactResult } | { ok: false; error: string }> {
  try {
    const res = await fetch("/api/chat/compact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, session_id: sessionId }),
    })
    if (res.ok) return { ok: true, result: (await res.json()) as CompactResult }
    const detail = await detailOf(res)
    if (detail) return { ok: false, error: detail }
    if ([502, 503, 504].includes(res.status)) return { ok: false, error: BACKEND_DOWN }
    return { ok: false, error: `HTTP ${res.status}` }
  } catch (err) {
    return { ok: false, error: `${BACKEND_DOWN} (${err})` }
  }
}
