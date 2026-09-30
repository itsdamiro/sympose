// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ sendChatTurn: vi.fn(), fetchChatPhase: vi.fn() }))
vi.mock("@/lib/chat-api", () => api)

import { useChat } from "./use-chat"

const ok = (reply: string, session = "s1") => ({
  ok: true,
  reply: { reply, session_id: session, model: null, ttft_ms: 610, truncated: false, saved: true, cloud: [], withheld: [] },
})

beforeEach(() => {
  api.fetchChatPhase.mockResolvedValue(null)
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.useRealTimers()
})

async function say(result: ReturnType<typeof renderHook<ReturnType<typeof useChat>, string>>["result"], text: string) {
  act(() => result.current.setDraft(text))
  await act(async () => {
    await result.current.send()
  })
}

describe("useChat", () => {
  it("shows the user's message and the persona's reply, and clears the draft", async () => {
    api.sendChatTurn.mockResolvedValue(ok("Hello!"))
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([["user", "hi"], ["persona", "Hello!"]])
    expect(result.current.turns[1].latency).toBe("0.61s")
    expect(result.current.draft).toBe("")
    expect(result.current.sending).toBe(false)
  })

  it("continues the conversation with the session id the backend returned", async () => {
    api.sendChatTurn.mockResolvedValueOnce(ok("one", "s9")).mockResolvedValueOnce(ok("two", "s9"))
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "first")
    await say(result, "second")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["first", "samantha", undefined])
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s9"])
  })

  it("shows a refusal as a system error line, not as a persona reply", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: false, error: "local models only" })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    const last = result.current.turns[result.current.turns.length - 1]
    expect(last).toMatchObject({ role: "system", kind: "error", body: "@samantha couldn't reply: local models only" })
  })

  it("does not send a blank message", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "   ")
    expect(api.sendChatTurn).not.toHaveBeenCalled()
  })

  it("does not send a second message while a reply is in flight", async () => {
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn.mockReturnValue(new Promise((r) => (release = r)))
    const { result } = renderHook(() => useChat("samantha"))
    act(() => result.current.setDraft("first"))
    let first: Promise<void> = Promise.resolve()
    act(() => {
      first = result.current.send()
    })
    expect(result.current.sending).toBe(true)
    await say(result, "second")
    expect(api.sendChatTurn).toHaveBeenCalledTimes(1)
    await act(async () => {
      release(ok("done"))
      await first
    })
    expect(result.current.sending).toBe(false)
  })

  it("asks what the reply is doing while it waits", async () => {
    vi.useFakeTimers()
    api.fetchChatPhase.mockResolvedValue("searching")
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn.mockReturnValue(new Promise((r) => (release = r)))
    const { result } = renderHook(() => useChat("samantha"))
    act(() => result.current.setDraft("hi"))
    act(() => {
      void result.current.send()
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(result.current.phase).toBe("searching")
    await act(async () => {
      release(ok("done"))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(result.current.phase).toBeNull()
  })

  it("keeps a conversation per persona, and a late reply goes to the persona it was for", async () => {
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn.mockReturnValue(new Promise((r) => (release = r)))
    const { result, rerender } = renderHook(({ p }) => useChat(p), { initialProps: { p: "samantha" } })
    act(() => result.current.setDraft("hi"))
    act(() => {
      void result.current.send()
    })
    rerender({ p: "aria" })
    expect(result.current.turns).toEqual([])
    await act(async () => release(ok("for samantha")))
    expect(result.current.turns).toEqual([])
    rerender({ p: "samantha" })
    await waitFor(() => expect(result.current.turns.map((t) => t.body)).toEqual(["hi", "for samantha"]))
  })
})
