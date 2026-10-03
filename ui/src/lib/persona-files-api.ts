import { detailOf, type SaveVaultNoteResult } from "@/lib/vault-note-api"

/**
 * Client for a persona's own files (docs/decisions/061): `soul.md`, `profile.md`, `context.md` and `decisions.md`,
 * listed, read and saved for the editor, the soul's reset to the shipped file, and the review of a rewrite the
 * engine staged for the profile or the context. The backend decides which names are allowed.
 */
export interface PersonaFileInfo {
  name: string
  label: string
  description: string
  /** The file is there (a file not written so far still opens, empty, and a first save creates it). */
  exists: boolean
  /** `soul.md` only: the user's own copy is in use, not the shipped one. */
  local: boolean
  /** `profile.md` and `context.md`: a rewrite is waiting for review. */
  pending: boolean
}

export interface PersonaFile {
  name: string
  content: string
  /** The file's mtime, which a save presents; `null` while the file does not exist yet. */
  mtime: number | null
  local: boolean
}

const base = (handle: string) => `/api/personas/${encodeURIComponent(handle)}/files`

async function read<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url)
    return res.ok ? ((await res.json()) as T) : null
  } catch {
    return null
  }
}

export async function listPersonaFiles(handle: string): Promise<PersonaFileInfo[] | null> {
  return (await read<{ files: PersonaFileInfo[] }>(base(handle)))?.files ?? null
}

export const fetchPersonaFile = (handle: string, name: string) => read<PersonaFile>(`${base(handle)}/${name}`)

export type SavePersonaFileResult = SaveVaultNoteResult & { local?: boolean }

/** `PUT`: the file's whole text with the mtime it was opened at. A 409 means it changed since: `conflict` says so. */
export async function savePersonaFile(
  handle: string,
  name: string,
  content: string,
  expectedMtime?: number
): Promise<SavePersonaFileResult> {
  try {
    const res = await fetch(`${base(handle)}/${name}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, expected_mtime: expectedMtime }),
    })
    if (res.ok) {
      const saved = (await res.json()) as { mtime?: number; local?: boolean }
      return { ok: true, mtime: saved.mtime, local: saved.local ?? false }
    }
    return { ok: false, error: (await detailOf(res)) || `Save failed (HTTP ${res.status})`, conflict: res.status === 409 }
  } catch (err) {
    return { ok: false, error: `Save failed — backend unreachable (${err})` }
  }
}

/** Puts the shipped soul back (the user's copy is kept aside): whether there was a copy, or `null` when it failed. */
export async function resetPersonaSoul(handle: string): Promise<boolean | null> {
  try {
    const res = await fetch(`${base(handle)}/soul.md/reset`, { method: "POST" })
    return res.ok ? ((await res.json()) as { removed: boolean }).removed : null
  } catch {
    return null
  }
}

export interface PendingRewrite {
  text: string
  /** A unified diff of the proposal against the file as it is now. */
  diff: string
}

/** The rewrite waiting for a file, or `null` when none is. */
export const fetchPendingRewrite = (handle: string, name: string) => read<PendingRewrite>(`${base(handle)}/${name}/pending`)

export async function resolvePendingRewrite(
  handle: string,
  name: string,
  action: "accept" | "discard"
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${base(handle)}/${name}/pending/${action}`, { method: "POST" })
    if (res.ok) return { ok: true }
    return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
  } catch (err) {
    return { ok: false, error: `Backend unreachable (${err})` }
  }
}
