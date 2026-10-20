import { detailOf } from "./vault-note-api"

/**
 * Client for the Folder look dialog (docs/decisions/090): the colour and icon of a folder below a top-level folder,
 * which the server keeps in that folder's top-level folder's definition note. What is sent is what the user picked.
 */
export interface FolderColor {
  /** Whether the folder can be given a look now: below one of the user's own top-level folders, in the persona's scope. */
  editable: boolean
  /** The folder's own colour as the note sets it; `null` for one that is not set (the folder then takes the colour
   *  of the folder above it). */
  accent: string | null
  accentDark: string | null
  /** The name of its icon in the icon set; `null` for none (the folder is drawn with the usual one). */
  icon: string | null
}

const text = (v: unknown): string | null => (typeof v === "string" && v !== "" ? v : null)

/** `GET /api/vault/folder/color`. `null` when the backend is unreachable or answers an error. */
export async function fetchFolderColor(path: string, persona: string): Promise<FolderColor | null> {
  try {
    const query = `path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`
    const res = await fetch(`/api/vault/folder/color?${query}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as Record<string, unknown>
    return { editable: data.editable === true, accent: text(data.accent), accentDark: text(data.accent_dark), icon: text(data.icon) }
  } catch (err) {
    console.info(`[folder-color] /api/vault/folder/color unreachable (${err})`)
    return null
  }
}

export type SaveFolderColorResult = { ok: true; created: boolean } | { ok: false; error: string }

/**
 * `PUT /api/vault/folder/color`: both colours and the icon `null` clears the folder's own look. A 409 means the note
 * changed while the dialog was open, a 400 carries why the look was refused.
 */
export async function saveFolderColor(
  path: string,
  look: { accent: string | null; accentDark: string | null; icon: string | null },
  persona: string
): Promise<SaveFolderColorResult> {
  try {
    const res = await fetch("/api/vault/folder/color", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, accent: look.accent, accent_dark: look.accentDark, icon: look.icon, persona }),
    })
    if (res.ok) return { ok: true, created: ((await res.json()) as { created?: boolean }).created === true }
    return { ok: false, error: (await detailOf(res)) || `Couldn't save the look (code ${res.status}). Try again.` }
  } catch {
    return { ok: false, error: `Couldn't save the look: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}
