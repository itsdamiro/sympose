// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { buildMasterGraph } from "./nebula-graph"
import { useLinkSources } from "./use-link-sources"

const fetchVaultNote = vi.fn()
vi.mock("@/lib/vault-note-api", () => ({ fetchVaultNote: (...a: unknown[]) => fetchVaultNote(...a) }))

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const graphWith = (tag: string) =>
  buildMasterGraph({
    nodes: [{ id: "a.md", label: "a", folder: "Notes", tags: [tag], val: 1 }],
    links: [],
  })

describe("useLinkSources", () => {
  it("completes [[wikilinks]] from the live tree", () => {
    const { result } = renderHook(() => useLinkSources([note("Atlas.md")], graphWith("x"), "samantha"))
    expect(result.current.wikiLinkSource("atl")).toEqual([{ target: "Atlas" }])
  })

  it("completes #tags from the graph, never from anything bundled", () => {
    const { result } = renderHook(() => useLinkSources([], graphWith("alpha"), "samantha"))
    expect(result.current.tagSource("")).toEqual([{ tag: "alpha" }])
    expect(result.current.tagSource("zzz")).toEqual([])
  })

  it("keeps each function's identity across a refetch but reads the new tree, graph and persona", () => {
    const { result, rerender } = renderHook(
      ({ tree, graph }) => useLinkSources(tree, graph, "samantha"),
      { initialProps: { tree: [note("Old.md")], graph: graphWith("old") } }
    )
    const first = result.current
    rerender({ tree: [note("New.md")], graph: graphWith("fresh") })
    expect(result.current.wikiLinkSource).toBe(first.wikiLinkSource)
    expect(result.current.tagSource).toBe(first.tagSource)
    expect(result.current.embedSource).toBe(first.embedSource)
    expect(result.current.wikiLinkSource("")).toEqual([{ target: "New" }])
    expect(result.current.tagSource("")).toEqual([{ tag: "fresh" }])
  })

  it("resolves an embed to nothing when the note is not in the tree", async () => {
    const { result } = renderHook(() => useLinkSources([], graphWith("x"), "samantha"))
    expect(await result.current.embedSource("Missing")).toBeNull()
  })

  it("resolves an embed for the persona in use now, not the one the editor mounted with", async () => {
    fetchVaultNote.mockResolvedValue(null)
    const { result, rerender } = renderHook(
      ({ persona }) => useLinkSources([note("Atlas.md")], graphWith("x"), persona),
      { initialProps: { persona: "samantha" } }
    )
    rerender({ persona: "other" })
    await result.current.embedSource("Atlas")
    expect(fetchVaultNote).toHaveBeenCalledWith("Atlas.md", "other")
  })
})
