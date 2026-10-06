import { afterEach, describe, expect, it, vi } from "vitest"

import { addFolderIcon, fetchDoctor, fetchHealth, fixable, fixDoctor, leftOver, type DoctorReport } from "./checks-api"

const respond = (body: unknown, ok = true, status = ok ? 200 : 500) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response

afterEach(() => vi.unstubAllGlobals())

describe("checks api", () => {
  it("reads the doctor with a GET and fixes with a POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ models: [], findings: [] }))
    vi.stubGlobal("fetch", fetchMock)
    await fetchDoctor()
    await fixDoctor()
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/doctor", undefined)
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/doctor/fix", { method: "POST" })
  })

  it("returns the report, the server's reason, the status, or that the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond({ persona: "samantha" })))
    expect(await fetchHealth()).toEqual({ ok: true, report: { persona: "samantha" } })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond({ detail: "No vault is set up." }, false, 409)))
    expect(await fetchHealth()).toEqual({ ok: false, error: "No vault is set up." })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond({}, false, 500)))
    expect(await fetchHealth()).toEqual({ ok: false, error: "Something failed on Sympose's side (code 500). Try again." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchHealth()).toEqual({ ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." })
  })

  it("tells what is fixable and what is left", () => {
    const f = (state: DoctorReport["findings"][number]["state"]) => ({ problem: state, state, fix: null, error: "" })
    const report = { models: [], findings: [f("fixable"), f("fixed"), f("needs_you"), f("failed")] }
    expect(fixable(report).map((x) => x.state)).toEqual(["fixable"])
    expect(leftOver(report).map((x) => x.state)).toEqual(["fixable", "needs_you", "failed"])
  })
})

describe("addFolderIcon", () => {
  it("POSTs the folder as JSON to the health's icon route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond({ folder: "Movies", added: ["icon: film-roll"] }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await addFolderIcon("Movies")).toEqual({ ok: true, report: { folder: "Movies", added: ["icon: film-roll"] } })
    expect(fetchMock).toHaveBeenCalledWith("/api/vault/health/icon", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder: "Movies" }),
    })
  })
})
