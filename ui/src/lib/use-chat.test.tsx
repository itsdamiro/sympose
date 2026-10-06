// @vitest-environment jsdom
import { attach, setAttachmentsNote } from "@/lib/attachments"
import { setOpenNoteSource } from "@/lib/open-note-source"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ sendChatTurn: vi.fn(), cancelChatTurn: vi.fn(), compactChatSession: vi.fn(), fetchChatStatus: vi.fn(), fetchChatSession: vi.fn(), startChatSession: vi.fn() }))
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

  it("sends the note open in the editor, as it is when the message goes", async () => {
    api.sendChatTurn.mockResolvedValue(ok("Done"))
    let text = "I run three times."
    setOpenNoteSource(() => ({ path: "a.md", text }))
    const { result } = renderHook(() => useChat("samantha"))
    text = "I run three times a week."

    await say(result, "make it four")

    expect(api.sendChatTurn.mock.calls[0][4]).toEqual({ path: "a.md", text: "I run three times a week." })
    setOpenNoteSource(null)
  })

  it("announces that she may have acted when a turn comes back, and not when it failed", async () => {
    const heard = vi.fn()
    window.addEventListener("sympose:persona-acted", heard)
    api.sendChatTurn.mockResolvedValueOnce({ ok: false, error: "no" }).mockResolvedValueOnce(ok("Done"))
    const { result } = renderHook(() => useChat("samantha"))

    await say(result, "one")
    expect(heard).not.toHaveBeenCalled()
    await say(result, "two")
    expect(heard).toHaveBeenCalledTimes(1)
    window.removeEventListener("sympose:persona-acted", heard)
  })

  it("asks for the note she showed, the last one, when the reply lands in the conversation in view", async () => {
    const reply = ok("Here it is.")
    api.sendChatTurn.mockResolvedValue({
      ...reply,
      reply: {
        ...reply.reply,
        sent: { notes: [], lookups: [{ tool: "show_note", path: "A.md", saved: true }, { tool: "show_note", path: "Projects/Atlas.md", saved: true }, { tool: "show_note", saved: false }] },
      },
    })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "open the Atlas note")
    expect(result.current.shownNote).toEqual({ path: "Projects/Atlas.md", n: 1 })
  })

  it("opens nothing when she did not, or could not", async () => {
    api.sendChatTurn.mockResolvedValue(ok("No such note."))
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "open it")
    expect(result.current.shownNote).toBeNull()
  })

  it("continues the conversation with the session id the backend returned", async () => {
    api.sendChatTurn.mockResolvedValueOnce(ok("one", "s9")).mockResolvedValueOnce(ok("two", "s9"))
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "first")
    await say(result, "second")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["first", "samantha", undefined, expect.any(AbortSignal), null, []])
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s9", expect.any(AbortSignal), null, []])
  })

  it("sends what the user attached with one message only", async () => {
    api.sendChatTurn.mockResolvedValueOnce(ok("one", "s9")).mockResolvedValueOnce(ok("two", "s9"))
    const { result } = renderHook(() => useChat("samantha"))
    setAttachmentsNote("a.md")
    attach({ quote: "three times", before: "I run ", after: "." })
    await say(result, "first")
    await say(result, "second")
    expect(api.sendChatTurn.mock.calls[0][5]).toEqual([{ quote: "three times", before: "I run ", after: "." }])
    expect(api.sendChatTurn.mock.calls[1][5]).toEqual([])
    setAttachmentsNote(undefined)
  })

  it("marks the user's message with how many passages were attached, and only that one", async () => {
    api.sendChatTurn.mockResolvedValue(ok("one", "s9"))
    const { result } = renderHook(() => useChat("samantha"))
    setAttachmentsNote("a.md")
    attach({ quote: "three times", before: "I run ", after: "." })
    attach({ quote: "raised", before: "", after: "" })
    await say(result, "first")
    await say(result, "second")
    const users = result.current.turns.filter((t) => t.role === "user")
    expect(users.map((t) => t.attached)).toEqual([2, undefined])
    setAttachmentsNote(undefined)
  })

  it("shows the mark on a resumed message too, from the saved record", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0, { sent: { notes: [], attached: 1 } }), saved(1)], 0, false))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(4))
    expect(result.current.turns.filter((t) => t.role === "user").map((t) => t.attached)).toEqual([1, undefined])
  })

  it("shows a refusal as a system error line, not as a persona reply", async () => {
    api.sendChatTurn.mockResolvedValue({ ok: false, error: "local models only" })
    const { result } = renderHook(() => useChat("samantha"))
    await say(result, "hi")
    const last = result.current.turns[result.current.turns.length - 1]
    expect(last).toMatchObject({ role: "system", kind: "error", body: "Couldn't get a reply: local models only" })
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
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second\n\nthird", "samantha", "s1", expect.any(AbortSignal), null, []])
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
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", undefined, expect.any(AbortSignal), null, []])
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["and then?", "samantha", "s7", expect.any(AbortSignal), null, []])
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", "s-blank", expect.any(AbortSignal), null, []])
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
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello again", "samantha", undefined, expect.any(AbortSignal), null, []])
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
    expect(api.sendChatTurn.mock.calls[1]).toEqual(["second", "samantha", "s-real", expect.any(AbortSignal), null, []])
  })

  it("resumes a conversation that was left blank as blank, and continues it", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([], 0, false, "s-blank"))
    api.sendChatTurn.mockResolvedValue(ok("hi", "s-blank"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(api.fetchChatSession).toHaveBeenCalled())
    expect(result.current.turns).toEqual([])
    await say(result, "hello")
    expect(api.sendChatTurn.mock.calls[0]).toEqual(["hello", "samantha", "s-blank", expect.any(AbortSignal), null, []])
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

  it("keeps the model that answered each reply with it, live and when resumed, so an old reply does not take on a model chosen later", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0, { model: "ollama_chat/gemma2:9b" })], 0, false))
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("live").reply, model: "gemini/gemini-flash-latest" } })
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(2))
    expect(result.current.turns[1].model).toBe("ollama_chat/gemma2:9b")
    await say(result, "again")
    expect(result.current.turns[result.current.turns.length - 1].model).toBe("gemini/gemini-flash-latest")
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
    expect(api.cancelChatTurn).toHaveBeenCalledWith("samantha", undefined)
    expect(result.current.turns.map((t) => [t.role, t.body])).toEqual([["system", "Stopped. No reply was sent."]])
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
      ["system", "Stopped. No reply was sent."],
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

