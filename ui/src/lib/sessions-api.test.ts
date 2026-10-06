import { afterEach, describe, expect, it, vi } from "vitest"

import {
  deleteSession,
  emptyBinnedSessions,
  fetchBinnedSessions,
  fetchSessions,
  purgeSession,
  restoreSession,
  updateSession,
} from "./sessions-api"

function reply(body: unknown, status = 200) {
  return { ok: status < 400, status, json: () => Promise.resolve(body) } as Response
}
const stub = (response: Response) => {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe("the conversation list", () => {
  it("reads the persona's rows, and gives null rather than an empty list when it cannot", async () => {
    const rows = [{ id: "a", title: "t", turns: 1, created_at: null, updated_at: null, pinned_at: null, replying: false }]
    const fetchMock = stub(reply({ sessions: rows }))
    expect(await fetchSessions("samantha")).toEqual(rows)
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/sessions?persona=samantha", undefined)
    stub(reply({}, 500))
    expect(await fetchSessions("samantha")).toBeNull()
  })

  it("renames and pins with one PATCH to the conversation's own address", async () => {
    const fetchMock = stub(reply({ id: "a/b", title: "New", pinned_at: null }))
    const out = await updateSession("samantha", "a/b", { title: "New", pinned: true })
    expect(out.ok && out.value.title).toBe("New")
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/chat/session/a%2Fb")
    expect(init.method).toBe("PATCH")
    expect(JSON.parse(init.body)).toEqual({ persona: "samantha", title: "New", pinned: true })
  })

  it("gives the backend's reason when a change is refused", async () => {
    stub(reply({ detail: "A reply is being written in that conversation. Stop it first." }, 409))
    expect(await deleteSession("samantha", "a")).toEqual({ ok: false, error: "A reply is being written in that conversation. Stop it first." })
  })

  it("says the backend is not reachable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    const out = await deleteSession("samantha", "a")
    expect(!out.ok && out.error).toContain("isn't responding")
  })

  it("deletes with DELETE on the conversation, naming the persona", async () => {
    const fetchMock = stub(reply({ deleted: "a" }))
    expect((await deleteSession("samantha", "a")).ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/session/a?persona=samantha", { method: "DELETE" })
  })
})

describe("the bin's conversations", () => {
  it("lists them, restores one by its name in the bin, deletes one for good, and empties", async () => {
    const rows = [{ id: "a.2", title: "t", turns: 1, deleted_at: 1, pinned_at: null }]
    stub(reply({ sessions: rows }))
    expect(await fetchBinnedSessions("samantha")).toEqual(rows)

    let fetchMock = stub(reply({ restored: "a.2" }))
    expect((await restoreSession("samantha", "a.2")).ok).toBe(true)
    expect(fetchMock.mock.calls[0][0]).toBe("/api/chat/sessions/bin/restore")
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ persona: "samantha", id: "a.2" })

    fetchMock = stub(reply({ deleted: "a.2" }))
    expect((await purgeSession("samantha", "a.2")).ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/sessions/bin?persona=samantha&id=a.2", { method: "DELETE" })

    stub(reply({ deleted: 3 }))
    expect(await emptyBinnedSessions("samantha")).toEqual({ ok: true, value: 3 })
  })

  it("is refused with the reason when one by that id is already back", async () => {
    stub(reply({ detail: "A conversation with that id is already there." }, 409))
    const out = await restoreSession("samantha", "a")
    expect(!out.ok && out.error).toBe("A conversation with that id is already there.")
  })
})
