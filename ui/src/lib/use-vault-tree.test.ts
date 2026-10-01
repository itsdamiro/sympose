// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { VaultNode } from "@/components/sympose"
import type { HiddenResult } from "./vault-hidden-api"
import { useVaultTree } from "./use-vault-tree"

const fetchVaultTree = vi.fn()
const fetchHidden = vi.fn()
const hidePath = vi.fn()
const unhidePath = vi.fn()
const notify = { error: vi.fn(), success: vi.fn() }
vi.mock("./vault-tree-api", () => ({ fetchVaultTree: (...a: unknown[]) => fetchVaultTree(...a) }))
vi.mock("./vault-hidden-api", () => ({
  NO_HIDDEN: { hidden: [], showDefinitionNotes: false },
  fetchHidden: () => fetchHidden(),
  hidePath: (...a: unknown[]) => hidePath(...a),
  unhidePath: (...a: unknown[]) => unhidePath(...a),
}))
vi.mock("./notify", () => ({ notify: { error: (...a: unknown[]) => notify.error(...a), success: (...a: unknown[]) => notify.success(...a) } }))

const note = (path: string, extra: Partial<VaultNode> = {}): VaultNode =>
  ({ type: "note", name: path.split("/").pop()!, path, ...extra }) as VaultNode
const state = (hidden: string[]) => ({ hidden, showDefinitionNotes: false })
const ok = (hidden: string[]): HiddenResult => ({ ok: true, state: state(hidden) })

function setup(initial = { activePersona: "samantha", vaultRefreshKey: 0 }) {
  const refreshVault = vi.fn()
  const hook = renderHook((p) => useVaultTree({ ...p, refreshVault }), { initialProps: initial })
  return { refreshVault, ...hook }
}

beforeEach(() => {
  vi.resetAllMocks()
  fetchHidden.mockResolvedValue(state([]))
  fetchVaultTree.mockResolvedValue({ tree: [note("a.md")], vaultName: "My vault" })
})

describe("useVaultTree: loading", () => {
  it("starts empty, then holds the tree and the vault's name for the persona", async () => {
    const { result } = setup()
    expect(result.current.vaultTree).toEqual([])
    expect(result.current.vaultName).toBeNull()
    await waitFor(() => expect(result.current.vaultName).toBe("My vault"))
    expect(result.current.vaultTree.map((n) => n.path)).toEqual(["a.md"])
    expect(fetchVaultTree).toHaveBeenCalledWith("samantha")
  })

  it("leaves what the user hid out of the tree they see, but still knows it is hidden", async () => {
    fetchVaultTree.mockResolvedValue({
      tree: [note("a.md"), note("secret.md", { hidden: "user" }), note("def.md", { hidden: "definition" })],
      vaultName: "v",
    })
    const { result } = setup()
    await waitFor(() => expect(result.current.vaultName).toBe("v"))
    expect(result.current.vaultTree.map((n) => n.path)).toEqual(["a.md"])
    expect(result.current.isHidden("secret.md")).toBe(true)
    expect(result.current.isHidden("a.md")).toBe(false)
    expect(result.current.isHidden("def.md")).toBe(false) // a definition note is not "hidden by the user"
    expect(result.current.isHidden(undefined)).toBe(false)
  })

  it("loads the hidden list", async () => {
    fetchHidden.mockResolvedValue(state(["Old"]))
    const { result } = setup()
    await waitFor(() => expect(result.current.hiddenState.hidden).toEqual(["Old"]))
  })

  it("fetches again for a new persona and for a refresh, not otherwise", async () => {
    const { rerender } = setup()
    await waitFor(() => expect(fetchVaultTree).toHaveBeenCalledTimes(1))
    rerender({ activePersona: "samantha", vaultRefreshKey: 0 })
    expect(fetchVaultTree).toHaveBeenCalledTimes(1)
    rerender({ activePersona: "samantha", vaultRefreshKey: 1 })
    await waitFor(() => expect(fetchVaultTree).toHaveBeenCalledTimes(2))
    expect(fetchHidden).toHaveBeenCalledTimes(2)
    rerender({ activePersona: "other", vaultRefreshKey: 1 })
    await waitFor(() => expect(fetchVaultTree).toHaveBeenCalledTimes(3))
    expect(fetchVaultTree).toHaveBeenLastCalledWith("other")
    expect(fetchHidden).toHaveBeenCalledTimes(2) // the hidden list is the vault's, not the persona's
  })

  it("keeps the tree that is shown when a refresh fails, with one notice", async () => {
    const { result, rerender } = setup()
    await waitFor(() => expect(result.current.vaultName).toBe("My vault"))
    fetchVaultTree.mockResolvedValue(null)
    rerender({ activePersona: "samantha", vaultRefreshKey: 1 })
    await waitFor(() => expect(notify.error).toHaveBeenCalledTimes(1))
    expect(notify.error).toHaveBeenCalledWith(expect.stringContaining("Couldn't load the vault"), { id: "vault-tree" })
    expect(result.current.vaultTree.map((n) => n.path)).toEqual(["a.md"])
    expect(result.current.vaultName).toBe("My vault")
  })

  it("drops the previous persona's tree and name when the new persona's fetch fails", async () => {
    const { result, rerender } = setup()
    await waitFor(() => expect(result.current.vaultName).toBe("My vault"))
    fetchVaultTree.mockResolvedValue(null)
    rerender({ activePersona: "other", vaultRefreshKey: 0 })
    await waitFor(() => expect(result.current.vaultTree).toEqual([]))
    expect(result.current.vaultName).toBeNull()
    expect(notify.error).toHaveBeenCalledTimes(1)
  })

  it("does not apply an answer that arrives after the persona changed", async () => {
    let release: (v: unknown) => void = () => {}
    fetchVaultTree.mockImplementationOnce(() => new Promise((r) => (release = r)))
    const { result, rerender } = setup()
    fetchVaultTree.mockResolvedValue({ tree: [note("new.md")], vaultName: "New" })
    rerender({ activePersona: "other", vaultRefreshKey: 0 })
    await waitFor(() => expect(result.current.vaultName).toBe("New"))
    await act(async () => release({ tree: [note("stale.md")], vaultName: "Stale" }))
    expect(result.current.vaultName).toBe("New")
    expect(result.current.vaultTree.map((n) => n.path)).toEqual(["new.md"])
  })
})

