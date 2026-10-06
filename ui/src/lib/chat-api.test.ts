import { afterEach, describe, expect, it, vi } from "vitest"

import { cancelChatTurn, compactChatSession, fetchChatStatus, fetchChatSession, fetchContextEstimate, sendChatTurn, startChatSession } from "./chat-api"

const reply = { reply: "Hi", session_id: "s1", model: "ollama_chat/gemma2:9b", ttft_ms: 400, truncated: false, saved: true, cloud: [], withheld: [] }

function stub(response: Partial<Response> & { json: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue(response as Response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe("sendChatTurn", () => {
  it("posts the message, the persona and the session, and returns the reply", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve(reply) })
    const res = await sendChatTurn("hello", "samantha", "s0")
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/chat/turn")
    expect(JSON.parse(init.body as string)).toEqual({ message: "hello", persona: "samantha", session_id: "s0", edits: true })
    expect(res).toEqual({ ok: true, reply })
  })

  it("sends the note open in the editor with the message, and says the screen can show a proposal", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve(reply) })
    await sendChatTurn("make it four", "samantha", "s0", undefined, { path: "a.md", text: "I run three times." })
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({
      message: "make it four", persona: "samantha", session_id: "s0", edits: true, open_note: { path: "a.md", text: "I run three times." },
    })
  })

  it("returns the backend's own reason when it refuses", async () => {
    stub({ ok: false, status: 409, json: () => Promise.resolve({ detail: "local models only" }) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "local models only" })
  })

  it("says the backend is not reachable instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const res = await sendChatTurn("hello", "samantha")
    expect(res.ok).toBe(false)
    expect(!res.ok && res.error).toContain("isn't responding")
  })

  it("tells a dev proxy's bare 502 (nothing behind it) from the backend's own 502 with a reason", async () => {
    stub({ ok: false, status: 502, json: () => Promise.reject(new Error("not json")) })
    const bare = await sendChatTurn("hello", "samantha")
    expect(!bare.ok && bare.error).toContain("isn't responding")
    expect(!bare.ok && bare.error).toContain("Check that it's still running")
    stub({ ok: false, status: 502, json: () => Promise.resolve({ detail: "the model is not running" }) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "the model is not running" })
  })

  it("keeps a plain status for an error that is not a gateway one", async () => {
    stub({ ok: false, status: 500, json: () => Promise.reject(new Error("not json")) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "Something failed on Sympose's side (code 500). Try again." })
  })

  it("reads a reply the backend says was stopped as cancelled, not as a reply", async () => {
    stub({ ok: true, status: 200, json: () => Promise.resolve({ cancelled: true }) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, cancelled: true })
  })

  it("passes the abort signal on, and reads an aborted wait as cancelled rather than as an unreachable backend", async () => {
    const abort = new AbortController()
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      abort.abort()
      return Promise.reject(Object.assign(new Error("aborted"), { name: "AbortError", signal: init.signal }))
    })
    vi.stubGlobal("fetch", fetchMock)
    expect(await sendChatTurn("hello", "samantha", "s0", abort.signal)).toEqual({ ok: false, cancelled: true })
    expect((fetchMock.mock.calls[0][1] as RequestInit).signal).toBe(abort.signal)
  })

  it("is not cancelled when the backend fails for another reason and nothing was aborted", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const res = await sendChatTurn("hello", "samantha", undefined, new AbortController().signal)
    expect(!res.ok && "cancelled" in res && res.cancelled).toBeFalsy()
  })
})

describe("cancelChatTurn", () => {
  it("asks the backend to stop a first message's reply, which has no conversation id yet, and says whether it was accepted", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ stopping: true }) })
    expect(await cancelChatTurn("samantha")).toBe(true)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect([url, init.method, JSON.parse(init.body as string)]).toEqual(["/api/chat/cancel", "POST", { persona: "samantha", unnamed: true }])
  })

  it("names the conversation when it has an id, so only that one is stopped", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ stopping: true }) })
    await cancelChatTurn("samantha", "s1")
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({ persona: "samantha", session_id: "s1", unnamed: false })
  })

  it("is false when there was nothing to stop, when the backend refuses, and when it cannot be reached", async () => {
    stub({ ok: true, status: 200, json: () => Promise.resolve({ stopping: false }) })
    expect(await cancelChatTurn("samantha")).toBe(false)
    stub({ ok: false, status: 404, json: () => Promise.resolve({ stopping: true }) })
    expect(await cancelChatTurn("samantha")).toBe(false)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await cancelChatTurn("samantha")).toBe(false)
  })
})

