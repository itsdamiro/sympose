/**
 * Shared drag-and-drop contract for moving a vault note by dragging its row —
 * the vault tree's own folder rows and the main menu's root
 * folders both accept the same drag. A custom MIME (rather than
 * `text/plain`) keeps an OS file drag from Finder — which carries a `Files`
 * type, never this one — from matching a drop target meant for an in-app
 * note row; that OS-import path isn't wired up yet and shouldn't silently
 * half-work.
 */
const VAULT_NOTE_MIME = "application/x-sympose-vault-note-path"

export function startNoteDrag(e: React.DragEvent, path: string) {
  e.dataTransfer.setData(VAULT_NOTE_MIME, path)
  e.dataTransfer.effectAllowed = "move"
}

/** True when the event's drag payload is a vault note row, not an OS file
 *  drag or some other in-page drag. Check before `preventDefault()`ing a
 *  `dragover` so a non-note drag still gets the browser's own no-drop cue. */
export function isNoteDrag(e: React.DragEvent) {
  return e.dataTransfer.types.includes(VAULT_NOTE_MIME)
}

export function readNoteDrag(e: React.DragEvent): string | undefined {
  return e.dataTransfer.getData(VAULT_NOTE_MIME) || undefined
}

/**
 * The same for a folder row (docs/decisions/074): a folder dragged onto another folder row, a root folder in the main
 * menu, or the vault root. Its own MIME, so a folder drop never lands on a surface that only takes notes, and a note
 * drop never lands on one that only takes folders.
 */
const VAULT_FOLDER_MIME = "application/x-sympose-vault-folder-path"

let dragged: string | undefined

export function startFolderDrag(e: React.DragEvent, path: string) {
  e.dataTransfer.setData(VAULT_FOLDER_MIME, path)
  e.dataTransfer.effectAllowed = "move"
  dragged = path
}

/** The drag ended, dropped or not. */
export function endFolderDrag() {
  dragged = undefined
}

/** The folder being dragged right now: a `dragover` can see the payload's type but not its value. */
export function draggedFolder(): string | undefined {
  return dragged
}

/** Whether this `dragover` carries a folder that may be dropped into `destination` (`""` is the vault root): the
 *  surfaces that take a folder offer a drop only then, so a forbidden target shows no highlight. */
export function canDropDraggedFolder(e: React.DragEvent, destination: string): boolean {
  return isFolderDrag(e) && dragged !== undefined && canDropFolder(dragged, destination)
}

export function isFolderDrag(e: React.DragEvent) {
  return e.dataTransfer.types.includes(VAULT_FOLDER_MIME)
}

export function readFolderDrag(e: React.DragEvent): string | undefined {
  return e.dataTransfer.getData(VAULT_FOLDER_MIME) || undefined
}

/** Whether `folder` may be dropped into `destination`: not onto itself, not into one of its own folders, not into the
 *  folder it is already in. */
export function canDropFolder(folder: string, destination: string): boolean {
  const parent = folder.includes("/") ? folder.slice(0, folder.lastIndexOf("/")) : ""
  return destination !== folder && !destination.startsWith(`${folder}/`) && destination !== parent
}

/** Whether a `dragleave` really leaves the element it is handled on, not just moves into one of its own children
 *  (a browser fires `dragenter` on the child first, then `dragleave` on the parent): the highlight stays while the
 *  drag is anywhere over the row, and goes out only when it leaves it. */
export function leavesTarget(e: React.DragEvent): boolean {
  return !e.currentTarget.contains(e.relatedTarget as Node | null)
}

type FolderDropOptions = {
  /** The folder this surface drops into (`""` is the vault root). */
  destination: string
  /** What the surface does with a note or a folder dropped on it; a missing one means it takes none of that kind. */
  onMoveNote?: (path: string, destination: string) => void
  onMoveFolder?: (path: string, destination: string) => void
  /** The highlight: on while a drag this surface takes is over it. */
  setOver: (over: boolean) => void
  /** A row over a larger drop surface (the main menu's rows over the vault root) gives this: it then answers for
   *  every folder drag itself, takes it or not, so the surface behind never sees it, and it is called when the
   *  row is entered or dropped on, so that surface can put out its own highlight. */
  onClaim?: () => void
}

/** The four drag handlers of a surface that takes a note or a folder dropped into `destination` (docs/decisions/074):
 *  the vault tree's folder rows, the folder in view's heading, the main menu's root folders and the vault root. A
 *  forbidden target shows no highlight and does not accept the drop. */
export function folderDropHandlers<T extends HTMLElement>({
  destination,
  onMoveNote,
  onMoveFolder,
  setOver,
  onClaim,
}: FolderDropOptions): Pick<React.HTMLAttributes<T>, "onDragOver" | "onDragEnter" | "onDragLeave" | "onDrop"> {
  const takes = (e: React.DragEvent) =>
    (!!onMoveNote && isNoteDrag(e)) || (!!onMoveFolder && canDropDraggedFolder(e, destination))
  const owned = (e: React.DragEvent) => !!onClaim && isFolderDrag(e)
  return {
    onDragOver: (e) => {
      if (owned(e)) e.stopPropagation()
      if (!takes(e)) return
      e.preventDefault()
      e.dataTransfer.dropEffect = "move"
    },
    onDragEnter: (e) => {
      if (owned(e)) {
        e.stopPropagation()
        onClaim?.()
      }
      if (takes(e)) setOver(true)
    },
    onDragLeave: (e) => {
      if (owned(e)) e.stopPropagation()
      if (leavesTarget(e)) setOver(false)
    },
    onDrop: (e) => {
      setOver(false)
      onClaim?.()
      if (owned(e)) e.stopPropagation()
      const folder = onMoveFolder ? readFolderDrag(e) : undefined
      if (folder) {
        e.preventDefault()
        endFolderDrag()
        if (canDropFolder(folder, destination)) onMoveFolder!(folder, destination)
        return
      }
      const path = onMoveNote ? readNoteDrag(e) : undefined
      if (!path) return
      e.preventDefault()
      onMoveNote!(path, destination)
    },
  }
}
