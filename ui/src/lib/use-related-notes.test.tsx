// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useRelatedNotes } from "./use-related-notes"
import * as api from "./vault-related-api"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const state = (...paths: string[]): api.RelatedState => ({
  enabled: true,
  related: paths.map((p) => ({ rel_path: p, title: p, percent: 50 })),
})

describe("useRelatedNotes while the index is being built", () => {
  it("asks again after a few seconds, and stops once the answer says it is done", async () => {
    vi.useFakeTimers()
    try {
      const spy = vi
        .spyOn(api, "fetchRelated")
        .mockResolvedValueOnce({ enabled: true, related: [], indexing: true })
        .mockResolvedValueOnce(state("b.md"))
      const { result } = renderHook(() => useRelatedNotes("a.md", "samantha"))
      await act(async () => {})
      expect(spy).toHaveBeenCalledTimes(1)
      expect(result.current.related).toEqual([])
      await act(async () => {
        await vi.advanceTimersByTimeAsync(4000)
      })
      expect(spy).toHaveBeenCalledTimes(1) // not before about five seconds
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
      expect(spy).toHaveBeenCalledTimes(2)
      expect(result.current.related[0].rel_path).toBe("b.md")
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000)
      })
      expect(spy).toHaveBeenCalledTimes(2) // finished: no more asking
    } finally {
      vi.useRealTimers()
    }
  })

  it("does not ask again when no longer open, and keeps asking nothing for a note that is closed", async () => {
    vi.useFakeTimers()
    try {
      const spy = vi.spyOn(api, "fetchRelated").mockResolvedValue({ enabled: true, related: [], indexing: true })
      const { unmount } = renderHook(() => useRelatedNotes("a.md", "samantha"))
      await act(async () => {})
      unmount()
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000)
      })
      expect(spy).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("useRelatedNotes", () => {
  it("asks for the open note and gives its neighbours", async () => {
    const spy = vi.spyOn(api, "fetchRelated").mockResolvedValue(state("b.md"))
    const { result } = renderHook(() => useRelatedNotes("a.md", "samantha"))
    await waitFor(() => expect(result.current.related).toHaveLength(1))
    expect(spy.mock.calls[0].slice(0, 2)).toEqual(["a.md", "samantha"])
  })

  it("asks nothing and shows nothing with no note open", () => {
    const spy = vi.spyOn(api, "fetchRelated")
    const { result } = renderHook(() => useRelatedNotes(undefined, "samantha"))
    expect(spy).not.toHaveBeenCalled()
    expect(result.current).toEqual(api.NO_RELATED)
  })

  it("never shows the last note's neighbours under the next note while it loads", async () => {
    let release: (s: api.RelatedState) => void = () => {}
    vi.spyOn(api, "fetchRelated")
      .mockResolvedValueOnce(state("b.md"))
      .mockReturnValueOnce(new Promise((r) => (release = r)))
    const { result, rerender } = renderHook(({ p }) => useRelatedNotes(p, "samantha"), { initialProps: { p: "a.md" } })
    await waitFor(() => expect(result.current.related).toHaveLength(1))
    rerender({ p: "c.md" })
    expect(result.current.related).toEqual([])
    await act(async () => release(state("d.md")))
    expect(result.current.related[0].rel_path).toBe("d.md")
  })

  it("does not show one persona's neighbours of a note to another persona who opens the same note", async () => {
    let release: (s: api.RelatedState) => void = () => {}
    vi.spyOn(api, "fetchRelated")
      .mockResolvedValueOnce(state("mine.md"))
      .mockReturnValueOnce(new Promise((r) => (release = r)))
    const { result, rerender } = renderHook(({ who }) => useRelatedNotes("a.md", who), { initialProps: { who: "samantha" } })
    await waitFor(() => expect(result.current.related).toHaveLength(1))
    rerender({ who: "ada" })
    expect(result.current.related).toEqual([])
    await act(async () => release(state("hers.md")))
    expect(result.current.related[0].rel_path).toBe("hers.md")
  })

  it("drops the answer of a note that is no longer open", async () => {
    let first: (s: api.RelatedState) => void = () => {}
    vi.spyOn(api, "fetchRelated")
      .mockReturnValueOnce(new Promise((r) => (first = r)))
      .mockResolvedValueOnce(state("d.md"))
    const { result, rerender } = renderHook(({ p }) => useRelatedNotes(p, "samantha"), { initialProps: { p: "a.md" } })
    rerender({ p: "c.md" })
    await waitFor(() => expect(result.current.related[0]?.rel_path).toBe("d.md"))
    await act(async () => first(state("late.md")))
    expect(result.current.related[0].rel_path).toBe("d.md")
  })
})
