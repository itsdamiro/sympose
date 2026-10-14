// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { notifyError, notifyInfo } = vi.hoisted(() => ({ notifyError: vi.fn(), notifyInfo: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError, info: notifyInfo } }))

import { SkillsRows } from "./skills-rows"

const skill = (over: Record<string, unknown> = {}) => ({
  name: "poem-writing", description: "Writes a poem.", own: false, enabled: true, length: 120, cap: 3000, tools: [], ...over,
})
const TRIP = skill({ name: "trip-planning", description: "Plans a trip.", own: true, enabled: false, tools: ["propose_note", "tool_calls"] })
const res = (body: unknown, ok = true, status = ok ? 200 : 422) => ({ ok, status, json: async () => body }) as Response

let calls: { url: string; init?: RequestInit }[]

function stub(routes: { add?: Response; put?: (enabled: boolean) => Response } = {}) {
  calls = []
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (init?.method === "POST") return routes.add ?? res({ skill: TRIP, left_out: 0 })
    if (init?.method === "PUT") return routes.put?.(JSON.parse(init.body as string).enabled) ?? res({})
    if (url.endsWith("/skills")) return res({ skills: [skill()] })
    return res({ ...TRIP, text: "---\nname: trip-planning\n---\n1. Ask the dates.\n" })
  }))
}

