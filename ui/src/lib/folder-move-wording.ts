import type { FolderMoveReach } from "@/lib/vault-folder-move-api"

const notes = (n: number) => `${n} note${n === 1 ? "" : "s"}`

/** The sentence for one persona whose reach changes (docs/decisions/074): "This gives Grace access to 12 notes." */
export function reachLine(r: FolderMoveReach): string {
  const bits = []
  if (r.gains) bits.push(`gives ${r.name} access to ${notes(r.gains)}`)
  if (r.loses) bits.push(`takes ${notes(r.loses)} away from ${r.name}`)
  return `This ${bits.join(" and ")}.`
}

/** The first few files that are in both folders, and how many more there are. */
export function clashList(files: string[], shown = 8): { shown: string[]; more: number } {
  return { shown: files.slice(0, shown), more: Math.max(0, files.length - shown) }
}

/** The name offered for a folder moved under another name: the first one the destination is not known to have. */
export function suggestedName(name: string): string {
  return `${name} (2)`
}
