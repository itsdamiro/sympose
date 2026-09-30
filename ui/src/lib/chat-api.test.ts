import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchChatPhase, fetchChatSession, sendChatTurn, startChatSession } from "./chat-api"

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
    expect(JSON.parse(init.body as string)).toEqual({ message: "hello", persona: "samantha", session_id: "s0" })
    expect(res).toEqual({ ok: true, reply })
  })

  it("returns the backend's own reason when it refuses", async () => {
    stub({ ok: false, status: 409, json: () => Promise.resolve({ detail: "local models only" }) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "local models only" })
  })

  it("says the backend is not reachable instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const res = await sendChatTurn("hello", "samantha")
    expect(res.ok).toBe(false)
    expect(!res.ok && res.error).toContain("not reachable")
  })

  it("tells a dev proxy's bare 502 (nothing behind it) from the backend's own 502 with a reason", async () => {
    stub({ ok: false, status: 502, json: () => Promise.reject(new Error("not json")) })
    const bare = await sendChatTurn("hello", "samantha")
    expect(!bare.ok && bare.error).toContain("not reachable")
    expect(!bare.ok && bare.error).toContain("Is it running")
    stub({ ok: false, status: 502, json: () => Promise.resolve({ detail: "the model is not running" }) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "the model is not running" })
  })

  it("keeps a plain status for an error that is not a gateway one", async () => {
    stub({ ok: false, status: 500, json: () => Promise.reject(new Error("not json")) })
    expect(await sendChatTurn("hello", "samantha")).toEqual({ ok: false, error: "HTTP 500" })
  })
})

describe("fetchChatPhase", () => {
  it("returns the phase the backend reports", async () => {
    const fetchMock = stub({ ok: true, status: 200, json: () => Promise.resolve({ phase: "reading" }) })
    expect(await fetchChatPhase("samantha")).toBe("reading")
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/status?persona=samantha")
  })

  it("is null when nothing is running, on an error, and when unreachable", async () => {
    stub({ ok: true, status: 200, json: () => Promise.resolve({ phase: null }) })
    expect(await fetchChatPhase("samantha")).toBeNull()
    stub({ ok: false, status: 500, json: () => Promise.resolve({}) })
    expect(await fetchChatPhase("samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchChatPhase("samantha")).toBeNull()
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
