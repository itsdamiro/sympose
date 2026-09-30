// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const { notifyError } = vi.hoisted(() => ({ notifyError: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError } }))

import { useModels } from "./use-models"

const stateFor = (current: string, own: string | null = null) => ({
  models: [],
  current,
  current_cloud: false,
  own,
  fallback: "ollama_chat/gemma2:9b",
  fallback_cloud: false,
})
const json = (body: unknown, ok = true, status = ok ? 200 : 500) => ({ ok, status, json: async () => body }) as Response

afterEach(() => {
  cleanup()
  notifyError.mockClear()
  vi.unstubAllGlobals()
})

describe("useModels", () => {
  it("reads the persona's model when it is known", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(stateFor("a/x"))))
    const { result } = renderHook(() => useModels("samantha"))
    expect(result.current.state).toBeNull()
    await waitFor(() => expect(result.current.state?.current).toBe("a/x"))
  })

  it("does not show one persona's models for another while the new one is read", async () => {
    let resolveSecond: (r: Response) => void = () => {}
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(stateFor("a/x")))
        .mockReturnValueOnce(new Promise<Response>((r) => (resolveSecond = r)))
    )
    const { result, rerender } = renderHook(({ p }) => useModels(p), { initialProps: { p: "one" } })
    await waitFor(() => expect(result.current.state?.current).toBe("a/x"))
    rerender({ p: "two" })
    expect(result.current.state).toBeNull()
    resolveSecond(json(stateFor("b/y")))
    await waitFor(() => expect(result.current.state?.current).toBe("b/y"))
  })

  it("saves a choice for the persona now chosen and takes what the backend reports", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(stateFor("a/x")))
      .mockResolvedValueOnce(json(stateFor("b/y", "b/y")))
    vi.stubGlobal("fetch", fetchMock)
    const { result } = renderHook(() => useModels("samantha"))
    await waitFor(() => expect(result.current.state).not.toBeNull())
    let saved = false
    await act(async () => {
      saved = await result.current.choose("b/y")
    })
    expect(saved).toBe(true)
    expect(result.current.state?.own).toBe("b/y")
    expect(fetchMock.mock.calls[1][0]).toBe("/api/personas/samantha/model")
  })

  it("changes the model for the persona now chosen, not the one it started with", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(stateFor("a/x")))
    vi.stubGlobal("fetch", fetchMock)
    const { result, rerender } = renderHook(({ p }) => useModels(p), { initialProps: { p: "one" } })
    await waitFor(() => expect(result.current.state).not.toBeNull())
    rerender({ p: "two" })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/models?persona=two"))
    await act(async () => {
      await result.current.choose("b/y")
    })
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe("/api/personas/two/model")
  })

  it("shows the reason a save failed, resolves false, and keeps the state as it was", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(json(stateFor("a/x")))
        .mockResolvedValueOnce(json({ detail: "Couldn't save the model into samantha's persona.yaml." }, false, 500))
    )
    const { result } = renderHook(() => useModels("samantha"))
    await waitFor(() => expect(result.current.state).not.toBeNull())
    let saved = true
    await act(async () => {
      saved = await result.current.choose("b/y")
    })
    expect(saved).toBe(false)
    expect(notifyError).toHaveBeenCalledWith("Couldn't save the model into samantha's persona.yaml.")
    expect(result.current.state?.current).toBe("a/x")
  })
})
