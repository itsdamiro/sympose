import { afterEach, describe, expect, it, vi } from "vitest"

import { moveVaultFolder, planFolderMove } from "./vault-folder-move-api"

function stub(ok: boolean, body: unknown, status = ok ? 200 : 409) {
  const fetchMock = vi.fn().mockResolvedValue({ ok, status, json: () => Promise.resolve(body) } as Response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}
const sent = (f: ReturnType<typeof vi.fn>) => {
  const [url, init] = f.mock.calls[0] as [string, RequestInit]
  return { url, method: init.method, body: JSON.parse(init.body as string) as Record<string, unknown> }
}

afterEach(() => vi.unstubAllGlobals())

describe("planFolderMove", () => {
  it("posts the folder and where it goes and reads the plan in camel case", async () => {
    const f = stub(true, { path: "A", destination: "B", new_path: "B/A", clash: true, note_clashes: ["x.md"], reach: [{ handle: "g", name: "Grace", gains: 2, loses: 0 }], definition: "stops" })

    const res = await planFolderMove("A", "B", "samantha")

    expect(sent(f)).toEqual({ url: "/api/vault/folder/move-plan", method: "POST", body: { path: "A", destination: "B", persona: "samantha", new_name: "" } })
    expect(res).toEqual({ ok: true, path: "A", destination: "B", newPath: "B/A", clash: true, noteClashes: ["x.md"], reach: [{ handle: "g", name: "Grace", gains: 2, loses: 0 }], definition: "stops" })
  })

  it("asks for the plan under another name when the user chose one", async () => {
    const f = stub(true, { path: "A", destination: "B", new_path: "B/Friends", clash: false, note_clashes: [], reach: [], definition: null })

    const res = await planFolderMove("A", "B", "samantha", "Friends")

    expect(sent(f).body).toEqual({ path: "A", destination: "B", persona: "samantha", new_name: "Friends" })
    expect(res.ok && res.newPath).toBe("B/Friends")
  })

  it("says what the server refused with", async () => {
    stub(false, { detail: "A folder cannot go into itself." }, 400)
    expect(await planFolderMove("A", "A", "p")).toEqual({ ok: false, error: "A folder cannot go into itself." })
  })

  it("says the backend is unreachable when the request throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    const res = await planFolderMove("A", "B", "p")
    expect(res.ok === false && res.error).toContain("unreachable")
  })
})

describe("moveVaultFolder", () => {
  it("sends no answers by default, and the root as an empty destination", async () => {
    const f = stub(true, { path: "A", detail: "Moved", personas: [], personas_unchanged: [], failed: 0 })

    await moveVaultFolder("B/A", "", "samantha")

    expect(sent(f)).toEqual({
      url: "/api/vault/folder/move",
      method: "PATCH",
      body: { path: "B/A", destination: "", persona: "samantha", if_exists: null, new_name: "", rename_clashing_notes: false, confirm_reach: false },
    })
  })

  it("sends the user's answers", async () => {
    const f = stub(true, { path: "B/Friends", detail: "Moved", personas: ["Ada"], personas_unchanged: [], failed: 1 })

    const res = await moveVaultFolder("A", "B", "p", { ifExists: "rename", newName: "Friends", renameClashingNotes: true, confirmReach: true })

    expect(sent(f).body).toMatchObject({ if_exists: "rename", new_name: "Friends", rename_clashing_notes: true, confirm_reach: true })
    expect(res).toEqual({ ok: true, path: "B/Friends", detail: "Moved", personas: ["Ada"], personasUnchanged: [], relinkFailed: 1 })
  })

  it("says what the server refused with, or the status when it gave no reason", async () => {
    stub(false, { detail: "confirm to move anyway" })
    expect(await moveVaultFolder("A", "B", "p")).toEqual({ ok: false, error: "confirm to move anyway" })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.reject(new Error("x")) } as Response))
    expect(await moveVaultFolder("A", "B", "p")).toEqual({ ok: false, error: "Move failed (HTTP 500)" })
  })
})
