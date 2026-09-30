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
}

const BACKEND_DOWN = "the Sympose backend is not reachable. Is it running (`sympose web`, or `python -m sympose.main` beside `npm run dev`)?"

export type SendChatTurnResult =
  | { ok: true; reply: ChatReply }
  | { ok: false; error: string }

/**
 * Client for `POST /api/chat/turn` — one message to a persona, answered whole. `sessionId` continues a
 * conversation; omitted, a new one starts and its id comes back. Returns a discriminated result rather than
 * throwing so the chat can show the reason as a system line (a model that is not running, a cloud model the
 * web chat does not use yet).
 */
export async function sendChatTurn(
  message: string,
  persona: string,
  sessionId?: string
): Promise<SendChatTurnResult> {
  try {
    const res = await fetch("/api/chat/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, persona, session_id: sessionId }),
    })
    if (res.ok) return { ok: true, reply: (await res.json()) as ChatReply }
    const detail = await detailOf(res)
    if (detail) return { ok: false, error: detail }
    // A gateway error with no reason of ours in it is the dev server's proxy saying nothing is behind it.
    if ([502, 503, 504].includes(res.status)) return { ok: false, error: BACKEND_DOWN }
    return { ok: false, error: `HTTP ${res.status}` }
  } catch (err) {
    return { ok: false, error: `${BACKEND_DOWN} (${err})` }
  }
}

/** Client for `GET /api/chat/status` — the phase of the persona's reply in flight, or `null`. */
export async function fetchChatPhase(persona: string): Promise<ChatPhase | null> {
  try {
    const res = await fetch(`/api/chat/status?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) return null
    return ((await res.json()) as { phase: ChatPhase | null }).phase
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
