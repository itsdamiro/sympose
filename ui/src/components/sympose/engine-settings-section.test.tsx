// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { notifyError } = vi.hoisted(() => ({ notifyError: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError } }))

import { EngineSettingsSections } from "./engine-settings-section"

const SECTIONS = ["memory", "context", "search", "note-lookup"]
const row = (over: Record<string, unknown>) => ({
  key: "k", kind: "toggle", summary: "a thing", value: true, default: true, is_default: true,
  text: "on", choices: [], hint: "", whole: false, ...over,
})
const GROUPS = {
  groups: [
    { name: "Context", settings: [row({ key: "reply_limit", kind: "number", summary: "the room kept for the reply", value: null, default: null, text: "automatic", hint: "tokens, 64 or more; empty for automatic", whole: true })] },
    { name: "Search", settings: [row({ key: "embedding_mode", kind: "choice", summary: "how notes are found", value: "auto", default: "auto", text: "auto", choices: ["auto", "keywords", "embeddings", "hybrid"] })] },
    { name: "Note lookup", settings: [row({ key: "vault_lookup", kind: "choice", summary: "who looks in your notes", value: "auto", default: "auto", text: "auto", choices: ["auto", "ask"] })] },
    { name: "Memory", settings: [row({ key: "memory_remember", summary: "adding to decisions.md", value: false, default: false, text: "off" })] },
  ],
}

let calls: { url: string; init?: RequestInit }[]

function stubBackend(put: (key: string, value: unknown) => Response) {
  calls = []
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (init?.method === "PUT") return put(url.split("/").pop()!, JSON.parse(init.body as string).value)
    return { ok: true, status: 200, json: async () => GROUPS } as Response
  }))
}

const ok = (setting: object) => ({ ok: true, status: 200, json: async () => ({ message: "ok", setting }) }) as Response
const refuse = (detail: string) => ({ ok: false, status: 422, json: async () => ({ detail }) }) as Response

beforeEach(() => {
  notifyError.mockClear()
  for (const s of SECTIONS) document.cookie = `sympose:pref.section.${s}=1`
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  for (const s of SECTIONS) document.cookie = `sympose:pref.section.${s}=; max-age=0`
})

describe("EngineSettingsSections", () => {
  it("draws one section per group the backend describes", async () => {
    stubBackend(() => ok({}))
    render(<EngineSettingsSections />)
    expect(await screen.findByText("Context")).toBeTruthy()
    expect(screen.getByText("Memory")).toBeTruthy()
    expect(screen.getByText("The room kept for the reply")).toBeTruthy()
  })

  it("flips a toggle through the backend and shows what it now reports", async () => {
    stubBackend((_, value) => ok(row({ key: "memory_remember", value, is_default: false, text: "on" })))
    render(<EngineSettingsSections />)
    const group = await screen.findByRole("radiogroup", { name: "Adding to decisions.md" })
    fireEvent.click(group.querySelector('[aria-checked="false"]') as HTMLElement)
    await waitFor(() => expect(calls.find((c) => c.init?.method === "PUT")?.init?.body).toBe(JSON.stringify({ value: true })))
    await waitFor(() => expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("On"))
  })

  it("saves a number typed in as a number when the field is left", async () => {
    stubBackend((_, value) => ok(row({ key: "reply_limit", kind: "number", value, default: null, is_default: false, text: String(value) })))
    render(<EngineSettingsSections />)
    const input = await screen.findByLabelText("The room kept for the reply")
    fireEvent.change(input, { target: { value: "300" } })
    fireEvent.blur(input)
    await waitFor(() => expect(calls.some((c) => c.init?.body === JSON.stringify({ value: 300 }))).toBe(true))
    await waitFor(() => expect((input as HTMLInputElement).value).toBe("300"))
  })

  it("does not send text that is not a number, and says why", async () => {
    stubBackend(() => ok({}))
    render(<EngineSettingsSections />)
    const input = await screen.findByLabelText("The room kept for the reply")
    fireEvent.change(input, { target: { value: "lots" } })
    fireEvent.blur(input)
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith(expect.stringContaining("'lots' is not a number")))
    expect(calls.some((c) => c.init?.method === "PUT")).toBe(false)
    expect((input as HTMLInputElement).value).toBe("")
  })

  it("changes a short choice with a click and names its values the way the toggles do", async () => {
    stubBackend((_, value) => ok(row({ key: "vault_lookup", kind: "choice", value, is_default: false, choices: ["auto", "ask"] })))
    render(<EngineSettingsSections />)
    fireEvent.click(await screen.findByRole("radio", { name: "Ask" }))
    await waitFor(() => expect(calls.some((c) => c.init?.body === JSON.stringify({ value: "ask" }))).toBe(true))
  })

  it("puts Escape's half-typed number away without saving it", async () => {
    stubBackend(() => ok({}))
    render(<EngineSettingsSections />)
    const input = (await screen.findByLabelText("The room kept for the reply")) as HTMLInputElement
    fireEvent.change(input, { target: { value: "12" } })
    fireEvent.keyDown(input, { key: "Escape" })
    expect(input.value).toBe("")
  })

  it("lists a choice of more than three values in a menu, not as segments", async () => {
    stubBackend(() => ok({}))
    render(<EngineSettingsSections />)
    expect(await screen.findByRole("combobox", { name: "How notes are found" })).toBeTruthy()
    expect(screen.queryByRole("radiogroup", { name: "How notes are found" })).toBeNull()
  })

  it("sends nothing when a field is left without being changed", async () => {
    stubBackend(() => ok({}))
    render(<EngineSettingsSections />)
    const input = await screen.findByLabelText("The room kept for the reply")
    fireEvent.focus(input)
    fireEvent.blur(input)
    await new Promise((r) => setTimeout(r, 20))
    expect(calls.some((c) => c.init?.method === "PUT")).toBe(false)
  })

  it("shows the reason a value was refused and keeps what was in force", async () => {
    stubBackend(() => refuse("3 is not valid for reply_limit"))
    render(<EngineSettingsSections />)
    const input = await screen.findByLabelText("The room kept for the reply")
    fireEvent.change(input, { target: { value: "3" } })
    fireEvent.blur(input)
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith("3 is not valid for reply_limit"))
    await waitFor(() => expect((input as HTMLInputElement).value).toBe(""))
  })

  it("offers Reset only while a number is not at its default, and resets with null", async () => {
    stubBackend((_, value) => ok(row({ key: "reply_limit", kind: "number", value, default: null, is_default: true, text: "automatic" })))
    GROUPS.groups[0].settings[0] = row({ key: "reply_limit", kind: "number", summary: "the room kept for the reply", value: 300, default: null, is_default: false, text: "300" })
    render(<EngineSettingsSections />)
    fireEvent.click(await screen.findByRole("button", { name: "Reset The room kept for the reply" }))
    await waitFor(() => expect(calls.some((c) => c.init?.body === JSON.stringify({ value: null }))).toBe(true))
    await waitFor(() => expect(screen.queryByRole("button", { name: /Reset/ })).toBeNull())
  })

  it("says when the settings could not be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    render(<EngineSettingsSections />)
    expect(await screen.findByText(/Couldn't load these: the Sympose backend is not reachable/)).toBeTruthy()
  })
})
