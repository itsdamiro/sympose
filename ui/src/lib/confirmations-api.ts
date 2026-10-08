import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/chat/confirmations` (docs/decisions/078): the requests a persona makes for the user's yes, shown as a
 * card in the chat. The backend holds every rule; a proposal is checked again when it is accepted.
 */
export interface PersonaDraft {
  name: string
  title: string
  soul: string
  icon: string
  accent: string
  accent_dark: string
  edit_mode: string
  folders: string[]
}

export type RequestState = "waiting" | "accepted" | "declined" | "replaced" | "outdated"

export interface ConfirmationRequest {
  id: string
  kind: "persona"
  state: RequestState
  /** The handle the new persona would have. */
  handle: string
  draft: PersonaDraft
  /** Why a request became outdated. */
  reason: string | null
  created_at: string
  /** The folders the pills offer: those the proposing persona can read. */
  folder_choices: string[]
  /** The edit modes the dropdown offers, each with its line. */
  edit_modes: { id: string; summary: string }[]
}

/** `GET`: the requests of one conversation, oldest first; `[]` when the backend is unreachable. */
export async function fetchConfirmations(persona: string, session: string): Promise<ConfirmationRequest[]> {
  try {
    const res = await fetch(`/api/chat/confirmations?persona=${encodeURIComponent(persona)}&session=${encodeURIComponent(session)}`)
    return res.ok ? ((await res.json()) as { requests: ConfirmationRequest[] }).requests : []
  } catch {
    return []
  }
}

export type AnswerResult = { ok: true; request: ConfirmationRequest } | { ok: false; error: string }

/** `POST`: accept (with the folders and the edit mode as the card was left) or decline a waiting request. */
export async function answerConfirmation(
  persona: string,
  id: string,
  accept: boolean,
  folders: string[] | null,
  editMode: string | null = null
): Promise<AnswerResult> {
  try {
    const res = await fetch(`/api/chat/confirmations/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, accept, folders, edit_mode: editMode }),
    })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Something failed on Sympose's side (code ${res.status}). Try again.` }
    return { ok: true, request: (await res.json()) as ConfirmationRequest }
  } catch {
    return { ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." }
  }
}
