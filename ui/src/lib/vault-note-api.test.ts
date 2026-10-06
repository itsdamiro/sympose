import { afterEach, describe, expect, it, vi } from "vitest"

import { detailOf, moveVaultNote, renameVaultFolder, saveVaultNote } from "./vault-note-api"

function stubRename(reply: { path: string; detail: string }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(reply),
  } as Response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

/** The `new_path` the request carried. */
function sentNewPath(fetchMock: ReturnType<typeof vi.fn>) {
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  return (JSON.parse(init.body as string) as { new_path: string }).new_path
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("moveVaultNote", () => {
  it("asks for the vault root with a leading slash, since a bare name stays in the note's folder", async () => {
    const fetchMock = stubRename({ path: "m.md", detail: "Renamed" })
    const res = await moveVaultNote("F/m.md", "", "samantha")
    expect(sentNewPath(fetchMock)).toBe("/m")
    expect(res).toEqual({ ok: true, path: "m.md", detail: "Renamed" })
  })

  it("asks for a folder by its vault-relative path", async () => {
    const fetchMock = stubRename({ path: "G/H/m.md", detail: "Renamed" })
    await moveVaultNote("F/m.md", "G/H", "samantha")
    expect(sentNewPath(fetchMock)).toBe("G/H/m")
  })

  it("does not call the backend when the note is dropped on its own folder", async () => {
    const fetchMock = stubRename({ path: "", detail: "" })
    expect(await moveVaultNote("F/m.md", "F", "samantha")).toEqual({
      ok: true,
      path: "F/m.md",
      detail: "",
    })
    expect(await moveVaultNote("m.md", "", "samantha")).toEqual({
      ok: true,
      path: "m.md",
      detail: "",
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe("saveVaultNote", () => {
  it("sends the mtime the note was opened from and returns the one the save left", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ mtime: 222 }),
    } as Response)
    vi.stubGlobal("fetch", fetchMock)
    const res = await saveVaultNote("N.md", "text", "samantha", 111)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(init.body as string).expected_mtime).toBe(111)
    expect(res).toEqual({ ok: true, mtime: 222 })
  })

  it("reports a 409 as a conflict", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ detail: "changed on disk" }),
      } as Response)
    )
    expect(await saveVaultNote("N.md", "text", "samantha", 111)).toEqual({
      ok: false,
      error: "changed on disk",
      conflict: true,
    })
  })
})

describe("detailOf", () => {
  const res = (body: unknown) => ({ json: () => Promise.resolve(body) }) as Response

  it("reads the backend's message when `detail` is text", async () => {
    expect(await detailOf(res({ detail: "Note changed on disk" }))).toBe("Note changed on disk")
  })

  it("reads a validation refusal, whose `detail` is a list of problems, as their messages and not [object Object]", async () => {
    const body = { detail: [{ type: "string_too_short", loc: ["body", "message"], msg: "String should have at least 1 character" }, { msg: "Field required" }] }
    expect(await detailOf(res(body))).toBe("String should have at least 1 character; Field required")
  })

  it("is undefined when there is no usable detail, or the body is not JSON", async () => {
    expect(await detailOf(res({}))).toBeUndefined()
    expect(await detailOf(res({ detail: [] }))).toBeUndefined()
    expect(await detailOf({ json: () => Promise.reject(new Error("no")) } as Response)).toBeUndefined()
  })
})

describe("renameVaultFolder", () => {
  it("sends the new name as one plain name for the persona and reads back the new path and who followed", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ path: "Team", detail: "Renamed to `Team`", personas: ["Ada"], personas_unchanged: ["Bo"], failed: 2 }),
    } as Response)
    vi.stubGlobal("fetch", fetchMock)

    const res = await renameVaultFolder("People", "Team", "samantha")

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/vault/folder")
    expect(init.method).toBe("PATCH")
    expect(JSON.parse(init.body as string)).toEqual({ path: "People", new_name: "Team", persona: "samantha" })
    expect(res).toEqual({ ok: true, path: "Team", detail: "Renamed to `Team`", personas: ["Ada"], personasUnchanged: ["Bo"], relinkFailed: 2 })
  })

  it("gives the server's reason when it refuses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 409, json: () => Promise.resolve({ detail: "`Team` is already taken in that folder." }) } as Response))

    expect(await renameVaultFolder("People", "Team", "samantha")).toEqual({ ok: false, error: "`Team` is already taken in that folder." })
  })

  it("says the backend is unreachable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))

    const res = await renameVaultFolder("People", "Team", "samantha")

    expect(res.ok).toBe(false)
    expect(!res.ok && res.error).toMatch(/isn't responding/)
  })
})

