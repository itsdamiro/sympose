import { afterEach, describe, expect, it, vi } from "vitest"

import { chooseModel, fetchModels } from "./models-api"

const raw = {
  models: [{ id: "a/x", label: "X — cloud", short: "X", cloud: true }],
  current: "a/x",
  current_cloud: true,
  own: "a/x",
  fallback: "ollama_chat/gemma2:9b",
  fallback_cloud: false,
}
const json = (body: unknown, ok = true, status = ok ? 200 : 500) => ({ ok, status, json: () => Promise.resolve(body) }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("fetchModels", () => {
  it("asks for the persona's models and returns them with the cloud flag under its browser name", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(raw))
    vi.stubGlobal("fetch", fetchMock)
    const result = await fetchModels("sam ntha")
    expect(fetchMock).toHaveBeenCalledWith("/api/models?persona=sam%20ntha")
    expect(result.ok && result.state.currentCloud).toBe(true)
    expect(result.ok && result.state.fallback).toBe("ollama_chat/gemma2:9b")
    expect(result.ok && result.state.fallbackCloud).toBe(false)
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Unknown persona" }, false, 404)))
    expect(await fetchModels("x")).toEqual({ ok: false, error: "Unknown persona" })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchModels("x")).toEqual({ ok: false, error: "the Sympose backend is not reachable" })
  })
})

describe("chooseModel", () => {
  it("puts the model to that persona's own address and returns the state now", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(raw))
    vi.stubGlobal("fetch", fetchMock)
    const result = await chooseModel("samantha", "a/x")
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/personas/samantha/model",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ model: "a/x" }) })
    )
    expect(result.ok && result.state.own).toBe("a/x")
  })

  it("encodes the persona's name in the address", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(raw))
    vi.stubGlobal("fetch", fetchMock)
    await chooseModel("a b/c", "a/x")
    expect(fetchMock.mock.calls[0][0]).toBe("/api/personas/a%20b%2Fc/model")
  })

  it("sends null to clear the persona's own model", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(raw))
    vi.stubGlobal("fetch", fetchMock)
    await chooseModel("samantha", null)
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ model: null }))
  })

  it("gives the reason a save was refused, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Couldn't save the model into samantha's persona.yaml." }, false, 500)))
    expect(await chooseModel("s", "a/x")).toEqual({ ok: false, error: "Couldn't save the model into samantha's persona.yaml." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const result = await chooseModel("s", "a/x")
    expect(!result.ok && result.error).toContain("not reachable")
  })
})
