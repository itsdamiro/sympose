import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchFolderSettings, saveFolderSettings } from "./folder-settings-api"

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: () => Promise.resolve(body) } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("fetchFolderSettings", () => {
  it("asks about the folder and persona and reads the note's values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        editable: true,
        defined: true,
        purpose: "Films.",
        template: ["role:", "tags: []"],
        template_source: "note",
        icon: "film-roll",
        accent: "#be123c",
        accent_dark: null,
      })
    )
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchFolderSettings("Books & Films", "samantha")).toEqual({
      editable: true,
      defined: true,
      purpose: "Films.",
      template: ["role:", "tags: []"],
      templateSource: "note",
      icon: "film-roll",
      accent: "#be123c",
      accentDark: null,
    })
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/vault/folder/settings?folder=Books%20%26%20Films&persona=samantha"
    )
  })

  it("reads an unknown source as the setting's keys and anything but true as not editable or defined", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ editable: "yes", defined: 1, template_source: "??", icon: "" }))
    )
    const found = await fetchFolderSettings("Books", "samantha")
    expect(found).toMatchObject({ editable: false, defined: false, templateSource: "settings", icon: null })
  })

  it("fills in what a partial answer leaves out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ editable: false })))
    expect(await fetchFolderSettings("Books", "samantha")).toEqual({
      editable: false,
      defined: false,
      purpose: "",
      template: [],
      templateSource: "settings",
      icon: null,
      accent: null,
      accentDark: null,
    })
  })

  it("keeps only the text lines of a template", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ template: ["a:", 3, null, "b:"] })))
    expect((await fetchFolderSettings("Books", "samantha"))?.template).toEqual(["a:", "b:"])
  })

  it("is null when the backend is unreachable or answers an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchFolderSettings("Books", "samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 409)))
    expect(await fetchFolderSettings("Books", "samantha")).toBeNull()
  })
})

describe("saveFolderSettings", () => {
  const input = { purpose: "What I read.", template: ["title:"], icon: "book", accent: "#1d4ed8", accentDark: null }

  it("PUTs the whole dialog with the colours under their file names, and says whether the note was created", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ path: "Books", created: true }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await saveFolderSettings("Books", input, "samantha")).toEqual({ ok: true, created: true })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/vault/folder/settings")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({
      path: "Books",
      purpose: "What I read.",
      template: ["title:"],
      icon: "book",
      accent: "#1d4ed8",
      accent_dark: null,
      persona: "samantha",
    })
  })

  it("says the note was edited when the server did not create it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ path: "Books", created: false })))
    expect(await saveFolderSettings("Books", input, "samantha")).toEqual({ ok: true, created: false })
  })

  it("returns the server's reason for a refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "A template line cannot start a code fence." }, false, 400))
    )
    expect(await saveFolderSettings("Books", input, "samantha")).toEqual({
      ok: false,
      error: "A template line cannot start a code fence.",
    })
  })

  it("has its own words for an error with no reason, and for a server that is not answering", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.reject(new Error("x")) }))
    expect(await saveFolderSettings("Books", input, "samantha")).toEqual({
      ok: false,
      error: "Couldn't save the folder settings (code 500). Try again.",
    })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const offline = await saveFolderSettings("Books", input, "samantha")
    expect(offline.ok).toBe(false)
    expect(!offline.ok && offline.error).toMatch(/isn't responding/)
  })
})
