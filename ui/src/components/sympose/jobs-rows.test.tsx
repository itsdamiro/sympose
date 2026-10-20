// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { notifyError } = vi.hoisted(() => ({ notifyError: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError } }))

import { JobsRows } from "./jobs-rows"

const job = (over: Record<string, unknown> = {}) => ({
  name: "weekly", file: "jobs/weekly.md", schedule: "weekly sun 18:00", kind: "ask", mechanical: false, model: "ollama/gemma4:e4b",
  cloud: false, enabled: true, problem: null, paused: false, failures: 0, last_run: null, outcome: null, detail: "", session_id: null,
  ...over,
})
const res = (body: unknown, ok = true, status = ok ? 200 : 422) => ({ ok, status, json: async () => body }) as Response

let calls: { url: string; init?: RequestInit }[]

function stub(
  routes: {
    list?: unknown[]
    put?: (enabled: boolean) => Response
    post?: Response
    schedule?: { supported: boolean; installed: boolean }
    putSchedule?: (installed: boolean) => Response
  } = {}
) {
  calls = []
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url === "/api/schedule") {
      if (init?.method === "PUT") return routes.putSchedule?.(JSON.parse(init.body as string).installed) ?? res(routes.schedule)
      return res(routes.schedule ?? { supported: false, installed: false })
    }
    if (init?.method === "POST") return routes.post ?? res({ job: job({ name: "new-job", file: "jobs/new-job.md", enabled: false }) })
    if (init?.method === "PUT") return routes.put?.(JSON.parse(init.body as string).enabled) ?? res({ job: job() })
    return res({ jobs: routes.list ?? [job()] })
  }))
}

// The backend writes the user's own clock with no offset: "2026-10-18T18:00:00".
const ago = (hours: number) => {
  const at = new Date(Date.now() - hours * 3600 * 1000)
  return new Date(at.getTime() - at.getTimezoneOffset() * 60000).toISOString().slice(0, 19)
}

