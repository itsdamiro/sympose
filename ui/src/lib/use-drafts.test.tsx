// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"

const api = vi.hoisted(() => ({ fetchDrafts: vi.fn() }))
vi.mock("@/lib/persona-changes-api", () => api)

import { announceDraftsChanged, useDrafts } from "./use-drafts"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const draft = (path: string) => ({ path, name: null, is_new: false, count: 1, time: "t" })

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
