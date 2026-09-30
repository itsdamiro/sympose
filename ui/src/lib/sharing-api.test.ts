import { afterEach, describe, expect, it, vi } from "vitest"

import { changeSharing, fetchSharing } from "./sharing-api"

const state = { model: "gemini/x", cloud: true, categories: [{ name: "notes", description: "passages", shared: false }] }
const json = (body: unknown, ok = true, status = ok ? 200 : 500) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("fetchSharing", () => {
  it("asks for the persona's model and returns what it may receive", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(state))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchSharing("samantha")).toEqual({ ok: true, state })
    expect(fetchMock).toHaveBeenCalledWith("/api/sharing?persona=samantha")
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Unknown persona" }, false, 404)))
    expect(await fetchSharing("x")).toEqual({ ok: false, error: "Unknown persona" })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchSharing("x")).toEqual({ ok: false, error: "the Sympose backend is not reachable" })
  })
})

describe("changeSharing", () => {
  it("puts whether the category is shared, for that persona, and returns the state now", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(state))
    vi.stubGlobal("fetch", fetchMock)
    expect(await changeSharing("samantha", "notes", true)).toEqual({ ok: true, state })
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sharing/notes?persona=samantha",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ shared: true }) })
    )
  })

  it("sends false when a category is stopped, and encodes what it puts in the address", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(state))
    vi.stubGlobal("fetch", fetchMock)
    await changeSharing("a b", "no tes", false)
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sharing/no%20tes?persona=a%20b",
      expect.objectContaining({ body: JSON.stringify({ shared: false }) })
    )
  })

  it("gives the reason a save failed, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Couldn't save the cloud-sharing setting." }, false, 500)))
    expect(await changeSharing("s", "notes", true)).toEqual({ ok: false, error: "Couldn't save the cloud-sharing setting." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const result = await changeSharing("s", "notes", true)
    expect(!result.ok && result.error).toContain("not reachable")
  })
})
