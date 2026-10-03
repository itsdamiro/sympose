import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchRelated, NO_RELATED } from "./vault-related-api"

afterEach(() => vi.unstubAllGlobals())

describe("fetchRelated (docs/decisions/066)", () => {
  it("asks for the open note's neighbours as the persona and returns them", async () => {
    const body = { path: "a.md", enabled: true, related: [{ rel_path: "b.md", title: "b", percent: 50 }] }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) })
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchRelated("Notes/a b.md", "samantha")).toEqual({ enabled: true, related: body.related, indexing: false })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/vault/related?path=Notes%2Fa+b.md&persona=samantha")
  })

  it("says off when the setting is off, and gives nothing for an error or an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ enabled: false, related: [] }) }))
    expect(await fetchRelated("a.md", "samantha")).toEqual({ enabled: false, related: [], indexing: false })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    expect(await fetchRelated("a.md", "samantha")).toEqual(NO_RELATED)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchRelated("a.md", "samantha")).toEqual(NO_RELATED)
  })

  it("treats a reply that does not say it is enabled as off, so the section is hidden", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ related: [] }) }))
    expect((await fetchRelated("a.md", "samantha")).enabled).toBe(false)
  })

  it("treats a reply without a list as none", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ enabled: true }) }))
    expect(await fetchRelated("a.md", "samantha")).toEqual({ enabled: true, related: [], indexing: false })
  })

  it("passes on that the index is still being built", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ enabled: true, indexing: true, related: [] }) }))
    expect((await fetchRelated("a.md", "samantha")).indexing).toBe(true)
  })
})