beforeEach(() => notifyError.mockClear())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("JobsRows", () => {
  it("lists each job with its schedule and says one has not run yet", async () => {
    stub()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText("weekly")).toBeTruthy()
    expect(screen.getByText("weekly sun 18:00")).toBeTruthy()
    expect(screen.getByText("not run yet")).toBeTruthy()
    expect(screen.getByRole("radiogroup", { name: "Run weekly" }).querySelector('[aria-checked="true"]')?.textContent).toBe("On")
  })

  it("shows how the last run went: when it ran, or why it failed", async () => {
    stub({ list: [job({ last_run: ago(3), outcome: "ok" }), job({ name: "broken-run", last_run: ago(1), outcome: "failed", detail: "model offline" })] })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText("3h ago")).toBeTruthy()
    expect(screen.getByLabelText("Ran")).toBeTruthy()
    expect(screen.getByText("1h ago: model offline")).toBeTruthy()
    expect(screen.getByLabelText("Failed")).toBeTruthy()
  })

  it("marks the model as on this computer or in the cloud, and a mechanical job has none", async () => {
    stub({
      list: [
        job({ name: "a-local" }),
        job({ name: "b-cloud", model: "gemini/x", cloud: true }),
        job({ name: "c-check", kind: "health", mechanical: true, model: null }),
      ],
    })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    await screen.findByText("c-check")
    expect(screen.getByLabelText("On your computer: ollama/gemma4:e4b")).toBeTruthy()
    expect(screen.getByLabelText("Cloud model: gemini/x")).toBeTruthy()
    expect(screen.getAllByLabelText(/model|computer/i)).toHaveLength(2)
    const shape = (label: string) => screen.getByLabelText(label).querySelector("path")?.getAttribute("d")
    expect(shape("On your computer: ollama/gemma4:e4b")).not.toBe(shape("Cloud model: gemini/x")) // not the same icon
  })

  it("lists the jobs by name, a job just made among them", async () => {
    stub({ list: [job({ name: "weekly" }), job({ name: "zeta" })] })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    await screen.findByText("zeta")
    fireEvent.click(screen.getByRole("button", { name: "Add a job" }))
    await screen.findByText("new-job")
    const names = screen.getAllByRole("radiogroup").map((g) => g.getAttribute("aria-label"))
    expect(names).toEqual(["Run new-job", "Run weekly", "Run zeta"])
  })

  it("says what is wrong with a file instead of its schedule", async () => {
    stub({ list: [job({ problem: "'whenever' is not a schedule.", enabled: true })] })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText("'whenever' is not a schedule.")).toBeTruthy()
    expect(screen.queryByText("weekly sun 18:00")).toBeNull()
  })

  it("shows a paused job as off, and the On switch turns it back on", async () => {
    stub({ list: [job({ paused: true, failures: 3 })], put: () => res({ job: job() }) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText("Paused after 3 failures in a row")).toBeTruthy()
    const group = screen.getByRole("radiogroup", { name: "Run weekly" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("Off")
    fireEvent.click(screen.getByRole("radio", { name: "On" }))
    await waitFor(() => expect(screen.queryByText(/Paused after/)).toBeNull())
    expect(JSON.parse(calls.find((c) => c.init?.method === "PUT")!.init!.body as string)).toEqual({ enabled: true })
  })

  it("switches a job off and keeps the answer", async () => {
    stub({ put: () => res({ job: job({ enabled: false }) }) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    await screen.findByText("weekly")
    fireEvent.click(screen.getByRole("radio", { name: "Off" }))
    await waitFor(() =>
      expect(screen.getByRole("radiogroup", { name: "Run weekly" }).querySelector('[aria-checked="true"]')?.textContent).toBe("Off")
    )
    expect(calls.find((c) => c.init?.method === "PUT")?.url).toBe("/api/personas/ada/jobs/weekly")
  })

  it("keeps the list and shows the reason when a switch is refused", async () => {
    stub({ put: () => res({ detail: "The job's file could not be saved." }, false) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    await screen.findByText("weekly")
    fireEvent.click(screen.getByRole("radio", { name: "Off" }))
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith("The job's file could not be saved."))
    expect(screen.getByRole("radiogroup", { name: "Run weekly" }).querySelector('[aria-checked="true"]')?.textContent).toBe("On")
  })

  it("opens a job's file in the editor from its row", async () => {
    stub()
    const onOpen = vi.fn()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={onOpen} />)
    fireEvent.click(await screen.findByRole("button", { name: "Open weekly in the editor" }))
    expect(onOpen).toHaveBeenCalledExactlyOnceWith("jobs/weekly.md")
  })

  it("makes a new job from the template, lists it and opens it in the editor", async () => {
    stub()
    const onOpen = vi.fn()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={onOpen} />)
    await screen.findByText("weekly")
    fireEvent.click(screen.getByRole("button", { name: "Add a job" }))
    await waitFor(() => expect(onOpen).toHaveBeenCalledExactlyOnceWith("jobs/new-job.md"))
    expect(screen.getByText("new-job")).toBeTruthy()
    expect(calls.some((c) => c.init?.method === "POST" && c.url === "/api/personas/ada/jobs")).toBe(true)
  })

  it("reads the jobs again when told a file was saved", async () => {
    stub()
    const { rerender } = render(<JobsRows persona="ada" personaName="Ada" version={0} onOpen={vi.fn()} />)
    await screen.findByText("weekly")
    const before = calls.length
    rerender(<JobsRows persona="ada" personaName="Ada" version={1} onOpen={vi.fn()} />)
    await waitFor(() => expect(calls.length).toBe(before + 1))
  })

  it("says it could not load the jobs, and offers nothing without a persona", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res({ detail: "No." }, false, 404)))
    const { container, rerender } = render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText("Couldn't load the jobs: No.")).toBeTruthy()
    rerender(<JobsRows persona={null} personaName="Ada" onOpen={vi.fn()} />)
    expect(container.textContent).toBe("")
  })

  describe("running while Sympose is closed", () => {
    const state = () => screen.getByRole("radiogroup", { name: "Run jobs while Sympose is closed" }).querySelector('[aria-checked="true"]')?.textContent

    it("shows the switch as the operating system has it", async () => {
      stub({ schedule: { supported: true, installed: true } })
      render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
      expect(await screen.findByText("Run while Sympose is closed")).toBeTruthy()
      expect(state()).toBe("On")
    })

    it("is not offered where it cannot be set up", async () => {
      stub({ schedule: { supported: false, installed: false } })
      render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
      await screen.findByText("weekly")
      expect(screen.queryByText("Run while Sympose is closed")).toBeNull()
    })

    it("sets it up when switched on, and takes it away when switched off", async () => {
      stub({ schedule: { supported: true, installed: false }, putSchedule: (installed) => res({ supported: true, installed }) })
      render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
      await screen.findByText("Run while Sympose is closed")
      const group = screen.getByRole("radiogroup", { name: "Run jobs while Sympose is closed" })
      fireEvent.click(group.querySelector('[role="radio"]:first-child')!) // On
      await waitFor(() => expect(state()).toBe("On"))
      fireEvent.click(group.querySelector('[role="radio"]:last-child')!) // Off
      await waitFor(() => expect(state()).toBe("Off"))
      const sent = calls.filter((c) => c.url === "/api/schedule" && c.init?.method === "PUT").map((c) => JSON.parse(c.init!.body as string))
      expect(sent).toEqual([{ installed: true }, { installed: false }])
    })

    it("keeps the switch where it was and shows the reason when it is refused", async () => {
      stub({ schedule: { supported: true, installed: false }, putSchedule: () => res({ detail: "Couldn't start the schedule: no way" }, false) })
      render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
      await screen.findByText("Run while Sympose is closed")
      fireEvent.click(screen.getByRole("radiogroup", { name: "Run jobs while Sympose is closed" }).querySelector('[role="radio"]:first-child')!)
      await waitFor(() => expect(notifyError).toHaveBeenCalledWith("Couldn't start the schedule: no way"))
      expect(state()).toBe("Off")
    })
  })
})
