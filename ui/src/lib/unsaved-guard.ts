/**
 * The note editor's unsaved changes, for anything about to change the vault underneath it (ADR 004, amendment
 * of 2026-10-01). The editor registers itself while a note is open; the vault switcher asks it before switching.
 * A module-level slot because there is one editor and the two sit far apart in the tree.
 */
export interface UnsavedGuard {
  /** The open note's name, for the question. */
  name: () => string
  isDirty: () => boolean
  /** Save to the vault the note came from; `true` when it is saved (or there was nothing to save). */
  save: () => Promise<boolean>
  /**
   * The open note's file was renamed or moved (from a tree row, a drop, or its own menu). If it is the note held
   * here, point the buffer at the new path and save its unsaved edits there now, so the leave-note flush that the
   * path change triggers does not `PUT` to the old path (404, edits lost). Other paths are ignored.
   */
  retarget: (oldPath: string, newPath: string) => Promise<void>
}

let guard: UnsavedGuard | null = null

export function setUnsavedGuard(next: UnsavedGuard | null): void {
  guard = next
}

export function getUnsavedGuard(): UnsavedGuard | null {
  return guard
}
