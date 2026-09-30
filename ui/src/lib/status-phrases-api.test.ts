import { afterEach, describe, expect, it, vi } from "vitest"

import { GENERIC_PHRASES, fetchStatusPhrases } from "./status-phrases-api"

const json = (body: unknown, ok = true, status = 200) => ({ ok, status, json: () => Promise.resolve(body) }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("fetchStatusPhrases", () => {
  it("asks for the persona's phrases and returns them with whether they are its own", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ phrases: ["One…", "Two…"], own: true }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchStatusPhrases("sam ntha")).toEqual({ phrases: ["One…", "Two…"], own: true })
    expect(fetchMock).toHaveBeenCalledWith("/api/chat/status-phrases?persona=sam%20ntha")
  })

  it("says the phrases are not its own while they are the generic ones", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ phrases: ["Generic…"], own: false })))
    expect((await fetchStatusPhrases("s"))?.own).toBe(false)
  })

  it("falls back to generic phrases when the answer holds none, and treats a missing flag as not its own", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ phrases: [] })))
    expect(await fetchStatusPhrases("s")).toEqual({ phrases: GENERIC_PHRASES, own: false })
  })

  it("is null when the backend cannot answer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, false, 404)))
    expect(await fetchStatusPhrases("s")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchStatusPhrases("s")).toBeNull()
  })
})
