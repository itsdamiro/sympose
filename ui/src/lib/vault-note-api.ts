export interface VaultNote {
  path: string
  content: string
  /** The file's mtime when it was read; a later save presents it so a change made elsewhere is caught. */
  mtime?: number
}

/** Pulls the backend's `{detail}` message out of a non-ok fetch Response, or
 *  `undefined` if the body isn't JSON / has no usable `detail`. A validation
 *  refusal (HTTP 422) carries a list of problems instead of text; their
 *  messages are joined. Shared by every vault-*-api.ts client so a caller can
 *  show a real error message instead of just an HTTP status. */
export async function detailOf(res: Response): Promise<string | undefined> {
  return res
    .json()
    .then((b) => {
      const detail = (b as { detail?: unknown }).detail
      if (typeof detail === "string") return detail
      if (!Array.isArray(detail)) return undefined
      const messages = detail.map((d) => (d as { msg?: unknown })?.msg).filter((m): m is string => typeof m === "string")
      return messages.length > 0 ? messages.join("; ") : undefined
    })
    .catch(() => undefined)
}

/**
 * Client for `GET /api/vault/note` — the raw Markdown (frontmatter included)
 * for one vault file, scoped to a persona's allowed vault folders. Returns
 * `null` on a 404 (note missing) or when the backend is unreachable (offline
 * dev), so the caller renders an empty/error state instead of throwing.
 */
