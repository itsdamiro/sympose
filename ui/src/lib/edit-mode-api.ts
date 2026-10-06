import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/personas/{handle}/edit-mode` (docs/decisions/072): which mode counts for a persona (plan, manual,
 * accept or auto), where it comes from, a line on each mode, and the note about the model she uses to show before
 * `accept` or `auto` is chosen. The backend holds every rule and every figure; saving goes to her untracked local file.
 */
export type EditModeId = "plan" | "manual" | "accept" | "auto"

export interface EditModeInfo {
  mode: EditModeId
  /** `persona`: her own file says so; `global`: she follows the Settings page's mode. */
  source: "persona" | "global"
  modes: { id: EditModeId; summary: string }[]
  /** About the model she uses, for the two modes that need it. */
  notes: { accept: string | null; auto: string | null }
  model: string
}

const url = (handle: string) => `/api/personas/${encodeURIComponent(handle)}/edit-mode`

/** `GET`: the persona's edit mode; `null` when the backend is unreachable. */
export async function fetchEditMode(handle: string): Promise<EditModeInfo | null> {
  try {
    const res = await fetch(url(handle))
    return res.ok ? ((await res.json()) as EditModeInfo) : null
  } catch {
    return null
  }
}

export type SaveEditModeResult = { ok: true; info: EditModeInfo } | { ok: false; error: string }

/** `PUT`: her own mode, or `null` to clear it so her shipped file's or the global one applies again. */
export async function saveEditMode(handle: string, mode: EditModeId | null): Promise<SaveEditModeResult> {
  try {
    const res = await fetch(url(handle), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Something failed on Sympose's side (code ${res.status}). Try again.` }
    return { ok: true, info: (await res.json()) as EditModeInfo }
  } catch {
    return { ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." }
  }
}

/** The global mode and who it reaches (docs/decisions/072): the personas with no mode of their own, and the note for `accept` and `auto` with one line for each. */
export interface GlobalEditMode {
  mode: EditModeId
  following: { handle: string; name: string; model: string }[]
  notes: { accept: string; auto: string }
}

/** `GET /api/edit-mode/global`; `null` when the backend is unreachable. */
export async function fetchGlobalEditMode(): Promise<GlobalEditMode | null> {
  try {
    const res = await fetch("/api/edit-mode/global")
    return res.ok ? ((await res.json()) as GlobalEditMode) : null
  } catch {
    return null
  }
}
