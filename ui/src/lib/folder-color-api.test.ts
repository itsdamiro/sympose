import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchFolderColor, saveFolderColor } from "./folder-color-api"

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: () => Promise.resolve(body) } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("fetchFolderColor", () => {
  it("asks about the folder's path and persona and reads its own colours", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ editable: true, accent: "#7c3aed", accent_dark: "#b98cff" }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchFolderColor("Projects/my app", "samantha")).toEqual({
      editable: true,
      accent: "#7c3aed",
      accentDark: "#b98cff",
    })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/vault/folder/color?path=Projects%2Fmy%20app&persona=samantha")
  })

  it("reads a colour that is not set as null, and anything but true as not editable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ editable: "yes", accent: "", accent_dark: 3 })))
    expect(await fetchFolderColor("Projects/x", "samantha")).toEqual({ editable: false, accent: null, accentDark: null })
  })

  it("gives null when the backend answers an error or cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 409)))
    expect(await fetchFolderColor("Projects/x", "samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    expect(await fetchFolderColor("Projects/x", "samantha")).toBeNull()
  })
})

describe("saveFolderColor", () => {
  it("puts the path, both colours and the persona", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ path: "Projects/x", created: true }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await saveFolderColor("Projects/x", { accent: "#be123c", accentDark: "#f2889b" }, "samantha")).toEqual({
      ok: true,
      created: true,
    })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/vault/folder/color")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({
      path: "Projects/x",
      accent: "#be123c",
      accent_dark: "#f2889b",
      persona: "samantha",
    })
  })

  it("sends null for both to clear the colour", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ created: false }))
    vi.stubGlobal("fetch", fetchMock)
    await saveFolderColor("Projects/x", { accent: null, accentDark: null }, "samantha")
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ accent: null, accent_dark: null })
  })

  it("carries the server's reason when it refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 400, json: () => Promise.resolve({ detail: "Not a colour." }) } as Response))
    expect(await saveFolderColor("Projects/x", { accent: "red", accentDark: null }, "samantha")).toEqual({ ok: false, error: "Not a colour." })
  })

  it("says Sympose isn't responding when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    const res = await saveFolderColor("Projects/x", { accent: null, accentDark: null }, "samantha")
    expect(res.ok).toBe(false)
    expect(!res.ok && res.error).toMatch(/isn't responding/)
  })
})
