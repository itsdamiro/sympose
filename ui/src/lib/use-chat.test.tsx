// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ sendChatTurn: vi.fn(), cancelChatTurn: vi.fn(), fetchChatStatus: vi.fn(), fetchChatSession: vi.fn(), startChatSession: vi.fn() }))
vi.mock("@/lib/chat-api", () => api)

import { useChat } from "./use-chat"

const ok = (reply: string, session = "s1") => ({
  ok: true,
  reply: { reply, session_id: session, model: null, ttft_ms: 610, truncated: false, saved: true, cloud: [], withheld: [] },
})

beforeEach(() => {
  api.fetchChatStatus.mockResolvedValue({ phase: null, indexing: null })
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["first", "samantha", undefined, expect.any(AbortSignal)])
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s9", expect.any(AbortSignal)])
  })

  it("shows a refusal as a system error line, not as a persona reply", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: false, error: "local models only" })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    const last = result.current.turns[result.current.turns.length - 1]
    expect(last).toMatchObject({ role: "system", kind: "error", body: "@samantha couldn't reply: local models only" })
  })

  it("keeps the last reply's token count and the model that made it, for the context meter", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("Hi").reply, model: "ollama_chat/gemma2:9b", context_used: 3812, context_limit: 6144 } })
    const { result } = renderHook(() => useChat("samantha"))
    expect(result.current.context).toBeUndefined()
    await say(result, "hi")
    expect(result.current.context).toEqual({ used: 3812, limit: 6144, model: "ollama_chat/gemma2:9b" })
    expect(result.current.sessionId).toBe("s1")
  })

  it("has no count when the model's window is unknown, or the reply names no model", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("Hi").reply, model: "m", context_used: null, context_limit: null } })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    expect(result.current.context).toBeUndefined()
  })

  it("keeps a count of zero tokens", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("Hi").reply, model: "m", context_used: 0, context_limit: 100 } })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    expect(result.current.context).toEqual({ used: 0, limit: 100, model: "m" })
  })

  it("leaves the count as it was when a reply fails, and clears it in a new conversation", async () => {
    api.sendChatTurn.mockResolvedValueOnce({ ok: true, reply: { ...ok("Hi").reply, model: "m", context_used: 10, context_limit: 100 } })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "one")
    api.sendChatTurn.mockResolvedValueOnce({ ok: false, error: "down" })
    await say(result, "two")
    expect(result.current.context?.used).toBe(10)
    await act(async () => {
      await result.current.newConversation()
    })
    expect(result.current.context).toBeUndefined()
  })

  it("adds a system line to this persona's conversation only", async () => {
    const { result, rerender } = renderHook(({ p }) => useChat(p), { initialProps: { p: "samantha" } })
    act(() => result.current.notice("confirmation", "Switched model to X."))
    expect(result.current.turns.map((t) => [t.role, t.kind, t.body])).toEqual([["system", "confirmation", "Switched model to X."]])
    rerender({ p: "aria" })
    expect(result.current.turns).toEqual([])
  })

  it("does not send a blank message", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "   ")
    expect(api.sendChatTurn).not.toHaveBeenCalled()
  })

  it("shows a message sent while a reply is in flight at once, and sends the ones that waited as one turn", async () => {
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn
      .mockReturnValueOnce(new Promise((r) => (release = r)))
      .mockResolvedValueOnce(ok("both answered", "s1"))
    const { result } = renderHook(() => useChat("samantha"))
    act(() => result.current.setDraft("first"))
    let first: Promise<void> = Promise.resolve()
    act(() => {
      first = result.current.send()
    })
    expect(result.current.sending).toBe(true)
    await say(result, "second")
    await say(result, "third")
    expect(api.sendChatTurn).toHaveBeenCalledTimes(1)
    expect(result.current.turns.map((t) => t.body)).toEqual(["first", "second", "third"]) // shown at once, unmarked
    await act(async () => {
      release(ok("to the first", "s1"))
      await first
    })
    expect(api.sendChatTurn).toHaveBeenCalledTimes(2)
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second\n\nthird", "samantha", "s1", expect.any(AbortSignal)])
    expect(result.current.turns.map((t) => t.body)).toEqual(["first", "second", "third", "to the first", "both answered"])
    expect(result.current.sending).toBe(false)
  })

  it("still sends what waited when the reply it waited for failed", async () => {
    let release: (v: unknown) => void = () => {}
    api.sendChatTurn
      .mockReturnValueOnce(new Promise((r) => (release = r)))
      .mockResolvedValueOnce(ok("fine", "s2"))
    const { result } = renderHook(() => useChat("samantha"))
    act(() => result.current.setDraft("first"))
    let first: Promise<void> = Promise.resolve()
    act(() => {
      first = result.current.send()
    })
    await say(result, "second")
    await act(async () => {
      release({ ok: false, error: "model down" })
      await first
    })
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", undefined, expect.any(AbortSignal)])
    expect(result.current.sending).toBe(false)
  })

  it("asks what the reply is doing while it waits", async () => {
    vi.useFakeTimers()
    api.fetchChatStatus.mockResolvedValue({ phase: "searching", indexing: 40 })
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
    expect(result.current.indexing).toBe(40)
    await act(async () => {
      release(ok("done"))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(result.current.phase).toBeNull()
    expect(result.current.indexing).toBeNull()
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["and then?", "samantha", "s7", expect.any(AbortSignal)])
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", "s-blank", expect.any(AbortSignal)])
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", undefined, expect.any(AbortSignal)])
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
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s-real", expect.any(AbortSignal)])
  })

  it("resumes a conversation that was left blank as blank, and continues it", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([], 0, false, "s-blank"))
    api.sendChatTurn.mockResolvedValue(ok("hi", "s-blank"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(api.fetchChatSession).toHaveBeenCalled())
    expect(result.current.turns).toEqual([])
    await say(result, "hello")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello", "samantha", "s-blank", expect.any(AbortSignal)])
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

  it("keeps what grounded a reply with it, live and when resumed", async () => {
    const sent = { notes: [{ path: "Projects/Atlas.md", heading: "", source: "vault" }] }
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0, { sent })], 0, false))
    api.sendChatTurn.mockResolvedValue({
      ok: true,
      reply: { ...ok("live").reply, sent },
    })
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    expect(result.current.turns[1].sent).toEqual(sent)
    expect(result.current.turns[0].sent).toBeUndefined()
    await say(result, "again")
    expect(result.current.turns[result.current.turns.length - 1].sent).toEqual(sent)
  })
})

