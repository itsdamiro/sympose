import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchChanges, fetchDrafts, resolveChanges } from "./persona-changes-api"

const json = (body: unknown, ok = true, status = ok ? 200 : 500) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("fetchChanges", () => {
  it("asks for the note's changes for the persona and encodes the path", async () => {
    const body = { path: "A b/N.md", exists: true, mtime: 1, proposals: [], annotations: [] }
    const fetchMock = vi.fn().mockResolvedValue(json(body))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchChanges("A b/N.md", "samantha")).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith("/api/vault/changes?path=A%20b%2FN.md&persona=samantha")
  })

  it("is null when the backend refuses or is unreachable", async () => {
    vi.spyOn(console, "info").mockImplementation(() => {})
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, false, 404)))
    expect(await fetchChanges("n.md", "x")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchChanges("n.md", "x")).toBeNull()
  })
})

describe("fetchDrafts", () => {
  it("returns the drafts, and nothing when the backend is down", async () => {
    vi.spyOn(console, "info").mockImplementation(() => {})
    const drafts = [{ path: "a.md", name: null, is_new: false, count: 2, time: "t" }]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ drafts })))
    expect(await fetchDrafts("samantha")).toEqual(drafts)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchDrafts("samantha")).toEqual([])
  })
})

describe("resolveChanges", () => {
  it("sends the named ids, or all", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ resolved: ["a"] }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await resolveChanges("n.md", "samantha", ["a"])).toEqual({ ok: true, resolved: ["a"] })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ path: "n.md", persona: "samantha", ids: ["a"] })
    await resolveChanges("n.md", "samantha", "all")
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ path: "n.md", persona: "samantha", all: true })
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "No such pending change." }, false, 404)))
    expect(await resolveChanges("n.md", "x", ["a"])).toEqual({ ok: false, error: "No such pending change." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await resolveChanges("n.md", "x", "all")).toEqual({ ok: false, error: "the Sympose backend is not reachable" })
  })
})

import { addComment, changeComment, deleteComment, replyToComment } from "./persona-changes-api"

describe("comments", () => {
  it("adds a comment with the editor's own context and returns it", async () => {
    const comment = { id: "c1" }
    const fetchMock = vi.fn().mockResolvedValue(json(comment))
    vi.stubGlobal("fetch", fetchMock)

    const result = await addComment({ path: "n.md", persona: "samantha", quote: "raised", before: "are ", after: ".", text: "why?" })

    expect(result).toEqual({ ok: true, comment })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/vault/annotations")
    expect(fetchMock.mock.calls[0][1].method).toBe("POST")
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ path: "n.md", persona: "samantha", quote: "raised", before: "are ", after: ".", text: "why?" })
  })

  it("replies under a comment by naming it, with no passage of its own", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ id: "r1" }))
    vi.stubGlobal("fetch", fetchMock)

    await replyToComment({ path: "n.md", persona: "samantha", replyTo: "c1", text: "because" })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ path: "n.md", persona: "samantha", reply_to: "c1", text: "because" })
  })

  it("resolves a comment with PATCH and gives no comment back", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ path: "n.md", id: "c1" }))
    vi.stubGlobal("fetch", fetchMock)

    expect(await changeComment({ path: "n.md", persona: "samantha", id: "c1", state: "resolved" })).toEqual({ ok: true, comment: undefined })
    expect(fetchMock.mock.calls[0][1].method).toBe("PATCH")
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ path: "n.md", persona: "samantha", id: "c1", state: "resolved" })
  })

  it("deletes with the path, id and persona in the address, encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({}))
    vi.stubGlobal("fetch", fetchMock)

    expect(await deleteComment("A b/n.md", "samantha", "c 1")).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith("/api/vault/annotations?path=A%20b%2Fn.md&id=c%201&persona=samantha", { method: "DELETE" })
  })

  it("gives the reason when refused and says so when the backend is unreachable, for each", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "No such comment." }, false, 404)))
    expect(await replyToComment({ path: "n.md", persona: "x", replyTo: "z", text: "" })).toEqual({ ok: false, error: "No such comment." })
    expect(await deleteComment("n.md", "x", "z")).toEqual({ ok: false, error: "No such comment." })

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const down = { ok: false, error: "the Sympose backend is not reachable" }
    expect(await addComment({ path: "n.md", persona: "x", quote: "q", before: "", after: "", text: "" })).toEqual(down)
    expect(await changeComment({ path: "n.md", persona: "x", id: "z", state: "open" })).toEqual(down)
    expect(await deleteComment("n.md", "x", "z")).toEqual(down)
  })
})
