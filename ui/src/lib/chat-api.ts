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
}

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
    return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
  } catch (err) {
    return { ok: false, error: `backend unreachable (${err})` }
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
