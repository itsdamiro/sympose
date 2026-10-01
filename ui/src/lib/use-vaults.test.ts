// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { setCookie, vaultScopedKey } from "./cookies"
import { useVaults, useVaultSwitching } from "./use-vaults"

const fetchVaults = vi.fn()
const setActiveVault = vi.fn()
const addVault = vi.fn()
const askToSaveFirst = vi.fn()
const notify = { error: vi.fn(), success: vi.fn() }
vi.mock("./vaults-api", () => ({
  fetchVaults: () => fetchVaults(),
  setActiveVault: (...a: unknown[]) => setActiveVault(...a),
  addVault: (...a: unknown[]) => addVault(...a),
}))
vi.mock("./ask-to-save-first", () => ({ askToSaveFirst: (...a: unknown[]) => askToSaveFirst(...a) }))
vi.mock("./notify", () => ({ notify: { error: (...a: unknown[]) => notify.error(...a), success: (...a: unknown[]) => notify.success(...a) } }))

const state = (active: string) => ({
  vaults: [
    { path: "/a", name: "Alpha" },
    { path: "/b", name: "Beta" },
  ],
  active,
})

beforeEach(() => {
  vi.resetAllMocks()
  askToSaveFirst.mockReturnValue(false)
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
})

describe("useVaults", () => {
  it("starts with no vaults, then holds the list the server answers with", async () => {
    fetchVaults.mockResolvedValue(state("/a"))
    const { result } = renderHook(() => useVaults())
    expect(result.current.vaultsState).toEqual({ vaults: [], active: null })
    await waitFor(() => expect(result.current.vaultsState.active).toBe("/a"))
  })

  it("does not apply an answer that arrives after it was unmounted", async () => {
    let release: (v: unknown) => void = () => {}
    fetchVaults.mockImplementation(() => new Promise((r) => (release = r)))
    const { result, unmount } = renderHook(() => useVaults())
    unmount()
    await act(async () => release(state("/a")))
    expect(result.current.vaultsState.active).toBeNull()
  })
})

function setup() {
  const setVaultsState = vi.fn()
  const setSelectedNote = vi.fn()
  const refreshVault = vi.fn()
  const hook = renderHook(() => useVaultSwitching({ setVaultsState, setSelectedNote, refreshVault }))
  return { setVaultsState, setSelectedNote, refreshVault, ...hook }
}

describe("useVaultSwitching: switch", () => {
  it("activates the vault, opens the note that vault left open, refreshes and says so", async () => {
    setCookie(vaultScopedKey("sympose:shell.note", "/b"), "Notes/B.md")
    setActiveVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result, setVaultsState, setSelectedNote, refreshVault } = setup()
    await act(async () => result.current.handleSwitchVault("/b"))
    expect(setActiveVault).toHaveBeenCalledWith("/b")
    expect(setVaultsState).toHaveBeenCalledWith(state("/b"))
    expect(setSelectedNote).toHaveBeenCalledWith("Notes/B.md")
    expect(refreshVault).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Switched to Beta")
  })

  it("opens no note when the vault left none open, rather than the previous vault's", async () => {
    setActiveVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result, setSelectedNote } = setup()
    await act(async () => result.current.handleSwitchVault("/b"))
    expect(setSelectedNote).toHaveBeenCalledWith(undefined)
  })

  it("falls back to a plain message when the vault has no name in the list", async () => {
    setActiveVault.mockResolvedValue({ ok: true, state: { vaults: [], active: "/b" } })
    const { result } = setup()
    await act(async () => result.current.handleSwitchVault("/b"))
    expect(notify.success).toHaveBeenCalledWith("Vault switched")
  })

  it("reports a failure and changes nothing", async () => {
    setActiveVault.mockResolvedValue({ ok: false, error: "no such vault" })
    const { result, setVaultsState, setSelectedNote, refreshVault } = setup()
    await act(async () => result.current.handleSwitchVault("/b"))
    expect(notify.error).toHaveBeenCalledWith("no such vault")
    expect(setVaultsState).not.toHaveBeenCalled()
    expect(setSelectedNote).not.toHaveBeenCalled()
    expect(refreshVault).not.toHaveBeenCalled()
  })

  it("asks to save an edited note first, and switches only once that is done", async () => {
    askToSaveFirst.mockReturnValue(true)
    setActiveVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result } = setup()
    await act(async () => result.current.handleSwitchVault("/b"))
    expect(setActiveVault).not.toHaveBeenCalled()
    const proceed = askToSaveFirst.mock.calls[0][0] as () => void
    await act(async () => proceed())
    await waitFor(() => expect(setActiveVault).toHaveBeenCalledWith("/b"))
  })
})

describe("useVaultSwitching: add", () => {
  it("adds and activates the vault in one go, says so by the name of the active vault, and resolves true", async () => {
    addVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result, setVaultsState, setSelectedNote, refreshVault } = setup()
    let done: boolean | undefined
    await act(async () => void (done = await result.current.handleAddVault("/b")))
    expect(addVault).toHaveBeenCalledWith("/b")
    expect(done).toBe(true)
    expect(setVaultsState).toHaveBeenCalledWith(state("/b"))
    expect(setSelectedNote).toHaveBeenCalledWith(undefined)
    expect(refreshVault).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Added Beta")
  })

  it("names the vault the server activated, not the text that was typed", async () => {
    addVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result } = setup()
    await act(async () => void (await result.current.handleAddVault("/b/")))
    expect(notify.success).toHaveBeenCalledWith("Added Beta")
  })

  it("opens the note the added vault already had open", async () => {
    setCookie(vaultScopedKey("sympose:shell.note", "/b"), "B.md")
    addVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result, setSelectedNote } = setup()
    await act(async () => void (await result.current.handleAddVault("/b")))
    expect(setSelectedNote).toHaveBeenCalledWith("B.md")
  })

  it("falls back to a plain message when the active vault has no name in the list", async () => {
    addVault.mockResolvedValue({ ok: true, state: { vaults: [], active: "/b" } })
    const { result } = setup()
    await act(async () => void (await result.current.handleAddVault("/b")))
    expect(notify.success).toHaveBeenCalledWith("Vault added")
  })

  it("resolves false on a failure, so the typed path stays, and reports it", async () => {
    addVault.mockResolvedValue({ ok: false, error: "not a folder" })
    const { result, setVaultsState } = setup()
    let done: boolean | undefined
    await act(async () => void (done = await result.current.handleAddVault("/x")))
    expect(done).toBe(false)
    expect(notify.error).toHaveBeenCalledWith("not a folder")
    expect(setVaultsState).not.toHaveBeenCalled()
  })

  it("resolves false while it asks to save first, and adds once that is done", async () => {
    askToSaveFirst.mockReturnValue(true)
    addVault.mockResolvedValue({ ok: true, state: state("/b") })
    const { result } = setup()
    let done: boolean | undefined
    await act(async () => void (done = await result.current.handleAddVault("/b")))
    expect(done).toBe(false)
    expect(addVault).not.toHaveBeenCalled()
    const proceed = askToSaveFirst.mock.calls[0][0] as () => void
    await act(async () => proceed())
    await waitFor(() => expect(addVault).toHaveBeenCalledWith("/b"))
  })
})
