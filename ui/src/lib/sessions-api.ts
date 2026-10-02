import { detailOf } from "@/lib/vault-note-api"

/** One conversation of a persona, as `GET /api/chat/sessions` lists it (ADR 057). */
export interface SessionRow {
  id: string
  /** The name the user gave it, else the start of its first message; empty for one with no message yet. */
  title: string
  turns: number
  created_at: string | null
  updated_at: string | null
  /** When it was pinned (the pinned ones come first, in this order), else `null`. */
  pinned_at: string | null
  /** A reply is being written into it right now (per the backend, so also one started in another window). */
  replying: boolean
}

/** One deleted conversation in the Bin, as `GET /api/chat/sessions/bin` lists it. `id` is its name in the Bin. */
export interface BinnedSession {
  id: string
  title: string
  turns: number
  /** Epoch seconds of the deletion. */
  deleted_at: number
  pinned_at: string | null
}

export type SessionResult<T = undefined> = { ok: true; value: T } | { ok: false; error: string }

const DOWN = "the Sympose backend is not reachable"

async function call<T>(url: string, init: RequestInit | undefined, pick: (body: unknown) => T): Promise<SessionResult<T>> {
  try {
    const res = await fetch(url, init)
    if (res.ok) return { ok: true, value: pick(await res.json()) }
    return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
  } catch (err) {
    return { ok: false, error: `${DOWN} (${err})` }
  }
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
})

const q = encodeURIComponent

/** `GET /api/chat/sessions` — the persona's conversations, the pinned ones first. `null` when it cannot be read. */
export async function fetchSessions(persona: string): Promise<SessionRow[] | null> {
  const out = await call(`/api/chat/sessions?persona=${q(persona)}`, undefined, (b) => (b as { sessions: SessionRow[] }).sessions)
  return out.ok ? out.value : null
}

/** `PATCH /api/chat/session/<id>` — rename and/or pin or unpin; the row comes back. */
export function updateSession(persona: string, id: string, change: { title?: string; pinned?: boolean }) {
  return call(`/api/chat/session/${q(id)}`, json("PATCH", { persona, ...change }), (b) => b as SessionRow)
}

/** `DELETE /api/chat/session/<id>` — to the Bin (nothing is destroyed). 409 while a reply is being written into it. */
export function deleteSession(persona: string, id: string) {
  return call(`/api/chat/session/${q(id)}?persona=${q(persona)}`, { method: "DELETE" }, () => undefined)
}

/** `GET /api/chat/sessions/bin` — the persona's deleted conversations, the last deleted first. `null` when unreadable. */
export async function fetchBinnedSessions(persona: string): Promise<BinnedSession[] | null> {
  const out = await call(`/api/chat/sessions/bin?persona=${q(persona)}`, undefined, (b) => (b as { sessions: BinnedSession[] }).sessions)
  return out.ok ? out.value : null
}

/** `POST /api/chat/sessions/bin/restore` — put a deleted conversation back (409 when one by its id exists). */
export function restoreSession(persona: string, id: string) {
  return call("/api/chat/sessions/bin/restore", json("POST", { persona, id }), () => undefined)
}

/** `DELETE /api/chat/sessions/bin` — delete one conversation from the Bin for good. */
export function purgeSession(persona: string, id: string) {
  return call(`/api/chat/sessions/bin?persona=${q(persona)}&id=${q(id)}`, { method: "DELETE" }, () => undefined)
}

/** `POST /api/chat/sessions/bin/empty` — delete every conversation in the Bin for good; how many there were. */
export function emptyBinnedSessions(persona: string) {
  return call("/api/chat/sessions/bin/empty", json("POST", { persona }), (b) => (b as { deleted: number }).deleted)
}
