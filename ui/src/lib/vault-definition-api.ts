import { detailOf } from "./vault-note-api"

/**
 * Client for setting up a new root folder (docs/decisions/038): the generic
 * template's property lines to start from, and writing the definition note
 * the user typed. Nothing is drafted by a model; what is sent is what the
 * user saw and edited.
 */
export interface NoteTemplate {
  /** The property lines a new note starts with, placeholders unfilled. */
  lines: string[]
  /** `vault` when they are the vault's own `Templates/Note template.md`,
   *  `settings` when they are built from the `note_template_keys` setting. */
  source: "vault" | "settings"
  /** Only when a folder was asked about: whether it can be given a definition
   *  now (a root folder of the user's content, in the persona's scope, without
   *  one). Absent when no folder was named. */
  definable?: boolean
}

/** `GET /api/vault/note-template`, naming the `folder` just created so the
 *  answer also says whether it can have a definition. `null` when the backend
 *  is unreachable or answers an error. */
export async function fetchNoteTemplate(
  folder: string,
  persona: string
): Promise<NoteTemplate | null> {
  try {
    const query = `folder=${encodeURIComponent(folder)}&persona=${encodeURIComponent(persona)}`
    const res = await fetch(`/api/vault/note-template?${query}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as Partial<NoteTemplate>
    return {
      lines: data.lines ?? [],
      source: data.source === "vault" ? "vault" : "settings",
      definable: data.definable === true,
    }
  } catch (err) {
    console.info(`[vault-definition] /api/vault/note-template unreachable (${err})`)
    return null
  }
}

export type CreateFolderDefinitionResult =
  | { ok: true; path: string }
  | { ok: false; error: string }

/**
 * `POST /api/vault/folder/definition` — write `<folder>/<folder>.md` from a
 * purpose (may be empty) and the template's property lines. A 409 means the
 * folder already has a definition, a 400 carries why the text was refused.
 */
export async function createFolderDefinition(
  path: string,
  purpose: string,
  template: string[],
  persona: string
): Promise<CreateFolderDefinitionResult> {
  try {
    const res = await fetch("/api/vault/folder/definition", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, purpose, template, persona }),
    })
    if (res.ok) return { ok: true, path }
    return {
      ok: false,
      error:
        (await detailOf(res)) || `Couldn't create the definition (HTTP ${res.status})`,
    }
  } catch (err) {
    return {
      ok: false,
      error: `Couldn't create the definition — backend unreachable (${err})`,
    }
  }
}
