import { notify } from "@/lib/notify"
import type { VaultNode } from "@/components/sympose"
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
  const moveNote = async (path: string, destFolder: string) => {
    const res = await moveVaultNote(path, destFolder, activePersona)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    if (res.path === path) return
    refreshVault()
    noteRenamed(path, res.path)
    notify.success(res.detail)
  }

  const vaultTreeActions = {
    selectedPath: openableNote,
    onHide: hideFromView,
    onSelect: (node: VaultNode) => {
      selectNote(node.path)
      openEditor()
    },
    persona: activePersona,
    onRenamed: (oldPath: string, newPath: string) => {
      refreshVault()
      noteRenamed(oldPath, newPath)
    },
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

  return { moveNote, vaultTreeActions, onEditorRenamed, onEditorDeleted }
}
