// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { SLACK_POLL_MS, useSlackConnected } from "./use-slack-connected"

const json = (connected: boolean) => ({ ok: true, status: 200, json: async () => ({ connected }) }) as Response

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("useSlackConnected", () => {
  it("is false until the backend has said, then follows it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(true)))
    const { result } = renderHook(() => useSlackConnected("samantha", true))
    expect(result.current).toBe(false)
    await waitFor(() => expect(result.current).toBe(true))
  })

  it("reads nothing while the persona page is not open", () => {
    const fetchMock = vi.fn().mockResolvedValue(json(true))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useSlackConnected("samantha", false))
    expect(result.current).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("looks again on a timer, and the dot goes out when the connection is gone", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(true)).mockResolvedValue(json(false))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useSlackConnected("samantha", true))
    await waitFor(() => expect(result.current).toBe(true))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SLACK_POLL_MS)
    })
    await waitFor(() => expect(result.current).toBe(false))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("stops looking when the page closes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(true))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ on }) => useSlackConnected("samantha", on), { initialProps: { on: true } })
    await waitFor(() => expect(result.current).toBe(true))
    rerender({ on: false })
    expect(result.current).toBe(false)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SLACK_POLL_MS * 3)
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("does not show one persona's dot for another while the new one is read", async () => {
    let resolveSecond: (r: Response) => void = () => {}
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(true))
      .mockReturnValueOnce(new Promise<Response>((r) => (resolveSecond = r)))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ p }) => useSlackConnected(p, true), { initialProps: { p: "samantha" } })
    await waitFor(() => expect(result.current).toBe(true))
    rerender({ p: "other" })
    expect(result.current).toBe(false)
    resolveSecond(json(true))
    await waitFor(() => expect(result.current).toBe(true))
  })

  it("ignores a late answer about the persona that was shown before", async () => {
    let resolveFirst: (r: Response) => void = () => {}
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(new Promise<Response>((r) => (resolveFirst = r)))
      .mockResolvedValueOnce(json(true))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ p }) => useSlackConnected(p, true), { initialProps: { p: "samantha" } })
    rerender({ p: "other" })
    await waitFor(() => expect(result.current).toBe(true))
    await act(async () => {
      resolveFirst(json(false))
    })
    expect(result.current).toBe(true)
  })

  it("does not look while the window is hidden", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(true))
    vi.stubGlobal("fetch", fetchMock)
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden")
    renderHook(() => useSlackConnected("samantha", true))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(SLACK_POLL_MS * 2)
    })
    expect(fetchMock).not.toHaveBeenCalled()
    visibility.mockReturnValue("visible")
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"))
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    visibility.mockRestore()
  })
})
