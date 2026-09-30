import type { VaultNode } from "@/components/sympose"

/** A `[[wikilink]]` target is a bare stem, e.g. "Getting Started" for
 * "journal/Getting Started.md" — strip the extension to compare against one. */
function stem(name: string): string {
  return name.replace(/\.md$/i, "").trim().toLowerCase()
}

/**
 * Depth-first search of the vault tree for the note a `[[wikilink]]` target
 * resolves to, matched by filename stem (case-insensitive) since a wikilink
 * carries no folder path. `undefined` when nothing in the tree matches.
 */
export function findNoteByWikilink(
  tree: VaultNode[],
  target: string
): VaultNode | undefined {
  const want = stem(target)
  for (const node of tree) {
    if (node.type === "note" && stem(node.name) === want) return node
    if (node.children) {
      const found = findNoteByWikilink(node.children, target)
      if (found) return found
    }
  }
  return undefined
}

/** The note at exactly `path` (its full vault-relative path), or `undefined` when the tree does not hold
 *  it — a note hidden from view or since deleted is not in the tree. Unlike a wikilink, a path is
 *  unambiguous, so two notes with the same name in different folders are told apart. */
export function findNoteByPath(tree: VaultNode[], path: string): VaultNode | undefined {
  for (const node of tree) {
    if (node.type === "note" && node.path === path) return node
    if (node.children) {
      const found = findNoteByPath(node.children, path)
      if (found) return found
    }
  }
  return undefined
}