describe("fetchContextEstimate", () => {
  it("asks for that persona's conversation and returns the figures", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ used: 3812, limit: 6144 }) })
    expect(await fetchContextEstimate("sam ntha", "s 1")).toEqual({ used: 3812, limit: 6144 })
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/context?persona=sam%20ntha&session_id=s%201")
  })

  it("is null when there is nothing to count, or when only one figure is known", async () => {
    stub({ ok: true, status: 200, json: () => Promise.resolve({ used: null, limit: null }) })
    expect(await fetchContextEstimate("s", "s1")).toBeNull()
    stub({ ok: true, status: 200, json: () => Promise.resolve({ used: 5, limit: null }) })
    expect(await fetchContextEstimate("s", "s1")).toBeNull()
  })

  it("keeps a figure of zero tokens", async () => {
    stub({ ok: true, status: 200, json: () => Promise.resolve({ used: 0, limit: 100 }) })
    expect(await fetchContextEstimate("s", "s1")).toEqual({ used: 0, limit: 100 })
  })

  it("is null when the backend answers an error or cannot be reached", async () => {
    stub({ ok: false, status: 404, json: () => Promise.resolve({}) })
    expect(await fetchContextEstimate("s", "s1")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchContextEstimate("s", "s1")).toBeNull()
  })
})

describe("fetchChatStatus", () => {
  it("returns the phase and the index build the backend reports", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ phase: "reading", indexing: 40 }) })
    expect(await fetchChatStatus("samantha")).toEqual({ phase: "reading", indexing: 40 })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/status?persona=samantha")
  })

  it("is empty when nothing is running, on an error, and when unreachable", async () => {
    const none = { phase: null, indexing: null }
    stub({ ok: true, status: 200, json: () => Promise.resolve({ phase: null, indexing: null }) })
    expect(await fetchChatStatus("samantha")).toEqual(none)
    stub({ ok: true, status: 200, json: () => Promise.resolve({ phase: "asking" }) })
    expect(await fetchChatStatus("samantha")).toEqual({ phase: "asking", indexing: null })
    stub({ ok: false, status: 500, json: () => Promise.resolve({}) })
    expect(await fetchChatStatus("samantha")).toEqual(none)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchChatStatus("samantha")).toEqual(none)
  })
})

describe("fetchChatSession", () => {
  const page = { session_id: "s1", turns: [], start: 0, total: 0, has_more: false }

  it("asks for the latest turns of a persona, or the section before a turn in a given conversation", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve(page) })
    expect(await fetchChatSession("samantha", { limit: 20 })).toEqual(page)
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/session?persona=samantha&limit=20")
    await fetchChatSession("samantha", { sessionId: "s1", before: 40, limit: 20 })
    expect(fetchMock.mock.calls[1][0]).toBe("/api/chat/session?persona=samantha&session_id=s1&before=40&limit=20")
  })

  it("asks for turn 0 as a real bound, not as if none was given", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve(page) })
    await fetchChatSession("samantha", { sessionId: "s1", before: 0 })
    expect(fetchMock.mock.calls[0][0]).toContain("before=0")
  })

  it("is null on an error and when unreachable", async () => {
    stub({ ok: false, status: 404, json: () => Promise.resolve({}) })
    expect(await fetchChatSession("samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchChatSession("samantha")).toBeNull()
  })
})

describe("startChatSession", () => {
  it("posts the persona and returns the new session's id", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ session_id: "s-new" }) })
    expect(await startChatSession("samantha")).toBe("s-new")
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/chat/session")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({ persona: "samantha" })
  })

  it("is null on an error and when unreachable", async () => {
    stub({ ok: false, status: 500, json: () => Promise.resolve({}) })
    expect(await startChatSession("samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await startChatSession("samantha")).toBeNull()
  })
})

describe("compactChatSession", () => {
  const done = { status: "done", covered: 11, text: "The user is building Pantry.", before: 600, after: 120 }

  it("posts the persona and the conversation and returns what happened", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve(done) })
    const res = await compactChatSession("samantha", "s1")
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/chat/compact")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({ persona: "samantha", session_id: "s1" })
    expect(res).toEqual({ ok: true, result: done })
  })

  it("returns the backend's own reason when it refuses", async () => {
    stub({ ok: false, status: 404, json: () => Promise.resolve({ detail: "No session `s1` for `samantha`." }) })
    expect(await compactChatSession("samantha", "s1")).toEqual({ ok: false, error: "No session `s1` for `samantha`." })
  })

  it("says the backend is not reachable instead of throwing, and tells a dev proxy's bare 502 apart", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const down = await compactChatSession("samantha", "s1")
    expect(!down.ok && down.error).toContain("isn't responding")
    stub({ ok: false, status: 502, json: () => Promise.reject(new Error("not json")) })
    const bare = await compactChatSession("samantha", "s1")
    expect(!bare.ok && bare.error).toContain("isn't responding")
  })
})
