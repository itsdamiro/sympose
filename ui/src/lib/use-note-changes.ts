import { notify } from "@/lib/notify"
import type { VaultNode } from "@/components/sympose"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { useFolderMove } from "@/lib/use-folder-move"
import { moveVaultNote } from "@/lib/vault-note-api"

/**
 * What the shell does when a note or folder is created, renamed, moved or deleted,
 * whether from a row of the tree or from the open editor: re-pull everything scoped
 * to the vault (`refreshVault`), keep the open note, the pins and the recents
 * pointing at the right path (`noteRenamed`), and close the editor on what just
 * went to the bin.
 *
 * - `moveNote` is a drag-and-drop of a note onto a folder row, either a subfolder
 *   in the tree in view or a root folder in the main menu. Both drop surfaces hand
 *   it the same `(path, destFolder)` pair; the no-op case (dropped back on its own
 *   folder) resolves without a fetch inside `moveVaultNote` itself, so nothing here
 *   guards it.
 * - `moveFolder` is the same for a folder row dropped on a folder, a root folder or the vault root (docs/decisions/074):
 *   it plans, asks what needs the user's word (`folderMoveAsk`, shown by `<FolderMoveDialog>`), moves, and follows.
 * - A rename or move of the open note first lets the editor save its unsaved edits to the new path
 *   (`followMove`), so nothing is written to the old one.
 * - `vaultTreeActions` is the row callbacks shared by both `<VaultTree>` instances
 *   (the folder in view, and the "beyond" tier): identical behaviour either way,
 *   spread onto each with its own `nodes` and `key`. Picking a note always brings
 *   the editor forward, the same as creating one or following a wikilink.
 * - `onEditorRenamed` and `onEditorDeleted` are the open editor's own rename and
 *   delete. When no note is selected, the path the editor reports becomes the
 *   selected note.
 */
export function useNoteChanges({
  activePersona,
  selectedNote,
  setSelectedNote,
  openableNote,
  selectNote,
  noteRenamed,
  folderRenamed,
  refreshVault,
  openEditor,
  hideFromView,
  isPinned,
  togglePin,
  unpinMany,
  removeFromRecents,
  clearRecents,
  hideExtension,
}: {
  activePersona: string
  selectedNote: string | undefined
  setSelectedNote: (path: string | undefined) => void
  openableNote: string | undefined
  selectNote: (path: string) => void
  noteRenamed: (oldPath: string, newPath: string) => void
  /** A folder was renamed: the pins, recents, open note and section under it follow (docs/decisions/073). */
  folderRenamed: (oldFolder: string, newFolder: string) => void
  refreshVault: () => void
  openEditor: () => void
  hideFromView: (path: string) => void
  isPinned: (path: string) => boolean
  togglePin: (path: string) => void
  unpinMany: (paths: string[]) => void
  removeFromRecents: (path: string) => void
  clearRecents: () => void
  hideExtension: boolean
}) {
  // The file is already at its new path: let the open editor save its unsaved edits there before its path
  // changes (otherwise its leave-note flush writes to the old path and fails).
  const followMove = async (oldPath: string, newPath: string) => {
    await getUnsavedGuard()?.retarget(oldPath, newPath)
    refreshVault()
    noteRenamed(oldPath, newPath)
  }

  // Before the rename request: a note with unsaved edits is saved first, whichever note it is, because the rename
  // rewrites links on disk and may rewrite this very note, so a buffer saved afterwards would conflict with the file or
  // overwrite the new links. `false` (it could not be saved; the editor says why) holds the rename back.
  const beforeFolderRename = async (): Promise<boolean> => {
    const guard = getUnsavedGuard()
    return !guard?.isDirty() || (await guard.save())
  }

  // The folder is already at its new name: a note open inside it has its unsaved edits saved at the new path first
  // (otherwise the leave-note flush would write to the old one), then everything that held the old path follows.
  const followFolderMove = async (oldFolder: string, newFolder: string) => {
    if (selectedNote?.startsWith(`${oldFolder}/`)) {
      await getUnsavedGuard()?.retarget(selectedNote, newFolder + selectedNote.slice(oldFolder.length))
    }
    refreshVault()
    folderRenamed(oldFolder, newFolder)
  }

  const moveNote = async (path: string, destFolder: string) => {
    const res = await moveVaultNote(path, destFolder, activePersona)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    if (res.path === path) return
    await followMove(path, res.path)
    notify.success(res.detail)
  }

  const { moveFolder, ask: folderMoveAsk, closeAsk: closeFolderMoveAsk } = useFolderMove({
    persona: activePersona,
    selectedNote,
    before: beforeFolderRename,
    after: followFolderMove,
    noteRenamedAway: () => setSelectedNote(undefined),
    refreshVault,
  })

  const vaultTreeActions = {
    selectedPath: openableNote,
    onHide: hideFromView,
    onSelect: (node: VaultNode) => {
      selectNote(node.path)
      openEditor()
    },
    persona: activePersona,
    onRenamed: followMove,
    onFolderRenamed: followFolderMove,
    onBeforeFolderRename: beforeFolderRename,
    onDeleted: (path: string) => {
      refreshVault()
      // `path` is a note's own path for a note-row delete, or a folder's path when
      // a whole folder went to the bin: either way, close the editor if it was
      // showing something that just moved.
      if (selectedNote === path || selectedNote?.startsWith(`${path}/`)) {
        setSelectedNote(undefined)
      }
    },
    onCreated: (path: string) => {
      refreshVault()
      selectNote(path)
      openEditor()
    },
    isPinned,
    onTogglePin: togglePin,
    onMoveNote: moveNote,
    onMoveFolder: moveFolder,
    onUnpinAll: unpinMany,
    onRemoveFromRecents: removeFromRecents,
    onClearRecents: clearRecents,
    hideExtension,
  }

  const onEditorRenamed = (newPath: string) => {
    if (selectedNote) noteRenamed(selectedNote, newPath)
    else setSelectedNote(newPath)
    refreshVault()
  }
  const onEditorDeleted = () => {
    setSelectedNote(undefined)
    refreshVault()
  }

  return { moveNote, moveFolder, folderMoveAsk, closeFolderMoveAsk, vaultTreeActions, onEditorRenamed, onEditorDeleted }
}
