import { afterEach, describe, expect, it, vi } from "vitest"

import { addSkill, fetchSkills, readSkill, removeSkill, switchSkill } from "./skills-api"

const skill = { name: "trip-planning", description: "Plans a trip.", own: true, enabled: false, length: 17, cap: 3000, tools: [] }
const json = (body: unknown, ok = true, status = ok ? 200 : 422) =>
  ({ ok, status, json: () => Promise.resolve(body) }) as Response
const DOWN = "Sympose isn't responding. Check that it's still running, then try again."

afterEach(() => vi.unstubAllGlobals())

describe("fetchSkills", () => {
  it("asks for the persona's skills", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ skills: [skill] }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await fetchSkills("a b")).toEqual({ ok: true, skills: [skill] })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/a%20b/skills")
  })

  it("gives the reason, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "There is no persona called x." }, false, 404)))
    expect(await fetchSkills("x")).toEqual({ ok: false, error: "There is no persona called x." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchSkills("x")).toEqual({ ok: false, error: DOWN })
  })
})

describe("readSkill", () => {
  it("reads one skill with its text, the name encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ ...skill, text: "---\n---\n" }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await readSkill("ada", "a b")).toEqual({ ok: true, skill: { ...skill, text: "---\n---\n" } })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/ada/skills/a%20b")
  })
})

describe("addSkill", () => {
  it("posts the folder's path and returns the skill with what was left out", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ skill, left_out: 2 }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await addSkill("ada", "/Users/me/trip-planning")).toEqual({ ok: true, skill, leftOut: 2 })
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/personas/ada/skills",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ folder: "/Users/me/trip-planning" }) })
    )
  })

  it("gives the reason a folder was refused, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "There is no folder at that path." }, false)))
    expect(await addSkill("ada", "/x")).toEqual({ ok: false, error: "There is no folder at that path." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await addSkill("ada", "/x")).toEqual({ ok: false, error: DOWN })
  })
})

describe("switchSkill", () => {
  it("puts whether it is on and returns the skill now", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ skill: { ...skill, enabled: true } }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await switchSkill("ada", "trip-planning", true)).toEqual({ ok: true, skill: { ...skill, enabled: true } })
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/personas/ada/skills/trip-planning",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ enabled: true }) })
    )
  })

  it("gives the reason it failed, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Couldn't save the change for Ada." }, false, 422)))
    expect(await switchSkill("ada", "x", true)).toEqual({ ok: false, error: "Couldn't save the change for Ada." })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const result = await switchSkill("ada", "x", false)
    expect(!result.ok && result.error).toContain("isn't responding")
  })
})

describe("removeSkill", () => {
  it("deletes the skill by name, the name encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ removed: "a b" }))
    vi.stubGlobal("fetch", fetchMock)
    expect(await removeSkill("ada", "a b")).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith("/api/personas/ada/skills/a%20b", { method: "DELETE" })
  })

  it("gives the reason it was refused, or says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "poem-writing ships with Sympose, so it can't be removed. Turn it off instead." }, false)))
    expect(await removeSkill("ada", "poem-writing")).toEqual({
      ok: false,
      error: "poem-writing ships with Sympose, so it can't be removed. Turn it off instead.",
    })
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await removeSkill("ada", "x")).toEqual({ ok: false, error: `Couldn't remove x: ${DOWN}` })
  })
})
