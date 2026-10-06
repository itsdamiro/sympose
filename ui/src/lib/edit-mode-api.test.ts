import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchEditMode, saveEditMode, type EditModeInfo } from "./edit-mode-api"

const INFO: EditModeInfo = {
  mode: "manual",
  source: "global",
  modes: [{ id: "manual", summary: "x" }],
  notes: { accept: "a", auto: "b" },
  model: "m",
}

afterEach(() => vi.unstubAllGlobals())

describe("fetchEditMode", () => {
  it("asks for the persona's mode by handle, encoded", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => INFO })
    vi.stubGlobal("fetch", fetch)
    expect(await fetchEditMode("a b")).toEqual(INFO)
    expect(fetch).toHaveBeenCalledWith("/api/personas/a%20b/edit-mode")
  })

  it("is null when the backend refuses or cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: "No such persona." }) }))
    expect(await fetchEditMode("x")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    expect(await fetchEditMode("x")).toBeNull()
  })
})

describe("saveEditMode", () => {
  it("puts the mode, or null to clear it, and returns the state the backend answers", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => INFO })
    vi.stubGlobal("fetch", fetch)
    expect(await saveEditMode("samantha", "auto")).toEqual({ ok: true, info: INFO })
    expect(fetch).toHaveBeenLastCalledWith("/api/personas/samantha/edit-mode", expect.objectContaining({ method: "PUT", body: JSON.stringify({ mode: "auto" }) }))
    await saveEditMode("samantha", null)
    expect(fetch).toHaveBeenLastCalledWith("/api/personas/samantha/edit-mode", expect.objectContaining({ body: JSON.stringify({ mode: null }) }))
  })

  it("says why when the backend refuses, and when it cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "not one of the modes" }), clone() { return this } }))
    expect(await saveEditMode("samantha", "auto")).toEqual({ ok: false, error: "not one of the modes" })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    expect(await saveEditMode("samantha", "auto")).toEqual({ ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." })
  })
})