export async function fetchVaultNote(
  path: string,
  persona: string
): Promise<VaultNote | null> {
  try {
    const res = await fetch(
      `/api/vault/note?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as VaultNote
  } catch (err) {
    console.info(`[vault-note] /api/vault/note unreachable (${err})`)
    return null
  }
}

export type SaveVaultNoteResult =
  | { ok: true; mtime?: number }
  | { ok: false; error: string; conflict?: boolean }

/**
 * Client for `PUT /api/vault/note` — write the editor's full Markdown (with
 * frontmatter) back to an existing vault note. The backend never creates a new
 * file: a 404 means the note is gone, a 403 that the path fell outside the
 * persona's sandbox, a 409 that the file changed since `expectedMtime` (from
 * `fetchVaultNote` or the last save). Returns a discriminated result rather
 * than throwing so the caller can toast the message.
 */
export async function saveVaultNote(
  path: string,
  content: string,
  persona: string,
  expectedMtime?: number
): Promise<SaveVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content, persona, expected_mtime: expectedMtime }),
    })
    if (res.ok) return { ok: true, mtime: ((await res.json()) as { mtime?: number }).mtime }
    return {
      ok: false,
      error: (await detailOf(res)) || `Save failed (code ${res.status}). Try again.`,
      conflict: res.status === 409,
    }
  } catch {
    return { ok: false, error: `Save failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type CreateVaultNoteResult =
  | { ok: true; path: string }
  | { ok: false; error: string }

/**
 * Client for `POST /api/vault/note` — create a new note at `path` (relative to
 * the vault, e.g. `Projects/Idea`). The backend seeds a frontmatter + title
 * stub. A 409 means a note already exists there, a 403 that the path is outside
 * the persona's sandbox.
 */
export async function createVaultNote(
  path: string,
  persona: string
): Promise<CreateVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, persona }),
    })
    if (res.ok) return { ok: true, path }
    return {
      ok: false,
      error: (await detailOf(res)) || `Couldn't create note (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Couldn't create note: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type CreateVaultFolderResult =
  | { ok: true; path: string }
  | { ok: false; error: string }

/**
 * Client for `POST /api/vault/folder` — create a new empty folder at `path`
 * (relative to the vault, e.g. `Projects/Archive`). A 409 means a file or
 * folder already exists there, a 403 that the path fell outside the persona's
 * sandbox.
 */
export async function createVaultFolder(
  path: string,
  persona: string
): Promise<CreateVaultFolderResult> {
  try {
    const res = await fetch("/api/vault/folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, persona }),
    })
    if (res.ok) return { ok: true, path }
    return {
      ok: false,
      error: (await detailOf(res)) || `Couldn't create folder (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Couldn't create folder: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type RenameVaultFolderResult =
  | { ok: true; path: string; detail: string; personas: string[]; personasUnchanged: string[]; relinkFailed: number }
  | { ok: false; error: string }

/**
 * Client for `PATCH /api/vault/folder` (docs/decisions/073) — rename the folder at `path` to `newName`, one plain
 * name: the folder keeps its parent. The links that name it, the personas' own folder scopes, the hidden list and the
 * persona's pending changes follow on the server. 404 gone, 409 name taken, 400 not a plain name, 403 outside the
 * sandbox. `path` in the result is the folder's new vault-relative path, `personas` those whose scope was rewritten.
 */
export async function renameVaultFolder(
  path: string,
  newName: string,
  persona: string
): Promise<RenameVaultFolderResult> {
  try {
    const res = await fetch("/api/vault/folder", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, new_name: newName, persona }),
    })
    if (res.ok) {
      const body = (await res.json()) as { path: string; detail: string; personas: string[]; personas_unchanged: string[]; failed: number }
      return { ok: true, path: body.path, detail: body.detail, personas: body.personas, personasUnchanged: body.personas_unchanged, relinkFailed: body.failed }
    }
    return { ok: false, error: (await detailOf(res)) || `Rename failed (code ${res.status}). Try again.` }
  } catch {
    return { ok: false, error: `Rename failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type RenameVaultNoteResult =
  | { ok: true; path: string; detail: string }
  | { ok: false; error: string }

/**
 * Client for `PATCH /api/vault/note` — rename `path` to `newName` (a bare stem
 * stays in the same folder, `Folder/stem` is relative to the vault, `/stem` is
 * the vault root) and rewrite the `[[wikilinks]]` that referenced it.
 * 404 source gone, 409 target taken, 403 outside the sandbox.
 * `path` in the result is the note's new vault-relative path.
 */
export async function renameVaultNote(
  path: string,
  newName: string,
  persona: string
): Promise<RenameVaultNoteResult> {
  try {
    const res = await fetch("/api/vault/note", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, new_path: newName, persona }),
    })
    if (res.ok) {
      const body = (await res.json()) as { path: string; detail: string }
      return { ok: true, path: body.path, detail: body.detail }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `Rename failed (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Rename failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

/**
 * Move a note into `destFolder` (vault-relative, `""` for the vault root) by
 * calling `renameVaultNote` with a slash-qualified target — the same
 * `PATCH /api/vault/note` endpoint already used for a same-folder rename
 * also relocates across folders when `new_path` carries a `/`, so
 * this is the drag-and-drop client, not a new backend route. A drop
 * back onto the note's current folder is a no-op resolved without a fetch,
 * so dragging a row over its own folder never round-trips or risks the
 * backend's own same-path `NOTE_EXISTS` check misreporting a clash.
 */
export async function moveVaultNote(
  path: string,
  destFolder: string,
  persona: string
): Promise<RenameVaultNoteResult> {
  const stem = path.split("/").pop()!.replace(/\.md$/i, "")
  const currentFolder = path.includes("/")
    ? path.slice(0, path.lastIndexOf("/"))
    : ""
  if (destFolder === currentFolder) {
    return { ok: true, path, detail: "" }
  }
  // A bare stem would keep the note in its folder; a leading slash is the root.
  return renameVaultNote(path, destFolder ? `${destFolder}/${stem}` : `/${stem}`, persona)
}

export type DeleteVaultNoteResult =
  | { ok: true; detail: string }
  | { ok: false; error: string }

/**
 * Client for `DELETE /api/vault/note` — move the note to `<vault>/.trash/`.
 * 404 if it's already gone, 403 outside the sandbox.
 */
export async function deleteVaultNote(
  path: string,
  persona: string
): Promise<DeleteVaultNoteResult> {
  try {
    const res = await fetch(
      `/api/vault/note?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`,
      { method: "DELETE" }
    )
    if (res.ok) {
      const body = (await res.json()) as { detail: string }
      return { ok: true, detail: body.detail }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `Delete failed (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Delete failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type DeleteVaultFolderResult =
  | { ok: true; detail: string }
  | { ok: false; error: string }

/**
 * Client for `DELETE /api/vault/folder` — an empty folder is removed
 * outright, a non-empty one moves to `<vault>/.trash/` note-by-note, same as
 * `deleteVaultNote`. 404 if it's already gone, 403 outside the
 * sandbox.
 */
export async function deleteVaultFolder(
  path: string,
  persona: string
): Promise<DeleteVaultFolderResult> {
  try {
    const res = await fetch(
      `/api/vault/folder?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`,
      { method: "DELETE" }
    )
    if (res.ok) {
      const body = (await res.json()) as { detail: string }
      return { ok: true, detail: body.detail }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `Delete failed (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Delete failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}
