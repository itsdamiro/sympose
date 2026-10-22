// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { notifyError, confirmMock } = vi.hoisted(() => ({ notifyError: vi.fn(), confirmMock: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify: { error: notifyError } }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))

import { JobsRows } from "./jobs-rows"

const job = (over: Record<string, unknown> = {}) => ({
  name: "weekly", file: "jobs/weekly.md", schedule: "weekly sun 18:00", kind: "ask", mechanical: false, model: "ollama/gemma4:e4b", own_model: "ollama/gemma4:e4b",
  cloud: false, enabled: true, problem: null, paused: false, failures: 0, last_run: null, outcome: null, detail: "", session_id: null,
  ...over,
})
const modelsState = {
  models: [
    { id: "ollama/gemma4:e4b", label: "Gemma 4 (on this computer)", short: "gemma4:e4b", cloud: false },
    { id: "gemini/gemini-flash-latest", label: "Gemini Flash (cloud)", short: "gemini-flash", cloud: true },
  ],
  current: "ollama/gemma4:e4b", current_cloud: false, own: null, fallback: "ollama/gemma4:e4b", fallback_cloud: false,
}
const res = (body: unknown, ok = true, status = ok ? 200 : 422) => ({ ok, status, json: async () => body }) as Response

let calls: { url: string; init?: RequestInit }[]

