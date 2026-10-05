// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchChanges: vi.fn(), resolveChanges: vi.fn() }))
const toast = vi.hoisted(() => ({ error: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => api)
vi.mock("@/lib/notify", () => ({ notify: toast }))

import { announcePersonaActed, usePersonaChanges } from "./use-persona-changes"

const proposal = (id: string) => ({ id, time: "t", kind: "edit", say: "", find: "x", replace: "y", before: "", after: "", status: "pending" })
const noteChanges = (path: string, ids: string[]) => ({ path, exists: true, mtime: 1, proposals: ids.map(proposal), annotations: [] })

afterEach(cleanup) // unmount every hook, so none keeps listening for focus into the next test

beforeEach(() => {
  api.fetchChanges.mockReset()
  api.resolveChanges.mockReset()
  toast.error.mockReset()
})

describe("usePersonaChanges", () => {
  it("fetches the open note's changes for the persona", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1", "2"]))

    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))

    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(2))
    expect(api.fetchChanges).toHaveBeenCalledWith("a.md", "samantha")
  })

  it("reads the note's changes again when a chat turn ends, since she may have proposed something in it", async () => {
    api.fetchChanges.mockResolvedValueOnce(noteChanges("a.md", [])).mockResolvedValueOnce(noteChanges("a.md", ["1"]))
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(result.current.changes).not.toBeNull())

    act(() => announcePersonaActed())

    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(1))
    expect(api.fetchChanges).toHaveBeenCalledTimes(2)
  })

  it("has nothing for no note and fetches nothing while disabled", async () => {
    const none = renderHook(() => usePersonaChanges({ path: undefined, persona: "samantha" }))
    const off = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha", enabled: false }))

    expect(none.result.current.changes).toBeNull()
    expect(off.result.current.changes).toBeNull()
    expect(api.fetchChanges).not.toHaveBeenCalled()
  })

  it("never shows one note's changes under another", async () => {
    api.fetchChanges.mockImplementation(async (path: string) => noteChanges(path, [path === "a.md" ? "A" : "B"]))
    const { result, rerender } = renderHook(({ path }) => usePersonaChanges({ path, persona: "samantha" }), { initialProps: { path: "a.md" } })
    await waitFor(() => expect(result.current.changes?.proposals[0].id).toBe("A"))

    api.fetchChanges.mockImplementation(() => new Promise(() => {}))
    rerender({ path: "b.md" })

    expect(result.current.changes).toBeNull()
  })

  it("ignores a slow answer for a note that is no longer open", async () => {
    let answerA: (v: unknown) => void = () => {}
    api.fetchChanges.mockImplementation((path: string) =>
      path === "a.md" ? new Promise((resolve) => (answerA = resolve)) : Promise.resolve(noteChanges("b.md", ["B"]))
    )
    const { result, rerender } = renderHook(({ path }) => usePersonaChanges({ path, persona: "samantha" }), { initialProps: { path: "a.md" } })
    rerender({ path: "b.md" })
    await waitFor(() => expect(result.current.changes?.proposals[0].id).toBe("B"))

    await act(async () => answerA(noteChanges("a.md", ["A"])))

    expect(result.current.changes?.proposals[0].id).toBe("B")
  })

  it("shows nothing once disabled, even with what it fetched before", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1"]))
    const { result, rerender } = renderHook(({ enabled }) => usePersonaChanges({ path: "a.md", persona: "samantha", enabled }), { initialProps: { enabled: true } })
    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(1))

    rerender({ enabled: false })

    expect(result.current.changes).toBeNull()
  })

  it("does not let a resolve begun on one note touch the next note's changes", async () => {
    api.fetchChanges.mockImplementation(async (path: string) => noteChanges(path, ["shared-id"]))
    api.resolveChanges.mockResolvedValue({ ok: true, resolved: [] })
    const { result, rerender } = renderHook(({ path }) => usePersonaChanges({ path, persona: "samantha" }), { initialProps: { path: "a.md" } })
    await waitFor(() => expect(result.current.changes?.path).toBe("a.md"))
    const resolveOnA = result.current.resolve

    rerender({ path: "b.md" })
    await waitFor(() => expect(result.current.changes?.path).toBe("b.md"))
    await act(async () => {
      await resolveOnA(["shared-id"])
    })

    expect(result.current.changes?.proposals).toHaveLength(1)
    expect(api.resolveChanges).toHaveBeenCalledWith("a.md", "samantha", ["shared-id"])
  })

  it("starts again for another persona", async () => {
    api.fetchChanges.mockImplementation(async (path: string, persona: string) => noteChanges(path, [persona]))
    const { result, rerender } = renderHook(({ persona }) => usePersonaChanges({ path: "a.md", persona }), { initialProps: { persona: "samantha" } })
    await waitFor(() => expect(result.current.changes?.proposals[0].id).toBe("samantha"))

    rerender({ persona: "grace" })

    await waitFor(() => expect(result.current.changes?.proposals[0].id).toBe("grace"))
  })

  it("forgets named proposals on screen at once and then on the server", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1", "2", "3"]))
    api.resolveChanges.mockResolvedValue({ ok: true, resolved: ["2"] })
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(3))

    await act(async () => {
      await result.current.resolve(["2"])
    })

    expect(result.current.changes?.proposals.map((p) => p.id)).toEqual(["1", "3"])
    expect(api.resolveChanges).toHaveBeenCalledWith("a.md", "samantha", ["2"])
  })

  it("forgets every proposal for all and keeps the comments", async () => {
    api.fetchChanges.mockResolvedValue({ ...noteChanges("a.md", ["1", "2"]), annotations: [{ id: "c" }] })
    api.resolveChanges.mockResolvedValue({ ok: true, resolved: ["1", "2"] })
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(2))

    await act(async () => {
      await result.current.resolve("all")
    })

    expect(result.current.changes?.proposals).toEqual([])
    expect(result.current.changes?.annotations).toHaveLength(1)
    expect(api.resolveChanges).toHaveBeenCalledWith("a.md", "samantha", "all")
  })

  it("reads the real state back and says why when the server could not forget", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1", "2"]))
    api.resolveChanges.mockResolvedValue({ ok: false, error: "the Sympose backend is not reachable" })
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(2))

    await act(async () => {
      await result.current.resolve(["1"])
    })

    expect(toast.error).toHaveBeenCalledWith("the Sympose backend is not reachable")
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(result.current.changes?.proposals).toHaveLength(2))
  })

  it("reads again when the window regains focus and when asked", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1"]))
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledTimes(1))

    act(() => {
      window.dispatchEvent(new Event("focus"))
    })
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledTimes(2))

    act(() => result.current.refresh())
    await waitFor(() => expect(api.fetchChanges).toHaveBeenCalledTimes(3))
  })

  it("does nothing to resolve when no note is open", async () => {
    const { result } = renderHook(() => usePersonaChanges({ path: undefined, persona: "samantha" }))
    await act(async () => {
      await result.current.resolve("all")
    })
    expect(api.resolveChanges).not.toHaveBeenCalled()
  })

  it("tells the Drafts list when changes were resolved, since the note may no longer be a draft", async () => {
    api.fetchChanges.mockResolvedValue(noteChanges("a.md", ["1"]))
    api.resolveChanges.mockResolvedValue({ ok: true, resolved: ["1"] })
    const heard = vi.fn()
    window.addEventListener("sympose:drafts-changed", heard)
    const { result } = renderHook(() => usePersonaChanges({ path: "a.md", persona: "samantha" }))
    await waitFor(() => expect(result.current.changes).not.toBeNull())

    await act(async () => {
      await result.current.resolve(["1"])
    })

    expect(heard).toHaveBeenCalledTimes(1)
    window.removeEventListener("sympose:drafts-changed", heard)
  })
})
