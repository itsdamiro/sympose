// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook, waitFor } from "@testing-library/react"

const api = vi.hoisted(() => ({ planFolderMove: vi.fn(), moveVaultFolder: vi.fn() }))
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }))
vi.mock("@/lib/vault-folder-move-api", () => api)
vi.mock("@/lib/notify", () => ({ notify }))

import { useFolderMove } from "./use-folder-move"

const plan = (over = {}) => ({ ok: true, path: "People", destination: "Archive", newPath: "Archive/People", clash: false, noteClashes: [], reach: [], definition: null, ...over })
const moved = (over = {}) => ({ ok: true, path: "Archive/People", detail: "Moved to `Archive/People`", personas: [], personasUnchanged: [], relinkFailed: 0, ...over })

function setup(over: { selectedNote?: string; before?: () => Promise<boolean> } = {}) {
  const after = vi.fn()
  const noteRenamedAway = vi.fn()
  const refreshVault = vi.fn()
  const before = over.before ?? (() => Promise.resolve(true))
  const hook = renderHook(() => useFolderMove({ persona: "samantha", selectedNote: over.selectedNote, before, after, noteRenamedAway, refreshVault }))
  return { after, noteRenamedAway, refreshVault, ...hook }
}

/** Answer the prompt that is waiting, once it is up. */
async function answer(result: ReturnType<typeof setup>["result"], kind: string, value: unknown) {
  await waitFor(() => expect(result.current.ask?.kind).toBe(kind))
  await act(async () => (result.current.ask!.resolve as (v: unknown) => void)(value))
}

beforeEach(() => {
  api.planFolderMove.mockResolvedValue(plan())
  api.moveVaultFolder.mockResolvedValue(moved())
})
afterEach(() => vi.clearAllMocks())

