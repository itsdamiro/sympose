/**
 * Client for `GET /api/chat/status-phrases` (docs/decisions/044, 043): the persona's own witty busy-line
 * phrases, or the generic ones while it has none. The first read for a persona with none also starts their
 * one-time generation on the backend. `null` when the backend cannot say: the line then rotates through the
 * generic phrases only.
 */
export interface StatusPhrases {
  phrases: string[]
  /** The persona has its own; `false` while it only has the generic ones (its own are being made). */
  own: boolean
}

export const GENERIC_PHRASES = ["Thinking it over…", "Working on it…", "One moment…", "Getting things in order…"]

export async function fetchStatusPhrases(persona: string): Promise<StatusPhrases | null> {
  try {
    const res = await fetch(`/api/chat/status-phrases?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) return null
    const body = (await res.json()) as Partial<StatusPhrases>
    return { phrases: body.phrases && body.phrases.length > 0 ? body.phrases : GENERIC_PHRASES, own: body.own === true }
  } catch {
    return null
  }
}
