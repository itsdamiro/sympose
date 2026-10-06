import { detailOf } from "@/lib/vault-note-api"

/** A persona whose reach of the moved folder's notes would change. */
export interface FolderMoveReach {
  handle: string
  name: string
  gains: number
  loses: number
}

/** What moving a folder would do and what needs the user's word first (docs/decisions/074). */
export interface FolderMovePlan {
  path: string
  destination: string
  newPath: string
  /** A folder of that name is already at the destination: the user chooses to rename or merge. */
  clash: boolean
  /** On a merge, the files that are in both, relative to the folder. */
  noteClashes: string[]
  reach: FolderMoveReach[]
  /** A definition note's folder moves between top level and below. */
  definition: "stops" | "starts" | null
}

export type FolderMovePlanResult = ({ ok: true } & FolderMovePlan) | { ok: false; error: string }

/** `POST /api/vault/folder/move-plan`: read only. `destination` is a folder path, or `""` for the vault root. With a
 *  `newName`, the plan is for the folder going in under that name (what the user chose for a clash). */
export async function planFolderMove(path: string, destination: string, persona: string, newName = ""): Promise<FolderMovePlanResult> {
  try {
    const res = await fetch("/api/vault/folder/move-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, destination, persona, new_name: newName }),
    })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Move failed (code ${res.status}). Try again.` }
    const b = (await res.json()) as {
      path: string
      destination: string
      new_path: string
      clash: boolean
      note_clashes: string[]
      reach: FolderMoveReach[]
      definition: "stops" | "starts" | null
    }
    return { ok: true, path: b.path, destination: b.destination, newPath: b.new_path, clash: b.clash, noteClashes: b.note_clashes, reach: b.reach, definition: b.definition }
  } catch {
    return { ok: false, error: `Move failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}

/** What the user answered to the plan's questions. */
export interface FolderMoveAnswers {
  ifExists?: "merge" | "rename"
  newName?: string
  renameClashingNotes?: boolean
  confirmReach?: boolean
}

export type MoveVaultFolderResult =
  | { ok: true; path: string; detail: string; personas: string[]; personasUnchanged: string[]; relinkFailed: number }
  | { ok: false; error: string }

/** `PATCH /api/vault/folder/move`: the move itself, after the answers. The server follows with the links, the personas'
 *  scopes, the hidden list and the pending changes. */
export async function moveVaultFolder(
  path: string,
  destination: string,
  persona: string,
  answers: FolderMoveAnswers = {}
): Promise<MoveVaultFolderResult> {
  try {
    const res = await fetch("/api/vault/folder/move", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path,
        destination,
        persona,
        if_exists: answers.ifExists ?? null,
        new_name: answers.newName ?? "",
        rename_clashing_notes: answers.renameClashingNotes ?? false,
        confirm_reach: answers.confirmReach ?? false,
      }),
    })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Move failed (code ${res.status}). Try again.` }
    const b = (await res.json()) as { path: string; detail: string; personas: string[]; personas_unchanged: string[]; failed: number }
    return { ok: true, path: b.path, detail: b.detail, personas: b.personas, personasUnchanged: b.personas_unchanged, relinkFailed: b.failed }
  } catch {
    return { ok: false, error: `Move failed: Sympose isn't responding. Check that it's still running, then try again.` }
  }
}