beforeEach(() => {
  notifyError.mockClear()
  notifyInfo.mockClear()
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("SkillsRows", () => {
  it("lists each skill by name and whether it is on, its description kept for the review", async () => {
    stub()
    render(<SkillsRows persona="ada" personaName="Ada" />)
    expect(await screen.findByText("poem-writing")).toBeTruthy()
    expect(screen.queryByText("Writes a poem.")).toBeNull()
    const group = screen.getByRole("radiogroup", { name: "Use poem-writing" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("On")
    expect(calls[0].url).toBe("/api/personas/ada/skills")
  })

  it("says whose skills these are, and follows the persona that is open", async () => {
    stub()
    const { rerender } = render(<SkillsRows persona="ada" personaName="Ada" />)
    expect(await screen.findByText(/These are Ada's skills\./)).toBeTruthy()
    rerender(<SkillsRows persona="bob" personaName="Bob" />)
    expect(screen.getByText(/These are Bob's skills\./)).toBeTruthy()
  })

  it("shows nothing without a persona", () => {
    stub()
    const { container } = render(<SkillsRows persona={null} personaName="" />)
    expect(container.textContent).toBe("")
  })

  it("switches a skill off through the backend and shows what it reports", async () => {
    stub({ put: (enabled) => res({ skill: skill({ enabled }) }) })
    render(<SkillsRows persona="ada" personaName="Ada" />)
    const group = await screen.findByRole("radiogroup", { name: "Use poem-writing" })
    fireEvent.click(group.querySelector("button:not([aria-checked='true'])")!)
    await waitFor(() => expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("Off"))
    expect(calls.at(-1)?.url).toBe("/api/personas/ada/skills/poem-writing")
    expect(calls.at(-1)?.init?.body).toBe(JSON.stringify({ enabled: false }))
  })

  it("keeps the row and shows the reason when a switch is refused", async () => {
    stub({ put: () => res({ detail: "Couldn't save the change for Ada." }, false) })
    render(<SkillsRows persona="ada" personaName="Ada" />)
    const group = await screen.findByRole("radiogroup", { name: "Use poem-writing" })
    fireEvent.click(group.querySelector("button:not([aria-checked='true'])")!)
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith("Couldn't save the change for Ada."))
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("On")
  })

  it("adds a folder by its path, off, and opens it to be read before it is turned on", async () => {
    stub({ put: (enabled) => res({ skill: { ...TRIP, enabled } }) })
    render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    fireEvent.change(screen.getByLabelText("Folder of the skill to add"), { target: { value: " /Users/me/trip-planning " } })
    fireEvent.click(screen.getByRole("button", { name: "Add the skill" }))

    expect(await screen.findByText(/1\. Ask the dates\./)).toBeTruthy()
    const post = calls.find((c) => c.init?.method === "POST")!
    expect(post.init?.body).toBe(JSON.stringify({ folder: "/Users/me/trip-planning" }))
    expect((screen.getByLabelText("Folder of the skill to add") as HTMLInputElement).value).toBe("")
    expect(screen.getByText("Needs the persona to propose new notes, use a model that can call tools")).toBeTruthy()
    expect(screen.getByText(/never to a cloud model/)).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: "Turn on" }))
    expect(await screen.findByRole("button", { name: "Turn off" })).toBeTruthy()
    expect(notifyInfo).not.toHaveBeenCalled() // nothing else was in the folder
  })

  it("does not put a skill added for one persona into another's list when the add finishes after a switch", async () => {
    let finish: (r: Response) => void = () => {}
    const slow = new Promise<Response>((resolve) => (finish = resolve))
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") return slow
      if (url.endsWith("/skills")) return res({ skills: [skill()] })
      return res({ ...TRIP, text: "t" })
    }))
    const { rerender } = render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    fireEvent.change(screen.getByLabelText("Folder of the skill to add"), { target: { value: "/x" } })
    fireEvent.click(screen.getByRole("button", { name: "Add the skill" }))
    rerender(<SkillsRows persona="bob" personaName="Bob" />)
    await screen.findByText("poem-writing")

    finish(res({ skill: TRIP, left_out: 0 }))
    await waitFor(() => expect(notifyError).not.toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))

    expect(screen.getByText("poem-writing")).toBeTruthy() // the other persona keeps its own list
    expect(screen.queryByRole("radiogroup", { name: "Use trip-planning", hidden: true })).toBeNull() // hidden too: an opened review hides the page
  })

  it("says only SKILL.md was copied when the folder held more", async () => {
    stub({ add: res({ skill: TRIP, left_out: 2 }) })
    render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    fireEvent.change(screen.getByLabelText("Folder of the skill to add"), { target: { value: "/x" } })
    fireEvent.click(screen.getByRole("button", { name: "Add the skill" }))
    await screen.findByText(/1\. Ask the dates\./)
    expect(notifyInfo).toHaveBeenCalledWith("Only SKILL.md was copied. Nothing else in that folder is used.")
  })

  it("shows the reason a folder was refused and keeps what was typed", async () => {
    stub({ add: res({ detail: "There is no folder at that path." }, false) })
    render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    const field = screen.getByLabelText("Folder of the skill to add") as HTMLInputElement
    fireEvent.change(field, { target: { value: "/nowhere" } })
    fireEvent.keyDown(field, { key: "Enter" })
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith("There is no folder at that path."))
    expect(field.value).toBe("/nowhere")
  })

  it("does not add while the field is empty", async () => {
    stub()
    render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    expect((screen.getByRole("button", { name: "Add the skill" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("does not send an empty or blank path when Enter is pressed", async () => {
    stub()
    render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    const field = screen.getByLabelText("Folder of the skill to add")
    fireEvent.keyDown(field, { key: "Enter" })
    fireEvent.change(field, { target: { value: "   " } })
    fireEvent.keyDown(field, { key: "Enter" })
    expect(calls.some((c) => c.init?.method === "POST")).toBe(false)
  })

  it("keeps the skills in name order when one is added, and drops another persona's list on a switch", async () => {
    const early = { ...TRIP, name: "a-first" }
    stub({ add: res({ skill: early, left_out: 0 }) })
    const { rerender } = render(<SkillsRows persona="ada" personaName="Ada" />)
    await screen.findByText("poem-writing")
    fireEvent.change(screen.getByLabelText("Folder of the skill to add"), { target: { value: "/x" } })
    fireEvent.click(screen.getByRole("button", { name: "Add the skill" }))
    await screen.findByText(/1\. Ask the dates\./)
    fireEvent.click(screen.getAllByRole("button", { name: "Close" })[0])
    await waitFor(() => expect(screen.queryByText(/1\. Ask the dates\./)).toBeNull())
    const order = () => screen.getAllByRole("radiogroup").map((g) => g.getAttribute("aria-label"))
    expect(order()).toEqual(["Use a-first", "Use poem-writing"])

    rerender(<SkillsRows persona="bob" personaName="Bob" />)
    expect(screen.queryByText("poem-writing")).toBeNull()
    expect(await screen.findByText("poem-writing")).toBeTruthy()
    expect(calls.at(-1)?.url).toBe("/api/personas/bob/skills")
  })

  it("says only the first part is sent when a skill is longer than the most that goes with a message", async () => {
    stub()
    vi.stubGlobal("fetch", vi.fn(async (url: string) =>
      url.endsWith("/skills") ? res({ skills: [skill({ length: 5000 })] }) : res({ ...skill({ length: 5000 }), text: "t" })))
    render(<SkillsRows persona="ada" personaName="Ada" />)
    fireEvent.click(await screen.findByRole("button", { name: "Read poem-writing" }))
    expect(await screen.findByText("5000 characters; only the first 3000 are sent with a message")).toBeTruthy()
  })

  it("opens a skill that is already there to be read, with a bundled one said to ship with Sympose", async () => {
    stub()
    render(<SkillsRows persona="ada" personaName="Ada" />)
    fireEvent.click(await screen.findByRole("button", { name: "Read poem-writing" }))
    expect(await screen.findByText("Ships with Sympose")).toBeTruthy()
    expect(screen.getByText("Writes a poem.")).toBeTruthy()
    expect(screen.getByText("120 characters")).toBeTruthy()
  })
})
