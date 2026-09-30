import { describe, expect, it } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { findNoteByPath, findNoteByWikilink } from "./find-note-by-wikilink"

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const folder = (name: string, children: VaultNode[]): VaultNode => ({ type: "folder", name, path: name, children }) as VaultNode

const tree: VaultNode[] = [
  folder("Work", [note("Work/Atlas.md"), folder("Old", [note("Work/Old/Plan.md")])]),
  folder("Home", [note("Home/Atlas.md")]),
]

describe("findNoteByPath", () => {
  it("finds a note by its exact vault path, at any depth", () => {
    expect(findNoteByPath(tree, "Work/Old/Plan.md")?.path).toBe("Work/Old/Plan.md")
  })

  it("tells two notes with the same name in different folders apart", () => {
    expect(findNoteByPath(tree, "Home/Atlas.md")?.path).toBe("Home/Atlas.md")
    expect(findNoteByPath(tree, "Work/Atlas.md")?.path).toBe("Work/Atlas.md")
    expect(findNoteByWikilink(tree, "Atlas")?.path).toBe("Work/Atlas.md") // a bare name cannot
  })

  it("finds nothing for a path that is not in the tree, or for a folder", () => {
    expect(findNoteByPath(tree, "Work/Missing.md")).toBeUndefined()
    expect(findNoteByPath(tree, "Work")).toBeUndefined()
  })
})
