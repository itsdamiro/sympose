import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchSchedule, switchSchedule } from "./schedule-api"

const json = (body: unknown, ok = true, status = ok ? 200 : 422) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response
const DOWN = "Sympose isn't responding. Check that it's still running, then try again."

afterEach(() => vi.unstubAllGlobals())

describe("fetchSchedule", () => {
  it("asks whether the operating system runs the jobs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ supported: true, installed: false }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchSchedule()).toEqual({ ok: true, schedule: { supported: true, installed: false } })
    expect(fetchMock).toHaveBeenCalledWith("/api/schedule")
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "No." }, false, 500)))
    expect(await fetchSchedule()).toEqual({ ok: false, error: "No." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchSchedule()).toEqual({ ok: false, error: DOWN })
  })
})

describe("switchSchedule", () => {
  it("sends the wish and returns the state now", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ supported: true, installed: true }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await switchSchedule(true)).toEqual({ ok: true, schedule: { supported: true, installed: true } })
    expect(fetchMock).toHaveBeenCalledWith("/api/schedule", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ installed: true }),
    })
  })

  it("says why it was refused, or that the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Couldn't start the schedule: no way" }, false)))
    expect(await switchSchedule(true)).toEqual({ ok: false, error: "Couldn't start the schedule: no way" })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await switchSchedule(false)).toEqual({ ok: false, error: `Couldn't change the schedule: ${DOWN}` })
  })
})
