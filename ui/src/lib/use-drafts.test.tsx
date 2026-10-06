// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"

const api = vi.hoisted(() => ({ fetchDrafts: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => api)

import { announceDraftsChanged, draftsInFolder, useDrafts } from "./use-drafts"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const draft = (path: string) => ({ path, name: null, is_new: false, count: 1, comments: 0, items: 1, time: "t" })

describe("useDrafts", () => {
  it("reads the persona's drafts when it mounts", async () => {
    api.fetchDrafts.mockResolvedValue([draft("A.md")])
    const { result } = renderHook(() => useDrafts("samantha", 0))
    await waitFor(() => expect(result.current).toEqual([draft("A.md")]))
    expect(api.fetchDrafts).toHaveBeenCalledWith("samantha")
  })

  it("reads again when the vault was refreshed, the window is focused again, or a change is announced", async () => {
    api.fetchDrafts.mockResolvedValue([])
    const { rerender } = renderHook(({ key }) => useDrafts("samantha", key), { initialProps: { key: 0 } })
    await waitFor(() => expect(api.fetchDrafts).toHaveBeenCalledTimes(1))
    rerender({ key: 1 })
    await waitFor(() => expect(api.fetchDrafts).toHaveBeenCalledTimes(2))
    act(() => void window.dispatchEvent(new Event("focus")))
    await waitFor(() => expect(api.fetchDrafts).toHaveBeenCalledTimes(3))
    act(() => announceDraftsChanged())
    await waitFor(() => expect(api.fetchDrafts).toHaveBeenCalledTimes(4))
  })

  it("never shows another persona's drafts while this one's are on their way", async () => {
    api.fetchDrafts.mockResolvedValueOnce([draft("Old.md")])
    const { result, rerender } = renderHook(({ p }) => useDrafts(p, 0), { initialProps: { p: "samantha" } })
    await waitFor(() => expect(result.current).toHaveLength(1))
    api.fetchDrafts.mockReturnValueOnce(new Promise(() => {}))
    rerender({ p: "grace" })
    expect(result.current).toEqual([])
  })

  it("stops listening when it unmounts", async () => {
    api.fetchDrafts.mockResolvedValue([])
    const { unmount } = renderHook(() => useDrafts("samantha", 0))
    await waitFor(() => expect(api.fetchDrafts).toHaveBeenCalledTimes(1))
    unmount()
    act(() => announceDraftsChanged())
    expect(api.fetchDrafts).toHaveBeenCalledTimes(1)
  })
})

describe("draftsInFolder: the drafts of the folder in view", () => {
  const all = [draft("Notes/a.md"), draft("Notes/Sub/b.md"), draft("Notes and Pets/c.md"), draft("Daily/d.md"), draft("root.md")]

  it("keeps the notes of the folder at any depth and nothing of another folder", () => {
    expect(draftsInFolder(all, "Notes").map((d) => d.path)).toEqual(["Notes/a.md", "Notes/Sub/b.md"])
    expect(draftsInFolder(all, "Daily").map((d) => d.path)).toEqual(["Daily/d.md"])
  })

  it("does not take a folder whose name only starts the same", () => {
    expect(draftsInFolder(all, "Notes and Pets").map((d) => d.path)).toEqual(["Notes and Pets/c.md"])
    expect(draftsInFolder(all, "Note")).toEqual([])
  })

  it("lists only the notes outside every folder when no folder is in view", () => {
    expect(draftsInFolder(all, undefined).map((d) => d.path)).toEqual(["root.md"])
  })

  it("lists nothing for a folder with no drafts", () => {
    expect(draftsInFolder(all, "Empty")).toEqual([])
  })

  it("lists a new note she proposed in every folder and at the root, since it has no folder to be found in yet", () => {
    const fresh = { ...draft("new/741e5dad7a59.md"), is_new: true, name: "Collaboration note" }
    const withNew = [...all, fresh]

    expect(draftsInFolder(withNew, "Notes").map((d) => d.path)).toEqual(["Notes/a.md", "Notes/Sub/b.md", "new/741e5dad7a59.md"])
    expect(draftsInFolder(withNew, "Empty").map((d) => d.path)).toEqual(["new/741e5dad7a59.md"])
    expect(draftsInFolder(withNew, undefined).map((d) => d.path)).toEqual(["root.md", "new/741e5dad7a59.md"])
  })
})
