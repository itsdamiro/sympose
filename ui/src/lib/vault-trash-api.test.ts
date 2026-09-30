import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchTrash } from "./vault-trash-api"

afterEach(() => vi.unstubAllGlobals())

describe("fetchTrash (#90)", () => {
  it("returns the items and the folders, empty lists for a bin with nothing in it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], folders: [] }) }))
    expect(await fetchTrash("samantha")).toEqual({ items: [], folders: [] })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [{ trash_path: "a.md" }] }) }))
    expect(await fetchTrash("samantha")).toEqual({ items: [{ trash_path: "a.md" }], folders: [] })
  })

  it("returns null on an error or when unreachable, not an empty bin", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    expect(await fetchTrash("samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchTrash("samantha")).toBeNull()
  })
})
