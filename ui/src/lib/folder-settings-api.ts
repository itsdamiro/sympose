import { detailOf } from "./vault-note-api"

/**
 * Client for the Folder settings dialog (docs/decisions/087): what a top-level folder's settings are now (its
 * definition note's own values, or the generic template when it has none), and saving what the user set. Nothing
 * is drafted by a model; what is sent is what the user saw and edited.
 */
export interface FolderSettings {
  /** Whether the folder can have settings now: a top-level folder of the user's own content, in the persona's scope. */
  editable: boolean
  /** Whether the folder already has a definition note, which a save then edits in place. */
  defined: boolean
  /** What the folder is for, `""` for none. */
  purpose: string
  /** The property lines a new note of the folder starts with, placeholders unfilled. */
  template: string[]
  /** `note` when they are the definition's own, `vault` when they are the vault's `Templates/Note template.md`,
   *  `settings` when they are built from the `note_template_keys` setting. */
  templateSource: "note" | "vault" | "settings"
  /** The folder's look as its note sets it; `null` for one that is not set. A name the icon set lacks is kept as
   *  typed, so a save does not drop it. */
  icon: string | null
  accent: string | null
  accentDark: string | null
}

/** What a save sends: the whole dialog; the server rewrites only what differs from the note. */
export interface FolderSettingsInput {
  purpose: string
  template: string[]
  icon: string | null
  accent: string | null
  accentDark: string | null
}

const text = (v: unknown): string | null => (typeof v === "string" && v !== "" ? v : null)

/** `GET /api/vault/folder/settings`. `null` when the backend is unreachable or answers an error (a 409 for a
 *  definition that cannot be read as text is one). */
export async function fetchFolderSettings(
  folder: string,
  persona: string
): Promise<FolderSettings | null> {
  try {
    const query = `folder=${encodeURIComponent(folder)}&persona=${encodeURIComponent(persona)}`
    const res = await fetch(`/api/vault/folder/settings?${query}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as Record<string, unknown>
    return {
      editable: data.editable === true,
      defined: data.defined === true,
      purpose: typeof data.purpose === "string" ? data.purpose : "",
      template: Array.isArray(data.template) ? data.template.filter((l): l is string => typeof l === "string") : [],
      templateSource: data.template_source === "note" || data.template_source === "vault" ? data.template_source : "settings",
      icon: text(data.icon),
      accent: text(data.accent),
      accentDark: text(data.accent_dark),
    }
  } catch (err) {
    console.info(`[folder-settings] /api/vault/folder/settings unreachable (${err})`)
    return null
  }
}

export type SaveFolderSettingsResult =
  | { ok: true; created: boolean }
  | { ok: false; error: string }

/**
 * `PUT /api/vault/folder/settings` — create `<folder>/<folder>.md` or change the one that exists. A 409 means the
 * note changed (or appeared) while the dialog was open, a 400 carries why the text or look was refused.
 */
export async function saveFolderSettings(
  path: string,
  input: FolderSettingsInput,
  persona: string
): Promise<SaveFolderSettingsResult> {
  try {
    const res = await fetch("/api/vault/folder/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path,
        purpose: input.purpose,
        template: input.template,
        icon: input.icon,
        accent: input.accent,
        accent_dark: input.accentDark,
        persona,
      }),
    })
    if (res.ok) return { ok: true, created: ((await res.json()) as { created?: boolean }).created === true }
    return {
      ok: false,
      error: (await detailOf(res)) || `Couldn't save the folder settings (code ${res.status}). Try again.`,
    }
  } catch {
    return {
      ok: false,
      error: `Couldn't save the folder settings: Sympose isn't responding. Check that it's still running, then try again.`,
    }
  }
}