describe("useVaultTree: a switch and then a failure", () => {
  it("keeps the new persona's tree when a later refresh fails, because it was loaded for that persona", async () => {
    const { result, rerender } = setup()
    await waitFor(() => expect(result.current.vaultName).toBe("My vault"))
    fetchVaultTree.mockResolvedValue({ tree: [note("b.md")], vaultName: "B" })
    rerender({ activePersona: "other", vaultRefreshKey: 0 })
    await waitFor(() => expect(result.current.vaultName).toBe("B"))
    fetchVaultTree.mockResolvedValue(null)
    rerender({ activePersona: "other", vaultRefreshKey: 1 })
    await waitFor(() => expect(notify.error).toHaveBeenCalledTimes(1))
    expect(result.current.vaultName).toBe("B")
    expect(result.current.vaultTree.map((n) => n.path)).toEqual(["b.md"])
  })

  it("does not apply a hidden list that arrives after a newer one was asked for", async () => {
    let release: (v: unknown) => void = () => {}
    fetchHidden.mockImplementationOnce(() => new Promise((r) => (release = r)))
    const { result, rerender } = setup()
    fetchHidden.mockResolvedValue(state(["Newer"]))
    rerender({ activePersona: "samantha", vaultRefreshKey: 1 })
    await waitFor(() => expect(result.current.hiddenState.hidden).toEqual(["Newer"]))
    await act(async () => release(state(["Stale"])))
    expect(result.current.hiddenState.hidden).toEqual(["Newer"])
  })
})

describe("useVaultTree: hiding", () => {
  it("hides a path, keeps the answer, refreshes the vault and says how to get it back", async () => {
    hidePath.mockResolvedValue(ok(["Notes"]))
    const { result, refreshVault } = setup()
    await act(async () => result.current.hideFromView("Notes"))
    expect(hidePath).toHaveBeenCalledWith("Notes")
    expect(result.current.hiddenState.hidden).toEqual(["Notes"])
    expect(refreshVault).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Hidden from view — Settings brings it back")
  })

  it("reports a failed hide and changes nothing", async () => {
    hidePath.mockResolvedValue({ ok: false, error: "nope" })
    const { result, refreshVault } = setup()
    await act(async () => result.current.hideFromView("Notes"))
    expect(notify.error).toHaveBeenCalledWith("nope")
    expect(notify.success).not.toHaveBeenCalled()
    expect(refreshVault).not.toHaveBeenCalled()
    expect(result.current.hiddenState.hidden).toEqual([])
  })

  it("unhides one path, or every entry that hid a search hit one after another, with no message", async () => {
    unhidePath.mockResolvedValueOnce(ok(["B"])).mockResolvedValueOnce(ok([]))
    const { result, refreshVault } = setup()
    await act(async () => result.current.unhideFromView(["A", "B"]))
    expect(unhidePath.mock.calls).toEqual([["A"], ["B"]])
    expect(result.current.hiddenState.hidden).toEqual([])
    expect(refreshVault).toHaveBeenCalledTimes(1)
    expect(notify.success).not.toHaveBeenCalled()
  })

  it("stops at the first entry that fails to unhide and reports it", async () => {
    unhidePath.mockResolvedValueOnce({ ok: false, error: "boom" })
    const { result, refreshVault } = setup()
    await act(async () => result.current.unhideFromView(["A", "B"]))
    expect(unhidePath).toHaveBeenCalledTimes(1)
    expect(notify.error).toHaveBeenCalledWith("boom")
    expect(refreshVault).not.toHaveBeenCalled()
  })

  it("applies the answer of any other hidden-list change, such as the definition-notes switch", async () => {
    const { result, refreshVault } = setup()
    await act(async () =>
      result.current.changeHidden(Promise.resolve({ ok: true, state: { hidden: [], showDefinitionNotes: true } }))
    )
    expect(result.current.hiddenState.showDefinitionNotes).toBe(true)
    expect(refreshVault).toHaveBeenCalledTimes(1)
  })
})
