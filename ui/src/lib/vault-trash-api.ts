/**
 * Clients for `/api/vault/trash*` — the recovery surface. `delete_note` and
 * `delete_folder` move a note, or a folder with everything in it (attachments
 * too), to `<vault>/.trash/` rather than unlinking it; these list every file
 * that's recoverable, put one back, or delete it for good. Same
 * discriminated-result shape as `vault-note-api.ts` (and its `detailOf`
 * helper) so callers can toast the message instead of catching.
 */

import { detailOf } from "./vault-note-api"

export interface TrashedNote {
  /** `.trash`-relative path — the handle for restore / purge. */
  trash_path: string
  /** Where the file lived before deletion (clash suffix already stripped). */
  original_path: string
  /** Epoch seconds of the deletion (the trashed file's mtime). */
  deleted_at: number
  size: number
  /** The bin directory of the deleted folder this file went with (docs/decisions/050); absent for a file deleted alone. */
  folder?: string
}

/** A folder deleted as a unit: one row in the bin, restorable whole. */
export interface TrashedFolder {
  /** `.trash`-relative directory — the handle for "restore folder". */
  trash_dir: string
  original_path: string
  deleted_at: number
  /** Files of it still in the bin (and in this persona's scope). */
  count: number
}

export interface Trash {
  items: TrashedNote[]
  folders: TrashedFolder[]
}

/**
 * `GET /api/vault/trash` — recoverable files for this persona, newest deletion
 * first, and the folders deleted as a unit. Returns `null` on any error, so the
 * caller says it could not load the bin instead of showing an empty one.
 */
export async function fetchTrash(persona: string): Promise<Trash | null> {
  try {
    const res = await fetch(
      `/api/vault/trash?persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = (await res.json()) as Partial<Trash>
    return { items: body.items ?? [], folders: body.folders ?? [] }
  } catch (err) {
    console.info(`[vault-trash] /api/vault/trash unreachable (${err})`)
    return null
  }
}

export type TrashMutationResult =
  { ok: true; detail: string } | { ok: false; error: string }

/**
 * `POST /api/vault/trash/restore` — move the trashed note back to its original
 * path. 404 not in trash, 409 something occupies the original path now, 403
 * outside the sandbox.
 */
export async function restoreTrashNote(
  trashPath: string,
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch("/api/vault/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: trashPath, persona }),
    })
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Restore failed (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Restore failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

export type RestoreFolderResult =
  | { ok: true; detail: string; restored: string[]; skipped: { path: string; reason: string }[] }
  | { ok: false; error: string }

/**
 * `POST /api/vault/trash/restore-folder` — put back every file of a deleted folder whose place is free. Nothing is
 * overwritten; a file whose place is taken is skipped and named in `skipped` (docs/decisions/050).
 */
export async function restoreTrashFolder(trashDir: string, persona: string): Promise<RestoreFolderResult> {
  try {
    const res = await fetch("/api/vault/trash/restore-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: trashDir, persona }),
    })
    if (res.ok) {
      const body = (await res.json()) as { detail: string; restored: string[]; skipped: { path: string; reason: string }[] }
      return { ok: true, ...body }
    }
    return { ok: false, error: (await detailOf(res)) || `Restore failed (code ${res.status}). Try again.` }
  } catch {
    return { ok: false, error: `Restore failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

/**
 * `DELETE /api/vault/trash?path=` — permanently delete one trashed note.
 * Irreversible; the caller guards it behind a confirm dialog.
 */
export async function purgeTrashNote(
  trashPath: string,
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch(
      `/api/vault/trash?path=${encodeURIComponent(trashPath)}&persona=${encodeURIComponent(persona)}`,
      { method: "DELETE" }
    )
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Delete failed (code ${res.status}). Try again.`,
    }
  } catch {
    return { ok: false, error: `Delete failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

/**
 * `POST /api/vault/trash/empty` — permanently delete every in-scope trashed
 * note. Irreversible; guard behind a confirm dialog.
 */
export async function emptyTrash(
  persona: string
): Promise<TrashMutationResult> {
  try {
    const res = await fetch("/api/vault/trash/empty", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona }),
    })
    if (res.ok) return { ok: true, detail: (await res.json()).detail as string }
    return {
      ok: false,
      error: (await detailOf(res)) || `Empty trash failed (code ${res.status}). Try again.`,
    }
  } catch {
    return {
      ok: false,
      error: `Empty trash failed: Sympose isn't responding. Check that it's still running, then try again.`,
    }
  }
}
