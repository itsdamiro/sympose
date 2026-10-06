import { afterEach, describe, expect, it, vi } from "vitest"

import {
  fetchPendingRewrite,
  fetchPersonaFile,
  listPersonaFiles,
  resetPersonaSoul,
  resolvePendingRewrite,
  savePersonaFile,
} from "./persona-files-api"

function stub(response: Partial<Response> & { json: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue(response as Response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}
const ok = (body: unknown) => ({ ok: true, status: 200, json: () => Promise.resolve(body) })
const refused = (status: number, detail: unknown) => ({ ok: false, status, json: () => Promise.resolve({ detail }) })

afterEach(() => vi.unstubAllGlobals())

describe("listPersonaFiles", () => {
  it("lists the persona's files, for the persona it is asked about", async () => {
    const files = [{ name: "soul.md", label: "Soul", description: "d", exists: true, local: false, pending: false }]
    const fetchMock = stub(ok({ files }))
    expect(await listPersonaFiles("sam antha")).toEqual(files)
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/sam%20antha/files")
  })

  it("is null when the backend cannot say", async () => {
    stub(refused(404, "no persona"))
    expect(await listPersonaFiles("nobody")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await listPersonaFiles("samantha")).toBeNull()
  })
})

describe("fetchPersonaFile", () => {
  it("reads one file whole with its mtime", async () => {
    const file = { name: "profile.md", content: "likes small steps", mtime: 12.5, local: false }
    const fetchMock = stub(ok(file))
    expect(await fetchPersonaFile("samantha", "profile.md")).toEqual(file)
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/samantha/files/profile.md")
  })

  it("is null when it cannot be read", async () => {
    stub(refused(500, "Couldn't read as text"))
    expect(await fetchPersonaFile("samantha", "profile.md")).toBeNull()
  })
})

describe("savePersonaFile", () => {
  it("saves the content with the mtime it was opened at and returns the one the next save presents", async () => {
    const fetchMock = stub(ok({ name: "soul.md", mtime: 99, local: true }))
    expect(await savePersonaFile("samantha", "soul.md", "my voice", 12)).toEqual({ ok: true, mtime: 99, local: true })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect([url, init.method, JSON.parse(init.body as string)]).toEqual([
      "/api/personas/samantha/files/soul.md", "PUT", { content: "my voice", expected_mtime: 12 },
    ])
  })

  it("reads a change made meanwhile as a conflict, with the backend's own words", async () => {
    stub(refused(409, "`soul.md` changed on disk since it was opened — reload before saving."))
    expect(await savePersonaFile("samantha", "soul.md", "x", 12)).toEqual({
      ok: false, error: "`soul.md` changed on disk since it was opened — reload before saving.", conflict: true,
    })
  })

  it("says the backend is unreachable instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const res = await savePersonaFile("samantha", "soul.md", "x")
    expect(res.ok).toBe(false)
    expect(!res.ok && res.error).toContain("isn't responding")
  })
})

describe("resetPersonaSoul", () => {
  it("asks for the shipped soul back and says whether there was a copy to set aside", async () => {
    const fetchMock = stub(ok({ removed: true }))
    expect(await resetPersonaSoul("samantha")).toBe(true)
    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toBe("/api/personas/samantha/files/soul.md/reset")
    stub(ok({ removed: false }))
    expect(await resetPersonaSoul("samantha")).toBe(false)
    stub(refused(404, "x"))
    expect(await resetPersonaSoul("samantha")).toBeNull()
  })
})

describe("rewrites waiting for review", () => {
  it("reads the proposal and its diff, or null when none is waiting", async () => {
    const fetchMock = stub(ok({ text: "new", diff: "-old\n+new" }))
    expect(await fetchPendingRewrite("samantha", "profile.md")).toEqual({ text: "new", diff: "-old\n+new" })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/samantha/files/profile.md/pending")
    stub(refused(404, "No rewrite of `profile.md` is waiting."))
    expect(await fetchPendingRewrite("samantha", "profile.md")).toBeNull()
  })

  it("accepts or discards it, and gives the reason when that fails", async () => {
    const fetchMock = stub(ok({ ok: true }))
    expect(await resolvePendingRewrite("samantha", "profile.md", "accept")).toEqual({ ok: true })
    expect(await resolvePendingRewrite("samantha", "profile.md", "discard")).toEqual({ ok: true })
    expect((fetchMock.mock.calls[0] as [string, RequestInit]).slice(0, 2)).toEqual([
      "/api/personas/samantha/files/profile.md/pending/accept", { method: "POST" },
    ])
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[0]).toBe("/api/personas/samantha/files/profile.md/pending/discard")
    stub(refused(404, "No rewrite of `profile.md` is waiting."))
    expect(await resolvePendingRewrite("samantha", "profile.md", "accept")).toEqual({
      ok: false, error: "No rewrite of `profile.md` is waiting.",
    })
  })
})
