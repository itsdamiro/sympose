import { afterEach, describe, expect, it, vi } from "vitest"

import { changeSetting, fetchSettings } from "./settings-api"

const raw = {
  key: "vault_lookup",
  kind: "choice",
  summary: "who looks",
  value: "auto",
  default: "auto",
  is_default: true,
  text: "auto",
  choices: ["auto", "ask"],
  hint: "",
  whole: false,
}

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return { ok, status, json: () => Promise.resolve(body) } as Response
}

afterEach(() => vi.unstubAllGlobals())

describe("fetchSettings", () => {
  it("returns the groups with each row's default flag under its browser name", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ groups: [{ name: "Note lookup", settings: [raw] }] })))
    const result = await fetchSettings()
    expect(result.ok && result.groups[0].name).toBe("Note lookup")
    expect(result.ok && result.groups[0].settings[0].isDefault).toBe(true)
  })

  it("says the backend is unreachable, or the status it answered with", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchSettings()).toEqual({ ok: false, error: "Sympose isn't responding. Check that it's still running, then try again." })
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 500)))
    expect(await fetchSettings()).toEqual({ ok: false, error: "Something failed on Sympose's side (code 500). Try again." })
  })
})

describe("changeSetting", () => {
  it("puts the value and returns the row as it now is", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ message: "ok", setting: { ...raw, value: "ask", is_default: false } }))
    vi.stubGlobal("fetch", fetchMock)
    const result = await changeSetting("vault_lookup", "ask")
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings/vault_lookup",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ value: "ask" }) })
    )
    expect(result.ok && result.setting.value).toBe("ask")
    expect(result.ok && result.setting.isDefault).toBe(false)
  })

  it("passes null through to restore the default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ setting: raw }))
    vi.stubGlobal("fetch", fetchMock)
    await changeSetting("vault_lookup", null)
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ value: null }))
  })

  it("gives the reason the backend refused a value with", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "3 is not valid for reply_limit" }, false, 422)))
    expect(await changeSetting("reply_limit", 3)).toEqual({ ok: false, error: "3 is not valid for reply_limit" })
  })

  it("says the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    const result = await changeSetting("reply_limit", 300)
    expect(!result.ok && result.error).toContain("isn't responding")
  })
})
