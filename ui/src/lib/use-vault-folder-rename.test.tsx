// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook } from "@testing-library/react"

const api = vi.hoisted(() => ({ renameVaultFolder: vi.fn(), renameVaultNote: vi.fn(), deleteVaultNote: vi.fn() }))
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
vi.mock("@/lib/vault-note-api", () => api)
vi.mock("@/lib/notify", () => ({ notify }))

import { useVaultNoteActions } from "./use-vault-note-actions"

const ok = (over = {}) => ({ ok: true, path: "Team", detail: "Renamed to `Team`", personas: [], personasUnchanged: [], relinkFailed: 0, ...over })

function setup(over: { onRenamed?: (p: string) => void; beforeRename?: () => Promise<boolean> } = {}) {
  const onRenamed = over.onRenamed ?? vi.fn()
  const hook = renderHook(() =>
    useVaultNoteActions({ kind: "folder", path: "People", persona: "samantha", stem: "People", onRenamed, onDeleted: vi.fn(), beforeRename: over.beforeRename })
  )
  return { onRenamed, ...hook }
}

async function rename(result: ReturnType<typeof setup>["result"], text: string) {
  act(() => result.current.setPendingRename(true))
  act(() => result.current.onMenuOpenChangeComplete(false))
  act(() => result.current.setRenaming(text))
  await act(async () => result.current.handleInputKeyDown({ key: "Enter" } as React.KeyboardEvent<HTMLInputElement>))
}

beforeEach(() => {
  api.renameVaultFolder.mockResolvedValue(ok())
})
afterEach(() => vi.clearAllMocks())

describe("renaming a folder from its row (docs/decisions/073)", () => {
  it("opens the field on the folder's own name, and nothing is sent until Enter", () => {
    const { result } = setup()

    act(() => result.current.setPendingRename(true))
    act(() => result.current.onMenuOpenChangeComplete(false))

    expect(result.current.renaming).toBe("People")
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
  })

  it("renames the folder through the folder route, not the note's, and tells the caller the new path and the user what happened", async () => {
    const { result, onRenamed } = setup()

    await rename(result, "Team")

    expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "Team", "samantha")
    expect(api.renameVaultNote).not.toHaveBeenCalled()
    expect(onRenamed).toHaveBeenCalledWith("Team")
    expect(notify.success).toHaveBeenCalledWith("Renamed to `Team`")
    expect(result.current.renaming).toBeNull()
  })

  it("keeps a name that ends in .md as it is: a folder is not a note", async () => {
    const { result } = setup()

    await rename(result, "v1.md")

    expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "v1.md", "samantha")
  })

  it("strips stray slashes and spaces from the typed name", async () => {
    const { result } = setup()

    await rename(result, "  /Team/  ")

    expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "Team", "samantha")
  })

  it("does nothing for an empty or unchanged name", async () => {
    const { result } = setup()

    await rename(result, "   ")
    await rename(result, "People")

    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(result.current.renaming).toBeNull()
  })

  it("says why and stays on the field when the server refuses", async () => {
    api.renameVaultFolder.mockResolvedValue({ ok: false, error: "`Journal` is already taken in that folder." })
    const { result, onRenamed } = setup()

    await rename(result, "Journal")

    expect(notify.error).toHaveBeenCalledWith("`Journal` is already taken in that folder.")
    expect(onRenamed).not.toHaveBeenCalled()
    expect(result.current.renaming).toBe("Journal")
  })

  it("warns, instead of reporting plain success, when a persona's scope or some links could not be followed", async () => {
    api.renameVaultFolder.mockResolvedValue(ok({ detail: "Renamed to `Team` (edit the folder scope by hand for Ada)", personasUnchanged: ["Ada"] }))
    const { result } = setup()
    await rename(result, "Team")

    expect(notify.warning).toHaveBeenCalledWith("Renamed to `Team` (edit the folder scope by hand for Ada)", expect.anything())
    expect(notify.success).not.toHaveBeenCalled()

    api.renameVaultFolder.mockResolvedValue(ok({ detail: "Renamed (1 relink failed)", relinkFailed: 1 }))
    notify.warning.mockClear()
    await rename(result, "Team2")
    expect(notify.warning).toHaveBeenCalledTimes(1)
  })

  it("renames a note through the note route as before", async () => {
    api.renameVaultNote.mockResolvedValue({ ok: true, path: "B.md", detail: "Renamed to `B.md`" })
    const onRenamed = vi.fn()
    const { result } = renderHook(() => useVaultNoteActions({ path: "A.md", persona: "samantha", stem: "A", onRenamed, onDeleted: vi.fn() }))

    act(() => result.current.setPendingRename(true))
    act(() => result.current.onMenuOpenChangeComplete(false))
    act(() => result.current.setRenaming("B"))
    await act(async () => result.current.handleInputKeyDown({ key: "Enter" } as React.KeyboardEvent<HTMLInputElement>))

    expect(api.renameVaultNote).toHaveBeenCalledWith("A.md", "B", "samantha")
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
  })

  it("lets the app save what is unsaved first, and sends the rename only after that", async () => {
    const order: string[] = []
    const beforeRename = vi.fn(async () => {
      order.push("saved")
      return true
    })
    api.renameVaultFolder.mockImplementation(async () => {
      order.push("renamed")
      return ok()
    })
    const { result } = setup({ beforeRename })

    await rename(result, "Team")

    expect(order).toEqual(["saved", "renamed"])
  })

  it("cancels the rename, sending nothing, when what was unsaved could not be saved", async () => {
    const { result, onRenamed } = setup({ beforeRename: async () => false })

    await rename(result, "Team")

    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(onRenamed).not.toHaveBeenCalled()
    expect(result.current.busy).toBe(false)
  })
})

