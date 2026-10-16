// @vitest-environment jsdom
import * as React from "react"
import { render, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

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

afterEach(() => vi.unstubAllGlobals())

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

  it("asks for an image from the open note's path, and gives a new function when the note changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(
      ({ from }) => useLinkSources([], graphWith("x"), "samantha", from),
      { initialProps: { from: "Old.md" } }
    )
    const first = result.current
    rerender({ from: "Old.md" })
    expect(result.current.imageSource).toBe(first.imageSource)
    rerender({ from: "Folder/New.md" })
    expect(result.current.imageSource).not.toBe(first.imageSource)
    await result.current.imageSource("a.png", "")
    await result.current.embedSource("b.png")
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/vault/image?path=a.png&from=Folder%2FNew.md&persona=samantha",
      "/api/vault/image?path=b.png&from=Folder%2FNew.md&persona=samantha",
    ])
  })

  it("gives an editor that mounts for another note the new note's path, not the last one's", () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal("fetch", fetchMock)
    // Like <Stylo key={path}>: it takes its source at mount and asks it in a mount effect, which runs before the
    // effects of the component that called the hook.
    function Editor({ source }: { source: (src: string, alt: string) => Promise<unknown> }) {
      const mounted = React.useRef(source)
      React.useEffect(() => void mounted.current("a.png", ""), [])
      return null
    }
    function Shell({ from }: { from: string }) {
      const { imageSource } = useLinkSources([], graphWith("x"), "samantha", from)
      return React.createElement(Editor, { key: from, source: imageSource })
    }
    const { rerender } = render(React.createElement(Shell, { from: "Old.md" }))
    rerender(React.createElement(Shell, { from: "Folder/New.md" }))
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/vault/image?path=a.png&from=Old.md&persona=samantha",
      "/api/vault/image?path=a.png&from=Folder%2FNew.md&persona=samantha",
    ])
  })
})
