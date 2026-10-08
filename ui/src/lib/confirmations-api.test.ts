import { afterEach, describe, expect, it, vi } from "vitest"

import { answerConfirmation, fetchConfirmations } from "./confirmations-api"

afterEach(() => vi.unstubAllGlobals())

describe("fetchConfirmations", () => {
  it("asks for the conversation's requests, persona and session encoded", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ requests: [{ id: "r1" }] }) })
    vi.stubGlobal("fetch", fetch)
    expect(await fetchConfirmations("a b", "s/1")).toEqual([{ id: "r1" }])
    expect(fetch).toHaveBeenCalledWith("/api/chat/confirmations?persona=a%20b&session=s%2F1")
  })

  it("is empty when the backend refuses or cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }))
    expect(await fetchConfirmations("x", "s")).toEqual([])
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    expect(await fetchConfirmations("x", "s")).toEqual([])
  })
})

describe("answerConfirmation", () => {
  it("posts the decision and the folders as the pills were left", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "r1", state: "accepted" }) })
    vi.stubGlobal("fetch", fetch)
    const result = await answerConfirmation("samantha", "r1", true, ["Work"], "plan")
    expect(result).toEqual({ ok: true, request: { id: "r1", state: "accepted" } })
    expect(fetch.mock.calls[0][0]).toBe("/api/chat/confirmations/r1")
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ persona: "samantha", accept: true, folders: ["Work"], edit_mode: "plan" })
    expect(fetch.mock.calls[0][1].method).toBe("POST")
  })

  it("gives the backend's reason when the answer is refused", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: "Choose at least one folder the new persona may read." }) }))
    expect(await answerConfirmation("samantha", "r1", true, [])).toEqual({ ok: false, error: "Choose at least one folder the new persona may read." })
  })

  it("says Sympose is not responding when it cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    const result = await answerConfirmation("samantha", "r1", false, null)
    expect(result.ok).toBe(false)
  })
})