describe("useChat: stopping a reply in flight (ADR 054)", () => {
  /** A reply that never lands on its own: it settles when the test says so, or as cancelled when aborted. */
  function pendingReply() {
    const handle: { land: (r: unknown) => void } = { land: () => {} }
    api.sendChatTurn.mockImplementationOnce(
      (_m: string, _p: string, _s: string | undefined, signal: AbortSignal) =>
        new Promise((resolve) => {
          handle.land = resolve
          signal.addEventListener("abort", () => resolve({ ok: false, cancelled: true }))
        })
    )
    return handle
  }
  const start = (result: Parameters<typeof say>[0], text: string) => {
    act(() => result.current.setDraft(text))
    let sending!: Promise<void>
    act(() => {
      sending = result.current.send()
    })
    return sending
  }

  it("throws the reply away: the message leaves the transcript and returns to the box, with a line saying so", async () => {
    pendingReply()
    api.cancelChatTurn.mockResolvedValue(true)
    const { result } = renderHook(() => useChat("samantha"))
    const sending = start(result, "hi there")
    await act(async () => {
      await result.current.stop()
      await sending
    })
    expect(api.cancelChatTurn).toHaveBeenCalledWith("samantha")
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([["system", "Stopped. @samantha did not reply."]])
    expect(result.current.draft).toBe("hi there")
    expect(result.current.sending).toBe(false)
    expect(result.current.sessionId).toBeUndefined()
  })

  it("puts the stopped message in front of whatever has been typed since", async () => {
    pendingReply()
    api.cancelChatTurn.mockResolvedValue(true)
    const { result } = renderHook(() => useChat("samantha"))
    const sending = start(result, "first thought")
    act(() => result.current.setDraft("and another"))
    await act(async () => {
      await result.current.stop()
      await sending
    })
    expect(result.current.draft).toBe("first thought\n\nand another")
  })

  it("does not abort or throw anything away when the backend says nothing was left to stop: the reply arrives", async () => {
    const reply = pendingReply()
    api.cancelChatTurn.mockResolvedValue(false)
    const { result } = renderHook(() => useChat("samantha"))
    const sending = start(result, "hi")
    await act(async () => {
      await result.current.stop()
      reply.land(ok("Hello!"))
      await sending
    })
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([["user", "hi"], ["persona", "Hello!"]])
    expect(result.current.draft).toBe("")
  })

  it("treats a reply the backend itself answers as stopped the same way", async () => {
    const reply = pendingReply()
    const { result } = renderHook(() => useChat("samantha"))
    const sending = start(result, "hi")
    await act(async () => {
      reply.land({ ok: false, cancelled: true })
      await sending
    })
    expect(result.current.turns.map((t) => t.role)).toEqual(["system"])
    expect(result.current.draft).toBe("hi")
  })

  it("still sends what waited while the reply was running, as its own turn, and keeps those messages", async () => {
    pendingReply()
    api.sendChatTurn.mockResolvedValueOnce(ok("About the second.", "s2"))
    api.cancelChatTurn.mockResolvedValue(true)
    const { result } = renderHook(() => useChat("samantha"))
    const sending = start(result, "first")
    act(() => result.current.setDraft("second"))
    await act(async () => {
      await result.current.send() // sent while the first reply is running: it waits
    })
    await act(async () => {
      await result.current.stop()
      await sending
    })
    expect(api.sendChatTurn.mock.calls[1].slice(0, 2)).toEqual(["second", "samantha"])
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([
      ["user", "second"],
      ["system", "Stopped. @samantha did not reply."],
      ["persona", "About the second."],
    ])
    expect(result.current.draft).toBe("first")
  })

  it("does nothing when no reply is running, even after one has finished", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    await act(async () => result.current.stop())
    api.sendChatTurn.mockResolvedValue(ok("Hello!"))
    await say(result, "hi")
    await act(async () => result.current.stop())
    expect(api.cancelChatTurn).not.toHaveBeenCalled()
  })
})