const notes = (extra: Record<string, unknown> = {}) => ({
  ok: true,
  result: { status: "done", covered: 11, text: "The user is building Pantry.", before: 600, after: 120, ...extra },
})

describe("useChat condensing (ADR 055)", () => {
  const withReplies = async () => {
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("Hi", "s1").reply, model: "m", context_used: 3000, context_limit: 4000 } })
    const hook = renderHook(() => useChat("samantha"))
    await say(hook.result, "hi")
    return hook
  }

  it("says once, on the reply that first used the notes, how many turns they stand for", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("a").reply, condensed: 0 } })
    await say(result, "one")
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("b").reply, condensed: 9 } })
    await say(result, "two")
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("c").reply, condensed: 9 } })
    await say(result, "three")
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("d").reply, condensed: 12 } })
    await say(result, "four")
    const said = result.current.turns.filter((t) => t.role === "system").map((t) => t.body)
    expect(said).toEqual(["Earlier messages were summarised to make room.", "Earlier messages were summarised to make room."])
  })

  it("puts the notes of a resumed conversation where they take over from the turns above, and keeps the count", async () => {
    api.fetchChatSession.mockResolvedValue({ ...pageOf([saved(4), saved(5)], 4, true, "s7"), compaction: { through: 5, text: "The user likes SQLite." } })
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(5))
    expect(result.current.turns.map((t) => [t.role, t.kind, t.title ? `${t.title}: ${t.body}` : t.body])).toEqual([
      ["user", undefined, "question 4"],
      ["persona", undefined, "answer 4"],
      ["system", "output", "Earlier messages are summarised here: The user likes SQLite."],
      ["user", undefined, "question 5"],
      ["persona", undefined, "answer 5"],
    ])
    expect(result.current.condensed).toBe(5)
  })

  it("does not announce notes the resumed conversation already had", async () => {
    api.fetchChatSession.mockResolvedValue({ ...pageOf([saved(5)], 5, true, "s7"), compaction: { through: 5, text: "notes" } })
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("next", "s7").reply, condensed: 5 } })
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.turns).toHaveLength(3)) // the notes' own line, and the turn
    await say(result, "and then?")
    expect(result.current.turns.filter((t) => t.body.includes("now condensed"))).toEqual([])
  })

  it("condenses the conversation, shows the notes as a line of their own and drops the stale meter figure", async () => {
    const { result } = await withReplies()
    expect(result.current.context).toEqual({ used: 3000, limit: 4000, model: "m" })
    api.compactChatSession.mockResolvedValue(notes())
    await act(async () => {
      await result.current.compact()
    })
    expect(api.compactChatSession).toHaveBeenCalledWith("samantha", "s1")
    const lines = result.current.turns.filter((t) => t.role === "system")
    expect(lines.map((t) => [t.kind, t.title ? `${t.title}: ${t.body}` : t.body])).toEqual([
      ["confirmation", "Summarised the first 11 messages to free up room:"],
      ["output", "The notes: The user is building Pantry."],
    ])
    expect(result.current.context).toBeUndefined()
    expect(result.current.compacting).toBe(false)
  })

  it("does not announce the notes again on the next reply that carries the same count", async () => {
    const { result } = await withReplies()
    api.compactChatSession.mockResolvedValue(notes())
    await act(async () => {
      await result.current.compact()
    })
    api.sendChatTurn.mockResolvedValue({ ok: true, reply: { ...ok("more", "s1").reply, condensed: 11 } })
    await say(result, "next")
    expect(result.current.turns.filter((t) => t.body.includes("now condensed"))).toEqual([])
  })

  it("says why nothing was written, and shows the notes already in force", async () => {
    const { result } = await withReplies()
    api.compactChatSession.mockResolvedValue(notes({ status: "nothing", text: "Earlier notes." }))
    await act(async () => {
      await result.current.compact()
    })
    const lines = result.current.turns.filter((t) => t.role === "system").map((t) => [t.kind, t.title ? `${t.title}: ${t.body}` : t.body])
    expect(lines).toEqual([
      ["notice", "Nothing to condense yet: the latest messages always stay as they are."],
      ["output", "The notes now: Earlier notes."],
    ])
    expect(result.current.context).toEqual({ used: 3000, limit: 4000, model: "m" }) // nothing changed
  })

  it.each([
    ["too_small", "notice", "Nothing to gain"],
    ["failed", "error", "The notes could not be written"],
    ["busy", "notice", "Already condensing"],
  ])("says %s in its own words", async (status, kind, words) => {
    const { result } = await withReplies()
    api.compactChatSession.mockResolvedValue(notes({ status, text: "" }))
    await act(async () => {
      await result.current.compact()
    })
    const last = result.current.turns[result.current.turns.length - 1]
    expect(last.kind).toBe(kind)
    expect(last.body).toContain(words)
  })

  it("shows the backend's refusal as an error line", async () => {
    const { result } = await withReplies()
    api.compactChatSession.mockResolvedValue({ ok: false, error: "No session `s1` for `samantha`." })
    await act(async () => {
      await result.current.compact()
    })
    expect(result.current.turns[result.current.turns.length - 1]).toMatchObject({
      kind: "error",
      body: "Couldn't condense the conversation: No session `s1` for `samantha`.",
    })
  })

  it("has nothing to condense before the conversation has started, and asks nothing", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    await act(async () => {
      await result.current.compact()
    })
    expect(api.compactChatSession).not.toHaveBeenCalled()
    expect(result.current.turns.map((t) => t.body)).toEqual(["Nothing to condense yet. This chat is too short."])
  })

  it("is not started a second time while the notes are being written", async () => {
    const { result } = await withReplies()
    let finish: (v: unknown) => void = () => {}
    api.compactChatSession.mockReturnValue(new Promise((resolve) => (finish = resolve)))
    let first: Promise<void> = Promise.resolve()
    act(() => {
      first = result.current.compact()
    })
    expect(result.current.compacting).toBe(true)
    await act(async () => {
      await result.current.compact()
    })
    expect(api.compactChatSession).toHaveBeenCalledTimes(1)
    await act(async () => {
      finish(notes())
      await first
    })
    expect(result.current.compacting).toBe(false)
  })

  it("drops notes that arrive for a conversation that was started over meanwhile", async () => {
    const { result } = await withReplies()
    let finish: (v: unknown) => void = () => {}
    api.compactChatSession.mockReturnValue(new Promise((resolve) => (finish = resolve)))
    let pending: Promise<void> = Promise.resolve()
    act(() => {
      pending = result.current.compact()
    })
    await act(async () => {
      await result.current.newConversation()
    })
    await act(async () => {
      finish(notes())
      await pending
    })
    expect(result.current.turns).toEqual([])
    expect(result.current.compacting).toBe(false)
  })
})


