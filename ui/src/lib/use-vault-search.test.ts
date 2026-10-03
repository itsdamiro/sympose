// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { VaultNode } from "@/components/sympose"
import type { VaultSearchResult } from "./vault-search-api"
import { contentMatchesIn, matchesBeyond, useVaultSearch } from "./use-vault-search"

const searchVault = vi.fn()
vi.mock("./vault-search-api", () => ({ searchVault: (...a: unknown[]) => searchVault(...a) }))

const hit = (rel: string, extra: Partial<VaultSearchResult> = {}): VaultSearchResult => ({
  file_name: rel.split("/").pop()!,
  rel_path: rel,
  match_type: "content",
  line_no: 1,
  snippet: "s",
  title: "t",
  tags: [],
  index: 0,
  ...extra,
})
const note = (path: string, extra: Partial<VaultNode> = {}): VaultNode =>
  ({ type: "note", name: path.split("/").pop()!, path, ...extra }) as VaultNode

describe("contentMatchesIn / matchesBeyond", () => {
  const results = [
    hit("Notes/a.md"),
    hit("Notes/b.md", { match_type: "title" }),
    hit("Notes/c.md", { match_type: "tag", hidden: true }),
    hit("Notes.md"),
    hit("NotesExtra/d.md"),
    hit("Daily/e.md", { match_type: "title" }),
    hit("Notes"),
  ]

  it("keeps the folder's content matches and its hidden hits, and drops its title and tag hits", () => {
    expect(contentMatchesIn(results, "Notes").map((r) => r.rel_path)).toEqual(["Notes/a.md", "Notes/c.md", "Notes"])
  })

  it("does not mistake a folder whose name only starts the same for the folder", () => {
    expect(contentMatchesIn(results, "Notes").some((r) => r.rel_path === "NotesExtra/d.md")).toBe(false)
    expect(matchesBeyond(results, "Notes").map((r) => r.rel_path)).toEqual(["Notes.md", "NotesExtra/d.md", "Daily/e.md"])
  })

  it("lists everything outside the folder, of every match type", () => {
    expect(matchesBeyond(results, "Daily").length).toBe(6)
  })

  it("treats a root note as its own folder in view", () => {
    expect(contentMatchesIn([hit("README.md")], "README.md").length).toBe(1)
    expect(matchesBeyond([hit("README.md")], "README.md")).toEqual([])
  })
})

function setup(over: Partial<Parameters<typeof useVaultSearch>[0]> = {}) {
  const base = {
    panelNodes: [note("Notes/Apple.md"), note("Notes/Pear.md")],
    resolvedActive: "Notes",
    isSentinel: false,
    activePersona: "samantha",
    vaultRefreshKey: 0,
    ...over,
  }
  return renderHook((p) => useVaultSearch(p), { initialProps: base })
}