describe("moving a folder (docs/decisions/074)", () => {
  it("with nothing to ask, plans then moves, and everything that held the old path follows", async () => {
    const { result, after, refreshVault } = setup()

    await act(async () => result.current.moveFolder("People", "Archive"))

    expect(api.planFolderMove).toHaveBeenCalledWith("People", "Archive", "samantha")
    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Archive", "samantha", {})
    expect(after).toHaveBeenCalledWith("People", "Archive/People")
    expect(refreshVault).toHaveBeenCalled()
    expect(notify.success).toHaveBeenCalledWith("Moved to `Archive/People`")
    expect(result.current.ask).toBeNull()
  })

  it("is held back, and asks the server nothing, when the open note could not be saved", async () => {
    const { result } = setup({ before: () => Promise.resolve(false) })

    await act(async () => result.current.moveFolder("People", "Archive"))

    expect(api.planFolderMove).not.toHaveBeenCalled()
    expect(api.moveVaultFolder).not.toHaveBeenCalled()
  })

  it("shows the server's refusal of the plan and moves nothing", async () => {
    api.planFolderMove.mockResolvedValue({ ok: false, error: "A folder cannot go into itself." })
    const { result, after } = setup()

    await act(async () => result.current.moveFolder("People", "People/Sub"))

    expect(notify.error).toHaveBeenCalledWith("A folder cannot go into itself.")
    expect(api.moveVaultFolder).not.toHaveBeenCalled()
    expect(after).not.toHaveBeenCalled()
  })

  it("shows the server's refusal of the move and follows nothing", async () => {
    api.moveVaultFolder.mockResolvedValue({ ok: false, error: "confirm to move anyway" })
    const { result, after } = setup()

    await act(async () => result.current.moveFolder("People", "Archive"))

    expect(notify.error).toHaveBeenCalledWith("confirm to move anyway")
    expect(after).not.toHaveBeenCalled()
  })

  it("warns, rather than reports success, when some links could not be rewritten", async () => {
    api.moveVaultFolder.mockResolvedValue(moved({ relinkFailed: 2, detail: "Moved (2 relinks failed)" }))
    const { result } = setup()

    await act(async () => result.current.moveFolder("People", "Archive"))

    expect(notify.warning).toHaveBeenCalledWith("Moved (2 relinks failed)")
    expect(notify.success).not.toHaveBeenCalled()
  })

  it("asks first when a folder of that name is there, and moves under the new name the user gives", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { newName: "Friends" })
    await act(() => done)

    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Archive", "samantha", { ifExists: "rename", newName: "Friends" })
  })

  it("names the folder and the place in the clash prompt, taking the folder's own name from a nested path", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true }))
    const { result } = setup()

    act(() => void result.current.moveFolder("Projects/People", "Archive"))

    await waitFor(() => expect(result.current.ask).toMatchObject({ kind: "clash", name: "People", destination: "Archive" }))
  })

  it("merges without more questions when no file is in both", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { merge: true })
    await act(() => done)

    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Archive", "samantha", { ifExists: "merge" })
  })

  it("lists the files in both in one prompt on a merge, and renames the incoming ones when the user agrees", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true, noteClashes: ["Anna.md", "Sub/Ben.md"] }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { merge: true })
    await waitFor(() => expect(result.current.ask).toMatchObject({ kind: "notes", files: ["Anna.md", "Sub/Ben.md"] }))
    await answer(result, "notes", true)
    await act(() => done)

    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Archive", "samantha", { ifExists: "merge", renameClashingNotes: true })
  })

  it("does not ask about files in both when the folder goes in under another name: nothing clashes then", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true, noteClashes: ["Anna.md"] }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { newName: "Friends" })
    await act(() => done)

    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Archive", "samantha", { ifExists: "rename", newName: "Friends" })
  })

  it.each([
    ["the clash prompt", null],
    ["the list of files in both", true],
  ])("changes nothing when %s is cancelled", async (_which, first) => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true, noteClashes: first ? ["Anna.md"] : [] }))
    const { result, after } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    if (first) {
      await answer(result, "clash", { merge: true })
      await answer(result, "notes", false)
    } else {
      await answer(result, "clash", null)
    }
    await act(() => done)

    expect(api.moveVaultFolder).not.toHaveBeenCalled()
    expect(after).not.toHaveBeenCalled()
  })

  it("asks before a move that changes what a persona can read, and sends the yes", async () => {
    const reach = [{ handle: "grace", name: "Grace", gains: 12, loses: 0 }]
    api.planFolderMove.mockResolvedValue(plan({ reach }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Other")
    })
    await waitFor(() => expect(result.current.ask).toMatchObject({ kind: "reach", reach }))
    expect(api.moveVaultFolder).not.toHaveBeenCalled()
    await answer(result, "reach", true)
    await act(() => done)

    expect(api.moveVaultFolder).toHaveBeenCalledWith("People", "Other", "samantha", { confirmReach: true })
  })

  it("does not move when the reach question is declined", async () => {
    api.planFolderMove.mockResolvedValue(plan({ reach: [{ handle: "g", name: "Grace", gains: 1, loses: 0 }] }))
    const { result } = setup()

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Other")
    })
    await answer(result, "reach", false)
    await act(() => done)

    expect(api.moveVaultFolder).not.toHaveBeenCalled()
  })

  it("closes the open note when a merge renamed it, so the editor does not land on the note that was there", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true, noteClashes: ["Anna.md"] }))
    const { result, noteRenamedAway } = setup({ selectedNote: "People/Anna.md" })

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { merge: true })
    await answer(result, "notes", true)
    await act(() => done)

    expect(noteRenamedAway).toHaveBeenCalled()
  })

  it("leaves the open note open when it was not one of those renamed", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true, noteClashes: ["Anna.md"] }))
    const { result, noteRenamedAway } = setup({ selectedNote: "People/Ben.md" })

    let done!: Promise<void>
    act(() => {
      done = result.current.moveFolder("People", "Archive")
    })
    await answer(result, "clash", { merge: true })
    await answer(result, "notes", true)
    await act(() => done)

    expect(noteRenamedAway).not.toHaveBeenCalled()
  })

  it("ignores a second drop while the first is waiting on the user", async () => {
    api.planFolderMove.mockResolvedValue(plan({ clash: true }))
    const { result } = setup()

    let first!: Promise<void>
    act(() => {
      first = result.current.moveFolder("People", "Archive")
    })
    await waitFor(() => expect(result.current.ask).not.toBeNull())
    await act(async () => result.current.moveFolder("Other", "Archive"))

    expect(api.planFolderMove).toHaveBeenCalledTimes(1)
    await answer(result, "clash", null)
    await act(() => first)
  })
})
