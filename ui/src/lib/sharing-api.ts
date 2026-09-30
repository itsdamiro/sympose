import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/sharing` — what the persona's model may receive from the user's vault (docs/decisions/031,
 * 044). The backend decides whether the model is a cloud one and holds the one list of approved categories the
 * terminal's `/share` uses too, so the browser holds no rule of its own.
 */
export interface ShareCategory {
  name: string
  /** What the category is, in the words the user is asked about it. */
  description: string
  /** Whether a cloud model may receive it. */
  shared: boolean
}

export interface SharingState {
  model: string
  /** The model is not a local one: something leaves the machine. */
  cloud: boolean
  categories: ShareCategory[]
}

export type SharingResult =
  | { ok: true; state: SharingState }
  | { ok: false; error: string }

const BACKEND_DOWN = "the Sympose backend is not reachable"

/** `GET /api/sharing`. */
export async function fetchSharing(persona: string): Promise<SharingResult> {
  try {
    const res = await fetch(`/api/sharing?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
    return { ok: true, state: (await res.json()) as SharingState }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/sharing/{category}`: approve or stop approving one category; answers with the state now. */
export async function changeSharing(
  persona: string,
  category: string,
  shared: boolean
): Promise<SharingResult> {
  try {
    const res = await fetch(
      `/api/sharing/${encodeURIComponent(category)}?persona=${encodeURIComponent(persona)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shared }),
      }
    )
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Couldn't save ${category} (HTTP ${res.status})` }
    return { ok: true, state: (await res.json()) as SharingState }
  } catch {
    return { ok: false, error: `Couldn't save ${category}: ${BACKEND_DOWN}` }
  }
}
