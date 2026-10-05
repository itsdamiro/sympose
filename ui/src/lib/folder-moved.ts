/**
 * A folder was renamed or moved (docs/decisions/073, 074): the pins, recents, open note and section follow through
 * the shell, and what lives inside a component that owns its own state follows by listening here (the tree's expanded
 * folders, so a moved folder does not come back collapsed).
 */
type Listener = (oldFolder: string, newFolder: string) => void

const listeners = new Set<Listener>()

export function onFolderMoved(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function announceFolderMoved(oldFolder: string, newFolder: string): void {
  for (const listener of listeners) listener(oldFolder, newFolder)
}
