// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ sendChatTurn: vi.fn(), fetchChatPhase: vi.fn(), fetchChatSession: vi.fn(), startChatSession: vi.fn() }))
vi.mock("@/lib/chat-api", () => api)

import { useChat } from "./use-chat"

const ok = (reply: string, session = "s1") => ({
  ok: true,
  reply: { reply, session_id: session, model: null, ttft_ms: 610, truncated: false, saved: true, cloud: [], withheld: [] },
})

beforeEach(() => {
  api.fetchChatPhase.mockResolvedValue(null)
  api.fetchChatSession.mockResolvedValue(null)
  api.startChatSession.mockResolvedValue(null)
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

// -- resuming a saved conversation ----------------------------------------------------------------

const saved = (index: number, extra: Record<string, unknown> = {}) => ({
  index,
  user: `question ${index}`,
  assistant: `answer ${index}`,
  timestamp: "2026-09-30T10:00:00+00:00",
  model: "m",
  ttft_ms: 500,
  truncated: false,
  sent: null,
  ...extra,
})
const pageOf = (turns: ReturnType<typeof saved>[], start: number, hasMore: boolean, sid = "s1") => ({
  session_id: sid,
  turns,
  start,
  total: start + turns.length,
  has_more: hasMore,
})

describe("useChat resuming", () => {
  it("shows the persona's latest saved conversation as user and persona turns", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(4), saved(5)], 4, true))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(4))
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([
      ["user", "question 4"], ["persona", "answer 4"], ["user", "question 5"], ["persona", "answer 5"],
    ])
    expect(result.current.turns[1]).toMatchObject({ handle: "samantha", latency: "0.50s" })
    expect(result.current.hasMore).toBe(true)
  })

  it("continues the resumed conversation, not a new one, when the user replies", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s7"))
    api.sendChatTurn.mockResolvedValue(ok("next", "s7"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    await say(result, "and then?")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["and then?", "samantha", "s7"])
  })

  it("asks for a persona's conversation once, however often it is shown", async () => {
    const { rerender } = renderHook(({ p }) => useChat(p), { initialProps: { p: "samantha" } })
    rerender({ p: "aria" })
    rerender({ p: "samantha" })
    await waitFor(() => expect(api.fetchChatSession).toHaveBeenCalledTimes(2))
    expect(api.fetchChatSession.mock.calls.map((c) => c[0]).sort()).toEqual(["aria", "samantha"])
  })

  it("starts empty when there is nothing saved or the backend cannot say", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([], 0, false))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(api.fetchChatSession).toHaveBeenCalled())
    expect(result.current.turns).toEqual([])
    expect(result.current.hasMore).toBe(false)
  })

  it("loads older turns in front of the ones shown, from the same conversation", async () => {
    api.fetchChatSession.mockResolvedValueOnce(pageOf([saved(2), saved(3)], 2, true, "s1"))
    api.fetchChatSession.mockResolvedValueOnce(pageOf([saved(0), saved(1)], 0, false, "s1"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.hasMore).toBe(true))
    await act(async () => {
      await result.current.loadOlder()
    })
    expect(api.fetchChatSession.mock.calls[1]).toEqual(["samantha", { sessionId: "s1", before: 2, limit: 20 }])
    expect(result.current.turns.map((t) => t.body)).toEqual([
      "question 0", "answer 0", "question 1", "answer 1", "question 2", "answer 2", "question 3", "answer 3",
    ])
    expect(result.current.hasMore).toBe(false)
  })

  it("does not ask for older turns when there are none", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    await act(async () => {
      await result.current.loadOlder()
    })
    expect(api.fetchChatSession).toHaveBeenCalledTimes(1)
  })

  it("starts over on a new conversation, and the next message continues the one the backend opened", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, true, "s1"))
    api.startChatSession.mockResolvedValue("s-blank")
    api.sendChatTurn.mockResolvedValue(ok("fresh", "s-blank"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    await act(async () => {
      await result.current.newConversation()
    })
    expect(api.startChatSession).toHaveBeenCalledWith("samantha")
    expect(result.current.turns).toEqual([])
    expect(result.current.hasMore).toBe(false)
    await say(result, "hello again")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", "s-blank"])
    expect(api.fetchChatSession).toHaveBeenCalledTimes(1)
  })

  it("is blank at once and still works when the backend cannot open the conversation", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s1"))
    api.startChatSession.mockResolvedValue(null)
    api.sendChatTurn.mockResolvedValue(ok("fresh", "s2"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    await act(async () => {
      await result.current.newConversation()
    })
    expect(result.current.turns).toEqual([])
    await say(result, "hello again")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", undefined])
  })

  it("keeps the conversation the user has started when the backend's blank one arrives late", async () => {
    let opened: (v: unknown) => void = () => {}
    api.startChatSession.mockReturnValue(new Promise((r) => (opened = r)))
    api.sendChatTurn.mockResolvedValueOnce(ok("one", "s-real")).mockResolvedValueOnce(ok("two", "s-real"))
    const { result } = renderHook(() => useChat("samantha"))
    let starting: Promise<void> = Promise.resolve()
    act(() => {
      starting = result.current.newConversation()
    })
    await say(result, "first")
    await act(async () => {
      opened("s-blank")
      await starting
    })
    await say(result, "second")
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s-real"])
  })

  it("resumes a conversation that was left blank as blank, and continues it", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([], 0, false, "s-blank"))
    api.sendChatTurn.mockResolvedValue(ok("hi", "s-blank"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(api.fetchChatSession).toHaveBeenCalled())
    expect(result.current.turns).toEqual([])
    await say(result, "hello")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello", "samantha", "s-blank"])
  })

  it("does not start over while a reply is in flight", async () => {
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn.mockReturnValue(new Promise((r) => (release = r)))
    const { result } = renderHook(() => useChat("samantha"))
    act(() => result.current.setDraft("hi"))
    act(() => {
      void result.current.send()
    })
    await act(async () => {
      await result.current.newConversation()
    })
    expect(api.startChatSession).not.toHaveBeenCalled()
    expect(result.current.turns.map((t) => t.body)).toEqual(["hi"])
    await act(async () => release(ok("done")))
  })

  it("does not put a saved conversation in front of one the user has already started", async () => {
    let arrive: (v: unknown) => void = () => {}
    api.fetchChatSession.mockReturnValue(new Promise((r) => (arrive = r)))
    api.sendChatTurn.mockResolvedValue(ok("fresh", "s2"))
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hello")
    await act(async () => arrive(pageOf([saved(0), saved(1)], 0, false, "s1")))
    expect(result.current.turns.map((t) => t.body)).toEqual(["hello", "fresh"])
  })

  it("drops older turns that arrive after the conversation was started over", async () => {
    let arrive: (v: unknown) => void = () => {}
    api.fetchChatSession.mockResolvedValueOnce(pageOf([saved(2)], 2, true, "s1"))
    api.fetchChatSession.mockReturnValueOnce(new Promise((r) => (arrive = r)))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.hasMore).toBe(true))
    let loading: Promise<void> = Promise.resolve()
    act(() => {
      loading = result.current.loadOlder()
    })
    await act(async () => {
      await result.current.newConversation()
    })
    await act(async () => {
      arrive(pageOf([saved(0), saved(1)], 0, false, "s1"))
      await loading
    })
    expect(result.current.turns).toEqual([])
    expect(result.current.hasMore).toBe(false)
  })
})
