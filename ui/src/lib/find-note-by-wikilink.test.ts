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

describe("findNoteByWikilink (#103)", () => {
  it("matches a bare name by file name, ignoring case and a .md", () => {
    expect(findNoteByWikilink(tree, "plan")?.path).toBe("Work/Old/Plan.md")
    expect(findNoteByWikilink(tree, "Plan.md")?.path).toBe("Work/Old/Plan.md")
  })

  it("ignores a heading, a block id and a label: the link opens the note", () => {
    for (const target of ["Plan#Goals", "Plan#Goals|the goals", "Plan|label", "Plan^abc123", "Plan#"]) {
      expect(findNoteByWikilink(tree, target)?.path).toBe("Work/Old/Plan.md")
    }
  })

  it("matches a target with a folder by its path, telling same-named notes apart", () => {
    expect(findNoteByWikilink(tree, "Home/Atlas")?.path).toBe("Home/Atlas.md")
    expect(findNoteByWikilink(tree, "Work/Atlas#Intro")?.path).toBe("Work/Atlas.md")
    expect(findNoteByWikilink(tree, "work/old/plan.md")?.path).toBe("Work/Old/Plan.md")
  })

  it("matches the end of a path, as Obsidian does, and prefers an exact path to a longer one", () => {
    expect(findNoteByWikilink(tree, "Old/Plan")?.path).toBe("Work/Old/Plan.md")
    const both = [...tree, note("Old/Plan.md")]
    expect(findNoteByWikilink(both, "Old/Plan")?.path).toBe("Old/Plan.md")
  })

  it("finds nothing for a folder that does not hold the note, or for a link to a heading of the same note", () => {
    expect(findNoteByWikilink(tree, "Home/Plan")).toBeUndefined()
    expect(findNoteByWikilink(tree, "#Goals")).toBeUndefined()
    expect(findNoteByWikilink(tree, "")).toBeUndefined()
  })
})
