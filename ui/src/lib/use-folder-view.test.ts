// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { useFolderView } from "./use-folder-view"

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const folder = (path: string, children: VaultNode[]): VaultNode =>
  ({ type: "folder", name: path.split("/").pop()!, path, children }) as VaultNode

const daily = folder("Daily", [folder("Daily/2026", [note("Daily/2026/Today.md")]), note("Daily/Plan.md")])
const code = folder("Code", [note("Code/Snippet.md")])
const tree = [daily, code, note("README.md")]

function view(over: Partial<Parameters<typeof useFolderView>[0]> = {}) {
  return renderHook((p) => useFolderView(p), {
    initialProps: { vaultTree: tree, resolvedActive: "Daily", pinnedPaths: [], recentPaths: [], ...over },
  })
}

describe("useFolderView: what is in view", () => {
  it("lists a folder's own contents, not the folder itself", () => {
    const { result } = view()
    expect(result.current.activeNode?.path).toBe("Daily")
    expect(result.current.panelNodes.map((n) => n.path)).toEqual(["Daily/2026", "Daily/Plan.md"])
    expect(result.current.activeRootFolder?.path).toBe("Daily")
  })

  it("lists a root note as the only thing in view, and is not a folder", () => {
    const { result } = view({ resolvedActive: "README.md" })
    expect(result.current.panelNodes.map((n) => n.path)).toEqual(["README.md"])
    expect(result.current.activeRootFolder).toBeUndefined()
  })

  it("lists nothing for a section that is not in the tree (Settings, the Bin, a folder that is gone)", () => {
    for (const id of ["__settings__", "Gone", ""]) {
      const { result } = view({ resolvedActive: id })
      expect(result.current.activeNode).toBeUndefined()
      expect(result.current.panelNodes).toEqual([])
      expect(result.current.activeRootFolder).toBeUndefined()
    }
  })

  it("lists an empty folder as empty", () => {
    const { result } = view({ vaultTree: [folder("Empty", [])], resolvedActive: "Empty" })
    expect(result.current.panelNodes).toEqual([])
    const noChildren = { type: "folder", name: "Bare", path: "Bare" } as VaultNode
    expect(view({ vaultTree: [noChildren], resolvedActive: "Bare" }).result.current.panelNodes).toEqual([])
  })

  it("keeps the same list while the tree and the section are unchanged", () => {
    const { result, rerender } = view()
    const first = result.current.panelNodes
    rerender({ vaultTree: tree, resolvedActive: "Daily", pinnedPaths: [], recentPaths: [] })
    expect(result.current.panelNodes).toBe(first)
  })
})

describe("useFolderView: following the tree", () => {
  it("lists the new contents when the tree is fetched again or another section is picked", () => {
    const { result, rerender } = view()
    rerender({ vaultTree: [folder("Daily", [note("Daily/New.md")]), code], resolvedActive: "Daily", pinnedPaths: [], recentPaths: [] })
    expect(result.current.panelNodes.map((n) => n.path)).toEqual(["Daily/New.md"])
    rerender({ vaultTree: [folder("Daily", [note("Daily/New.md")]), code], resolvedActive: "Code", pinnedPaths: [], recentPaths: [] })
    expect(result.current.panelNodes.map((n) => n.path)).toEqual(["Code/Snippet.md"])
  })
})

describe("useFolderView: pinned", () => {
  it("shows the notes pinned anywhere under the folder in view, however deep", () => {
    const { result } = view({ pinnedPaths: ["Daily/2026/Today.md", "Daily/Plan.md"] })
    expect(result.current.pinnedNodes.map((n) => n.path)).toEqual(["Daily/2026/Today.md", "Daily/Plan.md"])
  })

  it("keeps another root folder's pins out", () => {
    const { result } = view({ pinnedPaths: ["Code/Snippet.md", "Daily/Plan.md"] })
    expect(result.current.pinnedNodes.map((n) => n.path)).toEqual(["Daily/Plan.md"])
  })

  it("does not mistake a folder whose name only starts the same", () => {
    const tree2 = [folder("Daily", [note("Daily/a.md")]), folder("DailyExtra", [note("DailyExtra/b.md")])]
    const { result } = view({ vaultTree: tree2, pinnedPaths: ["DailyExtra/b.md"] })
    expect(result.current.pinnedNodes).toEqual([])
  })

  it("drops a pin that no longer resolves, and a pin that is a folder", () => {
    const { result } = view({ pinnedPaths: ["Daily/Gone.md", "Daily/2026", "Daily/Plan.md"] })
    expect(result.current.pinnedNodes.map((n) => n.path)).toEqual(["Daily/Plan.md"])
  })

  it("shows no pins for a root note or a section that is not a folder", () => {
    expect(view({ resolvedActive: "README.md", pinnedPaths: ["Daily/Plan.md"] }).result.current.pinnedNodes).toEqual([])
    expect(view({ resolvedActive: "__trash__", pinnedPaths: ["Daily/Plan.md"] }).result.current.pinnedNodes).toEqual([])
  })

  it("spells out a pinned row's path only when the root folder has nested subfolders", () => {
    expect(view({ resolvedActive: "Daily" }).result.current.pinnedShowPath).toBe(true)
    expect(view({ resolvedActive: "Code" }).result.current.pinnedShowPath).toBe(false)
    expect(view({ resolvedActive: "README.md" }).result.current.pinnedShowPath).toBe(false)
    expect(view({ resolvedActive: "Gone" }).result.current.pinnedShowPath).toBe(false)
  })
})

describe("useFolderView: recent", () => {
  it("resolves every recent path vault-wide, in the order given, whichever folder is in view", () => {
    const { result } = view({ resolvedActive: "Code", recentPaths: ["Daily/Plan.md", "README.md", "Code/Snippet.md"] })
    expect(result.current.recentNodes.map((n) => n.path)).toEqual(["Daily/Plan.md", "README.md", "Code/Snippet.md"])
  })

  it("drops what no longer resolves and what is a folder", () => {
    const { result } = view({ recentPaths: ["Gone.md", "Daily", "Daily/Plan.md"] })
    expect(result.current.recentNodes.map((n) => n.path)).toEqual(["Daily/Plan.md"])
  })

  it("lists recents even for a section that is not a folder", () => {
    const { result } = view({ resolvedActive: "__settings__", recentPaths: ["Daily/Plan.md"] })
    expect(result.current.recentNodes.map((n) => n.path)).toEqual(["Daily/Plan.md"])
  })
})
