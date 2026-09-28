import { describe, expect, it } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { isHiddenByUser, pruneHidden } from "./prune-hidden"

const note = (path: string, hidden?: VaultNode["hidden"]): VaultNode => ({
  name: path.split("/").pop()!,
  path,
  type: "note",
  ...(hidden ? { hidden } : {}),
})
const folder = (
  path: string,
  children: VaultNode[],
  hidden?: VaultNode["hidden"]
): VaultNode => ({
  name: path.split("/").pop()!,
  path,
  type: "folder",
  children,
  ...(hidden ? { hidden } : {}),
})

const tree: VaultNode[] = [
  folder("Drafts", [note("Drafts/One.md", "user")], "user"),
  folder("Journal", [
    note("Journal/Journal.md", "definition"),
    note("Journal/Secret.md", "user"),
    note("Journal/Open.md"),
  ]),
  note("Loose.md"),
]

describe("pruneHidden", () => {
  it("leaves out whatever is marked, at any depth, and keeps the rest in order", () => {
    const shown = pruneHidden(tree)
    expect(shown.map((n) => n.path)).toEqual(["Journal", "Loose.md"])
    expect(shown[0].children?.map((n) => n.path)).toEqual(["Journal/Open.md"])
  })

  it("leaves a tree with nothing marked as it is", () => {
    const plain = [folder("A", [note("A/x.md")]), note("b.md")]
    expect(pruneHidden(plain)).toEqual(plain)
  })

  it("does not change the tree it is given", () => {
    pruneHidden(tree)
    expect(tree[1].children).toHaveLength(3)
  })

  it("keeps an empty folder that is not itself hidden", () => {
    expect(pruneHidden([folder("Empty", [])]).map((n) => n.path)).toEqual(["Empty"])
  })
})

describe("isHiddenByUser", () => {
  it("is true for a note or folder the user hid, and for a note under one", () => {
    expect(isHiddenByUser(tree, "Journal/Secret.md")).toBe(true)
    expect(isHiddenByUser(tree, "Drafts")).toBe(true)
    expect(isHiddenByUser(tree, "Drafts/One.md")).toBe(true)
  })

  it("is false for a definition note (not the user's doing), a visible note, and a path the tree lacks", () => {
    expect(isHiddenByUser(tree, "Journal/Journal.md")).toBe(false)
    expect(isHiddenByUser(tree, "Journal/Open.md")).toBe(false)
    expect(isHiddenByUser(tree, "Nowhere.md")).toBe(false)
    expect(isHiddenByUser(tree, undefined)).toBe(false)
  })
})