describe("useVaultSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    searchVault.mockReset()
    searchVault.mockResolvedValue([])
  })
  afterEach(() => vi.useRealTimers())

  it("shows the whole folder, and asks the server nothing, while the field is empty", async () => {
    const { result } = setup()
    expect(result.current.searchedPanelNodes.map((n) => n.path)).toEqual(["Notes/Apple.md", "Notes/Pear.md"])
    await act(async () => void vi.advanceTimersByTime(1000))
    expect(searchVault).not.toHaveBeenCalled()
  })

  it("filters the folder in view at once from the tree already fetched", () => {
    const { result } = setup()
    act(() => result.current.setVaultSearch("app"))
    expect(result.current.searchedPanelNodes.map((n) => n.path)).toEqual(["Notes/Apple.md"])
    expect(result.current.vaultSearchQuery).toBe("app")
  })

  it("trims the query, and treats a blank one as no search", async () => {
    const { result } = setup()
    act(() => result.current.setVaultSearch("   "))
    expect(result.current.vaultSearchQuery).toBe("")
    expect(result.current.searchedPanelNodes.length).toBe(2)
    await act(async () => void vi.advanceTimersByTime(1000))
    expect(searchVault).not.toHaveBeenCalled()
  })

  it("asks the server once the typing has paused, not on every keystroke", async () => {
    const { result } = setup()
    act(() => result.current.setVaultSearch("a"))
    await act(async () => void vi.advanceTimersByTime(200))
    act(() => result.current.setVaultSearch("ap"))
    await act(async () => void vi.advanceTimersByTime(200))
    expect(searchVault).not.toHaveBeenCalled()
    await act(async () => void vi.advanceTimersByTime(60))
    expect(searchVault).toHaveBeenCalledTimes(1)
    expect(searchVault.mock.calls[0].slice(0, 2)).toEqual(["ap", "samantha"])
  })

  it("splits the answer into the folder's content matches and the rest", async () => {
    searchVault.mockResolvedValue([hit("Notes/a.md"), hit("Notes/b.md", { match_type: "title" }), hit("Daily/c.md", { match_type: "tag" })])
    const { result } = setup()
    act(() => result.current.setVaultSearch("x"))
    await act(async () => void vi.advanceTimersByTime(300))
    expect(result.current.contentMatches.map((r) => r.rel_path)).toEqual(["Notes/a.md"])
    expect(result.current.beyondFolderMatches.map((r) => r.rel_path)).toEqual(["Daily/c.md"])
  })

  it("re-splits the answer for another folder without asking again", async () => {
    searchVault.mockResolvedValue([hit("Notes/a.md"), hit("Daily/c.md")])
    const { result, rerender } = setup()
    act(() => result.current.setVaultSearch("x"))
    await act(async () => void vi.advanceTimersByTime(300))
    rerender({ panelNodes: [], resolvedActive: "Daily", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 0 })
    expect(result.current.contentMatches.map((r) => r.rel_path)).toEqual(["Daily/c.md"])
    expect(result.current.beyondFolderMatches.map((r) => r.rel_path)).toEqual(["Notes/a.md"])
    expect(searchVault).toHaveBeenCalledTimes(1)
  })

  it("never shows an answer for an earlier query, whatever order the answers arrive in", async () => {
    let releaseFirst: (v: VaultSearchResult[]) => void = () => {}
    searchVault.mockImplementationOnce(() => new Promise((r) => (releaseFirst = r)))
    searchVault.mockResolvedValueOnce([hit("Notes/new.md")])
    const { result } = setup()
    act(() => result.current.setVaultSearch("first"))
    await act(async () => void vi.advanceTimersByTime(300))
    act(() => result.current.setVaultSearch("second"))
    await act(async () => void vi.advanceTimersByTime(300))
    expect(result.current.contentMatches.map((r) => r.rel_path)).toEqual(["Notes/new.md"])
    await act(async () => releaseFirst([hit("Notes/old.md")]))
    expect(result.current.contentMatches.map((r) => r.rel_path)).toEqual(["Notes/new.md"])
  })

  it("aborts the request that a new query supersedes", async () => {
    const { result } = setup()
    act(() => result.current.setVaultSearch("first"))
    await act(async () => void vi.advanceTimersByTime(300))
    const signal = searchVault.mock.calls[0][2] as AbortSignal
    expect(signal.aborted).toBe(false)
    act(() => result.current.setVaultSearch("second"))
    expect(signal.aborted).toBe(true)
  })

  it("shows no results for a stale key: another persona, another refresh, a cleared query", async () => {
    searchVault.mockResolvedValue([hit("Notes/a.md")])
    const { result, rerender } = setup()
    act(() => result.current.setVaultSearch("x"))
    await act(async () => void vi.advanceTimersByTime(300))
    expect(result.current.contentMatches.length).toBe(1)
    searchVault.mockResolvedValue([])
    rerender({ panelNodes: [], resolvedActive: "Notes", isSentinel: false, activePersona: "other", vaultRefreshKey: 0 })
    expect(result.current.contentMatches.length).toBe(0)
    rerender({ panelNodes: [], resolvedActive: "Notes", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 0 })
    expect(result.current.contentMatches.length).toBe(1) // the key matches the stored answer again
    rerender({ panelNodes: [], resolvedActive: "Notes", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 1 })
    expect(result.current.contentMatches.length).toBe(0)
  })

  it("asks again after a vault refresh, and for another persona", async () => {
    const { result, rerender } = setup()
    act(() => result.current.setVaultSearch("x"))
    await act(async () => void vi.advanceTimersByTime(300))
    rerender({ panelNodes: [], resolvedActive: "Notes", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 1 })
    await act(async () => void vi.advanceTimersByTime(300))
    rerender({ panelNodes: [], resolvedActive: "Notes", isSentinel: false, activePersona: "other", vaultRefreshKey: 1 })
    await act(async () => void vi.advanceTimersByTime(300))
    expect(searchVault).toHaveBeenCalledTimes(3)
    expect(searchVault.mock.calls[2][1]).toBe("other")
  })

  it("does not ask the server from Settings, Persona or the Bin", async () => {
    const { result } = setup({ isSentinel: true })
    act(() => result.current.setVaultSearch("x"))
    await act(async () => void vi.advanceTimersByTime(1000))
    expect(searchVault).not.toHaveBeenCalled()
  })

  it("opens and closes the field, and closing it clears the query", () => {
    const { result } = setup()
    expect(result.current.searchOpen).toBe(false)
    act(() => result.current.setSearchOpen(true))
    act(() => result.current.setVaultSearch("abc"))
    act(() => result.current.closeSearch())
    expect(result.current.searchOpen).toBe(false)
    expect(result.current.vaultSearch).toBe("")
  })

  it("focuses the field when it opens", () => {
    const { result } = setup()
    const input = document.createElement("input")
    document.body.appendChild(input)
    result.current.searchInputRef.current = input
    act(() => result.current.setSearchOpen(true))
    expect(document.activeElement).toBe(input)
    input.remove()
  })

  it("does not pull focus back to the field when it closes", () => {
    const { result } = setup()
    const input = document.createElement("input")
    const other = document.createElement("button")
    document.body.append(input, other)
    result.current.searchInputRef.current = input
    act(() => result.current.setSearchOpen(true))
    other.focus()
    act(() => result.current.closeSearch())
    expect(document.activeElement).toBe(other)
    input.remove()
    other.remove()
  })

  it("keeps the same result arrays while nothing changes", async () => {
    const { result, rerender } = setup()
    const first = result.current
    rerender({ panelNodes: first.searchedPanelNodes, resolvedActive: "Notes", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 0 })
    expect(result.current.contentMatches).toBe(first.contentMatches)
    expect(result.current.beyondFolderMatches).toBe(first.beyondFolderMatches)
  })

  it("keeps a query from one folder to the next, and clears it when the kind of page changes", () => {
    const { result, rerender } = setup()
    act(() => {
      result.current.setSearchOpen(true)
      result.current.setVaultSearch("pear")
    })
    const props = { panelNodes: [note("Daily/x.md")], resolvedActive: "Daily", isSentinel: false, activePersona: "samantha", vaultRefreshKey: 0 }
    rerender({ ...props, scope: "vault" })
    expect(result.current.vaultSearch).toBe("pear") // folder to folder: the query stays

    rerender({ ...props, scope: "settings" })
    expect(result.current.vaultSearch).toBe("")
    expect(result.current.searchOpen).toBe(false)

    act(() => result.current.setVaultSearch("autosave"))
    rerender({ ...props, scope: "conversations" })
    expect(result.current.vaultSearch).toBe("") // a settings query must not filter the conversations
  })
})
