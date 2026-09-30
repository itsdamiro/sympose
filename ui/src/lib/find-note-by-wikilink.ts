import type { VaultNode } from "@/components/sympose"

/** A name or a path without its `.md`, lower-cased, for comparing. */
function stem(name: string): string {
  return name.replace(/\.md$/i, "").trim().toLowerCase()
}

/** The part of a `[[target#Heading|label]]` that names a note: no label, no heading, no block id. */
function noteTarget(target: string): string {
  return (target.split("|")[0] ?? "").split("#")[0].split("^")[0].trim()
}

function notesOf(tree: VaultNode[]): VaultNode[] {
  return tree.flatMap((node) => [...(node.type === "note" ? [node] : []), ...(node.children ? notesOf(node.children) : [])])
}

/**
 * The note a `[[wikilink]]` target resolves to in the vault tree (depth first), or `undefined` when nothing
 * matches. A bare name (`[[Getting Started]]`) matches by file name, case-insensitively. A target with a folder
 * (`[[Projects/Idea]]`) matches the note at that path, and failing that one whose path ends with it, as Obsidian
 * does. A heading, block id or label after the name (`[[Idea#Plan|the plan]]`) is ignored: it opens the note.
 */
export function findNoteByWikilink(
  tree: VaultNode[],
  target: string
): VaultNode | undefined {
  const want = stem(noteTarget(target)).replace(/^\/+/, "")
  if (!want) return undefined
  const notes = notesOf(tree)
  if (!want.includes("/")) return notes.find((node) => stem(node.name) === want)
  return (
    notes.find((node) => stem(node.path) === want) ??
    notes.find((node) => stem(node.path).endsWith(`/${want}`))
  )
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