function stub(
  routes: {
    list?: unknown[]
    put?: (enabled: boolean) => Response
    post?: Response
    rename?: Response
    del?: Response
    schedule?: { supported: boolean; installed: boolean }
    putSchedule?: (installed: boolean) => Response
    putModel?: (model: string | null) => Response
  } = {}
) {
  calls = []
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    if (url === "/api/schedule") {
      if (init?.method === "PUT") return routes.putSchedule?.(JSON.parse(init.body as string).installed) ?? res(routes.schedule)
      return res(routes.schedule ?? { supported: false, installed: false })
    }
    if (url.startsWith("/api/models")) return res(modelsState)
    if (init?.method === "PUT" && url.endsWith("/model")) return routes.putModel?.(JSON.parse(init.body as string).model) ?? res({ job: job() })
    if (init?.method === "POST" && url.endsWith("/rename")) return routes.rename ?? res({ job: job() })
    if (init?.method === "DELETE") return routes.del ?? res({ deleted: "weekly" })
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

beforeEach(() => {
  notifyError.mockClear()
  confirmMock.mockClear()
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("JobsRows", () => {
  it("says under Add a job what a job's file holds, now that its editor has no strip for it", async () => {
    stub()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByText(/the properties say when it runs and the text says what to do/)).toBeTruthy()
  })

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
        job({ name: "b-cloud", model: "gemini/gemini-flash-latest", cloud: true }),
        job({ name: "c-check", kind: "health", mechanical: true, model: null, own_model: null }),
      ],
    })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    await screen.findByText("c-check")
    const pickers = await screen.findAllByRole("button", { name: /^Model:/ })
    expect(pickers.map((p) => p.getAttribute("data-tier"))).toEqual(["local", "cloud"])
    expect(pickers.map((p) => p.textContent)).toEqual(["gemma4:e4b", "gemini-flash"])
  })

  it("shows the plain mark until the persona's models are known", async () => {
    stub({ list: [job({ model: "gemini/x", cloud: true })] })
    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL) =>
      String(url).startsWith("/api/models") ? res({ detail: "no" }, false, 500) : res({ jobs: [job({ model: "gemini/x", cloud: true })] })
    )
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    expect(await screen.findByLabelText("Cloud model: gemini/x")).toBeTruthy()
  })

  it("writes the model picked from a job's row, and the row shows it", async () => {
    stub({ putModel: () => res({ job: job({ model: "gemini/gemini-flash-latest", own_model: "gemini/gemini-flash-latest", cloud: true }) }) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: /^Model:/ }))
    fireEvent.click(await screen.findByRole("menuitem", { name: /Gemini Flash/ }))
    await waitFor(() => expect(screen.getByRole("button", { name: /^Model:/ }).getAttribute("data-tier")).toBe("cloud"))
    const sent = calls.filter((c) => c.init?.method === "PUT" && c.url.endsWith("/jobs/weekly/model"))
    expect(sent.map((c) => JSON.parse(c.init!.body as string))).toEqual([{ model: "gemini/gemini-flash-latest" }])
  })

  it("offers to go back to the persona's model only while the job has one of its own", async () => {
    stub({
      list: [job({ name: "a-own" }), job({ name: "b-persona's", own_model: null })],
      putModel: () => res({ job: job({ own_model: null }) }),
    })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    const [own, inherited] = await screen.findAllByRole("button", { name: /^Model:/ })
    fireEvent.click(inherited)
    await screen.findByRole("menuitem", { name: /Gemini Flash/ })
    expect(screen.queryByRole("menuitem", { name: /Use the default/ })).toBeNull()
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" })
    await waitFor(() => expect(screen.queryByRole("menuitem", { name: /Gemini Flash/ })).toBeNull())
    fireEvent.click(own)
    fireEvent.click(await screen.findByRole("menuitem", { name: /Use the default \(ollama\/gemma4:e4b\)/ }))
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PUT" && c.url.endsWith("/model") && JSON.parse(c.init.body as string).model === null)).toBe(true))
  })

  it("offers the persona's model as the default, not the job's own", async () => {
    stub({ list: [job({ model: "gemini/gemini-flash-latest", own_model: "gemini/gemini-flash-latest", cloud: true })] })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: /^Model:/ }))
    expect(await screen.findByRole("menuitem", { name: "Use the default (ollama/gemma4:e4b)" })).toBeTruthy()
  })

  it("opens a job's model menu below its row", async () => {
    stub()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: /^Model:/ }))
    await screen.findByRole("menuitem", { name: /Gemini Flash/ })
    expect(screen.getByRole("menu").getAttribute("data-side")).toBe("bottom")
  })

  it("keeps the row as it was and says why when the model is refused", async () => {
    stub({ putModel: () => res({ detail: "Pick a model from the list." }, false) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: /^Model:/ }))
    fireEvent.click(await screen.findByRole("menuitem", { name: /Gemini Flash/ }))
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith("Pick a model from the list."))
    expect(screen.getByRole("button", { name: /^Model:/ }).getAttribute("data-tier")).toBe("local")
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
    fireEvent.click(await screen.findByRole("button", { name: "Actions for weekly" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Open in the editor" }))
    expect(onOpen).toHaveBeenCalledExactlyOnceWith("jobs/weekly.md")
  })

  it("renames a job from its menu: the field takes the new name, Enter asks, the row and the editor follow", async () => {
    const renamed = job({ name: "weekly-review", file: "jobs/weekly-review.md" })
    stub({ rename: res({ job: renamed }) })
    const onRenamed = vi.fn()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} onRenamed={onRenamed} />)
    fireEvent.click(await screen.findByRole("button", { name: "Actions for weekly" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const field = (await screen.findByLabelText("New name for weekly")) as HTMLInputElement
    expect(field.value).toBe("weekly")
    fireEvent.change(field, { target: { value: "Weekly review" } })
    fireEvent.keyDown(field, { key: "Enter" })

    expect(await screen.findByText("weekly-review")).toBeTruthy()
    expect(calls.at(-1)).toMatchObject({ url: "/api/personas/ada/jobs/weekly/rename", init: { method: "POST", body: JSON.stringify({ name: "Weekly review" }) } })
    expect(screen.queryByText("weekly")).toBeNull()
    expect(onRenamed).toHaveBeenCalledExactlyOnceWith("jobs/weekly.md", "jobs/weekly-review.md")
  })

  it("keeps the field open and says why when a rename is refused, and Esc leaves the name as it was", async () => {
    stub({ rename: res({ detail: "There is already a job called daily." }, false) })
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: "Actions for weekly" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const field = await screen.findByLabelText("New name for weekly")
    fireEvent.change(field, { target: { value: "daily" } })
    fireEvent.keyDown(field, { key: "Enter" })
    await waitFor(() => expect(notifyError).toHaveBeenCalledExactlyOnceWith("There is already a job called daily."))
    expect(screen.getByLabelText("New name for weekly")).toBeTruthy()
    fireEvent.keyDown(screen.getByLabelText("New name for weekly"), { key: "Escape" })
    expect(await screen.findByText("weekly")).toBeTruthy()
    expect(screen.queryByLabelText("New name for weekly")).toBeNull()
  })

  it("asks nothing of the backend when the name is left as it was", async () => {
    stub()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
    fireEvent.click(await screen.findByRole("button", { name: "Actions for weekly" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
    fireEvent.keyDown(await screen.findByLabelText("New name for weekly"), { key: "Enter" })
    await waitFor(() => expect(screen.queryByLabelText("New name for weekly")).toBeNull())
    expect(calls.some((c) => c.url.endsWith("/rename"))).toBe(false)
  })

  it("asks before deleting, then the row goes and the editor is told", async () => {
    stub({ list: [job(), job({ name: "daily", file: "jobs/daily.md" })] })
    const onRemoved = vi.fn()
    render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} onRemoved={onRemoved} />)
    fireEvent.click(await screen.findByRole("button", { name: "Actions for weekly" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(calls.some((c) => c.init?.method === "DELETE")).toBe(false) // asked, not done

    await confirmMock.mock.calls[0][0].onConfirm()

    await waitFor(() => expect(screen.queryByText("weekly")).toBeNull())
    expect(screen.getByText("daily")).toBeTruthy()
    expect(calls.at(-1)).toMatchObject({ url: "/api/personas/ada/jobs/weekly", init: { method: "DELETE" } })
    expect(onRemoved).toHaveBeenCalledExactlyOnceWith("jobs/weekly.md")
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

    it("ignores a second click while the first change is still being made", async () => {
      let answer!: (r: Response) => void
      const pending = new Promise<Response>((resolve) => (answer = resolve))
      stub({ schedule: { supported: true, installed: false }, putSchedule: () => pending as unknown as Response })
      render(<JobsRows persona="ada" personaName="Ada" onOpen={vi.fn()} />)
      await screen.findByText("Run while Sympose is closed")
      const group = screen.getByRole("radiogroup", { name: "Run jobs while Sympose is closed" })
      fireEvent.click(group.querySelector('[role="radio"]:first-child')!) // On
      await waitFor(() => expect(group.querySelector('[role="radio"]:last-child')!.hasAttribute("disabled")).toBe(true))
      fireEvent.click(group.querySelector('[role="radio"]:last-child')!) // Off, too soon
      answer(res({ supported: true, installed: true }))
      await waitFor(() => expect(state()).toBe("On"))
      expect(calls.filter((c) => c.url === "/api/schedule" && c.init?.method === "PUT")).toHaveLength(1)
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
