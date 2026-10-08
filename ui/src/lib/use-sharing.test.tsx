// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const { notifyError } = vi.hoisted(() => ({ notifyError: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError } }))

import { announceSettingsChanged } from "./settings-changed"
import { useSharing } from "./use-sharing"

const stateFor = (model: string, shared = false) => ({
  model,
  cloud: true,
  categories: [{ name: "notes", description: "d", shared }],
})
const json = (body: unknown, ok = true, status = ok ? 200 : 500) => ({ ok, status, json: async () => body }) as Response

afterEach(() => {
  cleanup()
  notifyError.mockClear()
  vi.unstubAllGlobals()
})

describe("useSharing", () => {
  it("reads what the persona's model may receive when the persona is known", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(stateFor("gemini/x"))))
    const { result } = renderHook(() => useSharing("cloudy"))
    expect(result.current.state).toBeNull()
    await waitFor(() => expect(result.current.state?.model).toBe("gemini/x"))
  })

  it("does not show one persona's answer for another while the new one is read", async () => {
    let resolveSecond: (r: Response) => void = () => {}
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(stateFor("gemini/x")))
      .mockReturnValueOnce(new Promise<Response>((r) => (resolveSecond = r)))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ p }) => useSharing(p), { initialProps: { p: "cloudy" } })
    await waitFor(() => expect(result.current.state?.model).toBe("gemini/x"))
    rerender({ p: "other" })
    expect(result.current.state).toBeNull()
    resolveSecond(json(stateFor("openai/y")))
    await waitFor(() => expect(result.current.state?.model).toBe("openai/y"))
  })

  it("replaces the state with what the backend reports after a category is changed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(stateFor("gemini/x", false)))
      .mockResolvedValueOnce(json(stateFor("gemini/x", true)))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useSharing("cloudy"))
    await waitFor(() => expect(result.current.state).not.toBeNull())
    await act(() => result.current.setShared("notes", true))
    expect(result.current.state?.categories[0].shared).toBe(true)
    expect(fetchMock.mock.calls[1][0]).toBe("/api/sharing/notes?persona=cloudy")
  })

  it("reads again when the persona's model changes, so the notice follows the model in use", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(stateFor("ollama/x")))
      .mockResolvedValueOnce(json(stateFor("gemini/y")))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ m }) => useSharing("cloudy", m), { initialProps: { m: "ollama/x" } })
    await waitFor(() => expect(result.current.state?.model).toBe("ollama/x"))
    rerender({ m: "gemini/y" })
    await waitFor(() => expect(result.current.state?.model).toBe("gemini/y"))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("reads again when a setting was changed elsewhere, such as a request the user accepted", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(stateFor("gemini/x", false)))
      .mockResolvedValueOnce(json(stateFor("gemini/x", true)))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useSharing("cloudy", "gemini/x"))
    await waitFor(() => expect(result.current.state?.categories[0].shared).toBe(false))
    act(() => announceSettingsChanged())
    await waitFor(() => expect(result.current.state?.categories[0].shared).toBe(true))
  })

  it("changes a category for the persona now chosen, not the one it started with", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(stateFor("gemini/x")))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ p }) => useSharing(p), { initialProps: { p: "cloudy" } })
    await waitFor(() => expect(result.current.state).not.toBeNull())
    rerender({ p: "other" })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sharing?persona=other"))
    await act(() => result.current.setShared("notes", true))
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe("/api/sharing/notes?persona=other")
  })

  it("shows the reason a save failed and keeps what was last reported", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(stateFor("gemini/x", false)))
        .mockResolvedValueOnce(json({ detail: "Couldn't save the cloud-sharing setting." }, false, 500))
    )
    const { result } = renderHook(() => useSharing("cloudy"))
    await waitFor(() => expect(result.current.state).not.toBeNull())
    await act(() => result.current.setShared("notes", true))
    expect(notifyError).toHaveBeenCalledWith("Couldn't save the cloud-sharing setting.")
    expect(result.current.state?.categories[0].shared).toBe(false)
  })

  it("stays without a state when the backend cannot say", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const { result } = renderHook(() => useSharing("cloudy"))
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current.state).toBeNull()
  })
})
