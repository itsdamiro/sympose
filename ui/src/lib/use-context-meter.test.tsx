// @vitest-environment jsdom
import { cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchContextEstimate: vi.fn() }))
vi.mock("@/lib/chat-api", () => api)

import { useContextMeter } from "./use-context-meter"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const base = { persona: "samantha", sessionId: "s1", model: "m1", real: undefined, hasReplies: true }
type Args = Parameters<typeof useContextMeter>[0]
const run = (over: Partial<Args> = {}) => renderHook((p: Args) => useContextMeter(p), { initialProps: { ...base, ...over } as Args })

describe("useContextMeter", () => {
  it("shows the last reply's own count while it belongs to the model in use, and asks for no estimate", () => {
    const { result } = run({ real: { used: 100, limit: 1000, model: "m1" } })
    expect(result.current).toEqual({ used: 100, limit: 1000, estimated: false })
    expect(api.fetchContextEstimate).not.toHaveBeenCalled()
  })

  it("shows an estimate for a conversation with replies but no count of its own (a resumed one)", async () => {
    api.fetchContextEstimate.mockResolvedValue({ used: 300, limit: 1000 })
    const { result } = run()
    expect(result.current).toBeNull()
    await waitFor(() => expect(result.current).toEqual({ used: 300, limit: 1000, estimated: true }))
    expect(api.fetchContextEstimate).toHaveBeenCalledWith("samantha", "s1")
  })

  it("drops a count that another model made and estimates for the model now in use", async () => {
    api.fetchContextEstimate.mockResolvedValue({ used: 50, limit: 500 })
    const { result } = run({ real: { used: 100, limit: 1000, model: "old" } })
    await waitFor(() => expect(result.current).toEqual({ used: 50, limit: 500, estimated: true }))
  })

  it("asks again when the model changes, and shows nothing of the old model's estimate meanwhile", async () => {
    api.fetchContextEstimate.mockResolvedValueOnce({ used: 300, limit: 1000 }).mockResolvedValueOnce({ used: 200, limit: 2000 })
    const { result, rerender } = run()
    await waitFor(() => expect(result.current?.used).toBe(300))
    rerender({ ...base, model: "m2" })
    expect(result.current).toBeNull()
    await waitFor(() => expect(result.current).toEqual({ used: 200, limit: 2000, estimated: true }))
  })

  it("asks again when the conversation is condensed, and shows nothing of the longer one's estimate meanwhile", async () => {
    api.fetchContextEstimate.mockResolvedValueOnce({ used: 300, limit: 1000 }).mockResolvedValueOnce({ used: 120, limit: 1000 })
    const { result, rerender } = run()
    await waitFor(() => expect(result.current?.used).toBe(300))
    rerender({ ...base, condensed: 11 })
    expect(result.current).toBeNull()
    await waitFor(() => expect(result.current).toEqual({ used: 120, limit: 1000, estimated: true }))
    expect(api.fetchContextEstimate).toHaveBeenCalledTimes(2)
  })

  it("replaces an estimate with the real count when a reply lands", async () => {
    api.fetchContextEstimate.mockResolvedValue({ used: 300, limit: 1000 })
    const { result, rerender } = run()
    await waitFor(() => expect(result.current?.estimated).toBe(true))
    rerender({ ...base, real: { used: 350, limit: 1000, model: "m1" } })
    expect(result.current).toEqual({ used: 350, limit: 1000, estimated: false })
  })

  it("shows nothing for an empty conversation, with no session, or before the model is known", () => {
    run({ hasReplies: false })
    run({ sessionId: undefined })
    run({ model: undefined })
    run({ persona: null })
    expect(api.fetchContextEstimate).not.toHaveBeenCalled()
  })

  it("shows nothing when the backend has no figure", async () => {
    api.fetchContextEstimate.mockResolvedValue(null)
    const { result } = run()
    await waitFor(() => expect(api.fetchContextEstimate).toHaveBeenCalled())
    expect(result.current).toBeNull()
  })

  it("never shows an answer that arrives after the conversation changed", async () => {
    let resolveFirst: (v: unknown) => void = () => {}
    api.fetchContextEstimate.mockReturnValueOnce(new Promise((r) => (resolveFirst = r))).mockResolvedValueOnce({ used: 7, limit: 70 })
    const { result, rerender } = run()
    rerender({ ...base, sessionId: "s2" })
    await waitFor(() => expect(result.current?.used).toBe(7))
    resolveFirst({ used: 999, limit: 1000 }) // the first conversation's answer, arriving late
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current?.used).toBe(7)
  })

  it("drops a figure made for another persona's conversation", async () => {
    api.fetchContextEstimate.mockResolvedValue({ used: 300, limit: 1000 })
    const { result, rerender } = run()
    await waitFor(() => expect(result.current?.used).toBe(300))
    rerender({ ...base, persona: "aria", sessionId: undefined })
    expect(result.current).toBeNull()
  })
})