// ADR 057: several conversations of one persona, one state each.
describe("useChat: switching conversations while a reply is being written", () => {
  const held = () => {
    const handle: { land: (r: unknown) => void } = { land: () => {} }
    api.sendChatTurn.mockImplementationOnce(() => new Promise((resolve) => (handle.land = resolve)))
    return handle
  }
  const begin = (result: Parameters<typeof say>[0], text: string) => {
    act(() => result.current.setDraft(text))
    act(() => {
      void result.current.send()
    })
  }

  it("starts a new conversation while the reply is still being written, and the reply lands in the first", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    api.startChatSession.mockResolvedValue("s-new")
    const first = held()
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    begin(result, "about the movies")
    expect(result.current.sending).toBe(true)

    await act(async () => {
      await result.current.newConversation()
    })
    expect(api.startChatSession).toHaveBeenCalledTimes(1)
    expect(result.current.turns).toEqual([])
    expect(result.current.sending).toBe(false) // this conversation is not the one replying
    expect(result.current.sessionId).toBe("s-new")

    await act(async () => first.land(ok("a film reply", "s-old")))
    expect(result.current.turns).toEqual([]) // nothing leaked into the new conversation
    expect(result.current.marks["s-old"]).toEqual({ replying: false, unread: true })

    await act(async () => {
      await result.current.openConversation("s-old")
    })
    expect(result.current.turns.map((t) => t.body)).toEqual(["question 0", "answer 0", "about the movies", "a film reply"])
    expect(result.current.marks["s-old"].unread).toBe(false) // opening it reads it
  })

  it("keeps each conversation's draft and shows the one that is replying as replying when it is opened again", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    api.startChatSession.mockResolvedValue("s-new")
    held()
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    begin(result, "first")
    await act(async () => {
      await result.current.newConversation()
    })
    act(() => result.current.setDraft("half a thought"))
    await act(async () => {
      await result.current.openConversation("s-old")
    })
    expect(result.current.sending).toBe(true)
    expect(result.current.draft).toBe("")
    expect(result.current.marks["s-old"].replying).toBe(true)
    await act(async () => {
      await result.current.openConversation("s-new")
    })
    expect(result.current.draft).toBe("half a thought")
  })

  it("a message in the other conversation is sent at once, with that conversation's id", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    api.startChatSession.mockResolvedValue("s-new")
    held()
    api.sendChatTurn.mockResolvedValueOnce(ok("second answer", "s-new"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    begin(result, "first")
    await act(async () => {
      await result.current.newConversation()
    })
    await say(result, "second")
    expect(api.sendChatTurn.mock.calls.map((c) => [c[0], c[2]])).toEqual([["first", "s-old"], ["second", "s-new"]])
    expect(result.current.turns.map((t) => t.body)).toEqual(["second", "second answer"])
  })

  it("asks for the status, and stops, only the conversation on screen", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    api.cancelChatTurn.mockResolvedValue(true)
    api.sendChatTurn.mockImplementationOnce(
      (_m: string, _p: string, _s: string | undefined, signal: AbortSignal) =>
        new Promise((resolve) => signal.addEventListener("abort", () => resolve({ ok: false, cancelled: true })))
    )
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { result } = renderHook(() => useChat("samantha"))
    await vi.waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    begin(result, "hi")
    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    expect(api.fetchChatStatus).toHaveBeenCalledWith("samantha", "s-old")
    await act(async () => {
      await result.current.stop()
    })
    expect(api.cancelChatTurn).toHaveBeenCalledWith("samantha", "s-old")
  })

  it("does nothing when the conversation on screen is already blank", async () => {
    const { result } = renderHook(() => useChat("samantha"))
    await act(async () => {
      await result.current.newConversation()
    })
    expect(api.startChatSession).not.toHaveBeenCalled()
  })

  it("shows the blank conversation it already holds when the backend answers with that one", async () => {
    api.fetchChatSession.mockImplementation((_p: string, o: { sessionId?: string } = {}) =>
      Promise.resolve(o.sessionId === "s-old" ? pageOf([saved(0)], 0, false, "s-old") : pageOf([], 0, false, "s-blank"))
    )
    api.startChatSession.mockResolvedValue("s-blank")
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-blank"))
    act(() => result.current.setDraft("kept in the blank one"))
    await act(async () => {
      await result.current.openConversation("s-old")
    })
    await act(async () => {
      await result.current.newConversation() // the backend reuses its latest blank one, which this browser holds
    })
    expect(result.current.sessionId).toBe("s-blank")
    expect(result.current.draft).toBe("kept in the blank one") // the same conversation, not a second one for that id
    expect(result.current.turns).toEqual([])
    await act(async () => {
      await result.current.openConversation("s-old")
    })
    expect(result.current.turns.map((t) => t.body)).toEqual(["question 0", "answer 0"])
  })

  it("opens an earlier conversation from its saved turns, and says so when it cannot be read", async () => {
    api.fetchChatSession.mockImplementation((_p: string, o: { sessionId?: string } = {}) =>
      Promise.resolve(o.sessionId === "s-2" ? pageOf([saved(0), saved(1)], 0, false, "s-2") : null)
    )
    const { result } = renderHook(() => useChat("samantha"))
    await act(async () => {
      expect(await result.current.openConversation("s-2")).toBe(true)
    })
    expect(result.current.sessionId).toBe("s-2")
    expect(result.current.turns).toHaveLength(4)
    await act(async () => {
      expect(await result.current.openConversation("gone")).toBe(false)
    })
    expect(result.current.sessionId).toBe("s-2")
  })

  it("puts a fresh conversation in the place of the one on screen when that one is deleted", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    api.startChatSession.mockResolvedValue("s-new")
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    await act(async () => {
      await result.current.forgetConversation("s-old")
    })
    expect(result.current.turns).toEqual([])
    expect(result.current.sessionId).toBe("s-new")
    expect(result.current.marks["s-old"]).toBeUndefined()
  })

  it("leaves the conversation on screen alone when a different one is deleted", async () => {
    api.fetchChatSession.mockResolvedValue(pageOf([saved(0)], 0, false, "s-old"))
    const { result } = renderHook(() => useChat("samantha"))
    await waitFor(() => expect(result.current.sessionId).toBe("s-old"))
    await act(async () => {
      await result.current.forgetConversation("some-other")
    })
    expect(result.current.sessionId).toBe("s-old")
    expect(api.startChatSession).not.toHaveBeenCalled()
  })

  it("tells the list when something it shows may have changed", async () => {
    api.sendChatTurn.mockResolvedValue(ok("hi", "s1"))
    const { result } = renderHook(() => useChat("samantha"))
    const before = result.current.listVersion
    await say(result, "hello")
    expect(result.current.listVersion).toBeGreaterThan(before)
  })
})
