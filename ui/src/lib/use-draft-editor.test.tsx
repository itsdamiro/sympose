// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook } from "@testing-library/react"

const changes = vi.hoisted(() => ({ acceptDraft: vi.fn(), fetchChanges: vi.fn(), resolveChanges: vi.fn(), saveDraftText: vi.fn() }))
const notify = vi.hoisted(() => ({ notify: { error: vi.fn(), success: vi.fn() } }))
const guard = vi.hoisted(() => ({ getUnsavedGuard: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => changes)
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
  changes.acceptDraft.mockResolvedValue({ ok: true, path: "Ideas/New plan.md" })
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

  it("opens with the properties card, as the note will", () => {
    const { result } = setup()
    expect(result.current.file!.properties).toBe(true)
  })

  it("says to type a draft in the first time it opens, and not again", () => {
    const { result } = setup()
    expect(result.current.file!.reveal!()).toBe(true)
    expect(result.current.file!.reveal!()).toBe(false)
    act(() => result.current.close())
    act(() => result.current.open(PATH))
    expect(result.current.file!.reveal!()).toBe(false)
  })

  it("does not type in a draft the user has edited", async () => {
    const { result } = setup()
    await result.current.file!.save("x", "# New plan\n\nEdited\n")
    expect(result.current.file!.reveal!()).toBe(false)
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
    expect(changes.acceptDraft).not.toHaveBeenCalled()
    expect(await result.current.file!.load("x")).toEqual({ content: "# New plan\n\nEdited\n" })
  })

  it("says why and keeps nothing when the edit could not be kept, instead of reporting it saved", async () => {
    const { result } = setup()
    changes.saveDraftText.mockResolvedValue({ ok: false, error: "disk full" })

    expect(await result.current.file!.save("x", "# New plan\n\nEdited\n")).toEqual({ ok: false, error: "disk full" })

    expect(await result.current.file!.load("x")).toEqual({ content: proposal.text }) // the proposal's own text, not the failed edit
  })

  it("accepts: the editor is flushed, the server makes the note, the list and the editor are told, and the path is said", async () => {
    const order: string[] = []
    const { result, onAccepted } = setup()
    guard.getUnsavedGuard.mockReturnValue({ save: async () => (order.push("flush"), true) })
    changes.acceptDraft.mockImplementation(async () => (order.push("accept"), { ok: true, path: "Ideas/New plan.md" }))
    window.addEventListener("sympose:drafts-changed", () => order.push("announced"), { once: true })
    onAccepted.mockImplementation(() => order.push("opened"))

    await act(async () => result.current.accept())

    expect(order).toEqual(["flush", "accept", "announced", "opened"])
    expect(changes.acceptDraft).toHaveBeenCalledWith(PATH, "samantha")
    expect(onAccepted).toHaveBeenCalledWith("Ideas/New plan.md")
    expect(notify.notify.success).toHaveBeenCalledWith("Draft accepted")
    expect(result.current.current).toBeNull()
  })

  it("asks for the draft by its working path, and opens the note the server made, wherever it put it", async () => {
    const { result, onAccepted } = setup()
    act(() => result.current.open("new/741e5dad7a59.md"))
    changes.acceptDraft.mockResolvedValue({ ok: true, path: "Garden/Collaboration note ideas (3).md" })

    await act(async () => result.current.accept())

    expect(changes.acceptDraft).toHaveBeenCalledWith("new/741e5dad7a59.md", "samantha")
    expect(onAccepted).toHaveBeenCalledWith("Garden/Collaboration note ideas (3).md")
  })

  it("keeps the edit the user typed last by flushing the editor before asking the server", async () => {
    const { result } = setup()
    guard.getUnsavedGuard.mockReturnValue({ save: async () => (await result.current.file!.save("x", "typed just now"), true) })
    await act(async () => result.current.accept())
    expect(changes.saveDraftText.mock.invocationCallOrder[0]).toBeLessThan(changes.acceptDraft.mock.invocationCallOrder[0])
    expect(changes.saveDraftText).toHaveBeenCalledWith(PATH, "samantha", "typed just now")
  })

  it("does not make the note from older words when the editor could not keep the latest", async () => {
    const { result, onAccepted } = setup()
    guard.getUnsavedGuard.mockReturnValue({ save: async () => false })
    await act(async () => result.current.accept())
    expect(changes.acceptDraft).not.toHaveBeenCalled()
    expect(notify.notify.error).toHaveBeenCalledWith(expect.stringContaining("could not be kept"))
    expect(onAccepted).not.toHaveBeenCalled()
    expect(result.current.current).not.toBeNull()
  })

  it("keeps the draft and says why when the server cannot make the note", async () => {
    const { result, onAccepted } = setup()
    changes.acceptDraft.mockResolvedValue({ ok: false, error: "Seeds could not be saved: its folder is outside what this persona may write to." })
    await act(async () => result.current.accept())
    expect(notify.notify.error).toHaveBeenCalledWith("Seeds could not be saved: its folder is outside what this persona may write to.")
    expect(onAccepted).not.toHaveBeenCalled()
    expect(notify.notify.success).not.toHaveBeenCalled()
    expect(result.current.current).not.toBeNull()
  })

  it("declines: forgets the proposal, creates nothing, and closes", async () => {
    const { result, onAccepted } = setup()
    await act(async () => result.current.decline())
    expect(changes.resolveChanges).toHaveBeenCalledWith(PATH, "samantha", "all")
    expect(changes.acceptDraft).not.toHaveBeenCalled()
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

  describe("a draft decided in another program (docs/decisions/093)", () => {
    const NEW = "new/abc123.md"
    const focus = () => act(async () => void window.dispatchEvent(new Event("focus")))
    function setupNew() {
      const hook = setup()
      act(() => hook.result.current.open(NEW))
      changes.fetchChanges.mockClear()
      return hook
    }

    it("closes the editor, with no notice and without opening a note, when the window comes back and the draft is gone", async () => {
      const { result, onAccepted } = setupNew()
      changes.fetchChanges.mockResolvedValue({ proposals: [] })
      await focus()
      expect(changes.fetchChanges).toHaveBeenCalledWith(NEW, "samantha")
      expect(result.current.current).toBeNull()
      expect(onAccepted).not.toHaveBeenCalled()
      expect(notify.notify.success).not.toHaveBeenCalled()
    })

    it("tells the Drafts list so its row goes", async () => {
      const heard = vi.fn()
      window.addEventListener("sympose:drafts-changed", heard)
      setupNew()
      changes.fetchChanges.mockResolvedValue({ proposals: [] })
      await focus()
      expect(heard).toHaveBeenCalledTimes(1)
      window.removeEventListener("sympose:drafts-changed", heard)
    })

    it("leaves the draft open while it is still waiting, or when the server cannot be reached", async () => {
      const { result, onAccepted } = setupNew()
      changes.fetchChanges.mockResolvedValue({ proposals: [proposal] })
      await focus()
      changes.fetchChanges.mockResolvedValue(null)
      await focus()
      expect(result.current.current).not.toBeNull()
      expect(onAccepted).not.toHaveBeenCalled()
    })

    it("does nothing with an answer that arrives after the draft was closed", async () => {
      const { result } = setupNew()
      let answer: (value: unknown) => void = () => {}
      changes.fetchChanges.mockReturnValue(new Promise((resolve) => (answer = resolve)))
      await focus()
      act(() => result.current.close())
      const heard = vi.fn()
      window.addEventListener("sympose:drafts-changed", heard)
      await act(async () => answer({ proposals: [] }))
      expect(heard).not.toHaveBeenCalled()
      window.removeEventListener("sympose:drafts-changed", heard)
    })

    it("does not look for a draft that already has a real path, or when no draft is open, or after it is closed", async () => {
      const { result } = setup() // PATH is a real path
      changes.fetchChanges.mockClear()
      await focus()
      act(() => result.current.open(NEW))
      act(() => result.current.close())
      await focus()
      expect(changes.fetchChanges).not.toHaveBeenCalled()
    })
  })
})
