import { afterEach, describe, expect, it, vi } from "vitest"

import { createJob, fetchJobs, switchJob } from "./jobs-api"

const job = {
  name: "weekly", file: "jobs/weekly.md", schedule: "weekly sun 18:00", kind: "ask", mechanical: false, model: "ollama/gemma4:e4b",
  cloud: false, enabled: true, problem: null, paused: false, failures: 0, last_run: null, outcome: null, detail: "", session_id: null,
}
const json = (body: unknown, ok = true, status = ok ? 200 : 422) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response
const DOWN = "Sympose isn't responding. Check that it's still running, then try again."

afterEach(() => vi.unstubAllGlobals())

describe("fetchJobs", () => {
  it("asks for the persona's jobs, the handle encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ jobs: [job] }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchJobs("a b")).toEqual({ ok: true, jobs: [job] })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/a%20b/jobs")
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "There is no persona called x." }, false, 404)))
    expect(await fetchJobs("x")).toEqual({ ok: false, error: "There is no persona called x." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchJobs("x")).toEqual({ ok: false, error: DOWN })
  })
})

describe("createJob", () => {
  it("posts and returns the new job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ job }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await createJob("ada")).toEqual({ ok: true, job })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/ada/jobs", { method: "POST" })
  })

  it("says why it was refused", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "The job could not be made." }, false)))
    expect(await createJob("ada")).toEqual({ ok: false, error: "The job could not be made." })
  })
})

describe("switchJob", () => {
  it("puts the switch and returns the job as it is now", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ job: { ...job, enabled: false } }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await switchJob("ada", "a b", false)).toEqual({ ok: true, job: { ...job, enabled: false } })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/personas/ada/jobs/a%20b")
    expect(init.method).toBe("PUT")
    expect(JSON.parse(init.body)).toEqual({ enabled: false })
  })

  it("names the job when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await switchJob("ada", "weekly", true)).toEqual({ ok: false, error: `Couldn't change weekly: ${DOWN}` })
  })
})
