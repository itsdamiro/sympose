import { afterEach, describe, expect, it, vi } from "vitest"

import {
  NO_HIDDEN,
  fetchHidden,
  hidePath,
  setShowDefinitionNotes,
  unhidePath,
} from "./vault-hidden-api"

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: () => Promise.resolve(body) } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("fetchHidden", () => {
  it("returns the list and the definition-notes switch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ hidden: ["Drafts"], showDefinitionNotes: true })
      )
    )
    expect(await fetchHidden()).toEqual({
      hidden: ["Drafts"],
      showDefinitionNotes: true,
    })
  })

  it("shows nothing hidden when the backend is unreachable or answers an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchHidden()).toEqual(NO_HIDDEN)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 500)))
    expect(await fetchHidden()).toEqual(NO_HIDDEN)
  })

  it("fills in what a partial answer leaves out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({})))
    expect(await fetchHidden()).toEqual(NO_HIDDEN)
  })
})

describe("changing the list", () => {
  it("hides with a POST of the path and returns the new state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ hidden: ["A/b.md"], showDefinitionNotes: false }))
    vi.stubGlobal("fetch", fetchMock)
    const result = await hidePath("A/b.md")
    expect(result).toEqual({
      ok: true,
      state: { hidden: ["A/b.md"], showDefinitionNotes: false },
    })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/vault/hidden")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body)).toEqual({ path: "A/b.md" })
  })

  it("unhides with a DELETE, the path encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ hidden: [] }))
    vi.stubGlobal("fetch", fetchMock)
    await unhidePath("My notes/a&b.md")
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/vault/hidden?path=My%20notes%2Fa%26b.md")
    expect(init.method).toBe("DELETE")
  })

  it("sets the definition-notes switch with a PUT", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ hidden: [], showDefinitionNotes: true }))
    vi.stubGlobal("fetch", fetchMock)
    const result = await setShowDefinitionNotes(true)
    expect(result.ok && result.state.showDefinitionNotes).toBe(true)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/vault/hidden/definitions")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({ show: true })
  })

  it("passes on the server's own reason when it refuses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "`..` is not a vault-relative path." }, false, 400))
    )
    expect(await hidePath("..")).toEqual({
      ok: false,
      error: "`..` is not a vault-relative path.",
    })
  })

  it("says the backend is unreachable rather than throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const result = await hidePath("a")
    expect(result.ok).toBe(false)
    expect(!result.ok && result.error).toContain("backend unreachable")
  })
})
