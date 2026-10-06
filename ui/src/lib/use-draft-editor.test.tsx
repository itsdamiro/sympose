// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"

const changes = vi.hoisted(() => ({ fetchChanges: vi.fn(), resolveChanges: vi.fn(), saveDraftText: vi.fn() }))
const vault = vi.hoisted(() => ({ createVaultNote: vi.fn(), saveVaultNote: vi.fn() }))
const notify = vi.hoisted(() => ({ notify: { error: vi.fn(), success: vi.fn() } }))
const guard = vi.hoisted(() => ({ getUnsavedGuard: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => changes)
vi.mock("@/lib/vault-note-api", () => vault)
vi.mock("@/lib/notify", () => notify)
vi.mock("@/lib/unsaved-guard", () => guard)

import { useDraftEditor } from "./use-draft-editor"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const PATH = "Ideas/New plan.md"
const proposal = { id: "p", kind: "create", text: "# New plan\n\nHello\n", name: "New plan" }

function setup(onAccepted = vi.fn()) {
  changes.fetchChanges.mockResolvedValue({ proposals: [proposal] })
  changes.resolveChanges.mockResolvedValue({ ok: true, resolved: ["p"] })
  changes.saveDraftText.mockResolvedValue({ ok: true })
  vault.createVaultNote.mockResolvedValue({ ok: true, path: "Ideas/New plan" })
  vault.saveVaultNote.mockResolvedValue({ ok: true })
  guard.getUnsavedGuard.mockReturnValue(null)
  const hook = renderHook(() => useDraftEditor({ handle: "samantha", personaName: "Samantha", onAccepted }))
  act(() => hook.result.current.open(PATH))
  return { ...hook, onAccepted }
}

describe("useDraftEditor", () => {
  it("is not open until a draft is, and names the editor's path as never a vault path", () => {
    const { result } = renderHook(() => useDraftEditor({ handle: "samantha", personaName: "Samantha", onAccepted: () => {} }))
    expect(result.current.file).toBeUndefined()
    expect(result.current.path).toBeUndefined()
    act(() => result.current.open(PATH))
    expect(result.current.path).toBe("draft:samantha/Ideas/New plan.md")
  })

  it("loads the proposal's text as the note", async () => {
    const { result } = setup()
    expect(await result.current.file!.load("x")).toEqual({ content: proposal.text })
    expect(changes.fetchChanges).toHaveBeenCalledWith(PATH, "samantha")
  })

  it("has nothing to load when the proposal is gone", async () => {
    const { result } = setup()
    changes.fetchChanges.mockResolvedValue({ proposals: [] })
    expect(await result.current.file!.load("x")).toBeNull()
  })

  it("keeps an edit in her folder when the editor saves it, and creates nothing in the vault", async () => {
    const { result } = setup()
    expect(await result.current.file!.save("x", "# New plan\n\nEdited\n")).toEqual({ ok: true })
    expect(changes.saveDraftText).toHaveBeenCalledWith(PATH, "samantha", "# New plan\n\nEdited\n")
    expect(vault.createVaultNote).not.toHaveBeenCalled()
    expect(vault.saveVaultNote).not.toHaveBeenCalled()
    expect(await result.current.file!.load("x")).toEqual({ content: "# New plan\n\nEdited\n" })
  })

  it("says why and keeps nothing when the edit could not be kept, instead of reporting it saved", async () => {
    const { result } = setup()
    changes.saveDraftText.mockResolvedValue({ ok: false, error: "disk full" })

    expect(await result.current.file!.save("x", "# New plan\n\nEdited\n")).toEqual({ ok: false, error: "disk full" })

    expect(await result.current.file!.load("x")).toEqual({ content: proposal.text }) // the proposal's own text, not the failed edit
  })

  it("accepts: creates the file, writes the text, forgets the proposal, and says the path, in that order", async () => {
    const order: string[] = []
    const { result, onAccepted } = setup()
    vault.createVaultNote.mockImplementation(async () => (order.push("create"), { ok: true, path: "x" }))
    vault.saveVaultNote.mockImplementation(async () => (order.push("write"), { ok: true }))
    changes.resolveChanges.mockImplementation(async () => (order.push("forget"), { ok: true, resolved: [] }))
    onAccepted.mockImplementation(() => order.push("opened"))

    await act(async () => result.current.accept())

    expect(order).toEqual(["create", "write", "forget", "opened"])
    expect(vault.createVaultNote).toHaveBeenCalledWith("Ideas/New plan", "samantha")
    expect(vault.saveVaultNote).toHaveBeenCalledWith(PATH, proposal.text, "samantha")
    expect(changes.resolveChanges).toHaveBeenCalledWith(PATH, "samantha", "all")
    expect(onAccepted).toHaveBeenCalledWith(PATH)
    expect(result.current.current).toBeNull()
  })

  it("accepts the text as the user edited it, flushing the editor first", async () => {
    const { result } = setup()
    guard.getUnsavedGuard.mockReturnValue({ save: async () => (await result.current.file!.save("x", "typed just now"), true) })
    await act(async () => result.current.accept())
    expect(vault.saveVaultNote).toHaveBeenCalledWith(PATH, "typed just now", "samantha")
  })

  it("keeps the draft and says why when a note of that name exists", async () => {
    const { result, onAccepted } = setup()
    vault.createVaultNote.mockResolvedValue({ ok: false, error: "A note with that name already exists." })
    await act(async () => result.current.accept())
    expect(notify.notify.error).toHaveBeenCalledWith("A note with that name already exists.")
    expect(vault.saveVaultNote).not.toHaveBeenCalled()
    expect(changes.resolveChanges).not.toHaveBeenCalled()
    expect(onAccepted).not.toHaveBeenCalled()
    expect(result.current.current).not.toBeNull()
  })

  it("keeps the draft when the text could not be written after the file was made", async () => {
    const { result, onAccepted } = setup()
    vault.saveVaultNote.mockResolvedValue({ ok: false, error: "disk full" })
    await act(async () => result.current.accept())
    expect(notify.notify.error).toHaveBeenCalledWith(expect.stringContaining("disk full"))
    expect(changes.resolveChanges).not.toHaveBeenCalled()
    expect(onAccepted).not.toHaveBeenCalled()
  })

  it("declines: forgets the proposal, creates nothing, and closes", async () => {
    const { result, onAccepted } = setup()
    await act(async () => result.current.decline())
    expect(changes.resolveChanges).toHaveBeenCalledWith(PATH, "samantha", "all")
    expect(vault.createVaultNote).not.toHaveBeenCalled()
    expect(onAccepted).not.toHaveBeenCalled()
    expect(result.current.current).toBeNull()
  })

  it("flushes the editor before it closes on a decline, so an unsaved edit is not sent to a path that is not a note", async () => {
    const { result } = setup()
    const save = vi.fn().mockResolvedValue(true)
    guard.getUnsavedGuard.mockReturnValue({ save })
    await act(async () => result.current.decline())
    expect(save).toHaveBeenCalled()
  })

  it("forgets an edit once the draft is declined, so a later draft of the same name starts from its proposal", async () => {
    const { result } = setup()
    await result.current.file!.save("x", "edited")
    await act(async () => result.current.decline())
    act(() => result.current.open(PATH))
    expect(await result.current.file!.load("x")).toEqual({ content: proposal.text })
  })

  it("is closed when the persona changes", () => {
    const { result, rerender } = renderHook(({ h }) => useDraftEditor({ handle: h, personaName: "N", onAccepted: () => {} }), { initialProps: { h: "samantha" } })
    act(() => result.current.open(PATH))
    expect(result.current.current).not.toBeNull()
    rerender({ h: "grace" })
    expect(result.current.current).toBeNull()
  })

  it("says why when the server could not forget the proposal, and still closes the draft", async () => {
    const { result } = setup()
    changes.resolveChanges.mockResolvedValue({ ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." })
    await act(async () => result.current.decline())
    expect(notify.notify.error).toHaveBeenCalledWith("Sympose isn't responding. Check that it's still running, then try again.")
    expect(result.current.current).toBeNull()
  })

  it("tells the Drafts list after an accept and after a decline, so the row goes", async () => {
    const heard = vi.fn()
    window.addEventListener("sympose:drafts-changed", heard)
    const { result } = setup()
    await act(async () => result.current.accept())
    expect(heard).toHaveBeenCalledTimes(1)
    act(() => result.current.open(PATH))
    await act(async () => result.current.decline())
    expect(heard).toHaveBeenCalledTimes(2)
    window.removeEventListener("sympose:drafts-changed", heard)
  })
})
