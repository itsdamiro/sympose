import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchSlackConnected } from "./slack-api"

const json = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 500, json: async () => body }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("fetchSlackConnected", () => {
  it("asks about this persona and answers what the backend says", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ connected: true }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchSlackConnected("ada lovelace")).toBe(true)
    expect(fetchMock.mock.calls[0][0]).toBe("/api/personas/ada%20lovelace/slack")
  })

  it("is false when the backend says not connected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ connected: false })))
    expect(await fetchSlackConnected("samantha")).toBe(false)
  })

  it("is false for anything that is not exactly true, an error status or an unreachable backend", async () => {
    for (const body of [{ connected: "yes" }, {}, null]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(body)))
      expect(await fetchSlackConnected("samantha")).toBe(false)
    }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ connected: true }, false)))
    expect(await fetchSlackConnected("samantha")).toBe(false)
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")))
    expect(await fetchSlackConnected("samantha")).toBe(false)
  })
})
