import { afterEach, describe, expect, it, vi } from "vitest"

import {
  createFolderDefinition,
  fetchNoteTemplate,
} from "./vault-definition-api"

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: () => Promise.resolve(body) } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("fetchNoteTemplate", () => {
  it("asks about the folder and persona, and returns the lines, their source and whether it is definable", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ lines: ["title: x", "tags: []"], source: "vault", definable: true })
    )
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchNoteTemplate("Books & Films", "samantha")).toEqual({
      lines: ["title: x", "tags: []"],
      source: "vault",
      definable: true,
    })
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/vault/note-template?folder=Books%20%26%20Films&persona=samantha"
    )
  })

  it("reads anything but `vault` as the setting's keys, and anything but true as not definable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ lines: ["title:"], source: "??", definable: "yes" })
      )
    )
    const found = await fetchNoteTemplate("Books", "samantha")
    expect(found?.source).toBe("settings")
    expect(found?.definable).toBe(false)
  })

  it("fills in what a partial answer leaves out; without `definable` it is not definable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({})))
    expect(await fetchNoteTemplate("Books", "samantha")).toEqual({
      lines: [],
      source: "settings",
      definable: false,
    })
  })

  it("is null when the backend is unreachable or answers an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchNoteTemplate("Books", "samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 404)))
    expect(await fetchNoteTemplate("Books", "samantha")).toBeNull()
  })
})

describe("createFolderDefinition", () => {
  it("posts the folder, purpose, lines and persona", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ path: "Books" }, true, 201))
    vi.stubGlobal("fetch", fetchMock)
    expect(
      await createFolderDefinition("Books", "What I read.", ["title:", "tags: []"], "samantha")
    ).toEqual({ ok: true, path: "Books" })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/vault/folder/definition")
    expect(init.method).toBe("POST")
    expect(JSON.parse(init.body as string)).toEqual({
      path: "Books",
      purpose: "What I read.",
      template: ["title:", "tags: []"],
      persona: "samantha",
    })
  })

  it("carries the server's reason when the text is refused", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "A template line cannot start a code fence." }, false, 400)
      )
    )
    expect(await createFolderDefinition("Books", "", ["```"], "samantha")).toEqual({
      ok: false,
      error: "A template line cannot start a code fence.",
    })
  })

  it("names the status when the answer has no reason, and the network when it fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 502, json: () => Promise.reject(new Error("x")) })
    )
    const failed = await createFolderDefinition("Books", "", [], "samantha")
    expect(failed.ok).toBe(false)
    expect(!failed.ok && failed.error).toContain("code 502")
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const offline = await createFolderDefinition("Books", "", [], "samantha")
    expect(!offline.ok && offline.error).toContain("isn't responding")
  })
})
